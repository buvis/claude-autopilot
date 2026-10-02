---
prd: dev/local/prds/wip/00185-route-review-reruns-to-high-effort-v1.md
review: 1
date: 2026-09-07
head_sha: 9f74fd563fbbf2abcfa486f54a42936c70c1e50f
codex_thread_id: 01a07c0c-1b48-7a00-a5ed-c33859052a67
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00185-route-review-reruns-to-high-effort-v1

Diff range: `bf9f8d4a31418b886544f2f05af9f48b0e9e310b..9f74fd563fbbf2abcfa486f54a42936c70c1e50f`

codex_rung_guard: not fired

pack: unavailable this cycle (`engram pack` exited 1 twice — "not inside a registered repo; register it in ~/.config/gita/repos.csv"). Prompts carried the sentinel `(no pack available this cycle)` for `{PACK_FILE}` and `{PACK_FINDINGS}`. Review is degraded on retrieval context, not invalid.

diff-scope note: `gather-context.sh` with no `--since` produced an **empty** diff — its full-review default diffs against `master`, and HEAD *is* `master` on this repo. The run was redone with `--since bf9f8d4a31418b886544f2f05af9f48b0e9e310b` (`state.work_start_sha`), which is the PRD's whole work range and the scope the doubt lens requires. Reviewers saw 5 files / 591 diff lines. Had this not been caught, every lens would have reviewed nothing and the cycle would have converged vacuously.

verification-check queue: **not written this cycle.** The queue is fed from a doubt lens's FIX/VERIFY/KNOWN buckets. Eve did not run (the codex doubt-roster guard did not fire, so she was not activated), and `agents/bob.md` defines no such buckets — `references/output-formats.md` reserves `source: "bob"` explicitly and forbids inventing buckets he did not emit. Bob's two `Cannot statically verify:` lines are ordinary Low findings in the table below, classified normally, and are answered by the suite run recorded at the foot of this file.

## Review Summary

Reviewed: 3 completed tasks
PRDs checked: 00185-route-review-reruns-to-high-effort-v1

### Agent Status

- Alice: ✅ Available (Claude subagent, consensus engine `legacy`)
- Blake: ✅ Available (Claude subagent, blind lens — PRD-only)
- Bob: ✅ Available (codex, doubt + de-slop lens; thread id captured)
- Carl: ✅ Available (gemini-run backend `copilot`, model `gemini-3.8-flash`)

## Consolidated Findings

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [1/4] | 🟡 | `_run_once` (skills/run-autopilot/cli/loop.py:1184-1199) duplicates the newly-extracted `_launch_phase` (skills/run-autopilot/cli/loop.py:1246-1267) almost line-for-line: read state, `routing.route(...)`, build the same `━━ {stamp} · phase ... · prd ... · {plan.model}/{plan.effort} ━━` banner, then `self._launch(plan, ap_dir)`. The duplication predates this diff, but this diff is what turned one copy into a named, reusable function (`_launch_phase`) while leaving `_run_once`'s copy untouched — the cheapest moment to fold both onto one helper (e.g. have `_launch_phase` accept an already-resolved phase, or split out a shared `_announce_and_launch(ap_dir, phase, prd, plan)`) before it calcifies further. Behavior-preserving, not required for this PRD's acceptance criteria. | skills/run-autopilot/cli/loop.py | 2 | ALICE |
| [1/4] | 🟡 | FIX: `review_cycle` returns booleans for JSON boolean cycles, contrary to the existing schema's integer contract. Exclude `bool`, return 1, and test both boolean values. | skills/run-autopilot/cli/routing.py:205 | 1 | BOB |
| [1/4] | 🟡 | FIX: The override test never supplies both effort overrides, leaving their required precedence untested. Set REVIEW=xhigh and REVIEW_RERUN=medium together at cycle 3 and assert xhigh. | skills/run-autopilot/cli/test_routing.py:590 | 1 | BOB |
| [1/4] | 🟡 | FIX: Metrics tests call `_append_metrics` directly; neither launch path tests persisted rerun effort. Exercise `run()` and `run_once()` at cycle 2 and assert the spawned effort and both metrics copies contain high. | skills/run-autopilot/cli/test_routing.py:630 | 2 | BOB |
| [1/4] | 🟡 | FIX: The PRD's unreadable-state scenario lacks coverage. Make `Path.read_text` raise `PermissionError`; assert cycle 1, xhigh routing, and no state write. | skills/run-autopilot/cli/test_routing.py:542 | 1 | BOB |
| [1/4] | 🟡 | FIX: Seven comment lines narrate the metrics test's setup. Replace them with "Empty and unknown efforts must persist verbatim; repeated calls must append." This preserves the rationale without repeating the test body. | skills/run-autopilot/cli/test_routing.py:631 | 2 | BOB |
| [1/4] | ⚪ | FIX: The module documentation still says review stays at xhigh. Describe the new first-cycle/rerun distinction. | skills/run-autopilot/cli/routing.py:12 | 1 | BOB |
| [1/4] | ⚪ | KNOWN: Supplied counts show four unchanged methods exceeding 50 lines: `_register`, `_decide`, `_decide_no_progress`, and `_act_park`. Refactoring these unrelated methods is outside this PRD; changed functions satisfy the limit. | skills/run-autopilot/cli/loop.py | general | BOB |
| [1/4] | ⚪ | KNOWN: `loop.py` remains 1,380 lines, exceeding 800. This violation predates the diff; splitting the existing driver exceeds the effort-routing scope. | skills/run-autopilot/cli/loop.py | general | BOB |
| [1/4] | ⚪ | Cannot statically verify: per-test fail-first results; supplied replay ran zero tests. VERIFY by moving the new-symbol import into its helper tests temporarily and replaying against bf9f8d4a3141, inspecting each test's outcome. | N/A | 1 | BOB |
| [1/4] | ⚪ | Cannot statically verify: tests and release checks pass. VERIFY with `uv run --no-project --with pytest --with rich python -m pytest -q skills/run-autopilot/cli` and `bash dev/bin/release-checks`. | N/A | general | BOB |

### Full Consensus (4/4)

- (none)

### Majority Consensus (>50%)

- (none)

### Minority (<=50%)

All 11 findings are [1/4]. Two reviewers (Blake, Carl) returned clean; Alice
raised one; Bob raised ten.

## Alice

[ALICE] 🟡 `_run_once` (skills/run-autopilot/cli/loop.py:1184-1199) duplicates the newly-extracted `_launch_phase` (skills/run-autopilot/cli/loop.py:1246-1267) almost line-for-line: read state, `routing.route(...)`, build the same banner, then `self._launch(plan, ap_dir)`. The duplication predates this diff, but this diff is what turned one copy into a named, reusable function while leaving `_run_once`'s copy untouched. Behavior-preserving, not required for this PRD's acceptance criteria. | File: skills/run-autopilot/cli/loop.py | Task: 2

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

## Blake

[BLAKE] ✅ No issues found

B1: pass
B2: pass
B3: pass
B4: pass
B5: pass
B6: pass
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

[BOB] 🟡 FIX: `review_cycle` returns booleans for JSON boolean cycles, contrary to the existing schema's integer contract. Exclude `bool`, return 1, and test both boolean values. | File: skills/run-autopilot/cli/routing.py:205 | Task: 1
[BOB] 🟡 FIX: The override test never supplies both effort overrides, leaving their required precedence untested. Set REVIEW=xhigh and REVIEW_RERUN=medium together at cycle 3 and assert xhigh. | File: skills/run-autopilot/cli/test_routing.py:590 | Task: 1
[BOB] 🟡 FIX: Metrics tests call `_append_metrics` directly; neither launch path tests persisted rerun effort. Exercise `run()` and `run_once()` at cycle 2 and assert the spawned effort and both metrics copies contain high. | File: skills/run-autopilot/cli/test_routing.py:630 | Task: 2
[BOB] 🟡 FIX: The PRD's unreadable-state scenario lacks coverage. Make `Path.read_text` raise `PermissionError`; assert cycle 1, xhigh routing, and no state write. | File: skills/run-autopilot/cli/test_routing.py:542 | Task: 1
[BOB] 🟡 FIX: Seven comment lines narrate the metrics test's setup. Replace them with "Empty and unknown efforts must persist verbatim; repeated calls must append." This preserves the rationale without repeating the test body. | File: skills/run-autopilot/cli/test_routing.py:631 | Task: 2
[BOB] ⚪ FIX: The module documentation still says review stays at xhigh. Describe the new first-cycle/rerun distinction. | File: skills/run-autopilot/cli/routing.py:12 | Task: 1
[BOB] ⚪ KNOWN: Supplied counts show four unchanged methods exceeding 50 lines: `_register`, `_decide`, `_decide_no_progress`, and `_act_park`. Refactoring these unrelated methods is outside this PRD; changed functions satisfy the limit. | File: skills/run-autopilot/cli/loop.py | Task: general
[BOB] ⚪ KNOWN: `loop.py` remains 1,380 lines, exceeding 800. This violation predates the diff; splitting the existing driver exceeds the effort-routing scope. | File: skills/run-autopilot/cli/loop.py | Task: general
[BOB] ⚪ Cannot statically verify: per-test fail-first results; supplied replay ran zero tests. VERIFY by moving the new-symbol import into its helper tests temporarily and replaying against bf9f8d4a3141, inspecting each test's outcome. | File: N/A | Task: 1
[BOB] ⚪ Cannot statically verify: tests and release checks pass. VERIFY with `uv run --no-project --with pytest --with rich python -m pytest -q skills/run-autopilot/cli` and `bash dev/bin/release-checks`. | File: N/A | Task: general

R1: fail
R2: fail
R3: pass
R4: pass
R6: pass
R7: fail
R8: pass
R9: fail
R10: pass
R11: pass
R12: fail
R13: fail
D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

[CARL] ✅ No issues found

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

## Mechanical checks

- **Mechanical facts**: computed from `ast` over the three changed Python files and appended to the reviewer context. Bob's two KNOWN findings cite it correctly (`loop.py` at 1,380 lines; four unchanged methods over 50 lines) — those are his R12/R13 fails, and both are pre-existing violations he himself scopes out. PRD 00192 (`split-loop-py-and-its-tests-under-the-cap`) already sits in the backlog for `loop.py`.
- **Tautological test shapes**: 46 test functions checked in 1 test file, **0 `[MECH]` findings**.
- **Fail-first replay**: 0 touched tests ran; 1 test file could not be collected at base — HEAD's `test_routing.py` imports `review_cycle`, which does not exist at `bf9f8d4a3141`, so its tests fail there. That is fail-first evidence, not a gap. Bob's "supplied replay ran zero tests" finding restates this block rather than contradicting it.

## Tail sweep (post-convergence)

The cycle converged on the severity bar (zero CRITICAL, zero HIGH) and the
constraint gate certified, so the Medium/Low tail was swept rather than
re-reviewed. One `[D1]` task (id 4, tier sonnet) carried all 7 actionable
findings verbatim; 4 findings were discarded with reasons recorded in
`00185-route-review-reruns-to-high-effort-v1-ledger.json`.

Commits: `67b312f` (tests), `0bb137d` (implementation + CHANGELOG).

Per-task gates: `style_gate: clean`, `split_hygiene: clean`,
`self_deslop: skipped:trivial` (net +7 lines), `reflow` clean.
Red check saw red at the test commit (2 failed, 137 passed) and green after
the fix (149 passed).

Pat (step-5.7 per-task reviewer) returned `CLOSURE | resolved` for all 7 swept
findings and raised one new finding:

- ⚪ LOW | `skills/run-autopilot/cli/test_loop.py:386-419` | the two new
  launch-path tests are identical except for `lp.run()` vs `lp.run_once()` |
  fix: parametrize over the two entry points.

**Disposition: noted, not fixed.** Pat's own ladder routes a LOW to "note and
proceed", and Phase 5 does not reopen after convergence. It is recorded here
rather than in chat so it has a durable home; it is a cosmetic test-duplication
nit with no correctness impact, and the duplication is 17 lines.

One correction to this file's own record: the dispatch brief for the sweep
asserted that both the boolean-cycle case and the unreadable-state case were
unimplemented. Only the boolean case was — `review_cycle` already swallowed a
read error. The unreadable-state test is therefore a coverage backfill that
passes on arrival, not a fail-first test, and it is recorded as such.

Verdict: 11 findings
Tests: 2757 passed, 0 failed, 32 skipped (suite run this cycle)
Post-sweep suite at 0bb137d: 2763 passed, 0 failed, 32 skipped; `bash dev/bin/release-checks` exit 0
