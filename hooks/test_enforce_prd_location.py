"""Behavior tests for hooks/enforce_prd_location.py, the working-document
layout gate.

`_check_project_management_layout` decides from store-relative path parts
alone, so the tests drive it with tuples; no filesystem is touched.

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


class LayoutVocabularyTest(unittest.TestCase):
    def test_allows_intake_tree_for_raw_requirement_inputs(self) -> None:
        # specflow decision 2026-09-27: raw inputs live under intake/{new,processed}.
        for rel in (
            ("intake", "new", "specflow", "00001-initial-delivery", "design.md"),
            ("intake", "processed", "00002-widget", "qa-log.md"),
        ):
            with self.subTest(rel=rel):
                self.assertIsNone(hook._check_project_management_layout(rel))

    def test_blocks_unknown_top_level_dir(self) -> None:
        reason = hook._check_project_management_layout(("scratch", "notes.md"))
        self.assertIsNotNone(reason)
        self.assertIn(
            "`scratch/` is not a docs/dev/project-management top-level dir", reason
        )

    def test_blocks_file_in_store_root(self) -> None:
        self.assertIsNotNone(hook._check_project_management_layout(("stray.md",)))


if __name__ == "__main__":
    unittest.main()
