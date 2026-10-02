# Design: 00192 Split cli/loop.py and test_loop.py under the file cap

PRD: `dev/local/prds/wip/00192-split-loop-py-and-its-tests-under-the-cap-v1.md`
Baseline commit at design time: `54b7706` (`loop.py` 1420 lines, `test_loop.py`
1714 lines, 82 test functions / 85 collected cases). Task 1 re-measures at
execution time; every line range below is against `54b7706` and is a locator,
not a contract - the symbol names are the contract.

## Architecture fit

`skills/run-autopilot/cli/` is the `autopilot` subcommand package and the sole
`state.json` mutator surface (capsule § Component Boundaries). `cli/loop.py` is
the loop driver behind `autopilot loop` / `autopilot review-once`
(`__main__.py:972-985`, `loop.Loop().run()` / `.run_once()`). Its dominant style
is module-level functions grouped by responsibility (`pause.py`, `runner.py`,
`convergence.py`, `usage_limit.py`, `watchdog.py`) plus one class, `Loop`
(lines 447-1418, 970 of the 1420 lines), that holds the injectable
collaborators and the per-loop counters.

The split keeps that shape: three new sibling modules, each holding the
module-level functions of one responsibility plus a mixin carrying the `Loop`
methods of that responsibility. `loop.py` keeps `Loop`'s constructor, counters,
plumbing, spawning, metrics, the run/run_once orchestration, `main`, and a
compat re-export block. Lower seams never import `cli.loop`.

The `/autopilot:work` style gate (step 5.65, `work/scripts/check_style_limits.py`)
flags any function over 50 lines whose span intersects an added hunk, and a new
file is one added hunk. Four of the methods that move are over 50 lines at
`54b7706` (`_decide_no_progress` 94, `_act_park` 67, `_decide` 52, `_register`
52; every other function in both files is 49 or under). Moving them as-is would
trip the gate in every seam commit and hand the fixer an unplanned split. So a
**seam 0 (trim)** commit first extracts six named helpers in place, in
`loop.py`, before any file moves; seams 1-4 then move bodies byte-for-byte from
the post-trim tree and the gate exits 0 on each.

Runtime note: the live batch driver on this host is the installed
`autopilot@0.5.1`/`0.5.2` cache, not this checkout (capsule § Key Invariants),
so the split cannot break the loop that is running it; only the checkout's test
suites exercise the new files until the next release.

## Module placement

Seam 0 edits `loop.py` in place (no new file): the six helper methods in
§ Interfaces "Seam 0 extractions" are added to `Loop`, and the four over-cap
methods shrink to call them. `test_loop.py` is untouched by seam 0.

New implementation files (all in `skills/run-autopilot/cli/`), holding code
moved verbatim from the post-seam-0 `loop.py` (line ranges cite `54b7706`
locators for the unchanged bodies):

| file | holds | est. lines |
|---|---|---|
| `loop_decision.py` | `_CONNECTION_FAIL` (80-84); the whole "small pure ports" block 94-216: `died_next`, `_tostring`, `pause_detail`, `_jq_or`, `fingerprint`, `plugin_drift`, `last_result_field`, `_mtime`, `_utcnow_iso`; `class DecisionMixin` with `_decide`, `_decide_from_state`, `_decide_no_progress`, `_decide_limit_wait`, `_decide_network_outage`, `_decide_died` (post-trim forms of 720-866), `_fingerprint_bound` (868-899) | ~360 |
| `loop_gates.py` | `DEFAULT_LOOPS_DIR` (70); the registry block 219-334: `_pid_alive`, `_child_pids`, `_pid_tagged`, `prune_registry`, `live_wrapper_pid`; `class GatesMixin` with `_memory_gate` (568-605), `_register`, `_write_registry_entry` (post-trim forms of 607-658), `_plugin_gate` (660-686), `_schema_gate` (688-717) | ~310 |
| `loop_act.py` | `PURGE_SCRIPT` (71-78); the drained-path block 337-416: `run_purge`, `_run_agoge_process`, `run_agoge`; `class ActMixin` with `_stop_on_marker` (974-991), `_act_paused` (993-1028), `_act_done` (1030-1065), `_act_park`, `_park_marker_pending` (post-trim forms of 1067-1133), `_halt` (1309-1313), `_act_continue` (1315-1337), `_act_branch` (1339-1384) | ~365 |

Edited: `loop.py` keeps docstring, `_API_PROBE_URL`, `_Terminated`,
`_read_memory_pressure`, `_probe_api`, and on `Loop`: `__init__`, `_int`,
`_repo_name`, `_teardown`, `_cleanup_orphans`, `_resolve_ap_dir`,
`_append_metrics`, `_append_convergence`, `run`, `run_once`, `_guarded`,
`_launch`, `_one_shot_phase`, `_run_once`, `_loop_gates`,
`_announce_and_launch`, `_launch_phase`, `_run_loop`; plus `main`. Est. ~540
lines after the three moves.

New test-side files:

| file | holds (moved from `test_loop.py @54b7706`) | est. lines |
|---|---|---|
| `loop_testutil.py` | `_CLOCK_START`, `_BEFORE_CLOCK` (49-50); `Recorder`, `FakeClock`, `ScriptedSpawn`, `write_state`, `write_log`, `terminal_step`, `noop_step`, `make_loop`, `_notified` (53-185); the autouse fixture `_no_real_drain_side_effects` (191-202; its patch target changes at seam 4, see Interfaces); `_spawn_tagged_incumbent` (1169-1190) | ~200 |
| `test_loop_decision.py` | pure-port tests 205-310 (15) + decision-table tests 446-682 (13) | ~375 |
| `test_loop_gates.py` | pause-marker tests 998-1036 (4) + plugin/memory/schema tests 1079-1164 (6) + registry tests (13, listed in Data flow) + `_spawn_forked_loop_shell` (1359-1384) | ~410 |
| `test_loop_act.py` | stand-down tests 1038-1077 (2) + the drained-path section 1599-1715 (6: five direct `run_agoge` tests + `test_drained_branch_runs_purge_and_agoge_with_the_count`) + `_fake_claude`, `_fake_claude_env_probe` | ~190 |
| `test_loop_exports.py` | NEW, nothing moved: the one new test `test_public_names_remain_importable_from_loop` (§ Interfaces "New test"). Its own module because `test_loop.py`'s autouse drain stubs replace `loop_act.run_agoge` / `run_purge` for every test there and would mask the identity check. Binds no fixture, imports nothing from `loop_testutil`. | ~35 |

Edited: `test_loop.py` keeps its docstring, the drained-happy-path tests
(313-444, 9), the metrics/convergence tests with their helpers `_metrics_rows`,
`_state_step`, `_write_review` (684-993, 9 functions / 12 cases),
`_REAL_CLEANUP_ORPHANS` + `test_cleanup_orphans_hups_a_tagged_ppid1_process`
(188, 1211-1247), `test_loop_drives_the_real_runner_spawn_end_to_end`
(1288-1332), `test_interrupt_tears_down_and_returns_130`,
`test_sigterm_translates_to_143`, `test_loop_verb_is_registered_in_the_cli`
(1532-1597). Est. ~630 lines. `test_loop_review_once.py`: one import line
changes from `cli.test_loop` to `cli.loop_testutil` (and the docstring sentence
naming the fixture source). `cli/golden/`: untouched.

Not touched: `__main__.py` (still `from cli import loop` / `loop.Loop()`),
`routing.py`, `records.py`, `state.py`, `test_routing.py` (calls
`Loop()._append_metrics`, which stays on `Loop`), prose files naming
`cli/loop.py` (`phase-review.md`, `SKILL.md`, `references/*`) - they remain true
because `loop.py` remains the driver. No CHANGELOG entry: pure refactor
(`rules/changelog.md`).

## Interfaces & contracts

### Seam 0 extractions (in `loop.py`, before any move)

Six new `Loop` methods; the four callers keep their names, signatures,
docstrings and every print/notify string. The helper bodies are the exact
statements lifted out; nothing else changes. Post-trim lengths in brackets.

```python
    def _decide(self, ap_dir: Path, ts_start: float) -> dict:          # [~34]
        ...unchanged through `decision["state_touched"] = state_touched`...
        state = _load_json(state_path) if decision["signal"] == "" else None
        if isinstance(state, dict):
            self._decide_from_state(decision, state, state_touched)

        if decision["signal"] == "":
            self._decide_no_progress(decision, ap_dir, state_path, ts_start)
        return decision

    def _decide_from_state(self, decision: dict, state: dict, state_touched: bool) -> None:   # [~22]
        """The readable-state rows of the table, in signal order."""
        # verbatim lines 749-767: prd/batch/phase_end/next, pause_detail, stall_reason,
        # then the paused / replan / done / continue ladder

    def _decide_no_progress(self, decision: dict, ap_dir: Path, state_path: Path, ts_start: float) -> None:   # [~25]
        """Branch 5: a stand-down is a pause, limit-hit is scheduling,
        network outage is infrastructure, anything else died."""
        # verbatim 778-783 (stand-down), then:
        reset = self._detect_limit(ap_dir / "last-session.log")
        if isinstance(reset, int):
            self._decide_limit_wait(decision, reset)
            return
        api_fail = last_result_field(ap_dir / "last-session.log", "result", error_only=True)
        if isinstance(api_fail, str) and _CONNECTION_FAIL.search(api_fail):
            self._decide_network_outage(decision, api_fail)
            return
        self._decide_died(decision, state_path)

    def _decide_limit_wait(self, decision: dict, reset: int) -> None:            # [~20]
        """A usage-limit hit is scheduling: wait inside the cap, else die."""
        # verbatim 787-802

    def _decide_network_outage(self, decision: dict, api_fail: str) -> None:     # [~35]
        """A connection failure: poll connectivity inside the retry budget, else die."""
        # verbatim 811-840

    def _decide_died(self, decision: dict, state_path: Path) -> None:            # [~26]
        """The died ladder: retry, park, or halt loud on a bootstrap."""
        # verbatim 843-866

    def _register(self, ap_dir: Path) -> int | None:                              # [~33]
        # verbatim 610-636, then:
        self._write_registry_entry(loops_dir, root, ap_dir)
        return None

    def _write_registry_entry(self, loops_dir: Path, root: Path, ap_dir: Path) -> None:   # [~23]
        """Atomic write of this loop's registry entry; a failed write runs
        unregistered, loud."""
        # verbatim 637-657

    def _act_park(self, decision: dict, ap_dir: Path) -> int | None:              # [~38]
        """None to relaunch (marker written or preserved); an exit code
        to halt."""
        marker = ap_dir / "park-requested"
        if marker.is_file():
            return self._park_marker_pending(marker)
        self._park_relaunches = 0
        # verbatim 1104-1133

    def _park_marker_pending(self, marker: Path) -> int | None:                  # [~33]
        """An unconsumed marker from the previous relaunch: halt when the
        relaunch budget or the stale age trips, else back off and relaunch."""
        # verbatim 1072-1102
```

Argument sufficiency (what each lifted block reads and writes, so the
signature above is complete):

| helper | reads | writes / returns |
|---|---|---|
| `_decide_from_state` | `decision`, `state`, `state_touched`, `pause_detail` | mutates `decision` in place; returns None |
| `_decide_limit_wait` | `decision`, `reset`, `usage_limit.wait_decision`, `self._clock`, `self._int`, `_dt` | mutates `decision`; the caller's `return` follows the call exactly where the inline block returned |
| `_decide_network_outage` | `decision`, `api_fail`, `self._int`, `self._net_retries`, `self._clock`, `self.err`, `self._probe`, `self._sleep` | increments `self._net_retries` on the retry path (same place as before); mutates `decision` |
| `_decide_died` | `decision["prd"]`, `state_path`, `died_next`, `self._died_retries`, `self._int`, `_load_json` | increments `self._died_retries` on the retry path; mutates `decision` |
| `_write_registry_entry` | `loops_dir`, `root`, `ap_dir`, `self.loop_pid`, `_utcnow_iso`, `json`, `self.err` | sets `self._reg` on success; prints the unregistered warning on `OSError`; `_register` then `return None` as before |
| `_park_marker_pending` | `marker`, `self._park_relaunches`, `_mtime`, `self._clock`, `self._int`, `self.err`, `self._notify`, `self._repo_name`, `self._sleep` | increments `self._park_relaunches`; returns `1` (halt) or `None` (relaunch after the backoff sleep), which `_act_park` returns unchanged |

No lifted block reads a local that is assigned earlier in its parent other
than the arguments listed, and none assigns a local the parent reads
afterwards (the parents' remaining code uses only `decision`, `state_path`,
`ap_dir`, `loops_dir`, `root`, `marker` and `self`).

Seam 0 gate expectation: `check_style_limits.py` exit 0 (every touched function
is 50 or under after the trim; the FILE rule does not fire because
`n - ins + dels` stays above 800, i.e. pre-existing debt).

### Mixin classes (new; exact names)

```python
# cli/loop_decision.py
class DecisionMixin:
    """Loop's decision table: _decide, _decide_from_state, _decide_no_progress,
    _decide_limit_wait, _decide_network_outage, _decide_died,
    _fingerprint_bound. Reads self._int, self._clock, self._sleep, self._probe,
    self._detect_limit, self.err, and the counters self._net_retries,
    self._died_retries, self._fp_prev, self._fp_repeats - all set by
    Loop.__init__ in cli/loop.py. Imports nothing from cli.loop."""

# cli/loop_gates.py
class GatesMixin:
    """Loop's preflight gates: _memory_gate, _register, _write_registry_entry,
    _plugin_gate, _schema_gate. Reads self._int, self._pressure, self._clock,
    self._sleep, self._notify, self._repo_name, self.env, self.err,
    self.loop_pid, self._reg, self._warned_schema. Imports nothing from
    cli.loop."""

# cli/loop_act.py
class ActMixin:
    """Loop's act branches: _stop_on_marker, _act_paused, _act_done, _act_park,
    _park_marker_pending, _halt, _act_continue, _act_branch. Reads self._int,
    self._clock, self._sleep, self._notify, self._repo_name, self._teardown,
    self.cwd, self.env, self.out, self.err, self.runner_bin,
    self._park_relaunches. Imports nothing from cli.loop."""
```

```python
# cli/loop.py
class Loop(GatesMixin, DecisionMixin, ActMixin):
    """(docstring unchanged)"""
```

Method bodies, names, signatures, docstrings and return values are moved
byte-for-byte from the post-seam-0 tree; nothing inside a moved body is edited.
No method name appears in more than one mixin, so MRO order is irrelevant.
Attributes the mixins read stay initialised in `Loop.__init__` exactly as at
`54b7706` (`_reg`, `_net_retries`, `_died_retries`, `_park_relaunches`,
`_fp_prev`, `_fp_repeats`, `_proc_slot`, `_warned_schema`).

### Module-level names per seam (moved verbatim, same signatures)

```python
# cli/loop_decision.py
_CONNECTION_FAIL: re.Pattern
def died_next(prd: str, retries: int, retries_max: int) -> str
def _tostring(value) -> str
def pause_detail(state: dict) -> str
def _jq_or(state: dict, key: str, default)
def fingerprint(state: dict) -> str
def plugin_drift(state: dict, installed: dict) -> str | None
def last_result_field(log_path: Path, field: str, error_only: bool = False)
def _mtime(path: Path) -> int | None
def _utcnow_iso() -> str

# cli/loop_gates.py
DEFAULT_LOOPS_DIR: Path                      # Path.home() / ".claude" / "autopilot-loops"
def _pid_alive(pid: int) -> bool
def _child_pids(pid: int) -> list[str]
def _pid_tagged(pid: int, tag_pid: int) -> bool
def prune_registry(loops_dir: Path, own_pid: int) -> None
def live_wrapper_pid(root: Path, loops_dir: Path) -> int | None

# cli/loop_act.py
PURGE_SCRIPT: Path                           # ~/.claude/skills/purge-devlocal/scripts/purge_devlocal.py
def run_purge(repo: Path) -> None
def _run_agoge_process(claude_bin: str, prompt: str, log_path: Path, cap: int, env: dict) -> int
def run_agoge(ap_dir: Path, batch: str, drained, env: dict, out, claude_bin: str = "claude") -> None
```

### Import statements per module (literal; acyclic; lower seams never import `cli.loop`)

The moved bodies reference `routing._env_int`, `runner.child_env`,
`pause.stand_down_reason`, `usage_limit.wait_decision`, `state_mod.load` as
module attributes and `_load_json`, `_mtime`, `_utcnow_iso`, `plugin_drift`,
`Watchdog` as bare names; the statements below preserve exactly that.

```python
# cli/loop_decision.py
from __future__ import annotations
import datetime as _dt
import json
import re
from pathlib import Path
from cli import pause, usage_limit
from cli.routing import _load_json

# cli/loop_gates.py
from __future__ import annotations
import json
import os
import re
import subprocess
from pathlib import Path
from cli import state as state_mod
from cli.loop_decision import _utcnow_iso, plugin_drift
from cli.routing import _load_json

# cli/loop_act.py
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

# cli/loop.py (after the moves)
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
# then the unchanged sys.path insert + `import _walk_up`
```

`loop.py` drops `from cli import state as state_mod` and `from cli.watchdog
import Watchdog` (no remaining user). Cycle check at `54b7706`: `pause.py`,
`usage_limit.py`, `routing.py`, `state.py`, `watchdog.py` import no `cli`
module; `runner.py` imports only `cli.watchdog`; `convergence.py` only
`cli.gate`.

### Compat re-exports in `cli/loop.py` (the pre-00192 public surface)

```python
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
```

`__all__` follows the `scripts/resume_target.py` shim idiom and keeps the
re-exports from being read as unused imports by a formatter pass. Identity
holds: `cli.loop.died_next is cli.loop_decision.died_next`, and so on for every
name in `__all__` except `Loop` and `main`. `_Terminated`,
`_read_memory_pressure`, `_probe_api`, `_API_PROBE_URL` stay defined in
`loop.py` (not re-exports).

The preserved surface is the set of names `loop.py` itself DEFINED at
`54b7706` (the PRD's "existing public name"), not the collaborator modules it
happened to import (`state_mod`, `Watchdog`, `convergence`, `pause`, ...).
Verified at `54b7706`: no consumer reads any of those through `cli.loop`
(`rg -o "loop_mod\.[a-zA-Z_]+|\bloop\.[a-zA-Z_]+"` over the CLI, its tests and
`scripts/` finds only `loop.Loop`, `loop_mod._Terminated`, `loop_mod._pid_tagged`,
`loop_mod.subprocess`, plus the string targets in the monkeypatch table). So
`loop.py` drops the two imports that lose their last user rather than carry
them as dead re-exports.

### Monkeypatch-target adaptations (the only test-body edits)

| test (new home) | at `54b7706` | after | changes at seam |
|---|---|---|---|
| `_no_real_drain_side_effects` (`loop_testutil.py`) | `monkeypatch.setattr(loop_mod, "run_purge", ...)`, `monkeypatch.setattr(loop_mod, "run_agoge", ...)` | `monkeypatch.setattr(loop_act, "run_purge", ...)`, `monkeypatch.setattr(loop_act, "run_agoge", ...)` | seam 1 keeps `loop_mod` (`from cli import loop as loop_mod` inside `loop_testutil.py`); seam 4 switches to `loop_act` |
| `test_drained_branch_runs_purge_and_agoge_with_the_count` (`test_loop_act.py`) | `loop_mod.run_purge` / `loop_mod.run_agoge` | `loop_act.run_purge` / `loop_act.run_agoge` | seam 4 |
| `test_pid_tagged_matches_a_tag_ending_a_non_final_ps_line_not_a_longer_pid` (`test_loop_gates.py`) | `loop_mod._child_pids`, `loop_mod.subprocess`, `assert loop_mod._pid_tagged(...)` x2 | `loop_gates._child_pids`, `loop_gates.subprocess`, `assert loop_gates._pid_tagged(...)` x2 | seam 3 |
| `test_sigterm_translates_to_143` (stays) | `loop_mod._Terminated(143)` | unchanged | - |
| `Loop._cleanup_orphans` patches (fixture, `test_loop_review_once.py`) | `monkeypatch.setattr(Loop, "_cleanup_orphans", ...)` | unchanged (`_cleanup_orphans` stays on `Loop`) | - |

Rationale: `_act_done` resolves `run_purge`/`run_agoge` as globals of the module
that defines it, so the patch must land on `cli.loop_act`; the same for
`_pid_tagged`'s `_child_pids` lookup in `cli.loop_gates`. Every other
`monkeypatch.setattr` in the suite targets `Loop`, `convergence`, or a
`subprocess` attribute and is unaffected.

### Test-module wiring

Every test module that runs `Loop.run()` binds the autouse fixture as a module
attribute so pytest registers it there (pytest discovers fixtures by scanning
the module namespace; the bound object is the same fixture definition, and its
`monkeypatch` parameter resolves as a builtin fixture; a bare unreferenced
import could be read as unused by a fix pass, and `check_split_hygiene.py`
exempts `_`-prefixed bindings, so the binding is an explicit assignment):

```python
from cli import loop_testutil
from cli.loop_testutil import (
    FakeClock,
    _notified,
    make_loop,
    noop_step,
    terminal_step,
    write_log,
    write_state,
)

# The autouse fixture registers by being a module attribute.
_no_real_drain_side_effects = loop_testutil._no_real_drain_side_effects
```

Each module imports only the harness names it uses; the fixture binding appears
in all four of `test_loop.py`, `test_loop_decision.py`, `test_loop_gates.py`,
`test_loop_act.py`. Import sources for the code under test:

- `test_loop_decision.py`: `from cli.loop_decision import died_next, fingerprint, last_result_field, pause_detail, plugin_drift` (by name, from the seam).
- `test_loop_gates.py`: `from cli import loop_gates` (patch targets and `loop_gates._pid_tagged`) and `from cli.loop_gates import live_wrapper_pid, prune_registry`.
- `test_loop_act.py`: `from cli import loop_act` (patch targets) and `from cli.loop_act import run_agoge` (by name, so the five direct `run_agoge` tests call the real function while the autouse stub sits on the module attribute, exactly as today's "Direct tests use the saved originals").
- `test_loop.py`: `from cli import loop as loop_mod` and `from cli.loop import Loop` (unchanged).
- `test_loop_exports.py`: `from cli import loop, loop_act, loop_decision, loop_gates` only; no `loop_testutil` import and no fixture binding (see the new test below for why).
- `test_loop_review_once.py` changes exactly its harness import and keeps its own `_no_real_orphan_sweep` fixture:

```python
from cli.loop_testutil import (
    _spawn_tagged_incumbent,
    make_loop,
    noop_step,
    write_log,
    write_state,
)
```

So the `cli.loop` re-exports are pinned by the identity test and the two
external consumers (`__main__.py`, `test_loop_review_once.py`'s `Loop`), not by
the relocated unit tests.

### New test (the re-export contract)

```python
# test_loop_exports.py
"""The cli.loop compat surface (PRD 00192): every name loop.py defined before
the split is still importable from cli.loop and is the same object its seam
module defines. Lives apart from test_loop.py on purpose: that module's autouse
drain stubs replace loop_act.run_agoge / run_purge for every test there and
would mask the identity checks below."""

from __future__ import annotations

from cli import loop, loop_act, loop_decision, loop_gates

_EXPECTED_ALL = {
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
}


def test_public_names_remain_importable_from_loop():
    assert set(loop.__all__) == _EXPECTED_ALL
    for name in loop.__all__:
        assert getattr(loop, name) is not None
    assert loop.died_next is loop_decision.died_next
    assert loop.fingerprint is loop_decision.fingerprint
    assert loop.last_result_field is loop_decision.last_result_field
    assert loop.pause_detail is loop_decision.pause_detail
    assert loop.plugin_drift is loop_decision.plugin_drift
    assert loop.live_wrapper_pid is loop_gates.live_wrapper_pid
    assert loop.prune_registry is loop_gates.prune_registry
    assert loop.DEFAULT_LOOPS_DIR is loop_gates.DEFAULT_LOOPS_DIR
    assert loop.run_agoge is loop_act.run_agoge
    assert loop.run_purge is loop_act.run_purge
    assert loop.PURGE_SCRIPT is loop_act.PURGE_SCRIPT
    assert issubclass(loop.Loop, loop_gates.GatesMixin)
    assert issubclass(loop.Loop, loop_decision.DecisionMixin)
    assert issubclass(loop.Loop, loop_act.ActMixin)
```

(16 assert lines; three separate `issubclass` calls because a tuple argument
is an OR; the `__all__` set check is what catches a re-export silently dropped
from the list while its module attribute survives.)

### Baseline artifacts (task 1 writes; every seam commit re-checks)

Directory `dev/local/tmp/00192-baseline/`:

- `collect.txt`: the node ids from `uv run --no-project --with pytest --with rich --with textual python -m pytest --collect-only -q skills/run-autopilot/cli`, one per line (baseline: 1197 passed at 00191 close; exact count re-measured).
- `loop-collect.txt`: the same for `test_loop.py` + `test_loop_review_once.py` alone (baseline 85 + 10 = 95 ids).
- `asserts.txt`: every line of `test_loop.py` matching `^\s*assert\b`, leading whitespace stripped, in file order (the assertion inventory).
- `golden.sha256`: `shasum -a 256` over the 10 files under `skills/run-autopilot/cli/golden/` (recursive).
- `sizes.txt`: `wc -l` of `loop.py`, `test_loop.py`, `test_loop_review_once.py`, `__main__.py`, `test_state.py`.
- `bodies.py` + `bodies-<stage>.txt`: a ~12-line script that parses the given files with `ast`, and for every `FunctionDef`/`AsyncFunctionDef` (methods keyed by bare name, module functions likewise) prints `name<TAB>sha256(<source segment>)` sorted by name, where the segment runs from the first decorator line when the node has one (`node.decorator_list[0].lineno`) else the `def` line, through `node.end_lineno` - so a dropped `@pytest.fixture(autouse=True)` or `@pytest.mark.parametrize` changes the hash too. The segment is exact bytes, comments included, so a reflowed or edited body changes its hash; methods keep their 4-space indent across the move (class `Loop` -> class `*Mixin`), so no normalisation is needed. Run it once on `loop.py` at the task-1 HEAD (`bodies-base.txt`) and again right after seam 0 on `loop.py` (`bodies-trim.txt`). `bodies-trim.txt` is the byte-for-byte reference for seams 2-4.
- `test-bodies-base.txt`: the same script over `test_loop.py` at the task-1 HEAD - every test function, helper, fixture and `ScriptedSpawn.__call__` etc. keyed by bare name. This is the per-test ownership record `asserts.txt` cannot give (a multiline assert's continuation lines, and which test holds which assert); the two artifacts are checked together.

Equivalence rule after each seam commit (S0-S4) and at the end:

| check | S0 trim | S1 harness | S2 decision | S3 gates | S4 act |
|---|---|---|---|---|---|
| 1. `collect.txt` node ids, path stripped to `::name[param]`, as a multiset | identical | identical | identical | identical | identical + `test_public_names_remain_importable_from_loop` (in `test_loop_exports.py`) |
| 2. `assert` lines (whitespace-stripped multiset) across exactly `test_loop.py`, `test_loop_decision.py`, `test_loop_gates.py`, `test_loop_act.py` (NOT `test_loop_review_once.py` or `test_loop_exports.py`: neither is in the baseline) | identical | identical | identical | identical with two substitutions (`assert loop_mod._pid_tagged(999, 4321) is True` -> `assert loop_gates._pid_tagged(999, 4321) is True`, `assert loop_mod._pid_tagged(999, 432) is False` -> `assert loop_gates._pid_tagged(999, 432) is False`) | same two substitutions |
| 2b. `bodies.py` over `loop_testutil.py` + the four inventory test files vs `test-bodies-base.txt`, keyed by bare name | identical | identical | identical | identical except `test_pid_tagged_matches_a_tag_ending_a_non_final_ps_line_not_a_longer_pid`, whose new hash must equal the baseline segment with the token `loop_mod` -> `loop_gates` substituted and nothing else (the script takes `--subst loop_mod=loop_gates`, a whole-word `re.sub` applied before hashing, so both sides are compared after the one allowed rename) | additionally `_no_real_drain_side_effects` and `test_drained_branch_runs_purge_and_agoge_with_the_count`, each equal to its baseline segment under `--subst loop_mod=loop_act`; nothing else |
| 3. `shasum -a 256 -c golden.sha256` | pass | pass | pass | pass | pass |
| 4. suite `uv run --no-project --with pytest --with rich --with textual python -m pytest -q skills/run-autopilot/cli` | baseline count | baseline count | baseline count | baseline count | baseline + 1 |
| 5. `bodies.py` over `loop.py` + `loop_decision.py` + `loop_gates.py` + `loop_act.py` (whichever exist) vs `bodies-trim.txt` | (S0 vs `bodies-base.txt`: every name outside `_decide`, `_decide_no_progress`, `_register`, `_act_park` identical; those four changed; six new names present) | identical | identical | identical | identical |
| 6. `rg -c "^_no_real_drain_side_effects = loop_testutil._no_real_drain_side_effects$"` over `test_loop*.py` | - | 1 | 2 | 3 | 4 (and 0 in `test_loop_exports.py`, 0 in `test_loop_review_once.py`) |
| 7. `python3 -c "import cli.loop, cli.loop_decision, cli.loop_gates, cli.loop_act"` from `skills/run-autopilot` (import smoke) | - | - | partial (no gates/act yet) | partial | pass |
| 8. `check_style_limits.py` (the work skill's own step 5.65) | exit 0 | exit 0 | exit 0 | exit 0 | exit 0 |
| 9. static import-graph check: `rg -n "^from cli\.loop\b|^from cli import .*\bloop\b|^import cli\.loop\b" skills/run-autopilot/cli/loop_decision.py skills/run-autopilot/cli/loop_gates.py skills/run-autopilot/cli/loop_act.py` prints nothing (no seam imports the driver), and `rg -n "^from cli\.loop_(gates|act) import" skills/run-autopilot/cli/loop_decision.py skills/run-autopilot/cli/loop_gates.py` prints nothing (no upward edge among the seams) - a cycle that happens to import cleanly is caught here, not by check 7 | - | - | pass | pass | pass |

Final only: `wc -l` of `loop.py`, `loop_decision.py`, `loop_gates.py`,
`loop_act.py`, `loop_testutil.py`, `test_loop.py`, `test_loop_decision.py`,
`test_loop_gates.py`, `test_loop_act.py`, `test_loop_exports.py` each `< 800`;
`bash dev/bin/release-checks` exits 0 (it runs the registry, prose, custody,
fast-track and policy suites - none of `test_loop*.py` - so it is the
unrelated-regression net, not split evidence); `test_loop_review_once.py` 10
cases pass.

## Data flow

Runtime data flow is unchanged: `__main__.py` -> `Loop().run()` ->
`_run_loop` (loop.py) -> `_memory_gate` / `_loop_gates` (GatesMixin +
loop.py) -> `_launch_phase` (loop.py) -> `_decide` + `_fingerprint_bound`
(DecisionMixin) -> `_append_metrics` (loop.py) -> `_act_branch` (ActMixin)
-> back to the top or exit. `run_once` -> `_run_once` (loop.py) uses
`_memory_gate`, `_register`, `_plugin_gate`, `_schema_gate` (GatesMixin),
`_decide` (DecisionMixin), `_append_metrics` (loop.py). Cross-mixin calls
are `self.` attribute lookups on the one `Loop` instance, resolved by MRO,
identical to the single-class layout. The seam-0 helpers are called only by
the method they were lifted from, with the same arguments the inline code
read, so every branch, print, notify and counter update happens in the same
order.

Test data flow: `make_loop` (loop_testutil) builds a `Loop` with
`ScriptedSpawn`; each test module drives `lp.run()` / `lp.run_once()` and
reads `lp._test[...]`; the autouse fixture bound in each module stubs
`loop_act.run_purge`, `loop_act.run_agoge`, `Loop._cleanup_orphans`.

Seam commit order (each leaves the suite green, inventories mapped, goldens
identical, style gate exit 0; intermediate `loop.py` sizes may still exceed
800):

0. **trim**: the six extractions in `loop.py`; tests untouched. (`loop.py` -> ~1450.)
1. **harness**: `loop_testutil.py` out of `test_loop.py`; `test_loop.py` and `test_loop_review_once.py` import from it; the fixture still targets `loop_mod`. No implementation change. (`test_loop.py` -> ~1560.)
2. **decision**: `loop_decision.py` + `DecisionMixin`; `test_loop_decision.py` (28 tests). `loop.py` -> ~1120. Interim import in `loop.py` at this seam: `from cli.loop_decision import DecisionMixin, _mtime, _utcnow_iso, died_next, fingerprint, last_result_field, pause_detail, plugin_drift` - `_utcnow_iso` because `_register` is still in `loop.py` until seam 3, `_mtime` because `_act_park` is until seam 4, `plugin_drift` because `_plugin_gate` is until seam 3 (and it stays as a re-export). `_CONNECTION_FAIL` leaves with `_decide_no_progress` in this same commit.
3. **gates**: `loop_gates.py` + `GatesMixin`; `test_loop_gates.py` (23 tests); the `_pid_tagged` test retargets. `loop.py` -> ~850. `loop.py` drops `_utcnow_iso` from the seam-2 import (its last caller moved) and drops `state_mod`; `DEFAULT_LOOPS_DIR`, `prune_registry`, `live_wrapper_pid` leave with `_register` in this same commit and come back as re-exports.
4. **act**: `loop_act.py` + `ActMixin`; `test_loop_act.py` (8 tests); the fixture and the drained-branch test retarget to `loop_act`; the finished `__all__` and `test_loop_exports.py` (1 test) land here. `loop.py` -> ~540, `test_loop.py` -> ~630. `loop.py` drops `_mtime` (last caller moved) and `Watchdog`; `PURGE_SCRIPT`, `run_purge`, `run_agoge` leave with `_act_done` in this same commit and come back as re-exports; the import block now matches § Import statements exactly.

Registry tests moving to `test_loop_gates.py` (13):
`test_duplicate_loop_guard_refuses_a_second_loop`,
`test_registry_entry_written_and_removed_at_teardown`,
`test_registry_entry_carries_the_tracon_contract_shape`,
`test_own_stale_registry_entry_is_overwritten_not_refused`,
`test_registry_write_failure_runs_unregistered_loud`,
`test_loops_dir_is_propagated_to_session_children`,
`test_prune_keeps_a_loop_shell_tagged_only_on_its_child`,
`test_prune_removes_dead_untagged_and_malformed_entries`,
`test_live_wrapper_pid_ignores_an_alive_but_untagged_pid`,
`test_prune_spares_an_unreadable_entry_and_it_resolves_once_readable`,
`test_prune_deletes_an_entry_with_invalid_utf8_bytes_without_raising`,
`test_prune_deletes_a_utf16_encoded_entry_even_when_its_pid_is_live_and_tagged`,
`test_pid_tagged_matches_a_tag_ending_a_non_final_ps_line_not_a_longer_pid`.

Pause-marker tests moving to `test_loop_gates.py` (4):
`test_pause_marker_stops_before_any_spawn`,
`test_pause_exit_stamps_the_stop_for_the_observer`,
`test_pause_exit_names_autoclaude_as_the_resume`,
`test_a_resumed_loop_clears_the_pause_stamp`.

Stand-down tests moving to `test_loop_act.py` (2):
`test_stand_down_marker_pauses_without_retry_or_park`,
`test_empty_stand_down_marker_reads_as_operator_pause`.

Old-to-new count check: 15 + 13 (decision) + 4 + 6 + 13 (gates) + 2 + 6 (act)
+ 9 + 9 + 5 (stay) = 82 functions; parametrized cases add 3, total 85; plus 1
new in `test_loop_exports.py` = 86 in the loop files, 96 with
`test_loop_review_once.py`.

## Reuse inventory

- `skills/run-autopilot/cli/custody_testutil.py`, `custody_prose_testutil.py` - the pack's precedent for a shared, non-collected test harness module beside the tests; `loop_testutil.py` follows it (name and placement; note `work_routing.is_test_path` treats it as production, as it does the custody ones).
- `skills/run-autopilot/scripts/resume_target.py` - the `__all__` re-export shim idiom ("the same objects, not copies"); `loop.py`'s compat block copies it.
- `skills/work/scripts/check_style_limits.py` (`function_limit=50`, `file_limit=800`, hunk-intersection rule) and `skills/work/references/style-gate.md` (the exit-1 fixer ladder) - why seam 0 exists; the final size check uses `wc -l` directly because that gate scopes to a diff range.
- `cli/pause.py`, `cli/usage_limit.py`, `cli/watchdog.py` - already-extracted loop collaborators; the new seams import them, never re-implement.
- Mixin / multi-base precedent: nothing found, greps tried: `rg -n "Mixin|class .*\(.*,.*\):" skills/run-autopilot/cli skills/run-autopilot/scripts/tracon` (control `rg -n "^class "` lists 34 classes, all single-base or exception subclasses). The mixin is new to the pack; see Alternatives for why it beats the delegating-wrapper shape.
- Inventory / hashing helper: nothing found, greps tried: `rg -ln "hashlib|shasum|sha256sum|collect-only" skills/run-autopilot dev/bin` (control `rg -ln "golden" skills/run-autopilot/cli` lists 13 test files). Task 1 uses `shasum -a 256`, `pytest --collect-only -q` and the 12-line `bodies.py` directly.

## Alternatives considered

1. **Smallest diff: move only module-level functions** (pure ports, registry, drained helpers, ~320 lines) into siblings, leave `Loop` whole. Rejected: `loop.py` lands at ~1100 lines, still over the cap; the class alone is 970 lines.
2. **Mixins (chosen)**: cut the method blocks into three mixin classes, `Loop` inherits all three, ~15 lines of glue. Every method keeps its name on `Loop`, so `Loop._cleanup_orphans` / `lp._register` / `lp._append_metrics` patches and calls in `test_loop*.py`, `test_routing.py` are untouched; bodies move byte-for-byte. Cost: mixins read attributes they do not define (documented in each class docstring); one convention new to the pack.
3. **Module functions with thin delegating methods** (`def _decide(self, ap_dir, ts): return loop_decision.decide(self, ap_dir, ts)`): same acyclic layout, matches the pack's function-first style, but adds ~13 two-line wrappers (~40 lines) and doubles every method's name; a wrapper that drops a kwarg is the kind of drift a byte-for-byte move cannot have. Rejected for diff size and drift surface.
4. **Collaborator objects** (`Gates`, `Decider`, `Actor` injected into `Loop`): a real redesign of the counters (`_net_retries`, `_died_retries`, `_park_relaunches`, `_fp_*`) that tests poke directly (`lp._net_retries = 3`, `lp._died_retries == 0`). Out of the PRD's behaviour-preserving scope.

Style-gate alternative to seam 0: let each seam's gate exit 1 and have the
fixer split the four functions. Rejected: the fixer would improvise a split
of the 94-line six-branch `_decide_no_progress` with no design behind it, in a
commit the seam task never planned, and the byte-for-byte artifact could not
tell that drift from a bug. Seam 0 designs the same six extractions up front,
in one small reviewable commit, and leaves the fixer nothing to do.

Test-side alternative: a `cli/conftest.py` carrying the autouse fixture. Rejected: it would apply the `run_purge`/`run_agoge`/`_cleanup_orphans` stubs to every module under `cli/`, a behaviour change for `test_routing.py` and `test_loop_review_once.py`; binding the fixture per module keeps the scope exactly where it is today.

## Risks & edge cases

- **Silent no-op patches.** A test that still patches `loop_mod.run_agoge` after `_act_done` moves would pass while shelling out to the real agoge. Mitigation: the fixture and its one direct sibling are retargeted in the same commit as the move (seam 4), and `test_drained_branch_runs_purge_and_agoge_with_the_count` fails loudly (`agoges == []`) if the target is wrong.
- **Fixture not in scope.** A module that forgets the `_no_real_drain_side_effects` binding stays green while running the real orphan sweep (`pgrep`/`ps` on the live table), the real `purge_devlocal.py --apply` on a tmp repo and a real `claude` spawn attempt on a drain. Mitigation: equivalence check 6 counts the bindings (1/2/3/4 per seam).
- **Formatter reflow on new files.** loupe reflows edited `.py` files at turn end (memory `project-loupe-reflows-edited-py-files-at-turn-end`), and `git checkout --` cannot restore an untracked file. Every new file is `git add`-ed in the same turn it is written (the index snapshot precedes loupe's pass), reflowed hunks are reverted with `git checkout -- <path>`, then committed; check 5 (`bodies`) and check 2 (`asserts`) catch a reflow that slipped through.
- **Import order.** `loop_gates` imports `loop_decision`; `loop_act` imports `loop_decision`; `loop` imports all three. A future edit that makes `loop_decision` import `loop_gates` creates a cycle; the docstring of each seam names its allowed imports.
- **Prose that names `cli/loop.py`** (`phase-review.md`, pinned by `test_review_prompt_contracts.py`; `SKILL.md`; `references/*`) stays correct: `Loop._append_metrics` remains in `loop.py`.
- **Intermediate over-cap.** After seams 2 and 3 `loop.py` is still above 800; the PRD allows it, and the FILE rule of `check_style_limits.py` reads it as pre-existing debt (`n - ins + dels > 800`), so no per-commit gate trips.
- **Likely next changes and whether the split boxes them in:** 00199 (sleep-limit and stand-down guard rails) edits `_decide_limit_wait` / `_decide_no_progress` / `_act_continue`: now in `loop_decision.py` / `loop_act.py`, each with room, and the limit-wait branch already has its own method. 00200 (hand off on usage headroom, decouple the session model) edits `_launch_phase` / routing: stays in `loop.py` (~540 lines, room). 00196 (guard review-phase rework sessions) touches `_one_shot_phase` / `_loop_gates`: `loop.py`. None needs a fourth seam.
- **Unrelated oversized modules** (`__main__.py` 1099, `test_state.py` 814) stay over the cap by PRD non-goal; the final size check names only the ten files above.
- **Autouse stubs vs identity checks.** Any test that compares `loop.run_agoge` / `loop.run_purge` by identity must run without the drain stubs, which is why `test_loop_exports.py` exists and binds no fixture; a future move of that test into a stubbed module would fail loudly (`is` against a lambda), not silently.

## Test strategy outline

- **Task 1 (baseline):** write the baseline artifacts (`collect.txt`, `loop-collect.txt`, `asserts.txt`, `golden.sha256`, `sizes.txt`, `bodies.py`, `bodies-base.txt`, `test-bodies-base.txt`); assert the reviewed map is exact by listing every `def test_` / `def _helper` / class in `test_loop.py` and every `def` / method in `loop.py` against the Module placement tables (a symbol with no destination fails the task); run the CLI suite once green before any change.
- **Seam 0 (trim):** suite green; check 5 against `bodies-base.txt` shows exactly the four changed names and six new names; write `bodies-trim.txt`; style gate exit 0.
- **Per seam commit 1-4:** the row of the equivalence table; `git diff --stat` shows only the seam's files.
- **Seam 4 adds the one new test** `test_loop_exports.py::test_public_names_remain_importable_from_loop` (the `__all__` set, identity of every re-exported name, the three mixin bases). It fails on the pre-split `loop.py` (no `loop_act` module, no `__all__`), which is the regression it guards: a re-export silently dropped from `__all__` or rebound to a copy.
- **Final gate:** `wc -l` on the ten files `< 800`; import smoke (check 7) passes; `bash dev/bin/release-checks` exit 0; the fixture-loop integration tests (`test_continue_relaunches_until_drain`, `test_convergence_row_fields_come_from_state_and_review_files`, `test_loop_drives_the_real_runner_spawn_end_to_end`) still pass unmodified in `test_loop.py`; `test_loop_review_once.py` 10 cases pass with its new import.

## Review log

dispatch 1 (claude): cardinal-sin 0, blocker 1, non-blocker 6, question 3

- blocker (fixed): the work skill's style gate flags the four >50-line methods (`_decide_no_progress` 94, `_act_park` 67, `_decide` 52, `_register` 52) in every seam's new-file hunk and runs an unplanned fixer split. Fix: seam 0 (trim) with six designed extractions (`_decide_from_state`, `_decide_limit_wait`, `_decide_network_outage`, `_decide_died`, `_write_registry_entry`, `_park_marker_pending`) before any move; byte-for-byte now measured from the post-trim tree.
- non-blocker (folded into the fix, same sections rewritten): no artifact verified the byte-for-byte promise on the moved implementation -> `bodies.py` AST map, check 5.
- non-blocker (folded): import-graph rows were name lists, not statements; `loop_act` bodies use `routing._env_int` / `runner.child_env` as module attributes, and `loop.py` still needs `_load_json` -> literal import statements per module.
- non-blocker (folded): `issubclass(Loop, (A, B, C))` is an OR -> three asserts, 14 lines.
- non-blocker (folded): equivalence rule 2's `test_loop_*.py` glob pulled in `test_loop_review_once.py`; "at the end" was wrong; substitutions apply from seam 3 -> the four files named, per-seam table.
- non-blocker (folded): a forgotten fixture binding passes green with real side effects -> check 6 counts bindings per seam. The `make_loop` guard-flag alternative was not taken (adds harness behaviour).
- non-blocker (folded): `git checkout --` cannot restore an untracked new file after a loupe reflow -> `git add` in the writing turn, revert, commit.
- question (folded): the fixture's seam-1 target -> "changes at seam" column in the monkeypatch table.
- question (folded): `__main__.py --help` never imports `cli.loop`; `release-checks` runs no `test_loop*` -> import smoke check 7; release-checks kept as the unrelated-regression net only.
- question (folded): import source for moved public names in the new test modules -> stated per module; `test_loop_act.py` binds `run_agoge` by name so the direct tests keep the real function.

dispatch 2 (codex): cardinal-sin 0, blocker 1, non-blocker 2, question 2

- blocker (fixed): the identity test sat in `test_loop.py`, whose autouse fixture stubs `loop_act.run_agoge` / `run_purge` for every test, so `loop.run_agoge is loop_act.run_agoge` would compare the original against the stub and fail. Fix: the test moves to its own `test_loop_exports.py` with no fixture binding; the file list, counts, size list and check 6 updated.
- non-blocker (folded into the same fix): the test never inspected `__all__`, so a dropped entry passed -> `assert set(loop.__all__) == _EXPECTED_ALL` plus a resolve loop; 16 assert lines.
- non-blocker (folded, same artifact rewritten): `ast.dump` ignores comments and formatting, so the "byte-for-byte" and reflow-detection claims were untrue of it -> `bodies.py` hashes `ast.get_source_segment` (exact bytes, comments included; methods keep their 4-space indent across the move).
- question (folded): `test_drained_branch_runs_purge_and_agoge_with_the_count` read as double-booked because the wiring text said "six direct `run_agoge` tests" -> corrected to five direct tests plus that one; its single destination is `test_loop_act.py`.
- question (folded): why `state_mod` / `Watchdog` are not re-exported -> the preserved surface is defined as the names `loop.py` defined at `54b7706`; the verified-no-consumer `rg` is recorded under Compat re-exports.

dispatch 3 (codex): cardinal-sin 0, blocker 0, non-blocker 1, question 1

- non-blocker (folded, one more run of the same script): `asserts.txt` misses multiline-assert continuation lines and cannot say which test owns an assertion -> `test-bodies-base.txt` (per-function source hashes over the test side) and check 2b, with the three retargeted functions as the only allowed differences.
- question (folded): interim helper imports between seams were unspecified (`_register` still in `loop.py` at seam 2 needs `_utcnow_iso`; `_act_park` needs `_mtime` until seam 4) -> the per-seam import changes are now written into the Data flow seam list.
- engagement re-run (the two findings above were under the 3-finding floor): 1 non-blocker, 1 question, 5 section-anchored "checked" entries (Import statements, Data flow seam imports, Monkeypatch table + wiring, Module placement, Cardinal sins) - engaged, not WEAK.
  - non-blocker (folded, same artifacts): check 2b exempted the three retargeted test functions wholesale -> compared under a whole-word `--subst loop_mod=<seam>`; function hashes excluded decorators -> the segment now starts at the first decorator; a cycle that imports cleanly escaped check 7 -> check 9, a static `rg` over the seam files' import lines.
  - question (answered in place): seam 0's equivalence could not be judged from line ranges alone -> an argument-sufficiency table under "Seam 0 extractions" lists what each lifted block reads, writes and returns, and states that no lifted block shares a local with its parent beyond the listed arguments.
