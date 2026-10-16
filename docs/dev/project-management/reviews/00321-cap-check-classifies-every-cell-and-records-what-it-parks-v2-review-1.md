# Review: 00321-cap-check-classifies-every-cell-and-records-what-it-parks-v2 (cycle 1)

prd: 00321-cap-check-classifies-every-cell-and-records-what-it-parks-v2.md
cycle: 1
date: 2026-10-16
head_sha: 3c2d045a47800b10b6d42db1bfc370cef2a004af
reviewers: alice,blake,bob,carl
codex_thread_id: 01a145ec-2af6-7d42-8da6-d418db48e5a4

Diff range: de92b534336167bdeac5f4e5f192fb8058b9bf35..3c2d045a47800b10b6d42db1bfc370cef2a004af

codex_rung_guard: not fired

pack: failed (engram pack exit 1: sqlite3.OperationalError: attempt to write a readonly database)
bob: produced output after one retry with an inlined prompt (first run refused: `sandbox_apply: Operation not permitted`)

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [2/4] | 🟡 | A path that exists in the work tree but not at `head` is read as a git failure, not as "unresolved". `git cat-file -e <sha>:new.py` answers `fatal: path 'new.py' exists on disk, but not in '<sha>'`. I reproduced this in a scratch repo. That message contains neither "does not exist" nor "no such path", so `_missing_path_error` is False and `_file_exists_at` re-raises. The verb then exits 2 instead of printing `regression: null` and exiting 1. This hits an untracked file, a file a later commit added, or an absolute path outside the repo. The PRD says an unresolvable path yields `null` with a `reason`. The loop still stalls, via retry and then `sub_skill_fail`, but the row never gets its `reason` or its `cap_regression` stall. Fix: also treat "exists on disk, but not in" as a missing path, and add a test. | skills/run-autopilot/cli/cap_check.py:176 | 2 | ALICE, BLAKE |
| R2 | [2/4] | 🟡 | Other docs still describe the old behavior. `state-schema.md:510` says the `cap_critical` stall alone migrates every pending deferral and that a `cap_regression` `detail` carries "refs and commits". It does not mention the null-row `ref + reason` form. `phase-done.md:31` and the `cap_critical` branch of `phase-review.md:59` say `mint-stubs` mints only for "CRITICAL/HIGH or `cap_critical` rows", but it now also mints for `cap_regression` stall rows. | skills/run-autopilot/references/state-schema.md:510 | 3 | ALICE, BLAKE |
| R3 | [1/4] | 🟠 | `_verify_range` compares the two head_sha values as raw strings, so an upper-case and a lower-case spelling of the same commit pass the "differ" check. `merge-base --is-ancestor X X` also succeeds. I confirmed `_verify_range('.', h.upper(), h.lower())` returns None. `rev-list prev..head` is then empty, every row classifies `regression: false`, and the verb exits 0 and defers. That is the fail-open the spec's range proof exists to prevent. Fix by lower-casing both shas, or by comparing the resolved `rev-parse` output. | skills/run-autopilot/cli/cap_check.py:161 | 2 | BLAKE |
| R4 | [1/4] | 🟠 | Equal commits with differently cased SHA strings bypass the empty-range guard: both resolve successfully, but string equality fails, allowing an empty range to classify rows as non-regressions | skills/run-autopilot/cli/cap_check.py:161 | 2 | BOB |
| R5 | [1/4] | 🟡 | Two new behaviors have no test. (a) `_verify_range` has an "unresolvable 40-hex sha" branch ("does not resolve to a commit", cap_check.py:161), which the PRD's Must-have list names. The tests cover only equal, reversed, off-HEAD, abbreviated and branch-named shas, so nothing sends a well-formed sha for a nonexistent commit. (b) `_migrate_stall_deferrals` has no test for its exit-9 failure path. It also has no test that a retry with the same `op_id` does not write the records twice, which its docstring claims. The only migration test is the success case. | skills/run-autopilot/cli/test_cap_check.py:523 | 1 | ALICE |
| R6 | [1/4] | 🟡 | A range followed by a comma list blames only the first line. `a.py:3-5,9` parses to `[3]`, and `a.py:3,9` also gives `[3]`. The "comma list yields its first line only" rule is carried over from the old parser. The new range handling makes it a trap, because lines 4, 5 and 9 are silently skipped and the row can read `regression: false`, which defers. Either blame every listed line or send such cells to the unresolved path. | skills/run-autopilot/cli/cap_check.py:103 | 2 | ALICE |
| R7 | [1/4] | 🟡 | `do_stall` migrates pending deferrals differently from the contract. (a) The contract names `_migrate_pending_deferrals(autopilot_dir, current, prd)` gated on both `CUSTODY_SITE` and `REGRESSION_SITE`. The code has `_migrate_stall_deferrals(..., op_id)` gated on `REGRESSION_SITE` only (records.py:420 and 496). It reuses `custody.migration_records`. The cap_critical path already migrates inside `custody.record_critical`, so the narrower gate is sound and avoids a double write. But the design doc and the code now disagree, and the PRD's "no op_id on migrated records" line disagrees with its own Solution text. (b) The contract also required updating the `do_stall` docstring exit-code table for `REGRESSION_SITE`. That edit is missing (records.py:548). I suggest recording the deviation in the design doc and adding the docstring note. | skills/run-autopilot/cli/records.py:420 | 3 | ALICE |
| R8 | [1/4] | 🟡 | A `cap_regression` stall mints a stub for the stall row, and `triage._severity` hard-codes that stub as `severity: critical` (triage.py:290-292). Regressions here are HIGH or below, so the stub overstates severity. The migrated `cap-overflow` high rows also qualify, so `mint-stubs` mints one stub for the stall plus one per open high row. The spec says "one stub titled from the stall detail", and phase-review.md:59 describes N+1 stubs. The test only covers a lone stall row. | skills/run-autopilot/cli/triage.py:290 | 3 | BLAKE |
| R9 | [1/4] | 🟡 | `_COLON_L_RE` rejects the contracted `a.py:L 4` form because whitespace is accepted before `L` instead of after it; a resolvable regression becomes an unresolved-path verdict | skills/run-autopilot/cli/cap_check.py:27 | 2 | BOB |
| R10 | [1/4] | ⚪ | `skills/review-work-completion/references/output-formats.md:256` and `review-coverage-format.md:12` still tell reviewers to write `head_sha: <git HEAD sha>`. `cap-check` now rejects anything but a full 40-hex sha with exit 2. The spec should say "full 40-hex `git rev-parse HEAD`". | skills/review-work-completion/references/output-formats.md:256 | 2 | ALICE |
| R11 | [1/4] | ⚪ | `_assert_exit_2_naming` accepts any one of several words (`any(word in stderr)`), for example "equal", "same", "identical" or "differ". That is an either-or hedge and could pass on an unrelated message. Pin the one wording that `_verify_range` emits. | skills/run-autopilot/cli/test_cap_check.py:517 | 1 | ALICE |
| R12 | [1/4] | ⚪ | `__main__.py` is about 1970 lines, over the 800-line limit. The diff changes one line and adds nothing, so I am not counting it against the diff. | skills/run-autopilot/cli/__main__.py:907 | 2 | ALICE |
| R13 | [1/4] | ⚪ | `classify_findings` returns `[]` (exit 0, deferral) when `--previous` names a file that does not exist (cap_check.py:303-306). This behaviour predates PRD 00321. It is fail-open for a mistyped path, and it is not what "fail toward stalling" intends. | skills/run-autopilot/cli/cap_check.py:303 | 2 | BLAKE |
| R14 | [1/4] | ⚪ | Cannot statically verify: the 00310 review-pair command exits 1 and attributes R5 and R6 to `8b3a58f2` | N/A | 2 | BOB |

Consolidator note: row R1 merged citations that matched only after suffix stripping
(cap_check.py:176 ~ :247 ~ :243 ~ :109 ~ :181 — unbounded range expansion, per-line
blame cost, directory cells, and stderr-only missing-path matching all fold into it).

## Alice

Ran the four acceptance test files: 100 passed. The 00310 review pair exits 1 with R5 and R6
reading `"regression": true` at commit 8b3a58f2. Findings R1, R2, R5, R6, R7, R10, R11, R12 above.

R1: fail
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

Blind (PRD-only) lens. No Critical issues. Ran the four named test files: 100 passed; all 18 named
tests exist. The Phase 1 acceptance command on the 00310 review pair exits 1 and classifies R5 and R6
as regressions from 8b3a58f2. CHANGELOG.md has two cap-check entries under `[Unreleased]`. The
nice-to-have (`autopilot render report` printing `stalled: cap_regression`, pinned by a test) is not
implemented. Findings R1, R2, R3, R8, R13 above.

B1: fail
B2: pass
B3: pass
B4: pass
B5: fail
B6: pass
B7: pass
B8: pass
B9: pass
B10: fail
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

Doubt + de-slop lens (codex), after one retry (inlined). Findings R4, R9, R14 above.

FIX:
- Equivalent SHA spellings bypass range equality — skills/run-autopilot/cli/cap_check.py:161 — Compare canonical resolved commit IDs; add a regression test using lowercase and uppercase spellings of the same SHA.
- Colon-L parsing rejects whitespace after L — skills/run-autopilot/cli/cap_check.py:27 — Allow whitespace between `[Ll]` and the line number; test `a.py:L 4` against the fixture's expected regression commit.

VERIFY:
- Real review-pair attribution — Run `python3 skills/run-autopilot/cli/__main__.py cap-check --review-file docs/dev/project-management/reviews/00310-park-cap-regressions-v1-review-2.md --previous docs/dev/project-management/reviews/00310-park-cap-regressions-v1-review-1.md`; confirm exit 1 and R5/R6 both report regression true with commit `8b3a58f2`.

KNOWN:
- (none)

R1: fail
R2: pass
R3: pass
R4: pass
R6: pass
R7: fail
R8: pass
R9: fail
R10: pass
R11: pass
R12: pass
R13: fail

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

Backend: copilot. No issues found.

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

Verdict: 14 findings
Tests: 7002 passed, 0 failed, 3 skipped (suite run this cycle)
