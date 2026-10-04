---
catchup: skip
design: skip
default_model: sonnet
model_tier_rationale: transcription only - exact expressions given; every change is pinned by a named test that fails at base
---

# Tighten the phase-delegation guard

## Problem

PRD 00248 shipped `hooks/guard_phase_delegation.py` and capped out with two
HIGH findings, minted as hold stubs 00252 (ledger key `d37079d4a34e`) and
00253 (ledger key `b5a752c97f4a`), batch `202610031511`. Both were confirmed
at HEAD on 2026-10-04:

- **00252, missed delegation:** `_negated_before` trims at the FIRST sentence
  boundary in its 20-char window and does not treat a comma as a boundary, so
  `is_phase_delegation({"prompt": "Never stop, run the work phase for PRD 7."})`
  and `{"prompt": "OK; not now. Run the work phase for PRD 7."}` both return
  `False` (measured).
- **00253, false denial:** 5 of 235 real reviewer prompts are still denied,
  all of them prompts reviewing this guard (they quote its denied phrases).
  Reviewer personas cannot run a phase skill at all: every one declares
  `tools:` without `Skill` (`agents/alice.md`, `blake.md`, `eve.md`,
  `victor.md`: `Read, Bash`; the rest `Read`).

## Solution

Trim at the LAST boundary, counting a comma as one, and skip the predicate
for dispatches to the read-only reviewer personas.

## Requirements

### Must have
- Both 00252 examples are denied; `"Do not run the work phase."` stays allowed.
- An Agent call whose `subagent_type` is a reviewer persona is never denied.
- Hold stubs 00252 and 00253 leave `docs/dev/project-management/prds/hold/`.

### Nice to have
- None.

## Implementation

### Module: guard_phase_delegation
- **Location**: `hooks/guard_phase_delegation.py`
- **Responsibility**: deny whole-phase delegation to a subagent in loop mode
- **Exports**: `is_phase_delegation()` (unchanged signature)

### Dependencies
- guard_phase_delegation: No dependencies (foundation)

## Tasks

### Phase 0: Foundation
- [ ] guard_phase_delegation: in `_negated_before`, replace the
  `_SENTENCE_BOUNDARY_RE.search` block (the `boundary = ...` line and its `if`)
  with `preceding = _SENTENCE_BOUNDARY_RE.split(preceding)[-1]`, and change
  `_SENTENCE_BOUNDARY_RE` to `re.compile(r"[.;,\n]")`; update the docstring to
  say the LAST boundary wins and a comma counts. Add to
  `hooks/test_guard_phase_delegation.py`:
  `test_negation_before_a_comma_does_not_hide_delegation`
  ("Never stop, run the work phase for PRD 7." -> True),
  `test_negation_in_an_earlier_clause_does_not_hide_delegation`
  ("OK; not now. Run the work phase for PRD 7." -> True) and
  `test_direct_negation_still_allows` ("Do not run the work phase." -> False)
  - Acceptance: `python3 -m pytest hooks/test_guard_phase_delegation.py`
  passes, and the first two new tests fail against the old code.
- [ ] guard_phase_delegation: add
  `_READ_ONLY_REVIEWERS = frozenset({"autopilot:alice", "autopilot:blake", "autopilot:bob", "autopilot:carl", "autopilot:cora", "autopilot:eve", "autopilot:grace", "autopilot:mallory", "autopilot:pat", "autopilot:rita", "autopilot:toby", "autopilot:trent", "autopilot:victor"})`
  and, at the top of `is_phase_delegation` after the dict check, `return False`
  when `tool_input.get("subagent_type") in _READ_ONLY_REVIEWERS`. Add
  `test_reviewer_dispatch_quoting_the_guard_is_allowed` (subagent_type
  `autopilot:blake`, prompt "run the work phase" -> False),
  `test_worker_dispatch_is_still_checked` (subagent_type
  `autopilot:worker-sonnet`, same prompt -> True), and
  `test_every_exempt_reviewer_lacks_the_skill_tool`, which reads each exempt
  persona's `agents/<name>.md` frontmatter and asserts `Skill` is not in its
  `tools` line - Acceptance: `python3 -m pytest hooks/test_guard_phase_delegation.py` passes.

### Phase 1: Core
- [ ] triage: delete `docs/dev/project-management/prds/hold/00252-triage-guard-phase-delegation-s-negation-window-v1.md`
  and `docs/dev/project-management/prds/hold/00253-triage-five-of-235-real-reviewer-prompts-are-st-v1.md`
  (depends on: Phase 0). Premise: both files still exist and name ledger keys
  `d37079d4a34e` and `b5a752c97f4a`; re-check at execution, and if either is
  gone or names another key, skip that file and report - Acceptance:
  `test ! -e` on both paths.

## Success Criteria

- `test_negation_before_a_comma_does_not_hide_delegation`,
  `test_negation_in_an_earlier_clause_does_not_hide_delegation`,
  `test_direct_negation_still_allows`,
  `test_reviewer_dispatch_quoting_the_guard_is_allowed`,
  `test_worker_dispatch_is_still_checked` and
  `test_every_exempt_reviewer_lacks_the_skill_tool` pass.
- `bash dev/bin/release-checks` exits 0.
