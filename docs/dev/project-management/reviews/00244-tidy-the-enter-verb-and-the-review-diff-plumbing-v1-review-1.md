---
prd: docs/dev/project-management/prds/wip/00244-tidy-the-enter-verb-and-the-review-diff-plumbing-v1.md
review: 1
date: 2026-10-04
head_sha: 8340da79a00196cf273270e9bd2dda19de52d4d6
codex_thread_id: 01a1045e-6977-7383-bbae-b016766abab4
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00244-tidy-the-enter-verb-and-the-review-diff-plumbing-v1

Diff range: `c704212975724ee445dca70ebf3fe6a983508fc8..8340da79a00196cf273270e9bd2dda19de52d4d6`

codex_rung_guard: not fired

pack: failed (`engram pack` exited 1: "not inside a registered repo; register it in
`/Users/bob/.config/gita/repos.csv`"). `{PACK_FILE}` and `{PACK_FINDINGS}` were
substituted with `(no pack available this cycle)` in every prompt that takes
them. Degraded retrieval context, not an invalid review.

gather scope: this is cycle 1, a **full review**, but it was gathered with
`--since c704212975724ee445dca70ebf3fe6a983508fc8` (`state.work_start_sha`)
rather than bare. The installed plugin cache (0.7.0) still carries the
pre-00244 `SKILL.md`, which says to omit `--since` on a full review; this repo
works directly on master, so a bare run would have produced an empty diff —
exactly the 00237 defect this PRD fixes. The range used is the PRD's whole work
range, which is what the doubt lens is specified to review.

## Review Summary

Reviewed: 5 completed tasks (all landed in commit `6e31e89`)
PRDs checked: 00244-tidy-the-enter-verb-and-the-review-diff-plumbing-v1.md

### Agent Status

- Alice (Claude consensus): ✅ Available
- Blake (blind lens, PRD-only): ✅ Available
- Bob (codex, doubt + de-slop lens): ✅ Available
- Carl (Gemini/copilot): ✅ Available
- Eve (Fable doubt lens): ⏸️ Disabled — `doubt_reviewer: codex` and the codex
  doubt-roster guard did not fire (0 codex-implemented tasks), so she is not on
  this cycle's roster.

Consensus engine: `legacy` (single Alice subagent). No workflow run, so no
`consensus_run_id`.

## Consolidated Findings

17 findings. **No 🔴 Critical and no 🟠 High.** Consensus is out of 4 reviewers.

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [3/4] | 🟡 | The rework bullet "`head_sha` absent → fall back to a full review (omit `--since`)" still omits `--since`. Under autopilot at a clean master HEAD, gather-context.sh now exits 3 on that path, so "always passes the PRD's start" is not met. It should also pass `--since <state.work_start_sha>` when that field is set | skills/review-work-completion/SKILL.md:145 | 4 | ALICE, BLAKE, BOB |
| [2/4] | 🟡 | New failure mode in lane-check. `state_path.parents[1]` raises an uncaught `IndexError` when `--state` is a bare relative filename (`Path("state.json").parents` has one element; I reproduced the IndexError). The call sits outside the try block. `autopilot lane-check --state state.json` run from inside the autopilot dir used to work and now gives a traceback. The same pattern already exists at `_store_repo` (__main__.py:1233), and the PRD says to pass "the same argument", so this is a consistency risk, not a deviation. | skills/run-autopilot/cli/__main__.py:671 | Phase 0 | BLAKE, BOB |
| [2/4] | ⚪ | The empty-diff probe buffers the whole diff in `DIFF_CONTENT` just to test emptiness, and the diff then runs twice more (--stat and the file). `git diff --quiet "$DIFF_BASE" ${PATH_ARGS[@]+"${PATH_ARGS[@]}"}` (exit 0 = empty) is simpler. Under the current `2>/dev/null \|\| true`, a failing `git diff` also reads as "empty diff against X", a misleading cause for exit 3. Also, the header comment says "nothing written", but `mkdir -p docs/dev/tmp` runs first | skills/review-work-completion/scripts/gather-context.sh:104 | 3 | ALICE, BLAKE |
| [2/4] | ⚪ | The new regression tests are not wired into the release gate. test_lane_check.py is absent from the "effort lanes" block beside test_lane.py and test_lane_cli.py. test_gather_context_id.sh (which holds the new refusal scenario) is not run anywhere. Only test_gather_context_paths.sh is, at line 194 of release-checks. `release-checks` passes, but it cannot catch a regression in either fix | dev/bin/release-checks:136 | general | ALICE, BLAKE |
| [1/4] | 🟡 | The "--since given, refusal never fires" guard in gather-context.sh is untested. Only a non-empty --since diff is exercised, so deleting `-z "$SINCE_REF" &&` at gather-context.sh:108 leaves every test green. Task 3 Details name the empty-diff-with-`--since` case. Add a scenario: at a clean HEAD run `--since "$(git rev-parse HEAD)"` and assert exit 0 plus an empty diff file | skills/review-work-completion/scripts/test_gather_context_id.sh:60 | 3 | ALICE |
| [1/4] | 🟡 | test_lane_check.py duplicates an existing harness. `_clean_git_env` (test_lane_check.py:30-49) is a copy of test_store_boundary.py:517-536 with only the author name changed. `BareRepo` (test_lane_check.py:52-98) re-implements `Fixture(bare=True)` at test_store_boundary.py:539-585, which has the same `.claude/` store layout. Lift the env helper and fixture into the shared testutil (store_tree_testutil.py) instead of adding a third copy | skills/run-autopilot/cli/test_lane_check.py:30 | 2 | ALICE |
| [1/4] | 🟡 | FIX: The new preflight suppresses Git errors with `2>/dev/null \|\| true`, misreporting failed diffs as empty diffs. Preserve the diagnostic and distinguish command failure from successful empty output. | skills/review-work-completion/scripts/gather-context.sh:106 | 3 | BOB |
| [1/4] | 🟡 | FIX: The preflight materializes the entire patch even with `--since`, when refusal cannot fire, then regenerates it for the artifact. Guard this capture with the existing no-`--since` condition to eliminate unnecessary work without changing behavior. | skills/review-work-completion/scripts/gather-context.sh:104 | 3 | BOB |
| [1/4] | 🟡 | FIX: Bare-store coverage only commits harmless JSON, leaving the security-scan exclusion unpinned. Add a bare-repo case containing a security keyword inside the store alongside an ordinary outside Markdown change; assert no escalation. | skills/run-autopilot/cli/test_lane_check.py:106 | 2 | BOB |
| [1/4] | ⚪ | `store_tree.STORE_EXCLUDE_PATHSPECS` is now unused in production. `lane_check.diff_signal` was its only consumer, and rg finds it only in its own definition, test_store_lane.py:70-84 and a comment at lane_check.py:62. This diff orphaned it. Either drop it with its derivation test, or replace it with a helper that takes (repo, store_dir) and returns the prefixed pathspecs, so the `:(exclude,top)` construction has one home | skills/run-autopilot/cli/store_tree.py:25 | 2 | ALICE |
| [1/4] | ⚪ | An invalid or unreachable `--since` ref (e.g. a `work_start_sha` lost to a rebase) fails `rev-parse --verify`, so DIFF_BASE silently falls back to the branch base. The refusal is skipped because `SINCE_REF` is non-empty. A clean master then yields the same silent empty "full review" this PRD targets. The Task 3 Details literally say the refusal never fires with `--since`. Key the refusal on "no `--since` was applied" (`DIFF_BASE != SINCE_REF`), or fail loudly on an invalid ref | skills/review-work-completion/scripts/gather-context.sh:108 | 3 | ALICE |
| [1/4] | ⚪ | The `park_halt` row's "otherwise the row matching the exit code `detail` names" points at rows that cannot exist. `enter.py` raises `park_halt` only for exit 5 or an unmapped code (enter.py:138-145). The "Handle park request" table has rows only for 3, 0, 5, 4, 9, 10 and 2 (phase-build.md:125-133), and 4, 9, 10 and 2 route to other stop values. A session on an unmapped code (e.g. 7) finds no row. The wording is PRD-verbatim, so this is a PRD defect carried into the prose. A follow-up should say what to do for an unmapped code (e.g. PAUSE) | skills/run-autopilot/references/phase-build.md:30 | 4 | ALICE |
| [1/4] | ⚪ | `__main__.py` is 1344 lines, over the 800-line limit, and this diff adds 4 more at the `diff_signal` call site. This is a settled pre-existing deferral (PRDs 00223, 00236, 00241), and the call-site edit is PRD-mandated. It is noted for R13 only | skills/run-autopilot/cli/__main__.py:667 | 2 | ALICE |
| [1/4] | ⚪ | Style drift: stray space before the comma in `next((r for r in rows if _first_cell(r) == "park_halt") , None)`; the sibling fs_error test has none | skills/run-autopilot/cli/test_enter_prose.py:269 | 4 | ALICE |
| [1/4] | ⚪ | The empty-diff guard keys on `-z "$SINCE_REF"`, not on whether `--since` took effect. An unresolvable `--since <ref>` silently falls back to the base branch (gather-context.sh:78-81). At a clean master HEAD that gives an empty diff and exit 0, which is still a silently empty review. The guard also requires a non-empty `DIFF_BASE`, so a repo with no detectable base (for example a `main` branch with no origin) still prints "_No base branch found for diff_" and exits 0. Both match the PRD's literal wording ("no `--since` was given", "against <base>"), but the capability title says "never silently empty". | skills/review-work-completion/scripts/gather-context.sh:108 | Phase 0 | BLAKE |
| [1/4] | ⚪ | KNOWN: `__main__.py` exceeds the 800-line ceiling. This predates the change; splitting the CLI dispatcher is outside this PRD's narrowly scoped plumbing fixes. | skills/run-autopilot/cli/__main__.py:1344 | general | BOB |
| [1/4] | ⚪ | Cannot statically verify: acceptance suites pass (VERIFY: run `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli -k "enter or lane_check"`, `bash skills/review-work-completion/scripts/test_gather_context_id.sh`, and `bash dev/bin/release-checks`). | N/A | general | BOB |

Consolidation notes from `consolidate_findings.py`:

- row 3 merged citations that matched only after suffix stripping:
  `gather-context.sh:104 ~ gather-context.sh:42`
- row 4 merged citations that matched only after suffix stripping:
  `dev/bin/release-checks:136 ~ dev/bin/release-checks:194`

### Carry-forward and mechanical checks

- **Previous-cycle failed checks:** none — this is cycle 1, there is no
  `-checks-0.json`.
- **Tautological test shapes:** the computed block found **no `[MECH]` lines**
  across 91 test functions in 4 changed test files.
- **Fail-first replay:** 2 touched tests ran against base
  `c70421297572`, **2 failed there, 0 passed** — both new tests pin the change.
  3 test files could not be collected at base (they import `cli.enter_io`,
  which does not exist there, or are new), reported as "could not be collected"
  rather than as passes.

## Alice (consensus lens)

Ten findings, listed in the table above (2 🟡, 8 ⚪). Her own verification:
`bash dev/bin/release-checks` exits 0; `test_lane_check`, `test_enter*` and
`test_store_lane` give 173 passed; `test_gather_context_id.sh` gives 4 PASS;
`enter.py` is 370 lines (under the PRD's 400).

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
R13: fail
```

## Blake (blind lens — PRD only, found the code himself)

Five findings (1 🟡, 4 ⚪), listed in the table above. He confirmed every PRD
output against the code: `enter_io.py` exports the three renamed helpers and
`enter.py` imports them; the `fs_error` and `park_halt` rows match the PRD text
verbatim and their prose tests pass; `diff_signal` builds the prefixed
`:(exclude,top)` pathspec from `store_tree._store_prefix`; both CHANGELOG lines
are under `[Unreleased]`; `rg -c -- "--since <state.work_start_sha>"` on
SKILL.md is at least 1.

He verified by running: `pytest -k "enter or lane_check"` (209 passed),
`test_gather_context_id.sh` (4/4 PASS), `release-checks` (ran to the final
section with no failure; he did not capture the exit code — this session did,
and it is 0), `wc -l` (enter.py 370, enter_io.py 73).

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

## Bob (codex — doubt + de-slop lens)

Seven findings (5 🟡 FIX, 1 ⚪ KNOWN, 1 ⚪ cannot-statically-verify), listed in
the table above. Static analysis only, per his sandbox.

```
R1: fail
R2: pass
R3: pass
R4: fail
R6: pass
R7: pass
R8: pass
R9: fail
R10: fail
R11: pass
R13: fail
R12: pass
D1: pass
D2: pass
D3: pass
D4: pass
D5: pass
```

(Bob's own order; `R12`/`R13` are transcribed as he emitted them.)

## Carl (Gemini/copilot — frontend & design specialist, generalist here)

```
[CARL] ✅ No issues found
```

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

Backend note: Carl ran on copilot. His **first** `release-checks` invocation
reported `SUMMARY: 6 passed, 20 failed` in the runner-recursion-guard section —
that failure was caused by the dispatch-guard environment he inherited
(`AUTOPILOT_DISPATCH_DEPTH`, `COPILOT_CLI`, `CODEX_SESSION_ID`,
`_AUTOPILOT_LOOP`), which makes `codex-run.sh` refuse with exit 3. He re-ran
with `env -u` for those four and reached his clean verdict. This session's own
`release-checks` run, outside that environment, exited 0. The first run is a
harness artifact, not a finding.

## Follow-up tasks

**None created in this step.** The cycle carries no 🔴 and no 🟠, so it meets
the convergence test, and on a converged cycle the Medium/Low tail is owned by
the Phase 5 **Tail sweep** (`run-autopilot/references/phase-review.md`), which
builds exactly ONE `[D1] Tail sweep` task carrying every swept finding verbatim
and appends its id to `state.rework_task_ids`. Creating per-finding tasks here
as well would both duplicate that task and orphan these ones, since a converged
cycle's `/autopilot:work` pass runs only the ids in `rework_task_ids`.

## Verification-check queue

**Not written this cycle.** The queue is fed from the VERIFY bucket of a doubt
lens that emits one — Eve, or whichever lane stands in for her
(`references/output-formats.md` § Verification-check queue). Eve is off the
roster this cycle, and `"bob"` is explicitly reserved as a `source` value, so
there is no eligible bucket. Bob's one VERIFY-shaped item names three exact
commands, and all three were run during this cycle anyway:

- `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli -k "enter or lane_check"` → 209 passed (Blake)
- `bash skills/review-work-completion/scripts/test_gather_context_id.sh` → 4/4 PASS (Blake)
- `bash dev/bin/release-checks` → exit 0, 2268 passed (this session)

Not queued: no eligible doubt-lens source. The evidence above is the record.

Verdict: 17 findings
Tests: 2268 passed, 0 failed, 0 skipped (suite run this cycle)

Tests line provenance: `docs/dev/project-management/autopilot/last-verification.json`
records sha `cb9be6b068f391820aeccf71b0524590830a3a78`, which is **not** this
cycle's reviewed HEAD, so the record was not reused. `bash dev/bin/release-checks`
was run once in the foreground this cycle: **exit 0**. The count sums the 22
pytest summary lines (2152 passed) and the 4 bash-suite `SUMMARY:` lines (116
passed, 0 failed). One further bash suite (`gather-context paths`, 8 `PASS:`
assertions) prints no `SUMMARY:` line and is therefore not in the total; it
reported no failures. No test was skipped or xfailed anywhere in the run.
