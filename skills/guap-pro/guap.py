#!/usr/bin/env python3
"""Dependency-free CLI for the GUAP personal cabinet."""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import html
import json
import os
import secrets
import shlex
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

BASE_URL = "https://pro.guap.ru"
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131 Safari/537.36"


def hermes_home() -> Path:
    return Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))).expanduser()


def cookie_path() -> Path:
    return hermes_home() / "guap-pro" / "cookie.txt"


@dataclass
class Node:
    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    children: list[Any] = field(default_factory=list)

    def text(self) -> str:
        value = "".join(child.text() if isinstance(child, Node) else child for child in self.children)
        return " ".join(html.unescape(value).split())

    def descendants(self, tag: str | None = None) -> list["Node"]:
        result: list[Node] = []
        for child in self.children:
            if isinstance(child, Node):
                if tag is None or child.tag == tag:
                    result.append(child)
                result.extend(child.descendants(tag))
        return result

    def first(self, tag: str | None = None, **attrs: str) -> "Node | None":
        for node in self.descendants(tag):
            if all(node.attrs.get(key, "") == value for key, value in attrs.items()):
                return node
        return None

    def first_href(self, contains: str) -> "Node | None":
        for node in self.descendants("a"):
            if contains in node.attrs.get("href", ""):
                return node
        return None


class Parser:
    """Small HTML tree builder using only the Python standard library."""

    def __init__(self) -> None:
        from html.parser import HTMLParser

        class TreeParser(HTMLParser):
            def __init__(self, owner: Parser) -> None:
                super().__init__(convert_charrefs=True)
                self.owner = owner
                self.stack = [owner.root]

            def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
                node = Node(tag, {key: value or "" for key, value in attrs})
                self.stack[-1].children.append(node)
                if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}:
                    self.stack.append(node)

            def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
                self.stack[-1].children.append(Node(tag, {key: value or "" for key, value in attrs}))

            def handle_endtag(self, tag: str) -> None:
                for index in range(len(self.stack) - 1, 0, -1):
                    if self.stack[index].tag == tag:
                        del self.stack[index:]
                        break

            def handle_data(self, data: str) -> None:
                self.stack[-1].children.append(data)

        self.root = Node("root")
        self.parser = TreeParser(self)

    def feed(self, source: str) -> Node:
        self.parser.feed(source)
        return self.root


def compact(value: str) -> str:
    return " ".join(html.unescape(value).split())


def href_id(href: str, prefix: str) -> int | None:
    import re

    if prefix not in href:
        return None
    tail = href.split(prefix, 1)[1]
    digits = "".join(char for char in tail if char.isdigit())
    return int(digits) if digits else None


def cookie() -> str:
    value = os.environ.get("GUAP_COOKIE", "").strip()
    if value:
        return value
    path = cookie_path()
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    raise RuntimeError("No GUAP session. Run `python skills/guap-pro/guap.py pro auth` first or set GUAP_COOKIE.")


def request(path: str, params: dict[str, Any] | None = None) -> str:
    query = urllib.parse.urlencode({key: value for key, value in (params or {}).items() if value is not None})
    url = BASE_URL + path
    if query:
        url += "?" + query
    req = urllib.request.Request(url, headers={"Cookie": cookie(), "User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            body = response.read().decode("utf-8", errors="replace")
            final_url = response.geturl().lower()
            lowered = body.lower()
            if "sso.guap.ru" in final_url or "вход в личный кабинет" in lowered:
                raise RuntimeError("reauth_required: GUAP session has expired")
            return body
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"GUAP returned HTTP {exc.code} for {path}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach GUAP: {exc.reason}") from exc


def parse_tasks(source: str) -> list[dict[str, Any]]:
    root = Parser().feed(source)
    table = root.first("table")
    result = []
    if table is None:
        return result
    for row in table.descendants("tr"):
        cells = [child for child in row.children if isinstance(child, Node) and child.tag == "td"]
        if len(cells) < 4:
            continue
        task_link = cells[0].first("a")
        if task_link is None:
            continue
        task_id = href_id(task_link.attrs.get("href", ""), "/inside/student/tasks/")
        if task_id is None:
            continue
        subject_link = cells[1].first("a")
        name_link = cells[3].first("a")
        teacher_link = cells[9].first("a") if len(cells) > 9 else None
        points = compact(cells[5].text()) if len(cells) > 5 else ""
        earned, separator, maximum = points.partition("/")
        result.append(
            {
                "id": task_id,
                "subject": subject_link.text() if subject_link else cells[1].text(),
                "subject_id": href_id(subject_link.attrs.get("href", ""), "/inside/students/subjects/") if subject_link else None,
                "name": name_link.text() if name_link else cells[3].text(),
                "status": cells[4].text() if len(cells) > 4 else "",
                "points_earned": earned.strip() if separator else "",
                "points_max": maximum.strip() if separator else "",
                "type": cells[6].text() if len(cells) > 6 else "",
                "deadline": cells[7].text() if len(cells) > 7 else "",
                "teacher": teacher_link.text() if teacher_link else (cells[9].text() if len(cells) > 9 else ""),
            }
        )
    return result


def parse_task(source: str, task_id: int) -> dict[str, Any]:
    root = Parser().feed(source)
    info: dict[str, str] = {}
    keys = ("Тип:", "Семестр:", "Баллы:", "№ задания:", "Дата добавления:", "Доступные расширения файлов отчета:", "Предельная дата выполнения:")
    for heading in root.descendants("h5"):
        line = heading.text()
        for key in keys:
            if line.startswith(key):
                span = heading.first("span")
                info[key] = span.text() if span else line[len(key) :].strip()
    subject = root.first_href("/inside/students/subjects/")
    teacher = root.first_href("/inside/profile/")
    description = ""
    for heading in root.descendants("h5"):
        if "Описание задания" in heading.text():
            # The first non-empty paragraph after the label is the description.
            for paragraph in root.descendants("p"):
                if paragraph.text():
                    description = paragraph.text()
                    break
            break
    materials = [{"text": link.text(), "url": link.attrs.get("href", "")} for link in root.descendants("a") if "/inside/student/tasks/" in link.attrs.get("href", "") and "download" in link.attrs.get("href", "")]
    title = root.first("h3")
    return {
        "id": task_id,
        "name": title.text() if title else "",
        "subject": subject.text() if subject else "",
        "subject_id": href_id(subject.attrs.get("href", ""), "/inside/students/subjects/") if subject else None,
        "type": info.get("Тип:", ""),
        "semester": info.get("Семестр:", ""),
        "teacher": teacher.text() if teacher else "",
        "points_max": info.get("Баллы:", ""),
        "deadline": info.get("Предельная дата выполнения:", ""),
        "description": description,
        "allowed_extensions": info.get("Доступные расширения файлов отчета:", "Все"),
        "extra_materials": materials,
    }


def parse_materials(source: str) -> list[dict[str, Any]]:
    root = Parser().feed(source)
    table = root.first("table")
    result = []
    if table is None:
        return result
    for row in table.descendants("tr"):
        cells = [child for child in row.children if isinstance(child, Node) and child.tag == "td"]
        if len(cells) < 3:
            continue
        result.append({
            "subject": cells[1].text(),
            "name": cells[2].text(),
            "added_at": cells[3].text() if len(cells) > 3 else "",
            "teacher": cells[4].text() if len(cells) > 4 else "",
            "urls": [link.attrs.get("href", "") for link in cells[0].descendants("a")],
        })
    return result


def parse_profile(source: str) -> dict[str, str]:
    root = Parser().feed(source)
    title = root.first("h3")
    result = {"full_name": title.text() if title else ""}
    labels = ("Группа:", "Номер студенческого билета/ зачетной книжки:", "Институт/факультет:", "Специальность:", "Направленность:", "Форма обучения:", "Уровень профессионального образования:", "Статус:")
    for heading in root.descendants("h5"):
        line = heading.text()
        for label in labels:
            if line.startswith(label):
                span = heading.first("span")
                result[label.rstrip(":")] = span.text() if span else line[len(label) :].strip()
    return result


def _row_cells(row: Node) -> list[Node]:
    return [child for child in row.children if isinstance(child, Node) and child.tag in {"th", "td"}]


def _key(value: str) -> str:
    mapping = {
        "№": "number",
        "Дисциплина": "discipline",
        "Название": "name",
        "Задание": "task",
        "Статус": "status",
        "Оценка": "mark",
        "Преподаватель": "teacher",
        "Тип": "type",
        "Баллы": "points",
        "Предельная дата": "deadline",
        "Дата загрузки": "uploaded_at",
        "Пара": "lesson",
        "Время": "time",
        "Аудитория": "room",
        "Корпус": "building",
    }
    return mapping.get(compact(value), compact(value).lower().replace(" ", "_"))


def parse_table_records(source: str, table_index: int = 0) -> list[dict[str, str]]:
    root = Parser().feed(source)
    tables = root.descendants("table")
    if table_index >= len(tables):
        return []
    rows = tables[table_index].descendants("tr")
    if not rows:
        return []
    headers = _row_cells(rows[0])
    if not any(cell.tag == "th" for cell in headers):
        return []
    keys = [_key(cell.text()) for cell in headers]
    records: list[dict[str, str]] = []
    for row in rows[1:]:
        cells = _row_cells(row)
        if not cells:
            continue
        values = [cell.text() for cell in cells]
        records.append({key: values[index] if index < len(values) else "" for index, key in enumerate(keys)})
    return records


def parse_subjects(source: str) -> list[dict[str, Any]]:
    root = Parser().feed(source)
    result: list[dict[str, Any]] = []
    prefix = "/inside/students/subjects/"
    for card in root.descendants("div"):
        if "card" not in card.attrs.get("class", "").split():
            continue
        link = next((a for a in card.descendants("a") if prefix in a.attrs.get("href", "") and href_id(a.attrs["href"], prefix) is not None), None)
        if link is None:
            continue
        teachers = []
        for teacher in card.descendants("a"):
            teacher_id = href_id(teacher.attrs.get("href", ""), "/inside/profile/")
            if teacher_id is not None:
                teachers.append({"id": teacher_id, "name": teacher.text()})
        small = card.first("small")
        spans = [span.text() for span in card.descendants("span") if span.text()]
        result.append({
            "id": href_id(link.attrs["href"], prefix),
            "name": link.text(),
            "type": small.text() if small else "",
            "academic_year": spans[0] if spans else "",
            "term": spans[1] if len(spans) > 1 else "",
            "teachers": teachers,
        })
    return result


def parse_subject_detail(source: str, subject_id: int) -> dict[str, Any]:
    root = Parser().feed(source)
    title = root.first("h3")
    return {"id": subject_id, "name": title.text() if title else "", "tasks": parse_table_records(source)}


def parse_schedule(source: str, date: str) -> dict[str, Any]:
    return {"date": date, "lessons": parse_table_records(source)}


def parse_reports(source: str) -> list[dict[str, str]]:
    return parse_table_records(source)


def parse_marks(source: str) -> list[dict[str, str]]:
    return parse_table_records(source)


def parse_notices(source: str) -> list[dict[str, str]]:
    root = Parser().feed(source)
    result: list[dict[str, str]] = []
    for card in root.descendants("div"):
        if "card" not in card.attrs.get("class", "").split():
            continue
        title_node = next((card.first(tag) for tag in ("h5", "h4", "h3") if card.first(tag)), None)
        header = card.first("div", **{"class": "card-header"})
        paragraphs = [node.text() for node in card.descendants("p") if node.text()]
        if title_node is None and not paragraphs:
            continue
        result.append({
            "title": title_node.text() if title_node else "",
            "type": header.text() if header else "",
            "body": " ".join(paragraphs),
        })
    return result


def parse_professors(source: str) -> list[dict[str, Any]]:
    root = Parser().feed(source)
    unique: dict[int, dict[str, Any]] = {}
    for link in root.descendants("a"):
        professor_id = href_id(link.attrs.get("href", ""), "/inside/profile/")
        if professor_id is not None and link.text():
            unique.setdefault(professor_id, {"id": professor_id, "name": link.text()})
    return list(unique.values())


def output(data: Any, format_name: str) -> None:
    if format_name == "json":
        print(json.dumps(data, ensure_ascii=False, indent=2))
    elif isinstance(data, list):
        for item in data:
            print(" | ".join(f"{key}: {value}" for key, value in item.items() if not isinstance(value, (list, dict))))
    else:
        for key, value in data.items():
            print(f"{key}: {value}")


def query_params(**values: Any) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None and value != ""}


def save_cookie(value: str) -> None:
    path = cookie_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.strip(), encoding="utf-8")
    path.chmod(0o600)


def _read_exact(sock: socket.socket, size: int) -> bytes:
    data = bytearray()
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise RuntimeError("Browser debugging connection closed")
        data.extend(chunk)
    return bytes(data)


def _websocket_connect(url: str) -> socket.socket:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "ws":
        raise RuntimeError(f"Unsupported browser debugging URL: {url}")
    sock = socket.create_connection((parsed.hostname, parsed.port or 80), timeout=5)
    key = base64.b64encode(secrets.token_bytes(16)).decode("ascii")
    request = (
        f"GET {parsed.path or '/'} HTTP/1.1\r\n"
        f"Host: {parsed.hostname}:{parsed.port or 80}\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        "Sec-WebSocket-Version: 13\r\n\r\n"
    ).encode("ascii")
    sock.sendall(request)
    response = bytearray()
    while b"\r\n\r\n" not in response:
        response.extend(sock.recv(4096))
    if not response.startswith(b"HTTP/1.1 101"):
        sock.close()
        raise RuntimeError("Chrome did not accept the debugging WebSocket")
    return sock


def _websocket_send(sock: socket.socket, payload: str, opcode: int = 1) -> None:
    data = payload.encode("utf-8")
    mask = secrets.token_bytes(4)
    masked = bytes(value ^ mask[index % 4] for index, value in enumerate(data))
    first = 0x80 | opcode
    length = len(masked)
    if length < 126:
        header = bytes([first, 0x80 | length])
    elif length < 65536:
        header = bytes([first, 0x80 | 126]) + struct.pack(">H", length)
    else:
        header = bytes([first, 0x80 | 127]) + struct.pack(">Q", length)
    sock.sendall(header + mask + masked)


def _websocket_receive(sock: socket.socket) -> tuple[int, bytes]:
    first, second = _read_exact(sock, 2)
    opcode = first & 0x0F
    length = second & 0x7F
    if length == 126:
        length = struct.unpack(">H", _read_exact(sock, 2))[0]
    elif length == 127:
        length = struct.unpack(">Q", _read_exact(sock, 8))[0]
    mask = _read_exact(sock, 4) if second & 0x80 else b""
    data = _read_exact(sock, length)
    if mask:
        data = bytes(value ^ mask[index % 4] for index, value in enumerate(data))
    return opcode, data


def _cdp_call(sock: socket.socket, counter: int, method: str, params: dict[str, Any] | None = None) -> tuple[int, dict[str, Any]]:
    _websocket_send(sock, json.dumps({"id": counter, "method": method, "params": params or {}}))
    while True:
        opcode, data = _websocket_receive(sock)
        if opcode == 9:
            _websocket_send(sock, data.decode("utf-8", errors="ignore"), opcode=10)
            continue
        if opcode != 1:
            continue
        message = json.loads(data.decode("utf-8"))
        if message.get("id") == counter:
            return counter + 1, message.get("result", {})


def _json_url(url: str) -> Any:
    with urllib.request.urlopen(url, timeout=3) as response:
        return json.loads(response.read().decode("utf-8"))


def _browser_binary(explicit: str | None) -> str:
    candidates = [explicit] if explicit else []
    candidates += ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome", "msedge"]
    for candidate in candidates:
        if candidate and shutil.which(candidate):
            return candidate
    raise RuntimeError("Chrome or Chromium was not found. Use --browser-command or provide GUAP_COOKIE manually.")


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def browser_cookie(timeout: int, browser_command: str | None, keep_browser: bool, profile_dir: Path | None) -> str:
    """Launch a persistent Chrome profile and read GUAP cookies over CDP."""
    binary = _browser_binary(browser_command)
    ephemeral = profile_dir is None
    profile = Path(tempfile.mkdtemp(prefix="guap-skill-chrome-")) if ephemeral else profile_dir.expanduser()
    profile.mkdir(parents=True, exist_ok=True)
    lock_path = profile.parent / f".{profile.name}.lock"
    try:
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise RuntimeError("GUAP browser profile is already in use") from exc
    os.close(lock_fd)
    port = _free_port()
    command = shlex.split(binary)
    command += [
        f"--remote-debugging-port={port}",
        f"--user-data-dir={profile}",
        "--no-first-run",
        "--no-default-browser-check",
        BASE_URL,
    ]
    process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.monotonic() + timeout
    announced = False
    try:
        while time.monotonic() < deadline:
            try:
                targets = _json_url(f"http://127.0.0.1:{port}/json/list")
            except Exception:
                time.sleep(0.5)
                continue
            if not announced:
                print("Выполните вход в открывшемся Chrome. Пароль вводится только вами.")
                announced = True
            page = next((item for item in targets if item.get("type") == "page" and item.get("webSocketDebuggerUrl")), None)
            if page:
                sock = None
                try:
                    sock = _websocket_connect(page["webSocketDebuggerUrl"])
                    counter = 1
                    counter, url_result = _cdp_call(sock, counter, "Runtime.evaluate", {"expression": "location.href"})
                    current_url = url_result.get("result", {}).get("value", "")
                    counter, cookie_result = _cdp_call(sock, counter, "Network.getAllCookies")
                    cookies = cookie_result.get("cookies", [])
                    guap = [item for item in cookies if "guap.ru" in item.get("domain", "")]
                    if guap and "pro.guap.ru" in current_url and "sso.guap.ru" not in current_url:
                        return "; ".join(f"{item['name']}={item['value']}" for item in guap)
                except Exception:
                    pass
                finally:
                    if sock:
                        sock.close()
            time.sleep(1)
        raise RuntimeError("GUAP browser authentication timed out")
    finally:
        if not keep_browser:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            if ephemeral:
                shutil.rmtree(profile, ignore_errors=True)
        lock_path.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="guap-pro", description=__doc__)
    pro = parser.add_subparsers(dest="root_command", required=True).add_parser("pro", help="Commands for pro.guap.ru")
    commands = pro.add_subparsers(dest="command", required=True)
    auth = commands.add_parser("auth", help="Open Chrome and capture GUAP cookies")
    auth.add_argument("--cookie-file", type=Path, help="Read the Cookie header from a file")
    auth.add_argument("--timeout", type=int, default=180)
    auth.add_argument("--browser-command", help="Chrome/Chromium executable when auto-detection is insufficient")
    auth.add_argument("--keep-browser", action="store_true")
    auth.add_argument("--profile-dir", type=Path, default=hermes_home() / "guap-pro" / "chrome-profile")
    commands.add_parser("check")
    tasks = commands.add_parser("tasks")
    tasks.add_argument("--semester", type=int)
    tasks.add_argument("--subject", type=int)
    tasks.add_argument("--type", type=int)
    tasks.add_argument("--status", type=int)
    tasks.add_argument("--search")
    tasks.add_argument("--per-page", type=int)
    tasks.add_argument("--page", type=int)
    tasks.add_argument("--sort")
    tasks.add_argument("--direction", choices=("asc", "desc"))
    tasks.add_argument("--format", choices=("table", "json"), default="table")
    task = commands.add_parser("task")
    task.add_argument("id", type=int)
    task.add_argument("--format", choices=("table", "json"), default="table")
    materials = commands.add_parser("materials")
    materials.add_argument("--semester", type=int)
    materials.add_argument("--subject", type=int)
    materials.add_argument("--text")
    materials.add_argument("--per-page", type=int)
    materials.add_argument("--format", choices=("table", "json"), default="table")
    profile = commands.add_parser("profile")
    profile.add_argument("--format", choices=("table", "json"), default="table")
    subjects = commands.add_parser("subjects")
    subjects.add_argument("--format", choices=("table", "json"), default="table")
    subject = commands.add_parser("subject")
    subject.add_argument("id", type=int)
    subject.add_argument("--format", choices=("table", "json"), default="json")
    marks = commands.add_parser("marks")
    marks.add_argument("--semester", type=int)
    marks.add_argument("--type", type=int)
    marks.add_argument("--teacher", type=int)
    marks.add_argument("--mark", type=int)
    marks.add_argument("--format", choices=("table", "json"), default="table")
    schedule = commands.add_parser("schedule")
    schedule.add_argument("--date", default=dt.date.today().isoformat())
    schedule.add_argument("--group", type=int)
    schedule.add_argument("--teacher", type=int)
    schedule.add_argument("--building", type=int)
    schedule.add_argument("--room", type=int)
    schedule.add_argument("--format", choices=("table", "json"), default="json")
    reports = commands.add_parser("reports")
    reports.add_argument("--semester", type=int)
    reports.add_argument("--subject", type=int)
    reports.add_argument("--status", type=int)
    reports.add_argument("--text")
    reports.add_argument("--per-page", type=int)
    reports.add_argument("--format", choices=("table", "json"), default="table")
    notices = commands.add_parser("notices")
    notices.add_argument("--subject", type=int)
    notices.add_argument("--type")
    notices.add_argument("--search", dest="text")
    notices.add_argument("--per-page", type=int)
    notices.add_argument("--format", choices=("table", "json"), default="table")
    professors = commands.add_parser("professors")
    professors.add_argument("--search", dest="fullname")
    professors.add_argument("--position", type=int)
    professors.add_argument("--faculty", type=int)
    professors.add_argument("--subunit", type=int)
    professors.add_argument("--per-page", type=int)
    professors.add_argument("--format", choices=("table", "json"), default="table")
    args = parser.parse_args(argv)
    try:
        if args.command == "auth":
            value = args.cookie_file.read_text(encoding="utf-8") if args.cookie_file else browser_cookie(args.timeout, args.browser_command, args.keep_browser, args.profile_dir)
            save_cookie(value)
            print(f"Cookie saved to {cookie_path()}")
            return 0
        if args.command == "check":
            source = request("/inside/profile")
            valid = "sso.guap.ru" not in source and "Вход в личный кабинет" not in source
            print("Authentication valid" if valid else "Authentication invalid")
            return 0 if valid else 1
        if args.command == "tasks":
            output(parse_tasks(request("/inside/student/tasks/", query_params(
                semester=args.semester, subject=args.subject, type=args.type, showStatus=args.status,
                text=args.search, perPage=args.per_page, page=args.page, sort=args.sort, direction=args.direction,
            ))), args.format)
            return 0
        if args.command == "task":
            output(parse_task(request(f"/inside/student/tasks/{args.id}"), args.id), args.format)
            return 0
        if args.command == "materials":
            output(parse_materials(request("/inside/student/materials", query_params(
                semester=args.semester, subject=args.subject, text=args.text, perPage=args.per_page,
            ))), args.format)
            return 0
        if args.command == "profile":
            output(parse_profile(request("/inside/profile")), args.format)
            return 0
        if args.command == "subjects":
            output(parse_subjects(request("/inside/students/subjects", {})), args.format)
            return 0
        if args.command == "subject":
            output(parse_subject_detail(request(f"/inside/students/subjects/{args.id}"), args.id), args.format)
            return 0
        if args.command == "marks":
            output(parse_marks(request("/inside/student/marks", query_params(
                semester=args.semester, type=args.type, teacher=args.teacher, mark=args.mark,
            ))), args.format)
            return 0
        if args.command == "schedule":
            dt.date.fromisoformat(args.date)
            output(parse_schedule(request(f"/inside/students/classes/schedule/day/{args.date}", query_params(
                group=args.group, teacher=args.teacher, building=args.building, room=args.room,
            )), args.date), args.format)
            return 0
        if args.command == "reports":
            output(parse_reports(request("/inside/student/reports", query_params(
                semester=args.semester, subject=args.subject, status=args.status, text=args.text, perPage=args.per_page,
            ))), args.format)
            return 0
        if args.command == "notices":
            output(parse_notices(request("/inside/student/notice", query_params(
                subject=args.subject, type=args.type, text=args.text, perPage=args.per_page,
            ))), args.format)
            return 0
        if args.command == "professors":
            output(parse_professors(request("/inside/student/professors", query_params(
                fullname=args.fullname, position=args.position, facultyWithChairs=args.faculty,
                subunit=args.subunit, perPage=args.per_page,
            ))), args.format)
            return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
