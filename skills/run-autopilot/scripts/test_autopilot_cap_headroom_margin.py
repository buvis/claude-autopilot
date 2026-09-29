"""Tests for the HEADROOM_MARGIN and time term on `_headroom_exhausted`
(PRD 00218 follow-up).

Split out of test_autopilot_cap_headroom.py to keep that file under the
800-line limit; shares `_load_hook_module` with that module.

The margin cases call the predicate directly. The time-term cases drive the
HOOK end to end instead, because the term's whole point is the two reads
around the predicate: `_AUTOPILOT_SESSION_DEADLINE` out of the session's
environment, and the last completed task's `started_at`/`done_at` out of
state.json. A test that hands the predicate both numbers cannot see whether
either read happens at all.

`HookFixture.run_hook` builds the child env from `dict(os.environ)`, and the
sessions that run this suite export `_AUTOPILOT_SESSION_DEADLINE` themselves,
so every hook case here sets the variable or pops it explicitly - "absent"
is never the ambient default.
"""

from __future__ import annotations

import os
import time
import unittest
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

from test_autopilot_context_cap_hook import HookFixture, _load_hook_module

DEADLINE_ENV = "_AUTOPILOT_SESSION_DEADLINE"
RUNNER = Path(__file__).resolve().parent.parent / "cli" / "runner.py"

# A fire no term can carry on its own: 300K left under the 500K cap against
# a last task that cost 50K (margined threshold 62.5K), and 250 calls left
# under the 450 tripwire against a last task that cost 50 (threshold 62.5).
COMFORTABLE_TOTAL = 200_000
COMFORTABLE_COUNT = 200
CHEAP_USAGE = (100_000, 150_000)
CHEAP_CALLS = (100, 150)
STAMP_BASE = 1_700_000_000


@contextmanager
def _deadline(value: str | None) -> Iterator[None]:
    """Pin `_AUTOPILOT_SESSION_DEADLINE` in the env the hook subprocess
    inherits, restoring the ambient value afterwards. `None` POPS the key,
    which is the only honest way to test "no deadline" from a session that
    exports one."""
    with mock.patch.dict(os.environ):
        if value is None:
            os.environ.pop(DEADLINE_ENV, None)
        else:
            os.environ[DEADLINE_ENV] = value
        yield


def _epoch_in(secs: int) -> str:
    """The deadline value for `secs` seconds from now; negative for a
    deadline already past."""
    return str(int(time.time()) + secs)


def _completed(
    task_id: str,
    usage: tuple[int, int],
    calls: tuple[int, int],
    wall: int | None = None,
) -> dict:
    """A completed task carrying its recorded bounds and, when `wall` is
    given, the `started_at`/`done_at` stamps whose difference is that many
    seconds.

    Duplicated from test_autopilot_cap_headroom.py (a module helper there,
    but `_run_with`/`_marker_written` are methods on its TestCase) because
    that file is not this task's to edit. The copy there writes no stamps,
    which is exactly why its suite never sees the time term.
    """
    task: dict = {
        "id": task_id,
        "name": "done",
        "status": "completed",
        "usage_at_start": usage[0],
        "usage_at_done": usage[1],
        "calls_at_start": calls[0],
        "calls_at_done": calls[1],
    }
    if wall is not None:
        task["started_at"] = STAMP_BASE
        task["done_at"] = STAMP_BASE + wall
    return task


class HeadroomMarginTests(unittest.TestCase):
    def test_margin_hands_off_when_left_is_under_five_quarters_of_the_last_task(
        self,
    ) -> None:
        """173K left of USAGE_CAP (total=327_000) against a last task that
        cost 164K: HEADROOM_MARGIN's five-quarters threshold is 205K, and
        173K < 205K, so the rule fires even though 173K > 164K plainly."""
        module = _load_hook_module()
        self.assertTrue(module._headroom_exhausted(327_000, None, 164_000, 200))

    def test_time_term_is_false_when_plenty_of_time_remains(self) -> None:
        """5000s left against a last task whose wall time was 900s: the
        margined threshold is 900 * 1.25 = 1125, and 5000 is nowhere near
        under it, so the time term must not fire even though both
        secs_left and last_wall are set (it is not "any deadline plus any
        completed task's wall time means hand off")."""
        module = _load_hook_module()
        self.assertFalse(
            module._headroom_exhausted(
                300_000,
                120,
                150_000,
                200,
                secs_left=5000,
                last_wall=900,
            ),
        )

    def test_time_term_boundary_pins_strict_less_than(self) -> None:
        """The time term's margined threshold is last_wall * 1.25 = 1125
        for last_wall=900. Exactly at the threshold must stay False (the
        comparison is strict `<`, not `<=`); one second under must flip to
        True."""
        module = _load_hook_module()
        self.assertFalse(
            module._headroom_exhausted(
                None,
                None,
                150_000,
                200,
                secs_left=1125,
                last_wall=900,
            ),
        )
        self.assertTrue(
            module._headroom_exhausted(
                None,
                None,
                150_000,
                200,
                secs_left=1124,
                last_wall=900,
            ),
        )

    def test_usage_margin_boundary_pins_the_exact_multiplier(self) -> None:
        """HEADROOM_MARGIN's threshold for last_usage=164_000 is exactly
        164_000 * 1.25 = 205_000. USAGE_CAP - total sitting exactly on that
        threshold must stay False (strict `<`); one unit over the cap
        (i.e. one unit less headroom) must flip to True. This pins the
        multiplier precisely, closing the range of factors between ~1.055
        and ~3.05 that would otherwise also pass."""
        module = _load_hook_module()
        self.assertFalse(module._headroom_exhausted(295_000, None, 164_000, 200))
        self.assertTrue(module._headroom_exhausted(295_001, None, 164_000, 200))

    def test_calls_margin_fires_below_the_margined_threshold(self) -> None:
        """230 calls left of TURN_TRIPWIRE (count=220) against a last task
        that cost 200 calls: the calls term carries the same five-quarters
        margin as the usage term, so its threshold is 250 and 230 < 250
        fires - even though 230 > 200 plainly. Drop `* HEADROOM_MARGIN`
        from the calls term and this goes False."""
        module = _load_hook_module()
        self.assertTrue(module._headroom_exhausted(None, 220, 150_000, 200))

    def test_calls_margin_boundary_pins_the_exact_multiplier(self) -> None:
        """The calls threshold for last_calls=200 is exactly 200 * 1.25 =
        250. TURN_TRIPWIRE - count sitting exactly on it must stay False
        (strict `<`), which pins the multiplier rather than any factor that
        merely happens to fire on the case above."""
        module = _load_hook_module()
        self.assertFalse(module._headroom_exhausted(None, 200, 150_000, 200))


class TimeTermHookTests(unittest.TestCase):
    """The time term as the runtime sees it: hook subprocess, a deadline in
    the environment, and the wall span read off state.json."""

    def setUp(self) -> None:
        self._fresh()

    def _fresh(self) -> None:
        """A new temp cwd, so a marker written by an earlier case in the
        same test can never be read as this case's."""
        self.fx = HookFixture()
        self.addCleanup(self.fx.cleanup)

    def _run_with(
        self,
        *,
        total: int,
        count: int,
        tasks: list[dict],
        cap_rotations: object = None,
    ) -> None:
        """One fire at `total` tokens with the session counter seeded so
        this call is number `count`; task `t2` is always the one in
        progress. Duplicated from HeadroomHandoffTests, which owns it as a
        method on a file this task must not edit."""
        self.fx.write_state(
            phase="build",
            tasks=[*tasks, {"id": "t2", "name": "next", "status": "in_progress"}],
            cap_rotations=[] if cap_rotations is None else cap_rotations,
        )
        self.fx.write_transcript_lines([self.fx.usage_line(input_tokens=total)])
        self.fx.seed_counter("test-session", count - 1)
        result = self.fx.run_hook()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")
        self.assertNotIn("Traceback", result.stderr)
        self.assertFalse((self.fx.autopilot_dir / ".cap-fired").exists())

    def _run_timed(self, *, wall: int, cap_rotations: object = None) -> None:
        """One fire whose only tight term can be the clock: the last
        completed task cost 50K and 50 calls, and spanned `wall` seconds."""
        self._run_with(
            total=COMFORTABLE_TOTAL,
            count=COMFORTABLE_COUNT,
            tasks=[_completed("t1", CHEAP_USAGE, CHEAP_CALLS, wall=wall)],
            cap_rotations=cap_rotations,
        )

    def _marker_written(self) -> bool:
        return (self.fx.autopilot_dir / ".handoff-requested").exists()

    def test_time_term_hands_off_when_the_deadline_is_near(self) -> None:
        """A deadline 1000s out and a last completed task that spanned 900s:
        the margined threshold is 900 * 1.25 = 1125 and 1000 < 1125, so the
        hook hands off. Usage (300K left) and calls (250 left) are
        comfortable, so nothing but the clock can write this marker - which
        means the hook has to read both the env var and the task's stamps
        itself."""
        with _deadline(_epoch_in(1000)):
            self._run_timed(wall=900)
        self.assertTrue(self._marker_written())

    def test_time_term_is_inert_when_the_deadline_is_far(self) -> None:
        """The same 900s span against a deadline 100000s out (threshold
        1125) writes nothing: a far deadline is what proves the hook
        compares the distance rather than merely noticing that the variable
        is set. Wire the read so the parsed number is thrown away and every
        session spawned with a deadline hands off at its first task
        boundary, with every other case here still green."""
        with _deadline(_epoch_in(100_000)):
            self._run_timed(wall=900)
        self.assertFalse(self._marker_written())

    def test_time_term_is_inert_without_a_deadline(self) -> None:
        """With `_AUTOPILOT_SESSION_DEADLINE` popped from the child env
        there is no deadline to measure against, so the same state that
        hands off above writes no marker, however tight the 900s span is."""
        with _deadline(None):
            self._run_timed(wall=900)
        self.assertFalse(self._marker_written())

    def test_time_term_is_inert_without_a_completed_task(self) -> None:
        """A deadline 1000s out fires nothing when no completed task
        carries both stamps: neither a completed task recorded without
        `started_at`/`done_at` (the shape every pre-PRD-00218 state has) nor
        a state whose only task is still in progress gives a span to
        measure."""
        with _deadline(_epoch_in(1000)):
            self._run_with(
                total=COMFORTABLE_TOTAL,
                count=COMFORTABLE_COUNT,
                tasks=[_completed("t1", CHEAP_USAGE, CHEAP_CALLS)],
            )
            self.assertFalse(self._marker_written())
            self._fresh()
            self._run_with(total=COMFORTABLE_TOTAL, count=120, tasks=[])
        self.assertFalse(self._marker_written())

    def test_malformed_deadline_drops_the_time_term(self) -> None:
        """A deadline that is not an epoch int (`abc`, or the empty string)
        drops the time term instead of failing the hook: with usage and
        calls comfortable no marker appears, though a real deadline 1000s
        out would fire against the 900s span. Dropping the term must not
        disable the other two, so the second half exhausts usage (173K left
        against a 164K task) and calls (50 left against a 200-call task)
        under the same malformed deadline and requires the marker."""
        for value in ("abc", ""):
            with self.subTest(deadline=value, term="time"):
                self._fresh()
                with _deadline(value):
                    self._run_timed(wall=900)
                self.assertFalse(self._marker_written())
        with self.subTest(term="usage"):
            self._fresh()
            with _deadline("abc"):
                self._run_with(
                    total=327_000,
                    count=120,
                    tasks=[_completed("t1", (100_000, 264_000), (20, 220), wall=900)],
                )
            self.assertTrue(self._marker_written())
        with self.subTest(term="calls"):
            self._fresh()
            with _deadline("abc"):
                self._run_with(
                    total=COMFORTABLE_TOTAL,
                    count=400,
                    tasks=[_completed("t1", CHEAP_USAGE, (20, 220), wall=900)],
                )
            self.assertTrue(self._marker_written())

    def test_deadline_already_past_hands_off(self) -> None:
        """A deadline 60s in the past leaves -60s: a session out of time
        must hand off at the next boundary, so a past deadline is a firing
        value, never a reason to drop the term."""
        with _deadline(_epoch_in(-60)):
            self._run_timed(wall=900)
        self.assertTrue(self._marker_written())

    def test_a_rotated_task_wall_does_not_fire_the_time_term(self) -> None:
        """`started_at` is stamped once and never replaced, so a task cut
        mid-flight and finished in a later session carries every idle second
        between; that span is not work. The task's own id sits in
        `state.cap_rotations`, and a deadline 7200s out against its 6000s
        span (threshold 7500) would fire without that filter."""
        with _deadline(_epoch_in(7200)):
            self._run_timed(wall=6000, cap_rotations=[{"task_id": "t1"}])
        self.assertFalse(self._marker_written())

    def test_a_rotation_of_another_task_still_fires_the_time_term(self) -> None:
        """`cap_rotations` is per-PRD, so "this PRD rotated at some point"
        must not switch the time term off for the rest of the PRD. The
        measured task is un-rotated: its 6540s span against a deadline 7200s
        out (threshold 8175) hands off, even though a DIFFERENT task's
        rotation is on record."""
        with _deadline(_epoch_in(7200)):
            self._run_timed(wall=6540, cap_rotations=[{"task_id": "t0"}])
        self.assertTrue(self._marker_written())

    def test_a_paused_task_wall_does_not_fire_the_time_term(self) -> None:
        """A 40000s span is more wall time than a session can honestly
        spend on one task (a watchdog kill, an operator pause - what state
        does not record). It exceeds the credible ceiling, so it is
        discarded rather than used to hand off against a deadline 7200s
        out."""
        with _deadline(_epoch_in(7200)):
            self._run_timed(wall=40000)
        self.assertFalse(self._marker_written())

    def test_an_honest_long_wall_still_fires_the_time_term(self) -> None:
        """The credible ceiling must not swallow long-but-real tasks: a
        6540s span with no rotation on record against a deadline 7200s out
        (threshold 8175 > 7200) hands off."""
        with _deadline(_epoch_in(7200)):
            self._run_timed(wall=6540)
        self.assertTrue(self._marker_written())

    def test_a_malformed_cap_rotations_never_matches(self) -> None:
        """`cap_rotations` is state on disk, so any shape can appear. A
        string (whose `in` would match the task id character-wise), an entry
        that is not a dict, an empty entry and a null `task_id` must each
        leave the un-rotated 6540s span alone - marker written, and the hook
        never raising."""
        for rotations in ("t1", [{}], [{"task_id": None}], ["t1"]):
            with self.subTest(cap_rotations=rotations):
                self._fresh()
                with _deadline(_epoch_in(7200)):
                    self._run_timed(wall=6540, cap_rotations=rotations)
                self.assertTrue(self._marker_written())


class DeadlineSeamTests(unittest.TestCase):
    def test_deadline_env_name_matches_the_runner(self) -> None:
        """The runner writes the variable and the hook reads it, and no test
        can import both sides (`cli.runner` is not on this suite's path, and
        the writer hardcodes the name inline). So pin the seam the way this
        repo pins its other cross-boundary strings - read the writer as text
        and require the reader's constant in it. Rename one side only and
        the deadline silently never reaches the hook."""
        # Local import: the constant ships with the wiring this file pins.
        import _cap_headroom

        self.assertIn(
            _cap_headroom.DEADLINE_ENV,
            RUNNER.read_text(),
            f"{RUNNER}: the runner no longer exports "
            f"{_cap_headroom.DEADLINE_ENV!r}, so the hook's time term is "
            "dead at runtime while every unit test still passes",
        )


if __name__ == "__main__":
    unittest.main()
