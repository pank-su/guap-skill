#!/usr/bin/env python3
"""Bounded GUAP silent OAuth login. No passwords or token endpoint access."""
from __future__ import annotations

import datetime as dt
import copy
import http.cookies
import json
import re
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser

from session_store import PRO, SSO, SessionError, SessionStore, exact_origin, new_jar

AUTH_PATH = '/realms/master/protocol/openid-connect/auth'
CALLBACK_PATH = '/oauth/callback'
SCOPE = ['silent_sso', 'background_sso']
USER_AGENT = 'Mozilla/5.0 Hermes GUAP session client'

@dataclass
class WireResponse:
    status: int
    headers: object
    body: str

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

class PageMarkers(HTMLParser):
    def __init__(self):
        super().__init__()
        self.password = False
        self.logout = False
        self.in_title = False
        self.title = ''
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'input' and (attrs.get('type') or '').lower() == 'password':
            self.password = True
        if tag == 'a' and attrs.get('href') in ('/logout', PRO + '/logout'):
            self.logout = True
        if tag == 'title':
            self.in_title = True
    def handle_endtag(self, tag):
        if tag == 'title':
            self.in_title = False
    def handle_data(self, data):
        if self.in_title:
            self.title += data

def markers(body):
    p = PageMarkers()
    p.feed(body)
    return p

def verified_profile(response):
    p = markers(response.body)
    return response.status == 200 and p.logout and not p.password and 'Личный кабинет ГУАП' in p.title


def wire(url, jar, deadline, *, legacy_header=None, cabinet_header=None):
    exact_origin(url)
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise SessionError('session_request_timeout')
    headers = {'User-Agent': USER_AGENT, 'Accept': 'text/html,application/xhtml+xml'}
    if legacy_header:
        if exact_origin(url) != SSO or urllib.parse.urlsplit(url).path != AUTH_PATH:
            raise SessionError('legacy_identity_origin_blocked')
        headers['Cookie'] = legacy_header
    if cabinet_header:
        if exact_origin(url) != PRO or not urllib.parse.urlsplit(url).path.startswith('/inside/'):
            raise SessionError('legacy_cabinet_origin_blocked')
        headers['Cookie'] = cabinet_header
    request = urllib.request.Request(url, headers=headers, method='GET')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect(), urllib.request.HTTPCookieProcessor(jar))
    try:
        try:
            response = opener.open(request, timeout=min(15, remaining))
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            body = response.read(2_000_001)
            if len(body) > 2_000_000:
                raise SessionError('session_response_too_large')
            return WireResponse(response.code, response.headers, body.decode('utf-8', 'replace'))
    except (urllib.error.URLError, TimeoutError, OSError):
        raise SessionError('session_network_failed') from None


def renewal_permitted(store):
    raw = store.read('renewal-permit.json', optional=True)
    if raw is None:
        return False
    try:
        permit = json.loads(raw)
        if not isinstance(permit, dict) or set(permit) != {'version', 'enabled', 'scope', 'approved_at'}:
            return False
        approved = dt.datetime.fromisoformat(permit['approved_at'])
        return (type(permit.get('version')) is int and permit['version'] == 1
                and permit.get('enabled') is True and permit.get('scope') == SCOPE
                and approved.tzinfo is not None)
    except (ValueError, TypeError, KeyError, AttributeError):
        return False


def legacy_cabinet_header(raw):
    try:
        parsed = http.cookies.SimpleCookie(raw or '')
        pairs = []
        for name in ('PHPSESSID', 'last_visit_page', 'sharedsessioID'):
            if name in parsed:
                value = parsed[name].value
                if len(value) > 32768 or any(ord(c) < 33 or ord(c) > 126 or c in ';"\\' for c in value):
                    raise ValueError
                pairs.append(name + '=' + value)
        if not pairs:
            raise ValueError
        return '; '.join(pairs)
    except (ValueError, http.cookies.CookieError):
        raise SessionError('reauth_required') from None


def read_state(store):
    raw = store.read('renewal-state.json', optional=True)
    if raw is None:
        return {}
    try:
        state = json.loads(raw)
        if (not isinstance(state, dict) or state.get('status') not in {'ok', 'error', 'reauth_required'}
                or type(state.get('notified')) is not bool
                or (state.get('generation') is not None and not re.fullmatch('[a-f0-9]{32}', state['generation']))):
            raise ValueError
        return state
    except (ValueError, TypeError, KeyError):
        raise SessionError('invalid_renewal_state') from None


def record_failure(store, generation, error, *, notified=False):
    code = str(error)
    if not re.fullmatch('[a-z_]{1,64}', code):
        code = 'session_renewal_failed'
    previous = read_state(store)
    state = {'status': 'reauth_required' if code == 'reauth_required' else 'error',
             'code': code, 'generation': generation, 'notified': notified}
    if previous.get('last_success_at'):
        state['last_success_at'] = previous['last_success_at']
    store.write('renewal-state.json', json.dumps(state))
    return code


class SessionClient:
    def __init__(self, store, transport=None, deadline=None):
        self.store = store
        self.transport = transport or wire
        self.deadline = deadline if deadline is not None else time.monotonic() + 28
        self.jar = None
        self.generation = None

    def load(self):
        self.jar, self.generation = self.store.load()

    def step(self, url, **kwargs):
        exact_origin(url)
        if time.monotonic() >= self.deadline:
            raise SessionError('session_request_timeout')
        return self.transport(url, self.jar, self.deadline, **kwargs)

    def require_grant(self):
        if not renewal_permitted(self.store):
            raise SessionError('renewal_not_permitted')

    def legacy_identity(self):
        raw = self.store.read('cookie.txt', optional=True)
        if not raw:
            raise SessionError('reauth_required')
        try:
            parsed = http.cookies.SimpleCookie(raw)
            # Bootstrap only the known SSO identity cookies into a fresh login;
            # never import arbitrary legacy cookies or guessed domain metadata.
            pairs = []
            for name in ('KEYCLOAK_IDENTITY', 'KEYCLOAK_IDENTITY_LEGACY'):
                if name in parsed:
                    value = parsed[name].value
                    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,32768}', value):
                        raise ValueError
                    pairs.append(name + '=' + value)
            if not pairs:
                raise ValueError
            return '; '.join(pairs)
        except (ValueError, http.cookies.CookieError):
            raise SessionError('reauth_required') from None

    @staticmethod
    def redirect(url, response):
        if response.status not in (301, 302, 303, 307, 308):
            raise SessionError('unexpected_auth_response')
        location = response.headers.get('Location', '')
        if not isinstance(location, str) or not location:
            raise SessionError('missing_auth_redirect')
        destination = urllib.parse.urljoin(url, location)
        exact_origin(destination)
        return destination

    def fetch_cabinet(self, url, *, legacy_header=None):
        current = url
        for _ in range(6):
            if exact_origin(current) != PRO or not urllib.parse.urlsplit(current).path.startswith('/inside/'):
                raise SessionError('reauth_required')
            response = self.step(current, cabinet_header=legacy_header)
            if response.status in (301, 302, 303, 307, 308):
                current = self.redirect(current, response)
                continue
            if response.status in (401, 403):
                raise SessionError('reauth_required')
            if response.status != 200:
                raise SessionError('cabinet_http_failed')
            page = markers(response.body)
            if page.password or 'вход в личный кабинет' in page.title.lower():
                raise SessionError('reauth_required')
            if not page.logout:
                raise SessionError('unverified_cabinet_response')
            return response.body
        raise SessionError('cabinet_redirect_limit')

    def get(self, url):
        if exact_origin(url) != PRO or not urllib.parse.urlsplit(url).path.startswith('/inside/'):
            raise SessionError('unexpected_cabinet_target')
        self.load()
        try:
            legacy = None
            if self.generation is None:
                import os
                legacy = legacy_cabinet_header(os.environ.get('GUAP_COOKIE') or self.store.read('cookie.txt', optional=True))
            body = self.fetch_cabinet(url, legacy_header=legacy)
        except SessionError as exc:
            if str(exc) != 'reauth_required' or not renewal_permitted(self.store):
                raise
            previous = read_state(self.store)
            if previous.get('status') == 'reauth_required' and previous.get('generation') == self.generation:
                raise SessionError('reauth_required') from None
            try:
                self.silent_renew()
            except SessionError as failure:
                record_failure(self.store, self.generation, failure)
                raise
            body = self.fetch_cabinet(url)
        if self.generation is not None:
            self.store.save(self.jar, self.generation)
        return body

    def silent_renew(self):
        self.require_grant()
        self.load()
        legacy = self.legacy_identity() if self.generation is None else None
        # Retain SSO but create fresh application state; never replay stale
        # last_visit_page or import arbitrary legacy domain metadata.
        fresh = new_jar()
        for cookie in self.jar:
            if cookie.domain.lstrip('.') == 'sso.guap.ru':
                fresh.set_cookie(copy.copy(cookie))
        self.jar = fresh
        start = PRO + '/oauth/login'
        auth = self.redirect(start, self.step(start))
        p = urllib.parse.urlsplit(auth)
        q = urllib.parse.parse_qs(p.query, keep_blank_values=True)
        if (exact_origin(auth) != SSO or p.path != AUTH_PATH
                or any(len(values) != 1 for values in q.values())
                or q.get('response_type') != ['code']
                or q.get('redirect_uri') != [PRO + CALLBACK_PATH]
                or not q.get('client_id') or not q['client_id'][0]
                or not q.get('state') or not 16 <= len(q['state'][0]) <= 4096
                or 'offline_access' in q.get('scope', [''])[0].split()):
            raise SessionError('invalid_oauth_request')
        state = q['state'][0]
        q['prompt'] = ['none']
        auth = urllib.parse.urlunsplit((p.scheme, p.netloc, p.path, urllib.parse.urlencode(q, doseq=True), ''))
        self.require_grant()
        response = self.step(auth, legacy_header=legacy)
        if response.status == 200:
            # Password, OTP, CAPTCHA, consent and JS-only challenges all require
            # user interaction; never follow/submit an interactive step silently.
            raise SessionError('reauth_required')
        callback = self.redirect(auth, response)
        p = urllib.parse.urlsplit(callback)
        if exact_origin(callback) == SSO and p.path.startswith('/realms/master/login-actions/'):
            raise SessionError('reauth_required')
        q = urllib.parse.parse_qs(p.query, keep_blank_values=True)
        if (exact_origin(callback) != PRO or p.path != CALLBACK_PATH
                or any(len(values) != 1 for values in q.values())
                or not q.get('state') or not secrets.compare_digest(q['state'][0], state)):
            raise SessionError('invalid_oauth_callback')
        if q.get('error'):
            raise SessionError('reauth_required')
        if not q.get('code') or not 1 <= len(q['code'][0]) <= 32768:
            raise SessionError('invalid_oauth_callback')
        if q.get('iss') and q['iss'] != [SSO + '/realms/master']:
            raise SessionError('invalid_oauth_callback')
        self.require_grant()
        current = callback
        response = self.step(current)
        for _ in range(5):
            if response.status not in (301, 302, 303, 307, 308):
                break
            current = self.redirect(current, response)
            p = urllib.parse.urlsplit(current)
            if exact_origin(current) != PRO or p.path not in {'/inside/profile', '/inside', '/inside/', '/'}:
                raise SessionError('unexpected_callback_destination')
            response = self.step(current)
        else:
            raise SessionError('auth_redirect_limit')
        if urllib.parse.urlsplit(current).path != '/inside/profile':
            response = self.step(PRO + '/inside/profile')
        if not verified_profile(response):
            raise SessionError('reauth_required')
        self.require_grant()
        self.generation = secrets.token_hex(16)
        self.store.save(self.jar, self.generation)
        self.store.write('renewal-state.json', json.dumps({'status': 'ok', 'generation': self.generation,
            'last_success_at': dt.datetime.now(dt.timezone.utc).isoformat(), 'notified': False}))


def background_tick(store=None, *, transport=None, now=None):
    now = now or dt.datetime.now().astimezone()
    if not 8 <= now.hour < 23:
        return ''
    store = store or SessionStore()
    try:
        with store.locked():
            if not renewal_permitted(store):
                return ''
            client = SessionClient(store, transport=transport)
            client.load()
            previous = read_state(store)
            blocked = (previous.get('status') == 'reauth_required'
                       and previous.get('generation') == client.generation)
            if blocked:
                if previous.get('notified'):
                    return ''
                previous['notified'] = True
                store.write('renewal-state.json', json.dumps(previous))
                return '🔐 ГУАП требует повторного входа. Тихое продление остановлено; пароль не сохраняется.'
            try:
                client.silent_renew()
            except SessionError as error:
                code = str(error) if re.fullmatch('[a-z_]{1,64}', str(error)) else 'session_renewal_failed'
                repeated = (previous.get('code') == code and previous.get('generation') == client.generation
                            and previous.get('notified'))
                record_failure(store, client.generation, error, notified=True)
                if repeated:
                    return ''
                if code == 'reauth_required':
                    return '🔐 ГУАП требует повторного входа. Тихое продление остановлено; пароль не сохраняется.'
                return '⚠️ Не удалось тихо продлить сессию ГУАП: ' + code
            return ''
    except SessionError:
        # An unsafe/missing capability or busy/private store is never a reason
        # to read more credentials, start a relay or repeatedly notify the user.
        return ''
