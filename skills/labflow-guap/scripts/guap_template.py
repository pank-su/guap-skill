#!/usr/bin/env python3
"""Create and verify a protected GUAP Typst report template.

Only ``index.typ`` is intended to be edited by hand.  The files under
``.guap`` are managed by this CLI and are integrity checked before every
operation that consumes them.
"""

from __future__ import annotations

import argparse
import datetime as _datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
ASSETS_DIR = SKILL_DIR / "assets" / "guap"
# These are the user-designated source bytes, not a mutable runtime baseline.
EXPECTED_ASSET_HASHES = {
    "titlepage.typ": "46a24a747873436a14d6ded8062f5b84fdce0da6f9b16cbf032dd218f822ae4c",
    "gost.typ": "0996798b3ce078095efab6a224ef47ecc5ab8ebaeee7bbe8c95b19d0095d7727",
}
METADATA_FIELDS = (
    "title",
    "authors",
    "teachers",
    "date",
    "education",
    "department",
    "position",
    "documentName",
    "group",
    "city",
    "object",
)
STRING_FIELDS = {
    "title",
    "date",
    "education",
    "department",
    "position",
    "documentName",
    "group",
    "city",
    "object",
}
ARRAY_FIELDS = {"authors", "teachers"}
DRIVER = '''#import "titlepage.typ": titlepage
#import "gost.typ": init

#let metadata = json("metadata.json")
#let report-date = datetime(
  year: int(metadata.date.slice(0, 4)),
  month: int(metadata.date.slice(5, 7)),
  day: int(metadata.date.slice(8, 10)),
)

#titlepage(
  title: metadata.title,
  authors: metadata.authors,
  teachers: metadata.teachers,
  date: report-date,
  education: metadata.education,
  department: metadata.department,
  position: metadata.position,
  documentName: metadata.documentName,
  group: metadata.group,
  city: metadata.city,
  object: metadata.object,
)

#pagebreak()
#show: init
#include("../index.typ")
'''
DRIVER_BYTES = DRIVER.encode("utf-8")


class TemplateError(Exception):
    """A user-correctable template or command error."""


class IntegrityError(TemplateError):
    """A protected project was altered, damaged, or replaced."""


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_symlink(path: Path) -> bool:
    try:
        return path.is_symlink()
    except OSError as exc:
        raise IntegrityError(f"cannot inspect {path}: {exc}") from exc


def _require_dir(path: Path, label: str) -> None:
    if _is_symlink(path):
        raise IntegrityError(f"{label} must not be a symlink: {path}")
    if not path.is_dir():
        raise IntegrityError(f"{label} is missing or not a directory: {path}")


def _require_file(path: Path, label: str) -> None:
    if _is_symlink(path):
        raise IntegrityError(f"{label} must not be a symlink: {path}")
    if not path.is_file():
        raise IntegrityError(f"{label} is missing or not a regular file: {path}")


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _read_json(path: Path, label: str) -> Any:
    _require_file(path, label)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise IntegrityError(f"{label} is malformed JSON: {exc}") from exc


def _validate_metadata(value: Any, *, complete: bool = False) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TemplateError("metadata must be a JSON object")
    unknown = sorted(set(value) - set(METADATA_FIELDS))
    if unknown:
        raise TemplateError("unknown metadata field(s): " + ", ".join(unknown))
    if complete and set(value) != set(METADATA_FIELDS):
        missing = sorted(set(METADATA_FIELDS) - set(value))
        raise TemplateError("metadata is missing field(s): " + ", ".join(missing))

    result = {field: value.get(field, "" if field in STRING_FIELDS else []) for field in METADATA_FIELDS}
    for field in STRING_FIELDS:
        if not isinstance(result[field], str):
            raise TemplateError(f"metadata field {field!r} must be a string")
    for field in ARRAY_FIELDS:
        if not isinstance(result[field], list) or not all(isinstance(item, str) for item in result[field]):
            raise TemplateError(f"metadata field {field!r} must be an array of strings")
    date_value = result["date"]
    if date_value:
        if len(date_value) != 10 or date_value[4] != "-" or date_value[7] != "-":
            raise TemplateError("metadata field 'date' must be an ISO date (YYYY-MM-DD)")
        try:
            _datetime.date.fromisoformat(date_value)
        except ValueError as exc:
            raise TemplateError("metadata field 'date' must be a valid ISO date (YYYY-MM-DD)") from exc
    if complete:
        for field in STRING_FIELDS:
            if not result[field].strip():
                raise TemplateError(f"required metadata field {field!r} is blank")
        for field in ARRAY_FIELDS:
            if not result[field] or any(not item.strip() for item in result[field]):
                raise TemplateError(f"required metadata field {field!r} must contain non-blank strings")
        if not result["date"]:
            raise TemplateError("required metadata field 'date' is blank")
    return result


def _project_path(raw: str | os.PathLike[str]) -> Path:
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def _asset_bytes(name: str) -> bytes:
    path = ASSETS_DIR / name
    _require_file(path, f"canonical asset {name}")
    data = path.read_bytes()
    actual = _sha256_bytes(data)
    expected = EXPECTED_ASSET_HASHES[name]
    if actual != expected:
        raise IntegrityError(
            f"canonical asset {name} does not match the designated source hash "
            f"(expected {expected}, got {actual})"
        )
    return data


def _lock_for(metadata_bytes: bytes, asset_bytes: dict[str, bytes]) -> dict[str, Any]:
    return {
        "format": 1,
        "assets": {name: _sha256_bytes(data) for name, data in asset_bytes.items()},
        "main_sha256": _sha256_bytes(DRIVER_BYTES),
        "metadata_sha256": _sha256_bytes(metadata_bytes),
    }


def _atomic_write(path: Path, data: bytes) -> None:
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def _empty_metadata() -> dict[str, Any]:
    return {field: "" if field in STRING_FIELDS else [] for field in METADATA_FIELDS}


def init_project(raw_project: str | os.PathLike[str]) -> Path:
    project = _project_path(raw_project)
    if _is_symlink(project):
        raise TemplateError(f"project must not be a symlink: {project}")
    project.mkdir(parents=True, exist_ok=True)
    if not project.is_dir():
        raise TemplateError(f"project is not a directory: {project}")
    index = project / "index.typ"
    if index.exists() or _is_symlink(index):
        if _is_symlink(index) or not index.is_file():
            raise TemplateError(f"existing index.typ is not a regular file: {index}")
        index_exists = True
    else:
        index_exists = False
    protected = project / ".guap"
    if protected.exists() or _is_symlink(protected):
        raise TemplateError(f"refusing to overwrite existing protected directory: {protected}")

    assets = {name: _asset_bytes(name) for name in EXPECTED_ASSET_HASHES}
    protected.mkdir()
    try:
        if not index_exists:
            _atomic_write(index, b"// Edit this file: report body only.\n")
        for name, data in assets.items():
            _atomic_write(protected / name, data)
        _atomic_write(protected / "main.typ", DRIVER_BYTES)
        metadata_bytes = _json_bytes(_empty_metadata())
        _atomic_write(protected / "metadata.json", metadata_bytes)
        _atomic_write(protected / "lock.json", _json_bytes(_lock_for(metadata_bytes, assets)))
    except BaseException:
        shutil.rmtree(protected, ignore_errors=True)
        if not index_exists:
            try:
                index.unlink()
            except FileNotFoundError:
                pass
        raise
    return project


def _load_verified_project(raw_project: str | os.PathLike[str]) -> tuple[Path, dict[str, Any]]:
    project = _project_path(raw_project)
    if _is_symlink(project) or not project.is_dir():
        raise IntegrityError(f"project is missing or not a regular directory: {project}")
    _require_file(project / "index.typ", "index.typ")
    protected = project / ".guap"
    _require_dir(protected, ".guap")
    assets = {name: _asset_bytes(name) for name in EXPECTED_ASSET_HASHES}
    for name, canonical in assets.items():
        protected_file = protected / name
        _require_file(protected_file, f"protected {name}")
        if protected_file.read_bytes() != canonical:
            raise IntegrityError(f"protected {name} differs from the canonical asset")
    main = protected / "main.typ"
    _require_file(main, "protected main.typ")
    if main.read_bytes() != DRIVER_BYTES:
        raise IntegrityError("protected main.typ differs from the fixed generator driver")
    metadata_path = protected / "metadata.json"
    metadata = _read_json(metadata_path, "metadata.json")
    metadata = _validate_metadata(metadata)
    lock_path = protected / "lock.json"
    lock = _read_json(lock_path, "lock.json")
    expected_lock = _lock_for(metadata_path.read_bytes(), assets)
    if lock != expected_lock:
        raise IntegrityError("lock.json does not match protected files; metadata was not changed through the CLI")
    return project, metadata


def check_project(raw_project: str | os.PathLike[str]) -> dict[str, Any]:
    _, metadata = _load_verified_project(raw_project)
    return metadata


def update_title(raw_project: str | os.PathLike[str], data_file: str | os.PathLike[str]) -> Path:
    project, current = _load_verified_project(raw_project)
    data_path = _project_path(data_file)
    incoming = _read_json(data_path, "title data")
    if not isinstance(incoming, dict):
        raise TemplateError("title data must be a JSON object")
    unknown = sorted(set(incoming) - set(METADATA_FIELDS))
    if unknown:
        raise TemplateError("unknown metadata field(s): " + ", ".join(unknown))
    merged = dict(current)
    merged.update(incoming)
    metadata = _validate_metadata(merged)
    metadata_bytes = _json_bytes(metadata)
    assets = {name: _asset_bytes(name) for name in EXPECTED_ASSET_HASHES}
    _atomic_write(project / ".guap" / "metadata.json", metadata_bytes)
    _atomic_write(project / ".guap" / "lock.json", _json_bytes(_lock_for(metadata_bytes, assets)))
    _load_verified_project(project)
    return project


def build_project(raw_project: str | os.PathLike[str]) -> Path:
    project, metadata = _load_verified_project(raw_project)
    _validate_metadata(metadata, complete=True)
    output = project / "report.pdf"
    if _is_symlink(output):
        raise IntegrityError(f"report.pdf must not be a symlink: {output}")
    if output.exists() and not output.is_file():
        raise IntegrityError(f"report.pdf is not a regular file: {output}")
    typst = shutil.which("typst")
    if typst is None:
        raise TemplateError("typst executable was not found on PATH")
    fd, temporary = tempfile.mkstemp(prefix=".report.", suffix=".pdf", dir=str(project))
    os.close(fd)
    temporary_path = Path(temporary)
    try:
        temporary_path.unlink()
        command = [
            typst,
            "compile",
            "--root",
            str(project),
            "--diagnostic-format",
            "short",
            str(project / ".guap" / "main.typ"),
            str(temporary_path),
        ]
        completed = subprocess.run(command, text=True, capture_output=True)
        if completed.returncode != 0:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass
            detail = (completed.stderr or completed.stdout).strip()
            raise TemplateError(f"Typst compile failed (report.pdf was not replaced): {detail}")
        if not temporary_path.is_file() or temporary_path.stat().st_size == 0:
            raise TemplateError("Typst produced no non-empty PDF; report.pdf was not replaced")
        _load_verified_project(project)
        os.replace(temporary_path, project / "report.pdf")
    finally:
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass
    return project / "report.pdf"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "check", "build"):
        command = commands.add_parser(name)
        command.add_argument("project", type=Path)
    title = commands.add_parser("title")
    title.add_argument("project", type=Path)
    title.add_argument("--data", required=True, type=Path, help="JSON metadata fields to update")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            project = init_project(args.project)
            print(f"initialized protected GUAP template: {project}")
        elif args.command == "title":
            project = update_title(args.project, args.data)
            print(f"updated title metadata: {project / '.guap' / 'metadata.json'}")
        elif args.command == "check":
            metadata = check_project(args.project)
            status = "complete" if all(metadata.get(field) for field in METADATA_FIELDS) else "initialized (metadata incomplete)"
            print(f"protected GUAP template OK: {args.project} ({status})")
        elif args.command == "build":
            output = build_project(args.project)
            print(f"built report: {output}")
        return 0
    except (TemplateError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
