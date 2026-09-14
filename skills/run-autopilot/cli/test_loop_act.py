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

from cli import loop_act
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
