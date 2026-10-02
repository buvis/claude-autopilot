---
prd: 00175-restore-the-gemini-reviewer-lane-v1.md
date: 2026-09-05
mode: manual
base_head: ad1b20721ec2f5e0b724008fc7a15175a54a8ada
context_isolation: fork_turns=none
verdict: complete
---

# PRD 00175 manual implementation review

Implemented all three phases without running autopilot or its review ceremony.
Changes remain uncommitted in the working tree; pre-existing Qwen changes were
preserved, including their portions of CHANGELOG.md and state-schema.md.

## Result

- Copilot's interactive `/model` picker offered Gemini Flash models and rejected
  the former Pro Preview pin. Selected `gemini-3.8-flash`; a live dispatch verified
  inference works. The bundled SDK listing omitted Gemini, so that listing was
  not treated as authority over the observed successful dispatch.
- Exit 4 identifies permanent model/client-tier rejection. Exit 3 remains the
  recursion guard. Eligible default prompt runs try native Gemini once; explicit
  backend/model/session choices do not switch after rejection. Transient errors
  retain their status, except child 3/4 map to 1 to preserve reserved meanings.
- Stderr streams live through a FIFO and is captured for classification. Failed
  permanent dispatches publish no partial review file; existing destinations
  remain untouched. Successful fallback output contains only the fallback's text.
- Review instructions latch Carl's failure for the batch, preserve the original
  cycle/PRD, omit later dispatches and the ui lens, and emit the required skip
  line. Closed interactive batch rollover clears the latch and its provenance.
- An opt-in forced-Copilot probe uses the single production pin. No live model
  call was added to release checks.

## Independent reviews

Each reviewer was spawned with `fork_turns: none`; no implementation conversation
was inherited. The blind prompts contained only the PRD and repository path,
plus read-only instructions. Reviews ran independently before consolidation.

| Lane | Fresh task | Outcome |
| --- | --- | --- |
| Requirements | `/root/final_requirements` | No findings across all PRD phases. |
| Blind | `/root/final_blind` | Found interactive rollover retention; confirmed fix, no new findings. |
| Doubt and simplicity | `/root/final_doubt` | No remaining defects; R1–R5 all pass after live evidence was supplied. |
| Gemini | New Copilot session `815d8735-7ce6-45d1-a0c8-8e0269a74b70` | No correctness or integration findings; inline complete review packet. |

An earlier independent round (`review_requirements`, `review_blind`,
`review_doubt`, also with no inherited context) found the newly added PRD Phase 2,
hidden interactive stderr prompts, and the watcher's missing-file wait on
terminal rejection. All were fixed before the final round. The initial Gemini
packet omitted schema/changelog content; those packet-only findings were resolved
by providing the complete packet and running the fresh Gemini review above.

## Verification

- Final `dev/bin/release-checks`: **224 passed, 0 failed** (118 registry/contract,
  5 hook, 41 Codex runner, 33 Gemini runner, 27 Sonnet runner).
- Updated Carl contracts plus existing lifecycle tests: **22 passed**.
- Skeptical reviewer: **202 focused pytest checks**, **nine additional hermetic
  cases**, and all six final Carl contract tests passed. Actual schema validation
  and per-PRD reset preserved both batch fields and sibling entries, while
  clearing the prior review lens roster.
- New batch contracts were observed failing before their prose implementation;
  rollover regression likewise failed before the fix. Runner tests failed on
  the old runner for the new rejection/fallback/status behaviors.
- Bash syntax, scoped Ruff checks/format, and `git diff --check` passed.
- Live runner selected `backend=copilot model=gemini-3.8-flash`, exited **0**, and
  wrote **804 bytes** of reviewer output. Second run: **2.7 AI credits**, **4m24s**.
  The live test explicitly omitted inherited CLI recursion markers for this
  authorized root-level acceptance call; the guard code remains intact and tested.

Receipts: [release checks](00175-manual/release-checks.txt),
[final Gemini output](00175-manual/carl-final.txt),
[final Gemini packet](00175-manual/carl-final-prompt.txt).

No full autopilot rejection → later cycle → next PRD scenario was executed.
That agent-driven behavior was checked through prose contracts, source tracing,
and actual state validation/reset tests; this is the manual workflow's remaining
validation limit. The Gemini review packet predates the final rollover-only
fix, which the blind and doubt reviewers verified afterward.

## Cleanup

PRD tasks marked complete and moved to `dev/local/prds/done/`. No worktrees,
branches, or plan files were created for this task. Task-local scratch files were
removed; the final packet and output are retained here as review evidence.
