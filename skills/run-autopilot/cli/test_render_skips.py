#!/usr/bin/env python3
"""Tests for the batch summary's Skipped surface (PRD 00137).

A sibling of `cli/test_render.py` rather than more of it: that file sits at 684
lines against this project's 800-line ceiling, and
`cli/test_render_batch_summary_nonzero_binding.py` is the same split for its
concern.

Scope: `render_report.batch_summary`'s two new pieces - the `PRDs skipped: N`
count line, which must render even at zero (an all-skipped drain must not read
as a silent 0-done batch), and the `### Skipped` table, which appears only when
there is something in it.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cli import render_report


def _skip(prd: str, command: str = "false", exit_code: int = 1) -> dict:
    return {
        "prd": prd,
        "command": command,
        "exit_code": exit_code,
        "note": "",
        "at": "2026-08-26T18:04:11Z",
    }


def _state(skips: list[dict] | None = None, completed: list | None = None) -> dict:
    batch: dict = {"id": "202608261200", "completed_prds": completed or []}
    if skips is not None:
        batch["skips"] = skips
    return {"batch": batch}


class SkippedCountLineTests(unittest.TestCase):
    def test_renders_zero_when_no_skips_field_exists(self) -> None:
        self.assertIn("- PRDs skipped: 0", render_report.batch_summary(_state(), []))

    def test_renders_zero_for_an_empty_skips_list(self) -> None:
        self.assertIn("- PRDs skipped: 0", render_report.batch_summary(_state([]), []))

    def test_counts_two_skips(self) -> None:
        summary = render_report.batch_summary(
            _state([_skip("00110-a.md"), _skip("00113-b.md")]),
            [],
        )
        self.assertIn("- PRDs skipped: 2", summary)

    def test_sits_directly_under_the_completed_line(self) -> None:
        lines = render_report.batch_summary(
            _state([_skip("00110-a.md")]), []
        ).splitlines()
        completed_at = lines.index("- PRDs completed: 0")
        self.assertEqual(lines[completed_at + 1], "- PRDs skipped: 1")

    def test_an_all_skipped_batch_shows_the_skips_beside_a_zero_done_count(
        self,
    ) -> None:
        # The false-alarm this line exists to prevent: a drain that skipped
        # everything must not read as "0 done, session died".
        summary = render_report.batch_summary(_state([_skip("00110-a.md")]), [])
        self.assertIn("- PRDs completed: 0", summary)
        self.assertIn("- PRDs skipped: 1", summary)


class SkippedTableTests(unittest.TestCase):
    def test_no_table_when_there_are_no_skips(self) -> None:
        self.assertNotIn("### Skipped", render_report.batch_summary(_state([]), []))

    def test_table_names_the_prd_exit_code_and_command(self) -> None:
        summary = render_report.batch_summary(
            _state([_skip("00110-flip-v1.md", "test -f evidence.md", 1)]),
            [],
        )
        self.assertIn("### Skipped", summary)
        self.assertIn("| PRD | Exit code | Command |", summary)
        self.assertIn("| 00110-flip-v1.md | 1 | test -f evidence.md |", summary)

    def test_one_row_per_skip_in_recorded_order(self) -> None:
        summary = render_report.batch_summary(
            _state([_skip("00110-a.md"), _skip("00113-b.md", "false", 2)]),
            [],
        )
        rows = [ln for ln in summary.splitlines() if ln.startswith("| 001")]
        self.assertEqual(len(rows), 2)
        self.assertTrue(rows[0].startswith("| 00110-a.md |"), rows[0])
        self.assertTrue(rows[1].startswith("| 00113-b.md |"), rows[1])

    def test_a_pipe_in_the_command_is_escaped_so_the_table_survives(self) -> None:
        summary = render_report.batch_summary(
            _state([_skip("00110-a.md", "test $(ls | wc -l) -ge 3")]),
            [],
        )
        self.assertIn(r"test $(ls \| wc -l) -ge 3", summary)

    def test_the_table_follows_the_summary_lines(self) -> None:
        summary = render_report.batch_summary(_state([_skip("00110-a.md")]), [])
        self.assertLess(
            summary.index("- PRDs skipped: 1"),
            summary.index("### Skipped"),
        )


if __name__ == "__main__":
    unittest.main()
