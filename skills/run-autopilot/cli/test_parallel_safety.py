"""Proves the wave fixtures are safe under pytest-xdist (PRD 00233).

`test_the_wave_pair_passes_under_two_workers` is the fail-first proof: it
runs `test_hammer_a`/`test_hammer_b` under `-n 2` in a subprocess and
asserts both pass. Both hammer tests call the REAL `_repo()` fixture
(not a copy), so this is a standing regression guard: if `_repo()`'s
`commit.gpgsign false` line is ever reverted, this test goes red again.
"""

from __future__ import annotations

import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from cli.test_wave_launch import _repo

_HAMMER_THREADS = 12


def _hammer(tmp_path: Path) -> None:
    with ThreadPoolExecutor(max_workers=_HAMMER_THREADS) as pool:
        list(pool.map(lambda i: _repo(tmp_path / f"case-{i}", {}), range(_HAMMER_THREADS)))


def test_hammer_a(tmp_path: Path) -> None:
    _hammer(tmp_path)


def test_hammer_b(tmp_path: Path) -> None:
    _hammer(tmp_path)


def test_the_wave_pair_passes_under_two_workers() -> None:
    """Fail-first proof (PRD 00233 Phase 0): the hammer pair above, run
    under 2 real pytest-xdist workers in a subprocess, must both pass."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys, pytest; sys.exit(pytest.main(sys.argv[1:]))",
            "-q",
            "-n",
            "2",
            f"{__file__}::test_hammer_a",
            f"{__file__}::test_hammer_b",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, (
        f"wave hammer pair failed under -n 2:\n{result.stdout}\n{result.stderr}"
    )
