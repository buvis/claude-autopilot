# Decision Audit Log: 00180-route-codex-prompt-through-stdin-v1

PRD: `00180-route-codex-prompt-through-stdin-v1.md`
Started: 2026-09-06T21:14:40Z
Completed: 2026-09-06T21:14:40Z
Autonomous: 9  |  Deferred: 9  |  Doubts: 0

### [autonomous] 2026-09-06T21:14:40Z

### [autonomous] 2026-09-06T21:14:40Z

### [autonomous] 2026-09-06T21:14:40Z

### [autonomous] 2026-09-06T21:14:40Z

### [autonomous] 2026-09-06T21:14:40Z

### [autonomous] 2026-09-06T21:14:40Z

### [autonomous] 2026-09-06T21:14:40Z

### [autonomous] 2026-09-06T21:14:40Z

### [autonomous] 2026-09-06T21:14:40Z

### [deferred] 2026-09-06T21:14:40Z

**Decision**: PRD acceptance gate unmet: rg -c on PASS lines in skills/use-codex/scripts/test_codex_run.sh prints 21, not the 40 the PRD requires, because 24 cases were relocated into a new file test_codex_run_resume.sh that the PRD structural decomposition never names. Aggregate coverage is preserved (21+24=45) and no case was lost, but the PRD stop-and-report instruction was not honored.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-06T21:14:40Z

**Decision**: Tautological test: the unreadable prompt file case in skills/use-codex/scripts/test_codex_run.sh passes against the pre-fix code, so it does not pin the new cat-failure guard or its new stderr message.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-06T21:14:40Z

**Decision**: The unrequested test-file split duplicates 239 byte-identical lines across test_codex_run.sh and test_codex_run_resume.sh and defines child_stdin_is_prompt twice, instead of the single shared-helper extraction the cycle-1 task asked for.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-06T21:14:40Z

**Decision**: Scope creep in commit bb08599: codex-run.sh now rejects whitespace-only prompt files as Prompt required and errors explicitly on a failed cat read. Both were requested by the cycle-1 decision-gate task, but PRD 00180 never authorised either.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-06T21:14:40Z

**Decision**: The whitespace guard at codex-run.sh:154 sits outside the PROMPT_FILE block, so it also rejects a whitespace-only positional prompt, while the CHANGELOG describes the change as -f only.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-06T21:14:40Z

**Decision**: Fresh-JSON marker coverage at test_codex_run.sh:454 adds a separate codex invocation although the existing JSON-path case already captured argv; the final-token check could fold into that case.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-06T21:14:40Z

**Decision**: Trailing-newline coverage at test_codex_run.sh:434 duplicates the leading-dash file case, which already byte-compares a newline-terminated file.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-06T21:14:40Z

**Decision**: The unreadable prompt file test at test_codex_run.sh:392 degrades to a no-op PASS on any user that can read chmod-000 files, for example root in CI.

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-06T21:14:40Z

**Decision**: The PRD Test Strategy wants the leading-dash prompt case verified on the plain, JSON and resume paths, but the new test exercises only the plain path.

**Rationale**: rework cap reached with this finding unresolved
