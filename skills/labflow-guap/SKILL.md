---
name: labflow-guap
description: "Use when producing or revising GUAP coursework."
version: 0.1.1
author: Vasilii Pankov (pank-su), Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [guap, labflow, coursework, reports, review]
    related_skills: [guap-pro, guap-coursework-artifacts]
    external_skills: [labflow]
---

# Labflow GUAP

Apply a GUAP-specific artifact contract to Labflow. This skill owns source-to-style decisions and bounded revision/acceptance; it neither authenticates to the cabinet nor submits work. `guap-pro` owns cabinet access, `labflow` owns the generic phases, and `guap-coursework-artifacts` owns detailed build/visual procedures. Do not duplicate their implementation here.

## When to Use

- Produce a GUAP lab, course project, explanatory report, or defense presentation.
- Revise an existing GUAP artifact to match a user-designated previous coursework.
- Convert locally supplied GUAP task materials into an auditable Labflow project.

Do not use for cabinet-only reads or unrelated academic institutions.

## Teachers and subjects

This skill owns the academic reference notes in `references/teachers/` and
`references/subjects/`. Read `references/teachers/index.md` and
`references/subjects/index.md`, then only the matching
teacher/subject files when preparing a work or defense. Keep source attribution
without confidence badges; historical advice does not override the current task,
methodology or explicit user corrections. Do not infer an official grading rule
from a teacher–subject association. `guap-pro` only retrieves live cabinet records;
it does not own these preparation notes. The source archive covers the 2025/2026
spring semester; treat its teaching advice as historical context, not a live rule.

## Prerequisites and scope

Use the current attachment or requested artifact first. A local PDF/style correction does not require cabinet access, reauthentication, or a new download. Read the PDF with `read_file` or an extraction skill; a matching filename is not proof that it matches the workspace PDF.

Before acting, classify the request as full deliverable, bounded revision, or publication. Record the selected scope. A request to revise is not permission to commit, push, upload, submit, or start background jobs.

## Procedure

### 1. Pin the task and style sources

1. Read the current task/methodology and latest user corrections.
2. If the user says “like the previous coursework”, locate and read the exact relevant section of that work with `read_file`, not only its template library. Use conversation history only to locate a missing reference.
3. Record a compact contract in `context/artifact-contract.md`: source paths, content requirements, immutable template source, report/presentation format, local overrides, and accepted exceptions. Preserve conflicts with current methodology; do not invent teacher approval or formal submission dates.
4. Use `terminal` with Python `hashlib` to record SHA-256 of an immutable template and compare bytes with the authoritative external source. Git HEAD is a baseline only if the user explicitly designated it.

Done: each requirement/style decision has a source, and the original coursework is untouched.

### 2. Write academic prose, not an implementation checklist

For this user's coursework, unless the current methodology explicitly requires otherwise:

- Introduction follows the previous work's structure: subject/problem context, what the work is devoted to, relevance. Use connected paragraphs rather than a technical task dump.
- General facts may use present tense. Planned work uses future-oriented wording; do not mechanically repeat “будет” in every sentence. Do not describe already completed implementation/results in the introduction.
- Keep UUID, class/API names, framework versions, transaction details and exhaustive pattern inventories in the appropriate technical chapters, not in the introduction by default.
- Explain an entity's Russian meaning before introducing its code identifier.
- No bold, italic or inline-code emphasis in narrative prose. Reduce needless dashes; do not remove meaningful punctuation mechanically.
- Explain the content of figures, not the filesystem paths where their images are stored.

Done: the introduction resembles the designated example in structure and level of detail, not just tense.

### 3. Match report and presentation conventions

- For new labs requiring a title, use the protected generator described in `references/protected-template.md`. Only `index.typ` may be hand-edited; title metadata must be set with the generator's `title` command. Never edit protected layout, metadata, lock or build driver manually, including to make a check pass.
- For coursework, preserve the explicitly designated coursework template. A request for no title page takes precedence; never reinsert one or migrate an existing report silently. Do not add a service/assignment page without a source requirement.
- Each first-level section starts on a new page. Special structural headings follow the reference; ordinary chapter titles are not all-caps.
- Appendix heading follows the example: centered `ПРИЛОЖЕНИЕ А.` on the first line, a normal-case Russian title on the second. Keep its contents entry synchronized; no `PRODUCTION-ФАЙЛОВ` wording or duplicated visible heading. Typography may follow the reference's heading emphasis.
- Every table and figure has a caption, label, and explicit reference in prose.
- Appendices contain complete current required source files, preferably via `raw(read(...))`; no omitted methods or fabricated code. Exclude generated files/tests unless required.
- Use PlantUML technical diagrams and the designated GUAP Typst/Polylux presentation template.
- Final presentation slide contains only `Спасибо за внимание` as text by default; preserve template graphics. No extra “ИТОГ”, implementation bullets, QR or contacts unless requested. Other result slides are not implicitly removed.

Done: source and rendered appearance both satisfy the contract.

### 4. Verify proportional to the change

- Text/heading/single-slide revision: edit only requested scope, compile the affected artifact, extract its changed text, render and visually inspect the changed page/slide and dependent contents/pagination. Compare unaffected page text; if reflow occurs, expand visual review through every affected page.
- UI/state change: demonstrate RED then GREEN for behavior, not only color/constants. Verify that selecting an item then deleting/exhausting it invalidates the selection and disables the action. Derive current objects from current state rather than storing stale snapshots. Capture real UI states without retouching away defects.
- Full final candidate: follow the full build and page-by-page QA in `guap-coursework-artifacts`; derive test totals, pages, dimensions, bytes and hashes from actual outputs.
- Regenerate affected QA renders/contact sheets and update current evidence. Historical RED/GREEN logs remain explicitly historical, not silently rewritten into new results.

Done: report what was actually checked. A bounded revision is not an approval of the whole project.

### 5. Review and delivery without endless loops

Freeze candidate inputs before independent review. Give reviewers exact source/template paths, exceptions, scope and candidate fingerprint. Do not edit their target while they review; archive old verdicts rather than letting them appear current.

A template that is byte-identical to the designated external source must not be “fixed” to match HEAD. Report inherited whitespace separately; the exception applies only to the proven immutable template, never to authored files.

Interrupted, missing and stale reviews are not passed. A green build is not independent approval. After any artifact change, full publication approval is stale; get fresh required code/security and academic review before commit/push, not after every cosmetic local edit. Cosmetic changes do not require a manufactured RED test.

After a blocker-fix cycle, inspect whether the next finding is a real requirement violation or merely a suggestion. Do not silently expand scope to chase suggestions. If reviews keep reopening scope, give a short status with the remaining blocker and bounded options rather than silently launching another batch. If the user says stop, stop; do not resume on late asynchronous results or call an interrupted review successful.

Deliver the rebuilt requested PDF/source, with a concise statement of the change and verification. Do not attach stale filenames or claim submission/publication that did not occur.

## Pitfalls

- Copying old technical content while copying its style.
- Treating all chapter/appendix title text as an uppercase structural label.
- Re-running code/security review for every sentence while leaving the actual PDF uninspected.
- Saying “all pages checked” after looking only at contact sheets or changed pages.
- Changing existing GUAP authentication, permits, monitor scopes or server services during a document task.

## Verification

For each run, check the selected scope against `context/artifact-contract.md`, retain real compile/test output, inspect the actual delivered artifact, and state any incomplete review separately. For full publication, additionally require fresh validated reviews and read back remote commit/CI; for local revision, explicitly keep publication blocked until that gate passes.
