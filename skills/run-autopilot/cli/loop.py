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

from cli import (
    convergence,
    notify_out,
    pause,
    render_metrics,
    routing,
    runner,
    usage_limit,
)
from cli.loop_decision import (
    DecisionMixin,
    _mtime,
    died_next,
    fingerprint,
    last_result_field,
    pause_detail,
    plugin_drift,
)
from cli.loop_gates import DEFAULT_LOOPS_DIR, GatesMixin, live_wrapper_pid, prune_registry
from cli.routing import _load_json
from cli.watchdog import Watchdog

_SKILL_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS_DIR = _SKILL_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
import _walk_up

PURGE_SCRIPT = (
    Path.home()
    / ".claude"
    / "skills"
    / "purge-devlocal"
    / "scripts"
    / "purge_devlocal.py"
)

_API_PROBE_URL = "https://api.anthropic.com"


class _Terminated(Exception):
    def __init__(self, code: int) -> None:
        self.code = code


# ── drained-path helpers ─────────────────────────────────────────────────────


def run_purge(repo: Path) -> None:
    """`purge_devlocal.py --repo <repo> --apply || true`."""
    try:
        subprocess.run(
            [sys.executable, str(PURGE_SCRIPT), "--repo", str(repo), "--apply"],
        )
    except (OSError, subprocess.SubprocessError):
        pass


def _run_agoge_process(
    claude_bin: str,
    prompt: str,
    log_path: Path,
    cap: int,
    env: dict,
) -> int:
    """Spawn the agoge session under a wall-clock watchdog cap and
    return its exit code (1 on spawn failure, swallowed by the caller)."""
    try:
        env_for_child, _ = runner.child_env(env)
        with open(log_path, "wb") as log:
            proc = subprocess.Popen(
                [claude_bin, "-p", "--permission-mode", "auto", prompt],
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                env=env_for_child,
            )
            dog = Watchdog(proc, cap_secs=cap, grace_secs=20).start()
            rc = proc.wait()
            dog.cancel()
            return rc
    except (OSError, subprocess.SubprocessError):
        return 1


def run_agoge(
    ap_dir: Path,
    batch: str,
    drained,
    env: dict,
    out,
    claude_bin: str = "claude",
) -> None:
    """One product-QA run over a batch that actually completed work
    (PRD 00102). Once per batch. A batch that drained nothing gets a
    skip line and no run. Failure is recorded and swallowed, and a
    wall-clock cap bounds a hung run: a QA pass must never turn a
    successful drain into a failed or unfinished one.

    --authorized arms the runtime-security lane (PRD 00117): pointing
    this loop at a repo IS the operator's authorization - it already
    grants autonomous edit-and-commit rights, strictly more than
    probing. _AUTOPILOT_AGOGE_AUTHORIZED=0 is a brake on that
    default-on assertion, not an alternative way to make it (R5)."""
    if drained in (None, "", "null", 0, "0"):
        print("agoge: skipped — the batch drained no PRDs.", file=out)
        return
    stamp = batch or _dt.datetime.now().strftime("%Y%m%d%H%M")
    log_path = ap_dir / "reports" / f"{stamp}-agoge.log"
    print(f"agoge: product QA over the drained batch (log: {log_path})…", file=out)
    prompt = f"/run-agoge {Path.cwd()}"
    if env.get("_AUTOPILOT_AGOGE_AUTHORIZED") != "0":
        prompt += " --authorized autoclaude-drain"
    cap = routing._env_int(env, "_AUTOPILOT_AGOGE_CAP", 3600)
    rc = _run_agoge_process(claude_bin, prompt, log_path, cap, env)
    if rc == 0:
        print(
            "agoge: packets written to dev/local/audit-results/; walkthrough pending.",
            file=out,
        )
    else:
        print(
            f"agoge: run failed (rc {rc}). The drain is unaffected; see {log_path}",
            file=sys.stderr,
        )


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


class Loop(GatesMixin, DecisionMixin):
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
            }
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
            # Session row first, so build_row sees this session's batch.
            if phase_launched == "review" and decision.get("phase_end") == "done":
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

    # ── act branches ──

    def _stop_on_marker(self, ap_dir: Path, headline: str, note: str) -> int:
        """The marker-pause exit, shared by the operator pause and a
        session stand-down (PRD 00172). NOT the _act_paused runbook: that
        exit leaves a paused state that re-pauses the loop, so its
        interactive step is mandatory. Here the marker is consumed and
        nothing blocks, so autoclaude alone resumes - name that first,
        and keep the take-over path for the operator who wants in."""
        pause.stamp_paused(ap_dir)
        print(
            f"\n\033[1;33m⏸ autoclaude: {headline}.\033[0m State intact.\n"
            "Resume unattended: autoclaude\n"
            "To take over first: claude → "
            "/autopilot:run-autopilot, then autoclaude",
            file=self.out,
        )
        self._notify(f"autopilot ⏸ {self._repo_name()}", note)
        self._teardown()
        return 0

    def _act_paused(self, decision: dict, state_path: Path) -> int:
        print(
            f"\n\033[1;33m⏸ autoclaude: session paused ON PURPOSE — {decision['detail']}\033[0m",
            file=self.err,
        )
        state = _load_json(state_path)
        if isinstance(state, dict):
            cap = state.get("cap_pause_reason")
            findings = cap.get("unresolved_findings") if isinstance(cap, dict) else None
            for finding in findings or []:
                if isinstance(finding, dict):
                    severity = finding.get("severity") or "?"
                    issue = (finding.get("issue") or "")[:90]
                    print(f"  · [{severity}] {issue}", file=self.err)
        print(
            "\n\n\033[1;36mTo resume (re-running autoclaude now would just pause again):\033[0m\n",
            file=self.err,
        )
        print(
            "  1. claude                    # interactive session in this repo",
            file=self.err,
        )
        print(
            "  2. /autopilot:run-autopilot  "
            "# resumes from state.json; blockers become questions",
            file=self.err,
        )
        print(
            "  3. autoclaude                # after the decision, to continue unattended",
            file=self.err,
        )
        self._notify(
            f"autopilot ⚠️ {self._repo_name()}",
            f"Paused: {decision['detail']}",
        )
        return 1

    def _act_done(self, decision: dict, ap_dir: Path) -> int:
        reports = ap_dir / "reports"
        try:
            reports.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        state_path = ap_dir / "state.json"
        state = _load_json(state_path)
        prds_done = None
        if isinstance(state, dict):
            # jq's `.batch.completed_prds | length` yields 0 for missing
            # keys, so a parsed state always counts; only an unreadable
            # one omits the count (and the agoge decision) entirely.
            completed = (state.get("batch") or {}).get("completed_prds")
            prds_done = len(completed) if isinstance(completed, list) else 0
        stamp = decision["batch"] or _dt.datetime.now().strftime("%Y%m%d%H%M")
        try:
            state_path.replace(reports / f"{stamp}-state-final.json")
        except OSError:
            pass
        suffix = f" {prds_done} PRDs completed." if prds_done is not None else ""
        print(f"\nBacklog drained.{suffix}", file=self.out)
        self._notify(
            f"autopilot ✅ {self._repo_name()}",
            f"Backlog drained.{suffix}",
        )
        run_purge(self.cwd)
        run_agoge(
            ap_dir,
            decision["batch"],
            prds_done,
            self.env,
            self.out,
            claude_bin=self.runner_bin,
        )
        return 0

    def _act_park(self, decision: dict, ap_dir: Path) -> int | None:
        """None to relaunch (marker written or preserved); an exit code
        to halt."""
        marker = ap_dir / "park-requested"
        if marker.is_file():
            return self._park_marker_pending(marker)
        self._park_relaunches = 0
        try:
            marker.write_text(
                json.dumps({"prd": decision["prd"], "reason": decision["detail"]}),
            )
            written = marker.stat().st_size > 0
        except OSError:
            written = False
        if not written:
            print(
                f"\nautoclaude: park-requested write failed for {decision['prd']} — halting (cannot hand off).",
                file=self.err,
            )
            self._notify(
                f"autopilot ⚠️ {self._repo_name()}",
                "Park marker write failed; halting.",
            )
            try:
                marker.unlink()
            except OSError:
                pass
            return 1
        print(
            f"\nautoclaude: parking {decision['prd']} ({decision['detail']}); continuing batch.",
            file=self.out,
        )
        self._notify(
            f"autopilot ⏭ {self._repo_name()}",
            f"Parking {decision['prd']}.",
        )
        return None

    def _park_marker_pending(self, marker: Path) -> int | None:
        """An unconsumed marker from the previous relaunch: halt when the
        relaunch budget or the stale age trips, else back off and relaunch."""
        self._park_relaunches += 1
        marker_mtime = _mtime(marker)
        age = (
            0 if marker_mtime is None else max(0, int(self._clock()) - marker_mtime)
        )
        stale_max = max(
            self._int("_AUTOPILOT_SESSION_MAX", 7200),
            self._int("_AUTOPILOT_SESSION_MAX_REVIEW", 10800),
        )
        if (
            self._park_relaunches > self._int("_AUTOPILOT_DIED_RETRIES_MAX", 1)
            or age >= stale_max
        ):
            print(
                f"\nautoclaude: park-requested unconsumed "
                f"({self._park_relaunches} relaunches, {age}s) — halting "
                "(systemic).",
                file=self.err,
            )
            self._notify(
                f"autopilot ⚠️ {self._repo_name()}",
                "Park marker unconsumed; halting.",
            )
            return 1
        print(
            f"\nautoclaude: park-requested pending (relaunch "
            f"{self._park_relaunches}); backing off then relaunching.",
            file=self.err,
        )
        self._sleep(self._int("_AUTOPILOT_PARK_BACKOFF", 30))
        return None

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

    def _halt(self, message: str, note: str) -> int:
        print(message, file=self.err)
        self._notify(f"autopilot ⚠️ {self._repo_name()}", note)
        self._teardown()
        return 1

    def _act_continue(self, decision: dict) -> None:
        if decision["limit_wait"] is not None:
            print(
                f"\nautoclaude: usage limit hit; waiting "
                f"{decision['limit_wait'] // 60} min "
                f"({decision['detail']}).",
                file=self.out,
            )
            self._notify(
                f"autopilot ⏳ {self._repo_name()}",
                f"Usage limit; {decision['detail']}.",
            )
            self._sleep(decision["limit_wait"])
        elif decision["detail"] == "replan":
            print(
                "\nWork task prompt overran budget; PRD will be replanned. Continuing…",
                file=self.out,
            )
        else:
            print(
                f"\nContinuing (next phase: {decision['next']})…",
                file=self.out,
            )

    def _act_branch(self, decision: dict, ap_dir: Path) -> int | None:
        """The decision signal's branch. An exit code halts the loop
        (teardown already done); None means another iteration."""
        branch = decision["signal"]
        if branch == "state_write_failed":
            return self._halt(
                "\nautoclaude: state-write-failed marker present — halting "
                f"(broken state boundary): {decision['detail']}",
                f"State write failed: {decision['detail']}",
            )
        if branch == "continue":
            self._act_continue(decision)
            return None
        if branch == "paused":
            if decision.get("stood_down"):
                pause.consume_pause(ap_dir)
                return self._stop_on_marker(
                    ap_dir,
                    decision["detail"],
                    f"Session stood down: {decision['stood_down']}. State intact.",
                )
            code = self._act_paused(decision, ap_dir / "state.json")
            self._teardown()
            return code
        if branch == "done":
            code = self._act_done(decision, ap_dir)
            self._teardown()
            return code
        if branch == "died":
            return self._halt(
                f"\nautoclaude: session died ({decision['detail']}). "
                f"Backlog NOT drained. Check {ap_dir}/state.json and "
                f"{ap_dir}/last-session.log.",
                f"Stopped: {decision['detail']}. Needs attention.",
            )
        if branch == "park":
            code = self._act_park(decision, ap_dir)
            if code is not None:
                self._teardown()
            return code
        print(
            f"\nautoclaude: unknown decision signal '{branch}'; halting.",
            file=self.err,
        )
        self._teardown()
        return 1

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
