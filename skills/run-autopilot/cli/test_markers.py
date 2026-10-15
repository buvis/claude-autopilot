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
        self.autopilot_dir = self.root / "docs" / "dev" / "project-management" / "autopilot"
        self.autopilot_dir.mkdir(parents=True)

    def test_check_reports_absent_as_false(self) -> None:
        # A fresh fixture dir: neither marker has ever been written.
        proc = _run(["markers", "--check", "handoff-requested", "cap-fired"], cwd=self.root)

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(
            json.loads(proc.stdout),
            {"handoff-requested": False, "cap-fired": False},
        )

    def test_check_reports_present_as_true(self) -> None:
        (self.autopilot_dir / ".cap-fired").write_text("x", encoding="utf-8")

        proc = _run(["markers", "--check", "handoff-requested", "cap-fired"], cwd=self.root)

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(
            json.loads(proc.stdout),
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


if __name__ == "__main__":
    unittest.main()
