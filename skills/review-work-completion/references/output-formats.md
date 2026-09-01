# Output Formats

## Contents

- [Agent Output Format](#agent-output-format-single-source-of-truth)
- [Per-Rule Verdict Format](#per-rule-verdict-format)
- [Consolidation Rules](#consolidation-rules)
- [Consolidated Findings Table](#consolidated-findings-table)
- [Issue Documentation Format](#issue-documentation-format)
- [Task Description Format](#task-description-format)
- [Review Summary Format](#review-summary-format)
- [Zero Issues Handling](#zero-issues-handling)
- [Verification-check queue](#verification-check-queue)
- [Review File Format](#review-file-format)

## Agent Output Format (Single Source of Truth)

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

## Per-Rule Verdict Format

In addition to issue lines, every reviewer emits one verdict line per rule in the
numbered rubric inlined into their prompt (see `references/rubric.md` for
`review-work-completion`; analogous files exist for `review-blindly` and the
`run-autopilot` Phase 8 doubt-review).

Exact line shape — one rule per line, no other text on the line, no rationale.
The id prefix names the rubric (PRD 00108): `R{n}` consensus, `B{n}` blind,
`D{n}` doubt. A reviewer emits its own set's prefix and no other.

```
R1: pass
R2: fail
R3: pass
```

The doubt lens emits the same shape with its own prefix:

```
D1: pass
D2: fail
```

Rule IDs are stable within a set — the PRD 00108 rename changed prefixes only,
never a rule number. Reviewers MUST answer every rule. A rule the reviewer
cannot evaluate (insufficient context, blocked by sandbox, etc.) counts as a
`fail` — never omit the line.

> **Note:** `consolidate_findings.py` parses only lines matching the
> `[{AGENT}] {emoji} ... | File: ... | Task: ...` issue format and silently
> drops everything else. So `R`/`B`/`D` verdict lines do NOT survive
> consolidation into the findings table — they live only in the raw
> per-agent output files at `dev/local/tmp/{agent}-output-{id}.txt` (the
> location SKILL.md step 6 saves them to). Step 6 reads the doubt lens's
> verdict lines from those raw outputs (into `state.doubts_rubric_verdicts`
> on autopilot runs), and Bob's section in the saved review file keeps them.

## Consolidation Rules

Parse agent outputs and merge:

1. **Normalize** - Match similar issues by file+description
2. **Score by consensus** (scales with active agent count N):
   - `[N/N]` Full Consensus - all agents agree, highest priority
   - `[>N/2]/N` Majority Consensus - more than half agree, high priority
   - `[<=N/2]/N` Minority - half or fewer, normal priority
3. **Deduplicate** - Keep best description, note which agents found it

## Consolidated Findings Table

| Consensus | Severity | Issue | File | Found By |
|-----------|----------|-------|------|----------|
| [3/3] | 🔴 Critical | XSS in input handler | src/input.ts | Alice, Bob, Carl |
| [2/3] | 🟠 High | Missing null check | src/api.ts | Alice, Bob |
| [1/3] | 🟡 Medium | No test coverage | src/utils.ts | Blake |

## Issue Documentation Format

```
- {severity emoji} {description}
  - File: {path}
  - Task: {task ID}
  - PRD ref: {section if applicable}
  - Found by: {agent list}
```

## Task Description Format

```
Fix: {issue summary}

Issues addressed:
- {issue 1}
- {issue 2}

Found by: {agents}
Severity: {🔴/🟠/🟡/⚪}

Acceptance criteria:
- [ ] {criterion 1}
- [ ] {criterion 2}
```

## Review Summary Format

```
## Review Summary

Reviewed: {N} completed tasks
PRDs checked: {list}

### Agent Status
{for each configured agent, one of:}
- {Name}: ✅ Available
- {Name}: ⚠️ Unavailable: {reason}
- {Name}: ⏸️ Disabled: {reason}

## Consolidated Findings

### Full Consensus (N/N)
- [N/N] 🔴 {issue} | {file} | Found by: {agents}

### Majority Consensus (>50%)
- [M/N] 🟠 {issue} | {file} | Found by: {agents}

### Minority (<=50%)
- [1/N] 🟡 {issue} | {file} | Found by: {agent}

## Follow-up Tasks Created

1. {task title} (S/M/L) - 🔴 consensus - addresses X, Y
2. {task title} (S/M/L) - 🟠 consensus - addresses Z

_If no issues found: "✅ No follow-up tasks needed. All reviewers passed the implementation."_
```

## Zero Issues Handling

When consolidation yields no issues:
- Skip task creation entirely (don't create empty/placeholder tasks)
- In review summary, note: "✅ All agents passed - no issues found"
- Still save the review file (documents the clean review)
- Report success to user with agent consensus on passing

## Verification-check queue

Location: `dev/local/reviews/{prd-stem}-checks-{cycle}.json` — `{prd-stem}` is
`state.prd` minus `.md`, `{cycle}` is `state.cycle`. One file per cycle, beside
the review files and the settled-decisions ledger, so it dies with the PRD like
the other review satellites.

It is how a **VERIFY** finding — one that "needs a specific named check to
resolve" (`agents/eve.md`) — reaches a runner without becoming an
implementation task whose only content is "run this check". Step 6 writes it
from the doubt lenses' VERIFY buckets; `work` step 7 reads it, runs each
`command` once, and writes each entry's `result` back.

A JSON array:

```json
[
  {
    "cycle": 3,
    "finding": "<the finding text, verbatim>",
    "command": "<the exact check to run>",
    "source": "bob",
    "result": {"exit": 0}
  }
]
```

- `finding` is the reviewer's own words, not a summary — Phase 5's VERIFY row
  (`run-autopilot/references/phase-review.md`) matches findings against this
  field to decide which ones create no task.
- `command` is one runnable command line. **A VERIFY finding whose text yields
  no exact command is NOT queued** — it stays a normal finding and follows
  today's classification. Rubric rule D3 already requires a VERIFY item to name
  its exact check, so a vague one is a rubric failure, not a queue entry.
- **A queued command must be a project verification command** — a test, lint,
  build, type-check or project-defined check, the same shapes step 7 already
  runs. One command: no `&&`/`;`/`|` chaining, no redirection, no substitution,
  no `rm`/`curl`/`git push` or any other state change. The writer composes these
  from reviewer text, and reviewer text is derived from the diff and the PRD, so
  **anything else is not queued** — it stays a normal finding and is reported as
  refused. The runner enforces the same rule and skips what it would not run
  (`work/references/final-verification.md` § Queued verification checks).
- `source` names the lens that raised it: `"bob"`, `"eve"`, or — when a fallback
  lane produced the doubt output — the principal it stood in for (Bob's Claude
  fallback is `"bob"`, Eve's Claude substitute is `"eve"`), matching the
  `{agent}-output-{id}.txt` convention step 6 already uses.
- `result` is absent until the work phase runs the check, and is the only field
  the work phase writes. Its `exit` is the command's integer exit code, or the
  string `"timeout"` for a check that blew its budget — never a number for a
  command that returned no verdict.

**Reader tolerance:** an absent queue file means no checks. It is never an
error — a first-pass build phase has no review behind it and reads nothing. A
file that is present but unparseable is reported as unreadable and treated as
empty; these checks are evidence, never a gate.

## Review File Format

Location: `dev/local/reviews/<prd-filename-without-ext>-review-<NN>.md`

Example: PRD `00004-exchanger-web-ui-v1.md` → review `00004-exchanger-web-ui-v1-review-01.md`

```yaml
---
prd: dev/local/prds/wip/<prd-filename>
review: 1
date: YYYY-MM-DD
head_sha: <git HEAD sha at review time>
codex_thread_id: <codex session thread id, optional>
consensus_run_id: <review-fanout workflow runId, optional>
agents:
  alice: available
  bob: available
  carl: available
---

Agent states: `available` (ran successfully), `unavailable` (failed after retries), `disabled` (not invoked).

`head_sha`: the `git rev-parse HEAD` value captured when this review ran. The next rework cycle reads it and passes `--since <head_sha>` to `gather-context.sh`, scoping that cycle's diff to the rework commits. Absent on review files created before this field existed — consumers fall back to a full-branch diff.

`codex_thread_id`: the codex session thread id captured on cycle 1 via `codex-run.sh --emit-thread-id` (Bob/Codex reviewer). The next rework cycle reads it and passes `--resume-thread <codex_thread_id>` so Bob resumes his prior session instead of re-reviewing from zero. Omitted when Bob was skipped this cycle or thread-id capture failed — consumers then run Bob fresh.

`consensus_run_id`: the `review-fanout` workflow's `runId` for this cycle's consensus-engine run — the forensic handle for that run. Present whenever the engine ran (`consensus_engine` is `workflow` or `shadow`); omitted otherwise. Deliberately not written to `state.json`: the Workflow tool's `resumeFromRunId` is same-session only, so a stored id would outlive its usefulness.

`codex_rung_guard`: a plain body line, not a frontmatter field. Required by `check_review_file.py`. Accepted forms: `codex_rung_guard: not fired`, `codex_rung_guard: fired (N codex-implemented task(s))`, or that fired form suffixed with `; eve unavailable, doubt lens fell back to claude` or `; constraint UNMET` (SKILL.md step 6 documents when each suffix applies). Lives in the body top matter, directly after the `Diff range:` block, before the body sections (shown at its real position below).

# Review: <prd-name>

Diff range: `<since-sha>..<head-sha>`

codex_rung_guard: fired (N codex-implemented task(s))

{review summary content}
```
