---
name: guap-coursework-artifacts
description: "Use when producing GUAP coursework deliverables end-to-end."
version: 1.0.1
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [guap, coursework, typst, plantuml, reports, presentations]
    related_skills: [labflow-guap]
    external_skills: [labflow-report, labflow-self-review, powerpoint]
---

# GUAP Coursework Artifacts

Produce a coherent GUAP coursework package: localized application, Russian README, explanatory report, strict diagrams, defense presentation, evidence, and verified publication. This skill specializes institutional format and artifact consistency; use Labflow skills for implementation and independent review.

## Trigger

Use for GUAP course projects or similar academic projects where report, diagrams, presentation, source listings, and repository publication must agree with the final implementation.

## Source of truth

For GUAP-specific source selection, introduction/appendix wording, final-slide style,
and bounded revisions, load `labflow-guap`. This skill retains detailed artifact
build/visual procedures; do not maintain competing editorial rules in both skills.
A requested local revision need not rerun the end-to-end publication workflow.
Never label that limited verification a fresh whole-project approval.

1. Read the current methodology and the user's explicit corrections before formatting.
2. Reuse a user-designated prior coursework template rather than inventing a new style.
3. Re-read current production source after every code-fix batch before generating diagrams or listings.
4. Treat page counts, test totals, class names, methods, states, and screenshots as generated facts. Update every occurrence after rebuilds.

See `references/template-sources.md` for known template sources and `references/guap-format-checklist.md` for the user-specific finishing checklist.

## End-to-end workflow

### 1. Establish the artifact contract

Create a requirement-to-evidence matrix covering:

- application behavior and persistence;
- OOP hierarchy and required patterns;
- tests and control scenario;
- report sections and appendices;
- diagrams;
- defense presentation;
- publication and CI.

Keep the original methodology local when redistribution is not allowed. Extract requirements into project-owned notes rather than committing the source PDF.

### 2. Localize the deliverable

For this user's GUAP projects:

- all user-visible application text is Russian: window title, navigation, forms, buttons, validation, status, empty states, errors, and administration messages;
- README is fully Russian while commands, paths, identifiers, and dependency names remain literal;
- internal Kotlin/Java/class/API identifiers stay in their source language.

Run GUI smoke tests after localization; text expansion can break layouts even when compilation succeeds.

### 3. Build the explanatory report from the prior template

Use the prior coursework's Typst/GOST structure as the baseline, but replace all stale subject matter and metadata.

Required style for this user:

- omit the title page entirely; the user supplies it separately;
- start every level-1 section on a new page without creating accidental blank pages;
- center and capitalize only methodology-defined structural headings such as `ВВЕДЕНИЕ`, `ЗАКЛЮЧЕНИЕ`, and `СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ`;
- keep ordinary numbered chapter and subsection headings in normal case;
- use plain narrative prose: no bold, italics, or inline-code emphasis;
- actual standalone source listings may remain monospaced;
- every included source listing must be the exact complete current file, never an excerpt, ellipsis, omitted method, or pseudocode;
- exclude generated KSP/Room code and tests unless the methodology explicitly requires them.

Generate listings from current files or verify them byte-for-byte against current files immediately before final compilation.

### 4. Generate strict diagrams with PlantUML

Use PlantUML for every technical diagram: domain hierarchy, Room/ER schema, architecture, and each pattern diagram.

- commit `.puml` sources and generated SVGs;
- use actual production class, interface, method, field, state, table, foreign-key, and cardinality names;
- point UML generalization arrows toward parents;
- distinguish conceptual domain classes from Room record classes explicitly;
- regenerate presentation image assets from the same PlantUML sources;
- validate all `.puml` files and generated SVGs in one batch;
- inspect the rendered diagrams at both A4 report scale and 16:9 slide scale.

Do not hand-edit generated SVGs. Fix the `.puml` source and render again.

### 5. Build the presentation in Typst/Polylux

Use the GUAP Typst/Polylux template and a completed coursework presentation as the structural example. The authoritative presentation pipeline is:

```text
presentation/main.typ
presentation/lib/guap-template.typ
presentation/lib/images/*
presentation/course-<topic>.pdf
```

For this user:

- presentation content is Russian;
- use the official GUAP color, logo, title, header, footer, and final-slide assets;
- deliver Typst source plus PDF, not a parallel custom PPTX pipeline;
- keep 10–15 slides unless the methodology says otherwise;
- keep all visible text at least 28 pt by shortening copy rather than shrinking text;
- reuse the report's PlantUML diagrams and current GUI screenshots;
- remove obsolete PPTX generators/specs/readbacks when migrating to Typst so one pipeline remains authoritative.

Render every slide to PNG and visually inspect all slides, not only a contact sheet.

### 6. Perform page-by-page visual QA

After the final report build:

1. render every PDF page to PNG;
2. create a contact sheet;
3. inspect every page, with individual zooms for dense and sparse pages;
4. remove accidental blank or near-empty pages;
5. reduce or reposition images when they create large empty areas;
6. balance figure size, captions, paragraphs, and page breaks;
7. verify code listings are readable and untruncated;
8. recompute and update the actual page count everywhere.

A successful compiler exit is not visual verification.

### 7. Verify behavior and consistency

Before publication, run and read back:

- clean test/build on the complete project;
- exact JUnit totals from XML;
- report compilation and PDF metadata;
- Typst presentation compilation and slide count;
- PlantUML compilation for all diagrams;
- source-listing equivalence;
- scans for stale legacy terms, old test totals, old page counts, old screenshots, Web/WASM targets, and secrets;
- `git diff --check`;
- fresh independent code review and Labflow self-review.

If a review produces logic errors, fix them with failing regression tests first and launch a fresh review after changes. Do not reuse a stale verdict.

### 8. Publish safely

Default sequence:

1. full green verification;
2. independent reviews pass;
3. commit;
4. create a new repository without altering the source repository;
5. push;
6. read back the remote commit and root files;
7. wait for CI on the required Java version and inspect every step.

If the user explicitly asks to publish a known working baseline before fixes, honor that override: publish a consistent green commit, disclose that review findings remain, verify CI, then land fixes in a separate reviewed commit.

## Pitfalls

- A global uppercase/centered heading rule over-formats ordinary chapters.
- Removing the title page without updating page counts leaves contradictory documentation.
- Copying snippets into appendices creates stale listings after fixes.
- Manually drawn SVGs drift from implementation and are hard to audit.
- Font-size checks do not catch text leaving card boundaries; rendered-slide inspection is mandatory.
- A contact sheet alone can hide overflow and sparse pages.
- Translating only labels but not errors, loading states, or window titles leaves the application partially English.
- Maintaining both PPTX and Typst presentations creates conflicting deliverables.
- Publishing after a failed review is allowed only by explicit user override and must not be labelled verified.

## Completion criteria

The task is complete only when application, README, report, diagrams, presentation, test evidence, and remote repository all describe the same final state, every required build passes, every report page and presentation slide is visually inspected, and the remote CI result is read back.
