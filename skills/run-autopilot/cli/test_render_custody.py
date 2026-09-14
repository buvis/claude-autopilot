#!/usr/bin/env python3
"""The custody line in the stalled report: `render report --stalled` reads
this PRD's `cap_critical` stall record from the batch deferred JSON and adds
a `- Commits:` line between Detail and Resume when that record carries a
`commit_range`. Range-less stalls keep today's three-line body byte for byte.

The CLI half drives `__main__.py` as a real process against a constructed
<repo>/dev/local/autopilot tree (the test_render_cli.py fixture shape); the
function half pins `render_report.stalled_section` in process.
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
GOLDEN = CLI_DIR / "golden"

sys.path.insert(0, str(CLI_DIR.parent))

from cli import render_report

NOW = "2026-08-09T12:00:00Z"
PRD = "00040-feature-x-v1.md"
BATCH_ID = "202607202320"
SITE = "cap_critical"
DETAIL = "usage cap hit at 163K"
RANGE = "2c922c3..fa17e58"
COMMITS = 5

RANGE_LESS_BLOCK = (
    f"## {PRD} — STALLED ({SITE})\n"
    "\n"
    f"- Stalled: {NOW}\n"
    f"- Detail: {DETAIL}\n"
    "- Resume: move back to dev/local/prds/wip/ and re-run\n"
)


def _with_range_block(commit_range: str, commits: int) -> str:
    """Today's block with the custody line inserted before Resume."""
    return RANGE_LESS_BLOCK.replace(
        "- Resume:",
        f"- Commits: {commit_range} ({commits}) live on master, custody pending\n"
        "- Resume:",
    )


WITH_RANGE_BLOCK = _with_range_block(RANGE, COMMITS)


def _stall_record(**overrides: object) -> dict:
    """A cap_critical stall record for the golden PRD carrying a range. The
    record's own `detail` differs from the --detail flag on purpose: the
    rendered Detail line must come from the flag."""
    record: dict = {
        "type": "stall",
        "site": SITE,
        "detail": "recorded by the stall handler",
        "op_id": "op-0001",
        "prd": PRD,
        "commit_range": RANGE,
        "commits": COMMITS,
        "branch": "master",
        "repo_root": "/tmp/repo",
        "git_dir": "/tmp/repo/.git",
    }
    record.update(overrides)
    return record


def _range_less(record: dict) -> dict:
    return {k: v for k, v in record.items() if k not in ("commit_range", "commits")}


class StalledCustodyCliTests(unittest.TestCase):
    """`autopilot render report --stalled --stdout` as a real subprocess,
    with the batch deferred JSON seeded beside state.json."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name)
        self.ap_dir = self.repo / "dev" / "local" / "autopilot"
        self.ap_dir.mkdir(parents=True)
        self.state_path = self.ap_dir / "state.json"
        self.state_path.write_text(
            (GOLDEN / "state-render.json").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        (self.ap_dir / "loop-metrics.jsonl").write_text(
            (GOLDEN / "metrics-render.jsonl").read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    def _run(self, args: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(CLI_MAIN), *args, "--state", str(self.state_path)],
            capture_output=True,
            text=True,
        )

    def _seed_deferred(self, items: list[dict]) -> None:
        deferred = self.ap_dir / "deferred"
        deferred.mkdir(exist_ok=True)
        (deferred / f"{BATCH_ID}-deferred.json").write_text(
            json.dumps({"items": items}),
            encoding="utf-8",
        )

    def _render_stalled(self) -> str:
        proc = self._run(
            [
                "render",
                "report",
                "--stalled",
                "--site",
                SITE,
                "--detail",
                DETAIL,
                "--now",
                NOW,
                "--stdout",
            ],
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout

    def test_prints_the_commits_line_between_detail_and_resume(self) -> None:
        # Range and count deliberately differ from RANGE/COMMITS, which the
        # last-record test expects: no single hardcoded line satisfies both,
        # so the CLI has to read the values off the record.
        self._seed_deferred([_stall_record(commit_range="abc1234..def5678", commits=2)])
        out = self._render_stalled()
        self.assertIn(_with_range_block("abc1234..def5678", 2), out)
        self.assertEqual(out.count("- Commits:"), 1)
        self.assertNotIn(RANGE, out)

    def test_prints_todays_three_lines_when_no_deferred_json_exists(self) -> None:
        out = self._render_stalled()
        self.assertIn(RANGE_LESS_BLOCK, out)
        self.assertNotIn("- Commits:", out)

    def test_prints_todays_three_lines_when_the_stall_record_has_no_range(
        self,
    ) -> None:
        self._seed_deferred([_range_less(_stall_record())])
        out = self._render_stalled()
        self.assertIn(RANGE_LESS_BLOCK, out)
        self.assertNotIn("- Commits:", out)

    def test_ignores_records_for_another_prd_site_or_type(self) -> None:
        self._seed_deferred(
            [
                _stall_record(prd="00041-feature-y-v1.md"),
                _stall_record(site="oversized_plan"),
                _stall_record(type="decision"),
            ],
        )
        out = self._render_stalled()
        self.assertIn(RANGE_LESS_BLOCK, out)
        self.assertNotIn("- Commits:", out)

    def test_uses_the_last_stall_record_carrying_a_range(self) -> None:
        # The decoys carry a larger and a smaller count than the expected
        # record, so picking by count in either direction lands on a decoy;
        # only the last ranged record yields the expected block.
        self._seed_deferred(
            [
                _stall_record(commit_range="1111111..2222222", commits=9),
                _stall_record(commit_range="9999999..aaaaaaa", commits=1),
                _stall_record(),
                _range_less(_stall_record()),
            ],
        )
        out = self._render_stalled()
        self.assertIn(WITH_RANGE_BLOCK, out)
        self.assertEqual(out.count("- Commits:"), 1)
        self.assertNotIn("1111111..2222222", out)
        self.assertNotIn("9999999..aaaaaaa", out)

    def test_default_section_gains_no_commits_line(self) -> None:
        # The record belongs to another PRD: today's default render exits 12
        # ("deferred item missing from the rendered report") when this PRD's
        # own stall record sits in the deferred JSON, and that check is not
        # this feature's to change. A range for another PRD still catches a
        # lookup that drops the prd filter and feeds the completed section.
        self._seed_deferred([_stall_record(prd="00041-feature-y-v1.md")])
        proc = self._run(["render", "report", "--now", NOW, "--stdout"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn(f"## {PRD}", proc.stdout)
        self.assertNotIn("- Commits:", proc.stdout)


class StalledSectionCustodyTests(unittest.TestCase):
    """`render_report.stalled_section` in process: the range-less body is
    today's, and a range inserts exactly one line before Resume."""

    def test_no_range_returns_todays_three_line_body(self) -> None:
        text = render_report.stalled_section(PRD, SITE, DETAIL, NOW)
        self.assertEqual(text.rstrip("\n") + "\n", RANGE_LESS_BLOCK)

    def test_range_inserts_the_commits_line_between_detail_and_resume(
        self,
    ) -> None:
        base = render_report.stalled_section(PRD, SITE, DETAIL, NOW)
        text = render_report.stalled_section(
            PRD,
            SITE,
            DETAIL,
            NOW,
            commit_range="a..b",
            commits=3,
        )
        self.assertEqual(
            text,
            base.replace(
                "- Resume:",
                "- Commits: a..b (3) live on master, custody pending\n- Resume:",
            ),
        )


if __name__ == "__main__":
    unittest.main()
