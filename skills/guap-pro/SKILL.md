---
name: guap-pro
description: Use the GUAP cabinet CLI with subject references.
version: 0.1.0
author: Vasilii Pankov (pank-su), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [GUAP, CLI, pro.guap.ru, labs, teachers]
    related_skills: []
    external_skills: [labflow]
---

# guap-pro

Use the standalone `guap.py` CLI to read the GUAP personal cabinet at
`pro.guap.ru`, then apply the teacher and subject references in this repository.
This skill depends on the generic `labflow` skill for task context, coding,
mathematics, reporting, and self-review. It contains no MCP server.

## When to Use

- The user asks for current GUAP tasks, deadlines, materials, profile data, or submission status.
- A labflow project needs a teacher or subject pattern from `references/`.
- A report must be checked against GUAP task metadata before submission.

Do not use it for Moodle. Moodle is a separate future project.

## Prerequisites

- Python 3.10+.
- Install dependencies with `uv sync`.
- A GUAP account.
- `labflow` available as the generic workflow skill.

## CLI

From the repository root:

```bash
uv run python guap.py pro auth
uv run python guap.py pro check
uv run python guap.py pro tasks --format json
uv run python guap.py pro task <TASK_ID> --format json
uv run python guap.py pro materials --format json
uv run python guap.py pro profile --format json
```

Authentication opens a browser. The user enters credentials manually; the CLI
stores only a session cookie file under `~/.config/guap-skill/`. Never commit it.

## Procedure

1. Run `guap.py pro check`.
2. If authentication is invalid, ask the user to complete `guap.py pro auth`.
3. Retrieve the full task with `guap.py pro task <ID> --format json`.
4. Load `references/guap-rules.md`.
5. Load the matching teacher and subject references.
6. Copy only current, confirmed requirements into the labflow context.
7. Run the generic `labflow` workflow.
8. Before submission, re-check task ID, deadline, extension, and submitted-report status.

## Source Policy

Use information in this order:

1. Current task details from the CLI.
2. The current methodology or attached files.
3. Explicit user-provided notes.
4. References marked `confirmed`.
5. References marked `observed` as planning hints only.

Do not turn an old archive pattern into a current requirement without checking the
live task. If sources conflict, preserve the conflict and ask the user.

## GUAP Rules

- A task marked `ожидает проверки` is already submitted; do not redo it by default.
- A missing deadline is not permission to invent one.
- A title page is generated only from known context metadata.
- If the task mentions a defense, prepare the student to explain the method,
  inputs, intermediate results, and conclusions.
- Do not upload a report automatically; ask the user to approve it.
- Do not commit cookies, tokens, private task URLs, or downloaded personal data.

## References

- `references/guap-rules.md` — source precedence and cabinet rules.
- `references/teachers/` — teacher-specific patterns and preparation notes.
- `references/subjects/` — subject-specific patterns.

## Completion

This skill is complete when current cabinet data has been captured in the project
context, the generic `labflow` workflow has produced the artifacts, and no GUAP
specific claim relies only on an old archive.
