"""Task wall-clock bounds and scan-back tests (PRD 00200, PRD 00218, PRD 00243).

Split out of `test_autopilot_cap_headroom.py` to keep that file under the
800-line limit (PRD 00230): `TaskBoundsWallTests` moved here verbatim, and
`TrustedLastWallScanTests` joins it to pin the rewritten scan-back behavior
of `_cap_headroom.trusted_last_wall` (PRD 00243, review 00229).

Unit-level: exercises `_cap_task_record.py` and `_cap_headroom.py` directly
on synthetic state dicts, no hook subprocess involved. The suite runs from
scripts/ on sys.path, so the import resolves.
"""

import contextlib
import io
import unittest

from _cap_headroom import MAX_CREDIBLE_WALL_SECS, trusted_last_wall
from _cap_task_record import (
    BOUND_FIELDS,
    DONE_FIELDS,
    START_FIELDS,
    last_task_cost,
    last_task_wall,
    record_task_bounds,
)


class TaskBoundsWallTests(unittest.TestCase):
    """`record_task_bounds`'s `now` stamp and `last_task_wall` on top of it.

    Unit-level: exercises `_cap_task_record.py` directly on synthetic state
    dicts, no hook subprocess involved.
    """

    def test_start_fire_stamps_started_at(self) -> None:
        """The first fire after a task turns in_progress stamps `started_at`
        as the third value of the START pair, alongside the existing
        usage/calls stamps."""
        state = {"tasks": [{"id": "t1", "status": "in_progress"}]}
        record_task_bounds(state, "t1", 100_000, 20, 1_700_000_000, warn=True)
        task = state["tasks"][0]
        self.assertEqual(task["usage_at_start"], 100_000)
        self.assertEqual(task["calls_at_start"], 20)
        self.assertEqual(task["started_at"], 1_700_000_000)

    def test_done_fire_stamps_done_at(self) -> None:
        """The first fire after a task turns completed stamps `done_at` as
        the third value of the DONE pair, and the task id comes back as
        `done_task`."""
        state = {
            "tasks": [
                {
                    "id": "t1",
                    "status": "completed",
                    "usage_at_start": 100_000,
                    "calls_at_start": 20,
                    "started_at": 1_700_000_000,
                },
            ],
        }
        changed, done_task = record_task_bounds(
            state, "t2", 250_000, 220, 1_700_000_500, warn=True
        )
        task = state["tasks"][0]
        self.assertTrue(changed)
        self.assertEqual(done_task, "t1")
        self.assertEqual(task["usage_at_done"], 250_000)
        self.assertEqual(task["calls_at_done"], 220)
        self.assertEqual(task["done_at"], 1_700_000_500)

    def test_started_at_survives_a_second_session(self) -> None:
        """A `started_at` already stamped is never replaced by a later call:
        time does not restart at a rotation, the same never-rewrite rule the
        usage/calls halves of the START pair already follow."""
        state = {
            "tasks": [
                {
                    "id": "t1",
                    "status": "in_progress",
                    "usage_at_start": 50_000,
                    "calls_at_start": 5,
                    "started_at": 1_700_000_000,
                },
            ],
        }
        changed, _ = record_task_bounds(
            state, "t1", 90_000, 15, 1_700_001_000, warn=True
        )
        self.assertFalse(changed)
        self.assertEqual(state["tasks"][0]["started_at"], 1_700_000_000)

    def test_start_and_done_fields_are_three_tuples_ending_in_the_stamp(
        self,
    ) -> None:
        """The PRD's contract makes `started_at`/`done_at` the third member
        of `START_FIELDS`/`DONE_FIELDS`, with `now` as the third pair value
        routed through the same `record_pair` machinery as usage/calls."""
        self.assertEqual(
            START_FIELDS, ("usage_at_start", "calls_at_start", "started_at")
        )
        self.assertEqual(DONE_FIELDS, ("usage_at_done", "calls_at_done", "done_at"))

    def test_bound_fields_excludes_the_stamps_so_last_task_cost_ignores_them(
        self,
    ) -> None:
        """`BOUND_FIELDS` stays the four usage/call bounds; a malformed
        `started_at` on an otherwise well-formed completed record must not
        push `last_task_cost` onto the estimates fallback."""
        self.assertEqual(
            BOUND_FIELDS,
            ("usage_at_start", "usage_at_done", "calls_at_start", "calls_at_done"),
        )
        task = {
            "id": "t1",
            "status": "completed",
            "usage_at_start": 100_000,
            "usage_at_done": 220_000,
            "calls_at_start": 20,
            "calls_at_done": 170,
            "started_at": "not-a-timestamp",
        }
        self.assertEqual(last_task_cost({"tasks": [task]}, (1, 1)), (120_000, 150))

    def test_done_fire_stamps_done_at_when_usage_and_calls_are_already_recorded(
        self,
    ) -> None:
        """A completed record whose `usage_at_done`/`calls_at_done` are
        already stamped still acquires `done_at` on the next fire, rather
        than being skipped because the usage/calls half of the pair reports
        no change."""
        state = {
            "tasks": [
                {
                    "id": "t1",
                    "status": "completed",
                    "usage_at_start": 100_000,
                    "calls_at_start": 20,
                    "started_at": 1_700_000_000,
                    "usage_at_done": 250_000,
                    "calls_at_done": 220,
                },
            ],
        }
        changed, done_task = record_task_bounds(
            state, "t2", 999_999, 999, 1_700_000_500, warn=True
        )
        self.assertTrue(changed)
        self.assertEqual(done_task, "t1")
        self.assertEqual(state["tasks"][0]["done_at"], 1_700_000_500)

    def test_done_at_survives_a_second_session(self) -> None:
        """A `done_at` already stamped is never replaced by a later call,
        the same never-rewrite rule `started_at` follows: a fully-stamped
        completed record reports no change and keeps its original stamp."""
        state = {
            "tasks": [
                {
                    "id": "t1",
                    "status": "completed",
                    "usage_at_start": 100_000,
                    "calls_at_start": 20,
                    "started_at": 1_700_000_000,
                    "usage_at_done": 250_000,
                    "calls_at_done": 220,
                    "done_at": 1_700_000_500,
                },
            ],
        }
        changed, done_task = record_task_bounds(
            state, "t2", 300_000, 260, 1_700_009_999, warn=True
        )
        self.assertFalse(changed)
        self.assertIsNone(done_task)
        self.assertEqual(state["tasks"][0]["done_at"], 1_700_000_500)

    def test_non_int_started_at_warns_via_the_shared_diagnostic(self) -> None:
        """A non-int `started_at` is named on the same `_warn_non_int`
        stderr line the usage/call fields already get, once per fire, then
        overwritten like any other malformed field."""
        state = {
            "tasks": [
                {
                    "id": "t1",
                    "status": "in_progress",
                    "usage_at_start": 100_000,
                    "calls_at_start": 20,
                    "started_at": "bad",
                },
            ],
        }
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            record_task_bounds(state, "t1", 100_000, 20, 1_700_000_000, warn=True)
        lines = [
            line for line in stderr.getvalue().splitlines() if "not an int" in line
        ]
        self.assertEqual(len(lines), 1, stderr.getvalue())
        self.assertIn("started_at", lines[0])
        self.assertEqual(state["tasks"][0]["started_at"], 1_700_000_000)

    def test_module_docstring_names_the_stamp_fields_not_four_ints(self) -> None:
        """The module docstring describes the wall-clock stamps it now
        writes and no longer claims the record is "four ints"."""
        import _cap_task_record

        doc = _cap_task_record.__doc__ or ""
        self.assertNotIn("four ints", doc)
        self.assertIn("started_at", doc)
        self.assertIn("done_at", doc)

    def test_last_task_wall_reads_the_latest_completed_task(self) -> None:
        """`last_task_wall` reads `done_at - started_at` of the LAST
        completed task in list order, the same "most recent" rule
        `last_task_cost` already uses, ignoring an earlier completed task's
        span."""
        earlier = {
            "id": "a",
            "status": "completed",
            "started_at": 1_000,
            "done_at": 1_100,
        }
        latest = {
            "id": "b",
            "status": "completed",
            "started_at": 2_000,
            "done_at": 2_300,
        }
        state = {"tasks": [earlier, latest]}
        self.assertEqual(last_task_wall(state), 300)

    def test_last_task_wall_is_none_without_stamps(self) -> None:
        """No completed task carries both `started_at` and `done_at` as
        ints: `None`, not a crash or a fallback value."""
        no_stamps = {"id": "a", "status": "completed"}
        non_int = {
            "id": "b",
            "status": "completed",
            "started_at": "later",
            "done_at": 2_000,
        }
        pending = {"id": "c", "status": "pending", "started_at": 1, "done_at": 2}
        self.assertIsNone(last_task_wall({"tasks": [no_stamps]}))
        self.assertIsNone(last_task_wall({"tasks": [non_int]}))
        self.assertIsNone(last_task_wall({"tasks": [pending]}))

    def test_last_task_wall_rejects_a_negative_span(self) -> None:
        """A `done_at` before its `started_at` (a stale start from an
        earlier session) is not a valid span: `None`, never a negative
        number."""
        negative = {
            "id": "a",
            "status": "completed",
            "started_at": 5_000,
            "done_at": 4_000,
        }
        self.assertIsNone(last_task_wall({"tasks": [negative]}))

    def test_last_task_wall_falls_back_to_an_earlier_valid_span(self) -> None:
        """A partly stamped tail does not end the scan: with the LATEST
        completed task carrying no stamps, `last_task_wall` keeps walking
        back to the most recent completed task whose two stamps are ints
        with a non-negative difference, rather than returning `None` on the
        first unusable one."""
        valid_earlier = {
            "id": "a",
            "status": "completed",
            "started_at": 1_000,
            "done_at": 1_150,
        }
        unstamped_latest = {"id": "b", "status": "completed"}
        state = {"tasks": [valid_earlier, unstamped_latest]}
        self.assertEqual(last_task_wall(state), 150)


class TrustedLastWallScanTests(unittest.TestCase):
    """`_cap_headroom.trusted_last_wall`'s scan-back behavior (PRD 00243).

    The context-cap hook reads this function, not `last_task_wall`, for its
    time term (review 00229). It must skip an unusable completed task and
    keep walking back for an earlier one, exactly like `last_task_wall`
    already does - while still stopping outright on a rotated or
    over-ceiling span, the two deliberate stops this PRD leaves unchanged.
    """

    def test_an_unstamped_task_is_skipped_not_fatal(self) -> None:
        """The LATEST completed task carries no stamps at all: the scan
        keeps walking back to the most recent completed task whose stamps
        are usable, instead of returning `None` on the first miss."""
        valid_earlier = {
            "id": "a",
            "status": "completed",
            "started_at": 1_000,
            "done_at": 1_150,
        }
        unstamped_latest = {"id": "b", "status": "completed"}
        state = {"tasks": [valid_earlier, unstamped_latest]}
        self.assertEqual(trusted_last_wall(state), 150)

    def test_a_negative_span_is_skipped(self) -> None:
        """The LATEST completed task's `done_at` precedes its `started_at`
        (a stale start from an earlier session): that entry is unusable, not
        a stop signal, so the scan keeps walking back to an earlier valid
        span instead of returning `None`."""
        valid_earlier = {
            "id": "a",
            "status": "completed",
            "started_at": 1_000,
            "done_at": 1_150,
        }
        negative_latest = {
            "id": "b",
            "status": "completed",
            "started_at": 5_000,
            "done_at": 4_000,
        }
        state = {"tasks": [valid_earlier, negative_latest]}
        self.assertEqual(trusted_last_wall(state), 150)

    def test_a_non_dict_entry_never_raises(self) -> None:
        """A non-dict entry in `state.tasks` (a hand-edited or corrupted
        state file) is skipped like any other unusable entry. Nothing in the
        PostToolUse hook catches an `AttributeError` from here, so a crash
        on this shape would take the whole hook down with it."""
        valid_earlier = {
            "id": "a",
            "status": "completed",
            "started_at": 1_000,
            "done_at": 1_150,
        }
        state = {"tasks": [valid_earlier, "not-a-dict"]}
        self.assertEqual(trusted_last_wall(state), 150)

    def test_boolean_stamps_are_rejected(self) -> None:
        """`True`/`False` satisfy `isinstance(..., int)` but are never a
        real stamp: a boolean `started_at`/`done_at` on the LATEST completed
        task must be treated as absent, not as a valid (bogus) zero-length
        span that shadows an earlier task's real one."""
        valid_earlier = {
            "id": "a",
            "status": "completed",
            "started_at": 1_000,
            "done_at": 1_150,
        }
        bool_latest = {
            "id": "b",
            "status": "completed",
            "started_at": True,
            "done_at": True,
        }
        state = {"tasks": [valid_earlier, bool_latest]}
        self.assertEqual(trusted_last_wall(state), 150)

    def test_rotation_still_stops_the_scan(self) -> None:
        """A rotated task's wall spans both sessions (`record_task_bounds`
        never replaces `started_at`), so the scan must stop there outright -
        never fall through to an earlier task's span - even though the
        rotated entry is otherwise perfectly usable."""
        valid_earlier = {
            "id": "a",
            "status": "completed",
            "started_at": 1_000,
            "done_at": 1_100,
        }
        rotated_latest = {
            "id": "b",
            "status": "completed",
            "started_at": 2_000,
            "done_at": 2_300,
        }
        state = {
            "tasks": [valid_earlier, rotated_latest],
            "cap_rotations": [{"task_id": "b"}],
        }
        self.assertIsNone(trusted_last_wall(state))

    def test_the_ceiling_still_stops_the_scan(self) -> None:
        """A span above `MAX_CREDIBLE_WALL_SECS` (a watchdog kill or an
        operator pause state does not otherwise record) stops the scan
        outright, the same deliberate backstop as the rotation stop - never
        a fall-through to an earlier task's span."""
        valid_earlier = {
            "id": "a",
            "status": "completed",
            "started_at": 1_000,
            "done_at": 1_100,
        }
        over_ceiling_latest = {
            "id": "b",
            "status": "completed",
            "started_at": 0,
            "done_at": MAX_CREDIBLE_WALL_SECS + 1,
        }
        state = {"tasks": [valid_earlier, over_ceiling_latest]}
        self.assertIsNone(trusted_last_wall(state))

    def test_trusted_last_wall_agrees_with_last_task_wall(self) -> None:
        """With no rotation and no over-ceiling span in play,
        `trusted_last_wall` and `last_task_wall` walk `state.tasks` the same
        way and must never disagree - the design doc's pin against the two
        walks silently drifting apart."""
        valid_earlier = {
            "id": "a",
            "status": "completed",
            "started_at": 1_000,
            "done_at": 1_150,
        }
        unstamped_latest = {"id": "b", "status": "completed"}
        state = {"tasks": [valid_earlier, unstamped_latest]}
        self.assertEqual(trusted_last_wall(state), last_task_wall(state))


if __name__ == "__main__":
    unittest.main()
