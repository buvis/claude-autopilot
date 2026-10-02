---
prd: dev/local/prds/wip/00217-bound-concurrent-review-sessions-with-a-slot-semaphore-v1.md
review: 1
date: 2026-09-29
head_sha: 1ca6f5cb6b73cd97be6fef571ea0d24038453485
codex_thread_id: 01a0eba5-1e97-7d43-90d7-3de4fe1eab3e
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00217-bound-concurrent-review-sessions-with-a-slot-semaphore-v1

Diff range: `5bed041ff0d73d69a560ed382d8e6b78c5a17cac..1ca6f5cb6b73cd97be6fef571ea0d24038453485`
(full review, cycle 1 — the PRD's whole work range from `state.work_start_sha`)

codex_rung_guard: not fired

pack: failed (`engram pack` exited 1: "not inside a registered repo; register it in
/Users/bob/.config/gita/repos.csv"). Every prompt that takes `{PACK_FILE}` / `{PACK_FINDINGS}`
received the sentinel `(no pack available this cycle)` instead. Blake never receives a pack by
design.

**Carl ran twice this cycle.** His first run read `dev/local/tmp/bob-output-00217-c1.txt` mid-run
and returned Bob's six findings and all twelve of Bob's `R{n}` verdicts verbatim, relabelled
`[CARL]`. That output was not an independent lens and would have inflated every Bob finding from
[1/4] to [2/4], so it was set aside as
`dev/local/tmp/carl-output-00217-c1.contaminated.txt`, its dispatch row closed
`error / non-independent`, and Carl was re-dispatched once (`references/retry-policy.md` one-retry
budget) with an explicit independence rule forbidding him to open any other reviewer's output,
prompt, or the review/state directories. The retry is independent: it reproduced the race with its
own two-process experiment, in its own words, and returned a different severity and a different
verdict set. **Only the retry is consolidated below.**

## Review Summary

Reviewed: 3 completed tasks
PRDs checked: 00217-bound-concurrent-review-sessions-with-a-slot-semaphore-v1.md

### Agent Status

- Alice: ✅ Available (Claude subagent, consensus lens, `consensus_engine: legacy`)
- Blake: ✅ Available (Claude subagent, blind lens — PRD-only)
- Bob: ✅ Available (codex, doubt lens + de-slop, first run)
- Carl: ✅ Available (gemini/copilot, after one retry — see the contamination note above)
- Eve: ⏸️ Disabled (doubt reviewer resolved to `codex`; the codex doubt-roster guard did not fire —
  no task attempt has `implementor: "codex"`)

## Consolidated Findings

`consolidate_findings.py` ran and produced the machine table, but its suffix-stripping merge folded
two **distinct** findings into their neighbours (it merged `wave_slots.py:24` into the
`wave_slots.py:32` race row, and `test_wave_slots.py:141` into the `test_wave_slots.py:64` row).
Those two were split back out by hand and are marked below. Near-duplicate rows the matcher missed
because the raisers cited different files for the same defect (Bob's `wave_slots.py:54` nonpositive
count vs Alice/Blake's `loop.py:381`; Bob's `wave_slots.py:81` release vs Alice/Blake's same) were
folded, with consensus summed. Everything else is the script's output unchanged.

### Full Consensus (4/4)

- **[4/4] 🟠 Slot claim is not atomic and reclaim is not exclusive — the semaphore can hand one slot
  to two holders.** `_claim` does `os.mkdir` and only afterwards publishes `owner`. In that gap a
  second acquirer reads the missing `owner` as stale, renames the half-claimed slot aside and claims
  it; the first claimant then either dies with an uncaught `FileNotFoundError` out of `acquire` (and
  so out of `Loop._launch`), or finishes publishing over the second claimant's `owner`, leaving both
  holding slot N. That breaks the PRD's "never more than N review sessions" invariant and Phase 0's
  "the semaphore is exact". The dead-pid path has the same time-of-check/time-of-use gap:
  `os.rename(slot, aside)` moves whatever sits at the path, so a slower reclaimer can move a slot a
  faster peer just claimed with a live pid — the code comment "only one reclaimer can win the
  rename" is false. `release` also removes whatever dir it is handed with no ownership check, so it
  would delete the second claimant's slot.
  **This is the confirmed-but-unfixed MEDIUM the per-task review deferred here** (`attempts[0].review:
  "medium-retry:unfixed"` on task 1). Two reviewers reproduced it independently: Blake forced the
  interleaving with count=1 and got `slots/1` from both acquires; Carl demonstrated P1 overwriting
  P2's owner in a two-process script. Confidence: **confirmed**, not suspected.
  Fix both reviewers converged on: build the slot as `<n>.tmp-<pid>/` holding `owner`, then
  `os.rename` it onto `<n>` (renaming onto a non-empty dir fails), so an ownerless slot never exists.
  - File: `skills/run-autopilot/cli/wave_slots.py:32`
  - Task: 1
  - Found by: Alice, Blake, Bob, Carl

- **[4/4] 🟡 The five-minute stderr heartbeat has no test.** The PRD mandates "printing one stderr
  line per five minutes of waiting that names the dir". Every `acquire` test injects a `_fake_clock`
  returning a constant `0.0`, so the `HEARTBEAT_SECS` branch never executes. The line, its interval,
  its "names the dir" content and the `last_note` reset could all break unseen.
  - File: `skills/run-autopilot/cli/test_wave_slots.py:64`
  - Task: 1
  - Found by: Alice, Blake, Bob, Carl

### Majority Consensus (>50%)

- **[3/4] 🟡 A nonpositive `_AUTOPILOT_REVIEW_SLOTS` makes `acquire` poll forever.** `Loop._int` /
  `routing._env_int` pass `0` or a negative through unchanged, `range(1, count + 1)` is then empty,
  and `acquire` sleeps for ever with only a five-minute heartbeat that does not name the count.
  `wave run` and `wave.py` validate the count, but the hand-export path the PRD explicitly names
  ("any operator who exports the variables by hand for two loops in two repos") does not. Blake
  confirmed count 0 reaches `sleep_fn` with no slot ever claimed.
  - File: `skills/run-autopilot/cli/loop.py:381` (fix may equally land in `wave_slots.py:54`)
  - Task: 2
  - Found by: Alice, Blake, Bob

- **[3/4] 🟡 `release` swallows every removal error, not just "already gone".**
  `shutil.rmtree(slot, ignore_errors=True)` hides `EACCES`/`EBUSY` as readily as a missing dir, so a
  failed release leaks a slot held by a live loop pid for that loop's whole lifetime, silently
  cutting wave capacity. The reclaim path does the same to the `n.stale-<pid>` aside dir. The PRD
  asks only that "releasing a slot that is already gone is a no-op" — that is `FileNotFoundError`,
  not every `OSError`.
  - File: `skills/run-autopilot/cli/wave_slots.py:81` (also `:70`)
  - Task: 1
  - Found by: Alice, Blake, Bob

### Minority (<=50%)

- **[2/4] 🟡 A review row's `ts_start` and `wall_secs` include the slot wait, defeating the PRD's own
  post-release signal.** `_launch_phase` (`loop.py:506`) and `_run_once` stamp `ts_start` *before*
  `_announce_and_launch`, which then blocks in `wave_slots.acquire` (`loop.py:379`). A loop queued
  behind three running reviews therefore writes a `loop-metrics.jsonl` row whose interval overlaps
  all three. The PRD's third success metric is "no more than `_AUTOPILOT_REVIEW_SLOTS`
  `loop-metrics.jsonl` rows with `phase_launched: "review"` overlap in time" — so the metric reads as
  violated exactly when the semaphore is working. It also inflates review `wall_secs` in
  `render_metrics` and the wave-hours sum at `wave_assemble.py:59` with pure queue time. No test
  covers it.
  - File: `skills/run-autopilot/cli/loop.py:506` (also `:379`)
  - Task: 2
  - Found by: Alice, Blake

- **[2/4] 🟡 `test_docs_name_the_two_variables` pins only one of the two variables** (split back out
  of the script's row 2 by hand). The second assertion, `"_AUTOPILOT_REVIEW_SLOTS" in text`, is a
  substring of the first, `"_AUTOPILOT_REVIEW_SLOTS_DIR" in text`, so it cannot fail on its own: the
  test would still pass if the count variable and its default 3 were deleted from `waves.md`
  entirely. The PRD's Phase 2 acceptance criterion is that this test "pins
  `_AUTOPILOT_REVIEW_SLOTS_DIR` **and** `_AUTOPILOT_REVIEW_SLOTS`", so the criterion is not actually
  met. Fix: assert with a boundary the DIR name does not satisfy (a
  `_AUTOPILOT_REVIEW_SLOTS(?!_DIR)` regex, or the backticked form), and pin the default 3.
  - File: `skills/run-autopilot/cli/test_wave_slots.py:141`
  - Task: 3
  - Found by: Alice, Blake

- **[1/4] 🟡 `_stale` guards only `FileNotFoundError`, so several "malformed owner" cases crash
  instead of being reclaimed** (split back out of the script's row 1 by hand — it is a different
  defect from the race above, at a different function). Blake confirmed that an `owner` file holding
  non-UTF-8 bytes raises `UnicodeDecodeError` straight out of `acquire`, aborting the loop's launch;
  a slot path that is a file (`NotADirectoryError`) or unreadable (`PermissionError`) would raise the
  same way. Separately, an `owner` of `"0"` passes `isdigit()` and `os.kill(0, 0)` succeeds against
  the caller's own process group, so that slot is never reclaimed — Blake confirmed it reaches
  `sleep_fn`. The PRD says a missing **or malformed** owner is reclaimed; the tests cover only the
  `"not-a-pid"` shape.
  - File: `skills/run-autopilot/cli/wave_slots.py:24`
  - Task: 1
  - Found by: Blake

- **[1/4] 🟡 `test_pid_alive_tells_a_live_pid_from_an_exited_one` retests an unchanged imported
  helper** (de-slop lens). `_pid_alive` is `loop_gates`' existing, already-tested function; spawning
  a real subprocess here adds runtime to this suite without covering any behavior the diff changed.
  - File: `skills/run-autopilot/cli/test_wave_slots.py:128`
  - Task: 1
  - Found by: Bob

- **[2/4] 🟡 Two touched tests pass against the pre-change code** — `test_build_launch_never_touches_slots`
  and `test_no_slot_dir_means_no_semaphore`. Computed by the fail-first replay (7 of 9 touched tests
  failed against base, these 2 passed) and independently raised by the doubt lens.
  **Settled this cycle** — see Settled decisions below.
  - File: `skills/run-autopilot/cli/test_loop_slots.py:128`
  - Task: 2
  - Found by: Bob, mech-check

- **[1/4] ⚪ Liveness is `_pid_alive` only, so a recycled pid holds a slot indefinitely.**
  **Settled this cycle** — see Settled decisions below.
  - File: `skills/run-autopilot/cli/wave_slots.py:29`
  - Task: 1
  - Found by: Blake

- **[1/4] ⚪ Cannot statically verify: the recorded test and release-check runs pass at HEAD.**
  Bob's sandbox is static-only. **Routed to verification** — queued as
  `bash dev/bin/release-checks` in
  `dev/local/reviews/00217-bound-concurrent-review-sessions-with-a-slot-semaphore-v1-checks-1.json`;
  no task created for it.
  - File: N/A
  - Task: general
  - Found by: Bob

## Settled decisions (ledgered this cycle)

Both are recorded in
`dev/local/reviews/00217-bound-concurrent-review-sessions-with-a-slot-semaphore-v1-ledger.json`
so they are not re-argued in cycle 2.

1. **Two tests pass against pre-change code** (`test_loop_slots.py`) — settled-deferral. Both are
   PRD-named acceptance criteria asserting that the *unchanged* path stays unchanged: a build phase,
   and a loop with no slots dir, must touch no slot. A negative assertion of preserved behavior
   passes against the base by construction; making either fail first would change what it tests. The
   doubt lens filed it in KNOWN with the same justification.
2. **pid recycling** (`wave_slots.py:29`) — settled-deferral. The PRD's Risks section states liveness
   is by pid, and the raiser explicitly declined to count it against the spec. Adding `_pid_tagged`
   is a change to the shared liveness helper, not to this PRD's semaphore.

## Mechanical blocks

- **Mechanical facts** (`ast`): computed for all 5 changed Python files and supplied to every
  implementation-aware prompt. `acquire` is **34 lines**, inside the PRD's 50-line exit criterion;
  no function in the diff exceeds 50 lines; no file approaches 800. No finding contradicted the
  block, so nothing was discarded under the computed-facts rule.
- **Tautological test shapes**: 27 test functions checked across 3 test files, **no `[MECH]` lines**
  — no test in the diff is unfailable by shape.
- **Fail-first replay** (base `5bed041ff0d7`, HEAD's test files overlaid): 9 touched tests ran,
  **7 failed against base**, 2 passed; 1 test file could not be collected at base. The one `[MECH]`
  line it produced is absorbed into the table above and settled in the ledger.

## Alice

Six findings, listed above (the race, the untested heartbeat, the vacuous docs assertion, the
metrics clock, the swallowed release errors, the nonpositive count). Raw output:
`dev/local/tmp/alice-output-00217-c1.txt`.

R1: fail
R2: fail
R3: pass
R4: fail
R6: pass
R7: pass
R8: pass
R9: pass
R10: pass
R11: pass
R12: pass
R13: pass

## Blake

Blind lens, PRD-only — he located the code himself and reproduced two defects with live
experiments. Seven findings, listed above. He also recorded what he verified as correct: `acquire`
is 34 lines; `Loop._launch` is the only `self._spawn` call site and receives `phase` from
`_announce_and_launch`, so `review-once` takes a slot too; build phases and a loop without the dir
variable never touch the semaphore; the release runs in a `finally`; the CHANGELOG entry is under
`### Added`; the `waves.md` paragraph is at `references/waves.md:205`; both test files are in the
`[checks] waves` block at `dev/bin/release-checks:123`; the two new suites pass (20), and the
existing loop and wave_docs suites pass (157). Raw output:
`dev/local/tmp/blake-output-00217-c1.txt`.

B1: fail
B2: pass
B3: pass
B4: pass
B5: fail
B6: pass
B7: pass
B8: pass
B9: pass
B10: pass
B11: fail
B12: pass
B13: pass
B14: fail
B15: pass
B16: pass
B17: pass
B18: pass
B19: pass

## Bob

Doubt lens + de-slop, on codex (static-only sandbox), first run — no retry was needed. Six findings
plus one "cannot statically verify" note, all listed above. Raw output:
`dev/local/tmp/bob-output-00217-c1.txt`.

R1: fail
R2: fail
R3: pass
R4: pass
R6: pass
R7: fail
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
- Live claims can be reclaimed — skills/run-autopilot/cli/wave_slots.py:62 — serialize claim, owner publication, and reclamation, with race tests.
- Nonpositive counts wait forever — skills/run-autopilot/cli/wave_slots.py:54 — reject counts below 1.
- Release errors are swallowed — skills/run-autopilot/cli/wave_slots.py:81 — ignore only a missing slot.
- Waiting-message behavior is untested — skills/run-autopilot/cli/test_wave_slots.py:64 — test two five-minute intervals with an injected clock and captured stderr.
- Imported-helper test is redundant — skills/run-autopilot/cli/test_wave_slots.py:128 — remove the test.

VERIFY:
- Recorded green verification cannot be checked statically — run `bash dev/bin/release-checks` at HEAD.

KNOWN:
- Two required negative acceptance tests pass against pre-change code — their purpose is to preserve unchanged build and unset-directory behavior, so making each fail first would change what it tests.

## Carl

Gemini via copilot, **second (retry) run** — the first was discarded as non-independent, see the
note in the top matter. The retry independently reproduced the ownerless-window race with its own
two-process script and raised it at 🟡, plus the untested heartbeat at ⚪. It also ran
`bash dev/bin/release-checks`: the first attempt failed only because this session's environment had
`AUTOPILOT_DISPATCH_DEPTH` / `COPILOT_CLI` / `_AUTOPILOT_LOOP` exported, tripping the runner's
nested-dispatch guard inside the reviewer's own shell; re-run under `env -u ...` it completed clean.
That is a reviewer-environment artifact, not a repository failure, and is not counted as a finding.
Raw output: `dev/local/tmp/carl-output-00217-c1.txt`.

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

1. `[D1] Make the slot claim atomic and the reclaim exclusive` (M) — 🟠 4/4 consensus — addresses the
   race, `_stale` robustness, the swallowed release errors, the nonpositive count guard, the untested
   heartbeat, the vacuous docs assertion, and the redundant helper test. Tier: **opus**
   (algorithmic risk — concurrency correctness; the PRD's own `model_tier_rationale` reserves opus for
   exactly this row).
2. `[D1] Start the review metrics clock after the slot wait` (S) — 🟡 2/4 consensus — addresses the
   `ts_start` / `wall_secs` queue-time inflation that defeats the PRD's post-release signal. Tier:
   **sonnet** (`default_model` floor; no algorithmic-risk row).

Verdict: 11 findings
Tests: 1676 passed, 0 failed, 0 skipped (suite run this cycle: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli`, plus 664 subtests passed; `last-verification.json` matched the reviewed HEAD but carried null counts, so it could not be reused)
