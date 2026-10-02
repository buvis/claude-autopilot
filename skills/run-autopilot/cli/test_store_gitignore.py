#!/usr/bin/env python3
"""Tests for store_tree.ensure_store_gitignore's unreadable-input behavior: a
.gitignore body it cannot read must never be reported as already matching.

Split out of test_store_tree.py, which holds the rest of the writer's
contract. Written from the design contract only.
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cli import store_tree


@pytest.mark.parametrize(
    "breakage", ["missing-store-dir", "unreadable", "invalid-utf8"]
)
def test_ensure_store_gitignore_never_reports_a_match_it_cannot_read(
    tmp_path: Path,
    breakage: str,
) -> None:
    store_dir = tmp_path / "project-management"
    gitignore = store_dir / ".gitignore"
    if breakage != "missing-store-dir":
        store_dir.mkdir()
    if breakage == "unreadable":
        gitignore.write_text(store_tree.STORE_GITIGNORE, encoding="utf-8")
        gitignore.chmod(0)
        if os.access(gitignore, os.R_OK):
            gitignore.chmod(0o600)
            pytest.skip("running with privileges that ignore file modes")
    elif breakage == "invalid-utf8":
        gitignore.write_bytes(b"\xff\xfe\n")

    try:
        wrote = store_tree.ensure_store_gitignore(store_dir)
    except (OSError, UnicodeDecodeError):
        return  # failing loudly is allowed; a silent "already matching" is not
    finally:
        if breakage == "unreadable":
            gitignore.chmod(0o600)

    assert wrote is True, "a body it could not read counts as differing"
    assert gitignore.read_text(encoding="utf-8") == store_tree.STORE_GITIGNORE


if __name__ == "__main__":
    unittest.main()
