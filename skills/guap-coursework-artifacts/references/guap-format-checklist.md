# GUAP final-format checklist

## Application and README

- [ ] Window title, tabs, fields, buttons, validation, loading/empty states, errors, and success messages are Russian.
- [ ] README is Russian; commands, paths, identifiers, and dependency names remain exact.
- [ ] GUI smoke test was repeated after localization.

## Report

- [ ] No title page.
- [ ] Every level-1 section begins on a new page without an empty page.
- [ ] Only methodology-defined structural headings are centered and uppercase.
- [ ] Ordinary chapter and subsection headings use normal case.
- [ ] Narrative contains no bold, italics, or inline-code emphasis.
- [ ] Standalone code listings are complete current files with no omission or pseudocode.
- [ ] Generated code and tests are omitted unless required.
- [ ] Every page was rendered and inspected.
- [ ] Sparse pages were rebalanced by resizing figures or adjusting breaks.
- [ ] Actual page count is updated in all files.

## PlantUML

- [ ] Every technical diagram has a `.puml` source.
- [ ] All SVGs were freshly generated from `.puml`.
- [ ] Names, APIs, states, foreign keys, and cardinalities match current production code/schema.
- [ ] No generated SVG was manually edited.
- [ ] Diagrams are legible on A4 and 16:9 slides.

## Typst presentation

- [ ] Uses the GUAP Typst/Polylux template and official assets.
- [ ] Contains 10–15 Russian slides unless requirements differ.
- [ ] All visible text is at least 28 pt.
- [ ] Content matches the final code, tests, diagrams, and screenshots.
- [ ] Every slide was rendered to PNG and inspected for overflow/overlap.
- [ ] Obsolete PPTX generator/spec/readback artifacts were removed.

## Verification and publication

- [ ] Clean build and exact test totals pass.
- [ ] Report and presentation compile.
- [ ] PlantUML batch compiles.
- [ ] Source listings match files.
- [ ] Stale terms/counts/screenshots and secrets scan clean.
- [ ] Fresh independent code review and self-review use the post-fix tree.
- [ ] Remote commit and root files were read back.
- [ ] Required CI runtime and every workflow step succeeded.
