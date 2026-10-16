# Decision Audit Log: 00321-cap-check-classifies-every-cell-and-records-what-it-parks-v2

PRD: `00321-cap-check-classifies-every-cell-and-records-what-it-parks-v2.md`
Started: 2026-10-16T19:32:57Z
Completed: 2026-10-16T19:32:57Z
Autonomous: 29  |  Deferred: 1  |  Doubts: 0

### [autonomous] 2026-10-16T19:32:57Z

**Decision**: cap-check fails toward not-a-regression on six File-cell/validation bugs and records nothing on a cap_regression stall

**Choice**: strict per-path File-cell parsing, cryptographic range proof (full-sha + ancestor checks), unresolved-path rows stall (regression:null) rather than silently defer; cap_regression stall migrates pending deferred_decisions into the batch ledger and qualifies for mint-stubs exactly like cap_critical (minus custody)

**Rationale**: 3 review dispatches (1 claude, 2 claude-fallback after a codex gateguard failure), 4 blockers found and fixed across rounds, 0 open at close

### [autonomous] 2026-10-16T19:32:57Z

**Decision**: A path that exists in the work tree but not at `head` is read as a git failure, not as "unresolved"; `_missing_path_error` misses git's "exists on disk, but not in" wording so the verb exits 2 instead of printing regression: null and exiting 1.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-16T19:32:57Z

**Decision**: Docs still describe the old behavior: state-schema.md:510 omits the cap_regression migration and the null-row ref + reason detail form, and phase-done.md:31 / phase-review.md:59 say mint-stubs mints only for CRITICAL/HIGH or cap_critical rows.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-16T19:32:57Z

**Decision**: _verify_range compares head_sha values as raw strings, so an upper-case and a lower-case spelling of the same commit pass the "differ" check, the range is empty, every row classifies regression: false and the verb exits 0 and defers.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-16T19:32:57Z

**Decision**: Equal commits with differently cased SHA strings bypass the empty-range guard: both resolve successfully, but string equality fails, allowing an empty range to classify rows as non-regressions.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-16T19:32:57Z

**Decision**: Two new behaviors have no test: the _verify_range unresolvable-40-hex-sha branch, and _migrate_stall_deferrals' exit-9 failure path plus its same-op_id no-double-write claim.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-16T19:32:57Z

**Decision**: A range followed by a comma list blames only the first line: `a.py:3-5,9` parses to [3], so lines 4, 5 and 9 are silently skipped and the row can read regression: false.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-16T19:32:57Z

**Decision**: do_stall migrates pending deferrals differently from the design contract (_migrate_stall_deferrals gated on REGRESSION_SITE only), and the do_stall docstring exit-code table was never updated for REGRESSION_SITE.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-16T19:32:57Z

**Decision**: triage._severity hard-codes a cap_regression stall stub as severity: critical, overstating regressions that are HIGH or below; the test only covers a lone stall row.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-16T19:32:57Z

**Decision**: _COLON_L_RE rejects the contracted `a.py:L 4` form because whitespace is accepted before `L` instead of after it; a resolvable regression becomes an unresolved-path verdict.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-16T19:32:57Z

**Decision**: output-formats.md:256 and review-coverage-format.md:12 still tell reviewers to write `head_sha: <git HEAD sha>`, but cap-check now rejects anything but a full 40-hex sha with exit 2.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-16T19:32:57Z

**Decision**: _assert_exit_2_naming accepts any one of several words via any(word in stderr); pin the one wording _verify_range emits.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-16T19:32:57Z

**Decision**: classify_findings returns [] (exit 0, deferral) when --previous names a file that does not exist; that is fail-open for a mistyped path rather than failing toward stalling.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-16T19:32:57Z

**Decision**: R14 (BOB): cannot statically verify the 00310 review-pair attribution

**Choice**: routed to verification

**Rationale**: queued as cycle-1 check: python3 skills/run-autopilot/cli/__main__.py cap-check --review-file docs/dev/project-management/reviews/00310-park-cap-regressions-v1-review-2.md --previous docs/dev/project-management/reviews/00310-park-cap-regressions-v1-review-1.md (expect exit 1, R5/R6 regression true at 8b3a58f2); runs in the rework work pass step 7

### [autonomous] 2026-10-16T19:32:57Z

**Decision**: review_lenses after review-close read failed for every lens

**Choice**: rewrote review_lenses to done for consensus/blind/doubt/ui

**Rationale**: all four rostered reviewers produced usable output this cycle (Bob after one inlined retry); review-close re-derivation disagreed with the facts, and the dashboard must not read four failed lenses

### [autonomous] 2026-10-16T19:32:57Z

**Decision**: mech-check replay: 3 touched tests in test_cap_check.py pass against the pre-change code

**Choice**: discarded (ledgered)

**Rationale**: Behaviour-preserving pin of pre-existing untested range-proof behaviour, requested by cycle-1 R5; Alice verified each test fails if that behaviour breaks

### [autonomous] 2026-10-16T19:32:57Z

**Decision**: mech-check replay: 2 touched tests in test_records_stall.py pass against the pre-change code

**Choice**: discarded (ledgered)

**Rationale**: Behaviour-preserving pin of the pre-existing migration exit-9 and op_id dedup paths, requested by cycle-1 R5; Alice verified each test fails if that behaviour breaks

### [autonomous] 2026-10-16T19:32:57Z

**Decision**: Cycle 2 converged: 13 findings, no CRITICAL/HIGH, doubt-roster constraint certified

**Choice**: auto-fix via tail sweep (11 medium/low findings)

**Rationale**: Medium and Low never block convergence; the tail is swept by normal work tasks before finalize

### [autonomous] 2026-10-16T19:32:57Z

**Decision**: `state-schema.md` now says the `cap_regression` stall migrates pending deferrals "under `op_id`-less records since only the stall record itself is deduped". That is false. `_migrate_stall_deferrals` calls `custody.migration_records` (`skills/run-autopilot/cli/custody.py:305`), which keys each record `<op_id>-dd<i>`. The new `test_cap_regression_migration_dedupes_on_retry` relies on that, and `phase-review.md:59` and `recovery.md` say `<op_id>-dd<i>` too. The same sentence also says "exactly as `cap_critical` does", yet it describes a different record shape. Fix by replacing the clause with "under `op_id: "<op_id>-dd<i>"`, deduped on retry".

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-16T19:32:57Z

**Decision**: The `do_stall` docstring edit grew `do_stall` from about 46 to 56 lines (mech block: `do_stall` line 536, 56 lines). That breaks the 50-line limit, and this diff introduced the breach. The new paragraph repeats the comment already at `skills/run-autopilot/cli/records.py:493-495` and the `_migrate_stall_deferrals` docstring. Behaviour-preserving fix: cut the paragraph to one or two sentences, for example "`site == triage.REGRESSION_SITE` also migrates pending `deferred_decisions` (step 4a, via `_write_stall_records`), writing no custody marker", or move the detail into `_write_stall_records`.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-16T19:32:57Z

**Decision**: This is a residual case of R1. The "exists on disk, but not in" fix covers an untracked file or an absolute path outside the repo. A relative cell that escapes the repo, such as `../x.py`, still takes the exit-2 path instead of `regression: null`. I confirmed that git answers `fatal: '../x.py' is outside repository at '<root>'`, which none of the `_missing_path_error` substrings match, so `_file_exists_at` re-raises. `_normalise_path` only normalises such a path with `posixpath.normpath` and leaves it as `../x.py`. The loop still stalls through retry and `sub_skill_fail`, but the row gets no `reason`. Either add "is outside repository" to the missing-path matches and test it, or send a path starting with `..` to the unresolved verdict before calling git. Blake adds the same shape for a line past EOF (`a.py:9999`) and line 0: `_introducing_commit` re-raises anything `_missing_path_error` does not match ("file has only N lines", "-L invalid line number"), so one unreadable cell aborts the whole verb with exit 2 instead of yielding a null row, and every other row goes unclassified. Blake also notes `_missing_path_error` matches English git messages only and `_git` does not set `LC_ALL=C`, so under a non-English locale a genuinely missing path exits 2 instead of producing a null row.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-16T19:32:57Z

**Decision**: Medium: A backtick-wrapped name followed by a line spec is not parsed. `_clean_segment` strips backticks only at the segment edges, so `` `a.py`:4 `` leaves a trailing backtick and the row comes back `regression: null` with `reason: unresolved path a.py```. A fixture with a rework-added line 4 should classify this as a regression. The spec says to "strip backticks" and lists the backtick shape among the cells that must classify. The verb still exits 1, so it fails safe, but the `detail` is wrong and the shape is not parsed. The same applies to `` a.py:4 `b.py` ``. Blake also reports a filename containing a comma followed by a non-digit (`a,b.py`) is split into `a` and `b.py`, so the row reads `unresolved path a` (a false stall), and a nested-parenthesis annotation (`a.py:4 (note (nested))`) also falls to null.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-16T19:32:57Z

**Decision**: Medium: A directory File cell fails open. A cell like `skills/run-autopilot/cli/` resolves at head (cat-file -e succeeds on a tree). It is never in `changed_files`, which holds file names only. With no line spec, `_pair_commit` therefore returns None and the row is `regression: false`, so the finding is deferred even when the rework touched files under that directory. This is the "classifier fails toward not a regression" behaviour the PRD set out to remove.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-16T19:32:57Z

**Decision**: `_FILE_LINE_RE` accepts `a.py:1-2-3`, but `_parse_number_list` then calls `int("2-3")`, raising an uncaught ValueError instead of CapCheckError. Validate comma-separated tokens as individual numbers or single ranges.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-16T19:32:57Z

**Decision**: Carried forward from cycle 1: the queued verification check never ran (`result: null` in `-checks-1.json`) — `python3 skills/run-autopilot/cli/__main__.py cap-check --review-file docs/dev/project-management/reviews/00310-park-cap-regressions-v1-review-2.md --previous docs/dev/project-management/reviews/00310-park-cap-regressions-v1-review-1.md`. It proves the PRD's headline success criterion (the 00310 pair classifies R5/R6 as regressions and the verb exits 1). Run that exact command and record its result.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-16T19:32:57Z

**Decision**: `test_case_variant_equal_head_shas_are_treated_as_equal` only asserts `pytest.raises(CapCheckError)`. If git stopped resolving upper-case shas, it would pass on "does not resolve to a commit" instead of the equality guard. Add `match="equal"`.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-16T19:32:57Z

**Decision**: The design doc (PRD Interfaces & contracts) still names `_migrate_pending_deferrals`, gated on both sites with no `op_id`. The code has `_migrate_stall_deferrals(..., op_id)`, gated on `REGRESSION_SITE` only, which avoids a double write with `custody.record_critical`. The code side is now documented, but the PRD text was not reconciled. This is a documentation note only.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-16T19:32:57Z

**Decision**: Low: The `_parse_file_cell` docstring says a comma list yields "only its first" line, "as before". The code blames every line (`_parse_number_list` returns all of them and `_pair_commit` iterates them). The docstring is wrong.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-16T19:32:57Z

**Decision**: Low: `_severity` now labels a `cap_regression` stall stub `high` where a `cap_critical` stall gets `critical`. The spec does not mention this. It is harmless and test-pinned, but it is unspecified behaviour.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [deferred] 2026-10-16T19:32:57Z

**Decision**: __main__.py is about 1970 lines, over the 800-line limit. The diff changes one line and adds nothing, so I am not counting it against the diff.

**Rationale**: deferred by review-close
