"""Hard-breach tests for autopilot_context_cap_hook.py: the turn tripwire,
the rotation/stall instruction builders (C1), the marker-first rollback
invariant (C2) and the fsync-before-rename durability of every temp-then-
rename write.

Split out of test_autopilot_context_cap_hook.py to keep each file under the
800-line limit. Shares HookFixture with that module; the suite runs from
scripts/ on sys.path, so the import resolves.
"""

import contextlib
import inspect
import io
import json
import os
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from test_autopilot_context_cap_hook import HookFixture, _load_hook_module


class TurnTripwireTests(unittest.TestCase):
    """PRD 00073 turn tripwire, at 450 tool calls since PRD 00200 (orientation
    plus two measured opus tasks minus the margin the headroom rule provides;
    at 300 the second task of every opus session died mid-flight). The
    token-cap pin was reverted 2026-07-20 when the operator restored the [1m]
    default (cap back to 500K); the tripwire is independent of the cap and
    stays."""

    def setUp(self) -> None:
        self.fx = HookFixture()
        self.addCleanup(self.fx.cleanup)
        self.module = _load_hook_module()

    def test_cap_constants_and_tripwire(self) -> None:
        # Regression lock: keep the cap coupled to the [1m] default (never
        # re-pin to 150K without also shrinking the default window). The soft
        # cap is gone: the headroom rule and its first-task estimates replace it.
        self.assertEqual(self.module.USAGE_CAP, 500_000)
        self.assertEqual(self.module.TURN_TRIPWIRE, 450)
        self.assertEqual(self.module.FIRST_TASK_USAGE_ESTIMATE, 150_000)
        self.assertEqual(self.module.FIRST_TASK_CALLS_ESTIMATE, 200)
        self.assertFalse(hasattr(self.module, "SOFT_CAP"))
        self.assertFalse(hasattr(self.module, "_soft_limit"))
        self.assertLess(self.module.FIRST_TASK_USAGE_ESTIMATE, self.module.USAGE_CAP)

    def test_tripwire_fires_at_450_and_not_at_the_old_300(self) -> None:
        """The 300th call (the old tripwire) rotates nothing; a session at 449
        counted calls that takes its 450th (with usage well under the cap) is
        force-handed-off via the rotation path."""
        self.fx.write_state(
            phase="build",
            tasks=[{"id": "task-x", "name": "y", "status": "in_progress"}],
        )
        self.fx.write_transcript_lines([self.fx.usage_line(input_tokens=40_000)])
        self.fx.seed_counter("test-session", 299)
        result = self.fx.run_hook()
        self.assertEqual(result.returncode, 0)
        self.assertFalse((self.fx.autopilot_dir / ".cap-fired").exists())
        state = json.loads((self.fx.autopilot_dir / "state.json").read_text())
        self.assertEqual(state["cap_rotations"], [])

        self.fx.seed_counter("test-session", 449)
        result = self.fx.run_hook()
        self.assertEqual(result.returncode, 0)
        self.assertTrue((self.fx.autopilot_dir / ".cap-fired").exists())
        state = json.loads((self.fx.autopilot_dir / "state.json").read_text())
        self.assertEqual(state["cap_rotations"][-1]["task_id"], "task-x")

    def test_blocked_fire_still_refreshes_the_last_record(self) -> None:
        """After a rotation the `.cap-fired` marker survives into the
        relaunched session until `/work` step 2 clears it, so its fires are
        de-duplicated. They still count the call and rewrite `last` with THIS
        session's values (without arming the tripwire), or the gate-edge
        headroom check would read the dead session's exhausted `last` and
        hand off forever (review 1 of PRD 00200)."""
        self.fx.write_state(
            phase="build",
            cap_rotations=[{"task_id": "unknown", "cycle": 1}],
            tasks=[{"id": "1", "name": "t", "status": "pending"}],
        )
        (self.fx.autopilot_dir / ".cap-fired").write_text("unknown")
        (self.fx.autopilot_dir / ".turn-counts.json").write_text(
            json.dumps(
                {
                    "counts": {"dead-session": 450, "test-session": 5},
                    "fired": ["dead-session"],
                    "last": {"session": "dead-session", "count": 450, "usage": 510_000},
                },
            ),
        )
        self.fx.write_transcript_lines([self.fx.usage_line(input_tokens=100_000)])
        result = self.fx.run_hook()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")
        data = json.loads((self.fx.autopilot_dir / ".turn-counts.json").read_text())
        self.assertEqual(
            data["last"],
            {"session": "test-session", "count": 6, "usage": 100_000},
        )
        self.assertEqual(data["counts"]["test-session"], 6)
        self.assertEqual(data["fired"], ["dead-session"])
        state = json.loads((self.fx.autopilot_dir / "state.json").read_text())
        self.assertEqual(len(state["cap_rotations"]), 1)
        # Blocked fires never arm the tripwire, even past its threshold.
        self.fx.seed_counter("test-session", 460)
        (self.fx.autopilot_dir / ".cap-fired").write_text("unknown")
        result = self.fx.run_hook()
        self.assertEqual(result.returncode, 0)
        data = json.loads((self.fx.autopilot_dir / ".turn-counts.json").read_text())
        self.assertEqual(data["fired"], [])
        self.assertEqual(data["last"]["count"], 461)

    def test_tripwire_does_not_fire_at_449(self) -> None:
        """At the 449th call (seeded 448), no forced hand-off; usage is under
        cap and the headroom rule (200-call estimate against 450) does not
        rotate, it only writes the boundary marker."""
        self.fx.write_state(
            phase="build",
            tasks=[{"id": "task-x", "name": "y", "status": "in_progress"}],
        )
        self.fx.write_transcript_lines([self.fx.usage_line(input_tokens=40_000)])
        self.fx.seed_counter("test-session", 448)
        result = self.fx.run_hook()
        self.assertEqual(result.returncode, 0)
        self.assertFalse((self.fx.autopilot_dir / ".cap-fired").exists())
        state = json.loads((self.fx.autopilot_dir / "state.json").read_text())
        self.assertEqual(state["cap_rotations"], [])

    def test_turn_counter_records_the_last_fire_for_the_gate_edges(self) -> None:
        """Every fire rewrites `last` with this session's count and the usage
        total it saw, so the build gate can apply the headroom rule at the
        design->plan and plan->work edges where no task is in progress."""
        self.fx.write_state(phase="build")
        self.fx.write_transcript_lines([self.fx.usage_line(input_tokens=210_000)])
        self.fx.seed_counter("test-session", 41)
        result = self.fx.run_hook()
        self.assertEqual(result.returncode, 0)
        data = json.loads((self.fx.autopilot_dir / ".turn-counts.json").read_text())
        self.assertEqual(
            data["last"],
            {"session": "test-session", "count": 42, "usage": 210_000},
        )
        # No usage line yet: the count is still recorded, usage is null.
        self.fx.transcript.write_text("")
        result = self.fx.run_hook()
        self.assertEqual(result.returncode, 0)
        data = json.loads((self.fx.autopilot_dir / ".turn-counts.json").read_text())
        self.assertEqual(
            data["last"], {"session": "test-session", "count": 43, "usage": None}
        )

    def test_tripwire_counter_corruption_resets_without_crashing(self) -> None:
        """A corrupt counter file resets to 0 and the hook still exits 0."""
        self.fx.write_state(
            phase="build",
            tasks=[{"id": "task-x", "name": "y", "status": "in_progress"}],
        )
        self.fx.write_transcript_lines([self.fx.usage_line(input_tokens=40_000)])
        (self.fx.autopilot_dir / ".turn-counts.json").write_text("{not json")
        result = self.fx.run_hook()
        self.assertEqual(result.returncode, 0)
        self.assertFalse((self.fx.autopilot_dir / ".cap-fired").exists())

    def test_tripwire_valid_json_bad_count_value_does_not_crash(self) -> None:
        """A valid-JSON counter file with a non-int count (null / string) must
        reset that entry and exit 0, never raise (never-crash contract)."""
        self.fx.write_state(
            phase="build",
            tasks=[{"id": "task-x", "name": "y", "status": "in_progress"}],
        )
        self.fx.write_transcript_lines([self.fx.usage_line(input_tokens=40_000)])
        (self.fx.autopilot_dir / ".turn-counts.json").write_text(
            json.dumps({"counts": {"test-session": None}, "fired": []}),
        )
        result = self.fx.run_hook()
        self.assertEqual(result.returncode, 0)
        self.assertFalse((self.fx.autopilot_dir / ".cap-fired").exists())
        # a wrong-shape file (counts not a dict) also resets cleanly
        (self.fx.autopilot_dir / ".turn-counts.json").write_text(
            json.dumps({"counts": "nope"}),
        )
        result2 = self.fx.run_hook()
        self.assertEqual(result2.returncode, 0)

    def test_tripwire_exempt_for_interactive_session(self) -> None:
        """No $_AUTOPILOT_LOOP: even a seeded 449 counter must not fire."""
        self.fx.write_state(
            phase="build",
            tasks=[{"id": "task-x", "name": "y", "status": "in_progress"}],
        )
        self.fx.write_transcript_lines([self.fx.usage_line(input_tokens=40_000)])
        self.fx.seed_counter("test-session", 449)
        result = self.fx.run_hook(in_loop=False)
        self.assertEqual(result.returncode, 0)
        self.assertFalse((self.fx.autopilot_dir / ".cap-fired").exists())


class InstructionBuilderContractTests(unittest.TestCase):
    """C1: instruction builders must not take signal_path and must not emit
    any signal-write directive. The Stop hook now owns the signal write."""

    def setUp(self) -> None:
        self.module = _load_hook_module()

    # AC1: _rotation_instructions signature -----------------------------------

    def test_rotation_instructions_takes_only_limit_parameter(self) -> None:
        """_rotation_instructions must accept exactly one parameter named
        `limit` — no signal_path."""
        sig = inspect.signature(self.module._rotation_instructions)
        self.assertEqual(list(sig.parameters), ["limit"])

    # AC2: _oversized_stall_instructions signature ----------------------------

    def test_oversized_stall_instructions_takes_only_task_id_parameter(self) -> None:
        """_oversized_stall_instructions must accept exactly one parameter
        named `task_id` — no signal_path."""
        sig = inspect.signature(self.module._oversized_stall_instructions)
        self.assertEqual(list(sig.parameters), ["task_id"])

    # AC3: rotation text has no signal-write directive ------------------------

    def test_rotation_text_has_no_signal_write_directive(self) -> None:
        """_rotation_instructions must not emit any signal-write directive."""
        text = self.module._rotation_instructions(500_000)
        self.assertNotIn("write 'next'", text)
        self.assertNotIn("$_AUTOPILOT_LOOP", text)
        self.assertNotIn("signal", text.lower())

    # AC4: stall text has no signal-write directive ---------------------------

    def test_stall_text_has_no_signal_write_directive(self) -> None:
        """_oversized_stall_instructions must not emit any signal-write
        directive."""
        text = self.module._oversized_stall_instructions("task-abc")
        self.assertNotIn("write 'next'", text)
        self.assertNotIn("$_AUTOPILOT_LOOP", text)
        self.assertNotIn("signal", text.lower())

    # AC5: rotation text still describes a rotation and a stop ----------------

    def test_rotation_text_still_describes_rotation_and_stop(self) -> None:
        """_rotation_instructions must still say ROTATION, STOP, and
        reference build as the next_phase — guards against the builder
        being gutted entirely."""
        text = self.module._rotation_instructions(500_000)
        self.assertIn("rotation", text.lower())
        self.assertIn("stop", text.lower())
        self.assertIn("build", text.lower())

    # AC6: stall text still names the oversized stall and stalled state -------

    def test_stall_text_still_describes_oversized_stall(self) -> None:
        """_oversized_stall_instructions must still reference 'oversized' and
        the stall_reason 'stalled' state marker."""
        text = self.module._oversized_stall_instructions("task-abc")
        self.assertIn("oversized", text.lower())
        self.assertIn("stalled", text.lower())


class MarkerStateAtomicityTests(unittest.TestCase):
    """C2: marker-first + rollback. The `.cap-fired` marker is present iff the
    rotation/stall is recorded, so a marker-write OSError can never leave a
    state record that the next PostToolUse misreads as a second consecutive
    rotation (a false-livelock oversized-task stall)."""

    def setUp(self) -> None:
        self.module = _load_hook_module()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ap = Path(self.tmp.name)

    def _write_state(self) -> None:
        state = {
            "phase": "build",
            "cycle": 1,
            "cap_rotations": [],
            "tasks": [{"id": "task-x", "name": "y", "status": "in_progress"}],
        }
        (self.ap / "state.json").write_text(json.dumps(state))

    def test_marker_write_failure_during_rotation_leaves_cap_rotations_unchanged(
        self,
    ) -> None:
        """If the marker write fails, _handle_rotation must not record a rotation
        in state.cap_rotations — a rotation-without-marker re-fires as a false
        livelock. (A directory at the marker path makes write_text raise
        IsADirectoryError, an OSError.)"""
        self._write_state()
        marker = self.ap / ".cap-fired"
        marker.mkdir()
        self.module._handle_rotation(self.ap, marker, "task-x", 500_000)
        after = json.loads((self.ap / "state.json").read_text())
        self.assertEqual(
            after.get("cap_rotations"),
            [],
            "a marker-write failure must leave cap_rotations unchanged",
        )

    def test_marker_write_failure_during_livelock_leaves_stall_unset(self) -> None:
        """Same invariant on the livelock path: a marker-write failure must not
        record an oversized-task stall."""
        self._write_state()
        marker = self.ap / ".cap-fired"
        marker.mkdir()
        self.module._handle_livelock(self.ap, marker, "task-x", 600_000)
        after = json.loads((self.ap / "state.json").read_text())
        self.assertNotIn(
            "stall_reason",
            after,
            "a marker-write failure must not record an oversized-task stall",
        )

    def test_state_append_failure_during_rotation_rolls_back_marker(self) -> None:
        """C2 rollback path (the other half of the invariant): when the marker
        write SUCCEEDS but the cap_rotations state append FAILS, _handle_rotation
        must unlink the marker and emit no envelope. Otherwise a
        marker-without-rotation would block the cap forever (the next fire sees
        the marker and no-ops). The existing marker-write-failure test covers
        only the marker-FIRST failure; this covers the unlink rollback."""
        self._write_state()
        marker = self.ap / ".cap-fired"
        # Marker write succeeds (writable temp dir); force the state append to
        # fail so the rollback branch runs.
        self.module._append_rotation_to_state = lambda *a, **k: False
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            self.module._handle_rotation(self.ap, marker, "task-x", 500_000)
        self.assertFalse(
            marker.exists(),
            "a state-append failure must roll back (unlink) the marker",
        )
        after = json.loads((self.ap / "state.json").read_text())
        self.assertEqual(
            after.get("cap_rotations"),
            [],
            "no rotation may be recorded when the state append fails",
        )
        self.assertEqual(
            captured.getvalue().strip(),
            "",
            "no rotation envelope may be emitted when the state append fails",
        )

    def test_state_write_failure_during_livelock_rolls_back_marker(self) -> None:
        """C2 rollback path on the livelock branch: marker write succeeds, the
        oversized-stall state write fails -> _handle_livelock unlinks the marker
        and emits no envelope, leaving no stall_reason for the next fire to act
        on spuriously."""
        self._write_state()
        marker = self.ap / ".cap-fired"
        self.module._set_oversized_stall = lambda *a, **k: False
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            self.module._handle_livelock(self.ap, marker, "task-x", 600_000)
        self.assertFalse(
            marker.exists(),
            "a state-write failure must roll back (unlink) the marker",
        )
        after = json.loads((self.ap / "state.json").read_text())
        self.assertNotIn(
            "stall_reason",
            after,
            "no oversized-task stall may be recorded when the state write fails",
        )
        self.assertEqual(
            captured.getvalue().strip(),
            "",
            "no stall envelope may be emitted when the state write fails",
        )


class DurabilityBeforePublishTests(unittest.TestCase):
    """Every temp-then-rename in this hook fsyncs before publishing.

    os.replace is atomic against a crash but not against power loss: the
    directory entry can reach disk before the payload. For the turn counter
    that resurrects a stale count, so the tripwire re-fires or never fires for
    that session; for the state-write-failed marker it silently loses the halt
    record the recovery path reads. Asserts ordering, not merely that fsync
    was called, because a sync after the rename would be useless.
    """

    def setUp(self) -> None:
        self.module = _load_hook_module()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ap = Path(self.tmp.name)

    def _publish_order(self, write) -> list[str]:
        calls: list[str] = []
        real_fsync, real_replace = os.fsync, os.replace

        def spy_fsync(fd: int) -> None:
            calls.append("fsync")
            real_fsync(fd)

        def spy_replace(src, dst) -> None:
            calls.append("replace")
            real_replace(src, dst)

        with (
            unittest.mock.patch.object(os, "fsync", spy_fsync),
            unittest.mock.patch.object(os, "replace", spy_replace),
        ):
            write()
        return calls

    def test_turn_counter_is_fsynced_before_the_rename_publishes_it(self) -> None:
        calls = self._publish_order(
            lambda: self.module._bump_and_check_tripwire(self.ap, "sess-1"),
        )
        self.assertEqual(calls, ["fsync", "replace"])

    def test_state_write_failed_marker_is_fsynced_before_the_rename(self) -> None:
        calls = self._publish_order(
            lambda: self.module._write_state_write_failed_marker(self.ap, "detail"),
        )
        self.assertEqual(calls, ["fsync", "replace"])

    def test_turn_counter_still_survives_a_write_failure_without_firing(self) -> None:
        """The added fsync must not break the never-fire-what-we-cannot-persist
        rule: an OSError anywhere in the write path still returns False."""
        self.module._bump_and_check_tripwire(self.ap, "sess-1")

        def boom(*_args, **_kwargs):
            raise OSError("disk full")

        with unittest.mock.patch.object(os, "fsync", boom):
            count, fired = self.module._bump_and_check_tripwire(self.ap, "sess-1")
        self.assertFalse(fired)
        # The count is still returned for the task record (PRD 00200).
        self.assertEqual(count, 2)


if __name__ == "__main__":
    unittest.main()
