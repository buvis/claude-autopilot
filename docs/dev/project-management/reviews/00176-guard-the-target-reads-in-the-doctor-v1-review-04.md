---
prd: dev/local/prds/done/00176-guard-the-target-reads-in-the-doctor-v1.md
review: 4
date: 2026-09-05
head_sha: fdee7b9b3d147ff12e475cd1dceeb9d4bab86f63
reviewers: alice,blake,bob
agents:
  alice: available
  blake: available
  bob: available
  carl: unavailable
  eve: disabled
---

# Review: 00176-guard-the-target-reads-in-the-doctor-v1

Diff range: `4f9ca6405081eea7b869883c6b53d301e53f6080..fdee7b9b3d147ff12e475cd1dceeb9d4bab86f63`

codex_rung_guard: not fired

**Zero actionable source findings remain.** The previous permission-classification defect is resolved. Alice and Bob found no issues and passed every current R rule; Bob also passed D1–D5. Blake independently found no implementation defect. His acceptance-verification limitation and one mechanical replay observation are retained below with explicit dispositions. The formal verdict counts those two raw observations; neither requires rework.

This is a fresh standalone incremental review of the explicitly supplied PRD. No canonical task store or autopilot state exists or was created. Both completed PRD tasks have separate rows, shared original-commit provenance, and rework provenance in `dev/local/reviews/00176-artifacts/review-tasks-00176-04.md`. Original PRD base: `9336ab507525e13a685957a41b338561e74032fd`. The scoped diff contains CHANGELOG.md, the doctor, and its parse-error tests. No repository AGENTS.md/CLAUDE.md, agent_docs directory, matching design document, or local architecture note was found. The existing capsule and settled-decisions ledger were included for implementation-aware reviewers. Consensus resolves to legacy; doubt reviewer resolves to codex. Eve is not opted in; the state-based implementor guard cannot fire on this standalone path.

## Prior finding and rework

Alice and Bob independently verified that `_verdict_for` no longer calls the suppressing `Path.exists()` probe. Guarded `stat()` preserves `missing` for `FileNotFoundError` and maps other `OSError` values to `syntax_error` with their detail. The subsequent target read and compile share an error guard; disappearance after stat still yields `syntax_error`. Staleness compares the bytes already read and compiled, so there is no second target read. Verdict strings and report counting remain unchanged.

The new regression models Python 3.14's suppression on every supported Python version and fails against the incremental base. It asserts the exact permission error detail, a later target row, the summary, exit 1, and empty stderr. The existing disappearance regression moved its injection to stat/read because the exists/stat boundary was removed. Alice and Bob independently confirmed that this preserves existing coverage; it is the passing replay observation below.

Alice noticed that the previous cycle's follow-up requested a real parent-directory permission regression, while the persistent new test uses portable fault injection. The parent explicitly accepted this replacement: a real chmod-only case passes against the prior module on Python 3.13, whereas the portable suppression case fails across versions. The original PRD's real directory/read-only-repair tests remain. The coordinator additionally reproduced the real mode-000 parent-directory scenario on Python 3.14.6 at the reviewed HEAD, with the successful result below. No extra source change was needed.

## Reviewer execution and limits

All roster frontmatter was validated before prompt assembly. Each prompt was independently assembled from its current registry persona. Alice and Blake were dispatched with `fork_turns=none`; Bob followed in a third cleared subagent when a slot became available. Parent plus coordinator consume two of this host's four slots. Native Codex subagents are the available host adapter for the documented native Claude Task reviewers and Bob fallback. **Contexts are isolated, but there is no model diversity; the documented Claude model pins are unavailable on this host.**

Blake received only his persona, the verbatim PRD, the complete blind B1–B19 rubric, and the output contract. He received no diff, file list, implementation context, design, pack, previous findings, ledger, or handoff. After his sandbox blocked an acceptance command, he was asked to retain that limitation and finish the static audit. Matching verification evidence was used only during consolidation, without feeding it back into his blind context.

Alice received the full current checklist/R rubric, scoped diff, PRD, architecture context, mechanical facts, raw replay, previous findings, ledger, and matching verification record. Bob received the same implementation-aware material fully inlined with source snapshots, the complete current doubt and de-slop appendices, and D1–D5. He performed static analysis only and explicitly confirmed that the recorded verification resolves the prior runtime VERIFY. Bob's residual finding count is zero, so D1–D5 are vacuously satisfied. No FIX/VERIFY/KNOWN buckets or findings were invented.

Real Bob and Carl wrapper dispatches each returned exit 3, `refusing nested dispatch (already inside a CLI agent)`, on the initial attempt and one retry: `[RETRY] Bob attempt 1/1`, `[RETRY] Carl attempt 1/1`. No live backend started and no guard was bypassed. Bob's required doubt lens completed in the fresh native fallback. Carl is unavailable this cycle, not permanently unavailable, and has no output to consolidate. No stale CLI output or thread ID was reused.

Pack: unavailable. Engram was attempted twice and exited 1 because the checkout is not registered. Implementation-aware prompts used `(no pack available this cycle)`; no external configuration changed. The unavailable filesystem Write tool was adapted with structured apply_patch and standard-library artifact assembly, avoiding shell interpolation of prompt contents.

Reviewer output files were saved only after every reviewer completed. All issue lines and all current rubric verdicts passed format validation without a format retry: 12 R verdicts for Alice, 19 B verdicts for Blake, and 12 R plus 5 D verdicts for Bob. There is no R5 in the current consensus rubric; its numbering was preserved.

## Consolidated findings

`consolidate_findings.py` exited 0 with the existing ledger and `--ledger-dismiss BLAKE`. It produced the Blake row below and no auto-dismissed section. The required mechanical-test absorption adds the second row; no reviewer raised a duplicate. Neither row contradicts the computed mechanical facts. The rows remain visible even after disposition.

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [1/3] | 🟡 | Phase 0 acceptance remains unverified: `PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS='-p no:cacheprovider' mise exec -- uv run --no-project --with pytest python -m pytest -q skills/use-codex/scripts` was blocked opening `/Users/bob/.cache/uv/sdists-v9/.git` (Operation not permitted); `bash dev/bin/release-checks` was not run. Static inspection found no implementation defects. | dev/bin/release-checks | general | BLAKE |
| [1/3] | 🟡 | 1 touched test(s) pass against the pre-change code: test_target_deleted_after_stat_is_verdicted | skills/use-codex/scripts/test_codex_hook_doctor_parse_errors.py | general | mech-check |

Raw computed replay finding:

[MECH] 🟡 1 touched test(s) pass against the pre-change code: test_target_deleted_after_stat_is_verdicted | File: skills/use-codex/scripts/test_codex_hook_doctor_parse_errors.py | Task: general

## Decisions

1. **Resolved, Blake acceptance observation:** the exact-HEAD `last-verification.json` records successful full-suite and release-check commands. The full suite covers the doctor scripts, and the parent also ran the 91-test doctor suite on Python 3.10, 3.13, and 3.14. The immutable verification record and counts are listed below. Blake's raw output and B15 failure remain unchanged; his blocked execution was an evidence limit, not a source defect. The parent explicitly accepted this resolution.
2. **Discarded, mechanical replay observation:** `test_target_deleted_after_stat_is_verdicted` is the pre-existing disappearance regression adapted from exists/stat to stat/read after removal of exists. It preserves the same required disappearance behavior and error detail. Passing the incremental base is expected for behavior-preserving test maintenance; the genuinely new permission-suppression regression fails there. Alice and Bob independently verified this reason, and the parent explicitly approved dismissal. The verbatim computed issue and reason were appended as cycle 4 to `dev/local/reviews/00176-guard-the-target-reads-in-the-doctor-v1-ledger.json`.

There are **zero remaining actionable source findings** and no follow-up implementation tasks. Observations are reported here rather than written as tasks. Standalone mode creates no state.json, verification queue, or task store. The formal `Verdict:` preserves the two consolidated observations instead of silently dropping them after the decision gate.

## Verification

- Full suite: **2616 passed, 0 failed, 1 skipped**, plus **459 subtests passed** and **4 pre-existing warnings**. Counts are reused from the matching `last-verification.json` at the reviewed HEAD; the parent checked HEAD before and after the foreground run. Immutable copy: `dev/local/reviews/00176-artifacts/review-verification-record-00176-04.json`.
- Release checks: **224 passed**, exit 0, recorded at the same HEAD. The hermetic stub-test environment removes inherited runner markers; the real reviewer dispatches retained their recursion guards.
- Doctor suites: **91 passed** on each of Python **3.10, 3.13, and 3.14**, supplied by the parent. The record includes explicit 3.10 and 3.14 counts; the default 3.13 result is also reported in the parent handoff.
- Mechanical replay: **2 touched tests ran, 1 failed against the incremental base, 1 passed, 0 collection failures**. The failure is the new suppression regression; the passing adapted disappearance regression is explicitly dispositioned above. Full raw output: `dev/local/reviews/00176-artifacts/replay-output-00176-04.md`.
- Tautology shape scan: **13 test functions checked, no findings**. Computed AST counts keep every changed function below 50 lines. The changed Python files are **476** and **494** lines, below 800. `git diff --check 4f9ca6405081eea7b869883c6b53d301e53f6080 HEAD` passed.
- Real Python **3.14.6** parent-directory permission reproduction: **passed**, using `dev/local/reviews/00176-artifacts/reproduce-parent-permission-00176-04.py`. It asserted source HEAD before and after, restored mode in `finally`, and removed its temporary fixture.

The real reproduction creates a registered readable target under a mode-000 parent and a later readable target. `target.exists()` returns False while direct stat raises PermissionError 13. Doctor check now emits `syntax_error` with `[Errno 13] Permission denied`, followed by the later `ok` row and summary `1 ok, 0 stale, 1 broken`; it exits **1** with empty stderr. This verifies the precise Python 3.14 host behavior that failed in the previous cycle. Detailed dispatch and reproduction evidence: `dev/local/reviews/00176-artifacts/review-verification-00176-04.md`.

No coordinator duplicate full-suite, release, doctor-version-suite, or worktree-replay run was performed. The sole supplementary runtime check was the bounded real-permission reproduction requested by the parent to resolve Alice's concrete doubt. The one existing skip and four legacy warnings were not introduced by this change.

## Alice

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

[BLAKE] 🟡 Phase 0 acceptance remains unverified: `PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS='-p no:cacheprovider' mise exec -- uv run --no-project --with pytest python -m pytest -q skills/use-codex/scripts` was blocked opening `/Users/bob/.cache/uv/sdists-v9/.git` (Operation not permitted); `bash dev/bin/release-checks` was not run. Static inspection found no implementation defects. | File: dev/bin/release-checks | Task: general

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
B15: fail
B16: pass
B17: pass
B18: pass
B19: pass

## Bob

[BOB] ✅ No issues found

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

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Handoff

The coordinator made no tracked edits, commits, or branch changes. Source HEAD remained `fdee7b9b3d147ff12e475cd1dceeb9d4bab86f63` and the source tree is clean. A concurrent release-only update on master is outside this review; the parent owns integration and PRD closeout after this gated report. Preserve the reviewed doctor blob `38cc74bd4bdef87a4bdef01eaad7511349ebc91d` and parse-error-test blob `1a55bd4695e7e8ac50ffdc523ebcc839d5a1ed1d` when integrating release metadata.

The cycle contract card records zero actionable findings and the next gate as parent closeout. All raw reviewer outputs, verdicts, verification evidence, and replay dispositions are retained in the report and review artifacts.

## Integration and closeout

Integrated on master at `560f061a1bd500b9cf772a13ce86236e3b481bf4`. The doctor and regression-test Git blobs match the reviewed blobs above exactly. Concurrent v0.5.1 metadata was preserved and the new changelog entry remains under Unreleased. The full suite was rerun after integration: 2616 passed, 1 skipped, 4 pre-existing warnings, 459 subtests passed; all 224 release checks passed. The temporary implementation branch was removed, the PRD moved to done, and review scratch files were archived under `dev/local/reviews/00176-artifacts/`.

Verdict: 2 findings
Tests: 2616 passed, 0 failed, 1 skipped (reused from last-verification.json at fdee7b9b3d147ff12e475cd1dceeb9d4bab86f63; 459 additional subtests passed)
