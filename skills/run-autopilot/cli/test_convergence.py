#!/usr/bin/env python3
"""Tests for the `review_converged` row builder (cli/convergence.py) and the
event-row loader beside it (render_metrics.load_event_rows), called in
process.

Fixture trees are built under a TemporaryDirectory mirroring the live layout
(`dev/local/autopilot`, `dev/local/reviews`, `dev/local/prds/wip`); review
files, PRD files and state dicts are written inline. The golden
cli/golden/metrics-render.jsonl carries six session rows and exactly one
event row (line 7).
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

CLI_DIR = Path(__file__).resolve().parent
GOLDEN = CLI_DIR / "golden"

sys.path.insert(0, str(CLI_DIR.parent))

from cli import convergence, render_metrics

PRD = "00040-feature-x-v1.md"
BATCH = "202607202320"
TS = 1784701300

REVIEW_WITH_FINDINGS = """---
head_sha: abc123
reviewers: alice,blake,bob
---
## Alice

| Consensus | Severity | Issue | File | Found By |
|-----------|----------|-------|------|----------|
| [3/3] | 🔴 Critical | XSS in input handler | src/input.ts | Alice, Bob, Carl |
| [2/3] | 🟠 High | Missing null check | src/api.ts | Alice, Bob |

Verdict: 2 findings
Tests: 12 passed, 0 failed, 0 skipped
"""

REVIEW_CONVERGED = """---
head_sha: def456
reviewers: alice,blake,bob
---
## Alice

No findings this cycle.

Verdict: converged
Tests: 12 passed, 0 failed, 0 skipped
"""

PRD_TEXT = """# PRD 00040

## Tasks

- [ ] write the row builder
- [x] add load_event_rows
- [ ] pin the goldens
  - [ ] nested sub-item does not count
- plain bullet does not count
* [ ] star bullet does not count
- [x] wire the gate
- [ ] record the run conditions
"""
PRD_CHECKBOXES = 5  # differs from _state()'s tasks_total (4) and len(tasks) (3)

SESSIONS = [
    {
        "prd": PRD,
        "batch": BATCH,
        "phase_launched": "build",
        "model": "claude-sonnet-5",
    },
    {
        "prd": PRD,
        "batch": BATCH,
        "phase_launched": "review",
        "model": "claude-haiku-4-5",
    },
    {
        "prd": PRD,
        "batch": BATCH,
        "phase_launched": "build",
        "model": "claude-opus-4-8",
    },
    {"prd": PRD, "batch": BATCH, "phase_launched": "done"},
    {
        "prd": PRD,
        "batch": BATCH,
        "phase_launched": "build",
        "model": "claude-sonnet-5",
    },
    {
        "prd": PRD,
        "batch": BATCH,
        "phase_launched": "build",
        "model": "qwen3-coder-30b",
    },
    # Decoys wear realistic claude-* names so a filter that drops the prd or
    # batch check (or keys on the model name) picks them up.
    {
        "prd": "00002-object-entry-v1.md",
        "batch": BATCH,
        "phase_launched": "build",
        "model": "claude-haiku-4-5",
    },
    {
        "prd": PRD,
        "batch": "202601010000",
        "phase_launched": "build",
        "model": "claude-sonnet-4-5",
    },
]
BUILD_MODELS = ["claude-sonnet-5", "claude-opus-4-8", "qwen3-coder-30b"]


def _state(**overrides) -> dict:
    state = {
        "prd": PRD,
        "batch": {"id": BATCH},
        "cycle": 2,
        "rework_cap": 3,
        "tasks_total": 4,
        "tasks_completed": 2,
        "tasks": [
            {
                "id": "t1",
                "status": "completed",
                "attempts": [{"model": "qwen"}, {"model": "claude-sonnet-5"}],
            },
            {
                "id": "t2",
                "status": "completed",
                "attempts": [{"model": "claude-sonnet-5"}],
            },
            {
                "id": "t3",
                "status": "completed",
                "attempts": [{"model": "claude-opus-4-8"}],
            },
        ],
        "deferred_decisions": [],
    }
    state.update(overrides)
    return state


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class ConvergenceFixtureCase(unittest.TestCase):
    """Builds `<tmp>/dev/local/{autopilot,reviews,prds/wip}` per test."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.local = Path(tmp.name) / "dev" / "local"
        self.ap_dir = self.local / "autopilot"
        self.reviews = self.local / "reviews"
        self.wip = self.local / "prds" / "wip"
        for directory in (self.ap_dir, self.reviews, self.wip):
            directory.mkdir(parents=True)

    def review_path(self, n: str) -> Path:
        return self.reviews / f"00040-feature-x-v1-review-{n}.md"


class OutcomeTests(ConvergenceFixtureCase):
    def test_cap_overflow_deferral_reads_as_cap_deferred(self) -> None:
        # The cap-overflow entry sits in the MIDDLE of three deferrals, so
        # neither a first-entry nor a last-entry shortcut can see it.
        state = _state(
            deferred_decisions=[
                {"type": "question", "issue": "Which tree gets the phases?"},
                {"type": "cap-overflow", "issue": "3 unresolved at cap 3"},
                {"type": "question", "issue": "Keep the legacy flag?"},
            ],
        )
        self.assertEqual(convergence.outcome(state), "cap_deferred")
        row = convergence.build_row(self.ap_dir, state, [], TS)
        self.assertEqual(row["outcome"], "cap_deferred")

    def test_no_cap_overflow_reads_as_converged(self) -> None:
        cases = {
            "absent": {k: v for k, v in _state().items() if k != "deferred_decisions"},
            "empty": _state(deferred_decisions=[]),
            "other_types": _state(
                deferred_decisions=[
                    {"type": "question", "issue": "x"},
                    {"issue": "no type key at all"},
                ],
            ),
        }
        for label, state in cases.items():
            with self.subTest(label):
                self.assertEqual(convergence.outcome(state), "converged")
                row = convergence.build_row(self.ap_dir, state, [], TS)
                self.assertEqual(row["outcome"], "converged")


class ReadCycleTests(ConvergenceFixtureCase):
    def test_missing_review_file_reads_null_not_zero(self) -> None:
        # Absence must not read as clean: no review file means no reviewers,
        # no verdict, no counts - never a zero findings dict.
        self.assertEqual(
            convergence.read_cycle(self.reviews, PRD, 1),
            {"cycle": 1, "reviewers": None, "verdict": None, "findings": None},
        )
        # An unreadable path (a directory where the file should be) reads
        # the same way.
        self.review_path("2").mkdir()
        self.assertEqual(
            convergence.read_cycle(self.reviews, PRD, 2),
            {"cycle": 2, "reviewers": None, "verdict": None, "findings": None},
        )
        row = convergence.build_row(self.ap_dir, _state(cycle=1), [], TS)
        self.assertEqual(
            row["cycles"],
            [{"cycle": 1, "reviewers": None, "verdict": None, "findings": None}],
        )

    def test_severity_counts_come_from_table_rows_only(self) -> None:
        # One of each mark in consolidated rows. Decoys: a 🔴 and a 🟠 in
        # prose, a legend table row without a [n/m] cell, and a [n/m] row
        # carrying none of the four marks. Any of them counted shows up as
        # a 2 in some bucket.
        _write(
            self.review_path("1"),
            """---
head_sha: abc123
reviewers: alice,blake,bob
---
## Alice

The 🔴 from cycle 0 was a false alarm; 🟠 below is only a legend.

| Mark | Meaning |
|------|---------|
| 🟠 | high |

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [3/3] | 🔴 Critical | XSS in input handler | src/input.ts | 1 | Alice, Bob, Carl |
| [2/3] | 🟠 High | Missing null check | src/api.ts | 2 | Alice, Bob |
| [1/3] | 🟡 | No test coverage | src/utils.ts | 3 | Blake |
| [1/3] | ⚪ Low | Trailing whitespace | src/x.ts | 4 | Blake |
| [1/3] | Unmarked | No severity mark | src/y.ts | 5 | Blake |

Verdict: 4 findings
""",
        )
        cycle = convergence.read_cycle(self.reviews, PRD, 1)
        self.assertEqual(
            cycle["findings"],
            {"critical": 1, "high": 1, "medium": 1, "low": 1},
        )
        self.assertEqual(cycle["verdict"], 4)

    def test_reviewers_come_from_the_frontmatter_line(self) -> None:
        _write(self.review_path("1"), REVIEW_WITH_FINDINGS)
        self.assertEqual(
            convergence.read_cycle(self.reviews, PRD, 1)["reviewers"],
            ["alice", "blake", "bob"],
        )
        # Spaces after the commas and a trailing comma: the names come back
        # stripped, with no blank entry.
        _write(
            self.review_path("2"),
            "---\nhead_sha: abc123\nreviewers: alice, blake, bob,\n---\n"
            "## Alice\n\nVerdict: converged\n",
        )
        self.assertEqual(
            convergence.read_cycle(self.reviews, PRD, 2)["reviewers"],
            ["alice", "blake", "bob"],
        )
        # No `reviewers:` line: None, not an empty list.
        _write(
            self.review_path("3"),
            "---\nhead_sha: abc123\n---\n## Alice\n\nVerdict: converged\n",
        )
        cycle = convergence.read_cycle(self.reviews, PRD, 3)
        self.assertIsNone(cycle["reviewers"])
        self.assertEqual(cycle["verdict"], "converged")

    def test_padded_and_unpadded_review_names_both_resolve(self) -> None:
        # Cycle 1 lives at the padded -review-01.md, cycle 2 at the bare
        # -review-2.md, and cycle 12 at -review-12.md. All three carry
        # different verdicts, so a wrong-file read cannot pass; in
        # particular a suffix glob (`*2.md`) sorted first lands on cycle 12
        # when asked for cycle 2.
        _write(self.review_path("01"), REVIEW_WITH_FINDINGS)
        _write(self.review_path("2"), REVIEW_CONVERGED)
        _write(
            self.review_path("12"),
            "---\nreviewers: alice\n---\n## Alice\n\n"
            "| Consensus | Severity | Issue | File | Task | Found By |\n"
            "|-----------|----------|-------|------|------|----------|\n"
            "| [1/3] | 🟡 | Naming | src/z.ts | 1 | Alice |\n\n"
            "Verdict: 1 finding\n",
        )
        first = convergence.read_cycle(self.reviews, PRD, 1)
        second = convergence.read_cycle(self.reviews, PRD, 2)
        twelfth = convergence.read_cycle(self.reviews, PRD, 12)
        self.assertEqual((first["cycle"], first["verdict"]), (1, 2))
        self.assertEqual((second["cycle"], second["verdict"]), (2, "converged"))
        self.assertEqual(second["reviewers"], ["alice", "blake", "bob"])
        self.assertEqual((twelfth["cycle"], twelfth["verdict"]), (12, 1))
        self.assertEqual(twelfth["reviewers"], ["alice"])

    def test_verdict_line_parses_converged_and_finding_counts(self) -> None:
        cases = {
            "Verdict: converged\n": "converged",
            "Verdict: 3 findings\n": 3,
            "Verdict: 1 finding\n": 1,
            "## Alice\n\nnothing to report\n": None,
            "> Verdict: 9 findings\n": None,
        }
        for tail, expected in cases.items():
            with self.subTest(tail=tail):
                _write(self.review_path("1"), "---\nreviewers: alice\n---\n" + tail)
                cycle = convergence.read_cycle(self.reviews, PRD, 1)
                self.assertEqual(cycle["verdict"], expected)

    def test_severity_marks_map_the_four_marks_in_order(self) -> None:
        self.assertEqual(
            list(convergence.SEVERITY_MARKS.items()),
            [
                ("🔴", "critical"),
                ("🟠", "high"),
                ("🟡", "medium"),
                ("⚪", "low"),
            ],
        )


class BuildRowTests(ConvergenceFixtureCase):
    def test_build_row_records_the_run_conditions(self) -> None:
        # Root task counts (4 planned, 2 completed), the task list (3 tasks,
        # 3 completed) and the PRD checkboxes (5) all differ, so each field
        # has to come from its own source.
        _write(self.review_path("1"), REVIEW_WITH_FINDINGS)
        _write(self.review_path("2"), REVIEW_CONVERGED)
        _write(self.wip / PRD, PRD_TEXT)
        row = convergence.build_row(self.ap_dir, _state(), SESSIONS, TS)
        self.assertEqual(
            row,
            {
                "event": "review_converged",
                "prd": PRD,
                "batch": BATCH,
                "cycles_to_converge": 2,
                "outcome": "converged",
                "ts": TS,
                "rework_cap": 3,
                "build_models": BUILD_MODELS,
                "attempt_tiers": ["qwen", "claude-sonnet-5", "claude-opus-4-8"],
                "tasks_planned": 4,
                "tasks_completed": 2,
                "tasks_in_prd": PRD_CHECKBOXES,
                "cycles": [
                    {
                        "cycle": 1,
                        "reviewers": ["alice", "blake", "bob"],
                        "verdict": 2,
                        "findings": {"critical": 1, "high": 1, "medium": 0, "low": 0},
                    },
                    {
                        "cycle": 2,
                        "reviewers": ["alice", "blake", "bob"],
                        "verdict": "converged",
                        "findings": {"critical": 0, "high": 0, "medium": 0, "low": 0},
                    },
                ],
            },
        )

    def test_tasks_in_prd_counts_checkbox_lines(self) -> None:
        # Five `- [ ] ` / `- [x] ` lines at column 0; the nested, plain and
        # star bullets are decoys. The count must come from the file, so the
        # states used here carry a zero or absent tasks_total and a task list
        # of a different length.
        _write(self.wip / PRD, PRD_TEXT)
        row = convergence.build_row(self.ap_dir, _state(cycle=0, tasks_total=0), [], TS)
        self.assertEqual(row["tasks_in_prd"], PRD_CHECKBOXES)
        bare = {"prd": PRD, "batch": {"id": BATCH}, "tasks": []}
        row = convergence.build_row(self.ap_dir, bare, [], TS)
        self.assertEqual(row["tasks_in_prd"], PRD_CHECKBOXES)
        # Missing wip PRD file: None, not 0.
        (self.wip / PRD).unlink()
        row = convergence.build_row(self.ap_dir, _state(cycle=0), [], TS)
        self.assertIsNone(row["tasks_in_prd"])

    def test_build_models_are_this_prds_build_sessions_only(self) -> None:
        # SESSIONS carries: three distinct build models for this prd+batch
        # (one repeated, one non-claude), a review row and a done row for
        # this prd+batch, a claude-* build row of another PRD in this batch
        # and a claude-* build row of this PRD in another batch. Only the
        # three build models survive, in first-appearance order.
        row = convergence.build_row(self.ap_dir, _state(cycle=0), SESSIONS, TS)
        self.assertEqual(row["build_models"], BUILD_MODELS)
        self.assertEqual(
            convergence.build_row(self.ap_dir, _state(cycle=0), [], TS)["build_models"],
            [],
        )

    def test_task_counts_fall_back_to_the_task_list_then_null(self) -> None:
        # Zero root counts (the batch drain wipes them) fall back to the task
        # list: 3 planned, 2 completed. cycle=0 pins an empty cycles list.
        state = _state(
            cycle=0,
            tasks_total=0,
            tasks_completed=0,
            tasks=[
                {"id": "t1", "status": "completed", "attempts": []},
                {"id": "t2", "status": "completed", "attempts": []},
                {"id": "t3", "status": "in_progress", "attempts": []},
            ],
        )
        row = convergence.build_row(self.ap_dir, state, [], TS)
        self.assertEqual((row["tasks_planned"], row["tasks_completed"]), (3, 2))
        self.assertEqual(row["attempt_tiers"], [])
        self.assertEqual(row["cycles_to_converge"], 0)
        self.assertEqual(row["cycles"], [])

        # Zero root counts and a task list with nothing completed: the
        # fallback count is 0, not null (the list exists, it is just empty
        # of completed tasks).
        state = _state(
            cycle=0,
            tasks_total=0,
            tasks_completed=0,
            tasks=[{"id": "t1", "status": "in_progress", "attempts": []}],
        )
        row = convergence.build_row(self.ap_dir, state, [], TS)
        self.assertEqual((row["tasks_planned"], row["tasks_completed"]), (1, 0))

        # No root counts and no task list: null, never 0/0.
        bare = {"prd": PRD, "batch": {"id": BATCH}, "tasks": []}
        row = convergence.build_row(self.ap_dir, bare, [], TS)
        self.assertIsNone(row["tasks_planned"])
        self.assertIsNone(row["tasks_completed"])
        self.assertIsNone(row["cycles_to_converge"])
        self.assertEqual(row["cycles"], [])
        self.assertIsNone(row["rework_cap"])
        self.assertEqual(row["attempt_tiers"], [])
        self.assertEqual(row["ts"], TS)


class LoadEventRowsTests(unittest.TestCase):
    def test_load_event_rows_returns_only_event_rows(self) -> None:
        raw = (GOLDEN / "metrics-render.jsonl").read_text(encoding="utf-8")
        self.assertEqual(raw.count('"event":'), 1)
        self.assertEqual(
            render_metrics.load_event_rows(GOLDEN / "metrics-render.jsonl"),
            [
                {
                    "event": "review_converged",
                    "prd": "00040-feature-x-v1.md",
                    "batch": "202607202320",
                    "cycles_to_converge": 2,
                    "outcome": "converged",
                    "ts": 1784701300,
                    "rework_cap": 2,
                    "build_models": ["claude-sonnet-5"],
                    "attempt_tiers": ["sonnet", "opus"],
                    "tasks_planned": 3,
                    "tasks_completed": 3,
                    "tasks_in_prd": 3,
                    "cycles": [
                        {
                            "cycle": 1,
                            "reviewers": ["alice", "blake", "bob"],
                            "verdict": 2,
                            "findings": {
                                "critical": 0,
                                "high": 1,
                                "medium": 1,
                                "low": 0,
                            },
                        },
                        {
                            "cycle": 2,
                            "reviewers": ["alice", "blake", "bob"],
                            "verdict": "converged",
                            "findings": {
                                "critical": 0,
                                "high": 0,
                                "medium": 0,
                                "low": 0,
                            },
                        },
                    ],
                },
            ],
        )

    def test_load_rows_still_drops_event_rows(self) -> None:
        rows = render_metrics.load_rows(GOLDEN / "metrics-render.jsonl")
        self.assertEqual(len(rows), 6)
        self.assertTrue(all("event" not in row for row in rows))

    def test_load_event_rows_skips_malformed_lines_and_missing_file(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "metrics.jsonl"
        # The session row carries a bare `ts` and the second event row has
        # none, so only the `event` key can tell them apart.
        first = {"event": "review_converged", "prd": "00001-x.md", "ts": 1}
        session = {"prd": "00001-x.md", "phase_launched": "build", "ts": 2}
        last = {"event": "batch_done", "prd": "00001-x.md"}
        path.write_text(
            "\n".join(
                [
                    json.dumps(first),
                    "{not json",
                    json.dumps(session),
                    json.dumps(last),
                ],
            )
            + "\n",
            encoding="utf-8",
        )
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rows = render_metrics.load_event_rows(path)
        self.assertEqual(rows, [first, last])
        self.assertTrue(err.getvalue().strip())

        self.assertEqual(
            render_metrics.load_event_rows(Path(tmp.name) / "absent.jsonl"),
            [],
        )


if __name__ == "__main__":
    unittest.main()
