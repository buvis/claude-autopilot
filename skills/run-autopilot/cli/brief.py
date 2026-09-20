"""cli/brief.py - render the session brief (PRD 00201).

A fresh headless session spent ~100 tool calls re-deriving where it was
(state keys one at a time, four to six reference files, a hunt for the
wrapper binary). `render_brief` turns `state.json` plus the contract card
into one page the next session reads first: where the batch stands, the card
verbatim, and exactly which files the next gate needs. Code renders it, never
the model, so its shape is fixed and pinned byte for byte by
cli/golden/expected/session-brief-build.md.

Every field is read defensively: a missing or malformed value renders as
`none`, never as a crash, because the brief is written at a hand-off, where a
failure must be one stderr line and never a phase failure.
"""

from __future__ import annotations

import json

_PLUGIN = "${CLAUDE_PLUGIN_ROOT}/skills"

# next_phase -> the files that gate needs, in reading order. The paths keep
# the `${CLAUDE_PLUGIN_ROOT}` placeholder on purpose: the session substitutes
# the root it was told at load, exactly as for every reference file.
READ_NEXT: dict[str, list[tuple[str, str]]] = {
    "build": [
        (f"{_PLUGIN}/run-autopilot/references/phase-build.md", "the gate you are entering"),
        (f"{_PLUGIN}/work/SKILL.md", "only when tasks are pending"),
    ],
    "review": [
        (f"{_PLUGIN}/run-autopilot/references/phase-review.md", "the gate you are entering"),
        (
            f"{_PLUGIN}/review-work-completion/SKILL.md",
            "the lens roster the review gate invokes",
        ),
    ],
    "done": [
        (f"{_PLUGIN}/run-autopilot/references/phase-done.md", "the gate you are entering"),
    ],
    "paused": [
        (
            f"{_PLUGIN}/run-autopilot/references/recovery.md",
            "the resume handlers for a paused or stalled state",
        ),
    ],
}


def _text(value) -> str:
    return value if isinstance(value, str) and value else "none"


def _count(value) -> str:
    return str(value) if isinstance(value, int) and not isinstance(value, bool) else "none"


def _is_id(value) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    return isinstance(value, int) and not isinstance(value, bool)


def _id_list(value) -> str:
    """Comma-joined ids; entries that are not a str or int are dropped, and a
    list with none left renders `none` (never a Python repr)."""
    ids = [str(item) for item in value if _is_id(item)] if isinstance(value, list) else []
    return ", ".join(ids) if ids else "none"


def _json_or_none(value) -> str:
    if value is None:
        return "none"
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def _batch_line(batch) -> str:
    if not isinstance(batch, dict):
        return "- batch: none"
    completed = batch.get("completed_prds")
    done = str(len(completed)) if isinstance(completed, list) else "none"
    return f"- batch: {_text(batch.get('id'))} ({done} PRDs done)"


def _pending_ids(tasks) -> list:
    if not isinstance(tasks, list):
        return []
    return [
        task.get("id")
        for task in tasks
        if isinstance(task, dict) and task.get("status") != "completed"
    ]


def _lane_line(state: dict) -> str:
    # PRD 00205: the effective lane beside its classification, `none` on a
    # state written before the lane fields existed.
    if not isinstance(state.get("lane_effective"), str):
        return "- lane: none"
    return (
        f"- lane: {_text(state.get('lane_effective'))} (classified "
        f"{_text(state.get('lane'))}, {_text(state.get('lane_reason'))})"
    )


def _where(state: dict) -> list[str]:
    rotations = state.get("cap_rotations")
    return [
        "## Where",
        f"- repo root: {_text(state.get('repo_root'))}",
        _batch_line(state.get("batch")),
        f"- prd: {_text(state.get('prd'))}",
        f"- phase: {_text(state.get('phase'))}, next_phase: "
        f"{_text(state.get('next_phase'))}, cycle: {_count(state.get('cycle'))}",
        _lane_line(state),
        f"- tasks: {_count(state.get('tasks_completed'))}/{_count(state.get('tasks_total'))}"
        f" done; pending: {_id_list(_pending_ids(state.get('tasks')))};"
        f" rework: {_id_list(state.get('rework_task_ids'))}",
        f"- stall_reason: {_json_or_none(state.get('stall_reason'))};"
        f" pause_reason: {_json_or_none(state.get('pause_reason'))};"
        f" cap_rotations: {_count(len(rotations) if isinstance(rotations, list) else None)}",
    ]


def _read_next(next_phase) -> list[str]:
    # A next_phase the table does not know (a legacy `blind`/`doubt`, a typo)
    # renders `- none` exactly like a missing one: the header already shows
    # the odd value, and Phase 0 falls back to its state reads.
    entries = READ_NEXT.get(next_phase) if isinstance(next_phase, str) else None
    if not entries:
        return ["## Read next", "- none"]
    return ["## Read next", *[f"- `{path}` - {reason}" for path, reason in entries]]


def render_brief(state: dict, now: str) -> str:
    """The brief for `state` as written at `now` (an ISO UTC stamp), in the
    documented shape: header, Where, Contract card, Read next, Do not
    re-read. `state` is whatever `state.json` parsed to; every field it
    lacks renders as `none`."""
    card = state.get("contract_card")
    lines = [
        f"# Session brief (written {now} at {_text(state.get('phase'))} -> "
        f"{_text(state.get('next_phase'))})",
        "",
        *_where(state),
        "",
        "## Contract card",
        card if isinstance(card, str) and card.strip() else "(none yet)",
        "",
        *_read_next(state.get("next_phase")),
        "",
        "## Do not re-read",
        "- state.json keys listed above (already here)",
        "- the reference files not listed under Read next",
    ]
    return "\n".join(lines) + "\n"
