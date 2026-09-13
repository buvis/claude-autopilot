#!/usr/bin/env python3
"""Shared fixtures for test_custody.py and test_custody_stall.py: the
constants both use, real git repositories (git init plus real commits), and
the _StallTestCase base whose layout mirrors test_records_stall.py. Not a
test module (no test_ prefix), so nothing here is collected on its own.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from . import records

BATCH_ID = "202607300000"
NOTICE_PREFIX = f"> **Custody (cap_critical, batch {BATCH_ID}):**"
DECISIONS = [
    {"question": "q0", "status": "pending", "cycle": 1},
    {"question": "q1", "status": "resolved", "cycle": 1},
    {"question": "q2"},
    {"question": "q3", "status": "deferred", "type": "ambiguity"},
]
_GIT_ENV = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}


# -- git fixtures (real repositories, real commits) --------------------------
def _git(*args: str, cwd: Path | None = None) -> str:
    proc = subprocess.run(
        ["git", "-c", "user.email=t@example.com", "-c", "user.name=t", *args],
        cwd=cwd,
        env=_GIT_ENV,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    return proc.stdout.strip()


def _commit(work_tree: Path, name: str, git_dir: Path | None = None) -> str:
    (work_tree / name).write_text(name, encoding="utf-8")
    loc = (
        ["--git-dir", str(git_dir), "--work-tree", str(work_tree)]
        if git_dir
        else ["-C", str(work_tree)]
    )
    _git(*loc, "add", "-A", cwd=work_tree)
    _git(*loc, "commit", "-q", "-m", name, cwd=work_tree)
    return _git(*loc, "rev-parse", "HEAD", cwd=work_tree)


def _init_repo(repo: Path, commits: int = 3, branch: str = "master") -> list[str]:
    repo.mkdir(parents=True, exist_ok=True)
    _git("init", "-q", "-b", branch, str(repo))
    return [_commit(repo, f"f{i}.txt") for i in range(commits)]


def _init_bare_repo(bare: Path, work_tree: Path, commits: int = 3) -> list[str]:
    work_tree.mkdir(parents=True, exist_ok=True)
    _git("init", "-q", "--bare", "-b", "master", str(bare))
    return [_commit(work_tree, f"f{i}.txt", git_dir=bare) for i in range(commits)]


def _locator(*loc: str) -> str | None:
    """`git <loc> config --get autopilot.custodyMarker`, None when unset."""
    proc = subprocess.run(
        ["git", *loc, "config", "--get", "autopilot.custodyMarker"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return proc.stdout.strip() if proc.returncode == 0 else None


class _StallTestCase(unittest.TestCase):
    """Shared fixture: <root>/prds/wip (pre-created), <root>/prds/hold (left
    absent so do_stall's own mkdir -p is exercised by every success path),
    <root>/autopilot/state.json. The notifier is patched for every test.
    """

    PRD = "00004-feature-x.md"

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.prds_dir = self.root / "prds"
        self.autopilot_dir = self.root / "autopilot"
        self.state_path = self.autopilot_dir / "state.json"
        (self.prds_dir / "wip").mkdir(parents=True)
        self.autopilot_dir.mkdir(parents=True)
        self.notify = mock.patch("cli.notify_out.notify").start()
        self.addCleanup(mock.patch.stopall)

    # -- prd placement ------------------------------------------------
    def _put_in_wip(self, prd: str | None = None, content: str = "prd body") -> None:
        (self.prds_dir / "wip" / (prd or self.PRD)).write_text(
            content,
            encoding="utf-8",
        )

    def _in_wip(self, prd: str | None = None) -> bool:
        return (self.prds_dir / "wip" / (prd or self.PRD)).exists()

    def _in_hold(self, prd: str | None = None) -> bool:
        return (self.prds_dir / "hold" / (prd or self.PRD)).exists()

    # -- state ----------------------------------------------------------
    def _write_state(self, state: dict) -> None:
        self.state_path.write_text(json.dumps(state), encoding="utf-8")

    def _state(self) -> dict:
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def _sample_state(self, **overrides) -> dict:
        base = {
            "prd": self.PRD,
            "phase": "build",
            "next_phase": "build",
            "cycle": 2,
            "tasks": [{"id": "t1", "name": "x", "status": "in_progress"}],
            "batch": {
                "id": BATCH_ID,
                "completed_prds": [],
                "parks_consecutive": 1,
            },
        }
        base.update(overrides)
        return base

    # -- deferred log -----------------------------------------------------
    def _deferred_path(self, batch_id: str = BATCH_ID) -> Path:
        return self.autopilot_dir / "deferred" / f"{batch_id}-deferred.json"

    def _deferred_items(self, batch_id: str = BATCH_ID) -> list:
        path = self._deferred_path(batch_id)
        if not path.exists():
            return []
        return json.loads(path.read_text(encoding="utf-8"))["items"]

    # -- call under test --------------------------------------------------
    def _do_stall(
        self,
        *,
        prd=None,
        site="design_gate",
        detail="detail text",
        **kwargs,
    ):
        return records.do_stall(
            self.state_path,
            prd=prd if prd is not None else self.PRD,
            site=site,
            detail=detail,
            prds_dir=self.prds_dir,
            autopilot_dir=self.autopilot_dir,
            **kwargs,
        )
