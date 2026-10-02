---
design: skip
---

# Treat a session stand-down as a pause, not a death

## Problem

The loop driver (`cli/loop.py`) reads an untouched `state.json` as "the session died", retries once, then parks the PRD to `hold/`. A headless session that finds another session already working the same PRD has no sanctioned way to say "I stood down on purpose": it writes nothing (correct, to avoid corrupting the peer's state) and gets counted as a death. On 2026-09-02 in agent-skills, four consecutive sessions stood down for the interactive session `agent-skills-7b`, which was mid-dispatch on PRD 00010 task 5. The loop burned its retry, wrote `park-requested` for a healthy PRD 4 of 13 tasks in, and only stopped because the last session had touched `pause-requested` by improvisation. Even then the loop decided "park" first and consumed the pause marker second, so the false park marker survived for the next Phase 0 to act on. The one-loop-per-repo guard sees only wrappers, not bare interactive sessions, so this recurs whenever a human works a PRD while the loop runs.

## Solution

Make the existing pause marker the stand-down signal. A session that stands down writes `pause-requested` with a one-line JSON reason and ends its turn without touching state. The loop checks for a marker written during the session before it classifies "no progress": a fresh marker means `paused` (stop, notify with the reason, no retry burned, no park marker), the same exit the operator pause already takes. The run-autopilot skill gains a short stand-down procedure so the improvised behavior becomes the documented one. No peer-session detection is added to the driver; the session decides, the driver reacts.

## Requirements

### Must have
- In `_decide_no_progress`, before the limit, network, and `died_next` checks: if `pause-requested` exists with mtime at or after the session start, set `signal = "paused"` and `detail = "session stood down: <reason>"` (reason from the marker's JSON, or `"no reason given"` when the marker is empty or not JSON).
- That decision leaves `_died_retries` unchanged and writes no `park-requested`.
- The `paused` act branch for a stand-down consumes the marker, leaves the `paused-by-operator` stamp, prints the existing resume runbook, notifies once with the reason, and exits 0.
- An operator `touch` (empty marker) keeps working exactly as today, both at the top-of-loop check and through this new path.
- `run-autopilot/SKILL.md` § Session Loop gets a decision-table row for the stand-down (between rows 0 and 1) and a "Stand-down procedure" paragraph: when Phase 0 finds a peer session owning the selected PRD (a busy peer session in this repo per ListAgents, plus `state.json` or task artifacts modified within the last 15 minutes), write `pause-requested` as `{"reason": "<who owns the PRD and what evidence>"}` (guess), end the turn, and touch nothing else. The Operator runbook's Pause line notes that the marker may carry that JSON.
- `CHANGELOG.md` entry under `[Unreleased]` / Fixed with scope `run-autopilot`.

### Nice to have
- The stand-down reason lands in `loop-metrics.jsonl` on the pause row so `tracon` and the batch report can show why the loop stopped.

## Implementation

### Module: loop
- **Location**: `skills/run-autopilot/cli/loop.py`, `skills/run-autopilot/cli/pause.py`
- **Responsibility**: classify a session-written pause marker as `paused` before the no-progress ladder; read the optional JSON reason.
- **Exports**: `pause.read_reason(autopilot_dir) -> str`, the existing `consume_pause`, `stamp_paused`; `Loop._decide_no_progress` gains the marker check.

### Module: skill-docs
- **Location**: `skills/run-autopilot/SKILL.md`
- **Responsibility**: the decision-table row, the stand-down procedure, the runbook note.
- **Exports**: none (prose).

### Dependencies
- loop: No dependencies (foundation)
- skill-docs: Depends on [loop] (documents the branch the code adds)

## Tasks

### Phase 0: Foundation
- [ ] Add `pause.read_reason` and the stand-down branch in `_decide_no_progress` - `cli/test_loop.py` gains `test_stand_down_marker_pauses_without_retry_or_park`: a session that leaves state untouched and writes `pause-requested` with `{"reason": "peer agent-skills-7b owns task 5"}` makes the loop exit 0 after one launch, with no `park-requested` file, `paused-by-operator` present, the reason in the notification, and `_died_retries` still 0. `test_died_session_retries_once_then_parks_then_guard_halts` still passes unchanged.
- [ ] Keep the empty-marker path - `test_empty_stand_down_marker_reads_as_operator_pause`: the same scenario with an empty marker exits 0 with detail `session stood down: no reason given`. Existing `test_pause_marker_stops_before_any_spawn` still passes.

### Phase 1: Core
- [ ] Write the SKILL.md row, procedure, and runbook note (depends on: Phase 0) - `rg -n "Stand-down procedure" skills/run-autopilot/SKILL.md` matches once; the Session Loop decision table has a row containing `pause-requested` written during the session; `uv run pytest skills/run-autopilot` passes; CHANGELOG has the Fixed entry.

## Success Criteria

- A headless session that writes `pause-requested` and nothing else stops the loop with exit 0 and no `park-requested` file, verified by the Phase 0 tests.
- `uv run pytest skills/run-autopilot` passes with the two new tests and no skips added.
- The 2026-09-02 sequence (four stand-downs on PRD 00010) replayed against the new driver ends at the first stand-down with the PRD still in `wip/`.
