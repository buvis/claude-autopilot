"""cli/routing.py - per-phase model/effort/cap routing (PRD 00106).

Ports the wrapper's launch-model case table and
`_autopilot_build_model`/`_autopilot_build_target` verbatim
(development.plugin.bash; contract pinned by
test_autoclaude_build_model.sh, re-expressed in cli/test_routing.py).

Build routes per-PRD (PRD 00076): Sonnet unless a promotion signal
fires. The absent phase is a BUILD launch (a fresh batch has no
state.json and resumes at the build gate). A genuinely unknown non-empty
phase falls to Opus xhigh: fail expensive, never fail dumb. A fresh
review runs on Opus, at effort xhigh on cycle 1 and high on cycle 2 and
later; a rework resume (the cycle's review file on disk and unfinished
`rework_task_ids`, PRD 00207) takes the queued tasks' highest tier
instead, Sonnet unless one is opus or fable; `_AUTOPILOT_EFFORT_REVIEW`
forces one effort on every cycle and `_AUTOPILOT_EFFORT_REVIEW_RERUN`
sets the rerun value; finalize (done) is mechanical rendering - Sonnet at
medium.

The `[1m]` suffix is load-bearing: autopilot_context_cap_hook.USAGE_CAP
(500K) is sized for a 1M window, so every launch model here must carry
it.

Promotion decay (PRD 00111): recomputed from scratch on EVERY relaunch,
no stored latch, so a signal that clears stops promoting by
construction. The loop-metrics tail is deliberately NOT an input -
00111 retired signal 6 (repeat build session), and restoring that read
in any form is the decay regression.

`session_model` (PRD 00200) is parsed with the wrapper's own line grammar,
NOT cli/frontmatter.py: that module's Phase-0 contract caps at 22 head
lines and strips delimiter whitespace, neither of which this signal ever
did. It replaced `default_model` as signal 1: that key floors the per-task
tier for /plan-tasks and no longer buys an opus orchestrator.
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

OPUS = "claude-opus-5[1m]"
SONNET = "claude-sonnet-5[1m]"

_SESSION_MODEL_RE = re.compile(
    r"^[ \t]*session_model[ \t]*:[ \t]*(?:\"(opus|sonnet)\"|'(opus|sonnet)'|(opus|sonnet))[ \t]*$",
)
_TRAILING_COMMENT = re.compile(r"[ \t]+#.*$")
_PRD_GLOB = "[0-9][0-9][0-9][0-9][0-9]-*"


@dataclass(frozen=True)
class Route:
    model: str
    effort: str
    cap_secs: int


def _env_int(env: dict, key: str, default: int) -> int:
    raw = env.get(key)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def build_target(prds_dir: Path) -> Path | None:
    """The lowest 00XXX- PRD file in wip/, else in backlog/, else None.

    NEVER state.prd, which between PRDs still names the one that just
    finished. done/ and hold/ are not candidates.
    """
    for sub in ("wip", "backlog"):
        try:
            candidates = sorted((prds_dir / sub).glob(_PRD_GLOB))
        except OSError:
            candidates = []
        for path in candidates:
            if path.is_file():
                return path
    return None


def _frontmatter_session_model(prd_path: Path) -> str | None:
    """Signal 1: the value of a real (uncommented) `session_model` key in
    the LEADING frontmatter block only - `"opus"` or `"sonnet"` - else None.

    The wrapper's awk grammar verbatim: line 1 must be exactly `---` (no
    whitespace tolerance), the scan stops at the next exact `---`, a
    trailing comment needs whitespace before its `#` (YAML semantics:
    `opus#suffix` is the scalar value, `opus  # rationale` is opus), and
    the value must be exactly opus or sonnet, bare or matched-quoted.
    """
    try:
        lines = prd_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    if not lines or lines[0] != "---":
        return None
    for line in lines[1:]:
        if line == "---":
            return None
        match = _SESSION_MODEL_RE.match(_TRAILING_COMMENT.sub("", line))
        if match:
            return next(group for group in match.groups() if group)
    return None


def _load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _state_signals_fire(state_path: Path, target: str) -> bool:
    """Signals 2/3a/4, all guarded on state.prd being the target: a
    replan, a live stall, or a fired cap rotation. Signals 2 and 4 are
    cleared by Phase 9 step 10 at PRD completion; 3a clears when
    /run-autopilot resolves the stall."""
    state = _load_json(state_path)
    if not isinstance(state, dict) or state.get("prd") != target:
        return False
    replan = state.get("replan_count") or 0
    rotations = state.get("cap_rotations") or []
    return (
        (isinstance(replan, int) and replan > 0)
        or state.get("stall_reason") is not None
        or (isinstance(rotations, list) and len(rotations) > 0)
    )


def _ledger_has_key(ledger_path: Path, target: str) -> bool:
    """Signal 5: a rescue-ledger KEY for the target, any status. Sticky
    by design (a human approved that rescue). A key lookup, never a
    substring scan - the target appearing as a VALUE in another PRD's
    entry must not fire."""
    ledger = _load_json(ledger_path)
    return isinstance(ledger, dict) and target in ledger


def _deferred_stall_fires(deferred_dir: Path, target: str) -> bool:
    """Signal 3b: a type:"stall" item naming the target in the 2 NEWEST
    *-deferred.json files BY FILENAME (batch ids are minted in order;
    mtimes are not - a .bak restore or late append rewrites them). The
    type and the prd must match on the SAME item."""
    try:
        files = sorted(
            path for path in deferred_dir.glob("*-deferred.json") if path.is_file()
        )
    except OSError:
        return False
    for path in files[max(0, len(files) - 2) :]:
        record = _load_json(path)
        if not isinstance(record, dict):
            continue
        items = record.get("items")
        if not isinstance(items, list):
            continue
        for item in items:
            if (
                isinstance(item, dict)
                and item.get("type") == "stall"
                and item.get("prd") == target
            ):
                return True
    return False


def build_model(
    state_path: Path,
    prds_dir: Path,
    ledger_path: Path,
    deferred_dir: Path,
) -> str:
    """The build-phase launch model: OPUS when the target PRD carries
    difficulty evidence, else SONNET. Never raises and never writes -
    the wrapper ran this on every launch with its stderr as the
    operator's log, so a missing state.json, ledger or metrics file and
    an empty deferred dir are all normal."""
    target_path = build_target(prds_dir)
    if target_path is None:
        return SONNET
    if _frontmatter_session_model(target_path) == "opus":
        return OPUS
    target = target_path.name
    if _state_signals_fire(state_path, target) or _ledger_has_key(
        ledger_path,
        target,
    ):
        return OPUS
    if _deferred_stall_fires(deferred_dir, target):
        return OPUS
    return SONNET


def review_cycle(autopilot_dir: Path) -> int:
    """The current review cycle from state.json, else 1.

    Cycle 1 (or a missing/malformed state, or a non-int cycle) is the
    first review pass; anything above 1 is a rerun.
    """
    state = _load_json(autopilot_dir / "state.json")
    if not isinstance(state, dict):
        return 1
    cycle = state.get("cycle")
    if isinstance(cycle, int) and not isinstance(cycle, bool):
        return cycle
    return 1


def _unfinished_rework_tasks(state: dict) -> list[dict]:
    """The `state.tasks` entries `rework_task_ids` names whose status is
    not `completed`. Empty when the list is missing, not a list, or names
    only finished tasks (a stale list is a fresh review, not a resume)."""
    ids = state.get("rework_task_ids")
    tasks = state.get("tasks")
    if not isinstance(ids, list) or not ids or not isinstance(tasks, list):
        return []
    wanted = {
        str(i) for i in ids if isinstance(i, (str, int)) and not isinstance(i, bool)
    }
    return [
        t
        for t in tasks
        if isinstance(t, dict)
        and str(t.get("id")) in wanted
        and t.get("status") != "completed"
    ]


def _cycle_review_file(autopilot_dir: Path, prd: object, cycle: int) -> Path | None:
    """This cycle's review file, in either spelling `cli/convergence`
    accepts; None when absent or the state names no PRD."""
    if not isinstance(prd, str) or not prd:
        return None
    stem = prd.removesuffix(".md")
    reviews = autopilot_dir.parent / "reviews"
    for name in (f"{stem}-review-{cycle}.md", f"{stem}-review-{cycle:02d}.md"):
        candidate = reviews / name
        try:
            if candidate.is_file():
                return candidate
        except OSError:
            continue
    return None


def _rework_tasks(autopilot_dir: Path) -> list[dict]:
    """The unfinished rework tasks of a rework-resume launch (PRD 00207),
    else an empty list.

    A launch is a rework resume when `state.rework_task_ids` names at least
    one task that is not `completed` AND this cycle's review file is on
    disk (the same artifact `references/phase-review.md` Phase 4 skips on).
    Anything missing or malformed reads as a fresh review; a missing or
    non-int `cycle` reads as 1, exactly as `review_cycle` reads it.
    """
    state = _load_json(autopilot_dir / "state.json")
    if not isinstance(state, dict):
        return []
    pending = _unfinished_rework_tasks(state)
    if not pending:
        return []
    cycle = state.get("cycle")
    if not isinstance(cycle, int) or isinstance(cycle, bool):
        cycle = 1
    if _cycle_review_file(autopilot_dir, state.get("prd"), cycle) is None:
        return []
    return pending


def rework_resume(autopilot_dir: Path) -> bool:
    """PRD 00207: True when the next review launch resumes queued rework
    (Phases 4 and 5 already ran for this cycle), False for a fresh review."""
    return bool(_rework_tasks(autopilot_dir))


def _review_model(autopilot_dir: Path) -> str:
    """OPUS for a fresh review; on a rework resume (PRD 00207) Phases 4-5
    already ran and the orchestrator only dispatches /work for the queued
    fixes, so it takes their highest tier: OPUS when one carries an opus or
    fable (the rescue rung) model, else SONNET (a task without `model` is
    the legacy sonnet). One stderr line names the route."""
    pending = _rework_tasks(autopilot_dir)
    if not pending:
        return OPUS
    model = SONNET
    if any(t.get("model") in ("opus", "fable") for t in pending):
        model = OPUS
    print(
        f"review: rework resume, {len(pending)} task(s) left, routing {model}",
        file=sys.stderr,
    )
    return model


def route(phase: str, autopilot_dir: Path, env: dict | None = None) -> Route:
    """Model, effort and wall-clock cap for the next spawn.

    `phase` is state.next_phase as launched (empty string for a fresh
    batch with no state.json). Env overrides mirror the wrapper's knobs;
    the unknown-phase branch deliberately has none.
    """
    if env is None:
        env = dict(os.environ)
    if phase in ("build", ""):
        model = env.get("_AUTOPILOT_MODEL_BUILD") or build_model(
            autopilot_dir / "state.json",
            autopilot_dir.parent / "prds",
            autopilot_dir / "ledger" / "fable-requests.json",
            autopilot_dir / "deferred",
        )
        return Route(
            model=model,
            effort=env.get("_AUTOPILOT_EFFORT_BUILD") or "xhigh",
            cap_secs=_env_int(env, "_AUTOPILOT_SESSION_MAX", 7200),
        )
    if phase == "review":
        cycle = review_cycle(autopilot_dir)
        if cycle <= 1:
            effort = "xhigh"
        else:
            effort = env.get("_AUTOPILOT_EFFORT_REVIEW_RERUN") or "high"
        if "_AUTOPILOT_EFFORT_REVIEW" in env:
            effort = env["_AUTOPILOT_EFFORT_REVIEW"]
        return Route(
            model=env.get("_AUTOPILOT_MODEL_REVIEW") or _review_model(autopilot_dir),
            effort=effort,
            cap_secs=_env_int(env, "_AUTOPILOT_SESSION_MAX_REVIEW", 10800),
        )
    if phase == "done":
        return Route(
            model=env.get("_AUTOPILOT_MODEL_DONE") or SONNET,
            effort=env.get("_AUTOPILOT_EFFORT_DONE") or "medium",
            cap_secs=_env_int(env, "_AUTOPILOT_SESSION_MAX", 7200),
        )
    return Route(
        model=OPUS,
        effort="xhigh",
        cap_secs=_env_int(env, "_AUTOPILOT_SESSION_MAX", 7200),
    )
