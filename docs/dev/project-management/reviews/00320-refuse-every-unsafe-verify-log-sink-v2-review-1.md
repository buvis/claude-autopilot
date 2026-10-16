---
prd: docs/dev/project-management/prds/wip/00320-refuse-every-unsafe-verify-log-sink-v2.md
review: 1
date: 2026-10-16
head_sha: c2bf610d6ac4b832a70599f8ee6dca71a251e48c
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
dispatch_rows:
  bob: e6484980
  carl: 59d0577a
---

# Review: 00320-refuse-every-unsafe-verify-log-sink-v2

Diff range: `7b47b02c5315ac02d8870e4002b6bcc9d6b8d821..c2bf610d6ac4b832a70599f8ee6dca71a251e48c`

codex_rung_guard: not fired

Cycle 1, full review. Engine: `legacy` (single consensus subagent).

Degradations this cycle, named loudly:

- **pack: failed** (`engram pack exit 1: sqlite3.OperationalError: attempt to write a readonly database`). The engram index lives outside the seatbelt's writable roots, so no Findings-precedent section reached any reviewer. The review is degraded in that one respect, not invalid.
- **Bob ran as the Claude doubt-lens fallback, not codex.** His codex run refused for lack of input (`sandbox_apply: Operation not permitted` before its first read) and emitted a `Cannot statically verify` placeholder with every `R{n}` failed. The one sanctioned inlined retry (185 KB prompt, context + diff inlined verbatim) ran and exited without writing any review. The lane was then stopped and the doubt lens re-dispatched as a Claude subagent on Bob's exact assembled prompt; that run produced the full contract (FIX/VERIFY/KNOWN, every `R{n}`, D1-D5) and is what this file records as Bob's. The doubt lens did not drop.
- Bob's finding lines arrived bullet-prefixed (`- [BOB] …`), which `consolidate_findings.py`'s anchored line regex drops silently. The prefix was stripped and consolidation re-run; his 13 lines are in the table below. **No content was changed.** Worth its own PRD: a doubt lens whose findings vanish into a regex is exactly the silent-drop failure consolidation exists to prevent.

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [3/4] | 🟡 | `test_parent_dir_symlink_swap_is_refused` is weak. The `monkeypatch.setattr(log_sink_refusal, "refuse", ...)` is a no-op, because `_open_log_sink` never calls `refuse`. The test calls `_open_log_sink(sink)` with the default `root=Path("/")`, while production passes the repo root as `root`. `pytest.raises(OSError)` accepts any OSError, including one from a symlinked ancestor of `tmp_path`. Drop the monkeypatch, pass `root=repo`, and assert the specific errno (ELOOP/ENOTDIR). | skills/run-autopilot/cli/test_verify_log_refusal.py:508 | 1 | ALICE, BOB, CARL |
| R2 | [2/4] | 🟡 | The changed `test_gate_log_write_failure_degrades_instead_of_crashing` keeps an either-or hedge: `bool(summary["errors"]) or "gate skipped" in summary["gate"]["tests_line"]`. The fail-first replay shows it passes against the pre-change code, so it does not pin the new refusal-before-open behavior. Assert the "gate skipped" branch alone, matching the dirty-result path. | skills/run-autopilot/cli/test_review_stage.py:299 | 2 | ALICE, BOB, mech-check |
| R3 | [2/4] | 🟡 | Dead scaffolding left over from the red-first task in the new test file. The module docstring still says every refusal test "is expected to FAIL against the current code". The `try: from cli import log_sink_refusal / except ImportError: log_sink_refusal = None` block and the two `if log_sink_refusal is None: pytest.fail(...)` branches can no longer run. Replace the guarded import with a plain `from cli import log_sink_refusal`, delete both branches, and fix the docstring. | skills/run-autopilot/cli/test_verify_log_refusal.py:1 | 1 | ALICE, BOB |
| R4 | [2/4] | ⚪ | `meta/assumptions.md` was replaced wholesale. The previous `## 1: loop-truth-tests` assumption entries from an earlier PRD are deleted, not archived. Confirm this reset is intended. | docs/dev/project-management/meta/assumptions.md:1 | general | ALICE, BOB |
| R5 | [1/4] | 🟠 | Git directory identity check misses worktree .git file, allowing verify --log .git to overwrite and corrupt the worktree | skills/run-autopilot/cli/log_sink_refusal.py:80 | 2 | CARL |
| R6 | [1/4] | 🟡 | Case 4b nested-repo probe is bypassed for the nested repo's own git directory. `_in_nested_repo` treats any failing `git rev-parse --show-toplevel` as "not nested", but git also fails when run inside a `.git` directory (rc 128, "must be run in a work tree"). Confirmed on a fixture: with an ignored nested repo at `docs/dev/tmp/other`, `refuse()` returned None for `docs/dev/tmp/other/.git/config`, `.git/hooks/pre-commit` and `.git/hooks/newhook`. `_open_log_sink` would then unlink and recreate that config, so the "git internals" guarantee does not hold for a nested repo. Fix: also refuse when any ancestor of `resolved` below `toplevel` contains a `.git` entry (or probe `--git-dir`/`--is-inside-git-dir` and refuse on a hit), and add a regression test for the nested `.git/config` path. | skills/run-autopilot/cli/log_sink_refusal.py:123 | 2 | ALICE |
| R7 | [1/4] | 🟡 | `test_run_gate_refuses_a_symlinked_log_and_leaves_its_target` was rewritten, and the replay shows it passes against the pre-change code. The pre-spawn dirt scan already refused a symlinked log, so the test does not bind to the new case-3 refusal in `_lock_and_check`. Its own comment says the tracked and direct cases moved to the new file. Either add an assertion that only the new code satisfies (for example `dirty_paths` naming the target via `_log_rel_and_tracked`), or note that the test pins existing behavior. | skills/run-autopilot/cli/test_verification_log_sink.py:198 | 2 | ALICE, mech-check |
| R8 | [1/4] | 🟡 | An absolute `--log` outside the repo that has a symlinked ancestor gets the wrong reason text. `/etc/hosts` prints "is a symlink" instead of "resolves outside the repository", so a log pointed at another repo under `/tmp` (a symlink to `/private/tmp` on macOS) is reported as a symlink. `_symlinked_component` climbs above the repo root for such paths, but the spec limits the symlink check to ancestors below the toplevel. Exit code 2 and the no-write guarantee still hold. Only the reason text deviates, and the test uses a relative path so it does not catch this. | skills/run-autopilot/cli/log_sink_refusal.py:105 | 2 | BLAKE |
| R9 | [1/4] | 🟡 | Several carried-over tests assert less than the spec and the acceptance text require. `test_git_dir_identity_holds_from_a_subdirectory_cwd` checks only that `git status` ran (`returncode == 0`), so neither the reason text nor an unchanged status is checked. The hard-link, default-sink, FIFO, executable, outside-toplevel and other-repo-store tests check exit 2 and bytes but not the stderr reason or the JSON line. A wrong reason string, such as the one above, would go unnoticed. | skills/run-autopilot/cli/test_verify_log_refusal.py:282 | 1 | BLAKE |
| R10 | [1/4] | 🟡 | Case 2 falls open on a git-probe failure: `probe = _log_rel_and_tracked(repo_root, log_path)` returning `None` is treated as "untracked", but the design's case 2 requires "a `None` from a git failure fails closed as 'resolves outside the repository'"; with `_toplevel` already succeeding, the only `None` whose path is still inside the toplevel is an `ls-files` OSError, and such a path then clears cases 4-6 and the tracked sink gets truncated — fix: after computing `resolved`/`toplevel`, `if probe is None and resolved.is_relative_to(toplevel): return _OUTSIDE` | skills/run-autopilot/cli/log_sink_refusal.py:33 | 2 | BOB |
| R11 | [1/4] | 🟡 | Case 3's component walk is not bounded to the repository as its own docstring claims ("any component ... BELOW the repository"): it stops only at `repo_root`, `toplevel` or the filesystem root, so an out-of-repo or differently-spelled sink is walked up through `/`, returning "is a symlink" for a symlinked ancestor outside the repo (macOS `/tmp`, an unresolved `/var`) instead of "resolves outside the repository" — `test_verify_refuses_a_store_like_path_outside_the_repo` and `test_verify_refuses_an_absolute_out_of_repo_log` assert that exact tail, so the pair is environment-fragile; fix: run the `resolved.is_relative_to(toplevel)` containment test before `_symlinked_component`, or return early from the walk when `log_path` is not under `repo_root` | skills/run-autopilot/cli/log_sink_refusal.py:36 | 2 | BOB |
| R12 | [1/4] | 🟡 | `_open_log_sink(log_path, root: Path = Path("/"))`'s default has no production caller (`_run_locked_gate` always passes `cwd`); the only consumer is the test above, i.e. speculative generality on the security-critical open, and it is the reason that test exercises a non-production configuration — fix: drop the default and make `root` required once the test passes `repo` | skills/run-autopilot/cli/verification.py:466 | 2 | BOB |
| R13 | [1/4] | 🟡 | File test_review_stage.py exceeds the 800-line limit (805 lines) | skills/run-autopilot/cli/test_review_stage.py:805 | general | CARL |
| R14 | [1/4] | ⚪ | In `_identity_targets`, `Path(repo_root) / probe.stdout.strip()` wraps something that is already a `Path`. Use `repo_root / probe.stdout.strip()`. | skills/run-autopilot/cli/log_sink_refusal.py:75 | 2 | ALICE |
| R15 | [1/4] | ⚪ | Additions beyond the PRD. `_in_nested_repo` refuses a sink inside any nested git repository. `_open_log_sink` takes an extra `root` parameter. The test file has three tests the spec does not name: `test_parent_dir_symlink_swap_is_refused`, `test_nested_repo_store_is_refused` and `test_symlink_above_repo_root_does_not_refuse_default_sink`. The nested-repo refusal is a fair reading of "outside the repository" but is not stated. | skills/run-autopilot/cli/log_sink_refusal.py:121 | 2 | BLAKE |
| R16 | [1/4] | ⚪ | `_lock_and_check` folds every refusal reason into a dirty result, where the spec names only tracked and symlinked sinks. It is a safe superset. The "tracked" test is `git ls-files --error-unmatch`, which checks the index, not HEAD, as the spec literally says. | skills/run-autopilot/cli/verification.py:403 | 2 | BLAKE |
| R17 | [1/4] | ⚪ | `_descend` creates missing parent directories before opening the sink. That is only reached after the refusal passes, so it is not a hole, but the gate path now makes directories. | skills/run-autopilot/cli/verification.py:458 | 2 | BLAKE |
| R18 | [1/4] | ⚪ | The refusal JSON line's `"log": None` field (the design called its absence a blocker) is not asserted by any changed test — the updated `test_cli_verify_verb.py` cases check only `error` and `exit`; run `rg -n '\["log"\] is None' skills/run-autopilot/cli/test_cli_verify_verb.py skills/run-autopilot/cli/test_verify_truth.py` and, if it prints nothing, add that assertion to one refusal test | skills/run-autopilot/cli/__main__.py:1042 | 2 | BOB |
| R19 | [1/4] | ⚪ | Fail-first replay: `test_run_gate_streams_stdout_and_stderr_to_the_log` and `test_held_gate_lock_blocks_before_the_log_open_and_record_delete` pass against the pre-change code — out of scope as findings: both were only relocated from a `tmp_path_factory` sink into `docs/dev/tmp` because case 4 now refuses an out-of-repo sink, and they are pre-existing regression tests, not this PRD's behavior pins | skills/run-autopilot/cli/test_verification.py:454 | 2 | BOB, mech-check |
| R20 | [1/4] | ⚪ | Fail-first replay: `test_run_gate_refuses_a_symlinked_log_and_leaves_its_target` passes at base — out of scope: it is the surviving `symlink` arm of a deleted parametrize whose behavior was already correct at base, and its tracked arm moved to `test_verify_log_refusal.py::test_run_gate_refuses_tracked_log_without_opening` (which is red at base) | skills/run-autopilot/cli/test_verification_log_sink.py:198 | 2 | BOB, mech-check |
| R21 | [1/4] | ⚪ | Fail-first replay: `test_untracked_tmp_log_still_records` passes at base — out of scope: the PRD and design both state this happy-path test must already pass at the task's base commit | skills/run-autopilot/cli/test_verify_log_refusal.py:225 | 1 | BOB, mech-check |
| R22 | [1/4] | ⚪ | A CLI `verify` run now executes `log_sink_refusal.refuse` twice (pre-flight plus inside the lock), each pass spawning ~6 `git` subprocesses, so a gate run pays ~12 extra probes — out of scope: both enforcement points are a PRD Must-have ("a library caller cannot bypass the CLI"), and caching across the flock boundary would reintroduce the TOCTOU the second check exists to close | skills/run-autopilot/cli/log_sink_refusal.py:20 | 2 | BOB |
| R23 | [1/4] | ⚪ | R13: two changed files exceed the 800-line limit — `skills/run-autopilot/cli/__main__.py` (~1975 lines, last function at 1968) and `skills/run-autopilot/cli/test_review_stage.py` (~802, last function at 786+16) — out of scope: both were already over before this diff, which adds ~15 and 2 net lines respectively; splitting them is its own PRD (the same precedent that split `verification.py`/`dirty_tree.py` under 00311), and the new files this PRD adds are well inside the limit (log_sink_refusal.py 133, test_verify_log_refusal.py 374, verification.py ~742) | skills/run-autopilot/cli/__main__.py:1968 | general | BOB |

Consolidation was run by `consolidate_findings.py` (no ledger flags — cycle 1 has no settled-decisions ledger). It merged two citation groups after line-suffix stripping: row 1 (`test_verify_log_refusal.py:508 ~ :317 ~ :333`) and row 3 (`:1 ~ :32`).

### Mechanical test checks

Tautological test shapes: none across 103 test functions in 5 test files.

Fail-first replay: 26 touched tests ran against `7b47b02c5315`, 21 failed at base, 5 passed. All four `[MECH]` lines were absorbed into the rows above (R2, R7/R20, R19, R21) rather than added as separate rows — each names a test file and test already in the table.

## Alice (consensus lens)

Seven findings, five 🟡 and two ⚪ — table rows R1, R2, R3, R4, R6, R7, R14. Her sharpest is R6: she built a fixture with an ignored nested repo and showed `refuse()` returning `None` for that repo's own `.git/config`, `.git/hooks/pre-commit` and a new hook path, because `git rev-parse --show-toplevel` fails inside a `.git` directory and `_in_nested_repo` reads every failure as "not nested". `_open_log_sink` would then unlink and recreate that config.

Verdicts: R1 pass, R2 fail, R3 pass, R4 pass, R6 pass, R7 fail, R8 pass, R9 pass, R10 pass, R11 pass, R12 pass, R13 pass.

## Blake (blind lens, PRD-only)

Blake located the implementation himself and ran the three acceptance test files the PRD names (`test_verify_log_refusal.py`, `test_verification_dirty.py`, `test_verify_truth.py`): 56 passed. He confirmed, against the spec alone: the shared `log_sink_refusal` module behind both entry points; all seven refusal cases; the stderr line and the `{"error","exit":2,"log":null}` JSON line; the default sink going through the same check; `_open_log_sink` using `O_CREAT|O_WRONLY|O_EXCL|O_NOFOLLOW` against a pinned parent fd; `_lock_and_check` returning `_dirty_result([rel])` before the gate; all 14 named tests plus 3 extras present; the file registered once in `dev/bin/release-checks:338`; the CHANGELOG entry at `CHANGELOG.md:33`; `test_verification_dirty.py` still at 26 tests with no change in git history. He did not check the red-at-base acceptance, which needs the base checkout.

Five findings — table rows R8, R9, R15, R16, R17.

Verdicts: B1 fail, B2 pass, B3 pass, B4 pass, B5 fail, B6-B19 pass.

## Bob (doubt lens, D1-D5 + de-slop) — after one retry (inlined), then the Claude fallback

Bob ran as the Claude doubt-lens fallback; the codex path is documented in the degradations above. He read the context, the full diff, `dirty_tree.py` and `__main__.py`, and produced the full contract.

Six FIX findings (table rows R1, R2, R3, R10, R11, R12), two VERIFY (R4, R18 — both queued, below), five KNOWN (R19-R23, each a replay row or a pre-existing limit he argues out of scope with reasoning).

His two unique correctness findings are the strongest of the cycle: R10, a fail-open on a git-probe `None` where the design requires fail-closed, and R11, a symlink walk that is not bounded to the repository as its own docstring claims, making two refusal-reason assertions environment-fragile.

Verdicts: R1 pass, R2 fail, R3 pass, R4 pass, R6 pass, R7 pass, R8 pass, R9 fail, R10 pass, R11 pass, R12 pass, R13 fail.

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl (Gemini / copilot backend, frontend & design specialist)

Carl ran on the copilot backend and did real dynamic work: he built git worktree fixtures and exercised `refuse()` and `_open_log_sink` directly. He is the only reviewer to raise a 🟠 HIGH, R5: the git-directory identity check misses the `.git` **file** a linked worktree uses (a `gitdir:` pointer, not a directory), so `verify --log .git` inside a worktree can overwrite and corrupt it.

Three findings — table rows R5, R1, R13.

Verdicts: R1 pass, R2 fail, R3 pass, R4 fail, R6 pass, R7 pass, R8 pass, R9 fail, R10 pass, R11 pass, R12 pass, R13 fail.

## Verification-check queue

Two VERIFY findings named exact runnable commands and were queued to `docs/dev/project-management/reviews/00320-refuse-every-unsafe-verify-log-sink-v2-checks-1.json` (R18, R4). They run in the work phase's step-7 verification pass and create no tasks.

Verdict: 23 findings
Tests: 6977 passed, 0 failed, 3 skipped (reused from last-verification.json at 76f8c48)
