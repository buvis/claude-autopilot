# PRD 00119 — Premise check failure (Phase 2 planning)

## What the PRD asks for

Success metric: `create-skill` validator emits no size WARN for
`skills/work/SKILL.md` (<= 500 lines), achieved by extracting two situational
blocks (step-5.5 gate-failure machinery, step-2.85 Devon procedure) per the
design doc.

## What's already true on disk

Both design-scoped extractions are already implemented and committed, prior
to this session:

- `d6ce116e0` — refactor(work): extract step-5.5 gate-failure machinery to
  reference file. `skills/work/references/gate-failure.md` exists;
  `test_fablectl.py` already carries `GATE_FAILURE_REF`, the `combined_doc()`
  helper, the retargeted `TIER_TABLE_FILES`, and the generalized
  `WorkSkillExploitRejectionTest` (two-file `skill_copy`/`gate_copy` fixture) —
  exactly matching the design doc's Interfaces & contracts section.
- `16c9bbce7` — refactor(work): extract step-2.85 Devon procedure to
  adversarial-test-prompt.md. `skills/work/references/adversarial-test-prompt.md`
  already has a `## Procedure` section.

`git status --porcelain` on `skills/work/` and
`skills/run-autopilot/scripts/test_fablectl.py` is clean — nothing
uncommitted, nothing mid-flight.

## Why the acceptance criterion is still unmet

`python3 skills/create-skill/scripts/validate_skill.py skills/work` still
reports:

```
[WARN] SKILL.md is 683 lines (recommended max 500). Consider splitting content into references/
```

Both extractions saved their designed ~140 lines, but unrelated commits after
them regrew the file — most visibly `6afaffa5b` (feat(work): rewrite work
skill onto state reads and statectl writes) and its follow-ups. Net: still
683 lines, same WARN this PRD exists to eliminate.

A full heading survey of the current `SKILL.md` (`## Dependencies` through
`## Reference Files`) shows nothing left that isn't part of the per-task loop,
routing table, state sync, or commit rules — exactly the content the PRD's own
Non-Goals section forbids touching ("Touching the read-every-run sections...").
The design doc's own Alternatives section already rejected extracting a
*different* block instead (Alternative 2, "smallest-diff version") as
out-of-scope, and its Risks section flagged this exact possibility: "the
~500-line ceiling itself may need revisiting if the remaining read-every-run
sections alone approach it - out of scope here, flagged only."

## Conclusion

There is no PRD-authorized task left to plan. The two capabilities this PRD's
design doc scoped are done; the numeric acceptance criterion they were meant
to satisfy is unreachable within that scope because of intervening,
unrelated growth. Extending scope to find a third extraction candidate, or to
revisit the 500-line ceiling itself, is a new design decision this PRD's
review log never considered — not something to guess at planning time.
Parking without dispatching any Phase 3 task, per the PRD's own remaining
"Validator check" task having no achievable action left to take.

Un-parks once a human decides: (a) author a follow-up PRD naming a new
extraction target or revisiting the ceiling, or (b) close this PRD as
scope-complete with the size metric accepted as a known gap.
