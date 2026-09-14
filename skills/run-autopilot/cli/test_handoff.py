#!/usr/bin/env python3
"""Tests for cli/handoff.clear_markers and its three wiring sites: the
`phase-done` and `reset-prd` verbs in cli/__main__.py, and the successful
commit path inside records.do_stall (reached by the `stall` verb and, through
the park reconciliation, by `park`).

    clear_markers(autopilot_dir) -> None

removes `.handoff-requested` and `.cap-fired` from the directory holding
state.json, and is called ONLY after a lifecycle commit that ends the current
PRD or phase. The behavior under test is therefore a pair: which operations
clear the two markers, and which leave them exactly as they were.

The clear/preserve split is what these tests bind, row by row:

  build + tasks_done -> review              clear
  review + converged -> done                clear
  done + more_prds -> build (next PRD)      clear
  build/done + drained -> terminal          clear
  successful stall / park / reset-prd       clear
  review + rework -> same phase, same PRD   preserve
  any rejected or failed transaction        preserve

Every CLI row runs `cli/__main__.py` as a real subprocess against a synthetic
<root>/dev/local/{autopilot,prds} tree, matching test_lifecycle_cli.py. The
preserve rows assert the marker BYTES, not just existence, so a cleanup that
truncated or rewrote a marker could not pass as "preserved". The clear rows
assert a sibling file survives, so a cleanup that emptied the directory could
not pass as "cleared".

The two pure helpers this feature deliberately does NOT touch
(transitions.apply, records.reset_prd_fields) are covered in
test_transitions.py / test_records.py; nothing here stubs filesystem access
inside them, because they have none to stub.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cli import handoff

CLI_DIR = Path(__file__).resolve().parent
CLI_MAIN = CLI_DIR / "__main__.py"

HANDOFF_MARKER = ".handoff-requested"
CAP_MARKER = ".cap-fired"


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CLI_MAIN), *args],
        capture_output=True,
        text=True,
        cwd=str(cwd),
    )


def _state(**overrides) -> dict:
    base = {
        "prd": "00089-example-v1.md",
        "phase": "build",
        "next_phase": "build",
        "cycle": 1,
        "phases_completed": [],
        "batch": {"id": "202608071200", "completed_prds": [], "parks_consecutive": 0},
    }
    base.update(overrides)
    return base


class _MarkerTestCase(unittest.TestCase):
    """A synthetic <root>/dev/local/{autopilot,prds} tree per test, plus the
    two handoff markers and a sibling bystander file in the autopilot dir."""

    PRD = "00089-example-v1.md"
    HANDOFF_BODY = "handoff requested at 12:00\n"
    CAP_BODY = '{"usage": 512000}\n'

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.autopilot_dir = self.root / "dev" / "local" / "autopilot"
        self.autopilot_dir.mkdir(parents=True)
        self.prds_dir = self.root / "dev" / "local" / "prds"
        for lifecycle in ("wip", "backlog", "hold"):
            (self.prds_dir / lifecycle).mkdir(parents=True)
        self.state_path = self.autopilot_dir / "state.json"
        self.handoff_marker = self.autopilot_dir / HANDOFF_MARKER
        self.cap_marker = self.autopilot_dir / CAP_MARKER
        self.bystander = self.autopilot_dir / "session-log.txt"

    # -- fixtures ---------------------------------------------------------
    def write_state(self, **overrides) -> None:
        self.state_path.write_text(json.dumps(_state(**overrides)), encoding="utf-8")

    def read_state(self) -> dict:
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def put_markers(self) -> None:
        self.handoff_marker.write_text(self.HANDOFF_BODY, encoding="utf-8")
        self.cap_marker.write_text(self.CAP_BODY, encoding="utf-8")
        self.bystander.write_text("unrelated\n", encoding="utf-8")

    def put_prd(self, lifecycle: str, name: str, body: str = "# PRD\n") -> Path:
        path = self.prds_dir / lifecycle / name
        path.write_text(body, encoding="utf-8")
        return path

    # -- assertions -------------------------------------------------------
    def assert_markers_cleared(self) -> None:
        self.assertFalse(self.handoff_marker.exists(), HANDOFF_MARKER)
        self.assertFalse(self.cap_marker.exists(), CAP_MARKER)
        self.assertTrue(
            self.bystander.exists(),
            "only the two markers may go; siblings in the dir stay",
        )
        self.assertTrue(self.state_path.exists(), "state.json is not a marker")

    def assert_markers_preserved(self) -> None:
        self.assertEqual(
            self.handoff_marker.read_text(encoding="utf-8"),
            self.HANDOFF_BODY,
            "the handoff marker must survive byte-for-byte",
        )
        self.assertEqual(
            self.cap_marker.read_text(encoding="utf-8"),
            self.CAP_BODY,
            "the cap marker must survive byte-for-byte",
        )


class ClearMarkersTests(_MarkerTestCase):
    """The exported helper itself, called directly."""

    def test_removes_both_markers_and_leaves_the_rest_of_the_directory(self) -> None:
        self.put_markers()
        self.write_state()

        self.assertIsNone(handoff.clear_markers(self.autopilot_dir))

        self.assert_markers_cleared()

    def test_absent_markers_are_not_an_error(self) -> None:
        self.bystander.write_text("unrelated\n", encoding="utf-8")

        handoff.clear_markers(self.autopilot_dir)

        self.assertFalse(self.handoff_marker.exists())
        self.assertFalse(self.cap_marker.exists())
        self.assertTrue(self.bystander.exists())

    def test_one_marker_present_is_removed_without_the_other(self) -> None:
        self.cap_marker.write_text(self.CAP_BODY, encoding="utf-8")

        handoff.clear_markers(self.autopilot_dir)

        self.assertFalse(self.cap_marker.exists())

    def test_an_unremovable_marker_does_not_block_the_other_or_raise(self) -> None:
        # A directory standing where a marker file belongs: unlink raises
        # OSError. Both orders are exercised, so a helper that removed the
        # two in a single try block would fail on whichever it reached first.
        for broken, survivor in (
            (self.cap_marker, self.handoff_marker),
            (self.handoff_marker, self.cap_marker),
        ):
            with self.subTest(broken=broken.name):
                broken.mkdir()
                (broken / "occupant").write_text("x", encoding="utf-8")
                survivor.write_text("marker\n", encoding="utf-8")

                handoff.clear_markers(self.autopilot_dir)

                self.assertFalse(
                    survivor.exists(),
                    "a failure on one marker must not skip the other",
                )
                (broken / "occupant").unlink()
                broken.rmdir()


class PhaseDoneMarkerTests(_MarkerTestCase):
    def _phase_done(self, outcome: str) -> subprocess.CompletedProcess:
        return _run(
            ["phase-done", "--state", str(self.state_path), "--outcome", outcome],
            cwd=self.root,
        )

    def test_tasks_done_clears_the_markers_when_the_build_gate_advances(self) -> None:
        self.write_state(phase="build", next_phase="build")
        self.put_markers()

        proc = self._phase_done("tasks_done")

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.read_state()["phase"], "review")
        self.assert_markers_cleared()

    def test_converged_clears_the_markers_when_the_prd_reaches_done(self) -> None:
        self.write_state(phase="review", next_phase="review", cycle=2)
        self.put_markers()

        proc = self._phase_done("converged")

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.read_state()["phase"], "done")
        self.assert_markers_cleared()

    def test_more_prds_clears_the_markers_when_the_next_prd_starts(self) -> None:
        self.write_state(
            phase="done",
            next_phase="done",
            cycle=3,
            phases_completed=["review"],
            work_start_sha="abc123",
        )
        self.put_markers()

        proc = self._phase_done("more_prds")

        self.assertEqual(proc.returncode, 0, proc.stderr)
        state = self.read_state()
        self.assertEqual(state["phase"], "build")
        self.assertEqual(state["cycle"], 1)
        self.assert_markers_cleared()

    def test_drained_clears_the_markers_from_either_terminal_phase(self) -> None:
        for phase in ("done", "build"):
            with self.subTest(phase=phase):
                self.write_state(phase=phase, next_phase=phase)
                self.put_markers()

                proc = self._phase_done("drained")

                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertEqual(self.read_state()["next_phase"], "")
                self.assert_markers_cleared()

    def test_rework_preserves_the_markers_although_the_commit_succeeds(self) -> None:
        # The one successful outcome that stays on the same phase and PRD:
        # the session continues, so a pending handoff or cap must survive.
        self.write_state(
            phase="review",
            next_phase="review",
            cycle=2,
            rework_task_ids=["7"],
        )
        self.put_markers()

        proc = self._phase_done("rework")

        self.assertEqual(proc.returncode, 0, proc.stderr)
        state = self.read_state()
        self.assertEqual(state["cycle"], 3, "the transaction really did commit")
        self.assertEqual(state["phase"], "review")
        self.assert_markers_preserved()

    def test_a_rejected_transition_preserves_the_markers(self) -> None:
        self.write_state(phase="build", next_phase="build")
        self.put_markers()
        before = self.state_path.read_bytes()

        proc = self._phase_done("converged")

        self.assertEqual(proc.returncode, 1)
        self.assertEqual(self.state_path.read_bytes(), before, "nothing committed")
        self.assert_markers_preserved()

    def test_missing_markers_do_not_disturb_a_successful_phase_done(self) -> None:
        self.write_state(phase="build", next_phase="build")

        proc = self._phase_done("tasks_done")

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.read_state()["phase"], "review")
        self.assertNotIn(HANDOFF_MARKER, proc.stderr, "an absent marker is silent")
        self.assertNotIn(CAP_MARKER, proc.stderr, "an absent marker is silent")

    def test_a_marker_that_cannot_be_removed_does_not_fail_the_command(self) -> None:
        self.write_state(phase="build", next_phase="build")
        self.put_markers()
        self.cap_marker.unlink()
        self.cap_marker.mkdir()
        (self.cap_marker / "occupant").write_text("x", encoding="utf-8")

        proc = self._phase_done("tasks_done")

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertEqual(self.read_state()["phase"], "review", "the phase still landed")
        self.assertFalse(
            self.handoff_marker.exists(),
            "the removable marker must still go when its sibling fails",
        )


class ResetPrdMarkerTests(_MarkerTestCase):
    def test_a_successful_reset_prd_clears_the_markers(self) -> None:
        self.write_state(
            phase="build",
            next_phase="build",
            cycle=4,
            tasks=[{"id": "1", "status": "completed"}],
        )
        self.put_markers()

        proc = _run(["reset-prd", "--state", str(self.state_path)], cwd=self.root)

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.read_state()["cycle"], 1, "the reset really committed")
        self.assert_markers_cleared()

    def test_reset_prd_against_an_unreadable_state_preserves_the_markers(self) -> None:
        self.state_path.write_text("{ not json", encoding="utf-8")
        self.put_markers()

        proc = _run(["reset-prd", "--state", str(self.state_path)], cwd=self.root)

        self.assertEqual(proc.returncode, 2)
        self.assert_markers_preserved()


class StallMarkerTests(_MarkerTestCase):
    def _stall(self, detail: str = "design gate refused") -> subprocess.CompletedProcess:
        return _run(
            [
                "stall",
                "--state",
                str(self.state_path),
                "--prd",
                self.PRD,
                "--site",
                "design_gate",
                "--detail",
                detail,
                "--prds",
                str(self.prds_dir),
            ],
            cwd=self.root,
        )

    def test_a_successful_stall_clears_the_markers(self) -> None:
        self.write_state(phase="build", next_phase="build", cycle=2)
        self.put_prd("wip", self.PRD)
        self.put_markers()

        proc = self._stall()

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(
            (self.prds_dir / "hold" / self.PRD).exists(),
            "the stall really reached its commit",
        )
        self.assert_markers_cleared()

    def test_a_stall_that_cannot_read_the_state_preserves_the_markers(self) -> None:
        self.state_path.write_text("{ not json", encoding="utf-8")
        self.put_prd("wip", self.PRD)
        self.put_markers()

        proc = self._stall()

        self.assertEqual(proc.returncode, 2)
        self.assertTrue(
            (self.prds_dir / "wip" / self.PRD).exists(),
            "the stall never reached its commit",
        )
        self.assert_markers_preserved()

    def test_a_stall_whose_prd_is_nowhere_preserves_the_markers(self) -> None:
        # Exit 4: the move fails, so the commit never runs even though the
        # intent was already stamped.
        self.write_state(phase="build", next_phase="build", cycle=2)
        self.put_markers()

        proc = self._stall()

        self.assertEqual(proc.returncode, 4)
        self.assert_markers_preserved()


class ParkMarkerTests(_MarkerTestCase):
    def _park(self) -> subprocess.CompletedProcess:
        return _run(
            ["park", "--state", str(self.state_path), "--prds", str(self.prds_dir)],
            cwd=self.root,
        )

    def test_an_end_to_end_park_clears_the_markers_too(self) -> None:
        self.write_state(phase="build", next_phase="build", cycle=2)
        self.put_prd("wip", self.PRD)
        (self.autopilot_dir / "park-requested").write_text(
            json.dumps({"prd": self.PRD, "reason": "wrapper died mid-session"}),
            encoding="utf-8",
        )
        self.put_markers()

        proc = self._park()

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue((self.prds_dir / "hold" / self.PRD).exists())
        self.assertFalse(
            (self.autopilot_dir / "park-requested").exists(),
            "the park-requested marker is consumed as before",
        )
        self.assert_markers_cleared()

    def test_a_park_with_nothing_to_consume_preserves_the_markers(self) -> None:
        self.write_state(phase="build", next_phase="build", cycle=2)
        self.put_prd("wip", self.PRD)
        self.put_markers()

        proc = self._park()

        self.assertEqual(proc.returncode, 3, proc.stderr)
        self.assertTrue(
            (self.prds_dir / "wip" / self.PRD).exists(),
            "nothing was parked, so no commit ran",
        )
        self.assert_markers_preserved()


if __name__ == "__main__":
    unittest.main()
