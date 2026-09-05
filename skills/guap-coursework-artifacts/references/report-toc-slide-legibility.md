# Report TOC, GUI coverage, and slide legibility

Use this checklist when a GUAP coursework package combines a Typst report, PlantUML diagrams, and a Typst/Polylux defense deck.

## Preserve the designated prior report template

- Copy the user-designated prior coursework template implementation first; do not replace it with a simplified lookalike.
- Preserve its page geometry, heading/show rules, numbering, outline rendering, table/figure behavior, and structural-heading macros.
- Adapt project content and metadata only. If a compatibility change is necessary, keep it minimal and verify the rendered result against the prior report.

## Table of contents acceptance test

Visually inspect the rendered TOC and verify all of the following:

1. `СОДЕРЖАНИЕ` appears exactly once as the page heading.
2. Structural entries such as `ВВЕДЕНИЕ`, `ЗАКЛЮЧЕНИЕ`, `СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ`, and `ПРИЛОЖЕНИЕ …` are present and uppercase.
3. Ordinary numbered chapters retain normal case.
4. Level-1 entries do not receive artificial line breaks from custom outline markup; only natural wrapping is allowed.
5. Source filenames and one-entry-per-file appendix headings do not pollute the TOC. Complete listings may remain in the appendix while their file labels are excluded from the outline.
6. Each level-1 report section begins on a new page without an accidental blank page.

Check extracted PDF text for duplicates and forbidden filenames, then inspect the TOC page image. Text extraction alone cannot detect bad line wrapping.

## GUI screenshot manifest

Create an explicit manifest of every application screen or top-level tab. For each entry verify:

- current localized screenshot exists;
- screenshot shows the final application state rather than an obsolete build;
- it appears in the report with a descriptive caption;
- it appears in the presentation when the interface is part of the defense story;
- the rendered screenshot is large enough to recognize labels and primary controls.

Prefer two reasonably large screenshots per A4 page or defense slide over a tiny four-up grid. If four screens are required in a 10–15-slide deck, use two interface slides and consolidate prose-heavy slides rather than shrinking screenshots.

## Presentation-specific PlantUML

Do not shrink a dense report diagram onto a slide. Produce dedicated slide views from the same production facts:

- split hierarchy/table inventory from relations/cardinalities;
- keep entity and table labels large;
- remove edge text when it collides with lines, nodes, or multiplicities;
- put explanatory semantics or transaction guarantees in a large native Typst summary card;
- ensure each logical slide renders to exactly one PDF page;
- inspect both the diagram and the surrounding slide at final 16:9 size.

A useful decomposition is four technical slides: domain hierarchy, domain relations, Room tables/fields, and Room relations/constraints. This is preferable to one unreadable all-in-one UML image.

## Verification loop

After every report or presentation layout change:

1. rebuild both PDFs;
2. read PDF page/slide counts;
3. extract slide titles to detect silent overflow pages;
4. render affected pages/slides to PNG;
5. inspect the TOC, every screenshot page, every technical diagram, and the final page/slide;
6. update page-count evidence only after the layout is accepted;
7. obtain fresh academic/visual review before publication because any artifact change invalidates the prior verdict.
