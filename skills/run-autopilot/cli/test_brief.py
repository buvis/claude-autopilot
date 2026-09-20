"""Tests for cli/brief.py (PRD 00201): the session brief renderer.

The happy path is pinned byte for byte against cli/golden/expected/
session-brief-build.md rendered from cli/golden/state-brief-build.json (a
build-phase state, 3/7 tasks, a contract card), the package's golden
convention; shape is the contract here, so a golden is the right pin.
"""

from __future__ import annotations

import json
from pathlib import Path

from cli.brief import READ_NEXT, render_brief

GOLDEN = Path(__file__).resolve().parent / "golden"
NOW = "2026-09-20T12:00:00Z"


def _state() -> dict:
    return json.loads((GOLDEN / "state-brief-build.json").read_text(encoding="utf-8"))


def test_renders_the_documented_shape():
    expected = (GOLDEN / "expected" / "session-brief-build.md").read_text(encoding="utf-8")
    assert render_brief(_state(), NOW) == expected


def test_missing_fields_render_as_none():
    text = render_brief({}, NOW)
    assert text.startswith("# Session brief (written 2026-09-20T12:00:00Z at none -> none)\n")
    assert "- repo root: none\n" in text
    assert "- batch: none\n" in text
    assert "- prd: none\n" in text
    assert "- phase: none, next_phase: none, cycle: none\n" in text
    assert "- tasks: none/none done; pending: none; rework: none\n" in text
    assert "- stall_reason: none; pause_reason: none; cap_rotations: none\n" in text
    assert "## Contract card\n(none yet)\n" in text
    assert "## Read next\n- none\n" in text


def test_malformed_fields_render_as_none_not_a_crash():
    state = {
        "phase": 7,
        "next_phase": ["review"],
        "cycle": True,
        "tasks": "not a list",
        "tasks_total": "7",
        "rework_task_ids": {"2": 1},
        "cap_rotations": 3,
        "batch": {"id": 12, "completed_prds": "nope"},
        "contract_card": "   ",
    }
    text = render_brief(state, NOW)
    assert "- batch: none (none PRDs done)\n" in text
    assert "- phase: none, next_phase: none, cycle: none\n" in text
    assert "- tasks: none/none done; pending: none; rework: none\n" in text
    assert "cap_rotations: none\n" in text
    assert "## Contract card\n(none yet)\n" in text


def test_stall_and_pause_reasons_render_as_compact_json():
    state = {
        "stall_reason": {"stalled": "oversized_task", "task": "4"},
        "pause_reason": {"site": "mv_verify", "detail": "backlog -> wip failed"},
    }
    text = render_brief(state, NOW)
    assert (
        '- stall_reason: {"stalled":"oversized_task","task":"4"}; '
        'pause_reason: {"detail":"backlog -> wip failed","site":"mv_verify"}; '
        "cap_rotations: none\n"
    ) in text


def test_read_next_table_covers_every_phase():
    assert set(READ_NEXT) == {"build", "review", "done", "paused"}
    for phase, entries in READ_NEXT.items():
        assert entries, f"{phase} lists no file"
        for path, reason in entries:
            assert path.endswith(".md") and reason


def test_paused_lists_recovery_only_and_done_lists_the_done_gate():
    paused = render_brief({"next_phase": "paused"}, NOW)
    read_next = paused[paused.index("## Read next") : paused.index("## Do not re-read")]
    assert read_next.count("\n- ") == 1
    assert "references/recovery.md" in read_next
    done = render_brief({"next_phase": "done"}, NOW)
    assert "references/phase-done.md` - the gate you are entering" in done


def test_read_next_paths_carry_the_plugin_root_placeholder():
    for entries in READ_NEXT.values():
        for path, _reason in entries:
            assert path.startswith("${CLAUDE_PLUGIN_ROOT}/skills/")


def test_malformed_id_entries_never_render_a_python_repr():
    state = {
        "tasks": [{"status": "pending"}, {"id": 4, "status": "pending"}, "junk"],
        "rework_task_ids": [None, {"id": "2"}, True, "5"],
    }
    text = render_brief(state, NOW)
    assert "pending: 4; rework: 5\n" in text
    only_bad = render_brief({"rework_task_ids": [None, {}]}, NOW)
    assert "rework: none\n" in only_bad
