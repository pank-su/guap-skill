# Review convergence for coursework candidates

Use this checklist when code, report, presentation, evidence, and publication must describe one exact final state.

## Freeze the candidate

1. Finish all production and documentation edits.
2. Run a clean build and derive totals from fresh JUnit XML, not prose.
3. Rebuild every PDF and record page/slide counts, dimensions, and byte sizes.
4. Verify complete production-listing path equality, PlantUML sources/SVGs, legacy/secret scans, and `git diff --check`.
5. Render every page and slide; inspect dense, sparse, first, final, and recently shifted pages at native size.
6. Archive stale review outputs with their candidate identity before dispatching fresh reviewers; do not erase historical evidence.
7. Include exact candidate facts, authoritative external template path/hash and scoped exceptions in each review prompt; ask reviewers to verify independently. Do not substitute Git HEAD for the designated template.
8. Make no candidate edits while reviews run. Fingerprint candidate inputs (including untracked source and deliverables), excluding review-owned output files.

For bounded local text/heading/slide edits, apply `labflow-guap` proportional verification instead of restarting this full final-candidate procedure. A changed artifact still makes whole-project publication approval stale. Interrupted reviewers are incomplete, not passing.

## Reject stale verdicts

A review is stale if it cites old test totals, page counts, PDF sizes, missing behavior that was added later, or a tree that changed after dispatch. Do not average stale and fresh verdicts. Archive and label stale `SELF_REVIEW.md` files so later agents cannot treat them as current evidence.

## Blocker loop

For each functional blocker (editorial issues instead need targeted source correction,
compilation and visual verification, not a fabricated regression test):

1. write and run a focused RED regression test;
2. make the minimal GREEN production change;
3. run the focused test, affected suite, and full clean build;
4. recompute all generated facts and synchronize README, matrix, report, presentation, and evidence;
5. rebuild and visually inspect PDFs, especially listing pages shifted by added production lines;
6. rerun secret, legacy, listing, diagram, and whitespace checks;
7. dispatch two fresh independent reviews against the new frozen candidate.

## Kotlin coroutine cancellation gate

Plain Kotlin `runCatching` captures `CancellationException`. Around suspending ViewModel operations this can turn lifecycle cancellation into a user-visible failure or mutate UI state after `close()` cancels the scope.

Use a centralized cancellation-safe wrapper:

```kotlin
private inline fun <T> runCatchingCancellable(block: () -> T): Result<T> = try {
    Result.success(block())
} catch (error: CancellationException) {
    throw error
} catch (error: Throwable) {
    Result.failure(error)
}
```

Audit every suspending UI operation, including save/delete, issue/return, periodic refresh, seed, and clear. Add deterministic regression coverage for representative operation families and assert that cancellation is not published as a user error. Keep ordinary failures visible and verify that a later successful retry clears stale errors.

## Publication gate

Commit and push only when the exact frozen candidate has:

- green clean build and exact test totals;
- current report/presentation metadata and visual QA;
- exact listing/diagram/evidence consistency;
- empty blocker/security/logic lists from the fresh code review;
- a fresh validated academic self-review;
- successful remote CI on the required JDK after push.
