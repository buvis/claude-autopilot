---
prd: dev/local/prds/wip/00223-enter-the-build-gate-in-one-cli-call-v1.md
review: 1
date: 2026-09-29
head_sha: 20b4b0205d11c2cd252e10abd9458dad5ea554d0
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00223-enter-the-build-gate-in-one-cli-call-v1

Diff range: `2a64f20e0c88647e1791bcc107801c6c3ce176a2..20b4b0205d11c2cd252e10abd9458dad5ea554d0`

codex_rung_guard: not fired

pack: failed (engram exited 1: "not inside a registered repo; register it in /Users/bob/.config/gita/repos.csv"). Every prompt that takes `{PACK_FILE}` / `{PACK_FINDINGS}` received the sentinel `(no pack available this cycle)`. The review is degraded on retrieval context, not invalid.

Scope note: this is a FULL cycle-1 review. `gather-context.sh` was given `--since <work_start_sha>` so the diff is exactly the PRD's work range; the script's own "incremental review" label in the context file is an artifact of that flag, not a rework scope. `origin/master` is 101 commits behind HEAD, so the script's default base would have pulled in six other PRDs.

carl: ran on backend `copilot`, model `gemini-3.8-flash`.

## Review Summary

Reviewed: 3 completed tasks
PRDs checked: 00223-enter-the-build-gate-in-one-cli-call-v1

### Agent Status

- Alice: ✅ Available (Claude subagent, consensus lens)
- Blake: ✅ Available (Claude subagent, blind/PRD-only lens)
- Bob: ✅ Available (codex, doubt + de-slop lens; `--emit-thread-id` produced an empty sidecar, so no `codex_thread_id` is stamped and cycle 2 runs him fresh)
- Carl: ✅ Available (gemini via copilot, frontend/design specialist running as a generalist here)

## Consolidated Findings

35 findings. 0 🔴 Critical, 6 🟠 High, 20 🟡 Medium, 9 ⚪ Low.

`consolidate_findings.py` merged three clusters on file match after `:line` suffix stripping (rows 1, 2 and 5), so the top row folds several distinct `enter.py` failure modes into one entry. The follow-up tasks below split them back out.

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [4/4] | 🟠 | A failed backlog move escapes as a traceback instead of the `mv_verify` stop; the same gap exists at `_design`'s `doc.read_text`, at `_select`'s `statectl.mutate` skip write, and at the `_stall_stop` `pause_reason` write. Each ends in exit 1 with no JSON line, so the skill has no stop to dispatch on | skills/run-autopilot/cli/enter.py:211 | 1 | ALICE, BLAKE, BOB, CARL |
| [3/4] | 🟠 | The null-stop and exit-code paths drop obligations the replaced prose carried: the STALLED banner on a non-null `parked`, the loop-mode `custody: <n> entries await an attended resume` line, the meaning of a non-zero exit (2 corrupted state, 6 future schema), and Normal PRD selection's Active Work capsule read | skills/run-autopilot/references/phase-build.md:20 | 3 | ALICE, BLAKE, BOB |
| [3/4] | 🟡 | `test_enter_decisions.py` is not wired into `dev/bin/release-checks`, so a red decisions test never blocks a release | dev/bin/release-checks:138 | 3 | ALICE, BLAKE, BOB |
| [2/4] | 🟠 | `enter` silently discards every frontmatter warning; `enter.py:242` binds `_warnings` and never uses it, and the prose still promises "warns naming the field". A typo such as `design: skpi` defaults to `run` with no signal | skills/run-autopilot/cli/enter.py:242 | 1 | ALICE, BLAKE |
| [2/4] | 🟡 | `selection.select_eligible` and `frontmatter.apply` are new copies used only by enter; `autopilot select` and `autopilot frontmatter` keep their inline logic, so the verbs can drift. The `selection.py` docstring's "shared by" claim is false | skills/run-autopilot/cli/selection.py:11 | general | BLAKE, BOB |
| [1/4] | 🟠 | The lift was only half done: `_run_select`, `_run_frontmatter`, `_lane_fields`, `_listdir`, `_prd_text` and `_project_root` still carry their own copies, and the copies already differ (`_project_root(prds_dir)` vs `custody.project_root(autopilot_dir)` under `--prds`). The design's rejected Alternative 3 is the shipped state | skills/run-autopilot/cli/__main__.py:594 | 1 | ALICE |
| [1/4] | 🟠 | Three rows of the stop table route to the wrong owner (`park_precondition_failed`, `stall_op_malformed`, `deferred_io`), which is the PRD's own stated risk. `test_every_stop_value_has_a_row` cannot catch it | skills/run-autopilot/references/phase-build.md:34 | 3 | ALICE |
| [1/4] | 🟠 | `--prd` accepts absolute paths and traversal instead of a basename, letting `enter` reach a file outside `wip/` or `backlog/` (also raised by ALICE 🟡, CARL 🟠 and BLAKE ⚪) | skills/run-autopilot/cli/enter.py:184 | 1 | BOB |
| [1/4] | 🟡 | `batch_init` re-entry is ambiguous for a partial batch: an id-less `state.batch = {"skips": [...]}` reports `absent` while the prose calls it present | skills/run-autopilot/references/phase-build.md:42 | 3 | ALICE |
| [1/4] | 🟡 | Commit 912da43's naive/future-stamp fix shipped without a regression test; the real `_git_head_sha` is never executed; `--prds` is untested | skills/run-autopilot/cli/enter.py:253 | 1 | ALICE |
| [1/4] | 🟡 | The design's drift guard tying `enter._DISPATCH_RE` to the pinned `awk` regex was never written | skills/run-autopilot/cli/test_enter_prose.py:112 | 3 | ALICE |
| [1/4] | 🟡 | Simplification: `enter.py` mutates `sys.path` at import time and uses `importlib` to read the marker tuple; `cli/handoff.MARKERS` is the documented source | skills/run-autopilot/cli/enter.py:30 | 1 | ALICE |
| [1/4] | 🟡 | The `resume` handoff row is written before the lane check, against the PRD's step order | skills/run-autopilot/cli/enter.py:246 | general | BLAKE |
| [1/4] | 🟡 | Step 2 re-implements `--clear-markers` instead of calling it, losing its per-marker stderr forensics | skills/run-autopilot/cli/enter.py:139 | general | BLAKE |
| [1/4] | 🟡 | Recording skips on a fresh state creates a partial `batch` with no `id`; `test_enter.py:468` blesses the shape | skills/run-autopilot/cli/enter.py:199 | general | BLAKE |
| [1/4] | 🟡 | Scope creep beyond the PRD: five extra `stop` values, a state bootstrap, a stall_op precheck, `--prds`, and two files not in the PRD structure | skills/run-autopilot/cli/__main__.py:297 | general | BLAKE |
| [1/4] | 🟡 | `enter()`'s signature differs from the PRD's sketch (keyword-only, two extra params, two extra injectables) | skills/run-autopilot/cli/enter.py:299 | general | BLAKE |
| [1/4] | 🟡 | An unreadable custody entry reuses `stop: "deferred_io"`, whose prose row names only the park-request owner | skills/run-autopilot/cli/enter.py:329 | general | BLAKE |
| [1/4] | 🟡 | `frontmatter.apply()` duplicates the parse, lane and transaction logic still used by `autopilot frontmatter` | skills/run-autopilot/cli/frontmatter.py:165 | 1 | BOB |
| [1/4] | 🟡 | `select_eligible()` duplicates the eligibility loop still used by `autopilot select` | skills/run-autopilot/cli/selection.py:82 | 1 | BOB |
| [1/4] | 🟡 | CLI JSON assertions use `enter()` itself as the expected-value oracle | skills/run-autopilot/cli/test_enter.py:700 | 2 | BOB |
| [1/4] | 🟡 | The stop-table test checks substrings across all rows, so a row can be absent while its token appears elsewhere | skills/run-autopilot/cli/test_enter_prose.py:119 | 3 | BOB |
| [1/4] | 🟡 | An unmapped `do_park` exit code raises `KeyError` in `_park` instead of halting cleanly | skills/run-autopilot/cli/enter.py:159 | 1 | CARL |
| [1/4] | 🟡 | Substring search across markdown table rows in `test_every_stop_value_has_a_row` permits false passes | skills/run-autopilot/cli/test_enter_prose.py:115 | 3 | CARL |
| [1/4] | 🟡 | Redundant condition checks for codes 0 and 5 in `_park` can collapse into a direct branch | skills/run-autopilot/cli/enter.py:150 | 1 | CARL |
| [1/4] | 🟡 | An unreadable existing design doc raises past `enter()` instead of returning a JSON stop | skills/run-autopilot/cli/enter.py:293 | 1 | BOB |
| [1/4] | 🟡 | Uncaught `OSError` on an unreadable design doc in `_design` raises past `enter` | skills/run-autopilot/cli/enter.py:289 | 1 | CARL |
| [1/4] | ⚪ | Marker cleanup drops `_main_clear_markers`'s `cleared inherited <name> written <time>` stderr lines, unmentioned in the prose | skills/run-autopilot/cli/enter.py:139 | 1 | ALICE |
| [1/4] | ⚪ | `test_every_stop_value_has_a_row` matches by substring rather than the row's first cell (Pat's LOW, still open) | skills/run-autopilot/cli/test_enter_prose.py:112 | 3 | ALICE |
| [1/4] | ⚪ | `__main__.py` is now 1289 lines against the 800 limit (1253 before) | skills/run-autopilot/cli/__main__.py:293 | 2 | ALICE |
| [1/4] | ⚪ | `detail` for the park-family stops is a synthetic string, not the executor's message | skills/run-autopilot/cli/enter.py:147 | general | BLAKE |
| [1/4] | ⚪ | `batch` is null on every stop before step 8, which the PRD's value domain does not list | skills/run-autopilot/cli/enter.py:55 | general | BLAKE |
| [1/4] | ⚪ | Other unguarded file and state operations can traceback instead of stopping, including `prds_dir.parents[1]` IndexError on a shallow `--prds` | skills/run-autopilot/cli/enter.py:293 | general | BLAKE |
| [1/4] | ⚪ | The resume row shells out to `record_dispatch.py`, which resolves the autopilot dir from cwd, not from `state_path` | skills/run-autopilot/cli/enter.py:91 | general | BLAKE |
| [1/4] | ⚪ | `--prd` is not validated as a basename | skills/run-autopilot/cli/enter.py:186 | general | BLAKE |
| [1/4] | ⚪ | `test_every_stop_value_has_a_row` matches stops by bare substring; a stop named `plan` is satisfied by `replan` | skills/run-autopilot/cli/test_enter_prose.py:119 | general | BLAKE |
| [1/4] | ⚪ | The "Enter in one call" section says nothing about non-zero exits (1, 2, 6) or a traceback | skills/run-autopilot/references/phase-build.md:14 | general | BLAKE |
| [1/4] | ⚪ | The null-stop path's pointer claims enter runs "these steps", but it cannot do step 6 (the Active Work capsule read) | skills/run-autopilot/references/phase-build.md:164 | general | BLAKE |
| [1/4] | ⚪ | `python3` is hardcoded instead of `sys.executable` for the `record_dispatch.py` subprocess | skills/run-autopilot/cli/enter.py:96 | 1 | CARL |
| [1/4] | ⚪ | Cannot statically verify: tests and release checks pass | N/A | general | BOB |

### Mechanical checks (computed)

- Tautological test shapes: 57 test functions checked across 3 files, **no `[MECH]` findings**.
- Fail-first replay against `2a64f20e0c88`: 0 touched tests ran, **3 test files could not be collected at base** (they import `cli.enter`, which does not exist there) — i.e. none of the new tests passes against the pre-change code. No `[MECH]` findings.
- Function/file line counts were taken from the computed facts block; `enter.py`'s largest function is `enter` at 48 lines (under the 50 limit) and the file is 346 lines (under 400). `__main__.py` at 1289 lines is the only 800-limit breach, and it is pre-existing.

## Alice

15 findings, above. Alice answered the by-path hazard the carried context asked about: she found **no other by-path consumer at risk** — only `frontmatter.py` and `lane.py` are loaded by path (`fast-track/scripts/cards_from_prd.py:51-52`), `lane.py` is unchanged, and `frontmatter.py` is fixed by the deferred import at 20b4b02. `selection.py`'s new `from cli import eligibility` and `eligibility.py`'s `from cli import frontmatter` are only reached through the `cli` package. She ran the 144-test enter/doc-contract suite and a 330-test fast-track/lifecycle/lane/eligibility/triage suite, both green; she did not run the full `dev/bin/release-checks`.

R1: fail
R2: pass
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

## Blake

18 findings, above, from the PRD alone. Verification he ran: all `skills/run-autopilot/cli` tests plus `test_walk_up.py` and `test_autopilot_lifecycle.py` pass (1854 passed); `dev/bin/release-checks` completes green (its enter block ran 96 tests); the three enter test files alone run 106 passed.

Blake's B-rubric fails are dominated by deviations from the PRD sketch that the design doc (which he never sees, by construction) explicitly approved — see the settled-decisions ledger, where six of them are recorded as discards with their reasons.

B1: fail
B2: fail
B3: fail
B4: pass
B5: fail
B6: fail
B7: fail
B8: pass
B9: pass
B10: pass
B11: pass
B12: pass
B13: pass
B14: fail
B15: pass
B16: pass
B17: pass
B18: pass
B19: pass

## Bob

11 findings, above, carrying the doubt + de-slop lens.

R1: fail
R2: fail
R3: pass
R4: fail
R6: pass
R7: fail
R8: pass
R9: fail
R10: fail
R11: pass
R12: pass
R13: fail

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

FIX / VERIFY / KNOWN buckets:

```
FIX:
- `--prd` can escape the PRD directories — skills/run-autopilot/cli/enter.py:184 — reject absolute paths, separators, and non-basename arguments before filesystem access.
- Move errors bypass the JSON contract — skills/run-autopilot/cli/enter.py:211 — catch move errors and return `mv_verify` with the error in `detail`.
- Unreadable design docs bypass the JSON contract — skills/run-autopilot/cli/enter.py:293 — catch the read error and return an explicit stop.
- The capsule read is skipped on a null stop — skills/run-autopilot/references/phase-build.md:20 — retain an instruction to read Active Work before proceeding to Phase 1.
- Selection logic remains duplicated — skills/run-autopilot/cli/selection.py:82 — have `_run_select` call `select_eligible()`.
- Frontmatter logic remains duplicated — skills/run-autopilot/cli/frontmatter.py:165 — have `_run_frontmatter` call `apply()`.
- Decision tests are absent from release checks — dev/bin/release-checks:138 — add `test_enter_decisions.py` to the enter test invocation.
- CLI tests use the implementation as their oracle — skills/run-autopilot/cli/test_enter.py:700 — assert fixed expected values for fixtures with different decisions.
- Stop-table test accepts substring matches — skills/run-autopilot/cli/test_enter_prose.py:119 — parse and compare each row's first cell against `STOPS`.

VERIFY:
- Tests and release checks pass — `bash dev/bin/release-checks`

KNOWN:
- `__main__.py` exceeds 800 lines — a broad split of the pre-existing CLI registry is outside this PRD.
```

Bob's single VERIFY item names an exact runnable command and was queued to `dev/local/reviews/00223-enter-the-build-gate-in-one-cli-call-v1-checks-1.json`.

## Carl

6 findings, above, on backend `copilot` / model `gemini-3.8-flash`.

One artifact worth recording: Carl's first `bash dev/bin/release-checks` run reported `SUMMARY: 6 passed, 20 failed` in the runner-recursion-guard block. That was an environment artifact of running inside a nested dispatch (`AUTOPILOT_DISPATCH_DEPTH` / `COPILOT_CLI` / `_AUTOPILOT_LOOP` set), which makes `codex-run.sh` refuse with "refusing nested dispatch (depth=1)". He re-ran it as `env -u AUTOPILOT_DISPATCH_DEPTH -u COPILOT_CLI -u _AUTOPILOT_LOOP bash dev/bin/release-checks` and it completed green. **Not a finding against the diff**; Blake's independent green run agrees.

R1: pass
R2: pass
R3: pass
R4: pass
R6: pass
R7: fail
R8: pass
R9: pass
R10: pass
R11: pass
R12: pass
R13: pass

## Follow-up Tasks Created

Ten `[D1]` tasks, all at the `opus` tier (the PRD's `default_model: opus` floor). No 🔴 rows exist, so no rework design was run and no task belongs to Phase 6's CRITICAL path.

1. `[D1] Return a JSON stop instead of a traceback for every unguarded enter.py operation` (M) — 🟠 [4/4]
2. `[D1] Validate --prd as a basename so it cannot escape the PRD directories` (S) — 🟠
3. `[D1] Surface frontmatter warnings from enter instead of discarding them` (S) — 🟠 [2/4]
4. `[D1] Fix the stop-table rows that route to the wrong owning section` (S) — 🟠
5. `[D1] Restore the obligations the Enter in one call prose dropped` (M) — 🟠 [3/4]
6. `[D1] Finish the lift so autopilot select and frontmatter call the shared helpers` (L) — 🟠
7. `[D1] Wire test_enter_decisions.py into release-checks` (S) — 🟡 [3/4]
8. `[D1] Strengthen the enter tests: anchor the stop-table rows, drop the self-oracle, cover the untested paths` (L) — 🟡
9. `[D1] Resolve the batch_init partial-batch ambiguity in Normal PRD selection step 3` (S) — 🟡 [2/4]
10. `[D1] Simplify the marker read and the _park branch, and record the lost clear-markers forensics` (S) — 🟡

## Settled decisions (ledger)

Seven discards and one deferral were written to `dev/local/reviews/00223-enter-the-build-gate-in-one-cli-call-v1-ledger.json`. Six of the discards are blind-lens findings contradicted by the design doc and the task contracts Blake cannot see (the resume-row order, the five extra stop values and `--prds`, the `enter()` signature, `batch`'s `|null`, the synthetic `detail`, and `python3` vs `sys.executable`); one is Bob's sandbox "cannot statically verify" statement, which is not a defect. The deferral is `__main__.py` exceeding the 800-line limit — pre-existing, and the PRD explicitly forbids restructuring that file.

Verdict: 35 findings
Tests: 3910 passed, 0 failed, 1 skipped (suite run this cycle: `uv run --no-project --with pytest python -m pytest -q skills hooks --ignore=skills/run-autopilot/scripts/tracon`, plus 1049 subtests passed; `last-verification.json` records exit 0 at this sha but null counts, so it could not be reused. The three `scripts/tracon` test modules were excluded because `rich` is not installed in this environment — a pre-existing gap unrelated to this diff, and they are not part of `dev/bin/release-checks` either.)
