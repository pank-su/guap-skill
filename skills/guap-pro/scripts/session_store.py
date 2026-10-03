#!/usr/bin/env python3
"""Private domain-aware GUAP cookie persistence (POSIX, stdlib only)."""
from __future__ import annotations

import contextlib
import http.cookiejar
import json
import os
import re
import secrets
import stat
import time
import urllib.parse
import urllib.request
from pathlib import Path

PRO = 'https://pro.guap.ru'
SSO = 'https://sso.guap.ru'
COOKIE_FIELDS = ('version', 'name', 'value', 'port', 'port_specified', 'domain',
                 'domain_specified', 'domain_initial_dot', 'path', 'path_specified',
                 'secure', 'expires', 'discard', 'comment', 'comment_url',
                 'rfc2109')

class SessionError(RuntimeError):
    """Messages must contain only fixed, credential-free categories."""


def root_path() -> Path:
    return Path(os.environ.get('HERMES_HOME', str(Path.home() / '.hermes'))).expanduser() / 'guap-pro'


def exact_origin(url: str) -> str:
    try:
        p = urllib.parse.urlsplit(url)
        if any(ord(c) < 33 or ord(c) == 127 for c in url):
            raise ValueError
        if p.scheme != 'https' or p.netloc not in {'pro.guap.ru', 'sso.guap.ru', 'pro.guap.ru:443', 'sso.guap.ru:443'}:
            raise ValueError
        if p.username is not None or p.password is not None or p.port not in (None, 443) or p.fragment:
            raise ValueError
        return 'https://' + p.hostname
    except (ValueError, TypeError):
        raise SessionError('unexpected_origin_blocked') from None


def validate_cookie(c: http.cookiejar.Cookie):
    domain = c.domain.lstrip('.')
    if domain not in {'pro.guap.ru', 'sso.guap.ru', 'guap.ru'} or c.secure is not True:
        raise SessionError('unsafe_cookie_scope')
    if domain == 'guap.ru' and (c.name != 'sharedsessioID' or not c.domain_specified):
        raise SessionError('unsafe_cookie_scope')
    if c.name.startswith(('KEYCLOAK_', 'AUTH_SESSION_ID', 'KC_')) and domain != 'sso.guap.ru':
        raise SessionError('unsafe_cookie_scope')
    if c.name == 'PHPSESSID' and domain != 'pro.guap.ru':
        raise SessionError('unsafe_cookie_scope')
    if c.version not in (0, 1) or c.port_specified or c.port is not None:
        raise SessionError('unsafe_cookie_scope')
    if not isinstance(c.name, str) or not re.fullmatch(r'[A-Za-z0-9_!#$%&*+.^`|~-]{1,128}', c.name):
        raise SessionError('invalid_cookie')
    if not isinstance(c.value, str) or len(c.value) > 32768 or any(ord(x) < 32 or ord(x) > 126 or x == ';' for x in c.value):
        raise SessionError('invalid_cookie')
    if not isinstance(c.path, str) or not c.path.startswith('/') or len(c.path) > 1024 or any(ord(x) < 32 for x in c.path):
        raise SessionError('invalid_cookie')
    if c.expires is not None and (isinstance(c.expires, bool) or not isinstance(c.expires, (int, float))):
        raise SessionError('invalid_cookie')


class ScopedPolicy(http.cookiejar.DefaultCookiePolicy):
    def set_ok(self, cookie, request):
        try:
            exact_origin(request.full_url)
            validate_cookie(cookie)
        except SessionError:
            return False
        return super().set_ok(cookie, request)

    def return_ok(self, cookie, request):
        try:
            exact_origin(request.full_url)
            validate_cookie(cookie)
        except SessionError:
            return False
        return super().return_ok(cookie, request)


def new_jar() -> http.cookiejar.CookieJar:
    policy = ScopedPolicy(
        strict_ns_domain=http.cookiejar.DefaultCookiePolicy.DomainStrictNonDomain)
    return http.cookiejar.CookieJar(policy=policy)


def header_for(jar: http.cookiejar.CookieJar, url: str) -> str:
    exact_origin(url)
    request = urllib.request.Request(url)
    jar.add_cookie_header(request)
    return request.get_header('Cookie', '')


def jar_from_cdp(entries):
    jar = new_jar()
    for item in entries:
        try:
            domain = item['domain']
            if domain.lstrip('.') not in {'pro.guap.ru', 'sso.guap.ru', 'guap.ru'}:
                continue
            expires = item.get('expires', -1)
            session = item.get('session', expires <= 0)
            rest = {}
            if item.get('httpOnly'):
                rest['HttpOnly'] = None
            if item.get('sameSite'):
                rest['SameSite'] = item['sameSite']
            c = http.cookiejar.Cookie(version=0, name=item['name'], value=item['value'],
                port=None, port_specified=False, domain=domain,
                domain_specified=domain.startswith('.'), domain_initial_dot=domain.startswith('.'),
                path=item.get('path', '/'), path_specified=True, secure=item.get('secure') is True,
                expires=None if session else int(expires), discard=session,
                comment=None, comment_url=None, rest=rest, rfc2109=False)
            validate_cookie(c)
            jar.set_cookie(c)
        except (ValueError, KeyError, TypeError, SessionError):
            continue
    return jar


class SessionStore:
    def __init__(self, root: Path | None = None):
        self.root = root if root is not None else root_path()
        self.fd = None

    @contextlib.contextmanager
    def locked(self, timeout: float = 4.0):
        if self.fd is not None:
            raise SessionError('nested_session_lock')
        if os.name != 'posix':
            raise SessionError('private_sessions_require_posix')
        import fcntl
        # Reject pre-existing symlink components, including the root.
        for component in [*reversed(self.root.absolute().parents), self.root.absolute()]:
            try:
                info = component.lstat()
            except FileNotFoundError:
                continue
            if not stat.S_ISDIR(info.st_mode):
                raise SessionError('unsafe_session_directory')
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        lock_fd = None
        acquired = False
        try:
            info = os.fstat(fd)
            if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
                raise SessionError('unsafe_session_directory')
            lock_fd = os.open('session.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600, dir_fd=fd)
            self._check_file(os.fstat(lock_fd))
            deadline = time.monotonic() + timeout
            while True:
                try:
                    fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    acquired = True
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise SessionError('session_busy') from None
                    time.sleep(0.025)
            self.fd = fd
            yield self
        except OSError:
            raise SessionError('private_session_io_failed') from None
        finally:
            self.fd = None
            if lock_fd is not None:
                if acquired:
                    fcntl.flock(lock_fd, fcntl.LOCK_UN)
                os.close(lock_fd)
            os.close(fd)

    @staticmethod
    def _check_file(info):
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1:
            raise SessionError('unsafe_private_file')

    def read(self, name: str, *, optional: bool = False) -> str | None:
        if self.fd is None or name not in {'cookies.json', 'cookie.txt', 'renewal-permit.json', 'renewal-state.json'}:
            raise SessionError('invalid_private_read')
        try:
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=self.fd)
        except FileNotFoundError:
            if optional:
                return None
            raise SessionError('private_file_missing') from None
        except OSError:
            raise SessionError('unsafe_private_file') from None
        with os.fdopen(fd, 'r', encoding='utf-8') as handle:
            info = os.fstat(handle.fileno())
            self._check_file(info)
            if info.st_size > 2_000_000:
                raise SessionError('private_file_too_large')
            return handle.read(2_000_001)

    def write(self, name: str, text: str):
        if self.fd is None or name not in {'cookies.json', 'cookie.txt', 'renewal-state.json'}:
            raise SessionError('invalid_private_write')
        try:
            info = os.stat(name, dir_fd=self.fd, follow_symlinks=False)
        except FileNotFoundError:
            info = None
        if info is not None:
            self._check_file(info)
        temporary = '.session-' + secrets.token_hex(16)
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=self.fd)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, name, src_dir_fd=self.fd, dst_dir_fd=self.fd)
            os.fsync(self.fd)
        finally:
            try:
                os.unlink(temporary, dir_fd=self.fd)
            except FileNotFoundError:
                pass

    def load(self):
        raw = self.read('cookies.json', optional=True)
        if raw is None:
            return new_jar(), None
        try:
            document = json.loads(raw)
            if document['version'] != 1 or not re.fullmatch('[a-f0-9]{32}', document['generation']):
                raise ValueError
            entries = document['cookies']
            if not isinstance(entries, list) or len(entries) > 100:
                raise ValueError
            jar = new_jar()
            identities = set()
            for entry in entries:
                if not isinstance(entry, dict) or set(entry) != set(COOKIE_FIELDS) | {'rest'}:
                    raise ValueError
                c = http.cookiejar.Cookie(**entry)
                validate_cookie(c)
                identity = (c.domain, c.path, c.name)
                if identity in identities:
                    raise ValueError
                identities.add(identity)
                jar.set_cookie(c)
            return jar, document['generation']
        except (ValueError, TypeError, KeyError, AttributeError):
            raise SessionError('invalid_cookie_store') from None

    def import_legacy(self, value):
        if not isinstance(value, str) or '\r' in value.strip() or '\n' in value.strip():
            raise SessionError('invalid_legacy_header')
        self.write('cookie.txt', value.strip())
        for name in ('cookies.json', 'renewal-state.json'):
            try:
                info = os.stat(name, dir_fd=self.fd, follow_symlinks=False)
            except FileNotFoundError:
                continue
            self._check_file(info)
            os.unlink(name, dir_fd=self.fd)

    def save(self, jar: http.cookiejar.CookieJar, generation: str):
        if not re.fullmatch('[a-f0-9]{32}', generation):
            raise SessionError('invalid_session_generation')
        jar.clear_expired_cookies()
        entries = []
        for c in jar:
            validate_cookie(c)
            entry = {key: getattr(c, key) for key in COOKIE_FIELDS}
            entry['rest'] = dict(c._rest)
            entries.append(entry)
        self.write('cookies.json', json.dumps({'version': 1, 'generation': generation, 'cookies': entries}, sort_keys=True))
        self.write('cookie.txt', header_for(jar, PRO + '/inside/profile'))
