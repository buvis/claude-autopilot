---
catchup: skip
design: skip
---

# Retain attempt history across batches

Source: backlog review 2026-08-25, gap G1 (`~/.claude/dev/local/audit-results/backlog-review-2026-08-25.md`, written while this PRD lived in `~/.claude`). Enabler for `~/.claude`'s held PRD 00113 and for audit-qwen's archived-state input. Backlog review 2026-08-26 (`dev/local/audit-results/backlog-review-2026-08-26.md`) cut the audit-qwen repoint from this PRD: that skill is not part of the plugin and its file is outside this repo's write scope, so the reader is written by `~/.claude`'s PRD `00146-close-autopilot-extraction-chores-v1` against the row shape frozen below.

## Problem

Every per-task fact the pipeline records - `state.tasks[].attempts[]` with `implementor`, `model`, `preflight_outcome`, `pipeline`, `escalation_reason`, `escalated_from`, `qwen_gate_failed`, `qwen_excluded_reason`, `red_check`, `self_deslop`, `review` - lives only in the live `state.json`, and the per-PRD reset at `complete-prd` drops `tasks[]` (`cli/records.py` `PER_PRD_RESET_FIELDS`). Only two `*state-final.json` snapshots exist under `~/.claude/dev/local/autopilot/reports/`, both with `tasks=0`. Measured 2026-08-25: zero escalation stamps exist anywhere on this machine although PRD 00065 has written them since July; 0 of 35 attempts across all repos carry gate fields; `~/.claude/skills/audit-qwen/scripts/audit_qwen.py:452` admits its archived-state input is dead. Any tuning, report card, or audit that wants attempt outcomes is starved by construction, not by sample size.

## Solution

Append every task's attempt records to a durable per-repo ledger at the moment `complete-prd` closes the PRD, before the reset runs. One JSONL row per attempt, carrying the batch id, PRD filename, task id and name, and the attempt object verbatim. Readers (00113's tuner, audit-qwen) then read the ledger instead of live state; wiring those readers is `~/.claude` work, not this PRD's.

## Requirements

### Must have
- `statectl.py complete-prd <prd>` appends, inside the same locked transaction and BEFORE the per-PRD reset, one row per entry of `tasks[].attempts[]` to `dev/local/autopilot/ledger/attempts.jsonl`: `{"batch_id", "prd", "task_id", "task_name", "task_model", "qwen_eligible", "recorded_at", "attempt": <the attempt object verbatim>}`. `recorded_at` is the ISO-8601 UTC time of the write.
- Append discipline: create the file (and `ledger/`) if absent, never truncate, tolerate a missing trailing newline. Reimplement it inside `cli/statectl.py`; do NOT import `hooks/_common.py` (its `append_jsonl_row` is a hooks-side helper and `cli/` must not depend on `hooks/`). A write failure is a loud `SchemaError`-class exit that leaves `state.json` untouched (no reset without the ledger row).
- `references/state-schema.md` documents the ledger file and row shape next to `loop-metrics.jsonl`; `references/phase-done.md` names it in the `complete-prd` step.
- Tests: cases for the appended rows (count equals the attempt count across tasks; row fields; verbatim attempt object; append to an existing ledger; write failure leaves state untouched). `scripts/test_statectl_complete_prd.py` is 708 lines; if the new cases would push it past the 800-line cap, put them in a new `scripts/test_statectl_ledger.py`.

### Nice to have
- A one-line `ledger/attempts.jsonl` row count in the batch report's Loop Metrics section.

## Implementation

### Module: attempt-ledger
- **Location**: `skills/run-autopilot/cli/statectl.py` (`do_complete_prd`, `:376`), `skills/run-autopilot/scripts/test_statectl_complete_prd.py` (or the new `test_statectl_ledger.py`), `skills/run-autopilot/references/state-schema.md`, `skills/run-autopilot/references/phase-done.md`
- **Responsibility**: durable per-attempt rows written at PRD close, documented.
- **Exports**: `append_attempt_rows(state, prd, ledger_path) -> int` (rows written)

### Dependencies
- attempt-ledger: No dependencies (foundation)

## Tasks

### Phase 0: Foundation
- [ ] Append attempt rows in `complete-prd` before the reset, with tests and the two doc updates - `uv run --with pytest pytest skills/run-autopilot/scripts/test_statectl_complete_prd.py skills/run-autopilot/scripts/test_statectl_ledger.py -q` green (drop the second path if the cases fit in the first file); a fixture state with 2 tasks x 2 attempts yields 4 ledger rows and a reset state; a forced ledger write failure leaves `state.tasks` intact and exits non-zero; `rg -n "attempts.jsonl" skills/run-autopilot/references/state-schema.md skills/run-autopilot/references/phase-done.md` hits both.

### Phase 1: Core
No Phase 1 work in this repo: the ledger's readers (audit-qwen, 00113's tuner) live in `~/.claude` and are wired there against the row shape above.

## Success Criteria

- The fixture tests prove the reset never runs without the rows: a forced ledger write failure leaves `state.tasks` intact and exits non-zero; a clean close yields exactly one row per attempt.
- `do_complete_prd` stays under 50 lines after the change (it is 18 lines today, `cli/statectl.py:376-393`, since PRD 00122 extracted `_completed_prd_record`; the ledger write goes into `append_attempt_rows`).
- Post-release signal (not judged in-session): after the next batch closes one PRD on this machine, `dev/local/autopilot/ledger/attempts.jsonl` holds one row per attempt with `escalation_reason` present where stamped.
