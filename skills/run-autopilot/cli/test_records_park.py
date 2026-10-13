#!/usr/bin/env python3
"""Tests for cli/records.do_park: the Phase 0 park handler that consumes the
<autopilot_dir>/park-requested marker end-to-end.

do_park does not exist yet (records.py currently exposes reset_prd_fields,
record_defer, do_stall). These tests bind only the do_park contract given in
the task brief:

  do_park(state_path, *, prds_dir, autopilot_dir) -> int

  no marker            -> exit 3 (nothing to do; caller falls through)
  malformed            -> delete marker, log one line, exit 3
  stale                -> RECONCILE, then delete marker, exit 3
  park -> continue     -> the park transaction, exit 0
  park -> systemic halt -> the park transaction + pause, exit 5

  The park transaction is do_stall(site="wrapper_died", detail=<marker
  reason>) with ONE composed commit: its step-5 mutator additionally
  increments batch.parks_consecutive, and on the systemic branch also sets
  phase/next_phase="paused" and pause_reason={"site":"systemic_park",...}.
  Marker delete is LAST, after the commit. The match is on BOTH the marker's
  PRD and any pending stall_op's site; a stall_op naming a different PRD than
  the marker is a conflict (exit 10) regardless of wip/ placement.

  Exit codes: 0 parked | 3 no/ignored/reconciled marker | 5 parked AND
  systemic halt | 10 stall_op conflict | 2 state error. (Exit 4/9, inherited
  from do_stall, and exit 1, owned by the argparse layer, are out of scope
  here -- covered by test_records_stall.py.)

reset_prd_fields, record_defer, and do_stall are exercised only indirectly
here (through do_park); their own contracts are covered in test_records.py
and test_records_stall.py and are not re-tested in this file.

The original wrapper_died contract's test classes (no marker, malformed/
stale marker, normal park, systemic halt, commit-boundary and failpoint
recovery, stall_op reconcile/conflict cases) moved to
test_records_park_wrapper_died.py (PRD 00282, review finding 7: this file
crossed the 800-line limit). The `_ParkTestCase` fixture and `_without`
helper below are the pinned, shared import surface that split relies on;
the budget-site park contract (newer, PRD 00282) stays here.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cli import records


FAILPOINT_ENV = "_AUTOPILOT_CLI_FAILPOINT"


def _without(state: dict, *keys: str) -> dict:
    """A shallow copy of `state` with `keys` dropped, for equality checks
    that must ignore write-boundary bookkeeping fields (schema_version)."""
    return {k: v for k, v in state.items() if k not in keys}


class _ParkTestCase(unittest.TestCase):
    """Shared fixture: <root>/prds/wip (pre-created), <root>/prds/hold (left
    absent unless a test needs the PRD pre-placed there),
    <root>/autopilot/state.json, <root>/autopilot/park-requested.
    """

    PRD = "00010-sample-prd.md"

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.prds_dir = self.root / "prds"
        self.autopilot_dir = self.root / "autopilot"
        self.state_path = self.autopilot_dir / "state.json"
        self.marker_path = self.autopilot_dir / "park-requested"
        (self.prds_dir / "wip").mkdir(parents=True)
        self.autopilot_dir.mkdir(parents=True)

    # -- prd placement ------------------------------------------------
    def _put_in_wip(self, prd: str | None = None, content: str = "prd body") -> None:
        (self.prds_dir / "wip" / (prd or self.PRD)).write_text(content, encoding="utf-8")

    def _put_in_hold(self, prd: str | None = None, content: str = "prd body") -> None:
        (self.prds_dir / "hold").mkdir(parents=True, exist_ok=True)
        (self.prds_dir / "hold" / (prd or self.PRD)).write_text(content, encoding="utf-8")

    def _in_wip(self, prd: str | None = None) -> bool:
        return (self.prds_dir / "wip" / (prd or self.PRD)).exists()

    def _in_hold(self, prd: str | None = None) -> bool:
        return (self.prds_dir / "hold" / (prd or self.PRD)).exists()

    # -- marker -----------------------------------------------------------
    def _write_marker(self, prd: str | None = None, reason: str = "wrapper died mid-session") -> None:
        self.marker_path.write_text(
            json.dumps({"prd": prd if prd is not None else self.PRD, "reason": reason}),
            encoding="utf-8",
        )

    def _write_raw_marker(self, text: str) -> None:
        self.marker_path.write_text(text, encoding="utf-8")

    def _marker_exists(self) -> bool:
        return self.marker_path.exists()

    # -- state ----------------------------------------------------------
    def _write_state(self, state: dict) -> None:
        self.state_path.write_text(json.dumps(state), encoding="utf-8")

    def _state(self) -> dict:
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def _sample_state(self, **overrides) -> dict:
        base = {
            "prd": self.PRD,
            "phase": "build",
            "next_phase": "build",
            "cycle": 2,
            "tasks": [{"id": "t1", "name": "x", "status": "in_progress"}],
            "batch": {
                "id": "202607300000",
                "completed_prds": [],
                "parks_consecutive": 0,
            },
        }
        base.update(overrides)
        return base

    # -- deferred log -----------------------------------------------------
    def _deferred_path(self, batch_id: str = "202607300000") -> Path:
        return self.autopilot_dir / "deferred" / f"{batch_id}-deferred.json"

    def _deferred_items(self, batch_id: str = "202607300000") -> list:
        path = self._deferred_path(batch_id)
        if not path.exists():
            return []
        return json.loads(path.read_text(encoding="utf-8"))["items"]

    # -- call under test --------------------------------------------------
    def _do_park(self) -> int:
        return records.do_park(
            self.state_path,
            prds_dir=self.prds_dir,
            autopilot_dir=self.autopilot_dir,
        )


class BudgetSiteParkTests(_ParkTestCase):
    """A park-requested marker carrying "site": "budget" parks through
    do_stall(site="budget", extra_mutator=None): exit 0 always, no
    parks_consecutive increment, never the systemic-halt branch."""

    BUDGET_REASON = "prd budget exhausted"

    def _write_budget_marker(self, reason: str | None = None) -> None:
        self._write_raw_marker(json.dumps({
            "prd": self.PRD,
            "reason": reason if reason is not None else self.BUDGET_REASON,
            "site": "budget",
        }))

    def test_budget_site_park_moves_prd_to_hold_and_records_budget_stall(self) -> None:
        self._put_in_wip()
        self._write_budget_marker()
        self._write_state(self._sample_state(batch={
            "id": "202607300000", "completed_prds": [], "parks_consecutive": 0,
        }))

        rc = self._do_park()

        self.assertEqual(rc, 0)
        self.assertFalse(self._in_wip())
        self.assertTrue(self._in_hold())
        self.assertFalse(self._marker_exists(), "marker is deleted after a successful park")

        items = self._deferred_items()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["type"], "stall")
        self.assertEqual(items[0]["site"], "budget")
        self.assertEqual(items[0]["prd"], self.PRD)
        self.assertIn(self.BUDGET_REASON, items[0]["detail"])

        final = self._state()
        self.assertNotIn("stall_op", final)
        self.assertNotIn("tasks", final, "reset_prd_fields must have run")
        self.assertEqual(final["cycle"], 1)

    def test_budget_site_park_leaves_parks_consecutive_at_zero(self) -> None:
        # Contrast: NormalParkTests' wrapper_died park from 0 ends at 1.
        self._put_in_wip()
        self._write_budget_marker()
        self._write_state(self._sample_state(batch={
            "id": "202607300000", "completed_prds": [], "parks_consecutive": 0,
        }))

        self.assertEqual(self._do_park(), 0)

        self.assertEqual(self._state()["batch"]["parks_consecutive"], 0)

    def test_budget_site_park_after_a_wrapper_park_never_halts_and_resets_counter(self) -> None:
        # parks_consecutive=1 would trip the systemic halt (exit 5) for a
        # wrapper_died marker (SystemicHaltTests); a budget park must not.
        self._put_in_wip()
        self._write_budget_marker()
        self._write_state(self._sample_state(batch={
            "id": "202607300000", "completed_prds": [], "parks_consecutive": 1,
        }))

        rc = self._do_park()

        self.assertEqual(rc, 0)
        self.assertTrue(self._in_hold())
        self.assertFalse(self._marker_exists())

        final = self._state()
        self.assertEqual(final["batch"]["parks_consecutive"], 0)
        self.assertNotEqual(final.get("phase"), "paused")
        self.assertNotEqual(final.get("next_phase"), "paused")
        self.assertNotIn("pause_reason", final)

        items = self._deferred_items()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["site"], "budget")

    def test_budget_site_park_calls_do_stall_with_budget_site_and_no_mutator(self) -> None:
        self._put_in_wip()
        self._write_budget_marker()
        self._write_state(self._sample_state(batch={
            "id": "202607300000", "completed_prds": [], "parks_consecutive": 1,
        }))

        with mock.patch.object(records, "do_stall", wraps=records.do_stall) as spy:
            rc = self._do_park()

        self.assertEqual(rc, 0)
        self.assertEqual(spy.call_count, 1)
        kwargs = spy.call_args.kwargs
        self.assertEqual(kwargs["site"], "budget")
        self.assertIsNone(kwargs.get("extra_mutator"))
        self.assertEqual(kwargs["prd"], self.PRD)

    def test_budget_site_routes_on_marker_site_not_on_reason_text(self) -> None:
        # The reason carries no "budget" substring: routing must key on the
        # marker's site field. parks_consecutive=1 makes a wrapper_died
        # misroute visible (exit 5, counter 2, site "wrapper_died").
        reason = "token ceiling hit"
        self._put_in_wip()
        self._write_budget_marker(reason=reason)
        self._write_state(self._sample_state(batch={
            "id": "202607300000", "completed_prds": [], "parks_consecutive": 1,
        }))

        rc = self._do_park()

        self.assertEqual(rc, 0)
        self.assertTrue(self._in_hold())
        self.assertFalse(self._marker_exists())

        items = self._deferred_items()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["site"], "budget")
        self.assertIn(reason, items[0]["detail"])

        final = self._state()
        self.assertEqual(final["batch"]["parks_consecutive"], 0)
        self.assertNotIn("pause_reason", final)

    def test_budget_site_do_stall_failure_propagates_and_keeps_the_marker(self) -> None:
        self._put_in_wip()
        self._write_budget_marker()
        self._write_state(self._sample_state(batch={
            "id": "202607300000", "completed_prds": [], "parks_consecutive": 0,
        }))

        with mock.patch.object(records, "do_stall", return_value=4) as stub:
            rc = self._do_park()

        self.assertEqual(rc, 4, "a nonzero do_stall rc must propagate unchanged")
        self.assertEqual(stub.call_count, 1)
        self.assertEqual(stub.call_args.kwargs["site"], "budget")
        self.assertTrue(self._marker_exists(), "a failed park must not delete the marker")
        self.assertTrue(self._in_wip())
        self.assertEqual(self._deferred_items(), [])


class ResumeInFlightBudgetParkTests(_ParkTestCase):
    """Budget twin of ResumeInFlightParkTests (test_records_park_wrapper_died.py):
    a budget park crashed after stamping its stall_op, PRD still in wip/,
    marker still present. The resume must land the park exactly once, not
    reconcile it and then park it again."""

    def test_budget_site_resumes_a_park_left_mid_wip_exactly_once(self) -> None:
        self._put_in_wip()
        self._write_raw_marker(json.dumps({
            "prd": self.PRD, "reason": "prd budget exhausted", "site": "budget",
        }))
        state = self._sample_state(batch={
            "id": "202607300000", "completed_prds": [], "parks_consecutive": 0,
        })
        state["stall_op"] = {
            "op_id": "op-resume-budget-1",
            "prd": self.PRD,
            "site": "budget",
            "detail": "prd budget exhausted",
        }
        self._write_state(state)

        rc = self._do_park()

        self.assertEqual(rc, 0)
        self.assertFalse(self._marker_exists())
        self.assertFalse(self._in_wip())
        self.assertTrue(self._in_hold())

        items = self._deferred_items()
        self.assertEqual(len(items), 1, "the resumed budget park must record exactly once")
        self.assertEqual(
            items[0]["op_id"], "op-resume-budget-1",
            "resuming an in-flight intent must reuse its op_id, not mint a new one",
        )
        self.assertEqual(items[0]["site"], "budget")

        final = self._state()
        self.assertNotIn("stall_op", final)
        self.assertEqual(final["cycle"], 1)
        self.assertEqual(final["batch"]["parks_consecutive"], 0)


class BudgetSiteParseMarkerTests(_ParkTestCase):
    def test_budget_site_parse_marker_returns_the_marker_site(self) -> None:
        self._write_raw_marker(json.dumps({
            "prd": self.PRD, "reason": "prd budget exhausted", "site": "budget",
        }))

        self.assertEqual(
            records._parse_marker(self.marker_path),
            {"prd": self.PRD, "reason": "prd budget exhausted", "site": "budget"},
        )

    def test_budget_site_parse_marker_defaults_site_to_wrapper_died(self) -> None:
        self._write_marker(reason="wrapper died mid-session")

        self.assertEqual(
            records._parse_marker(self.marker_path),
            {"prd": self.PRD, "reason": "wrapper died mid-session", "site": "wrapper_died"},
        )


class BudgetSiteResetFieldTests(unittest.TestCase):
    def test_budget_site_prd_budget_since_is_a_per_prd_reset_field(self) -> None:
        self.assertIn("prd_budget_since", records.PER_PRD_RESET_FIELDS)

    def test_budget_site_reset_drops_prd_budget_since(self) -> None:
        reset = records.reset_prd_fields({"prd_budget_since": "2026-10-13T00:00:00Z", "batch": {}})

        self.assertNotIn("prd_budget_since", reset)


if __name__ == "__main__":
    unittest.main()
