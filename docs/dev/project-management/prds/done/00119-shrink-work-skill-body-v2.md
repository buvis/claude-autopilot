# Shrink work SKILL.md Under The 500-Line Ceiling, And Keep It There

> Source: claude-config audit 2026-08-09 (report:
> ~/.claude/dev/local/audit-results/2026-08-09.md); user decision "split
> situational parts".
>
> **v2 rescope 2026-08-23 (operator decision).** v1's two authorized
> extractions shipped before the 2026-08-18 batch reached this PRD
> (gate-failure.md commit d6ce116e0, Devon procedure commit 16c9bbce7) and
> autopilot parked it as spent (evidence:
> `dev/local/reviews/00119-shrink-work-skill-body-evidence.md`). The problem
> is not solved: SKILL.md was 683 lines at park and is 688 on 2026-08-23.
> **Corrected 2026-08-25 (backlog review grounding):** growth is not what keeps
> it over - the file was 683 immediately after both extractions and has gained
> only +6 lines in three commits since; it has never been at or under 500 in
> its last 40 revisions. The overage is structural: v1's Non-Goals fenced off
> the blocks that hold it. v2 is therefore: widen what may be extracted (see
> Non-Goals), trim to <= 480, AND add a size gate so future growth must
> extract at write time.
> **Renamed to `-v2` 2026-08-26 (backlog review):** this PRD now lives in the
> plugin repo, and the v1 design doc plus the v1 review ledger keyed on the old
> stem would have been reused (Phase 1.5 artifact skip; `--ledger-dismiss BLAKE`).
> Both stay on disk for GC. SKILL.md is 703 lines today (+15 from PRD 00140's
> step 7.0 style gate), so reaching 480 means cutting ~223 lines.

## Overview

### Problem Statement

`skills/work/SKILL.md` is 703 lines against the validator's 500-line ceiling
(~15K tokens loaded on every work invocation). Three extractions have shipped
(codex rung `d0c37b9f` 806 -> 737, gate-failure `d6ce116e` 813 -> 697, Devon
procedure `16c9bbce` 697 -> 683) and each landed on a file far above the
ceiling; the ~220 lines of overage sit in blocks v1 declared always-read. The
ceiling is only a WARN in create-skill's validator
(`~/.claude/skills/create-skill/scripts/validate_skill.py`, a personal skill
outside this pack: `MAX_SKILL_MD_LINES = 500` at `:21`, counted at `:315`),
which no autopilot path runs; nothing fails when the file grows.

### Target Users

The maintainer (skill stays reviewable) and every autopilot work session
(smaller always-read body).

### Success Metrics

- `skills/work/SKILL.md` <= 500 lines. (Author-machine check, not judged
  in-session: the `create-skill` validator emits no size WARN.)
- A size-gate test in the run-autopilot contract suites fails when SKILL.md
  exceeds 500 lines, proven fail-first by appending filler and watching it
  fail before it ships green.
- `test_fablectl.py` retains its full rejection power: every exploit fixture
  still REJECTS its mutation, with anchors retargeted to wherever the prose
  lives; zero fixtures deleted or weakened.
- All work/run-autopilot contract suites green (`test_fablectl.py`,
  `test_work_routing.py`, `test_work_routing_ladder_fence.py`,
  `test_golden_contracts.py`).
- Every SKILL.md pointer to extracted content mandates reading the reference
  at its trigger point (gate failure -> read gate-failure reference before
  acting), mirroring the shipped codex-implementor.md pattern.

### Non-Goals

- Rewording, slimming, or "improving" the extracted prose - this is a
  verbatim relocation plus anchor retargeting.
- Removing or reordering the always-read skeleton: the per-task loop letters,
  the routing table's decision rows, § Dashboard State Sync, and the commit
  rules stay in SKILL.md. (Widened 2026-08-25, operator decision: the
  situational machinery around them IS extractable to `references/` with
  read-at-trigger pointers - step 3's qwen breaker, batch-scoped preflight and
  codex-interception prose (~45 lines), step 5.6's self-deslop mechanics, step
  5.7's reviewer mechanics, and the routing-probe rationale. v1's blanket fence
  made 500 unreachable.)
- Relaxing any fable/one-dispatch invariant the tests enforce.
- Raising or removing the 500-line ceiling.

## Functional Decomposition

### Capability: Current overage extracted, contracts intact

#### Feature: Overage inventory and extraction
- **Description**: classify every SKILL.md section as always-read or
  situational; extract enough situational content to `skills/work/references/`
  to land at or under 480 lines (headroom so the next small edit does not
  retrip the gate); leave a hard read-first pointer at each trigger point.
- **Inputs**: SKILL.md at HEAD; test_fablectl.py anchor inventory; the diff
  since 6afaffa5b (what grew after the last extraction).
- **Outputs**: SKILL.md <= 480 lines; one or more reference files.
- **Behavior**: `test_fablectl.py` loaders/fixtures retarget to the reference
  files so every existing rejection case still fires.

### Capability: Growth forces extraction

#### Feature: Size gate
- **Description**: a contract test asserting SKILL.md <= 500 lines, living
  with the other work contracts so every autopilot run and local suite run
  enforces the ceiling.
- **Behavior**: lives in `skills/work/scripts/test_dispatch_prose.py` (it
  already reads the live SKILL.md text); counts lines the way
  `validate_skill.py:315` does (`content.count("\n") + 1`,
  which reports one more than `wc -l`) so the gate and the validator agree
  at the boundary; on failure it names the current line count and the
  extraction convention (move situational prose to references/ with a
  read-first pointer), so the fix path is in the failure message, not tribal
  knowledge.

## Implementation Phases

### Phase 0: Anchor and overage inventory
**Tasks**:
- Shipped (2026-08-15..18), no task: the anchor inventory is checked in at
  `skills/run-autopilot/scripts/test_fablectl.py:679-727` (22 test methods,
  none dropped), and the retargeting machinery shipped (`GATE_FAILURE_REF` in
  `TIER_TABLE_FILES`, `combined_doc()`, the two-file exploit fixture).
- [ ] Choose the extraction set from the widened candidates (step 3 qwen/codex
  machinery, 5.6, 5.7, routing-probe rationale) that lands <= 480 lines.
  Acceptance: a checked-in section -> keep/move table; the sentence pinned by
  `test_a_qwen_gate_pass_resets_the_breaker_counter_in_the_always_read_body`
  (`test_fablectl.py:1593-1608`, which reads SKILL.md ALONE) stays in the body.

### Phase 1: Move and retarget
**Tasks**:
- [ ] Extract the chosen set, retarget anchors (depends on: Phase 0).
  Acceptance: suites green; a spot mutation of moved prose in its reference
  file is REJECTED by the retargeted fixture (rejection power survived the
  move).
- [ ] Validator check (depends on: extraction). Acceptance: no size WARN;
  SKILL.md reference list updated; every pointer mandates read-at-trigger.

### Phase 2: Gate
**Tasks**:
- [ ] Add the size-gate test to the contract suite (depends on: Phase 1).
  Acceptance: green at HEAD; fails when 200 filler lines are appended to
  SKILL.md (fail-first proof, then revert the filler); failure message names
  the count and the extraction convention.

**Exit Criteria**: SKILL.md <= 500 lines (target 480); all four suites green;
gate mutation-proved; rejection spot-checks pass.

## Test Strategy

The contract suites ARE the test strategy; the new work is keeping their
rejection power through the move, proven by deliberate mutations (fail-first
on the retargeted fixtures), plus the size gate's own fail-first proof.

## Risks

- **Silent anchor loss** (a fixture that stops rejecting after retargeting):
  mitigated by the Phase 1 mutation spot-checks.
- **Autopilot regression from a missed pointer**: mitigated by mirroring the
  shipped codex-implementor.md pointer pattern. The live work-phase smoke on a
  toy PRD is a post-release check (the batch runs the installed plugin cache, so
  an in-session smoke cannot read the edited SKILL.md).
- **Gate blocks an urgent skill edit mid-batch**: mitigated by the 480-line
  headroom target and by the gate failing with the fix path in its message
  rather than silently.

## Carried in from PRD 00120's review — 2026-08-17

One open design question about this file, recorded here because this PRD owns it.
Source: `~/.claude/dev/local/autopilot/deferred/202608162223-deferred.json` (raised by
Ivan during 00120 task 13, surfaced rather than acted on).

`work/SKILL.md:553` (step 5.6, the self-deslop dispatch - the only occurrence in
the file; drifted from :537 and :543) specifies the name-only fallback for an **absent**
`description` only. A task whose persisted description is an empty string counts as
present, so `/work` dispatches with an empty `{{task_description}}` body instead of
falling back to the task name — and the name is the more useful payload there.

**Decided 2026-08-23 (operator): empty = absent.** The dispatch contract treats an
empty-string description like an absent one and falls back to the task name. No Python
consumer implements the fallback (`render_prompt.py` has no description handling), so this
is a prose contract: one sentence at the fallback site plus a prose-binding test in
`skills/work/scripts/test_dispatch_prose.py` pinning the empty-string wording; retarget
00120's pinned helper wording to the new contract while moving this text.
