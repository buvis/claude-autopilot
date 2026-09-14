#!/usr/bin/env python3
"""Tests for the `autopilot check-plan` subcommand, which exposes the
plan-expansion verdict of cli/policy.py.

The exit-code contract (0 pass or override, 3 stall, 2 unreadable input) is
pinned as a real CLI process exit via subprocess, the way test_cli.py pins
exits 5/9/10. The pure functions are exercised in-process by test_policy.py,
which also owns the fixture helpers imported here.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from cli.test_policy import (
    _SRC_TREE,
    _prd_00167,
    _prd_00169,
    _prd_text,
    _sections,
    _src_state,
    _state_00167,
    _state_00169,
    _state_with_files,
    _state_with_tasks,
)

CLI_MAIN = Path(__file__).resolve().parent / "__main__.py"


class CheckPlanCliTests(unittest.TestCase):
    """The plan-expansion gate as a real process: exit 0 on pass or override,
    3 on a stall (with the split note on disk and the stall instruction on
    stderr), 2 on a missing state or PRD."""

    _OVERRIDE = "---\nplan_expansion: allow\n---\n"

    def _run(self, args: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(CLI_MAIN), *args],
            capture_output=True,
            text=True,
        )

    def _write_state(self, tmp: Path, state: dict) -> Path:
        state_path = tmp / "state.json"
        state_path.write_text(json.dumps(state), encoding="utf-8")
        return state_path

    def _write_prd(
        self, tmp: Path, text: str, name: str = "00004-feature-x.md"
    ) -> Path:
        prd_path = tmp / name
        prd_path.write_text(text, encoding="utf-8")
        return prd_path

    def _stall_lines(self, numbers: str, reasons: str, note_path: Path) -> list[str]:
        """The two stderr lines the stall branch prints, by contract."""
        return [
            f"autopilot: plan expansion gate: {numbers}; note {note_path}",
            'Loop mode: stall this PRD (site "plan_expansion", detail '
            f'"{reasons}; note {note_path}"). '
            "Interactive: this is a warning, continue.",
        ]

    def test_under_ceiling_exits_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = self._write_state(Path(tmp), _state_with_tasks(15))
            prd_path = self._write_prd(Path(tmp), _prd_text(0))
            result = self._run(
                ["check-plan", "--state", str(state_path), "--prd", str(prd_path)],
            )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_over_ceiling_exits_three_and_names_both_numbers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = self._write_state(Path(tmp), _state_with_tasks(16))
            prd_path = self._write_prd(Path(tmp), _prd_text(0))
            result = self._run(
                ["check-plan", "--state", str(state_path), "--prd", str(prd_path)],
            )
        self.assertEqual(result.returncode, 3)
        self.assertIn("16", result.stderr)
        self.assertIn("15", result.stderr)
        self.assertIn("task_count 16 > 15", result.stderr)
        self.assertIn("plan_expansion", result.stderr)
        self.assertNotIn("oversized_plan", result.stderr)

    def test_ceiling_flag_is_honored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = self._write_state(Path(tmp), _state_with_tasks(16))
            prd_path = self._write_prd(Path(tmp), _prd_text(0))
            result = self._run(
                [
                    "check-plan",
                    "--state",
                    str(state_path),
                    "--prd",
                    str(prd_path),
                    "--ceiling",
                    "20",
                ],
            )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_production_parser_exposes_no_count_flag(self) -> None:
        """The count must never be suppliable by the caller being gated."""
        with tempfile.TemporaryDirectory() as tmp:
            state_path = self._write_state(Path(tmp), _state_with_tasks(16))
            prd_path = self._write_prd(Path(tmp), _prd_text(0))
            result = self._run(
                [
                    "check-plan",
                    "--state",
                    str(state_path),
                    "--prd",
                    str(prd_path),
                    "--count",
                    "3",
                ],
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--count", result.stderr)

    def test_missing_state_fails_loud_rather_than_passing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "state.json"
            prd_path = self._write_prd(Path(tmp), _prd_text(0))
            result = self._run(
                ["check-plan", "--state", str(missing), "--prd", str(prd_path)],
            )
        self.assertEqual(result.returncode, 2)
        self.assertIn("check-plan failed", result.stderr)

    def test_corrupt_state_fails_loud_rather_than_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            corrupt = Path(tmp) / "state.json"
            corrupt.write_text("not json", encoding="utf-8")
            prd_path = self._write_prd(Path(tmp), _prd_text(0))
            result = self._run(
                ["check-plan", "--state", str(corrupt), "--prd", str(prd_path)],
            )
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("check-plan failed", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_stall_writes_split_note_and_names_the_site(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = self._write_state(Path(tmp), _state_00167())
            prd_path = self._write_prd(Path(tmp), _prd_00167())
            note_path = Path(tmp) / "split-notes" / "00004-feature-x.md"
            result = self._run(
                ["check-plan", "--state", str(state_path), "--prd", str(prd_path)],
            )
            self.assertEqual(result.returncode, 3, result.stderr)
            self.assertTrue(note_path.exists(), result.stderr)
            note = note_path.read_text(encoding="utf-8")
        self.assertIn("UNLISTED", note)
        self.assertEqual(
            note.splitlines()[:2],
            [
                "# Split note: 00167-sync-manager-merge.md",
                "planned=21 prd_tasks=4 expansion=5.25 "
                "reasons=task_count, expansion, module_drift",
            ],
            "the note on disk is the verdict's note, headed by the state's prd",
        )
        headings = [heading for heading, _body in _sections(note)]
        self.assertIn("ddb-core/src/parser (UNLISTED)", headings)
        self.assertIn("ddb-core/src/sync_manager (listed)", headings)
        self.assertIn("plan_expansion", result.stderr)
        self.assertIn("module_drift", result.stderr)
        self.assertIn(str(note_path), result.stderr)
        self.assertEqual(
            result.stderr.splitlines()[:2],
            [
                "autopilot: plan expansion gate: task_count 21 > 15, "
                "expansion 5.25 > 3.0 (planned 21 > 8), "
                "module_drift 4 > 1 (ddb-core/src/git_ops, ddb-core/src/id_minting, "
                f"ddb-core/src/parser, ddb-core/src/types); note {note_path}",
                'Loop mode: stall this PRD (site "plan_expansion", detail '
                f'"task_count, expansion, module_drift; note {note_path}"). '
                "Interactive: this is a warning, continue.",
            ],
        )
        self.assertNotIn("oversized_plan", result.stderr)

    def test_stall_names_only_the_task_count_when_it_alone_fires(self) -> None:
        """00169: 20 tasks over the ceiling, ratio 2.0 and one drifting module
        stay under their bounds, so neither appears in the numbers."""
        with tempfile.TemporaryDirectory() as tmp:
            state_path = self._write_state(Path(tmp), _state_00169())
            prd_path = self._write_prd(Path(tmp), _prd_00169())
            note_path = Path(tmp) / "split-notes" / "00004-feature-x.md"
            result = self._run(
                ["check-plan", "--state", str(state_path), "--prd", str(prd_path)],
            )
            self.assertEqual(result.returncode, 3, result.stderr)
            self.assertTrue(note_path.exists(), result.stderr)
            note = note_path.read_text(encoding="utf-8")
        self.assertEqual(
            result.stderr.splitlines()[:2],
            self._stall_lines("task_count 20 > 15", "task_count", note_path),
        )
        self.assertEqual(
            note.splitlines()[1],
            "planned=20 prd_tasks=10 expansion=2.00 reasons=task_count",
        )

    def test_raised_ceiling_leaves_expansion_and_drift_to_stall(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = self._write_state(Path(tmp), _state_00167())
            prd_path = self._write_prd(Path(tmp), _prd_00167())
            note_path = Path(tmp) / "split-notes" / "00004-feature-x.md"
            result = self._run(
                [
                    "check-plan",
                    "--state",
                    str(state_path),
                    "--prd",
                    str(prd_path),
                    "--ceiling",
                    "30",
                ],
            )
            self.assertEqual(result.returncode, 3, result.stderr)
            self.assertTrue(note_path.exists(), result.stderr)
        self.assertEqual(
            result.stderr.splitlines()[:2],
            self._stall_lines(
                "expansion 5.25 > 3.0 (planned 21 > 8), "
                "module_drift 4 > 1 (ddb-core/src/git_ops, ddb-core/src/id_minting, "
                "ddb-core/src/parser, ddb-core/src/types)",
                "expansion, module_drift",
                note_path,
            ),
        )
        self.assertNotIn("task_count", result.stderr)

    def test_prd_task_lines_decide_the_expansion_verdict(self) -> None:
        """Ten filed tasks pass against four PRD task lines (2.50) and stall
        against three (3.33): the ratio is read from the PRD, not assumed."""
        with tempfile.TemporaryDirectory() as tmp:
            state_path = self._write_state(Path(tmp), _src_state(10))
            prd_path = self._write_prd(Path(tmp), _prd_text(4, _SRC_TREE))
            passed = self._run(
                ["check-plan", "--state", str(state_path), "--prd", str(prd_path)],
            )
            split_notes_exists = (Path(tmp) / "split-notes").exists()
        self.assertEqual(passed.returncode, 0, passed.stderr)
        self.assertEqual(passed.stderr, "")
        self.assertFalse(split_notes_exists, "a ratio of 2.50 writes no split note")
        with tempfile.TemporaryDirectory() as tmp:
            state_path = self._write_state(Path(tmp), _src_state(10))
            prd_path = self._write_prd(Path(tmp), _prd_text(3, _SRC_TREE))
            note_path = Path(tmp) / "split-notes" / "00004-feature-x.md"
            stalled = self._run(
                ["check-plan", "--state", str(state_path), "--prd", str(prd_path)],
            )
            self.assertEqual(stalled.returncode, 3, stalled.stderr)
            self.assertTrue(note_path.exists(), stalled.stderr)
        self.assertEqual(
            stalled.stderr.splitlines()[:2],
            self._stall_lines(
                "expansion 3.33 > 3.0 (planned 10 > 8)", "expansion", note_path
            ),
        )

    def test_note_is_named_after_the_prd_stem(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = self._write_state(Path(tmp), _state_00167())
            prd_path = self._write_prd(
                Path(tmp), _prd_00167(), name="00167-sync-manager-merge.md"
            )
            note_path = Path(tmp) / "split-notes" / "00167-sync-manager-merge.md"
            result = self._run(
                ["check-plan", "--state", str(state_path), "--prd", str(prd_path)],
            )
            self.assertEqual(result.returncode, 3, result.stderr)
            self.assertTrue(note_path.exists(), result.stderr)
            self.assertEqual(
                [p.name for p in (Path(tmp) / "split-notes").iterdir()],
                ["00167-sync-manager-merge.md"],
                "the note carries the --prd stem, never a fixed name",
            )
        first, second = result.stderr.splitlines()[:2]
        self.assertTrue(first.endswith(f"; note {note_path}"), first)
        self.assertIn(f'; note {note_path}")', second)

    def test_override_exits_zero_and_says_why(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = self._write_state(Path(tmp), _state_00167())
            prd_path = self._write_prd(Path(tmp), self._OVERRIDE + _prd_00167())
            result = self._run(
                ["check-plan", "--state", str(state_path), "--prd", str(prd_path)],
            )
            split_notes_exists = (Path(tmp) / "split-notes").exists()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stderr.splitlines(),
            [
                "autopilot: check-plan: plan_expansion: allow set in PRD frontmatter; "
                "skipping task_count, expansion, module_drift; "
                "plan-expansion: unfiled=0; drift=checked",
            ],
        )
        self.assertFalse(split_notes_exists, "an override writes no split note")

    def test_body_mention_of_the_override_key_is_not_an_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = self._write_state(Path(tmp), _state_00167())
            prd_path = self._write_prd(
                Path(tmp),
                _prd_00167() + "\nSet `plan_expansion: allow` to opt out.\n",
            )
            note_path = Path(tmp) / "split-notes" / "00004-feature-x.md"
            result = self._run(
                ["check-plan", "--state", str(state_path), "--prd", str(prd_path)],
            )
            self.assertEqual(result.returncode, 3, result.stderr)
            self.assertTrue(note_path.exists(), result.stderr)
        self.assertIn("module_drift", result.stderr)
        self.assertNotIn(
            "plan_expansion: allow set",
            result.stderr,
            "only the leading frontmatter block opts out, not a body mention",
        )

    def test_missing_prd_flag_is_a_usage_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = self._write_state(Path(tmp), _state_with_tasks(3))
            result = self._run(["check-plan", "--state", str(state_path)])
        # _ArgumentParser maps every usage error to exit 1; 2 is reserved for
        # state errors (see the exit-code table in __main__.py's docstring).
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("--prd", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_unreadable_prd_fails_loud(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = self._write_state(Path(tmp), _state_with_tasks(3))
            missing = Path(tmp) / "00004-feature-x.md"
            result = self._run(
                ["check-plan", "--state", str(state_path), "--prd", str(missing)],
            )
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn(f"check-plan failed: cannot read PRD {missing}", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_success_reports_unfiled_and_skipped_drift(self) -> None:
        state = _state_with_files(
            "00004-feature-x.md",
            [["src/a.py"], None, ["src/b.py"]],
        )
        with tempfile.TemporaryDirectory() as tmp:
            state_path = self._write_state(Path(tmp), state)
            prd_path = self._write_prd(Path(tmp), _prd_text(3))
            result = self._run(
                ["check-plan", "--state", str(state_path), "--prd", str(prd_path)],
            )
            split_notes_exists = (Path(tmp) / "split-notes").exists()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(
            "plan-expansion: unfiled=1; drift=skipped (no Repository Structure)",
            result.stderr,
        )
        self.assertFalse(split_notes_exists, "a pass writes no split note")

    def test_fully_filed_plan_with_a_tree_passes_silently(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = self._write_state(Path(tmp), _src_state(3))
            prd_path = self._write_prd(Path(tmp), _prd_text(3, _SRC_TREE))
            result = self._run(
                ["check-plan", "--state", str(state_path), "--prd", str(prd_path)],
            )
            split_notes_exists = (Path(tmp) / "split-notes").exists()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stderr,
            "",
            "nothing unfiled and drift checked: no diagnostic at all",
        )
        self.assertFalse(split_notes_exists)

    def test_pass_diagnostic_counts_every_unfiled_task(self) -> None:
        state = _state_with_files(
            "00004-feature-x.md",
            [["src/a.py"], None, []],
        )
        with tempfile.TemporaryDirectory() as tmp:
            state_path = self._write_state(Path(tmp), state)
            prd_path = self._write_prd(Path(tmp), _prd_text(3))
            result = self._run(
                ["check-plan", "--state", str(state_path), "--prd", str(prd_path)],
            )
            split_notes_exists = (Path(tmp) / "split-notes").exists()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stderr.splitlines(),
            ["plan-expansion: unfiled=2; drift=skipped (no Repository Structure)"],
            "a missing `files` key and an empty list are both unfiled",
        )
        self.assertFalse(split_notes_exists)

    def test_override_combines_diagnostics_on_one_line(self) -> None:
        state = _state_with_files(
            "00004-feature-x.md",
            [["src/a.py"], None, ["src/b.py"]],
        )
        with tempfile.TemporaryDirectory() as tmp:
            state_path = self._write_state(Path(tmp), state)
            prd_path = self._write_prd(Path(tmp), self._OVERRIDE + _prd_text(3))
            result = self._run(
                ["check-plan", "--state", str(state_path), "--prd", str(prd_path)],
            )
            split_notes_exists = (Path(tmp) / "split-notes").exists()
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = result.stderr.splitlines()
        self.assertEqual(len(lines), 1, result.stderr)
        self.assertIn("plan_expansion: allow", lines[0])
        self.assertIn(
            "plan-expansion: unfiled=1; drift=skipped (no Repository Structure)",
            lines[0],
        )
        self.assertEqual(
            lines,
            [
                "autopilot: check-plan: plan_expansion: allow set in PRD frontmatter; "
                "skipping task_count, expansion, module_drift; "
                "plan-expansion: unfiled=1; drift=skipped (no Repository Structure)",
            ],
            "the skipped-rules list is a fixed literal; only the diag varies",
        )
        self.assertFalse(split_notes_exists)

    def _checkout_fixture(self, tmp: Path) -> tuple[Path, Path, Path]:
        """A `<tmp>/dev/local` checkout: the 00167 state under autopilot/ and
        its PRD in prds/wip/; returns (state_path, wip_prd, note_path)."""
        state = {
            **_state_00167(),
            "prd": "00004-feature-x.md",
            "batch": {"id": "202609141200", "completed_prds": []},
        }
        ap_dir = tmp / "dev" / "local" / "autopilot"
        prds = tmp / "dev" / "local" / "prds"
        ap_dir.mkdir(parents=True)
        for sub in ("backlog", "wip", "hold"):
            (prds / sub).mkdir(parents=True)
        state_path = self._write_state(ap_dir, state)
        wip_prd = prds / "wip" / "00004-feature-x.md"
        wip_prd.write_text(_prd_00167(), encoding="utf-8")
        note_path = ap_dir / "split-notes" / "00004-feature-x.md"
        return state_path, wip_prd, note_path

    def _render_stalled_report(self, state_path: Path, detail: str) -> str:
        """`render report --stalled` with `detail` against `state_path`;
        returns the report text from <state dir>/reports/."""
        report = self._run(
            [
                "render",
                "report",
                "--state",
                str(state_path),
                "--stalled",
                "--site",
                "plan_expansion",
                "--detail",
                detail,
                "--now",
                "2026-09-14T12:00:00Z",
            ],
        )
        self.assertEqual(report.returncode, 0, report.stderr)
        return (state_path.parent / "reports" / "202609141200-report.md").read_text(
            encoding="utf-8",
        )

    def test_stall_detail_reaches_the_stalled_report(self) -> None:
        """The detail check-plan prints is lifted verbatim into `stall` and
        `render report --stalled`, so the note path lands in the report."""
        with tempfile.TemporaryDirectory() as tmp:
            state_path, wip_prd, note_path = self._checkout_fixture(Path(tmp))
            prds = wip_prd.parent.parent

            gate = self._run(
                ["check-plan", "--state", str(state_path), "--prd", str(wip_prd)],
            )
            self.assertEqual(gate.returncode, 3, gate.stderr)
            details = re.findall(r'detail "([^"]*)"', gate.stderr)
            self.assertEqual(
                details,
                [f"task_count, expansion, module_drift; note {note_path}"],
                gate.stderr,
            )
            detail = details[0]

            stall = self._run(
                [
                    "stall",
                    "--state",
                    str(state_path),
                    "--prd",
                    "00004-feature-x.md",
                    "--site",
                    "plan_expansion",
                    "--detail",
                    detail,
                ],
            )
            self.assertEqual(stall.returncode, 0, stall.stderr)
            self.assertTrue((prds / "hold" / "00004-feature-x.md").exists())
            self.assertFalse(wip_prd.exists())

            text = self._render_stalled_report(state_path, detail)
        self.assertIn("STALLED (plan_expansion)", text)
        self.assertIn(str(note_path), text)


if __name__ == "__main__":
    unittest.main()
