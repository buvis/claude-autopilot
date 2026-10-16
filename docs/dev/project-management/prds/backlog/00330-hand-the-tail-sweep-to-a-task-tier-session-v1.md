---
design: skip
default_model: sonnet
model_tier_rationale: prose-only transcription of the Phase 6 hand-off (phase-review.md:312) into the tail sweep's step 3, with the exact replacement text given; two additive prose tests pin it
---

# Hand the tail sweep to a task-tier session

Source: batch 202610141430 and 202610161547 measurements of 2026-10-16: the review-phase rows and `review_converged` events in `docs/dev/project-management/autopilot/loop-metrics.jsonl`, and the 00312 review transcript (session 2adad986, claude-opus-5, 378 requests: 78 before its tail sweep began, 300 after).

## Problem

The review phase launches on opus: `_review_model` (`skills/run-autopilot/cli/routing.py:283-299`) returns OPUS for a fresh review and routes by the queued tasks' own tier only on a rework resume (`rework_resume`, `skills/run-autopilot/cli/routing.py:277-280`, PRD 00207).

When a cycle converges with a Medium/Low tail, the Tail sweep (`skills/run-autopilot/references/phase-review.md:189-201`) queues the swept tasks in `state.rework_task_ids` through `review-close --batch-id tail-sweep` and then, in step 3, invokes `/autopilot:work` inside that same opus session, so sonnet-tier fixes are orchestrated by an opus session that already holds the whole review consolidation.

Measured on 00312 (2026-10-15): the review proper took 78 requests and 11.5M cache-read tokens; the sweep of tasks 6-9 that followed took 300 requests and 113.7M cache-read tokens, about 91% of the session's $74.94. Across batch 202610141430 the review phase cost $438 of $698 and opus sessions $409, while plans grew from 3-5 PRD tasks to 9-11 (`review_converged` rows in `loop-metrics.jsonl`: `tasks_planned` 10, 9, 11, 9 against `tasks_in_prd` 3, 3, 4, 5).

Phase 6 already solved this for rework fixes: its "Dispatch rework" section (`skills/run-autopilot/references/phase-review.md:312`, PRD 00208) hands off before the first fix once `rework_task_ids` is filled, and the next session launches on the queued tasks' tier. The Phase 4 skip (`skills/run-autopilot/references/phase-review.md:22`) already resumes a Tail sweep whose task in `rework_task_ids` is unfinished ("resume at Tail sweep step 3 and continue through its step 4"). Step 4 (`skills/run-autopilot/references/phase-review.md:203`) forbids reopening the cycle, incrementing `state.cycle` or a review → review hand-off, which is why the tail sweep never got the hand-off that would use the skip.

## Solution

Make Tail sweep step 3 the same loop-mode hand-off Phase 6 performs: after step 2's `review-close --batch-id tail-sweep` has queued the sweep tasks, a session that ran Phases 4-5 writes the contract card, the brief and the `leave` row, prints a banner and ends the turn; `state.phase`, `state.next_phase` and `state.cycle` stay as they are. The next session enters through the existing Phase 4 skip on the tier `_review_model` reads from the queued tasks, invokes `/autopilot:work` there and continues to step 4. Sessions that entered through that skip, and interactive runs, invoke `/autopilot:work` directly, as today. Step 4's "do NOT hand off review → review" sentence names this one deliberate hand-off as its exception. No code changes: `cli/routing.py` and the Phase 4 skip already implement the routing.

## Requirements

### Must have
- Tail sweep step 3 of `skills/run-autopilot/references/phase-review.md` reads, for loop mode (`$_AUTOPILOT_LOOP` set) in a session that ran Phases 4-5 of this cycle: write the contract card naming the queued sweep task ids and `resume at Tail sweep step 3`; write the brief; write the `leave` row (`--site review --edge leave --phase review`); print `── AUTOPILOT ── PRD: {prd-name} ── tail sweep queued, handing off {n} task(s) ──`; END TURN, with no `phase-done` and no change to `state.cycle`, `state.phase` or `state.next_phase`. A session that entered through the Phase 4 skip, and every interactive run, invokes `/autopilot:work` in rework mode as today and never hands off again.
- Step 4 keeps its three prohibitions and adds the sentence `The step 3 loop-mode hand-off is the one exception: it keeps the cycle number and reopens nothing.`
- The `[D{cycle}] Tail sweep: <theme>` task name in step 2 and the literal labels `**3. Dispatch.**` and `**4. Finalize.**` are unchanged: the resume rule and `skills/run-autopilot/scripts/test_review_resume_prose.py:54` read them.
- Two prose tests pin the new step 3 and the step 4 exception.
- A CHANGELOG `[Unreleased]` Changed entry under **run-autopilot**.

### Nice to have
- None.

## Implementation

### Module: tail-sweep-handoff-prose
- **Location**: `skills/run-autopilot/references/phase-review.md` (Tail sweep steps 3 and 4)
- **Responsibility**: the sweep's fixes run in a session launched on the swept tasks' tier, never inside the opus review session
- **Exports**: none (prose)

### Module: tail-sweep-handoff-tests
- **Location**: `skills/run-autopilot/scripts/test_review_resume_prose.py`
- **Responsibility**: pin the hand-off sentences and the step 4 exception
- **Exports**: none
- New symbols: `test_tail_sweep_dispatch_hands_off_in_loop_mode`, `test_tail_sweep_finalize_names_the_handoff_exception`

### Dependencies
- tail-sweep-handoff-tests: No dependencies (foundation)
- tail-sweep-handoff-prose: Depends on [tail-sweep-handoff-tests]

## Tasks

### Phase 0: Foundation
- [ ] Add two tests to `skills/run-autopilot/scripts/test_review_resume_prose.py` (already registered in `dev/bin/release-checks` under `[checks] cap hook`, `dev/bin/release-checks:230`). `test_tail_sweep_dispatch_hands_off_in_loop_mode` slices `phase-review.md` between `**3. Dispatch.**` and `**4. Finalize.**` and asserts the slice contains `--site review --edge leave --phase review`, `tail sweep queued, handing off`, `END TURN`, `PRD 00208` and `entered through that Phase 4 skip`. `test_tail_sweep_finalize_names_the_handoff_exception` slices from `**4. Finalize.**` to the next fenced block and asserts it contains `do NOT hand off review → review` and `The step 3 loop-mode hand-off is the one exception` - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/scripts/test_review_resume_prose.py -k tail_sweep` reports the two new tests failing and `test_tail_sweep_prose_never_says_one_task` passing at the task's base commit.

### Phase 1: Core
- [ ] Replace the step 3 (`Dispatch`) paragraph at `skills/run-autopilot/references/phase-review.md:201` with the text below, and append ` The step 3 loop-mode hand-off is the one exception: it keeps the cycle number and reopens nothing.` to the bold sentence of step 4 at `skills/run-autopilot/references/phase-review.md:203` (the sentence that forbids changing `state.cycle`) (depends on: Phase 0) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/scripts/test_review_resume_prose.py skills/run-autopilot/scripts/test_phase_review_closes_via_review_close.py skills/run-autopilot/scripts/test_rework_groups_prose.py skills/work/scripts/test_verify_queue_prose.py` passes; `rg -c 'tail sweep queued, handing off' skills/run-autopilot/references/phase-review.md` prints 1.

  ```
  **3. Dispatch.** **Loop mode (`$_AUTOPILOT_LOOP` set), in a session that ran Phases 4-5 of this cycle: hand off here, before any sweep fix runs, exactly as Phase 6's "Dispatch rework" does (PRD 00208).** This session holds the whole review consolidation, and the swept tasks carry their own tier; running them here bills sonnet work at the review session's opus rate (measured 2026-10-15 on PRD 00312: 300 of the review session's 378 requests were its tail sweep). In this order: write the contract card naming the queued sweep task ids and `resume at Tail sweep step 3`; write the brief; write the `leave` row (`--site review --edge leave --phase review`); print the banner `── AUTOPILOT ── PRD: {prd-name} ── tail sweep queued, handing off {n} task(s) ──`; END TURN. No `phase-done`: `state.phase`, `state.next_phase` and `state.cycle` are unchanged, and the next session lands in Phase 4's skip ("resume at Tail sweep step 3") on the swept tasks' own tier (`cli/routing.rework_resume`, PRD 00207). **A session that entered through that Phase 4 skip, and every interactive run, invokes `/autopilot:work` in rework mode now, exactly as Phase 6 does, and never hands off again.** The mandatory one-verification-pass constraint is satisfied by `/autopilot:work`'s own pipeline — tests-first 2.7 for behavioral fixes, the 5.5 gate, 5.6 self-deslop, 5.7 per-task review. Nothing extra runs here.
  ```

- [ ] Add the CHANGELOG `[Unreleased]` Changed entry `**run-autopilot**: the tail sweep hands off to a session launched on the swept tasks' tier instead of running inside the opus review session` (depends on: Phase 1 prose) - Acceptance: `rg -c 'the tail sweep hands off' CHANGELOG.md` prints 1.

## Success Criteria

- On the next batch, every review-phase row in `loop-metrics.jsonl` whose session queued `[D{n}] Tail sweep` tasks is followed by a row with `phase_launched: "review"` and `model: "claude-sonnet-5[1m]"`, unless a swept task carries `model: opus`.
- `test_review_resume_prose.py` is green and still asserts the `[D{cycle}] Tail sweep: <theme>` name and the `resume at Tail sweep step 3` phrase.
