---
prd: dev/local/prds/wip/00217-bound-concurrent-review-sessions-with-a-slot-semaphore-v1.md
review: 2
date: 2026-09-29
head_sha: 83165038f9dfd92ebf64ae94f38f61b946a17ee3
codex_thread_id: 01a0eba5-1e97-7d43-90d7-3de4fe1eab3e
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00217-bound-concurrent-review-sessions-with-a-slot-semaphore-v1

Diff range: `1ca6f5cb6b73cd97be6fef571ea0d24038453485..83165038f9dfd92ebf64ae94f38f61b946a17ee3`
(incremental review, cycle 2 — the rework since cycle 1. Bob resumed his cycle-1
codex thread via `--resume-thread`; the PRD's full work range from
`state.work_start_sha` was reviewed in cycle 1.)

codex_rung_guard: not fired

pack: failed (`engram pack` exited 1: "not inside a registered repo; register it in
/Users/bob/.config/gita/repos.csv" — the same structural gap as cycle 1, so no retry was
spent). Every prompt that takes `{PACK_FILE}` / `{PACK_FINDINGS}` received the sentinel
`(no pack available this cycle)` instead. Blake never receives a pack by design.

**Carl ran independently this cycle.** Cycle 1's first Carl run was discarded for reading
Bob's output file mid-run. His cycle-2 prompt carried an explicit independence rule
forbidding him to open any other reviewer's output or prompt file, `dev/local/reviews/`,
or `dev/local/autopilot/`. His transcript confirms he honoured it: he read only the two
files named in his prompt plus repository sources, ran the two suites, the full `cli`
suite and `dev/bin/release-checks` himself, and ran two of his own `os.rename` /
`shutil.rmtree` probe scripts. He returned `✅ No issues found` — his own conclusion, not
a relabelling of anyone else's.

## Review Summary

Reviewed: 5 completed tasks (cycle-2 scope is tasks 4 and 5, the cycle-1 `[D1]` rework)
PRDs checked: 00217-bound-concurrent-review-sessions-with-a-slot-semaphore-v1.md

### Agent Status

- Alice: ✅ Available (Claude subagent, consensus lens, `consensus_engine: legacy`)
- Blake: ✅ Available (Claude subagent, blind lens — PRD-only)
- Bob: ✅ Available (codex, doubt lens + de-slop, resumed cycle-1 thread, first run)
- Carl: ✅ Available (gemini/copilot, first run, independent — see the note above)
- Eve: ⏸️ Disabled (doubt reviewer resolved to `codex`; the codex doubt-roster guard did
  not fire — no task attempt has `implementor: "codex"`)

## Cycle-1 findings: resolution status

All eight actionable cycle-1 findings were verified resolved by at least two reviewers
working independently. Alice and Bob each walked the list; Blake found the code cold and
did not re-raise any of them.

| Cycle-1 finding | Status | Evidence |
|---|---|---|
| 🟠 Non-atomic claim / non-exclusive reclaim | **Resolved, one residual** | `_claim` stages `N.tmp-*` with `owner` inside and publishes with one `os.rename` (wave_slots.py:64-84); `_discard` compares the moved-aside owner against the judged text. The three-party put-back residual is raised fresh below. |
| 🟡 Heartbeat untested | **Resolved** | Advancing `_Ticker` clock; tests cover under 5 min, 301s, 770s, 2100s. |
| 🟡 Nonpositive count polls forever | **Resolved** | `acquire` raises `ValueError` before `dir.mkdir` (wave_slots.py:140); a test pins it. Blake re-raises the *new* consequence below. |
| 🟡 `release` swallows every removal error | **Resolved** | `_remove` ignores only `FileNotFoundError`, prints anything else to stderr (wave_slots.py:27-39). Both cases tested. |
| 🟡 `ts_start` includes the slot wait | **Resolved** | `_launch` returns the post-acquire clock reading (loop.py:389, 405); `_announce_and_launch` passes it up to both callers. Fail-first test fails against the old code. |
| 🟡 Docs test pinned only one variable | **Resolved** | `(?!_DIR)` regex plus a "3" required within 100 characters of the count variable. |
| 🟡 `_stale` guarded only `FileNotFoundError` | **Partly resolved** | `_owner` catches `OSError` and decodes with `errors="replace"`; `_is_stale` uses `isdecimal()` and `int(owner) > 0`. Non-UTF-8, `"0"` and `"²"` all reclaimed, each tested. Oversized digit strings still crash — raised fresh below. |
| 🟡 `test_pid_alive_...` retest | **Resolved** | Test removed. |
| ⚪ Cannot statically verify (routed) | **Answered** | `bash dev/bin/release-checks` exit 0 at this HEAD, twice: the `last-verification.json` record and Carl's own run. |

## Consolidated Findings

`consolidate_findings.py` ran and produced the machine table. Its suffix-stripping merge
folded **four** citations into row 1 (`wave_slots.py:116 ~ :108 ~ :102 ~ :111`). Three of
those are genuinely one defect — Alice's `:116`, Blake's `:102` and Bob's `:111` all
describe the same three-party put-back race — so row 1 is a true [3/4]. The fourth,
Alice's `:108`, is a **different defect at a different function** and was split back out
by hand below, marked as such. Everything else is the script's output unchanged, plus the
two absorbed `[MECH]` lines.

### Majority Consensus (>50%)

- **[3/4] 🟠 The reclaim can still hand one slot to two holders (three-party put-back
  race).** `_discard` moves a stale-looking slot aside before judging it. If it wins that
  rename against a peer that has just re-claimed the slot live, the slot *name* is vacant
  from `os.rename(slot, aside)` (wave_slots.py:110) until the put-back at `:116`. A third
  acquirer's `_claim` can take the name in that window; the put-back then fails, the live
  claim is stranded in `N.stale-<pid>`, and count=1 admits two concurrent sessions. The
  stranded holder's `release` — which has no ownership check — later removes the third
  party's slot. The code documents this residual itself (wave_slots.py:102-106) and names
  the fix: a per-slot `fcntl.flock`. Needs three parties within microseconds and is
  reported on stderr, so likelihood is low; but it breaks the PRD's core invariant
  ("never more than N review sessions") and the cycle-1 acceptance criterion said the
  two-holder case no longer reproduces. Confidence: **confirmed** — three reviewers
  reached it independently and the source comment concedes it.
  - File: `skills/run-autopilot/cli/wave_slots.py:116`
  - Task: 4
  - Found by: Alice, Blake, Bob

### Minority (<=50%)

- **[2/4] ⚪ Leaked `N.tmp-*` and `N.stale-*` dirs are never swept.** A kill between
  `mkdtemp` and `rename`, or an `ENOSPC` on the owner write, leaves a staging dir; a
  failed `_remove` leaves an aside dir. Nothing cleans either until the wave-slots dir is
  removed at wave end. Harmless to correctness (`acquire` reads only `<dir>/<n>`, so
  non-digit names are invisible), but it accumulates debris.
  - File: `skills/run-autopilot/cli/wave_slots.py:77`
  - Task: 4
  - Found by: Alice, Blake

- **[1/4] 🟡 A decimal owner too large for a C int crashes `acquire` instead of being
  reclaimed.** `_is_stale` passes `"99999999999999999999"` (`isdecimal()` true, `> 0`
  true) to `_pid_alive`, whose `os.kill` raises `OverflowError`; `_pid_alive` catches only
  `OSError`, so it escapes out of `acquire`. Alice reproduced it directly against
  `acquire`. A string over 4300 digits would also raise `ValueError` from `int()`. Same
  class as the cycle-1 malformed-owner finding, and the PRD says a malformed owner is
  reclaimed. Fix: bound the parsed pid, or catch `(OverflowError, ValueError)` and treat
  the owner as stale. Confidence: **confirmed** (reproduced).
  - File: `skills/run-autopilot/cli/wave_slots.py:61`
  - Task: 4
  - Found by: Alice

- **[1/4] 🟡 `_discard`'s aside name `N.stale-<pid>` is deterministic — the exact
  collision the cycle-2 fix removed from `_claim`** (split back out of the script's row 1
  by hand; a different defect at a different function from the race above). Commit
  `ef9314e` gave `_claim` a unique staging name via `mkdtemp` precisely because a reused
  name collides with a leftover. `_discard` kept the deterministic form. If `_remove(aside)`
  fails, or a live claim is stranded there by the race above, the next `_discard` by the
  same pid does `os.rename(slot, aside)` onto a non-empty leftover, raises `OSError`, and
  returns False — permanently. The loop's pid is stable for its lifetime, so that slot
  number can never be reclaimed again by that loop, silently shrinking wave capacity.
  Confidence: **confirmed by reading** — `aside` at wave_slots.py:108 is
  `f"{slot.name}.stale-{pid}"`, and `_remove` at `:38` reports rather than raises, so the
  leftover path is reachable.
  - File: `skills/run-autopilot/cli/wave_slots.py:108`
  - Task: 4
  - Found by: Alice

- **[1/4] 🟡 Scope creep: the metrics clock change is not in the PRD.** `_launch` and
  `_announce_and_launch` now return a `ts_start` taken after the slot wait. The PRD's
  Feature text asks only to acquire, spawn and release in a `finally`. Blake, blind, read
  this as functionality beyond the spec (his sole `B6: fail`). Counterpoint the gate
  notes: the PRD's *third success metric* is unmeasurable without it, which is why cycle 1
  created task 5 for exactly this.
  - File: `skills/run-autopilot/cli/loop.py:389`
  - Task: 2
  - Found by: Blake

- **[1/4] 🟡 A bad slot count crashes the loop.** `_AUTOPILOT_REVIEW_SLOTS=0` or negative
  makes `acquire` raise `ValueError` at loop.py:382 — **outside the `try` at :390** — so
  it escapes `_launch` and kills the loop at its first review launch. A non-numeric value
  silently falls back to 3 via `routing._env_int`. Confidence: **confirmed by reading**
  the call site. Note: the raise is a *deliberate* cycle-1 decision (recorded in
  `autonomous_decisions`: "ValueError before dir.mkdir is the fail-loud choice over the
  alternative of polling forever"); Blake is blind and could not know that. The open
  question is fail-loud-crash vs clamp-to-1, not whether the cycle-1 fix landed.
  - File: `skills/run-autopilot/cli/wave_slots.py:140`
  - Task: 2
  - Found by: Blake

- **[1/4] 🟡 The acquire/reclaim mechanism differs from the spec's literal wording.** The
  PRD says `mkdir <dir>/<n>`, write `owner`, and on reclaim `rmdir` and retry. The code
  stages a `mkdtemp` dir and publishes with `os.rename`, and reclaims by renaming to
  `<n>.stale-<pid>` and back. This is the cycle-1 4/4 fix working as intended, so the
  deviation is sanctioned. The substantive half of the finding: `os.rename` onto an
  existing **empty** dir succeeds on POSIX, so an empty `<n>` from a hand-made `mkdir`
  would be silently overwritten. No code path in this implementation creates an empty
  `<n>`, so it needs an operator to make one by hand.
  - File: `skills/run-autopilot/cli/wave_slots.py:64`
  - Task: 1
  - Found by: Blake

- **[1/4] 🟡 `_claim` treats every rename error as a lost slot race.** A permission or
  filesystem error is indistinguishable from an occupied destination, so `acquire` can
  poll indefinitely on a broken filesystem. Distinguish `ENOTEMPTY`/`EEXIST` from other
  errors and surface the rest.
  - File: `skills/run-autopilot/cli/wave_slots.py:78`
  - Task: 4
  - Found by: Bob

- **[1/4] 🟡 Review metrics still *end* after the slot is released.** `ts_end` is read
  after `_launch` returns, so decision work runs inside the measured interval while
  another loop may already hold the slot. The cycle-1 finding fixed the start of the
  interval; Bob points out the same argument applies to its end. Capture the session end
  before release.
  - File: `skills/run-autopilot/cli/loop.py:402`
  - Task: 5
  - Found by: Bob

- **[1/4] 🟡 Moving `ts_start` into `_launch` also changes timing for builds and reviews
  without a slots dir** — their rows now exclude routing and banner time, despite the PRD
  requiring those paths run "exactly as today". **Unadjudicated disagreement:** Alice
  reports two tests pin that these paths keep the old timing; the fail-first replay shows
  both of those tests pass against the base, so they cannot demonstrate preservation.
  Neither reviewer settled it and the gate did not adjudicate it — it rides into the
  deferral below with this note.
  - File: `skills/run-autopilot/cli/loop.py:387`
  - Task: 5
  - Found by: Bob

- **[1/4] ⚪ The `waves.md` paragraph sits inside the `## wave run` section** and reads as
  a `wave run` feature. The PRD names manual export for two loops in two repos as a use
  case, and that is not described. Both variable names and the default 3 are present, so
  the Phase 2 acceptance criterion itself is met.
  - File: `skills/run-autopilot/references/waves.md:205`
  - Task: 3
  - Found by: Blake

- **[1/4] ⚪ Cannot statically verify: the recorded tests and release checks pass at
  HEAD.** Bob's sandbox is static-only. **Routed to verification** — queued as
  `bash dev/bin/release-checks` in `...-checks-2.json`; no task created. Already answered
  at this HEAD by two independent runs (see that file's `result.note`).
  - File: N/A
  - Task: general
  - Found by: Bob

### Absorbed mechanical checks

- **[1/4] 🟡 `[MECH]` 2 touched tests pass against the pre-change code:
  `test_build_launch_ts_start_matches_pre_launch_clock`,
  `test_review_launch_without_slots_dir_ts_start_matches_pre_launch_clock`.**
  **Settled this cycle** — see Settled decisions below.
  - File: `skills/run-autopilot/cli/test_loop_slots.py`
  - Task: 5
  - Found by: mech-check

- **[1/4] 🟡 `[MECH]` 12 touched tests pass against the pre-change code** in
  `test_wave_slots.py`. **Discarded this cycle** — an incremental-replay artifact, see
  Settled decisions below.
  - File: `skills/run-autopilot/cli/test_wave_slots.py`
  - Task: 4
  - Found by: mech-check

## Settled decisions (ledgered this cycle)

Recorded in
`dev/local/reviews/00217-bound-concurrent-review-sessions-with-a-slot-semaphore-v1-ledger.json`
alongside cycle 1's two entries.

1. **Two loop tests pass against pre-change code** (`test_loop_slots.py`) —
   settled-deferral. Same class as cycle 1's settled entry, with new names: both are
   negative assertions that an UNCHANGED path keeps today's timing. The PRD requires
   "every other phase, and every loop without the variable, runs exactly as today", so a
   test of preserved behavior passes against the base by construction. Task 5's own
   acceptance criteria name these two tests explicitly. Alice reached the same conclusion
   unprompted.
2. **12 `test_wave_slots.py` tests pass against pre-change code** — **discarded**, an
   artifact of the incremental replay base rather than a tautology. The base
   `1ca6f5cb6b73` is cycle 1's HEAD, where `test_wave_slots.py` already existed with 11
   passing test functions. Verified with `git show 1ca6f5c:...test_wave_slots.py`: five of
   the six named tests are present at that base. They pass there because cycle 1 wrote
   them; the cycle-2 diff only reorganised the file around them. The sixth is new but
   backfills coverage of behavior already correct at base, which the replay block itself
   says passes by design. The cycle-2 fixes are pinned by the 11 touched tests that **did**
   fail against base.

## Mechanical blocks

- **Mechanical facts** (`ast`): computed for the 4 changed Python files and supplied to
  every implementation-aware prompt. `acquire` is **33 lines**, inside the PRD's 50-line
  exit criterion. Largest function in the diff is `Loop._append_metrics` at 50 lines
  (pre-existing, at the limit, not over it); `_discard` is 39. No file approaches 800
  lines. No finding contradicted the block, so nothing was discarded under the
  computed-facts rule.
- **Tautological test shapes**: 35 test functions checked across 2 test files, **no
  `[MECH]` lines** — no test in the diff is unfailable by shape.
- **Fail-first replay** (base `1ca6f5cb6b73`, HEAD's test files overlaid): 25 touched
  tests ran, **11 failed against base**, 14 passed; 0 test files failed to collect. Both
  `[MECH]` lines it produced are absorbed into the table above and dispositioned in the
  ledger.

## Alice

Four findings, listed above (the oversized-owner crash, the three-party race residual, the
deterministic aside name, the leaked staging dirs). She verified all nine cycle-1 findings
individually, ran both suites (37 passed) and reproduced the `OverflowError` against
`acquire`. She did not re-raise either settled decision. Raw output:
`dev/local/tmp/alice-output-00217-c2.txt`.

R1: pass
R2: pass
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: fail
R10: pass
R11: pass
R12: pass
R13: pass

## Blake

Blind lens, PRD-only — he found the code himself with no diff and no history. Six
findings, listed above. He read `wave_slots.py`, `Loop._launch`, the `waves.md`
paragraph, the `[checks] waves` block and the CHANGELOG entry; ran both test files (37
passed); confirmed all 13 named acceptance tests exist. He did not run
`dev/bin/release-checks`. His single rubric failure is `B6` (scope creep), on the
metrics-clock change. Raw output: `dev/local/tmp/blake-output-00217-c2.txt`.

B1: pass
B2: pass
B3: pass
B4: pass
B5: pass
B6: fail
B7: pass
B8: pass
B9: pass
B10: pass
B11: pass
B12: pass
B13: pass
B14: pass
B15: pass
B16: pass
B17: pass
B18: pass
B19: pass

## Bob

Doubt lens + de-slop, on codex (static-only sandbox), resumed from his cycle-1 thread
`01a0eba5-1e97-7d43-90d7-3de4fe1eab3e` — no retry was needed. Four findings plus one
"cannot statically verify" note, all listed above. Raw output:
`dev/local/tmp/bob-output-00217-c2.txt`.

R1: fail
R2: pass
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: fail
R10: fail
R11: pass
R12: pass
R13: pass

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

FIX:
- A three-loop reclaim race can strand a live holder — skills/run-autopilot/cli/wave_slots.py:111 — make reclamation exclusive and add the three-loop test.
- Rename errors can become an indefinite wait — skills/run-autopilot/cli/wave_slots.py:78 — handle only destination-occupied errors as lost races; surface other errors and clean up staging.
- Metrics can overlap after slot release — skills/run-autopilot/cli/loop.py:402 — capture the session end before release and test concurrent row intervals.
- Unslotted timing changed — skills/run-autopilot/cli/loop.py:387 — retain the prelaunch start reading for builds and reviews without a slots dir.

VERIFY:
- Recorded green verification cannot be checked statically — run `bash dev/bin/release-checks` at HEAD.

KNOWN:
- (none)

## Carl

Gemini via copilot, **first run, independent** (see the top matter). He read only his two
named input files plus repository sources, ran `test_wave_slots.py` + `test_loop_slots.py`,
the full `skills/run-autopilot/cli` suite, and `bash dev/bin/release-checks` under
`env -u AUTOPILOT_DISPATCH_DEPTH -u COPILOT_CLI -u _AUTOPILOT_LOOP` (it completed). He ran
his own `os.rename` and `shutil.rmtree` probe scripts to check the semaphore's primitives,
and inspected `loop_decision.py` and `routing._env_int`. He returned no issues. Raw
output: `dev/local/tmp/carl-output-00217-c2.txt`.

R1: pass
R2: pass
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: pass
R10: pass
R11: pass
R12: pass
R13: pass

## Follow-up Tasks Created

**None.** `state.cycle` (2) has reached `state.rework_cap` (2), so the review gate's Cap
check routes this cycle to the loop-mode cap-out path rather than to rework: every
unresolved finding is ≤ 🟠 HIGH (no 🔴 CRITICAL), so each is recorded in
`state.deferred_decisions` as a `cap-overflow` record and the PRD finalizes as
converged-with-deferrals. Creating follow-up tasks here would strand pending tasks that
no rework pass will ever dispatch, breaking the Phase 9 all-tasks-completed invariant.
Recorded as an autonomous decision.

Verdict: 14 findings
Tests: 1693 passed, 0 failed, 0 skipped (reused from last-verification.json at 83165038f9dfd92ebf64ae94f38f61b946a17ee3)
