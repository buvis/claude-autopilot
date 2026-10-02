---
catchup: skip
design: skip
---

# Retire the dead build-overhead counter and re-measure the build phase

Supersedes `00093-cut-build-phase-clerical-overhead-v1.md` (now in `hold/`). Backlog review 2026-08-25 (`~/.claude/dev/local/audit-results/backlog-review-2026-08-25.md`, written while this PRD lived in `~/.claude`) grounded v1 against HEAD: five of its six open tasks had already shipped (`render_prompt.py` + suite, `agents/ivan.md`, rendered dispatch in `work/SKILL.md` steps 2.7/3/5.5/5.7, batch-scoped `state.qwen_preflight`, step-2.95 `n/a:new_module`), and its headline "68 statectl calls = 7.5 per task" was a substring count over a transcript (real: 14 calls, 2.80 per completed task). This v2 keeps only what is still true and unshipped. Backlog review 2026-08-26 (`dev/local/audit-results/backlog-review-2026-08-26.md`) moved the 00120 wording fix out: that archived PRD lives in `~/.claude`, outside this repo's write scope, so it now sits in `~/.claude`'s PRD `00146-close-autopilot-extraction-chores-v1`. The same review named the golden test that must change.

## Problem

`skills/work/scripts/check_build_overhead.py` derives `completed_tasks` from `TaskUpdate` tool calls (`:69-75`), a tool PRD 00120 retired. On any post-00120 transcript it prints `completed tasks: 0` and a statectl-per-task ratio of `0.00`, which reads as a perfect score. Its own acceptance from v1 (>= 7 statectl calls per task on the engram baseline) fails today at 2.80, so the number it was built to track was never real. Nobody has measured the build phase with the statectl verbs that replaced the retired tools.

## Solution

Re-baseline the counter on the statectl task verbs (`task-start`, `task-done`, `task-add`, `task-set-status`), make the script refuse to report a ratio when it finds zero completed tasks, and measure batch `202608180438` (11 PRDs, 62 tasks, drained entirely under statectl 2026-08-18..21, run from `~/.claude`) once, recording the numbers where v1's stale ones lived.

## Requirements

### Must have
- `check_build_overhead.py` counts completed tasks from `statectl ... task-done <id>` (and `task-set-status <id> completed`) Bash calls, never from `TaskUpdate`; when it finds zero completed tasks it prints `completed tasks: 0 (no statectl task-done calls found)` and NO per-task ratio line, exit 0.
- `test_check_build_overhead.py` updated: the retired-tool fixtures are replaced by statectl-shaped transcript fixtures; one test pins the zero-tasks output shape; one pins the per-task ratio on a fixture with 3 `task-done` calls and 9 statectl calls (`3.00`); and the existing golden `test_golden_baseline_engram_session_matches_recorded_numbers` (`:518-546`, today asserting `ratio == 2.80` from `TaskUpdate` counting) is rewritten to assert the zero-tasks line and the absence of a ratio line for that transcript, keeping its `skipif` (the transcript exists only on the author's machine).
- One measurement of batch `202608180438` (the transcripts under `~/.claude/projects/-Users-bob--claude/` whose `state.json` batch id matches; read-only, author's machine) recorded as a table in `dev/local/audit-results/build-overhead-202608180438.md`: sessions, tasks completed, statectl calls per task, prompt-authoring `Write` calls, Agent dispatches. No target is set by this PRD; the table is the baseline the next tuning decision reads.

### Nice to have
- The measurement table gains one row per PRD size bucket (KB of PRD text) since PRD size, not repo difficulty, sets throughput (`~/.claude` project memory `project_autopilot_prd_size_drives_throughput`).

## Implementation

### Module: check_build_overhead
- **Location**: `skills/work/scripts/check_build_overhead.py`, `skills/work/scripts/test_check_build_overhead.py`
- **Responsibility**: count clerical calls per completed task from a transcript, honestly.
- **Exports**: `count_completed_tasks(entries) -> int` (statectl-based), `report(path) -> str`

### Module: measurement
- **Location**: `dev/local/audit-results/build-overhead-202608180438.md`
- **Responsibility**: the recorded baseline.
- **Exports**: none (prose)

### Dependencies
- check_build_overhead: No dependencies (foundation)
- measurement: Depends on [check_build_overhead]

## Tasks

### Phase 0: Foundation
- [ ] Re-baseline `check_build_overhead.py` on statectl task verbs with the zero-tasks guard and updated tests, including the golden rewrite - `uv run --with pytest pytest skills/work/scripts/test_check_build_overhead.py -q` green; running the script on the engram baseline transcript `~/.claude/projects/-Users-bob-git-src-github-com-buvis-engram/4bddd2d6-0c28-4a2d-aa41-bbf06873027d.jsonl` prints the zero-tasks line (it predates statectl verbs) and no ratio.

### Phase 1: Core
- [ ] Measure batch 202608180438 (depends on: Phase 0) - the audit-results table exists with one row per session and a totals row.

## Success Criteria

- `check_build_overhead.py` never prints a `0.00` ratio again: zero completed tasks yields the explicit zero-tasks line.
- The baseline table for batch 202608180438 exists with real statectl-based numbers, and v1's retired metrics (TaskList hydration turns, 7.5 statectl/task) appear nowhere in a live PRD.
