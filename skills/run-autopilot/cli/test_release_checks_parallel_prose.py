"""Pin the `[checks] parallel safety` block in dev/bin/release-checks.

Nothing else in the suite covers this block: test_wave_docs.py pins the
`waves` block's file set as a closed set and does not reach this one, so
deleting the block or dropping its `--with pytest-xdist` would otherwise
leave every existing test green (PRD 00233). This file runs from the
`[checks] effort lanes` block, so deleting the block it pins does not delete
the pin with it.
"""

from pathlib import Path

RELEASE_CHECKS = (
    Path(__file__).resolve().parents[3] / "dev" / "bin" / "release-checks"
).read_text()

_MARKER = 'echo "[checks] '
_NAME = "parallel safety"
_TEST_PATH = "skills/run-autopilot/cli/test_parallel_safety.py"


def _pytest_invocation() -> str:
    """The block's `-m pytest` command as one line, backslash continuations
    joined and comment lines dropped: an echo, a comment or a skip list that
    names the test path or the flag is not the command the gate runs."""
    lines = RELEASE_CHECKS.splitlines()
    heads = [i for i, line in enumerate(lines) if line.startswith(_MARKER)]
    start = next((i for i in heads if lines[i].startswith(f'{_MARKER}{_NAME}"')), None)
    assert start is not None, f"release-checks: no `[checks] {_NAME}` block"
    end = next((i for i in heads if i > start), len(lines))
    body = "\n".join(
        line for line in lines[start + 1 : end] if not line.lstrip().startswith("#")
    )
    commands = body.replace("\\\n", " ").splitlines()
    invocation = next((line for line in commands if "-m pytest" in line), None)
    assert invocation is not None, (
        f"release-checks: the `[checks] {_NAME}` block has no `-m pytest` command"
    )
    return invocation


def test_parallel_safety_block_runs_test_parallel_safety():
    assert _TEST_PATH in _pytest_invocation().split(), (
        f"[checks] {_NAME} block's pytest command must run {_TEST_PATH}"
    )


def test_parallel_safety_block_uses_pytest_xdist():
    assert "--with pytest-xdist" in _pytest_invocation(), (
        f"[checks] {_NAME} block's `uv run` must pass --with pytest-xdist"
    )
