"""Tests for autopilot_context_cap_hook.py.

Stdlib-only unittest, subprocess.run pattern (matches ~/.claude/hooks/tests/).
"""

import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

HOOK = Path(__file__).parent / "autopilot_context_cap_hook.py"


def _loop_env() -> dict[str, str]:
    """Env for a loop-wrapped session. The hook is guarded on
    $_AUTOPILOT_LOOP (2026-07-19: interactive sessions sharing a cwd tree
    with parked autopilot state must never rotate/stall it), so tests that
    exercise the firing paths must run inside a simulated loop env."""
    env = dict(os.environ)
    env["_AUTOPILOT_LOOP"] = "test-loop"
    # A zone 5:30 off UTC on every host, so a naive LOCAL stamp dressed up
    # with a fake `+00:00` falls outside the marker tests' before/after window
    # here too, not only on a host whose clock happens to sit away from UTC.
    env["TZ"] = "Asia/Kolkata"
    return env


def _load_hook_module():
    """Load the hook as an importable module so its `main()` can be called
    in-process. Used by the perf test to time only the hook's work,
    excluding subprocess fork + Python interpreter startup."""
    spec = importlib.util.spec_from_file_location("autopilot_context_cap_hook", HOOK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class HookFixture:
    """Sets up a working directory with dev/local/autopilot/ and a transcript."""

    def __init__(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = Path(self.tmp.name)
        self.autopilot_dir = self.cwd / "dev" / "local" / "autopilot"
        self.autopilot_dir.mkdir(parents=True, exist_ok=True)
        self.transcript = self.cwd / "transcript.jsonl"
        self.transcript.touch()

    def write_state(self, **fields: object) -> None:
        default: dict[str, object] = {
            "prd": "00099-test.md",
            "phase": "build",
            "phases_completed": [],
            "cycle": 1,
            "tasks_total": 0,
            "tasks_completed": 0,
            "tasks": [],
            "review_cycles": [],
            "autonomous_decisions": [],
            "deferred_decisions": [],
            "doubts": [],
            "task_aborts": [],
            "cap_rotations": [],
            "replan_count": 0,
            "needs_attention": False,
        }
        default.update(fields)
        (self.autopilot_dir / "state.json").write_text(json.dumps(default))

    def write_transcript_lines(self, lines: list[dict]) -> None:
        with self.transcript.open("w") as f:
            for entry in lines:
                f.write(json.dumps(entry) + "\n")

    def usage_line(
        self,
        *,
        input_tokens: int = 0,
        cache_read: int = 0,
        cache_create: int = 0,
    ) -> dict:
        return {
            "type": "assistant",
            "message": {
                "usage": {
                    "input_tokens": input_tokens,
                    "cache_read_input_tokens": cache_read,
                    "cache_creation_input_tokens": cache_create,
                },
            },
        }

    def run_hook(
        self,
        stdin_payload: dict | None = None,
        *,
        in_loop: bool = True,
    ) -> subprocess.CompletedProcess:
        if stdin_payload is None:
            stdin_payload = {
                "session_id": "test-session",
                "transcript_path": str(self.transcript),
            }
        env = _loop_env()
        if not in_loop:
            env.pop("_AUTOPILOT_LOOP", None)
        return subprocess.run(
            [sys.executable, str(HOOK)],
            input=json.dumps(stdin_payload),
            capture_output=True,
            text=True,
            cwd=str(self.cwd),
            timeout=5,
            env=env,
        )

    def cleanup(self) -> None:
        self.tmp.cleanup()


class ContextCapHookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fx = HookFixture()
        self.addCleanup(self.fx.cleanup)

    # No-op cases ------------------------------------------------------------

    def test_no_state_json_is_noop(self) -> None:
        result = self.fx.run_hook()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")

    def test_phase_not_build_is_noop(self) -> None:
        """The gate is the `build` phase. Over the cap on any other gate
        (here `review`) is a no-op — only `build` runs /work tasks."""
        self.fx.write_state(phase="review")
        self.fx.write_transcript_lines([self.fx.usage_line(input_tokens=600_000)])
        result = self.fx.run_hook()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")
        self.assertFalse((self.fx.autopilot_dir / ".cap-fired").exists())

    def test_noops_on_work_phase(self) -> None:
        """`work` is the now-dead pre-collapse phase name (folded into
        `build`). Over the cap with phase=="work" must NOT fire."""
        self.fx.write_state(
            phase="work",
            tasks=[{"id": "task-x", "name": "y", "status": "in_progress"}],
        )
        self.fx.write_transcript_lines([self.fx.usage_line(input_tokens=600_000)])
        result = self.fx.run_hook()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")
        self.assertFalse((self.fx.autopilot_dir / ".cap-fired").exists())

    def test_marker_for_same_task_is_noop(self) -> None:
        """Marker carries the task id. When the in-progress task matches the
        marker, the hook is a no-op (already fired for this task)."""
        self.fx.write_state(
            phase="build",
            tasks=[{"id": "task-x", "name": "y", "status": "in_progress"}],
        )
        self.fx.write_transcript_lines([self.fx.usage_line(input_tokens=600_000)])
        (self.fx.autopilot_dir / ".cap-fired").write_text("task-x")
        result = self.fx.run_hook()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")

    def test_usage_under_threshold_is_noop(self) -> None:
        self.fx.write_state(phase="build")
        self.fx.write_transcript_lines(
            [
                self.fx.usage_line(
                    input_tokens=50_000,
                    cache_read=40_000,
                    cache_create=10_000,
                ),
            ],
        )
        result = self.fx.run_hook()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")
        self.assertFalse((self.fx.autopilot_dir / ".cap-fired").exists())

    def test_missing_transcript_path_field_is_noop(self) -> None:
        self.fx.write_state(phase="build")
        result = self.fx.run_hook(stdin_payload={"session_id": "x"})
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")

    def test_malformed_transcript_lines_is_noop(self) -> None:
        self.fx.write_state(phase="build")
        self.fx.transcript.write_text("not json\n{also not\n")
        result = self.fx.run_hook()
        self.assertEqual(result.returncode, 0)
        self.assertFalse((self.fx.autopilot_dir / ".cap-fired").exists())

    # Loop guard -------------------------------------------------------------

    def test_interactive_session_is_noop_even_over_cap(self) -> None:
        """2026-07-19 regression: without $_AUTOPILOT_LOOP the hook must not
        touch parked autopilot state, even far over the cap. An interactive
        session sharing the cwd tree with a parked batch wrote rotations and
        a bogus oversized-task stall into that batch's state.json."""
        self.fx.write_state(
            phase="build",
            tasks=[{"id": "task-x", "name": "y", "status": "in_progress"}],
        )
        self.fx.write_transcript_lines([self.fx.usage_line(input_tokens=600_000)])
        before = (self.fx.autopilot_dir / "state.json").read_text()
        result = self.fx.run_hook(in_loop=False)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")
        self.assertEqual((self.fx.autopilot_dir / "state.json").read_text(), before)
        self.assertFalse((self.fx.autopilot_dir / ".cap-fired").exists())
        self.assertFalse((self.fx.autopilot_dir / ".handoff-requested").exists())

    # Single hard cap --------------------------------------------------------

    def test_does_not_fire_below_cap(self) -> None:
        """The single hard cap is 500K; usage below it does not fire (no
        window classification — the same cap applies regardless of model)."""
        self.fx.write_state(phase="build")
        self.fx.write_transcript_lines([self.fx.usage_line(input_tokens=200_000)])
        result = self.fx.run_hook()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")
        self.assertFalse((self.fx.autopilot_dir / ".cap-fired").exists())

    def test_fires_above_cap(self) -> None:
        """Usage above the single 500K hard cap fires the rotation."""
        self.fx.write_state(
            phase="build",
            tasks=[{"id": "task-big", "name": "y", "status": "in_progress"}],
        )
        self.fx.write_transcript_lines([self.fx.usage_line(input_tokens=600_000)])
        result = self.fx.run_hook()
        self.assertEqual(result.returncode, 0)
        self.assertTrue((self.fx.autopilot_dir / ".cap-fired").exists())
        out = json.loads(result.stdout)
        self.assertIn("hookSpecificOutput", out)

    # Task usage and call record (PRD 00200) --------------------------------

    def _seed_counter(self, session_id: str, count: int) -> None:
        (self.fx.autopilot_dir / ".turn-counts.json").write_text(
            json.dumps({"counts": {session_id: count}, "fired": []}),
        )

    def _tasks(self) -> list[dict]:
        return json.loads((self.fx.autopilot_dir / "state.json").read_text())["tasks"]

    def test_usage_and_calls_at_start_are_written_once(self) -> None:
        """The first PostToolUse after a task turns in_progress stamps the
        session's usage total and tool-call count on it; a later fire with a
        different total leaves both fields as first written."""
        self.fx.write_state(
            phase="build",
            tasks=[{"id": "t1", "name": "y", "status": "in_progress"}],
        )
        self.fx.write_transcript_lines([self.fx.usage_line(input_tokens=120_000)])
        self._seed_counter("test-session", 41)
        result = self.fx.run_hook()
        self.assertEqual(result.returncode, 0)
        task = self._tasks()[0]
        self.assertEqual(task["usage_at_start"], 120_000)
        self.assertEqual(task["calls_at_start"], 42)

        self.fx.write_transcript_lines([self.fx.usage_line(input_tokens=130_000)])
        result = self.fx.run_hook()
        self.assertEqual(result.returncode, 0)
        task = self._tasks()[0]
        self.assertEqual(task["usage_at_start"], 120_000)
        self.assertEqual(task["calls_at_start"], 42)
        self.assertNotIn("usage_at_done", task)

    def test_usage_and_calls_at_done_are_written_on_completion(self) -> None:
        """The first PostToolUse after a task turns completed stamps the done
        pair; a task already carrying it is left alone, and the pending task
        gets no done pair."""
        self.fx.write_state(
            phase="build",
            tasks=[
                {
                    "id": "t1",
                    "name": "y",
                    "status": "completed",
                    "usage_at_start": 100_000,
                    "calls_at_start": 10,
                },
                {
                    "id": "t0",
                    "name": "x",
                    "status": "completed",
                    "usage_at_start": 40_000,
                    "calls_at_start": 3,
                    "usage_at_done": 90_000,
                    "calls_at_done": 9,
                },
                {"id": "t2", "name": "z", "status": "pending"},
            ],
        )
        self.fx.write_transcript_lines([self.fx.usage_line(input_tokens=250_000)])
        self._seed_counter("test-session", 209)
        result = self.fx.run_hook()
        self.assertEqual(result.returncode, 0)
        done, earlier, pending = self._tasks()
        self.assertEqual(done["usage_at_done"], 250_000)
        self.assertEqual(done["calls_at_done"], 210)
        self.assertEqual(earlier["usage_at_done"], 90_000)
        self.assertEqual(earlier["calls_at_done"], 9)
        self.assertNotIn("usage_at_done", pending)
        self.assertNotIn("usage_at_start", pending)

    def test_non_int_record_field_is_treated_as_absent_with_one_stderr_line(
        self,
    ) -> None:
        """A record field holding a non-int (a string, a bool) is absent: it
        is rewritten, and exactly one stderr line names it. No crash."""
        self.fx.write_state(
            phase="build",
            tasks=[
                {
                    "id": "t1",
                    "name": "y",
                    "status": "in_progress",
                    "usage_at_start": "lots",
                    "calls_at_start": True,
                },
            ],
        )
        self.fx.write_transcript_lines([self.fx.usage_line(input_tokens=120_000)])
        self._seed_counter("test-session", 41)
        result = self.fx.run_hook()
        self.assertEqual(result.returncode, 0)
        task = self._tasks()[0]
        self.assertEqual(task["usage_at_start"], 120_000)
        self.assertEqual(task["calls_at_start"], 42)
        lines = [line for line in result.stderr.splitlines() if "not an int" in line]
        self.assertEqual(len(lines), 1, result.stderr)

    # Walk-up cases ---------------------------------------------------------

    def test_finds_autopilot_dir_when_cwd_is_subdirectory(self) -> None:
        """Hook must walk up from cwd to find dev/local/autopilot/.

        Same fix pattern as a0c5b8e09 for the stop hook: agent may cd into
        a subdirectory during work, so a relative `dev/local/autopilot`
        resolution from cwd must walk parents until found.
        """
        self.fx.write_state(
            phase="build",
            tasks=[{"id": "task-deep", "name": "x", "status": "in_progress"}],
        )
        self.fx.write_transcript_lines([self.fx.usage_line(input_tokens=600_000)])
        deep = self.fx.cwd / "src" / "modules" / "feature"
        deep.mkdir(parents=True)
        result = subprocess.run(
            [sys.executable, str(HOOK)],
            input=json.dumps({"transcript_path": str(self.fx.transcript)}),
            capture_output=True,
            text=True,
            cwd=str(deep),
            timeout=5,
            env=_loop_env(),
        )
        self.assertEqual(result.returncode, 0)
        self.assertTrue((self.fx.autopilot_dir / ".cap-fired").exists())
        state = json.loads((self.fx.autopilot_dir / "state.json").read_text())
        self.assertEqual(state["cap_rotations"][-1]["task_id"], "task-deep")

    def test_no_autopilot_ancestor_is_noop(self) -> None:
        """When cwd has no dev/local/autopilot ancestor, hook is a no-op."""
        with tempfile.TemporaryDirectory() as plain:
            plain_path = Path(plain)
            transcript = plain_path / "transcript.jsonl"
            transcript.write_text(
                json.dumps(self.fx.usage_line(input_tokens=600_000)) + "\n",
            )
            result = subprocess.run(
                [sys.executable, str(HOOK)],
                input=json.dumps({"transcript_path": str(transcript)}),
                capture_output=True,
                text=True,
                cwd=plain,
                timeout=5,
                env=_loop_env(),
            )
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout.strip(), "")

    # Symlink and unreadable-path edge cases ---------------------------------

    def test_dangling_symlink_at_autopilot_path_is_noop(self) -> None:
        """A dangling symlink where dev/local/autopilot/ would be must not
        be returned as the autopilot dir. is_dir() returns False on dangling
        symlinks, so the walk-up skips it and returns None, making the hook
        a no-op (no valid autopilot dir found).
        """
        with tempfile.TemporaryDirectory() as plain:
            plain_path = Path(plain)
            ap_dir = plain_path / "dev" / "local" / "autopilot"
            ap_dir.parent.mkdir(parents=True)
            os.symlink("/nonexistent/path/that/does/not/exist", str(ap_dir))
            transcript = plain_path / "t.jsonl"
            transcript.write_text(
                json.dumps(self.fx.usage_line(input_tokens=200_000)) + "\n",
            )
            result = subprocess.run(
                [sys.executable, str(HOOK)],
                input=json.dumps({"transcript_path": str(transcript)}),
                capture_output=True,
                text=True,
                cwd=str(plain_path),
                timeout=5,
                env=_loop_env(),
            )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")

    def test_unreadable_transcript_path_is_noop(self) -> None:
        """When transcript_path exists but is not readable (permissions 000),
        _latest_usage_total must return None and the hook must be a no-op.
        Verifies the OSError path in _latest_usage_total.
        """
        self.fx.write_state(phase="build")
        self.fx.transcript.write_text(
            json.dumps(self.fx.usage_line(input_tokens=200_000)) + "\n",
        )
        original_mode = self.fx.transcript.stat().st_mode
        self.fx.transcript.chmod(0o000)
        self.addCleanup(self.fx.transcript.chmod, original_mode)
        result = self.fx.run_hook()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")
        self.assertFalse((self.fx.autopilot_dir / ".cap-fired").exists())

    def test_transcript_with_no_usage_lines_is_noop(self) -> None:
        """A transcript containing only non-usage JSON (no message.usage field)
        must cause the hook to return None from _latest_usage_total and be a
        no-op — no abort emitted even at very large file sizes.
        """
        self.fx.write_state(phase="build")
        lines = [
            {"type": "user", "message": {"content": "hello"}},
            {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}},
            {"type": "tool_result", "content": [{"type": "text", "text": "output"}]},
        ]
        self.fx.write_transcript_lines(lines)
        result = self.fx.run_hook()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")
        self.assertFalse((self.fx.autopilot_dir / ".cap-fired").exists())

    def test_transcript_truncated_mid_line_is_noop(self) -> None:
        """A transcript whose last line is truncated mid-JSON (no closing brace)
        must not crash the hook. Partial lines are silently skipped by the
        JSON parser, and if no complete usage line is found, returns None.
        """
        self.fx.write_state(phase="build")
        with self.fx.transcript.open("w") as f:
            f.write(json.dumps(self.fx.usage_line(input_tokens=50_000)) + "\n")
            # Write a partial line (truncated JSON object, no newline)
            f.write('{"message": {"usage": {"input_tokens": 999999')
        result = self.fx.run_hook()
        self.assertEqual(result.returncode, 0)
        # The truncated line has the high-token data but is unparseable;
        # the hook should pick up the complete 50K line (under threshold).
        self.assertEqual(result.stdout.strip(), "")
        self.assertFalse((self.fx.autopilot_dir / ".cap-fired").exists())

    # Performance ------------------------------------------------------------

    def test_hook_main_completes_under_100ms_in_process(self) -> None:
        """PRD 00024 sets a <100ms target on the hook itself. Time only the
        in-process `main()` work so the threshold tracks hook logic, not
        the ~50-80ms Python interpreter cold-start that a subprocess fork
        would add. A regression that scanned the full transcript instead of
        the 64KB tail would balloon the timing here even at this scale.

        The transcript is ~4.8 MB of noise followed by one **over-threshold**
        usage line at the tail. Using an over-threshold value lets the test
        assert that the hook actually parsed the tail and emitted the
        rotation envelope — a regression that bailed out before reading the
        transcript would produce empty stdout and fail the assertion,
        regardless of how fast it ran.
        """
        self.fx.write_state(phase="build")
        line_blob = json.dumps({"type": "noise", "padding": "x" * 4_000}) + "\n"
        with self.fx.transcript.open("w") as f:
            for _ in range(1_200):
                f.write(line_blob)
            f.write(json.dumps(self.fx.usage_line(input_tokens=600_000)) + "\n")

        module = _load_hook_module()
        payload = json.dumps({"transcript_path": str(self.fx.transcript)})
        prev_stdin, prev_stdout, prev_cwd = sys.stdin, sys.stdout, os.getcwd()
        prev_loop = os.environ.get("_AUTOPILOT_LOOP")
        os.environ["_AUTOPILOT_LOOP"] = "test-loop"
        sys.stdin = io.StringIO(payload)
        captured_stdout = io.StringIO()
        sys.stdout = captured_stdout
        os.chdir(self.fx.cwd)
        try:
            start = time.perf_counter()
            module.main()
            elapsed_ms = (time.perf_counter() - start) * 1_000
        finally:
            sys.stdin = prev_stdin
            sys.stdout = prev_stdout
            os.chdir(prev_cwd)
            if prev_loop is None:
                os.environ.pop("_AUTOPILOT_LOOP", None)
            else:
                os.environ["_AUTOPILOT_LOOP"] = prev_loop

        self.assertLess(elapsed_ms, 100, f"hook took {elapsed_ms:.0f}ms")
        # Proves the tail-read + parse code path actually ran. A regression
        # that bailed out before reading the transcript would leave stdout
        # empty and fail here, not on the timing assertion above.
        emitted = captured_stdout.getvalue()
        self.assertIn("hookSpecificOutput", emitted)
        self.assertIn("context cap reached", emitted.lower())

    # Marker self-clearing -------------------------------------------------

    def test_stale_marker_for_different_task_is_cleared_and_hook_fires(self) -> None:
        """When the in-progress task differs from the marker's task id, the
        hook must clear the stale marker and process the overrun. Otherwise
        a missed `/work` step-2 Bash clear would silently disable the cap
        for every task in the phase after the first abort.
        """
        self.fx.write_state(
            phase="build",
            tasks=[{"id": "task-new", "name": "y", "status": "in_progress"}],
        )
        self.fx.write_transcript_lines([self.fx.usage_line(input_tokens=600_000)])
        (self.fx.autopilot_dir / ".cap-fired").write_text("task-old")

        result = self.fx.run_hook()
        self.assertEqual(result.returncode, 0)

        marker = self.fx.autopilot_dir / ".cap-fired"
        self.assertTrue(marker.exists())
        self.assertEqual(marker.read_text().strip(), "task-new")
        out = json.loads(result.stdout)
        self.assertIn("hookSpecificOutput", out)

    def test_marker_with_empty_contents_is_cleared(self) -> None:
        """A marker file from a pre-self-clearing version (touched, no
        contents) must not block the hook. Cleared and re-fired on a real
        overrun."""
        self.fx.write_state(
            phase="build",
            tasks=[{"id": "task-x", "name": "y", "status": "in_progress"}],
        )
        self.fx.write_transcript_lines([self.fx.usage_line(input_tokens=600_000)])
        (self.fx.autopilot_dir / ".cap-fired").touch()

        result = self.fx.run_hook()
        self.assertEqual(result.returncode, 0)
        marker = self.fx.autopilot_dir / ".cap-fired"
        self.assertEqual(marker.read_text().strip(), "task-x")

    # Reverse-chunk tail search --------------------------------------------

    def test_finds_usage_line_after_large_tool_result(self) -> None:
        """A single large tool result (> 64KB) between the latest usage line
        and EOF used to push the usage line out of the fixed 64KB tail
        window, causing the cap to silently disengage. The chunked reverse
        scan keeps reading until a usage line is found.
        """
        self.fx.write_state(phase="build")
        # 200KB of noise (mixture of valid-shape lines and junk), then the
        # latest over-threshold usage line at EOF. Old TAIL_BYTES=64KB
        # would miss the usage line because the 200KB noise block precedes
        # it; with reverse-chunk reads the hook walks back until found.
        lines = []
        big_payload = "x" * 200_000
        lines.append({"type": "noise", "padding": big_payload})
        lines.append(self.fx.usage_line(input_tokens=600_000))
        self.fx.write_transcript_lines(lines)

        result = self.fx.run_hook()
        self.assertEqual(result.returncode, 0)
        self.assertTrue((self.fx.autopilot_dir / ".cap-fired").exists())
        out = json.loads(result.stdout)
        self.assertIn("hookSpecificOutput", out)

    def test_reverse_scan_bounded_by_max_tail_bytes(self) -> None:
        """If the transcript is many MB and the latest usage line is buried
        deep, the hook still completes (it gives up at MAX_TAIL_BYTES). It
        should not crash, hang, or read the entire file. Verifies the cap
        is bounded.
        """
        self.fx.write_state(phase="build")
        with self.fx.transcript.open("w") as f:
            # The first line is the only usage line; everything after is
            # noise that pushes the usage line out of MAX_TAIL_BYTES.
            f.write(json.dumps(self.fx.usage_line(input_tokens=600_000)) + "\n")
            noise = json.dumps({"type": "noise", "padding": "x" * 100_000}) + "\n"
            # ~5MB of noise — more than MAX_TAIL_BYTES (4MB).
            for _ in range(50):
                f.write(noise)

        module = _load_hook_module()
        payload = json.dumps({"transcript_path": str(self.fx.transcript)})
        prev_stdin, prev_stdout, prev_cwd = sys.stdin, sys.stdout, os.getcwd()
        prev_loop = os.environ.get("_AUTOPILOT_LOOP")
        os.environ["_AUTOPILOT_LOOP"] = "test-loop"
        sys.stdin = io.StringIO(payload)
        captured = io.StringIO()
        sys.stdout = captured
        os.chdir(self.fx.cwd)
        try:
            start = time.perf_counter()
            module.main()
            elapsed_ms = (time.perf_counter() - start) * 1_000
        finally:
            sys.stdin = prev_stdin
            sys.stdout = prev_stdout
            os.chdir(prev_cwd)
            if prev_loop is None:
                os.environ.pop("_AUTOPILOT_LOOP", None)
            else:
                os.environ["_AUTOPILOT_LOOP"] = prev_loop

        # No abort emitted — the usage line is beyond the MAX_TAIL_BYTES
        # window, so the hook treats this turn as "no recent usage info"
        # and stays silent. The hook MUST not hang or crash trying to
        # search the whole multi-MB file.
        self.assertEqual(captured.getvalue().strip(), "")
        # Bounded read should still complete fast — well under 500ms.
        self.assertLess(elapsed_ms, 500, f"hook took {elapsed_ms:.0f}ms")

    def test_review_phase_writes_no_handoff_marker(self) -> None:
        """The build-only guard sits ahead of the headroom check: headroom
        exhausted in `review` requests no handoff — only `build` runs /work tasks."""
        self.fx.write_state(
            phase="review",
            tasks=[{"id": "task-x", "name": "y", "status": "in_progress"}],
        )
        self.fx.write_transcript_lines([self.fx.usage_line(input_tokens=400_000)])
        result = self.fx.run_hook()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")
        self.assertFalse((self.fx.autopilot_dir / ".handoff-requested").exists())

    def test_missing_or_unreadable_state_writes_no_handoff_marker(self) -> None:
        """The state-read guard also sits ahead of the headroom check. With
        state.json absent, or present-and-unreadable (permissions 000) while
        holding a valid build state, nothing may be written."""
        self.fx.write_transcript_lines([self.fx.usage_line(input_tokens=400_000)])
        handoff = self.fx.autopilot_dir / ".handoff-requested"
        state = self.fx.autopilot_dir / "state.json"

        with self.subTest(state="missing"):
            result = self.fx.run_hook()
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout.strip(), "")
            self.assertFalse(handoff.exists())

        with self.subTest(state="unreadable"):
            self.fx.write_state(
                phase="build",
                tasks=[{"id": "task-x", "name": "y", "status": "in_progress"}],
            )
            original_mode = state.stat().st_mode
            state.chmod(0o000)
            self.addCleanup(state.chmod, original_mode)
            result = self.fx.run_hook()
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout.strip(), "")
            self.assertFalse(handoff.exists())

    def test_cap_fired_marker_for_same_task_blocks_headroom_path(self) -> None:
        """When `.cap-fired` already named the in-progress task (a rotation
        already fired), the hook early-returns before the headroom check — no
        `.handoff-requested` is written for that task."""
        self.fx.write_state(
            phase="build",
            tasks=[{"id": "task-x", "name": "y", "status": "in_progress"}],
        )
        self.fx.write_transcript_lines([self.fx.usage_line(input_tokens=400_000)])
        (self.fx.autopilot_dir / ".cap-fired").write_text("task-x")
        result = self.fx.run_hook()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")
        self.assertFalse((self.fx.autopilot_dir / ".handoff-requested").exists())


if __name__ == "__main__":
    unittest.main()
