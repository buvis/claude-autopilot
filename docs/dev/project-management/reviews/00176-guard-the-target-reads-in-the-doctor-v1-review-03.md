---
prd: dev/local/prds/done/00176-guard-the-target-reads-in-the-doctor-v1.md
review: 3
date: 2026-09-05
head_sha: 4f9ca6405081eea7b869883c6b53d301e53f6080
reviewers: alice,blake,bob
agents:
  alice: available
  blake: available
  bob: available
  carl: unavailable
  eve: disabled
---

# Review: 00176-guard-the-target-reads-in-the-doctor-v1

Diff range: `31fe06b59973374da818a116ec4b3606845049d6..4f9ca6405081eea7b869883c6b53d301e53f6080`

codex_rung_guard: not fired

One actionable Medium finding remains: Python 3.14 suppresses a target permission error inside `Path.exists()`, returning `missing` without the required error detail. All three cycle-2 findings are resolved. Four raw consolidated rows are preserved below: the source finding, two descriptions of the same mechanical replay observation (discarded with evidence), and a runtime verification note (resolved by the matching exact-HEAD record).

This is a standalone incremental review of the explicitly supplied PRD. No canonical task store or autopilot state exists or was created. The two completed PRD task rows remain separate in `dev/local/reviews/00176-artifacts/review-tasks-00176-03.md`, including shared and rework commit provenance. Original PRD base is `9336ab507525e13a685957a41b338561e74032fd`. There is no repository AGENTS.md/CLAUDE.md, matching design document, or pre-existing settled-decisions ledger. Consensus resolves to legacy; doubt reviewer resolves to codex. Eve is not opted in. The state-based Codex implementor guard cannot fire on this standalone path.

An external release-stamp revert changed HEAD from the handoff's `6906a89` to the captured `4f9ca64` during setup. The incremental net diff was gathered after that change, before Alice and Bob dispatch, and contains only CHANGELOG.md, the doctor, and its parse-error tests. The parent reran verification with the captured SHA checked before and after the suite. The source review ended before the parent began task-1 rework; later uncommitted test edits are not part of this snapshot.

## Prior findings

Alice and Bob independently verified each prior finding:

- `_repair_known` guards `is_symlink()` metadata errors and returns an `unrepairable` row while later targets continue.
- `_write_repair` reserves the predictable temporary path with exclusive `xb` creation, retains the open handle, and cleans up only after creation succeeded. Pre-existing regular files and symlinks survive. Partial-write, replace, and cleanup errors retain the existing reporting behavior.
- Orphan cleanup excludes both registered targets and targets already emitted by repair, preventing duplicate rows for a dangling orphan while still processing later empty orphans.

The changed functions remain below 50 lines and the changed Python files are 475 and 459 lines, below 800.

## Execution and limitations

Every roster prompt was assembled independently from validated current registry frontmatter and body. Alice and Blake ran in fresh native subagents with `fork_turns=none`; Bob followed in another fresh subagent when Alice released a slot. Parent plus review coordinator consume two of this host's four slots. Native Codex subagents are the available host adapter for the documented Claude Task reviewers and Bob fallback. Contexts are isolated, but there is no model diversity and the documented Claude model pins cannot be fulfilled by this host.

Blake received only persona, verbatim PRD, blind rubric B1–B19, and output contract, with no implementation context, history, findings, diff, pack, or design. Alice received the complete current R rubric, checklist, scoped diff, mechanical facts, and previous findings. Bob received the same inputs plus the current doubt/de-slop appendix and D1–D5 rubric; his review was static-only. All issue lines and all current R/B/D verdict lines passed format validation without a retry.

Bob later read the coordinator's verification artifact and explicitly reported the permission-error issue as supplied evidence. He is a confirming reviewer, not a second independent discoverer of that issue; the script's [2/3] row counts two reporting reviewers, while independent discovery is Blake's and the coordinator separately reproduced it. This exposure occurred after Bob independently confirmed the prior fixes.

Real Bob and Carl wrapper dispatches each returned exit 3, `refusing nested dispatch (already inside a CLI agent)`, on initial attempt and one retry: `[RETRY] Bob attempt 1/1`, `[RETRY] Carl attempt 1/1`. No live backend launched and no guard was bypassed. Bob's required doubt lens completed in the fresh fallback. Carl is unavailable this cycle, not permanently unavailable, and has no output to consolidate. No stale CLI result or thread ID was reused.

Pack: unavailable. Engram exited 1 because this checkout is not registered. Implementation-aware prompts used `(no pack available this cycle)`; no external configuration changed. Mechanical replay was appended verbatim when the parent supplied it. The lack of a filesystem Write tool was handled through structured apply_patch for textual artifacts and a standard-library assembly script; no shell interpolation of prompt contents was used.

## Consolidated findings

`consolidate_findings.py` exited 0. Its four raw rows are preserved verbatim. The script did not merge the two differing descriptions of the same replay observation; the decision records below group them explicitly. There was no ledger to filter at dispatch or initial consolidation. No finding contradicts the computed mechanical facts.

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [2/3] | 🟡 | Medium: On Python 3.14.6, create a readable registered target inside a directory, then chmod its parent to 000. Direct target.stat() raises PermissionError, but target.exists() suppresses that error, causing `missing` with empty detail instead of the required `syntax_error` with OSError text. Reproduced: exit 1, remaining target processed. | skills/use-codex/scripts/codex_hook_doctor.py:54 | 1 | BLAKE, BOB |
| [1/3] | 🟡 | Both changed partial-write/replace test cases pass the incremental baseline, leaving the mandatory changed-test fail-first requirement unmet. | skills/use-codex/scripts/test_codex_hook_doctor_parse_errors.py:245 | 2 | ALICE |
| [1/3] | 🟡 | KNOWN Mechanical replay reports two touched partial-write/replace cases passing against the incremental base. These preserve existing error-handling coverage while adapting its I/O patch; forcing them to discriminate an unchanged behavior is outside this rework. | skills/use-codex/scripts/test_codex_hook_doctor_parse_errors.py:245 | 2 | BOB |
| [1/3] | ⚪ | VERIFY Cannot statically verify acceptance checks: confirm the parent’s full scripts pytest suite and bash dev/bin/release-checks both pass at captured HEAD 4f9ca6405081eea7b869883c6b53d301e53f6080. | N/A | general | BOB |

The `[MECH]` line names the same test as both replay rows; `mech-check` is added as a finder to both of those rows for the final finding record. It creates no fifth finding. The raw computed evidence is retained verbatim:

[MECH] 🟡 2 touched test(s) pass against the pre-change code: test_failed_repair_cleans_tmp_and_repairs_next_target | File: skills/use-codex/scripts/test_codex_hook_doctor_parse_errors.py | Task: general

## Decisions and actionable follow-up

1. **Accepted, Medium, task 1:** Replace the suppressing existence probe with guarded stat classification. Preserve `missing` for a nonexistent target and return `syntax_error` plus the OSError text for permission failures. Add a real parent-directory permission regression that fails at this reviewed HEAD and checks later rows continue. Root owns this source fix.
2. **Discarded, both replay rows plus mech-check:** Partial-write and failed-replace behavior is intentionally unchanged. The existing regression test moved its I/O injection from Path.write_bytes to Path.open/stream.write because exclusive creation must retain one handle. Both cases retain the original error-path assertions; all five actual new behavior cases fail against the incremental base. Passing the rework base is expected behavior-preserving regression maintenance, not unpinned new behavior. Parent decision gate accepted this dismissal. The three verbatim issue texts and reason are recorded in `dev/local/reviews/00176-guard-the-target-reads-in-the-doctor-v1-ledger.json`. Alice's and Bob's raw R2 failures remain visible; this disposition does not rewrite reviewer verdicts.
3. **Resolved, Bob runtime VERIFY:** The matching recorded suite and release commands both exited 0 at the reviewed HEAD. Counts and command provenance appear below. No standalone verification queue or tasks were created.

The formal `Verdict:` counts the four raw consolidated rows; the decision gate leaves exactly one source issue requiring rework. Findings are reported rather than written as tasks because this is standalone.

## Verification

- Full suite: **2615 passed, 0 failed, 1 skipped**, plus **459 subtests passed** and 4 existing warnings. Reused from `last-verification.json` at the captured HEAD; parent checked HEAD before and after the mandatory foreground run. The immutable copy is `dev/local/reviews/00176-artifacts/review-verification-record-00176-03.json`.
- Release checks: **224 passed**, exit 0, recorded at the same HEAD. Only the hermetic stub-test invocation removed inherited runner markers; the real reviewer attempts retained their recursion guards.
- Doctor scripts: **90 passed**, independently run by Blake. He also independently ran release checks successfully after correcting the inherited guard variables in the stub-test environment.
- Mechanical replay: **7 touched cases ran, 5 failed against the incremental base, 2 passed, zero collection failures**. The five new behavior cases fail as intended; the two passing existing error-path cases are explicitly dispositioned above. Full raw output: `dev/local/reviews/00176-artifacts/replay-output-00176-03.md`.
- Tautology shape scan: **12 test functions checked, no findings**. AST function counts and changed-file sizes meet the rubric. `git diff --check 31fe06b59973374da818a116ec4b3606845049d6 HEAD` passed against the captured source.

The one skip and four warnings are the same existing baseline skip and legacy schema warnings observed in prior cycles. Verification was not inferred from a stale SHA; the old cycle-2 record was ignored until the matching record arrived. No duplicate coordinator full-suite, release, or worktree replay was run.

Blake's CLI reproduction on Python 3.14.6 creates a registered readable target inside a directory and a later readable target, then changes the first parent to mode 000. Its direct stat raises PermissionError (errno 13); check emits `missing` with empty detail, later `ok`, and summary `1 ok, 0 stale, 1 broken`, exit 1. The coordinator independently reproduced the underlying result with real filesystem permissions:

```text
target.exists: False
target.stat: PermissionError 13
verdict: ('missing', '')
```

Both reproductions restore directory permissions in `finally`. Coordinator script and dispatch evidence are in `dev/local/reviews/00176-artifacts/reproduce-exists-permission-00176-03.py` and `dev/local/reviews/00176-artifacts/review-verification-00176-03.md`.

## Alice

[ALICE] 🟡 Both changed partial-write/replace test cases pass the incremental baseline, leaving the mandatory changed-test fail-first requirement unmet. | File: skills/use-codex/scripts/test_codex_hook_doctor_parse_errors.py:245 | Task: 2
R1: pass
R2: fail
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

[BLAKE] 🟡 Medium: On Python 3.14.6, create a readable registered target inside a directory, then chmod its parent to 000. Direct target.stat() raises PermissionError, but target.exists() suppresses that error, causing `missing` with empty detail instead of the required `syntax_error` with OSError text. Reproduced: exit 1, remaining target processed. | File: skills/use-codex/scripts/codex_hook_doctor.py:54 | Task: 1

B1: fail
B2: pass
B3: pass
B4: pass
B5: fail
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

[BOB] 🟡 FIX Supplied verification confirms Path.exists() suppresses EACCES on Python 3.14, returning missing without detail for an unreadable existing target. Classify existence from guarded stat, preserve missing for ENOENT, and add the permission regression. | File: skills/use-codex/scripts/codex_hook_doctor.py:55 | Task: 1
[BOB] 🟡 KNOWN Mechanical replay reports two touched partial-write/replace cases passing against the incremental base. These preserve existing error-handling coverage while adapting its I/O patch; forcing them to discriminate an unchanged behavior is outside this rework. | File: skills/use-codex/scripts/test_codex_hook_doctor_parse_errors.py:245 | Task: 2
[BOB] ⚪ VERIFY Cannot statically verify acceptance checks: confirm the parent’s full scripts pytest suite and bash dev/bin/release-checks both pass at captured HEAD 4f9ca6405081eea7b869883c6b53d301e53f6080. | File: N/A | Task: general

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
R12: pass
R13: pass
D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Handoff

The coordinator made no tracked source edits, commits, branch changes, state.json, or verification queue. Root owns the accepted source fix and cycle 4 must run in another fresh review session with fresh reviewer contexts. Review evidence remains under dev/local; the cycle contract card records the transition.

Verdict: 4 findings
Tests: 2615 passed, 0 failed, 1 skipped (reused from last-verification.json at 4f9ca6405081eea7b869883c6b53d301e53f6080; 459 additional subtests passed)
