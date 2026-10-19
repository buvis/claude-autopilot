"""Tests for cli/loop_act.py (PRD 00192 seam 4): the drained-path helpers
and the act branches of the loop driver, moved out of test_loop.py with the
code they cover. The harness (fake clock, scripted spawn, make_loop) is
cli/loop_testutil.py.
"""

from __future__ import annotations

import io
import json
import os
import stat
import sys
from pathlib import Path

from cli import loop_act, state, statectl
from cli.loop_act import run_agoge
from cli import loop_testutil
from cli.loop_testutil import (
    _notified,
    make_loop,
    terminal_step,
    write_state,
)

# The autouse fixture registers by being a module attribute.
_no_real_drain_side_effects = loop_testutil._no_real_drain_side_effects


# ── preflights ───────────────────────────────────────────────────────────────


def test_stand_down_marker_pauses_without_retry_or_park(tmp_path):
    # PRD 00172: a session that finds a peer owning its PRD writes the
    # pause marker with a reason and touches nothing else. That is a
    # stand-down, not a death - no retry burned, no park marker, the
    # operator-pause exit with the reason quoted.
    def stand_down(ap_dir: Path) -> None:
        (ap_dir / "pause-requested").write_text(
            json.dumps({"reason": "peer agent-skills-7b owns task 5"}),
        )

    lp = make_loop(tmp_path, [stand_down])
    ap = lp._test["ap_dir"]
    write_state(ap, prd="00010-x-v1.md", next_phase="build", batch={"id": "b"})
    assert lp.run() == 0
    assert len(lp._test["spawn"].launches) == 1
    assert not (ap / "park-requested").exists()
    assert not (ap / "pause-requested").exists()
    assert (ap / "paused-by-operator").is_file()
    assert lp._died_retries == 0
    out = lp._test["out"].getvalue()
    assert "stood down" in out
    assert "peer agent-skills-7b owns task 5" in out
    assert "Resume unattended: autoclaude" in out
    assert _notified(lp, "peer agent-skills-7b owns task 5")


def test_empty_stand_down_marker_reads_as_operator_pause(tmp_path):
    # An operator `touch` mid-session is a stand-down with no reason: the
    # same exit, never the died ladder.
    def touch_marker(ap_dir: Path) -> None:
        (ap_dir / "pause-requested").touch()

    lp = make_loop(tmp_path, [touch_marker])
    ap = lp._test["ap_dir"]
    write_state(ap, prd="00010-x-v1.md", next_phase="build", batch={"id": "b"})
    assert lp.run() == 0
    assert len(lp._test["spawn"].launches) == 1
    assert not (ap / "park-requested").exists()
    assert "session stood down: no reason given" in lp._test["out"].getvalue()


def test_park_notification_names_the_reason(tmp_path):
    # Packet 13: the park notification said only "Parking <prd>.", while
    # the stdout line it mirrors carries the decision detail - the
    # notification must name the reason too.
    lp = make_loop(tmp_path, [])
    ap = lp._test["ap_dir"]
    decision = {
        "prd": "00010-x-v1.md",
        "detail": "budget: $310.00 > $300; parking 00010-x-v1.md",
    }

    assert lp._act_park(decision, ap) is None

    assert _notified(lp, f"Parking {decision['prd']} ({decision['detail']}).")


def test_failed_invalidation_marks_the_child_entry_stale(tmp_path, monkeypatch):
    # Stub 00305 (PRD 00282 cycle 2): _invalidate_loop_entry swallowed a
    # second write failure, so a loop_entry from an earlier successful
    # launch stayed on disk and the session replayed its stale result
    # instead of running enter() for real. The launched child's
    # environment must carry the stale marker so the session skips the
    # replay.
    def raise_state_error(*args, **kwargs):
        raise state.StateError("pre-launch enter not available")

    def raise_on_mutate(path, apply):
        raise OSError("disk full")

    monkeypatch.setattr(statectl, "mutate", raise_on_mutate)

    lp = make_loop(tmp_path, [terminal_step()], enter_fn=raise_state_error)
    ap = lp._test["ap_dir"]
    write_state(ap, prd="00010-x-v1.md", next_phase="build", batch={"id": "b"})

    assert lp.run() == 0

    assert lp._test["spawn"].launches[-1]["env"].get("_AUTOPILOT_LOOP_ENTRY_STALE") == "1"


def test_stale_entry_marker_does_not_leak_into_a_later_successful_launch(
    tmp_path,
    monkeypatch,
):
    # The marker belongs to the launch whose pre-entry and invalidation both
    # failed, not to the loop: the next launch, whose pre-entry succeeds,
    # carries no marker key at all.
    real_mutate = statectl.mutate
    enter_calls = []

    def enter_fails_once(*args, **kwargs):
        enter_calls.append(1)
        if len(enter_calls) == 1:
            raise state.StateError("pre-launch enter not available")
        return {}

    def raise_on_mutate(path, apply):
        raise OSError("disk full")

    def first_session(ap_dir: Path) -> None:
        # The failures end with the first session.
        monkeypatch.setattr(statectl, "mutate", real_mutate)
        write_state(ap_dir, prd="00010-x-v1.md", next_phase="build", batch={"id": "b"})

    monkeypatch.setattr(statectl, "mutate", raise_on_mutate)
    lp = make_loop(
        tmp_path,
        [first_session, terminal_step()],
        enter_fn=enter_fails_once,
    )
    ap = lp._test["ap_dir"]
    write_state(ap, prd="00010-x-v1.md", next_phase="build", batch={"id": "b"})

    assert lp.run() == 0

    launches = lp._test["spawn"].launches
    assert len(launches) == 2
    assert launches[0]["env"]["_AUTOPILOT_LOOP_ENTRY_STALE"] == "1"
    assert "_AUTOPILOT_LOOP_ENTRY_STALE" not in launches[1]["env"]


# ── drained-path helpers ─────────────────────────────────────────────────────


def test_run_agoge_skips_a_zero_drain(tmp_path):
    out = io.StringIO()
    run_agoge(tmp_path, "b-1", 0, {}, out)
    assert "skipped — the batch drained no PRDs" in out.getvalue()


def _fake_claude(tmp_path: Path, exit_code: int = 0) -> str:
    path = tmp_path / "fake-claude"
    argv_file = tmp_path / "agoge-argv"
    path.write_text(
        f"#!{sys.executable}\nimport sys\n"
        f"open({str(argv_file)!r}, 'w').write(repr(sys.argv[1:]))\n"
        f"print('qa output')\nsys.exit({exit_code})\n",
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return str(path)


def test_run_agoge_launches_authorized_and_logs(tmp_path):
    (tmp_path / "reports").mkdir()
    out = io.StringIO()
    run_agoge(
        tmp_path,
        "b-1",
        2,
        {"PATH": os.environ["PATH"]},
        out,
        claude_bin=_fake_claude(tmp_path),
    )
    argv = (tmp_path / "agoge-argv").read_text()
    assert "'-p', '--permission-mode', 'auto'" in argv
    assert "--authorized autoclaude-drain" in argv
    assert "walkthrough pending" in out.getvalue()
    assert "qa output" in (tmp_path / "reports" / "b-1-agoge.log").read_text()


def test_run_agoge_brake_removes_only_the_flag(tmp_path):
    (tmp_path / "reports").mkdir()
    out = io.StringIO()
    run_agoge(
        tmp_path,
        "b-1",
        2,
        {"PATH": os.environ["PATH"], "_AUTOPILOT_AGOGE_AUTHORIZED": "0"},
        out,
        claude_bin=_fake_claude(tmp_path),
    )
    argv = (tmp_path / "agoge-argv").read_text()
    assert "/run-agoge" in argv
    assert "--authorized" not in argv


def test_run_agoge_failure_is_swallowed_and_reported(tmp_path, capsys):
    (tmp_path / "reports").mkdir()
    out = io.StringIO()
    run_agoge(
        tmp_path,
        "b-1",
        2,
        {"PATH": os.environ["PATH"]},
        out,
        claude_bin=_fake_claude(tmp_path, exit_code=3),
    )
    err = capsys.readouterr().err
    assert "run failed (rc 3)" in err
    assert "The drain is unaffected" in err


def _fake_claude_env_probe(tmp_path: Path) -> str:
    path = tmp_path / "fake-claude-env-probe"
    env_file = tmp_path / "agoge-env"
    path.write_text(
        f"#!{sys.executable}\nimport json, os\n"
        f"open({str(env_file)!r}, 'w').write(json.dumps(dict(os.environ)))\n",
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return str(path)


def test_run_agoge_scrubs_host_markers(tmp_path):
    (tmp_path / "reports").mkdir()
    out = io.StringIO()
    run_agoge(
        tmp_path,
        "b-1",
        2,
        {"PATH": os.environ["PATH"], "CODEX_SESSION_ID": "abc123"},
        out,
        claude_bin=_fake_claude_env_probe(tmp_path),
    )
    child_environ = json.loads((tmp_path / "agoge-env").read_text())
    assert "CODEX_SESSION_ID" not in child_environ


def test_run_agoge_default_cap_is_two_hours(tmp_path, monkeypatch):
    # 00351: the drain agoge run's wall-clock cap default must be 7200s
    # (two hours), not the old 3600s, when no env override is given.
    (tmp_path / "reports").mkdir()
    captured = {}

    def fake_process(claude_bin, prompt, log_path, cap, env):
        captured["cap"] = cap
        return 0

    monkeypatch.setattr(loop_act, "_run_agoge_process", fake_process)
    out = io.StringIO()
    run_agoge(tmp_path, "b-1", 2, {}, out)
    assert captured["cap"] == 7200


def test_run_agoge_cap_env_overrides_the_default(tmp_path, monkeypatch):
    # 00351: _AUTOPILOT_AGOGE_CAP still overrides the default cap.
    (tmp_path / "reports").mkdir()
    captured = {}

    def fake_process(claude_bin, prompt, log_path, cap, env):
        captured["cap"] = cap
        return 0

    monkeypatch.setattr(loop_act, "_run_agoge_process", fake_process)
    out = io.StringIO()
    env = {"_AUTOPILOT_AGOGE_CAP": "900"}
    run_agoge(tmp_path, "b-1", 2, env, out)
    assert captured["cap"] == 900


def test_drained_branch_runs_purge_and_agoge_with_the_count(tmp_path, monkeypatch):
    purges, agoges = [], []
    monkeypatch.setattr(loop_act, "run_purge", lambda repo: purges.append(repo))
    monkeypatch.setattr(
        loop_act,
        "run_agoge",
        lambda ap_dir, batch, drained, env, out, claude_bin="claude": agoges.append(
            (batch, drained),
        ),
    )
    lp = make_loop(
        tmp_path,
        [terminal_step(batch="b-9", completed_prds=["00001-a.md", "00002-b.md"])],
    )
    write_state(lp._test["ap_dir"], prd="p.md", next_phase="build", batch={"id": "b-9"})
    assert lp.run() == 0
    assert purges == [lp.cwd]
    assert agoges == [("b-9", 2)]
    assert "2 PRDs completed." in lp._test["out"].getvalue()
