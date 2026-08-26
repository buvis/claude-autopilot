# Design Rationale (incident history)

The WHY behind the work skill's load-bearing rules. The rules live in
`SKILL.md` where they are enforced; this file holds the incident stories and
design arguments. Nothing here is normative — if a statement here contradicts
`SKILL.md`, `SKILL.md` wins.

## Per-task routing has no session memory (2026-06-09, ddb)

On a 9-task ddb batch, all nine tasks were `qwen_eligible: true` with healthy
qwen infra. Task 1 correctly routed to qwen; tasks 2-9 then silently went to
Claude with **no preflight recorded** — the session had generalized a routing
decision ("qwen was used already") instead of re-running the table per task.
Zero-cost local capacity sat idle for 8/9 tasks. Hence step 3's rule: re-run
the routing table for EVERY claimed task, and self-check before each Ivan
dispatch that a Claude dispatch on a `qwen_eligible` task carries a
non-`"healthy"` `preflight_outcome` justifying the fallback.

## Parallel rework is capped at 2 agents (2026-06-25 RAM lockout)

An uncapped 3-way parallel cargo rework fan-out (18 rustc jobs each) exhausted
48 GB of RAM, triggered jetsam, logged the user out, and locked the machine.
Parallel agents share one working tree and one build lock, so their compiles
serialize anyway — but each `cargo` invocation still spawns a full `rustc`
fleet. The caps in "Parallel dispatch for independent rework fixes" (max 2
agents, never raise `CARGO_BUILD_JOBS`/`--jobs`, no full-workspace builds
inside a parallel agent) bound that fleet; the global `~/.cargo/config.toml`
`[build] jobs` cap is the backstop.

## Why self-deslop is a fresh dispatch, not an Ivan prompt extension

Ivan's prompt already injects the code-quality rules block. Adding "after
passing tests, prune your diff" to the same prompt is cheap but ineffective:
same model + same session + "this is my work" attachment defeats slop
detection — empirically, models defend their own output. A separate dispatch
with task-as-external framing breaks that loop while staying at the same tier
budget (step 5.6 dispatches at `state.tasks[i].model`).

## Why the infrastructure circuit breaker exists (step 4.2)

Two back-to-back infrastructure failures (lost result / watchdog-killed hang)
on the same task, silently re-dispatched in a loop, caused a multi-hour stall.
One re-dispatch is recovery; a second failure on the same task is a pattern —
stop and escalate with `stall_reason: subagent_infra_failure`.

## Why the pipeline is tier-gated (PRD 00044)

Devon (adversarial test validation, step 2.85) is the most expensive
quality-gate dispatch and pays off on the hardest tasks — so only `opus`-tier
tasks run it. Per-task code review (step 5.7) is skipped only on `haiku`-tier
tasks: cheap mechanical tasks rely on per-task test verification plus the
PRD-level review lenses (consensus, blind, doubt — every review cycle), which
review every task's diff regardless of tier. Escalation restores depth
automatically: when the review gate escalates a task to `opus`, the rework
attempt regains Devon with no extra mechanism. Tier source: `state.tasks[i].model`
set by `/plan-tasks` (PRD 00025), escalated by the review gate's Phase 6.

## Why qwen gets exactly one shot per task (PRD 00031)

The local qwen lane exists for zero-token-cost wins on small backend tasks the
test gate keeps honest. A qwen attempt that fails its tests has already spent
the cheap try; retrying qwen risks a loop on a model that plainly wasn't up to
the task, so the step-5.5 re-dispatch escalates straight to Claude Sonnet and
the remaining retry budget runs entirely on Claude. The qwen attempt does not
consume a step-5.5 retry slot — it consumed the single qwen attempt.

## SKILL.md extraction map (2026-08)

PRD 00119-v2, Phase 0. `SKILL.md` was 703 lines against a 500-line ceiling. The
overage is situational machinery read at one trigger point, so each block below
moves **verbatim** into a reference and leaves a read-first pointer at its
trigger. Line ranges are at HEAD `cae4b36`; the "keeps" are the sentences that
stay in the always-read body because a rule, a table row, or a test anchor
depends on them being there.

| # | Block | Lines | Destination | Keep in SKILL.md | Test that reads it |
|---|---|---|---|---|---|
| 1 | § 5.6 self-deslop mechanics (dispatch contract, prompt construction, outcome table) | 549-568 | `self-deslop-prompt.md` § Procedure | heading, best-effort rule, skip rule with both commands, description-fallback sentence, outcome-logging sentence | `test_dispatch_prose.py` (new empty-description pin) |
| 2 | § 3 codex-rung interception fences and `#### Codex implementor mechanics` | 388-407, 444-455 | `codex-implementor.md` | the one-line interception rule and the never-`-y` / kill-before-fallback invariants | none |
| 3 | § 3 qwen batch-scope check, row-3 consult, batch-scoped preflight | 423-424, 435-442 | `qwen-integration.md` | the routing table rows, the breaker-reset sentence (`:425`) | `test_fablectl.py::test_a_qwen_gate_pass_resets_the_breaker_counter_in_the_always_read_body` reads SKILL.md ALONE - the reset sentence must not move |
| 4 | § 3 rationale (why fence 4 is required, why row 3 is codex-eligible) | 411, 413 | `design-rationale.md` | the fence list itself | none |
| 5 | § 5.7 reviewer mechanics (haiku rationale, sonnet-runner dispatch, result handling) | 580, 596-603, 605-606 | `per-task-review.md` (new) | tier-gate table, the `pat.md` render block, the `medium-retry:` sentence naming `FILES_TOUCHED` | `test_dispatch_prose.py::test_pat_dispatch_is_rendered_through_render_prompt_py`, `::test_step_5_7_gives_in_task_medium_findings_one_retry_stamped_medium_retry`; `test_fablectl.py` `check_review_row` (the table) |
| 6 | § 6.5 task-boundary handoff mechanics | 629, 632-648 | `task-boundary-handoff.md` (new) | heading, the marker trigger rule, the no-pending-tasks skip | none |
| 7 | § 2.8 test quality gate rubric and retry render | 280-297 | `test-author-prompt.md` § Quality gate | the gate rule, the total-Tess-budget rule | none |
| 8 | § 1.5 rework-mode mechanics (status, attempt fields, abort semantics) | 196-209 | `rework-mode.md` (new) | the two-mode filter table | none |
| 9 | § 2.95 red-check detail and outcome table | 336-350 | `red-check.md` (new) | the `n/a:new_module` rule, the skip-when-2.7-skipped rule | none |
| 10 | § 5.5 retry render block and the `_AUTOPILOT_ESCALATION == "legacy"` branch | 512-521, 527-530 | `gate-failure.md` (already in `combined_doc`: zero anchor work) | heading, scope rule, the never-weaken-tests rule, the default-flow pointer | `test_fablectl.py` `check_budget` / `check_no_auto_escalation` / `check_retry_repair_excludes_fable` already scan `gate-failure.md` |
| 11 | § 2.7 "Tess receives / does NOT receive" bullets and the post-render notes | 247-252, 267-274 | `test-author-prompt.md` § Context Selection | the `tess-prompt.md` render block, the budget rule | `test_dispatch_prose.py::test_tess_dispatch_is_rendered_through_render_prompt_py` |
| 12 | § 4.2 infrastructure circuit-breaker steps and § 4.5 | 471-475, 479 | `gate-failure.md` | the two headings, the one-re-dispatch rule, the escalate-on-second rule | none |
| 13 | § 7 "What to run", improvised-suite rule, failure handling | 658-679 | `final-verification.md` (new) | heading, the run-once mandate, all of § 7.0, the `fully green` stop condition, the report line | `test_dispatch_prose.py::test_step_7_*` (all four read § 7 / § 7.0 - nothing they touch moves) |
| 14 | § CRITICAL blocked-verification and cargo-backgrounding paragraphs | 46, 48 | `subagent-dispatch.md` | the never-ask rule and its two exceptions | none |

Rows 13-14 extend the PRD's candidate list: rows 1-12 alone land at ~510 lines,
above the 500-line hard bar.

## Why per-task verification stays narrow

Per-task full-suite runs compound to 40+ minutes of redundant test time across
a 20-task phase, so step 5.5 runs only the tests Tess wrote for the task and
the full suite (workspace tests, smoke, integration, lint) runs exactly once
in step 7.

## Why the loop steps are lettered (2026-08)

The per-task loop steps in `SKILL.md` § CRITICAL: One Task at a Time are
lettered on purpose - they are a conceptual sequence, distinct from the numbered
section headers (`### 1`...`### 7`) that the rest of the skill cross-references.
"step 7" always means the section, never a loop step.

## Why step 2.5 loads rich context

1M context makes it practical - richer prompts produce better first-pass
results, so the main session front-loads AGENTS.md, the active PRD and the
relevant module interfaces instead of making the implementor hunt for them.

## Why the routing model is kept in sync by review

`scripts/work_routing.py` is a decision model of step 3's table and the codex
interception, tested in isolation by `scripts/test_work_routing.py`; it is kept
in sync with the prose by review, not by a test that flips red when the prose
changes. The one exception is the `codex_eligible` fence itself:
`test_work_routing.py` extracts it live from `model-ladder.md` § Codex rung, so
editing a clause's field or value, adding or removing a clause, or changing the
`OR` that joins them, all flip a test red (see
`test_codex_eligible_agrees_with_every_clause_extracted_from_the_real_ladder`
and `test_extractor_raises_when_the_fence_joins_clauses_with_a_non_or_combinator`).
A cosmetic reword of the fence's own opening line (e.g. renaming the pseudocode
parameter) does not - the extractor's fence-selection match is deliberately
loose there. The guard binds the fence to `_codex_eligible`, not the reverse:
widening `_codex_eligible` to a value no clause and no candidate in
`_CODEX_ELIGIBLE_CANDIDATES` names is not caught, so an edit there still needs
review.
