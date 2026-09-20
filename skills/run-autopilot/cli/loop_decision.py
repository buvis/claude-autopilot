"""cli/loop_decision.py - the decision table and pure ports of the loop
driver (PRD 00192).

Allowed imports: stdlib, `cli.pause`, `cli.usage_limit`, `cli.routing`;
never `cli.loop`, `cli.loop_gates` or `cli.loop_act`.
"""

from __future__ import annotations

import datetime as _dt
import json
import re
from pathlib import Path

from cli import pause, usage_limit
from cli.routing import _load_json

_CONNECTION_FAIL = re.compile(
    r"unable to connect|connection ?(refused|reset|error)|econn|etimedout"
    r"|enotfound|eai_again|network is unreachable|fetch failed",
    re.IGNORECASE,
)


# ── small pure ports ─────────────────────────────────────────────────────────


def died_next(prd: str, retries: int, retries_max: int) -> str:
    """Branch 5's final else as a pure decision: retry|park|die. Empty
    prd (bootstrap - nothing selected yet) always halts loud; otherwise
    retry until the budget is exhausted, then park."""
    if not prd:
        return "die"
    if retries < retries_max:
        return "retry"
    return "park"


def _tostring(value) -> str:
    """jq `tostring`: strings stay bare, everything else is its JSON."""
    if isinstance(value, str):
        return value
    return json.dumps(value, separators=(",", ":"))


def pause_detail(state: dict) -> str:
    """The wrapper's one-line pause summary. cap_pause_reason is
    summarized rather than dumped - raw findings JSON buried the resume
    runbook at the operator (2026-07-19); the full findings stay in
    state.json."""
    reason = state.get("pause_reason")
    if state.get("phase") != "paused" and reason in (None, False, ""):
        return ""
    value = None
    if isinstance(reason, dict):
        value = reason.get("detail")
        if value is None:
            value = reason
    elif reason is not None:
        value = reason
    if value is None:
        cap = state.get("cap_pause_reason")
        if isinstance(cap, dict) and "cycle" in cap:
            count = len(cap.get("unresolved_findings") or [])
            value = f"review cap hit: cycle {cap.get('cycle')}/{cap.get('cap')} · {count} unresolved findings"
        else:
            value = cap
    if value is None:
        value = "paused"
    return _tostring(value)


def _jq_or(state: dict, key: str, default):
    """jq's `//`: the default replaces null and false, not just absence.
    Identity checks, not `in (None, False)` - Python equates 0 == False
    and jq's // must NOT replace a legitimate 0."""
    value = state.get(key)
    return default if value is None or value is False else value


def fingerprint(state: dict) -> str:
    """The fields that must move for the batch to progress."""
    rotations = _jq_or(state, "cap_rotations", [])
    parts = [
        _tostring(state.get("prd")),
        _tostring(state.get("next_phase")),
        _tostring(_jq_or(state, "tasks_completed", -1)),
        _tostring(_jq_or(state, "review_cycles", -1)),
        _tostring(_jq_or(state, "cycle", -1)),
        _tostring(len(rotations) if isinstance(rotations, (list, dict)) else 0),
        _tostring(_jq_or(state, "replan_count", -1)),
    ]
    return "|".join(parts)


def plugin_drift(state: dict, installed: dict) -> str | None:
    """PRD 00086 R3: a plugin pinned at batch selection that differs
    from what is installed now. None when every pin matches or no pin
    was recorded (an unpinned batch is never blocked)."""
    pins = (state.get("batch") or {}).get("plugin_versions")
    if not isinstance(pins, dict):
        return None
    for name, pin in pins.items():
        current = "MISSING"
        entries = (installed.get("plugins") or {}).get(name)
        if isinstance(entries, list) and entries and isinstance(entries[0], dict):
            version = entries[0].get("version")
            if version is not None:
                current = _tostring(version)
        if _tostring(pin) != current:
            return f"{name} pinned={_tostring(pin)} now={current}"
    return None


def last_result_field(log_path: Path, field: str, error_only: bool = False):
    """The LAST result event's `field` from the session log, or None.
    Sessions re-invoked by background-task notifications emit one result
    event PER re-invoke - the final one wins (2026-07-13)."""
    value = None
    try:
        with open(log_path, "rb") as fh:
            for raw in fh:
                try:
                    entry = json.loads(raw)
                except ValueError:
                    continue
                if not isinstance(entry, dict) or entry.get("type") != "result":
                    continue
                if error_only and entry.get("is_error") is not True:
                    continue
                got = entry.get(field)
                if got is not None:
                    value = got
    except OSError:
        return None
    return value


def _mtime(path: Path) -> int | None:
    try:
        return int(path.stat().st_mtime)
    except OSError:
        return None


def _utcnow_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class DecisionMixin:
    """Loop's decision table: _decide, _decide_from_state, _decide_no_progress,
    _decide_limit_wait, _decide_network_outage, _decide_died,
    _fingerprint_bound. Reads self._int, self._clock, self._sleep, self._probe,
    self._detect_limit, self.err, and the counters self._net_retries,
    self._died_retries, self._fp_prev, self._fp_repeats - all set by
    Loop.__init__ in cli/loop.py. Imports nothing from cli.loop."""

    # ── decision table ──
    def _decide(self, ap_dir: Path, ts_start: float) -> dict:
        decision = {
            "signal": "",
            "detail": "",
            "next": "",
            "phase_end": "",
            "prd": "",
            "batch": "",
            "limit_wait": None,
        }
        state_path = ap_dir / "state.json"
        marker = ap_dir / "state-write-failed"
        if marker.is_file():
            decision["signal"] = "state_write_failed"
            data = _load_json(marker)
            detail = data.get("detail") if isinstance(data, dict) else None
            decision["detail"] = detail or "state write failed"

        state_touched = False
        mtime = _mtime(state_path)
        if mtime is not None and mtime >= int(ts_start):
            state_touched = True
        if state_touched:
            self._net_retries = 0
            self._died_retries = 0
        decision["state_touched"] = state_touched

        state = _load_json(state_path) if decision["signal"] == "" else None
        if isinstance(state, dict):
            self._decide_from_state(decision, state, state_touched)

        if decision["signal"] == "continue":
            self._limit_wait_for(ap_dir, decision)
        elif decision["signal"] == "":
            self._decide_no_progress(decision, ap_dir, state_path, ts_start)
        return decision

    def _decide_from_state(
        self, decision: dict, state: dict, state_touched: bool
    ) -> None:
        """The readable-state rows of the table, in signal order."""
        decision["prd"] = state.get("prd") or ""
        decision["batch"] = (state.get("batch") or {}).get("id") or ""
        decision["phase_end"] = state.get("next_phase") or ""
        decision["next"] = decision["phase_end"]
        detail = pause_detail(state)
        stalled = None
        stall = state.get("stall_reason")
        if isinstance(stall, dict):
            stalled = stall.get("stalled")
        if detail:
            decision["signal"] = "paused"
            decision["detail"] = detail
        elif stalled == "subagent_prompt_overrun":
            decision["signal"] = "continue"
            decision["detail"] = "replan"
        elif not decision["next"]:
            decision["signal"] = "done"
        elif state_touched:
            decision["signal"] = "continue"

    def _decide_no_progress(
        self, decision: dict, ap_dir: Path, state_path: Path, ts_start: float
    ) -> None:
        """Branch 5: a stand-down is a pause, limit-hit is scheduling,
        network outage is infrastructure, anything else died."""
        reason = pause.stand_down_reason(ap_dir, ts_start)
        if reason is not None:
            decision["signal"] = "paused"
            decision["detail"] = f"session stood down: {reason}"
            decision["stood_down"] = reason
            return

        if self._limit_wait_for(ap_dir, decision):
            return

        api_fail = last_result_field(
            ap_dir / "last-session.log",
            "result",
            error_only=True,
        )
        if isinstance(api_fail, str) and _CONNECTION_FAIL.search(api_fail):
            self._decide_network_outage(decision, api_fail)
            return

        self._decide_died(decision, state_path)

    def _limit_wait_for(self, ap_dir: Path, decision: dict) -> bool:
        """The limit check both paths share (PRD 00199). A live rejected
        event in the session log's tail sets the wait (or the beyond-cap
        death) whether or not the session made progress and whatever
        `overageStatus` says: a relaunch into overage is never scheduled.
        On the progress path only the event counts, never the prose banner
        (hand-off text may mention limits); the no-progress path keeps the
        injected detector, event first then banner. True when a wait or a
        death was decided."""
        log = ap_dir / "last-session.log"
        if decision["signal"] == "continue":
            reset = usage_limit.detect_rejected_from_log(log)
        else:
            reset = self._detect_limit(log)
        if isinstance(reset, int):
            self._decide_limit_wait(decision, reset)
            return True
        return False

    def _decide_limit_wait(self, decision: dict, reset: int) -> None:
        """A usage-limit hit is scheduling: wait inside the cap, else die."""
        wait = usage_limit.wait_decision(
            reset,
            now=self._clock(),
            max_wait_secs=self._int("_AUTOPILOT_LIMIT_WAIT_MAX", 21600),
        )
        if wait is not None:
            stamp = _dt.datetime.fromtimestamp(reset).strftime("%H:%M")
            decision["signal"] = "continue"
            decision["detail"] = f"usage-limit; resuming ~{stamp}"
            decision["limit_wait"] = wait
        else:
            decision["signal"] = "died"
            decision["detail"] = (
                "usage-limit reset beyond _AUTOPILOT_LIMIT_WAIT_MAX "
                f"({self._int('_AUTOPILOT_LIMIT_WAIT_MAX', 21600)}s)"
            )

    @staticmethod
    def _probe_budget(net_max: int) -> int:
        """Probes per retry: one every 30 s across `_AUTOPILOT_NET_WAIT_MAX`,
        never fewer than one."""
        return max(1, net_max // 30)

    def _decide_network_outage(self, decision: dict, api_fail: str) -> None:
        """A connection failure: poll connectivity inside the retry budget, else die.

        The budget counts probes, not wall-clock (PRD 00199): a machine that
        sleeps between two probes spends nothing, where a deadline against
        `self._clock()` read a lid-close as three exhausted outage windows."""
        retries_max = self._int("_AUTOPILOT_NET_RETRIES_MAX", 3)
        if self._net_retries < retries_max:
            self._net_retries += 1
            probes = self._probe_budget(self._int("_AUTOPILOT_NET_WAIT_MAX", 1800))
            print(
                f"\nautoclaude: API unreachable ({api_fail}). Polling "
                f"connectivity, max {probes} probes (retry {self._net_retries}"
                f"/{retries_max})…",
                file=self.err,
            )
            ok = False
            for attempt in range(probes):
                if self._probe():
                    ok = True
                    break
                if attempt + 1 < probes:
                    self._sleep(30)
            if ok:
                decision["signal"] = "continue"
                decision["detail"] = f"network restored (retry {self._net_retries})"
            else:
                decision["signal"] = "died"
                decision["detail"] = f"API unreachable for {probes} probes"
        else:
            decision["signal"] = "died"
            decision["detail"] = (
                f"repeated API connection failures ({retries_max} relaunches)"
            )

    def _decide_died(self, decision: dict, state_path: Path) -> None:
        """The died ladder: retry, park, or halt loud on a bootstrap."""
        verdict = died_next(
            decision["prd"],
            self._died_retries,
            self._int("_AUTOPILOT_DIED_RETRIES_MAX", 1),
        )
        if verdict == "retry":
            self._died_retries += 1
            decision["signal"] = "continue"
            decision["detail"] = (
                f"session died; retry {self._died_retries}/{self._int('_AUTOPILOT_DIED_RETRIES_MAX', 1)}"
            )
        elif verdict == "park":
            decision["signal"] = "park"
            decision["detail"] = (
                f"died after {self._died_retries} retries; parking {decision['prd']}"
            )
        else:
            decision["signal"] = "died"
            if not state_path.is_file():
                decision["detail"] = "no state.json"
            elif _load_json(state_path) is not None:
                decision["detail"] = "session made no progress (state.json untouched)"
            else:
                decision["detail"] = "state.json unreadable"

    def _fingerprint_bound(self, decision: dict, state_path: Path) -> None:
        """N identical progress fingerprints in a row = the loop is
        burning sessions on nothing. Cap deliberately generous
        (default 5); any progress resets it."""
        if (
            decision["signal"] == "continue"
            and decision.get("state_touched")
            and decision["detail"] != "replan"
        ):
            state = _load_json(state_path)
            fp = fingerprint(state) if isinstance(state, dict) else ""
            if fp and fp == self._fp_prev:
                self._fp_repeats += 1
                if self._fp_repeats >= self._int("_AUTOPILOT_PHASE_REPEATS_MAX", 5):
                    if decision["prd"]:
                        decision["signal"] = "park"
                        decision["detail"] = (
                            f"no progress across {self._fp_repeats} sessions; parking {decision['prd']}"
                        )
                    else:
                        decision["signal"] = "paused"
                        decision["detail"] = (
                            f"no measurable progress across {self._fp_repeats} "
                            f"consecutive sessions (fingerprint {fp}); "
                            "inspect state.json"
                        )
            else:
                self._fp_repeats = 0
            self._fp_prev = fp
        else:
            self._fp_repeats = 0
            self._fp_prev = ""
