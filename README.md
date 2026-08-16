# guap-skill

Standalone GUAP Agent Skill and dependency-free Python tools for Hermes. This
repository does **not** contain an MCP server and does not require package
installation or a build.

## Contents

```text
skills/guap-pro/SKILL.md
skills/guap-pro/guap.py       # read-only cabinet CLI
skills/guap-pro/relay.py      # optional short-lived login relay
skills/guap-pro/references/
tests/
```

The skill depends on the generic [`labflow`](https://github.com/pank-su/labflow)
skill. It adds GUAP-specific rules, teacher patterns, subject patterns, and a
read-only CLI for `pro.guap.ru`.

## Hermes and Telegram

Before using an account session, Hermes must ask the user for explicit approval in
Telegram. Before uploads or other state changes, it must ask again for that exact
action.

The optional `relay.py` provides a short-lived custom HTTPS login page for cases
where the user is remote and GUAP keeps invalidating the session. The user opens
the page from a phone and enters credentials there. The form is forwarded through
the Hermes host's outbound IP. This is a credential relay, not end-to-end
forwarding: the Hermes process can technically see the password in memory while
forwarding it. The page discloses this before submission.

The relay never writes passwords or form bodies to logs/files and stores only the
resulting session Cookie header with mode `0600` under `$HERMES_HOME/guap-pro/`.
Use it only behind HTTPS and only after Telegram approval.

## CLI

Read-only commands use the Python standard library:

```bash
python3 skills/guap-pro/guap.py pro check
python3 skills/guap-pro/guap.py pro tasks --format json
python3 skills/guap-pro/guap.py pro task <TASK_ID> --format json
python3 skills/guap-pro/guap.py pro materials --format json
python3 skills/guap-pro/guap.py pro profile --format json
python3 skills/guap-pro/guap.py pro subjects --format json
python3 skills/guap-pro/guap.py pro subject <SUBJECT_ID> --format json
python3 skills/guap-pro/guap.py pro marks --format json
python3 skills/guap-pro/guap.py pro schedule --date YYYY-MM-DD --format json
python3 skills/guap-pro/guap.py pro reports --format json
python3 skills/guap-pro/guap.py pro notices --format json
python3 skills/guap-pro/guap.py pro professors --format json
```

The added read-only methods cover disciplines, subject details, grades,
schedule, submitted reports, announcements, and teacher search. Filters are
available for semester, subject, status, text search, teacher, group, building,
room, and pagination where the cabinet exposes them.

Local interactive authentication opens persistent Chrome/Chromium state under
`$HERMES_HOME/guap-pro/chrome-profile/`:

```bash
python3 skills/guap-pro/guap.py pro auth
```

Remote relay, after explicit user approval:

```bash
python3 skills/guap-pro/relay.py \
  --bind 0.0.0.0 \
  --port 8765 \
  --public-url https://login.example.com \
  --approval-scope 'GUAP read-only access'
```

The command prints a short-lived login URL as JSON and waits for the user-driven
login. It rejects non-HTTPS public URLs. Put a real TLS reverse proxy in front of
it, or provide `--certfile` and `--keyfile`.

## References

References are based on the supplied previous-semester archive and are labeled as
confirmed, observed, or user-provided. Current task data always has priority.

## Moodle

Moodle is intentionally not included. It will be a separate project.

## License

MIT
