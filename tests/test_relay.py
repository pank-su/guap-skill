from __future__ import annotations

import http.cookiejar
import importlib.util
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch


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

    def test_serve_returns_tunnel_failed_when_aborted(self) -> None:
        abort_event = threading.Event()
        abort_event.set()
        server = unittest.mock.MagicMock()
        with (
            patch.object(relay, "RelayHTTPServer", return_value=server),
            patch.object(relay, "print") as output,
        ):
            result = relay.serve(
                bind="127.0.0.1",
                port=8765,
                public_url="https://relay.example.com/guap",
                ttl=300,
                user_label="telegram-user",
                approval_scope="GUAP read-only access",
                cookie_path=Path("/tmp/cookie"),
                abort_event=abort_event,
            )
        self.assertEqual(result, 3)
        self.assertIn('"status": "tunnel_failed"', output.call_args_list[-1].args[0])

    def test_serve_reports_failed_done_state_as_failed(self) -> None:
        server = unittest.mock.MagicMock()

        def server_factory(address, state):
            def finish_with_failure() -> None:
                state.session.state = "failed"
                state.session.error = "upstream failed"
                state.done.set()

            server.handle_request.side_effect = finish_with_failure
            return server

        with (
            patch.object(relay, "RelayHTTPServer", side_effect=server_factory),
            patch.object(relay, "print") as output,
        ):
            result = relay.serve(
                bind="127.0.0.1",
                port=8765,
                public_url="https://relay.example.com/guap",
                ttl=300,
                user_label="telegram-user",
                approval_scope="GUAP read-only access",
                cookie_path=Path("/tmp/cookie"),
            )
        self.assertEqual(result, 1)
        self.assertIn('"status": "failed"', output.call_args_list[-1].args[0])
        self.assertNotIn('"status": "authenticated"', output.call_args_list[-1].args[0])

    def test_direct_cli_rejects_public_url_delimiters_and_credentials(self) -> None:
        invalid_urls = (
            "https://relay.example.com/guap?",
            "https://relay.example.com/guap#",
            "https://relay.example.com/guap?token=secret",
            "https://relay.example.com/guap#login",
            "https://user:password@relay.example.com/guap",
            "https://relay.example.com:bad/guap",
            "https://relay.example.com:/guap",
            "https:///guap",
            "http://relay.example.com/guap",
        )
        for public_url in invalid_urls:
            with self.subTest(public_url=public_url), patch.object(relay, "serve") as serve:
                result = relay.main(
                    [
                        "--public-url",
                        public_url,
                        "--approval-scope",
                        "GUAP read-only access",
                    ]
                )
            self.assertEqual(result, 2)
            serve.assert_not_called()

    def test_abort_cleanup_does_not_wait_for_session_lock(self) -> None:
        session = relay.RelaySession("test-token")
        session.form = relay.LoginForm(action="https://sso.guap.ru/login", method="POST")
        release_lock = threading.Event()
        lock_ready = threading.Event()

        def hold_session_lock() -> None:
            with session._lock:
                lock_ready.set()
                release_lock.wait(2)

        holder = threading.Thread(target=hold_session_lock)
        holder.start()
        self.assertTrue(lock_ready.wait(1))
        abort_event = threading.Event()
        abort_event.set()
        server = unittest.mock.MagicMock()
        try:
            with patch.object(relay, "RelaySession", return_value=session), patch.object(
                relay, "RelayHTTPServer", return_value=server
            ):
                result = relay.serve(
                    bind="127.0.0.1",
                    port=8765,
                    public_url="https://relay.example.com/guap",
                    ttl=300,
                    user_label="telegram-user",
                    approval_scope="GUAP read-only access",
                    cookie_path=Path("/tmp/cookie"),
                    abort_event=abort_event,
                )
            self.assertEqual(result, 3)
            self.assertNotEqual(session.state, "destroyed")
        finally:
            release_lock.set()
            holder.join(1)
        for _ in range(100):
            if session.state == "destroyed":
                break
            threading.Event().wait(0.01)
        self.assertEqual(session.state, "destroyed")
        self.assertIsNone(session.form)


if __name__ == "__main__":
    unittest.main()
