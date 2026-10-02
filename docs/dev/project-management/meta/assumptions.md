# Assumptions ledger — PRD 00236 (replan pass, batch 202610021244)

## Task 1 — STORE_GITIGNORE / ensure_store_gitignore

Tess (tests):
- `crlf` expects False because the contract names `read_text(encoding="utf-8")` as the comparison and that call translates CRLF to LF (verified against a reference implementation).
- `invalid-utf8` and a mode-0 file accept either a raise or a write, since the contract's error clause covers OSError only and a mode-0 file cannot be rewritten in place.
- A missing `store_dir` accepts either a raise or create-and-write; only a silent False is rejected (the contract says creating the dir is not required).
- The untouched store files used as witnesses (`decisions.md`, `autopilot/state.json`) are test fixtures; the contract names no required store contents.
- `ensure_store_gitignore` returns a real `bool` (tests use `is True` / `is False`).
- The tests pre-create `store_dir`, matching the brief's note that creating it is not required.
- Treated loupe's end-of-turn reflow of `test_store_tree.py` as the repo's own formatter and kept it.

Ivan (implementation):
- The CRLF row expects `wrote is False`, so the comparison reads with `Path.read_text` rather than comparing raw bytes.
- `missing-store-dir` creates the store directory rather than raising; the test tolerates either.
- The unreadable-file case is allowed to raise PermissionError from the write; no fallback added.

## Task 2 — the ensure-store verb and the enter wiring

Tess (tests):
- A from-empty batch (`enter()` with no `state.json`, a PRD in `wip/`) halts at stop `batch_init`, since `state.init` writes no `batch` key; confirmed empirically.
- `enter`'s call passes `prds_dir.parent` as a plain unresolved `Path`, so recorder equality against `env.pm` holds; same for the verb's `state_path.parent.parent`, since `_resolve_state_path` does not resolve.
- stdout silence is asserted only for the open-batch enter case, not for the halting arrangements, to avoid pinning print behavior the contract never states.
- The printed line is the absolute path as formed from `--state` (no `.resolve()`), compared as `Path(stdout.strip())`.

Ivan (implementation):
- `ensure-store` takes only an optional `--state` and resolves a missing one through the same `_resolve_state_path` walk-up as every other verb.
- `print(path)` of a `Path` is the intended one-line output format.
- The gitignore call belongs inside `_prepare_tree` after the mkdirs, so it runs once per `enter()` before the state bootstrap and on every arrangement including `drained`.
- Suppressing only `OSError` is sufficient; nothing else escapes `ensure_store_gitignore`.

## Task 4 — the phase-build.md lifecycle step

Ivan (implementation):
- Kept the existing word "below" in "the instructions below stay the hand-run reference" rather than retargeting it, since the task asked only to keep that line true and this is the minimal change.

## Task 5 — the rotation and task-boundary handoff sites

Ivan (implementation):
- The pre-existing pin `test_handoff_placement_prose.py::test_leave_row_is_the_last_write_before_the_stop` asserts the literal substring "last write before the stop" in step 3h, so kept that substring and qualified it ("the last write before the stop that touches state") instead of rewording to "last state write".
- Step 3e spells the verb as the full `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-autopilot/cli/__main__.py dirty ...` invocation, matching step 3h's own lines and the pack's uniform idiom.
- Avoided the words `status --porcelain` in the file entirely (wrote "a raw whole-tree check") to stay clear of the later prose pin.

## Task 6 — fast-track's dirty-path sites

Ivan (implementation):
- Future prose pins are assumed to match `dirty --state` (or `autopilot dirty`) as a substring, not the full un-wrapped invocation.
- `<state.json>` is the placeholder spelling at both sites.
- The "it skips the store" clause at the worktree bullet is a short clause, not a new paragraph.

Orchestrator: reverted Ivan's 80-col wrapping of the two `dirty --state` invocations so each command stays on one line, per the pack's commands-on-one-line rule.

## Task 7 — the prose-pin suite

Ivan (implementation):
- Flag shape: any `.md` line containing `status --porcelain` / `status --short` must be allowlisted, rather than classifying "gate framing" semantically. Strictly stronger than the contract asked, and it passes today.
- Stale allowlist entries are tolerated (no unused-exemption assertion), trading audit strictness for reword tolerance.
- `.md` under `skills/` means recursive, with the golden-fixture directory excluded by a parent check.

## Task 8 — the release-checks block and the CHANGELOG entry

Ivan (implementation):
- Placed the new CHANGELOG bullet after the existing `pytest-xdist` bullet and omitted a trailing period, matching the section's first bullet rather than the period-carrying xdist bullet.
- Copied `[checks] enter`'s serial invocation shape literally and added no explanatory `# serial:` comment.

## Task 9 — derive the store boundary from the work-tree

Orchestrator (contract resolution):
- Task 9 says "make `foreign_dirty` not raise" while task 12 requires `_run_dirty` to return a distinct exit code for a failed probe; the two cannot both hold if a failed probe returns a value. Resolved as a typed `StoreGitError`: no raw subprocess traceback escapes (task 9's intent), and task 12 has something to catch. A `foreign_dirty` that returned `[]` on a broken probe would make every refusal gate pass on a failed check, which is the worse failure for a safety gate.
- The derivation reads the store directory the caller already holds rather than asking git: `git rev-parse --show-prefix` was measured to return the empty string at the work-tree root even in the nested layout, so git cannot report where the store is.

Tess (tests):
- `state.json`'s work-tree key is top-level `repo_root` (string), pinned only by `custody.repo_and_git_dir`'s docstring.
- `StoreGitError` carries git's stderr for a `CalledProcessError` (not just `str(err)`) and is raised with `raise ... from err`, so `__cause__` is the original exception.
- `record_store` keeps today's call shape (`add`, `diff --cached` emptiness probe, `commit`, `rev-parse`), returns the full 40-char sha, and keeps the `chore(autopilot): record <site> state for <prd>` subject.
- Two genuine collapsed store ancestors cannot co-occur in one `git status` output, so the "keeps classifying after one expansion" case uses an ancestor plus a sibling collapsed directory instead.
- Nested-store prefixes may be deeper than one level (`a/b/docs/dev/project-management`).

Ivan (implementation):
- `_store_prefix` returns `""` for any `store_dir` it cannot place inside `repo` — wrong tail, outside the repo, a name-extending sibling, or an `OSError` from `resolve()`.
- Only untracked entries ending in `/` are candidates for the scoped re-listing, so an untracked *file* whose name prefixes a store root costs no extra probe.
- The expansion probe needs no recursion, since `--untracked-files=all` yields only leaf paths.
- `loop.py` / `loop_act.py` pass `ap_dir.parent` as the store dir; neither has a handed test covering it (the orchestrator's stub edit now pins it).
- `store_git` in `loop_act.py` keeps its two-tuple return; the store dir is computed at the call sites.

## Task 10 — keep store commits out of lane routing and wave lanes

Orchestrator (contract resolution):
- The lane signal is the existing `_AUTOPILOT_REVIEW_SLOTS_DIR` that `wave launch` sets on every lane loop (and `runner.child_env` passes down), not a new marker file or a linked-worktree probe.
- The exclusion is a git `:(exclude)` pathspec on both of `diff_signal`'s reads, with `cwd=repo_root`, rather than a Python filter: a filter would leave the diff body unscanned and `--work-tree` does not anchor a relative pathspec.
- The loop gate also requires `decision["state_touched"]`, not `signal == "continue"` alone: `_decide_died` turns the first death into a `continue`, so the single condition would have recorded the store after a dead session, against the task's own acceptance criterion.
- `done` keeps no per-iteration record; the drained exit's own `"drained"` record covers that iteration.

Tess (tests):
- The lane loop's env sets both `_AUTOPILOT_REVIEW_SLOTS_DIR` and `_AUTOPILOT_REVIEW_SLOTS`, mirroring `wave_launch._spawn_lane`; only the dir's identity is pinned.
- `docs/scripts/tool.py` is the production-path-under-`docs/` case (verified against `lane.is_production_path`), and `docs/dev/project-management/{notes,log}.md` carry the synthetic `password: hunter2` secret.
- The hand-off phases parametrized for a progressing session (`plan`, `design`, `build`, `verify`, `review`) are all valid `next_phase` values; `routing.route` sends unknown ones down a default branch.
- The store dir is compared resolved, because `_walk_up.find_autopilot_dir` resolves symlinks (`/private/var` vs `/var` on macOS); `None` is still rejected outright.
- `"state_write_failed"` is left uncovered rather than guessed at, and weak point 4's surviving shortcut is unobservable through the contract so no argv assertion was added.

Ivan (implementation):
- `store_git(ap_dir)` moved inside the gate in `loop.py` (nothing needs the runner when no record happens) but stays before the archive in `loop_act.py`, where it must read the live state; tests pin neither.
- `_git_output`'s new `cwd` is a required positional, since both call sites have one.
- No `WAVE_LANE_VAR` constant: the variable name is spelled once, inside `in_wave_lane`.

## Task 11 — record the store on the review-once exit path (rework, cycle 1)

Tess (tests):
- The task description's example "any phase `routing.route` accepts, e.g. `review` or `build`" is inaccurate against the actual code: `_one_shot_phase` only lets `next_phase` values `review` or `done` through the one-shot gate. Used `next_phase="review"` for the initial state (matching the existing `run_once` precedent tests), with the scripted session itself handing off to `"build"` as its next phase.
- Used the existing `_progress_step("p.md", "build")` helper rather than inventing a new one or importing a sibling helper from `test_loop_review_once.py`, to keep the change surgical to one file.
- Did not add assertions about the `repo`/`run_git`/`store_dir` shape of the `review_once` call (the way the "loop"/"drained" sites' dedicated tests do) — out of scope per the task's simplicity instruction to test only the two named behaviors.

## Task 12 — store failures legible: dirty's exit codes, gitignore write errors, ignored-store recording (rework, cycle 1)

Tess (tests):
- Followed rule 10a literally: tests assert the dirty-failure exit code is a new value outside {0, 1}, never pin it to exactly 2 or 5 — the task left that choice to the implementer.
- For the "any other exception type" phrase in the dirty finding, used `store_tree.StoreGitError` (the one `_status`/`foreign_dirty` are documented to raise) plus a plain `RuntimeError` (a broader catch than `except StoreGitError` alone, since `_status` only wraps `OSError`/`subprocess.SubprocessError` into `StoreGitError`). Did not add a third case routing a real `subprocess.CalledProcessError`/`TimeoutExpired` through a fake git at the CLI layer, matching every existing CLI-level test's convention of mocking at the `store_tree.foreign_dirty`/`record_store` boundary.
- Blocker/gap flagged rather than silently worked around: finding #2's text says "Pin it in the existing survives-a-failing-write tests," implying a pre-existing test suite for `ensure_store_gitignore` write failures. Tess's authorized file scope (the three production files plus one sample test file) did not include `test_store_gitignore.py`/`test_store_boundary.py`/`test_store_lane.py`, where such a test might already live, so she added new standalone equivalent-coverage tests instead of opening those files.
- Used `monkeypatch.setattr(store_tree, ...)` (mocking the `store_tree` seam) rather than real chmod-based permission failures for the two gitignore-write-failure tests, to avoid OS-permission-model flakiness across environments.

Ivan (implementation):
- Exit code 13 was free to pick (tests only assert it's not 0/1 and that it's documented); chose the next sequential unused integer after the existing 0-12 table, matching the file's own numbering convention. Pat's review (LOW) noted the task text suggested reusing 2 or 5; accepted 13 as a documented deviation rather than reworking.
- `_run_dirty`'s new except tuple reuses the exact `(OSError, RuntimeError, subprocess.SubprocessError)` shape from `record_store`'s precedent per the architecture note, even though the two test cases alone only require catching `RuntimeError` (`StoreGitError` subclasses it) — kept for consistency with the documented reuse-this-shape guidance.
- Placed the new `dirty` Subcommands docstring entry immediately before `record-store`, matching the `_SUBCOMMANDS` dict's registration order (`mint-stubs`, `dirty`, `record-store`, `ensure-store`), since the existing docstring list order isn't strictly alphabetical and this was the closest observable convention.
- The ignored-store match is a literal substring of git's English stderr ("ignored by one of your .gitignore files"); Pat's review (LOW) noted a localized git would miss it. Accepted as-is — matches the git this pack already assumes elsewhere.

## Task 13 — make the new store tests able to fail (rework, cycle 1)

Ivan (implementation, clusters 1/2/4/5):
- The ONE_LANE fixture in `test_wave_launch.py` never trips `foreign_dirty`'s nested collapsed-untracked-directory probe (verified empirically with a scratch git repo), so cluster 2 only needed to pin the single `-z` call, not an additional nested-probe assertion.
- For cluster 4, "a real temporary git repository" means using `store_tree.record_store`'s default `run_git` (which shells out to real `git`), not a custom stand-in.
- For cluster 5's docstring, the exact added wording was left to Ivan's judgment since the task only specified the required meaning, not exact phrasing.
- For cluster 1's `test_wave_review.py` diagnostic-exclusion check, "store-prefixed path" in the assertion refers to the two concrete `STORE_FILES` paths that test's own setup makes dirty, not every possible store-prefixed path in the abstract.
- Treated `test_wave_assemble.py` and `test_wave_launch_refusals.py` as already satisfying cluster 1 in full (no edits needed) — confirmed by the orchestrator against the real code (added by an earlier task-3 commit, outside this task's own diff) before accepting.

Ivan (implementation, style-gate split of the oversize test_store_tree.py):
- The split-by-"function/behavior under test" instruction maps to the original file's own comment-delimited sections (foreign_dirty, record_store, CLI wiring, custody.repo_and_git_dir, STORE_GITIGNORE) rather than an arbitrary equal-size cut.
- A shared `store_tree_testutil.py` (non-test module) is the right home for helpers used by 2+ of the split files, following the existing `loop_testutil.py`/`custody_testutil.py` convention; helpers used by only one file were kept local to that file.
- Deleting the original `test_store_tree.py` (via `git rm`) rather than leaving it as an empty stub, since the content is fully relocated.
- Reverted an unrelated whitespace-only reflow that appeared on `store_tree.py` mid-task (a formatter pass, not Ivan's own edit) — out of scope, so `git checkout --` restored it.

Orchestrator (review follow-up): Pat's per-task review reported two CLOSURE verdicts unresolved because this task's own diff never touches `test_wave_assemble.py` / `test_wave_launch_refusals.py`. Verified directly against the code: both files already carry the required store-only positive control (`test_assemble_ignores_a_tree_dirty_only_inside_the_store`, `test_launch_ignores_a_tree_dirty_only_inside_the_store`), added by an earlier commit (`2aa0737`, task 3 of this same PRD) that predates this task's diff range. Accepted both findings as already resolved rather than dispatching Ivan to duplicate existing coverage. Two LOW findings (a private-helper import naming nit; no explicit base-replay note for the docstring-only writer fix) noted, not actioned.

## Task 14 — pin the cap-rotation and task-boundary record-store instructions (rework, cycle 1)

Ivan (implementation):
- The absolute path to `cli/__main__.py` is derived at call time from the hook script's own `__file__` location (two directories up, then into `cli/`); inlined as a local variable in `_rotation_instructions` rather than a module-level constant, since it has exactly one call site.

Orchestrator (dispatch-time contract resolution): the task's own text left the target runnable-invocation shape unstated beyond "every other site in the pack spells the full `python3 .../cli/__main__.py ...` form" — resolved it concretely before dispatching Tess (assert `python3 `, `cli/__main__.py`, `record-store`, the phase-specific `--site`, and `--prd` as substrings, not a hardcoded full path) so the red test and Ivan's fix targeted the same contract. Pat's review (4 LOW, 0 unresolved CLOSURE) flagged: the task-boundary-handoff test only orders `handoff` before `record-store` without also bounding it before STOP; the runnable-invocation check doesn't verify the extracted path actually resolves on disk; the two phase tests are near-duplicates a parametrize would collapse; and the task-boundary-handoff pin locks in the same bare non-runnable form the task fixed elsewhere. All four noted, not actioned (LOW, carried to PRD-level review per the lean pipeline's retry rule).

## Task 15 — collapse the duplicated store git-runner closure into one (rework, cycle 1)

Orchestrator (dispatch-time contract resolution): the task text left the shared function's exact home and shape unstated beyond "better... move it next to `git_argv` in `cli/custody.py`" — resolved concretely before dispatching Tess: a new `custody.store_git(ap_dir: Path) -> tuple[Path, object]`, with `loop_act.py` re-exporting it as `store_git = custody.store_git` (so `loop.py`'s existing `from cli.loop_act import ... store_git` keeps resolving unchanged) and `__main__._store_repo` delegating to it. Also resolved: the new function must keep using `store_tree.GIT_TIMEOUT_SECS` for its timeout, not custody's own same-valued-but-distinct `GIT_TIMEOUT_SECS` constant, since the task calls this behavior-preserving rather than constant-consolidating.

Ivan (implementation): no assumptions reported — the architecture context fully specified the target shapes (signature, re-export form, which constant to use), so nothing was guessed.

Pat's review: all 3 duplicate-closure CLOSURE verdicts resolved. 2 LOW findings noted, not actioned: the moved `store_git` docstring dropped the loop_act original's "resolve while state.json is still live - once archived, the bare git dir is lost" invariant note; and the `store_git = custody.store_git` re-export is a plain name bind at import time, so a test that monkeypatches `custody.store_git` would not reach a `loop_act.store_git` caller (today nothing does; flagged for future awareness).

## Task 16 — store-tracking cleanups: dead except arm, stale docstring, SKILL.md dirt site, gitignore literal (rework, cycle 1)

Orchestrator (dispatch-time contract resolution): the task left two items' exact target wording unstated beyond intent - resolved both before dispatching Tess: item 2's docstring fix reads `"""...or \`repo\` has any uncommitted change outside the store (store churn is exempt)."""`; item 3's SKILL.md addition is one appended sentence, `"A store write (state.json, a ledger append, a review file) is never foreign dirt here: \`autopilot dirty\` is store-exempt, and that is the check this rule means."`, placed in the same paragraph right after the existing "Any other dirty path is foreign" sentence, which stays verbatim. Also resolved for item 1: `record_store`'s try block never raises `StoreGitError` (a `RuntimeError` subclass raised only elsewhere in the module), so dropping bare `RuntimeError` from the except tuple changes nothing it actually catches - confirmed by reading the function, not assumed.

Tess (tests): corrected a wrong premise in the dispatch for item 3 - the dispatch said the test file already loads `skills/work/SKILL.md`'s text as `_TEXT`; this is false (`_TEXT` is `skills/run-autopilot/SKILL.md`, the pack skill, not `skills/work/SKILL.md`). Verified by reading the file and added a new `_WORK_SKILL_TEXT` module-level constant instead, following the file's existing `_HANDOFF`/`_HANDOFF_TEXT` pattern.

Ivan (implementation): no assumptions reported - all four fixes had exact target text in the architecture context.

Pat's review: all 3 CLOSURE verdicts resolved. 4 LOW findings noted, not actioned: (1) a claim that the porcelain-gate suite was never run during verification - verified false: the recorded verification command explicitly included `test_store_tree_prose.py`, and `test_no_gate_parses_porcelain_by_hand` passed within it (re-confirmed standalone); (2) a preference to reword the SKILL.md carve-out as "Any other path `autopilot dirty` reports is foreign" instead of the appended-sentence form - a style preference, not a defect, and changing it now would re-open an already-closed finding; (3) and (4) two suggestions to drop the new structural/docstring-text tests (items 4 and 2) as pinning style rather than behavior - kept, since each is exactly what makes its finding checkable (BOB's and ALICE's findings were about the source/docstring text itself, not a byte-level behavior already covered elsewhere).

## Step 7 regression fix (task 13, attempt 2) — stale release-checks reference

Orchestrator: `bash dev/bin/release-checks` (the repo's documented definition-of-done gate, README.md) failed at its "[checks] store tree" block with `ERROR: file or directory not found: skills/run-autopilot/cli/test_store_tree.py` - task 13's earlier style-gate split (this same cycle) deleted that file and replaced it with five focused modules but never updated this script's reference to it, and `set -euo pipefail` meant the script aborted before any later block (including "[checks] enter" and "[checks] gather-context paths") ran at all. Re-opened task 13 per step 7's "Handling failures" procedure, dispatched a narrow Ivan fix (`dev/bin/release-checks` only) swapping the one deleted path for the five replacement paths and leaving every other line untouched, then re-ran the full script from the top: all blocks green end to end (`391` lines of PASS/passed output, 0 failures). Re-synced task 13 with a second attempt entry recording this fix.
