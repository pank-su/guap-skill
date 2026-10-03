from __future__ import annotations
import http.cookiejar
import json
import sys
import tempfile
import unittest
import urllib.parse
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/guap-pro/scripts'
sys.path.insert(0, str(SCRIPTS))
from test_session_store import sample_cookie

PROFILE = "<title>Личный кабинет ГУАП</title><a href='/logout'>Выйти</a>"
STATE = 'example-state-value-long-enough'

class SilentSSOTests(unittest.TestCase):
    def module(self):
        self.assertTrue((SCRIPTS / 'session_client.py').exists(), 'Silent SSO client is missing')
        import session_client
        return session_client

    def permit(self, root):
        root.mkdir(mode=0o700, exist_ok=True)
        path = root / 'renewal-permit.json'
        path.write_text(json.dumps({'version': 1, 'enabled': True,
            'scope': ['silent_sso', 'background_sso'], 'approved_at': '2026-10-03T10:00:00+03:00'}))
        path.chmod(0o600)

    def test_background_success_is_quiet(self):
        import datetime as dt
        module = self.module()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'session'; self.permit(root)
            store = module.SessionStore(root)
            with store.locked():
                jar = http.cookiejar.CookieJar(); jar.set_cookie(sample_cookie('KEYCLOAK_IDENTITY', 'example-sso', 'sso.guap.ru', '/realms/master/'))
                store.save(jar, 'a' * 32)
            count = []
            auth = module.SSO + module.AUTH_PATH + '?' + urllib.parse.urlencode({'state': STATE, 'response_type': 'code', 'client_id': 'example', 'redirect_uri': module.PRO + '/oauth/callback'})
            callback = module.PRO + '/oauth/callback?' + urllib.parse.urlencode({'state': STATE, 'code': 'example-code'})
            def transport(url, jar, deadline, **kwargs):
                count.append(url)
                if len(count) == 1: return module.WireResponse(302, {'Location': auth}, '')
                if len(count) == 2: return module.WireResponse(302, {'Location': callback}, '')
                if len(count) == 3:
                    jar.set_cookie(sample_cookie()); return module.WireResponse(302, {'Location': module.PRO + '/inside/profile'}, '')
                return module.WireResponse(200, {}, PROFILE)
            now = dt.datetime(2026, 10, 3, 14, tzinfo=dt.timezone(dt.timedelta(hours=3)))
            self.assertEqual(module.background_tick(store, transport=transport, now=now), '')
            with store.locked():
                self.assertEqual(module.read_state(store)['status'], 'ok')
            self.assertEqual(len(count), 4)

    def test_background_entrypoint_is_quiet_without_a_grant(self):
        import os, shutil, subprocess
        entry = SCRIPTS / 'renew_background.py'
        self.assertTrue(entry.exists(), 'Deterministic background entrypoint is missing')
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            shutil.copytree(SCRIPTS, home / 'skills' / 'guap-pro' / 'scripts', ignore=shutil.ignore_patterns('__pycache__'))
            result = subprocess.run([sys.executable, str(entry)], capture_output=True, text=True,
                                    env={**os.environ, 'HERMES_HOME': str(home)}, timeout=10)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout, '')
            self.assertEqual(result.stderr, '')

    def test_legacy_read_never_sends_sso_identity_to_the_cabinet(self):
        module = self.module()
        with tempfile.TemporaryDirectory() as temporary:
            store = module.SessionStore(Path(temporary) / 'session')
            calls = []
            with store.locked():
                store.write('cookie.txt', 'PHPSESSID=example-pro; KEYCLOAK_IDENTITY=example-sso')
                def transport(url, jar, deadline, **kwargs):
                    calls.append((url, kwargs))
                    return module.WireResponse(200, {}, PROFILE)
                self.assertEqual(module.SessionClient(store, transport=transport).get(module.PRO + '/inside/profile'), PROFILE)
                self.assertIsNone(store.read('cookies.json', optional=True))
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0][1].get('cabinet_header'), 'PHPSESSID=example-pro')

    def test_interactive_html_never_reaches_callback_or_changes_saved_cookies(self):
        module = self.module()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'session'; self.permit(root)
            store = module.SessionStore(root)
            with store.locked():
                jar = http.cookiejar.CookieJar(); jar.set_cookie(sample_cookie('KEYCLOAK_IDENTITY', 'example-sso', 'sso.guap.ru', '/realms/master/'))
                store.save(jar, 'a' * 32)
                before = store.read('cookies.json')
                calls = []
                auth = module.SSO + module.AUTH_PATH + '?' + urllib.parse.urlencode({'state': STATE, 'response_type': 'code', 'client_id': 'example', 'redirect_uri': module.PRO + '/oauth/callback'})
                def transport(url, jar, deadline, **kwargs):
                    calls.append(url)
                    if len(calls) == 1:
                        return module.WireResponse(302, {'Location': auth}, '')
                    return module.WireResponse(200, {}, '<html>captcha or one-time confirmation</html>')
                with self.assertRaisesRegex(module.SessionError, 'reauth_required'):
                    module.SessionClient(store, transport=transport).silent_renew()
                self.assertEqual(store.read('cookies.json'), before)
                self.assertEqual(len(calls), 2)

    def test_invalid_callback_and_revocation_never_consume_code(self):
        module = self.module()
        for mode in ('state', 'origin', 'port', 'duplicate', 'revocation', 'verification'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary) / 'session'; self.permit(root)
                store = module.SessionStore(root)
                with store.locked():
                    jar = http.cookiejar.CookieJar(); jar.set_cookie(sample_cookie('KEYCLOAK_IDENTITY', 'example-sso', 'sso.guap.ru', '/realms/master/'))
                    store.save(jar, 'a' * 32); before = store.read('cookies.json')
                    calls = []
                    auth = module.SSO + module.AUTH_PATH + '?' + urllib.parse.urlencode({'state': STATE, 'response_type': 'code', 'client_id': 'example', 'redirect_uri': module.PRO + '/oauth/callback'})
                    callback = module.PRO + '/oauth/callback?' + urllib.parse.urlencode({'state': 'mismatch' if mode == 'state' else STATE, 'code': 'example-code'})
                    if mode == 'origin': callback = callback.replace(module.PRO, 'https://evil.example')
                    if mode == 'port': callback = callback.replace(module.PRO, module.PRO + ':444')
                    if mode == 'duplicate': callback += '&state=' + STATE
                    def transport(url, jar, deadline, **kwargs):
                        calls.append(url)
                        if len(calls) == 1: return module.WireResponse(302, {'Location': auth}, '')
                        if len(calls) == 2:
                            if mode == 'revocation':
                                payload = json.loads((root / 'renewal-permit.json').read_text()); payload['enabled'] = False
                                (root / 'renewal-permit.json').write_text(json.dumps(payload))
                            return module.WireResponse(302, {'Location': callback}, '')
                        return module.WireResponse(200, {}, '<title>Public page</title>')
                    with self.assertRaises(module.SessionError):
                        module.SessionClient(store, transport=transport).silent_renew()
                    self.assertEqual(store.read('cookies.json'), before)
                    if mode != 'verification': self.assertEqual(len(calls), 2)

    def test_real_cookie_processor_scopes_and_rotates_response_cookies(self):
        import email.message, io, time, urllib.request, urllib.response
        from unittest.mock import patch
        module = self.module()
        import session_store
        calls = []
        class FakeHTTPS(urllib.request.HTTPSHandler):
            def https_open(self, request):
                calls.append((request.full_url, request.get_header('Cookie', '')))
                headers = email.message.Message()
                if len(calls) == 1: headers.add_header('Set-Cookie', 'PHPSESSID=wire-rotation; Path=/; Secure; HttpOnly')
                else: headers.add_header('Set-Cookie', 'KEYCLOAK_IDENTITY=deleted; Path=/realms/master/; Secure; Max-Age=0')
                response = urllib.response.addinfourl(io.BytesIO(b'example'), headers, request.full_url, 200)
                response.msg = 'OK'
                return response
        original = urllib.request.build_opener
        def build(*handlers): return original(FakeHTTPS(), *handlers)
        jar = session_store.new_jar(); jar.set_cookie(sample_cookie()); jar.set_cookie(sample_cookie('KEYCLOAK_IDENTITY', 'example-sso', 'sso.guap.ru', '/realms/master/'))
        with patch.object(urllib.request, 'build_opener', side_effect=build):
            module.wire(module.PRO + '/inside/profile', jar, time.monotonic() + 5)
            module.wire(module.SSO + module.AUTH_PATH, jar, time.monotonic() + 5)
        self.assertNotIn('KEYCLOAK', calls[0][1]); self.assertNotIn('PHPSESSID', calls[1][1])
        self.assertEqual(next(c for c in jar if c.name == 'PHPSESSID').value, 'wire-rotation')
        self.assertFalse(any(c.name == 'KEYCLOAK_IDENTITY' for c in jar))

    def test_background_interaction_notice_is_once_and_then_stops_requests(self):
        import datetime as dt
        module = self.module()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'session'
            self.permit(root)
            store = module.SessionStore(root)
            with store.locked():
                jar = http.cookiejar.CookieJar()
                jar.set_cookie(sample_cookie('KEYCLOAK_IDENTITY', 'example-sso', 'sso.guap.ru', '/realms/master/'))
                store.save(jar, 'a' * 32)
            calls = []
            auth = module.SSO + module.AUTH_PATH + '?' + urllib.parse.urlencode({'state': STATE,
                'response_type': 'code', 'client_id': 'example', 'redirect_uri': module.PRO + '/oauth/callback'})
            callback = module.PRO + '/oauth/callback?' + urllib.parse.urlencode({'state': STATE, 'error': 'login_required'})
            def transport(url, jar, deadline, **kwargs):
                calls.append(url)
                return module.WireResponse(302, {'Location': auth if len(calls) == 1 else callback}, '')
            now = dt.datetime(2026, 10, 3, 14, tzinfo=dt.timezone(dt.timedelta(hours=3)))
            first = module.background_tick(store, transport=transport, now=now)
            second = module.background_tick(store, transport=transport, now=now)
            self.assertIn('🔐', first)
            self.assertEqual(second, '')
            self.assertEqual(len(calls), 2)
            self.assertNotIn('example-sso', first)
            night = now.replace(hour=23)
            self.assertEqual(module.background_tick(store, transport=transport, now=night), '')
            self.assertEqual(len(calls), 2)

    def test_missing_or_overbroad_grants_do_not_touch_credentials_or_network(self):
        from unittest.mock import patch
        module = self.module()
        for payload in (None, [], {'version': 1, 'enabled': True, 'scope': ['silent_sso', 'background_sso', 'upload'], 'approved_at': '2026-10-03T10:00:00+03:00'}):
            with self.subTest(payload=payload), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary) / 'session'
                root.mkdir(mode=0o700)
                if payload is not None:
                    path = root / 'renewal-permit.json'
                    path.write_text(json.dumps(payload)); path.chmod(0o600)
                store = module.SessionStore(root)
                with store.locked(), patch.object(store, 'load') as load, patch.object(module, 'wire') as transport:
                    client = module.SessionClient(store)
                    with self.assertRaises(module.SessionError):
                        client.silent_renew()
                    load.assert_not_called()
                    transport.assert_not_called()

    def test_unknown_permit_fields_fail_closed_before_session_load(self):
        from unittest.mock import patch
        module = self.module()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'session'
            self.permit(root)
            permit = json.loads((root / 'renewal-permit.json').read_text())
            permit['unexpected'] = True
            (root / 'renewal-permit.json').write_text(json.dumps(permit))
            store = module.SessionStore(root)
            with store.locked(), patch.object(store, 'load', side_effect=AssertionError('credential read')), patch.object(module, 'wire', side_effect=AssertionError('network')):
                with self.assertRaisesRegex(module.SessionError, 'renewal_not_permitted'):
                    module.SessionClient(store).silent_renew()


    def test_expired_cabinet_recovers_once_through_sso(self):
        module = self.module()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'session'
            self.permit(root)
            store = module.SessionStore(root)
            with store.locked():
                jar = http.cookiejar.CookieJar()
                jar.set_cookie(sample_cookie('KEYCLOAK_IDENTITY', 'example-sso', 'sso.guap.ru', '/realms/master/'))
                store.save(jar, 'a' * 32)
                calls = []
                auth = module.SSO + module.AUTH_PATH + '?' + urllib.parse.urlencode({'state': STATE,
                    'response_type': 'code', 'client_id': 'example', 'redirect_uri': module.PRO + '/oauth/callback'})
                callback = module.PRO + '/oauth/callback?' + urllib.parse.urlencode({'state': STATE, 'code': 'example-code'})
                def transport(url, jar, deadline, **kwargs):
                    calls.append(url)
                    if len(calls) == 1:
                        return module.WireResponse(302, {'Location': module.PRO + '/oauth/login'}, '')
                    if len(calls) == 2:
                        return module.WireResponse(302, {'Location': auth}, '')
                    if len(calls) == 3:
                        return module.WireResponse(302, {'Location': callback}, '')
                    if len(calls) == 4:
                        jar.set_cookie(sample_cookie(value='new-example'))
                        return module.WireResponse(302, {'Location': module.PRO + '/inside/profile'}, '')
                    return module.WireResponse(200, {}, PROFILE)
                client = module.SessionClient(store, transport=transport)
                self.assertEqual(client.get(module.PRO + '/inside/profile'), PROFILE)
            self.assertEqual(len(calls), 6)
            self.assertEqual(sum('/oauth/login' in u for u in calls), 1)

    def test_cabinet_reads_keep_cookie_rotation_without_touching_sso(self):
        module = self.module()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'session'
            self.permit(root)
            store = module.SessionStore(root)
            calls = []
            with store.locked():
                initial = http.cookiejar.CookieJar()
                initial.set_cookie(sample_cookie())
                store.save(initial, 'a' * 32)
                def transport(url, jar, deadline, **kwargs):
                    calls.append(url)
                    jar.set_cookie(sample_cookie(value='rotated-example'))
                    return module.WireResponse(200, {}, PROFILE)
                client = module.SessionClient(store, transport=transport)
                self.assertEqual(client.get(module.PRO + '/inside/profile'), PROFILE)
                jar, generation = store.load()
            self.assertEqual(calls, [module.PRO + '/inside/profile'])
            self.assertEqual(next(iter(jar)).value, 'rotated-example')
            self.assertEqual(generation, 'a' * 32)

    def test_silent_flow_validates_state_and_verifies_profile_before_saving(self):
        module = self.module()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'session'
            self.permit(root)
            store = module.SessionStore(root)
            with store.locked():
                initial = http.cookiejar.CookieJar()
                initial.set_cookie(sample_cookie('KEYCLOAK_IDENTITY', 'example-old-sso', 'sso.guap.ru', '/realms/master/'))
                store.save(initial, 'a' * 32)
            calls = []
            auth = module.SSO + '/realms/master/protocol/openid-connect/auth?' + urllib.parse.urlencode({
                'state': STATE, 'response_type': 'code', 'client_id': 'example-cabinet',
                'redirect_uri': module.PRO + '/oauth/callback', 'scope': 'openid'})
            callback = module.PRO + '/oauth/callback?' + urllib.parse.urlencode({'state': STATE, 'code': 'example-code'})
            def transport(url, jar, deadline, **kwargs):
                calls.append(url)
                if len(calls) == 1:
                    return module.WireResponse(302, {'Location': auth}, '')
                if len(calls) == 2:
                    self.assertEqual(urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)['prompt'], ['none'])
                    jar.set_cookie(sample_cookie('KEYCLOAK_IDENTITY', 'example-new-sso', 'sso.guap.ru', '/realms/master/'))
                    return module.WireResponse(302, {'Location': callback}, '')
                if len(calls) == 3:
                    jar.set_cookie(sample_cookie())
                    return module.WireResponse(302, {'Location': module.PRO + '/inside/profile'}, '')
                return module.WireResponse(200, {}, PROFILE)
            with store.locked():
                client = module.SessionClient(store, transport=transport)
                client.silent_renew()
                jar, generation = store.load()
            self.assertTrue(generation)
            self.assertEqual(len(calls), 4)
            self.assertTrue((root / 'cookies.json').exists())
            self.assertNotIn('example-code', (root / 'cookies.json').read_text())
            self.assertEqual({c.name for c in jar}, {'PHPSESSID', 'KEYCLOAK_IDENTITY'})

if __name__ == '__main__':
    unittest.main()
