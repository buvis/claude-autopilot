#!/usr/bin/env python3
"""PRD 00146: the Deferred to Batch End table renders the union of
`state.deferred_decisions` and the batch deferred JSON's items for the PRD,
deduplicated, with a Reason cell for cap-overflow rows and `resolved`
entries excluded; `autopilot render report` exits 12 naming any pending
JSON item its rendered section does not contain.

The 00140 fixture (cli/golden/deferred-00140-cycle2.json) is the six
cycle-2 records copied verbatim from batch 202608180438, the batch whose
report lost them.
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

NOW = "2026-08-26T12:00:00Z"
PRD_00140 = "00140-gate-style-limits-before-review-v1.md"
TABLE_HEADING = "### Deferred to Batch End"


def _fixture_items() -> list[dict]:
    return json.loads(
        (GOLDEN / "deferred-00140-cycle2.json").read_text(encoding="utf-8")
    )["items"]


def _state(prd: str = "00099-x-v1.md", deferred: list | None = None) -> dict:
    return {
        "prd": prd,
        "cycle": 2,
        "batch": {"id": "202608180438", "completed_prds": []},
        "deferred_decisions": deferred or [],
        "tasks": [],
    }


def _deferred_rows(text: str) -> list[str]:
    """The data rows of the Deferred to Batch End table, or [] when the
    section is absent."""
    if TABLE_HEADING not in text:
        return []
    lines = text.split(TABLE_HEADING, 1)[1].splitlines()
    body = lines[lines.index("|-------|----------|--------|") + 1 :]
    rows = []
    for line in body:
        if not line.startswith("| "):
            break
        rows.append(line)
    return rows


def _cap(issue: str, **extra) -> dict:
    return {
        "type": "cap-overflow",
        "issue": issue,
        "severity": "medium",
        "consensus": "1/4",
        "cycle": 2,
        **extra,
    }


class MergeRenderTests(unittest.TestCase):
    def test_a_json_only_record_renders_a_row(self) -> None:
        text = render_report.prd_section(
            _state(), [], NOW, json_items=[_cap("only in the JSON sink")]
        )
        rows = _deferred_rows(text)
        self.assertEqual(len(rows), 1, text)
        self.assertIn("only in the JSON sink", rows[0])

    def test_the_same_normalized_issue_in_both_sinks_renders_once(self) -> None:
        state = _state(deferred=[_cap("Rename  the   config key", reason="state")])
        text = render_report.prd_section(
            state, [], NOW, json_items=[_cap("rename the config KEY", reason="json")]
        )
        rows = _deferred_rows(text)
        self.assertEqual(len(rows), 1, text)
        # State entries win the dedup (they were written first).
        self.assertIn("| state |", rows[0])

    def test_a_resolved_entry_renders_no_row(self) -> None:
        item = _cap("fixed at the walkthrough", resolved={"commit": "c175402"})
        text = render_report.prd_section(_state(), [], NOW, json_items=[item])
        self.assertEqual(_deferred_rows(text), [], text)
        state = _state(deferred=[item])
        self.assertEqual(_deferred_rows(render_report.prd_section(state, [], NOW)), [])

    def test_a_falsy_resolved_value_still_counts_as_open(self) -> None:
        # Key presence is not resolution: `resolved: null`/`false` must not
        # hide a pending finding, which is the under-reporting being fixed.
        items = [_cap("still open", resolved=None), _cap("also open", resolved=False)]
        text = render_report.prd_section(_state(), [], NOW, json_items=[*items])
        self.assertEqual(len(_deferred_rows(text)), 2, text)
        for item in items:
            item["prd"] = "p.md"
        self.assertEqual(render_report.missing_from_report("", items, "p.md"), items)

    def test_a_cap_overflow_record_without_reason_renders_a_synthesized_reason(
        self,
    ) -> None:
        state = _state(deferred=[_cap("no reason key", consensus="3/4", cycle=2)])
        rows = _deferred_rows(render_report.prd_section(state, [], NOW))
        self.assertEqual(len(rows), 1)
        self.assertIn(
            "| rework cap reached with this finding unresolved (cycle 2, consensus 3/4) |",
            rows[0],
        )

    def test_the_synthesized_reason_names_only_the_parts_the_record_carries(
        self,
    ) -> None:
        # The phase-review.md:53 state shape has no `cycle`; never print None.
        state = _state(
            deferred=[
                {"type": "cap-overflow", "issue": "state shape", "severity": "high"},
                {"type": "cap-overflow", "issue": "consensus only", "consensus": "2/4"},
            ]
        )
        rows = _deferred_rows(render_report.prd_section(state, [], NOW))
        self.assertTrue(
            rows[0].endswith("| rework cap reached with this finding unresolved |"), rows[0]
        )
        self.assertTrue(
            rows[1].endswith("| rework cap reached with this finding unresolved (consensus 2/4) |"),
            rows[1],
        )
        self.assertNotIn("None", "\n".join(rows))

    def test_a_populated_reason_or_disposition_is_kept_verbatim(self) -> None:
        state = _state(
            deferred=[
                _cap("has reason", reason="kept"),
                _cap("has disposition", disposition="also kept"),
            ]
        )
        rows = _deferred_rows(render_report.prd_section(state, [], NOW))
        self.assertEqual(len(rows), 2)
        self.assertTrue(rows[0].endswith("| kept |"), rows[0])
        self.assertTrue(rows[1].endswith("| also kept |"), rows[1])
        self.assertNotIn("rework cap reached", "\n".join(rows))

    def test_two_distinct_issues_stay_two_rows(self) -> None:
        text = render_report.prd_section(
            _state(),
            [],
            NOW,
            json_items=[_cap("first distinct finding"), _cap("second distinct finding")],
        )
        self.assertEqual(len(_deferred_rows(text)), 2, text)

    def test_the_00140_fixture_replay_renders_five_rows_with_reasons(self) -> None:
        items = _fixture_items()
        self.assertEqual(len(items), 6)
        text = render_report.prd_section(
            _state(prd=PRD_00140), [], NOW, json_items=items
        )
        rows = _deferred_rows(text)
        self.assertEqual(len(rows), 5, text)
        for row in rows:
            cells = [c.strip() for c in row.strip().strip("|").split(" | ")]
            self.assertEqual(len(cells), 3, row)
            self.assertNotEqual(cells[2], "", row)
        self.assertNotIn("REPRODUCED: a 61-line function", text)
        for item in items[1:]:
            self.assertIn(render_report._cell(item["issue"]), text)

class MissingFromReportTests(unittest.TestCase):
    def test_a_pending_item_absent_from_the_report_is_returned(self) -> None:
        item = _cap("never rendered", prd="p.md")
        self.assertEqual(
            render_report.missing_from_report("## p.md\n\nnothing", [item], "p.md"),
            [item],
        )

    def test_a_rendered_item_is_not_missing_despite_whitespace_and_pipes(self) -> None:
        item = _cap("a | b   c", prd="p.md")
        text = "\n".join(render_report._deferred_to_batch_end([item]))
        self.assertEqual(render_report.missing_from_report(text, [item], "p.md"), [])

    def test_resolved_other_prd_and_settled_items_never_trip(self) -> None:
        items = [
            _cap("resolved one", prd="p.md", resolved={"commit": "abc"}),
            _cap("other prd", prd="q.md"),
            _cap("settled", prd="p.md", status="approved"),
        ]
        self.assertEqual(render_report.missing_from_report("", items, "p.md"), [])

    def test_an_item_without_issue_is_always_missing(self) -> None:
        items = [
            {"type": "cap-overflow", "severity": "medium", "prd": "p.md"},
            _cap("", prd="p.md"),
        ]
        self.assertEqual(render_report.missing_from_report("", items, "p.md"), items)


class RenderReportGuardTests(unittest.TestCase):
    """`autopilot render report` as a subprocess against a constructed
    <repo>/dev/local/autopilot tree whose deferred JSON holds 00140's records."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.ap_dir = Path(tmp.name) / "dev" / "local" / "autopilot"
        self.ap_dir.mkdir(parents=True)
        self.state_path = self.ap_dir / "state.json"
        self.state_path.write_text(json.dumps(_state(prd=PRD_00140)), encoding="utf-8")
        (self.ap_dir / "deferred").mkdir()
        self.deferred_path = self.ap_dir / "deferred" / "202608180438-deferred.json"
        self.report = self.ap_dir / "reports" / "202608180438-report.md"

    def _seed(self, items: list[dict]) -> None:
        self.deferred_path.write_text(
            json.dumps({"batch_id": "202608180438", "items": items}), encoding="utf-8"
        )

    def _run(self) -> subprocess.CompletedProcess:
        return subprocess.run(
            [
                sys.executable,
                str(CLI_MAIN),
                "render",
                "report",
                "--now",
                NOW,
                "--state",
                str(self.state_path),
            ],
            capture_output=True,
            text=True,
        )

    def test_the_00140_records_render_and_the_guard_exits_0_silently(self) -> None:
        self._seed(_fixture_items())
        proc = self._run()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stderr, "")
        rows = _deferred_rows(self.report.read_text(encoding="utf-8"))
        self.assertEqual(len(rows), 5)

    def test_a_pending_item_without_issue_exits_12_naming_it(self) -> None:
        self._seed(
            _fixture_items()
            + [{"type": "cap-overflow", "severity": "medium", "prd": PRD_00140}]
        )
        proc = self._run()
        self.assertEqual(proc.returncode, 12, proc.stderr)
        self.assertIn(
            "autopilot: render report: deferred item missing from the rendered report:",
            proc.stderr,
        )
        self.assertNotIn("Traceback", proc.stderr)
        # The section itself was still written: the guard reports, it does
        # not withhold the rows that did render (the issue-less item renders
        # a blank Issue cell and is what the guard names).
        rows = _deferred_rows(self.report.read_text(encoding="utf-8"))
        self.assertEqual(len(rows), 6)
        self.assertTrue(rows[-1].startswith("|  | medium |"), rows[-1])

    def test_a_resolved_item_does_not_trip_the_guard(self) -> None:
        self._seed([_fixture_items()[0]])
        proc = self._run()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stderr, "")
        self.assertNotIn(TABLE_HEADING, self.report.read_text(encoding="utf-8"))

    def test_items_of_another_prd_are_neither_rendered_nor_guarded(self) -> None:
        self._seed([_cap("belongs elsewhere", prd="00001-other-v1.md")])
        proc = self._run()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("belongs elsewhere", self.report.read_text(encoding="utf-8"))

    def test_no_deferred_file_renders_as_before(self) -> None:
        proc = self._run()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn(f"## {PRD_00140}", self.report.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
