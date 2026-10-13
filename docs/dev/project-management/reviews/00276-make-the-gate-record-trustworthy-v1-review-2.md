---
prd: docs/dev/project-management/prds/wip/00276-make-the-gate-record-trustworthy-v1.md
review: 2
date: 2026-10-13
head_sha: 66234dd33b6d19d6b1c01e0c9a7171e419abd480
codex_thread_id: 01a13360-26bf-7561-ac07-8f2265701ecf
reviewers: alice,blake,bob
agents:
  alice: available
  blake: available
  bob: available
  carl: unavailable
dispatch_rows:
  bob: 6e50c6af, 0db6c044 (retry)
  carl: d240c809, 22e62662 (retry)
---

# Review: 00276-make-the-gate-record-trustworthy-v1 (cycle 2)

Diff range: `df04aafad8c0691a229bbe643bdd5261bc03ce24..HEAD` (incremental — the cycle-1 rework commits only)

codex_rung_guard: not fired

## Review Summary

Reviewed: 13 completed tasks (9 original + 4 cycle-1 `[D1]` rework tasks)
PRDs checked: 00276-make-the-gate-record-trustworthy-v1

### Agent Status

- Alice: ✅ Available (consensus lens, legacy engine)
- Blake: ✅ Available (blind lens, PRD-only)
- Bob: ✅ Available (doubt lens, codex) — after one retry (inlined). His first run (resuming the cycle-1 thread) refused with the sandbox read failure (`sandbox_apply: Operation not permitted`) and emitted twelve unevidenced `fail` verdicts; the inlined retry prompt carried the review context and the full diff verbatim, and its output is what is consolidated here.
- Carl: ⚠️ Unavailable: `gemini-run` exit 1 on both the first run and the retry, backend `copilot` model `gemini-3.8-flash`, `Error: Authentication failed` (GitHub Copilot token invalid, expired, or missing the `Copilot Requests` permission). Exit 1 is a runtime failure, not the exit-4 permanent shape, so no `state.batch.unavailable_reviewers` latch was written.

pack: failed (engram pack exit 1: `sqlite3.OperationalError: attempt to write a readonly database`) — the review ran without the findings-precedent pack, which is degraded, not invalid.

Consolidation note (fail loud): Bob's `-o` file held the whole codex transcript (the inlined prompt echoed back, including the format-spec's own `[BOB]` example lines), so it was trimmed to his final answer block before consolidation; the raw transcript is no longer retained. The consolidator reported one suffix-stripped merge on row R1, folding Alice's `__main__.py:947` with Bob's `__main__.py:1007` — those are two different defects at the same file (the tracked-log refusal removal and the exit-code mapping), so the merge is wrong in the second half: Bob's exit-code claim is recorded separately in his own section below and is discarded (see Decision notes).

Mechanical checks: the tautological-test block produced no `[MECH]` findings. The fail-first replay was **skipped** this cycle — the runner timed out after 600 s — so no replay findings exist to absorb. No cycle-1 verification-check queue file exists (`00276-…-checks-1.json` absent), so nothing was carried forward.

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [2/3] | 🟠 | The tracked-`--log` refusal was removed, but the design doc and tasks 5 and 7 still require it. Design doc step 2.5 says `run_gate` refuses a tracked log "outright" before opening anything. Task 5 and task 7 both name that refusal, the CLI exit-2 "resolves to a tracked file" check, and tests that leave the file's bytes unchanged. The rework deleted `_tracked_log_path`, the `_refuse_verify_log` branch and the refusal tests. The PRD feature text names only the store check, so the PRD and the design doc conflict, and the change settled it by dropping the safer behaviour. `autopilot verify --log src/app.py` now truncates and overwrites tracked product code before any check. The test at test_verification_log_sink.py:197 and the one at test_cli_review_verbs.py:548 assert the overwrite (`read_bytes() != before`). The run then reports exit 3, which the docs call "the suite did not fail". Restore the refusal, or record the conflict in the PRD and design doc so the contracts agree. | skills/run-autopilot/cli/__main__.py:947 | 5 | ALICE, BOB |
| R2 | [2/3] | 🟡 | Two docs omit a path that exits 1: the `__main__.py` verify entry and final-verification.md. They define exit 1 as "timed out or non-zero gate exit". But a pre-spawn dirty-tree refusal, a sha mismatch, a lock-wait expiry and a `--log` refused by `run_gate` all return `exit: None`, and `_run_verify` returns 1 for them. A reader following the "three outcomes" prose can't tell a dirty-tree refusal from a red suite. The previous docstring listed "dirty tree OR timed out". Restore that wording. | skills/work/references/final-verification.md:162 | 8 | ALICE, BLAKE |
| R3 | [1/3] | 🟠 | Removing tracked-log refusal reintroduces destructive writes: `verify --log src/app.py` truncates committed source before spawning the gate. The changed tests explicitly require that overwrite; a tracked scratch log even permits recording afterward. Tasks 5/7 and the design explicitly require refusal at both boundaries, so prior finding R9's "scope creep" premise was incorrect. Restore both refusals and byte-preservation tests, including nested repo roots; restore the corresponding documentation. | skills/run-autopilot/cli/verification.py:540 | 5 | BOB |
| R4 | [1/3] | 🟡 | `_acquire_lock` catches every `OSError` and treats it as "lock busy". Only `BlockingIOError` means that for `LOCK_EX \| LOCK_NB`. A persistent real error (`ENOLCK`, `EBADF`) is polled for the whole timeout, up to 1800 s, then returned as a timed-out gate. The failure is swallowed and reported as the wrong cause. Catch `BlockingIOError` and let other errors propagate. | skills/run-autopilot/cli/verification.py:533 | 11 | ALICE |
| R5 | [1/3] | 🟡 | The `os.killpg` `ProcessLookupError` guard added for the cycle-1 R14 finding has no test. Make `os.killpg` raise `ProcessLookupError` in the existing sink-error test (`test_log_write_error_kills_and_reaps_the_gate`) and assert the original sink `OSError` still propagates and the child is reaped. | skills/run-autopilot/cli/test_verification_log_sink.py:120 | 11 | ALICE |
| R6 | [1/3] | 🟡 | `_run_locked_gate` grew to 51 lines (557-607) once the kill and reap block was added. `_reap` already does `killpg`, `wait` and both pipe closes, so the sink-error `except` can call a shared helper. Put the `ProcessLookupError` guard in that helper, which also covers the unguarded `os.killpg` in `_reap`. This removes the over-limit function and the duplicated reap code. | skills/run-autopilot/cli/verification.py:557 | 11 | ALICE |
| R7 | [1/3] | 🟡 | `_hidden_flag_edits` no longer looks at edits: it returns every flagged path. It still runs `ls-files -v -s` and unpacks `mode`, `blob` and `stage`, none of which is used now. Rename it (for example `_hidden_flag_paths`) and parse plain `ls-files -v -z` output, as the design contract specifies. | skills/run-autopilot/cli/verification.py:206 | 2 | ALICE |
| R8 | [1/3] | 🟡 | The cycle-1 R7 finding is only half fixed. `_store_roots` is now reused, but `_dirty_store_paths` and `_dirty_outside_store_paths` still run the same `git status --porcelain=1 -z` call and the same record parse, with the filter flipped. Extract one status-records helper. | skills/run-autopilot/cli/verification.py:127 | 1 | ALICE |
| R9 | [1/3] | 🟡 | `_acquire_lock` catches every `OSError` and treats it as contention, concealing permanent locking failures until they become misleading timeout results. Retry only contention errors (`EACCES`/`EAGAIN`), propagate other errors, and add a test proving a non-contention error propagates immediately. | skills/run-autopilot/cli/verification.py:533 | 4 | BOB |
| R10 | [1/3] | 🟡 | The hidden-flag scan retains unnecessary machinery from the deleted hashing implementation: a toplevel lookup, staged metadata, and parsing three unused fields. Replace these with the specified single `git ls-files -v -z --full-name` call without a pathspec, parsing only tag and path. This preserves whole-index coverage and removes the remaining prior R10 deviation. | skills/run-autopilot/cli/verification.py:206 | 2 | BOB |
| R11 | [1/3] | 🟡 | Rework pushes `_run_locked_gate` to 52 lines and `run_gate` to 53 according to the supplied mechanical facts. These are changed functions, outside the settled exemption for unchanged oversized functions. Shorten the repetitive exception commentary and deadline docstring while preserving their contracts to meet the 50-line limit. | skills/run-autopilot/cli/verification.py:557 | general | BOB |
| R12 | [1/3] | ⚪ | `_run_verify` resolves `log_path` (`.resolve()`), then `_refuse_verify_log` calls `log_path.resolve()` again on the already-resolved path. Drop the second call. | skills/run-autopilot/cli/__main__.py:957 | 7 | ALICE |
| R13 | [1/3] | ⚪ | Tracked-log case differs from the PRD wording. `run_gate` excludes its own log only when the log is untracked (`_untracked_log_exclusion`). The PRD says to pass `log_path` as an extra excluded path. A tracked log outside the store stays dirt, so the run records nothing and `verify` exits 3. This is safer than the PRD and documented in `skills/work/references/final-verification.md:169`, but it is a deviation. | skills/run-autopilot/cli/verification.py:276 | general | BLAKE |
| R14 | [1/3] | ⚪ | `verify --log <tracked product file>` is not refused. `_run_locked_gate` opens it with "wb" (`skills/run-autopilot/cli/verification.py:574`) and truncates it before the gate runs. The record is then correctly refused as dirty, but the file's content is lost. The PRD only requires refusing store-resolving logs, so this is a hardening gap, not a spec miss. | skills/run-autopilot/cli/verification.py:574 | general | BLAKE |
| R15 | [1/3] | ⚪ | Extras beyond the PRD, all inside packets 16 and 2. `_store_symlink_targets_changed` handles a directory alias to the repo root and also checks uncommitted store edits. The CHANGELOG records these. | skills/run-autopilot/cli/verification.py:144 | general | BLAKE |

### Auto-dismissed (ledger)

- [BLAKE] ⚪ The product-symlink scan runs `git ls-files -s` from `repo_root`, which lists only the subtree below `repo_root`. When `repo_root` is below the toplevel, a tracked symlink outside that subtree that points into the store is not seen. The hidden-flag probe correctly uses the toplevel. Absolute symlink targets and chains are taken at face value (documented in the docstring). | File: skills/run-autopilot/cli/verification.py:153 — The design doc scopes packet 16 to relative, single-hop symlink aliases and names absolute targets and chains as accepted out-of-scope limitations. Bob raised it in his KNOWN bucket, not as a defect. Widening the scope here would be new work, not a fix.

### Full Consensus (3/3)

- (none)

### Majority Consensus (>50%)

- [2/3] 🟠 The tracked-`--log` refusal was dropped by cycle 1's R9 ruling; `verify --log <tracked file>` now truncates committed product code | skills/run-autopilot/cli/__main__.py:947 | Found by: Alice, Bob
- [2/3] 🟡 The exit-1 paths (dirty refusal, HEAD moved, lock expiry) are missing from the prose and the verb docstring | skills/work/references/final-verification.md:162 | Found by: Alice, Blake

### Minority (<=50%)

Rows R3-R15 above. R3 is a second 🟠 naming the same tracked-log regression as R1 from the doubt lens.

## Alice

See the eight `[ALICE]` rows above (one 🟠, six 🟡, one ⚪) and her prior-findings check: cycle-1 R1, R2, R3, R4, R5, R6, R8, R11, R12, R13 and R14 are resolved; R7 is half-fixed (row R8 above). She ran the seven verification and CLI test files (156 passed, 0 skipped or xfailed) and pyflakes `--select F` on the changed modules.

R1: fail
R2: pass
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: fail
R10: fail
R11: pass
R12: fail
R13: pass

## Blake

Five ⚪ rows (one of them auto-dismissed by the ledger). He confirmed all 14 PRD-named tests exist, the seven verification/verb test files pass (156 tests), and `bash dev/bin/release-checks` ends with `PASS 3587 FAIL 0`; he explicitly did not confirm the new tests fail at base. Every blind rubric rule passed.

B1: pass
B2: pass
B3: pass
B4: pass
B5: pass
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

After one retry (inlined). FIX bucket: five findings (rows R3, R9, R10, R11 above, plus the exit-code claim below). VERIFY and KNOWN buckets: `(none)`.

Bob's exit-code finding, recorded here and **discarded** rather than tabled (contradicts the PRD): "Mid-run dirt now returns 3 instead of the required 1 … exit 3 requires a green, non-dirty, non-timed-out result." The PRD's own task 7 line reads "exit 3 when green but unrecorded", and its success metric is "verify exits non-zero whenever it wrote no record" — exit 3 satisfies both, and cycle 1's R1 was fixed to this shape by three-lens consensus. No 1-vs-3 change is warranted.

R1: fail
R2: fail
R3: pass
R4: fail
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

Carl: unavailable (both dispatches exit 1, `copilot` backend authentication failure). No UI/design lens this cycle; the diff is CLI and library Python with no frontend surface, so the lens gap is low-impact here.

Verdict: 15 findings
Tests: 3587 passed, 0 failed, 0 skipped (reused from last-verification.json at 1d53276 via `review-stage`'s gate reuse check — HEAD 66234dd differs from that sha only by two store-only autopilot telemetry commits, so no suite was run this cycle)
