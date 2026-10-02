# Decision Audit Log: 00178-fix-bob-first-run-and-specify-his-retry-v1

PRD: `00178-fix-bob-first-run-and-specify-his-retry-v1.md`
Started: 2026-09-06T18:38:01Z
Completed: 2026-09-06T18:38:01Z
Autonomous: 10  |  Deferred: 5  |  Doubts: 0

### [autonomous] 2026-09-06T18:38:01Z

### [autonomous] 2026-09-06T18:38:01Z

### [autonomous] 2026-09-06T18:38:01Z

### [autonomous] 2026-09-06T18:38:01Z

### [autonomous] 2026-09-06T18:38:01Z

### [autonomous] 2026-09-06T18:38:01Z

### [autonomous] 2026-09-06T18:38:01Z

### [autonomous] 2026-09-06T18:38:01Z

### [autonomous] 2026-09-06T18:38:01Z

### [autonomous] 2026-09-06T18:38:01Z

### [deferred] 2026-09-06T18:38:01Z

**Decision**: The prose tests do not pin ledger closure/outcomes, the ALL-THREE conjunction, exact inlined blocks, output-path reuse, or omission of --resume-thread, so several introduced behaviors can regress while all tests pass

**Rationale**: Cycle 1: PRD 00178 Phase 2 enumerates the exact assertion list the test must carry and every listed assertion is present; deepening the pins is new test scope this PRD did not specify.

### [deferred] 2026-09-06T18:38:01Z

**Decision**: The unrelated Python-first UUID fallback is not pinned; the existing test checks only that pat_session_id exists, so reversing the fallback order would pass

**Rationale**: Cycle 1: concerns commit fda6abd, inside the reviewed range but not one of PRD 00178 four tasks. Real gap, wrong PRD; needs its own PRD against skills/work.

### [deferred] 2026-09-06T18:38:01Z

**Decision**: Eleven single-assert methods carry comments that largely repeat their descriptive names and assertions; use table-driven subTest cases and retain only comments explaining non-obvious invariants

**Rationale**: Cycle 1: PRD 00178 mandates mirroring the _section pattern of test_codex_resume_contract.py, which is what shipped. Restructuring is a behavior-preserving refactor of a file whose assertions are the PRD contract.

### [deferred] 2026-09-06T18:38:01Z

**Decision**: The refusal predicate and retry assembly are dense single paragraphs; replace them with three numbered gates and ordered assembly steps while preserving every required literal

**Rationale**: Cycle 1: PRD 00178 specifies both section bodies as verbatim Outputs, and the prose test plus acceptance rg -c commands pin literals inside them. Reformatting risks the pinned counts for no behavior change.

### [deferred] 2026-09-06T18:38:01Z

**Decision**: FIX: The new exit-routing rule compresses four branches and prompt-selection behavior into one dense paragraph; replace it with a trigger/routing/retry-prompt table while preserving the pinned cross-reference count

**Rationale**: Cycle 2: same class as the cycle-1 settled deferral on retry-policy.md dense prose. Behavior-preserving reformat with zero functional change, in a file carrying a hard pinned count (rg -c Lack-of-input refusal must stay exactly 1) that a table rewrite could break. Alice and Carl both read the same paragraph and found it consistent with SKILL.md step 5; only Bob judged it too dense. Not worth risking a pinned acceptance criterion.
