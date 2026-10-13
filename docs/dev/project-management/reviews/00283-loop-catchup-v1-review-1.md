---
prd: 00283-loop-catchup-v1.md
cycle: 1
head_sha: 121579d215215872a1f688c3f102cceda7aa215c
codex_thread_id: 01a136f2-5d06-7253-9a29-d689ce0a2392
reviewers: alice,blake,bob
---

# Review: 00283-loop-catchup-v1 — cycle 1

Diff range: 714227e17aa09801f75cc1c39f59d03b1b318450..121579d215215872a1f688c3f102cceda7aa215c
Batch: 202610111300

codex_rung_guard: not fired

pack: failed (engram pack exit 1: sqlite3.OperationalError: attempt to write a readonly database) — review degraded, not invalid
carl: failed this cycle (copilot backend exit 1 authentication failure; native gemini retry produced no output within the watcher budget and was stopped). Not latched for the batch — exit 1 is a runtime failure, not exit 4.

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [3/3] | 🟠 | Phase 1 prose contradicts `_catchup`. Condition 1 says a spent `force` "reads delta when every commit since `catchup_head_sha` is loop-only ... checked before falling through to conditions 2 and 3". The code does not do that. With tasks present, `_catchup` still checks `catchup_completed_at` freshness first, so a stale cache with loop-only commits returns `full` (the code's own test pins this at `skills/run-autopilot/cli/test_enter_decisions.py:1774`). The prose also never states the actual F5 rule, which is the first-entry `force` (tasks empty) returning delta on loop-only commits without consulting freshness (`skills/run-autopilot/cli/enter.py:317`). As written, condition 1 sends every first-entry `force` to full catchup. Fix: state the first-entry rule in condition 1, and drop the "before conditions 2 and 3" sentence for the tasks-present case | skills/run-autopilot/references/phase-build.md:290 | 4 | ALICE, BLAKE, BOB |
| R2 | [2/3] | 🟡 | The task specified a `# ponytail: process-wide env, the loop process commits nothing else` comment on the `os.environ` write, and it is missing. Without it, a process-wide mutation in a launch helper looks accidental | skills/run-autopilot/cli/loop.py:421 | 1 | ALICE, BOB |
| R3 | [2/3] | 🟡 | `catchup_probe.main(argv)` is dead code: nothing calls it, because `__main__.py` registers its own `_run_catchup_probe`, and no test covers it. It duplicates the `--state` argparse setup. Either drop `main` and its imports (`argparse`, `json`) from the module, or make `_run_catchup_probe` delegate to it | skills/run-autopilot/cli/catchup_probe.py:82 | 2 | ALICE, BLAKE |
| R4 | [2/3] | 🟡 | The Phase 0 acceptance command for the committer stamp does not pass. `pytest ... skills/run-autopilot/cli/test_loop.py -k committer` deselects all 32 tests and exits 5. The committer tests live in a new file, `test_loop_committer.py`, instead of `test_loop.py`. The tests themselves pass | skills/run-autopilot/cli/test_loop_committer.py:1 | 1 | BLAKE, BOB |
| R5 | [1/3] | 🟠 | Phase 1 invokes `autopilot catchup-probe` without arguments, but the parser requires `--state`, so the documented call fails before probing. Use the existing state-path resolver for an optional argument and test that invocation | skills/run-autopilot/cli/__main__.py:1801 | 2 | BOB |
| R6 | [1/3] | 🟡 | `Loop._launch` assigns a local named `state`, which shadows the imported `state` module. `skills/run-autopilot/cli/loop.py:571` warns about this exact hazard and uses `current` instead. Rename the local to `current` | skills/run-autopilot/cli/loop.py:418 | 1 | ALICE |
| R7 | [1/3] | 🟡 | `os.environ["GIT_COMMITTER_NAME"]` is set by `Loop._launch` and never restored. Every test that runs a Loop leaks the stamp into the pytest process, so later git-committing tests inherit a committer name they did not ask for. Add an autouse `monkeypatch.delenv("GIT_COMMITTER_NAME", raising=False)` fixture (or restore it in `make_loop`) | skills/run-autopilot/cli/loop_testutil.py:119 | 1 | ALICE |
| R8 | [2/3] | 🟡 | `test_git_commit_honors_the_committer_name_env_var` is tautological. It exercises only git's own env handling and never touches `_launch` or `loop_committer`. It passes against the pre-change code (fail-first replay confirms this). The two `_launch` tests above it already pin the stamp, so delete this test, or make it commit using the env that `_launch` produced | skills/run-autopilot/cli/test_loop_committer.py:52 | 1 | ALICE, mech-check |
| R9 | [1/3] | 🟡 | The `catchup-probe` CLI wiring is untested. `_add_catchup_probe`/`_run_catchup_probe` and the dispatch-table entry have no test, so a broken `--state` parse or JSON print would pass the suite. The PRD pins "Stdout gets one JSON line" | skills/run-autopilot/cli/__main__.py:1800 | 2 | ALICE |
| R10 | [2/3] | 🟡 | `test_enter_decisions.py` is now 850 lines, over the 800-line cap. This diff added about 236 lines to it, and it is not one of the files 00192 deliberately excluded. Move the new loop-only block to a new `test_enter_loop_only.py`, and register it in the `[checks] enter` block of `dev/bin/release-checks` | skills/run-autopilot/cli/test_enter_decisions.py:850 | 3 | ALICE, BOB |
| R11 | [1/3] | 🟡 | Nothing tests the `os.environ["GIT_COMMITTER_NAME"]` stamp on the loop process, which the spec requires for the loop's own store commits. The tests only check the env handed to the spawn. Deleting the `os.environ` line would break no test | skills/run-autopilot/cli/loop.py:421 | 1 | BLAKE |
| R12 | [1/3] | 🟡 | Tests assert only individual child-environment snapshots; parent-process stamping and replacement after a batch change remain unpinned. Add a two-launch test checking both environment sources, with cleanup restoring `os.environ` | skills/run-autopilot/cli/test_loop_committer.py:31 | 1 | BOB |
| R13 | [1/3] | ⚪ | `probe()` has no docstring, though the design contract specifies one saying it returns `{"skip": [...]}` and writes `state.catchup_probe` unless the batch is already covered | skills/run-autopilot/cli/catchup_probe.py:52 | 2 | ALICE |
| R14 | [1/3] | ⚪ | The `batch.catchup_completed_at` row still says delta needs `catchup_head_sha` to "match current HEAD". It now also reads delta after loop-only commits | skills/run-autopilot/references/state-schema.md:238 | 4 | ALICE |
| R15 | [1/3] | ⚪ | In the first batch session, `Loop._launch` can run before `state.json` has a `batch.id`. That session's commits get `autopilot-loop/no-batch`, which `_catchup` does not recognise, so the next entry reads full once per batch. Bounded and fails safe, but unmentioned in Risks | skills/run-autopilot/cli/loop.py:419 | 1 | ALICE |
| R16 | [1/3] | ⚪ | `probe` trusts the stored record's shape. A non-dict `catchup_probe`, or a dict missing `gh` or `engram`, raises `AttributeError` or `KeyError` instead of re-probing | skills/run-autopilot/cli/catchup_probe.py:61 | 2 | BLAKE |
| R17 | [1/3] | ⚪ | `loop_committer` is defined in `enter_io.py`, not `cli/loop.py` as the Phase 0 task states. Both importers are correct, so behavior is right | skills/run-autopilot/cli/enter_io.py:65 | 1 | BLAKE |
| R18 | [1/3] | ⚪ | Small edits outside the spec's file list: an unused `NOW` import removed from `test_enter.py`, imports reordered in `test_loop_review_once.py`, a shared helper added to `enter_harness.py` | skills/run-autopilot/cli/test_loop_review_once.py:53 | general | BLAKE |
| R19 | [1/3] | ⚪ | The refreshed capsule contains the placeholder timestamp `2026-10-13T18:xx`. Replace it with the actual refresh time or a date-only value | docs/dev/project-management/meta/project-capsule.md:531 | general | BOB |

## Alice

Consensus lens, implementation-aware. Eleven findings, one HIGH (R1, the prose/code contradiction in the Phase 1 catchup conditions). The rest are quality and test-binding issues: a shadowed module name, a missing ponytail comment the task specified, an unrestored process env var, a tautological test, untested CLI wiring, dead code, and the 800-line file cap.

R1: fail
R2: fail
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: fail
R10: pass
R11: pass
R12: pass
R13: fail

## Blake

Blind lens, PRD-only. Independently found the same prose/code contradiction (R1) as his single HIGH, plus the broken Phase 0 acceptance command (R4) and the unpinned parent-process env stamp (R11). Verified as correct: `commits_all_loop` semantics (empty range True, any git failure False), `_catchup`'s first-entry force path and shared tail ordering, probe verdicts and their 15 s timeout, the state-schema row, the CHANGELOG entries, the release-checks registration and the reset-parity entry. Ran the suite: `bash dev/bin/release-checks` → PASS 6525 FAIL 0 SKIP 32 EXIT 0.

B1: fail
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

Doubt + de-slop lens (codex), after one retry (inlined). The first dispatch returned a lack-of-input refusal (`sandbox_apply: Operation not permitted`); the inlined retry carried the context and full diff as text and produced the review below. Eight findings, one HIGH: the documented `autopilot catchup-probe` invocation omits the `--state` the parser requires (R5), so the Phase 1 call fails before probing. Also independently confirmed the prose/force mismatch, the missing ponytail comment, the tautological committer test (matching the mechanical replay), the 800-line overflow, and a placeholder timestamp left in the capsule.

FIX: 8 findings. VERIFY: none. KNOWN: none.

R1: fail
R2: fail
R3: pass
R4: fail
R6: pass
R7: pass
R8: pass
R9: fail
R10: pass
R11: fail
R12: pass
R13: fail

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

Carl: failed (copilot backend exit 1, authentication failure: "Your GitHub token may be invalid, expired, or lacking the required permissions"; native-gemini retry stalled with no output past the watcher's 30-run budget and was stopped). One reviewer failing does not block the cycle; consensus denominators are 3.

Verdict: 19 findings
Tests: 6525 passed, 0 failed, 32 skipped (reused from last-verification.json at 121579d215215872a1f688c3f102cceda7aa215c)
