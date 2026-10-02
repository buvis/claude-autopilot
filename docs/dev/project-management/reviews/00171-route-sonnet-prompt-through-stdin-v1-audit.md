# Decision Audit Log: 00171-route-sonnet-prompt-through-stdin-v1

PRD: `00171-route-sonnet-prompt-through-stdin-v1.md`
Started: 2026-09-05T07:11:20Z
Completed: 2026-09-05T07:11:20Z
Autonomous: 5  |  Deferred: 0  |  Doubts: 0

### [autonomous] 2026-09-05T07:11:20Z

**Decision**: Qwen added an unrequested -f direct-file special case

**Choice**: replace it with the PRD-pinned unconditional printf pipeline

**Rationale**: the verbatim contract requires one prompt-mode stdin shape

### [autonomous] 2026-09-05T07:11:20Z

**Decision**: Concurrent PRD 00170 commit landed between the test and fix commits

**Choice**: scope the per-task review to commits 20be167 and b231d0d

**Rationale**: preserve the foreign commit without presenting its 1003-line routing diff as PRD 00171 work

### [autonomous] 2026-09-05T07:11:20Z

**Decision**: Codex and Gemini reviewer CLIs both refused dispatch with exit 3 (refusing nested dispatch); this headless session carries a full codex marker set CODEX_SESSION_ID/CODEX_THREAD_ID/CODEX_CI

**Choice**: did not bypass the recursion guard; ran Bob on the mandated Claude fallback and skipped Carl as graceful degradation, leaving 3 reviewers

**Rationale**: the guard is a real safety mechanism and the doubt lens has a sanctioned non-codex path, so degrading beats disarming

### [autonomous] 2026-09-05T07:11:20Z

**Decision**: Two cycle-1 findings were resolved without a fix: Bob's Cannot-statically-verify line and his no--i-interactive-test line

**Choice**: discarded the first (verified live by Alice and Blake in the same cycle) and settled the second as an out-of-scope deferral; both recorded in the ledger

**Rationale**: a finding already answered by live evidence, and one the doubt lens itself bucketed KNOWN with justification, must not be re-argued next cycle

### [autonomous] 2026-09-05T07:11:20Z

**Decision**: Tail-sweep per-task review (Pat) returned one unresolved CLOSURE claiming the -t/-t Read/-S/-R case labels were never renamed

**Choice**: verified against the file (lines 248, 261, 288, 304) and discarded the verdict; no rework dispatched

**Rationale**: those labels already name the prompt-on-stdin/absent-from-argv shape the PRD describes, and the PRD prescribes an exact string only for assertion 1, which now matches; Pat could not see them because they lie outside the reviewed diff
