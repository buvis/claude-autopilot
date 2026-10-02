---
prd: dev/local/prds/wip/00190-bind-the-codex-run-tests-and-dedupe-their-split-v1.md
review: 1
date: 2026-09-14
head_sha: 3324a4845c26aa0c40bdbddaf7cecdae84ee46f6
codex_thread_id: 01a0a0b1-af81-7343-a428-a1f5f87707b7
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00190-bind-the-codex-run-tests-and-dedupe-their-split-v1

Diff range: `7f7713a846243855f72dcb7dd6be8c7b80b395a2..3324a4845c26aa0c40bdbddaf7cecdae84ee46f6`

codex_rung_guard: not fired

pack: failed (`engram pack` exited 1 — "not inside a registered repo; register it in /Users/bob/.config/gita/repos.csv"; the same deterministic error the 00187, 00188 and 00189 cycles recorded, so no retry was spent). `{PACK_FILE}` and `{PACK_FINDINGS}` were substituted with the literal `(no pack available this cycle)` in every prompt that takes them. The review is degraded by the missing retrieval context, not invalid.

scope note: cycle 1, full review of the PRD's whole work range (4 commits, 5 files, +247/-341). `gather-context.sh` was run with `--since 7f7713a8…` (`state.work_start_sha`) because its default base is `master` and the batch works on `master`, so the bare form yields an empty diff; the context file's scope label was corrected by hand to say "full review". Blake stayed blind: PRD and rubric only, no filesystem-notes block (`dev/local` is a real directory — `readlink` exits 1 — and the root has no dot prefix). No design doc exists (`design: skip`). No Python in the diff, so the mechanical-facts, tautological-shapes and fail-first-replay blocks cover nothing (all three files skipped as non-python; "Checked 0 test function(s)"; "replay: skipped (the diff touches no test function)") — the PRD's bash-level replay against `bb08599~1` was performed by Alice, Blake and Carl instead (evidence in their sections).

bob note: codex ran this cycle (exit 0, first dispatch, thread `01a0a0b1-…` captured for the next cycle's `--resume-thread`). No `Cannot statically verify` lines, no lack-of-input shape, all twelve `R` lines and five `D` lines present, so no retry was spent. Bob's `File:` values carry `:line` suffixes and are kept as he wrote them.

verification queue: none written this cycle. Bob emitted six FIX items and explicit `VERIFY: - (none)` / `KNOWN: - (none)`, so there is nothing to queue; Eve did not run (`doubt_reviewer: codex`, no codex-implemented task).

## Review Summary

Reviewed: 3 completed tasks
PRDs checked: 00190-bind-the-codex-run-tests-and-dedupe-their-split-v1

### Agent Status

- Alice: ✅ Available (Claude subagent, sonnet; ran both harnesses (22 + 25 passed), the fail-first replay against `bb08599~1` in a disposable worktree (unreadable case FAILs there, `20 passed, 2 failed`, exit 1), the root SKIP branch via an `id` PATH shim, `test_record_dispatch.py` (14 passed) and `release-checks` (exit 0); 1 🟡, all twelve R rules pass)
- Blake: ✅ Available (Claude subagent, sonnet, blind/PRD-only; reconciled the case inventory against the 483/524-line baseline (45 → 47 PASS lines, only the two named label exceptions), replayed against `bb08599~1` in a worktree (FAIL, exit 1), exercised the root SKIP via a PATH shim, ran `release-checks` (exit 0); 1 🟠, 1 🟡, 1 ⚪; B1, B4, B15 fail)
- Bob: ✅ Available (codex, exit 0, static analysis; doubt + de-slop lens; 6 issue lines: 4 🟡, 2 ⚪; R1/R2/R9 fail, D1-D5 pass)
- Carl: ✅ Available (gemini-run backend=copilot model=gemini-3.8-flash, exit 0; ran both harnesses and `release-checks` with the host dispatch markers unset, replayed against `bb08599~1` via `git show` into a temp dir, exercised the root SKIP through a python-launched PATH shim, and probed `/bin/bash` 3.2's empty-array subscript; 1 🟠, 2 🟡; R9 fails)

## Consolidated Findings

7 findings: 8 rows from `consolidate_findings.py` (two paraphrase merges by the script: the 413-line row to `[4/4]`, the plain-path `-` row to `[3/4]`) with one further cross-reviewer paraphrase merged by the orchestrator (Blake's ⚪ and Bob's ⚪ F5 on the `[checks] dispatch ledger` label — the script kept them apart because Bob's `File:` carries a `:24` suffix) into one `[2/4]` row. No `[MECH]` lines to absorb (no Python in the diff). No 🔴 Critical; **one 🟠 High** (`[3/4]`, orchestrator-confirmed by reading case 2b); 4 🟡 Medium; 2 ⚪ Low.

Every reviewer with a shell (Alice, Blake, Carl) independently confirmed the PRD's three runtime metrics: the unreadable-prompt case FAILs against `bb08599~1` and PASSes against the current runner with the exact stderr text, the root branch SKIPs under a faked `id -u`, and `release-checks` runs `test_record_dispatch.py` green. The findings are all spec-fidelity gaps in the tests, not runner defects.

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [3/4] | 🟠 High | Leading-dash case's plain-path assertion (2b) never checks the final argv token is "-", only stdin bytes, though the PRD's Behavior requires "captured stdin equals the file bytes and argv ends with - on each" of plain/json/resume; json (2c) and resume both include the check, plain does not / Bob F1: Plain leading-dash case checks stdin bytes but omits the required final `-` argv assertion / Carl: Plain path leading-dash case does not assert argv ends with '-' | skills/use-codex/scripts/test_codex_run.sh | 2 | Blake, Bob, Carl |
| [4/4] | 🟡 Medium | `test_codex_run_resume.sh` is 413 lines, over the PRD's stated "two scripts under 400 lines each" output contract (Features and contracts > Shared helper file). It was 388 lines right after task 1's extraction (commit 91ca091) and crossed 400 when task 2 added the resume-path leading-dash case (~25 lines); the repo-wide 800-line ceiling (R13) is still satisfied / Bob F3 / Blake / Carl | skills/use-codex/scripts/test_codex_run_resume.sh | 2 | Alice, Blake, Bob, Carl |
| [1/4] | 🟡 Medium | F2: New JSON/resume leading-dash cases never assert their dispatch mode; a plain invocation or fresh fallback can satisfy their checks. | N/A (skills/use-codex/scripts/test_codex_run.sh:77, test_codex_run_resume.sh:91) | 2 | Bob |
| [1/4] | 🟡 Medium | F6: New leading-dash cases remove output files before use even though their unique paths are inside a freshly created temporary directory; remove these redundant cleanup commands. (deferred by design, reason below) | N/A (test_codex_run.sh:70, test_codex_run_resume.sh:84) | 2 | Bob |
| [1/4] | 🟡 Medium | Unchecked negative array index on empty ARGV_ARR causes bad array subscript in bash 3.2 (deferred by design, reason below) | skills/use-codex/scripts/test_codex_run.sh | 1 | Carl |
| [2/4] | ⚪ Low | Release-checks block is labeled "[checks] dispatch ledger" rather than the PRD's literal "[checks] record_dispatch"; functionally correct (rg -c count and green run both hold) / Bob F5 | dev/bin/release-checks:24 | 3 | Blake, Bob |
| [1/4] | ⚪ Low | F4: Folded JSON marker check retains its standalone PASS label instead of the required combined host label. | skills/use-codex/scripts/test_codex_run.sh:189 | 1 | Bob |

### Decision gate (Phase 5)

Cycle 1 < rework cap 3, one 🟠 High unresolved → not converged → rework. Every decision is in `state.autonomous_decisions` (5 new entries) or `state.deferred_decisions` (2 new entries); the two by-design deferrals are in `00190-bind-the-codex-run-tests-and-dedupe-their-split-v1-ledger.json` and mirrored into the batch deferred JSON. No settled deferrals from a prior cycle (cycle 1), no cap-overflow, no scope alarm (1 follow-up task), no recurring issue, no verification queue.

- **Auto-fix, reworked (5 findings → 1 `[D1]` task):**
  - The 🟠 plain-path `-` assertion: confirmed by reading `test_codex_run.sh:47-61` — case 2b diffs `$DASH_PROMPT_FILE` against `$STUB_STDIN_FILE` and never reads `$STUB_ARGV_FILE`; cases 2c and the resume case both check `${ARGV_ARR[last]} = "-"`. Additive (one `read_argv_array` plus a conjunct and a label change), so auto-fix at any severity.
  - The `[4/4]` 413-line Medium: measured by the orchestrator (`wc -l` = 145 / 350 / 413). The PRD's Output contract says "two scripts under 400 lines each"; the resume script crossed it when task 2 added its 25-line case. Fix by condensing commentary in `test_codex_run_resume.sh` (its 7-line header and per-case banner comments) without dropping any case or assertion — mechanical.
  - F2 (Medium, 1/4): confirmed — case 2c asserts stdin bytes and the final `-` only, so a regression that ran the `-f` prompt through the plain (non-`--json`) path would still pass it; the resume-path case likewise never checks `exec resume <uuid>`, so a silent fresh-fallback would pass it. Additive: one `argv_has_pair "--output-last-message" "$DASH_JSON_OUTFILE"` conjunct on 2c and an `exec resume <uuid>` prefix check on the resume case, mirroring case 14's shape.
  - F4 (Low): the PRD's Shared helper file Behavior says the folded cases' "old labels become combined host labels"; the fresh-JSON marker fold kept its own PASS line ("--emit-thread-id: final argv token is the literal '-' stdin marker") beside case 10 instead of joining case 10's label. Fold the final-token conjunct and label into case 10 (the stdin check of the `--emit-thread-id` block).
  - The `[2/4]` label Low: rename the echo at `dev/bin/release-checks:24` to `[checks] record_dispatch`, the PRD's literal name.
- **Deferred by design (2 findings, `deferred_decisions` + ledger `settled-deferral` + batch deferred JSON; batch-end review may overrule):**
  - F6 (`rm -f` before use): the two new cases copy the pattern every sibling case in both harnesses already uses (`rm -f "$RESUME_OUTFILE"` at `test_codex_run_resume.sh:22`, the `--emit-thread-id` block in `test_codex_run.sh`); deleting the lines from the new cases alone would leave the harness inconsistent, and touching the pre-existing cases is outside the PRD's "preserve all baseline cases" contract. Cost is two no-op `rm -f` calls.
  - Carl's empty-`ARGV_ARR` subscript: confirmed on `/bin/bash` 3.2.57 by the orchestrator (`/tmp/warden-task-negidx.sh`: prints `bad array subscript` on stderr and takes the FAIL branch; the script continues). The pattern is baseline — case 14 (`RESUME_LAST_IDX`, `test_codex_run_resume.sh:31`) and the old case 45 use it unchanged — and it only fires when codex was never invoked, which the case already reports as FAIL; the verdict is correct, only the diagnostic gains a stderr line. A guard would touch pre-existing cases, outside the PRD's contract.

## Follow-up Tasks Created

One `[D1]` task at tier `sonnet` (classifier default `sonnet`; the PRD's `default_model: sonnet` floor leaves it unchanged), covering 5 of the 7 findings; `state.rework_task_ids = ["4"]`.

1. Task 4 — `[D1]` Bind the plain-path leading-dash case to the `-` marker, assert the json/resume dispatch modes, fold case 45's label into case 10, trim `test_codex_run_resume.sh` under 400 lines, rename the release-checks block to `record_dispatch` (S) - 🟠 High - 5 findings

## Alice

Consensus lens, Claude subagent (sonnet). She read the diff and the three harness files, ran both harnesses, `test_record_dispatch.py` and `release-checks`, replayed the current harness against `bb08599~1` in a disposable worktree and exercised the root SKIP via a PATH shim; cleaned both up and confirmed `git status --short` clean. 1 🟡 Medium (she also wrote `[ALICE] ✅ No other issues found`, dropped before consolidation so it would not read as an all-clear), all twelve R rules pass.

```
[ALICE] 🟡 `test_codex_run_resume.sh` is 413 lines, over the PRD's stated "two scripts under 400 lines each" output contract (Features and contracts > Shared helper file). It was 388 lines right after task 1's extraction (commit 91ca091) and crossed 400 when task 2 added the resume-path leading-dash case (~25 lines); the PRD's 5 numbered acceptance metrics don't restate this cap, and the repo-wide 800-line ceiling (R13) is still satisfied, but the explicit "under 400 lines each" design contract in the PRD text is not met by either the pack context or a re-split. | File: skills/use-codex/scripts/test_codex_run_resume.sh | Task: 2

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
```

Evidence: `wc -l` → 350 / 413 / 145; `bash skills/use-codex/scripts/test_codex_run.sh` → `SUMMARY: 22 passed, 0 failed`, exit 0; `bash skills/use-codex/scripts/test_codex_run_resume.sh` → `SUMMARY: 25 passed, 0 failed`, exit 0; `git worktree add /tmp/codex-replay-00190 bb08599~1` then the current harness against that worktree's `codex-run.sh` → unreadable-prompt case FAILs (`ERROR: Prompt required` instead of the guard's exact message), `SUMMARY: 20 passed, 2 failed`, exit 1 (the other failure is case 43, the whitespace case, which also predates the old runner's guard); root shim → `SKIP: unreadable prompt file: running as root, chmod 000 files are still readable`, `21 passed, 0 failed`, exit 0; `rg -n '^child_stdin_is_prompt\(\) \{' skills/use-codex/scripts/*.sh` → one hit in the helper; `test_record_dispatch.py` → 14 passed; `bash dev/bin/release-checks` → exit 0.

## Blake

Blind lens, Claude subagent (sonnet), PRD and rubric only. He located the three harness files, the runner, `release-checks` and the CHANGELOG; verified the single `child_stdin_is_prompt` definition and both `source` lines; reconciled the case inventory against the `730bcc9^` baseline (483/524 lines, `rg -c 'PASS "'` 21 + 24 = 45, matching the PRD's problem statement; now 22 + 25 = 47 with only the root-SKIP and plain/json/resume exceptions); replayed against `bb08599~1` in a detached worktree (exit 1, unreadable case FAILs with the old `Prompt required` text); exercised the root SKIP with a PATH shim (exit 0, 21 passed); ran `release-checks` (exit 0); confirmed the CHANGELOG Unreleased line names both forms with the 0.5.2 line untouched, and that `codex-run.sh` has only a comment-only commit (`6ee0aca`) since `bb08599`. 1 🟠, 1 🟡, 1 ⚪; B1, B4 and B15 fail on his own findings.

```
[BLAKE] 🟠 Leading-dash case's plain-path assertion (2b) never checks the final argv token is "-", only stdin bytes, though the PRD's Behavior requires "captured stdin equals the file bytes and argv ends with - on each" of plain/json/resume; json (2c) and resume both include the check, plain does not | File: skills/use-codex/scripts/test_codex_run.sh | Task: Phase 1
[BLAKE] 🟡 test_codex_run_resume.sh is 413 lines, exceeding the PRD's stated Output "two scripts under 400 lines each" by 13 lines (test_codex_run.sh is 350, compliant) | File: skills/use-codex/scripts/test_codex_run_resume.sh | Task: Phase 0
[BLAKE] ⚪ Release-checks block is labeled "[checks] dispatch ledger" rather than the PRD's literal "[checks] record_dispatch"; functionally correct (rg -c count and green run both hold) | File: dev/bin/release-checks | Task: Phase 2

B1: fail
B2: pass
B3: pass
B4: fail
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
```

## Bob

Doubt + de-slop lens, codex (static-only sandbox), first dispatch, no retry. 6 issue lines (4 🟡, 2 ⚪), six FIX items, empty VERIFY and KNOWN buckets. R1, R2 and R9 fail on his own findings (F1/F2 for R1/R2, F3/F4/F5 for R9); D1-D5 pass. The orchestrator confirmed F1, F3, F4 and F5 by reading the cited lines and F2 by reading cases 2c and the resume-dash case against case 14; F6 is deferred by design (pattern matches every sibling case).

```
[BOB] 🟡 F1: Plain leading-dash case checks stdin bytes but omits the required final `-` argv assertion. | File: skills/use-codex/scripts/test_codex_run.sh:56 | Task: 2
[BOB] 🟡 F2: New JSON/resume leading-dash cases never assert their dispatch mode; a plain invocation or fresh fallback can satisfy their checks. | File: N/A | Task: 2
[BOB] 🟡 F3: Resume harness remains 413 lines; the PRD requires both harnesses under 400. | File: skills/use-codex/scripts/test_codex_run_resume.sh:4 | Task: 1
[BOB] ⚪ F4: Folded JSON marker check retains its standalone PASS label instead of the required combined host label. | File: skills/use-codex/scripts/test_codex_run.sh:189 | Task: 1
[BOB] ⚪ F5: Release-check header prints `[checks] dispatch ledger`; the PRD specifies `[checks] record_dispatch`. | File: dev/bin/release-checks:24 | Task: 3
[BOB] 🟡 F6: New leading-dash cases remove output files before use even though their unique paths are inside a freshly created temporary directory; remove these redundant cleanup commands. | File: N/A | Task: 2

R1: fail
R2: fail
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: fail
R10: pass
R11: pass
R12: pass
R13: pass

FIX:

- F1, missing marker assertion — skills/use-codex/scripts/test_codex_run.sh:56 — Assert this invocation's final argv token equals `-`.
- F2, unproven dispatch modes — skills/use-codex/scripts/test_codex_run.sh:77 and skills/use-codex/scripts/test_codex_run_resume.sh:91 — Assert JSON flags/output target and the resume `exec resume <uuid>` prefix on the corresponding captures.
- F3, PRD size limit — skills/use-codex/scripts/test_codex_run_resume.sh:4 — Condense redundant introductory and case commentary to reach at most 399 lines while retaining every assertion.
- F4, separate marker label — skills/use-codex/scripts/test_codex_run.sh:189 — Combine the marker and host stdin checks under a label naming both.
- F5, header mismatch — dev/bin/release-checks:24 — Change the header to `[checks] record_dispatch`.
- F6, redundant removals — skills/use-codex/scripts/test_codex_run.sh:70 and skills/use-codex/scripts/test_codex_run_resume.sh:84 — Delete the two unnecessary `rm -f` commands.

VERIFY:

- (none)

KNOWN:

- (none)

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass
```

## Carl

Consensus lens, gemini-run backend=copilot model=gemini-3.8-flash, exit 0, no retry. Read the context, the diff, the PRD, the runner, `release-checks`, the CHANGELOG and both harnesses; ran both harnesses and `release-checks` with the host dispatch markers unset; replayed the current harness against `bb08599~1` (runner extracted with `git show` into a temp dir); exercised the root SKIP through a python-launched PATH shim; probed `/bin/bash` 3.2's behavior on an empty array's `-1` subscript; confirmed the single helper definition and no TODO/FIXME markers. No frontend surface, reviewed as a generalist. 1 🟠, 2 🟡; R9 fails.

```
[CARL] 🟠 Plain path leading-dash case does not assert argv ends with '-' | File: skills/use-codex/scripts/test_codex_run.sh | Task: 2
[CARL] 🟡 File length is 413 lines, exceeding PRD requirement of two scripts under 400 lines each | File: skills/use-codex/scripts/test_codex_run_resume.sh | Task: 1
[CARL] 🟡 Unchecked negative array index on empty ARGV_ARR causes bad array subscript in bash 3.2 | File: skills/use-codex/scripts/test_codex_run.sh | Task: 1

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
R13: pass
```

## Mechanical checks

- Mechanical facts: all five changed files skipped (non-python); `wc -l` measured by the orchestrator: helper 145, `test_codex_run.sh` 350, `test_codex_run_resume.sh` 413.
- Tautological shapes: none (0 test functions in 0 files checked — bash harnesses are outside the script's reach).
- Fail-first replay: skipped (the diff touches no test function). The PRD's bash-level replay was performed by Alice, Blake and Carl: the current harness against `codex-run.sh` at `bb08599~1` FAILs the unreadable-prompt case (old text `ERROR: Prompt required`), exit 1; against the current runner it PASSes.

Verdict: 7 findings

Tests: 667 passed, 0 failed, 0 skipped (suite run this cycle: `bash dev/bin/release-checks` at 3324a484, exit 0 — 560 pytest passes across ten blocks plus 107 bash-harness PASS lines, summed by the orchestrator; `last-verification.json` matched the sha but carried null counts)
