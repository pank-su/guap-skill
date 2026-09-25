#!/usr/bin/env python3
"""Compile source-attributed GUAP formatting profiles, without modifying templates."""

import argparse
import math
import json
from pathlib import Path
import sys

PROFILES = Path(__file__).resolve().parents[1] / "assets/profiles"
NAMES = ("physics", "calculation", "coursework", "lecture")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load(path):
    require(Path(path).stat().st_size <= 1024 * 1024, "JSON exceeds limit")

    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result

    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=pairs)


def plain(value):
    require(
        type(value) is str
        and 0 < len(value) <= 4096
        and not any(ord(c) < 32 for c in value),
        "expected plain attribution",
    )


def validate_rule(key, value, default):
    if key in ("body_pt", "table_pt"):
        require(
            type(value) in (int, float) and math.isfinite(value) and 8 <= value <= 36,
            "invalid text size",
        )
    elif key == "rounding_decimals":
        require(
            value is None or type(value) is int and 0 <= value <= 12,
            "invalid displayed precision",
        )
    elif type(default) is bool:
        require(type(value) is bool, "expected boolean rule")
    elif type(default) is list:
        require(type(value) is list and 0 < len(value) <= 64, "invalid sections")
        for entry in value:
            plain(entry)
        require(len(value) == len(set(value)), "duplicate sections")
    else:
        plain(value)


def apply_overrides(rules, provenance, overrides):
    require(
        type(overrides) is dict
        and set(overrides) == {"methodology", "user", "accepted_exceptions"},
        "invalid override fields",
    )
    accepted = overrides["accepted_exceptions"]
    require(
        type(accepted) is list
        and all(type(k) is str for k in accepted)
        and len(accepted) == len(set(accepted)),
        "invalid accepted exceptions",
    )
    conflicts = []
    for tier in ("methodology", "user"):
        values = overrides[tier]
        require(type(values) is dict and values.keys() <= rules.keys(), "unknown rule")
        for key, record in values.items():
            require(
                type(record) is dict and set(record) == {"value", "source", "locator"},
                "override needs value/source/locator",
            )
            plain(record["source"])
            plain(record["locator"])
            validate_rule(key, record["value"], rules[key])
            if (
                tier == "user"
                and key in overrides["methodology"]
                and rules[key] != record["value"]
            ):
                conflicts.append(
                    {
                        "field": key,
                        "methodology": rules[key],
                        "user": record["value"],
                        "accepted": key in accepted,
                    }
                )
            rules[key] = record["value"]
            provenance[key] = {
                "tier": tier,
                "source": record["source"],
                "locator": record["locator"],
            }
    require(
        set(accepted) <= {entry["field"] for entry in conflicts},
        "exception without an actual conflict",
    )
    return conflicts


def compile_profile(
    name, output, overrides_path=None, scope="full", output_format=None, domains=None
):
    profile = load(PROFILES / (name + ".json"))
    rules = profile["rules"]
    output_format = output_format or profile["default_format"]
    domains = (
        domains
        if domains is not None
        else ([] if scope == "revision" else profile["default_domains"])
    )
    require(len(domains) == len(set(domains)), "duplicate domain")
    phases = ([] if scope == "revision" else ["context"]) + sorted(
        domains, key=("code", "math").index
    )
    phases += {"pdf": ["report"], "notes": ["notes"], "csv": []}[output_format] + [
        "verify"
    ]
    if scope != "revision":
        phases.append("review")
    contract = {
        "version": 1,
        "profile": name,
        "status": "ready",
        "rules": rules,
        "plan": {"scope": scope, "format": output_format, "phases": phases},
        "provenance": {
            key: {
                "tier": "profile_default",
                "source": "assets/profiles/" + name + ".json",
                "locator": "rules." + key,
            }
            for key in rules
        },
        "conflicts": [],
    }
    if overrides_path:
        contract["conflicts"] = apply_overrides(
            rules, contract["provenance"], load(overrides_path)
        )
        if any(not entry["accepted"] for entry in contract["conflicts"]):
            contract["status"] = "blocked"
    output = Path(output)
    ancestor = output.absolute()
    while True:
        require(not ancestor.is_symlink(), "symlink output unsupported")
        if ancestor.parent == ancestor:
            break
        ancestor = ancestor.parent
    output = output.parent.resolve() / output.name
    require(".guap" not in output.parts, "cannot write protected template directory")
    output.mkdir(parents=True, exist_ok=False)
    (output / "contract.json").write_text(
        json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if output_format == "pdf" and contract["status"] == "ready":
        style = "#let profile-style(body) = {\n"
        style += (
            "  set text(font: "
            + json.dumps(rules["font"], ensure_ascii=False)
            + ", size: "
            + str(rules["body_pt"])
            + "pt)\n"
        )
        style += "  show table: set text(size: " + str(rules["table_pt"]) + "pt)\n"
        if rules["first_level_new_page"]:
            style += (
                "  show heading.where(level: 1): it => { pagebreak(weak: true); it }\n"
            )
        style += "  body\n}\n"
        (output / "style.typ").write_text(style, encoding="utf-8")
    return contract


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    p = sub.add_parser("compile")
    p.add_argument("--profile", choices=NAMES, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--overrides", type=Path)
    p.add_argument(
        "--scope", choices=("full", "revision", "publication"), default="full"
    )
    p.add_argument("--format", choices=("pdf", "notes", "csv"))
    p.add_argument("--domain", choices=("code", "math"), action="append")
    args = parser.parse_args()
    try:
        result = (
            {"profiles": list(NAMES)}
            if args.command == "list"
            else compile_profile(
                args.profile,
                args.output_dir,
                args.overrides,
                args.scope,
                args.format,
                args.domain,
            )
        )
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result.get("status", "ready") == "ready" else 2
    except (ValueError, OSError, UnicodeError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
