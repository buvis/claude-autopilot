#!/usr/bin/env python3
"""Tests for which entries the "Autonomous Decisions" table draws a row for,
and for which keys feed each of its five cells.

Two rules live here. The blank-row filter: a decision with no issue text is
dropped, whether the source keys are absent (rendering None) or
present-but-empty (""). The alias chains: the Issue, Action and Reason cells
each read the first non-empty value from an ordered list of keys, because
real recorded entries file their text under decision/finding/supersedes/
detail/question rather than under "issue".

Split out as a new sibling of test_render.py (PRD 00122 item 6) to keep
both files under the 800-line limit; render_report.py's overall render
contract (golden fixtures, prd_section, batch_summary, etc.) is documented
in test_render.py's module docstring. test_render.py's own
AutonomousBlankRowTests class already covers the None-only baseline (an
absent key renders None, which the pre-existing filter already dropped);
these tests add the ""-aware cases PRD 00122 item 6 requires.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cli import render_report

# The alias chains, in the order each cell reads them.
ISSUE_KEYS = ("issue", "question", "decision", "finding", "supersedes", "detail")
ACTION_KEYS = ("action", "disposition")
REASON_KEYS = ("reason", "resolution", "rationale", "assumption")

# Positions in the row _autonomous_row returns, matching the table columns
# ["Cycle", "Issue", "Severity", "Action", "Reason"].
CYCLE, ISSUE, SEVERITY, ACTION, REASON = range(5)


def data_rows(lines: list[str]) -> list[str]:
    """The rendered data rows: the "| " lines, minus the header."""
    return [ln for ln in lines if ln.startswith("| ") and not ln.startswith("| Cycle")]


def cells(row: str) -> list[str]:
    """The five cell texts of one rendered data row, blanks included."""
    return [cell.strip() for cell in row.split("|")[1:-1]]


class AutonomousBlankRowEmptyStringTests(unittest.TestCase):
    """_cell() already renders "" the same as None (both come out blank),
    so _autonomous's blank-row filter must treat them the same way too: a
    decision whose five keys are all present but set to "" must be dropped
    exactly like an all-absent-keys decision is."""

    def test_drops_a_decision_whose_cells_are_all_empty_strings(self) -> None:
        # Exactly one row, not two: today's `any(cell is not None ...)`
        # predicate treats "" as non-blank and wrongly keeps this row.
        decisions = [
            {
                "cycle": 1,
                "issue": "Missing null check",
                "severity": "medium",
                "action": "auto-fix",
                "reason": "mechanical fix",
            },
            {"cycle": "", "issue": "", "severity": "", "action": "", "reason": ""},
        ]
        rows = data_rows(render_report._autonomous(decisions))
        self.assertEqual(len(rows), 1)
        # The surviving row keeps every cell it was given -- checked against
        # the input rather than against a blank-row literal, because a
        # literal only catches a blank row whose Cycle cell is blank too.
        self.assertEqual(
            cells(rows[0]),
            ["1", "Missing null check", "medium", "auto-fix", "mechanical fix"],
        )
        self.assertEqual([row for row in rows if not cells(row)[ISSUE]], [])

    def test_drops_a_decision_mixing_absent_and_empty_string_keys(self) -> None:
        # issue/severity/reason absent, cycle/action present but "" -- still
        # nothing but emptiness in every one of the 5 cells.
        decisions = [{"cycle": "", "action": ""}]
        self.assertEqual(render_report._autonomous(decisions), [])

    def test_omits_the_section_when_every_row_is_blank_via_empty_strings(
        self,
    ) -> None:
        decisions = [
            {"cycle": "", "issue": "", "severity": "", "action": "", "reason": ""},
        ]
        self.assertEqual(render_report._autonomous(decisions), [])


class AutonomousRowCellAliasTests(unittest.TestCase):
    """Each cell reads the first non-empty value among its own ordered list
    of keys, and nothing else on the entry reaches any cell."""

    def test_returns_the_five_cells_in_column_order(self) -> None:
        row = render_report._autonomous_row(
            {
                "cycle": 1,
                "issue": "state.json task tracker stale on resume",
                "severity": "low",
                "action": "reconcile-state",
                "reason": "verified via git log/show and full test run",
            },
        )
        self.assertEqual(
            row,
            [
                1,
                "state.json task tracker stale on resume",
                "low",
                "reconcile-state",
                "verified via git log/show and full test run",
            ],
        )

    def test_the_cycle_cell_repeats_the_cycle_it_was_given(self) -> None:
        # More than one cycle number, because a report spans several cycles
        # and a row that always says 1 files every later finding under the
        # first cycle.
        for cycle in (0, 2, 7):
            with self.subTest(cycle=cycle):
                row = render_report._autonomous_row({"cycle": cycle, "issue": "i"})
                self.assertEqual(row[CYCLE], cycle)

    def test_an_absent_cycle_renders_a_blank_cycle_cell(self) -> None:
        rows = data_rows(render_report._autonomous([{"issue": "i"}]))
        self.assertEqual(len(rows), 1)
        self.assertEqual(cells(rows[0]), ["", "i", "", "", ""])

    def test_the_severity_cell_repeats_the_severity_it_was_given(self) -> None:
        # Every level, not just one: a cell that reports a fixed level would
        # silently downgrade the critical findings a report exists to show.
        for severity in ("low", "medium", "high", "critical"):
            with self.subTest(severity=severity):
                row = render_report._autonomous_row(
                    {"cycle": 1, "issue": "i", "severity": severity},
                )
                self.assertEqual(row[SEVERITY], severity)

    def test_every_issue_alias_feeds_the_issue_cell(self) -> None:
        for key in ISSUE_KEYS:
            with self.subTest(key=key):
                row = render_report._autonomous_row({"cycle": 1, key: f"text-{key}"})
                self.assertEqual(row[ISSUE], f"text-{key}")

    def test_the_earlier_issue_alias_wins_when_several_are_present(self) -> None:
        # Walks the chain, so every adjacent pair is present together at
        # least once and the whole order is pinned, not just its first link.
        # The decision-beats-finding and decision-beats-supersedes steps are
        # the ones real recorded entries hit.
        for index, winner in enumerate(ISSUE_KEYS):
            entry = {key: f"text-{key}" for key in ISSUE_KEYS[index:]}
            with self.subTest(winner=winner):
                row = render_report._autonomous_row(entry)
                self.assertEqual(row[ISSUE], f"text-{winner}")

    def test_disposition_renders_as_action(self) -> None:
        text = "\n".join(
            render_report._autonomous(
                [{"cycle": 1, "issue": "i", "disposition": "auto-fix"}],
            ),
        )
        self.assertIn("| 1 | i |  | auto-fix |  |", text)

    def test_action_wins_over_disposition_when_both_are_present(self) -> None:
        entry = {key: f"text-{key}" for key in ACTION_KEYS}
        row = render_report._autonomous_row({**entry, "issue": "i"})
        self.assertEqual(row[ACTION], "text-action")

    def test_every_reason_alias_feeds_the_reason_cell(self) -> None:
        for key in REASON_KEYS:
            with self.subTest(key=key):
                row = render_report._autonomous_row({"issue": "i", key: f"text-{key}"})
                self.assertEqual(row[REASON], f"text-{key}")

    def test_the_earlier_reason_alias_wins_when_several_are_present(self) -> None:
        for index, winner in enumerate(REASON_KEYS):
            entry = {key: f"text-{key}" for key in REASON_KEYS[index:]}
            with self.subTest(winner=winner):
                row = render_report._autonomous_row({**entry, "issue": "i"})
                self.assertEqual(row[REASON], f"text-{winner}")

    def test_an_empty_earlier_alias_falls_through_to_the_next_one(self) -> None:
        # "" and None are both empty; only a value that is neither stops the
        # chain, so an entry that stamped an empty "issue" still shows the
        # text it filed under "decision".
        cases = [
            ({"issue": "", "decision": "d"}, ISSUE, "d"),
            ({"issue": None, "decision": "d"}, ISSUE, "d"),
            (
                {"issue": "i", "action": "", "disposition": "auto-fix"},
                ACTION,
                "auto-fix",
            ),
            ({"issue": "i", "reason": "", "resolution": "r"}, REASON, "r"),
        ]
        for entry, cell, expected in cases:
            with self.subTest(entry=entry):
                self.assertEqual(render_report._autonomous_row(entry)[cell], expected)

    def test_keys_outside_the_alias_chains_feed_no_cell(self) -> None:
        # Every value below except cycle and issue is unreachable: the row
        # renders 1 and "i" and three blanks, so none of the bookkeeping
        # fields real entries carry can leak into Severity/Action/Reason.
        entry = {
            "cycle": 1,
            "issue": "i",
            "type": "seam-defect-found",
            "task": "9",
            "task_id": 1,
            "label": "autonomous",
            "phase": "1.5-design",
            "consensus": "unanimous",
            "residual": "annotation still reads list[Discard]",
            "unresolved_non_blockers": "calibration-corpus test only runs locally",
            "id": 7,
        }
        text = "\n".join(render_report._autonomous([entry]))
        self.assertIn("| 1 | i |  |  |  |", text)


class AutonomousRowTextRequirementTests(unittest.TestCase):
    """A row is drawn only for a dict whose Issue cell holds text and whose
    type is not "assumed-ambiguity". Replaces the two tests that pinned the
    older "any one of the five cells is non-empty" rule
    (test_keeps_a_decision_whose_only_populated_cell_is_cycle and
    test_keeps_a_decision_whose_only_populated_cell_is_integer_zero)."""

    def test_cycle_only_entry_draws_no_row(self) -> None:
        self.assertFalse(render_report.is_autonomous_row({"cycle": 1}))
        self.assertEqual(render_report._autonomous([{"cycle": 1}]), [])

    def test_integer_zero_cycle_renders_as_zero_not_a_blank_cell(self) -> None:
        # Keeps the guard the old cycle-only version carried against a
        # truthiness-based filter (`any(cell for cell in row)`): _cell(0)
        # renders "0", not blank. The zero is paired with issue text because
        # a cycle-only entry no longer draws a row at all.
        text = "\n".join(render_report._autonomous([{"cycle": 0, "decision": "d"}]))
        self.assertIn("| 0 | d |  |  |  |", text)

    def test_entry_whose_only_populated_cell_is_severity_draws_no_row(self) -> None:
        entry = {"id": 7, "severity": "high"}
        self.assertFalse(render_report.is_autonomous_row(entry))
        self.assertEqual(render_report._autonomous([entry]), [])

    def test_text_only_outside_the_issue_chain_draws_no_row(self) -> None:
        # Issue text is what earns a row; text in the Action or Reason cell
        # is no substitute, because the row it draws still shows a blank
        # Issue -- the exact shape this filter exists to reject.
        entries = [
            {"action": "auto-fix"},
            {"disposition": "auto-fix"},
            {"reason": "mechanical fix"},
            {"resolution": "reconciled state.json against git"},
            {"cycle": 2, "severity": "high", "action": "auto-fix", "reason": "r"},
        ]
        for entry in entries:
            with self.subTest(entry=entry):
                self.assertFalse(render_report.is_autonomous_row(entry))
                self.assertEqual(render_report._autonomous([entry]), [])

    def test_issue_text_under_any_alias_draws_a_row(self) -> None:
        for key in ISSUE_KEYS:
            with self.subTest(key=key):
                self.assertTrue(
                    render_report.is_autonomous_row({"cycle": 1, key: f"text-{key}"}),
                )
        # An empty "issue" must not shadow the alias carrying the text.
        self.assertTrue(render_report.is_autonomous_row({"issue": "", "decision": "d"}))

    def test_assumed_ambiguity_entry_draws_no_row_even_with_issue_text(self) -> None:
        ambiguity = {
            "type": "assumed-ambiguity",
            "cycle": 1,
            "question": "queue.save()'s skip rule said skip on (a) or (b)",
            "assumption": "Scoped condition (a) to undecided/kept decisions only",
        }
        self.assertFalse(render_report.is_autonomous_row(ambiguity))
        self.assertEqual(render_report._autonomous([ambiguity]), [])
        # Only that one type value is excluded: every other type is an
        # ordinary autonomous decision and still draws its row.
        self.assertTrue(
            render_report.is_autonomous_row(
                {
                    "type": "seam-defect-found",
                    "task": "9",
                    "decision": "Adapt discards inside funnel.main() instead",
                },
            ),
        )

    def test_non_dict_entry_is_not_a_row_and_does_not_raise(self) -> None:
        for entry in ("not-a-dict", None, 7, ["cycle", 1]):
            with self.subTest(entry=entry):
                self.assertFalse(render_report.is_autonomous_row(entry))


if __name__ == "__main__":
    unittest.main()
