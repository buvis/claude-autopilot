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
    ],
)
def test_auth_failure_exits_4_without_fallback(tmp_path: Path, auth_error: str) -> None:
    env = _stubs(tmp_path)
    env.update(COPILOT_EXIT_CODE="1", COPILOT_STDERR=auth_error)
    result = _run(tmp_path, env)
    assert Path(env["COPILOT_ARGV_FILE"]).is_file(), "copilot must be tried first"
    assert result.returncode == 4, f"auth failure must be permanent (exit 4); stderr: {result.stderr}"
    assert auth_error in result.stderr, "the auth reason must reach the caller"
    gemini_argv = Path(env["GEMINI_ARGV_FILE"])
    assert not gemini_argv.exists() or gemini_argv.read_text() == "", (
        f"native gemini must not be tried on an auth failure; argv: {gemini_argv.read_text()!r}"
    )
    assert "stub-gemini-ran" not in result.stdout


def test_tier_rejection_still_falls_back(tmp_path: Path) -> None:
    env = _stubs(tmp_path)
    env.update(COPILOT_EXIT_CODE="1", COPILOT_STDERR=TIER_REJECTION, GEMINI_EXIT_CODE="7")
    result = _run(tmp_path, env)
    gemini_argv = Path(env["GEMINI_ARGV_FILE"])
    assert gemini_argv.is_file(), f"tier rejection must fall back to native gemini; stderr: {result.stderr}"
    argv = gemini_argv.read_text().splitlines()
    assert "-p" in argv and argv[argv.index("-p") + 1] == PROMPT, f"fallback argv: {argv}"
    assert "stub-gemini-ran" in result.stdout
    assert result.returncode == 7, f"the native stub's exit code must propagate; stderr: {result.stderr}"


def test_fallback_with_no_output_exits_4_at_the_deadline(tmp_path: Path) -> None:
    env = _timeout_env(tmp_path)
    pidfiles = [tmp_path / "gemini.pid", tmp_path / "gemini-child.pid"]
    try:
        rc, elapsed = _run_to_deadline(tmp_path, env)
        assert Path(env["GEMINI_ARGV_FILE"]).is_file(), "the fallback must actually start"
        assert elapsed >= 2.0, f"returned before the 2s deadline: {elapsed:.2f}s"
        assert elapsed < 5.0, f"GEMINI_FALLBACK_TIMEOUT=2 not honored: took {elapsed:.2f}s"
        assert rc == 4, f"a timed-out fallback must exit 4, got {rc}; stderr: {(tmp_path / 'wrapper.err').read_text()}"
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
        pids = [int(leader_file.read_text().strip()), int(child_file.read_text().strip())]
        assert rc == 4, f"got {rc}; stderr: {(tmp_path / 'wrapper.err').read_text()}"
        assert _gone_within(pids[0], 3), "the native gemini process itself must be killed"
        assert _gone_within(pids[1], 3), "the gemini process's backgrounded child must be killed with its group"
        assert decoy.poll() is None, "a process outside the fallback's group must survive"
    finally:
        decoy.kill()
        decoy.wait()
        for pid in pids:
            if _alive(pid):
                os.kill(pid, signal.SIGKILL)
