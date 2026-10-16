# Review: 00321-cap-check-classifies-every-cell-and-records-what-it-parks-v2 (cycle 2)

prd: 00321-cap-check-classifies-every-cell-and-records-what-it-parks-v2.md
cycle: 2
date: 2026-10-16
head_sha: 8804f40e8d14e668fcf07a0f1dfc3b0b216a00d0
reviewers: alice,blake,bob,carl
codex_thread_id: 01a14618-3e2e-7d72-be96-d380177027b8

Diff range: 3c2d045a47800b10b6d42db1bfc370cef2a004af..8804f40e8d14e668fcf07a0f1dfc3b0b216a00d0 (incremental: rework since cycle 1)

codex_rung_guard: not fired

pack: failed (engram pack exit 1: sqlite3.OperationalError: attempt to write a readonly database)
bob: produced output after one retry (inlined) — the first run refused with `sandbox_apply: Operation not permitted`

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [3/4] | 🟡 | `state-schema.md` now says the `cap_regression` stall migrates pending deferrals "under `op_id`-less records since only the stall record itself is deduped". That is false. `_migrate_stall_deferrals` calls `custody.migration_records` (`skills/run-autopilot/cli/custody.py:305`), which keys each record `<op_id>-dd<i>`. The new `test_cap_regression_migration_dedupes_on_retry` relies on that, and `phase-review.md:59` and `recovery.md` say `<op_id>-dd<i>` too. The same sentence also says "exactly as `cap_critical` does", yet it describes a different record shape. Fix by replacing the clause with "under `op_id: "<op_id>-dd<i>"`, deduped on retry". | skills/run-autopilot/references/state-schema.md:510 | 5 | ALICE, BLAKE, BOB |
| R2 | [2/4] | 🟡 | The `do_stall` docstring edit grew `do_stall` from about 46 to 56 lines (mech block: `do_stall` line 536, 56 lines). That breaks the 50-line limit, and this diff introduced the breach. The new paragraph repeats the comment already at `skills/run-autopilot/cli/records.py:493-495` and the `_migrate_stall_deferrals` docstring. Behaviour-preserving fix: cut the paragraph to one or two sentences, for example "`site == triage.REGRESSION_SITE` also migrates pending `deferred_decisions` (step 4a, via `_write_stall_records`), writing no custody marker", or move the detail into `_write_stall_records`. | skills/run-autopilot/cli/records.py:546 | 6 | ALICE, BOB |
| R3 | [2/4] | 🟡 | This is a residual case of R1. The "exists on disk, but not in" fix covers an untracked file or an absolute path outside the repo. A relative cell that escapes the repo, such as `../x.py`, still takes the exit-2 path instead of `regression: null`. I confirmed that git answers `fatal: '../x.py' is outside repository at '<root>'`, which none of the `_missing_path_error` substrings match, so `_file_exists_at` re-raises. `_normalise_path` only normalises such a path with `posixpath.normpath` and leaves it as `../x.py`. The loop still stalls through retry and `sub_skill_fail`, but the row gets no `reason`. Either add "is outside repository" to the missing-path matches and test it, or send a path starting with `..` to the unresolved verdict before calling git. | skills/run-autopilot/cli/cap_check.py:128 | 2 | ALICE, BLAKE |
| R4 | [1/4] | 🟡 | Medium: A backtick-wrapped name followed by a line spec is not parsed. `_clean_segment` strips backticks only at the segment edges, so `` `a.py`:4 `` leaves a trailing backtick and the row comes back `regression: null` with `reason: unresolved path a.py```. A fixture with a rework-added line 4 should classify this as a regression. The spec says to "strip backticks" and lists the backtick shape among the cells that must classify. The verb still exits 1, so it fails safe, but the `detail` is wrong and the shape is not parsed. The same applies to `` a.py:4 `b.py` ``. | skills/run-autopilot/cli/cap_check.py:112 | 1 | BLAKE |
| R5 | [1/4] | 🟡 | Medium: A directory File cell fails open. A cell like `skills/run-autopilot/cli/` resolves at head (cat-file -e succeeds on a tree). It is never in `changed_files`, which holds file names only. With no line spec, `_pair_commit` therefore returns None and the row is `regression: false`, so the finding is deferred even when the rework touched files under that directory. This is the "classifier fails toward not a regression" behaviour the PRD set out to remove. | skills/run-autopilot/cli/cap_check.py:261 | 1 | BLAKE |
| R6 | [1/4] | 🟡 | `_FILE_LINE_RE` accepts `a.py:1-2-3`, but `_parse_number_list` then calls `int("2-3")`, raising an uncaught ValueError instead of CapCheckError. Validate comma-separated tokens as individual numbers or single ranges. | skills/run-autopilot/cli/cap_check.py:91 | 4 | BOB |
| R7 | [1/4] | 🟡 | 3 touched test(s) pass against the pre-change code: test_unresolvable_full_sha_raises_naming_does_not_resolve, test_equal_or_reversed_head_shas_exit_2, test_ref_name_head_sha_exits_2 | skills/run-autopilot/cli/test_cap_check.py | general | mech-check |
| R8 | [1/4] | 🟡 | 2 touched test(s) pass against the pre-change code: test_cap_regression_migration_dedupes_on_retry, test_cap_regression_migration_failure_exits_9 | skills/run-autopilot/cli/test_records_stall.py | general | mech-check |
| R9 | [1/4] | 🟡 | Carried forward from cycle 1: the queued verification check never ran (`result: null` in `-checks-1.json`) — `python3 skills/run-autopilot/cli/__main__.py cap-check --review-file docs/dev/project-management/reviews/00310-park-cap-regressions-v1-review-2.md --previous docs/dev/project-management/reviews/00310-park-cap-regressions-v1-review-1.md`. It proves the PRD's headline success criterion (the 00310 pair classifies R5/R6 as regressions and the verb exits 1). Blake's independent probe reports exit 1 with both rows `regression: true, commit: 8b3a58f2`, but the queued check itself has no recorded result. | skills/run-autopilot/cli/cap_check.py | general | verify-check |
| R10 | [1/4] | ⚪ | `test_case_variant_equal_head_shas_are_treated_as_equal` only asserts `pytest.raises(CapCheckError)`. If git stopped resolving upper-case shas, it would pass on "does not resolve to a commit" instead of the equality guard. Add `match="equal"`. | skills/run-autopilot/cli/test_cap_check.py:688 | 7 | ALICE |
| R11 | [1/4] | ⚪ | The design doc (PRD Interfaces & contracts) still names `_migrate_pending_deferrals`, gated on both sites with no `op_id`. The code has `_migrate_stall_deferrals(..., op_id)`, gated on `REGRESSION_SITE` only, which avoids a double write with `custody.record_critical`. The code side is now documented, but the PRD text was not reconciled. This is a documentation note only. | N/A | 6 | ALICE |
| R12 | [1/4] | ⚪ | Low: The `_parse_file_cell` docstring says a comma list yields "only its first" line, "as before". The code blames every line (`_parse_number_list` returns all of them and `_pair_commit` iterates them). The docstring is wrong. | skills/run-autopilot/cli/cap_check.py:148 | 1 | BLAKE |
| R13 | [1/4] | ⚪ | Low: `_severity` now labels a `cap_regression` stall stub `high` where a `cap_critical` stall gets `critical`. The spec does not mention this. It is harmless and test-pinned, but it is unspecified behaviour. | skills/run-autopilot/cli/triage.py:297 | 2 | BLAKE |

Note: the consolidator merged Blake's two further Low rows (comma-in-filename / nested-parenthesis parsing, and the English-only `_missing_path_error` locale dependence) into R4 and R3 respectively on file-citation match.

## Alice

Incremental review of the cycle-1 rework. Prior findings R1, R3, R4, R5, R6, R8, R9, R10, R11 and R13 all verified resolved in code; R7 and R2 partly fixed (code side documented, design doc / PRD text and `state-schema.md` still disagree). Fail-first replay: five touched tests pass against the base commit, but each pins behaviour that already existed and was only untested, so not counted as tautological. Findings: the `state-schema.md` false claim (R1), the `do_stall` 56-line breach (R2), the residual `../x.py` exit-2 case of cycle-1 R1 (R3), a weak assertion in `test_case_variant_equal_head_shas_are_treated_as_equal` (R10) and the stale design-doc interface name (R11).

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
R12: fail
R13: pass

## Blake

Blind (PRD-only) lens. Verified the four test files pass (106 passed), all 18 named tests exist, and the 00310-pair success criterion holds (exit 1, R5 and R6 both `regression: true, commit: 8b3a58f2`). Probed eleven cell shapes on a scratch repo; all classify as specified except the backtick-wrapped (R4), directory (R5), out-of-repo and past-EOF (R3) cases. Also flagged the `state-schema.md` contradiction (R1), the wrong `_parse_file_cell` docstring (R12) and the unspecified `cap_regression` severity (R13). Did not check whether `autopilot render report` prints `stalled: cap_regression`.

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

Doubt + de-slop lens (codex), after one retry (inlined). Three findings: the `a.py:1-2-3` uncaught `ValueError` (R6), the `state-schema.md` contradiction (R1) and the `do_stall` 56-line breach (R2). FIX bucket carries all three; VERIFY and KNOWN are empty.

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
R12: fail
R13: pass

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

[CARL] ✅ No issues found — no frontend or design surface in this diff.

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

Verdict: 13 findings
Tests: 7008 passed, 0 failed, 3 skipped (suite run this cycle)
