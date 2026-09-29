#!/usr/bin/env python3
"""enter.py - the Phase 0 step chain as one call.

    enter(state_path, *, prds_dir, autopilot_dir, prd_arg, in_loop) -> dict

Runs mkdir, state bootstrap, marker clear, the stall_op precheck, park,
the stall/cap-pause checks, resume target, custody, selection, the batch
report, the prd/frontmatter write plus handoff row, the lane check, and the
catchup and design decisions - in that order - and returns one dict whose
`stop` names the first step that halted (None when all passed). Every side
effect runs through the module that already owns it; only the clock,
`git rev-parse HEAD`, and the cross-pack handoff row are injected.
"""

from __future__ import annotations

import contextlib
import importlib
import io
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import custody, frontmatter, records, resume, schema, selection, state, statectl

_SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
_walk_up = importlib.import_module("_walk_up")

STOPS: tuple[str, ...] = (
    "fs_error",
    "park_halt", "mv_verify", "deferred_io", "stall_op_conflict",
    "stall_op_malformed", "park_precondition_failed",
    "replan", "escalation_exhausted", "cap_pause",
    "custody", "drained", "prd_not_found", "batch_init", "lane",
    "state_write_failed", "design_review_log_empty",
)

_RECORD_DISPATCH = (
    Path(__file__).resolve().parents[2]
    / "work" / "scripts" / "record_dispatch.py"
)

_CATCHUP_FRESH = timedelta(hours=4)

# null = "this step never ran", distinct from a checked value.
_EMPTY_RESULT = {
    "stop": None, "detail": "", "prd": None, "source": None, "parked": None,
    "custody_pending": 0, "lane_effective": None, "catchup": None,
    "design": None, "resume_target": None, "batch": None,
}

_DISPATCH_RE = re.compile(
    r"dispatch \d+ \((claude|codex|claude-fallback)\): "
    r"cardinal-sin \d+, blocker \d+, non-blocker \d+, question \d+"
)

# do_park exit codes that halt Phase 0 (5 is handled apart: it names the PRD).
_PARK_STOPS = {
    4: ("mv_verify", "do_park exited 4: the park move to hold/ failed verification"),
    9: ("deferred_io", "do_park exited 9: a deferred-record append failed"),
    10: ("stall_op_conflict", "do_park exited 10: stall_op and park marker name different PRDs"),
    2: (
        "park_precondition_failed",
        "do_park exited 2: do_stall's preflight guard refused "
        "(missing batch.id or a failed cap_critical range capture)",
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _git_head_sha(repo_root: Path) -> str | None:
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def _record_resume_row(prd: str, site: str) -> None:
    """Best-effort handoff row via the work pack's record_dispatch.py; any
    failure goes to stderr, never past the caller."""
    try:
        proc = subprocess.run(
            ["python3", str(_RECORD_DISPATCH), "handoff", "--site", site,
             "--edge", "resume", "--phase", "build", "--prd", prd],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as err:
        print(f"autopilot: enter: resume row failed: {err}", file=sys.stderr)
        return
    if proc.returncode != 0:
        print(
            f"autopilot: enter: resume row exited {proc.returncode}: {proc.stderr.strip()}",
            file=sys.stderr,
        )


def _review_log_has_dispatch_line(text: str) -> bool:
    in_section = False
    for line in text.splitlines():
        if line.startswith("## Review log"):
            in_section = True
            continue
        if line.startswith("## "):
            in_section = False
        if in_section and _DISPATCH_RE.search(line):
            return True
    return False


def _stop(out: dict, stop: str, detail: str) -> dict:
    out["stop"] = stop
    out["detail"] = detail
    return out


def _prepare_tree(state_path: Path, prds_dir: Path, autopilot_dir: Path) -> None:
    """Steps 0-2: lifecycle dirs, state.json bootstrap, inherited markers."""
    for name in ("backlog", "wip", "done", "hold"):
        (prds_dir / name).mkdir(parents=True, exist_ok=True)
    (prds_dir.parent / "reviews").mkdir(parents=True, exist_ok=True)
    (prds_dir.parents[1] / "tmp").mkdir(parents=True, exist_ok=True)
    (autopilot_dir / "reports").mkdir(parents=True, exist_ok=True)
    (autopilot_dir / "deferred").mkdir(parents=True, exist_ok=True)
    if not state_path.exists():
        state.init(state_path, {"phase": "build", "next_phase": "build"})
    for name in _walk_up.INHERITED_MARKERS:
        (autopilot_dir / name).unlink(missing_ok=True)


def _park(out: dict, state_path: Path, prds_dir: Path, autopilot_dir: Path) -> bool:
    """Step 4. True when the park result halts Phase 0."""
    marker = records._parse_marker(autopilot_dir / "park-requested")
    marked = marker["prd"] if isinstance(marker, dict) else None
    with contextlib.redirect_stdout(io.StringIO()):
        code = records.do_park(state_path, prds_dir=prds_dir, autopilot_dir=autopilot_dir)
    if code == 3:
        return False
    if code in (0, 5):
        out["parked"] = marked
    if code == 0:
        return False
    if code == 5:
        _stop(out, "park_halt", f"parked {marked}; systemic halt (2+ consecutive wrapper_died parks)")
        return True
    _stop(out, *_PARK_STOPS[code])
    return True


def _stall_stop(state_path: Path) -> tuple[dict, tuple[str, str] | None]:
    """Step 5: drop pause_reason, then the three stall/cap-pause stops."""
    current, _ = state.load(state_path)
    if "pause_reason" in current:
        statectl.mutate(state_path, lambda data: data.pop("pause_reason", None))
        current, _ = state.load(state_path)
    stall = current.get("stall_reason")
    stalled = stall.get("stalled") if isinstance(stall, dict) else None
    if stalled == "subagent_prompt_overrun":
        return current, ("replan", "stall_reason: subagent_prompt_overrun; replan the task")
    if stalled == "escalation_exhausted":
        return current, ("escalation_exhausted", "stall_reason: escalation_exhausted")
    if current.get("phase") == "paused" and current.get("cap_pause_reason"):
        return current, ("cap_pause", "paused at the rework cap (cap_pause_reason set)")
    return current, None


def _select(
    out: dict, state_path: Path, prds_dir: Path, autopilot_dir: Path,
    prd_arg: str | None, now: Callable[[], str],
) -> bool:
    """Step 8. True when selection halts Phase 0."""
    if prd_arg is not None:
        out.update(prd=prd_arg, source="arg")
        if (prds_dir / "wip" / prd_arg).exists():
            return False
        if not (prds_dir / "backlog" / prd_arg).exists():
            out.update(prd=None, source=None)
            _stop(out, "prd_not_found", f"{prd_arg} is in neither wip/ nor backlog/")
            return True
    else:
        prd, source, skips = selection.select_eligible(
            prds_dir, custody.project_root(autopilot_dir),
        )
        if skips:
            at = now()
            entries = [{**skip, "at": at} for skip in skips]
            statectl.mutate(
                state_path,
                lambda data: data.setdefault("batch", {}).setdefault("skips", []).extend(entries),
            )
        if source == "drained":
            _stop(out, "drained", "no selectable PRD in wip/ or backlog/")
            return True
        out.update(prd=prd, source=source)
        if source == "wip":
            return False
    src = prds_dir / "backlog" / out["prd"]
    dst = prds_dir / "wip" / out["prd"]
    shutil.move(str(src), str(dst))
    if not dst.exists() or src.exists():
        _stop(out, "mv_verify", f"move {src} -> {dst} did not verify")
        return True
    return False


def _batch_report(out: dict, state_path: Path) -> bool:
    """Step 9. True when the batch is absent or closed."""
    current, _ = state.load(state_path)
    batch = current.get("batch")
    if not isinstance(batch, dict) or not isinstance(batch.get("id"), str):
        out["batch"] = "absent"
    elif current.get("phase") == "done" and current.get("next_phase") == "":
        out["batch"] = "closed"
    else:
        out["batch"] = "open"
        return False
    _stop(out, "batch_init", f"batch {out['batch']}; initialize a batch first")
    return True


def _write_prd(
    out: dict, state_path: Path, prds_dir: Path,
    record_resume_row: Callable[[str, str], None],
) -> dict | None:
    """Step 10 writes: state.prd, the frontmatter fields, the handoff row.
    Returns the fields, or None after a state_write_failed stop."""
    prd = out["prd"]
    try:
        statectl.mutate(state_path, lambda data: data.update(prd=prd))
        fields, warnings = frontmatter.apply(prds_dir / "wip" / prd, state_path)
    except (OSError, state.StateError, schema.SchemaError) as err:
        _stop(out, "state_write_failed", str(err))
        return None
    for line in warnings:
        print(line, file=sys.stderr)
    try:
        record_resume_row(prd, "build")
    except Exception as err:  # best-effort row: never halts Phase 0
        print(f"autopilot: enter: resume row failed: {err}", file=sys.stderr)
    return fields


def _fresh(stamp: object, now_iso: str) -> bool:
    """True when ISO `stamp` is under four hours before ISO `now_iso`."""
    try:
        then = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
        now = datetime.fromisoformat(now_iso.replace("Z", "+00:00"))
        return now - then < _CATCHUP_FRESH
    except (TypeError, ValueError):
        return False


def _catchup(
    current: dict, state_path: Path, autopilot_dir: Path,
    now: Callable[[], str], git_head: Callable[[Path], str | None],
) -> str:
    """Step 11: skip, delta (batch cache fresh and HEAD unmoved), or full."""
    mode = current.get("catchup_mode")
    if mode in ("skip", "skipped"):
        if mode == "skip":
            statectl.mutate(state_path, lambda data: data.update(catchup_mode="skipped"))
        return "skip"
    batch = current["batch"]
    tasks = current.get("tasks")
    if mode == "force" and not (isinstance(tasks, list) and tasks):
        return "full"
    if "catchup_completed_at" not in batch or not _fresh(batch["catchup_completed_at"], now()):
        return "full"
    head = git_head(custody.project_root(autopilot_dir))
    if head is None or batch.get("catchup_head_sha") != head:
        return "full"
    return "delta"


def _design(out: dict, current: dict, autopilot_dir: Path) -> None:
    """Step 12: skip, run (no design doc), reuse, or the empty-log stop."""
    if current.get("design_mode") == "skip":
        out["design"] = "skip"
        return
    doc = autopilot_dir.parent / "designs" / f"{Path(out['prd']).stem}-design.md"
    if not doc.exists():
        out["design"] = "run"
    elif _review_log_has_dispatch_line(doc.read_text(encoding="utf-8")):
        out["design"] = "reuse"
    else:
        _stop(out, "design_review_log_empty", f"{doc} has empty ## Review log (review never ran)")


def enter(
    state_path: Path,
    *,
    prds_dir: Path,
    autopilot_dir: Path,
    prd_arg: str | None,
    in_loop: bool,
    now: Callable[[], str] = _utc_now,
    git_head: Callable[[Path], str | None] = _git_head_sha,
    record_resume_row: Callable[[str, str], None] = _record_resume_row,
) -> dict:
    """Run the Phase 0 step chain in documented order; return the one JSON
    line as a dict. A corrupt state.json raises state.StateError."""
    out = dict(_EMPTY_RESULT)
    try:
        _prepare_tree(state_path, prds_dir, autopilot_dir)
    except OSError as err:
        return _stop(out, "fs_error", str(err))
    current, _ = state.load(state_path)
    stall_op = current.get("stall_op")
    if stall_op is not None and records._stall_op_malformed(stall_op):
        return _stop(out, "stall_op_malformed", "malformed stall_op in state.json; refusing to park")
    if _park(out, state_path, prds_dir, autopilot_dir):
        return out
    current, stall = _stall_stop(state_path)
    if stall is not None:
        return _stop(out, *stall)
    out["resume_target"] = resume.resume_target(current)
    try:
        out["custody_pending"] = len(custody.pending(autopilot_dir))
    except custody.CustodyError as err:
        return _stop(out, "deferred_io", str(err))
    if not in_loop and out["custody_pending"]:
        return _stop(out, "custody", f"{out['custody_pending']} custody record(s) pending review")
    if _select(out, state_path, prds_dir, autopilot_dir, prd_arg, now):
        return out
    if _batch_report(out, state_path):
        return out
    fields = _write_prd(out, state_path, prds_dir, record_resume_row)
    if fields is None:
        return out
    out["lane_effective"] = fields["lane_effective"]
    if fields["lane_effective"] != "full":
        return _stop(out, "lane", f"lane: {fields['lane']} ({fields['lane_reason']})")
    current, _ = state.load(state_path)
    out["catchup"] = _catchup(current, state_path, autopilot_dir, now, git_head)
    _design(out, current, autopilot_dir)
    return out
