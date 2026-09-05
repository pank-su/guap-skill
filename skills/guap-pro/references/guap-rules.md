# GUAP Rules

These rules are the operational baseline for the GUAP companion skill.

## Sources, not confidence badges

Keep plain source attribution (task, methodology, user advice, archive) without
verification/status labels on teachers or subjects. Archive notes are context,
not current requirements. Preserve uncertainty and source conflicts in plain prose.

## Current-task handling

- Read the full task detail before creating files.
- Treat `deadline`, `allowed_extensions`, `description`, `extra_materials`, and
  submitted-report status as separate fields.
- If the status is `ожидает проверки`, do not create a duplicate submission unless
  the user explicitly requests it.
- If no deadline is shown, write `deadline: unknown` and do not calculate one.
- If the task says `защита`, add oral-preparation steps to the checklist.

## Report handling

- For a required GUAP title page, use `labflow-guap` and its protected generator.
  Edit only `index.typ` manually; set title metadata only through the script.
  Preserve the selected completed-lab layout, never redesign it or fill teacher,
  department, group, city or date from an old example. A request for no title page wins.
- Match the required file extension exactly.
- Keep the report's calculations and code traceable to real artifacts.
- Do not assume that a previous semester's GOST or title-page layout is current.

## Archive scope

The supplied archive contains projects and session data from the 2025/2026 spring
semester. Its teacher advice is historical context, not a live university rule.
