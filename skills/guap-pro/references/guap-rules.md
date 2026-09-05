# GUAP Cabinet Rules

## Current-task handling

- Read the full task detail before preparing the source context.
- Treat `deadline`, `allowed_extensions`, `description`, `extra_materials`, and
  submitted-report status as separate fields.
- If the status is `ожидает проверки`, do not create a duplicate submission unless
  the user explicitly requests it.
- If no deadline is shown, write `deadline: unknown` and do not calculate one.
- Preserve references to defense and submission requirements from the task text
  in the handoff; do not invent missing requirements.
- Use current task data and attachments for cabinet state. Preserve conflicts
  with user-provided information instead of resolving them from archive assumptions.

## Academic handoff

Pass sanitized current source records to `labflow-guap`. That skill owns teacher
and subject notes, preparation for defense, report formatting and protected templates.
Do not store or duplicate its academic reference directories in `guap-pro`.
