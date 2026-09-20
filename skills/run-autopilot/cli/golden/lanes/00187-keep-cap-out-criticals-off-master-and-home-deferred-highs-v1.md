---
catchup: skip
design: run
default_model: opus
model_tier_rationale: custody persisted across retries and batch rollover, command-aware git guard, attended git-mutating resolution
---

# Keep cap-out CRITICALs under custody

## Overview

### Problem Statement
A cap-out with an unresolved CRITICAL parks its PRD but leaves the commits live. `skills/run-autopilot/references/phase-review.md` stalls with site cap_critical; `cli/records.py:do_stall` moves wip to hold, appends a stall record and resets per-PRD state, dropping pending deferred decisions. Nothing records which commits carry the CRITICAL or blocks their push, and the hold PRD keeps its pre-work text.

Source: ddb assessment `/Users/bob/git/src/github.com/doogat/ddb/dev/local/audit-results/refactor-assessment-2026-09-06.md`, F2 and Decision step 3; read-only ledger `/Users/bob/git/src/github.com/doogat/ddb/dev/local/autopilot/deferred/202607161128-deferred.json`. ddb 00168 stalled at cap 2 after bundle import could merge stale bundle/master data following a wildcard fetch; 25 PRD-tagged commits remained live and its hold PRD still described the old implementation. Done 00146 made stall records render; this PRD adds custody, not a second stall/report mechanism.

The approved split assigns reviewed CRITICAL rework design to backlog 00194 and deferred-finding stub minting to backlog 00195. This PRD introduces neither command nor integration calls for those later capabilities. Plan expansion (00189) and run-condition measurement (00188) remain complementary. Every review lens still runs every cycle.

### Target Users
The operator resuming after a batch and the loop, which must keep draining while pending custody blocks pushes.

### Success Metrics
- Checkout CLI fixture stall records a stable range/count, migrates pending deferrals, refreshes the hold PRD and blocks a push.
- Retrying after a custody-write failure produces one marker entry, one hold notice and no duplicated migrated records.
- Each attended resolve choice has a headless temp-repo proof; a successful choice lifts the guard, a conflict retains custody.
- Custody, hook, prose and report tests plus `bash dev/bin/release-checks` pass.

## Functional Decomposition

### Capability: Custody of a cap-out CRITICAL
#### Feature: Retry-stable critical record
- **Description**: cap_critical stall captures the PRD's live commits before reset.
- **Inputs**: state work_start_sha, repo_root (project root when absent), batch.id, deferred_decisions, stall detail and Git HEAD in that repository.
- **Outputs**: a captured `commit_range: "<work_start_sha>..<head>"` and `commits: <git rev-list --count range>` in the durable stall_op and stall record; marker `dev/local/autopilot/critical-on-master` with JSON `{"entries":[{"prd","batch","op_id","commit_range","commits","detail"}]}`; matching batch.critical_on_master entry.
- **Behavior**: derive the range internally once when stamping the intent, then reuse the persisted capture on every retry, even if HEAD advances. Require valid recorded base/repository state; missing or invalid range inputs fail loudly with exit 2 before moving the PRD. There is no caller-supplied range option. Preserve the existing order: mkdir hold → stamp durable intent (including range/count) → move wip to hold → append stall/deferred records → write custody marker and hold refresh → commit per-PRD reset plus the batch mirror through extra_mutator. Migrate pending deferred_decisions into the batch JSON in Phase 9's deferred_decision shape before reset, deduping by operation and source row. A custody/deferred write error exits 9 with the PRD already in hold, intent retained and per-PRD state unreset. Reuse the existing operation ID and never recapture metadata on retry. Non-cap_critical stalls retain their existing contract. Notify once on successful custody creation, naming PRD/range; notifications remain best-effort. The file survives batch rollover; the loop continues draining.

#### Feature: Hold PRD refresh
- **Description**: make the parked artifact explain what is live.
- **Inputs**: the moved hold PRD and captured entry.
- **Outputs**: preserve/insert frontmatter with `critical_on_master: <range>` and `ledger: deferred/<batch>-deferred.json#<op_id>`; under Problem Statement (or H1 if absent), add `> **Custody (cap_critical, batch <id>):** <detail> Commits <range> (<n>) are live on master. Resolve with autopilot custody resolve.`
- **Behavior**: retrying the same operation replaces/reuses its notice, never appends another. Preserve the PRD's other content and frontmatter. Metadata remains ignored by normal frontmatter parsing.

#### Feature: Command-aware push guard
- **Description**: deny a Bash Git push targeting a repo with pending custody.
- **Inputs**: PreToolUse Bash payload command/cwd, effective Git repository and its marker.
- **Outputs**: exit 2 naming pending PRDs, ranges and `autopilot custody resolve`; exit 0 for commands without a pending-custody push.
- **Behavior**: stdlib/shlex parsing must recognize Git only in executable position, including an absolute git executable, leading environment assignments and `command git`. Support literal `-C` (including repeated relative changes), `-c key=value`, `--git-dir` and `--work-tree` in separate/equals forms before the push subcommand; option values are not subcommands. Resolve against payload cwd plus literal cd/compound context, not whichever repo the hook itself occupies. Inspect commands separated by newline, semicolon, &&, ||, pipelines and grouped commands. Quoted echo arguments such as `echo 'git' 'push'`, Git read-only commands and option values containing push pass. For malformed or dynamically unresolved push-like commands, do not claim shell evaluation: conservatively deny when the payload-cwd or any resolvable target repo has pending custody, explaining that the target could not be resolved; otherwise pass. Document this supported grammar and limitation. This guards pushes in every mode, with no automatic revert or batch halt.

#### Feature: Attended resolution
- **Description**: expose explicit custody choices, with no Git mutation from loop-mode resumption.
- **Inputs**: `autopilot custody resolve --prd <stem> --choice revert|branch-and-revert|accept` and pending entries.
- **Outputs**: revert runs `git revert --no-edit <range>`; branch-and-revert first runs `git branch custody/<stem> <range-end>`; accept leaves Git untouched. Append `{"type":"custody","choice","prd","commit_range"}` to the entry's batch ledger before removing its marker/state mirror.
- **Behavior**: Phase 0, before normal selection, offers the three choices in attended mode. Loop mode only prints `custody: <n> entries await an attended resume` and continues. Run Git in the recorded repository; a revert conflict exits 5, retains custody and leaves Git's conflict state for the operator. This PRD validates choices with isolated fixtures, never live user approval or a real push.

#### Feature: Custody in the stalled report
- **Description**: surface live commit custody beside the existing stall details.
- **Inputs**: a stall record with or without commit_range/commits.
- **Outputs**: add `- Commits: <range> (<n>) live on master, custody pending` when a range is present.
- **Behavior**: wire the record through the existing render report --stalled path; range-less stalls render as before. Preserve ordinary completed-report goldens.

## Structural Decomposition

### Repository Structure
```
dev/local/autopilot/critical-on-master               # NEW runtime output: custody core
skills/run-autopilot/cli/custody.py                  # NEW: custody core
skills/run-autopilot/cli/records.py                  # intent, migration and stall integration
skills/run-autopilot/cli/__main__.py                 # custody verb and stalled render wiring
skills/run-autopilot/cli/render_report.py            # custody report line
skills/run-autopilot/cli/test_custody.py             # NEW: fixture/retry/resolve tests
skills/run-autopilot/cli/test_custody_prose.py        # NEW: integration contract tests
skills/run-autopilot/cli/test_render_custody.py       # NEW: stalled renderer tests
skills/run-autopilot/references/phase-review.md
skills/run-autopilot/references/phase-build.md
skills/run-autopilot/references/recovery.md
skills/run-autopilot/references/state-schema.md
skills/run-autopilot/SKILL.md
hooks/guard_push_on_critical.py                      # NEW: Bash guard
hooks/test_guard_push_on_critical.py                 # NEW: command/repo fixtures
hooks/hooks.json
dev/bin/release-checks
CHANGELOG.md
```

### Module: custody core
- **Maps to capability**: Custody of a cap-out CRITICAL
- **Responsibility**: cli/custody.py, records.py, __main__.py and test_custody.py, plus the runtime critical-on-master marker; captured intent, durable writes and explicit resolve.
- **Exports**: record_critical, pure refresh_hold_prd(text, entry) -> str, resolve; reviewed design fixes internal argument shapes before planning, while CLI/JSON contracts above stay fixed.

### Module: push guard
- **Maps to capability**: Custody of a cap-out CRITICAL
- **Responsibility**: the three hooks files; command/target resolution and enforcement.
- **Exports**: main() using hooks/_common.py allow/block; parser and decision helpers tested without executing pushes.

### Module: custody integration
- **Maps to capability**: Custody of a cap-out CRITICAL
- **Responsibility**: render_report.py, test_render_custody.py, test_custody_prose.py, all listed run-autopilot reference/SKILL files, release-checks and CHANGELOG.
- **Exports**: existing stalled renderer and documented custody lifecycle.

## Dependency Graph

### Foundation Layer (Phase 0)
- **custody core**: no new dependencies; reuse existing state transactions and record_defer.
- **push guard**: depends on the fixed marker contract only.

### Core Layer (Phase 1)
- **custody core**: attended resolution depends on its Phase 0 persisted entries.
- **custody integration**: depends on [custody core, push guard].

### Integration Layer (Phase 2)
- **custody integration**: stalled report and release verification depend on the Phase 1 lifecycle wiring.

## Implementation Phases

### Phase 0: Capture and guard
**Goal**: a cap-out leaves retry-stable custody and its pushes are denied.
**Tasks**:
- [ ] Implement captured intent, pending-deferral migration, marker/mirror and hold refresh (no deps). Premise: do_stall ends append then commit, and reset drops deferred_decisions; recheck execution-time functions, skip/report changed premises. Acceptance: test_custody.py covers base..HEAD/count capture, missing/invalid base exit 2, retry after HEAD advances preserving the original range, pending migration before reset, frontmatterless hold refresh, one entry/notice per op_id, non-critical stalls, and custody-write failure exit 9 with hold/intent/unreset state followed by successful idempotent retry; preserve test_records_stall.py assertions, adding realistic Git fixtures only where the new cap_critical contract requires them.
- [ ] Add/register the PreToolUse Bash guard (no deps). Premise: inspect the current Bash registration and preserve its handlers; skip/report a superseding guard. Acceptance: hook tests cover direct/absolute/command-prefixed push, leading assignments, -C/-c/--git-dir/--work-tree forms, compound commands and effective target repos; echo/arguments/read-only Git pass; malformed/dynamic commands follow the stated fallback; absent/empty markers allow; denial names PRD/range/resolve. Registration names the new guard once in the Bash matcher.
**Exit Criteria**: checkout stall and hook fixtures pass without executing a real push.

### Phase 1: Resolve and route
**Goal**: explicit attended choices clear custody only after recording the outcome.
**Tasks**:
- [ ] Implement the custody resolve verb (depends on: Phase 0). Premise: the command is absent; recheck before adding it, skip/report if superseded. Acceptance: temp-repo subprocess tests cover all three choices, branch at range end, recorded choice in the original batch ledger, state/marker removal only on success, accept leaving Git untouched, and revert conflict exit 5 retaining custody.
- [ ] Wire Phase 0, the cap-out branch, recovery, state-schema and SKILL push-error prose (depends on: Phase 0). Acceptance: test_custody_prose.py pins attended three-choice handling, loop log-and-continue, internally derived range with no manual-range flag, marker writer/consumer and batch mirror, captured stall_op retry fields and custody record shape. The review lens roster sentence remains byte-identical; no calls to the later mint-stubs or design-rework feature are introduced.
**Exit Criteria**: custody CLI and prose tests pass; loop-mode fixtures never perform a resolve.

### Phase 2: Report and release
**Goal**: surface custody and run its enforcement tests in the release gate.
**Tasks**:
- [ ] Wire stalled report custody data and add the custody line (depends on: Phase 1). Premise: stalled_section currently emits Stalled, Detail and Resume; recheck, skip/report if changed. Acceptance: test_render_custody.py proves with-range and range-less rendering through the checkout CLI; cli/golden/expected/report-section.md remains byte-identical.
- [ ] Register the guard tests in release-checks and add targeted Unreleased Added entries for run-autopilot custody and hooks push guarding (depends on: report task). Acceptance: assert each entry's subject under Unreleased without counting unrelated scope entries; `bash dev/bin/release-checks` passes.
**Exit Criteria**: all Success Metrics hold; CLI tests invoke this checkout's skills/run-autopilot/cli/__main__.py with the test interpreter and temp repositories/state.

## Test Strategy

### Critical Scenarios
- **Happy path**: three PRD commits → captured base..HEAD/count 3, migrated records, refreshed hold PRD and push denial; fixture revert resolves custody.
- **Edge case**: interruption after a durable write then retry with a later HEAD → original range, one entry/notice and no duplicate migrated deferrals.
- **Error case**: custody path unwritable → exit 9, PRD in hold, intent retained and state unreset; revert conflict → exit 5 and custody retained.

## Risks
- **Later commits make revert conflict**: attended choice only, preserving Git conflict state and custody.
- **Literal shell parsing is bounded**: pin supported syntax and conservative ambiguous-command fallback; never claim arbitrary shell evaluation.
- **Custody blocks pushes until resolved**: deliberate operator-visible effect, with accept available as an explicit recorded decision.
