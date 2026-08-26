#!/usr/bin/env python3
"""eligibility.py - the PRD `eligibility:` gate evaluated at pick time (PRD 00137).

A PRD may declare one shell command in its frontmatter:

    eligibility: "test -f dev/local/reviews/00110-evidence.md"

`autopilot select` runs it before choosing that PRD. Exit 0 = eligible.
Anything else - non-zero, unknown binary, timeout, an unusable cwd - is UNMET,
and an unmet PRD is SKIPPED: it stays in `backlog/`, gets no session, and is
never parked to `hold/`. The gate fails toward not-running the PRD, so a broken
check costs a skip, never a crashed drain.

    command_for(prd_text)         -> the command, or None when absent
    evaluate(command, cwd)        -> (exit_code, note)

Two conventions the code cannot enforce, documented at the contract instead:

- **Read-only commands only.** These strings are PRD-authored and run
  unattended. They run through `subprocess` inside this process, so warden
  never sees them - nothing gates what they do.
- **30 seconds.** The default timeout. A check that cannot answer in 30s is
  the wrong shape for a gate that runs on every pick.

`cwd` is the project root (the directory holding `dev/local/`), so a check can
name repo-relative paths the way the PRD prose does.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from cli import frontmatter

_KEY = "eligibility"
_QUOTES = "\"'"


def _unquote(value: str) -> str:
    """Strip ONE layer of matching outer quotes. `"test $(ls 'a b')"` keeps the
    inner quotes the shell still needs; an unmatched quote is left alone rather
    than guessed at."""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in _QUOTES:
        return value[1:-1]
    return value


def command_for(prd_text: str) -> str | None:
    """The PRD's eligibility command, or None when it declares none.

    None is the common answer and means eligible: `frontmatter.py` ignores this
    key entirely (it is not a Phase-0 state field), so a PRD written before the
    gate existed reads exactly as it always did.
    """
    body = frontmatter._block(prd_text)
    if body is None:
        return None
    return _unquote(frontmatter._pairs(body).get(_KEY, "").strip()) or None


def evaluate(command: str, cwd: Path, timeout: float = 30.0) -> tuple[int, str]:
    """Run `command` from `cwd` and return (exit_code, note).

    `note` is empty for a command that ran, whatever it exited with; it names
    the failure mode only when the command never got to answer. Those cases
    exit -1, which no shell produces, so a caller can tell "the check said no"
    from "the check could not be run" without parsing prose.

    Output is captured and dropped: `select` prints machine-read JSON on
    stdout, and a chatty check must not land in the middle of it.
    """
    # shell=True IS the contract: the PRD declares one shell command and the
    # gate reports its exit code. The command comes from a PRD in this repo's
    # own dev/local, authored by the operator, so there is no untrusted input
    # to escape here - splitting it would only break the pipes and $(...) the
    # checks are written in. The real mitigations are the read-only convention
    # above, the timeout, and failure meaning skip.
    try:
        completed = subprocess.run(
            command,
            shell=True,
            cwd=str(cwd),
            timeout=timeout,
            capture_output=True,
            text=True,
        )
    except subprocess.TimeoutExpired:
        return -1, "timeout"
    except OSError as err:
        return -1, f"error: {err}"
    return completed.returncode, ""
