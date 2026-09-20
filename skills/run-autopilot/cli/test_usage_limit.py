"""Tests for cli/usage_limit.py's loop-side wait decision (PRD 00106).

Detection itself is covered by scripts/test_detect_usage_limit.py, which
loads scripts/detect_usage_limit.py by path — now a re-export shim over
this module, so that whole suite exercises the absorbed implementation.
Here: the branch-5 arithmetic the wrapper used to do inline, plus the
shim's same-object guarantee.
"""

from __future__ import annotations

import importlib.util
import json
import time
from pathlib import Path

from cli import usage_limit


def _event(status: str, resets_at: int, limit_type: str = "five_hour") -> str:
    return json.dumps(
        {
            "type": "rate_limit_event",
            "rate_limit_info": {
                "status": status,
                "resetsAt": resets_at,
                "rateLimitType": limit_type,
                "utilization": 0.9,
                "isUsingOverage": False,
            },
        },
    )


# ── the allowed_warning parse (PRD 00199) ────────────────────────────────────


def test_warning_reset_reads_allowed_warning():
    reset = int(time.time()) + 3600
    tail = "\n".join([json.dumps({"type": "result"}), _event("allowed_warning", reset)])
    assert usage_limit._warning_reset(tail) == reset


def test_warning_reset_ignores_a_stale_warning():
    reset = int(time.time()) - usage_limit.GRACE_SECS - 10
    assert usage_limit._warning_reset(_event("allowed_warning", reset)) is None


def test_warning_reset_ignores_the_seven_day_window_and_rejected_events():
    reset = int(time.time()) + 3600
    tail = "\n".join(
        [
            _event("allowed_warning", reset, limit_type="seven_day"),
            _event("rejected", reset + 1),
        ],
    )
    assert usage_limit._warning_reset(tail) is None
    assert usage_limit._rejected_reset(tail) == reset + 1


def test_detect_warning_from_log_reads_the_tail_and_tolerates_a_missing_log(tmp_path):
    reset = int(time.time()) + 900
    log = tmp_path / "last-session.log"
    log.write_text(
        _event("allowed_warning", reset) + "\n" + json.dumps({"type": "result"}) + "\n",
    )
    assert usage_limit.detect_warning_from_log(log) == reset
    assert usage_limit.detect_warning_from_log(tmp_path / "absent.log") is None


def test_detect_rejected_from_log_reads_only_the_event_never_the_prose(tmp_path):
    reset = int(time.time()) + 900
    log = tmp_path / "last-session.log"
    log.write_text("You've hit your session limit · resets 8:10pm\n")
    assert usage_limit.detect_rejected_from_log(log) is None
    log.write_text(_event("rejected", reset) + "\n")
    assert usage_limit.detect_rejected_from_log(log) == reset


# ── the branch-5 wait arithmetic ─────────────────────────────────────────────


def test_wait_is_reset_minus_now_plus_margin():
    assert usage_limit.wait_decision(1000, now=400, max_wait_secs=21600) == 720


def test_wait_floors_at_sixty_seconds():
    # A reset that just passed still sleeps the minimum, never 0 or negative.
    assert usage_limit.wait_decision(1000, now=1500, max_wait_secs=21600) == 60


def test_wait_at_the_cap_boundary_still_waits():
    # Bash used -le: a wait exactly equal to the cap is honored.
    assert usage_limit.wait_decision(1000, now=880, max_wait_secs=240) == 240


def test_wait_beyond_cap_is_refused():
    assert usage_limit.wait_decision(100000, now=0, max_wait_secs=21600) is None


def test_scripts_shim_reexports_the_same_objects():
    shim_path = (
        Path(__file__).resolve().parents[1] / "scripts" / "detect_usage_limit.py"
    )
    spec = importlib.util.spec_from_file_location("detect_usage_limit_shim", shim_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.detect_from_log is usage_limit.detect_from_log
    assert module.detect is usage_limit.detect
