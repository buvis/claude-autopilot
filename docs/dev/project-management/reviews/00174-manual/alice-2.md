---
prd: dev/local/prds/backlog/00174-align-qwen-routing-with-single-file-trust-v1.md
review: 2
date: 2026-09-05
head_sha: ad1b20721ec2f5e0b724008fc7a15175a54a8ada
agent: alice
---

New PRD findings: none. All seven cycle-1 repairs are verified. The two items below are baseline-only bookkeeping, not newly introduced acceptance failures or requests to expand PRD 00174.

[ALICE] 🟡 Baseline-only mandatory MECH finding: test_step_4_7_binds_contract_edit_to_the_task_s_own_edits hedges with `or`: either outcome satisfies it; the supplied test-shapes.md requires carrying this finding, and git show HEAD confirms the test is unchanged by this PRD | File: skills/plan-tasks/scripts/test_plan_tasks_prose.py:255 | Task: general
[ALICE] ⚪ Baseline-only R13 debt: test_work_routing.py already exceeds 800 lines; this PRD adds only the required file_paths argument to its existing routing fixture, so splitting the existing suite is not required for PRD 00174 acceptance | File: skills/work/scripts/test_work_routing.py:148 | Task: general

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
R13: fail

Reviewed the PRD, cycle-2.diff, mechanical-facts.md, test-shapes.md, rework-1.md, applicable Alice instructions, dimensions, rubric, output contract, current callers and surrounding recovery rules. No review pack was supplied. The separate routing-tuner/ledger edits are outside this diff. The older context.md validation is superseded by the cycle-2 evidence supplied with this assignment.

R2 concerns new or changed tests: the mandatory MECH item is an unchanged baseline test and does not fail that rule. R13 is a literal size verdict; the supplied mechanical facts locate existing functions beyond line 800. The successful diff-scoped style gate is compatible with this result: check_style_limits.py intentionally reports files newly pushed across the limit, while this file was already oversized. No new or changed function exceeds 50 lines in the supplied mechanical facts.

| Prior repair | Verification | Result |
|---|---|---|
| 1. Index shortcuts hide Tess mutations | check_qwen_output.py:51 reads committed mode/blob and actual disk content independently of the index; :67 retains the separate cached comparison. All four before/during-dispatch combinations of assume-unchanged and skip-worktree pass real-Git regression tests. Independent deletion, executable-mode and symlink mutations each returned qwen_test_mutation, restored canonical tests and preserved implementation/foreign content. | Closed |
| 2. Failed or killed Qwen bypasses test integrity | work/SKILL.md:339 requires the tests-only guard after stopping every unsuccessful helper. gate-failure.md:243 repeats the failure-table prerequisite; subagent-dispatch.md:73 puts it before watchdog partial-work verification. CLI tests prove unchanged tests retain handle_failure and mutated tests select Sonnet. | Closed |
| 3. Dispatch self-check contradicts effective exclusions | work/SKILL.md:329 checks the effective decision, admits file/test-only/preparation exclusions, preserves actual preflight attribution and excludes direct capability escalations from initial routing. Prose regression passes. | Closed |
| 4. Split example advertises two-file Qwen | plan-tasks/references/task-examples.md:101 now requires independent one-file gates and retains the correlated metrics/export or internal-interface/caller slice above Qwen. Planner tests pin both separable and inseparable examples and preserve the context-budget rule. | Closed |
| 5. Repository ancestors named tests disable Qwen | work_routing.py:124 consumes the caller's explicit is_test_only; the caller contract specifies repository-relative classification. check_qwen_output.py:34 normalizes paths before its own classification. Routing matrices and an independent actual guard run below a tests/project ancestor pass. | Closed |
| 6. Duplicate schema meanings conflict | state-schema.md:181 admits runtime files in the attempt signature and points to its dedicated field row; :182 describes both output causes and correct lower/higher row ownership; :198 includes pre-commit capability rejection in the breaker meaning. attempt-logging.md agrees. Authority-section prose tests pass. | Closed |
| 7. Batch report loses runtime files | render_report.py:324 includes the files bucket and counts each task once per bucket. Exact-output tests prove deduplication across attempts and distinct plan/runtime populations. batch-report-format.md states that population distinction. | Closed |

Requirement coverage is complete for the scoped behavior. Planning requires one distinct nonempty implementor write and preserves UI/tier/contract precedence. Runtime zero-file input fails closed; stale two/three-file tasks retain every existing Codex fence. Healthy single-file tasks still reach Qwen. No-edit classification ignores foreign staged work; mutation takes precedence, checks both worktree and index, and cannot proceed to staging/gating. Recovery preserves the one-shot Sonnet edge, separates attempt rows, avoids unsafe branch resets and preserves the canonical oracle. Test-only work stays on the Claude path. Qwen guidance, ladder, causes, schema, telemetry and changelog agree.

Independent verification:

- Focused planner, existing routing, new trust, guard, prose and report tests: **256 passed in 3.97s**, with no skips. Command: `GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 PYTHONDONTWRITEBYTECODE=1 /Users/bob/.local/share/mise/installs/python/latest/bin/python -m pytest -q -p no:cacheprovider skills/plan-tasks/scripts/test_plan_tasks_prose.py skills/work/scripts/test_work_routing.py skills/work/scripts/test_check_qwen_output.py skills/work/scripts/test_qwen_trust.py skills/work/scripts/test_qwen_trust_prose.py skills/run-autopilot/cli/test_qwen_exclusion_report.py`.
- The first run inherited host Git configuration and errored while creating disposable fixture commits, before any guard assertion; isolated Git configuration resolved all 17 fixture setup errors. No source adjustment was needed.
- Disposable real-Git probes additionally exercised a bare repository with explicit work-tree, a repository beneath a tests ancestor, a filename containing spaces and shell metacharacters, and deleted/mode-changed/symlink Tess tests. The clean case proceeded; each mutation rejected and restored only its test; foreign symlink-target content and HEAD remained unchanged. Temporary probes were removed by their temporary-directory contexts.
- Active-rule search found no remaining Qwen three-file trust claim in the planner, work references, ladder references, agents or README. Historical changelog entries remain history.
- Supplied cycle-2 evidence: full suite **2555 passed, 32 pre-existing skipped, 459 subtests passed**; release checks, plugin validation, isolated Ruff, style regression limits and diff checks passed. Supplied context/rework notes report fail-first regressions for initial behavior and executable repairs; no independent replay artifact was provided.

Security and simplicity review found no new acceptance defect. The guard uses argument-vector Git calls with literal pathspecs, validates canonical owned paths before dispatch, explicitly reports indeterminate checks, and permits restoration only on the caller's ownership proof plus unchanged HEAD. The small executable guard, pure decision model and prose call sites follow the existing architecture. No behavior-preserving simplification justified a new Medium finding.

No live Qwen dispatch or autopilot loop was run, as required by this manual-review scope. Prose orchestration is verified by source tracing and contract tests; model adherence in a live batch remains outside the supplied evidence.
