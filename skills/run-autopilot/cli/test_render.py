#!/usr/bin/env python3
"""Tests for the PRD 00107 render surfaces: render_audit, render_report,
render_metrics and status, called in process. Their `autopilot render` /
`autopilot status` CLI wiring lives in test_render_cli.py; the report's
`- Run conditions:` line has test_render_run_conditions.py.

Goldens live in cli/golden/: the fixture state mirrors the documented
schema PLUS the live-state deviations the renders must tolerate (bare-string
`batch.completed_prds` entries, question/resolution decision shapes, an
attempt with no `implementor`), and each render is pinned byte-for-byte
against cli/golden/expected/.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

CLI_DIR = Path(__file__).resolve().parent
GOLDEN = CLI_DIR / "golden"
EXPECTED = GOLDEN / "expected"

sys.path.insert(0, str(CLI_DIR.parent))

from cli import render_audit, render_metrics, render_report, status

NOW = "2026-08-09T12:00:00Z"
STARTED = "2026-08-09T10:00:00Z"


def _state() -> dict:
    return json.loads((GOLDEN / "state-render.json").read_text(encoding="utf-8"))


def _rows() -> list[dict]:
    return render_metrics.load_rows(GOLDEN / "metrics-render.jsonl")


def _batch_state() -> dict:
    """A reconstruction of real batch 202608162223 with hand-written dict
    counts (not the archived record) standing in for the batch that exposed
    all five original render_report.py defects."""
    return json.loads(
        (GOLDEN / "state-batch-202608162223-reconstructed.json").read_text(
            encoding="utf-8",
        ),
    )


class GoldenRenderTests(unittest.TestCase):
    """Each render matches its golden built from the real-shaped fixture."""

    def test_audit_matches_golden(self) -> None:
        text = render_audit.render_audit(_state(), STARTED, NOW)
        self.assertEqual(text, (EXPECTED / "audit.md").read_text(encoding="utf-8"))

    def test_report_section_matches_golden(self) -> None:
        state = _state()
        rows = render_metrics.matching_rows(_rows(), state["prd"], state["batch"]["id"])
        convergence = render_metrics.load_event_rows(GOLDEN / "metrics-render.jsonl")[0]
        text = render_report.prd_section(state, rows, NOW, convergence=convergence)
        self.assertEqual(
            text,
            (EXPECTED / "report-section.md").read_text(encoding="utf-8"),
        )

    def test_batch_summary_matches_golden(self) -> None:
        text = render_report.batch_summary(_state(), _rows(), 2)
        self.assertEqual(
            text,
            (EXPECTED / "report-summary.md").read_text(encoding="utf-8"),
        )

    def test_metrics_summary_matches_golden(self) -> None:
        text = render_metrics.render_metrics(_rows()) + "\n"
        self.assertEqual(text, (EXPECTED / "metrics.md").read_text(encoding="utf-8"))

    def test_status_matches_golden(self) -> None:
        text = status.render_status(_state()) + "\n"
        self.assertEqual(text, (EXPECTED / "status.txt").read_text(encoding="utf-8"))


class MetricsFilterTests(unittest.TestCase):
    def test_matching_rows_excludes_other_prd_and_other_batch(self) -> None:
        state = _state()
        rows = render_metrics.matching_rows(_rows(), state["prd"], state["batch"]["id"])
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(r["prd"] == state["prd"] for r in rows))
        self.assertTrue(all(r["batch"] == state["batch"]["id"] for r in rows))

    def test_event_rows_are_not_counted_as_sessions(self) -> None:
        # PRD 00094: the review gate appends {"event": "review_converged", ...}
        # rows to the same file, sharing the fixture's prd+batch. They are not
        # sessions - counting one would inflate every Sessions and Total cell
        # and open a bogus `?` phase row. The fixture carries exactly one.
        raw = (GOLDEN / "metrics-render.jsonl").read_text(encoding="utf-8")
        self.assertEqual(raw.count('"event":"review_converged"'), 1)
        self.assertTrue(all("event" not in row for row in _rows()))
        self.assertEqual(len(_rows()), 6)

    def test_empty_rows_render_the_manual_run_line(self) -> None:
        self.assertEqual(render_metrics.phase_table([]), render_metrics.NO_METRICS)

    def test_missing_cost_renders_blank_not_zero(self) -> None:
        table = render_metrics.phase_table(
            [{"phase_launched": "done", "wall_secs": 10}],
        )
        self.assertIn("| done | 1 | 10 |  |  |", table)
        self.assertNotIn("0.00", table)

    def test_null_cost_renders_blank_not_zero_in_both_tables(self) -> None:
        # The fast-track recorder writes `"cost_usd": null` on purpose when no
        # --cost was passed: the key is present, the value is None, and an
        # unmeasured item is not a free one. Such a row has to render exactly
        # like one with no cost key at all - a blank cell, never 0.00, never
        # the word None, and no TypeError out of the sum. Pinned as equality
        # against the keyless rendering, for both public renderers.
        null_row = {
            "prd": "00001-x.md",
            "phase_launched": "done",
            "wall_secs": 10,
            "cost_usd": None,
        }
        keyless_row = {"prd": "00001-x.md", "phase_launched": "done", "wall_secs": 10}

        table = render_metrics.phase_table([null_row])
        self.assertEqual(table, render_metrics.phase_table([keyless_row]))
        self.assertIn("| done | 1 | 10 |  |  |", table)
        self.assertNotIn("0.00", table)
        self.assertNotIn("None", table)

        summary = render_metrics.render_metrics([null_row])
        self.assertEqual(summary, render_metrics.render_metrics([keyless_row]))
        self.assertIn("| 00001-x.md | 1 | 10 |  |", summary)
        self.assertNotIn("0.00", summary)
        self.assertNotIn("None", summary)

    def test_null_cost_beside_priced_rows_sums_the_priced_rows_only(self) -> None:
        # A group that mixes priced rows and a null one shows the priced sum
        # and nothing else: 3.75 in the group row and again in the Total row,
        # no 0.00 anywhere, neither addend on its own. Two distinct prices,
        # so the cell has to come from a real sum rather than from whichever
        # priced value the renderer happened to keep.
        rows = [
            {
                "prd": "00001-x.md",
                "phase_launched": "done",
                "wall_secs": 10,
                "cost_usd": 1.25,
            },
            {
                "prd": "00001-x.md",
                "phase_launched": "done",
                "wall_secs": 5,
                "cost_usd": 2.50,
            },
            {
                "prd": "00001-x.md",
                "phase_launched": "done",
                "wall_secs": 5,
                "cost_usd": None,
            },
        ]

        table = render_metrics.phase_table(rows)
        self.assertIn("| done | 3 | 20 |  | 3.75 |", table)
        self.assertEqual(table.count("3.75"), 2)
        self.assertNotIn("1.25", table)
        self.assertNotIn("2.50", table)
        self.assertNotIn("0.00", table)

        summary = render_metrics.render_metrics(rows)
        self.assertIn("| 00001-x.md | 3 | 20 | 3.75 |", summary)
        self.assertEqual(summary.count("3.75"), 2)
        self.assertNotIn("1.25", summary)
        self.assertNotIn("2.50", summary)
        self.assertNotIn("0.00", summary)

    def test_a_measured_zero_cost_renders_zero_even_beside_a_null(self) -> None:
        # 0.0 is a measurement (the item cost nothing); None is the absence of
        # one. The null-only tests above cannot tell a filter that keeps every
        # non-null value from one that keeps every truthy value, and the second
        # blanks every free row. So a free row on its own shows 0.00, and a
        # free row beside a null still shows 0.00: the null leaves the sum,
        # the zero stays in it.
        rows = [
            {
                "prd": "00001-x.md",
                "phase_launched": "done",
                "wall_secs": 10,
                "cost_usd": 0.0,
            },
            {
                "prd": "00002-y.md",
                "phase_launched": "review",
                "wall_secs": 5,
                "cost_usd": 0.0,
            },
            {
                "prd": "00002-y.md",
                "phase_launched": "review",
                "wall_secs": 2,
                "cost_usd": None,
            },
        ]

        table = render_metrics.phase_table(rows)
        self.assertIn("| done | 1 | 10 |  | 0.00 |", table)
        self.assertIn("| review | 2 | 7 |  | 0.00 |", table)
        self.assertNotIn("None", table)

        summary = render_metrics.render_metrics(rows)
        self.assertIn("| 00001-x.md | 1 | 10 | 0.00 |", summary)
        self.assertIn("| 00002-y.md | 2 | 7 | 0.00 |", summary)
        self.assertNotIn("None", summary)


class ReportEdgeTests(unittest.TestCase):
    def test_no_tasks_renders_no_implementor_data(self) -> None:
        state = _state()
        state["tasks"] = []
        self.assertIn("no implementor data", render_report.prd_section(state, [], NOW))

    def test_empty_decision_arrays_omit_their_sections(self) -> None:
        state = _state()
        for key in ("autonomous_decisions", "deferred_decisions", "doubts"):
            state[key] = []
        state["doubts_rubric_verdicts"] = []
        text = render_report.prd_section(state, [], NOW)
        for heading in (
            "### Autonomous Decisions",
            "### Escalated Decisions",
            "### Doubt Review Findings",
            "### Doubt Rubric Verdicts",
            "### Assumptions Made",
            "### Deferred to Batch End",
        ):
            self.assertNotIn(heading, text)
        self.assertIn(render_metrics.NO_METRICS, text)

    def test_source_tagged_verdicts_combine_per_rule(self) -> None:
        state = _state()
        state["doubts_rubric_verdicts"] = [
            {"rule_id": "D1", "verdict": "pass", "source": "codex"},
            {"rule_id": "D1", "verdict": "fail", "source": "fable"},
        ]
        text = render_report.prd_section(state, [], NOW)
        self.assertIn("| D1 | pass (codex) / fail (fable) |", text)

    def test_probe_from_another_batch_renders_not_run(self) -> None:
        state = _state()
        state["codex_probe"]["batch_id"] = "202601010000"
        text = render_report.prd_section(state, [], NOW)
        lines = [ln for ln in text.splitlines() if ln.startswith("codex probe:")]
        self.assertEqual(lines, ["codex probe: not run"])

    def test_hook_doctor_from_another_batch_does_not_leak_into_probe_line(
        self,
    ) -> None:
        state = _state()
        state["codex_probe"]["batch_id"] = "202601010000"
        state["codex_probe"]["hook_doctor"] = "stale: _common.py"
        text = render_report.prd_section(state, [], NOW)
        lines = [ln for ln in text.splitlines() if ln.startswith("codex probe:")]
        self.assertEqual(lines, ["codex probe: not run"])

    def test_hook_doctor_note_appends_to_the_probe_line(self) -> None:
        state = _state()
        state["codex_probe"]["hook_doctor"] = "stale: _common.py"
        text = render_report.prd_section(state, [], NOW)
        self.assertIn(
            "codex probe: healthy (backend: codex); hooks: stale: _common.py",
            text,
        )

    def test_probe_line_without_hook_doctor_key_renders_todays_exact_line(
        self,
    ) -> None:
        state = _state()
        self.assertNotIn("hook_doctor", state["codex_probe"])
        text = render_report.prd_section(state, [], NOW)
        self.assertIn("codex probe: healthy (backend: codex)\n", text)
        self.assertNotIn("; hooks:", text)

    def test_hook_doctor_ok_renders_todays_exact_line(self) -> None:
        state = _state()
        state["codex_probe"]["hook_doctor"] = "ok"
        text = render_report.prd_section(state, [], NOW)
        self.assertIn("codex probe: healthy (backend: codex)\n", text)
        self.assertNotIn("; hooks:", text)

    def test_tripped_breaker_names_the_failures_and_reroutes(self) -> None:
        state = _state()
        state["qwen_breaker"] = {
            "tripped": True,
            "after_task": "t2",
            "failed_tasks": ["t1", "t2"],
            "batch_id": state["batch"]["id"],
        }
        state["tasks"][2]["attempts"][0]["breaker_skipped"] = True
        text = render_report.prd_section(state, [], NOW)
        self.assertIn(
            "capability breaker: tripped after t2 "
            "(2 consecutive gate failures: t1, t2); 1 tasks rerouted",
            text,
        )

    def test_pipes_in_issue_text_stay_table_safe(self) -> None:
        state = _state()
        state["autonomous_decisions"] = [
            {"cycle": 1, "issue": "a | b", "action": "auto-fix"},
        ]
        self.assertIn("a \\| b", render_report.prd_section(state, [], NOW))

    def test_stalled_section_shape(self) -> None:
        text = render_report.stalled_section(
            "00040-x.md",
            "oversized_plan",
            "34 tasks",
            NOW,
        )
        self.assertIn("## 00040-x.md — STALLED (oversized_plan)", text)
        self.assertIn("- Detail: 34 tasks", text)
        self.assertIn("move back to dev/local/prds/wip/", text)


class PrdSectionTaskCountTests(unittest.TestCase):
    """Task counts come from the closing batch record or
    len(state['tasks']), never the stale state-root fields the batch
    drain wipes to 0 (R1, R2)."""

    def test_reads_counts_from_the_matching_completed_prds_record(self) -> None:
        state = _state()
        state["tasks_completed"] = 999  # stale root field: must be ignored
        state["tasks_total"] = 999
        state["tasks"] = []
        state["batch"]["completed_prds"] = [
            {
                "filename": state["prd"],
                "cycles": 2,
                "tasks_completed": 5,
                "tasks_total": 6,
            },
        ]
        text = render_report.prd_section(state, [], NOW)
        self.assertIn("- Tasks: 5/6", text)
        self.assertNotIn("- Tasks: 999/999", text)

    def test_falls_back_to_state_tasks_when_no_batch_record_matches(self) -> None:
        state = _state()
        state["tasks_completed"] = 999
        state["tasks_total"] = 999
        state["batch"]["completed_prds"] = []
        state["tasks"] = [
            {"status": "completed"},
            {"status": "completed"},
            {"status": "in_progress"},
        ]
        text = render_report.prd_section(state, [], NOW)
        self.assertIn("- Tasks: 2/3", text)
        self.assertNotIn("- Tasks: 999/999", text)

    def test_skips_bare_string_completed_prds_entries(self) -> None:
        state = _state()
        state["batch"]["completed_prds"] = [state["prd"]]  # bare string, no counts
        state["tasks"] = [{"status": "completed"}]
        text = render_report.prd_section(state, [], NOW)
        self.assertIn("- Tasks: 1/1", text)

    def test_renders_question_marks_when_no_task_data_is_available(self) -> None:
        state = _state()
        state["tasks_completed"] = 0
        state["tasks_total"] = 0
        state["batch"]["completed_prds"] = []
        state["tasks"] = []
        text = render_report.prd_section(state, [], NOW)
        self.assertIn("- Tasks: ?/?", text)
        self.assertNotIn("- Tasks: 0/0", text)


class PrdSectionCycleCountTests(unittest.TestCase):
    """The `- Cycles:` line reads state['cycle'] when that key is present
    (0 included), else the `cycles` of the batch.completed_prds record whose
    filename matches, else `?` - two real sections came out `- Cycles: ?`
    because the per-PRD reset wiped the root field before the section
    rendered."""

    def test_cycles_falls_back_to_completed_prd_record(self) -> None:
        # Three things vary so only a filename lookup can satisfy them all:
        # the reported count (no fixed constant), the PRD under render (no
        # hardcoded filename), and the list position of this PRD's own
        # record, which sits SECOND behind a decoy carrying a different
        # count (no first-entry shortcut).
        for prd, cycles, decoy_cycles in (
            ("00040-feature-x-v1.md", 4, 9),
            ("00113-another-prd-v1.md", 7, 3),
        ):
            with self.subTest(prd=prd, cycles=cycles):
                state = _state()
                del state["cycle"]  # wiped by the per-PRD reset before the render
                state["prd"] = prd
                own_record = {
                    "filename": prd,
                    "cycles": cycles,
                    "tasks_completed": 5,
                    "tasks_total": 6,
                }
                decoy = {
                    **own_record,
                    "filename": "00001-other-prd-v1.md",
                    "cycles": decoy_cycles,
                }
                state["batch"]["completed_prds"] = [decoy, own_record]
                text = render_report.prd_section(state, [], NOW)
                self.assertIn(f"\n- Cycles: {cycles}\n", text)
                self.assertNotIn(f"- Cycles: {decoy_cycles}", text)
                self.assertNotIn("- Cycles: ?", text)
                # Only the Cycles line changes: the record still drives Tasks.
                self.assertIn("- Tasks: 5/6", text)

    def test_state_cycle_wins_over_a_differing_batch_record(self) -> None:
        state = _state()
        self.assertEqual(state["cycle"], 2)
        state["batch"]["completed_prds"] = [
            {
                "filename": state["prd"],
                "cycles": 9,
                "tasks_completed": 5,
                "tasks_total": 6,
            },
        ]
        text = render_report.prd_section(state, [], NOW)
        self.assertIn("- Cycles: 2", text)
        self.assertNotIn("- Cycles: 9", text)

    def test_cycles_ignores_bare_string_and_other_prd_entries(self) -> None:
        # A legacy bare-string entry plus a dict for a DIFFERENT filename that
        # is otherwise identical in shape to this PRD's own record - same keys,
        # same value types. Only the filename tells them apart, so a render
        # that grabs any cycles-carrying entry reports 7 instead of `?`.
        state = _state()
        del state["cycle"]
        own_record_shape = {
            "filename": state["prd"],
            "cycles": 4,
            "tasks_completed": 5,
            "tasks_total": 6,
        }
        other_prd = {
            **own_record_shape,
            "filename": "00002-object-entry-v1.md",
            "cycles": 7,
        }
        state["batch"]["completed_prds"] = [
            "00001-legacy-string-entry-v1.md",
            other_prd,
        ]
        text = render_report.prd_section(state, [], NOW)
        self.assertIn("\n- Cycles: ?\n", text)
        self.assertNotIn("- Cycles: 7", text)

    def test_present_zero_state_cycle_is_not_replaced_by_the_batch_record(
        self,
    ) -> None:
        # A cycle of 0 is a real count: the key is present, so the record is
        # never consulted, even though 0 is falsy.
        state = _state()
        state["cycle"] = 0
        state["batch"]["completed_prds"] = [
            {
                "filename": state["prd"],
                "cycles": 5,
                "tasks_completed": 5,
                "tasks_total": 6,
            },
        ]
        text = render_report.prd_section(state, [], NOW)
        self.assertIn("\n- Cycles: 0\n", text)
        self.assertNotIn("- Cycles: 5", text)

    def test_cycles_of_zero_in_the_record_renders_zero_not_a_question_mark(
        self,
    ) -> None:
        state = _state()
        del state["cycle"]
        state["batch"]["completed_prds"] = [
            {
                "filename": state["prd"],
                "cycles": 0,
                "tasks_completed": 5,
                "tasks_total": 6,
            },
        ]
        text = render_report.prd_section(state, [], NOW)
        self.assertIn("\n- Cycles: 0\n", text)
        self.assertNotIn("- Cycles: ?", text)

    def test_cycles_renders_question_mark_when_the_record_lacks_cycles(self) -> None:
        state = _state()
        del state["cycle"]
        state["batch"]["completed_prds"] = [
            {"filename": state["prd"], "tasks_completed": 5, "tasks_total": 6},
        ]
        text = render_report.prd_section(state, [], NOW)
        self.assertIn("- Cycles: ?", text)


class AutonomousBlankRowTests(unittest.TestCase):
    """_autonomous drops rows where every cell is empty instead of
    rendering a blank record (R2)."""

    def test_drops_the_fully_blank_row_but_keeps_populated_ones(self) -> None:
        decisions = [
            {
                "cycle": 1,
                "issue": "Missing null check",
                "severity": "medium",
                "action": "auto-fix",
                "reason": "mechanical fix",
            },
            {},
            {
                "cycle": 2,
                "issue": "New dependency needed",
                "severity": "high",
                "action": "auto-fix",
                "reason": "research-passed",
            },
        ]
        lines = render_report._autonomous(decisions)
        text = "\n".join(lines)
        self.assertIn(
            "| 1 | Missing null check | medium | auto-fix | mechanical fix |",
            text,
        )
        self.assertIn(
            "| 2 | New dependency needed | high | auto-fix | research-passed |",
            text,
        )
        self.assertNotIn("|  |  |  |  |  |", text)
        # heading, blank, table header, separator, 2 data rows, trailing blank
        self.assertEqual(len(lines), 7)

    def test_omits_the_section_when_every_row_is_blank(self) -> None:
        self.assertEqual(render_report._autonomous([{}]), [])

    def test_partially_populated_rows_survive_the_blank_filter(self) -> None:
        # A clarification-shaped decision (question/resolution, no
        # severity/action) is not "blank" - only rows where every one of
        # the 5 cells is empty get dropped.
        decisions = [
            {
                "cycle": 1,
                "question": "Which tree gets the phases?",
                "resolution": "Operator chose the plugin tree.",
            },
        ]
        text = "\n".join(render_report._autonomous(decisions))
        self.assertIn(
            "| 1 | Which tree gets the phases? |  |  | "
            "Operator chose the plugin tree. |",
            text,
        )


class DeferredToBatchEndDispositionTests(unittest.TestCase):
    """_deferred_to_batch_end reads `disposition`, falling back to
    `reason` (R2)."""

    def test_renders_disposition_when_reason_is_absent(self) -> None:
        deferred = [
            {
                "issue": "API signature change needed",
                "severity": "high",
                "disposition": "revisit after v2 ships",
            },
        ]
        text = "\n".join(render_report._deferred_to_batch_end(deferred))
        self.assertIn(
            "| API signature change needed | high | revisit after v2 ships |",
            text,
        )

    def test_disposition_wins_over_reason_when_both_present(self) -> None:
        deferred = [
            {
                "issue": "Rename the config key",
                "severity": "medium",
                "reason": "user-visible rename",
                "disposition": "batch-end: needs a follow-up PRD",
            },
        ]
        text = "\n".join(render_report._deferred_to_batch_end(deferred))
        self.assertIn(
            "| Rename the config key | medium | batch-end: needs a follow-up PRD |",
            text,
        )
        self.assertNotIn("user-visible rename", text)

    def test_still_renders_plain_reason_when_no_disposition(self) -> None:
        # Regression: entries using only the pre-existing `reason` field
        # (no `disposition`) must keep rendering exactly as before.
        deferred = [
            {
                "issue": "Legacy entry",
                "severity": "low",
                "reason": "pre-migration shape",
            },
        ]
        text = "\n".join(render_report._deferred_to_batch_end(deferred))
        self.assertIn("| Legacy entry | low | pre-migration shape |", text)


class AuditEdgeTests(unittest.TestCase):
    def test_empty_arrays_render_no_decisions_recorded(self) -> None:
        state = _state()
        for key in ("autonomous_decisions", "deferred_decisions", "doubts"):
            state[key] = []
        text = render_audit.render_audit(state, STARTED, NOW)
        self.assertIn("no decisions recorded", text)
        self.assertIn("Autonomous: 0  |  Deferred: 0  |  Doubts: 0", text)

    def test_existing_started_is_extracted(self) -> None:
        text = render_audit.render_audit(_state(), STARTED, NOW)
        self.assertEqual(render_audit.existing_started(text), STARTED)


class StatusEdgeTests(unittest.TestCase):
    def test_flags_render_when_present(self) -> None:
        state = _state()
        state["stall_reason"] = {"stalled": "oversized_task", "task": "t9"}
        state["cap_pause_reason"] = {
            "cycle": 3,
            "cap": 3,
            "unresolved_findings": [{"issue": "x"}],
        }
        state["pause_reason"] = {"site": "reviewer_fail", "detail": "carl hung"}
        state["needs_attention"] = True
        text = status.render_status(state)
        self.assertIn("STALL:  oversized_task (task: t9)", text)
        self.assertIn("CAP-PAUSE: cycle 3 at cap 3, 1 unresolved finding(s)", text)
        self.assertIn("PAUSED: reviewer_fail — carl hung", text)
        self.assertIn("FLAG:   needs_attention", text)

    def test_empty_state_degrades_not_crashes(self) -> None:
        text = status.render_status({})
        self.assertIn("PRD:    (none)", text)


class Batch202608162223ReconstructionTests(unittest.TestCase):
    """Rendering the reconstructed archived 202608162223 state (the batch
    that exposed all five original render_report.py defects) produces
    the real historical numbers instead of zeros/blanks."""

    def test_cycles_and_tasks_come_from_the_batch_record_not_the_wiped_root(
        self,
    ) -> None:
        state = _batch_state()
        self.assertEqual(state["tasks"], [])
        self.assertEqual(state["tasks_completed"], 0)
        self.assertEqual(state["tasks_total"], 0)

        section = render_report.prd_section(state, [], NOW)
        self.assertIn("- Tasks: 7/7", section)
        self.assertNotIn("- Tasks: 0/0", section)

        summary = render_report.batch_summary(
            state,
            [],
            len(state["deferred_decisions"]),
        )
        self.assertIn("- Total cycles: 2", summary)
        # The fixture's completed_prds record carries 6 (7 raw autonomous
        # decisions minus the 1 genuinely-blank one) - not the misleading
        # 0 a missing field would sum to.
        self.assertIn("- Autonomous decisions: 6", summary)

    def test_the_blank_autonomous_decision_row_is_dropped(self) -> None:
        state = _batch_state()
        self.assertEqual(len(state["autonomous_decisions"]), 7)
        section = render_report.prd_section(state, [], NOW)
        self.assertNotIn("|  |  |  |  |  |", section)
        # 7 raw decisions minus the 1 genuinely-blank entry = 6 rendered rows.
        rows = render_report._autonomous(state["autonomous_decisions"])
        table_rows = [
            ln for ln in rows if ln.startswith("| ") and not ln.startswith("| Cycle")
        ]
        self.assertEqual(len(table_rows), 6)

    def test_deferred_to_batch_end_reason_cells_are_populated_from_disposition(
        self,
    ) -> None:
        state = _batch_state()
        self.assertEqual(len(state["deferred_decisions"]), 5)
        self.assertTrue(all("status" not in d for d in state["deferred_decisions"]))
        text = "\n".join(
            render_report._deferred_to_batch_end(state["deferred_decisions"]),
        )
        for entry in state["deferred_decisions"]:
            self.assertIn(
                f"| {entry['issue']} | {entry['severity']} | {entry['disposition']} |",
                text,
            )

    def test_escalated_decisions_section_is_omitted(self) -> None:
        # All 5 deferred entries lack a `status` key, so `_is_pending`
        # defaults them to pending - none are escalated.
        state = _batch_state()
        section = render_report.prd_section(state, [], NOW)
        self.assertNotIn("### Escalated Decisions", section)
        summary = render_report.batch_summary(
            state,
            [],
            len(state["deferred_decisions"]),
        )
        self.assertIn("- Escalated decisions: 0", summary)


if __name__ == "__main__":
    unittest.main()
