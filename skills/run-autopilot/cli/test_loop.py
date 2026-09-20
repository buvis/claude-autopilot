"""Tests for cli/loop.py (PRD 00106).

Re-expresses the bash loop contracts against the CLI driver: the
decision table (test_autoclaude_park.sh, test_autoclaude_review_cap.sh,
test_autoclaude_state_write_failed.sh), the preflights
(test_autoclaude_plugin_pin.sh, memory breaker, duplicate-loop guard),
the metrics line (test_loop_metrics.sh), the drained-path agoge run
(test_autoclaude_agoge_drain.sh), and the e2e launch-line assertions
from test_autoclaude_build_model.sh - all through injected
collaborators, no real claude/network/notifier.

Timing: the harness runs on a fake clock, and `state_touched` compares
the state file's mtime against it - so every scripted session that
writes state gets its mtime pinned to the fake clock, and states
pre-written by a test are stamped BEFORE the clock's start (a state
left by a previous session is by definition untouched by this one).
"""

from __future__ import annotations

import io
import json
import os
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

from cli import convergence
from cli import loop as loop_mod
from cli.loop import Loop
from cli import loop_testutil
from cli.loop_testutil import (
    Recorder,
    _notified,
    make_loop,
    metrics_rows,
    noop_step,
    terminal_step,
    write_log,
    write_state,
)

_REAL_CLEANUP_ORPHANS = Loop._cleanup_orphans

# The autouse fixture registers by being a module attribute.
_no_real_drain_side_effects = loop_testutil._no_real_drain_side_effects


# ── the drained happy path (the bash e2e rows) ───────────────────────────────


def test_drained_batch_exits_zero_with_banner_and_notification(tmp_path):
    lp = make_loop(tmp_path, [terminal_step(batch="20260708-e2e")])
    ap = lp._test["ap_dir"]
    write_state(
        ap,
        prd="00088-thin-v1.md",
        next_phase="build",
        replan_count=0,
        cap_rotations=[],
        stall_reason=None,
        batch={"id": "20260708-e2e"},
    )
    rc = lp.run()
    assert rc == 0
    out = lp._test["out"].getvalue()
    assert "Backlog drained." in out
    assert "━━" in out and "phase build" in out
    assert _notified(lp, "Backlog drained.")
    assert (ap / "reports" / "20260708-e2e-state-final.json").exists()
    assert not (ap / "state.json").exists()


def test_signal_free_build_launches_sonnet_xhigh(tmp_path):
    lp = make_loop(tmp_path, [terminal_step()])
    ap = lp._test["ap_dir"]
    prds = ap.parent / "prds" / "wip"
    prds.mkdir(parents=True)
    (prds / "00088-thin-v1.md").write_text("# fixture\n")
    write_state(
        ap,
        prd="00088-thin-v1.md",
        next_phase="build",
        replan_count=0,
        cap_rotations=[],
        stall_reason=None,
        batch={"id": "b"},
    )
    assert lp.run() == 0
    launch = lp._test["spawn"].launches[0]
    assert launch["model"] == "claude-sonnet-5[1m]"
    assert launch["effort"] == "xhigh"


def test_build_kill_switch_wins(tmp_path):
    lp = make_loop(
        tmp_path,
        [terminal_step()],
        env={"_AUTOPILOT_MODEL_BUILD": "claude-opus-5[1m]"},
    )
    write_state(lp._test["ap_dir"], prd="p.md", next_phase="build", batch={"id": "b"})
    assert lp.run() == 0
    assert lp._test["spawn"].launches[0]["model"] == "claude-opus-5[1m]"


def test_bootstrap_without_state_is_a_build_launch(tmp_path):
    lp = make_loop(tmp_path, [terminal_step()])
    assert lp.run() == 0
    launch = lp._test["spawn"].launches[0]
    assert launch["model"] == "claude-sonnet-5[1m]"
    assert "bootstrap" in lp._test["out"].getvalue()


def test_review_branch_routes_opus_with_review_cap(tmp_path):
    lp = make_loop(tmp_path, [terminal_step()])
    write_state(lp._test["ap_dir"], prd="p.md", next_phase="review", batch={"id": "b"})
    assert lp.run() == 0
    launch = lp._test["spawn"].launches[0]
    assert launch["model"] == "claude-opus-5[1m]"
    assert launch["cap_secs"] == 10800


def test_run_relaunches_a_cycle_two_review_at_high_effort_and_persists_it(tmp_path):
    lp = make_loop(tmp_path, [terminal_step()])
    ap = lp._test["ap_dir"]
    write_state(ap, prd="p.md", next_phase="review", cycle=2, batch={"id": "b"})
    assert lp.run() == 0
    launch = lp._test["spawn"].launches[0]
    assert launch["model"] == "claude-opus-5[1m]"
    assert launch["effort"] == "high"
    primary = json.loads(
        (ap / "loop-metrics.jsonl").read_text().strip().splitlines()[0],
    )
    ledger = json.loads(
        (ap / "ledger" / "loop-metrics.jsonl").read_text().strip().splitlines()[0],
    )
    assert primary["effort"] == "high"
    assert ledger["effort"] == "high"


def test_run_once_launches_a_cycle_two_review_at_high_effort_and_persists_it(tmp_path):
    lp = make_loop(tmp_path, [noop_step])
    ap = lp._test["ap_dir"]
    write_state(ap, prd="p.md", next_phase="review", cycle=2, batch={"id": "b"})
    lp.run_once()
    launch = lp._test["spawn"].launches[0]
    assert launch["model"] == "claude-opus-5[1m]"
    assert launch["effort"] == "high"
    primary = json.loads(
        (ap / "loop-metrics.jsonl").read_text().strip().splitlines()[0],
    )
    ledger = json.loads(
        (ap / "ledger" / "loop-metrics.jsonl").read_text().strip().splitlines()[0],
    )
    assert primary["effort"] == "high"
    assert ledger["effort"] == "high"


def test_done_branch_routes_sonnet_medium(tmp_path):
    lp = make_loop(tmp_path, [terminal_step()])
    write_state(lp._test["ap_dir"], prd="p.md", next_phase="done", batch={"id": "b"})
    assert lp.run() == 0
    launch = lp._test["spawn"].launches[0]
    assert launch["model"] == "claude-sonnet-5[1m]"
    assert launch["effort"] == "medium"


def test_continue_relaunches_until_drain(tmp_path):
    def review_step(ap_dir: Path) -> None:
        (ap_dir / "state.json").write_text(
            json.dumps({"prd": "p.md", "next_phase": "review", "batch": {"id": "b"}}),
        )
        write_log(ap_dir, {"type": "result"})

    lp = make_loop(tmp_path, [review_step, terminal_step()])
    write_state(lp._test["ap_dir"], prd="p.md", next_phase="build", batch={"id": "b"})
    assert lp.run() == 0
    assert len(lp._test["spawn"].launches) == 2
    assert "Continuing (next phase: review)" in lp._test["out"].getvalue()


def test_metrics_line_lands_in_primary_and_ledger_mirror(tmp_path):
    lp = make_loop(tmp_path, [terminal_step(batch="mb-1")])
    write_state(
        lp._test["ap_dir"],
        prd="00001-m-v1.md",
        next_phase="build",
        batch={"id": "mb-1"},
    )
    assert lp.run() == 0
    ap = lp._test["ap_dir"]
    primary = (ap / "loop-metrics.jsonl").read_text().strip().splitlines()
    mirror = (ap / "ledger" / "loop-metrics.jsonl").read_text().strip().splitlines()
    assert primary == mirror
    assert len(primary) == 1
    row = json.loads(primary[0])
    assert row["signal"] == "done"
    assert row["phase_launched"] == "build"
    assert row["phase_end"] == ""
    assert row["model"] == "claude-sonnet-5[1m]"
    assert row["cost_usd"] == 0.01
    assert row["tokens_out"] == 10
    assert row["wall_secs"] == row["ts_end"] - row["ts_start"]


def test_one_metrics_line_per_session(tmp_path):
    def review_step(ap_dir: Path) -> None:
        (ap_dir / "state.json").write_text(
            json.dumps({"prd": "p.md", "next_phase": "review", "batch": {"id": "b"}}),
        )
        write_log(ap_dir, {"type": "result"})

    lp = make_loop(tmp_path, [review_step, terminal_step()])
    write_state(lp._test["ap_dir"], prd="p.md", next_phase="build", batch={"id": "b"})
    assert lp.run() == 0
    rows = (lp._test["ap_dir"] / "loop-metrics.jsonl").read_text().strip().splitlines()
    assert [json.loads(row)["signal"] for row in rows] == ["continue", "done"]


def test_paused_row_carries_the_stand_down_reason_and_condition(tmp_path):
    # PRD 00199: a stand-down's paused row records the marker's reason and
    # its condition, so a false stand-down is visible in the ledger.
    def stand_down(ap_dir: Path) -> None:
        (ap_dir / "pause-requested").write_text(
            json.dumps(
                {"reason": "peer repo-x-7 owns 00010-x-v1.md", "condition": "dirty_tree"},
            ),
        )

    lp = make_loop(tmp_path, [stand_down])
    ap = lp._test["ap_dir"]
    write_state(ap, prd="00010-x-v1.md", next_phase="build", batch={"id": "b"})
    assert lp.run() == 0
    rows = metrics_rows(ap)
    assert len(rows) == 1
    assert rows[0]["signal"] == "paused"
    assert rows[0]["stood_down"] == "peer repo-x-7 owns 00010-x-v1.md"
    assert rows[0]["stood_down_condition"] == "dirty_tree"


def test_a_conditionless_stand_down_row_reads_unknown_and_other_rows_carry_neither(
    tmp_path,
):
    def stand_down(ap_dir: Path) -> None:
        (ap_dir / "pause-requested").write_text(json.dumps({"reason": "peer owns it"}))

    lp = make_loop(tmp_path, [stand_down])
    ap = lp._test["ap_dir"]
    write_state(ap, prd="00010-x-v1.md", next_phase="build", batch={"id": "b"})
    assert lp.run() == 0
    row = metrics_rows(ap)[0]
    assert row["stood_down_condition"] == "unknown"

    lp2 = make_loop(tmp_path / "other", [terminal_step()])
    write_state(lp2._test["ap_dir"], prd="p.md", next_phase="build", batch={"id": "b"})
    assert lp2.run() == 0
    done_row = metrics_rows(lp2._test["ap_dir"])[0]
    assert "stood_down" not in done_row
    assert "stood_down_condition" not in done_row


def _state_step(**state):
    """A session that writes ``state`` and a bare result log."""

    def step(ap_dir: Path) -> None:
        (ap_dir / "state.json").write_text(json.dumps(state))
        write_log(ap_dir, {"type": "result"})

    return step


def _write_review(
    ap: Path,
    name: str,
    reviewers: str,
    verdict: str,
    *rows: str,
) -> None:
    """The review file the convergence row reads: frontmatter, one reviewer
    section with a findings table of ``rows``, and the verdict line."""
    reviews = ap.parent / "reviews"
    reviews.mkdir(parents=True)
    (reviews / name).write_text(
        f"---\nreviewers: {reviewers}\n---\n\n## Alice\n\n"
        "| # | Severity | Issue |\n|---|----------|-------|\n"
        + "".join(f"{row}\n" for row in rows)
        + f"\nVerdict: {verdict}\n",
    )


def test_review_exit_to_done_writes_the_convergence_row(tmp_path):
    converging_review = _state_step(
        prd="00188-x-v1.md",
        next_phase="done",
        batch={"id": "b"},
        cycle=2,
        rework_cap=2,
        tasks_total=3,
        tasks_completed=3,
        deferred_decisions=[
            {"type": "cap-overflow", "issue": "x", "severity": "high"},
        ],
    )
    lp = make_loop(tmp_path, [converging_review, terminal_step()])
    ap = lp._test["ap_dir"]
    _write_review(
        ap,
        "00188-x-v1-review-2.md",
        "alice,blake,bob",
        "3 findings",
        "| [2/3] | 🟠 High | the gate lies |",
        "| [2/3] | 🟠 High | the mirror drifts |",
        "| [1/3] | 🟡 Medium | typo |",
    )
    write_state(ap, prd="00188-x-v1.md", next_phase="review", batch={"id": "b"})
    assert lp.run() == 0
    rows = metrics_rows(ap)
    assert len(rows) == 3
    assert "event" not in rows[0] and rows[0]["phase_launched"] == "review"
    assert "event" not in rows[2] and rows[2]["phase_launched"] == "done"
    event = rows[1]
    assert event["event"] == "review_converged"
    assert event["prd"] == "00188-x-v1.md"
    assert event["batch"] == "b"
    assert event["outcome"] == "cap_deferred"
    assert event["rework_cap"] == 2
    assert event["cycles_to_converge"] == 2
    assert event["ts"] == rows[0]["ts_end"]
    assert event["tasks_planned"] == 3
    assert event["tasks_completed"] == 3
    assert event["build_models"] == []  # the review's own row never counts
    assert [c["cycle"] for c in event["cycles"]] == [1, 2]
    assert event["cycles"][0]["reviewers"] is None  # cycle 1 has no file
    assert event["cycles"][0]["verdict"] is None
    assert event["cycles"][0]["findings"] is None
    assert event["cycles"][1]["reviewers"] == ["alice", "blake", "bob"]
    assert event["cycles"][1]["verdict"] == 3
    assert event["cycles"][1]["findings"]["high"] == 2
    assert event["cycles"][1]["findings"]["medium"] == 1


@pytest.mark.parametrize(
    "identity",
    [
        {"prd": "00188-x-v1.md"},
        {"prd": "00188-x-v1.md", "batch": {}},
        {"batch": {"id": "b"}},
    ],
    ids=["no-batch", "no-batch-id", "no-prd"],
)
def test_review_exit_to_done_without_batch_writes_the_session_row_and_no_event(
    tmp_path,
    monkeypatch,
    identity,
):
    # The schema leaves batch, batch.id and prd optional: a row that cannot
    # name its PRD or batch is skipped BEFORE the builder runs - a decision,
    # never a KeyError swallowed on the way out. The states carry every run
    # field a converging review does, so only the missing identity key sets
    # them apart.
    def spy(*args, **kwargs):
        raise AssertionError("build_row must not run for an unidentifiable state")

    monkeypatch.setattr(convergence, "build_row", spy)
    review_state = {
        "next_phase": "done",
        "cycle": 1,
        "rework_cap": 2,
        "tasks_total": 3,
        "tasks_completed": 3,
        "tasks": [],
        "deferred_decisions": [],
        **identity,
    }
    lp = make_loop(tmp_path, [_state_step(**review_state), terminal_step()])
    ap = lp._test["ap_dir"]
    write_state(ap, prd="00188-x-v1.md", next_phase="review", batch={"id": "b"})
    assert lp.run() == 0
    rows = metrics_rows(ap)
    assert [row.get("phase_launched") for row in rows] == ["review", "done"]
    assert all("event" not in row for row in rows)


@pytest.mark.parametrize(
    ("deferred", "outcome"),
    [
        (
            [
                "cap-overflow",
                {"type": "cap-overflow", "issue": "x", "severity": "high"},
            ],
            "cap_deferred",
        ),
        (["cap-overflow", {"type": "question", "issue": "x"}], "converged"),
    ],
    ids=["cap-overflow-dict", "question-dict"],
)
def test_review_exit_to_done_with_a_non_dict_deferral_still_writes_the_event(
    tmp_path,
    deferred,
    outcome,
):
    # A stray string BEFORE the dict, spelling the marker itself: the event
    # still lands and its outcome follows the dict alone. The state carries
    # only the five keys the row needs - fewer than the skipped states
    # above, so a key count cannot tell the two apart.
    converging_review = _state_step(
        prd="00188-x-v1.md",
        next_phase="done",
        batch={"id": "b"},
        cycle=1,
        deferred_decisions=deferred,
    )
    lp = make_loop(tmp_path, [converging_review, terminal_step()])
    ap = lp._test["ap_dir"]
    write_state(ap, prd="00188-x-v1.md", next_phase="review", batch={"id": "b"})
    assert lp.run() == 0
    rows = metrics_rows(ap)
    assert [row.get("phase_launched") for row in rows] == ["review", None, "done"]
    assert [("event" in row) for row in rows] == [False, True, False]
    assert rows[1]["event"] == "review_converged"
    assert rows[1]["prd"] == "00188-x-v1.md"
    assert rows[1]["outcome"] == outcome


def test_convergence_row_fields_come_from_state_and_review_files(tmp_path):
    # A different state, review file and a preceding build session: every
    # payload field must move with its source, so a constant row fails.
    build = _state_step(prd="00190-y-v1.md", next_phase="review", batch={"id": "b2"})
    converging_review = _state_step(
        prd="00190-y-v1.md",
        next_phase="done",
        batch={"id": "b2"},
        cycle=1,
        rework_cap=3,
        tasks_total=5,
        tasks_completed=4,
    )
    lp = make_loop(tmp_path, [build, converging_review, terminal_step()])
    ap = lp._test["ap_dir"]
    _write_review(
        ap,
        "00190-y-v1-review-1.md",
        "carl,eve",
        "converged",
        "| [1/2] | ⚪ Low | nit |",
        "| [2/2] | 🔴 Critical | the row lies |",
    )
    write_state(ap, prd="00190-y-v1.md", next_phase="build", batch={"id": "b2"})
    assert lp.run() == 0
    rows = metrics_rows(ap)
    phases = [row.get("phase_launched") for row in rows]
    assert phases == ["build", "review", None, "done"]
    event = rows[2]
    assert event["event"] == "review_converged"
    assert event["prd"] == "00190-y-v1.md"
    assert event["batch"] == "b2"
    assert event["outcome"] == "converged"
    assert event["rework_cap"] == 3
    assert event["cycles_to_converge"] == 1
    assert event["ts"] == rows[1]["ts_end"]
    assert event["tasks_planned"] == 5
    assert event["tasks_completed"] == 4
    assert event["build_models"] == ["claude-sonnet-5[1m]"]
    assert len(event["cycles"]) == 1
    assert event["cycles"][0]["cycle"] == 1
    assert event["cycles"][0]["reviewers"] == ["carl", "eve"]
    assert event["cycles"][0]["verdict"] == "converged"
    assert event["cycles"][0]["findings"] == {
        "critical": 1,
        "high": 0,
        "medium": 0,
        "low": 1,
    }


def test_review_exit_to_review_writes_no_convergence_row(tmp_path):
    rework_review = _state_step(
        prd="00188-x-v1.md", next_phase="review", cycle=2, batch={"id": "b"}
    )
    lp = make_loop(tmp_path, [rework_review, terminal_step()])
    ap = lp._test["ap_dir"]
    write_state(
        ap,
        prd="00188-x-v1.md",
        next_phase="review",
        cycle=1,
        batch={"id": "b"},
    )
    assert lp.run() == 0
    rows = metrics_rows(ap)
    assert [row["phase_launched"] for row in rows] == ["review", "review"]
    assert all("event" not in row for row in rows)


def test_build_exit_writes_no_convergence_row(tmp_path):
    finishing_build = _state_step(
        prd="00188-x-v1.md", next_phase="done", batch={"id": "b"}
    )
    lp = make_loop(tmp_path, [finishing_build, terminal_step()])
    ap = lp._test["ap_dir"]
    write_state(ap, prd="00188-x-v1.md", next_phase="build", batch={"id": "b"})
    assert lp.run() == 0
    rows = metrics_rows(ap)
    assert [row["phase_launched"] for row in rows] == ["build", "done"]
    assert all("event" not in row for row in rows)


def test_review_exit_to_paused_writes_no_convergence_row(tmp_path):
    pausing_review = _state_step(
        prd="00188-x-v1.md",
        phase="paused",
        next_phase="paused",
        pause_reason={"detail": "design gate needs the operator"},
        batch={"id": "b"},
        cycle=1,
    )
    lp = make_loop(tmp_path, [pausing_review])
    ap = lp._test["ap_dir"]
    write_state(ap, prd="00188-x-v1.md", next_phase="review", batch={"id": "b"})
    assert lp.run() == 1
    rows = metrics_rows(ap)
    assert [row.get("phase_launched") for row in rows] == ["review"]
    assert all("event" not in row for row in rows)


# ── registry ─────────────────────────────────────────────────────────────────


def test_cleanup_orphans_hups_a_tagged_ppid1_process(tmp_path):
    tag = "424242"
    # bash backgrounds python and exits, so the child reparents to
    # launchd (PPID 1) carrying the loop tag in its env - exactly the
    # stray the sweep exists to reap.
    # The child's fds must not inherit bash's stdout pipe, or
    # capture_output blocks until the ORPHAN exits, not bash.
    result = subprocess.run(
        [
            "bash",
            "-c",
            f'{sys.executable} -c "import time; time.sleep(60)" '
            ">/dev/null 2>&1 & echo $!",
        ],
        env={**os.environ, "_AUTOPILOT_LOOP": tag},
        capture_output=True,
        text=True,
    )
    orphan_pid = int(result.stdout.strip())
    lp = make_loop(tmp_path, [], env={"_AUTOPILOT_LOOP": tag})
    assert lp.loop_pid == int(tag)
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            _REAL_CLEANUP_ORPHANS(lp)
            try:
                os.kill(orphan_pid, 0)
            except ProcessLookupError:
                return  # HUP delivered; the orphan is gone
            time.sleep(0.1)
        raise AssertionError("tagged orphan survived the cleanup sweep")
    finally:
        try:
            os.kill(orphan_pid, 9)
        except (ProcessLookupError, PermissionError):
            pass


def test_loop_drives_the_real_runner_spawn_end_to_end(tmp_path):
    # The scripted spawns mirror runner.spawn's signature; this test binds
    # Loop to the REAL runner.spawn with a stub claude binary, so a
    # signature drift between the two fails here, not in a live batch.
    stub = tmp_path / "stub-claude"
    ap_rel = "repo/dev/local/autopilot"
    stub.write_text(
        f"#!{sys.executable}\n"
        "import json, pathlib, sys\n"
        f"ap = pathlib.Path({str(tmp_path)!r}) / {ap_rel!r}\n"
        "(ap / 'state.json').write_text(json.dumps("
        "{'prd': 'p.md', 'next_phase': '', 'batch': {'id': 'real-1'}}))\n"
        "print(json.dumps({'type': 'result', 'total_cost_usd': 0.02,"
        " 'usage': {'output_tokens': 7}}))\n",
    )
    stub.chmod(stub.stat().st_mode | stat.S_IXUSR)

    repo = tmp_path / "repo"
    ap_dir = repo / "dev" / "local" / "autopilot"
    ap_dir.mkdir(parents=True)
    notify = Recorder()
    out, err = io.StringIO(), io.StringIO()
    lp = Loop(
        cwd=repo,
        env={
            "PATH": os.environ["PATH"],
            "_AUTOPILOT_LOOPS_DIR": str(tmp_path / "loops"),
            "_AUTOPILOT_TRACON_CHILD": "1",  # discard presenter: no render child
        },
        notify_fn=notify,
        pressure_fn=lambda: 1,
        out=out,
        err=err,
        runner_bin=str(stub),
    )
    lp._cleanup_orphans = lambda: None  # keep the real-spawn test hermetic too
    assert lp.run() == 0
    assert "Backlog drained." in out.getvalue()
    row = json.loads(
        (ap_dir / "loop-metrics.jsonl").read_text().strip().splitlines()[0],
    )
    assert row["signal"] == "done"
    assert row["cost_usd"] == 0.02
    assert (ap_dir / "last-session.log").read_bytes().startswith(b'{"type": "result"')


def test_interrupt_tears_down_and_returns_130(tmp_path):
    # Ctrl-C reaches the loop as KeyboardInterrupt (the group signal):
    # teardown must remove the registry entry, terminate a mid-flight
    # child, and return the bash-parity code.
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])

    def interrupting_spawn(
        model,
        effort,
        *,
        cap_secs,
        autopilot_dir,
        env,
        runner_bin,
        proc_slot=None,
        **kwargs,
    ):
        if proc_slot is not None:
            proc_slot[0] = child
        raise KeyboardInterrupt

    lp = make_loop(tmp_path, [], spawn_fn=interrupting_spawn)
    try:
        assert lp.run() == 130
        assert list((tmp_path / "loops").glob("*.json")) == []
        child.wait(timeout=10)
        assert child.returncode != 0  # terminated, not exited
    finally:
        child.kill()
        child.wait()


def test_sigterm_translates_to_143(tmp_path):
    def terminating_spawn(
        model,
        effort,
        *,
        cap_secs,
        autopilot_dir,
        env,
        runner_bin,
        proc_slot=None,
        **kwargs,
    ):
        raise loop_mod._Terminated(143)

    lp = make_loop(tmp_path, [], spawn_fn=terminating_spawn)
    assert lp.run() == 143
    assert list((tmp_path / "loops").glob("*.json")) == []


def test_loop_verb_is_registered_in_the_cli():
    import importlib.util

    main_path = Path(__file__).resolve().parent / "__main__.py"
    spec = importlib.util.spec_from_file_location(
        "autopilot_main_under_test",
        main_path,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert "loop" in module._SUBCOMMANDS
    args = module._build_parser().parse_args(["loop"])
    assert args.command == "loop"
