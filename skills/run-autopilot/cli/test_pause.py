"""Tests for cli/pause.py's stand-down marker reads (PRD 00172, 00199).

`consume_pause` is covered in test_notify_out.py. Here: the reason and the
condition a session writes into `pause-requested` when it stands down for a
peer, and the `unknown` default the loop records when the marker carries no
condition.
"""

from __future__ import annotations

import json
import os

from cli.pause import stand_down_condition, stand_down_reason


def _write_marker(tmp_path, payload: str, at: float = 2_000.0) -> None:
    marker = tmp_path / "pause-requested"
    marker.write_text(payload)
    os.utime(marker, (at, at))


def test_condition_defaults_to_unknown(tmp_path):
    assert stand_down_condition(tmp_path) == "unknown"  # no marker at all
    _write_marker(tmp_path, json.dumps({"reason": "peer x owns p.md"}))
    assert stand_down_condition(tmp_path) == "unknown"  # marker, no condition
    _write_marker(tmp_path, "")
    assert stand_down_condition(tmp_path) == "unknown"  # an operator touch
    _write_marker(tmp_path, json.dumps({"condition": 7}))
    assert stand_down_condition(tmp_path) == "unknown"  # not a string


def test_condition_is_read_from_the_marker(tmp_path):
    _write_marker(
        tmp_path,
        json.dumps({"reason": "peer x owns p.md (dirty tree)", "condition": "dirty_tree"}),
    )
    assert stand_down_condition(tmp_path) == "dirty_tree"
    _write_marker(tmp_path, json.dumps({"condition": " peer_claimed \n"}))
    assert stand_down_condition(tmp_path) == "peer_claimed"


def test_reason_and_condition_read_the_same_marker(tmp_path):
    _write_marker(
        tmp_path,
        json.dumps({"reason": "peer x owns p.md", "condition": "state_after_leave"}),
        at=2_000.0,
    )
    assert stand_down_reason(tmp_path, since=1_500.0) == "peer x owns p.md"
    assert stand_down_condition(tmp_path) == "state_after_leave"


def test_reason_ignores_a_marker_older_than_the_session(tmp_path):
    _write_marker(tmp_path, json.dumps({"reason": "stale"}), at=1_000.0)
    assert stand_down_reason(tmp_path, since=1_500.0) is None
