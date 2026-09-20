"""Headroom-handoff tests for autopilot_context_cap_hook.py (PRD 00200).

Split out of test_autopilot_context_cap_hook.py to keep each file under the
800-line limit; the `.handoff-requested` marker-shape cases moved here with
the rule that writes the marker. Shares HookFixture with that module; the
suite runs from scripts/ on sys.path, so the import resolves.

The rule: `.handoff-requested` is written when `USAGE_CAP - total <
last_task_usage` or `TURN_TRIPWIRE - count < last_task_calls`, where the
last-task values are the recorded bounds of the most recently completed task
in this session, or the fixed first-task estimates (150K, 200 calls) when
none. With no task in progress nothing is written. Fixtures that only care
about the marker's shape run at 400K with no completed task: the estimate
leaves 100K of headroom under the 500K cap, so the rule fires.
"""

import json
import unittest
from datetime import datetime, timedelta, timezone

from test_autopilot_context_cap_hook import HookFixture, _load_hook_module


def _parse_iso_utc(value: str) -> datetime:
    """Read a marker's `at` field as an aware UTC datetime.

    The contract pins a UTC ISO-8601 stamp: the raw text must spell a zero
    offset (`+00:00` or `Z`). A naive stamp, or one on any other offset, is a
    contract break and fails the calling test outright — nothing here assumes
    a zone or converts to one."""
    not_utc = f"`at` must spell a zero UTC offset (+00:00 or Z): {value!r}"
    if not value.endswith(("+00:00", "Z")):
        raise AssertionError(not_utc)
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(text)
    if parsed.utcoffset() != timedelta(0):
        raise AssertionError(not_utc)
    return parsed


def _completed(task_id: str, usage: tuple[int, int], calls: tuple[int, int]) -> dict:
    """A completed task carrying its recorded bounds."""
    return {
        "id": task_id,
        "name": "done",
        "status": "completed",
        "usage_at_start": usage[0],
        "usage_at_done": usage[1],
        "calls_at_start": calls[0],
        "calls_at_done": calls[1],
    }


class HeadroomHandoffTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fx = HookFixture()
        self.addCleanup(self.fx.cleanup)

    def _handoff_payload(self) -> dict:
        return json.loads((self.fx.autopilot_dir / ".handoff-requested").read_text())

    def _assert_handoff_payload(
        self,
        payload: dict,
        *,
        task_id: str,
        session: str,
    ) -> None:
        """The marker is a JSON object with exactly four fields: a literal
        `build` phase, the hook's session id, a UTC stamp and the active task
        id. Extra or missing keys are a contract break."""
        self.assertEqual(sorted(payload), ["at", "phase", "session", "task_id"])
        self.assertEqual(payload["phase"], "build")
        self.assertEqual(payload["task_id"], task_id)
        self.assertEqual(payload["session"], session)

    def _run_with(self, *, total: int, count: int, tasks: list[dict]) -> None:
        """One fire at `total` tokens with the session counter seeded so this
        call is number `count`; task `t2` is always the one in progress."""
        self.fx.write_state(
            phase="build",
            tasks=[*tasks, {"id": "t2", "name": "next", "status": "in_progress"}],
        )
        self.fx.write_transcript_lines([self.fx.usage_line(input_tokens=total)])
        self.fx.seed_counter("test-session", count - 1)
        result = self.fx.run_hook()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")
        self.assertFalse((self.fx.autopilot_dir / ".cap-fired").exists())

    def _marker_written(self) -> bool:
        return (self.fx.autopilot_dir / ".handoff-requested").exists()

    # The rule --------------------------------------------------------------

    def test_headroom_above_last_task_writes_no_marker(self) -> None:
        """300K used of 500K and 120 calls of 450 leave more than the last
        task cost (150K, 200 calls): the next task fits, no marker."""
        last = _completed("t1", usage=(100_000, 250_000), calls=(20, 220))
        self._run_with(total=300_000, count=120, tasks=[last])
        self.assertFalse(self._marker_written())

    def test_usage_headroom_below_last_task_writes_marker(self) -> None:
        """380K used leaves 120K, less than the last task's 150K: marker."""
        last = _completed("t1", usage=(100_000, 250_000), calls=(20, 220))
        self._run_with(total=380_000, count=120, tasks=[last])
        self.assertTrue(self._marker_written())
        self.assertEqual(self._handoff_payload()["task_id"], "t2")

    def test_call_headroom_below_last_task_writes_marker(self) -> None:
        """260 calls of 450 leave 190, less than the last task's 200, even
        with plenty of context left: marker."""
        last = _completed("t1", usage=(100_000, 250_000), calls=(20, 220))
        self._run_with(total=300_000, count=260, tasks=[last])
        self.assertTrue(self._marker_written())

    def test_first_task_uses_the_fixed_estimates(self) -> None:
        """No completed task: 150K and 200 calls stand in. 340K leaves 160K
        (fits); 360K leaves 140K (marker); 251 calls leave 199 (marker)."""
        with self.subTest(total=340_000, count=120):
            self._run_with(total=340_000, count=120, tasks=[])
            self.assertFalse(self._marker_written())
        with self.subTest(total=360_000, count=120):
            self._run_with(total=360_000, count=120, tasks=[])
            self.assertTrue(self._marker_written())
        (self.fx.autopilot_dir / ".handoff-requested").unlink()
        with self.subTest(total=300_000, count=251):
            self._run_with(total=300_000, count=251, tasks=[])
            self.assertTrue(self._marker_written())

    def test_negative_record_falls_back_to_the_estimates(self) -> None:
        """The last completed task's start (stamped by an earlier session)
        exceeds its done: the fixed estimates apply, never a negative cost.
        340K fits under the 150K estimate and 360K does not; a -50K cost
        would have let both pass."""
        negative = _completed("t1", usage=(300_000, 250_000), calls=(20, 220))
        self._run_with(total=340_000, count=120, tasks=[negative])
        self.assertFalse(self._marker_written())
        self._run_with(total=360_000, count=120, tasks=[negative])
        self.assertTrue(self._marker_written())

    def test_last_task_cost_reads_the_last_completed_record_or_the_estimates(
        self,
    ) -> None:
        """`_last_task_cost` is the rule's input: the LAST completed task in
        list order, its four int bounds as two differences; a task with a
        missing done pair, a non-int bound, or a negative difference yields
        the estimates rather than an earlier task's record or a negative."""
        module = _load_hook_module()
        estimates = (module.FIRST_TASK_USAGE_ESTIMATE, module.FIRST_TASK_CALLS_ESTIMATE)
        good = _completed("a", usage=(100_000, 220_000), calls=(20, 170))
        later = _completed("b", usage=(220_000, 300_000), calls=(170, 260))
        no_done = {
            "id": "c",
            "status": "completed",
            "usage_at_start": 1,
            "calls_at_start": 1,
        }
        bad_int = _completed("d", usage=(1, 2), calls=(1, 2))
        bad_int["calls_at_done"] = "2"
        pending = {"id": "e", "status": "pending"}
        self.assertEqual(module._last_task_cost({"tasks": []}), estimates)
        self.assertEqual(module._last_task_cost({"tasks": [good]}), (120_000, 150))
        self.assertEqual(module._last_task_cost({"tasks": [good, later]}), (80_000, 90))
        self.assertEqual(
            module._last_task_cost({"tasks": [good, later, pending]}), (80_000, 90)
        )
        self.assertEqual(module._last_task_cost({"tasks": [good, no_done]}), estimates)
        self.assertEqual(module._last_task_cost({"tasks": [good, bad_int]}), estimates)
        self.assertEqual(module._last_task_cost({"tasks": "nope"}), estimates)

    def test_two_tasks_fit_and_the_boundary_hands_off_once_headroom_is_gone(
        self,
    ) -> None:
        """Happy path: two tasks of 120K / 150 calls each. After task 1 the
        session (250K, 170 calls) still fits a task; after task 2 the totals
        (390K, or 301 calls) do not, and the marker appears."""
        task1 = _completed("t1", usage=(100_000, 220_000), calls=(20, 170))
        task2 = _completed("t1b", usage=(220_000, 340_000), calls=(170, 320))
        self._run_with(total=250_000, count=170, tasks=[task1])
        self.assertFalse(self._marker_written())
        self._run_with(total=390_000, count=290, tasks=[task1, task2])
        self.assertTrue(self._marker_written())
        (self.fx.autopilot_dir / ".handoff-requested").unlink()
        self._run_with(total=340_000, count=301, tasks=[task1, task2])
        self.assertTrue(self._marker_written())

    def test_headroom_with_no_task_in_progress_writes_no_handoff_marker(self) -> None:
        """Headroom exhausted with no in-progress task and no task crossing
        its boundary on this fire (the completed task carries no record):
        there is no task boundary to hand off at, so the hook writes nothing.
        A marker written here (as `unknown`) made the next session hand off
        after one task."""
        self.fx.write_state(
            phase="build",
            tasks=[{"id": "1", "name": "t", "status": "completed"}],
        )
        self.fx.write_transcript_lines([self.fx.usage_line(input_tokens=400_000)])
        result = self.fx.run_hook()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")
        self.assertFalse(self._marker_written())
        self.assertFalse((self.fx.autopilot_dir / ".cap-fired").exists())

    def test_completion_fire_applies_the_completed_tasks_own_cost(self) -> None:
        """The first fire after task-done (no task in progress) stamps the
        done pair and judges the boundary by that task's own measured cost,
        writing the marker under its id for step 6.5 to read next. A 220K
        task ending at 320K leaves 180K, less than it cost: marker. The next
        fire, with the record already stamped and still no task in progress,
        is a wind-down fire and writes nothing (review 1 of PRD 00200)."""
        self.fx.write_state(
            phase="build",
            tasks=[
                {
                    "id": "t1",
                    "name": "big",
                    "status": "completed",
                    "usage_at_start": 100_000,
                    "calls_at_start": 20,
                },
                {"id": "t2", "name": "next", "status": "pending"},
            ],
        )
        self.fx.write_transcript_lines([self.fx.usage_line(input_tokens=320_000)])
        self.fx.seed_counter("test-session", 219)
        result = self.fx.run_hook()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")
        self.assertTrue(self._marker_written())
        self._assert_handoff_payload(
            self._handoff_payload(),
            task_id="t1",
            session="test-session",
        )
        state = json.loads((self.fx.autopilot_dir / "state.json").read_text())
        self.assertEqual(state["tasks"][0]["usage_at_done"], 320_000)
        self.assertEqual(state["tasks"][0]["calls_at_done"], 220)

        (self.fx.autopilot_dir / ".handoff-requested").unlink()
        self.fx.write_transcript_lines([self.fx.usage_line(input_tokens=330_000)])
        result = self.fx.run_hook()
        self.assertEqual(result.returncode, 0)
        self.assertFalse(self._marker_written())

    def test_stale_start_from_an_earlier_session_is_restamped(self) -> None:
        """A start pair above this session's own total and count was stamped
        by an earlier session (a rotated or died task keeps its stamp; within
        a session both only grow), so it is replaced rather than kept as the
        base of an understated cost."""
        self.fx.write_state(
            phase="build",
            tasks=[
                {
                    "id": "t1",
                    "name": "y",
                    "status": "in_progress",
                    "usage_at_start": 300_000,
                    "calls_at_start": 400,
                },
            ],
        )
        self.fx.write_transcript_lines([self.fx.usage_line(input_tokens=120_000)])
        self.fx.seed_counter("test-session", 41)
        result = self.fx.run_hook()
        self.assertEqual(result.returncode, 0)
        task = json.loads((self.fx.autopilot_dir / "state.json").read_text())["tasks"][
            0
        ]
        self.assertEqual(task["usage_at_start"], 120_000)
        self.assertEqual(task["calls_at_start"], 42)

    def test_missing_usage_line_still_checks_the_call_headroom(self) -> None:
        """A transcript with no usage line yet leaves the calls half of the
        rule in force: 261 calls of 450 leave 189, under the 200-call
        estimate, so the marker is written."""
        self.fx.write_state(
            phase="build",
            tasks=[{"id": "t1", "name": "y", "status": "in_progress"}],
        )
        self.fx.write_transcript_lines([{"type": "user", "message": {"content": "hi"}}])
        self.fx.seed_counter("test-session", 260)
        result = self.fx.run_hook()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")
        self.assertTrue(self._marker_written())
        self.assertFalse((self.fx.autopilot_dir / ".cap-fired").exists())

    def test_non_int_bound_on_the_last_completed_task_is_named_once(self) -> None:
        """A completed record with a non-int START bound is unusable for the
        rule (the estimates apply) and is named on exactly one stderr line,
        the same diagnostic the record's own writer gives."""
        self.fx.write_state(
            phase="build",
            tasks=[
                {
                    "id": "t1",
                    "name": "y",
                    "status": "completed",
                    "usage_at_start": "lots",
                    "calls_at_start": 20,
                    "usage_at_done": 250_000,
                    "calls_at_done": 220,
                },
                {"id": "t2", "name": "next", "status": "in_progress"},
            ],
        )
        self.fx.write_transcript_lines([self.fx.usage_line(input_tokens=340_000)])
        self.fx.seed_counter("test-session", 120)
        result = self.fx.run_hook()
        self.assertEqual(result.returncode, 0)
        self.assertFalse(self._marker_written())
        lines = [line for line in result.stderr.splitlines() if "not an int" in line]
        self.assertEqual(len(lines), 1, result.stderr)
        self.assertIn("usage_at_start", lines[0])

    def test_headroom_exhausted_is_a_pure_predicate(self) -> None:
        module = _load_hook_module()
        self.assertFalse(module._headroom_exhausted(300_000, 120, 150_000, 200))
        self.assertTrue(module._headroom_exhausted(380_000, 120, 150_000, 200))
        self.assertTrue(module._headroom_exhausted(300_000, 260, 150_000, 200))
        # No count (stdin carried no session id): only the usage half applies.
        self.assertFalse(module._headroom_exhausted(300_000, None, 150_000, 200))
        self.assertTrue(module._headroom_exhausted(380_000, None, 150_000, 200))

    # The marker ------------------------------------------------------------

    def test_exhausted_headroom_writes_handoff_marker(self) -> None:
        """Usage at 300K and 261 calls with no completed task: 189 calls left
        of 450, under the 200-call first-task estimate (the old 320K soft cap
        would have stayed silent at 300K), so the rule writes
        `.handoff-requested` as a JSON payload naming the phase, the hook's
        session id, a UTC ISO-8601 stamp and the in-progress task id. The path
        is non-destructive — no `.cap-fired`, no rotation, no state mutation.

        The session id on stdin is deliberately unlike anything else in this
        fixture (not the task id, not a default literal), so `session` can only
        be satisfied by reading the id off the incoming payload."""
        self.fx.write_state(
            phase="build",
            tasks=[{"id": "task-x", "name": "y", "status": "in_progress"}],
        )
        self.fx.write_transcript_lines([self.fx.usage_line(input_tokens=300_000)])
        self.fx.seed_counter("sess-9f3a2c", 260)
        before = datetime.now(timezone.utc) - timedelta(seconds=1)
        result = self.fx.run_hook(
            stdin_payload={
                "session_id": "sess-9f3a2c",
                "transcript_path": str(self.fx.transcript),
            },
        )
        after = datetime.now(timezone.utc) + timedelta(seconds=1)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")

        self.assertTrue(self._marker_written())
        payload = self._handoff_payload()
        self._assert_handoff_payload(payload, task_id="task-x", session="sess-9f3a2c")
        # The raw text spells a zero UTC offset; a naive stamp is not "UTC by
        # convention", it is a contract break.
        self.assertTrue(
            payload["at"].endswith(("+00:00", "Z")),
            f"`at` must carry +00:00 or Z, got {payload['at']!r}",
        )
        # `at` must be a real stamp of this run, not a fixed or empty string.
        stamped = _parse_iso_utc(payload["at"])
        self.assertGreaterEqual(stamped, before)
        self.assertLessEqual(stamped, after)

        # Non-destructive: hard-cap artifacts must NOT appear, and the record
        # stamp is the only state change.
        self.assertFalse((self.fx.autopilot_dir / ".cap-fired").exists())
        state = json.loads((self.fx.autopilot_dir / "state.json").read_text())
        self.assertEqual(state["cap_rotations"], [])
        self.assertNotIn("stall_reason", state)
        self.assertEqual(state["tasks"][0]["status"], "in_progress")

    def test_headroom_left_writes_no_marker(self) -> None:
        """Usage at 80K leaves far more than the estimate: neither marker."""
        self.fx.write_state(
            phase="build",
            tasks=[{"id": "task-x", "name": "y", "status": "in_progress"}],
        )
        self.fx.write_transcript_lines([self.fx.usage_line(input_tokens=80_000)])
        result = self.fx.run_hook()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")
        self.assertFalse(self._marker_written())
        self.assertFalse((self.fx.autopilot_dir / ".cap-fired").exists())

    def test_hard_cap_overrun_writes_no_handoff_marker(self) -> None:
        """A hard-cap overrun takes the rotation path and must NOT also write
        `.handoff-requested` — the two paths are mutually exclusive."""
        self.fx.write_state(
            phase="build",
            tasks=[{"id": "task-x", "name": "y", "status": "in_progress"}],
        )
        self.fx.write_transcript_lines([self.fx.usage_line(input_tokens=600_000)])
        result = self.fx.run_hook()
        self.assertEqual(result.returncode, 0)
        self.assertTrue((self.fx.autopilot_dir / ".cap-fired").exists())
        self.assertFalse(self._marker_written())

    def test_handoff_marker_legacy_plain_same_task_not_rewritten(self) -> None:
        """A pre-JSON marker holding the bare in-progress task id is still a
        same-task no-op (one-shot per task): the legacy plain string is left
        exactly as found, not upgraded to JSON mid-task."""
        self.fx.write_state(
            phase="build",
            tasks=[{"id": "task-x", "name": "y", "status": "in_progress"}],
        )
        self.fx.write_transcript_lines([self.fx.usage_line(input_tokens=400_000)])
        handoff = self.fx.autopilot_dir / ".handoff-requested"
        handoff.write_text("task-x")
        before = handoff.read_bytes()
        result = self.fx.run_hook()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")
        self.assertEqual(handoff.read_bytes(), before)

    def test_marker_task_id_reads_a_numeric_legacy_marker_as_that_task_id(self) -> None:
        """A bare number is a legacy plain marker naming that task, even though
        it also parses as JSON. Reading it as "no task" would rewrite the marker
        on every fire for any task with a purely numeric id. Several ids, so a
        reader that special-cases one literal cannot pass; a bracketed number
        is JSON that names no task and stays empty."""
        module = _load_hook_module()
        for task_id in ("0", "7", "42", "123456"):
            with self.subTest(marker=task_id):
                self.assertEqual(module._marker_task_id(task_id), task_id)
        self.assertEqual(module._marker_task_id("[42]"), "")

    def test_handoff_marker_numeric_legacy_same_task_not_rewritten(self) -> None:
        """The same-task no-op holds for a numeric id: a legacy plain `19` for
        in-progress task `19` is left byte-for-byte, exactly like `task-x`. A
        number the direct test above does not use, so no single literal
        satisfies both."""
        self.fx.write_state(
            phase="build",
            tasks=[{"id": "19", "name": "y", "status": "in_progress"}],
        )
        self.fx.write_transcript_lines([self.fx.usage_line(input_tokens=400_000)])
        handoff = self.fx.autopilot_dir / ".handoff-requested"
        handoff.write_text("19")
        before = handoff.read_bytes()
        result = self.fx.run_hook()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")
        self.assertEqual(handoff.read_bytes(), before)

    def test_handoff_marker_non_object_json_beside_a_numeric_task_is_replaced(
        self,
    ) -> None:
        """Reading bare numbers as legacy ids must not widen to every non-object
        JSON body: `[1]` and `null` name no task, so with task `1` in progress
        each is replaced by the JSON payload rather than kept as a same-task
        no-op (a bracket-stripping or str()-of-JSON reading would keep it)."""
        self.fx.write_state(
            phase="build",
            tasks=[{"id": "1", "name": "y", "status": "in_progress"}],
        )
        self.fx.write_transcript_lines([self.fx.usage_line(input_tokens=400_000)])
        handoff = self.fx.autopilot_dir / ".handoff-requested"
        for label, content in (("json-list", "[1]"), ("json-null", "null")):
            with self.subTest(existing=label):
                handoff.write_text(content)
                result = self.fx.run_hook()
                self.assertEqual(result.returncode, 0)
                self._assert_handoff_payload(
                    self._handoff_payload(),
                    task_id="1",
                    session="test-session",
                )

    def test_handoff_marker_legacy_plain_stale_task_overwritten(self) -> None:
        """A pre-JSON marker naming an earlier task is replaced by a full JSON
        payload for the current task, so the handoff request stays current
        after the session advances."""
        self.fx.write_state(
            phase="build",
            tasks=[{"id": "task-new", "name": "y", "status": "in_progress"}],
        )
        self.fx.write_transcript_lines([self.fx.usage_line(input_tokens=400_000)])
        (self.fx.autopilot_dir / ".handoff-requested").write_text("task-old")
        result = self.fx.run_hook()
        self.assertEqual(result.returncode, 0)
        self._assert_handoff_payload(
            self._handoff_payload(),
            task_id="task-new",
            session="test-session",
        )

    def test_handoff_marker_json_same_task_not_rewritten(self) -> None:
        """A JSON marker whose task_id matches the in-progress task is a
        no-op: the earlier session id and stamp survive byte-for-byte, so a
        redundant PostToolUse fire cannot move the request's own timestamp."""
        self.fx.write_state(
            phase="build",
            tasks=[{"id": "task-x", "name": "y", "status": "in_progress"}],
        )
        self.fx.write_transcript_lines([self.fx.usage_line(input_tokens=400_000)])
        handoff = self.fx.autopilot_dir / ".handoff-requested"
        handoff.write_text(
            json.dumps(
                {
                    "phase": "build",
                    "session": "earlier-session",
                    "at": "2020-01-02T03:04:05+00:00",
                    "task_id": "task-x",
                },
            ),
        )
        before = handoff.read_bytes()
        result = self.fx.run_hook()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")
        self.assertEqual(handoff.read_bytes(), before)

    def test_handoff_marker_json_stale_task_overwritten(self) -> None:
        """A JSON marker naming an earlier task is overwritten with a fresh
        payload — new task id, this session's id, and a stamp later than the
        one it replaced."""
        self.fx.write_state(
            phase="build",
            tasks=[{"id": "task-new", "name": "y", "status": "in_progress"}],
        )
        self.fx.write_transcript_lines([self.fx.usage_line(input_tokens=400_000)])
        stale_at = "2020-01-02T03:04:05+00:00"
        (self.fx.autopilot_dir / ".handoff-requested").write_text(
            json.dumps(
                {
                    "phase": "build",
                    "session": "earlier-session",
                    "at": stale_at,
                    "task_id": "task-old",
                },
            ),
        )
        result = self.fx.run_hook()
        self.assertEqual(result.returncode, 0)
        payload = self._handoff_payload()
        self._assert_handoff_payload(
            payload,
            task_id="task-new",
            session="test-session",
        )
        self.assertGreater(_parse_iso_utc(payload["at"]), _parse_iso_utc(stale_at))

    def test_handoff_marker_task_whose_id_prefixes_the_marked_one_is_overwritten(
        self,
    ) -> None:
        """Task ids match whole, never by appearing somewhere in the marker:
        `task-1` is a different task from the marked `task-10`, so the marker is
        rewritten for it. Both stored shapes are checked, because a legacy plain
        string and a JSON payload both literally contain `task-1`. Treating that
        as a same-task no-op would silently drop the handoff request for every
        task whose id is a prefix of the one already named."""
        self.fx.write_state(
            phase="build",
            tasks=[{"id": "task-1", "name": "y", "status": "in_progress"}],
        )
        self.fx.write_transcript_lines([self.fx.usage_line(input_tokens=400_000)])
        handoff = self.fx.autopilot_dir / ".handoff-requested"
        for label, content in (
            ("legacy-plain", "task-10"),
            (
                "json",
                json.dumps(
                    {
                        "phase": "build",
                        "session": "earlier-session",
                        "at": "2020-01-02T03:04:05+00:00",
                        "task_id": "task-10",
                    },
                ),
            ),
        ):
            with self.subTest(existing=label):
                handoff.write_text(content)
                result = self.fx.run_hook()
                self.assertEqual(result.returncode, 0)
                self._assert_handoff_payload(
                    self._handoff_payload(),
                    task_id="task-1",
                    session="test-session",
                )

    def test_handoff_marker_empty_or_malformed_is_replaced_with_json(self) -> None:
        """Junk left at the marker path (empty, whitespace, unparseable, or
        JSON that is not an object) names no task, so it must neither block
        the request nor crash the hook — the next write lands valid JSON."""
        self.fx.write_state(
            phase="build",
            tasks=[{"id": "task-x", "name": "y", "status": "in_progress"}],
        )
        self.fx.write_transcript_lines([self.fx.usage_line(input_tokens=400_000)])
        handoff = self.fx.autopilot_dir / ".handoff-requested"
        for label, content in (
            ("empty", ""),
            ("whitespace", "   \n"),
            ("not-json", "{not json"),
            ("json-list", "[1, 2]"),
            ("json-null", "null"),
        ):
            with self.subTest(existing=label):
                handoff.write_text(content)
                result = self.fx.run_hook()
                self.assertEqual(result.returncode, 0)
                self._assert_handoff_payload(
                    self._handoff_payload(),
                    task_id="task-x",
                    session="test-session",
                )

    def test_handoff_marker_session_is_empty_string_when_stdin_omits_session_id(
        self,
    ) -> None:
        """`session` falls back to the empty string only when the payload
        carries no session id — never to a placeholder or the task id."""
        self.fx.write_state(
            phase="build",
            tasks=[{"id": "task-x", "name": "y", "status": "in_progress"}],
        )
        self.fx.write_transcript_lines([self.fx.usage_line(input_tokens=400_000)])
        result = self.fx.run_hook(
            stdin_payload={"transcript_path": str(self.fx.transcript)},
        )
        self.assertEqual(result.returncode, 0)
        self._assert_handoff_payload(
            self._handoff_payload(),
            task_id="task-x",
            session="",
        )


if __name__ == "__main__":
    unittest.main()
