# Decision Audit Log: 00320-refuse-every-unsafe-verify-log-sink-v2

PRD: `00320-refuse-every-unsafe-verify-log-sink-v2.md`
Started: 2026-10-16T17:10:21Z
Completed: 2026-10-16T17:10:21Z
Autonomous: 17  |  Deferred: 24  |  Doubts: 0

### [autonomous] 2026-10-16T17:10:21Z

**Decision**: design review found 5 blockers across 2 reviewer dispatches (resolve()-ordering + duplicate JSON print; parent-dir symlink race; nested-repo exclusion gap; JSON/stderr text mismatch)

**Choice**: fixed all 5 blockers in the design doc before planning: pass log_path unresolved throughout; make the refusal wrapper the sole stderr/JSON printer with one shared message string; pin the open parent via openat-style no-follow traversal; split case 4 into toplevel-containment plus a nested-repo exclusion

**Rationale**: each was a real gap the PRD must-haves require closed; a third codex dispatch (degraded to claude-fallback on a codex hang) verified all fixes hold with zero open findings

### [autonomous] 2026-10-16T17:10:21Z

**Decision**: `test_parent_dir_symlink_swap_is_refused` is weak. The `monkeypatch.setattr(log_sink_refusal, "refuse", ...)` is a no-op, because `_open_log_sink` never calls `refuse`. The test calls `_open_log_sink(sink)` with the default `root=Path("/")`, while production passes the repo root as `root`. `pytest.raises(OSError)` accepts any OSError, including one from a symlinked ancestor of `tmp_path`. Drop the monkeypatch, pass `root=repo`, and assert the specific errno (ELOOP/ENOTDIR).

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-16T17:10:21Z

**Decision**: The changed `test_gate_log_write_failure_degrades_instead_of_crashing` keeps an either-or hedge: `bool(summary["errors"]) or "gate skipped" in summary["gate"]["tests_line"]`. The fail-first replay shows it passes against the pre-change code, so it does not pin the new refusal-before-open behavior. Assert the "gate skipped" branch alone, matching the dirty-result path.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-16T17:10:21Z

**Decision**: Dead scaffolding left over from the red-first task in the new test file. The module docstring still says every refusal test "is expected to FAIL against the current code". The `try: from cli import log_sink_refusal / except ImportError: log_sink_refusal = None` block and the two `if log_sink_refusal is None: pytest.fail(...)` branches can no longer run. Replace the guarded import with a plain `from cli import log_sink_refusal`, delete both branches, and fix the docstring.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-16T17:10:21Z

**Decision**: Git directory identity check misses worktree .git file, allowing verify --log .git to overwrite and corrupt the worktree

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-16T17:10:21Z

**Decision**: Case 4b nested-repo probe is bypassed for the nested repo's own git directory. `_in_nested_repo` treats any failing `git rev-parse --show-toplevel` as "not nested", but git also fails when run inside a `.git` directory (rc 128, "must be run in a work tree"). Confirmed on a fixture: with an ignored nested repo at `docs/dev/tmp/other`, `refuse()` returned None for `docs/dev/tmp/other/.git/config`, `.git/hooks/pre-commit` and `.git/hooks/newhook`. `_open_log_sink` would then unlink and recreate that config, so the "git internals" guarantee does not hold for a nested repo. Fix: also refuse when any ancestor of `resolved` below `toplevel` contains a `.git` entry (or probe `--git-dir`/`--is-inside-git-dir` and refuse on a hit), and add a regression test for the nested `.git/config` path.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-16T17:10:21Z

**Decision**: `test_run_gate_refuses_a_symlinked_log_and_leaves_its_target` was rewritten, and the replay shows it passes against the pre-change code. The pre-spawn dirt scan already refused a symlinked log, so the test does not bind to the new case-3 refusal in `_lock_and_check`. Its own comment says the tracked and direct cases moved to the new file. Either add an assertion that only the new code satisfies (for example `dirty_paths` naming the target via `_log_rel_and_tracked`), or note that the test pins existing behavior.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-16T17:10:21Z

**Decision**: An absolute `--log` outside the repo that has a symlinked ancestor gets the wrong reason text. `/etc/hosts` prints "is a symlink" instead of "resolves outside the repository", so a log pointed at another repo under `/tmp` (a symlink to `/private/tmp` on macOS) is reported as a symlink. `_symlinked_component` climbs above the repo root for such paths, but the spec limits the symlink check to ancestors below the toplevel. Exit code 2 and the no-write guarantee still hold. Only the reason text deviates, and the test uses a relative path so it does not catch this.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-16T17:10:21Z

**Decision**: Several carried-over tests assert less than the spec and the acceptance text require. `test_git_dir_identity_holds_from_a_subdirectory_cwd` checks only that `git status` ran (`returncode == 0`), so neither the reason text nor an unchanged status is checked. The hard-link, default-sink, FIFO, executable, outside-toplevel and other-repo-store tests check exit 2 and bytes but not the stderr reason or the JSON line. A wrong reason string, such as the one above, would go unnoticed.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-16T17:10:21Z

**Decision**: Case 2 falls open on a git-probe failure: `probe = _log_rel_and_tracked(repo_root, log_path)` returning `None` is treated as "untracked", but the design's case 2 requires "a `None` from a git failure fails closed as 'resolves outside the repository'"; with `_toplevel` already succeeding, the only `None` whose path is still inside the toplevel is an `ls-files` OSError, and such a path then clears cases 4-6 and the tracked sink gets truncated — fix: after computing `resolved`/`toplevel`, `if probe is None and resolved.is_relative_to(toplevel): return _OUTSIDE`

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-16T17:10:21Z

**Decision**: Case 3's component walk is not bounded to the repository as its own docstring claims ("any component ... BELOW the repository"): it stops only at `repo_root`, `toplevel` or the filesystem root, so an out-of-repo or differently-spelled sink is walked up through `/`, returning "is a symlink" for a symlinked ancestor outside the repo (macOS `/tmp`, an unresolved `/var`) instead of "resolves outside the repository" — `test_verify_refuses_a_store_like_path_outside_the_repo` and `test_verify_refuses_an_absolute_out_of_repo_log` assert that exact tail, so the pair is environment-fragile; fix: run the `resolved.is_relative_to(toplevel)` containment test before `_symlinked_component`, or return early from the walk when `log_path` is not under `repo_root`

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-16T17:10:21Z

**Decision**: `_open_log_sink(log_path, root: Path = Path("/"))`'s default has no production caller (`_run_locked_gate` always passes `cwd`); the only consumer is the test above, i.e. speculative generality on the security-critical open, and it is the reason that test exercises a non-production configuration — fix: drop the default and make `root` required once the test passes `repo`

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-16T17:10:21Z

**Decision**: In `_identity_targets`, `Path(repo_root) / probe.stdout.strip()` wraps something that is already a `Path`. Use `repo_root / probe.stdout.strip()`.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-16T17:10:21Z

**Decision**: The refusal JSON line's "log": None field is not asserted by any changed test (R18)

**Choice**: routed to verification

**Rationale**: queued in 00320-...-checks-1.json as `rg -n '\["log"\] is None' skills/run-autopilot/cli/test_cli_verify_verb.py skills/run-autopilot/cli/test_verify_truth.py`; the check runs in the work phase step-7 pass, so no task was created

### [autonomous] 2026-10-16T17:10:21Z

**Decision**: meta/assumptions.md was replaced wholesale, deleting the previous PRD loop-truth-tests entries (R4)

**Choice**: routed to verification

**Rationale**: queued in 00320-...-checks-1.json as `rg -n assumptions skills/run-autopilot/SKILL.md skills/run-autopilot/references` to settle whether the skill specifies replace-per-PRD or append; the check runs in the work phase step-7 pass, so no task was created

### [autonomous] 2026-10-16T17:10:21Z

**Decision**: Bob/codex refused for lack of input twice (sandbox_apply: Operation not permitted before its first read, then an inlined 185 KB retry that exited writing nothing); the engram context pack also failed (readonly database under the seatbelt)

**Choice**: degraded and continued with the doubt lens rescued

**Rationale**: Safety Checks row 4: a transient reviewer failure is logged and the cycle continues on the reviewers that succeeded. The doubt lens was re-dispatched as a Claude subagent on Bob's exact assembled prompt and produced the full contract (FIX/VERIFY/KNOWN, every R{n}, D1-D5), so the lens did not drop. The pack failure left every reviewer without the Findings-precedent section: degraded, not invalid.

### [autonomous] 2026-10-16T17:10:21Z

**Decision**: Bob's finding lines arrived bullet-prefixed (- [BOB] ...), which consolidate_findings.py's anchored line regex (^\[) drops silently; his 13 findings were absent from the first consolidation

**Choice**: stripped the bullet prefix and re-consolidated; flagged for its own PRD

**Rationale**: no content was changed, only the line prefix. Consensus moved on re-run (R1 went 2/4 to 3/4) and six of Bob's findings became fix tasks, including the two sharpest correctness findings of the cycle (fail-open on a git-probe None, unbounded symlink walk). A doubt lens whose findings vanish into a regex is the silent-drop failure consolidation exists to prevent, and it is a product defect in the pack, not in this PRD.

### [deferred] 2026-10-16T17:10:21Z

**Decision**: File test_review_stage.py exceeds the 800-line limit (805 lines)

**Rationale**: deferred by review-close

### [deferred] 2026-10-16T17:10:21Z

**Decision**: Additions beyond the PRD. `_in_nested_repo` refuses a sink inside any nested git repository. `_open_log_sink` takes an extra `root` parameter. The test file has three tests the spec does not name: `test_parent_dir_symlink_swap_is_refused`, `test_nested_repo_store_is_refused` and `test_symlink_above_repo_root_does_not_refuse_default_sink`. The nested-repo refusal is a fair reading of "outside the repository" but is not stated.

**Rationale**: deferred by review-close

### [deferred] 2026-10-16T17:10:21Z

**Decision**: `_lock_and_check` folds every refusal reason into a dirty result, where the spec names only tracked and symlinked sinks. It is a safe superset. The "tracked" test is `git ls-files --error-unmatch`, which checks the index, not HEAD, as the spec literally says.

**Rationale**: deferred by review-close

### [deferred] 2026-10-16T17:10:21Z

**Decision**: `_descend` creates missing parent directories before opening the sink. That is only reached after the refusal passes, so it is not a hole, but the gate path now makes directories.

**Rationale**: deferred by review-close

### [deferred] 2026-10-16T17:10:21Z

**Decision**: Fail-first replay: `test_run_gate_streams_stdout_and_stderr_to_the_log` and `test_held_gate_lock_blocks_before_the_log_open_and_record_delete` pass against the pre-change code — out of scope as findings: both were only relocated from a `tmp_path_factory` sink into `docs/dev/tmp` because case 4 now refuses an out-of-repo sink, and they are pre-existing regression tests, not this PRD's behavior pins

**Rationale**: deferred by review-close

### [deferred] 2026-10-16T17:10:21Z

**Decision**: Fail-first replay: `test_run_gate_refuses_a_symlinked_log_and_leaves_its_target` passes at base — out of scope: it is the surviving `symlink` arm of a deleted parametrize whose behavior was already correct at base, and its tracked arm moved to `test_verify_log_refusal.py::test_run_gate_refuses_tracked_log_without_opening` (which is red at base)

**Rationale**: deferred by review-close

### [deferred] 2026-10-16T17:10:21Z

**Decision**: Fail-first replay: `test_untracked_tmp_log_still_records` passes at base — out of scope: the PRD and design both state this happy-path test must already pass at the task's base commit

**Rationale**: deferred by review-close

### [deferred] 2026-10-16T17:10:21Z

**Decision**: A CLI `verify` run now executes `log_sink_refusal.refuse` twice (pre-flight plus inside the lock), each pass spawning ~6 `git` subprocesses, so a gate run pays ~12 extra probes — out of scope: both enforcement points are a PRD Must-have ("a library caller cannot bypass the CLI"), and caching across the flock boundary would reintroduce the TOCTOU the second check exists to close

**Rationale**: deferred by review-close

### [deferred] 2026-10-16T17:10:21Z

**Decision**: R13: two changed files exceed the 800-line limit — `skills/run-autopilot/cli/__main__.py` (~1975 lines, last function at 1968) and `skills/run-autopilot/cli/test_review_stage.py` (~802, last function at 786+16) — out of scope: both were already over before this diff, which adds ~15 and 2 net lines respectively; splitting them is its own PRD (the same precedent that split `verification.py`/`dirty_tree.py` under 00311), and the new files this PRD adds are well inside the limit (log_sink_refusal.py 133, test_verify_log_refusal.py 374, verification.py ~742)

**Rationale**: deferred by review-close

### [deferred] 2026-10-16T17:10:21Z

**Decision**: A `.git` file with a RELATIVE `gitdir:` pointer is still not refused. `_worktree_gitdir_pointer` returns the pointer unresolved, so `os.path.samefile` resolves it against cwd, raises, and the `continue` swallows it; reproduced on a submodule and on a `worktree.useRelativePaths` worktree. `_open_log_sink` would unlink and recreate that `.git` file. Fix: anchor a relative pointer on `resolved.parent`, plus a regression test.

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-16T17:10:21Z

**Decision**: The nested-repo refusal is locale-dependent and fails open: `_in_nested_repo` matches the English git message `"work tree" in probe.stderr` and `dirty_tree._git` pins no locale, so under a translated LC_ALL the probe failure reads as "not nested". Fix: use `git rev-parse --is-inside-git-dir`, or pin LC_ALL=C.

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-16T17:10:21Z

**Decision**: The nested-`.git` refusal still misses a path whose parent directory does not exist yet (`nested/.git/refs/heads/newdir/ref`, `.git/hooks/sub/x`, `.git/objects/zz/yy` all return None): `_git(resolved.parent, ...)` raises FileNotFoundError and that reads as "no nested repo". Fix: lexical ancestor walk for a `.git` entry below toplevel.

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-16T17:10:21Z

**Decision**: `_worktree_gitdir_pointer` slurps the whole candidate file with `read_text()` to test a 7-byte prefix, on every existing regular-file sink, twice per verify run. Fix: read a bounded binary prefix.

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-16T17:10:21Z

**Decision**: Case-order deviation: containment (case 4) runs before the symlink walk (case 3), so a symlink resolving outside the toplevel reports `resolves outside the repository` instead of `is a symlink`. Refusal and exit 2 unchanged; no test covers the shape.

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-16T17:10:21Z

**Decision**: `test_cli_refuses_symlinked_log` only plants a symlink to an untracked in-repo target, so the reason-text overlap above is unpinned.

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-16T17:10:21Z

**Decision**: Refusal behaviour beyond the spec's case list: the worktree gitfile pointer check, the nested-repo stderr-sniffing probe, and seven tests beyond the PRD's fourteen.

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-16T17:10:21Z

**Decision**: The two tests added for this cycle's refusal gaps assert only `result is not None`, so a refusal for the wrong reason still passes. Fix: assert the exact reason string (also in `test_cli_refuses_git_dir_log`).

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-16T17:10:21Z

**Decision**: `test_run_gate_refuses_a_symlinked_log_and_leaves_its_target` binds case 2 (tracked), not the case 3 its rewritten comment claims, because its symlink target is committed. Fix: retarget the link at an untracked in-repo file, or correct the comment.

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-16T17:10:21Z

**Decision**: `test_absolute_log_outside_repo_via_symlinked_ancestor_reports_outside` and `test_symlinked_ancestor_component_walk_is_bounded_to_the_repo` pin the same ordering; keep one or differentiate the second.

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-16T17:10:21Z

**Decision**: `_pinned_parent_fd` raises a bare OSError for an absolute `--log` spelled through a different root than `--repo-root`, producing exit 2 with a JSON line that lacks the stated `{"error","exit","log":null}` shape.

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-16T17:10:21Z

**Decision**: Residual check-then-act: a leaf swapped between the refusal and `os.unlink(leaf)` is deleted (not written through). Minor and recoverable; the exclusive no-follow open closes the write hole.

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-16T17:10:21Z

**Decision**: The `gitdir:` pointer loop compares against every `_identity_targets` entry including the store, where it can only ever yield the wrong reason text. Restrict it to the two git-dir targets.

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-16T17:10:21Z

**Decision**: Stale comment left by the cycle-1 R2 fix: it still describes the removed either-or while the assertion below pins the `gate skipped` branch alone.

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-16T17:10:21Z

**Decision**: Two tests pin the identical containment early return with the same fixture and assertion; one is redundant.

**Choice**: deferred to batch end

**Rationale**: rework cap reached with this finding unresolved
