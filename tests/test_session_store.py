from __future__ import annotations

import http.cookiejar
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'skills/guap-pro/scripts/session_store.py'

def sample_cookie(name='PHPSESSID', value='example-value', domain='pro.guap.ru', path='/'):
    return http.cookiejar.Cookie(version=0, name=name, value=value, port=None,
        port_specified=False, domain=domain, domain_specified=False,
        domain_initial_dot=False, path=path, path_specified=True, secure=True,
        expires=None, discard=True, comment=None, comment_url=None,
        rest={'HttpOnly': None, 'SameSite': 'lax'}, rfc2109=False)

class PersistenceTests(unittest.TestCase):
    def module(self):
        self.assertTrue(SCRIPT.exists(), 'Scoped private session persistence is missing')
        sys.path.insert(0, str(SCRIPT.parent))
        import session_store
        return session_store

    def test_legacy_import_invalidates_the_previous_snapshot(self):
        module = self.module()
        with tempfile.TemporaryDirectory() as temporary:
            store = module.SessionStore(Path(temporary) / 'session')
            with store.locked():
                jar = module.new_jar(); jar.set_cookie(sample_cookie()); store.save(jar, 'a' * 32)
                store.import_legacy('PHPSESSID=fresh-example')
                self.assertIsNone(store.read('cookies.json', optional=True))
                self.assertEqual(store.read('cookie.txt'), 'PHPSESSID=fresh-example')

    def test_browser_cookie_metadata_is_not_flattened(self):
        module = self.module()
        entries = [{'name': 'PHPSESSID', 'value': 'example-browser', 'domain': 'pro.guap.ru', 'path': '/', 'secure': True, 'httpOnly': True, 'session': True, 'expires': -1},
                   {'name': 'KEYCLOAK_IDENTITY', 'value': 'example-sso', 'domain': 'sso.guap.ru', 'path': '/realms/master/', 'secure': True, 'httpOnly': True, 'session': True, 'expires': -1},
                   {'name': 'unrelated', 'value': 'example-other', 'domain': 'unrelated.example', 'path': '/', 'secure': True, 'session': True, 'expires': -1}]
        jar = module.jar_from_cdp(entries)
        self.assertEqual({c.name for c in jar}, {'PHPSESSID', 'KEYCLOAK_IDENTITY'})
        self.assertNotIn('KEYCLOAK', module.header_for(jar, module.PRO + '/inside/profile'))

    def test_cookie_rotation_and_deletion_and_lock_exclusion(self):
        module = self.module()
        with tempfile.TemporaryDirectory() as temporary:
            store = module.SessionStore(Path(temporary) / 'session')
            with store.locked():
                jar = module.new_jar()
                jar.set_cookie(sample_cookie())
                jar.set_cookie(sample_cookie(value='rotation-example'))
                store.save(jar, 'a' * 32)
                self.assertIn('rotation-example', store.read('cookie.txt'))
                deleted = sample_cookie(value='deleted-example'); deleted.expires = 0
                jar.set_cookie(deleted)
                store.save(jar, 'a' * 32)
                self.assertEqual(store.read('cookie.txt'), '')
                with self.assertRaisesRegex(module.SessionError, 'session_busy'):
                    with module.SessionStore(store.root).locked(timeout=0.03):
                        self.fail('second writer entered the lock')

    def test_private_files_reject_symlinks_hardlinks_and_permissive_modes(self):
        import os
        module = self.module()
        for kind in ('symlink', 'hardlink', 'permissions'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary) / 'session'; root.mkdir(mode=0o700)
                target = Path(temporary) / 'target'; target.write_text('example'); target.chmod(0o600)
                path = root / 'cookie.txt'
                if kind == 'symlink':
                    path.symlink_to(target)
                elif kind == 'hardlink':
                    os.link(target, path)
                else:
                    path.write_text('example'); path.chmod(0o644)
                store = module.SessionStore(root)
                with store.locked(), self.assertRaises(module.SessionError):
                    store.read('cookie.txt')
                with store.locked(), self.assertRaises(module.SessionError):
                    store.write('cookie.txt', 'replacement')
                self.assertEqual(target.read_text(), 'example')

    def test_duplicate_cookie_records_are_rejected(self):
        import json
        module = self.module()
        with tempfile.TemporaryDirectory() as temporary:
            store = module.SessionStore(Path(temporary) / 'session')
            with store.locked():
                jar = module.new_jar(); jar.set_cookie(sample_cookie())
                store.save(jar, 'a' * 32)
                document = json.loads(store.read('cookies.json'))
                document['cookies'].append(dict(document['cookies'][0]))
                store.write('cookies.json', json.dumps(document))
                with self.assertRaises(module.SessionError):
                    store.load()

    def test_insecure_or_overbroad_cookies_cannot_be_persisted(self):
        module = self.module()
        for mutate in ('insecure', 'parent-domain', 'header-injection', 'wrong-sso-host'):
            with self.subTest(mutate=mutate), tempfile.TemporaryDirectory() as temporary:
                store = module.SessionStore(Path(temporary) / 'session')
                jar = module.new_jar()
                c = sample_cookie()
                if mutate == 'insecure':
                    c.secure = False
                elif mutate == 'parent-domain':
                    c.domain = '.guap.ru'
                    c.domain_specified = True
                elif mutate == 'header-injection':
                    c.value = 'example\r\nInjected: value'
                else:
                    c.name = 'KEYCLOAK_IDENTITY'
                jar.set_cookie(c)
                with store.locked(), self.assertRaises(module.SessionError):
                    store.save(jar, 'a' * 32)

    def test_cookie_host_and_path_scope_do_not_leak(self):
        module = self.module()
        jar = module.new_jar()
        jar.set_cookie(sample_cookie())
        jar.set_cookie(sample_cookie('KEYCLOAK_IDENTITY', 'sso-example', 'sso.guap.ru', '/realms/master/'))
        self.assertNotIn('KEYCLOAK', module.header_for(jar, module.PRO + '/inside/profile'))
        self.assertNotIn('PHPSESSID', module.header_for(jar, module.SSO + '/realms/master/protocol/openid-connect/auth'))
        self.assertNotIn('KEYCLOAK', module.header_for(jar, module.SSO + '/other'))
        with self.assertRaises(module.SessionError):
            module.header_for(jar, 'https://evil.example/')

    def test_scoped_cookies_roundtrip_privately(self):
        module = self.module()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'session'
            store = module.SessionStore(root)
            jar = module.new_jar()
            jar.set_cookie(sample_cookie())
            jar.set_cookie(sample_cookie('KEYCLOAK_IDENTITY', 'example-sso-value', 'sso.guap.ru', '/realms/master/'))
            with store.locked():
                store.save(jar, generation='a' * 32)
                restored, generation = store.load()
            self.assertEqual(generation, 'a' * 32)
            self.assertEqual([(c.name, c.domain, c.path, c.secure, c.discard) for c in restored],
                             [(c.name, c.domain, c.path, c.secure, c.discard) for c in jar])
            self.assertEqual(root.stat().st_mode & 0o777, 0o700)
            self.assertEqual((root / 'cookies.json').stat().st_mode & 0o777, 0o600)
            compatibility = (root / 'cookie.txt').read_text()
            self.assertIn('PHPSESSID=', compatibility)
            self.assertNotIn('KEYCLOAK', compatibility)
            self.assertEqual((root / 'cookie.txt').stat().st_mode & 0o777, 0o600)

if __name__ == '__main__':
    unittest.main()
