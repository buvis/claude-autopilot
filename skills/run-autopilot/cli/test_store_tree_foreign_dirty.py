#!/usr/bin/env python3
"""Tests for cli/store_tree.py's foreign_dirty: the dirty-tree predicate
listing paths outside the autopilot store roots.

Written from the design contract only. Every test injects a fake run_git
that records the argv it was called with, so no real git runs here.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cli import store_tree
from cli.store_tree_testutil import REPO, FakeGit

STATUS_ARGS = ["status", "--porcelain", "-z"]


def _porcelain(*fields: str) -> str:
    """NUL-terminate every field, exactly as `git status -z` does."""
    return "".join(f"{field}\0" for field in fields)


def _foreign(porcelain: str) -> tuple[list[str], FakeGit]:
    git = FakeGit({"status": porcelain})
    return store_tree.foreign_dirty(REPO, run_git=git), git


class StorePrefixesTests(unittest.TestCase):
    def test_store_prefixes_are_the_two_slash_terminated_store_roots(self) -> None:
        self.assertEqual(
            tuple(store_tree.STORE_PREFIXES),
            ("docs/dev/project-management/", "docs/dev/tmp/"),
        )


class ForeignDirtyTests(unittest.TestCase):
    def test_store_paths_are_never_foreign(self) -> None:
        porcelain = _porcelain(
            " M docs/dev/project-management/autopilot/state.json",
            "A  docs/dev/project-management/prds/wip/00001-x.md",
            "?? docs/dev/tmp/scratch.txt",
            "D  docs/dev/tmp/old/gone.txt",
            "R  docs/dev/project-management/prds/done/00001-x.md",
            "docs/dev/project-management/prds/wip/00001-x.md",
        )

        out, git = _foreign(porcelain)

        self.assertEqual(out, [])
        self.assertEqual(git.calls, [(STATUS_ARGS, REPO)])

    def test_a_clean_tree_has_no_foreign_paths(self) -> None:
        out, git = _foreign("")

        self.assertEqual(out, [])
        self.assertEqual(git.calls, [(STATUS_ARGS, REPO)])

    def test_a_path_outside_the_store_is_foreign(self) -> None:
        porcelain = _porcelain(
            " M src/app.py",
            " M docs/dev/project-management/autopilot/state.json",
            "?? docs/dev/project-management-notes/foo.txt",
            "?? docs/dev/tmpfile.txt",
            "?? dir with space/f.txt",
            "A  docs/dev/tmp/a.txt",
            "?? vendor/docs/dev/tmp/x.txt",
            "?? a/docs/dev/project-management/b",
            " D src/deleted_in_tree.py",
            "D  src/deleted_in_index.py",
            "MM src/both.py",
            "UU src/conflict.py",
        )

        out, _ = _foreign(porcelain)

        self.assertEqual(
            sorted(out),
            sorted(
                [
                    "src/app.py",
                    "docs/dev/project-management-notes/foo.txt",
                    "docs/dev/tmpfile.txt",
                    "dir with space/f.txt",
                    "vendor/docs/dev/tmp/x.txt",
                    "a/docs/dev/project-management/b",
                    "src/deleted_in_tree.py",
                    "src/deleted_in_index.py",
                    "src/both.py",
                    "src/conflict.py",
                ],
            ),
            "a sibling that only shares the prefix text, a nested path that "
            "merely contains a store root, and any outside status code "
            "(deletions and conflicts included) are all outside the store",
        )

    def test_an_untracked_store_reports_only_the_non_store_paths(self) -> None:
        porcelain = _porcelain(
            "?? docs/dev/project-management/autopilot/state.json",
            "?? docs/dev/project-management/prds/backlog/00002-y.md",
            "?? docs/dev/tmp/dispatch.txt",
            "?? README.md",
        )

        out, _ = _foreign(porcelain)

        self.assertEqual(out, ["README.md"])

    def test_a_rename_out_of_the_store_is_foreign(self) -> None:
        porcelain = _porcelain(
            "R  src/moved.md",
            "docs/dev/project-management/prds/wip/old.md",
        )

        out, _ = _foreign(porcelain)

        self.assertEqual(
            out,
            ["src/moved.md"],
            "the outside side is foreign; the store side contributes nothing",
        )

    def test_a_rename_into_the_store_reports_the_outside_old_path(self) -> None:
        porcelain = _porcelain(
            "R  docs/dev/project-management/prds/wip/new.md",
            "notes/old.md",
        )

        out, _ = _foreign(porcelain)

        self.assertEqual(
            out,
            ["notes/old.md"],
            "the old side counts even though the entry's own path slot is in the store",
        )

    def test_rename_and_copy_old_paths_are_not_misread_as_entries(self) -> None:
        porcelain = _porcelain(
            "R  docs/dev/project-management/b.md",
            "docs/dev/project-management/a.md",
            "RM docs/dev/tmp/y.txt",
            "docs/dev/tmp/x.txt",
            "C  lib/copy.py",
            "lib/orig.py",
            " M src/after.py",
        )

        out, _ = _foreign(porcelain)

        self.assertEqual(
            sorted(out),
            ["lib/copy.py", "lib/orig.py", "src/after.py"],
            "a store-to-store rename adds nothing; a copy with both sides "
            "outside reports both; the entry after a rename still parses",
        )


if __name__ == "__main__":
    unittest.main()
