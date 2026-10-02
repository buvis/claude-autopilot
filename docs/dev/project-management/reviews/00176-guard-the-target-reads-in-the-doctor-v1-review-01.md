---
prd: dev/local/prds/done/00176-guard-the-target-reads-in-the-doctor-v1.md
review: 1
date: 2026-09-05
head_sha: ece9ac34053a17e9629e9af50355e7c84dc32fe2
reviewers: alice,blake,bob
agents:
  alice: available
  blake: available
  bob: available
  carl: unavailable
  eve: disabled
---

# Review: 00176-guard-the-target-reads-in-the-doctor-v1

Diff range: `9336ab507525e13a685957a41b338561e74032fd..ece9ac34053a17e9629e9af50355e7c84dc32fe2`

codex_rung_guard: not fired

Full review, cycle 1, scoped to the explicit authorized base. `gather-context.sh --since` was used solely to select that base; this is not an incremental review. No prior review or ledger exists for this PRD.

Standalone manual review: no autopilot state exists and none was created. No canonical task store exists. The two completed PRD task rows both name shared commit `ece9ac34053a17e9629e9af50355e7c84dc32fe2`; see `dev/local/reviews/00176-artifacts/review-tasks-00176-01.md`. The consensus engine defaults to legacy; the doubt reviewer defaults to codex. Eve is not opted in, and the state-based Codex implementor guard cannot fire without state.

## Review execution and limitations

Alice, Blake, and Bob each ran in a fresh native Codex subagent with `fork_turns=none`. Alice and Blake were dispatched concurrently; the two available reviewer slots required Bob to follow. Bob was dispatched by the parent coordinator after an approval wait interrupted this coordinator. Each initial prompt was assembled from the current registry persona and rubric. Blake received only the blind persona, verbatim PRD, B1–B19 rubric, and output contract; no diff, implementation summary, changed-file list, design document, pack, or review history was passed to him.

The native host adapter preserves the independent prompt disciplines but does not provide model diversity: Alice's/Blake's Claude Sonnet pins and the documented Claude fallback are unavailable here; all completed reviewers used native Codex subagents. Bob received the current consensus rubric plus the doubt and de-slop appendix and D1–D5. Bob's independently authored reproduction was executed by the parent after his sandbox restriction.

Bob and Carl CLI attempts both returned exit 3, `refusing nested dispatch (already inside a CLI agent)`. Their one retry each returned the same result: `[RETRY] Bob attempt 1/1`, `[RETRY] Carl attempt 1/1`. No real backend launched and no recursion guard was bypassed. Bob's mandatory doubt lens completed via the fresh native fallback. Carl is unavailable for this cycle (dispatch refusal, not permanent model rejection), produced no reviewer output, and is omitted from consolidation.

Pack: unavailable. `engram pack` exited 1 because this repo is not registered. Prompts received the mandated `(no pack available this cycle)` sentinel. No registry/configuration edits were made.

## Consolidated findings

Consolidated with `consolidate_findings.py`, exit 0. All issue lines and required R/B/D verdicts were format-valid. The table below preserves the script's two merged findings and consensus counts; wording is shortened for readability.

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [3/3] | 🟠 High | Repair still loses every row when a read-only hooks directory contains an unregistered empty `.py` file: `_remove_orphaned_empty` raises from `unlink()` after guarded writes accumulated results. Guard its per-target stat/unlink operations and add the mixed-directory regression. | skills/use-codex/scripts/codex_hook_doctor.py:296 | 2 | Alice, Blake, Bob |
| [2/3] | 🟡 Medium | `_repair_known` is now 53 lines, exceeding the 50-line limit. Extract its guarded write/replace/cleanup operation into a focused helper, preserving the original and cleanup error details. | skills/use-codex/scripts/codex_hook_doctor.py:184 | 2 | Alice, Bob |

Both findings are accepted for rework. The cleanup path predates this diff, but it defeats this PRD's stated read-only-directory/no-lost-rows success criterion; Alice reproduced it live, Blake traced it independently, and the parent independently executed Bob's reproduction: exit 2, empty stdout, PermissionError for `hooks/unused.py`.

The function-size finding agrees with the mandatory AST measurement: `_repair_known` is 53 lines. No finding contradicted the mechanical facts.

## Verification

- Full suite independently run this cycle: `mise exec -- uv run --no-project --with pytest --with rich --with textual python -m pytest -q skills`; exit 0, **2608 passed, 1 skipped, 459 subtests passed**, in 79.14s.
- Blake independently ran the complete doctor scripts suite: **83 passed** in 0.86s.
- Mechanical replay against `9336ab507525e13a685957a41b338561e74032fd`: **8 touched test cases failed, 0 passed**; zero collection failures. All added regressions pin changed behavior.
- Mechanical tautology check: 8 test functions checked, **no findings**. There are no `[MECH]` findings to absorb.
- `git diff --check 9336ab507525e13a685957a41b338561e74032fd HEAD` passed.
- Release checks: **224 passing checks, builder-observed on identical HEAD**. This coordinator's rerun was denied access to the uv cache, and its escalation remained pending until interrupted. Parent instructed no further rerun. These 224 checks are not claimed as independently rerun here. Host markers were unset only for that hermetic stub-test command, never for real reviewer dispatch.
- The existing `last-verification.json` names stale SHA `57ed616f4022e5ab623a173924202b6ba8fb16fd`; no count was reused from it.

The one suite skip is the existing golden transcript baseline test in `skills/work/scripts/test_check_build_overhead.py:593`; its referenced local transcript fixture is absent. It is unrelated to this diff. The four warnings are existing `UserWarning` messages from `skills/run-autopilot/cli/schema.py:199`: legacy bare-string completed-PRD entries `00001-x.md` in two schema tests, and `00120-migrate-task-tracking-to-statectl-v1.md` plus `00001-legacy-string-entry-v1.md` in the golden-fixtures schema test.

Detailed commands, warning attribution, mechanical blocks, and tool limitations are saved in `dev/local/reviews/00176-artifacts/review-verification-00176-01.md`.

## Alice

[ALICE] 🟠 Repair still loses every row when a read-only hooks directory contains an unregistered empty `.py` file: reproduced exit 2 with empty stdout after both guarded writes failed. `_remove_orphaned_empty` then raises from `unlink()`. Guard its stat/unlink operations per target and extend the read-only regression fixture with an empty orphan. | File: skills/use-codex/scripts/codex_hook_doctor.py:296 | Task: 2
[ALICE] 🟡 `_repair_known` is now 53 lines, exceeding the 50-line limit. Extract its guarded write/replace/cleanup operation into a focused helper, preserving the original and cleanup error details. | File: skills/use-codex/scripts/codex_hook_doctor.py:184 | Task: 2
R1: fail
R2: pass
R3: pass
R4: fail
R6: pass
R7: pass
R8: pass
R9: fail
R10: fail
R11: pass
R12: fail
R13: pass

## Blake

[BLAKE] 🟠 Repair still exits 2 without TSV rows when a read-only hooks directory contains an unregistered empty `*.py`: guarded writes accumulate `unrepairable` results, but `_remove_orphaned_empty` then raises from unguarded `unlink()` before reporting them. Its unguarded `stat()` similarly aborts on dangling or disappearing targets. Guard both cleanup operations and extend regression coverage. | File: skills/use-codex/scripts/codex_hook_doctor.py:289 | Task: general

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
B14: fail
B15: pass
B16: pass
B17: pass
B18: pass
B19: pass

## Bob

[BOB] 🟠 FIX: A read-only hooks directory containing an unregistered empty .py still aborts repair during orphan cleanup, discarding every accumulated row. Root executed my isolated reproduction with two stale registered hooks plus unused.py: exit 2, empty stdout, PermissionError from unused.py. Guard the cleanup scan's per-target stat/unlink errors, report unrepairable, and add this mixed-directory regression. | File: skills/use-codex/scripts/codex_hook_doctor.py:296 | Task: 2
[BOB] 🟡 FIX: _repair_known grew to 53 lines according to the supplied mechanical count, exceeding R12's 50-line limit. Extract the guarded write/cleanup operation into a focused I/O helper to separate validation from mutation. | File: skills/use-codex/scripts/codex_hook_doctor.py:184 | Task: 2
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
R12: fail
R13: pass
D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Follow-up work

Findings are reported rather than written as tasks because this is standalone; no state.json or verification queue was fabricated. Root owns implementation.

1. **High, task 2 (S):** Guard each cleanup stat/unlink failure, emit an `unrepairable` row including the OSError, and continue remaining targets. Pin the read-only-directory case with an unregistered empty orphan and the relevant stat-race failure.
2. **Medium, task 2 (S):** Extract the guarded copy/replace/cleanup operation so every function respects the 50-line rubric; preserve the existing error-detail behavior.

No tracked source, branch, or commit was changed during review. The mechanical replay removed its temporary worktree. Review inputs and outputs remain under `dev/local` as audit evidence. The next gate is rework followed by a fresh review session at cycle 2.

Verdict: 2 findings
Tests: 2608 passed, 0 failed, 1 skipped (suite run this cycle; 459 additional subtests passed)
