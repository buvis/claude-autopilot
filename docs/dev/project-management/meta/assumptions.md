# Assumption ledger

Per-plan. Replaced at the first completed task of a full-plan pass.

Plan: PRD 00282 (loop guards v1), batch 202610111300.

## 1: records: budget park site + reset field

Tess (test author):

- The budget park's deferred `detail` contains the marker reason (used `assertIn`, not equality - the contract didn't pin an exact detail string).
- A budget park starting from `parks_consecutive=1` ends at 0 (from `_commit_stall`'s existing "any non-wrapper_died site zeroes the counter" rule, plus "never increments").
- A budget park leaves no `pause_reason` and never sets phase/next_phase to "paused".
- `do_stall` is called with `prd` as a keyword argument (spy reads `call_args.kwargs`).
- `reset_prd_fields` drops `prd_budget_since` because it is in `PER_PRD_RESET_FIELDS` (same mechanism as every other reset field).
- (Strengthening round, after Devon's adversarial pass) the resume-dup test also pins the reused op_id and `cycle == 1`, mirroring the existing `ResumeInFlightParkTests`, beyond what the brief asked.
- Exit 4 is a valid `do_stall` failure code to stub in the propagation test (named in `do_stall`'s own docstring as the move-failed code).

Ivan (implementor):

- The budget branch keeps the existing `; lane=<lane_effective>` suffix on the detail (tests only check `assertIn`, so either choice passes).
- A state-load failure (exit 2) in `_finish_park` is checked before the site branch, so it applies to budget parks too.
- Any marker site other than "budget" takes the wrapper_died path (later tightened in review to normalize an unknown/non-budget site to "wrapper_died" rather than passing it through raw, to avoid colliding with an unrelated pending stall_op's site).

## 2: watchdog: session_busy(log_path)

Tess (test author):

- `session_busy` takes a `str` path (matches how `Watchdog` already passes `activity_path=str(...)`); no test pins whether a `Path` also works.
- "Unreadable" covers both a missing file and a mode-000 file; both return False.
- The internal-fault test assumes `session_busy` parses lines via the module-level `json.loads` (it patches `json.loads`) and that only `ValueError` (decode errors) count as malformed-and-skipped, with any other exception type reaching the busy fallback.
- A `background_tasks_changed` event's non-empty `tasks` list counts as live regardless of each task's `status`.

Ivan (implementor):

- Lines whose parsed JSON is not an object (`[1,2,3]`, `"str"`, `42`, `null`) are skipped, not treated as faults.
- A `message.content` that is a plain string (no tool blocks) is skipped rather than counted as a fault - otherwise a session could latch "busy" forever on an ordinary text message, defeating the idle kill.
- The file is read with `errors="replace"` so stray non-UTF-8 bytes become a malformed line (skipped) rather than raising `UnicodeDecodeError` (which is a `ValueError`, so it would otherwise fall outside the "unreadable file" case).
- An `OSError` while reading the file returns False (idle), not True.
- (Review round) event fields are read tolerantly (`.get()`, `isinstance` checks) rather than by strict indexing, so one odd-shaped event in a growing log degrades to "skip this event" instead of latching the whole session busy for its remaining lifetime.

## 3: enter: set prd_budget_since on entry

Tess (test author):

- `prd_budget_since` stores exactly the string `now()` returns (exact string equality, no reformatting).
- A state `prd` naming a file not in wip/ does not halt `enter()` before step 10 (confirmed by running the harness: it reaches the value assertion, not a stop).
- The "absent" condition applies on its own, including on same-PRD re-entry (plain logical OR), and a non-full-lane entry still carries `prd_budget_since` since `_write_prd` (step 10) runs before the lane stop.

Ivan (implementor):

- An absent previous `prd` counts as "differs", so the stamp is refreshed on a from-nothing entry.
- `now()` is called only when a stamp is actually needed, inside the same `statectl.mutate` callback that writes `state.prd` - one atomic read-decide-write.

## 4: loop: budget_usd_for + _budget_bound wired into _run_loop

Tess (test author):

- `budget_usd_for` lives in `cli.loop_decision`; the contract names no module.
- "Resumed from hold" means the operator moves hold/X to backlog/X, then Phase 0 runs `enter(prd_arg=X)` - no existing loop fixture modeled a resume, so this was built from `enter()`'s own selection and stamp code.
- `ts_start` (int epoch) and `prd_budget_since` (ISO UTC) are compared as points in time; the fake clock's epoch and `_iso()`-made stamps reconcile through that comparison.
- A row missing `ts_start` or `cost_usd` (null, absent, or wrong type) counts as 0, never raises - the PRD doesn't say so explicitly, but a crash on a malformed metrics row would be worse than undercounting.
- (Strengthening round) `_budget_bound` is tested directly against a hand-seeded `loop-metrics.jsonl`/`state.json` rather than only through full multi-session runs, to pin the window-boundary (`>=`) and malformed-row behavior precisely.

Ivan (implementor):

- `prd_budget_since` is an ISO UTC stamp parsed via `fromisoformat` (`Z` swapped for `+00:00`); a stamp with no timezone is read as UTC.
- `ts_start` in metrics rows is numeric epoch seconds, matching `_metrics_line`'s own write; a non-numeric `ts_start`/`cost_usd` (including bool) counts as missing.
- This session's own cost is read from `last-session.log` (not from `loop-metrics.jsonl`) because `_budget_bound` runs before `_append_metrics` writes this session's row.
- A negative budget value is used as given at first; a later review round changed this to a nan/inf/negative-rejects-to-default guard.
- (Review round) the bound now no-ops when `decision.get("limit_wait")` is set, so a budget crossing never drops a scheduled usage-limit sleep (the HIGH finding: parking there risks relaunching straight into a still-live limit and halting the loop on an unconsumed park marker).
