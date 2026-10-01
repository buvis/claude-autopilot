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

import pytest

from cli.test_wave_launch import _git, _repo

_HAMMER_THREADS = 12


def _assert_gpgsign_disabled(repo: Path) -> None:
    assert _git(repo, "config", "--local", "commit.gpgsign").stdout.strip() == "false"


def _hammer(tmp_path: Path) -> list[Path]:
    with ThreadPoolExecutor(max_workers=_HAMMER_THREADS) as pool:
        return list(
            pool.map(lambda i: _repo(tmp_path / f"case-{i}", {})[0], range(_HAMMER_THREADS))
        )


def test_hammer_a(tmp_path: Path) -> None:
    for repo in _hammer(tmp_path):
        _assert_gpgsign_disabled(repo)


def test_hammer_b(tmp_path: Path) -> None:
    for repo in _hammer(tmp_path):
        _assert_gpgsign_disabled(repo)


def test_the_wave_pair_passes_under_two_workers() -> None:
    """Fail-first proof (PRD 00233 Phase 0): the hammer pair above, run
    under 2 real pytest-xdist workers in a subprocess, must both pass."""
    pytest.importorskip(
        "xdist", reason="gated by [checks] parallel safety, which installs pytest-xdist"
    )
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


def test_repo_disables_signing_regardless_of_host_gpg_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Deterministic regression guard (PRD 00233): pins the `_repo()` fix
    without depending on the host's own global git config. With this
    global config active, the pre-fix `_repo()` exits 128 ("gpg failed to
    sign the data"); the fixed `_repo()` returns normally because it
    disables `commit.gpgsign` locally."""
    global_config = tmp_path / "gitconfig-global"
    global_config.write_text(
        "[commit]\n\tgpgsign = true\n[gpg]\n\tprogram = /usr/bin/false\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(global_config))
    repo, _ = _repo(tmp_path / "case", {})
    _assert_gpgsign_disabled(repo)
