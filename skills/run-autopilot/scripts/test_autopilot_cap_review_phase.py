"""Review-phase cases for autopilot_context_cap_hook.py (PRD 00196): a
rotation or stall inside a review-phase rework session returns to the review
gate, records its phase, and a build-era rotation entry never counts against
a task's fresh attempt in review.

Split out of test_autopilot_cap_rotation.py to keep each file under the
800-line limit. Shares HookFixture with test_autopilot_context_cap_hook.py;
the suite runs from scripts/ on sys.path, so the import resolves.
"""

import json
import unittest

from test_autopilot_context_cap_hook import HookFixture


class ReviewPhaseRotationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fx = HookFixture()
        self.addCleanup(self.fx.cleanup)

    def test_rotation_in_review_phase_sets_next_phase_review(self) -> None:
        """PRD 00196: a rotation inside a review-phase rework session returns
        to the phase it left - next_phase is review, never build - and the
        envelope names it; the rework task is reset to pending as in build."""
        self.fx.write_state(
            phase="review",
            next_phase="review",
            cycle=2,
            rework_task_ids=["7"],
            tasks=[{"id": "7", "name": "rework", "status": "in_progress"}],
        )
        self.fx.write_transcript_lines([self.fx.usage_line(input_tokens=600_000)])
        result = self.fx.run_hook()
        self.assertEqual(result.returncode, 0)
        state = json.loads((self.fx.autopilot_dir / "state.json").read_text())
        self.assertEqual(state["next_phase"], "review")
        self.assertEqual(state["phase"], "review")
        self.assertEqual(
            state["cap_rotations"],
            [{"task_id": "7", "cycle": 2, "phase": "review"}],
        )
        self.assertEqual(state["tasks"][0]["status"], "pending")
        self.assertEqual(state["rework_task_ids"], ["7"])
        context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("next_phase is set to review", context)
        self.assertNotIn("set to build", context)

    def test_build_era_rotation_does_not_livelock_a_review_flagged_task(self) -> None:
        """A task that rotated during build, completed, and was review-flagged
        keeps its build rotation entry; its first breach in review is a fresh
        attempt, so it rotates again (with the review phase recorded) instead
        of parking the PRD as an oversized task (review 1 of PRD 00196)."""
        self.fx.write_state(
            phase="review",
            next_phase="review",
            cycle=1,
            rework_task_ids=["task-x"],
            cap_rotations=[{"task_id": "task-x", "cycle": 1, "phase": "build"}],
            tasks=[{"id": "task-x", "name": "flagged", "status": "in_progress"}],
        )
        self.fx.write_transcript_lines([self.fx.usage_line(input_tokens=600_000)])
        result = self.fx.run_hook()
        self.assertEqual(result.returncode, 0)
        state = json.loads((self.fx.autopilot_dir / "state.json").read_text())
        self.assertNotIn("stall_reason", state)
        self.assertEqual(
            state["cap_rotations"],
            [
                {"task_id": "task-x", "cycle": 1, "phase": "build"},
                {"task_id": "task-x", "cycle": 1, "phase": "review"},
            ],
        )
        self.assertEqual(state["next_phase"], "review")
        self.assertIn("rotation", result.stdout.lower())

    def test_second_review_rotation_of_the_same_task_livelocks_in_review(self) -> None:
        """Two consecutive review-phase rotations of one rework task are the
        real livelock: the oversized-task stall is recorded and next_phase
        stays on review (PRD 00196: the stall writes next_phase = phase)."""
        self.fx.write_state(
            phase="review",
            next_phase="review",
            cycle=1,
            rework_task_ids=["task-x"],
            cap_rotations=[{"task_id": "task-x", "cycle": 1, "phase": "review"}],
            tasks=[{"id": "task-x", "name": "flagged", "status": "in_progress"}],
        )
        self.fx.write_transcript_lines([self.fx.usage_line(input_tokens=600_000)])
        result = self.fx.run_hook()
        self.assertEqual(result.returncode, 0)
        state = json.loads((self.fx.autopilot_dir / "state.json").read_text())
        self.assertEqual(state["stall_reason"]["stalled"], "oversized_task")
        self.assertEqual(len(state["cap_rotations"]), 1)
        self.assertEqual(state["next_phase"], "review")
        self.assertIn("oversized", result.stdout.lower())

    def test_legacy_rotation_entry_without_phase_counts_as_build(self) -> None:
        """Entries written before PRD 00196 carry no phase and were all build
        rotations: a second build breach of that task still livelocks."""
        self.fx.write_state(
            phase="build",
            cap_rotations=[{"task_id": "task-x", "cycle": 1}],
            tasks=[{"id": "task-x", "name": "y", "status": "in_progress"}],
        )
        self.fx.write_transcript_lines([self.fx.usage_line(input_tokens=600_000)])
        result = self.fx.run_hook()
        self.assertEqual(result.returncode, 0)
        state = json.loads((self.fx.autopilot_dir / "state.json").read_text())
        self.assertEqual(state["stall_reason"]["stalled"], "oversized_task")
        self.assertEqual(state["next_phase"], "build")


if __name__ == "__main__":
    unittest.main()
