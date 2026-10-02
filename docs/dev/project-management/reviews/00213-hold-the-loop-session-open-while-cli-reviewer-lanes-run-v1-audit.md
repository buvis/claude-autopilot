# Decision Audit Log: 00213-hold-the-loop-session-open-while-cli-reviewer-lanes-run-v1

PRD: `00213-hold-the-loop-session-open-while-cli-reviewer-lanes-run-v1.md`
Started: 2026-09-26T00:06:07Z
Completed: 2026-09-26T00:06:07Z
Autonomous: 8  |  Deferred: 0  |  Doubts: 0

### [autonomous] 2026-09-26T00:06:07Z

**Decision**: test_hooks_json_is_valid has no assertion (two reviewer rows, one mech-check)

**Choice**: settled deferral, ledgered

**Rationale**: pre-existing test untouched by this diff; fixing it is unrelated cleanup under the surgical-changes rule. Bobs doubt lens filed it KNOWN with that justification.

### [autonomous] 2026-09-26T00:06:07Z

**Decision**: lane-snapshot one-liner duplicated across three stub heredocs

**Choice**: settled deferral, ledgered

**Rationale**: the three stubs are independent generated subshell scripts in two suites; extraction needs a stub-generation refactor. Per-stub isolation beats de-duplicating three fixtures. The VAR-guard hardening of the same line is swept separately.

### [autonomous] 2026-09-26T00:06:07Z

**Decision**: gemini-run.sh writes the lane marker before the per-mode empty-prompt validation

**Choice**: settled deferral, ledgered

**Rationale**: the merged EXIT trap removes the marker on the validation-triggered exit, so the observable contract holds and no acceptance criterion fails; the validation lives inside the per-backend functions, so moving the write would duplicate it across two backends.

### [autonomous] 2026-09-26T00:06:07Z

**Decision**: marker removal is on EXIT only, not INT/TERM

**Choice**: settled deferral, ledgered

**Rationale**: bash runs the EXIT trap on the common signal-initiated exits, and the hooks dead-pid reaping makes a stale marker self-healing. Adding INT TERM would also change gemini-run.sh pre-existing RUN_TMP cleanup, outside this PRD scope. Bobs KNOWN bucket carries the same justification.

### [autonomous] 2026-09-26T00:06:07Z

**Decision**: Bob VERIFY item: exercise the loop-session to blocked-stop chain end to end

**Choice**: not queued: command shape; swept as a test task instead

**Rationale**: the named check is three chained commands with backgrounding and command substitution, which the verification-check queue forbids (one runnable command line, no chaining, no substitution). Swept as add the end-to-end test in the D1 tail sweep.

### [autonomous] 2026-09-26T00:06:07Z

**Decision**: codex reviewer lane (Bob) failed twice with exit 1 and turn.failed, no output file and no salvageable sidecar

**Choice**: one retry spent, then the Claude fallback ran Bobs exact assembled prompt

**Rationale**: retry-policy allows one retry for a plain non-zero exit; the doubt lens must never silently drop, so a Claude Task subagent carried the same doubt plus de-slop prompt and its output is Bobs section. Graceful degradation, cycle not blocked.

### [autonomous] 2026-09-26T00:06:07Z

**Decision**: engram pack generation failed (not inside a registered repo)

**Choice**: continued with the no-pack sentinel in every prompt

**Rationale**: the pack is additive retrieval context; the skill prescribes the sentinel and a noted failure rather than a blocked cycle. No retry: the failure is deterministic gita registration, not transient.

### [autonomous] 2026-09-26T00:06:07Z

**Decision**: task 5: the str(...) cwd cast (LOW) conflicts with the same cycles MEDIUM loud-internal-failure finding

**Choice**: not applied, ledgered as a settled deferral

**Rationale**: with the cast a non-string cwd resolves quietly and the hook allows the stop in silence; without it the TypeError is reported by the new fail-open handler. The louder behaviour wins. Pats closure verdict records the non-fix.
