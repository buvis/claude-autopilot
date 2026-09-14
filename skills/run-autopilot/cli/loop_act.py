"""cli/loop_act.py - the drained-path helpers and the act branches of the loop
driver, moved from `loop.py` by PRD 00192.

Allowed imports: stdlib, `cli.pause`, `cli.routing`, `cli.runner`,
`cli.watchdog`, `cli.loop_decision`; never `cli.loop` or `cli.loop_gates`.
"""

from __future__ import annotations

import datetime as _dt
import json
import subprocess
import sys
from pathlib import Path

from cli import pause, routing, runner
from cli.loop_decision import _mtime
from cli.routing import _load_json
from cli.watchdog import Watchdog

PURGE_SCRIPT = (
    Path.home()
    / ".claude"
    / "skills"
    / "purge-devlocal"
    / "scripts"
    / "purge_devlocal.py"
)


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


class ActMixin:
    """Loop's act branches: _stop_on_marker, _act_paused, _act_done, _act_park,
    _park_marker_pending, _halt, _act_continue, _act_branch. Reads self._int,
    self._clock, self._sleep, self._notify, self._repo_name, self._teardown,
    self.cwd, self.env, self.out, self.err, self.runner_bin,
    self._park_relaunches. Imports nothing from cli.loop."""

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
