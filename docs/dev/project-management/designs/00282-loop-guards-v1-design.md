# Design: Loop guards (spend budget, instant exits, idle hangs, in-code entry)

## Architecture fit

All four features land inside `skills/run-autopilot/cli/`, the loop-driver
layer already split by PRD 00192 into `loop.py` (orchestration), the
`DecisionMixin` (`loop_decision.py`, pure decision table), the `ActMixin`
(`loop_act.py`, act branches), `records.py` (state-mutating lifecycle
primitives: `do_stall`/`do_park`), `enter.py` (the Phase-0 step chain run
by `autopilot enter`), `watchdog.py` (wall-clock cap for one spawned
child), and `runner.py` (spawns the child, wires the watchdog). No new
layer is needed: every capability is a widening of a table/call that
already exists at exactly the seam this PRD names.

- **Spend guard (F1)** is a new decision-table override, applied the same
  way `_fingerprint_bound` already overrides a `continue` decision into
  `park` — it reads the metrics ledger, not state, so it belongs beside
  `fingerprint`/`_fingerprint_bound` in `loop_decision.py`, not in
  `_decide_from_state`.
- **Instant-exit (F3)** is a new row in `_decide`, checked before the
  existing `state_touched` counter reset (exactly where the docstring in
  `loop_decision.py` already says `_decide` branches happen), because it
  must see the session's own wall time and cost, which only `loop.py`'s
  caller (`_run_loop`) can supply via `ts_start`/`last-session.log`.
- **Idle watchdog from launch (F4)** is a widening of `Watchdog`'s own
  state machine in `watchdog.py`: today `_watch()` waits blind for
  `self._cap`, then (if `activity_path` is set) polls for idle/ceiling
  only *past* the cap. F4 adds the mirror pre-cap polling path.
- **In-code entry (F2)** moves the first step of every build session
  (`autopilot enter`) from the session's own first Bash call into the
  loop driver, immediately before `_launch_phase` spawns a `build`
  session — the loop already owns `ap_dir` and `state.json` at that
  point, and `enter()` is already a pure, injectable function
  (`cli/enter.py`) the CLI subcommand (`_run_enter`) already calls.

## Module placement

New files: none. Every change is an edit to an existing module.

| File | Change |
|---|---|
| `cli/records.py` | `_parse_marker` gains a `site` key (default `"wrapper_died"`); `_finish_park` reorders to check the marker's `site` for `"budget"` BEFORE it consults `parks_consecutive`/`resume.park_decision` at all (a bigger reshuffle than one branch — the budget path must never reach the systemic-halt consult); `PER_PRD_RESET_FIELDS` gains `"prd_budget_since"`. |
| `cli/loop_decision.py` | new `budget_usd_for(env)`, `DecisionMixin._budget_bound(decision, ap_dir)`; new `_INSTANT_EXIT_SECS` constant and the instant-exit row inside `_decide`. |
| `cli/loop.py` | adds `from cli import enter, state` to its imports (both used only by the new code below); `_run_loop` calls `_budget_bound` right after `_fingerprint_bound`; `Loop.__init__` gains `enter_fn` keyword; new `Loop._pre_enter`; `_launch_phase` calls it before routing. |
| `cli/loop_act.py` | `_act_park` writes `decision["park_site"]` into the marker as `"site"` when set. |
| `cli/enter.py` | `_write_prd` gains a new `now` parameter (it has none today — only `enter()` itself does) and sets `state.prd_budget_since`; `enter()`'s call to `_write_prd` at its existing call site must be updated to pass `now=now`. |
| `cli/__main__.py` | `_run_enter` gains the `loop_entry` replay branch, before calling `enter.enter()`. |
| `cli/brief.py` | new `_entry_lines(state)`; `render_brief` splices it in right after `_where`. |
| `cli/watchdog.py` | `Watchdog.__init__` gains `busy_fn` keyword; new `_wait_pre_cap`; `_watch` calls it instead of a blind `proc.wait(timeout=remaining)` when `busy_fn` is set; new module-level `session_busy(log_path)`. |
| `cli/runner.py` | `_run_session` passes `busy_fn=lambda: session_busy(log_path)` into `Watchdog(...)`. |
| `references/state-schema.md` | rows for `loop_entry`, `prd_budget_since`. |
| `references/phase-build.md` | one sentence under "Enter in one call" naming the `## Entry` brief replay. |
| run-autopilot docs (`SKILL.md` or the env-knob table it already carries) | `_AUTOPILOT_PRD_BUDGET_USD` beside the other `_AUTOPILOT_*` knobs. |
| `CHANGELOG.md` | `[Unreleased]` → `### Added`: budget guard, instant-exit signal, idle-from-launch watchdog. |

## Interfaces & contracts

### F1 — Spend guard

```python
# cli/loop_decision.py

def budget_usd_for(env: dict) -> float:
    """`_AUTOPILOT_PRD_BUDGET_USD`: float; default 300.0; "0" or 0 disables
    (returns 0.0); unparseable keeps the default."""
    raw = env.get("_AUTOPILOT_PRD_BUDGET_USD")
    if raw is None:
        return 300.0
    try:
        return float(raw)
    except ValueError:
        return 300.0


class DecisionMixin:
    def _budget_bound(self, decision: dict, ap_dir: Path) -> None:
        """Called in `Loop._run_loop` immediately after `_fingerprint_bound`.
        Applies only when `decision["signal"]` is already `"continue"`
        (a relaunch is about to happen for `decision["prd"]`, including an
        `instant_exit` whose `then` resolved to `"continue"`)."""
        budget = budget_usd_for(self.env)
        prd = decision["prd"]
        if not budget or not prd:
            return
        state = _load_json(ap_dir / "state.json")
        since = state.get("prd_budget_since") if isinstance(state, dict) else None
        if not since:
            return
        total = _prd_spend_total(ap_dir, prd, since)
        cost = last_result_field(ap_dir / "last-session.log", "total_cost_usd")
        if isinstance(cost, (int, float)) and not isinstance(cost, bool):
            total += cost
        if total > budget:
            decision["signal"] = "park"
            decision["park_site"] = "budget"
            decision["detail"] = f"budget: ${total:.2f} > ${budget:g}; parking {prd}"


def _prd_spend_total(ap_dir: Path, prd: str, since: str) -> float:
    """Sum of `cost_usd` over `loop-metrics.jsonl` rows with
    `row["prd"] == prd` and `row["ts_start"] >= since`'s epoch seconds.
    `since` is an ISO-8601 UTC stamp (the same shape `enter.py`'s `now`
    callable produces); an unparseable `since` reads as `0` (every row for
    this prd counts) rather than raising. Uses
    `cli.render_metrics.load_rows` (already the ledger reader `loop.py`'s
    `_append_convergence` uses) — no new JSONL parser."""
```

`_act_park` in `cli/loop_act.py` carries the new field into the marker:

```python
def _act_park(self, decision: dict, ap_dir: Path) -> int | None:
    ...
    payload = {"prd": decision["prd"], "reason": decision["detail"]}
    if decision.get("park_site"):
        payload["site"] = decision["park_site"]
    marker.write_text(json.dumps(payload))
```

`cli/records.py`:

```python
def _parse_marker(marker_path: Path) -> str | dict | None:
    """... Returns {"prd": str, "reason": str, "site": str} for a present,
    usable marker — "site" defaults to "wrapper_died" when the marker
    predates this field (every existing marker shape still parses)."""
    ...
    return {"prd": raw["prd"], "reason": raw.get("reason", ""),
            "site": raw.get("site") or "wrapper_died"}
```

`do_park`'s tail (`_finish_park`) branches on the parsed `site`:

```python
def _finish_park(..., marker, prd, reason, wip_filenames) -> int:
    site = marker.get("site", "wrapper_died") if isinstance(marker, dict) else "wrapper_died"
    if site == "budget":
        rc = do_stall(state_path, prd=prd, site="budget", detail=reason,
                       prds_dir=prds_dir, autopilot_dir=autopilot_dir,
                       extra_mutator=None)
        if rc == 0:
            delete_marker()
            print(f"autopilot: parked {prd} (budget)")
        return rc  # never the systemic-halt branch; park_decision not consulted
    # ... existing wrapper_died branch unchanged
```

(`do_stall`'s existing `site != "wrapper_died"` rule already zeroes
`batch.parks_consecutive` for any non-`wrapper_died` site — no change
needed there.)

`cli/records.py` reset field:

```python
PER_PRD_RESET_FIELDS = (
    ...,
    "prd_budget_since",
)
```

`cli/enter.py`, `_write_prd`:

```python
def _write_prd(
    out, state_path, prds_dir, autopilot_dir, record_resume_row,
    now: Callable[[], str] = _utc_now,
) -> dict | None:
    prd = out["prd"]
    try:
        def _mut(data: dict) -> None:
            if data.get("prd") != prd or "prd_budget_since" not in data:
                data["prd_budget_since"] = now()
            data["prd"] = prd
        statectl.mutate(state_path, _mut)
        ...
```

`state.prd_budget_since`: ISO-8601 UTC string (same format as
`batch.catchup_completed_at`). Set on first entry for a PRD, kept across a
same-PRD re-entry (cap rotation, task-boundary resume), refreshed when
`state.prd` changes before the write (a different PRD, or the same PRD
re-entering after a park→backlog→wip resume, since the park cleared it via
`PER_PRD_RESET_FIELDS`).

### F2 — Loop pre-launch enter

```python
# cli/loop.py

class Loop(...):
    def __init__(self, ..., enter_fn=enter.enter) -> None:
        ...
        self._enter_fn = enter_fn

    def _pre_enter(self, ap_dir: Path) -> None:
        """Called from `_launch_phase` before `routing.route`, only when
        the about-to-launch phase is `build` or a `park-requested` marker
        exists (park must run before the session's own Bash call would,
        so a parked PRD never gets a wasted build session). Runs `enter()`
        in-process; failure degrades to "launch normally", never halts the
        loop — enter() is unattended-safe by construction (it never
        raises except StateError on a corrupt state.json, already handled
        by the loop's `_schema_gate`)."""
        # NOTE (dispatch 2 found this): the local variable here must NOT
        # be named `state` — `cli.enter` imports the `state` MODULE
        # (`from . import ... state ...`), and shadowing it with a dict
        # local would make a bare `except state.StateError` below crash
        # with AttributeError instead of catching anything, defeating the
        # "never halts the loop" guarantee this function exists for.
        current = _load_json(ap_dir / "state.json")
        next_phase = current.get("next_phase") if isinstance(current, dict) else None
        marker = (ap_dir / "park-requested").is_file()
        if next_phase != "build" and not marker:
            return
        try:
            result = self._enter_fn(
                ap_dir / "state.json",
                prds_dir=ap_dir.parent / "prds",
                autopilot_dir=ap_dir,
                prd_arg=None,
                in_loop=True,
            )
        except state.StateError as err:  # never halts the loop
            print(f"autoclaude: pre-launch enter failed: {err}", file=self.err)
            return
        warnings = result.pop("warnings", [])
        for line in warnings:
            print(line, file=self.err)
        statectl.mutate(
            ap_dir / "state.json",
            lambda data: data.update(loop_entry={
                "entered_by": "loop", "prd": result.get("prd"), "result": result,
            }),
        )
```

`_launch_phase` calls `self._pre_enter(ap_dir)` as its first line, before
re-reading `state.json` for the phase to route (the pre-enter mutates
`state.json`, so the existing read must stay after it, not before).

`cli/__main__.py`, `_run_enter` (replay branch, first thing inside the
function body, before any call to `enter.enter`):

```python
def _run_enter(args: argparse.Namespace) -> int:
    state_path = _resolve_state_path(args.state)
    refuse = _schema_version_preflight(state_path)
    if refuse is not None:
        return refuse
    autopilot_dir = state_path.parent
    current, _ = state.load(state_path)
    loop_entry = current.get("loop_entry")
    if isinstance(loop_entry, dict):
        statectl.mutate(state_path, lambda data: data.pop("loop_entry", None))
        # args.prd is None for every loop-driven call (Loop._pre_enter's
        # own enter_fn call passes prd_arg=None); only take the replay
        # when this session's own invocation also asked for no explicit
        # PRD, so a manual `autopilot enter --prd X` is never silently
        # answered with a stale loop-selected result for a different PRD
        # (dispatch 2's finding):
        if (
            args.prd is None
            and loop_entry.get("prd") == current.get("prd")
            and isinstance(loop_entry.get("result"), dict)
        ):
            result = dict(loop_entry["result"])
            print(json.dumps(result, sort_keys=True))
            if result.get("detail"):
                print(f"autopilot: {result['detail']}", file=sys.stderr)
            return 0
        # any other loop_entry (stale PRD, malformed result): fall through,
        # enter() runs as today.
    prds_dir = Path(_resolve_prds_path(args.prds, autopilot_dir))
    try:
        result = enter.enter(...)
    ...
```

`result["result"]` (as stored in `loop_entry`) is the `enter()` return
dict **minus** `"warnings"` — `Loop._pre_enter` already popped it before
storing, so the replay never re-prints warnings a dead session already
emitted on its own stderr.

`cli/brief.py`:

```python
def _entry_lines(state: dict) -> list[str]:
    """`## Entry`: prd/catchup/design/stop from `state.loop_entry.result`,
    rendered right after `_where`'s lines, only when `loop_entry` is a
    dict with a `result` dict. Absent `loop_entry` renders nothing (not
    even the header) — the golden build brief (no loop_entry) is
    unchanged byte for byte."""
    entry = state.get("loop_entry")
    result = entry.get("result") if isinstance(entry, dict) else None
    if not isinstance(result, dict):
        return []
    return [
        "",
        "## Entry",
        f"- prd: {_text(result.get('prd'))}",
        f"- catchup: {_text(result.get('catchup'))}",
        f"- design: {_text(result.get('design'))}",
        f"- stop: {_text(result.get('stop'))}",
    ]
```

`render_brief` splices `*_entry_lines(state)` immediately after the
`_where(state)` block and before the blank line + `## Contract card`
header.

Phase-build.md gains one sentence under "Enter in one call": *"When the
session brief carries an `## Entry` section, take `prd`, `catchup` and
`design` from it directly; running `autopilot enter` anyway is safe (it
replays the same stored line) but adds nothing."*

### F3 — Instant-exit signal

**Dispatch 1 found this section's first draft unbuildable as written**
(the code sample replaced the real `_limit_wait_for`/`_decide_no_progress`
dispatch instead of wrapping its *result*, which would have silently
dropped the died/retry/park ladder and the in-flight usage-limit check
for any session under 30s). Corrected below: the real dispatch in
`_decide` runs FIRST, completely unchanged; `_apply_instant_exit` runs
AFTER it and only ever reclassifies the `decision` the real dispatch
already produced — it never substitutes for that dispatch.

**Dispatch 2 found a second bug in the first correction**: that draft
moved the `_net_retries`/`_died_retries` reset from its real position
(BEFORE the dispatch, which is where it sits in the actual code today —
confirmed by reading `cli/loop_decision.py` directly) to AFTER it, framed
as if it were already there ("the counter reset below"). Moving it would
zero out, in the same call, any increment that very call's own
`_decide_died`/`_decide_network_outage` dispatch just made — a touched-
state session that also died every time would retry forever, never
escalating to park. Corrected below: the reset keeps its real,
pre-dispatch position, completely untouched; `_apply_instant_exit` is
appended strictly as a new step after the dispatch, and never touches
the counters at all (it only ever reads/rewrites `decision["signal"]`
and `decision["then"]`):

```python
# cli/loop_decision.py

_INSTANT_EXIT_SECS = 30

class DecisionMixin:
    def _decide(self, ap_dir: Path, ts_start: float) -> dict:
        decision = {...}
        ...
        state_touched = False
        mtime = _mtime(state_path)
        if mtime is not None and mtime >= int(ts_start):
            state_touched = True
        # UNCHANGED real position — before dispatch, exactly as today:
        if state_touched:
            self._net_retries = 0
            self._died_retries = 0
        decision["state_touched"] = state_touched

        state = _load_json(state_path) if decision["signal"] == "" else None
        if isinstance(state, dict):
            self._decide_from_state(decision, state, state_touched)

        # unchanged dispatch — runs to completion exactly as today,
        # including every side effect (_died_retries/_net_retries
        # increments inside _decide_died/_decide_network_outage, the
        # limit-wait sleep decision, etc. — these run AFTER the reset
        # above, so an increment made here survives into the returned
        # decision, exactly as today):
        if decision["signal"] == "continue":
            self._limit_wait_for(ap_dir, decision)
        elif decision["signal"] == "":
            self._decide_no_progress(decision, ap_dir, state_path, ts_start)

        # new: the only new step, appended after everything above with
        # no interaction with the counters:
        self._apply_instant_exit(decision, ap_dir, ts_start)
        return decision
```

`_decide_from_state`/`_limit_wait_for`/`_decide_no_progress`, and the
counter reset's position relative to them, are **not edited at all** —
`_apply_instant_exit` is a pure post-processing step appended after
everything that exists today, that reads the `decision` they already
wrote and only ever changes its presentation (`signal`/`then`), never
which retry-ladder branch ran and never the counters:

```python
    def _apply_instant_exit(self, decision: dict, ap_dir: Path, ts_start: float) -> None:
        """Runs after the real dispatch above has already set
        decision["signal"] to its true outcome (continue/died/park/paused/
        done/state_write_failed) and already taken every side effect that
        outcome carries (a died-retry increment, a limit-wait sleep
        decision, etc. — all untouched). Reclassifies the PRESENTATION
        only: a session under 30s wall with no billed cost gets
        signal="instant_exit" plus decision["then"] = what the real
        dispatch actually decided, so metrics/act both see the true
        outcome via `then` while the row itself flags it instant. Skips
        reclassifying "paused", "done", and "state_write_failed" — those
        rows are never presented as instant_exit even if they resolved in
        under 30s, because a human-facing pause or a drained batch must
        never read as a transient blip."""
        if decision["signal"] in ("paused", "done", "state_write_failed"):
            return
        wall = self._clock() - ts_start
        cost = last_result_field(ap_dir / "last-session.log", "total_cost_usd")
        billed = isinstance(cost, (int, float)) and not isinstance(cost, bool) and cost > 0
        if wall >= _INSTANT_EXIT_SECS or billed:
            return
        decision["then"] = decision["signal"] or "continue"
        decision["signal"] = "instant_exit"
```

Because the real dispatch already ran unmodified, `_died_retries`/
`_net_retries` increment exactly once per instant-exit session (inside
`_decide_died`/`_decide_network_outage`, as they always have) —
matching the named acceptance test ("3s, $0: retry first, park second,
`_died_retries` not reset by the touched state"). No throwaway decision
copy is needed: there is only ever one `decision` dict, mutated once by
the real dispatch and once more, in place, by the reclassification.

`cli/loop_act.py`, `_act_branch` dispatches on `then`:

```python
    def _act_branch(self, decision: dict, ap_dir: Path) -> int | None:
        branch = decision["signal"]
        if branch == "instant_exit":
            print(f"\nautoclaude: instant exit ({decision['detail']}); then {decision['then']}.", file=self.out)
            decision = {**decision, "signal": decision["then"]}
            branch = decision["signal"]
        if branch == "state_write_failed":
            ...  # unchanged from here down
```

Metrics: `_metrics_line` already copies `decision["signal"]` verbatim, so
an `instant_exit` row's `"signal"` field is `"instant_exit"` with `"then"`
riding along via `_decision_fields` (new row: copy `decision.get("then")`
into the line when the signal is `instant_exit`).

### F4 — Idle watchdog from launch

```python
# cli/watchdog.py

def session_busy(log_path: str) -> bool:
    """Scan the stream-json log for `tool_use` ids under unmatched
    `tool_result`, or a non-empty `tasks` list on the last
    `background_tasks_changed` system event. True (busy, never kill) on
    any parse/IO exception, on a missing file, or on the first malformed
    line encountered (skip it, keep scanning). False only when the scan
    completes clean and finds neither signal."""
    try:
        open_ids: set[str] = set()
        last_tasks: list | None = None
        with open(log_path, "r", encoding="utf-8") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    entry = json.loads(raw)
                except ValueError:
                    continue
                if not isinstance(entry, dict):
                    continue
                kind = entry.get("type")
                if kind == "assistant":
                    for block in _content_blocks(entry):
                        if block.get("type") == "tool_use" and isinstance(block.get("id"), str):
                            open_ids.add(block["id"])
                elif kind == "user":
                    for block in _content_blocks(entry):
                        if block.get("type") == "tool_result" and isinstance(block.get("tool_use_id"), str):
                            open_ids.discard(block["tool_use_id"])
                elif kind == "system" and entry.get("subtype") == "background_tasks_changed":
                    last_tasks = entry.get("tasks")
        return bool(open_ids) or bool(last_tasks)
    except OSError:
        return True
```

`_content_blocks(entry)` is a 3-line helper reading
`entry.get("message", {}).get("content")` as a list, filtering to dicts —
pulled out only because both branches need it; not a new public symbol.

**Dispatch 1 also found the first draft of this section broken**: it only
replaced the SECOND (post-warning-fire) blind wait inside `_watch`,
leaving the FIRST blind wait — `self._proc.wait(timeout=self._cap -
self._warn)`, which covers `[0, cap - warn_secs)`, almost the entire cap
window under the runner's real wiring (`warn_secs=900` by default against
a 7200s cap) — completely unpolled. Since `cli/runner.py` always passes
`on_warn` (it is unconditional in `_run_session`), that first draft would
never have caught the PRD's own motivating case (a 2h10m hang) until the
last 15 minutes. Corrected below: `_wait_pre_cap` now owns the **entire**
`[0, cap]` window in one poll loop (folding the warning fire in as one more
thing it checks each tick) whenever `busy_fn` is wired; the old two-stage
blind-wait structure is kept only for the `busy_fn is None` case (today's
exact behavior, unchanged).

```python
class Watchdog:
    def __init__(self, ..., busy_fn: Callable[[], bool] | None = None) -> None:
        ...
        self._busy_fn = busy_fn

    def _watch(self) -> None:
        if self._busy_fn is not None and self._idle > 0:
            result = self._wait_pre_cap()
            if result is None:
                return  # exited on its own, or cancelled, before any fire
            reason, silence = result
        else:
            # unchanged two-stage blind wait (today's exact behavior):
            remaining = self._cap
            if self._on_warn is not None and 0 < self._warn < self._cap:
                try:
                    self._proc.wait(timeout=self._cap - self._warn)
                    return
                except subprocess.TimeoutExpired:
                    pass
                if self._cancelled.is_set():
                    return
                self.warned = True
                print(...)  # unchanged warning message
                try:
                    self._on_warn()
                except Exception as err:
                    print(f"\nautoclaude: cap warning failed: {err}", file=sys.stderr)
                remaining = self._warn
            try:
                self._proc.wait(timeout=remaining)
                return
            except subprocess.TimeoutExpired:
                pass
            if self._cancelled.is_set():
                return
            reason = self._determine_fire_reason()
            if reason is None:
                return
        self.fired_reason = reason
        self.fired = True
        self._terminate_and_escalate()

    def _wait_pre_cap(self) -> tuple[str, float] | None:
        """Poll every `self._poll` seconds across the WHOLE `[0, cap]`
        window from launch (not just past it): on each tick, fire the
        warning callback once (if configured) at `cap - warn_secs`, same
        as the old two-stage wait did, and separately fire "idle"
        immediately the first tick where the activity path has been silent
        for `self._idle` seconds AND `busy_fn()` is False — whichever
        condition is reached first on that tick. Reaching the cap with
        no idle fire falls through to the EXISTING unchanged post-cap
        path (`_determine_fire_reason`/`_wait_past_cap`), so the ceiling
        backstop (twice the cap) is untouched — this method only ever
        returns "idle", never "ceiling"; the cap itself is where this
        method's own window ends."""
        start = time.monotonic()
        deadline = start + self._cap
        warn_at = deadline - self._warn if (self._on_warn and 0 < self._warn < self._cap) else None
        while True:
            now = time.monotonic()
            if now >= deadline:
                reason = self._determine_fire_reason()
                return (reason, 0.0) if reason is not None else None
            try:
                self._proc.wait(timeout=min(self._poll, deadline - now))
                return None
            except subprocess.TimeoutExpired:
                pass
            if self._cancelled.is_set():
                return None
            if warn_at is not None and not self.warned and time.monotonic() >= warn_at:
                self.warned = True
                print(
                    f"\nautoclaude: session is {self._warn:g}s from the "
                    f"{self._cap:g}s wall-clock cap; requesting a "
                    "task-boundary handoff.",
                    file=sys.stderr,
                )
                try:
                    self._on_warn()
                except Exception as err:
                    print(f"\nautoclaude: cap warning failed: {err}", file=sys.stderr)
            mtime = self._activity_mtime(self._activity_path) if self._activity_path else None
            silence = time.time() - mtime if mtime is not None else float("inf")
            if silence >= self._idle and not self._busy_fn():
                print(
                    f"\nautoclaude: session silent for {silence:g}s "
                    f"(idle-from-launch, before the {self._cap:g}s cap); "
                    "SIGTERM (idle).",
                    file=sys.stderr,
                )
                return "idle", silence
```

At its own deadline (the cap), `_wait_pre_cap` calls the **existing**
`_determine_fire_reason` itself (unchanged function, re-checking
`activity_path`/`idle_secs` and running `_wait_past_cap`/ceiling) rather
than returning control to `_watch` for that — so the post-cap ceiling
backstop is reached through exactly the code path it runs through today,
just invoked one level deeper. `_watch`'s only job once `_wait_pre_cap`
returns is: `None` means the child exited or the watchdog was cancelled
(nothing to fire), a `(reason, silence)` tuple means fire it. F4 adds a
polling window *before* the cap; it does not replace what already
happens *after* it.

`cli/runner.py`, `_run_session`:

```python
from cli.watchdog import Watchdog, session_busy
...
dog = Watchdog(
    proc, cap_secs=cap_secs, grace_secs=grace_secs, warn_secs=warn_secs,
    on_warn=lambda: request_wrapper_handoff(autopilot_dir),
    idle_secs=idle_secs, activity_path=str(log_path), poll_secs=_IDLE_POLL_SECS,
    busy_fn=(lambda: session_busy(log_path)) if idle_secs > 0 else None,
).start()
```

(`busy_fn` is only wired when `idle_secs > 0`, matching the existing
"idle_zero keeps cap only" contract — `_wait_pre_cap`'s own `self._idle >
0` guard in `_watch` makes this belt-and-suspenders, not load-bearing.)

## Data flow

- **F1**: `_run_loop` → `_decide` (unchanged) → `_fingerprint_bound`
  (unchanged) → **new** `_budget_bound` reads `loop-metrics.jsonl` +
  `state.prd_budget_since` + the just-finished session's own cost from
  `last-session.log`, and may rewrite `decision["signal"]` from
  `"continue"` to `"park"` with `decision["park_site"] = "budget"` →
  `_append_metrics` (unchanged, records whatever `decision["signal"]`
  ended up) → `_act_branch` → `_act_park` reads `park_site` and stamps it
  into the marker → next loop iteration's Phase-0 park handler
  (`records.do_park`/`_finish_park`) reads the marker's `site`, calls
  `do_stall(site="budget")`, which resets `prd_budget_since` via
  `PER_PRD_RESET_FIELDS` and moves the PRD to `hold/` without touching
  `parks_consecutive`'s systemic-halt path.
- **F2**: `_launch_phase` → `_pre_enter` (new, runs `enter()` in-process,
  writes `state.loop_entry`) → the existing `_load_json` re-read inside
  `_launch_phase` now sees `next_phase` as `enter()` left it → `routing.route`
  → session spawns → the session's own first Bash call
  (`autopilot enter`) hits `_run_enter`'s new replay branch, which reads
  `state.loop_entry`, prints the stored JSON line, deletes the field, and
  returns — no second `enter()` run, one resume-row write total (the
  loop's own `_pre_enter` → `enter()` → `record_resume_row`).
- **F3**: `_decide`'s real dispatch (`_decide_from_state` then
  `_limit_wait_for`/`_decide_no_progress`) runs to completion exactly as
  today, incrementing `_died_retries`/`_net_retries` through its own
  normal path. Only then does the new `_apply_instant_exit` run, strictly
  before the `state_touched` counter reset, reclassifying
  `decision["signal"]` to `"instant_exit"` with the real outcome preserved
  in `decision["then"]` — the metrics row thus always shows what
  *actually* happened (`instant_exit`) with what the real dispatch
  *decided* riding beside it (`then`), and `_act_branch` unwraps `then`
  at act time to drive the correct branch.
- **F4**: `runner._run_session` wires `Watchdog(busy_fn=...)` →
  `Watchdog._watch` now polls every `poll_secs` from launch (not only
  past the cap) while `busy_fn()` is False and `activity_path` is silent
  for `idle_secs` → on an idle fire, `Watchdog.fired`/`fired_reason` are
  set exactly as the post-cap path already sets them → `runner.spawn`
  returns `SpawnResult(cap_fired=True, cap_reason="idle")` exactly as
  today → `Loop._launch`/`_killed_by` and `_metrics_line`'s
  `killed_by` field are unchanged consumers; the loop's decision table
  (unchanged per the Risks note below) treats a killed-and-touched
  session as `continue`, a killed-and-untouched one as the no-progress
  ladder (died/retry).

## Reuse inventory

- Ledger reading for F1's spend total: `cli/render_metrics.load_rows`
  (`cli/render_metrics.py`), already used by `loop._append_convergence`
  to read `loop-metrics.jsonl` rows — no new JSONL parser.
- Env-int/float parsing pattern: `routing._env_int` exists for ints;
  `budget_usd_for` needs a float, so it is a 6-line sibling in
  `loop_decision.py` rather than a reused helper (no existing float
  parser to share — `greps tried: rg "_env_float|env.get.*float" cli/`
  → nothing).
- Marker read/write: `records._parse_marker`/`do_park`/`do_stall` are
  reused as-is for F1's park path; only `_parse_marker`'s return shape and
  `_finish_park`'s branch are widened, per Interfaces above.
- `state.transaction`/`statectl.mutate`: reused for every new state write
  (`prd_budget_since`, `loop_entry`) — no new write primitive.
- Watchdog's existing `_activity_mtime`/poll loop shape
  (`_wait_past_cap`) is the template `_wait_pre_cap` mirrors; no new
  polling primitive, just the pre-cap twin of the existing one.
- `cli.enter.enter()` itself is reused unchanged as the loop's in-process
  call (F2) — the loop calls the exact function `_run_enter` already
  calls, with the exact same keyword contract, so there is only one
  Phase-0 implementation, called from two places.
- `greps tried` for F3: `rg "instant.exit|INSTANT_EXIT" cli/` → nothing
  (confirms no half-built prior art to extend instead of adding new).

## Alternatives considered

1. **F1 — track spend as a running counter in `state.json` instead of
   summing `loop-metrics.jsonl` per decision.** Smaller diff (no ledger
   read), but it duplicates data the ledger already holds durably, needs
   its own reset-on-park logic independent of `PER_PRD_RESET_FIELDS`, and
   drifts the moment a row is written to the ledger but the counter
   write fails (two writers, two failure windows). **Rejected**: the
   ledger is already the system of record for cost
   (`_metrics_line`/`last_result_field`), and `prd_budget_since` plus a
   sum-on-demand is one field, zero new write paths, and self-heals from
   any gap in the counter approach. **Chosen** (sum-on-demand) is also the
   smallest-diff option on this capability: no new persistent counter
   field at all beyond the timestamp fence already needed to scope the
   sum.
2. **F2 — have the session call `autopilot enter` as today, and have the
   loop only pre-*compute* the routing decision (model/effort) without
   running Phase 0 itself.** Smaller diff, but it does not address the
   PRD's actual complaint (every build session burns its first several
   calls running Phase 0 over again) — it would shave launch latency, not
   session calls. **Rejected**: it is the smallest diff but solves the
   wrong problem. **Chosen**: run `enter()` in the loop and replay the
   stored result — the full fix, and still bounded in size because it
   reuses `enter()` verbatim.
3. **F3 — detect instant-exit by wall time alone (drop the cost check).**
   Smallest diff (one field, no `last_result_field` call), but a short,
   $0 session that nonetheless wrote real state (a design doc, a few
   tasks) at low API cost would misclassify as instant_exit and log
   noise without changing the decision. **Rejected** in favor of the
   PRD's own `wall < 30s AND cost in (0, absent)` compound test, which
   the risk note ("Unknown cause of the 2-7s sessions") confirms is the
   intended signal — a session with billed cost is never "instant" by
   this PRD's own definition regardless of wall time.
4. **F4 — lower `poll_secs` only, and treat "silent since the cap started
   counting" the same way `_wait_past_cap` already does, without a
   separate pre-cap method.** This was tried first as the smallest diff
   (reuse `_wait_past_cap`'s loop unconditionally, starting its
   `ceiling_at` clock from `time.monotonic()` at launch instead of after
   the cap). **Rejected**: `_wait_past_cap`'s ceiling math
   (`ceiling_at = now + self._cap`, fired at `twice the cap`) is written
   assuming it starts running only once the cap has already elapsed;
   reusing it from launch would silently double the effective ceiling
   window and misname "ceiling" in its own log line ("twice the Ncap
   secs cap" becomes false). **Chosen**: a parallel, smaller
   `_wait_pre_cap` that fires only the "idle" reason (never "ceiling" —
   the cap itself is the ceiling for the pre-cap phase) and falls through
   cleanly into the unchanged post-cap method when the cap arrives with
   no idle fire.

## Risks & edge cases

- **`total_cost_usd` not cumulative** (noted in the PRD itself): `_budget_bound`
  sums every row's own `cost_usd` plus the live session's, so if
  `last_result_field` ever returns a per-turn delta instead of a running
  total, the guard *undercounts* (never overcounts) — parks late, not
  early. No corrective code added here; flagged for the metrics owner.
  Not yet confirmed cumulative-per-session against a real multi-result-event
  log (a session re-invoked by background-task notifications, per
  `last_result_field`'s own docstring); Phase 1's budget test adds one
  scripted case with such a re-invoked session so the sum is exercised
  against that shape, not just a single-result-event session.
- **Idle kill on a legitimately quiet reviewer**: covered by `busy_fn`
  (open `tool_use`, or a live `background_tasks_changed` task list) —
  `session_busy` is deliberately biased toward "busy" on any ambiguity
  (malformed line skipped, not failed; IOError → `True`).
- **Instant-exit and the died-retry counter**: `_apply_instant_exit` runs
  only after the real `_decide_no_progress`/`_decide_died` dispatch has
  already executed on the actual `decision` (not a copy), so
  `_died_retries` is incremented exactly once per instant-exit session,
  by that real dispatch — matching the named acceptance test ("3s, $0:
  retry first, park second, `_died_retries` not reset by the touched
  state").
- **`_pre_enter`'s except clause is narrowed to `state.StateError` only**
  (not a bare `Exception`), matching `enter()`'s own documented contract
  ("never raises except StateError on a corrupt state.json") — a real
  bug inside `enter()` (TypeError, a future regression) is deliberately
  NOT swallowed here, consistent with the codebase's "never silently
  swallow errors" convention; only the one documented, expected failure
  mode degrades to "launch normally".
- **Two writers at the `build` hand-off** (F2): the loop's `_pre_enter`
  and the session's `_run_enter` replay both read/write `state.json`, but
  never concurrently — `_pre_enter` finishes and the process exits before
  the child session is spawned, and the replay only ever runs inside that
  spawned session. The one-resume-row test pins this ordering.
- **A `park-requested` marker already pending when `_pre_enter` would
  otherwise run `enter()` for a `build` phase**: `_pre_enter`'s guard
  checks for the marker explicitly (`next_phase != "build" and not
  marker`) so a pending park is never skipped in favor of a wasted
  `enter()` call — `enter()` itself still runs (it is also how Phase 0's
  own park handling fires), and whichever PRD it then selects gets its
  own fresh `_pre_enter` computation.
- **Likely next changes this design should not box in**: (1) widening
  the budget guard to a whole-batch cap, not just per-PRD — `_budget_bound`
  reads `state.prd`/`state.prd_budget_since` exactly, so a batch-level
  variant is a sibling function, not a rewrite; (2) teaching
  `session_busy` to also treat an open Edit/Write as busy if a future
  idle-kill false-positive surfaces on a long single-tool-call session —
  the function's shape (one pass over the log, one boolean) absorbs a new
  signal as one more `elif kind == ...` branch; (3) a per-lane budget
  (fast-track/solo may want a smaller default than 300) — `budget_usd_for`
  takes `env` only today; a lane-aware variant would need `state` too, a
  signature widening this design does not pre-empt but does not block
  either.

## Test strategy outline

Per the PRD's own Phase 0/1/2 task list (already pinned to exact `pytest -k`
acceptance commands) — this design changes none of those commands or file
targets, only confirms each against the real code read above:

- `test_records_park.py -k budget_site`: a budget marker (`site: "budget"`)
  parks to `hold/`, the deferred record carries `site: "budget"`, and
  `batch.parks_consecutive` is 0 after (confirmed: `do_stall`'s existing
  `site != "wrapper_died"` branch already zeroes it).
- `test_watchdog.py -k session_busy`: fixtures for open `tool_use`, a
  closed pair, non-empty-then-empty `background_tasks_changed`, an
  unreadable file (→ `True`), malformed lines skipped.
- `test_enter.py -k budget_since`: set on first entry, kept on a
  same-PRD re-entry, refreshed on a different PRD — exercised through
  `_write_prd`'s injected `now`.
- `cli -k "test_budget_park_lands_prd_in_hold_and_next_prd_launches or
  test_budget_resets_after_resume_from_hold or test_budget_zero_disables"`:
  scripted multi-session loop runs via the existing `ScriptedSpawn` test
  harness (`test_loop.py`), asserting the park fires at the right
  cumulative cost and the next PRD launches clean.
- `test_loop_decision.py -k instant_exit`: the two named scenarios
  (retry-then-park without resetting `_died_retries`; usage-limit still
  waits even when instant).
- `test_watchdog.py -k "test_idle_kill_before_cap_when_silent_and_no_open_tool_use
  or test_no_idle_kill_while_tool_use_open or test_idle_zero_keeps_cap_only"`:
  small `idle_secs`/`cap_secs` against a real sleeping child process (the
  existing `Watchdog` tests already spawn real subprocesses for the
  cap/grace behavior, so no new fixture style is introduced).
- `cli -k "test_loop_entry_then_skill_entry_writes_one_resume_row or
  test_stale_loop_entry_is_dropped or test_pre_enter_failure_launches_without_entry
  or test_brief_entry_section"`: the first patches `enter_io.record_resume_row`
  and counts calls across `Loop._pre_enter` + `__main__.main(["enter", ...])`
  in one scripted sequence — exactly 1.
- `test_brief.py` stays green unchanged (golden `session-brief-build.md`
  has no `loop_entry`, so `_entry_lines` returns `[]` and the rendered
  brief is byte-identical).
- `rg -n "prd_budget_since|loop_entry" skills/run-autopilot/references/state-schema.md`
  and `rg -n "_AUTOPILOT_PRD_BUDGET_USD" skills/run-autopilot` (docs +
  code), plus the PRD's own named Phase 2 acceptance command,
  `uv run --no-project --with pytest python -m pytest -q
  skills/run-autopilot/cli/test_enter_prose.py
  skills/run-autopilot/cli/test_doc_contract.py` — the authoritative
  Phase 2 gate; the two `rg` checks above are a quick local proof, not a
  substitute for it (dispatch 2's finding: this design's test-strategy
  list omitted the PRD's own named files).
- Full `bash dev/bin/release-checks` exit 0, `FAIL 0`, as the PRD's own
  exit criterion.

## Review log

dispatch 1 (claude): cardinal-sin 0, blocker 2, non-blocker 1, question 1

- Blocking (fixed): F3's `_decide` rewrite silently dropped the real
  no-progress/limit-wait dispatch for any sub-30s, unbilled session —
  `_apply_instant_exit` now runs strictly after the unchanged real
  dispatch and only reclassifies its result.
- Blocking (fixed): F4's pre-cap idle polling only covered the window
  after the warning fired (the first, longer blind wait was untouched) —
  `_wait_pre_cap` now owns the whole `[0, cap]` window and folds the
  warning check into the same poll loop.
- Non-blocking (noted in Module placement): `_write_prd`'s `now`
  parameter and `_finish_park`'s pre-consult reordering are both larger
  wiring changes than their one-line table entries first suggested.
- Question (noted in Risks): `cost_usd`'s cumulative-per-session shape
  across a re-invoked session is unconfirmed; added to the Phase 1 test
  list rather than resolved here.

dispatch 2 (claude-fallback): cardinal-sin 0, blocker 2, non-blocker 2, question 1

- Blocking (fixed): `_pre_enter`'s local `state = _load_json(...)`
  shadowed the `state` module, so its own safety-net
  `except state.StateError` would have raised `AttributeError` instead
  of catching anything — renamed the local to `current` and narrowed the
  except to `state.StateError` alone.
- Blocking (fixed): the F3 rewrite had moved the `_net_retries`/
  `_died_retries` reset from its real pre-dispatch position to after the
  dispatch, which would zero out an increment the same call's dispatch
  just made — restored the reset to its unmoved, pre-dispatch position;
  `_apply_instant_exit` is strictly appended after everything that exists
  today and never touches the counters.
- Non-blocking (fixed): `_run_enter`'s replay branch ignored `args.prd`,
  so a manual `--prd X` during a stale same-PRD `loop_entry` would
  silently answer with the loop's result instead — gated the replay on
  `args.prd is None`.
- Non-blocking (fixed): the Test strategy section never named the PRD's
  own Phase 2 acceptance command (`test_enter_prose.py`/
  `test_doc_contract.py`) — added it as the authoritative check beside
  the two `rg` greps.
- Question (resolved, noted in Risks): confirmed the narrowed
  `except state.StateError` (not bare `Exception`) is deliberate, matching
  both `enter()`'s own contract and the codebase's error-swallowing
  convention.

dispatch 3 (claude-fallback, verification): cardinal-sin 0, blocker 0, non-blocker 2, question 0

- Verified against the real code (not just the Review log's own
  narrative): the `_pre_enter` local-rename fix resolves cleanly (no
  other `state` local in `loop.py` collides with the new module import;
  `cli/state.py` does define `StateError`); the F3 counter-reset is shown
  in the exact position it holds in the real, current `_decide`; and
  `args.prd is None` is true for every loop-driven path (no invocation in
  `references/phase-build.md` or the design's own `_pre_enter` sample
  passes `--prd`).
- Non-blocking (no action): confirmed `_run_enter`'s existing `in_loop`
  env read is untouched and irrelevant to the replay branch (replay
  returns before `enter.enter()` would read it).
- Non-blocking (no action): confirmed `_finish_park`'s current code has
  no early branch at all (always `site="wrapper_died"`, always consults
  `parks_consecutive` first), so the Module placement table's "bigger
  reshuffle than one branch" note is correctly calibrated, not
  understated.
- No cardinal sins, no new blockers.

result: ok
