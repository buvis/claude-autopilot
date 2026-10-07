## 1: Gate the summary tests (00221)

- I treated the existing (already-uncommitted) `test_every_wave_test_file_is_listed` function as the one the brief asked for, since only the formatter's line join differed from the spec, and did not rewrite it from scratch.
- Ran pytest via `uv run --no-project --with pytest` because system `python3` has no pytest installed.
- (strengthening pass) Same `uv run --with pytest` assumption repeated.
- (strengthening pass) The `ast` duplicate-assignment check scans only top-level `Assign` nodes; an annotated (`AnnAssign`) or augmented reassignment of `_WAVE_TEST_FILES` would not be counted as a second assignment. Fine for today's plain assignment.
- (Ivan) None reported.

## 5: Switch the assembly worktree gate to foreign_dirty and hold the seeded backlog (00225)

- (Tess, initial) Used `wave_assemble._default_run_git` as the `run_git` argument to `_land_cleanup` in both tests - the contract doesn't name a fake; this is the same default `_check_reviewable`/`review()` rely on elsewhere in the file.
- (Tess, initial) Represented "foreign dirt beside store churn" with one case (`readme_edited`) rather than the full `FOREIGN_CASES` matrix, per SIMPLICITY FIRST.
- (Tess, initial) Assumed backlog PRDs for the "seeded backlog" test can be plain unstaged files written directly into the worktree's `prds/backlog/` before `seed_state` runs, rather than first committing them in the main repo.
- (Tess, strengthen) Git's default rename detection means point 5's "lists ... as added" can't be asserted via an `A\t` prefix; asserted the destination path's presence in the diff instead.
- (Tess, strengthen) Point 8 ("call seed_state a second time... assert HEAD unchanged") interpreted as the fail-then-retry scenario the codebase already supports, not a second call after a fully successful run (the real CLI steps reject a second `phase-done` once phase is already `review`).
- (Tess, strengthen) Did not add a non-md-file assertion to the `_seed_with_backlog`/retry helper, since point 7 is specific to the test named in the brief.
- (Ivan, initial) `branch -D` assumed acceptable in `_land_cleanup` (flagged for review attention; the per-task reviewer caught this and it was reverted to `-d`).
- (Ivan, initial) The hold commit uses pathspec `prds`, so it also picks up other edits to tracked files under `prds/` that are not staged; untracked files like a new wip stub are not included.
- (Ivan, initial) Backlog PRDs may be tracked, untracked, or gitignored; `rm --cached --ignore-unmatch` plus `add -f` handles both.
- (Ivan, retry) `cli/test_wave_review_cleanup.py` assumed to be the right test file to check, since it is the only test that references `_land_cleanup`.

## 6: Land after a hand review (00226)

- (Tess, initial) "Without writing any stub" means the stub must be absent from the worktree's `prds/done/`. Removed it by `git rm` plus commit, not an uncommitted delete, so the result doesn't depend on any dirty-tree check in the review_failed path.
- (Tess, initial) In the hand-reviewed test, the stub content must match what `_landable` already committed, to avoid tripping the pre-removal dirty check.
- (Tess, initial) After a hand-reviewed land, the stub should appear in the main repo's `prds/done/` - the same migration the converged path already does.
- (Tess, strengthen) A hand-reviewed wave reuses the converged path's existing summary-line format `"## Assembly review: converged (1 cycle(s)), landed <tip>"`, with the cycle count read from the worktree's `state.json`.
- (Tess, strengthen) The master-moved sibling does not assert the persisted `wave.json` status (it would be "converged" after the flip) - only the "nothing landed or removed" effects are pinned.
- (Ivan) The hand-review signal is only "the stub file exists in the worktree's prds/done/". No commit is needed, and wave.json is not re-checked.
- (Ivan) A hand-reviewed land never writes the review_failed summary line - only the converged one, as the test's single "## Assembly review:" count requires.

## 7: Document the hand-review route and changelog the six fixes

- (Ivan) The "existing sentence" ends with its parenthetical "(no git write).", so the new sentence goes after that and not in the middle of the parenthetical.

## 8: [D1] Save converged on the hand-review land route (00226) (S)

- (Ivan) The brief's description of `_land_review_failed`'s new behavior ("gains a wave_path param... returns None and saves converged on the hand-reviewed path") meant the hand-reviewed-stub-exists check itself moves inside `_land_review_failed`, rather than staying in `land()` with `_land_review_failed` only ever handling the no-stub case. Both constructions are observably equivalent against the given tests, but the docstring's phrasing only makes sense if `_land_review_failed` owns that branch, so this was not treated as a real ambiguity.

## 9: [D1] Retry the branch delete on rerun and widen the OSError guard (00222) (S)

- (Tess) "Re-run the SAME single-lane scenario fresh" read literally as pytest's own `tmp_path_factory.mktemp(...)` mechanism for a genuinely fresh temp directory, rather than reusing the same `tmp_path`.
- (Tess) Used a named nested function `boom` to raise the OSError (matching this file's own existing idiom), rather than the generator-lambda form the brief offered as an alternative - the brief allowed either.
- (Tess) Exact test/helper names and placement within each file were her own choice; the brief specified required behavior and conventions to follow, not exact names or line position.
- (Ivan) The fix for the branch-delete retry belongs in `_drain_lane`'s early-return branch itself (duplicating the two-line branch-delete check rather than extracting a helper), since that is the only place that can see "worktree already gone, branch maybe not" on a rerun, and there are only two call sites.
- (Ivan) No `lane["status"] == "assembled"` guard was added before the early-return branch-delete check, since `worktree_removed` is only ever set inside the `status == "assembled"` block, so status is already guaranteed assembled whenever that early return is reached.

## 10: [D1] Restore the PRD's acceptance test ids and make them fail-first (00221, 00225) (M)

- (Ivan) Items 2 and 3's hand demonstrations both needed the same temporary `wave_review.py` edit (disabling the `_hold_backlog` call site), so they were combined into one sequence instead of two separate edit/restore cycles - the net effect and evidence gathered are identical.
- (Ivan) Treated the task's own explicit "Verify (run exactly these, in order, as your final check before reporting)" section, which names `bash dev/bin/release-checks` as a required final command, as superseding the generic rule against running the full suite inside a task dispatch - this task's brief is more specific and one of its sub-items depends on that command's output.

## 11: [D1] Make _hold_backlog safe under partial failure (00225) (S)

- (Tess) Simulated the commit failure via `subprocess.CalledProcessError` raised directly by a monkeypatched `_default_run_git` (one of two exception types the brief offered as equally valid) rather than `RuntimeError`.
- (Tess) Asserted a generic `Exception` type for the collision refusal (the brief explicitly offered either `Exception` or `ValueError` as defensible) and asserted the exception message contains the full absolute paths of both the backlog and hold files.
- (Tess) Both new tests call `_hold_backlog` directly rather than through `seed_state`, per the brief's explicit "your choice" - this keeps each test isolated to the function under test.
- (Tess) Added `(pm / "prds" / "hold").mkdir(parents=True, exist_ok=True)` to test 1's setup, mirroring the precondition `seed_state`'s earlier steps already guarantee for the other tests in this file - calling `_hold_backlog` directly bypasses that guarantee.
- (Ivan, review retry 1) Added a new git subcommand (`ls-files --others --exclude-standard`) to detect held-but-uncommitted files on disk, since `diff --cached` alone cannot see untracked files - necessary to cover a failure at `rm --cached` before anything is staged.
- (Ivan, review retry 1) Kept `names` in the three-way union (`names | staged | untracked`) defensively, even though `untracked` alone already covers freshly-renamed files once the rename loop has run.
- (Ivan, review retry 1) Moved the no-op guard to run after the rename loop and the staged/untracked recomputation (rather than before, as in the original code), since the fix requires detection to happen after renaming - this costs two extra git calls in the true-no-op case but is otherwise behavior-equivalent.

## 13: [D2] Tail sweep: close the cycle-2 medium/low tail on the wave slot lock, hold-backlog and drain-lane paths (M)

- (Tess) Took the lock through the module-level `_slot_lock` seam rather than patching `builtins.open`, because the brief offered either and the lock's file-opening shape was not visible from the interface notes; the vanish-before-lock test wraps it with a `*args, **kwargs` shim. Both tests ran as intended against the pre-fix code.
- (Tess) For the vanish-before-lock case, asserted only "no raise and nothing created", not stderr content, since the brief is silent on output there.
- (Tess) `_crash_on_hold_backlog_step` matches the first git call carrying `rm` or `add` as a list element and then restores real git; this assumes `_hold_backlog` renames before its first `rm`, which the brief states.
- (Tess) The space-in-name tests pre-create `prds/hold/`, mirroring the existing retry test; whether `_hold_backlog` creates it itself is untested.
- (Tess) A filename containing a space appears unquoted in `git show --name-only`, which held when run.
- (Ivan) The `-z` queries need no `core.quotePath` handling, because `-z` output is unquoted.
- (Ivan) Placed `_delete_lane_branch` directly above `_drain_lane` and `_pending_hold_names` directly above `_hold_backlog`.

## 1: Write hooks/guard_phase_delegation.py with is_phase_delegation and fixtures (00248)

- (Tess, initial) Denied fixture format: line 1 is the Agent `description`, the remainder is the `prompt` - the task did not specify a fixture format.
- (Tess, initial) Allowed fixtures, and every corpus file, are passed as `tool_input["prompt"]` with description "".
- (Tess, initial) The corpus test calls `is_phase_delegation` in-process rather than running the hook as a subprocess, for speed.
- (Tess, initial) The test module is not run as `__main__`, so `guard_phase_delegation.py` must be importable without side effects (`main()` guarded by `if __name__ == "__main__"`).
- (Tess, initial) Fail-open cases assert the exact stderr strings given in the contract's `main()`; a JSON array at stdin counts as an empty/unparseable payload.
- (Tess, strengthen) A realistic Agent `description` is the stem-derived label "<Role> <n> <suffix> subagent" - the contract does not specify description shapes.
- (Tess, strengthen) `{}`, `{"prompt": None}` and both-None must give empty stderr, per the contract's predicate-returns-False / main-prints-only-on-raise semantics.
- (Tess, strengthen) For a non-string prompt beside a string description the contract does not pin the predicate's result, so either a silent allow or the "predicate raised, allowing" line is accepted.
- (Tess, strengthen) Skipping corpus files that mention `guard_phase_delegation` (rather than a fixed name list) is the right reading of "this PRD's own dispatch prompts are self-referential".
- (Ivan) A non-dict `tool_input` passed straight to `is_phase_delegation` returns False, per the contract docstring.
- (Ivan) A non-string prompt beside a string description gets coerced into the joined text by the f-string rather than ignored; the predicate does not raise, so the hook allows with empty stderr.
- (Orchestrator, autonomous decision) Widened the design contract's `_IMPERATIVE` regex to also match present-participle forms (executing/running/invoking/following/continuing/resuming): Tess recovered the real 2026-10-03 00242 transcript and found the verbatim base-form-only regex misses 2 of the 4 real denied delegations ("You are executing the `autopilot:design-solution` skill"). Logged to `state.json` `autonomous_decisions`.

## 2: Add the CLI_SUFFIX sentence forbidding blocked coreutils (00248)

- (Tess) The new sentence is the last thing in every autopilot launch prompt - follows from the contract's verbatim `CLI_SUFFIX` (new sentence last) and `prompt_for` returning `prompt + brief + cli`.
- (Tess) Matching the contract's full sentence exactly, not just the acceptance-criteria substring, is intended, since the dispatch calls the contract text "verbatim".
- (Ivan) None reported.

## 3: Register the hook on PreToolUse Agent and add the gate prose (00248)

- (Tess) Contract line breaks and "> " markers in the design doc are just markdown wrapping; prose is checked as rendered markdown (one space per whitespace run, blank line splits paragraphs).
- (Tess) "Just before" the anchor means only whitespace (a line wrap or a blank line) between the gate sentence and the anchor; same-paragraph or separate-paragraph both pass.
- (Tess) "Append to the existing STOP paragraph" means the note continues the same paragraph after one space, no blank line before it.
- (Tess) PreToolUse entry order in hooks.json is not checked, only that the set of matchers is preserved and none is lost.
- (Tess, strengthen after Devon) Reworked the gate-prose check to operate on real (non-flattened) paragraphs so a gate/anchor hidden in an HTML comment, heading, or code fence - or split across a blank line - cannot pass; added neighbour-paragraph and section-boundary checks so a sentence can't be relocated elsewhere in the file; added a banned-phrase check so prose that contradicts the gate (e.g. "may be ignored") cannot pass.
- (Ivan) None reported.

## 7: Merge the duplicated gate sentences in phase-build.md Phase 2 and Phase 3 (00248)

- (review cycle 1, low finding) `skills/work/SKILL.md`'s STOP-line addition deliberately differs from the PRD's example sentence ("In loop mode a hook enforces this (`hooks/guard_phase_delegation.py`).") - it is expanded with a disclaimer scoping the claim to what the hook actually checks (it does not enforce the general one-task-per-dispatch rule; the STOP paragraph still governs that by prose alone). The design doc's dispatch-2 non-blocker made this change deliberately. Left unchanged per the rework task's own instruction to record, not churn it.

## 8: [D1] Rework: skills/run-autopilot/cli/ (00249, cycle 1)

- (Tess) `review_close.close()` gains a `require_codex_guard: bool = False` parameter (name matched to the existing `gate.run_gate` kwarg).
- (Tess) Tail-sweep no-op gating keyed on `batch_id == "tail-sweep"` (the literal already used elsewhere in the file).
- (Tess) `review_stage.stage()` gains a `prior_findings: Path | None = None` parameter, threaded through to `render_roster`.
- (Tess) `_is_chosen_finding` rejects classifications outside `{"fix", "defer", "verify", "discard"}` and requires `found_by`, when present, to be a list of strings.
- (Ivan, initial) `found_by` list-of-strings validation applies only to `fix`/`defer` rows. Tail-sweep skip covers `doubts_rubric_verdicts`, `review_lenses`, and `_end_dispatch_rows` together. `review_stage.py`'s raw/merged PRD split uses the literal marker `"\n\n## Design Doc\n\n"`. `require_codex_guard` default stays `False`; no CLI flag added yet at this point (added in retry 2).

## 4: review_stage: Eve PRD-only, Bob appendix unconditional, one diff-base resolver (00256)

- (Ivan, review-fix retry) The old `--base master` assertion in `test_replay_cmd_never_receives_gate_command` was superseded by the confirmed review finding, so editing that test was in scope.
- (Ivan, review-fix retry) During the fail-first check it briefly stashed and restored `review_stage.py` with `git stash`; the stash was popped cleanly.

## 5: gate: findings JSON cross-check, wired into review-close's state mutation (00256)

- (Tess) `gate --findings` takes a path to a JSON file, mirroring `review-close --findings` (confirmed by probing the CLI). Highest-risk assumption of the task: inline JSON would have needed six gate tests changed.
- (Tess) `test_cli_exit_2_on_findings_mismatch` drives `_run_review_close()` through a real subprocess rather than a hand-built `argparse.Namespace`, since the Namespace field names and `--default-tier`'s default were never pinned.
- (Tess) In the bullet-list row shape, a combined severity cell sits inline right after the `[M/N]` marker (`- [2/3] 🟠 High wrong default | ...`); the contract described pipe-table "cells" but mandated the bullet-list parser.
- (Tess) `_normalize_finding_row` is not tested directly: the contract gave its signature only as `(...)`. Its behaviour is pinned indirectly through the severity/file/whitespace cases.
- (Tess) A "well-formed but empty" consolidated section is the heading plus the three subheadings with no bullet rows.
- (Tess) A bad `--findings` file asserts only non-zero exit, non-empty stderr and no `Traceback`; the contract never picked between exit 1 and 2 for that case.
- (Ivan, initial) `--findings` is a trailing positional-capable `findings_file` parameter on `run_gate`, so `review_close`'s existing call and its monkeypatched spy signature keep working. An unusable findings file exits 1, reserving 2 for a real mismatch. The consolidated-findings parse is scoped to the section between `## Consolidated Findings` and the next `## ` heading. The mismatch check runs before `--assert-constraint-met`. Issue text compares case-insensitively with whitespace collapsed; file paths compare case-sensitively after stripping.
- (Ivan, review-fix retry) Finding 1's symmetry fix lives inside `_finding_key`, the one place both sides converge. Side effect judged unreachable and left unhandled: a findings row whose issue text is *only* a severity word now keys with an empty issue string. `verify` and `discard` are taken as the complete set of non-applied classifications.
- (orchestrator) On a `"malformed"` cross-check `close()` does not refuse; it surfaces `findings_cross_check: "malformed"` on the applied result. Recorded as an autonomous decision in `state.autonomous_decisions` - the task mandated refusal on mismatch only, and refusing on malformed would have broken ~14 existing fixtures and refused legacy review files.
- (Ivan, retry 2) Could not add `prd_raw_file` as a new parameter to `render_roster`/`_run_inputs` because tests monkeypatch `render_roster` with fixed-arity fakes; used a filename convention (`review-prd-raw-{id}.md` beside `review-prd-{id}.md`) instead. `autonomous_decisions` entries use a minimal field set (`cycle`, `issue`, `severity`, `action`, `reason`); severity is lowered through an emoji-to-word map to satisfy `schema.py`'s `DECISION_SEVERITIES` vocabulary (discovered only via the test run, `schema.py` outside the file allowlist). A persona in `dispatch_rows:` but absent from `agents:` defaults to outcome `"ok"` (preserves prior behavior for that case).
- (Ivan, retry 2) `_KNOWN_SEVERITIES` initially accepted both emoji and plain-word severities (no test exercised rejection) - corrected in retry 3 to emoji-only after the per-task reviewer flagged the word form as a live bypass of CRITICAL grouping.
- (Ivan, retry 3) Used a plain dict (`ctx`) rather than a dataclass to collapse `_close_mutator`'s 9 positional args, to avoid a new import.
- Deferred, not fixed (3-cycle per-task review cap reached): `dispatch_rows:`/`agents:` frontmatter block documentation (needs SKILL.md/output-formats.md edits, outside this task's file allowlist); Eve's PRD-body isolation (F3) and failure-fallback doubt-prompt completeness (F4); per-reviewer doubt-verdict source tagging; `run_gate`'s unsplit length and unbounded `communicate()` buffering. `style_gate` also stayed `failed:` on two pre-existing `__main__.py` functions (`_select_report_block`, `_render_report_surface`) and `review_stage.py`'s file-length cap, both outside this task's fix list.

## 6: skill prose sync: ledger flags, all five lenses, dispatch_rows format, word severity (00256)

- (orchestrator) The three named acceptance tests did not exist, so Ivan wrote them; placed together in a new `skills/review-work-completion/scripts/test_review_verbs_prose.py` because the Verify command collects both skill trees.
- (Ivan) The new flag bullet went directly after the `--replay-cmd` bullet in step 3's flag list.
- (Ivan) The `dispatch_rows` explanation sentence went after the "Agent states" line, not inside the YAML example.
- (Ivan) The `timeout` gloss "(no result in time)" is Ivan's wording; the contract named only the value.
- (orchestrator) The self-deslop pass removed the contract-mandated Blake "stays history-free" sentence (and the blank line before the Standalone-runs paragraph); its commit `2e5a234` was reverted as `f040476` because the sentence traces straight to the task's verbatim contract.

## 12: [D1] Read the findings table in the cross-check (cycle-1 CRITICAL) (00256, cycle 1)

- (Tess) The table-specific malformed reason contains the word "row" and differs from the no-section reason; the exact wording is not asserted. Later tightened to also require "table" or "header", so the literal string `"row"` cannot pass.
- (Tess) `Row.severity` and `Row.issue` may be raw or normalized, so their exact values are never asserted - only `Row.file` equality, substring presence in `issue`, and bullet-vs-table triple equality.
- (Tess) A section holding a pipe table from which zero findings rows can be read is `"unreadable-table"`, for both a header missing required columns and malformed data rows.
- (Tess) The chosen-findings `ref` values are `"R1"`, `"R2"`, ... in review-table row order, and the `Ref` column is the first column of both the header and every data row.
- (Tess) `Row.severity` normalizes to the lowercase English word, so a `High` cell keys as `"high"`; pinned together with equality against the emoji spelling so the test stays honest if only the literal is wrong.
- (Tess) `TABLE_DATA_ROW_RE` is anchored or at least bracket-gated, so `.search` on the header and separator lines returns None.
- (Tess) Mid-table fixture rows are addressed by index, assuming `_reviewed_keys` preserves table order - the same assumption the pre-existing `rows[21]` assertion already made.

## 8: [D1] Tail: release-checks counts the exit status and the harness summaries (00256, cycle 1)

- (Tess) The `INFRA_FAIL=1` case is asserted through the computed exit line, not by reading `INFRA_FAIL` directly; that also assumes the parsed passed count is still added when the exit is non-zero.
- (Tess) For the no-SUMMARY fallback, exit codes 0 and 3 were picked - any non-zero exit counts as one fail.
- (Tess) For the SUMMARY case, the harness's own exit code does not change the counts.
- (Ivan) The harness SUMMARY regex is `^SUMMARY: [0-9]+ passed, [0-9]+ failed` and the last match wins.
- (Ivan) A SUMMARY line with a non-zero exit and `failed` = 0 forces EXIT 1 through `INFRA_FAIL`, matching the `run_pytest` rule.

## 9: [D1] Tail: verification.py honours the deadline, refuses a failed record, states its rule (00256, cycle 1)

- (Tess) The "failed gate" record shapes were tested as given (`commands[0]["exit"]` a non-zero int, `failed` an int > 0); other red shapes (a non-zero exit deeper in `commands`, a string `"1"`) were not invented.
- (Tess) The docstring wording is unspecified, so substrings were pinned ("rename", "copy", "both", "endpoint", the store path, "dirty") rather than a sentence; a correct docstring avoiding any one of those words would fail the test.
- (Tess) The `_drain_bounded` spy uses the documented positional signature `(proc, cap, deadline)`; renaming those parameters would need the same rename in two tests.
- (Tess) The `done is False` case uses a child with pipes still open, because the requirements do not say whether the exit deadline lands inside `_drain_bounded` or in `run_gate`'s wait.
- (Tess) Wall-clock slack (6s timeout asserting `5 < elapsed < 10`, 1s asserting `0.5 < elapsed < 4`, drain deadline 0.5s asserting `elapsed < 5`) is a judgement of a non-flaky margin on this machine.
- (Tess) `pyproject.toml` and `Makefile` are throwaway non-store paths in the temporary git repos; the fixture has no real build files, so the names carry no meaning beyond being outside the store and outside `src/`.
- (Ivan) A record whose `commands` key is missing, not a list, empty, or holding a non-dict entry is treated as NOT green (stale), following the module's fail-toward-re-running invariant.
- (Ivan) "Under 50 lines" is counted from the `def` line through the last body line inclusive.
- (Ivan) `_reap` takes an explicit `drained` flag rather than inferring it, preserving the old unconditional process-group kill when output never drained; no test covers the shell-exited-but-pipes-held case.
- (Ivan) `record["failed"] != 0` was left untouched: a non-int `failed` (e.g. `"0"`) is out of the named scope.
- (Tess) Import style `from cli.test_gate import ...` plus `sys.path.insert(0, parent.parent)` is the pack's convention; reaching `FindingsCrossCheckTests` through the module rather than binding its name, to stop pytest re-collecting that suite (34 vs 17 collected, measured).
- (Ivan) `Row.issue` preserves case and `_backed` lowercases at compare time, resolving the conflict between the design's "normalized per rule 6" and the fixture assertions requiring mixed-case substrings. `_finding_key` still returns a lowercased issue, so the chosen side is byte-identical to before.
- (Ivan) A header carrying Severity and Issue but no File column is treated as not-a-header, implementing "a header missing any of the three contributes no keys" with one predicate.
- (Ivan) The `Ref` separator cell is `-----` (five dashes); no source states it.
- (Ivan) `" | ["` is the replacement data-row filter idiom in `test_consolidate_findings.py`; the dispatch named no replacement because it did not anticipate five further functions breaking on the new leading column.
- (Ivan) "No exception raised" at the CLI boundary is asserted as "no `Traceback` on stderr", since Python exits 1 on an uncaught exception and the expected malformed exit is also 1.
- (orchestrator) `dev/bin/release-checks` ran neither `test_gate.py` nor the new `test_gate_findings_table.py`; both were added to its `[checks] review verbs` block. This is outside the task's declared file list, kept because a new suite outside the release gate is a gap this change would otherwise introduce.
- (orchestrator) Ivan was permitted to update `test_consolidate_findings.py`'s exact-header golden because the `Ref` column deliberately changes that rendered contract; he then widened five further row filters in the same file, two of which were `assert not [...]` checks that the new leading column would have made vacuously true.
- (orchestrator) Pat's cycle-1 prompt measured 60007 bytes against the 50000-byte dispatch budget after the one permitted trim pass (fixture data dropped); dispatched anyway through the sonnet helper-script lane rather than narrowing the reviewer's view of the diff.
- (orchestrator) No CHANGELOG entry for the truncated-row crash fix: the crash existed only in this same unreleased change, which already carries an entry.

## 10: [D1] Tail: make the new tests pin this change, and drop the reformat churn (00256, cycle 1 rework)

- (Ivan, initial) For `test_rename_into_store_from_production_is_not_clean`, used a direct `_dirty_path_is_in_store` call rather than the sibling `test_rename_out_of_store_is_not_clean`'s integration shape (real `git mv` + `reuse_verdict`), because the integration shape could not diverge from base behavior for that direction (verified empirically via a base-worktree overlay) - a direct unit call was the only way to satisfy the "must fail against pre-change code" requirement.
- (Ivan, initial) `test_run_gate_drains_stderr_without_deadlock` is kept as a regression guard even though it passes at base (old `run_gate` used `communicate()`, which is deadlock-safe); documented via comment per the task's own behavior-preserving fallback rule rather than omitted, since the finding named it explicitly.
- (orchestrator) Pat's per-task review (cycle 1 and its delta re-run) raised a MEDIUM claiming `test_run_gate_streams_and_keeps_tail` has no assertion on the drain bound; refuted by direct pytest execution against a disposable base-worktree overlay (the test fails at base, proving the pre-existing `_drain_bounded` spy and its `len(calls[0]["tail"]) <= 4096` assertion are present and effective). Discarded per the reviewer-can-be-wrong rule rather than re-dispatching Ivan on a false claim.

## 11: [D1] Tail: one replay base in review_stage, and the smaller close/stage loose ends (00256, cycle 1 rework)

- (Tess) For the missing-persona lens fail-safe test, reused the existing fixture's default two-persona `agents:` string (alice/bob only, which already omits blake/carl/eve) rather than inventing a new one, since the task only required at least one named persona to be entirely absent.
- (Ivan) Preserved the existing `name: name` fallback in `_lens_states` for an extra/unknown key present directly under `agents:` (not a known persona name), adding the missing-persona fail-safe on top of it rather than replacing that branch.
- (orchestrator) BLAKE's cycle-1 finding that the merge-base step in the extracted `_replay_base` is "a second resolver" is refuted: commit 7b1f589 added it to fix a real regression an earlier task in this same PRD introduced (removing the old `resolve_base()` in favor of a raw, un-anchored scope-recorded branch name, which replays from a branch's moving tip instead of its fork point). Kept the step, moved it into the extraction, and justified it in a one-line comment instead of removing it.
- (orchestrator) `review_stage.py` is 802 lines after this task, 2 over the task's literal "800 lines or fewer" acceptance criterion. The extraction's own overhead (a `def` line plus unavoidable PEP8 2-blank-line separators) cannot net-reduce the file below its pre-task 801-line debt while keeping one line of WHY-comment and the file's existing formatting conventions; the automated regression-only style gate (`check_style_limits.py`, which flags only a diff that pushes a file over 800 from a baseline at or under 800) passes, since the file was already over before this task. Accepted with warning at the 3-cycle per-task review cap.
- (orchestrator) Neither `test_replay_cmd_never_receives_gate_command` nor `test_replay_base_is_branch_point_when_scope_records_a_branch_name` fails if `_replay_base`'s merge-base step is removed: both fixtures only exercise scenarios the since-removed `resolve_base()` would also resolve correctly (verified directly via a disposable base-worktree overlay against pre-PRD commit 540edd9). This is a genuine test-coverage gap for the 7b1f589 regression, not evidence the step is unneeded - no fixture here constructs the divergence between gather-context.sh's own candidate search and a raw, un-anchored branch name. Accepted with warning at the cap; flagged for the batch report rather than left silent.
- (orchestrator) Deferred, out of this task's file scope (SKILL.md not in `Contract.files`): the timed-out gate's fabricated "Tests: 0 passed, 0 failed, 0 skipped" line at `review_stage.py:372` and SKILL.md:203/:254's contradicting hand-append instruction for the bare-repo fallback.
- (orchestrator) Loupe's end-of-turn reflow struck `test_review_close.py` and `test_review_stage.py` twice across this task's turns, each time reformatting dozens of unrelated lines to black-style multi-line call wrapping; reverted both times with a clean rewrite from the last good commit plus the two intended edits, verified via `git diff` against the pre-reflow baseline before each commit.

## 2: _common: read_input fails open on non-UTF-8 and deeply nested payloads (00267)

- (Tess, initial) Pinned stdin to strict UTF-8 via `PYTHONIOENCODING=utf-8:strict` in the new `_run_bytes` helper rather than a `LANG` value, because the bare `PATH`/`HOME` env falls back to the C locale's `surrogateescape` stdin, which hides the non-UTF-8 bug entirely (measured against three envs).
- (Tess, initial) The added "no Traceback in stderr" assertion is within the task's "(no traceback, no exit 1)" wording.
- (Tess, initial) The nested-payload test closes its brackets (`"[" * depth + "]" * depth`) rather than leaving them open, as the task's phrasing allows either.
- (Tess, strengthen) "Denial reason reached stderr intact" is read as the file's `REASON` constant appearing in stderr; the task does not say whether the raw prompt text itself (e.g. a non-ASCII character) must also be echoed, so that was not asserted.
- (Tess, strengthen) The existing `test_reworded_delegations_are_denied` fixture "Run the autopilot:work skill on PRD 00300 and report back." is reused as the known-denied phrasing for the new positive-control tests.
- (Tess, strengthen) For the truncated-multibyte case, the broken bytes are appended after a valid, otherwise-complete denied payload, so the test fails open regardless of whether the eventual fix decodes strictly or with replacement characters.
- (Ivan) The orchestrator corrected the initial implementation (a try/except around text-mode `sys.stdin.read()`) to the task's verbatim contract (`sys.stdin.buffer.read().decode("utf-8", errors="replace")`), since the task named that exact approach rather than leaving it open; both passed the tests, but only the contract-matching form was kept.

## 3: guard_phase_delegation: widen matching predicate for the missed phrasings (00267)

- (Tess) The `_denied()` fixture-count assertion is one line; the duplicate `== 4` inside `test_the_four_observed_delegations_are_denied` must also become `== 17`, or the suite could never pass. The test's stale name ("four") was kept, since renaming wasn't part of the task.
- (Tess, strengthen) "Up to three words" generalizes to other phases/skill names ("plan phase", "design phase", `/autopilot:plan-tasks`, `/autopilot:design-solution`) and other wording ("whole" for "entire"), not only the PRD's literal work-phase examples, since Devon's weak points asked for held-out variants of the same classes.
- (orchestrator) Two of Tess's strengthened cases ("Kick off the design phase" as a held-out verb; "Never forget to run the work phase" as a third negation-exception word) were dropped before committing: the contract pins an exact six-verb list and an exact three-word negation exception (`hesitate|fail|only`), and "kick off"/"forget" are in neither - adding them would have forced Ivan to invent contract beyond what was specified, risking new false positives on the allow corpus the way the over-broad-verb-list exploit (Devon's #5) demonstrated.
- (Ivan, initial) "Up to three words" counts the article as one of the three ("the entire" is 2 of 3), tighter than a reading that adds the gap on top of an article; both pass the given tests.
- (Ivan, initial) The three-word gap applies to the bare-skill pattern as well as the phase-jargon pattern, since the contract says "between the verb and its object" generally, not only for phase names.
- (Ivan, initial) A negation word can never fill a gap-pattern word slot, so "Do not run the work phase" doesn't match from "Do" past its own "not" - unstated by the contract, needed to keep the existing direct-negation tests passing once "do" became a recognized verb.
- (Ivan, initial) `does not` gets the hesitate/fail/only exemption (it contains "not" directly before the exempted word); contractions (`don't`, `won't`, ...) do not.
- (Ivan, review-fix retry) The colon-lead reverse-direction pattern ("`<phase> phase ...: <verb>`") keeps the original six-verb list rather than the widened one - the fix for Pat's confirmed finding that e.g. "Work phase: complete" read as a delegation under the wider list.
- (Ivan, review-fix retry) Only an `autopilot:`-prefixed skill name (with or without a leading slash, backtick, or quote) takes the three-word gap before a bare-skill target; a plain `plan-tasks`/`design-solution` keeps the original `(?:the\s+)?` adjacency - the fix for Pat's confirmed finding that e.g. "call the helper in plan-tasks" read as a delegation.
- (orchestrator) Pat's cycle-2 delta review closed both confirmed MEDIUMs and left 2 LOW findings open (a `_PREFIXED_SKILL`/`_BARE_SKILL` pattern-duplication risk, and no dedicated regression test for the two review-fix behavior changes) - accepted per the LOW-only ladder row rather than spending a third review cycle; flagged in the attempt record for the PRD-level review/batch report.

## Tail: step 7 regression fix on task 2's read_input change (00267)

- (orchestrator) Step 7's full-suite run caught a real regression task 2 introduced: `hooks/test_enforce_prd_location.py`'s `LayoutVocabularyTest` went from 2 passed to 2 failed (exit 0 instead of 2), confirmed against the pre-PRD baseline (76d9b7d) via a disposable git worktree. Root cause: `read_input()`'s `sys.stdin.buffer.read()...` has no `.buffer` to read when `_common.py`'s `capture_main()` swaps `sys.stdin` for an `io.StringIO` (the in-process `hook.run(payload)` test pattern several hooks' test suites use) - the resulting `AttributeError` was silently swallowed by `capture_main`'s own exception isolation, turning a real deny into a false allow.
- (Ivan) Fixed by reading `getattr(sys.stdin, "buffer", None)`: real subprocess stdin still reads/decodes bytes; the `capture_main`/`StringIO` in-process case falls back to `sys.stdin.read()` directly (already `str`, no decode needed). Re-verified both `hooks/test_enforce_prd_location.py` and `hooks/test_guard_phase_delegation.py` green, then the full `dev/bin/release-checks` suite (2620 passed, 0 failed).
