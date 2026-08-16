from __future__ import annotations

import http.cookiejar
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/guap-pro/scripts/guap.py"
RELAY = ROOT / "skills/guap-pro/scripts/relay.py"

def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# Load the CLI first because relay.py imports it by module name.
guap = load_module("guap", SCRIPT)
relay = load_module("guap_relay", RELAY)


class RelayTests(unittest.TestCase):
    def test_extracts_hidden_login_fields_and_password(self) -> None:
        source = """
        <html><head><title>SSO</title></head><body>
          <form action='/login' method='post'>
            <input type='hidden' name='_csrf' value='csrf-value'>
            <input type='text' name='username' placeholder='Логин' required>
            <input type='password' name='password' required>
            <input type='submit' value='Войти'>
          </form>
        </body></html>
        """
        form = relay.RelaySession._extract_form("https://sso.guap.ru/start", source)
        self.assertIsNotNone(form)
        assert form is not None
        self.assertEqual(form.action, "https://sso.guap.ru/login")
        self.assertEqual([field.name for field in form.fields], ["_csrf", "username", "password"])
        self.assertEqual(form.fields[0].value, "csrf-value")
        self.assertEqual(form.fields[2].kind, "password")

    def test_authenticated_submit_saves_no_form_data_to_output(self) -> None:
        session = relay.RelaySession("test-token")
        session.form = relay.LoginForm(
            action="https://sso.guap.ru/login",
            method="POST",
            fields=[
                relay.FormField("_csrf", "csrf", "hidden"),
                relay.FormField("username", "", "text", "Логин", True),
                relay.FormField("password", "", "password", "Пароль", True),
            ],
        )
        captured: list[bytes] = []

        def fake_request(url: str, data: bytes | None = None):
            session.jar.set_cookie(http.cookiejar.Cookie(
                version=0, name="session", value="ok", port=None, port_specified=False,
                domain="pro.guap.ru", domain_specified=True, domain_initial_dot=False,
                path="/", path_specified=True, secure=True, expires=None, discard=True,
                comment=None, comment_url=None, rest={}, rfc2109=False,
            ))
            if data is None:
                return "https://pro.guap.ru/inside/profile", "<html>profile</html>"
            captured.append(data)
            return "https://pro.guap.ru/inside/profile", "<html>profile</html>"

        session._request = fake_request  # type: ignore[method-assign]
        result = session.submit({"username": ["vasya"], "password": ["secret"]})
        self.assertEqual(result, "authenticated")
        self.assertEqual(session.cookie_header(), "session=ok")
        self.assertNotIn("secret", relay.json.dumps({"status": session.state}))
        self.assertIn(b"username=vasya", captured[0])
        self.assertIn(b"password=secret", captured[0])

    def test_empty_password_cannot_complete_relay(self) -> None:
        session = relay.RelaySession("test-token")
        session.form = relay.LoginForm(
            action="https://sso.guap.ru/login",
            method="POST",
            fields=[relay.FormField("password", "", "password", "Пароль", True)],
        )
        with self.assertRaisesRegex(relay.RelayError, "credentials_required"):
            session.submit({"password": [""]})

    def test_cookie_path_uses_hermes_home_and_mode(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            old = os.environ.get("HERMES_HOME")
            os.environ["HERMES_HOME"] = directory
            try:
                path = relay.relay_cookie_path()
                relay.save_cookie_to(path, "session=secret")
                self.assertEqual(path, Path(directory) / "guap-pro" / "cookie.txt")
                self.assertEqual(path.read_text(encoding="utf-8"), "session=secret")
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            finally:
                if old is None:
                    os.environ.pop("HERMES_HOME", None)
                else:
                    os.environ["HERMES_HOME"] = old

    def test_expired_relay_is_invalid(self) -> None:
        session = relay.RelaySession("token", ttl=0)
        self.assertFalse(session.valid("token"))
        self.assertEqual(session.state, "created")


if __name__ == "__main__":
    unittest.main()
