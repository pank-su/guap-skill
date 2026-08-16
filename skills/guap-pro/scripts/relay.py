#!/usr/bin/env python3
"""Short-lived GUAP credential relay for user-driven remote login.

The relay is intentionally separate from the read-only cabinet client. It serves
an HTTPS form, forwards the user's submission to GUAP with urllib, keeps upstream
cookies in memory, and writes only the resulting Cookie header to the Hermes-safe
cookie path after successful login.

Run it behind HTTPS. Do not expose the HTTP listener directly to the Internet.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import html
import http.server
import http.cookiejar
import json
import os
import secrets
import ssl
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    from guap import BASE_URL, Node, Parser, save_cookie
except ImportError:  # pragma: no cover - supports package-style imports
    from .guap import BASE_URL, Node, Parser, save_cookie

RELAY_DEFAULT_TTL = 300
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131 Safari/537.36"


def hermes_home() -> Path:
    return Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))).expanduser()


def relay_cookie_path() -> Path:
    return hermes_home() / "guap-pro" / "cookie.txt"


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def escape(value: str) -> str:
    return html.escape(value, quote=True)


def absolute_url(url: str, base: str) -> str:
    return urllib.parse.urljoin(base, url)


def response_is_login(url: str, body: str) -> bool:
    lowered_url = url.lower()
    lowered_body = body.lower()
    if "sso.guap.ru" in lowered_url:
        return True
    root = Parser().feed(body)
    return any(
        node.attrs.get("type", "").lower() == "password"
        for node in root.descendants("input")
    ) or "вход в личный кабинет" in lowered_body


@dataclass
class FormField:
    name: str
    value: str = ""
    kind: str = "text"
    label: str = ""
    required: bool = False


@dataclass
class LoginForm:
    action: str
    method: str
    fields: list[FormField] = field(default_factory=list)
    title: str = "Вход в ГУАП"


class RelayError(RuntimeError):
    pass


class RelaySession:
    """One isolated upstream cookie jar and one short-lived login flow."""

    def __init__(self, token: str, ttl: int = RELAY_DEFAULT_TTL) -> None:
        self.token_digest = token_digest(token)
        self.expires_at = time.time() + ttl
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.current_url = BASE_URL + "/inside/profile"
        self.form: LoginForm | None = None
        self.state = "created"
        self.error = ""
        self._lock = threading.RLock()

    def expired(self) -> bool:
        return time.time() >= self.expires_at

    def valid(self, token: str) -> bool:
        return secrets.compare_digest(self.token_digest, token_digest(token)) and not self.expired()

    def _request(self, url: str, data: bytes | None = None) -> tuple[str, str]:
        request = urllib.request.Request(
            url,
            data=data,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
            method="POST" if data is not None else "GET",
        )
        try:
            with self.opener.open(request, timeout=30) as response:
                body = response.read(2_000_000).decode("utf-8", errors="replace")
                return response.geturl(), body
        except urllib.error.HTTPError as exc:
            body = exc.read(2_000_000).decode("utf-8", errors="replace")
            return exc.geturl(), body
        except urllib.error.URLError as exc:
            raise RelayError(f"GUAP is unreachable: {exc.reason}") from exc

    @staticmethod
    def _extract_form(url: str, body: str) -> LoginForm | None:
        root = Parser().feed(body)
        form_node = root.first("form")
        if form_node is None:
            return None
        action = absolute_url(form_node.attrs.get("action", url), url)
        method = form_node.attrs.get("method", "post").upper()
        fields: list[FormField] = []
        for input_node in form_node.descendants("input"):
            name = input_node.attrs.get("name", "")
            if not name:
                continue
            kind = input_node.attrs.get("type", "text").lower()
            if kind in {"submit", "button", "reset", "file"}:
                continue
            if kind in {"checkbox", "radio"} and "checked" not in input_node.attrs:
                continue
            fields.append(
                FormField(
                    name=name,
                    value=input_node.attrs.get("value", ""),
                    kind="password" if kind == "password" else "hidden" if kind == "hidden" else "text",
                    label=input_node.attrs.get("aria-label", "") or input_node.attrs.get("placeholder", "") or name,
                    required="required" in input_node.attrs,
                )
            )
        if not fields:
            return None
        title = root.first("title")
        return LoginForm(action=action, method=method, fields=fields, title=title.text() if title else "Вход в ГУАП")

    def load(self) -> LoginForm:
        with self._lock:
            if self.expired():
                self.state = "expired"
                raise RelayError("relay_expired")
            url, body = self._request(self.current_url)
            self.current_url = url
            if not response_is_login(url, body) and "form" not in body.lower():
                if self._session_is_authenticated():
                    self.state = "authenticated"
                    return LoginForm(action=url, method="GET", title="Сессия уже авторизована")
                self.state = "failed"
                raise RelayError("reauth_required: GUAP did not expose an authenticated session")
            form = self._extract_form(url, body)
            if form is None:
                self.state = "failed"
                raise RelayError("relay_failed: GUAP login form was not detected")
            self.form = form
            self.state = "awaiting_credentials"
            return form

    def submit(self, values: dict[str, list[str]]) -> str:
        with self._lock:
            if self.expired():
                self.state = "expired"
                raise RelayError("relay_expired")
            if self.form is None:
                self.load()
            assert self.form is not None
            password_fields = [field.name for field in self.form.fields if field.kind == "password"]
            if password_fields and not any(values.get(name, [""])[-1].strip() for name in password_fields):
                raise RelayError("credentials_required: password field is empty")
            allowed = {field.name for field in self.form.fields}
            payload: list[tuple[str, str]] = []
            for field in self.form.fields:
                submitted = values.get(field.name)
                if submitted:
                    payload.append((field.name, submitted[-1]))
                elif field.kind == "hidden":
                    payload.append((field.name, field.value))
            for name in values:
                if name not in allowed:
                    continue
            body = urllib.parse.urlencode(payload).encode("utf-8")
            url, response = self._request(self.form.action, body)
            self.current_url = url
            if response_is_login(url, response):
                next_form = self._extract_form(url, response)
                if next_form is None:
                    self.state = "failed"
                    raise RelayError("relay_failed: GUAP returned an unsupported login step")
                self.form = next_form
                self.state = "awaiting_second_factor"
                return "additional_step"
            if not self._session_is_authenticated():
                self.state = "failed"
                raise RelayError("reauth_required: GUAP did not confirm the session")
            self.state = "authenticated"
            self.form = None
            return "authenticated"

    def _session_is_authenticated(self) -> bool:
        url, body = self._request(BASE_URL + "/inside/profile")
        return not response_is_login(url, body) and "sso.guap.ru" not in url.lower()

    def cookie_header(self) -> str:
        return "; ".join(f"{item.name}={item.value}" for item in self.jar)

    def destroy(self) -> None:
        with self._lock:
            self.jar.clear()
            self.form = None
            self.state = "destroyed"


@dataclass
class RelayState:
    token: str
    session: RelaySession
    user_label: str
    approval_scope: str
    cookie_path: Path
    done: threading.Event = field(default_factory=threading.Event)


class RelayHandler(http.server.BaseHTTPRequestHandler):
    server_version = "guap-pro-relay/0.1"

    def log_message(self, format: str, *args: Any) -> None:
        # Never log paths: they contain the bearer token.
        return

    @property
    def relay(self) -> "RelayHTTPServer":
        return self.server  # type: ignore[return-value]

    def _send(self, status: int, body: str, content_type: str = "text/html; charset=utf-8") -> None:
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        try:
            self.wfile.write(data)
        except BrokenPipeError:
            # Mobile browsers may close the tab immediately after submitting.
            # Authentication has already been verified before this response.
            pass

    def _token(self) -> str | None:
        parts = urllib.parse.urlsplit(self.path).path.strip("/").split("/")
        if len(parts) == 2 and parts[0] == "login":
            return parts[1]
        return None

    def _state(self) -> RelayState | None:
        token = self._token()
        if not token:
            return None
        state = self.relay.state
        if not state.session.valid(token):
            return None
        return state

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/healthz":
            self._send(200, "ok\n", "text/plain; charset=utf-8")
            return
        state = self._state()
        if state is None:
            self._send(404, "Not found\n", "text/plain; charset=utf-8")
            return
        try:
            if state.session.state == "created":
                state.session.load()
            if state.session.state == "authenticated":
                self._send(200, self._page("Готово", "Авторизация завершена. Вернитесь в Telegram и закройте эту вкладку."))
                return
            if state.session.form is None:
                state.session.load()
            self._send(200, self._form_page(state))
        except RelayError as exc:
            state.session.error = str(exc)
            state.session.state = "failed"
            state.done.set()
            self._send(502, self._page("Не удалось открыть вход", escape(str(exc))))

    def do_POST(self) -> None:  # noqa: N802
        state = self._state()
        if state is None:
            self._send(404, "Not found\n", "text/plain; charset=utf-8")
            return
        length = int(self.headers.get("Content-Length", "0"))
        if length > 64_000:
            self._send(413, "Request too large\n", "text/plain; charset=utf-8")
            return
        raw = self.rfile.read(length)
        values = urllib.parse.parse_qs(raw.decode("utf-8", errors="replace"), keep_blank_values=True)
        try:
            result = state.session.submit(values)
            if result == "authenticated":
                cookie = state.session.cookie_header()
                if not cookie:
                    raise RelayError("relay_failed: GUAP returned no session cookie")
                save_cookie_to(state.cookie_path, cookie)
                state.done.set()
                self._send(200, self._page("Готово", "Авторизация завершена. Вернитесь в Telegram и закройте эту вкладку."))
            else:
                self._send(200, self._form_page(state))
        except RelayError as exc:
            state.session.error = str(exc)
            state.session.state = "failed"
            state.done.set()
            self._send(502, self._page("Авторизация не завершена", "Сессия ГУАП не подтверждена. Вернитесь в Telegram."))

    @staticmethod
    def _page(title: str, message: str) -> str:
        return f"<!doctype html><meta charset='utf-8'><title>{escape(title)}</title><main><h1>{escape(title)}</h1><p>{message}</p></main>"

    def _form_page(self, state: RelayState) -> str:
        assert state.session.form is not None
        fields = []
        visible_number = 0
        for field in state.session.form.fields:
            if field.kind == "hidden":
                fields.append(f"<input type='hidden' name='{escape(field.name)}' value='{escape(field.value)}'>")
                continue
            visible_number += 1
            label = field.label or f"Поле {visible_number}"
            fields.append(
                f"<label>{escape(label)}<input type='{field.kind}' name='{escape(field.name)}' autocomplete='{'current-password' if field.kind == 'password' else 'username'}' {'required' if field.required else ''}></label>"
            )
        return f"""<!doctype html>
<meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'>
<title>Вход в ГУАП</title>
<style>body{{font:16px system-ui;max-width:32rem;margin:3rem auto;padding:0 1rem;background:#f5f5f5}}main{{background:#fff;padding:1.5rem;border-radius:12px}}label{{display:block;margin:1rem 0}}input{{display:block;width:100%;box-sizing:border-box;padding:.7rem;margin-top:.35rem;border:1px solid #aaa;border-radius:6px}}button{{padding:.75rem 1rem;border:0;border-radius:6px;background:#165dff;color:#fff;font-weight:600}}.warning{{background:#fff3cd;padding:1rem;border-radius:8px}}</style>
<main><h1>Вход в ГУАП</h1><p><b>Разрешённый scope:</b> {escape(state.approval_scope)}</p><p class='warning'>Данные формы будут переданы через Hermes-машину на сайт ГУАП. Hermes не сохраняет пароль и не показывает его в Telegram. Продолжая, вы подтверждаете отправку формы.</p><form method='post'>{''.join(fields)}<button type='submit'>Войти</button></form></main>"""


def save_cookie_to(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.strip(), encoding="utf-8")
    path.chmod(0o600)


class RelayHTTPServer(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], state: RelayState) -> None:
        super().__init__(address, RelayHandler)
        self.state = state
        self.timeout = 1


def serve(
    *,
    bind: str,
    port: int,
    public_url: str,
    ttl: int,
    user_label: str,
    approval_scope: str,
    cookie_path: Path,
    certfile: Path | None = None,
    keyfile: Path | None = None,
) -> int:
    token = secrets.token_urlsafe(32)
    session = RelaySession(token, ttl)
    state = RelayState(token, session, user_label, approval_scope, cookie_path)
    server = RelayHTTPServer((bind, port), state)
    if certfile or keyfile:
        if not certfile or not keyfile:
            raise SystemExit("Both --certfile and --keyfile are required for HTTPS")
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certfile=str(certfile), keyfile=str(keyfile))
        server.socket = context.wrap_socket(server.socket, server_side=True)
    link = public_url.rstrip("/") + "/login/" + token
    print(json.dumps({"status": "waiting", "url": link, "expires_in": ttl, "scope": approval_scope}, ensure_ascii=False), flush=True)
    try:
        while not state.done.is_set() and not session.expired():
            server.handle_request()
        if state.done.is_set():
            print(json.dumps({"status": "authenticated", "cookie_path": str(cookie_path)}, ensure_ascii=False), flush=True)
            return 0
        print(json.dumps({"status": "expired"}, ensure_ascii=False), flush=True)
        return 2
    finally:
        session.destroy()
        server.server_close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--public-url", required=True, help="HTTPS base URL reachable by the user")
    parser.add_argument("--ttl", type=int, default=RELAY_DEFAULT_TTL)
    parser.add_argument("--user-label", default="telegram-user")
    parser.add_argument("--approval-scope", required=True, help="Exact scope already approved by the user in Telegram")
    parser.add_argument("--cookie-path", type=Path, default=relay_cookie_path())
    parser.add_argument("--certfile", type=Path)
    parser.add_argument("--keyfile", type=Path)
    args = parser.parse_args(argv)
    if not args.public_url.startswith("https://"):
        print("Refusing non-HTTPS public URL", file=sys.stderr)
        return 2
    try:
        return serve(
            bind=args.bind,
            port=args.port,
            public_url=args.public_url,
            ttl=args.ttl,
            user_label=args.user_label,
            approval_scope=args.approval_scope,
            cookie_path=args.cookie_path,
            certfile=args.certfile,
            keyfile=args.keyfile,
        )
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
