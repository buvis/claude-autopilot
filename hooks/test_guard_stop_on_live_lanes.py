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
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

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


def _run_stdin(stdin: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    """`_run` with the stdin bytes chosen by the caller, always inside the loop."""
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": str(Path.home()),
        "_AUTOPILOT_LOOP": "4242",
    }
    return subprocess.run(
        [sys.executable, str(GUARD)],
        input=stdin,
        capture_output=True,
        text=True,
        env=env,
        cwd=str(cwd),
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


def test_all_lanes_without_output_files_never_ask_for_a_fileless_awaiter(
    tmp_path: Path,
) -> None:
    # Every live marker's second line is empty, so the awaiter has nothing to
    # await; `await_reviewer_outputs.py --budget 100` with zero files exits 2
    # and the instruction cannot be followed.
    repo = _repo(tmp_path)
    child = _live()
    try:
        _mark(repo, child.pid, "codex", "")
        result = _run(repo, loop=True)
    finally:
        _kill(child)
    assert result.returncode == 2
    err = result.stderr
    assert "autopilot: 1 CLI reviewer lane(s) still running:" in err
    assert f"codex (pid {child.pid}) -> (no -o file)" in err
    assert "--budget 100" not in err
    assert "await_reviewer_outputs.py" not in err
    # Dropping the awaiter must not drop the guidance with it: the session is
    # held open, so the reason still has to say what to wait for.
    kills = "Headless claude kills them when this turn ends."
    assert kills in err
    guidance = err.split(kills, 1)[1]
    assert str(child.pid) in guidance, guidance
    assert "Do not end the turn before then." in guidance
    assert _counter(repo).read_text().strip() == "1"


@pytest.mark.parametrize(
    "flavour",
    [
        "directory",
        pytest.param(
            "read-only file",
            marks=pytest.mark.skipif(
                os.geteuid() == 0, reason="mode bits do not bite as root"
            ),
        ),
    ],
)
def test_unwritable_block_counter_does_not_cancel_the_block(
    tmp_path: Path, flavour: str
) -> None:
    # Every write to `.lane-guard-blocks` raises OSError here, in two flavours:
    # the path is a directory (IsADirectoryError, and reading it fails too) or
    # a read-only file (PermissionError, reading it succeeds). Failing open
    # would end the turn with a live reviewer attached.
    repo = _repo(tmp_path)
    counter = _counter(repo)
    if flavour == "directory":
        counter.mkdir()
    else:
        counter.write_text("7\n")
        counter.chmod(0o444)
    codex_out = str(tmp_path / "review-codex.md")
    child = _live()
    try:
        _mark(repo, child.pid, "codex", codex_out)
        result = _run(repo, loop=True)
    finally:
        _kill(child)
        if flavour == "read-only file":
            counter.chmod(0o644)
    assert result.returncode == 2
    err = result.stderr
    assert "autopilot: 1 CLI reviewer lane(s) still running:" in err
    assert f"codex (pid {child.pid}) -> {codex_out}" in err
    assert f"{AWAITER} --budget 100 {codex_out} in the foreground" in err
    assert "Do not end the turn before then." in err
    if flavour == "directory":
        assert counter.is_dir()
    else:
        # Unchanged, so the run really did hit a failing write.
        assert counter.read_text().strip() == "7"


@pytest.mark.parametrize(
    ("flavour", "exc_name"),
    [
        pytest.param(
            "unreadable lanes dir",
            "PermissionError",
            marks=pytest.mark.skipif(
                os.geteuid() == 0, reason="mode bits do not bite as root"
            ),
        ),
        ("non-string cwd", "TypeError"),
    ],
)
def test_internal_failure_fails_open_but_says_so(
    tmp_path: Path, flavour: str, exc_name: str
) -> None:
    # Two genuine failures in different code paths: listing the lane markers
    # raises PermissionError out of `live_lanes` (the dir is mode 0o000 while
    # `lanes/` still stats as a directory), and a non-string payload `cwd`
    # raises TypeError out of `Path(...)` before the walk-up. A malformed JSON
    # payload is deliberately not used: `_common.read_input` returns `{}` for
    # it, which is the ordinary allow path, not a failure.
    repo = _repo(tmp_path)
    lanes = _lanes(repo)
    cwd: object = str(repo)
    if flavour == "unreadable lanes dir":
        lanes.chmod(0o000)
    else:
        cwd = 42
    stdin = json.dumps({"session_id": SESSION, "cwd": cwd, "hook_event_name": "Stop"})
    try:
        result = _run_stdin(stdin, repo)
    finally:
        lanes.chmod(0o755)
    assert result.returncode == 0
    marked = [line for line in result.stderr.splitlines() if "lane_guard" in line]
    assert marked, result.stderr
    assert any("internal error" in line.lower() for line in marked), marked
    # The failure has to be reported, not recited: only a real `except` knows
    # which exception it caught.
    assert any(exc_name in line for line in marked), marked
    assert "Do not end the turn before then." not in result.stderr


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


def _bullet(section: str, marker: str) -> str:
    """The list item starting with `marker`, through its continuation lines."""
    lines = section.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(marker))
    end = next(
        (
            i
            for i in range(start + 1, len(lines))
            if lines[i].startswith(("- **", "#")) or not lines[i].strip()
        ),
        len(lines),
    )
    return "\n".join(lines[start:end])


def _sentences_with(text: str, needle: str) -> list[str]:
    flat = " ".join(text.split())
    return [s for s in re.split(r"(?<=\.)\s+", flat) if needle in s]


def test_docs_name_the_guard() -> None:
    # read_text raises on a missing document: a failure, never a skip.
    review = (PACK / "skills/review-work-completion/SKILL.md").read_text()
    fast = (PACK / "skills/fast-track/SKILL.md").read_text()
    autopilot = (PACK / "skills/run-autopilot/SKILL.md").read_text()
    guard = "guard_stop_on_live_lanes.py"
    anchor = "The Watcher is scaffolding, not a reviewer"
    paragraphs = [p for p in review.split("\n\n") if anchor in p]
    assert len(paragraphs) == 1, "review-work-completion lost its Watcher paragraph"
    assert any(
        "holds the session open" in s and "PRD 00213" in s
        for s in _sentences_with(paragraphs[0], guard)
    ), (
        "review-work-completion/SKILL.md step 5 Watcher paragraph no longer "
        f"says {guard} (PRD 00213) holds the session open"
    )
    preconditions = re.sub(
        r"<!--.*?-->", "", _section(fast, "## Preconditions", ("## ",)), flags=re.S
    )
    loop = _bullet(preconditions, "- **Loop session.**")
    assert any("holds the session open" in s for s in _sentences_with(loop, guard)), (
        "fast-track/SKILL.md ## Preconditions **Loop session.** bullet no "
        f"longer says {guard} holds the session open"
    )
    retention = _section(autopilot, "### Retention", ("## ", "### "))
    lanes = "dev/local/autopilot/lanes/"
    assert lanes in _bullet(retention, "- **Disposable**"), (
        f"run-autopilot/SKILL.md ### Retention **Disposable** no longer lists {lanes}"
    )
    assert lanes not in _bullet(retention, "- **Durable**"), (
        f"run-autopilot/SKILL.md ### Retention lists {lanes} as **Durable**"
    )
