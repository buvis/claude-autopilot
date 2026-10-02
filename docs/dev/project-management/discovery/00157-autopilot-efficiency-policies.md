# Discovery: Autopilot efficiency policies

## Classification
Depth: comprehensive | Date: 2026-08-26

## Problem
A recent 12-task PRD paid the full Opus and per-task review pipeline for every task, including test-only work. Repeated self-deslop, Pat review, redundant verification, and mandatory retries for maintainability-only MEDIUM findings dominated the elapsed time without adding proportional correctness signal. The same run also encountered stale Codex hook paths, producing repeated hook churn instead of a durable repair.

The final fresh-session PRD review remains mandatory and continues to run every required lens. The goal is to remove redundant per-task work while preserving that final safety net.

## Requirements

### Must have
- Skip the self-deslop dispatch for test-only diffs.
- Skip per-task Pat review for test-only tasks; rely on narrow task verification plus the mandatory full PRD review.
- Define test-only at execution time: every path in the committed diff must be test or fixture code; any production path falls back to the normal pipeline.
- Use a conservative shared path predicate for test-only detection: conventional test/fixture directory or filename patterns qualify; inline tests inside production files do not.
- Make Pat strictly diff-only: no test runs, shell commands, or extra repository inspection; it uses only the supplied diff, acceptance criteria, and recorded verification result.
- Limit automatic retries for in-scope MEDIUM findings to correctness and security issues; style, duplication, and maintainability findings must not trigger per-task rework.
- Keep Pat's existing output shape; encode the retry distinction in severity semantics by requiring style, DRY, and maintainability-only findings to be LOW.
- Retry an invalid Pat output once with a terse contract correction; a second invalid output records `review: failed:invalid_output` and proceeds to the mandatory PRD review.
- Reserve Opus planning tiers for tasks with public-contract or algorithmic risk.
- Make automatic Opus routing task-local: actual public-contract edits or concrete novel-algorithm, concurrency, or data-migration risk only; PRD-wide keywords, generic wording, file count, and token count do not qualify by themselves.
- Route test ports and packaging work to Sonnet rather than Opus.
- Under automatic routing, pure test-port and packaging tasks are fixed at Sonnet even when a manifest is externally consumed; only an explicit Opus floor may raise them.
- Preserve explicit PRD frontmatter `default_model: opus` as an unconditional operator-selected floor over automatic routing.
- Repair stale Codex hook paths durably; zero-byte placeholders are not valid repairs.
- Add a plugin-owned Codex hook doctor that validates every configured target, repairs known hooks from canonical plugin sources, and removes unregistered zero-byte placeholders after rechecking they remain unused.
- Run the hook doctor in check-only mode once per batch before the first Codex dispatch; an unhealthy result falls back to Claude, while repair remains explicit or a one-time migration task.
- Produce three separate, sequenced PRDs: per-task review efficiency, model routing, and Codex hook integrity.

### Nice to have
- Make every skip and routing decision visible in task attempt data or phase output so efficiency changes remain auditable.

### Out of scope
- Weakening or skipping the mandatory fresh-session PRD review lenses.
- Implementing any behavior change during discovery or PRD authoring.
- Automatically mutating global Codex hook configuration during an ordinary dispatch.
- A wall-clock or token-percentage SLA; deterministic dispatch counts are the acceptance contract.

## Constraints
- Preserve fail-first task testing and the full project suite at the end of the work phase.
- Preserve the final consensus, blind, and doubt/de-slop review cycle in a fresh session.
- Avoid silent best-effort fallbacks for broken hooks.
- Keep policy decisions deterministic enough for headless execution and automated tests.

## Codebase Context
- **Relevant code**: `skills/work/SKILL.md` steps 5.5-5.7, `skills/work/references/self-deslop-prompt.md`, `skills/work/references/per-task-review.md`, `agents/pat.md`, `skills/plan-tasks/SKILL.md` step 4.7, `skills/run-autopilot/references/state-schema.md`, and host config `~/.codex/hooks.json` plus `~/.codex/hooks/`.
- **Conventions**: workflow policy lives in skill prose with contract tests; per-task tiers persist in `state.tasks`; skip outcomes are recorded in attempt state; hook registrations are tested against real non-missing targets.
- **Integration points**: `/plan-tasks` assigns the task tier, `/work` consumes tier and task/diff scope, Pat reports severity-tagged findings, and the final `/review-work-completion` phase remains unchanged.
- **Similar implementations**: docs/config tasks already skip Pat; haiku tasks already skip per-task review; step 5.6 already records `skipped:trivial`; hook registration tests already reject missing plugin-owned targets.
- **Observed hook state**: the current `~/.codex/hooks.json` targets are present, but the config and most local copies are untracked; `analyze-instincts.py` and `observe_tool.py` are zero-byte, currently unregistered leftovers. Any migration must recheck this premise and skip destructive cleanup if registration or content changed.

## Approach
- **Chosen**: split the work into three sequenced PRDs: per-task pipeline policy, planner tier routing, then Codex hook integrity.
- **Why**: the work pipeline and planner are separate policy surfaces with independent tests, while Codex host-hook repair has a different ownership and deployment boundary.
- **Rejected alternatives**:
  - One combined PRD: couples unrelated host-hook repair to plugin workflow policy and creates an oversized review surface.
  - One PRD per individual policy: splits tightly related `/work` review decisions into unnecessary coordination overhead.

## Success Criteria
- A test-only task performs its required task verification but dispatches neither self-deslop nor Pat.
- A Pat dispatch performs no commands or duplicate verification.
- Invalid Pat output causes at most one additional Pat dispatch.
- A maintainability/style/DRY MEDIUM does not cause automatic task rework; a correctness/security MEDIUM still does.
- Test ports and packaging tasks persist `model: "sonnet"`; only tasks meeting the agreed public-contract or algorithmic-risk rule persist `model: "opus"`.
- Every Codex hook registration resolves to an intentional, non-placeholder implementation and a regression test catches stale or empty targets.
- The final fresh-session PRD review remains mandatory and unchanged.
- Dispatch-count contracts hold: test-only diffs dispatch zero self-deslop and zero Pat reviewers; invalid Pat output causes at most two Pat calls total; style/DRY/maintainability findings cause zero automatic retries.

## Risks
- **Misclassifying mixed diffs as test-only**: use one conservative path predicate at planning and execution, recheck the committed diff, and fall back to the normal pipeline when any production or unknown path is present.
- **Under-routing risky work**: define task-local Opus signals and preserve explicit escalation/floor mechanisms.
- **Severity-label gaming**: define correctness/security semantics in the reviewer contract and pin them with contract tests.
- **Host-config ownership drift**: `~/.codex/hooks.json` and most `~/.codex/hooks/` copies are not tracked by the bare dotfiles index; their source implementations are split across autopilot, aegis, the legacy `buvis/home` clone, and one local-only hook.

## Discovery Log

### Q1: Should the work become three separate, sequenced PRDs covering per-task review efficiency, model routing, and Codex hook integrity?
**Answer**: Yes.

### Q2: Should test-only require every changed path to be test or fixture code, verified from the committed diff, with any production path falling back to the normal pipeline?
**Answer**: Yes.

### Q3: Should Pat keep its current output format while style, DRY, and maintainability-only findings are classified LOW, leaving MEDIUM retries for correctness/security?
**Answer**: Yes.

### Q4: Should Pat be strictly diff-only, with no test runs, shell commands, or extra repository inspection?
**Answer**: Yes; use the supplied diff, acceptance criteria, and recorded verification result only.

### Q5: If Pat violates its output contract, should the pipeline retry once, then record `review: failed:invalid_output` and continue to mandatory PRD review?
**Answer**: Yes.

### Q6: Should automatic Opus routing be task-local and limited to actual public-contract edits or concrete novel-algorithm, concurrency, or data-migration risk?
**Answer**: Yes. Remove PRD-wide keywords, generic wording, file count, and token count as independent Opus triggers.

### Q7: Should explicit PRD frontmatter `default_model: opus` remain an intentional override that raises every task?
**Answer**: Yes; keep the explicit floor for operator control and compatibility.

### Q8: Under automatic routing, should pure test-port and packaging tasks be fixed at Sonnet, with only explicit `default_model: opus` allowed to raise them?
**Answer**: Yes, including externally consumed manifests.

### Inferred: Where is the current Codex hook configuration owned?
**Answer**: It has no single tracked owner. The bare dotfiles index tracks only `.codex/hooks/notify.py`; `~/.codex/hooks.json` and other local hook copies are untracked, while source implementations are split across several repositories.

### Q9: Should the hook-integrity PRD add a plugin-owned doctor that validates configured targets, repairs known hooks from canonical sources, and removes unregistered zero-byte placeholders?
**Answer**: Yes.

### Q10: Should `/work` run check-only hook validation once per batch before Codex, falling back to Claude when unhealthy, while repair remains explicit or a one-time migration?
**Answer**: Yes.

### Q11: Should efficiency success use deterministic dispatch-count assertions rather than a wall-clock target?
**Answer**: Yes: zero self-deslop/Pat calls for test-only diffs, at most two Pat calls for invalid output, and zero retries for style/DRY/maintainability findings.

### Q12: Should test-only detection accept only standard test/fixture directories and filenames, treating inline tests inside production files as mixed production work?
**Answer**: Yes.

### Inferred: What triggered this need?
**Answer**: A specific recent PRD run repeatedly paid expensive per-task work that added little or no signal.

### Inferred: What safety behavior must remain?
**Answer**: The mandatory fresh-session PRD review runs every required lens without thinning or skipping.
