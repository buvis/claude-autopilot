"""cli/loop_gates.py - the loop registry and the preflight gates of the loop
driver, moved from `loop.py` by PRD 00192.

Allowed imports: stdlib, `cli.state`, `cli.routing`, `cli.loop_decision`;
never `cli.loop` or `cli.loop_act`.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

from cli import state as state_mod
from cli.loop_decision import _utcnow_iso, plugin_drift
from cli.routing import _load_json

DEFAULT_LOOPS_DIR = Path.home() / ".claude" / "autopilot-loops"


# ── registry (loop singleton per repo) ───────────────────────────────────────


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True  # EPERM etc.: it exists, we just can't signal it
    return True


def _child_pids(pid: int) -> list[str]:
    try:
        out = subprocess.run(
            ["pgrep", "-P", str(pid)],
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    return [token for token in out.split() if token.isdigit()]


def _pid_tagged(pid: int, tag_pid: int) -> bool:
    """The recycled-pid guard: a live pid counts as a loop only when its
    ps env - or a direct child's - carries its own _AUTOPILOT_LOOP=<pid>
    tag. Children count because ps reports the EXEC-time environment: the
    tracon front-end forks the loop shell (whose pid the registry stores,
    since killpg needs the group leader) and exports the tag only after
    that fork, so the tag shows up on the exec'd driver beneath it and
    never on the shell itself. Checking the shell alone swept live loops
    out of the registry, blinding tracon to them."""
    pids = [str(pid), *_child_pids(pid)]
    try:
        out = subprocess.run(
            ["ps", "ewww", "-p", ",".join(pids), "-o", "command="],
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    return re.search(rf"_AUTOPILOT_LOOP={tag_pid}( |$)", out, re.MULTILINE) is not None


def prune_registry(loops_dir: Path, own_pid: int) -> None:
    """Sweep stale entries: dead pid, alive-but-untagged (recycled), or
    malformed - none can denote a live loop. Never touches the CURRENT
    process's own entry. An unreadable entry (OSError, e.g. permission
    denied) means "couldn't check this", not "this is garbage" - it is
    left alone rather than swept."""
    try:
        entries = list(loops_dir.glob("*.json"))
    except OSError:
        return
    for path in entries:
        try:
            raw = path.read_bytes()
        except OSError:
            continue  # unreadable (permission/ownership) - leave alone, not corrupt
        try:
            data = json.loads(raw.decode("utf-8"))
        except ValueError:
            data = None  # unparseable/undecodable - garbage, not unreadable
        pid = data.get("pid") if isinstance(data, dict) else None
        if pid == own_pid:
            continue
        if (
            not isinstance(pid, int)
            or isinstance(pid, bool)
            or not _pid_alive(pid)
            or not _pid_tagged(pid, pid)
        ):
            try:
                path.unlink()
            except OSError:
                pass


def live_wrapper_pid(root: Path, loops_dir: Path) -> int | None:
    """The incumbent loop's pid for this repo root, else None. Same
    contract as tracon.discovery.live_wrapper_pid, applied to an
    explicit loops dir. A pid that is alive but never carries its own
    _AUTOPILOT_LOOP tag (per _pid_tagged) is a recycled/borrowed pid,
    not an incumbent. An unreadable entry (OSError) means "couldn't
    check this" - it is skipped (unresolvable until readable again),
    never deleted."""
    resolved = root.resolve()
    try:
        entries = list(loops_dir.glob("*.json"))
    except OSError:
        return None
    for path in entries:
        data = _load_json(path)
        if not isinstance(data, dict):
            continue
        pid, reg_root = data.get("pid"), data.get("root")
        if (
            not isinstance(pid, int)
            or isinstance(pid, bool)
            or not isinstance(reg_root, str)
        ):
            continue
        try:
            if (
                Path(reg_root).resolve() == resolved
                and _pid_alive(pid)
                and _pid_tagged(pid, pid)
            ):
                return pid
        except OSError:
            continue
    return None


class GatesMixin:
    """Loop's preflight gates: _memory_gate, _register, _write_registry_entry,
    _plugin_gate, _schema_gate. Reads self._int, self._pressure, self._clock,
    self._sleep, self._notify, self._repo_name, self.env, self.err,
    self.loop_pid, self._reg, self._warned_schema. Imports nothing from
    cli.loop."""

    # ── preflights ──
    def _memory_gate(self) -> int | None:
        """None to proceed; an exit code to stop the loop."""
        level = self._pressure()
        if level is None or level < 2:
            return None
        print(
            f"\nautoclaude: memory pressure (level {level}); waiting for it to clear before launching next session.",
            file=self.err,
        )
        self._notify(
            f"autopilot ⏳ {self._repo_name()}",
            f"Waiting: memory pressure (level {level}).",
        )
        max_wait = self._int("_AUTOPILOT_MEM_WAIT_MAX", 3600)
        poll = self._int("_AUTOPILOT_MEM_POLL_SECS", 60)
        deadline = self._clock() + max_wait
        while self._clock() < deadline:
            self._sleep(poll)
            level = self._pressure()
            if level is None or level < 2:
                break
        if level is not None and level >= 2:
            print(
                f"\nautoclaude: memory pressure still elevated (level {level}) "
                f"after {max_wait}s; stopping loop. Free RAM, then re-run.",
                file=self.err,
            )
            self._notify(
                f"autopilot ⚠️ {self._repo_name()}",
                f"Stopped: memory pressure (level {level}) did not clear "
                f"within {max_wait}s. Free RAM, then re-run autoclaude.",
            )
            return 1
        print(
            f"\nautoclaude: memory pressure cleared (level {level}); resuming.",
            file=self.err,
        )
        return None

    def _register(self, ap_dir: Path) -> int | None:
        """Registry + duplicate-loop guard, once per loop. None to
        proceed; an exit code to refuse."""
        if self._reg is not None:
            return None
        loops_dir = Path(self.env.get("_AUTOPILOT_LOOPS_DIR") or DEFAULT_LOOPS_DIR)
        self.env["_AUTOPILOT_LOOPS_DIR"] = str(loops_dir)
        try:
            loops_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        prune_registry(loops_dir, self.loop_pid)
        root_str = str(ap_dir)
        suffix = "/dev/local/autopilot"
        root = Path(root_str[: -len(suffix)]) if root_str.endswith(suffix) else ap_dir
        incumbent = live_wrapper_pid(root, loops_dir)
        # An incumbent carrying OUR OWN pid is this shell's earlier loop
        # that died without teardown (SIGKILL of the python driver leaves
        # the entry naming the still-alive shell). The bash loop could
        # never reach this state - killing the loop killed the shell - so
        # prune's own-pid skip was enough there; here the stale self-entry
        # must be overwritten, never treated as a live duplicate.
        if incumbent is not None and incumbent != self.loop_pid:
            print(
                f"autoclaude: a loop is already running for {root} "
                f"(pid {incumbent}). Refusing to start a second loop on the "
                "same repo.",
                file=self.err,
            )
            return 1
        self._write_registry_entry(loops_dir, root, ap_dir)
        return None

    def _write_registry_entry(self, loops_dir: Path, root: Path, ap_dir: Path) -> None:
        """Atomic write of this loop's registry entry; a failed write runs
        unregistered, loud."""
        reg = loops_dir / f"{self.loop_pid}.json"
        entry = {
            "pid": self.loop_pid,
            "root": str(root),
            "ap_dir": str(ap_dir),
            "started_at": _utcnow_iso(),
        }
        tmp = loops_dir / f"{reg.name}.tmp.{self.loop_pid}"
        try:
            tmp.write_text(json.dumps(entry))
            tmp.replace(reg)
            self._reg = reg
        except OSError:
            try:
                tmp.unlink()
            except OSError:
                pass
            print(
                "autoclaude: registry write failed; running unregistered.",
                file=self.err,
            )

    def _oldest_live_loop_pid(self) -> int | None:
        """The pid of the live loop with the earliest `started_at` across the
        whole registry, any repo (PRD 00199: the five-hour window is per
        account, so every loop on it competes). None when the registry is
        unreadable or holds no live entry. An entry that is unreadable,
        malformed or missing `started_at` is named once on stderr and treated
        as absent - it can never make this loop yield."""
        loops_dir = Path(self.env.get("_AUTOPILOT_LOOPS_DIR") or DEFAULT_LOOPS_DIR)
        try:
            entries = sorted(loops_dir.glob("*.json"))
        except OSError:
            return None
        oldest: tuple[str, int] | None = None
        for path in entries:
            data = _load_json(path)
            pid = data.get("pid") if isinstance(data, dict) else None
            started = data.get("started_at") if isinstance(data, dict) else None
            if (
                not isinstance(pid, int)
                or isinstance(pid, bool)
                or not isinstance(started, str)
                or not started
            ):
                print(
                    f"autoclaude: loop registry entry {path.name} is unreadable or "
                    "has no started_at; ignored for the window yield.",
                    file=self.err,
                )
                continue
            if pid != self.loop_pid and not _pid_alive(pid):
                continue
            if oldest is None or started < oldest[0]:
                oldest = (started, pid)
        return None if oldest is None else oldest[1]

    def _plugin_gate(self, ap_dir: Path) -> int | None:
        state_path = ap_dir / "state.json"
        plugins_json = Path(
            self.env.get("_AUTOPILOT_PLUGINS_JSON")
            or Path.home() / ".claude" / "plugins" / "installed_plugins.json",
        )
        if not state_path.is_file() or not plugins_json.is_file():
            return None
        state = _load_json(state_path)
        installed = _load_json(plugins_json)
        if not isinstance(state, dict) or not isinstance(installed, dict):
            return None
        drift = plugin_drift(state, installed)
        if drift is None:
            return None
        print(
            f"\nautoclaude: plugin version drift ({drift}) — enforcement code "
            "rotated mid-batch. Stopping so the batch never runs on unpinned "
            "enforcement code. Re-pin state.batch.plugin_versions or "
            "investigate, then relaunch.",
            file=self.err,
        )
        self._notify(
            f"autopilot ⚠️ {self._repo_name()}",
            f"Plugin drift ({drift}); halted.",
        )
        return 1

    def _schema_gate(self, ap_dir: Path) -> int | None:
        """PRD 00106 acceptance: a resumed batch whose state schema this
        CLI does not understand is detected before any spawn. future →
        refuse loud; old/unstamped → warn once and continue."""
        try:
            loaded, status = state_mod.load(ap_dir / "state.json")
        except state_mod.StateError:
            return None
        if status == "future":
            version = loaded.get("schema_version")
            print(
                f"autoclaude: state.json carries schema v{version}, newer than "
                "this CLI understands; refusing to drive it. Update the CLI or "
                "restore the matching state.",
                file=self.err,
            )
            self._notify(
                f"autopilot ⚠️ {self._repo_name()}",
                f"Future-schema state.json (v{version}); halted.",
            )
            return 1
        if status in ("old", "unstamped") and not self._warned_schema:
            self._warned_schema = True
            print(
                f"autoclaude: state.json schema status '{status}' — a "
                "pre-cutover batch; the state CLI upgrades it on its next "
                "transaction.",
                file=self.err,
            )
        return None
