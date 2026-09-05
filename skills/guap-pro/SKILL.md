---
name: guap-pro
description: Read GUAP tasks and authorize through Hermes.
version: 0.6.3
author: Vasilii Pankov (pank-su), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [GUAP, CLI, Telegram, authentication, labs]
    related_skills: [labflow-guap]
    external_skills: [labflow]
---

# guap-pro Skill

Use the dependency-free CLI and optional credential relay to work with the GUAP
personal cabinet from Hermes and Telegram. This skill owns cabinet access, authentication
and sanitized task retrieval. `labflow-guap` separately owns GUAP artifact/style
adaptation; generic `labflow` owns academic phase ordering. It contains no MCP server.

A request to edit a supplied PDF, report or presentation is not a cabinet-access
request: use local sources and `labflow-guap`, without reading cookies, authenticating,
or fetching task data. Authentication and read-only permits never authorize publishing
code or submitting coursework. Preserve the existing permit, relay and monitor boundaries.

## When to Use

- The user asks for current GUAP tasks, deadlines, materials, profile data, or status.
- A project needs current task, subject or professor records retrieved from the cabinet.
  Teaching notes and preparation/defense guidance belong to `labflow-guap`, not this skill.
- The user needs remote re-authentication because GUAP invalidated the session.

Do not use it for Moodle. Do not use the relay for unrelated websites.

## Prerequisites

- Python 3.10+ with only the standard library.
- The `labflow-guap` and `labflow` skills are needed only for producing academic artifacts, not cabinet-only reads.
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

Before account access, require either a current-session approval naming the scope or
an explicit standing read-only grant. A standing grant is opt-in, remains valid
until its declared expiry or revocation, and must be represented by a mode-0600
permit at `$HERMES_HOME/guap-pro/background-permit.json`. It may cover only the
exact read-only commands `tasks`, `marks`, `notices`, and `reports`; the monitor
must fail closed if the permit is missing, disabled, malformed, or has a different
scope.

Rules:

1. Without a current approval or valid standing permit, do not launch a browser,
   read cookies, start a relay, or request GUAP data.
2. Current-session approval applies only to its named scope. Standing approval
   applies only to the exact commands in its permit and never authorizes login.
3. Ask again before starting a credential relay, uploading, resubmitting, changing
   cabinet state, or expanding the standing scope.
4. Revocation takes effect by disabling/removing the permit and pausing/removing
   the corresponding cron job. A revoked permit must fail closed.
5. Do not treat a reply to an unrelated message as approval.
6. Never put the password or cookies in Telegram, tool output, logs, reports, or Git.

The CLI cannot cryptographically verify a Telegram reply. The `--approval-scope`
argument is an explicit operational guard for interactive authentication: Hermes
supplies it only after receiving approval and must keep the scope identical to the
confirmation. A standing read-only permit is a separate local capability and does
not authorize `remote_relay.py` or `guap.py pro auth`.

## Standing Background Monitor

A no-agent cron monitor may use a valid standing permit to call only `tasks`,
`marks`, `notices`, and `reports`. Keep the scheduler wake-up deterministic and the
actual cabinet requests randomized locally. For this profile, wake every 15 minutes,
choose 1–8 active ticks between requests (15–120 minutes), and make no cabinet
requests from 23:00 through 07:59 local time. Night ticks must not consume the
remaining active-tick counter.

The monitor must establish a silent baseline, emit only exact deltas, persist only
normalized records and scheduling metadata with mode `0600`, and deduplicate
unchanged, repeated-error, and `reauth_required` states. It must never invoke
`auth`, start a relay, or perform a write. When reauthentication is required, send
one sanitized notice and wait for a separate current-session authentication
approval.

### Daily Task and Material Sync

A separately approved no-agent daily sync may use
`$HERMES_HOME/guap-pro/daily-sync-permit.json` with the exact scope `tasks`,
`task`, `materials`, and `subjects`. Keep this permit separate from the standing
monitor permit. It authorizes only read-only retrieval and local file writes; it
never authorizes `auth`, a credential relay, report upload, task submission, or
other GUAP mutations.

The sync must filter user-declared excluded subjects before fetching task details,
downloading materials, or creating work. Store task sources, subject indexes,
material files, and external-link references locally with private permissions.
Create blocked, unassigned Labflow Kanban cards with a stable idempotency key
derived from the GUAP task ID and a durable workspace. They must remain
non-dispatchable until the user manually reviews, assigns, and unblocks them. Each
card must forbid GUAP submission and use only the local source and material copies. A first baseline is silent except for newly
created actionable lab cards; unchanged runs produce no output. The daily sync
comments task-status transitions on existing cards without delivering a duplicate
user alert; the standing monitor remains the single source of user-visible task
status deltas. Deliver only new actionable labs, unique sync errors, or
`reauth_required` from the daily job.

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
- returns `reauth_required` or `relay_failed` instead of retrying blindly;
- sends the terminal HTML response before setting the completion event, so the
  server and SSH tunnel cannot close while the browser is still receiving it.

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

1. Verify a current-session approval or an enabled, exact-scope standing read-only
   permit before reading the cookie or requesting cabinet data.
2. If the cookie session may be valid, run `guap.py pro check` through `terminal`.
3. If the result contains `reauth_required`, obtain a separate current-session
   approval for authentication. Then choose authentication from the actual
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
9. For lab work, retrieve only sources required by the task and authorized by the
   current scope. A standing/daily permit does not authorize broader commands such
   as `subject` or `profile`. Do not run this interactive procedure under a narrow
   permit if it would expand access; use the permit's dedicated read-only workflow.
   Preserve live cabinet status and attached methodology as separate source records.
10. For planning, use `schedule`, `marks`, and `notices` only when each command is
    authorized and relevant; do not infer one source from another.
11. Hand only sanitized task context and approved local source copies to
    `labflow-guap` and `labflow`. Record GUAP task ID, source path, retrieval time,
    requirements and unresolved conflicts; never pass cookies, relay links or credentials.
12. Before any upload, ask for a separate Telegram confirmation and re-check the task.

## Source Policy

Use information in this order:

1. Current task details from the live CLI.
2. The current methodology or attached files.
3. Explicit user-provided notes.
Academic interpretation and historical teacher/subject notes belong to
`labflow-guap`; hand over current source records without imposing those notes.

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
Teacher and subject preparation references are maintained in `labflow-guap`, not
in this skill.
