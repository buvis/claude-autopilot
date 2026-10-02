
Read /Users/bob/git/src/github.com/buvis/claude-autopilot/dev/local/tmp/review-context-00176-03.md for review context, and /Users/bob/git/src/github.com/buvis/claude-autopilot/dev/local/tmp/review-diff-00176-03.diff for the full diff.

Read (no pack available this cycle) and treat its full content as prepended context: similar code, reuse precedent, findings precedent, and task prose for this diff's changed symbols.

Use this review checklist:
# Review Dimensions

Detailed checklist for reviewing completed work.

## Plan Compliance

- [ ] Implementation matches task description
- [ ] All acceptance criteria met
- [ ] No scope creep (extra features not requested)
- [ ] No missing pieces from original task

## PRD Coverage

- [ ] All "must have" requirements addressed
- [ ] Success metrics achievable with implementation
- [ ] No PRD sections left unimplemented
- [ ] Dependencies correctly handled

## Simplification

Hunt actively for simplification — do not just tick boxes. The diff under
review is fresh; this is the cheapest moment to cut complexity before it sets.
For every added or changed file, ask "what would make this simpler to read
without changing what it does?" and flag concrete opportunities.

- [ ] **Reduce complexity** — no needless indirection, dead branches, or
      abstractions built for a single caller; nesting <= 4 levels; functions
      under 50 lines
- [ ] **Eliminate redundancy** — no logic duplicated within the diff or against
      existing code; no helper that reimplements a stdlib or existing utility
- [ ] **Improve naming** — names state intent; no opaque abbreviations;
      action-named functions start with a verb
- [ ] **Follow project standards** — conventions from CLAUDE.md / AGENTS.md and
      the surrounding code; no style drift
- [ ] **No dead code** — no commented-out blocks, unused imports, variables, or
      speculatively-added parameters
- [ ] **Appropriate error handling** — explicit, never silently swallowed

**How to flag a simplification:** give the file:line, the current shape, and
the simpler replacement. Flag concrete behavior-preserving simplifications at
🟡 Medium so the decision gate routes them into the rework loop. Do not inflate
them to 🟠 High; that floods the rework loop and can trip the scope alarm.

**Balance — do not over-simplify:** never propose a change that trades clarity
for brevity, drops error handling, collapses a deliberate boundary, or removes
a documented invariant. Simpler means easier to read and maintain, not shorter
at any cost. If a "simplification" would change behavior, it is out of scope —
do not flag it.

## Testing

- [ ] Unit tests for new logic
- [ ] Edge cases covered
- [ ] Error paths tested
- [ ] Integration tests if crossing boundaries
- [ ] Tests actually run and pass
- [ ] No tautological test — every new or changed test fails against the
      pre-change code (the context's fail-first replay block), and no assert
      is constant, self-comparing, or an either-or hedge (the shapes block)

## Security

- [ ] No hardcoded secrets
- [ ] Input validation at boundaries
- [ ] No SQL/command injection risks
- [ ] Auth/authz correctly applied
- [ ] Sensitive data not logged

## Documentation

- [ ] Public APIs documented
- [ ] Complex logic has comments
- [ ] README updated if needed
- [ ] Breaking changes noted


In addition, work through the numbered rubric:
# Review-Work-Completion Rubric

This rubric defines binary pass/fail criteria for consensus review of completed work. Each rule is numbered and stable for tracking coverage. Reviewers must answer "R{n}: pass|fail" for every rule in their prompt.

## Rules

### Tests

R1: Tests cover every new behavior introduced by the diff.
R2: Tests bind to intent, not just observable behavior; no new or changed test is tautological (passes against the pre-change code, or cannot fail as written).
R3: No skipped or xfail tests mask failures.

### Integration

R4: Changed components integrate with existing callers.

### Security

R6: No hardcoded secrets in the codebase.
R7: All user input is validated and sanitized.
R8: No injection-unsafe queries or commands.

### Domain

R9: Implementation matches PRD feature behavior exactly.
R10: Error handling is explicit and not swallowed.
R11: No debug statements, TODOs, or placeholder markers remain.

### Code Quality

R12: Function sizes respect the 50-line limit.
R13: File sizes respect the 800-line limit.

Review the completed work against PRD requirements. Explore the codebase as needed.

OUTPUT FORMAT IS MANDATORY. Follow exactly:

Each agent outputs issues in this exact format:

```
[{AGENT_NAME}] {emoji} {description} | File: {path or "N/A"} | Task: {id or "general"}
```

**Severity emojis:** 🔴 Critical, 🟠 High, 🟡 Medium, ⚪ Low

**Rules:**
- One issue per line
- Use "N/A" for file if issue is architectural/cross-cutting
- Use "general" for task if issue spans multiple tasks or is a PRD gap
- If zero issues found: `[{AGENT_NAME}] ✅ No issues found`

**Examples:**
```
[ALICE] 🔴 SQL injection in query builder | File: src/db/query.ts | Task: 3
[BOB] 🟠 Missing error handling strategy | File: N/A | Task: general
[CARL] 🟡 PRD section 2.3 not implemented | File: N/A | Task: 5
```


PER-RULE VERDICTS ARE MANDATORY. For every rule in the numbered rubric, emit one line:
R{n}: pass   or   R{n}: fail
(one rule per line, no other text on the line, no rationale).

## Frontend & Design Focus

You still review every dimension in the checklist, but you are the panel's
frontend and design specialist. On any UI, component, styling, or
user-facing change, review with extra depth:

- Accessibility: semantic markup, keyboard navigation, focus management,
  ARIA usage, colour contrast, screen-reader labels.
- Responsive behaviour: layout across breakpoints, overflow, touch targets.
- Visual consistency: design-token usage, spacing/typography scale, reuse
  of existing components over one-off styling.
- UX correctness: loading/empty/error states, form validation feedback,
  no layout shift, sensible defaults.
- Component structure: state vs props boundaries, no prop drilling,
  composability, no duplicated markup.

If the change has no frontend surface, review it as a generalist against
the shared checklist - do not invent frontend findings.

## Incremental review
This is an incremental review of the rework done since the previous review cycle — the diff is scoped to changes since then. Two jobs: (1) for each prior finding listed below, verify it is now resolved in the code; (2) review the scoped diff for any regression the rework introduced. You need not re-review unchanged code; the previous cycle already reviewed the full implementation.

`consolidate_findings.py` exited 0 and produced three distinct findings, each [1/3]. No ledger filter applies. The shortened table preserves every finding, severity, finder, and consensus count. None contradicts the measured mechanical facts.

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [1/3] | 🟠 High | `target.is_symlink()` can raise from its target metadata read, aborting repair with exit 2 and no TSV rows. Guard it per target and continue. | skills/use-codex/scripts/codex_hook_doctor.py:198 | general | Blake |
| [1/3] | 🟡 Medium | Cleanup deletes a pre-existing read-only `.tmp` after write failed before creating it. Use a temporary file owned by this attempt and clean up only that file. | skills/use-codex/scripts/codex_hook_doctor.py:240 | 2 | Blake |
| [1/3] | 🟡 Medium | Orphan cleanup can append a second `unrepairable` row for a target already emitted by `_repair_unknown`, such as an unregistered dangling symlink. Merge its error into the existing target row and pin the full repair path. | skills/use-codex/scripts/codex_hook_doctor.py:346 | 2 | Bob |

The symlink metadata gap predates this rework and is a remaining PRD error-handling gap found through the blind lens. The temporary-file deletion was introduced in the original PRD guarded-write work and preserved by this cycle's extraction. The duplicate row is a regression in this cycle's new orphan handler. The parent accepted all three verified findings for rework. No standalone tasks or verification queue were created.

## Execution constraints
This is a review only. Source stays immutable: no edits, commits, or branch changes. Native cleared-context reviewer is the host adapter. Read-only shell calls provide file-read access where a Read tool is absent; Bob remains static-only and must not execute code, tests, or package managers. The coordinator is obtaining exact-HEAD full-suite, release, and replay evidence; do not duplicate full-suite/release runs. No design doc or ledger is available.
