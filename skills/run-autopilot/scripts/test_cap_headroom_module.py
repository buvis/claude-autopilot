"""Tests for `_cap_headroom`, the pure module behind the context-cap hook's
headroom rule (PRD 00218 follow-up).

The hook reads the environment, state.json and the transcript; this module is
the part that can be judged without any of them - the deadline parse, the
trust filter on a completed task's wall span, and the three-term predicate
with its caps handed in. Nothing here monkeypatches: the env mapping and the
clock are arguments.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from _cap_headroom import (
    DEADLINE_ENV,
    MAX_CREDIBLE_WALL_SECS,
    headroom_exhausted,
    secs_left_from_env,
    trusted_last_wall,
)

MODULE = Path(__file__).resolve().parent / "_cap_headroom.py"
NOW = 1_700_000_000
USAGE_CAP = 500_000
TURN_TRIPWIRE = 450
MARGIN = 1.25


def _exhausted(
    total: int | None,
    count: int | None,
    last_usage: int,
    last_calls: int,
    *,
    secs_left: float | None = None,
    last_wall: float | None = None,
    usage_cap: int = USAGE_CAP,
    turn_tripwire: int = TURN_TRIPWIRE,
    margin: float = MARGIN,
) -> bool:
    """The predicate under the hook's own caps, unless a case overrides one."""
    return headroom_exhausted(
        total,
        count,
        last_usage,
        last_calls,
        secs_left,
        last_wall,
        usage_cap=usage_cap,
        turn_tripwire=turn_tripwire,
        margin=margin,
    )


def _spanned(task_id: str, wall: int, status: str = "completed") -> dict:
    """A task whose stamps differ by `wall` seconds."""
    return {
        "id": task_id,
        "name": "done",
        "status": status,
        "started_at": NOW,
        "done_at": NOW + wall,
    }


class ModuleIndependenceTests(unittest.TestCase):
    def test_cap_headroom_does_not_import_cli(self) -> None:
        """The hook runs as a subprocess with only `scripts/` on its path,
        so a `cli` import here would traceback at runtime while this suite,
        run from the repo root, stayed green. Importing the module proves
        nothing about that, which is why the source is read as text. This
        pins freedom from `cli` only - it is not a stdlib-only proof."""
        source = MODULE.read_text()
        for statement in ("from cli", "import cli"):
            with self.subTest(statement=statement):
                self.assertNotIn(
                    statement,
                    source,
                    f"{MODULE}: `{statement}` puts the hook's headroom rule "
                    "behind a package the hook subprocess cannot import",
                )


class SecsLeftFromEnvTests(unittest.TestCase):
    def test_the_constant_names_the_variable_the_runner_exports(self) -> None:
        """The runner spawns each session with this name and the hook reads
        it back; the string is the whole contract between them."""
        self.assertEqual(DEADLINE_ENV, "_AUTOPILOT_SESSION_DEADLINE")

    def test_returns_the_seconds_left_before_the_deadline(self) -> None:
        """The value is an epoch second, so what is left is deadline minus
        now - not the raw stamp, and not a duration since the start."""
        env = {DEADLINE_ENV: str(NOW + 1000)}
        self.assertEqual(secs_left_from_env(env, NOW), 1000)

    def test_a_missing_or_unparsable_deadline_drops_the_term(self) -> None:
        """No deadline, an empty value, or anything that is not an epoch
        int returns None - the signal the caller uses to drop the time term
        entirely rather than guess at a number."""
        for env in (
            {},
            {DEADLINE_ENV: ""},
            {DEADLINE_ENV: "abc"},
            {DEADLINE_ENV: "12.5"},
            {"OTHER": str(NOW + 1000)},
        ):
            with self.subTest(env=env):
                self.assertIsNone(secs_left_from_env(env, NOW))

    def test_a_deadline_already_past_returns_a_non_positive_number(self) -> None:
        """A session out of time must still hand off, so a deadline behind
        `now` is a real (non-positive) measurement, never the None that
        drops the term."""
        self.assertEqual(secs_left_from_env({DEADLINE_ENV: str(NOW - 60)}, NOW), -60)
        self.assertEqual(secs_left_from_env({DEADLINE_ENV: str(NOW)}, NOW), 0)


class TrustedLastWallTests(unittest.TestCase):
    def test_returns_the_last_completed_span(self) -> None:
        """The span is the LAST completed entry's own `done_at -
        started_at`; earlier completed tasks and the one still in progress
        say nothing about what the next task will cost. The earlier task is
        the LONGER one here, so "last" and "longest" disagree: a walk that
        keeps the biggest span it saw answers 6540 and reserves twenty
        times the headroom the next task needs. A state with no
        `cap_rotations` key at all is ordinary, not an error."""
        state = {
            "tasks": [
                _spanned("t0", 6540),
                _spanned("t1", 300),
                {"id": "t2", "name": "next", "status": "in_progress"},
            ],
        }
        self.assertEqual(trusted_last_wall(state), 300)

    def test_a_rotation_of_the_measured_task_drops_its_span(self) -> None:
        """`started_at` is stamped once and never replaced, so a rotated
        task's span counts every idle second between sessions. The filter is
        per task and must be asked about the entry the span came from: the
        same two tasks give None when the measured one rotated, and the full
        span when a different one did. `cap_rotations` is per-PRD, so "any
        rotation" would kill the term for the rest of the PRD - and it
        accumulates, so the measured task's entry is the SECOND one here.
        A filter that consults only the first entry misses it. The honest
        6540s task behind the rotated one must not be reported in its
        place either: a walk that steps back past an untrusted last entry
        answers 6540 where the truth is "nothing to measure"."""
        tasks = [_spanned("t0", 6540), _spanned("t1", 300)]
        measured_rotated = {
            "tasks": tasks,
            "cap_rotations": [{"task_id": "t9"}, {"task_id": "t1"}],
        }
        other_rotated = {"tasks": tasks, "cap_rotations": [{"task_id": "t0"}]}
        self.assertIsNone(trusted_last_wall(measured_rotated))
        self.assertEqual(trusted_last_wall(other_rotated), 300)

    def test_a_span_over_the_credible_ceiling_is_dropped(self) -> None:
        """The ceiling is the backstop for what state does not record - a
        watchdog kill, an operator pause. It is a strict ceiling: exactly
        three hours is still work, one second more is not. An honest
        completed task sits behind the over-ceiling one and the answer is
        still None: the walk stops at the last completed entry rather than
        stepping back to report some older task's span as this one's."""
        self.assertEqual(MAX_CREDIBLE_WALL_SECS, 10800)
        at_ceiling = {"tasks": [_spanned("t1", MAX_CREDIBLE_WALL_SECS)]}
        over_ceiling = {
            "tasks": [_spanned("t0", 6540), _spanned("t1", MAX_CREDIBLE_WALL_SECS + 1)],
        }
        self.assertEqual(trusted_last_wall(at_ceiling), MAX_CREDIBLE_WALL_SECS)
        self.assertIsNone(trusted_last_wall(over_ceiling))

    def test_a_malformed_cap_rotations_never_matches(self) -> None:
        """`cap_rotations` is state on disk, so any shape can turn up: a
        string (whose `in` would match the id character-wise), a number, an
        empty entry, a null `task_id`, a bare string entry. None of them may
        raise, and none may be read as a rotation of the measured task."""
        for rotations in ("t1", 7, [{}], [{"task_id": None}], ["t1"], [None]):
            with self.subTest(cap_rotations=rotations):
                state = {"tasks": [_spanned("t1", 6540)], "cap_rotations": rotations}
                self.assertEqual(trusted_last_wall(state), 6540)

    def test_a_null_id_on_the_measured_task_matches_no_rotation(self) -> None:
        """A task without an id cannot be the task a rotation names, so a
        null-to-null comparison must not count as a match and silently drop
        an honest span."""
        task = _spanned("t1", 6540)
        task["id"] = None
        state = {"tasks": [task], "cap_rotations": [{"task_id": None}]}
        self.assertEqual(trusted_last_wall(state), 6540)

    def test_stamps_that_are_not_both_ints_give_no_span(self) -> None:
        """Both stamps must be ints to subtract. A task recorded before the
        stamps existed, a half-stamped one, or one carrying a string or null
        gives no measurable span - and an honest 6540s task behind it is not
        a substitute: the answer is about the LAST completed entry, so an
        unmeasurable one means None, never an older task's span."""
        for stamps in (
            {},
            {"started_at": NOW},
            {"done_at": NOW + 600},
            {"started_at": None, "done_at": NOW + 600},
            {"started_at": "1700000000", "done_at": NOW + 600},
            {"started_at": NOW, "done_at": None},
        ):
            with self.subTest(stamps=stamps):
                task = {"id": "t1", "name": "done", "status": "completed", **stamps}
                state = {"tasks": [_spanned("t0", 6540), task]}
                self.assertEqual(trusted_last_wall(state), 6540)

    def test_a_negative_span_gives_nothing(self) -> None:
        """`done_at` before `started_at` is a stale stamp from an earlier
        session, not a task that took negative time - and a negative span
        would make the time term fire on every check. With no earlier task
        behind it the answer is still None; with an honest task behind it
        the scan steps back past the unusable last entry to that task's span
        (PRD 00243)."""
        self.assertIsNone(trusted_last_wall({"tasks": [_spanned("t1", -5)]}))
        behind = {"tasks": [_spanned("t0", 6540), _spanned("t1", -5)]}
        self.assertEqual(trusted_last_wall(behind), 6540)

    def test_a_zero_second_span_is_measured_not_dropped(self) -> None:
        """A task that started and finished inside the same second is a
        measurement of zero, not a missing measurement. The difference
        matters: 0 keeps the time term alive, so a session already past its
        deadline still hands off, while None switches the term off
        entirely. A guard written as "drop anything <= 0" collapses the
        two and leaves that session working on."""
        self.assertEqual(trusted_last_wall({"tasks": [_spanned("t1", 0)]}), 0)

    def test_no_completed_task_gives_nothing(self) -> None:
        """Only a `completed` entry is finished work to measure. The first
        task of a session has nothing completed behind it, and a task that
        failed or was aborted stopped somewhere unknown - its stamps span an
        attempt, not a task's cost. A filter written as "anything not still
        in progress" would measure those two."""
        for status in ("in_progress", "failed", "aborted"):
            with self.subTest(status=status):
                state = {"tasks": [_spanned("t1", 600, status=status)]}
                self.assertIsNone(trusted_last_wall(state))

    def test_a_state_without_a_usable_task_list_gives_nothing(self) -> None:
        """This answer is computed inside a PostToolUse hook that must never
        traceback, and state.json is a file on disk: the `tasks` key can be
        missing entirely (a PRD whose planning has not run), null, or
        something that is not a list at all. Each must answer None rather
        than raise and take the hook down with it."""
        for state in ({}, {"tasks": None}, {"tasks": "nope"}, {"tasks": []}):
            with self.subTest(state=state):
                self.assertIsNone(trusted_last_wall(state))


class HeadroomExhaustedTests(unittest.TestCase):
    def test_the_usage_term_fires_when_the_context_left_is_under_the_margin(
        self,
    ) -> None:
        """173K left under the 500K cap against a task that cost 164K: the
        margined threshold is 205K, so the next task would not fit. Exactly
        205K left is still room (strict `<`)."""
        self.assertTrue(_exhausted(327_000, None, 164_000, 200))
        self.assertFalse(_exhausted(295_000, None, 164_000, 200))

    def test_the_calls_term_fires_when_the_calls_left_are_under_the_margin(
        self,
    ) -> None:
        """230 calls left under the 450 tripwire against a task that cost
        200 calls: the margined threshold is 250, and exactly 250 left is
        still room."""
        self.assertTrue(_exhausted(None, 220, 150_000, 200))
        self.assertFalse(_exhausted(None, 200, 150_000, 200))

    def test_the_time_term_fires_when_the_seconds_left_are_under_the_margin(
        self,
    ) -> None:
        """1000s left against a task that spanned 900s: the margined
        threshold is 1125. Exactly at it is still room, one second under
        fires."""
        self.assertTrue(
            _exhausted(None, None, 150_000, 200, secs_left=1000, last_wall=900),
        )
        self.assertFalse(
            _exhausted(None, None, 150_000, 200, secs_left=1125, last_wall=900),
        )
        self.assertTrue(
            _exhausted(None, None, 150_000, 200, secs_left=1124, last_wall=900),
        )

    def test_nothing_fires_when_every_term_has_room(self) -> None:
        """300K, 330 calls and 5000s left against a task that cost 50K, 50
        calls and 900s: no term is close, so the session keeps working."""
        self.assertFalse(
            _exhausted(200_000, 120, 50_000, 50, secs_left=5000, last_wall=900),
        )

    def test_a_none_total_drops_the_usage_term(self) -> None:
        """No context total (the transcript gave none) leaves the usage term
        unjudgeable, so it contributes nothing instead of firing."""
        self.assertTrue(_exhausted(490_000, 120, 400_000, 50))
        self.assertFalse(_exhausted(None, 120, 400_000, 50))

    def test_a_none_count_drops_the_calls_term(self) -> None:
        """No call count (stdin carried no session id) leaves the calls term
        unjudgeable, so it contributes nothing instead of firing."""
        self.assertTrue(_exhausted(200_000, 440, 50_000, 200))
        self.assertFalse(_exhausted(200_000, None, 50_000, 200))

    def test_a_none_on_either_side_drops_the_time_term(self) -> None:
        """No deadline, or no trusted span to compare it against, leaves the
        time term unjudgeable - either None alone switches it off."""
        self.assertTrue(
            _exhausted(200_000, 120, 50_000, 50, secs_left=1000, last_wall=900),
        )
        self.assertFalse(
            _exhausted(200_000, 120, 50_000, 50, secs_left=None, last_wall=900),
        )
        self.assertFalse(
            _exhausted(200_000, 120, 50_000, 50, secs_left=1000, last_wall=None),
        )

    def test_the_thresholds_come_from_the_arguments(self) -> None:
        """The caps and the margin are the caller's, not constants baked
        into this module: a wider cap, a higher tripwire, or a margin of 1.0
        each turn a firing case into a quiet one. The margin is pinned on
        all three terms, one at a time - 173K left against a 164K task, 230
        calls against a 200-call task and 1000s against a 900s span all fire
        at 1.25 and all go quiet at 1.0, so a term that ignores the argument
        and multiplies by its own 1.25 is caught here."""
        self.assertFalse(_exhausted(327_000, None, 164_000, 200, usage_cap=1_000_000))
        self.assertFalse(_exhausted(None, 220, 150_000, 200, turn_tripwire=900))
        self.assertFalse(_exhausted(327_000, None, 164_000, 200, margin=1.0))
        self.assertFalse(_exhausted(None, 220, 150_000, 200, margin=1.0))
        self.assertFalse(
            _exhausted(
                None,
                None,
                150_000,
                200,
                secs_left=1000,
                last_wall=900,
                margin=1.0,
            ),
        )


if __name__ == "__main__":
    unittest.main()
