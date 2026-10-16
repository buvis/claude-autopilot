---
prd: docs/dev/project-management/prds/wip/00320-refuse-every-unsafe-verify-log-sink-v2.md
review: 2
date: 2026-10-16
head_sha: f698f51e5d25b4ccb1a34d9b915ccb18f3c7f483
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available (claude fallback)
  carl: available
dispatch_rows:
  bob: 2ff6b97a
  carl: 187caaf3
---

# Review: 00320-refuse-every-unsafe-verify-log-sink-v2

Diff range: `c2bf610d6ac4b832a70599f8ee6dca71a251e48c..f698f51e5d25b4ccb1a34d9b915ccb18f3c7f483`

codex_rung_guard: not fired

Cycle 2, incremental review of the cycle-1 rework. Engine: `legacy` (single consensus subagent).

Degradations this cycle, named loudly:

- **pack: failed** (`engram pack exit 1: sqlite3.OperationalError: attempt to write a readonly database`) — same seatbelt cause as cycle 1. No Findings-precedent section reached any reviewer. Degraded in that one respect, not invalid.
- **Bob ran as the Claude doubt-lens fallback, not codex** — again. His codex run refused for lack of input (`Cannot statically verify`, every `R{n}` failed, reads denied before the first file). The one sanctioned inlined retry (174 KB prompt, context + diff inlined verbatim) ran, exited 0, and wrote no review file at all — byte-for-byte the cycle-1 failure mode. The doubt lens was then re-dispatched as a Claude subagent on Bob's exact assembled prompt and produced the full contract (FIX/VERIFY/KNOWN, every `R{n}`, D1-D5). The doubt lens did not drop. The codex lane has now failed identically on two consecutive cycles of this PRD under the seatbelt; that is a tooling defect worth its own PRD, not a reviewer verdict.

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [3/4] | 🟠 | A `.git` file with a RELATIVE `gitdir:` pointer is still not refused. `_worktree_gitdir_pointer` returns `Path("../../.git/modules/vendor/sub")`, which `os.path.samefile` resolves against cwd instead of the `.git` file's directory, so the samefile raises OSError and the `continue` swallows it. Reproduced on a submodule: `.git` contains `gitdir: ../../.git/modules/vendor/sub`, and `refuse(sm/".git", sm)` returned None. Git also writes relative pointers for linked worktrees when `worktree.useRelativePaths` is set. `_open_log_sink` would unlink and recreate that file, so the R5 corruption class survives. Fix: `pointer = (resolved.parent / pointer)` when the pointer is relative. Add a submodule or relative-pointer regression test; the current test covers only the absolute linked-worktree form. | skills/run-autopilot/cli/log_sink_refusal.py:137 | 4 | ALICE, BOB, CARL |
| R2 | [2/4] | 🟡 | The R6 fix is locale-dependent and fails open. `_in_nested_repo` returns `"work tree" in probe.stderr`, but `_git` (`cli/dirty_tree.py:27`) does not pin the locale. With `LC_ALL=de_DE.UTF-8`, git prints "Schwerwiegend: ..." and `refuse(nested/.git/config, repo)` returns None on a fixture where the C locale returns "resolves outside the repository". Fix: run `git rev-parse --is-inside-git-dir` (stdout "true", locale-free), or pass `LC_ALL=C` in this one probe, plus a regression test that sets a translated locale. | skills/run-autopilot/cli/log_sink_refusal.py:174 | 4 | ALICE, BOB |
| R3 | [2/4] | 🟡 | The R6 fix still misses a nested `.git` path whose parent directory does not exist yet. Reproduced: `refuse(nested/.git/refs/heads/newdir/ref)`, `.git/hooks/sub/x` and `.git/objects/zz/yy` all return None. `_git(resolved.parent, ...)` raises FileNotFoundError for the missing cwd, `_in_nested_repo` reads that as "no nested repo", and `_descend` then creates directories and a file inside the nested repo's git directory. Fix: replace the string match with a lexical walk — refuse if any ancestor of `resolved` strictly below `toplevel` that exists on disk contains a `.git` entry; keep the probe only for the non-`.git` nested working-tree case. | skills/run-autopilot/cli/log_sink_refusal.py:169 | 4 | ALICE, BLAKE |
| R4 | [2/4] | 🟡 | `_worktree_gitdir_pointer` calls `resolved.read_text()` on any existing regular file to test a 7-byte prefix. A multi-megabyte previous gate log gets read whole, twice per CLI run (pre-flight plus in-lock). Read a bounded prefix instead (64-256 bytes, binary, `errors="ignore"`), or only inspect files named `.git`. | skills/run-autopilot/cli/log_sink_refusal.py:132 | 4 | ALICE, BOB |
| R5 | [2/4] | 🟡 | Reason text deviates from the listed case order when a symlink overlaps another case. `refuse()` runs the outside-repo test (case 4) before the symlink walk (case 3), so a symlink or symlinked ancestor resolving outside the toplevel prints `resolves outside the repository`, not `is a symlink`. This applies to the default sink as well. Still refused with exit 2; only the reason text deviates, and no test covers the shape. | skills/run-autopilot/cli/log_sink_refusal.py:38 | 2 | BLAKE, BOB |
| R6 | [1/4] | 🟡 | `test_cli_refuses_symlinked_log` only plants a symlink whose target is inside the repo, untracked, in docs/dev/tmp. The overlap above is therefore not pinned. A symlink to an outside or tracked target gets a different reason than `is a symlink`, and no test fixes the expected reason for that case. | skills/run-autopilot/cli/test_verify_log_refusal.py:118 | 1 | BLAKE |
| R7 | [1/4] | 🟡 | Extra refusal behaviour the spec's case list does not name: the linked-worktree `.git` gitfile pointer check in `_worktree_gitdir_pointer`; the nested-repo probe in `_in_nested_repo`, which relies on the string match `"work tree" in probe.stderr` (brittle, locale- and git-version-dependent); and seven tests beyond the fourteen the PRD names. The nested-repo refusal is arguably covered by "another repository's store" under case 4; the worktree-pointer and stderr-sniffing parts are unrequested. | skills/run-autopilot/cli/log_sink_refusal.py:122 | 2 | BLAKE |
| R8 | [1/4] | 🟡 | Both tests added for the two refusal gaps assert only `result is not None`, so a refusal arriving for the wrong reason still passes — the same weakness R9 had this cycle's other tests fix. Fix: assert `result == "resolves inside the git directory"` in `test_worktree_dotgit_file_log_is_refused` (:392) and the exact reason the nested case yields in `test_nested_repo_git_internals_are_refused` (:407); `test_cli_refuses_git_dir_log` (:165) still asserts no reason either. | skills/run-autopilot/cli/test_verify_log_refusal.py:392 | 5 | BOB |
| R9 | [1/4] | 🟡 | `test_run_gate_refuses_a_symlinked_log_and_leaves_its_target`'s rewritten comment says it binds "case 3's own refusal in `_lock_and_check`", but its symlink target `logs/gate.log` is committed, so `_log_rel_and_tracked` resolves through the link and `refuse()` returns "is tracked" (case 2) before `_symlinked_component` ever runs — the symlink case stays unpinned on the library path. Fix: point the link at an untracked in-repo file so case 3 actually fires, or correct the comment. | skills/run-autopilot/cli/test_verification_log_sink.py:204 | 6 | BOB |
| R10 | [1/4] | ⚪ | `test_absolute_log_outside_repo_via_symlinked_ancestor_reports_outside` and `test_symlinked_ancestor_component_walk_is_bounded_to_the_repo` pin the same ordering (a symlinked ancestor outside the repo yields "resolves outside"), and both fail on the old code for the same reason. Keep one, or make the second assert something the first does not. | skills/run-autopilot/cli/test_verify_log_refusal.py:689 | 5 | ALICE |
| R11 | [1/4] | ⚪ | The tracked check uses `git ls-files --error-unmatch` (index), not "tracked at HEAD". A staged-new file counts as tracked, which is the stricter and safer reading. A deviation in wording only. | skills/run-autopilot/cli/dirty_tree.py:255 | 2 | BLAKE |
| R12 | [1/4] | ⚪ | `_pinned_parent_fd` raises a bare `OSError` ("not under root") when an absolute `--log` is spelled through a different root than `--repo-root`, for example `/private/tmp/...` against `/tmp/...`, even though `refuse()` accepted it via resolve. The result is exit 2 with a JSON error that lacks the stated `{"error","exit","log":null}` shape (it prints `{"sha","log","error"}`). Rare. | skills/run-autopilot/cli/verification.py:440 | 2 | BLAKE |
| R13 | [1/4] | ⚪ | Residual check-then-act: the refusal runs, then `os.unlink(leaf)` runs. If an attacker swaps the leaf for a tracked file between the two, only the directory entry is removed and the content is never written through. The exclusive no-follow open closes the write-through hole; the remaining exposure is deletion of a swapped-in entry, minor and recoverable. | skills/run-autopilot/cli/verification.py:479 | 2 | BLAKE |
| R14 | [1/4] | ⚪ | The new `gitdir:` pointer loop compares against every entry of `_identity_targets`, the store included, where a worktree pointer can only ever produce the wrong reason text ("resolves inside the store" for a git-dir sink) — restrict the loop to the two git-dir targets. | skills/run-autopilot/cli/log_sink_refusal.py:103 | 4 | BOB |
| R15 | [1/4] | ⚪ | Stale comment left behind by the R2 fix: it still describes the removed either-or ("an errors entry, or a gate result that skipped the gate") while the assertion below now pins the `gate skipped` branch alone. | skills/run-autopilot/cli/test_review_stage.py:296 | 6 | BOB |
| R16 | [1/4] | ⚪ | `test_absolute_log_outside_repo_via_symlinked_ancestor_reports_outside` and `test_symlinked_ancestor_component_walk_is_bounded_to_the_repo` pin the same single early return (`not resolved.is_relative_to(toplevel)`) with the same fixture shape and assertion; one of the two is redundant. | skills/run-autopilot/cli/test_verify_log_refusal.py:466 | 5 | BOB |
| R17 | [1/4] | 🟡 | 1 touched test passes against the pre-change code: `test_gate_log_write_failure_degrades_instead_of_crashing` | skills/run-autopilot/cli/test_review_stage.py | general | mech-check |
| R18 | [1/4] | 🟡 | 1 touched test passes against the pre-change code: `test_run_gate_refuses_a_symlinked_log_and_leaves_its_target` | skills/run-autopilot/cli/test_verification_log_sink.py | general | mech-check |
| R19 | [1/4] | 🟡 | 10 touched tests pass against the pre-change code: `test_cli_refuses_log_outside_toplevel`, `test_cli_refuses_fifo_log`, `test_cli_refuses_executable_target`, `test_cli_refuses_hardlinked_log`, `test_default_sink_symlink_is_refused`, `test_default_sink_hardlink_is_refused` +4 more | skills/run-autopilot/cli/test_verify_log_refusal.py | general | mech-check |

Consolidation was run by `consolidate_findings.py` with `--ledger ... --ledger-dismiss BLAKE`. It merged two citation groups after line-suffix stripping: row 1 (`log_sink_refusal.py:137 ~ :136`) and row 3 (`:169 ~ :74`). R17-R19 are the three `[MECH]` replay lines, absorbed as their own rows per step 6.

### Auto-dismissed (ledger)

- [BLAKE] 🟡 The library path (`_lock_and_check`) now refuses every case, not only "tracked or symlinked" as the spec says, and reports each as `dirty: true` with `[rel]` ... This is defensible hardening, but it goes beyond the PRD and changes the library contract. | File: skills/run-autopilot/cli/verification.py:403 — dismissed against the cycle-1 settled deferral: the design doc prescribes exactly this `_dirty_result([rel])` return, and `ls-files --error-unmatch` against the index is the stricter test, failing in the safe direction.

### Mechanical test checks

Tautological test shapes: none across 57 test functions in 3 test files.

Fail-first replay: 19 touched tests ran against `c2bf610d6ac4`, 7 failed at base, 12 passed; 0 files failed to collect. The three `[MECH]` rows (R17-R19) are expected on an incremental base: `c2bf610d` already carries cycle 1's production code, so every test this cycle only *strengthened* (reason-text assertions, the `gate skipped` tightening, the symlink/`dirty_paths` test) passes there by construction. All seven genuinely new tests of this cycle — 1 worktree, 3 nested-`.git` params, 3 containment/fail-closed — are red at base, which is what the 7-failed count is.

## Alice (consensus lens)

Five findings — table rows R1, R2, R3, R4, R10. She verified all thirteen cycle-1 findings against the code and reproduced three surviving holes on throwaway fixtures: the relative `gitdir:` pointer (R1, reproduced on a real submodule), the locale-dependent nested-repo probe (R2, reproduced under `LC_ALL=de_DE.UTF-8`), and the nested `.git` path whose parent does not exist yet (R3, reproduced on three paths). She ran the five touched test files: 103 passed, 0 failed.

Verdicts: R1 pass, R2 pass, R3 pass, R4 pass, R6 pass, R7 fail, R8 pass, R9 pass, R10 pass, R11 pass, R12 pass, R13 pass.

## Blake (blind lens, PRD-only)

Eight findings, one auto-dismissed against the ledger — table rows R3, R5, R6, R7, R11, R12, R13. Against the spec alone he confirmed: 63 passed across the three PRD-named acceptance files; all fourteen named tests present plus seven extras; the single `dev/bin/release-checks:338` registration; the `CHANGELOG.md:33` entry; `test_verification_dirty.py` untouched; `_open_log_sink` using `O_CREAT|O_WRONLY|O_EXCL|O_NOFOLLOW` after unlinking the leaf, inside the lock, descending a pinned directory fd; the CLI pre-flight running before `run_gate`; the FIFO case guarded by `lstat`/`S_ISREG` before any read. Not verified: the Phase 0 fail-first acceptance at the base commit, which he did not replay.

Verdicts: B1-B19 all pass.

## Bob (doubt lens, D1-D5 + de-slop) — after one retry (inlined), then the Claude fallback

Bob ran as the Claude doubt-lens fallback; the codex path is documented in the degradations above. He read the context, the full diff, `log_sink_refusal.py`, `verification.py:370-520`, `dirty_tree.py` and the three touched test files, and ran one read-only git probe for grounding (`rev-parse --show-toplevel` inside a `.git` dir: rc 128; `--is-inside-git-dir`: `true`, git 2.55.0).

Nine findings — table rows R1, R2, R4, R5, R8, R9, R14, R15, R16. Eight FIX, zero VERIFY, one KNOWN (the containment-before-symlink case-order deviation, argued out of scope because it is the shape R11's accepted cycle-1 fix produced). He verified every cycle-1 finding individually, including R4 against `skills/work/references/attempt-logging.md` (the assumption ledger is per-plan and replaced, not appended — the wholesale reset was specified behavior) and R18 against `test_verify_truth.py:420`.

His sharpest unique finding is R9: the rewritten symlink test's target is committed, so it binds case 2 (tracked) and not the case 3 its own comment claims.

Verdicts: R1 pass, R2 pass, R3 pass, R4 pass, R6 pass, R7 fail, R8 pass, R9 fail, R10 pass, R11 pass, R12 pass, R13 fail.

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl (Gemini / copilot backend, model gemini-3.8-flash, frontend & design specialist)

Carl did real dynamic work again: git worktree and submodule fixtures, `refuse()` and `_open_log_sink` exercised directly, plus both touched test suites run. One finding — table row R1, the 🟠 HIGH, independently reproduced: `_worktree_gitdir_pointer` returns an unanchored relative path, so `samefile` resolves it against cwd and `verify --log .git` from a subdirectory cwd can overwrite the `.git` file. His and Alice's reproductions agree.

Verdicts: R1 pass, R2 pass, R3 pass, R4 pass, R6 pass, R7 fail, R8 pass, R9 fail, R10 pass, R11 pass, R12 pass, R13 pass.

## Verification-check queue

No VERIFY entry named an exact runnable command this cycle (Bob's VERIFY bucket is empty), so no `checks-2.json` was written. Both cycle-1 queued checks ran in the rework pass and exited 0, so nothing carried forward.

Verdict: 19 findings
Tests: 6984 passed, 0 failed, 3 skipped (suite run this cycle by review-stage, recorded at f698f51)
