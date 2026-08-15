#!/usr/bin/env python3
"""Dependency-free CLI for the GUAP personal cabinet."""

from __future__ import annotations

import argparse
import getpass
import html
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

BASE_URL = "https://pro.guap.ru"
COOKIE_PATH = Path.home() / ".config" / "guap-skill" / "cookie.txt"
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131 Safari/537.36"


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
    if COOKIE_PATH.exists():
        return COOKIE_PATH.read_text(encoding="utf-8").strip()
    raise RuntimeError("No GUAP session. Run `python skills/guap-pro/guap.py pro auth` first or set GUAP_COOKIE.")


def request(path: str, params: dict[str, Any] | None = None) -> str:
    query = urllib.parse.urlencode({key: value for key, value in (params or {}).items() if value is not None})
    url = BASE_URL + path
    if query:
        url += "?" + query
    req = urllib.request.Request(url, headers={"Cookie": cookie(), "User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return response.read().decode("utf-8", errors="replace")
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


def output(data: Any, format_name: str) -> None:
    if format_name == "json":
        print(json.dumps(data, ensure_ascii=False, indent=2))
    elif isinstance(data, list):
        for item in data:
            print(" | ".join(f"{key}: {value}" for key, value in item.items() if not isinstance(value, (list, dict))))
    else:
        for key, value in data.items():
            print(f"{key}: {value}")


def save_cookie(value: str) -> None:
    COOKIE_PATH.parent.mkdir(parents=True, exist_ok=True)
    COOKIE_PATH.write_text(value.strip(), encoding="utf-8")
    COOKIE_PATH.chmod(0o600)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="guap-pro", description=__doc__)
    pro = parser.add_subparsers(dest="root_command", required=True).add_parser("pro", help="Commands for pro.guap.ru")
    commands = pro.add_subparsers(dest="command", required=True)
    auth = commands.add_parser("auth", help="Save a browser Cookie header manually")
    auth.add_argument("--cookie-file", type=Path, help="Read the Cookie header from a file")
    commands.add_parser("check")
    tasks = commands.add_parser("tasks")
    tasks.add_argument("--semester", type=int)
    tasks.add_argument("--subject", type=int)
    tasks.add_argument("--type", type=int)
    tasks.add_argument("--status", type=int)
    tasks.add_argument("--format", choices=("table", "json"), default="table")
    task = commands.add_parser("task")
    task.add_argument("id", type=int)
    task.add_argument("--format", choices=("table", "json"), default="table")
    materials = commands.add_parser("materials")
    materials.add_argument("--semester", type=int)
    materials.add_argument("--subject", type=int)
    materials.add_argument("--format", choices=("table", "json"), default="table")
    profile = commands.add_parser("profile")
    profile.add_argument("--format", choices=("table", "json"), default="table")
    args = parser.parse_args(argv)
    try:
        if args.command == "auth":
            value = args.cookie_file.read_text(encoding="utf-8") if args.cookie_file else getpass.getpass("Paste Cookie header from pro.guap.ru: ")
            save_cookie(value)
            print(f"Cookie saved to {COOKIE_PATH}")
            return 0
        if args.command == "check":
            source = request("/inside/profile")
            valid = "sso.guap.ru" not in source and "Вход в личный кабинет" not in source
            print("Authentication valid" if valid else "Authentication invalid")
            return 0 if valid else 1
        if args.command == "tasks":
            output(parse_tasks(request("/inside/student/tasks/", {"semester": args.semester, "subject": args.subject, "type": args.type, "showStatus": args.status})), args.format)
            return 0
        if args.command == "task":
            output(parse_task(request(f"/inside/student/tasks/{args.id}"), args.id), args.format)
            return 0
        if args.command == "materials":
            output(parse_materials(request("/inside/student/materials", {"semester": args.semester, "subject": args.subject})), args.format)
            return 0
        if args.command == "profile":
            output(parse_profile(request("/inside/profile")), args.format)
            return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
