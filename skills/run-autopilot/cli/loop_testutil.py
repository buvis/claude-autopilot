"""Shared harness for cli/test_loop*.py. Not a test module (no test_
prefix), so nothing here is collected on its own.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from cli import loop as loop_mod
from cli.loop import Loop
from cli.runner import SpawnResult

_CLOCK_START = 1_000_000.0
_BEFORE_CLOCK = _CLOCK_START - 1000


class Recorder:
    def __init__(self) -> None:
        self.calls: list = []

    def __call__(self, *args, **kwargs) -> None:
        self.calls.append((args, kwargs))


class FakeClock:
    def __init__(self, start: float = _CLOCK_START) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def sleep(self, secs: float) -> None:
        self.now += secs


class ScriptedSpawn:
    """Each call runs the next step: a callable(ap_dir) that mutates the
    sandbox the way a real session would. A step that (re)writes
    state.json gets its mtime pinned to the fake clock so
    state_touched reads exactly as it would in real time."""

    def __init__(self, steps, clock: FakeClock) -> None:
        self.steps = list(steps)
        self.launches: list[dict] = []
        self.clock = clock

    def __call__(
        self,
        model,
        effort,
        *,
        cap_secs,
        autopilot_dir,
        env,
        runner_bin,
        proc_slot=None,
        **kwargs,
    ) -> SpawnResult:
        self.launches.append(
            {"model": model, "effort": effort, "cap_secs": cap_secs},
        )
        self.clock.now += 1  # a session takes wall time
        if not self.steps:
            raise AssertionError("spawned more sessions than the test scripted")
        step = self.steps.pop(0)
        state = autopilot_dir / "state.json"
        before = state.stat().st_mtime_ns if state.exists() else None
        step(autopilot_dir)
        after = state.stat().st_mtime_ns if state.exists() else None
        if after is not None and after != before:
            os.utime(state, (self.clock.now, self.clock.now))
        return SpawnResult(0, autopilot_dir / "last-session.log", False)


def write_state(ap_dir: Path, at: float = _BEFORE_CLOCK, **fields) -> None:
    path = ap_dir / "state.json"
    path.write_text(json.dumps(fields))
    os.utime(path, (at, at))


def write_log(ap_dir: Path, *events) -> None:
    lines = [json.dumps(event) for event in events]
    (ap_dir / "last-session.log").write_text("\n".join(lines) + "\n")


def terminal_step(prd: str = "00099-drained-v1.md", batch: str = "b-1", **extra):
    def step(ap_dir: Path) -> None:
        (ap_dir / "state.json").write_text(
            json.dumps({"prd": prd, "next_phase": "", "batch": {"id": batch, **extra}}),
        )
        write_log(
            ap_dir,
            {"type": "result", "total_cost_usd": 0.01, "usage": {"output_tokens": 10}},
        )

    return step


def noop_step(ap_dir: Path) -> None:  # session dies: touches nothing
    pass


def make_loop(tmp_path: Path, steps, env: dict | None = None, **kwargs):
    repo = tmp_path / "repo"
    ap_dir = repo / "dev" / "local" / "autopilot"
    ap_dir.mkdir(parents=True, exist_ok=True)
    clock = kwargs.pop("clock", None) or FakeClock()
    spawn = ScriptedSpawn(steps, clock=clock)
    notify = Recorder()
    sleeps: list[float] = []

    def sleep(secs: float) -> None:
        sleeps.append(secs)
        clock.sleep(secs)

    full_env = {"_AUTOPILOT_LOOPS_DIR": str(tmp_path / "loops")}
    full_env.update(env or {})
    out, err = io.StringIO(), io.StringIO()
    lp = Loop(
        cwd=repo,
        env=full_env,
        spawn_fn=kwargs.pop("spawn_fn", None) or spawn,
        notify_fn=notify,
        sleep_fn=sleep,
        pressure_fn=kwargs.pop("pressure_fn", lambda: 1),
        probe_fn=kwargs.pop("probe_fn", lambda: True),
        detect_limit_fn=kwargs.pop("detect_limit_fn", lambda path: None),
        clock=clock,
        out=out,
        err=err,
        **kwargs,
    )
    lp._test = {
        "ap_dir": ap_dir,
        "spawn": spawn,
        "notify": notify,
        "sleeps": sleeps,
        "out": out,
        "err": err,
        "clock": clock,
    }
    return lp


def _notified(lp, fragment: str) -> bool:
    return any(
        fragment in args[0] or fragment in args[1]
        for args, _ in lp._test["notify"].calls
    )


@pytest.fixture(autouse=True)
def _no_real_drain_side_effects(monkeypatch):
    """The drained branch shells to purge/agoge, and the orphan sweep
    shells to pgrep/ps on the REAL process table - keep loop runs
    hermetic and fast. Direct tests use the saved originals."""
    monkeypatch.setattr(loop_mod, "run_purge", lambda repo: None)
    monkeypatch.setattr(
        loop_mod,
        "run_agoge",
        lambda ap_dir, batch, drained, env, out, claude_bin="claude": None,
    )
    monkeypatch.setattr(Loop, "_cleanup_orphans", lambda self: None)


def _spawn_tagged_incumbent() -> subprocess.Popen:
    """A live process whose ps env carries its own _AUTOPILOT_LOOP=<pid>
    tag: exec keeps the shell's pid, so $$ IS the final pid."""
    proc = subprocess.Popen(
        [
            "bash",
            "-c",
            f"exec env _AUTOPILOT_LOOP=$$ {sys.executable} -c "
            '"import time; time.sleep(60)"',
        ],
    )
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        out = subprocess.run(
            ["ps", "ewww", "-p", str(proc.pid), "-o", "command="],
            capture_output=True,
            text=True,
        ).stdout
        if f"_AUTOPILOT_LOOP={proc.pid}" in out:
            return proc
        time.sleep(0.05)
    raise AssertionError("tagged incumbent never appeared in ps")
