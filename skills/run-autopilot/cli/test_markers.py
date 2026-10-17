#!/usr/bin/env python3
"""Tests for the `markers` verb (PRD 00309 fast-track card c1).

A census of batch 202610111300's loop transcripts counted 7 `ls` and 6 `rm`
calls against `.handoff-requested` and `.cap-fired` where a verb should have
answered instead - the model doing by shell what the CLI should do by flag.
`markers --check NAME...` prints `{"NAME": bool, ...}` (present/absent as a
JSON object keyed by the bare marker name, no leading dot) and `markers
--clear NAME...` removes them, mirroring `cli.handoff.MARKERS`' own two
names (`handoff-requested`, `cap-fired`) mapped to `.handoff-requested` and
`.cap-fired` beside `state.json`.

No `--state` flag: like `loop` and the other flagless verbs, the autopilot
dir resolves by walking up from cwd, so these tests run `cli/__main__.py`
as a subprocess with `cwd` set to a synthetic
<root>/docs/dev/project-management/autopilot tree, exactly as
test_handoff.py's `_run` helper does.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pytest

from cli.__main__ import main

CLI_DIR = Path(__file__).resolve().parent
CLI_MAIN = CLI_DIR / "__main__.py"


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CLI_MAIN), *args],
        capture_output=True,
        text=True,
        cwd=str(cwd),
    )


class MarkersTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.autopilot_dir = (
            self.root / "docs" / "dev" / "project-management" / "autopilot"
        )
        self.autopilot_dir.mkdir(parents=True)

    def test_check_reports_absent_as_false(self) -> None:
        # A fresh fixture dir: neither marker has ever been written.
        proc = _run(
            ["markers", "--check", "handoff-requested", "cap-fired"], cwd=self.root
        )

        self.assertEqual(proc.returncode, 0, proc.stderr)
        output = json.loads(proc.stdout)
        output.pop("store", None)
        self.assertEqual(
            output,
            {"handoff-requested": False, "cap-fired": False},
        )

    def test_check_reports_present_as_true(self) -> None:
        (self.autopilot_dir / ".cap-fired").write_text("x", encoding="utf-8")

        proc = _run(
            ["markers", "--check", "handoff-requested", "cap-fired"], cwd=self.root
        )

        self.assertEqual(proc.returncode, 0, proc.stderr)
        output = json.loads(proc.stdout)
        output.pop("store", None)
        self.assertEqual(
            output,
            {"handoff-requested": False, "cap-fired": True},
        )

    def test_clear_is_idempotent(self) -> None:
        marker = self.autopilot_dir / ".handoff-requested"
        marker.write_text("handoff requested\n", encoding="utf-8")

        first = _run(["markers", "--clear", "handoff-requested"], cwd=self.root)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertFalse(marker.exists())

        # A second clear of an already-absent marker must not fail or print
        # a spurious removal error: the verb is idempotent by construction.
        second = _run(["markers", "--clear", "handoff-requested"], cwd=self.root)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertFalse(marker.exists())

    def test_unknown_name_exits_1(self) -> None:
        proc = _run(["markers", "--check", "not-a-real-marker"], cwd=self.root)

        self.assertEqual(proc.returncode, 1)
        self.assertTrue(proc.stderr.strip())
        self.assertEqual(proc.stdout, "")

    def test_markers_accepts_state_flag(self) -> None:
        # _run_markers has no --state flag today, so passing one is an
        # unrecognized argument - even though _walk_up_or_exit's own error
        # message tells the caller to pass --state when the walk fails.
        (self.autopilot_dir / ".cap-fired").write_text("x", encoding="utf-8")
        outside = self.root / "outside-of-the-tree"
        outside.mkdir()

        proc = _run(
            [
                "markers",
                "--check",
                "cap-fired",
                "--state",
                str(self.autopilot_dir / "state.json"),
            ],
            cwd=outside,
        )

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["cap-fired"], True)

    def test_markers_walk_stops_at_the_git_toplevel(self) -> None:
        # The walk follows the physical cwd through a symlink without ever
        # stopping at the git toplevel of the cwd, so a nested git repo with
        # no store of its own can still resolve an unrelated repository's
        # store that happens to sit above it.
        second_store_repo = self.root / "second-store-repo"
        second_autopilot_dir = (
            second_store_repo / "docs" / "dev" / "project-management" / "autopilot"
        )
        second_autopilot_dir.mkdir(parents=True)
        (second_autopilot_dir / ".cap-fired").write_text("x", encoding="utf-8")

        container = self.root / "container"
        container.mkdir()
        (container / "docs").symlink_to(
            second_store_repo / "docs",
            target_is_directory=True,
        )

        nested_repo = container / "nested-repo"
        nested_repo.mkdir()
        subprocess.run(
            ["git", "init", "-q"],
            cwd=nested_repo,
            check=True,
            capture_output=True,
        )

        proc = _run(["markers", "--check", "cap-fired"], cwd=nested_repo)

        # nested_repo is its own git toplevel and carries no autopilot store
        # of its own, so the walk must stop there and fail rather than climb
        # past it (through the symlink) into the unrelated repo's store.
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(proc.stdout, "")

    def test_markers_output_names_the_store(self) -> None:
        proc = _run(["markers", "--check", "handoff-requested"], cwd=self.root)

        self.assertEqual(proc.returncode, 0, proc.stderr)
        output = json.loads(proc.stdout)
        self.assertIn("store", output)
        self.assertEqual(
            Path(output["store"]).resolve(),
            self.autopilot_dir.resolve(),
        )


def _store_with_cleared_marker(root: Path) -> tuple[Path, Path]:
    autopilot_dir = root / "docs" / "dev" / "project-management" / "autopilot"
    autopilot_dir.mkdir(parents=True)
    marker = autopilot_dir / ".handoff-requested"
    marker.write_text("handoff requested\n", encoding="utf-8")
    return autopilot_dir, marker


def test_clear_refuses_when_git_toplevel_lookup_times_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # An unrelated autopilot store sits above cwd. A git timeout must not
    # fall back to an unbounded walk that reaches it and clears its marker.
    _autopilot_dir, marker = _store_with_cleared_marker(tmp_path)
    cwd = tmp_path / "nested" / "cwd"
    cwd.mkdir(parents=True)
    real_run = subprocess.run

    def _timeout(args, **kwargs):
        if args[:1] == ["git"]:
            raise subprocess.TimeoutExpired(cmd=args, timeout=10)
        return real_run(args, **kwargs)

    monkeypatch.setattr(subprocess, "run", _timeout)
    monkeypatch.chdir(cwd)

    raised = False
    code = None
    try:
        code = main(["markers", "--clear", "handoff-requested"])
    except Exception:
        raised = True

    assert raised or code != 0
    assert marker.exists(), "an unrelated store's marker was cleared after a git timeout"


def test_clear_refuses_when_git_toplevel_lookup_raises_oserror(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _autopilot_dir, marker = _store_with_cleared_marker(tmp_path)
    cwd = tmp_path / "nested" / "cwd"
    cwd.mkdir(parents=True)
    real_run = subprocess.run

    def _boom(args, **kwargs):
        if args[:1] == ["git"]:
            raise FileNotFoundError("git: command not found")
        return real_run(args, **kwargs)

    monkeypatch.setattr(subprocess, "run", _boom)
    monkeypatch.chdir(cwd)

    raised = False
    code = None
    try:
        code = main(["markers", "--clear", "handoff-requested"])
    except Exception:
        raised = True

    assert raised or code != 0
    assert marker.exists(), "an unrelated store's marker was cleared after a git OSError"


def test_clear_still_walks_unbounded_when_git_reports_not_a_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # cwd is not inside a git repo at all: git's own explicit "not a
    # repository" answer (not a tool failure) must still let the unbounded
    # walk reach an autopilot store above cwd, exactly as before this fix.
    _autopilot_dir, marker = _store_with_cleared_marker(tmp_path)
    cwd = tmp_path / "nested" / "cwd"
    cwd.mkdir(parents=True)
    real_run = subprocess.run

    def _not_a_repo(args, **kwargs):
        if args[:1] == ["git"]:
            return subprocess.CompletedProcess(
                args, returncode=128, stdout="", stderr="fatal: not a git repository\n"
            )
        return real_run(args, **kwargs)

    monkeypatch.setattr(subprocess, "run", _not_a_repo)
    monkeypatch.chdir(cwd)

    code = main(["markers", "--clear", "handoff-requested"])

    assert code == 0
    assert not marker.exists()


if __name__ == "__main__":
    unittest.main()
