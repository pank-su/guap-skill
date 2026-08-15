#!/usr/bin/env python3
"""Standalone read-only CLI for the GUAP personal cabinet."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import httpx
from bs4 import BeautifulSoup

BASE_URL = "https://pro.guap.ru"
COOKIE_PATH = Path.home() / ".config" / "guap-skill" / "cookie.json"
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131 Safari/537.36"


def cookie_string() -> str:
    value = os.environ.get("GUAP_COOKIE", "").strip()
    if value:
        return value
    if COOKIE_PATH.exists():
        data = json.loads(COOKIE_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            value = data.get("cookie_string", "")
        else:
            value = str(data)
        if value:
            return value.strip()
    raise RuntimeError("No GUAP session. Run `guap-pro pro auth` first or set GUAP_COOKIE.")


def client() -> httpx.Client:
    return httpx.Client(
        base_url=BASE_URL,
        headers={"Cookie": cookie_string(), "User-Agent": USER_AGENT},
        follow_redirects=True,
        timeout=30,
    )


def href_id(href: str | None, prefix: str) -> int | None:
    if not href:
        return None
    match = re.search(re.escape(prefix) + r"(\d+)", href)
    return int(match.group(1)) if match else None


def text(element: Any) -> str:
    return re.sub(r"\s+", " ", element.get_text(" ", strip=True)) if element else ""


def task_list(html: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "lxml")
    table = soup.select_one("table")
    if not table:
        return []
    result = []
    for row in table.select("tr"):
        cells = row.select("td")
        if len(cells) < 4:
            continue
        task_link = cells[0].select_one("a")
        task_id = href_id(task_link.get("href"), "/inside/student/tasks/") if task_link else None
        if task_id is None:
            continue
        subject_link = cells[1].select_one("a") if len(cells) > 1 else None
        name_link = cells[3].select_one("a") if len(cells) > 3 else None
        points = text(cells[5]) if len(cells) > 5 else ""
        points_parts = [part.strip() for part in points.split("/", 1)]
        teacher_link = cells[9].select_one("a") if len(cells) > 9 else None
        result.append(
            {
                "id": task_id,
                "subject": text(subject_link) or text(cells[1]),
                "subject_id": href_id(subject_link.get("href"), "/inside/students/subjects/") if subject_link else None,
                "name": text(name_link) or text(cells[3]),
                "status": text(cells[4]) if len(cells) > 4 else "",
                "points_earned": points_parts[0] if len(points_parts) == 2 else "",
                "points_max": points_parts[1] if len(points_parts) == 2 else "",
                "type": text(cells[6]) if len(cells) > 6 else "",
                "deadline": text(cells[7]) if len(cells) > 7 else "",
                "teacher": text(teacher_link) or (text(cells[9]) if len(cells) > 9 else ""),
            }
        )
    return result


def task_detail(html: str, task_id: int) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    info: dict[str, str] = {}
    keys = (
        "Тип:",
        "Семестр:",
        "Баллы:",
        "№ задания:",
        "Дата добавления:",
        "Доступные расширения файлов отчета:",
        "Предельная дата выполнения:",
    )
    for heading in soup.select("h5"):
        line = text(heading)
        for key in keys:
            if line.startswith(key):
                span = heading.select_one("span")
                info[key] = text(span) or line[len(key) :].strip()

    subject = soup.select_one("h5 a[href*='/inside/students/subjects/']")
    teacher = soup.select_one("h5 a[href*='/inside/profile/']")
    description = ""
    for heading in soup.select("h5"):
        if "Описание задания" in text(heading):
            sibling = heading.find_next_sibling()
            while sibling:
                if text(sibling):
                    description = text(sibling)
                    break
                sibling = sibling.find_next_sibling()
            break

    materials = []
    for heading in soup.select("h5"):
        if "Доп. материалы" in text(heading):
            for link in heading.select("a[href]"):
                materials.append({"text": text(link), "url": link["href"]})
            break

    reports = []
    for heading in soup.select("h4"):
        if "Мои отчеты" not in text(heading):
            continue
        table = heading.find_next("table")
        if table:
            for row in table.select("tr"):
                cells = row.select("td")
                if not cells:
                    continue
                reports.append(
                    {
                        "status": text(cells[0]),
                        "file_url": cells[1].select_one("a").get("href") if len(cells) > 1 and cells[1].select_one("a") else None,
                        "uploaded_at": text(cells[2]) if len(cells) > 2 else "",
                        "checked_at": text(cells[3]) if len(cells) > 3 else "",
                        "student_comment": text(cells[4]) if len(cells) > 4 else "",
                        "teacher_comment": text(cells[5]) if len(cells) > 5 else "",
                    }
                )
        break

    return {
        "id": task_id,
        "name": text(soup.select_one("h3.page__title")),
        "subject": text(subject),
        "subject_id": href_id(subject.get("href"), "/inside/students/subjects/") if subject else None,
        "type": info.get("Тип:", ""),
        "semester": info.get("Семестр:", ""),
        "teacher": text(teacher),
        "points_max": info.get("Баллы:", ""),
        "deadline": info.get("Предельная дата выполнения:", ""),
        "description": description,
        "allowed_extensions": info.get("Доступные расширения файлов отчета:", "Все"),
        "extra_materials": materials,
        "submitted_reports": reports,
    }


def materials_list(html: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "lxml")
    table = soup.select_one("table")
    if not table:
        return []
    result = []
    for row in table.select("tr"):
        cells = row.select("td")
        if len(cells) < 3:
            continue
        links = cells[0].select("a[href]")
        result.append(
            {
                "subject": text(cells[1]),
                "name": text(cells[2]),
                "added_at": text(cells[3]) if len(cells) > 3 else "",
                "teacher": text(cells[4]) if len(cells) > 4 else "",
                "urls": [link.get("href") for link in links],
            }
        )
    return result


def profile_data(html: str) -> dict[str, str]:
    soup = BeautifulSoup(html, "lxml")
    result = {"full_name": text(soup.select_one("h3.text-center"))}
    labels = (
        "Группа:",
        "Номер студенческого билета/ зачетной книжки:",
        "Институт/факультет:",
        "Специальность:",
        "Направленность:",
        "Форма обучения:",
        "Уровень профессионального образования:",
        "Статус:",
    )
    for heading in soup.select("h5"):
        line = text(heading)
        for label in labels:
            if line.startswith(label):
                result[label.rstrip(":")] = text(heading.select_one("span")) or line[len(label) :].strip()
    return result


def get_json(path: str, **params: Any) -> Any:
    with client() as http:
        response = http.get(path, params={key: value for key, value in params.items() if value is not None})
        response.raise_for_status()
        return response.text


def print_data(data: Any, output_format: str) -> None:
    if output_format == "json":
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return
    if isinstance(data, list):
        for item in data:
            print(" | ".join(f"{key}: {value}" for key, value in item.items() if not isinstance(value, (list, dict))))
    else:
        for key, value in data.items():
            print(f"{key}: {value}")


async def authenticate(timeout: int) -> None:
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise RuntimeError("Install Playwright to use auth: uv sync") from exc
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto(BASE_URL)
        print("Выполните вход в личный кабинет ГУАП в открывшемся браузере.")
        print(f"Ожидание авторизации: {timeout} секунд.")
        for _ in range(timeout):
            if "sso.guap.ru" not in page.url and "pro.guap.ru" in page.url:
                cookies = [item for item in await context.cookies() if "guap.ru" in item.get("domain", "")]
                COOKIE_PATH.parent.mkdir(parents=True, exist_ok=True)
                COOKIE_PATH.write_text(
                    json.dumps(
                        {"cookie_string": "; ".join(f"{item['name']}={item['value']}" for item in cookies)},
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )
                print(f"Сессия сохранена в {COOKIE_PATH}")
                await browser.close()
                return
            await asyncio.sleep(1)
        await browser.close()
        raise RuntimeError("Авторизация не завершена вовремя")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="guap-pro", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    pro = sub.add_parser("pro", help="Commands for pro.guap.ru")
    pro_sub = pro.add_subparsers(dest="pro_command", required=True)

    auth = pro_sub.add_parser("auth")
    auth.add_argument("--timeout", type=int, default=120)

    pro_sub.add_parser("check")

    tasks = pro_sub.add_parser("tasks")
    tasks.add_argument("--semester", type=int)
    tasks.add_argument("--subject", type=int)
    tasks.add_argument("--type", type=int)
    tasks.add_argument("--status", type=int)
    tasks.add_argument("--format", choices=("table", "json"), default="table")

    task = pro_sub.add_parser("task")
    task.add_argument("id", type=int)
    task.add_argument("--format", choices=("table", "json"), default="table")

    materials = pro_sub.add_parser("materials")
    materials.add_argument("--semester", type=int)
    materials.add_argument("--subject", type=int)
    materials.add_argument("--format", choices=("table", "json"), default="table")

    profile = pro_sub.add_parser("profile")
    profile.add_argument("--format", choices=("table", "json"), default="table")

    args = parser.parse_args(argv)
    try:
        if args.pro_command == "auth":
            asyncio.run(authenticate(args.timeout))
            return 0
        if args.pro_command == "check":
            with client() as http:
                response = http.get("/inside/profile")
                valid = response.status_code == 200 and "sso.guap.ru" not in str(response.url)
            print("Authentication valid" if valid else "Authentication invalid")
            return 0 if valid else 1
        if args.pro_command == "tasks":
            html = get_json("/inside/student/tasks/", semester=args.semester, subject=args.subject, type=args.type, showStatus=args.status)
            print_data(task_list(html), args.format)
            return 0
        if args.pro_command == "task":
            html = get_json(f"/inside/student/tasks/{args.id}")
            print_data(task_detail(html, args.id), args.format)
            return 0
        if args.pro_command == "materials":
            html = get_json("/inside/student/materials", semester=args.semester, subject=args.subject)
            print_data(materials_list(html), args.format)
            return 0
        if args.pro_command == "profile":
            html = get_json("/inside/profile")
            print_data(profile_data(html), args.format)
            return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
