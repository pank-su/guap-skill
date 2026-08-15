# guap-skill

Standalone GUAP Agent Skill and Python CLI. This repository does **not** contain
an MCP server.

## Contents

```text
skills/guap-pro/SKILL.md
skills/guap-pro/references/
guap.py
pyproject.toml
```

The skill depends on the generic [`labflow`](https://github.com/pank-su/labflow)
skill. It adds GUAP-specific rules, teacher patterns, subject patterns, and a
read-only CLI for `pro.guap.ru`.

## Install

```bash
uv sync
```

## CLI

```bash
uv run guap-pro pro auth
uv run guap-pro pro check
uv run guap-pro pro tasks --format json
uv run guap-pro pro task <TASK_ID> --format json
uv run guap-pro pro materials --format json
uv run guap-pro pro profile --format json
```

`guap.py` uses direct HTTP requests and HTML parsing. Authentication is completed
by the user in a browser; the password is never entered by the agent.

## References

References are based on the supplied previous-semester archive and are labeled
as confirmed, observed, or user-provided. Current task data always has priority.

Important examples include preparation advice for Вершинина, Colab and defense
patterns for Майер, sequential numerical tables for Пичугин, and title-page/PDF
requirements observed for Климочкина.

## Moodle

Moodle is intentionally not included. It will be a separate project.

## License

MIT
