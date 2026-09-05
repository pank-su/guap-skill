# Pagination and review convergence

Use this after any report prose, listing, font, figure, or forced-page-break change.

1. Recompile the exact candidate and derive page count and byte size from the PDF.
2. Render every page, then inspect the page immediately before each forced level-1 page break at native resolution. A one- or two-line continuation followed by a forced break is an accidental near-empty page even if the contact sheet looks acceptable.
3. If prose is shortened or reflowed, rerender all pages and recreate every range-named contact sheet; do not keep evidence named for the previous final page.
4. Update page count, content/listing ranges, final-page references, PDF size, and QA filenames in README, requirement matrices, build evidence, and review prompts.
5. Scan both tracked files and gitignored review evidence for stale generated facts. Temporary self-review summaries and pdfinfo captures can invalidate an otherwise consistent candidate.
6. Inspect the new final listing page at native resolution and verify exact closing braces and complete final files.
7. Delete stale review verdicts and rerun independent code/security and academic reviews against the frozen candidate; no verdict survives a candidate edit.

For multiple asynchronous UI error sources, keep independent state channels. A success may clear only its own error class; add regression coverage for both cross-operation directions as well as failure-then-success recovery within each class.