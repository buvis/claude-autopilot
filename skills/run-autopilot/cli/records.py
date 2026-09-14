#!/usr/bin/env python3
"""records.py - the per-PRD state reset and the idempotent deferred-record log.

Exposes:
    PER_PRD_RESET_FIELDS
        Tuple of state.json field names removed when a batch advances from
        one PRD to the next.
    reset_prd_fields(state) -> dict
        PURE. Returns a NEW dict; never mutates `state`. Removes every
        PER_PRD_RESET_FIELDS key (if present; absent is not an error),
        resets phases_completed/cycle/tasks_total/tasks_completed/
        replan_count/phase/next_phase by direct assignment, and preserves
        every other key - in particular `batch`, in full - unchanged. The
        caller wraps this in a `state.transaction`; this module never opens
        state.json's lock.
    record_defer(path, prd, batch_id, record) -> None
        Appends `record` (stamped with `record["prd"] = prd`, without
        mutating the caller's dict) to
        `<path>/deferred/<batch_id>-deferred.json`, creating the `deferred/`
        directory and the `{"batch_id": ..., "items": []}` skeleton file
        when absent. Idempotent by "op_id": a record whose op_id matches an
        existing item's op_id is skipped; a record with no op_id is always
        appended. Preserves the file's existing batch_id and prior items.
        Locked and written atomically via its own `.lock` sidecar next to
        the deferred file - a different lock from state.json's.
    do_stall(state_path, *, prd, site, detail, prds_dir, autopilot_dir,
             extra_mutator=None) -> int
        The Loop-mode stall procedure (references/recovery.md) as ONE call
        with a durable intent record (state.stall_op), recoverable on retry
        from a kill at any of its three internal boundaries. Clears the
        handoff/cap markers (cli/handoff.py) once the commit lands, and only
        then - a stall that never commits leaves them alone. See
        test_records_stall.py's module docstring for the full 0-5 step /
        exit-code / retry contract.
    do_park(state_path, *, prds_dir, autopilot_dir) -> int
        The Phase 0 park-request handler as one callable: consumes
        `<autopilot_dir>/park-requested`, reconciles any pending stall_op
        first, then parks via `do_stall(site="wrapper_died", ...)`. Never
        writes state itself - every effect rides through do_stall's
        transactions. See test_records_park.py's module docstring for the
        full marker/stall_op match matrix and exit-code contract.
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import sys
import uuid
from pathlib import Path

from . import custody, handoff, resume, schema, state

# park_decision used to be imported from scripts/resume_target.py behind a
# scoped sys.path insert. PRD 00089 absorbed it into cli/resume.py, so it is
# now an ordinary package import and the dance is gone.

# Fields removed by the per-PRD reset, grouped by why they're here:
#
# - Fields already named in every prose reset list today (per-PRD work
#   product: tasks, review/doubt history, design choices, pause/stall
#   reasons).
# - repo_root: reset only per phase-done.md step 10, not the general prose
#   lists, but still a per-PRD field. git_dir (the bare-repo locator beside
#   it) follows it.
# - The four fields that leak into the next PRD today (bug this reset
#   fixes): pause_on_ambiguity, review_lenses, contract_card,
#   needs_attention.
PER_PRD_RESET_FIELDS = (
    "tasks",
    "task_aborts",
    "cap_rotations",
    "autonomous_decisions",
    "deferred_decisions",
    "review_cycles",
    "doubts",
    "doubts_rubric_verdicts",
    "rework_task_ids",
    "work_start_sha",
    "design_doc",
    "design_gate",
    "design_mode",
    "pause_reason",
    "cap_pause_reason",
    "stall_reason",
    "repo_root",
    "git_dir",
    "pause_on_ambiguity",
    "plan_expansion_override",
    "review_lenses",
    "contract_card",
    "needs_attention",
)

# NOT reset here, deliberately:
# - batch: preserved in full - it tracks the whole batch, not one PRD. That
#   includes batch.skips (PRD 00137): the eligibility gate's skip records
#   belong to the drain, not to whichever PRD it eventually picked.
# - catchup_mode, rework_cap, doubt_reviewer, consensus_engine: re-derived
#   by Phase 0 from the next PRD's frontmatter, not carried forward.
# - qwen_gate_failures_consecutive, qwen_breaker, codex_probe, qwen_preflight:
#   batch-scoped, each with its own lazy reset elsewhere.
# - schema_version: stamped by the state.transaction boundary, not here.


def reset_prd_fields(state: dict) -> dict:
    """Return a new dict with PER_PRD_RESET_FIELDS removed and per-PRD
    counters/phase markers reset by assignment. Pure: does not mutate
    `state`; every other key is preserved unchanged."""
    new_state = {k: v for k, v in state.items() if k not in PER_PRD_RESET_FIELDS}
    new_state.update(
        {
            "phases_completed": [],
            "cycle": 1,
            "tasks_total": 0,
            "tasks_completed": 0,
            "replan_count": 0,
            "phase": "build",
            "next_phase": "build",
        },
    )
    return new_state


def record_defer(path: str | Path, prd: str, batch_id: str, record: dict) -> None:
    """Append `record` to `<path>/deferred/<batch_id>-deferred.json`.

    Creates the `deferred/` directory and the file (skeleton
    {"batch_id": batch_id, "items": []}) when absent. Stamps a COPY of
    `record` with `"prd": prd` (the caller's dict is never mutated). Skips
    the append when an existing item's "op_id" equals `record["op_id"]`; a
    record with no "op_id" is always appended. Locked and written
    atomically under its own `.lock` sidecar next to the deferred file.

    Raises ValueError for an invalid `prd`/`batch_id`, or when the existing
    deferred file is shape-corrupt (not a dict, "items" not a list, or an
    "items" element that isn't a dict).
    """
    if "/" in prd or prd == "..":
        raise ValueError(f"record_defer: invalid prd {prd!r}")
    if (
        not isinstance(batch_id, str)
        or not batch_id
        or "/" in batch_id
        or ".." in batch_id
    ):
        raise ValueError(f"record_defer: invalid batch_id {batch_id!r}")

    deferred_dir = Path(path) / "deferred"
    deferred_dir.mkdir(parents=True, exist_ok=True)
    file_path = deferred_dir / f"{batch_id}-deferred.json"
    lock_path = Path(f"{file_path}.lock")

    with open(lock_path, "w", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        if file_path.exists():
            content = json.loads(file_path.read_text(encoding="utf-8"))
            if (
                not isinstance(content, dict)
                or not isinstance(content.get("items"), list)
                or not all(isinstance(i, dict) for i in content["items"])
            ):
                raise ValueError(f"record_defer: corrupt deferred file {file_path}")
        else:
            content = {"batch_id": batch_id, "items": []}

        op_id = record.get("op_id")
        already_present = op_id is not None and any(
            item.get("op_id") == op_id for item in content["items"]
        )
        if already_present:
            return

        item = dict(record)
        item["prd"] = prd
        content["items"].append(item)

        state.atomic_write(file_path, content)


def _new_op_id() -> str:
    return uuid.uuid4().hex[:12]


def _trip(boundary: str) -> None:
    """Raise RuntimeError("failpoint: <boundary>") when
    _AUTOPILOT_CLI_FAILPOINT is set to `boundary`, simulating a kill at that
    point. Zero cost when unset."""
    if os.environ.get("_AUTOPILOT_CLI_FAILPOINT") == boundary:
        raise RuntimeError(f"failpoint: {boundary}")


_RANGE_RE = re.compile(r"[0-9a-f]{40}\.\.[0-9a-f]{40}")
_CAPTURE_KEYS = ("commit_range", "commits", "branch", "repo_root", "git_dir")


def _capture_malformed(stall_op: dict) -> bool:
    """True when a cap_critical intent's capture is incomplete or invalid:
    an intent is never accepted half-written and never recaptured."""
    commits = stall_op.get("commits")
    return (
        not isinstance(stall_op.get("commit_range"), str)
        or not _RANGE_RE.fullmatch(stall_op["commit_range"])
        or not isinstance(commits, int)
        or commits < 0
        or not isinstance(stall_op.get("branch"), str)
        or not stall_op["branch"]
        or not isinstance(stall_op.get("repo_root"), str)
        or not stall_op["repo_root"]
        or not isinstance(stall_op.get("git_dir"), (str, type(None)))
    )


def _stall_op_malformed(stall_op) -> bool:
    """True when a present stall_op fails the required-string-fields shape
    check shared by do_stall's step-0 guard and do_park's pre-effect
    guard, or (site == cap_critical) the capture-shape check."""
    if (
        not isinstance(stall_op, dict)
        or not isinstance(stall_op.get("op_id"), str)
        or not isinstance(stall_op.get("prd"), str)
        or not isinstance(stall_op.get("site"), str)
        or not isinstance(stall_op.get("detail"), str)
    ):
        return True
    return stall_op["site"] == custody.CUSTODY_SITE and _capture_malformed(stall_op)


def _validate_stall_op(new_state: dict) -> None:
    """Owned-fields validator for do_stall's step-2 intent stamp: checks
    only the stall_op shape this write sets, never the whole state."""
    stall_op = new_state.get("stall_op")
    schema.require(stall_op, dict, "stall_op")
    for key in ("op_id", "prd", "site", "detail"):
        schema.require(stall_op.get(key), str, f"stall_op.{key}")


def _validate_stall_commit(new_state: dict) -> None:
    """Owned-fields validator for do_stall's step-5 commit: checks only the
    reset scalars, batch.parks_consecutive, and stall_op absence this write
    sets. A malformed unrelated field elsewhere in state must not block a
    stall - statectl.py stays an unvalidated writer until PRD 00089, so
    whole-state schema.validate would wedge real states here."""
    if "stall_op" in new_state:
        raise schema.SchemaError("stall_op: must be absent after commit")
    schema.require(new_state.get("phase"), str, "phase")
    schema.require(new_state.get("next_phase"), str, "next_phase")
    schema.require(new_state.get("phases_completed"), list, "phases_completed")
    for field in ("cycle", "tasks_total", "tasks_completed", "replan_count"):
        schema.require(new_state.get(field), int, field)
    batch = new_state.get("batch")
    parks = batch.get("parks_consecutive") if isinstance(batch, dict) else None
    schema.require(parks, int, "batch.parks_consecutive")


def _capture_range(current: dict, autopilot_dir: Path) -> dict:
    """A fresh cap_critical capture: work_start_sha..HEAD of the state's
    repo (repo_root, else the project root above autopilot_dir). Raises
    custody.CustodyError."""
    repo_root = current.get("repo_root") or str(custody.project_root(autopilot_dir))
    git_dir = current.get("git_dir")
    commit_range, commits, branch = custody.capture_range(
        repo_root,
        git_dir,
        str(current.get("work_start_sha") or ""),
    )
    return {
        "commit_range": commit_range,
        "commits": commits,
        "branch": branch,
        "repo_root": repo_root,
        "git_dir": git_dir,
    }


def _stall_preflight(
    current: dict,
    prd: str,
    site: str,
    autopilot_dir: Path,
) -> tuple[str, dict, int | None]:
    """do_stall's step-0 guard: stall_op malformed/identity checks, batch.id
    presence, then (cap_critical only) the range capture - reused from a
    present stall_op stamped for this site (another site's intent is a
    conflict, exit 10), captured fresh otherwise. Returns (op_id, capture,
    None) on success, ("", {}, <exit code>) on failure - the caller returns
    immediately when the code is set. `capture` is {} for other sites."""
    stall_op = current.get("stall_op")
    if stall_op:
        if _stall_op_malformed(stall_op):
            print("autopilot: malformed stall_op in state; refusing", file=sys.stderr)
            return "", {}, 2
        if stall_op.get("prd") != prd:
            return "", {}, 10
        state_prd = current.get("prd")
        if state_prd and state_prd != prd:
            return "", {}, 10
        op_id = stall_op["op_id"]
    else:
        op_id = _new_op_id()

    batch = current.get("batch")
    if not isinstance(batch, dict) or not isinstance(batch.get("id"), str):
        print("autopilot: batch.id missing or not a string; refusing", file=sys.stderr)
        return "", {}, 2

    if site != custody.CUSTODY_SITE:
        return op_id, {}, None
    if stall_op:
        if stall_op.get("site") != site:
            return "", {}, 10
        return op_id, {key: stall_op[key] for key in _CAPTURE_KEYS}, None
    try:
        capture = _capture_range(current, autopilot_dir)
    except custody.CustodyError as err:
        print(f"autopilot: cap_critical custody capture failed: {err}", file=sys.stderr)
        return "", {}, 2
    return op_id, capture, None


def _mkdir_hold(prds_dir: Path) -> int | None:
    """do_stall's step 1: mkdir -p <prds_dir>/hold. Returns an exit code
    (4) on failure, None on success."""
    try:
        (prds_dir / "hold").mkdir(parents=True, exist_ok=True)
    except OSError:
        return 4
    return None


def _stamp_stall_intent(
    state_path: Path,
    op_id: str,
    prd: str,
    site: str,
    detail: str,
    capture: dict,
) -> int | None:
    """do_stall's step 2: stamp the intent, including the cap_critical
    capture (idempotent on retry: same op_id). Returns an exit code (2) on
    failure, None on success."""

    def _stamp_intent(s: dict) -> dict:
        new_s = dict(s)
        new_s["stall_op"] = {
            "op_id": op_id,
            "prd": prd,
            "site": site,
            "detail": detail,
            **capture,
        }
        return new_s

    try:
        state.transaction(state_path, _stamp_intent, validator=_validate_stall_op)
    except (state.StateError, schema.SchemaError, OSError):
        return 2
    return None


def _move_prd_to_hold(prds_dir: Path, prd: str) -> int | None:
    """do_stall's step 3: move the PRD, verify arrival. Already-in-hold +
    absent-from-wip counts as success (retry-idempotent). Returns an exit
    code (4) on failure, None on success."""
    wip_path = prds_dir / "wip" / prd
    hold_path = prds_dir / "hold" / prd
    if wip_path.exists():
        try:
            wip_path.rename(hold_path)
        except OSError:
            return 4
    if not hold_path.exists():
        return 4
    return None


def _append_stall_deferred(
    autopilot_dir: Path,
    current: dict,
    prd: str,
    site: str,
    detail: str,
    op_id: str,
    capture: dict,
) -> int | None:
    """do_stall's step 4: append the deferred record (plus the cap_critical
    capture keys), deduped by op_id. Returns an exit code (9) on failure,
    None on success."""
    try:
        record_defer(
            autopilot_dir,
            prd,
            (current.get("batch") or {}).get("id"),
            {
                "type": "stall",
                "site": site,
                "detail": detail,
                "op_id": op_id,
                **capture,
            },
        )
    except (OSError, ValueError):
        return 9
    return None


def _record_stall_custody(
    autopilot_dir: Path,
    prds_dir: Path,
    current: dict,
    prd: str,
    site: str,
    detail: str,
    op_id: str,
    capture: dict,
) -> tuple[dict | None, int | None]:
    """do_stall's step 4b, cap_critical only: custody.record_critical behind
    the `after-append-before-custody` failpoint. Returns (marker entry for
    the commit's mirror, None) on success, (None, 9) on failure; (None, None)
    for every other site."""
    if site != custody.CUSTODY_SITE:
        return None, None
    _trip("after-append-before-custody")
    rc = custody.record_critical(
        autopilot_dir=autopilot_dir,
        prds_dir=prds_dir,
        current=current,
        prd=prd,
        op_id=op_id,
        detail=detail,
        capture=capture,
    )
    if rc is not None:
        return None, rc
    return custody.marker_entry(prd, current["batch"]["id"], op_id, detail, capture), None


def _commit_stall(
    state_path: Path, site: str, extra_mutator, entry: dict | None
) -> int:
    """do_stall's step 5: single commit - reset_prd_fields, the
    parks_consecutive rule, the batch.critical_on_master mirror of `entry`
    (cap_critical only), extra_mutator, then the stall_op delete. Returns
    the exit code (0 on success, 2 on failure)."""

    def _commit(s: dict) -> dict:
        new_s = reset_prd_fields(s)
        batch = dict(new_s.get("batch") or {})
        if site != "wrapper_died":
            batch["parks_consecutive"] = 0
        new_s["batch"] = batch
        if entry is not None:
            new_s = custody.mirror_mutator(entry)(new_s)
        if extra_mutator is not None:
            new_s = extra_mutator(new_s)
        new_s.pop("stall_op", None)
        return new_s

    try:
        state.transaction(state_path, _commit, validator=_validate_stall_commit)
    except (state.StateError, schema.SchemaError, OSError):
        return 2
    return 0


def do_stall(
    state_path: str | Path,
    *,
    prd: str,
    site: str,
    detail: str,
    prds_dir: str | Path,
    autopilot_dir: str | Path,
    extra_mutator=None,
) -> int:
    """Loop-mode stall as ONE call with a durable intent (state.stall_op); see
    test_records_stall.py. Exit codes: 0 stalled | 2 state unreadable or
    capture failed | 4 move failed | 9 record/custody write failed | 10 conflict."""
    state_path = Path(state_path)
    prds_dir = Path(prds_dir)
    autopilot_dir = Path(autopilot_dir)
    try:
        current, _version = state.load(state_path)
    except state.StateError:
        return 2

    op_id, capture, rc = _stall_preflight(current, prd, site, autopilot_dir)
    if rc is not None:
        return rc
    rc = _mkdir_hold(prds_dir)
    if rc is not None:
        return rc
    _trip("after-mkdir-before-intent")
    rc = _stamp_stall_intent(state_path, op_id, prd, site, detail, capture)
    if rc is not None:
        return rc
    _trip("after-intent-before-move")
    rc = _move_prd_to_hold(prds_dir, prd)
    if rc is not None:
        return rc
    _trip("after-move-before-append")
    rc = _append_stall_deferred(
        autopilot_dir, current, prd, site, detail, op_id, capture
    )
    if rc is not None:
        return rc
    entry, rc = _record_stall_custody(
        autopilot_dir, prds_dir, current, prd, site, detail, op_id, capture
    )
    if rc is not None:
        return rc
    _trip("after-append-before-commit")
    rc = _commit_stall(state_path, site, extra_mutator, entry)
    if rc == 0:
        # The PRD is off this session's plate; a pending handoff or cap
        # request is about the session that just ended.
        handoff.clear_markers(autopilot_dir)
    return rc


def _park_mutator(pause_detail: str | None = None):
    """Compose into do_stall's step-5 commit: increment
    batch.parks_consecutive by 1; when `pause_detail` is given, also set the
    systemic-halt phase/next_phase/pause_reason fields."""

    def _mutator(s: dict) -> dict:
        new_s = dict(s)
        batch = dict(new_s.get("batch") or {})
        batch["parks_consecutive"] = batch.get("parks_consecutive", 0) + 1
        new_s["batch"] = batch
        if pause_detail is not None:
            new_s["phase"] = "paused"
            new_s["next_phase"] = "paused"
            new_s["pause_reason"] = {"site": "systemic_park", "detail": pause_detail}
        return new_s

    return _mutator


def _parse_marker(marker_path: Path) -> str | dict | None:
    """Return None (absent), "malformed" (unparseable or missing/empty
    prd), or {"prd": str, "reason": str} for a present, usable marker."""
    if not marker_path.exists():
        return None
    try:
        raw = json.loads(marker_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return "malformed"
    if not isinstance(raw, dict) or not raw.get("prd"):
        return "malformed"
    return {"prd": raw["prd"], "reason": raw.get("reason", "")}


def _park_guard(stall_op, marker) -> int | None:
    """do_park's pre-effect guards: malformed stall_op shape, then a
    stall_op/marker PRD-identity conflict. Returns an exit code (2 or 10)
    on failure, None when clear to proceed."""
    if stall_op and _stall_op_malformed(stall_op):
        print("autopilot: malformed stall_op in state; refusing", file=sys.stderr)
        return 2
    if isinstance(marker, dict) and stall_op and stall_op.get("prd") != marker["prd"]:
        return 10
    return None


def _reconcile_stall_op(stall_op, state_path, prds_dir, autopilot_dir) -> int | None:
    """Run do_stall for a pending stall_op - do_park's marker-absent and
    valid-marker branches both reconcile through this. Returns None when
    do_stall succeeded (rc == 0), otherwise the nonzero rc to propagate."""
    extra = _park_mutator() if stall_op["site"] == "wrapper_died" else None
    rc = do_stall(
        state_path,
        prd=stall_op["prd"],
        site=stall_op["site"],
        detail=stall_op["detail"],
        prds_dir=prds_dir,
        autopilot_dir=autopilot_dir,
        extra_mutator=extra,
    )
    return rc if rc != 0 else None


def _park_marker_absent(stall_op, state_path, prds_dir, autopilot_dir) -> int:
    """do_park's marker-absent path: nothing to do unless a stall_op is
    pending, in which case reconcile it. Returns the exit code (3 no
    marker/reconciled, or a nonzero rc propagated from do_stall)."""
    if not stall_op:
        print("autopilot: no park-requested; nothing to do")
        return 3
    rc = _reconcile_stall_op(stall_op, state_path, prds_dir, autopilot_dir)
    if rc is not None:
        return rc
    print(
        f"autopilot: reconciled pending {stall_op['site']} stall for {stall_op['prd']}",
    )
    return 3


def _park_marker_present(
    marker,
    stall_op,
    state_path,
    prds_dir,
    autopilot_dir,
    delete_marker,
):
    """do_park's valid-marker path: reconcile any stall_op that isn't
    simply the same wrapper_died park resuming, then confirm the PRD is
    still in wip/. Returns (prd, reason, wip_filenames, None) to continue
    into _finish_park, or (None, None, None, exit_code) to return
    immediately."""
    prd = marker["prd"]
    reason = marker["reason"]
    wip_filenames = [p.name for p in (prds_dir / "wip").glob("*.md")]
    prd_in_wip = prd in wip_filenames

    if stall_op and not (prd_in_wip and stall_op["site"] == "wrapper_died"):
        rc = _reconcile_stall_op(stall_op, state_path, prds_dir, autopilot_dir)
        if rc is not None:
            return None, None, None, rc

    if not prd_in_wip:
        delete_marker()
        print(f"autopilot: park-requested named {prd} not in wip/; ignoring")
        return None, None, None, 3

    return prd, reason, wip_filenames, None


def _finish_park(
    state_path,
    prds_dir,
    autopilot_dir,
    delete_marker,
    marker,
    prd,
    reason,
    wip_filenames,
) -> int:
    """do_park's tail once the marker's PRD is confirmed present in wip/:
    consult parks_consecutive, decide (park_decision), run do_stall, delete
    the marker, and report. Returns the exit code (0 parked | 5 parked AND
    systemic halt | 2 state error | 4/9 propagated from do_stall)."""
    try:
        consult_state, _version = state.load(state_path)
    except state.StateError:
        return 2
    parks_consecutive = (consult_state.get("batch") or {}).get("parks_consecutive", 0)

    decision = resume.park_decision(marker, wip_filenames, parks_consecutive)
    if decision.endswith("systemic halt"):
        pause_detail = f"{parks_consecutive + 1} consecutive PRDs parked via wrapper_died; batch halted"
        extra = _park_mutator(pause_detail=pause_detail)
        exit_code = 5
    else:
        extra = _park_mutator()
        exit_code = 0

    rc = do_stall(
        state_path,
        prd=prd,
        site="wrapper_died",
        detail=reason,
        prds_dir=prds_dir,
        autopilot_dir=autopilot_dir,
        extra_mutator=extra,
    )
    if rc != 0:
        return rc
    delete_marker()
    suffix = " (systemic halt)" if exit_code == 5 else ""
    print(f"autopilot: parked {prd}{suffix}")
    return exit_code


def do_park(
    state_path: str | Path,
    *,
    prds_dir: str | Path,
    autopilot_dir: str | Path,
) -> int:
    """Consume `<autopilot_dir>/park-requested` end-to-end: the Phase 0 park
    handler as one callable, reconciling command. See
    test_records_park.py's module docstring for the full contract. Returns
    the exit code (0 parked | 3 no/ignored/reconciled marker | 5 parked AND
    systemic halt | 10 stall_op conflict | 2 state error | 4/9 propagated
    from an inner do_stall move/append failure).
    """
    state_path, prds_dir, autopilot_dir = (
        Path(state_path),
        Path(prds_dir),
        Path(autopilot_dir),
    )
    marker_path = autopilot_dir / "park-requested"

    def _delete_marker() -> None:
        _trip("after-commit-before-marker-delete")
        marker_path.unlink()

    marker = _parse_marker(marker_path)
    try:
        current, _version = state.load(state_path)
    except state.StateError:
        return 2

    stall_op = current.get("stall_op")
    rc = _park_guard(stall_op, marker)
    if rc is not None:
        return rc
    if marker == "malformed":
        _delete_marker()
        print("autopilot: park-requested malformed; ignoring")
        return 3
    if marker is None:
        return _park_marker_absent(stall_op, state_path, prds_dir, autopilot_dir)

    prd, reason, wip_filenames, rc = _park_marker_present(
        marker,
        stall_op,
        state_path,
        prds_dir,
        autopilot_dir,
        _delete_marker,
    )
    if rc is not None:
        return rc
    return _finish_park(
        state_path,
        prds_dir,
        autopilot_dir,
        _delete_marker,
        marker,
        prd,
        reason,
        wip_filenames,
    )
