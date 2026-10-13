---
prd: docs/dev/project-management/prds/wip/00276-make-the-gate-record-trustworthy-v1.md
review: 1
date: 2026-10-13
head_sha: df04aafad8c0691a229bbe643bdd5261bc03ce24
codex_thread_id: 01a13360-26bf-7561-ac07-8f2265701ecf
reviewers: alice,blake,bob
agents:
  alice: available
  blake: available
  bob: available
  carl: unavailable
dispatch_rows:
  bob: f9404c10, dad506e1 (retry)
  carl: 0cbd3600, f42a1316 (retry)
---

# Review: 00276-make-the-gate-record-trustworthy-v1 (cycle 1)

Diff range: `ccd03afeda572937632bea12ebaf7a7a52a9ee5c..df04aafad8c0691a229bbe643bdd5261bc03ce24` (full — the PRD's whole work range)

codex_rung_guard: not fired

## Review Summary

Reviewed: 9 completed tasks
PRDs checked: 00276-make-the-gate-record-trustworthy-v1

### Agent Status

- Alice: ✅ Available (consensus lens, legacy engine)
- Blake: ✅ Available (blind lens, PRD-only)
- Bob: ✅ Available (doubt lens, codex) — after one retry (inlined). His first run refused with the sandbox read failure (`sandbox-exec: sandbox_apply: Operation not permitted`, both read-only `cat` attempts failed before reading) and emitted twelve unevidenced `fail` verdicts; the inlined retry prompt carried the review context and the full diff verbatim, and its output is what is consolidated here.
- Carl: ⚠️ Unavailable: `gemini-run` exit 1 on both the first run and the retry, backend `copilot` model `gemini-3.8-flash`, `Error: Authentication failed` (GitHub Copilot token invalid, expired, or missing the `Copilot Requests` permission). Exit 1 is a runtime failure, not the exit-4 permanent shape, so no `state.batch.unavailable_reviewers` latch was written and the next cycle will try him again.

pack: failed (engram pack exit 1: `sqlite3.OperationalError: attempt to write a readonly database`) — the review ran without the findings-precedent pack, which is degraded, not invalid.

Consolidation note (fail loud): Bob's output emits its finding lines as `- [BOB] …` bullets inside the FIX/VERIFY/KNOWN buckets, and `consolidate_findings.py`'s `_LINE_RE` anchors on `^[`, so the first run of the consolidator silently dropped all seven of his findings. The bullet prefix was stripped from his output file (raw copy retained at `docs/dev/tmp/bob-output-00276c1-202610131.raw.txt`) and the consolidator re-run; the table below is that second run. The consolidator also reported one suffix-stripped merge on row R1, folding `__main__.py:1010` (Alice), `__main__.py` (Blake) and `__main__.py:1009` (Bob) — the same `_run_verify` exit-code defect, correctly merged into a 3/3.

Mechanical checks: the tautological-test block produced no `[MECH]` findings. The fail-first replay block produced four, absorbed as follows: the `test_hidden_flag_alone_without_an_edit_is_not_dirt` replay result is the same test Alice's row R6 already names, so `mech-check` was added as a finder on R6 rather than creating a row; the other three replay results name tests no reviewer row names, so they were added as their own rows R20, R21 and R22. Per the absorption rule, a replay row states a computed fact (the test passes against the pre-change code) and stays 🟡 — for a behavior-preserving refactor that is by design, and Alice judged this block to list "only behavior-preserving regression guards", which is the reason the decision gate may ledger-dismiss them.

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [3/3] | 🟠 | `verify` exits 0 when the tree turns dirty after the gate ran and no record was written. `_run_verify` returns `3 if not recorded and not dirty else 0`, so exit 0, dirty True and recorded False falls to 0. The PRD success metric says "verify exits non-zero whenever it wrote no record". The design contract gates the whole success branch on `not result["dirty"]` and returns 1 otherwise. The `__main__.py` docstring and final-verification.md both say exit 0 requires a non-dirty tree. The fix is to test `not dirty` before the `recorded` branch and return 1 for any dirty result. test_verify_dirtied_during_the_run_still_reports_the_process_exit (skills/run-autopilot/cli/test_cli_review_verbs.py:410) currently asserts `code == 0` with `recorded` False and `dirty` True, so it pins the wrong behavior and needs flipping to 1. | skills/run-autopilot/cli/__main__.py:1010 | 7 | ALICE, BLAKE, BOB |
| R2 | [2/3] | 🟡 | `_tracked_log_path` and `_untracked_log_exclusion` both do the same work: find the toplevel, compute the resolved toplevel-relative POSIX path, and run `ls-files --error-unmatch`. Fold them into one helper that returns (rel, tracked). | skills/run-autopilot/cli/verification.py:259 | 5 | ALICE, BOB |
| R3 | [1/3] | 🟠 | The `gate.lock` wait is unbounded, and the spec's expiry behavior is missing. The spec says the wait is bounded by the gate timeout, and on expiry the second caller returns the timed-out result and writes nothing. `_lock_and_check` calls a blocking `fcntl.flock(lock_fd, fcntl.LOCK_EX)` with no timeout or `LOCK_NB` loop. The `run_gate` docstring admits "blocking, no timeout of its own". A hung or orphaned holder (for example a grandchild keeping the lock fd) blocks every later `verify` indefinitely. `test_concurrent_runs_serialize_on_the_gate_lock` cannot catch this. | skills/run-autopilot/cli/verification.py:534 | Phase 0 flock | BLAKE |
| R4 | [1/3] | 🟠 | Hidden-flag handling violates the required flag-alone refusal. `_hidden_flag_edits` compares content hashes instead, overlooking executable-bit changes and potentially treating a replacement symlink as unchanged when its referent matches the indexed bytes. Return every flagged outside-store path as required; remove the hashing branch and reverse the flag-alone acceptance test. | skills/run-autopilot/cli/verification.py:202 | 2 | BOB |
| R5 | [1/3] | 🟠 | A single-hop directory symlink resolving to the repository root escapes staleness detection: `src/root -> ..` normalizes to `"."`, while store paths never start with `"./"`. Treat `"."` as an ancestor of every repository-relative store path and add committed/uncommitted regression cases. This is within the required relative directory-alias scope. | skills/run-autopilot/cli/verification.py:166 | 6 | BOB |
| R6 | [1/3] | 🟡 | `_hidden_flag_edits` does not treat every skip-worktree or assume-unchanged path outside the store as dirt. It only counts a flagged path when its work-tree content differs from the index blob or the file is missing. The PRD and design say any `S` or lowercase `ls-files -v` tag outside the store counts as dirty. test_hidden_flag_alone_without_an_edit_is_not_dirt (skills/run-autopilot/cli/test_verification_hidden_flags.py:137) enshrines the narrower behavior. It is arguably better (no refusal for an unedited sparse-checkout or flagged file) and still blocks the edit scenario, but it is an unrecorded deviation. Either align with the spec or note the decision in the PRD or design doc. | skills/run-autopilot/cli/verification.py:202 | 2 | ALICE, mech-check |
| R7 | [1/3] | 🟡 | `_dirty_outside_store_paths` repeats the `rev-parse --show-prefix` and `prefix + STORE_PREFIXES` logic that `_store_roots` already holds. Replace the inline block with `store = _store_roots(repo_root)`. The status scan is also duplicated between `_dirty_store_paths` and `_dirty_outside_store_paths`. | skills/run-autopilot/cli/verification.py:171 | 1 | ALICE |
| R8 | [1/3] | 🟡 | The `reuse_verdict` and `_ancestor_and_clean` docstrings, which list the conditions for "reused", do not mention the new symlink-alias staleness checks (committed and uncommitted). Add them to the "Returns reused only when ALL hold" list. | skills/run-autopilot/cli/verification.py:342 | 6 | ALICE |
| R9 | [1/3] | 🟡 | Scope creep: a tracked-file `--log` refusal that the spec does not ask for. `_refuse_verify_log` adds an exit-2 path ("resolves to a tracked file"), `run_gate` adds a `_tracked_log_path` refusal returning `_dirty_result`, and the docstring and `final-verification.md` document both. The spec asks only for the store-resolving refusal. Note that `run_gate` runs its tracked-log check after taking the lock but before the dirty check, so it reports a different `dirty_paths`. | skills/run-autopilot/cli/__main__.py:958 | Phase 1 log checks | BLAKE |
| R10 | [1/3] | 🟡 | Hidden-flag rule deviates from the spec. The spec says the tree is dirty when `ls-files -v` shows an `S` or lowercase tag outside the store, with one extra git call. `_hidden_flag_edits` counts a flagged path only if its work-tree content differs from the index blob or the file is gone. It makes three or more git calls (`rev-parse --show-toplevel`, `ls-files -v -s`, `hash-object`). A flagged but unmodified file is not dirt, where the spec says it is. This is arguably a safer reading and both named tests pass. Edge cases: a flagged symlink or gitlink makes `hash-object` follow the symlink or fail, so it reports false dirt or a probe failure. Both fail closed. | skills/run-autopilot/cli/verification.py:202 | Phase 0 hidden flags | BLAKE |
| R11 | [1/3] | 🟡 | Hidden-edit refusal tests pass `"abc"` as the SHA and assert only refusal. The new SHA check independently produces that result even if hidden-edit detection is removed. Pass actual HEAD and assert the offending `dirty_paths`; verify these tests fail with the hidden-flag scan disabled. | skills/run-autopilot/cli/test_verification_hidden_flags.py:66 | 2 | BOB |
| R12 | [1/3] | 🟡 | `_run_verify` checks resolved paths but passes and prints the unresolved path, contrary to its contract; it also skips CLI validation for the default destination. Resolve the selected destination once, validate both explicit and default destinations before `run_gate`, then pass and print that same path. | skills/run-autopilot/cli/__main__.py:990 | 7 | BOB |
| R13 | [1/3] | ⚪ | Drive-by edits unrelated to the task: `text[len(shell) :]` was reflowed in `normalize_command`, and one docstring line in `_dirty_outside_store_paths` is over-long. Both look like the formatter pass; revert them. | skills/run-autopilot/cli/verification.py:326 | general | ALICE |
| R14 | [1/3] | ⚪ | In the log-sink error path, `os.killpg` in `_run_locked_gate` can raise `ProcessLookupError`, which is an OSError. That would mask the original sink error and skip `proc.wait()`, leaving a zombie. Guard the `killpg` call. | skills/run-autopilot/cli/verification.py:3862 | 5 | ALICE |
| R15 | [1/3] | ⚪ | The symlink-reuse check lives in `_ancestor_and_clean`, not in `reuse_verdict` as the spec words it. The behavior is equivalent, since `reuse_verdict` calls it, and a git failure becomes stale through `OSError`. It also treats symlinks that point into `docs/dev/tmp/` and directory-level symlinks as product, which is conservative. | skills/run-autopilot/cli/verification.py:105 | Phase 0 symlink | BLAKE |
| R16 | [1/3] | ⚪ | `_hidden_flag_edits` and `_untracked_log_exclusion` swallow some git failures into "no exclusion" or "no log". Both fail toward refusing or re-running, so this is acceptable. `_tracked_log_path` has no try/except around `resolve()`, though that is low risk. | skills/run-autopilot/cli/verification.py:259 | general | BLAKE |
| R17 | [1/3] | ⚪ | The new tests sit in files other than those named in the PRD (`test_verification_dirty_paths.py`, `test_verification_hidden_flags.py`, `test_verification_log_sink.py`). The test names match. I ran 148 tests across the six verification and CLI test files and all passed, so tests pass despite the exit-3 defect above. The exit-3 test uses a hand-built result and never exercises the mid-run-dirty path. | skills/run-autopilot/cli/test_cli_review_verbs.py:725 | Phase 1 | BLAKE |
| R18 | [1/3] | ⚪ | Absolute symlink targets and symlink chains remain outside reuse detection; the design explicitly accepts these limitations for this change. | skills/run-autopilot/cli/verification.py:143 | 6 | BOB |
| R19 | [1/3] | ⚪ | Existing unchanged functions exceed 50 lines, and `__main__.py` exceeds 800 lines according to the supplied mechanical facts; restructuring unrelated CLI code is outside this review's scope. | skills/run-autopilot/cli/__main__.py:1404 | general | BOB |
| R20 | [1/3] | 🟡 | 6 touched test(s) pass against the pre-change code: test_verify_accepts_a_store_like_path_outside_the_repo, test_verify_writes_an_absolute_out_of_repo_log_where_asked, test_verify_untracked_log_outside_the_store_still_works, test_verify_exits_2_when_the_log_cannot_be_opened, test_verify_exits_0_when_the_same_green_result_is_recorded, test_verify_exits_1_when_the_gate_timed_out_with_exit_0 | skills/run-autopilot/cli/test_cli_review_verbs.py | general | mech-check |
| R21 | [1/3] | 🟡 | 10 touched test(s) pass against the pre-change code: test_run_gate_drains_stderr_without_deadlock, test_run_gate_unparseable_output_records_nothing, test_run_gate_keeps_tail_so_a_late_summary_line_still_parses, test_run_gate_streams_and_keeps_tail, test_run_gate_uses_last_summary_line_not_first, test_run_gate_closes_the_child_pipes_before_returning +4 more | skills/run-autopilot/cli/test_verification.py | general | mech-check |
| R22 | [1/3] | 🟡 | 35 touched test(s) pass against the pre-change code: test_reuse_when_only_store_paths_changed, test_stale_when_code_changed, test_reuse_verdict_fails_closed_on_git_error, test_reuse_verdict_rejects_non_ancestor_sha, test_reuse_verdict_rejects_dirty_tree, test_rename_out_of_store_is_not_clean +29 more | skills/run-autopilot/cli/test_verification_dirty.py | general | mech-check |

### Full Consensus (3/3)

- [3/3] 🟠 `_run_verify` returns exit 0 when the gate ran green but the tree went dirty and no record was written | skills/run-autopilot/cli/__main__.py:1010 | Found by: Alice, Blake, Bob

### Majority Consensus (>50%)

- [2/3] 🟡 `_tracked_log_path` and `_untracked_log_exclusion` duplicate the same toplevel/relative-path/tracked lookup | skills/run-autopilot/cli/verification.py:259 | Found by: Alice, Bob

### Minority (<=50%)

Rows R3-R22 above, including three further 🟠 raised by a single lens each: the unbounded `gate.lock` wait (Blake), the hidden-flag content-hash deviation (Bob), and the `.`-normalizing directory-symlink escape (Bob).

## Alice

Her eight findings are rows R1, R6, R7, R8, R2, R13, R14 and R19-equivalent above. Notes she recorded: the 155 tests across `test_verification*.py` and `test_cli_review_verbs.py` pass (50s); no skip or xfail markers were added; `verification.py` is 638 lines with every function under 50 lines; the fail-first replay block lists only behavior-preserving regression guards as passing at base, which she judged acceptable; and the mid-run-dirty exit-0 test contradicts the PRD, so the suite does not catch that defect.

R1: pass
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
R13: fail

## Blake

His seven findings are rows R1, R3, R9, R10, R15, R16 and R17 above. He is PRD-only by construction and located the code himself. He also recorded eleven points verified as compliant: `_dirty_outside_store_paths` using `STORE_PREFIXES` plus the untracked-log exclusion by exact match; `dirty_paths` present in every result shape and printed by `verify`; a relative `--log` joining `--repo-root` and a store-resolving `--log` refused with exit 2 before any open; the record deleted after the pre-spawn dirty check and after the log opens, before the spawn; a log-sink `OSError` killing and reaping the process group then re-raising; the `OSError` branch of `verify` printing `{sha, log, error}` and exiting 2; `final-verification.md:164` documenting exit 3 and the `--log` refusal; the CHANGELOG `[Unreleased]` gate, hidden-flag and symlink lines; and exit 3 documented in the `__main__.py` docstring. He did not run `release-checks`.

B1: fail
B2: pass
B3: fail
B4: fail
B5: fail
B6: fail
B7: pass
B8: pass
B9: pass
B10: pass
B11: fail
B12: pass
B13: pass
B14: pass
B15: fail
B16: pass
B17: pass
B18: pass
B19: pass

## Bob

Doubt lens (codex), after one retry (inlined). His seven findings are rows R1, R4, R11, R5, R2, R12 (FIX bucket) and R18, R19 (KNOWN bucket). His VERIFY bucket is empty, so no verification-check queue file was written for this cycle.

R1: fail
R2: fail
R3: pass
R4: fail
R6: pass
R7: fail
R8: pass
R9: fail
R10: pass
R11: pass
R12: fail
R13: fail
D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

⚠️ Unavailable: `gemini-run` exit 1 on both the first run and the retry (backend `copilot`, model `gemini-3.8-flash`, `Error: Authentication failed`). No findings. Exit 1 is a runtime failure rather than the exit-4 permanent shape, so no batch latch was recorded.

Verdict: 22 findings
Tests: 3586 passed, 0 failed, 0 skipped (suite run this cycle: `dev/bin/release-checks` at df04aaf exited 0; the counts are read from last-verification.json at 55e3fd3, whose code is byte-identical to df04aaf — `git diff --stat 55e3fd3 df04aaf` shows only four autopilot telemetry JSONL files and no code)
