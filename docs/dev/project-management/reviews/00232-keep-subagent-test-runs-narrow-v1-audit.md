# Decision Audit Log: 00232-keep-subagent-test-runs-narrow-v1

PRD: `00232-keep-subagent-test-runs-narrow-v1.md`
Started: 2026-10-01T00:20:02Z
Completed: 2026-10-01T00:20:02Z
Autonomous: 6  |  Deferred: 4  |  Doubts: 0

### [autonomous] 2026-10-01T00:20:02Z

**Decision**: Consolidation split one defect across two rows. BOB cited skills/work/SKILL.md:71 as the false claim; ALICE and BLAKE cited skills/work/references/tess-retry-prompt.md:32 as the omission making it false.

**Choice**: merged into one 3/4 HIGH row at the decision gate

**Rationale**: consolidate_findings.py merges paraphrases only when they name the same file, so a defect cited at its cause and at its symptom stays split. Gate judgment on issue text plus file says these are one finding. Merging raises consensus from 2/4 to 3/4 and keeps the rework batch from carrying two tasks for one fix. Recorded because the script counted 9 rows and the review file states 8.

### [autonomous] 2026-10-01T00:20:02Z

**Decision**: BOB doubt-lens VERIFY item asks to inspect the next batch last-session.log for Tess/Devon/Ivan whole-directory runs.

**Choice**: not queued: command shape

**Rationale**: The verification-check queue accepts one runnable project verification command. This item names an inspection of an artifact that does not exist until the next batch, so it yields no such command. It stays an ordinary finding and was discarded as the PRD post-release metric, unevaluable pre-release. No checks-1.json was written this cycle because no VERIFY item qualified.

### [autonomous] 2026-10-01T00:20:02Z

**Decision**: test_adversarial_prompt_carries_narrow_in_feedback_section only proves NARROW appears once somewhere after the "## Feedback to Tess" heading, not inside the fenced template; moving the paragraph below the closing fence still passes and Tess would never receive the rule

**Choice**: auto-fix via the cycle-2 tail sweep

**Rationale**: Medium with a clear mechanical fix (slice the fenced body and assert NARROW inside it). Raised by Alice and Bob independently (2/4). Swept, not deferred: Medium never blocks convergence but is fixed in one task before finalize.

### [autonomous] 2026-10-01T00:20:02Z

**Decision**: Redundant .rstrip() follows _norm(), which already strips leading and trailing whitespace (test_narrow_runs_prose.py:182)

**Choice**: auto-fix via the cycle-2 tail sweep

**Rationale**: Medium at 1/4 consensus and a behavior-preserving simplification; the de-slop lens raised it. Classification routes Medium/1-of-N and mechanical fixes to auto-fix.

### [autonomous] 2026-10-01T00:20:02Z

**Decision**: Task 4 Process step 3 rewording and the Rule 6 single-line rejoin have no pin; the step-3 wording can regress silently and _norm hides the wrap (test_narrow_runs_prose.py:174)

**Choice**: auto-fix via the cycle-2 tail sweep

**Rationale**: Low severity, any consensus, and additive only (adds assertions, changes no product prose). Classification routes it to auto-fix.

### [autonomous] 2026-10-01T00:20:02Z

**Decision**: mech-check fail-first replay: 6 of 8 touched tests pass against the pre-change code at be7da2c

**Choice**: discarded (behavior-preserving carve-out), ledgered

**Rationale**: Task 5 strengthened pins over prose cycle 1 had already shipped, so a pin over already-correct prose necessarily passes at that base; its value is failing on a future deletion, which the task acceptance verified by temporary edit. The replay block states this carve-out itself. The two tests covering task 4 NEW prose do fail at base. Alice reviewed the same block and passed R2.

### [deferred] 2026-10-01T00:20:02Z

**Decision**: NARROW hard-codes pytest flags (-q --tb=line) in a stack-agnostic pack, and "Read the pass count and exit code from that one run" has an ambiguous antecedent (the orchestrator run the subagent cannot read).

**Choice**: deferred to batch end

**Rationale**: The PRD mandates the NARROW sentence verbatim and the code reproduces it exactly, so the defect is in the spec wording, not this change. Needs a follow-up PRD against the NARROW text.

### [deferred] 2026-10-01T00:20:02Z

**Decision**: skills/fast-track/SKILL.md:495 RETRY_INSTRUCTION ends "keep the suite green", which pulls Ivan toward the whole-suite run the new narrow-run sentence forbids.

**Choice**: deferred to batch end

**Rationale**: Pre-existing text in a file this PRD neither touches nor names; fixing it here would widen the diff beyond scope.

### [deferred] 2026-10-01T00:20:02Z

**Decision**: The PRD-mandated sentence at skills/work/SKILL.md:71 asserts every subagent prompt carries the same narrow-run sentence, but the PRD own Devon feature specifies different wording for Devon. The claim cannot be made true for Devon without rewording the mandated sentence or giving Devon the NARROW paragraph.

**Choice**: deferred to batch end

**Rationale**: Internal PRD inconsistency needing a spec decision, not an implementation fix. Cycle 1 rework fixes the unambiguous Tess half.

### [deferred] 2026-10-01T00:20:02Z

**Decision**: Scope beyond the PRD four insertion points: NARROW also lands in skills/work/references/tess-retry-prompt.md:34 and inside the "Feedback to Tess" template at skills/work/references/adversarial-test-prompt.md:96, with four extra pinning tests. The PRD Repository Structure names only tess-prompt, ivan, adversarial and SKILL.md.

**Choice**: deferred to batch end

**Rationale**: Requirements ambiguity in the PRD, not a defect in the change: the PRD file list names four files while the sentence the PRD mandates at skills/work/SKILL.md:71 asserts EVERY subagent prompt carries the rule. Cycle 1 High 3/4 was exactly that omission, and task 4 made the mandated claim true rather than rewording it; reverting the extras would re-open it. Blake is blind by design and grants the extras are consistent with the intent, harmless and passing. Same root as the cycle-1 deferral of the Devon "same sentence" inconsistency - resolve both as one spec decision against the PRD text.
