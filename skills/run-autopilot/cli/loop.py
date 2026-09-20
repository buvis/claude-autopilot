"""cli/loop.py - the autopilot loop driver (PRD 00106).

Replaces the bash `autoclaude()` loop body: read state through the
00051 core, decide over the PRD-00014 decision table, spawn the routed
phase runner, act on the branch. One session = one `claude -p` turn =
one process that exits at turn end; the decision is made from
state.json after exit, never from the session's words.

Signals, in decision order (one per session):
    state_write_failed  the 00051 marker survives past state.json and
                        wins over an otherwise-continue state
    paused              a human is needed (pause_reason / review cap), or
                        the session stood down for a peer that owns its
                        PRD (pause marker written mid-session, PRD 00172)
    continue            next phase queued (also: replan, limit wait,
                        network restored, died-retry)
    done                backlog drained (next_phase empty)
    died                no progress and no scheduling explanation
    park                died past the retry budget, or the
                        no-progress fingerprint bound fired

state_touched guards the no-progress branch: a healthy session ALWAYS
writes state at its hand-off, so an untouched state.json means this
session made no progress (limit-hit at start, crash, cap-kill) -
without the mtime check a mid-batch limit hit would relaunch into the
same banner in a tight loop.

Everything the wrapper accreted rides along: memory circuit-breaker
(2026-06-25 RAM lockout), loop registry + duplicate guard, plugin-pin
preflight (PRD 00086 R3), usage-limit wait (bounded), network-outage
poll (bounded, retry-capped), died-retry + park marker with its
unconsumed-marker bounds (PRD 00066), progress-fingerprint bound
(2026-07-14), per-session metrics with the GC-exempt ledger mirror,
and the drained-path purge + agoge QA run (PRD 00102).
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import re
import signal as signal_mod
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from cli import convergence, notify_out, pause, render_metrics, routing, runner, usage_limit
from cli.loop_act import PURGE_SCRIPT, ActMixin, run_agoge, run_purge
from cli.loop_decision import DecisionMixin, died_next, fingerprint, last_result_field, pause_detail, plugin_drift
from cli.loop_gates import DEFAULT_LOOPS_DIR, GatesMixin, live_wrapper_pid, prune_registry
from cli.routing import _load_json

_SKILL_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS_DIR = _SKILL_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
import _walk_up

# compat re-exports: the names loop.py defined before PRD 00192 split it
__all__ = [
    "DEFAULT_LOOPS_DIR",
    "Loop",
    "PURGE_SCRIPT",
    "died_next",
    "fingerprint",
    "last_result_field",
    "live_wrapper_pid",
    "main",
    "pause_detail",
    "plugin_drift",
    "prune_registry",
    "run_agoge",
    "run_purge",
]

_API_PROBE_URL = "https://api.anthropic.com"


class _Terminated(Exception):
    def __init__(self, code: int) -> None:
        self.code = code


# ── the driver ───────────────────────────────────────────────────────────────


def _read_memory_pressure() -> int | None:
    """macOS memorystatus level: 1 normal, 2 warning, 4 critical.
    None where the sysctl does not exist."""
    try:
        out = subprocess.run(
            ["sysctl", "-n", "kern.memorystatus_vm_pressure_level"],
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip()
        return int(out) if out else None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def _probe_api() -> bool:
    try:
        urllib.request.urlopen(_API_PROBE_URL, timeout=5)
        return True
    except urllib.error.HTTPError:
        return True  # an HTTP status IS connectivity (curl -s exits 0 too)
    except (OSError, ValueError):
        return False


def _decision_fields(decision: dict) -> dict:
    """The PRD 00199 fields of a session row. A stand-down's paused row
    names why the session stood down and on what evidence, so a false
    stand-down (a reader mistaken for a writer) is visible in the ledger,
    not only in the notification. A continue row that sleeps first (a
    rejected wait or a window yield) carries `limit_wait`; a wait the
    fingerprint bound overrode into park/paused never happens, so those
    rows carry none. Empty for every other row."""
    fields: dict = {}
    if decision.get("stood_down"):
        fields["stood_down"] = decision["stood_down"]
        fields["stood_down_condition"] = decision.get("stood_down_condition", "unknown")
    if decision["signal"] == "continue" and decision.get("limit_wait") is not None:
        fields["limit_wait"] = decision["limit_wait"]
    return fields


class Loop(GatesMixin, DecisionMixin, ActMixin):
    """One `autopilot loop` invocation: drives sessions until drain,
    pause, halt, or an operator signal. Collaborators are injectable so
    the decision table and every act branch are testable without a real
    claude, notifier, network, or clock."""

    def __init__(
        self,
        cwd: Path | None = None,
        env: dict | None = None,
        *,
        spawn_fn=runner.spawn,
        notify_fn=notify_out.notify,
        sleep_fn=time.sleep,
        pressure_fn=_read_memory_pressure,
        probe_fn=_probe_api,
        detect_limit_fn=usage_limit.detect_from_log,
        clock=time.time,
        out=None,
        err=None,
        runner_bin: str = "claude",
    ) -> None:
        self.cwd = Path.cwd() if cwd is None else cwd
        self.env = dict(os.environ) if env is None else env
        self._spawn = spawn_fn
        self._notify = notify_fn
        self._sleep = sleep_fn
        self._pressure = pressure_fn
        self._probe = probe_fn
        self._detect_limit = detect_limit_fn
        self._clock = clock
        self.out = out if out is not None else sys.stdout
        self.err = err if err is not None else sys.stderr
        self.runner_bin = runner_bin

        raw_tag = self.env.get("_AUTOPILOT_LOOP", "")
        self.loop_pid = int(raw_tag) if raw_tag.isdigit() else os.getpid()
        # Children must inherit the tag (orphan cleanup and the recycled-pid
        # guard both grep for it), exactly as the bash export did.
        self.env["_AUTOPILOT_LOOP"] = str(self.loop_pid)

        self._reg: Path | None = None
        self._net_retries = 0
        self._died_retries = 0
        self._park_relaunches = 0
        self._fp_prev = ""
        self._fp_repeats = 0
        self._proc_slot: list = [None]
        self._warned_schema = False

    # ── env knobs ──
    def _int(self, key: str, default: int) -> int:
        return routing._env_int(self.env, key, default)

    # ── plumbing ──
    def _repo_name(self) -> str:
        return self.cwd.name

    def _teardown(self) -> None:
        proc = self._proc_slot[0]
        if proc is not None and proc.poll() is None:
            proc.terminate()
        self._cleanup_orphans()
        if self._reg is not None:
            try:
                self._reg.unlink()
            except OSError:
                pass

    def _cleanup_orphans(self) -> None:
        """HUP orphaned (PPID=1) processes tagged with our marker, so
        shells propagate the signal to their children. One ps over all
        candidates (the bash loop ran ps per pid; launchd parents
        hundreds of user processes, so per-pid probing is seconds of
        work per session)."""
        try:
            out = subprocess.run(
                ["pgrep", "-u", os.environ.get("USER", ""), "-P", "1"],
                capture_output=True,
                text=True,
                timeout=10,
            ).stdout
        except (OSError, subprocess.SubprocessError):
            return
        pids = [token for token in out.split() if token.isdigit()]
        if not pids:
            return
        try:
            ps_out = subprocess.run(
                ["ps", "ewww", "-p", ",".join(pids), "-o", "pid=,command="],
                capture_output=True,
                text=True,
                timeout=10,
            ).stdout
        except (OSError, subprocess.SubprocessError):
            return
        tag = re.compile(rf"_AUTOPILOT_LOOP={self.loop_pid}( |$)")
        for line in ps_out.splitlines():
            parts = line.strip().split(None, 1)
            if len(parts) == 2 and parts[0].isdigit() and tag.search(parts[1]):
                try:
                    os.kill(int(parts[0]), signal_mod.SIGHUP)
                except OSError:
                    pass

    def _resolve_ap_dir(self) -> Path:
        ap_dir = _walk_up.find_autopilot_dir(self.cwd)
        if ap_dir is None:
            # walk-up miss = no dir exists yet (normal on a fresh repo), not a failure
            print(
                f"autoclaude: no existing autopilot dir found (fresh start); creating {self.cwd}/dev/local/autopilot",
                file=self.err,
            )
            ap_dir = self.cwd / "dev" / "local" / "autopilot"
        try:
            ap_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        return ap_dir

    def _append_metrics(
        self,
        ap_dir: Path,
        ts_start: float,
        ts_end: float,
        decision: dict,
        phase_launched: str,
        model: str,
        effort: str,
    ) -> None:
        """One JSONL line per session, after the decision and before any
        exit path, plus the review_converged row when a review exits to done.
        Observation only - the append can never block or fail the loop (the
        one sanctioned silent failure, scoped to itself)."""
        try:
            line = {
                "ts_start": int(ts_start),
                "ts_end": int(ts_end),
                "wall_secs": int(ts_end) - int(ts_start),
                "prd": decision["prd"],
                "batch": decision["batch"],
                "phase_launched": phase_launched,
                "phase_end": decision["phase_end"],
                "signal": decision["signal"],
                "model": model,
                "effort": effort,
                "lane": decision.get("lane"),
                "lane_effective": decision.get("lane_effective"),
            }
            line.update(_decision_fields(decision))
            cost = last_result_field(ap_dir / "last-session.log", "total_cost_usd")
            if isinstance(cost, (int, float)) and not isinstance(cost, bool):
                line["cost_usd"] = cost
            usage = last_result_field(ap_dir / "last-session.log", "usage")
            tokens = usage.get("output_tokens") if isinstance(usage, dict) else None
            if isinstance(tokens, int) and not isinstance(tokens, bool):
                line["tokens_out"] = tokens
            encoded = json.dumps(line, separators=(",", ":"))
            with open(ap_dir / "loop-metrics.jsonl", "a", encoding="utf-8") as fh:
                fh.write(encoded + "\n")
            ledger_dir = ap_dir / "ledger"
            ledger_dir.mkdir(parents=True, exist_ok=True)
            with open(ledger_dir / "loop-metrics.jsonl", "a", encoding="utf-8") as fh:
                fh.write(encoded + "\n")
            # Session row first, so build_row sees this session's batch. A
            # lane-routed build (solo, fast-track; PRD 00205) converges from
            # `build`, so its build-to-done exit writes the row too.
            lane_routed = decision.get("lane_effective") in ("solo", "fast-track")
            if decision.get("phase_end") == "done" and (
                phase_launched == "review" or lane_routed
            ):
                self._append_convergence(ap_dir, ledger_dir, ts_end)
        except (OSError, ValueError, TypeError):
            pass

    def _append_convergence(
        self,
        ap_dir: Path,
        ledger_dir: Path,
        ts_end: float,
    ) -> None:
        """The review_converged row, appended to both metrics files; nothing
        when state.json is gone, malformed or names no prd/batch (the session
        row already written stays)."""
        state = _load_json(ap_dir / "state.json")
        if not isinstance(state, dict):
            return
        # Unidentifiable reads as unreadable: no prd or batch id, no row.
        prd = state.get("prd")
        batch = (state.get("batch") or {}).get("id")
        if not (isinstance(prd, str) and prd and isinstance(batch, str) and batch):
            return
        rows = render_metrics.load_rows(ap_dir / "loop-metrics.jsonl")
        row = convergence.build_row(ap_dir, state, rows, int(ts_end))
        event = json.dumps(row, separators=(",", ":"))
        for path in (ap_dir, ledger_dir):
            with open(path / "loop-metrics.jsonl", "a", encoding="utf-8") as fh:
                fh.write(event + "\n")

    # ── run ──
    def run(self) -> int:
        return self._guarded(self._run_loop)

    def run_once(self) -> int:
        """`autopilot review-once`: one review or finalize session for
        state.next_phase, then exit. No relaunch, no park, no
        notification, and the operator's pause marker is left alone."""
        return self._guarded(self._run_once)

    def _guarded(self, body) -> int:
        """Signal contract shared by the loop and the one-shot: SIGTERM
        and SIGHUP exit 128+signum, Ctrl-C exits 130, both after a
        teardown, and the caller's own handlers are restored on the way
        out."""

        def _on_term(signum, frame):
            raise _Terminated(128 + signum)

        old_handlers = {}
        for sig in (signal_mod.SIGTERM, signal_mod.SIGHUP):
            try:
                old_handlers[sig] = signal_mod.signal(sig, _on_term)
            except (ValueError, OSError):
                pass  # not the main thread (tests) - handlers stay default
        try:
            return body()
        except KeyboardInterrupt:
            self._teardown()
            return 130
        except _Terminated as term:
            self._teardown()
            return term.code
        finally:
            for sig, handler in old_handlers.items():
                try:
                    signal_mod.signal(sig, handler)
                except (ValueError, OSError):
                    pass

    def _launch(self, plan: routing.Route, ap_dir: Path) -> None:
        """One routed session, plus the slot reset and orphan sweep that
        always follow it. The keyword set is the contract every spawn_fn
        (runner.spawn and the tests' ScriptedSpawn) is written against."""
        self._spawn(
            plan.model,
            plan.effort,
            cap_secs=plan.cap_secs,
            autopilot_dir=ap_dir,
            env=self.env,
            runner_bin=self.runner_bin,
            proc_slot=self._proc_slot,
        )
        self._proc_slot[0] = None
        self._cleanup_orphans()

    def _one_shot_phase(self, state, state_path: Path) -> str | None:
        """The phase guard. Only `review` and `done` may be driven by a
        single session; a build needs the loop's acting branches, so
        refusing here is what keeps the operator from starting one by
        accident. None = refused, and the reason is already printed."""
        value = state.get("next_phase") or "" if isinstance(state, dict) else "missing"
        if value in ("review", "done"):
            return value
        print(
            f"autopilot review-once: next_phase is '{value}' ({state_path}); "
            "this verb runs review and finalize sessions only. Drive the "
            "build in your session, or run autoclaude.",
            file=self.err,
        )
        return None

    def _run_once(self) -> int:
        code = self._memory_gate()
        if code is not None:
            self._teardown()
            return code

        ap_dir = self._resolve_ap_dir()
        for gate in (self._register, self._plugin_gate, self._schema_gate):
            code = gate(ap_dir)
            if code is not None:
                self._teardown()
                return code

        state = _load_json(ap_dir / "state.json")
        next_phase = self._one_shot_phase(state, ap_dir / "state.json")
        if next_phase is None:
            self._teardown()
            return 1

        ts_start = self._clock()
        prd = (state.get("prd") or "") if isinstance(state, dict) else ""
        plan = routing.route(next_phase, ap_dir, env=self.env)
        self._announce_and_launch(ap_dir, next_phase, prd, plan)

        decision = self._decide(ap_dir, ts_start)
        # NOT _fingerprint_bound: it parks.
        self._append_metrics(
            ap_dir,
            ts_start,
            self._clock(),
            decision,
            next_phase,
            plan.model,
            plan.effort,
        )
        print(
            f"autopilot review-once: signal {decision['signal']} · next phase "
            f"'{decision['next']}' · {decision['detail']}",
            file=self.out,
        )
        self._teardown()
        ok = decision["state_touched"] and decision["signal"] != "state_write_failed"
        return 0 if ok else 1

    def _loop_gates(self, ap_dir: Path) -> int | None:
        """The per-iteration gates that run once the autopilot dir is
        known. An exit code halts the loop (teardown already done);
        None means this iteration launches a session."""
        code = self._register(ap_dir)
        if code is not None:
            self._teardown()
            return code

        if pause.consume_pause(ap_dir):
            return self._stop_on_marker(
                ap_dir,
                "paused by operator ON PURPOSE",
                "Paused by operator at a session boundary. State intact.",
            )

        pause.clear_paused(ap_dir)  # past the pause branch: this loop runs

        for gate in (self._plugin_gate, self._schema_gate):
            code = gate(ap_dir)
            if code is not None:
                self._teardown()
                return code
        return None

    def _announce_and_launch(
        self, ap_dir: Path, phase: str, prd: str, plan: routing.Route
    ) -> None:
        """Print the launch banner and spawn the routed session. Phase
        resolution and the banner's empty-phase fallback stay with each
        caller: `_run_once` passes an already-restricted phase,
        `_launch_phase` passes `phase_launched or 'bootstrap'`."""
        stamp = _dt.datetime.now().strftime("%H:%M:%S")
        print(
            f"\n━━ {stamp} · phase {phase} · prd {prd or 'no-prd'} · "
            f"{plan.model}/{plan.effort} ━━",
            file=self.out,
        )
        self._launch(plan, ap_dir)

    def _launch_phase(self, ap_dir: Path) -> tuple[float, str, routing.Route]:
        """Read state, route it, announce it, spawn it. Returns the
        start clock, the phase launched and the route, all three needed
        by the metrics line the caller appends."""
        ts_start = self._clock()
        state = _load_json(ap_dir / "state.json")
        phase_launched = ""
        prd_launched = ""
        if isinstance(state, dict):
            phase_launched = state.get("next_phase") or ""
            prd_launched = state.get("prd") or ""

        plan = routing.route(phase_launched, ap_dir, env=self.env)
        self._announce_and_launch(
            ap_dir, phase_launched or "bootstrap", prd_launched, plan
        )
        return ts_start, phase_launched, plan

    def _run_loop(self) -> int:
        while True:
            code = self._memory_gate()
            if code is not None:
                self._teardown()
                return code

            ap_dir = self._resolve_ap_dir()

            code = self._loop_gates(ap_dir)
            if code is not None:
                return code

            ts_start, phase_launched, plan = self._launch_phase(ap_dir)

            decision = self._decide(ap_dir, ts_start)
            self._fingerprint_bound(decision, ap_dir / "state.json")
            ts_end = self._clock()
            self._append_metrics(
                ap_dir,
                ts_start,
                ts_end,
                decision,
                phase_launched,
                plan.model,
                plan.effort,
            )

            code = self._act_branch(decision, ap_dir)
            if code is not None:
                return code


def main(argv: list[str] | None = None) -> int:
    return Loop().run()
