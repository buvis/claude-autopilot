---
prd: 00310-park-cap-regressions-v1.md
cycle: 1
date: 2026-10-15
head_sha: a7335cc17d30ecd35414cae057198d6146397818
codex_thread_id: 01a13f1d-9668-7052-8f22-19305e44fa7a
reviewers: alice,blake,bob,carl
---

# Review: 00310-park-cap-regressions-v1 (cycle 1)

Diff range: 420597624162aacab104976429cc7eb40b5f3916..a7335cc17d30ecd35414cae057198d6146397818

codex_rung_guard: not fired

pack: failed (engram pack exit 1: sqlite3.OperationalError: attempt to write a readonly database)

Notes:
- Bob's first codex run returned a lack-of-input refusal (sandbox initialization failed before any read-only command ran, all R verdicts emitted as `fail` with no findings). One retry was dispatched with the inlined retry prompt (`docs/dev/tmp/bob-prompt-00310-c1-retry.md`, context + full diff inlined); it produced a complete review. Bob's section below is the retry's output.
- `consolidate_findings.py` dropped Bob's issue lines on the first pass: `agents/eve.md`'s doubt contract emits them as `- [BOB] ...` bullets inside the FIX/VERIFY/KNOWN sections, and the consolidator's line parser requires `[BOB]` at column zero. Bob's output was normalized (leading `- ` stripped) into `docs/dev/tmp/bob-output-00310-c1-normalized.txt` and re-consolidated, so the doubt lens is represented in the table below. This is a defect in the review pack, not in this PRD's diff; it is out of scope here and recorded for the batch.
- Mechanical checks are clean: 0 tautological test shapes across 13 test functions, and 13/13 touched tests failed against the pre-change base (fail-first holds). No `[MECH]` findings to absorb.

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [4/4] | 🟠 | `commit` is always `git log --format=%h -1 <head>`, i.e. the review's head commit, not the commit that made the row a regression. The contract says "the first commit that made the row a regression", and the PRD success criterion says the verb "names the rework commit". Real rework ranges hold several commits, and the last is usually an autopilot state-record commit. So the `cap_regression` stall `detail` will name the wrong commit. Fix: for line rows use the blamed SHA (`blame.splitlines()[0].split()[0]`, abbreviated). For path rows use `git log --format=%h --reverse <prev>..<head> -- <file>` and take the first line. The single-commit fixture hides this. | skills/run-autopilot/cli/cap_check.py:94 | 2 | ALICE, BLAKE, BOB, CARL |
| R2 | [3/4] | 🟡 | The prose says "the same custody/mint-stubs sequence the `cap_critical` branch above runs applies here too" for the `cap_regression` stall. That contradicts the PRD and design, which say `mint-stubs` is intentionally NOT extended to `cap_regression`; `triage.qualifies` only matches `site == cap_critical`. Custody capture in `records.py` is also `cap_critical`-only. A model following this will expect custody and stub minting that never happen. Drop the sentence, or say explicitly that custody and `mint-stubs` do not apply. | skills/run-autopilot/references/phase-review.md:59 | 3 | ALICE, BLAKE, CARL |
| R3 | [2/4] | 🟡 | Fail-first gap: the fixture has exactly one rework commit, so the tests cannot tell a head SHA from a blamed or introducing SHA. They assert `rework_short`, which equals both. Add a rework range of 2+ commits (the later one touching another file) and assert the SHA of the commit that changed a.py:3 and of the commit that added b.py. | skills/run-autopilot/cli/test_cap_check.py:78 | 1 | ALICE, CARL |
| R4 | [2/4] | 🟡 | `_FILE_LINE_RE` only splits a bare trailing `:<digits>`. Cells such as `a.py:10-20` or `a.py:3,9` stay whole as the filename. The row then fails the `changed_files` lookup and reads as a silent non-regression (a false negative). `git diff --name-only` without `-z` also quotes non-ASCII paths. Consider matching `:(\d+)(?:[-,]\d+)*$` and taking the first number, and use `-z`. | skills/run-autopilot/cli/cap_check.py:17 | 2 | ALICE, BOB |
| R5 | [1/4] | 🟠 | A File cell holding a line range (`path:576-581`) or a path with a trailing annotation does not match `^(.*):(\d+)$`. The row is parsed as path-with-no-line, with the whole cell as the "path". It is then never found in `git diff --name-only`, so a real rework regression is silently classified `regression: false` and the PRD defers instead of stalling. Range cells exist in real review files (`docs/dev/project-management/reviews/00186-add-item-grained-fast-track-lane-v1-review-2.md`). Absolute-path cells (reviews 00093) can never match a repo-relative diff either. Both fail open. | skills/run-autopilot/cli/cap_check.py:17 | 2 | BLAKE |
| R6 | [1/4] | 🟠 | Every blame failure becomes "not a regression," allowing classifier errors to reach cap-overflow deferral. Suppress only confirmed missing-path errors; propagate invalid line ranges and other Git failures as CapCheckError. | skills/run-autopilot/cli/cap_check.py:73 | 2 | BOB |
| R7 | [1/4] | 🟡 | Test names and coverage deviate from the PRD's named list. Only `test_exit_1_on_any_regression_and_0_otherwise` and `test_unreadable_head_sha_exits_2` match. The others were renamed: `test_line_in_rework_commit_is_regression` became `test_line_blamed_to_rework_commit_is_regression`, `test_line_outside_rework_range_is_not` became `test_rows_outside_rework_range_are_not_regressions`, `test_row_without_path_is_not_regression` became `test_row_without_file_is_not_regression`, `test_medium_rows_are_not_classified` became `test_medium_and_low_rows_are_never_classified`, and `test_missing_previous_file_exits_0` became `test_missing_previous_review_yields_no_rows` at module level only. No CLI test covers the missing-`--previous` exit 0, the JSON-lines stdout (the PRD's "names the rework commit" replay criterion), or `--help` naming `--review-file` and `--previous` (a PRD acceptance item). Rename to the PRD symbols and add CLI assertions on stdout and on missing `--previous`. | skills/run-autopilot/cli/test_cap_check.py:78 | 1 | ALICE |
| R8 | [1/4] | 🟡 | Simplification: `review_file` is read twice, once in `classify_findings` and again in `_head_sha`, each with its own OSError wrapper. Read the text once, then pass it to a `_head_sha(text, path)` that only parses frontmatter (the previous file would still go through a read-and-parse wrapper). This removes the duplicated try/except. | skills/run-autopilot/cli/cap_check.py:119 | 2 | ALICE |
| R9 | [1/4] | 🟡 | `_line_regression` swallows `CapCheckError` from `git blame` and returns False. The spec says exit 2 "when ... a git call fails, with the reason on stderr". A blame failure on a deleted file or an out-of-range line means "not a regression", with no stderr reason. For a row naming a file the rework deleted, that is the wrong answer. | skills/run-autopilot/cli/cap_check.py:73 | 2 | BLAKE |
| R10 | [1/4] | 🟡 | Phase 0 test deliverable deviates from the spec. The spec names eight tests, and the file collects nine. Only `test_unreadable_head_sha_exits_2` keeps its name. The other seven are renamed: for example `test_line_blamed_to_rework_commit_is_regression` replaces `test_line_in_rework_commit_is_regression`, and `test_missing_previous_review_yields_no_rows` replaces `test_missing_previous_file_exits_0`. `test_unreadable_head_sha_raises_cap_check_error` and `test_rework_range_returns_endpoints_unchanged` were added. `test_missing_previous_file_exits_0` is never exercised through the CLI exit code. The spec's fixture also differs: c.py MEDIUM is replaced by c.py CRITICAL, and a gone.py deletion is added. | skills/run-autopilot/cli/test_cap_check.py:78 | 1 | BLAKE |
| R11 | [1/4] | 🟡 | Extra `--repo-root` flag on the `cap-check` verb is not in the spec, which gives only `--review-file` and `--previous`. It defaults to cwd, so it is low-risk, but it is unrequested surface. | skills/run-autopilot/cli/__main__.py:882 | 2 | BLAKE |
| R12 | [1/4] | 🟡 | `classify_findings` classifies every high/critical row of the consolidated table, with no way to exclude rows the cycle already dismissed or resolved. The prose calls them "unresolved" rows, but code cannot tell. It also never validates that `head_sha` is a SHA. A value starting with `-` flows into `git rev-list` and `git blame` arguments, and the two blame/rev-list calls take it positionally. This is low risk, since review files are produced by the pipeline. | skills/run-autopilot/cli/cap_check.py:126 | 2 | BLAKE |
| R13 | [1/4] | 🟡 | Deleted file-only findings incorrectly count as regressions: the fixture's `gone.py` remains in `git diff --name-only`. Check existence at the reviewed head before classifying file-only rows. | skills/run-autopilot/cli/cap_check.py:93 | 2 | BOB |
| R14 | [1/4] | 🟡 | Invalid UTF-8 in either review escapes as UnicodeDecodeError, producing CLI exit 1 instead of the required error exit 2. Share a reader that catches OSError and UnicodeError, and reuse the current review text instead of reading it twice. | skills/run-autopilot/cli/cap_check.py:121 | 2 | BOB |
| R15 | [1/4] | 🟡 | Severity filtering occurs after both Git calls, violating the required no-Git path when no HIGH/CRITICAL rows remain. Filter first and return an empty result before invoking Git. | skills/run-autopilot/cli/cap_check.py:131 | 2 | BOB |
| R16 | [1/4] | 🟡 | CLI tests assert only exit codes: a traceback on the regression path also exits 1 and passes. Assert the mixed fixture's complete JSON output and stderr contract, and cover omitted/nonexistent `--previous` through the CLI. | skills/run-autopilot/cli/test_cap_check.py:212 | 1 | BOB |
| R17 | [1/4] | 🟡 | The regression-routing test obtains its `autopilot stall` match from the exit-2 handler, so removing exit-1 stall routing could leave it passing. Restrict assertions to the Exit 1 clause and verify its stall instruction and cap_regression site together. | skills/run-autopilot/scripts/test_cap_regression_prose.py:44 | 3 | BOB |
| R18 | [1/4] | 🟡 | Path("").exists() resolves to current directory, causing empty previous_review_file to raise CapCheckError rather than return [] | skills/run-autopilot/cli/cap_check.py:114 | 2 | CARL |
| R19 | [1/4] | ⚪ | `head_sha` is only checked for non-empty, then passed positionally to `git blame` and `git log`. A value starting with `-` would be read as an option. Validate it against `^[0-9a-fA-F]{4,40}$` in `_head_sha` and raise `CapCheckError` otherwise. | skills/run-autopilot/cli/cap_check.py:30 | 2 | ALICE |
| R20 | [1/4] | ⚪ | Weak prose pins. `test_exit_1_routes_to_cap_regression_stall` requires `autopilot stall` and `cap_regression` anywhere in the slice, and the exit-2 `sub_skill_fail` clause already supplies `autopilot stall`. `test_recovery_lists_cap_regression_slug` does not check that the slugs are adjacent, despite its name and the task text ("next to"). Assert the `autopilot stall`/Loop-mode stall procedure text sits in the same clause as `cap_regression`, and that the slugs sit within one list. | skills/run-autopilot/scripts/test_cap_regression_prose.py:44 | 3 | ALICE |
| R21 | [1/4] | ⚪ | The `cap-check` verb is documented only in the phase-review bullet. Other verbs such as `group-rework` are described in state-schema.md, but `cap-check` has no entry, so the "public API documented" box is only partly met. | skills/run-autopilot/references/state-schema.md | 3 | ALICE |
| R22 | [1/4] | ⚪ | The Nice-to-have `autopilot render report` printing `stalled: cap_regression` is not implemented, and I found no `cap_regression` reference under `render`. | skills/run-autopilot/cli/__main__.py | general | BLAKE |
| R23 | [1/4] | ⚪ | `rework_range()` is an identity function that returns its arguments. It meets the spec's export list but does no range computation. | skills/run-autopilot/cli/cap_check.py:24 | 2 | BLAKE |
| R24 | [1/4] | ⚪ | Existing CLI size violations remain: the supplied mechanical facts show functions of 55 and 51 lines and a file exceeding 800 lines. Splitting these unchanged sections is outside this PRD's scope. | skills/run-autopilot/cli/__main__.py:1469 | general | BOB |

## Alice

Nine findings, listed in the consolidated table above (R1, R3, R4, R7, R8, R19, R20, R21 plus the simplification row). Her lens: implementation-aware consensus against the PRD and the design doc.

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
R13: pass

## Blake

Blind lens, PRD only. Nine findings (R1, R5, R9, R10, R11, R12, R22, R23 above).

Checked and passing, in his words:
- The tests (13 across `test_cap_check.py` and `test_cap_regression_prose.py`) pass.
- `cap-check --help` names `--review-file` and `--previous`.
- Both test files are registered in `dev/bin/release-checks` (lines 225 and 346).
- The CHANGELOG `[Unreleased]` entry exists at CHANGELOG.md:19.
- `recovery.md:101` and `state-schema.md:510` list `cap_regression` beside `cap_critical`.
- The exit codes are 1 for any regression, 0 for none or a missing previous file, and 2 for an unreadable `head_sha` or a failed rev-list or diff.
- The row parser is the shared `findings_section._reviewed_keys`, not a second parser.

B1: fail
B2: pass
B3: pass
B4: pass
B5: fail
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

Doubt lens + de-slop, codex, after one retry (inlined).

FIX:
- [BOB] 🟠 Every blame failure becomes "not a regression," allowing classifier errors to reach cap-overflow deferral. Suppress only confirmed missing-path errors; propagate invalid line ranges and other Git failures as CapCheckError. | File: skills/run-autopilot/cli/cap_check.py:73 | Task: 2
- [BOB] 🟡 Every regression reports `head`, even when an earlier rework commit introduced it. Return the blamed commit for line findings and the first relevant range commit for file-only findings; test multiple rework commits. | File: skills/run-autopilot/cli/cap_check.py:94 | Task: 2
- [BOB] 🟡 Deleted file-only findings incorrectly count as regressions: the fixture's `gone.py` remains in `git diff --name-only`. Check existence at the reviewed head before classifying file-only rows. | File: skills/run-autopilot/cli/cap_check.py:93 | Task: 2
- [BOB] 🟡 Invalid UTF-8 in either review escapes as UnicodeDecodeError, producing CLI exit 1 instead of the required error exit 2. Share a reader that catches OSError and UnicodeError, and reuse the current review text instead of reading it twice. | File: skills/run-autopilot/cli/cap_check.py:121 | Task: 2
- [BOB] 🟡 Git quotes non-ASCII filenames in ordinary `--name-only` output, so file-only findings such as `café.py` can silently miss regressions. Preserve raw stdout and parse `--name-only -z` output using NUL separators. | File: skills/run-autopilot/cli/cap_check.py:135 | Task: 2
- [BOB] 🟡 Severity filtering occurs after both Git calls, violating the required no-Git path when no HIGH/CRITICAL rows remain. Filter first and return an empty result before invoking Git. | File: skills/run-autopilot/cli/cap_check.py:131 | Task: 2
- [BOB] 🟡 CLI tests assert only exit codes: a traceback on the regression path also exits 1 and passes. Assert the mixed fixture's complete JSON output and stderr contract, and cover omitted/nonexistent `--previous` through the CLI. | File: skills/run-autopilot/cli/test_cap_check.py:212 | Task: 1
- [BOB] 🟡 The regression-routing test obtains its `autopilot stall` match from the exit-2 handler, so removing exit-1 stall routing could leave it passing. Restrict assertions to the Exit 1 clause and verify its stall instruction and cap_regression site together. | File: skills/run-autopilot/scripts/test_cap_regression_prose.py:44 | Task: 3

VERIFY:
- (none)

KNOWN:
- [BOB] ⚪ Existing CLI size violations remain: the supplied mechanical facts show functions of 55 and 51 lines and a file exceeding 800 lines. Splitting these unchanged sections is outside this PRD's scope. | File: skills/run-autopilot/cli/__main__.py:1469 | Task: general

R1: fail
R2: fail
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: fail
R10: fail
R11: pass
R12: fail
R13: fail

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

Backend: copilot (gemini runner). Four findings (R1, R18, R3, R2 above).

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

Verdict: 24 findings
Tests: 6881 passed, 0 failed, 34 skipped (suite run this cycle)
