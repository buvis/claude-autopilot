#!/usr/bin/env python3
"""records_park.py - do_park, the Phase 0 park-request handler.

Split out of records.py (PRD 00282, review finding 7: records.py crossed
the 800-line limit). `do_park` and its helpers used to live in
records.py; `records.do_park` (and the rest of this module's public
names) re-exports them there unchanged, so no caller needs to change its
import.

Exposes:
    do_park(state_path, *, prds_dir, autopilot_dir) -> int
        The Phase 0 park-request handler as one callable: consumes
        `<autopilot_dir>/park-requested`, reconciles any pending stall_op
        first, then parks via `do_stall(site=<marker's site,
        "wrapper_died" or "budget">, ...)`. Never writes state itself -
        every effect rides through do_stall's transactions. See
        test_records_park.py's module docstring for the full
        marker/stall_op match matrix and exit-code contract.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from . import records, resume, state
from .records import _park_mutator, _stall_op_malformed, _trip

# do_stall is called as records.do_stall(...), not imported by name: tests
# patch it via mock.patch.object(records, "do_stall", ...), which only
# rebinds the attribute on the records module - a direct `from .records
# import do_stall` here would keep its own stale reference and never see
# the patch (strunk python-testing: patch where the name is used).


def _parse_marker(marker_path: Path) -> str | dict | None:
    """Return None (absent), "malformed" (unparseable or missing/empty
    prd), or {"prd": str, "reason": str, "site": str} for a present, usable
    marker; site defaults to "wrapper_died" when the marker omits it."""
    if not marker_path.exists():
        return None
    try:
        raw = json.loads(marker_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return "malformed"
    if not isinstance(raw, dict) or not raw.get("prd"):
        return "malformed"
    # Any site other than "budget" takes the wrapper_died path - normalize
    # an unknown/absent value instead of passing it through raw, or a park
    # marker's site could collide with an unrelated pending stall_op site
    # (cap_critical, design_gate) and skip the resume reconcile.
    site = raw.get("site")
    return {
        "prd": raw["prd"],
        "reason": raw.get("reason", ""),
        "site": site if site == "budget" else "wrapper_died",
    }


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
    rc = records.do_stall(
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
    """do_park's valid-marker path: reconcile any stall_op that isn't the
    same park (same site as the marker) resuming, then confirm wip/
    placement. Returns (prd, reason, wip_filenames, None) to continue, or
    (None, None, None, exit_code) to return immediately."""
    prd = marker["prd"]
    reason = marker["reason"]
    wip_filenames = [p.name for p in (prds_dir / "wip").glob("*.md")]
    prd_in_wip = prd in wip_filenames

    if stall_op and not (prd_in_wip and stall_op["site"] == marker["site"]):
        rc = _reconcile_stall_op(stall_op, state_path, prds_dir, autopilot_dir)
        if rc is not None:
            return None, None, None, rc

    if not prd_in_wip:
        delete_marker()
        print(f"autopilot: park-requested named {prd} not in wip/; ignoring")
        return None, None, None, 3

    return prd, reason, wip_filenames, None


def _finish_park_budget(state_path, prds_dir, autopilot_dir, delete_marker, prd, reason) -> int:
    """Budget-site branch: not a wrapper death, no parks_consecutive bump, never the systemic halt."""
    rc = records.do_stall(
        state_path, prd=prd, site="budget", detail=reason,
        prds_dir=prds_dir, autopilot_dir=autopilot_dir, extra_mutator=None,
    )
    if rc != 0:
        return rc
    delete_marker()
    print(f"autopilot: parked {prd} (budget)")
    return 0


def _finish_park_wrapper_died(
    state_path, prds_dir, autopilot_dir, delete_marker, marker, prd, reason,
    wip_filenames, parks_consecutive,
) -> int:
    """Wrapper_died branch: decide (park_decision), do_stall, delete marker, report."""
    decision = resume.park_decision(marker, wip_filenames, parks_consecutive)
    if decision.endswith("systemic halt"):
        pause_detail = f"{parks_consecutive + 1} consecutive PRDs parked via wrapper_died; batch halted"
        extra = _park_mutator(pause_detail=pause_detail)
        exit_code = 5
    else:
        extra = _park_mutator()
        exit_code = 0

    rc = records.do_stall(
        state_path, prd=prd, site="wrapper_died", detail=reason,
        prds_dir=prds_dir, autopilot_dir=autopilot_dir, extra_mutator=extra,
    )
    if rc != 0:
        return rc
    delete_marker()
    suffix = " (systemic halt)" if exit_code == 5 else ""
    print(f"autopilot: parked {prd}{suffix}")
    return exit_code


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
    """do_park's tail: routes to the budget or wrapper_died branch."""
    try:
        consult_state, _version = state.load(state_path)
    except state.StateError:
        return 2
    parks_consecutive = (consult_state.get("batch") or {}).get("parks_consecutive", 0)
    # A lane-routed PRD parked mid-build carries its lane (PRD 00205), so the
    # STALLED report says which runbook died.
    if consult_state.get("lane_effective"):
        reason = f"{reason}; lane={consult_state['lane_effective']}"

    if marker["site"] == "budget":
        return _finish_park_budget(state_path, prds_dir, autopilot_dir, delete_marker, prd, reason)

    return _finish_park_wrapper_died(
        state_path, prds_dir, autopilot_dir, delete_marker, marker, prd, reason,
        wip_filenames, parks_consecutive,
    )


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
