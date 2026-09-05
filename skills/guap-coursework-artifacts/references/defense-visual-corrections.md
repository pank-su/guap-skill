# Defense visual correction patterns

Use this when a GUAP report/deck is technically complete but the user rejects the visual presentation.

## Preserve the designated baseline

- Reuse the user-designated previous coursework's Typst/GOST implementation; do not substitute a simplified lookalike.
- Preserve geometry, heading/show rules, outline behavior, caption rules, and numbering unless a minimal compatibility fix is necessary.
- Validate the rendered TOC: one `СОДЕРЖАНИЕ`, uppercase structural entries, normal-case chapters, no technical filenames, and no artificial level-1 wrapping.

## Complete GUI coverage without unreadable grids

- Enumerate every top-level screen/tab before layout work.
- Include every current localized screenshot in the report and, when UI is part of the defense story, in the presentation.
- Prefer two large screenshots per A4 page or per defense slide.
- If the deck must remain within 10–15 slides, consolidate prose/pattern slides to free a second interface slide instead of using a tiny four-up grid.

## Simplify slide diagrams without losing facts

Create presentation-specific PlantUML views from the report's production facts:

1. domain hierarchy;
2. domain relations/cardinalities;
3. Room tables/key fields;
4. Room relations/constraints.

Remove edge labels when they collide with nodes, connectors, or multiplicities. Put relation semantics and transaction guarantees into large native Typst cards. Keep visible authored and diagram text at least 28 pt. Extract PDF slide titles and count pages because an overflowing Typst slide can silently become an extra PDF page.

## Review convergence

- Render and inspect every affected slide/page at native size.
- A contact sheet can miss table-cell collisions and one-line orphan pages; zoom dense tables, sparse pages, screenshot pages, and final pages individually.
- If a long identifier crosses a table boundary, insert a controlled semantic line break rather than shrinking the whole table.
- If prose leaves one or two lines before a forced level-1 page break, shorten/reflow the prose and rebuild all evidence.
- After reflow, update page/slide totals, PDF size, page ranges, final-page references, QA filenames, and any tracked or gitignored review summaries.
- Freeze the candidate before fresh academic/visual review; no verdict survives an artifact edit.

Cross-reference requirements for every table and figure are documented in `references/figure-table-cross-references.md`.
