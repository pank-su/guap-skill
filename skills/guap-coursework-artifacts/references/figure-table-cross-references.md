# Typst table and figure cross-reference gate

Use this after report content stabilizes and before visual review.

## Authoring contract

For every table or figure:

1. introduce it in narrative prose before the object (`в таблице @label`, `на рисунке @label`);
2. provide a descriptive `caption`;
3. assign a unique Typst label after the object;
4. let Typst resolve numbering—never hard-code a table or figure number.

Preferred table form:

```typst
Результаты приведены в таблице @results-table.

#figure(
  kind: table,
  caption: [Результаты проверки],
  table(...),
) <results-table>
```

Preferred figure form:

```typst
Архитектура показана на рисунке @architecture-figure.

#figure(
  image("images/architecture.svg"),
  caption: [Архитектура приложения],
) <architecture-figure>
```

A caption is not a substitute for a prose reference.

## Deterministic validation

Parse each `#figure(...)` block with balanced-parenthesis scanning rather than a naive non-greedy regex because figures contain nested `table(...)`, `grid(...)`, and function calls. For every object assert:

- a following `<label>` exists;
- `caption:` exists inside the block;
- table wrappers declare `kind: table`;
- the source contains at least one `@label` occurrence outside the definition.

Report explicit totals, for example:

```text
verified_objects=18 tables=4 figures=14 all_captioned_labeled_referenced=true
```

The declared totals are assertions: reconcile them with the source before finalizing.

## Visual checks after compilation

- Confirm references resolve to numbers in extracted PDF text.
- Inspect every table/figure page at native resolution, not only a contact sheet.
- Look for long identifiers crossing a table-cell boundary; insert a controlled semantic line break at a readable boundary if natural wrapping overlaps.
- Inspect the page before each forced level-1 break; shorten prose when a one- or two-line continuation creates a near-empty page.
- Rebuild all page renders and update page-count evidence after any reflow.
