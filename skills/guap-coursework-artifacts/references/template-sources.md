# GUAP template sources

Use these as design and structure references; inspect the live repositories before copying because templates can evolve.

## Presentation

- GUAP Typst/Polylux template: https://github.com/pank-suai/pres_template
  - `main.typ` demonstrates template calls.
  - `lib/guap-template.typ` defines GUAP colors, typography, title/header/footer, slide helpers, and final slide.
  - `lib/images/` contains the official logo and title/final backgrounds.
- Completed coursework example: https://github.com/pank-suai/course_pres
  - `main.typ` demonstrates a real defense sequence, diagram slides, screenshots, conclusions, and final slide.
  - Use its organization as a reference, not its subject-matter content.

Authoritative output is Typst source plus PDF. Do not retain a conflicting custom PPTX pipeline unless the user explicitly asks for both.

## Report

- Reuse the report template from the user-designated prior coursework repository (for this family of projects, inspect the `docs/index.typ` and `docs/lib/gost.typ` files in the relevant prior course repo).
- Preserve template structure, numbering, margins, captions, lists, bibliography, and appendix conventions while replacing all stale content.
- Never copy the prior title page when the user says they will create it separately.

## Diagram source

- PlantUML: https://plantuml.com/
- Commit `.puml` and generated SVG; regenerate from source rather than editing SVG.
