"""cli/watchdog.py - wall-clock cap for a spawned phase session (PRD 00106).

Ports the `_autopilot_session_cap` contract from
development.plugin.bash: a session that exceeds its cap gets SIGTERM,
then SIGKILL after a grace period if TERM was ignored; a session that
exits on its own under the cap is never signaled. The bash sidecar had
to FIND the claude child via pgrep/comm exact-matching (and so carried a
bystander contract); here the spawner owns the Popen handle directly,
so only that process can ever be signaled - the bystander guarantee
holds by construction and needs no resolver.

The wrapper's cap kills the WHOLE session, and a capped session is a
died session: it takes the loop's no-progress branch. Nothing here
records anything - the loop's decision table owns that.

The warning window (2026-09-26): the cap was invisible to the session it
killed, so a two-hour opus build session died mid-task with its work
committed but its attempt record unwritten. With `warn_secs` set, the
watchdog calls `on_warn` once the child is within that window of the cap;
the runner's callback writes the `.handoff-requested` marker `/work`
reads at its task boundaries. The cap itself is unchanged.
"""

from __future__ import annotations

import subprocess
import sys
import threading
from typing import Callable


class Watchdog:
    """TERM-then-KILL cap on one child process.

    start() arms a daemon thread; the thread blocks on the child's own
    exit, so a session that finishes under the cap wakes it immediately
    and nothing is signaled. cancel() disarms a not-yet-fired cap and
    joins the thread (the post-exit `kill $_cap_pid; wait` parity).
    `fired` reports whether the cap ever signaled the child; `warned`
    whether the warning callback ran.
    """

    def __init__(
        self,
        proc: subprocess.Popen,
        cap_secs: float,
        grace_secs: float,
        warn_secs: float = 0.0,
        on_warn: Callable[[], None] | None = None,
    ) -> None:
        self._proc = proc
        self._cap = cap_secs
        self._grace = grace_secs
        self._warn = warn_secs
        self._on_warn = on_warn
        self._cancelled = threading.Event()
        self._thread = threading.Thread(target=self._watch, daemon=True)
        self.fired = False
        self.warned = False

    def start(self) -> "Watchdog":
        self._thread.start()
        return self

    def cancel(self) -> None:
        self._cancelled.set()
        # The thread is parked in proc.wait(); the child is gone by the
        # time the loop calls cancel(), so the join is immediate.
        if self._thread.is_alive():
            self._thread.join()

    def _watch(self) -> None:
        remaining = self._cap
        if self._on_warn is not None and 0 < self._warn < self._cap:
            try:
                self._proc.wait(timeout=self._cap - self._warn)
                return  # exited before the warning window: never signaled
            except subprocess.TimeoutExpired:
                pass
            if self._cancelled.is_set():
                return
            self.warned = True
            print(
                f"\nautoclaude: session is {self._warn:g}s from the {self._cap:g}s "
                "wall-clock cap; requesting a task-boundary handoff.",
                file=sys.stderr,
            )
            try:
                self._on_warn()
            except Exception as err:  # the cap must still fire
                print(f"\nautoclaude: cap warning failed: {err}", file=sys.stderr)
            remaining = self._warn
        try:
            self._proc.wait(timeout=remaining)
            return  # exited under the cap: never signaled
        except subprocess.TimeoutExpired:
            pass
        if self._cancelled.is_set():
            return
        print(
            f"\nautoclaude: session exceeded the {int(self._cap)}s wall-clock "
            "cap; SIGTERM (session cap).",
            file=sys.stderr,
        )
        self.fired = True
        self._proc.terminate()
        try:
            self._proc.wait(timeout=self._grace)
        except subprocess.TimeoutExpired:
            print(
                "\nautoclaude: session ignored SIGTERM; SIGKILL (session cap).",
                file=sys.stderr,
            )
            self._proc.kill()
