# Installing `guap-pro`

`guap-pro` follows the open Agent Skills format. The repository contains one
portable skill bundle; the target harness decides where that bundle is installed.
No Python package installation or build is required.

## Claude Code, Codex CLI, and OpenCode

Install globally for the current user with the shared `npx skills` installer.
Run it without `--agent` or `--yes`: the installer will show the detected
harnesses, let the user choose the targets, and ask for confirmation:

```bash
npx skills add pank-su/guap-skill \
  --skill guap-pro \
  --global \
  --copy
```

Install into the current project instead:

```bash
npx skills add pank-su/guap-skill \
  --skill guap-pro \
  --copy
```

Project installation is committed with the project. The installer writes the
harness-specific directories; do not manually duplicate the skill body.

The native discovery locations are:

| Harness | Project | User |
| --- | --- | --- |
| Claude Code | `.claude/skills/` | `~/.claude/skills/` |
| Codex CLI | `.agents/skills/` | `~/.agents/skills/` |
| OpenCode | `.opencode/skills/` | `~/.config/opencode/skills/` |

OpenCode also reads the Claude- and Agent-Skills-compatible locations.

## Hermes Agent

Install directly from GitHub:

```bash
hermes skills install \
  https://raw.githubusercontent.com/pank-su/guap-skill/main/skills/guap-pro/SKILL.md \
  --name guap-pro
```

Verify:

```bash
hermes skills list
```

The installed skill becomes available as `/guap-pro` in Hermes CLI and connected
messaging platforms. Hermes keeps it under `$HERMES_HOME/skills/`.

## Use from a checkout

For development or a local checkout:

```bash
python3 skills/guap-pro/scripts/guap.py pro check
python3 skills/guap-pro/scripts/guap.py pro tasks --format json
```

The skill's runtime files are under `skills/guap-pro/scripts/`; references are
under `skills/guap-pro/references/`. A harness should resolve paths relative to
the directory containing `SKILL.md`, not assume the user's project CWD.

## Updating or removing

```bash
npx skills update guap-pro
npx skills remove guap-pro
hermes skills update
hermes skills uninstall guap-pro
```

After installation, restart the harness if it does not discover the updated
skill immediately.

## Security

Inspect the repository and `SKILL.md` before installing. The relay in
`scripts/relay.py` is optional and must be used only with explicit Telegram
approval and an HTTPS endpoint. It handles login credentials in process memory;
it never belongs in a project with committed cookies or secrets.
