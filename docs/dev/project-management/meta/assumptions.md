# Assumptions ledger — PRD 00308-reviewer-lane-resilience-v1

## 1: Replay kills its process group

- Using `files=["test_calc.py"]` with the sibling fixture (`_repo`, `HEAD_IMPL`, `HEAD_TESTS` from `test_replay_tests_against_base.py`) is a valid real worktree setup.
- A 3s grace poll is enough for the killed processes to be cleaned up before checking their pids.
- `/bin/sh` as the runner shell is fine for macOS and Linux.
- `git checkout --` counts as overwriting a file with its original content for Devon's cleanup obligation (no `rm` used).
- The current test failure before the implementation is the expected red state, since the test-only commit precedes it.
- 2.0s of slack above the timeout is enough on a loaded machine (later flagged by review as possibly too tight; left as a non-blocking LOW).
- The exact wording of the timeout skip reason is free, as long as it starts with "runner did not complete:" — the test only checks that a reason is returned.

## 2: Auth failure is permanent; bounded native fallback

- Auth-phrase matching is case-insensitive, like the existing `grep -Ei` in `permanently_unavailable` — the task names only the phrases `Authentication failed` and `Copilot Requests permission`, not the case rule.
- No bare "401" variant was added to the auth-failure test matrix — the task's match list covers the two named phrases only.
- The 3s upper margin on the fallback deadline tests (2→<5s, 3→<6s) follows the existing test's margin.
- `GEMINI_FALLBACK_TIMEOUT` bounds the whole fallback run (a hard deadline), not specifically "time without output" despite the test name — the tests cannot distinguish the two, and a hard limit is simpler.
- The auth latch applies on every backend (not just copilot): on the native gemini backend an auth failure still exits 4, with nothing further to fall back to.
- If stderr matches both an auth pattern and a tier-rejection pattern, the auth classification wins and there is no fallback.

## 3: Retry rows inherit their task

- The new `queued_at` comes from `time.time()`, truncated to an int like `start_row`.
- The new row has exactly the keys id, kind, task, queued_at, prompt_bytes and detail, nothing more.
- A row with a matching id but no `queued_at` (an end-only row) is not a start row, so retrying that id exits 1.
- Ids must match exactly (no prefix matching).
- A dispatch that already ended (timeout, error) can still be retried — its end row does not block a retry of its start row.
- The retry row belongs in the `ledger/` mirror too, like every other row.
- With no autopilot dir, `retry` prints a token and writes nothing, matching `start_row`'s existing no-op precedent (not the silent-exit-0 behavior `end`/`handoff` have).

## 4: Bob inlined on the first run; review skill uses the new shapes

- Auth matching is case-insensitive, like the existing `grep -Ei` in `permanently_unavailable` — carried over from task 2.
- The new retry-policy.md section heading is "## Inlined prompt (Bob's first dispatch)" (not specified verbatim by the task).
- `bob-prompt-{id}-retry.md` keeps its "-retry" filename even though the prompt is now built on the first dispatch — renaming it would require updating `test_inlined_retry_prompt_uses_dedicated_retry_filename` too, which is out of this task's scope.
- The outcome table's two retry rows (success-via-retry, retry-itself-failed) stay, with only the `lack-of-input` detail variant removed — a retry still exists (format/verdict gate retries, and the dispatch-ledger `retry` verb), so dropping those rows entirely would leave a retried dispatch unrecorded.
