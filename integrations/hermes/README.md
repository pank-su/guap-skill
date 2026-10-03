# Existing daily-sync integration

The optional patch targets an already deployed `scripts/guap_labflow_sync.py` and
its test suite. It changes no permit, retrieval scope, ignored subjects, Kanban
policy, schedule or upload behavior. It reopens the owned mode-0600 compatibility
cookie file for every material download after CLI queries may have restored the
application session. No-follow opens, descriptor ownership/type/mode checks and
bounded single-line reads prevent unsafe fallback snapshots.

Review/apply the patch only to matching versions of the existing integration. It
uses zero-context hunks: run `git apply --check --unidiff-zero` against the patch
before applying with `git apply --unidiff-zero`, then run the integration's full
tests. The supplied regression demonstrates an actual expired-cookie
snapshot before the change and fresh cookies afterward. These integration files
are not required for ordinary cabinet CLI or SSO renewal.
