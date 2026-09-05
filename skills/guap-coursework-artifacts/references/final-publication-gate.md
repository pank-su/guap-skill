# Final gate for coursework publication

Use this after implementation is functionally complete but before commit/push.

## Fail-closed review loop

1. Run the complete clean build and derive test totals from JUnit XML, not console prose.
2. Synchronize every generated fact: README, requirement matrix, report narrative/table, presentation table, and evidence files.
3. Rebuild report and presentation; recompute page/slide counts and exact byte sizes.
4. Because report listings read production files directly, render all pages after every production change. Remove accidental blank or braces-only trailing pages by adjusting listing layout conservatively, then recheck readability.
5. Run listing-path equality, PlantUML/SVG validation, secret/legacy scans, and `git diff --check`.
6. Launch fresh independent code/security and academic reviews. Any production, test, report, or presentation change invalidates all prior verdicts.
7. Commit/push only when the exact candidate has a fail-closed code verdict (`passed=true`, empty security and logic lists) and a validated academic `Final Status: passed`.

## Coroutine ViewModel review probes

Reviewers should test state transitions, not only happy-path outputs:

- Never turn `CancellationException` into a user-visible error. A cancellation-safe result helper must rethrow it while preserving ordinary failures.
- Cover each suspend-operation family: create/save/delete, issue/return, periodic refresh, seed/clear.
- Distinguish parent-scope cancellation from an operation cancelled while the parent remains live. Do not mutate state after `close()`, but clear transient `isBusy` when a standalone operation cancellation leaves the ViewModel active.
- Test `failure → success`, not just failure: successful retry must clear the relevant stale error.
- If several operation types share one error flow, verify success from one type does not incorrectly erase an unrelated error from another; separate error sources when needed.
- Periodic jobs need deterministic time/interval injection, lifecycle cancellation, surfaced ordinary failures, recovery after a later success, and no busy loop.

## Evidence discipline

- Keep RED and GREEN commands/results in the TDD evidence file.
- Treat historical intermediate totals as explicitly historical (`at this stage`), never as final.
- Remove stale `SELF_REVIEW.md` before dispatching a fresh academic reviewer.
- Refresh temporary review PDFs, text extraction, page/slide renders, contact sheets, and scan summaries so reviewers do not consume stale evidence.
- Re-read the remote commit and CI run after push; local success is not publication success.
