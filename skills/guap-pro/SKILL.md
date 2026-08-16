---
name: guap-pro
description: Read GUAP tasks and authorize through Hermes.
version: 0.3.0
author: Vasilii Pankov (pank-su), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [GUAP, CLI, Telegram, authentication, labs]
    related_skills: []
    external_skills: [labflow]
---

# guap-pro Skill

Use the dependency-free CLI and optional credential relay to work with the GUAP
personal cabinet from Hermes and Telegram. This skill adds GUAP teacher and subject
references on top of the generic `labflow` skill. It contains no MCP server.

## When to Use

- The user asks for current GUAP tasks, deadlines, materials, profile data, or status.
- A `labflow` project needs GUAP teacher, subject, submission, or defense rules.
- The user needs remote re-authentication because GUAP invalidated the session.

Do not use it for Moodle. Do not use the relay for unrelated websites.

## Prerequisites

- Python 3.10+ with only the standard library.
- The `labflow` skill available separately.
- A user-approved HTTPS endpoint for the relay, or a local Chrome/Chromium window.
- The user must explicitly approve account access in Telegram before Hermes reads
  cookies, opens the relay, or requests GUAP data.

## Quick Reference

Read-only cabinet commands through the Hermes `terminal` tool:

```text
terminal(command="python3 skills/guap-pro/guap.py pro check")
terminal(command="python3 skills/guap-pro/guap.py pro tasks --format json")
terminal(command="python3 skills/guap-pro/guap.py pro task <TASK_ID> --format json")
terminal(command="python3 skills/guap-pro/guap.py pro materials --format json")
terminal(command="python3 skills/guap-pro/guap.py pro profile --format json")
terminal(command="python3 skills/guap-pro/guap.py pro subjects --format json")
terminal(command="python3 skills/guap-pro/guap.py pro subject <SUBJECT_ID> --format json")
terminal(command="python3 skills/guap-pro/guap.py pro marks --format json")
terminal(command="python3 skills/guap-pro/guap.py pro schedule --date YYYY-MM-DD --format json")
terminal(command="python3 skills/guap-pro/guap.py pro reports --format json")
terminal(command="python3 skills/guap-pro/guap.py pro notices --format json")
terminal(command="python3 skills/guap-pro/guap.py pro professors --format json")
```

Direct local browser authentication:

```text
terminal(command="python3 skills/guap-pro/guap.py pro auth")
```

Remote credential relay, only after Telegram approval:

```text
terminal(
  command="python3 skills/guap-pro/relay.py --bind 0.0.0.0 --port 8765 --public-url https://<approved-host> --approval-scope 'GUAP read-only access'",
  background=true,
  timeout=10
)
```

The command prints one JSON line containing a short-lived URL. Send that URL to
the user in Telegram only after checking that the scope and hostname are correct.
The endpoint must terminate HTTPS before reaching the relay, or the relay must be
started with `--certfile` and `--keyfile`.

## Telegram Approval Gate

Before any account operation, ask in Telegram with an explicit scope, for example:

> Разрешить открыть ГУАП и получить текущие задания? Это read-only доступ.

Rules:

1. No clear approval means no browser launch, cookie read, relay start, or GUAP request.
2. Approval applies only to the named scope and current session.
3. Ask again before uploading, resubmitting, or changing cabinet state.
4. Do not treat a reply to an unrelated message as approval.
5. Never put the password or cookies in Telegram, tool output, logs, reports, or Git.

The CLI cannot cryptographically verify a Telegram reply. The `--approval-scope`
argument is an explicit operational guard: Hermes supplies it only after receiving
approval and must keep the scope identical to the confirmation.

## Credential Relay

`relay.py` serves a short-lived custom HTTPS page and forwards the submitted GUAP or
SSO form through the Hermes host's outbound IP. This is a deliberate credential
relay: the Hermes process technically sees the password in memory while forwarding
it. The page warns the user about this before the form is submitted. Do not call it
end-to-end or password-blind.

The relay:

- generates a random single-use URL token;
- expires the session after a short TTL;
- keeps upstream cookies in an isolated in-memory cookie jar;
- preserves hidden fields, CSRF fields, redirects, and multi-step forms where possible;
- writes only the resulting Cookie header to `$HERMES_HOME/guap-pro/cookie.txt`;
- uses mode `0600` for the cookie file;
- never logs request paths, form bodies, passwords, or cookies;
- destroys the in-memory jar after completion or expiry;
- returns `reauth_required` or `relay_failed` instead of retrying blindly.

The relay needs a real HTTPS public URL. A plain `http://` public URL is rejected.
Prefer an existing HTTPS reverse proxy with access controls. Do not put the relay
behind an unprotected public hostname. Do not send the relay URL to anyone except
the Telegram user who approved the scope.

## Procedure

1. Ask for Telegram approval naming `read-only access` or the exact state-changing scope.
2. If the cookie session may be valid, run `guap.py pro check` through `terminal`.
3. If the result contains `reauth_required`, ask whether to start the relay.
4. After approval, start `relay.py` through `terminal(background=true)` and inspect
   its JSON output without copying cookies into the conversation.
5. Send only the relay URL to the approving user in Telegram.
6. Wait for the relay process to report `authenticated`; do not assume success from
   the user saying that the form was submitted.
7. Run `guap.py pro check` again, then retrieve the requested data as JSON.
8. For lab work, load `subjects`, `subject`, `tasks`, `reports`, `materials`, and
   matching teacher/subject references together; do not infer status from one page.
9. For planning, use `schedule`, `marks`, and `notices` as separate current sources.
10. Hand the sanitized current task context to `labflow` for the generic workflow.
11. Before any upload, ask for a separate Telegram confirmation and re-check the task.

## Source Policy

Use information in this order:

1. Current task details from the live CLI.
2. The current methodology or attached files.
3. Explicit user-provided notes.
4. References marked `confirmed`.
5. References marked `observed` as planning hints only.

Never turn an old archive pattern into a current requirement without checking the
live task. If sources conflict, preserve the conflict and ask the user.

## Pitfalls

- GUAP may invalidate sessions after several hours. A persistent browser profile or
  cookie file cannot defeat a server-side TTL; detect `reauth_required` every time.
- SSO may use JavaScript, CAPTCHA, hidden fields, or a second-factor step. Stop with
  `relay_failed` if the form cannot be forwarded reliably.
- Never retry a login or submission blindly: a relay may have reached GUAP already.
- Never use the relay for uploads unless the user approved that exact action.
- Never commit `$HERMES_HOME/guap-pro/cookie.txt` or a browser profile.
- The relay is not a general reverse proxy. Limit its lifetime, hostname, and scope.

## Verification

Use the Hermes `terminal` tool to run:

```text
terminal(command="python3 -m unittest discover -s tests -v")
terminal(command="python3 skills/guap-pro/guap.py --help")
terminal(command="python3 skills/guap-pro/relay.py --help")
terminal(command="python3 -m py_compile skills/guap-pro/guap.py skills/guap-pro/relay.py")
```

A successful workflow has a current authenticated check, a JSON task response, and
no password, cookie value, or private task URL in the returned Hermes context.

## References

- `references/guap-rules.md` — source precedence and cabinet rules.
- `references/teachers/` — teacher-specific patterns and preparation notes.
- `references/subjects/` — subject-specific patterns.
