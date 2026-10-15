"""gemini-run.sh: an auth failure is permanent, and the native fallback is bounded.

Black-box: stub `copilot` and `gemini` on PATH, run gemini-run.sh as a
subprocess, and observe exit codes, stub argv files and the stub's own pids.
The timeout stub backgrounds a real `sleep` child, so killing only the stub
leaves that child alive and the leftover-child test catches it.
"""

from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent / "gemini-run.sh"
REPO = Path(__file__).resolve().parents[3]
PROMPT = "say hi from gemini"
TIER_REJECTION = "IneligibleTierError: This client is no longer supported for Gemini Code Assist for individuals"

COPILOT_STUB = """#!/bin/bash
printf '%s\\n' "$@" > "${COPILOT_ARGV_FILE:?}"
echo "stub-copilot-ran"
[ -z "${COPILOT_STDERR:-}" ] || printf '%s\\n' "$COPILOT_STDERR" >&2
exit "${COPILOT_EXIT_CODE:-0}"
"""

GEMINI_STUB = """#!/bin/bash
printf '%s\\n' "$@" > "${GEMINI_ARGV_FILE:?}"
[ -z "${GEMINI_PIDFILE:-}" ] || echo $$ > "$GEMINI_PIDFILE"
if [ -n "${GEMINI_SLEEP_SECONDS:-}" ]; then
    sleep "$GEMINI_SLEEP_SECONDS" &
    [ -z "${GEMINI_CHILD_PIDFILE:-}" ] || echo $! > "$GEMINI_CHILD_PIDFILE"
    sleep "$GEMINI_SLEEP_SECONDS"
fi
if [ -n "${GEMINI_ORPHAN_SECONDS:-}" ]; then
    # Backgrounded and never waited on: the stub exits while this child is
    # still alive, still holding the inherited stderr fifo open.
    sleep "$GEMINI_ORPHAN_SECONDS" &
    [ -z "${GEMINI_CHILD_PIDFILE:-}" ] || echo $! > "$GEMINI_CHILD_PIDFILE"
fi
echo "stub-gemini-ran"
exit "${GEMINI_EXIT_CODE:-0}"
"""


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def _gone_within(pid: int, seconds: float) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if not _alive(pid):
            return True
        time.sleep(0.1)
    return not _alive(pid)


def _stubs(tmp_path: Path) -> dict[str, str]:
    stub_dir = tmp_path / "stub"
    stub_dir.mkdir()
    for name, body in (("copilot", COPILOT_STUB), ("gemini", GEMINI_STUB)):
        stub = stub_dir / name
        stub.write_text(body, encoding="utf-8")
        stub.chmod(0o755)
    run_tmp = tmp_path / "tmp"
    run_tmp.mkdir()
    # Clean env: no recursion-guard markers, and no mise on PATH (the wrapper
    # would prepend mise's PATH ahead of the stubs).
    return {
        "PATH": f"{stub_dir}:/usr/bin:/bin",
        "HOME": str(tmp_path),
        "TMPDIR": str(run_tmp),
        "COPILOT_ARGV_FILE": str(tmp_path / "copilot.argv"),
        "GEMINI_ARGV_FILE": str(tmp_path / "gemini.argv"),
    }


def _prompt_file(tmp_path: Path) -> Path:
    prompt = tmp_path / "prompt.txt"
    prompt.write_text(PROMPT, encoding="utf-8")
    return prompt


def _run(tmp_path: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT), "-f", str(_prompt_file(tmp_path))],
        cwd=REPO,
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _run_to_deadline(tmp_path: Path, env: dict[str, str]) -> tuple[int, float]:
    """Run with headless stdin in a new session; output goes to files, not pipes,
    so a leaked child holding stdout cannot stretch the measured return time."""
    out = (tmp_path / "wrapper.out").open("w")
    err = (tmp_path / "wrapper.err").open("w")
    started = time.monotonic()
    proc = subprocess.Popen(
        ["bash", str(SCRIPT), "-f", str(_prompt_file(tmp_path))],
        cwd=REPO,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=out,
        stderr=err,
        start_new_session=True,
    )
    try:
        rc = proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait()
        rc = proc.returncode
    finally:
        out.close()
        err.close()
    return rc, time.monotonic() - started


def _timeout_env(tmp_path: Path) -> dict[str, str]:
    env = _stubs(tmp_path)
    env.update(
        COPILOT_EXIT_CODE="1",
        COPILOT_STDERR=TIER_REJECTION,
        GEMINI_FALLBACK_TIMEOUT="2",
        GEMINI_SLEEP_SECONDS="30",
        GEMINI_PIDFILE=str(tmp_path / "gemini.pid"),
        GEMINI_CHILD_PIDFILE=str(tmp_path / "gemini-child.pid"),
    )
    return env


@pytest.mark.parametrize(
    "auth_error",
    [
        "Error: Authentication failed. Run `copilot login` to sign in.",
        "Error: the token lacks the Copilot Requests permission.",
        # Variants: different case and surrounding text, so a match on the two
        # fixture sentences alone cannot pass.
        "copilot: authentication failed (token expired)",
        "AUTHENTICATION FAILED",
        "HTTP 403: your PAT is missing copilot requests permission; regenerate it",
    ],
)
def test_auth_failure_exits_4_without_fallback(tmp_path: Path, auth_error: str) -> None:
    env = _stubs(tmp_path)
    env.update(COPILOT_EXIT_CODE="1", COPILOT_STDERR=auth_error)
    result = _run(tmp_path, env)
    assert Path(env["COPILOT_ARGV_FILE"]).is_file(), "copilot must be tried first"
    assert result.returncode == 4, (
        f"auth failure must be permanent (exit 4); stderr: {result.stderr}"
    )
    assert auth_error in result.stderr, "the auth reason must reach the caller"
    gemini_argv = Path(env["GEMINI_ARGV_FILE"])
    assert not gemini_argv.exists(), (
        "native gemini must not be tried on an auth failure; "
        f"argv: {gemini_argv.read_text()!r}"
    )
    assert "stub-gemini-ran" not in result.stdout


def test_ordinary_copilot_failure_stays_exit_1_without_fallback(tmp_path: Path) -> None:
    env = _stubs(tmp_path)
    env.update(
        COPILOT_EXIT_CODE="1", COPILOT_STDERR="Error: read ECONNRESET (network)"
    )
    result = _run(tmp_path, env)
    assert result.returncode == 1, (
        f"a transient failure is not permanent: expected exit 1, got {result.returncode}; "
        f"stderr: {result.stderr}"
    )
    assert not Path(env["GEMINI_ARGV_FILE"]).exists(), (
        "an ordinary failure must not fall back to native gemini"
    )


def test_successful_copilot_run_mentioning_auth_keeps_exit_0(tmp_path: Path) -> None:
    env = _stubs(tmp_path)
    env.update(
        COPILOT_EXIT_CODE="0",
        COPILOT_STDERR="warning: Authentication failed for an optional MCP server",
    )
    result = _run(tmp_path, env)
    assert result.returncode == 0, (
        f"auth text on a successful run must not discard it; stderr: {result.stderr}"
    )
    assert "stub-copilot-ran" in result.stdout
    assert not Path(env["GEMINI_ARGV_FILE"]).exists()


def test_tier_rejection_still_falls_back(tmp_path: Path) -> None:
    env = _stubs(tmp_path)
    # A large deadline with a stub that exits at once: the wrapper must return
    # on the process exit, not after a fixed wait.
    env.update(
        COPILOT_EXIT_CODE="1",
        COPILOT_STDERR=TIER_REJECTION,
        GEMINI_EXIT_CODE="7",
        GEMINI_FALLBACK_TIMEOUT="10",
    )
    started = time.monotonic()
    result = _run(tmp_path, env)
    elapsed = time.monotonic() - started
    assert elapsed < 3.0, (
        f"the fallback must end when gemini exits, not at the 10s deadline: {elapsed:.2f}s"
    )
    gemini_argv = Path(env["GEMINI_ARGV_FILE"])
    assert gemini_argv.is_file(), (
        f"tier rejection must fall back to native gemini; stderr: {result.stderr}"
    )
    argv = gemini_argv.read_text().splitlines()
    assert "-p" in argv and argv[argv.index("-p") + 1] == PROMPT, (
        f"fallback argv: {argv}"
    )
    assert "stub-gemini-ran" in result.stdout
    assert result.returncode == 7, (
        f"the native stub's exit code must propagate; stderr: {result.stderr}"
    )


@pytest.mark.parametrize("deadline", [2, 3])
def test_fallback_with_no_output_exits_4_at_the_deadline(
    tmp_path: Path, deadline: int
) -> None:
    # Two distinct values: a hardcoded deadline cannot satisfy both windows.
    env = _timeout_env(tmp_path)
    env["GEMINI_FALLBACK_TIMEOUT"] = str(deadline)
    pidfiles = [tmp_path / "gemini.pid", tmp_path / "gemini-child.pid"]
    try:
        rc, elapsed = _run_to_deadline(tmp_path, env)
        assert Path(env["GEMINI_ARGV_FILE"]).is_file(), (
            "the fallback must actually start"
        )
        assert elapsed >= deadline, (
            f"returned before the {deadline}s deadline: {elapsed:.2f}s"
        )
        assert elapsed < deadline + 3.0, (
            f"GEMINI_FALLBACK_TIMEOUT={deadline} not honored: took {elapsed:.2f}s"
        )
        assert rc == 4, (
            f"a timed-out fallback must exit 4, got {rc}; stderr: {(tmp_path / 'wrapper.err').read_text()}"
        )
    finally:
        for pidfile in pidfiles:
            if pidfile.exists() and _alive(pid := int(pidfile.read_text().strip())):
                os.kill(pid, signal.SIGKILL)


def test_fallback_leaves_no_child_running(tmp_path: Path) -> None:
    env = _timeout_env(tmp_path)
    leader_file = tmp_path / "gemini.pid"
    child_file = tmp_path / "gemini-child.pid"
    pids: list[int] = []
    # Same command as the stub's child, outside its group: a kill-by-name
    # implementation would take it down too.
    decoy = subprocess.Popen(["sleep", "30"], start_new_session=True)
    try:
        rc, _ = _run_to_deadline(tmp_path, env)
        pids = [
            int(leader_file.read_text().strip()),
            int(child_file.read_text().strip()),
        ]
        assert rc == 4, f"got {rc}; stderr: {(tmp_path / 'wrapper.err').read_text()}"
        assert _gone_within(pids[0], 3), (
            "the native gemini process itself must be killed"
        )
        assert _gone_within(pids[1], 3), (
            "the gemini process's backgrounded child must be killed with its group"
        )
        assert decoy.poll() is None, (
            "a process outside the fallback's group must survive"
        )
    finally:
        decoy.kill()
        decoy.wait()
        for pid in pids:
            if _alive(pid):
                os.kill(pid, signal.SIGKILL)


def test_watchdog_stays_armed_while_a_child_holds_stderr(tmp_path: Path) -> None:
    # gemini itself exits almost at once, but leaves a backgrounded child that
    # still holds the inherited stderr fifo open. Draining stderr blocks until
    # every writer closes, so if the watchdog is cancelled the moment gemini's
    # own process exits (the pre-fix order), that wait has nothing left to
    # bound it and the wrapper never reaches the deadline check.
    env = _timeout_env(tmp_path)
    del env["GEMINI_SLEEP_SECONDS"]
    env["GEMINI_ORPHAN_SECONDS"] = "30"
    env["GEMINI_FALLBACK_TIMEOUT"] = "2"
    child_file = tmp_path / "gemini-child.pid"
    pid: int | None = None
    try:
        rc, elapsed = _run_to_deadline(tmp_path, env)
        pid = int(child_file.read_text().strip())
        wrapper_err = (tmp_path / "wrapper.err").read_text()
        assert rc == 4, (
            f"the watchdog must still fire and reap the orphaned child, got {rc}; "
            f"stderr: {wrapper_err}"
        )
        assert "produced no output within 2s" in wrapper_err, (
            f"the fallback-timeout message must match the PRD text; stderr: {wrapper_err}"
        )
        assert elapsed < 10.0, (
            f"wait on stderr must stay bounded by the watchdog: took {elapsed:.2f}s"
        )
        assert _gone_within(pid, 3), (
            "the orphaned child holding stderr must be killed with its group"
        )
    finally:
        if pid is not None and _alive(pid):
            os.kill(pid, signal.SIGKILL)
