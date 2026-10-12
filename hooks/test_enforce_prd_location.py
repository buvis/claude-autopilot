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
        # The rejection message must publish the vocabulary it rejected
        # against, and every member of that vocabulary must be writable.
        for known in (
            "designs",
            "reviews",
            "plans",
            "autopilot",
            "discovery",
            "notes",
            "spikes",
            "specs",
            "walkthroughs",
            "audit-results",
        ):
            with self.subTest(known=known):
                self.assertIn(known, stderr)
                allowed_code, _, allowed_err = _run((known, "x.md"))
                self.assertEqual(allowed_code, 0)
                self.assertEqual(allowed_err, "")

    def test_blocks_file_in_store_root(self) -> None:
        exit_code, _, stderr = _run(("stray.md",))
        self.assertEqual(exit_code, 2)
        self.assertIn(
            "`stray.md` would land in docs/dev/project-management ROOT",
            stderr,
        )
        # A named keeper is still a root file at root, and belongs in meta/.
        exit_code, _, stderr = _run(("project-capsule.md",))
        self.assertEqual(exit_code, 2)
        self.assertIn(
            "`project-capsule.md` would land in docs/dev/project-management ROOT",
            stderr,
        )
        self.assertIn("named keeper", stderr)
        exit_code, _, stderr = _run(("meta", "project-capsule.md"))
        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr, "")

    def test_allows_ordinary_source_and_lifecycle_prd_paths(self) -> None:
        for rel in (
            ("hooks", "_common.py"),
            ("docs", "dev", "project-management", "prds", "backlog", "00271-x.md"),
        ):
            with self.subTest(rel=rel):
                file_path = str(_REPO_ROOT.joinpath(*rel))
                payload = {"tool_name": "Write", "tool_input": {"file_path": file_path}}
                exit_code, stdout, stderr = hook.run(payload)
                self.assertEqual(exit_code, 0)
                self.assertEqual(stdout, "")
                self.assertEqual(stderr, "")

    def test_blocks_bash_command_naming_a_repo_root_lifecycle_dir(self) -> None:
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "mv backlog/x.md wip/"},
        }
        exit_code, stdout, stderr = hook.run(payload)
        self.assertEqual(exit_code, 2)
        self.assertIn(
            "command references a repo-root `backlog/`, `wip/`, `hold/`, "
            "or `done/` directory",
            stderr,
        )
        self.assertEqual(stdout, "")
        payload = {
            "tool_name": "Bash",
            "tool_input": {
                "command": (
                    "mv docs/dev/project-management/prds/backlog/x.md "
                    "docs/dev/project-management/prds/wip/"
                ),
            },
        }
        exit_code, _, stderr = hook.run(payload)
        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr, "")

    def test_blocks_multiedit_whose_later_edit_leaves_the_store(self) -> None:
        payload = {
            "tool_name": "MultiEdit",
            "tool_input": {
                "edits": [
                    {
                        "file_path": str(
                            _REPO_ROOT / "docs/dev/project-management/notes/ok.md",
                        ),
                    },
                    {"file_path": str(_REPO_ROOT / "hold" / "00001-x.md")},
                ],
            },
        }
        exit_code, stdout, stderr = hook.run(payload)
        self.assertEqual(exit_code, 2)
        self.assertIn(
            "BLOCKED: `hold/00001-x.md` looks like a PRD lifecycle path at repo root",
            stderr,
        )
        self.assertEqual(stdout, "")

    def test_blocks_repo_root_backlog_write_whose_path_holds_a_lone_surrogate(
        self,
    ) -> None:
        for rel in (
            ("backlog", "x\ud800.md"),
            ("backlog", "x\udfff.md"),
            ("backlog", "x\udc80.md"),
            ("backlog", "sub\ud800", "x.md"),
            ("wip", "x\ud800.md"),
        ):
            with self.subTest(rel=rel):
                file_path = str(_REPO_ROOT.joinpath(*rel))
                payload = {"tool_name": "Write", "tool_input": {"file_path": file_path}}
                exit_code, stdout, stderr = hook.run(payload)
                self.assertEqual(exit_code, 2)
                # The hook normalizes un-encodable code points before it
                # resolves, so the message names the whole relative path with
                # each surrogate replaced - still the full rel, never a
                # basename.
                named = "/".join(rel).encode("utf-8", "replace").decode("utf-8")
                self.assertIn(
                    f"BLOCKED: `{named}` looks like a PRD lifecycle path at repo root",
                    stderr,
                )
                self.assertEqual(stdout, "")
                self.assertNotIn("policy hook degraded", stderr)

    def test_blocks_lone_surrogate_path_over_a_real_subprocess_pipe(self) -> None:
        # Drives the real entry point as a subprocess (the in-process tests
        # above only call hook.run() directly) with a strict-UTF-8 JSON
        # payload. Green at base: no subprocess-encoding bug, just a gap in
        # coverage (read_input decodes with errors="replace" already).
        import json
        import subprocess

        rel = ("backlog", "x\ud800.md")
        file_path = str(_REPO_ROOT.joinpath(*rel))
        payload = json.dumps(
            {"tool_name": "Write", "tool_input": {"file_path": file_path}},
            ensure_ascii=True,
        )
        result = subprocess.run(
            [sys.executable, str(_HOOKS_DIR / "enforce_prd_location.py")],
            input=payload.encode("ascii"),
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        named = "/".join(rel).encode("utf-8", "replace").decode("utf-8")
        self.assertIn(
            f"BLOCKED: `{named}` looks like a PRD lifecycle path at repo root",
            result.stderr.decode("utf-8"),
        )

    def test_allows_non_lifecycle_write_whose_path_holds_a_lone_surrogate(self) -> None:
        # Fail open elsewhere: an un-encodable path outside the lifecycle
        # layout is not a layout violation, so it must not be blocked.
        for file_path in (
            str(_REPO_ROOT / "docs" / "dev" / "tmp" / "x\ud800.md"),
            str(_REPO_ROOT / "hooks" / "x\ud800.py"),
            "/tmp/x\ud800.md",
        ):
            with self.subTest(file_path=file_path):
                payload = {"tool_name": "Write", "tool_input": {"file_path": file_path}}
                exit_code, stdout, stderr = hook.run(payload)
                self.assertEqual(exit_code, 0)
                self.assertNotIn("BLOCKED", stderr)
                self.assertEqual(stdout, "")


if __name__ == "__main__":
    unittest.main()
