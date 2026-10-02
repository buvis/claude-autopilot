---
prd: dev/local/prds/done/00176-guard-the-target-reads-in-the-doctor-v1.md
review: 2
date: 2026-09-05
head_sha: 31fe06b59973374da818a116ec4b3606845049d6
reviewers: alice,blake,bob
agents:
  alice: available
  blake: available
  bob: available
  carl: unavailable
  eve: disabled
---

# Review: 00176-guard-the-target-reads-in-the-doctor-v1

Diff range: `ece9ac34053a17e9629e9af50355e7c84dc32fe2..31fe06b59973374da818a116ec4b3606845049d6`

codex_rung_guard: not fired

Incremental standalone review, cycle 2. The prior review supplies the incremental base; original PRD work began at `9336ab507525e13a685957a41b338561e74032fd`. The explicit target is the only WIP PRD. No canonical task store or autopilot state exists, and neither was created. The two completed PRD task rows are recorded separately in `dev/local/reviews/00176-artifacts/review-tasks-00176-02.md`, including their shared original commit and task 2's rework commit. No design document or settled-decisions ledger exists. Consensus resolves to legacy and doubt reviewer to codex; Eve is not opted in. Without state, the state-based Codex implementor guard cannot fire.

## Prior findings

Both accepted cycle-1 findings are resolved, independently verified by Alice and Bob. `_remove_orphaned_empty` catches each target's stat/unlink `OSError`, reports `unrepairable` with its error, and processes later targets. `_repair_known` is now 42 lines and delegates guarded write/replace/cleanup to a 17-line helper; original and cleanup errors remain visible. The orphan helper is 22 lines. No current function exceeds the 50-line rubric; changed Python files are 466 and 362 lines.

## Review execution and limitations

Alice, Blake, and Bob each ran with `fork_turns=none`, in native Codex subagents using this runtime's host adapter for the skill's native reviewers. Alice and Blake ran concurrently; Bob followed when a child slot opened. One early Bob fallback spawn hit the thread limit, then succeeded after Alice finished. This preserves independent prompt disciplines but supplies no model diversity: the documented Claude pins/fallback are unavailable in this host.

Each prompt was assembled from the current registry after frontmatter validation. Blake received only his persona, the verbatim PRD, B1–B19 rubric, and output contract, with no diff, changed-file list, implementation history, prior findings, design, or pack. Alice received the current checklist, R rubric, incremental diff, and prior findings. Bob received the same implementation-aware inputs plus the current doubt/de-slop appendix and D1–D5 rubric. All reviewer issue lines and their complete R/B/D verdict sets passed format checks.

Real Bob and Carl wrapper dispatches each returned exit 3, `refusing nested dispatch (already inside a CLI agent)`, on the initial attempt and their one retry (`[RETRY] Bob attempt 1/1`, `[RETRY] Carl attempt 1/1`). No backend launched and no guard was bypassed. Bob's mandatory doubt lens completed in the fresh native fallback. Carl is unavailable this cycle, not permanently unavailable, and produced no output to consolidate.

Pack: unavailable. `engram pack` exited 1 because the repository is not registered. Implementation-aware prompts received `(no pack available this cycle)`; no registry/configuration changes were made.

## Consolidated findings

`consolidate_findings.py` exited 0 and produced three distinct findings, each [1/3]. No ledger filter applies. The shortened table preserves every finding, severity, finder, and consensus count. None contradicts the measured mechanical facts.

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [1/3] | 🟠 High | `target.is_symlink()` can raise from its target metadata read, aborting repair with exit 2 and no TSV rows. Guard it per target and continue. | skills/use-codex/scripts/codex_hook_doctor.py:198 | general | Blake |
| [1/3] | 🟡 Medium | Cleanup deletes a pre-existing read-only `.tmp` after write failed before creating it. Use a temporary file owned by this attempt and clean up only that file. | skills/use-codex/scripts/codex_hook_doctor.py:240 | 2 | Blake |
| [1/3] | 🟡 Medium | Orphan cleanup can append a second `unrepairable` row for a target already emitted by `_repair_unknown`, such as an unregistered dangling symlink. Merge its error into the existing target row and pin the full repair path. | skills/use-codex/scripts/codex_hook_doctor.py:346 | 2 | Bob |

The symlink metadata gap predates this rework and is a remaining PRD error-handling gap found through the blind lens. The temporary-file deletion was introduced in the original PRD guarded-write work and preserved by this cycle's extraction. The duplicate row is a regression in this cycle's new orphan handler. The parent accepted all three verified findings for rework. No standalone tasks or verification queue were created.

## Verification

- Full suite: **2610 passed, 0 failed, 1 skipped, 459 subtests passed**, 4 existing warnings, in 76.99s. Counts reused from the matching `last-verification.json` at reviewed HEAD; the parent ran the mandatory foreground suite, so no duplicate suite was launched here. The immutable record copy is `dev/local/reviews/00176-artifacts/review-verification-record-00176-02.json`.
- Release checks: **224 passed**, exit 0, parent-run at the same HEAD and recorded in the matching verification record. Host markers were removed only for that hermetic stub-test command; real reviewer dispatch retained every recursion guard.
- Doctor scripts suite: **85 passed**, builder-observed at reviewed HEAD.
- Mechanical fail-first replay against `ece9ac34053a17e9629e9af50355e7c84dc32fe2`: **3 touched cases ran, 3 failed against base, 0 passed, 0 collection failures**. Parent executed the exact replay command after the child sandbox denial. Output is `dev/local/reviews/00176-artifacts/replay-output-00176-02.md`.
- Tautology scan: **9 test functions checked, no findings**. Together with the replay, there are no `[MECH]` findings to absorb.
- `git diff --check ece9ac34053a17e9629e9af50355e7c84dc32fe2 HEAD` passed against reviewed HEAD.

The single skip is the existing golden transcript baseline test, whose local fixture is absent. The four warnings are the existing legacy bare-string completed-PRD schema warnings, unchanged from cycle 1. The final parent verification arrived after the independent reviewers returned; it resolves their pending-runtime notes and does not alter their source findings.

The coordinator independently verified all three residual findings with bounded reproductions:

- Python 3.12.13, target `lstat()` boundary injection with two known stale targets: doctor exit 2, empty stdout, EACCES in stderr.
- Actual filesystem case: a pre-existing mode-0444 `.tmp` in a writable directory was deleted after `write_bytes` failed; target bytes remained unchanged.
- Actual dangling symlink plus later empty orphan: `repair()` emitted two `unrepairable` rows for the symlink and a `removed` row for the later orphan.

Exact reproduction scripts, normalized outputs, dispatch limitations, and mechanical-check provenance are in `dev/local/reviews/00176-artifacts/review-verification-00176-02.md`. The probe directories cleaned themselves. Initial mechanical replay was sandbox-skipped creating `.git/worktrees/wt`; the parent was given the exact command for escalation. No replay worktree remains in the coordinator's final worktree listing.

## Alice

Both prior findings are resolved. No regressions or concrete simplifications found in the incremental diff. Full-suite, release-check, and fail-first replay verification remain pending the coordinator’s exact-HEAD records.

[ALICE] ✅ No issues found

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

## Blake

[BLAKE] 🟠 `target.is_symlink()` remains unguarded. An `OSError` from its metadata read still aborts `repair` with exit 2 and no TSV rows; reproduced on Python 3.12 by injecting `EACCES` into `lstat()`. Guard this operation and report `unrepairable` while continuing. | File: skills/use-codex/scripts/codex_hook_doctor.py:198 | Task: general
[BLAKE] 🟡 Failed writes unconditionally delete the predictable `.tmp` path, even when this attempt never created it. A pre-existing read-only `.tmp` in a writable directory fails to open, then gets deleted by cleanup. Reserve a temporary file owned by this attempt and clean up only that file. | File: skills/use-codex/scripts/codex_hook_doctor.py:240 | Task: 2

B1: fail
B2: pass
B3: fail
B4: pass
B5: fail
B6: pass
B7: pass
B8: pass
B9: pass
B10: pass
B11: pass
B12: fail
B13: pass
B14: fail
B15: pass
B16: pass
B17: pass
B18: pass
B19: pass

## Bob

[BOB] 🟡 FIX: Orphan stat failures produce duplicate repair rows when `_repair_target` already reported the target. Coordinator reproduction confirmed two `unrepairable` rows for an unregistered dangling `.py` symlink, followed by successful removal of a later orphan. Merge the cleanup error into the existing target row, preserving OSError detail, and add end-to-end coverage asserting one row per target. | File: skills/use-codex/scripts/codex_hook_doctor.py:346 | Task: 2
R1: fail
R2: pass
R3: pass
R4: fail
R6: pass
R7: pass
R8: pass
R9: fail
R10: pass
R11: pass
R12: pass
R13: pass
D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Follow-up work

Findings are reported rather than written as tasks because this is standalone; no state.json or verification queue was fabricated. All three findings are accepted; parent owns implementation.

1. **High (S):** Guard target symlink metadata errors, emit an `unrepairable` row carrying the error, and continue later targets. Add a fail-first I/O-boundary regression on a Python version whose `Path.is_symlink` can propagate EACCES.
2. **Medium, task 2 (S):** Reserve a temporary file owned by this repair attempt so a failed open cannot delete a pre-existing file; preserve partial-write and failed-replace cleanup.
3. **Medium, task 2 (S):** Merge orphan cleanup failures into already-emitted target rows, preserve OSError detail, and pin exactly one row per target in the full repair path.

The review coordinator made no tracked source edits, branch changes, or commits. Root owns subsequent rework; this evidence remains scoped to the captured HEAD. Review artifacts remain under `dev/local` as audit evidence. Next gate: resolve the findings and conduct cycle 3 in a fresh review session.

Verdict: 3 findings
Tests: 2610 passed, 0 failed, 1 skipped (reused from last-verification.json at 31fe06b59973374da818a116ec4b3606845049d6; 459 additional subtests passed)
