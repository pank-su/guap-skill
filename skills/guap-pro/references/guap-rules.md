# GUAP Rules

These rules are the operational baseline for the GUAP companion skill.

## Evidence labels

- `confirmed` — stated in a current task, methodology, or repeated archive evidence.
- `user_note` — explicitly supplied by the user; keep the provenance visible.
- `observed` — a recurring pattern in the archive that still needs current-task confirmation.

## Current-task handling

- Read the full task detail before creating files.
- Treat `deadline`, `allowed_extensions`, `description`, `extra_materials`, and
  submitted-report status as separate fields.
- If the status is `ожидает проверки`, do not create a duplicate submission unless
  the user explicitly requests it.
- If no deadline is shown, write `deadline: unknown` and do not calculate one.
- If the task says `защита`, add oral-preparation steps to the checklist.

## Report handling

- Generate a title page only from the context supplied by the user or the current
  task. Never fill a teacher, department, group, or city from memory.
- Match the required file extension exactly.
- Keep the report's calculations and code traceable to real artifacts.
- Do not assume that a previous semester's GOST or title-page layout is current.

## Archive scope

The supplied archive contains projects and session data from the 2025/2026 spring
semester. Its teacher advice is historical context, not a live university rule.
