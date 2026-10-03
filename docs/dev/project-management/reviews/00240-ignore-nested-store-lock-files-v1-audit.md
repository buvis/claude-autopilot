# Decision Audit Log: 00240-ignore-nested-store-lock-files-v1

PRD: `00240-ignore-nested-store-lock-files-v1.md`
Started: 2026-10-03T14:03:35Z
Completed: 2026-10-03T14:03:35Z
Autonomous: 6  |  Deferred: 0  |  Doubts: 0

### [autonomous] 2026-10-03T14:03:35Z

**Decision**: SKILL.md Retention Disposable entry omits the PRD-mandated parenthetical after `autopilot/**/*.lock` (4/4 consensus: Alice, Blake, Bob, Carl)

**Choice**: auto-fix via the [D1] tail sweep

**Rationale**: Medium with a clear mechanical fix: append the exact parenthetical the PRD contract gives verbatim. The parity test cannot catch it (its regex collects only backticked paths), so nothing else binds the prose.

### [autonomous] 2026-10-03T14:03:35Z

**Decision**: The positive-control assert `"b-deferred.json" in status` is also satisfied by the `b-deferred.json.lock` line, so it cannot alone show the .json is listed (2/4: Alice, Blake)

**Choice**: auto-fix via the [D1] tail sweep

**Rationale**: Low, additive test precision: an exact porcelain-line match makes the PRD error-case scenario stand on its own instead of holding only by elimination.

### [autonomous] 2026-10-03T14:03:35Z

**Decision**: `_GIT_ENV` is re-declared byte-for-byte in test_store_tree_gitignore.py although cli/custody_testutil.py:28 already defines it

**Choice**: auto-fix via the [D1] tail sweep

**Rationale**: Low, behavior-preserving de-duplication; verified the existing definition is byte-identical at custody_testutil.py:28.

### [autonomous] 2026-10-03T14:03:35Z

**Decision**: The PRD Test Strategy edge case (an existing store .gitignore carrying the old pattern is rewritten by ensure-store) has no dedicated test

**Choice**: auto-fix via the [D1] tail sweep

**Rationale**: Low and additive: the idempotency parametrization covers byte-different bodies generically but never the literal old `autopilot/*.lock` body the PRD names.

### [autonomous] 2026-10-03T14:03:35Z

**Decision**: engram pack unavailable for this cycle

**Choice**: degraded and continued

**Rationale**: `engram pack` exited 1 with `not inside a registered repo`. Deterministic config refusal, not transient, so not retried. Every prompt carried the documented `(no pack available this cycle)` sentinel; the review is degraded on retrieval context, not invalid.

### [autonomous] 2026-10-03T14:03:35Z

**Decision**: Carl reported 20 release-checks failures from inside the copilot sandbox

**Choice**: discarded as environmental

**Rationale**: COPILOT_CLI / AUTOPILOT_DISPATCH_DEPTH / CODEX_SESSION_ID are set inside the copilot CLI, so codex-run.sh correctly refuses nested dispatch (exit 3) and the recursion-guard block fails for environmental reasons. Carl diagnosed it himself and re-ran with those unset; the orchestrator clean-environment run is exit 0 green.
