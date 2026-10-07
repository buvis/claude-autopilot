# Decision Audit Log: 00267-widen-the-phase-delegation-guard-v1

PRD: `00267-widen-the-phase-delegation-guard-v1.md`
Started: 2026-10-07T07:40:58Z
Completed: 2026-10-07T07:40:58Z
Autonomous: 16  |  Deferred: 0  |  Doubts: 0

### [autonomous] 2026-10-07T07:40:58Z

**Decision**: Cannot statically verify: tests and release checks pass at the reviewed revision. Run `python3 -m pytest hooks/test_guard_phase_delegation.py` and `bash dev/bin/release-checks`; require exit 0 from both.

**Choice**: routed to verification

**Rationale**: cycle 1: queued to 00267-widen-the-phase-delegation-guard-v1-checks-1.json as two commands (python3 -m pytest hooks/test_guard_phase_delegation.py; bash dev/bin/release-checks); the tail sweep work pass runs them in its step 7 rather than creating a run-this-check task

### [autonomous] 2026-10-07T07:40:58Z

**Decision**: five low-severity findings (R11, R17, and Blake's curly-double-quote, whitespace-in-jargon and not-only breadth observations)

**Choice**: settled deferral (ledgered, not swept)

**Rationale**: cycle 1: each is either out of this PRD's scope (R17 belongs to parked PRD 00265), a deliberate harmless superset (R11), or implements the PRD's literal instruction; recorded in 00267-widen-the-phase-delegation-guard-v1-ledger.json so later cycles do not re-raise them

### [autonomous] 2026-10-07T07:40:58Z

**Decision**: `Don't hesitate to run the work phase` is still allowed. Only `not`/`never` get the `hesitate|fail|only` double-negation exception. The contraction `don't` (and `doesn't`, `won't`) stays a plain negation and hides the delegation (probe returns False). This is the same missed class as the PRD's own `Do not hesitate...` and is the more common spelling. It matches the PRD's literal wording, so extend the exception to the contractions or record the gap as a deliberate limit

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-07T07:40:58Z

**Decision**: The new verbs `do`/`complete`/`start` plus the 3-word gap over-match ordinary prose and falsely deny. Probes that return True (deny): "Tell me what we do in the work phase", "Decide what to do about the work phase", "Tasks complete in the work phase", "Start with the work phase fixtures", "Review diff; complete the work phase checklist", "Fix the bug. Do tests for the design phase". Gap words may be prepositions or nouns, so verb plus any 3 words plus jargon fires. PRD says a false deny costs a session. The allowed corpus still passes, but it holds no case for these verbs. Safer shape: limit gap words to determiners and modifiers (the|this|entire|whole|full|all|complete), or require a non-preposition gap for the six new verbs

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-07T07:40:58Z

**Decision**: The false-positive side of the widened verbs has no test. `test_non_delegating_verb_before_a_phase_name_is_allowed` uses only `Review`, `Document` and `Test`, which were never delegating verbs. It passes against the pre-change code and cannot fail if `do`/`complete`/`start`/`call` over-match. Add negative cases that use the new verbs, such as "what we do in the work phase" or "Tasks complete in the work phase". Those currently deny, so the fix above has to land first

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-07T07:40:58Z

**Decision**: The `_IMPERATIVE_COLON` restriction is untested. It keeps the colon-lead pattern off the new verbs so "Work phase: complete" and "In the work phase: do not skip tests" stay allowed. Nothing pins this: no test asserts those strings are allowed, so swapping in `_IMPERATIVE` would pass if the corpus lacks them

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-07T07:40:58Z

**Decision**: The `Never fail to report; do not run the work phase.` case does not pin the `hesitate|fail|only` exception. It is allowed with or without the exception, because the `;` ends the sentence and the later `do not run` is a real negation. It passes against the pre-change code. Use a case where the exception changes the outcome

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-07T07:40:58Z

**Decision**: Simplification: the six original verbs are spelled out twice, in `_IMPERATIVE` and `_IMPERATIVE_COLON`. Build `_IMPERATIVE` from the colon list plus `|start|do|perform|complete|launch|call`. `_BARE_SKILL` and `_PREFIXED_SKILL` also repeat the same skill alternation and quote group. The new `_PREFIXED_SKILL` pattern subsumes the prefixed alternatives of `_BARE_SKILL`, so that pattern only needs the bare names

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-07T07:40:58Z

**Decision**: `_SKILL_READ` newly denies `Read skills/work/SKILL.md and do not perform all tasks`: negation is checked before `Read`, missing the prohibition inside the match. Check negation around the execution verb and add this allowed regression case.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-07T07:40:58Z

**Decision**: Non-UTF-8 tests only exercise payloads that remain invalid JSON after replacement; catching UnicodeDecodeError and returning `{}` also passes. Add invalid bytes inside a JSON string alongside a valid delegation, asserting the hook still denies it after replacement decoding.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-07T07:40:58Z

**Decision**: Tests omit the `only` negation exception, exactly-three/four-word gap boundaries, and a prefixed skill with intervening words. Add explicit cases pinning these contracts; current examples cannot detect their removal or incorrect limits.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-07T07:40:58Z

**Decision**: Replay reports 12 touched cases passing against base. Preservation controls have a purpose, but `test_positive_controls_carry_raw_non_ascii_bytes_and_exceed_4kib` only tests generated fixture data. Move those checks into the subprocess test's setup and remove the standalone helper-only test.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-07T07:40:58Z

**Decision**: The denied-corpus count is hard-coded as 17 in two places. The next fixture added breaks both asserts. This continues the existing hard-coded 4

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-07T07:40:58Z

**Decision**: `read_input` silently falls back to text `sys.stdin.read()` when `sys.stdin.buffer` is absent. The fallback exists for `capture_main`'s StringIO swap, but the docstring does not mention it or the new bytes-then-replace decode path

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-07T07:40:58Z

**Decision**: Test brittleness. `_denied()` and the committed-allowed test hard-pin fixture counts (17 and 24). Adding a fixture later breaks them for no behavioral reason.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-07T07:40:58Z

**Decision**: The zero-width fixture is a single file covering both "inside Run" and "inside work". The spec lists the two together, so this is compliant, but a regression that handled only one of the two would still pass the fixture. The mid-prompt parametrized tests cover each of the five invisible code points separately.

**Choice**: auto-fixed

**Rationale**: fixed by review-close
