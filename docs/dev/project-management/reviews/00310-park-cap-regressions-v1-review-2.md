---
prd: 00310-park-cap-regressions-v1.md
cycle: 2
date: 2026-10-15
head_sha: 258fa16ca969a2e3e4a4b431e15fb9eeba5013bd
codex_thread_id: 01a13f42-b9e9-7301-97cf-4f2001ebc1a5
reviewers: alice,blake,bob,carl
---

# Review: 00310-park-cap-regressions-v1 (cycle 2)

Diff range: a7335cc17d30ecd35414cae057198d6146397818..258fa16ca969a2e3e4a4b431e15fb9eeba5013bd

codex_rung_guard: not fired

pack: failed (engram pack exit 1: sqlite3.OperationalError: attempt to write a readonly database)

Notes:
- Incremental review: the diff is scoped to the cycle-1 rework commits, and Alice, Bob and Carl were given the cycle-1 findings to verify. Blake stayed blind (PRD only).
- Bob's first codex run returned a lack-of-input refusal in substance (no findings, every `R{n}` emitted as `fail`, body asking for the context and diff to be pasted) - the same failure mode as cycle 1. One inlined retry was dispatched (`docs/dev/tmp/bob-prompt-00310c2-retry.md`, context + full diff inlined, 146 KB); it produced a complete review. Bob's section below is the retry's output (after one retry (inlined)).
- Mechanical checks: 0 tautological test shapes across 19 test functions. The fail-first replay flagged 6 touched tests that pass against the pre-change code; those `[MECH]` findings are absorbed into the table below (R2, R3 and R14 gained `mech-check` as a finder; R18 and R19 carry the remainder).
- A formatter reflow of three already-committed files (black-style line wrapping, no behavior change) was present in the work tree at session start and was discarded with `git checkout` before staging, so the reviewed range is the committed rework only.

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [2/4] | 🟡 | Prior finding R4 (the `-z` half) is still open: `git diff --name-only` is still read without `-z`, so a non-ASCII path comes back quoted. Confirmed that `café.py` returns `"caf\303\251.py"` without `-z` and `café.py\0` with it. A file-only row naming a non-ASCII file then never matches `changed_files` and silently reads as a non-regression (fail-open). The rework fixed only the regex half, and the settled-decisions ledger does not defer this half. Fix: use `diff --name-only -z` and split on NUL, or drop the pre-check and rely on `_first_commit_touching`. | skills/run-autopilot/cli/cap_check.py:188 | 5 | ALICE, BOB |
| R2 | [2/4] | 🟡 | `test_file_only_row_is_attributed_to_the_commit_that_added_it` is tautological for its stated purpose, and the fail-first replay confirms it passes against the pre-change code. b.py is added by the LAST rework commit, which is also the review's head. The old "always `head`" behaviour and the new `_first_commit_touching` therefore both return `rework_short`, and the docstring's "not the range's last commit" claim is false. A regression of `_first_commit_touching` to `head` would stay green. Fix: assert a file-only row for a file touched earlier in the range (for example `a.py` with no line, expecting `line_fix_short`), or touch b.py again in a third commit. | skills/run-autopilot/cli/test_cap_check.py:102 | 1 | ALICE, BOB, mech-check |
| R3 | [2/4] | 🟡 | The `bad_sha` assertion in `test_unreadable_head_sha_raises_cap_check_error` does not pin the new `_SHA_RE` guard, and the fail-first replay confirms the test passes at base. `-rf` already fails at base because `git rev-list -rf..<head>` exits 129, so the same error is raised without the guard. Use a head_sha that git would resolve but the regex rejects (for example `HEAD`, or a branch name), and assert `CapCheckError` with "malformed head_sha" in the message. | skills/run-autopilot/cli/test_cap_check.py:233 | 1 | ALICE, BOB, mech-check |
| R4 | [2/4] | 🟡 | The R6 fix now makes any non-missing-path blame error exit 2. Confirmed that a reviewer-cited line beyond EOF ("file a.py has only 3 lines"), line 0 ("-L invalid line number: 0"), or an absolute path outside the repo ("outside repository") each raises `CapCheckError`. The error is deterministic, so the prose's "re-invoke once" cannot help, and one bad citation on a HIGH row stalls the whole PRD as `sub_skill_fail` instead of classifying that row. This matches the spec's "git call fails -> exit 2", so it is not a defect. Consider noting the trade-off in the cap-out prose or in `_missing_path_error`'s docstring. | skills/run-autopilot/cli/cap_check.py:86 | 2 | ALICE, BLAKE |
| R5 | [1/4] | 🟠 | Spec says the `cap_regression` stall is "the same `records.do_stall` call as `cap_critical`" and "lets `mint-stubs` run". The implementation deliberately does neither. The prose says "Unlike `cap_critical`, this stall captures no custody and mints no hold stub". `triage.qualifies` only accepts a stall row whose site is `cap_critical`. The regression path also writes no `cap-overflow` deferral. The regressed HIGH therefore reaches no deferred JSON and no stub, only the stall `detail` string. That is the "nobody reads it until batch end" gap the PRD set out to close. | skills/run-autopilot/references/phase-review.md:59, skills/run-autopilot/cli/triage.py:156-162 | 3 | BLAKE |
| R6 | [1/4] | 🟠 | On the `cap_regression` path, the other unresolved findings are not recorded. These are the non-regression HIGH rows and the MEDIUM and LOW rows. The `cap-overflow` recording step sits after the Exit 1 branch and is skipped, so those findings reach no ledger. Only the regression refs and commits are kept, in the stall `detail`. | skills/run-autopilot/references/phase-review.md:59 | 3 | BLAKE |
| R7 | [1/4] | 🟠 | Missing-path handling still suppresses real failures: `_file_exists_at` catches every `CapCheckError`, while `_missing_path_error` searches the command text too, allowing filenames containing "does not exist" to suppress unrelated blame errors. Inspect actual Git stderr, suppress only confirmed missing paths, and test both failure cases. | skills/run-autopilot/cli/cap_check.py:117 | 4 | BOB |
| R8 | [1/4] | 🟠 | Absolute and annotated locations remain false negatives: `/repo/b.py` cannot match repo-relative changed filenames, and `a.py:3 (note)` bypasses blame. Normalize in-repository absolute paths for lookup; parse or explicitly reject unsupported annotations instead of returning a clean verdict. | skills/run-autopilot/cli/cap_check.py:133 | 4 | BOB |
| R9 | [1/4] | 🟡 | `_file_exists_at` catches every `CapCheckError` and returns False. A non-missing-path git failure (corrupt object, git error) therefore reads as "file gone, not a regression" and fails open. The same rework (R6) made `_introducing_commit` re-raise everything except a missing path. Reuse `_missing_path_error(err)` and re-raise otherwise: `cat-file -e` prints "does not exist in", which the helper already matches. | skills/run-autopilot/cli/cap_check.py:120 | 2 | ALICE |
| R10 | [1/4] | 🟡 | Six of the eight Phase 0 test names the spec requires are absent, so the Phase 0 acceptance ("collects the eight tests") does not hold literally. Missing: `test_line_in_rework_commit_is_regression`, `test_line_outside_rework_range_is_not`, `test_file_without_line_added_by_rework_is_regression`, `test_medium_rows_are_not_classified`, `test_row_without_path_is_not_regression`, `test_missing_previous_file_exits_0`. Renamed equivalents exist, and only `test_exit_1_on_any_regression_and_0_otherwise` and `test_unreadable_head_sha_exits_2` match by name. The fixture also differs from the spec (two rework commits, not one). All 19 tests pass. | skills/run-autopilot/cli/test_cap_check.py:85 | 1 | BLAKE |
| R11 | [1/4] | 🟡 | The file-only predicate differs from the spec. The spec says a row with a path and no line is a regression when the path appears in `git diff --name-only prev..head`. The code adds a `_file_exists_at(head, file)` condition, so a file deleted by the rework is never a regression. The commit is also resolved via an extra `git log --reverse` call. This is probably sensible, but it is an unspecified predicate change. | skills/run-autopilot/cli/cap_check.py:142 | 2 | BLAKE |
| R12 | [1/4] | 🟡 | The spec says `cap-check` runs first in the cap-out branch. The prose runs it only after the CRITICAL check ("Otherwise (all unresolved findings ≤ high)"). A rework-introduced CRITICAL takes the `cap_critical` route and `cap-check` never sees it, although the verb classifies critical rows. This is defensible, but it is an ordering deviation. | skills/run-autopilot/references/phase-review.md:59 | 3 | BLAKE |
| R13 | [1/4] | 🟡 | CLI coverage remains incomplete: substring assertions do not verify valid JSON, all classified rows, or stream contracts; nonexistent `--previous` still lacks CLI coverage. Parse and compare the mixed fixture's complete JSON output, assert stderr/stdout contracts, and exercise a nonexistent previous file. | skills/run-autopilot/cli/test_cap_check.py:303 | 5 | BOB |
| R14 | [1/4] | 🟡 | The changed routing test does not protect the actual prose correction: restoring the old custody/mint-stubs instruction still passes, consistent with the supplied replay. Pin the Exit 1 clause's explicit exclusion of custody capture and hold-stub minting. | skills/run-autopilot/scripts/test_cap_regression_prose.py:66 | 7 | BOB, mech-check |
| R15 | [1/4] | 🟡 | The adjacency heuristic still does not establish membership in a stall-site enumeration: nearby prose within 2,000 characters can satisfy it, and one matching pair can hide another missing enumeration entry. Replace the duplicated closest-pair scans with assertions scoped to each stall-site list or table row. | skills/run-autopilot/scripts/test_cap_regression_prose.py:82 | 7 | BOB |
| R16 | [1/4] | ⚪ | The `cap_regression` entry says "Resume exactly like `cap_critical` above". The `cap_critical` entry's resume is the attended `autopilot custody resolve ...` handler, but the rework correctly established that `cap_regression` has no custody. The clause after the dash clarifies, but the lead-in still points a reader at the custody path. Reword to "Resume: the PRD sits in `hold/`; ...". | skills/run-autopilot/references/recovery.md:106 | 3 | ALICE |
| R17 | [1/4] | ⚪ | The nice-to-have (`autopilot render report` printing `stalled: cap_regression`) was not specifically implemented. `stalled_section` takes the site generically, so it likely renders already, but I did not verify it and no test pins it. | skills/run-autopilot/cli/render_report.py:76 | general | BLAKE |
| R18 | [1/4] | 🟡 | Fail-first replay: `test_omitted_previous_exits_0_with_no_output` and `test_unreadable_head_sha_exits_2` pass against the pre-change code, so neither pins this change's behaviour. | skills/run-autopilot/cli/test_cap_check.py | 1 | mech-check |
| R19 | [1/4] | 🟡 | Fail-first replay: `test_recovery_lists_cap_regression_slug` passes against the pre-change code, so it does not pin the slug addition it is named for. | skills/run-autopilot/scripts/test_cap_regression_prose.py | 7 | mech-check |

### Auto-dismissed (ledger)

- [BLAKE] 🟡 Beyond the specified `--review-file` and `--previous`, the verb adds `--repo-root`. The `--help` output lists it. | File: skills/run-autopilot/cli/__main__.py:882 — The flag is what lets the fixture tests invoke the verb against a temporary repo; it defaults to cwd so the documented two-flag surface is unchanged in use. Removing it would require the tests to chdir, which is worse. Kept deliberately.

## Alice

Findings: R1, R2, R3, R9 (plus R4 and R16 as observations). Prior-cycle verification: R1, R2, R3, R5, R6, R7, R8, R9, R13, R14, R15, R16, R17, R18, R19, R20, R21 resolved; R4's `-z` half still open; R5's absolute-path half unhandled. Not re-raised per the settled decisions: `--repo-root`, the identity `rework_range`, the `__main__.py` size violations.

R1: pass
R2: fail
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: pass
R10: fail
R11: pass
R12: pass
R13: pass

## Blake

Blind lens, PRD only. Findings: R5, R6 (🟠), R10, R11, R12 (🟡), R17 and the exit-0-on-missing-review-file observation (⚪). Confirmed compliant: `classify_findings`/`rework_range` exported with the specified row keys, the classifier reuses `findings_section._reviewed_keys` (no second parser), exit codes 1/0/2 with the reason on stderr, `head_sha` regex-validated before git, the slug listed in `recovery.md` and `state-schema.md`, the CHANGELOG entry under `[Unreleased]` Added, both test files registered in `dev/bin/release-checks`, and `cap-check --help` naming `--review-file` and `--previous`.

B1: fail
B2: pass
B3: pass
B4: pass
B5: pass
B6: pass
B7: fail
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

Doubt lens + de-slop (after one retry (inlined)). Findings: R7, R8 (🟠), R1, R2, R3, R13, R14, R15 (🟡). VERIFY: none. KNOWN: none.

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

## Carl

[CARL] ✅ No issues found. Carl ran the full `dev/bin/release-checks` gate plus targeted pytest and probed the git blame/cat-file edge cases directly.

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

Verdict: 19 findings
Tests: 6887 passed, 0 failed, 34 skipped (suite run this cycle)
