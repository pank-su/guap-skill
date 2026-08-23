---
name: guap-pro
description: Read GUAP tasks and authorize through Hermes.
version: 0.4.0
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

The examples below use a repository checkout. After installation, resolve the
directory containing this `SKILL.md` as `<skill-root>` and run the same commands
from that directory using `scripts/guap.py`.

```text
terminal(command="python3 skills/guap-pro/scripts/guap.py pro check")
terminal(command="python3 skills/guap-pro/scripts/guap.py pro tasks --format json")
terminal(command="python3 skills/guap-pro/scripts/guap.py pro task <TASK_ID> --format json")
terminal(command="python3 skills/guap-pro/scripts/guap.py pro materials --format json")
terminal(command="python3 skills/guap-pro/scripts/guap.py pro profile --format json")
terminal(command="python3 skills/guap-pro/scripts/guap.py pro subjects --format json")
terminal(command="python3 skills/guap-pro/scripts/guap.py pro subject <SUBJECT_ID> --format json")
terminal(command="python3 skills/guap-pro/scripts/guap.py pro marks --format json")
terminal(command="python3 skills/guap-pro/scripts/guap.py pro schedule --date YYYY-MM-DD --format json")
terminal(command="python3 skills/guap-pro/scripts/guap.py pro reports --format json")
terminal(command="python3 skills/guap-pro/scripts/guap.py pro notices --format json")
terminal(command="python3 skills/guap-pro/scripts/guap.py pro professors --format json")
```

Direct local browser authentication, only when the user explicitly intends to
complete the login on the same computer:

```text
terminal(command="python3 skills/guap-pro/scripts/guap.py pro auth")
```

In a Telegram or other remote-chat session, do **not** start local Chrome by
default. Use the SSH-backed remote relay after approval:

```text
terminal(
  command="python3 skills/guap-pro/scripts/remote_relay.py --ssh-host <approved-vps> --ssh-user <user> --ssh-key ~/.ssh/<key> --remote-port 18765 --public-url https://<approved-host>/guap-relay --approval-scope 'GUAP read-only access'",
  background=true,
  notify_on_complete=true,
  timeout=700
)
```

The approved VPS reverse proxy must strip the public prefix and forward only to
the reverse SSH listener on server loopback. Example Caddy route:

```caddyfile
handle_path /guap-relay/* {
    reverse_proxy 127.0.0.1:18765
}
```

`remote_relay.py` opens the reverse SSH tunnel as an SSH ControlMaster, waits
until `ssh -O check` confirms that the reverse forward is established, prints one
JSON line containing the short-lived URL, runs `relay.py`, and always closes the
tunnel when the login succeeds, fails, or expires. The readiness check has a hard
timeout bounded by the remaining readiness deadline. If SSH exits while the relay
is active, the relay stops promptly and reports `tunnel_failed` instead of waiting
for the TTL. Long-lived SSH stderr is written to a temporary file rather than a
pipe; only a bounded tail is read when reporting a failure. Send the URL to the
approving Telegram user only after checking the scope and hostname. The endpoint
must use HTTPS. Both entry points reject control characters, missing hosts,
userinfo, query or fragment delimiters (including empty `?` or `#`), and malformed
ports. The SSH wrapper also requires local and remote ports in `1..65535` and
rejects empty, option-like, control-character, whitespace, or ambiguous SSH user
and host values.

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
- destroys the in-memory jar after completion or expiry; on tunnel abort it returns
  without waiting for an in-flight upstream request and defers lock-held cleanup
  to a daemon cleanup thread (process exit also clears process memory);
- returns `reauth_required` or `relay_failed` instead of retrying blindly.

The direct `relay.py` CLI and `remote_relay.py` use the same public-URL validation:
only an HTTPS URL with a host and optional path is accepted. Credentials, control
characters, malformed ports, and any query or fragment delimiter—including empty
`?` and `#`—are rejected before the URL is printed or used.
Prefer an existing HTTPS reverse proxy on infrastructure approved by the user.
TLS termination is a trust boundary: the machine or provider terminating TLS can
technically inspect form contents. If that is a third-party tunnel provider, name
it and obtain explicit approval before starting; never describe edge-terminated
HTTPS as end-to-end encrypted. A user-controlled VPS plus a reverse SSH tunnel is
the preferred remote-chat setup. Bind the remote forwarded port to `127.0.0.1`,
keep the URL short-lived, and do not send it to anyone except the approving user.

## Procedure

1. Ask for Telegram approval naming `read-only access` or the exact state-changing scope.
2. If the cookie session may be valid, run `guap.py pro check` through `terminal`.
3. If the result contains `reauth_required`, choose authentication from the actual
   communication channel: use `remote_relay.py` for Telegram/remote chat; use
   `guap.py pro auth` only after the user explicitly says they can use the same Mac.
4. For a remote relay, confirm the exact HTTPS hostname and who controls TLS
   termination. Obtain separate approval before using any third-party tunnel.
5. Start `remote_relay.py` through `terminal(background=true,
   notify_on_complete=true)`. Inspect its first JSON line without copying cookies
   into the conversation.
6. Send only the relay URL to the approving user.
7. Wait for the process to report `authenticated`; do not assume success from the
   user saying that the form was submitted. The wrapper closes SSH automatically.
8. Run `guap.py pro check` again, then retrieve the requested data as JSON.
9. For lab work, load `subjects`, `subject`, `tasks`, `reports`, `materials`, and
   matching teacher/subject references together; do not infer status from one page.
10. For planning, use `schedule`, `marks`, and `notices` as separate current sources.
11. Hand the sanitized current task context to `labflow` for the generic workflow.
12. Before any upload, ask for a separate Telegram confirmation and re-check the task.

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
- Never commit `$HERMES_HOME/guap-pro/cookie.txt`, SSH private keys, or a browser profile.
- `guap.py pro auth` launches a local browser. Never choose it merely because the
  conversation is in Telegram; remote chat requires `remote_relay.py` or an explicit
  statement that the user is at the same computer.
- On macOS, Chrome lives under `/Applications/...` and the executable path contains
  spaces. Preserve absolute paths as one argv element; failed launches must release
  the profile lock.
- The relay is not a general reverse proxy. Limit its lifetime, hostname, and scope.

## Verification

Use the Hermes `terminal` tool to run:

```text
terminal(command="python3 -m unittest discover -s tests -v")
terminal(command="python3 skills/guap-pro/scripts/guap.py --help")
terminal(command="python3 skills/guap-pro/scripts/relay.py --help")
terminal(command="python3 skills/guap-pro/scripts/remote_relay.py --help")
terminal(command="python3 -m py_compile skills/guap-pro/scripts/guap.py skills/guap-pro/scripts/relay.py skills/guap-pro/scripts/remote_relay.py")
```

A successful workflow has a current authenticated check, a JSON task response, and
no password, cookie value, or private task URL in the returned Hermes context.

## References

- `references/guap-rules.md` — source precedence and cabinet rules.
- `references/teachers/` — teacher-specific patterns and preparation notes.
- `references/subjects/` — subject-specific patterns.
