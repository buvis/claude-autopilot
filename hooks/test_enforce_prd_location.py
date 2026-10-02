"""Behavior tests for hooks/enforce_prd_location.py, the working-document
layout gate.

Drives the hook through its real dispatched entry point, `run(payload)`,
which feeds a PreToolUse-shaped payload to `main()` as stdin JSON and
returns the (exit_code, stdout, stderr) triple the dispatcher sees.

Stdlib-only unittest, collected by pytest.
"""

from __future__ import annotations

import importlib
import sys
import unittest
from pathlib import Path

_HOOKS_DIR = Path(__file__).resolve().parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))
hook = importlib.import_module("enforce_prd_location")

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _run(rel: tuple[str, ...]) -> tuple[int, str, str]:
    file_path = str(_REPO_ROOT.joinpath("docs/dev/project-management", *rel))
    payload = {"tool_name": "Write", "tool_input": {"file_path": file_path}}
    return hook.run(payload)


class LayoutVocabularyTest(unittest.TestCase):
    def test_allows_intake_tree_for_raw_requirement_inputs(self) -> None:
        # specflow decision 2026-09-27: raw inputs live under intake/{new,processed}.
        for rel in (
            ("intake", "new", "specflow", "00001-initial-delivery", "design.md"),
            ("intake", "processed", "00002-widget", "qa-log.md"),
        ):
            with self.subTest(rel=rel):
                exit_code, _, _ = _run(rel)
                self.assertEqual(exit_code, 0)

    def test_blocks_unknown_top_level_dir(self) -> None:
        exit_code, _, stderr = _run(("scratch", "notes.md"))
        self.assertEqual(exit_code, 2)
        self.assertIn(
            "`scratch/` is not a docs/dev/project-management top-level dir",
            stderr,
        )

    def test_blocks_file_in_store_root(self) -> None:
        exit_code, _, _ = _run(("stray.md",))
        self.assertEqual(exit_code, 2)


if __name__ == "__main__":
    unittest.main()
