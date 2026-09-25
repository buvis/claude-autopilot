"""The Stop hook that holds a loop session open while a CLI reviewer lane runs.

`guard_stop_on_live_lanes.py` reads the lane markers the codex and gemini
wrappers leave under `dev/local/autopilot/lanes/<pid>` and refuses the turn's
end (exit 2, reason on stderr) while one of those pids is alive. It runs here
as a subprocess with a stdin payload and a `tmp_path` repo, exactly as the
harness invokes it. A live lane is a `sleep 60` child this test starts.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

HOOKS = Path(__file__).resolve().parent
PACK = HOOKS.parent
GUARD = HOOKS / "guard_stop_on_live_lanes.py"
SESSION = "11111111-2222-3333-4444-555555555555"
AWAITER = (
    f"python3 {PACK}/skills/review-work-completion/scripts/await_reviewer_outputs.py"
)


def _repo(tmp_path: Path) -> Path:
    (tmp_path / "dev" / "local" / "autopilot").mkdir(parents=True)
    return tmp_path


def _lanes(repo: Path) -> Path:
    lanes = repo / "dev" / "local" / "autopilot" / "lanes"
    lanes.mkdir(parents=True, exist_ok=True)
    return lanes


def _counter(repo: Path) -> Path:
    return repo / "dev" / "local" / "autopilot" / ".lane-guard-blocks"


def _mark(repo: Path, pid: int, kind: str, output: str) -> Path:
    marker = _lanes(repo) / str(pid)
    marker.write_text(f"{kind}\n{output}\n")
    return marker


def _live() -> subprocess.Popen[bytes]:
    return subprocess.Popen(["sleep", "60"])


def _dead_pid() -> int:
    child = subprocess.Popen(["sleep", "0"])
    child.wait()
    return child.pid


def _kill(*children: subprocess.Popen[bytes]) -> None:
    for child in children:
        child.kill()
        child.wait()


def _run(
    repo: Path, *, loop: bool, process_cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    payload = {"session_id": SESSION, "cwd": str(repo), "hook_event_name": "Stop"}
    env = {"PATH": "/usr/bin:/bin", "HOME": str(Path.home())}
    if loop:
        env["_AUTOPILOT_LOOP"] = "4242"
    return subprocess.run(
        [sys.executable, str(GUARD)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        cwd=str(process_cwd) if process_cwd is not None else payload["cwd"],
    )


def test_live_lanes_block_the_stop_with_the_files_to_await(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    codex_out = str(tmp_path / "review-codex.md")
    gemini_out = str(tmp_path / "review-gemini.md")
    codex, gemini = _live(), _live()
    try:
        _mark(repo, codex.pid, "codex", codex_out)
        _mark(repo, gemini.pid, "gemini", gemini_out)
        result = _run(repo, loop=True)
    finally:
        _kill(codex, gemini)
    assert result.returncode == 2
    err = result.stderr
    assert "autopilot: 2 CLI reviewer lane(s) still running:" in err
    assert f"codex (pid {codex.pid}) -> {codex_out}" in err
    assert f"gemini (pid {gemini.pid}) -> {gemini_out}" in err
    assert "Headless claude kills them when this turn ends." in err
    assert f"{AWAITER} --budget 100 " in err
    awaited = err.split("--budget 100 ", 1)[1].split(" in the foreground", 1)[0]
    assert sorted(awaited.split(" ")) == sorted([codex_out, gemini_out])
    assert "while its last line is WAITING run it again" in err
    assert "Do not end the turn before then." in err
    assert _counter(repo).read_text().strip() == "1"


def test_dead_lane_marker_is_ignored_and_removed(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    marker = _mark(repo, _dead_pid(), "codex", str(tmp_path / "review-codex.md"))
    result = _run(repo, loop=True)
    assert result.returncode == 0
    assert "still running" not in result.stderr
    assert not marker.exists()
    assert not _counter(repo).exists()


def test_lane_past_the_age_ceiling_does_not_hold_the_session(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    child = _live()
    try:
        marker = _mark(repo, child.pid, "gemini", str(tmp_path / "review-gemini.md"))
        aged = time.time() - 3700
        os.utime(marker, (aged, aged))
        result = _run(repo, loop=True)
    finally:
        _kill(child)
    assert result.returncode == 0
    # 3700 s is 61 whole minutes.
    assert (
        f"autopilot: lane gemini (pid {child.pid}) has run 61 min, "
        "past the 60 min ceiling; not holding the session for it"
    ) in result.stderr.splitlines()
    assert "still running" not in result.stderr


def test_lane_under_the_age_ceiling_still_holds_the_session(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    child = _live()
    try:
        marker = _mark(repo, child.pid, "gemini", str(tmp_path / "review-gemini.md"))
        aged = time.time() - 3500
        os.utime(marker, (aged, aged))
        result = _run(repo, loop=True)
    finally:
        _kill(child)
    assert result.returncode == 2
    assert f"gemini (pid {child.pid}) -> " in result.stderr
    assert "Do not end the turn before then." in result.stderr
    assert "past the 60 min ceiling" not in result.stderr


def test_cwd_comes_from_the_payload_and_walks_up(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    nested = repo / "a" / "b"
    nested.mkdir(parents=True)
    codex_out = str(tmp_path / "review-codex.md")
    child = _live()
    try:
        _mark(repo, child.pid, "codex", codex_out)
        # The process cwd has no dev/local/autopilot at or above it; only the
        # payload's cwd (a subdirectory of the repo) leads to the lanes.
        result = _run(nested, loop=True, process_cwd=tmp_path.parent)
    finally:
        _kill(child)
    assert result.returncode == 2
    assert f"codex (pid {child.pid}) -> {codex_out}" in result.stderr
    assert "Do not end the turn before then." in result.stderr
    assert _counter(repo).read_text().strip() == "1"


def test_outside_the_loop_never_blocks(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    child = _live()
    try:
        _mark(repo, child.pid, "codex", str(tmp_path / "review-codex.md"))
        result = _run(repo, loop=False)
    finally:
        _kill(child)
    assert result.returncode == 0
    assert result.stderr == ""
    assert not _counter(repo).exists()


def test_no_autopilot_dir_passes(tmp_path: Path) -> None:
    result = _run(tmp_path, loop=True)
    assert result.returncode == 0
    assert result.stderr == ""
    assert not (tmp_path / "dev").exists()


def test_no_lanes_dir_passes(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    result = _run(repo, loop=True)
    assert result.returncode == 0
    assert "still running" not in result.stderr
    assert not _counter(repo).exists()


def test_non_pid_marker_names_are_ignored(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    readme = _lanes(repo) / "README"
    readme.write_text("codex\n/nowhere/out.md\n")
    child = _live()
    try:
        _mark(repo, child.pid, "codex", str(tmp_path / "review-codex.md"))
        result = _run(repo, loop=True)
    finally:
        _kill(child)
    assert result.returncode == 2
    # Only the pid-named marker counts; README is neither a lane nor removed.
    assert "autopilot: 1 CLI reviewer lane(s) still running:" in result.stderr
    assert "/nowhere/out.md" not in result.stderr
    assert readme.read_text() == "codex\n/nowhere/out.md\n"


def test_lane_without_an_output_file_is_named_but_not_awaited(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    gemini_out = str(tmp_path / "review-gemini.md")
    codex, gemini = _live(), _live()
    try:
        _mark(repo, codex.pid, "codex", "")
        _mark(repo, gemini.pid, "gemini", gemini_out)
        result = _run(repo, loop=True)
    finally:
        _kill(codex, gemini)
    assert result.returncode == 2
    err = result.stderr
    assert "autopilot: 2 CLI reviewer lane(s) still running:" in err
    assert f"codex (pid {codex.pid}) -> (no -o file)" in err
    assert f"{AWAITER} --budget 100 {gemini_out} in the foreground" in err
    assert "Do not end the turn before then." in err


def test_block_cap_gives_up_loud(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _counter(repo).write_text("40")
    child = _live()
    try:
        _mark(repo, child.pid, "codex", str(tmp_path / "review-codex.md"))
        result = _run(repo, loop=True)
    finally:
        _kill(child)
    assert result.returncode == 0
    assert (
        "giving up after 40 blocked exits to preserve session liveness" in result.stderr
    )
    assert "Do not end the turn before then." not in result.stderr
    assert not _counter(repo).exists()


def test_counter_beyond_the_cap_also_gives_up(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _counter(repo).write_text("100")
    child = _live()
    try:
        _mark(repo, child.pid, "codex", str(tmp_path / "review-codex.md"))
        result = _run(repo, loop=True)
    finally:
        _kill(child)
    assert result.returncode == 0
    assert (
        "giving up after 40 blocked exits to preserve session liveness" in result.stderr
    )
    assert "Do not end the turn before then." not in result.stderr
    assert not _counter(repo).exists()


def test_block_at_the_cap_still_denies(tmp_path: Path) -> None:
    # 39 -> 40 does not exceed BLOCK_CAP: the stop is still refused.
    repo = _repo(tmp_path)
    _counter(repo).write_text("39")
    child = _live()
    try:
        _mark(repo, child.pid, "codex", str(tmp_path / "review-codex.md"))
        result = _run(repo, loop=True)
    finally:
        _kill(child)
    assert result.returncode == 2
    assert "Do not end the turn before then." in result.stderr
    assert "giving up" not in result.stderr
    assert _counter(repo).read_text().strip() == "40"


def test_blocks_count_up_and_reset_when_lanes_finish(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    child = _live()
    try:
        marker = _mark(repo, child.pid, "codex", str(tmp_path / "review-codex.md"))
        first = _run(repo, loop=True)
        assert first.returncode == 2
        assert "Do not end the turn before then." in first.stderr
        assert _counter(repo).read_text().strip() == "1"
        second = _run(repo, loop=True)
        assert second.returncode == 2
        assert "Do not end the turn before then." in second.stderr
        assert _counter(repo).read_text().strip() == "2"
    finally:
        _kill(child)
    done = _run(repo, loop=True)
    assert done.returncode == 0
    assert "still running" not in done.stderr
    assert not _counter(repo).exists()
    assert not marker.exists()


def _section(text: str, heading: str, stops: tuple[str, ...]) -> str:
    lines = text.splitlines()
    start = lines.index(heading)
    end = next(
        (i for i in range(start + 1, len(lines)) if lines[i].startswith(stops)),
        len(lines),
    )
    return "\n".join(lines[start:end])


def test_docs_name_the_guard() -> None:
    # read_text raises on a missing document: a failure, never a skip.
    review = (PACK / "skills/review-work-completion/SKILL.md").read_text()
    fast = (PACK / "skills/fast-track/SKILL.md").read_text()
    autopilot = (PACK / "skills/run-autopilot/SKILL.md").read_text()
    anchor = "The Watcher is scaffolding, not a reviewer"
    paragraphs = [p for p in review.split("\n\n") if anchor in p]
    assert len(paragraphs) == 1, "review-work-completion lost its Watcher paragraph"
    assert "guard_stop_on_live_lanes.py" in paragraphs[0], (
        "review-work-completion/SKILL.md step 5 Watcher paragraph "
        "no longer names guard_stop_on_live_lanes.py"
    )
    preconditions = _section(fast, "## Preconditions", ("## ",))
    assert "guard_stop_on_live_lanes.py" in preconditions, (
        "fast-track/SKILL.md ## Preconditions no longer names "
        "guard_stop_on_live_lanes.py"
    )
    retention = _section(autopilot, "### Retention", ("## ", "### "))
    assert "dev/local/autopilot/lanes/" in retention, (
        "run-autopilot/SKILL.md ### Retention no longer lists "
        "dev/local/autopilot/lanes/"
    )
