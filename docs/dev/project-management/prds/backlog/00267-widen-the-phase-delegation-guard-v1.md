---
catchup: skip
design: skip
default_model: opus
model_tier_rationale: an invented matching predicate where both a miss and a false deny cost a session; the allowed corpus must keep passing
---

# Widen the phase-delegation guard

## Problem

The 2026-10-06 agoge run (`docs/dev/project-management/audit-results/agoge-2026-10-06.md`,
finding 8, MEDIUM, confirmed; live in v0.9.0): `hooks/guard_phase_delegation.py`
denies only the phrasings it was tuned on. Under `_AUTOPILOT_LOOP=1` these all
exit 0 (allowed) although each delegates a phase:

- `Do not hesitate to run the work phase`, `never fail to execute /autopilot:work`
- `Start the work phase`, `Do the work phase`, `Perform the work phase`, `Complete the work phase`
- `Launch /autopilot:work`, `Call /autopilot:plan-tasks`
- `Run the entire work phase`, `Run '/autopilot:work'`
- full-width `Ｒｕｎ the work phase`, and a zero-width character inside `Run` or `work`
- `Read skills/work/SKILL.md and do all tasks`

Controls `Run the work phase` and `Run /autopilot:work` exit 2. The guard
targets model drift, not a hostile user. Operator decision (2026-10-06): apply
the recommended fix.

## Solution

Normalize the prompt (NFKC, strip zero-width characters), allow up to three
words between the verb and its object, widen the verb list (`start`, `do`,
`perform`, `complete`, `launch`, `call`), accept single quotes like backticks
around a skill name, and do not treat `not`/`never` followed by
`hesitate|fail|only` as a negation.

## Requirements

### Must have
- Every phrasing above is denied.
- Every prompt in `hooks/fixtures/phase_delegation/allowed/` stays allowed.

### Nice to have
- None.

## Implementation

### Module: guard_phase_delegation
- **Location**: `hooks/guard_phase_delegation.py`
- **Responsibility**: deny whole-phase delegation to a subagent in loop mode
- **Exports**: `is_phase_delegation()` (unchanged signature)

### Module: _common
- **Location**: `hooks/_common.py`
- **Responsibility**: `read_input` fails open cleanly on any payload
- **Exports**: `read_input()` (unchanged signature)

### Module: fixtures
- **Location**: `hooks/fixtures/phase_delegation/denied/`
- **Responsibility**: one file per missed phrasing above
- **Exports**: none

### Dependencies
- fixtures: No dependencies (foundation)
- guard_phase_delegation: Depends on [fixtures]

## Tasks

### Phase 0: Foundation
- [ ] fixtures: add each phrasing above as a file under `hooks/fixtures/phase_delegation/denied/` (no deps) - Acceptance: the existing denied-corpus test in `hooks/test_guard_phase_delegation.py` fails at base on the new files.

### Phase 1: Core
- [ ] _common: `read_input` reads `sys.stdin.buffer`, decodes with `errors="replace"`, and catches `RecursionError`, failing open with the documented stderr line (agoge #21, LOW: non-UTF-8 and `[`*100000 payloads exit 1 with a traceback today) (depends on: Phase 0) - Acceptance: `test_non_utf8_payload_fails_open_cleanly` and `test_deeply_nested_payload_fails_open_cleanly` pass in `hooks/test_guard_phase_delegation.py`.
- [ ] guard_phase_delegation: NFKC plus zero-width stripping, the 3-word gap, the wider verb list, single-quote skill names, and the `hesitate|fail|only` negation exception (depends on: Phase 0) - Acceptance: `python3 -m pytest hooks/test_guard_phase_delegation.py` passes, denied and allowed corpora both included.

## Success Criteria

- `python3 -m pytest hooks/test_guard_phase_delegation.py` passes with every new denied fixture and every existing allowed fixture.
- `bash dev/bin/release-checks` exits 0.
