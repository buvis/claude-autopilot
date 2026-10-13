---
prd: 00283-loop-catchup-v1.md
cycle: 2
head_sha: c691ef519ad0ea62cac2391e23ebb9e55fa5c641
codex_thread_id: 01a1374f-1fba-7142-9225-175d01e3d394
reviewers: alice,blake,bob
---

# Review: 00283-loop-catchup-v1 — cycle 2

Diff range: 121579d215215872a1f688c3f102cceda7aa215c..c691ef519ad0ea62cac2391e23ebb9e55fa5c641
Batch: 202610111300

codex_rung_guard: not fired

pack: failed (engram pack exit 1: sqlite3.OperationalError: attempt to write a readonly database) — review degraded, not invalid
carl: failed this cycle (copilot backend exit 1 authentication failure; the native gemini lane was past the 60 min ceiling and was stopped). Not latched for the batch — exit 1 is a runtime failure, not exit 4.
bob: after one retry (inlined) — the first run refused for lack of input (`sandbox_apply: Operation not permitted` on both staged files)

Incremental review of the cycle-1 rework. No CRITICAL and no HIGH finding: the cycle converged.

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [1/3] | 🟡 | Simplification: `_restoring_committer_name` (19 lines) monkey-patches `run` and `run_once` on each Loop instance in `make_loop`. An autouse fixture doing `monkeypatch.delenv("GIT_COMMITTER_NAME", raising=False)` is about 3 lines and also covers tests that don't go through `make_loop`. This is the fix R7 originally suggested. The current wrapper works, so the change is optional | skills/run-autopilot/cli/loop_testutil.py:119 | 5 | ALICE |
| R2 | [1/3] | 🟡 | The Phase 1 acceptance filter (`pytest test_enter_decisions.py -k "force or head_moved"`) passes but does not select the five named tests. They live in `test_enter_loop_only.py`, so the literal acceptance command never runs them. I ran them directly and they pass, along with the existing `test_enter.py` force and moved-HEAD cases. | skills/run-autopilot/cli/test_enter_loop_only.py:40 | 3 | BLAKE |
| R3 | [1/3] | 🟡 | `catchup-probe --state` is optional and resolves the state path by walking up from cwd. The spec says `catchup-probe --state <path>`. This is a documented fix, so it is a small, benign extension. | skills/run-autopilot/cli/__main__.py:1801 | 2 | BLAKE |
| R4 | [1/3] | 🟡 | First-entry `force` still fails condition 1 of the “ALL” list, while the same paragraph permits delta without condition 2. Move the first-entry rule before the shared conditions, requiring a recorded SHA and loop-only commits. | skills/run-autopilot/references/phase-build.md:290 | 6 | BOB |
| R5 | [1/3] | 🟡 | Moving the five named acceptance tests leaves the Phase 1 command targeting only `test_enter_decisions.py`; it can pass without exercising them. Add `test_enter_loop_only.py` to that command. | docs/dev/project-management/prds/wip/00283-loop-catchup-v1.md:127 | 5 | BOB |
| R6 | [1/3] | ⚪ | R14 is only partly resolved: the `batch.catchup_completed_at` row (state-schema.md:237) still says delta needs `catchup_head_sha` to "match current HEAD". The edit landed on the adjacent `batch.catchup_head_sha` row instead, so the cited row stays stale against the loop-only rule | skills/run-autopilot/references/state-schema.md:237 | 6 | ALICE |
| R7 | [1/3] | ⚪ | The new `batch.catchup_head_sha` text names the internal closure `_loop_moved` (enter.py:308) in a schema reference. The user-facing rule is "every commit since it has committer `autopilot-loop/<batch.id>`", so drop the symbol name | skills/run-autopilot/references/state-schema.md:238 | 6 | ALICE |
| R8 | [1/3] | ⚪ | `commits_all_loop` interpolates `base` into `git log` as `f"{base}..HEAD"` with no `--end-of-options` or `^{commit}` guard. A `catchup_head_sha` starting with `-` would be read as a git option. The value comes from the agent-written state.json, so this is low risk. A bad sha makes git fail and the result is `full`, so it fails safe. | skills/run-autopilot/cli/enter_io.py:76 | 3 | BLAKE |
| R9 | [1/3] | ⚪ | The committer name is a plain string match. Anyone who sets `GIT_COMMITTER_NAME=autopilot-loop/<id>` can forge a loop commit. The spec accepts this under Risks, and a forged commit only changes the result from full to delta. | skills/run-autopilot/cli/enter_io.py:85 | general | BLAKE |
| R10 | [1/3] | ⚪ | The first session of a batch gets `autopilot-loop/no-batch`, so the next entry reads one extra full catchup. The spec accepts this under Risks and no code special-cases it. | skills/run-autopilot/cli/loop.py:419 | 1 | BLAKE |
| R11 | [1/3] | ⚪ | Prior R14 remains: the `batch.catchup_completed_at` row still documents only exact HEAD equality; the rework changed the adjacent row. Update this row to include loop-only movement and the first-entry `force` freshness exemption. | skills/run-autopilot/references/state-schema.md:237 | 6 | BOB |
| R12 | [1/3] | 🟡 | 3 touched test(s) pass against the pre-change code: test_explicit_state_flag_exits_zero_and_prints_one_json_line_with_skip_list, test_explicit_state_wins_over_the_cwd_walk_up, test_bare_invocation_without_an_autopilot_ancestor_exits_one_naming_state | skills/run-autopilot/cli/test_catchup_probe_cli.py | general | mech-check |
| R13 | [1/3] | 🟡 | 29 touched test(s) pass against the pre-change code: test_force_is_delta_when_all_commits_are_loop_commits, test_force_is_full_when_one_commit_is_not, test_force_is_full_on_git_failure +23 more | skills/run-autopilot/cli/test_enter_loop_only.py | general | mech-check |
| R14 | [1/3] | 🟡 | 1 touched test(s) pass against the pre-change code: test_git_commit_honors_the_env_launch_stamps | skills/run-autopilot/cli/test_loop_committer.py | general | mech-check |

### Auto-dismissed (ledger)

- [BLAKE] 🟡 `loop_committer` lives in `cli/enter_io.py`, not `cli/loop.py` as the Phase 0 task text says. Behavior is correct: `Loop._launch` and `enter._catchup` both use it, and `loop.py:420-422` sets `self.env` and `os.environ`. This is a placement deviation only. | File: skills/run-autopilot/cli/enter_io.py:65 — Observation only: the reviewer confirms behavior is correct. The task text named a plausible home for the helper; relocating working code to match prose is churn, not a fix.

## Alice

Consensus lens, implementation-aware. Every prior-cycle finding is resolved except R14, which was fixed on the adjacent schema row instead of the cited one. Three findings this cycle: the misplaced R14 edit, a schema reference naming an internal closure, and one optional test-harness simplification.

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

Blind lens, PRD-only. Six findings, none above 🟡: two prose/spec deviations (helper placement, optional `--state`), the acceptance-filter gap, and three accepted-risk observations (git arg interpolation, committer-name forgery, the `no-batch` first session). He verified every PRD requirement against the code and ran 8 test files directly (219 passed) plus the full gate (`PASS 6533 FAIL 0 SKIP 32 EXIT 0`).

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

Doubt lens + de-slop, after one retry (inlined). Three FIX findings, no VERIFY and no KNOWN: the Phase 1 prose ordering, the PRD acceptance command still pointing only at `test_enter_decisions.py`, and prior R14 landing on the wrong schema row. His R9 verdict is a `fail` on the acceptance-command gap, which is R5 in the table above.

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

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

Carl: failed this cycle (copilot backend exit 1 authentication failure; native gemini lane stopped past the 60 min ceiling). Not latched for the batch.

Verdict: 14 findings
Tests: 6533 passed, 0 failed, 32 skipped (suite run this cycle)
