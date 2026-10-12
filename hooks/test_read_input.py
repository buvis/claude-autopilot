"""Pin the stdin hardening of every hook that reads a payload from stdin.

`_common.read_input` reads `sys.stdin.buffer` and decodes with
`errors="replace"`, and returns `{}` on a parse failure or a `RecursionError`.
These cases drive the real hooks as subprocesses - the only place the
`.buffer` path exists, since `capture_main` swaps in a `StringIO` - so an
invalid byte, a deeply nested payload, empty stdin and a payload already
carrying U+FFFD all have to leave the hook non-fatal.

`PYTHONIOENCODING=utf-8:strict` is set on purpose: a hook that echoes a
replaced byte back out must not die encoding its own message.

The second test pins the other half of the contract - lossy decoding is not a
bypass. A payload the delegation guard denies still gets denied when an
invalid byte sits inside one of its strings.

The hooks run as subprocesses with a stdin payload - the same harness shape as
`test_guard_phase_delegation_replay.py`, but with stdin passed as BYTES,
because one case is not expressible as a str.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parent

# Every hook in this directory that reads a payload from stdin.
STDIN_HOOKS = (
    "enforce_prd_location.py",
    "guard_push_on_critical.py",
    "guard_skill_after_leave.py",
    "guard_phase_delegation.py",
    "note_session_leave.py",
    "guard_stop_on_live_lanes.py",
)

REPLACEMENT = "�"

# A valid payload whose string values already hold U+FFFD: the shape a hook
# sees once `read_input` has replaced an invalid byte. `tool_name` and the
# guarded skill are left intact so the hooks actually engage instead of
# short-circuiting on an unrecognised tool.
REPLACED_PAYLOAD = {
    "session_id": f"1111{REPLACEMENT}111-2222-3333-4444-555555555555",
    "tool_name": "Skill",
    "tool_input": {
        "skill": "autopilot:run-autopilot",
        "description": f"resume the {REPLACEMENT} hand-off",
    },
}

BAD_INPUTS = {
    "invalid-utf8": b"\xff\xfe\x80",
    "deep-nesting": b"[" * 100000 + b"]" * 100000,
    "empty": b"",
    "replaced-bytes": json.dumps(REPLACED_PAYLOAD).encode("utf-8"),
}


def _run(hook: str, stdin: bytes, cwd: Path) -> subprocess.CompletedProcess[bytes]:
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": str(Path.home()),
        "_AUTOPILOT_LOOP": "1",
        "PYTHONIOENCODING": "utf-8:strict",
    }
    return subprocess.run(
        [sys.executable, str(HOOKS / hook)],
        input=stdin,
        capture_output=True,
        env=env,
        cwd=str(cwd),
    )


def _output(result: subprocess.CompletedProcess[bytes]) -> str:
    return (result.stdout + result.stderr).decode("utf-8", errors="replace")


@pytest.mark.parametrize("hook", STDIN_HOOKS)
@pytest.mark.parametrize("case", sorted(BAD_INPUTS))
def test_every_stdin_hook_survives_bad_input(
    hook: str,
    case: str,
    tmp_path: Path,
) -> None:
    # cwd is a tmp_path so a hook that walks up for the autopilot directory or
    # writes a marker cannot reach the real repo.
    result = _run(hook, BAD_INPUTS[case], tmp_path)
    output = _output(result)
    assert result.returncode == 0, output
    # Both halves matter: handler isolation can swallow a crash and still exit
    # 0, so exit 0 alone would not catch a hook that died on the payload.
    assert "Traceback" not in output, output


def test_replaced_bytes_inside_a_string_are_still_checked(tmp_path: Path) -> None:
    # The denied payload shape comes from test_guard_phase_delegation_dispatch.py.
    payload = {
        "session_id": "11111111-2222-3333-4444-555555555555",
        "tool_name": "Agent",
        "tool_input": {
            "prompt": "Run the work phase for PRD 00300.",
            "subagent_type": "general-purpose",
        },
    }
    # The invalid byte lands inside the leading "Run", away from both the
    # phrase the guard matches on ("work phase") and the anchor that follows
    # it ("for PRD"), so the JSON stays structurally valid and the match stays
    # reachable. Lossy decoding must not buy a bypass.
    spliced = json.dumps(payload).encode("utf-8").replace(b"Run", b"R\xffun")
    assert b"\xff" in spliced

    result = _run("guard_phase_delegation.py", spliced, tmp_path)
    assert result.returncode == 2, _output(result)
