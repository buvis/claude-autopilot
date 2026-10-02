---
prd: dev/local/prds/wip/00181-scrub-inherited-host-markers-at-loop-spawn-v1.md
review: 1
date: 2026-09-07
head_sha: 407c1e87458bde2291cb03c2b10f977c54e73ac1
codex_thread_id: 01a078d3-4645-7b62-88f6-97e605907447
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00181-scrub-inherited-host-markers-at-loop-spawn-v1

Diff range: `f1489df17d887c4afc415503d7be2418fb0709f8..407c1e87458bde2291cb03c2b10f977c54e73ac1`

codex_rung_guard: not fired

## Run notes

- **Diff base.** This is a full review of the PRD's whole work range. The base is `state.work_start_sha`. It was passed to `gather-context.sh` via `--since`, because this repo commits directly to `master`, so the script's default `git diff master` base produced an empty diff on the first attempt. The context file's own "incremental review" scope label is therefore wrong and was corrected in place; there is no prior cycle.
- **Context pack.** `engram pack` exited 1 (`not inside a registered repo; register it in /Users/bob/.config/gita/repos.csv`). Not retried — a deterministic configuration error, not a transient one. `{PACK_FILE}` and `{PACK_FINDINGS}` were substituted with `(no pack available this cycle)` for every reviewer that takes them. The review is degraded by the missing retrieval context, not invalid.
- **Consolidation.** `consolidate_findings.py` ran and produced 8 rows. Two of those rows are the same defect: Bob's `loop.py:357` finding and Alice's `loop.py` finding both describe `runner.child_env(env)[0]` discarding the tuple's second member by positional index. The script did not merge them because their `File:` strings differ by the `:357` line suffix. **They were merged by hand into one `[2/4]` row below** — flagged here rather than left silent, so the table's consensus count is not mistaken for the script's own output. The other six rows are the script's verbatim.
- **Verification-check queue.** Not written this cycle. Eve did not run (the codex doubt-roster guard did not fire — no task in this PRD has `attempts[].implementor == "codex"`; all four ran on `claude`), and `agents/bob.md` defines no FIX/VERIFY/KNOWN buckets, so `source: "bob"` is reserved and nothing sources from him. Bob's one VERIFY-flavoured line is kept as an ordinary finding below (**not queued: no mandated doubt-lens VERIFY bucket this cycle**).
- **Carl backend.** `backend=copilot model=gemini-3.8-flash`, exit 0, non-empty reviewer text.

## Mechanical checks (computed)

- **Tautological test shapes:** 90 test functions checked across 2 test files. No `[MECH]` lines.
- **Fail-first replay** against `f1489df17d88`: 1 touched test ran, 1 failed against base, 0 passed; 1 test file could not be collected at base (its tests fail there). No `[MECH]` lines. Nothing in this diff's tests passes against the pre-change code.

## Consolidated Findings

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [2/4] | 🟡 Medium | `runner.child_env(env)[0]` in `_run_agoge_process` obscures which tuple member reaches `Popen`; unpack to `env_for_child, _ = runner.child_env(env)` and pass the named value. Alice notes it matches the PRD's "discard or ignore the list" instruction; Bob asks for the named unpack. | skills/run-autopilot/cli/loop.py:357 | 3 | ALICE, BOB |
| [2/4] | ⚪ Low | The PRD's own Success Metrics command (`pytest -q skills/run-autopilot/cli/test_runner.py -k "child_env or scrub"`) selects only 4 of the "five new tests" it claims to verify: `test_spawn_silent_without_markers` matches neither keyword, and `test_run_agoge_scrubs_host_markers` lives in `test_loop.py`, outside the named file. All five tests exist and pass. PRD-authoring imprecision, not an implementation defect. | N/A | general | ALICE, BLAKE |
| [1/4] | 🟡 Medium | The spawn scrub test uses one marker, so it cannot verify sorted multi-marker rendering or the required comma-space separator; use the three-marker PRD example and assert its exact stderr line. | skills/run-autopilot/cli/test_runner.py:129 | 2 | BOB |
| [1/4] | 🟡 Medium | Exact tuple equality already verifies the tuple shape and excludes `AUTOPILOT_DISPATCH_DEPTH`; remove the redundant `isinstance` assertion and the standalone exclusion test while retaining the behavioral depth-survival test. | skills/run-autopilot/cli/test_runner.py:252 | 1 | BOB |
| [1/4] | ⚪ Low | Pre-existing file-size cap violation: `loop.py` (1355 lines) and `test_loop.py` (1404 lines) exceed the 800-line max; both were already over (1343 / 1378) at base `f1489df17d88`, so this diff adds to but did not create it. Raised under rubric R13; not attributable to this PRD's scope. | skills/run-autopilot/cli/loop.py | general | ALICE |
| [1/4] | ⚪ Low | `spawn()`'s docstring was not updated to mention the new host-marker scrub notice, only the pre-existing launch/tee/cap behavior. | skills/run-autopilot/cli/runner.py | 2 | ALICE |
| [1/4] | ⚪ Low | Cannot statically verify tests and release checks pass; run `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_runner.py skills/run-autopilot/cli/test_loop.py` and `bash dev/bin/release-checks`. (Bob's sandbox cannot execute. Both commands were in fact run at this exact HEAD by the work phase and by Alice, Blake and Carl independently — all green.) | N/A | general | BOB |

No 🔴 Critical and no 🟠 High findings from any reviewer.

## Alice (consensus lens, Claude subagent)

Four ⚪ Low findings, all listed above. Verification she performed: ran `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_runner.py skills/run-autopilot/cli/test_loop.py` → 90 passed. Ran the PRD's exact success-metric command (`-k "child_env or scrub"`) → 4 passed, which is the basis of the PRD-imprecision finding. Confirmed `rg -n 'LAUNCH_ENV' skills/run-autopilot/cli --glob '!test_*'` lists only `runner.py`; `runner.LAUNCH_ENV` has zero hits in `loop.py` and `child_env` exactly one; `HOST_MARKERS` has exactly one hit each in `host-markers.md` and `CHANGELOG.md`, the CHANGELOG entry correctly under `### Fixed` in `[Unreleased]`. Confirmed `spawn()` and `run_agoge()` signatures are unchanged and each has exactly one caller. Confirmed the fail-first replay block is consistent with genuine, non-tautological tests. No hardcoded secrets, no injection vectors (`Popen` uses argv lists throughout, no `shell=True`), no debug or TODO markers in the diff.

Rubric verdicts:

```
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
R13: fail
```

R13 fails on the pre-existing `loop.py` / `test_loop.py` size violation described above, which predates this diff.

## Blake (blind lens, PRD-only)

One ⚪ Low finding, listed above. Blake received only the PRD and the blind rubric — no diff, no changed-file list, no review history — and located the code himself.

He confirmed: the `HOST_MARKERS` tuple matches the PRD's exact eight names and order, declared next to `LAUNCH_ENV`; `child_env(env) -> tuple[dict, list[str]]` is pure, does not mutate its input, keeps `AUTOPILOT_DISPATCH_DEPTH`, and returns the sorted dropped-name list; `spawn()` calls `child_env` and prints the exact notice format to stderr before `Popen`, silent when the list is empty; `loop.py`'s `_run_agoge_process` calls `runner.child_env(env)[0]` at line 358, with `rg -n 'runner.LAUNCH_ENV' cli/loop.py` returning nothing and `rg -n 'child_env' cli/loop.py` returning exactly one hit; `rg -n 'LAUNCH_ENV' skills/run-autopilot/cli --glob '!test_*'` lists only `runner.py`. All five named acceptance tests exist and pass; the full `test_runner.py` + `test_loop.py` suite is 90 passed. `host-markers.md` carries the "Scrubbed at loop spawn" paragraph naming `runner.HOST_MARKERS` and the depth exception; `CHANGELOG.md` carries the `### Fixed` entry under `[Unreleased]`. He ran `bash dev/bin/release-checks` end to end (the Phase 2 exit criterion) — all sub-suites passed, including the codex/gemini/sonnet runner-recursion-guard scripts that exercise the very `CODEX_SESSION_ID` / `COPILOT_CLI` refusal paths this scrub feeds. He traced each implementing commit and found every diff minimal, mapped 1:1 to a PRD phase task, with no unrelated changes, no new imports, and no new external dependencies.

Rubric verdicts:

```
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
```

## Bob (doubt + de-slop lens, codex, static-only sandbox)

Three 🟡 Medium findings and one ⚪ Low, all listed above. Two of the three Mediums are de-slop calls on the new tests (a single-marker scrub assertion that under-tests the sorted comma-space rendering, and a redundant `isinstance` assertion beside an exact-tuple-equality check). The third is the `child_env(env)[0]` readability call that Alice independently raised.

Consensus rubric verdicts:

```
R1: fail
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
```

R1 fails on his single-marker-test finding: he holds that the sorted multi-marker rendering of the notice is new behavior the tests do not cover.

Doubt rubric verdicts:

```
D1: pass
D2: pass
D3: pass
D4: pass
D5: pass
```

## Carl (frontend & design specialist, gemini via copilot, model gemini-3.8-flash)

No issues found. This diff has no frontend surface, so Carl reviewed it as a generalist against the shared checklist. He read the full context and diff, `runner.py`, `loop.py`, both test files, `host-markers.md` and `CHANGELOG.md`; ran the runner and loop test selections, `test_run_agoge_scrubs_host_markers`, both full test files, and `bash dev/bin/release-checks` both with and without the parent host markers unset; ran every one of the PRD's `rg` acceptance commands; and checked the added lines for trailing whitespace, debug markers and TODOs, finding none.

```
[CARL] ✅ No issues found
```

Rubric verdicts:

```
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
```

Verdict: 7 findings
Tests: 971 passed, 0 failed, 0 skipped (reused from last-verification.json at 407c1e87458bde2291cb03c2b10f977c54e73ac1)
