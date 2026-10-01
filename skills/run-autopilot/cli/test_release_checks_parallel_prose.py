"""Pin the `[checks] parallel safety` block in dev/bin/release-checks.

Nothing else in the suite covers this block: test_wave_docs.py pins the
`waves` block's file set as a closed set and does not reach this one, so
deleting the block or dropping its `--with pytest-xdist` would otherwise
leave every existing test green (PRD 00233).
"""

from pathlib import Path

RELEASE_CHECKS = (
    Path(__file__).resolve().parents[3] / "dev" / "bin" / "release-checks"
).read_text()

_START = 'echo "[checks] parallel safety"'
_start_index = RELEASE_CHECKS.index(_START)
_end_index = RELEASE_CHECKS.index('\necho "[checks] ', _start_index + len(_START))
PARALLEL_SAFETY_BLOCK = RELEASE_CHECKS[_start_index:_end_index]


def test_parallel_safety_block_runs_test_parallel_safety():
    assert "test_parallel_safety.py" in PARALLEL_SAFETY_BLOCK, (
        "[checks] parallel safety block must run "
        "skills/run-autopilot/cli/test_parallel_safety.py"
    )


def test_parallel_safety_block_uses_pytest_xdist():
    assert "--with pytest-xdist" in PARALLEL_SAFETY_BLOCK, (
        "[checks] parallel safety block must pass --with pytest-xdist to uv run"
    )
