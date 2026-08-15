# guap-skill

Standalone GUAP Agent Skill and dependency-free Python CLI. This repository does
**not** contain an MCP server and does not require package installation or a build.

## Contents

```text
skills/guap-pro/SKILL.md
skills/guap-pro/guap.py
skills/guap-pro/references/
tests/
```

The skill depends on the generic [`labflow`](https://github.com/pank-su/labflow)
skill. It adds GUAP-specific rules, teacher patterns, subject patterns, and a
read-only CLI for `pro.guap.ru`.

## CLI

```bash
python skills/guap-pro/guap.py pro auth
python skills/guap-pro/guap.py pro check
python skills/guap-pro/guap.py pro tasks --format json
python skills/guap-pro/guap.py pro task <TASK_ID> --format json
python skills/guap-pro/guap.py pro materials --format json
python skills/guap-pro/guap.py pro profile --format json
```

The CLI uses only `urllib` and `html.parser` from the Python standard library.
`pro auth` asks the user to paste the browser Cookie header and saves it to
`~/.config/guap-skill/cookie.txt`. The agent never receives a password.

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
