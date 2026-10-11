"""PRD 00211: the two hooks around the session's `leave` row.

`note_session_leave.py` (PostToolUse, Bash) records which loop session wrote
its leave row; `guard_skill_after_leave.py` (PreToolUse, Skill) then denies an
`autopilot:*` skill call from that same session. Both run here as
subprocesses with a stdin payload and a `tmp_path` repo, exactly as the
harness invokes them.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HOOKS = Path(__file__).resolve().parent
NOTE = HOOKS / "note_session_leave.py"
GUARD = HOOKS / "guard_skill_after_leave.py"
SESSION = "11111111-2222-3333-4444-555555555555"
LEAVE_CMD = (
    "python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/record_dispatch.py handoff "
    "--site build --edge leave --phase review --prd 00052-x-v1.md"
)


def _repo(tmp_path: Path) -> Path:
    (tmp_path / "docs" / "dev" / "project-management" / "autopilot").mkdir(parents=True)
    return tmp_path


def _marker(repo: Path) -> Path:
    return repo / "docs" / "dev" / "project-management" / "autopilot" / ".session-left"


def _run(script: Path, payload: dict, *, loop: bool) -> subprocess.CompletedProcess[str]:
    env = {"PATH": "/usr/bin:/bin", "HOME": str(Path.home())}
    if loop:
        env["_AUTOPILOT_LOOP"] = "4242"
    return subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        cwd=payload.get("cwd"),
    )


def _bash_payload(repo: Path, command: str, response: dict | None = None) -> dict:
    return {
        "session_id": SESSION,
        "cwd": str(repo),
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "tool_response": response or {"stdout": "", "stderr": "", "interrupted": False},
    }


def _skill_payload(repo: Path, skill: str, session: str = SESSION) -> dict:
    return {
        "session_id": session,
        "cwd": str(repo),
        "tool_name": "Skill",
        "tool_input": {"skill": skill},
    }


# ── note_session_leave.py ────────────────────────────────────────────────────


def test_leave_row_marks_the_session(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    before = datetime.now(timezone.utc)
    result = _run(NOTE, _bash_payload(repo, LEAVE_CMD), loop=True)
    assert result.returncode == 0
    record = json.loads(_marker(repo).read_text())
    assert record["session"] == SESSION
    assert record["at"].endswith("Z") and "T" in record["at"]
    # The time of this hand-off, not a constant: a frozen stamp is no record.
    at = datetime.fromisoformat(record["at"].replace("Z", "+00:00"))
    assert before - timedelta(seconds=5) <= at <= datetime.now(timezone.utc) + timedelta(seconds=5)


def test_leave_row_outside_loop_writes_nothing(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    result = _run(NOTE, _bash_payload(repo, LEAVE_CMD), loop=False)
    assert result.returncode == 0
    assert not _marker(repo).exists()


def test_failed_leave_row_writes_nothing(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    failed = {"stdout": "", "stderr": "boom", "interrupted": False, "is_error": True}
    result = _run(NOTE, _bash_payload(repo, LEAVE_CMD, failed), loop=True)
    assert result.returncode == 0
    assert not _marker(repo).exists()


def test_other_bash_commands_write_nothing(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    resume = LEAVE_CMD.replace("--edge leave", "--edge resume")
    # Merely naming the flag is not handing off: only the dispatch call ends a session.
    mention = 'rg -n -- "--edge leave" docs/'
    for command in (resume, mention):
        result = _run(NOTE, _bash_payload(repo, command), loop=True)
        assert result.returncode == 0, command
        assert not _marker(repo).exists(), command


def test_leave_row_without_an_autopilot_dir_writes_nothing(tmp_path: Path) -> None:
    # No docs/dev/project-management/autopilot above cwd: the hook neither writes nor creates it.
    result = _run(NOTE, _bash_payload(tmp_path, LEAVE_CMD), loop=True)
    assert result.returncode == 0
    assert not (tmp_path / "dev").exists()
    assert list(tmp_path.rglob(".session-left")) == []
    # The dir is looked for above cwd too: from a nested cwd inside a repo the
    # marker lands in the repo-root autopilot dir.
    repo = _repo(tmp_path / "repo")
    nested = repo / "src" / "deep"
    nested.mkdir(parents=True)
    assert _run(NOTE, _bash_payload(nested, LEAVE_CMD), loop=True).returncode == 0
    assert json.loads(_marker(repo).read_text())["session"] == SESSION


def test_leave_row_with_a_replaced_byte_session_writes_nothing(tmp_path: Path) -> None:
    # A session id carrying U+FFFD counts as missing: two ids differing only in
    # an invalid byte must never collapse onto one marker.
    repo = _repo(tmp_path)
    for session in ("�", "a�b", SESSION[:-1] + "�", "s1�"):
        payload = _bash_payload(repo, LEAVE_CMD) | {"session_id": session}
        result = _run(NOTE, payload, loop=True)
        assert result.returncode == 0, session
        assert not _marker(repo).exists(), session
        # Not written beside the marker either: no record of this id anywhere.
        assert list(_marker(repo).parent.iterdir()) == [], session
    # A clean id still marks the session, whatever its shape or length: the
    # invalid byte is the gate, not UUID-ness.
    clean = _bash_payload(repo, LEAVE_CMD) | {"session_id": "next-session"}
    assert _run(NOTE, clean, loop=True).returncode == 0
    assert json.loads(_marker(repo).read_text())["session"] == "next-session"


# ── guard_skill_after_leave.py ───────────────────────────────────────────────


def _leave(repo: Path, session: str = SESSION) -> None:
    _marker(repo).write_text(json.dumps({"session": session, "at": "2026-09-20T20:33:45Z"}))


def test_autopilot_skill_after_leave_is_denied_with_the_reason(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _leave(repo)
    result = _run(GUARD, _skill_payload(repo, "autopilot:run-autopilot"), loop=True)
    assert result.returncode == 2
    assert "autopilot:run-autopilot" in result.stderr
    assert "2026-09-20T20:33:45Z" in result.stderr
    assert "End the turn now" in result.stderr


def test_catchup_after_leave_is_denied_too(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _leave(repo)
    result = _run(GUARD, _skill_payload(repo, "git-ferry:catchup"), loop=True)
    assert result.returncode == 2
    # A missing script would also be non-zero: the reason text is the proof.
    assert "do not invoke git-ferry:catchup" in result.stderr


def test_guard_without_an_autopilot_dir_passes(tmp_path: Path) -> None:
    # No docs/dev/project-management/autopilot above cwd: nothing to consult, never a denial.
    result = _run(GUARD, _skill_payload(tmp_path, "autopilot:run-autopilot"), loop=True)
    assert result.returncode == 0
    assert result.stderr == ""
    # The dir is looked for above cwd too: a repo-root marker still denies a
    # call made from a nested cwd.
    repo = _repo(tmp_path / "repo")
    _leave(repo)
    nested = repo / "src" / "deep"
    nested.mkdir(parents=True)
    denied = _run(GUARD, _skill_payload(nested, "autopilot:run-autopilot"), loop=True)
    assert denied.returncode == 2


def test_other_session_marker_never_denies(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _leave(repo, session="99999999-0000-0000-0000-000000000000")
    result = _run(GUARD, _skill_payload(repo, "autopilot:run-autopilot"), loop=True)
    assert result.returncode == 0
    assert result.stderr == ""


def test_non_autopilot_skill_passes(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _leave(repo)
    # Near misses included: only the autopilot plugin and git-ferry:catchup are guarded.
    for skill in (
        "ponytail:ponytail",
        "other:autopilot-notes",
        "foo:catchup",
        "notautopilot:run",
    ):
        result = _run(GUARD, _skill_payload(repo, skill), loop=True)
        assert result.returncode == 0, skill
        assert result.stderr == "", skill


def test_malformed_marker_passes(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    for text in ("not json", "[1, 2]"):
        _marker(repo).write_text(text)
        result = _run(GUARD, _skill_payload(repo, "autopilot:work"), loop=True)
        assert result.returncode == 0, text
        assert result.stderr == "", text
    # A marker naming this session but carrying no `at` still denies, with
    # fallback wording where the timestamp would go.
    _marker(repo).write_text(json.dumps({"session": SESSION}))
    denied = _run(GUARD, _skill_payload(repo, "autopilot:work"), loop=True)
    assert denied.returncode == 2
    assert "an earlier call" in denied.stderr


def test_guard_outside_loop_passes(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _leave(repo)
    result = _run(GUARD, _skill_payload(repo, "autopilot:run-autopilot"), loop=False)
    assert result.returncode == 0


def test_no_marker_passes(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    result = _run(GUARD, _skill_payload(repo, "autopilot:run-autopilot"), loop=True)
    assert result.returncode == 0


def test_skill_call_with_a_replaced_byte_session_passes_despite_a_matching_marker(
    tmp_path: Path,
) -> None:
    # The marker names the very same U+FFFD-bearing string, yet a session id
    # holding U+FFFD identifies nobody: the guard must not deny on it.
    repo = _repo(tmp_path)
    for session in ("�", "a�b", SESSION[:-1] + "�", "s1�"):
        _leave(repo, session=session)
        payload = _skill_payload(repo, "autopilot:run-autopilot", session=session)
        result = _run(GUARD, payload, loop=True)
        assert result.returncode == 0, session
        assert result.stderr == "", session
        # No deny envelope on stdout either: the call really goes through.
        assert result.stdout == "", session
    # A clean id still denies on its own marker, however short: the allow comes
    # from the invalid byte, not from the id's length.
    _leave(repo, session="s1")
    denied = _run(GUARD, _skill_payload(repo, "autopilot:run-autopilot", session="s1"), loop=True)
    assert denied.returncode == 2


def test_the_pair_end_to_end(tmp_path: Path) -> None:
    # The measured failure: leave row written, then run-autopilot re-invoked.
    repo = _repo(tmp_path)
    assert _run(NOTE, _bash_payload(repo, LEAVE_CMD), loop=True).returncode == 0
    denied = _run(GUARD, _skill_payload(repo, "autopilot:run-autopilot"), loop=True)
    assert denied.returncode == 2
    # The next session (a new id) is free to start its Phase 0.
    fresh = _skill_payload(repo, "autopilot:run-autopilot", session="next-session")
    assert _run(GUARD, fresh, loop=True).returncode == 0
