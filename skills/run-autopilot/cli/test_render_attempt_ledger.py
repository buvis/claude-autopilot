#!/usr/bin/env python3
"""Tests for the attempt ledger's part in the Implementor Mix: the union of
`state.tasks[].attempts` with the ledger rows `complete-prd` drained them
into, and prd_section's own load-and-filter of that ledger file.

Split out as a new sibling of test_render.py to keep both files under the
800-line limit; render_report.py's overall render contract (golden fixtures,
the rest of prd_section, batch_summary, the CLI wiring) stays there, and is
documented in test_render.py's module docstring.
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cli import render_report

GOLDEN = Path(__file__).resolve().parent / "golden"

NOW = "2026-08-09T12:00:00Z"

# The Implementor Mix lines that come from `state` rather than from the
# attempts: the qwen exclusion histogram, the codex probe and the breaker.
STATE_DERIVED_PREFIXES = (
    "Excluded from qwen:",
    "codex probe:",
    "capability breaker:",
)


def _state_derived_lines(text: str) -> list[str]:
    return [ln for ln in text.splitlines() if ln.startswith(STATE_DERIVED_PREFIXES)]


def _state() -> dict:
    return json.loads((GOLDEN / "state-render.json").read_text(encoding="utf-8"))


def _ledger_row(
    state: dict,
    task_id: str,
    attempt: int,
    implementor: str,
    preflight_outcome: str | None = None,
) -> dict:
    """One dev/local/autopilot/ledger/attempts.jsonl row in the shape
    statectl.append_attempt_rows writes it: the envelope (batch_id, prd,
    task_id as a STRING, task metadata) wrapping the nested attempt."""
    return {
        "batch_id": state["batch"]["id"],
        "prd": state["prd"],
        "task_id": task_id,
        "task_name": f"task {task_id}",
        "task_model": "opus",
        "qwen_eligible": False,
        "task_tier_reason": "complex",
        "task_qwen_excluded_reason": "contract",
        "recorded_at": "2026-09-07T05:48:00Z",
        "attempt": {
            "attempt": attempt,
            "implementor": implementor,
            "preflight_outcome": preflight_outcome,
        },
    }


class _CountingPath(type(Path())):
    """A ledger path that records every read of itself and can start refusing
    them after a given number.

    `read_text` and `read_bytes` both go through `Path.open`, so overriding
    that one method counts a read once however the caller asks for it, and
    `fails_after` turns a file the filesystem still holds into one whose next
    read raises -- the boundary a chmod cannot express, since a chmod refuses
    every read alike.

    `reads` and `fails_after` are set by
    `PrdSectionLedgerTests._counting_ledger`.
    """

    def open(self, *args, **kwargs):
        self.reads.append(kwargs.get("mode", args[0] if args else "r"))
        if self.fails_after is not None and len(self.reads) > self.fails_after:
            raise OSError(f"read {len(self.reads)} of {self} refused")
        return super().open(*args, **kwargs)


class ImplementorMixLedgerTests(unittest.TestCase):
    """Implementor Mix counts the union of the state attempts and the
    PRD's attempt-ledger rows: complete-prd empties state.tasks[].attempts
    into the ledger before the section renders, so state alone reads as
    `no implementor data` for every PRD."""

    def test_implementor_mix_reads_ledger_when_state_tasks_empty(self) -> None:
        state = _state()
        state["tasks"] = []
        rows = [
            _ledger_row(state, "1", 1, "claude", preflight_outcome="healthy"),
            _ledger_row(state, "1", 2, "claude"),
            _ledger_row(state, "2", 1, "qwen"),
        ]
        text = "\n".join(render_report._implementor_mix(state, rows))
        self.assertNotIn("no implementor data", text)
        self.assertIn("| claude | 2 |", text)
        self.assertIn("| qwen | 1 |", text)
        self.assertIn("Qwen preflight outcomes: healthy 1", text)
        # The exclusion line still reads state.tasks only, so the rows'
        # task_qwen_excluded_reason must not conjure one.
        self.assertNotIn("Excluded from qwen:", text)

    def test_implementor_mix_dedups_state_and_ledger(self) -> None:
        state = _state()
        state["tasks"] = [
            {
                "id": 1,
                "attempts": [
                    {"attempt": 1, "implementor": "claude", "preflight_outcome": None},
                ],
            },
        ]
        rows = [
            # Same task and same attempt number as the state attempt. The
            # ledger's string "1" against the state's int 1 must still read
            # as one attempt, and the state copy is the one kept.
            _ledger_row(state, "1", 1, "qwen"),
            _ledger_row(state, "1", 2, "codex"),
            # Another task's attempt 1: the attempt NUMBER collides with the
            # state attempt but the task does not, so it is a different
            # attempt and must survive. Deduping on the number alone drops it.
            _ledger_row(state, "2", 1, "gemini"),
        ]
        text = "\n".join(render_report._implementor_mix(state, rows))
        self.assertIn("| claude | 1 |", text)
        self.assertIn("| codex | 1 |", text)
        self.assertIn("| gemini | 1 |", text)
        self.assertNotIn("| qwen |", text)

    def test_a_ledger_row_appended_twice_is_counted_once(self) -> None:
        # A replayed or re-appended ledger holds the same (task, attempt)
        # pair twice. Deduping the ledger against state only would count it
        # twice and inflate every implementor on a resumed batch.
        state = _state()
        state["tasks"] = []
        rows = [
            _ledger_row(state, "1", 1, "codex"),
            _ledger_row(state, "1", 1, "codex"),
            _ledger_row(state, "1", 2, "qwen"),
        ]
        text = "\n".join(render_report._implementor_mix(state, rows))
        self.assertIn("| codex | 1 |", text)
        self.assertIn("| qwen | 1 |", text)
        self.assertNotIn("| codex | 2 |", text)

    def test_empty_state_and_empty_ledger_render_no_implementor_data(self) -> None:
        state = _state()
        state["tasks"] = [{"id": 1, "attempts": []}]
        text = "\n".join(render_report._implementor_mix(state, []))
        self.assertIn("no implementor data", text)
        self.assertNotIn("| Implementor | Attempts |", text)

    def test_tasks_without_attempts_keep_the_state_derived_lines(self) -> None:
        # An empty union costs the report its implementor table and nothing
        # more. The exclusion, codex-probe and breaker lines are read off
        # state, not off the attempts, so they must survive the swap to the
        # placeholder -- this is the state a missing or unreadable ledger
        # leaves the section in, and dropping them makes the report strictly
        # less informative than no fix at all.
        state = _state()
        state["tasks"] = [{**task, "attempts": []} for task in state["tasks"]]
        text = "\n".join(render_report._implementor_mix(state, []))
        self.assertIn("no implementor data", text)
        self.assertNotIn("| Implementor | Attempts |", text)
        self.assertIn("Excluded from qwen: contract 1, unknown 1 (plan-time)", text)
        self.assertIn("codex probe: healthy (backend: codex)", text)
        self.assertIn("capability breaker: not tripped", text)

    def test_the_state_derived_lines_report_this_state_not_the_fixture(self) -> None:
        # The same empty-union path as the test above, driven by a DIFFERENT
        # state: a tripped breaker, a probe on another backend, another
        # exclusion reason. Restoring the three lines as literals would keep
        # printing the case above ("healthy", "not tripped"), which is worse
        # than omitting them because it reports the opposite of the truth.
        state = _state()
        state["tasks"] = [{**task, "attempts": []} for task in state["tasks"]]
        state["tasks"][0]["qwen_excluded_reason"] = "memory_pressure"
        state["codex_probe"] = {
            **state["codex_probe"],
            "verdict": "unhealthy",
            "backend": "copilot",
            "detail": "codex CLI not on PATH",
        }
        state["qwen_breaker"] = {
            **state["qwen_breaker"],
            "tripped": True,
            "after_task": "t2",
            "failed_tasks": ["t1", "t2"],
        }
        text = "\n".join(render_report._implementor_mix(state, []))
        self.assertIn("no implementor data", text)
        self.assertNotIn("Excluded from qwen: contract 1, unknown 1 (plan-time)", text)
        self.assertNotIn("codex probe: healthy (backend: codex)", text)
        self.assertNotIn("capability breaker: not tripped", text)

        # Whatever the three lines say for THIS state, they say it the same
        # way on the unchanged non-empty-union path: the same state with one
        # attempt added, nothing else touched. An empty union costs the
        # table, never the state.
        staffed = json.loads(json.dumps(state))
        staffed["tasks"][0]["attempts"] = [
            {"attempt": 1, "implementor": "claude", "preflight_outcome": None},
        ]
        with_attempts = "\n".join(render_report._implementor_mix(staffed, []))
        self.assertIn("| claude | 1 |", with_attempts)
        self.assertEqual(len(_state_derived_lines(with_attempts)), 3)
        self.assertEqual(
            _state_derived_lines(text),
            _state_derived_lines(with_attempts),
        )

    def test_each_qwen_preflight_outcome_is_counted_separately(self) -> None:
        # One healthy attempt is the one shape a hardcoded "healthy 1" can
        # survive, so the fixture carries two distinct outcomes with
        # different counts: the line is a histogram of what the attempts
        # actually reported, not a fixed string.
        state = _state()
        state["tasks"] = []
        rows = [
            _ledger_row(state, "1", 1, "qwen", preflight_outcome="healthy"),
            _ledger_row(state, "2", 1, "qwen", preflight_outcome="pi_missing"),
            _ledger_row(state, "3", 1, "qwen", preflight_outcome="pi_missing"),
        ]
        text = "\n".join(render_report._implementor_mix(state, rows))
        self.assertIn("Qwen preflight outcomes: healthy 1, pi_missing 2", text)

    def test_no_tasks_at_all_render_no_implementor_data_alone(self) -> None:
        # The boundary on the other side of the case above: with no tasks
        # there is nothing to say about exclusions, the probe or the breaker,
        # so restoring those lines unconditionally is also wrong.
        state = _state()
        state["tasks"] = []
        text = "\n".join(render_report._implementor_mix(state, []))
        self.assertIn("no implementor data", text)
        self.assertNotIn("Excluded from qwen:", text)
        self.assertNotIn("codex probe:", text)
        self.assertNotIn("capability breaker:", text)


class PrdSectionLedgerTests(unittest.TestCase):
    """prd_section loads the attempt ledger itself, keeps only the rows for
    this section's PRD and batch, and never lets a bad ledger fail the
    render."""

    def setUp(self) -> None:
        import tempfile

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.ledger = self.tmp / "attempts.jsonl"

    def _write_ledger(self, lines: list[str]) -> None:
        self.ledger.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _counting_ledger(self, fails_after: int | None = None) -> _CountingPath:
        """The ledger path, counting its own reads. `fails_after` is how many
        reads succeed before every later one raises; None never fails."""
        path = _CountingPath(str(self.ledger))
        path.reads = []
        path.fails_after = fails_after
        return path

    def test_rows_for_another_prd_or_batch_are_not_counted(self) -> None:
        state = _state()
        state["tasks"] = []
        mine = _ledger_row(state, "1", 1, "claude")
        # A second local row whose implementor is not claude: the section
        # counts every implementor the ledger names, not a claude allowlist.
        mine_qwen = _ledger_row(state, "2", 1, "qwen")
        # Two DIFFERENT local tasks sharing one attempt number AND one
        # implementor. They are two attempts; a dedup keyed on (attempt,
        # implementor) rather than on (task, attempt) collapses them to one
        # and hides a filter that lets foreign rows through.
        mine_codex_a = _ledger_row(state, "5", 1, "codex")
        mine_codex_b = _ledger_row(state, "6", 1, "codex")
        # The foreign rows reuse LOCAL task ids, so a task-id whitelist cannot
        # pass for a filter: it would keep these and drop the codex rows. Their
        # implementors appear nowhere locally, so an unfiltered ledger names
        # them in the table.
        other_prd = _ledger_row(state, "1", 2, "mistral")
        other_prd["prd"] = "00099-other-prd.md"
        other_batch = _ledger_row(state, "2", 2, "grok")
        other_batch["batch_id"] = "202601010000"
        self._write_ledger(
            [
                json.dumps(r)
                for r in (
                    mine,
                    mine_qwen,
                    mine_codex_a,
                    mine_codex_b,
                    other_prd,
                    other_batch,
                )
            ],
        )
        text = render_report.prd_section(state, [], NOW, None, self.ledger)
        self.assertIn("| claude | 1 |", text)
        self.assertIn("| qwen | 1 |", text)
        self.assertIn("| codex | 2 |", text)
        self.assertNotIn("mistral", text)
        self.assertNotIn("grok", text)

    def test_ledger_rows_join_the_state_attempts_in_one_table(self) -> None:
        # Mid-batch (any render before complete-prd drains them), state still
        # holds attempts. The ledger is a union with them, not a fallback for
        # an empty state.tasks: consulting it only when state.tasks is empty
        # would silently drop every ledger row here.
        state = _state()
        state["tasks"] = [
            {
                "id": 1,
                "status": "completed",
                "attempts": [
                    {"attempt": 1, "implementor": "claude", "preflight_outcome": None},
                ],
            },
        ]
        self._write_ledger([json.dumps(_ledger_row(state, "2", 1, "qwen"))])
        text = render_report.prd_section(state, [], NOW, None, self.ledger)
        self.assertNotIn("no implementor data", text)
        self.assertIn("| claude | 1 |", text)
        self.assertIn("| qwen | 1 |", text)
        self.assertEqual(text.count("| Implementor | Attempts |"), 1)

    def test_missing_ledger_renders_no_implementor_data_and_one_stderr_line(
        self,
    ) -> None:
        # The section still renders, without an implementor table. An empty
        # render is right, but a silent one hides a ledger the batch expected
        # to exist: the operator gets one line naming the path.
        state = _state()
        state["tasks"] = []
        missing = self.tmp / "gone.jsonl"
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            text = render_report.prd_section(state, [], NOW, None, missing)
        self.assertEqual(len(err.getvalue().splitlines()), 1)
        self.assertIn(str(missing), err.getvalue())
        self.assertIn("no implementor data", text)
        self.assertIn("## 00040-feature-x-v1.md", text)

    def test_directory_ledger_renders_no_implementor_data_and_one_stderr_line(
        self,
    ) -> None:
        self.ledger.mkdir()  # a directory where the ledger file belongs
        state = _state()
        state["tasks"] = []
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            text = render_report.prd_section(state, [], NOW, None, self.ledger)
        self.assertEqual(len(err.getvalue().splitlines()), 1)
        self.assertIn(str(self.ledger), err.getvalue())
        self.assertIn("no implementor data", text)
        self.assertIn("## 00040-feature-x-v1.md", text)

    def test_unreadable_regular_file_ledger_is_reported_once_on_stderr(self) -> None:
        # A directory at the ledger path (the case above) is not the same
        # thing as a file the process cannot open. The mechanism here is
        # chmod 000 on a real regular file holding a real row, which root
        # ignores -- so probe it and skip rather than let the suite pass
        # because the file stayed readable.
        state = _state()
        state["tasks"] = []
        self._write_ledger([json.dumps(_ledger_row(state, "1", 1, "claude"))])
        self.ledger.chmod(0o000)
        self.addCleanup(self.ledger.chmod, 0o600)
        try:
            self.ledger.read_text(encoding="utf-8")
        except OSError:
            pass
        else:
            self.skipTest("this user can read a chmod 000 file (running as root?)")

        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rows = render_report._ledger_rows(state, self.ledger)
        self.assertEqual(rows, [])
        self.assertEqual(len(err.getvalue().splitlines()), 1)
        self.assertIn(str(self.ledger), err.getvalue())

        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            text = render_report.prd_section(state, [], NOW, None, self.ledger)
        self.assertEqual(len(err.getvalue().splitlines()), 1)
        self.assertIn(str(self.ledger), err.getvalue())
        self.assertIn("no implementor data", text)
        # The unread row named claude, so a section counting it would prove
        # the file was opened after all.
        self.assertNotIn("| claude | 1 |", text)

    def test_write_only_regular_file_ledger_is_reported_once_on_stderr(self) -> None:
        # chmod 000 is not the only way a regular file resists opening. A
        # write-only file is owned by this process and still unreadable, so
        # a check that asks "are the mode bits exactly 000?" instead of
        # "can I open it?" walks straight past this one. Same root probe:
        # root ignores the mode, and a readable file would pass vacuously.
        state = _state()
        state["tasks"] = []
        self._write_ledger([json.dumps(_ledger_row(state, "1", 1, "claude"))])
        self.ledger.chmod(0o200)
        self.addCleanup(self.ledger.chmod, 0o600)
        try:
            self.ledger.read_text(encoding="utf-8")
        except OSError:
            pass
        else:
            self.skipTest("this user can read a write-only file (running as root?)")

        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rows = render_report._ledger_rows(state, self.ledger)
        self.assertEqual(rows, [])
        self.assertEqual(len(err.getvalue().splitlines()), 1)
        self.assertIn(str(self.ledger), err.getvalue())

        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            text = render_report.prd_section(state, [], NOW, None, self.ledger)
        self.assertEqual(len(err.getvalue().splitlines()), 1)
        self.assertIn(str(self.ledger), err.getvalue())
        self.assertIn("no implementor data", text)
        # The unread row named claude, so a section counting it would prove
        # the file was opened after all.
        self.assertNotIn("| claude | 1 |", text)

    def test_malformed_ledger_line_is_skipped_and_good_rows_still_count(self) -> None:
        state = _state()
        state["tasks"] = []
        self._write_ledger(
            [
                json.dumps(_ledger_row(state, "1", 1, "claude")),
                "{not json at all",
                json.dumps(_ledger_row(state, "1", 2, "claude")),
            ],
        )
        text = render_report.prd_section(state, [], NOW, None, self.ledger)
        self.assertIn("| claude | 2 |", text)
        self.assertNotIn("no implementor data", text)

    def test_the_existing_positional_calls_read_no_ledger(self) -> None:
        state = _state()
        state["tasks"] = []
        self._write_ledger([json.dumps(_ledger_row(state, "1", 1, "claude"))])
        self.assertIn("no implementor data", render_report.prd_section(state, [], NOW))
        self.assertIn(
            "no implementor data",
            render_report.prd_section(state, [], NOW, None),
        )

    def test_the_ledger_is_read_once_per_ledger_rows_call(self) -> None:
        # Proving a file is readable and then parsing it are two reads of the
        # same bytes: the whole ledger travels twice on every render, and the
        # read that matters is the second one. The rows still have to come
        # back, so a reader that opens nothing at all fails this too.
        state = _state()
        self._write_ledger(
            [
                json.dumps(_ledger_row(state, "1", 1, "claude")),
                json.dumps(_ledger_row(state, "2", 1, "qwen")),
            ],
        )
        path = self._counting_ledger()
        rows = render_report._ledger_rows(state, path)
        self.assertEqual(
            [r["attempt"]["implementor"] for r in rows],
            ["claude", "qwen"],
        )
        self.assertEqual(len(path.reads), 1, f"opened for reading: {path.reads}")

    def test_a_ledger_readable_only_once_still_yields_its_rows(self) -> None:
        # The case that separates one read from two, and the reason the second
        # read is not free: this file opens for the first read and refuses
        # every read after it. A render that proves readability and then reads
        # again for the rows loses them here, and loses them SILENTLY, because
        # the failure lands inside a loader that swallows OSError -- the
        # probe's success stands in as proof for a read that never happened.
        state = _state()
        self._write_ledger([json.dumps(_ledger_row(state, "1", 1, "claude"))])
        path = self._counting_ledger(fails_after=1)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rows = render_report._ledger_rows(state, path)
        self.assertEqual([r["attempt"]["implementor"] for r in rows], ["claude"])
        self.assertEqual(err.getvalue(), "")

    def test_a_read_failure_is_reported_once_whichever_read_fails(self) -> None:
        # Every read of this file raises, so whichever read the render performs
        # is the one that fails and the one whose failure has to be reported:
        # no rows, exactly one line naming the path, no exception, and a
        # section that still renders. A file the process cannot open at all is
        # the chmod cases above; here the refusal comes from the read itself,
        # which no mode bit and no pre-flight check can predict.
        state = _state()
        state["tasks"] = []
        self._write_ledger([json.dumps(_ledger_row(state, "1", 1, "claude"))])
        path = self._counting_ledger(fails_after=0)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rows = render_report._ledger_rows(state, path)
        self.assertEqual(rows, [])
        self.assertEqual(len(err.getvalue().splitlines()), 1)
        self.assertIn(str(path), err.getvalue())

        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            text = render_report.prd_section(state, [], NOW, None, path)
        self.assertEqual(len(err.getvalue().splitlines()), 1)
        self.assertIn(str(path), err.getvalue())
        self.assertIn("no implementor data", text)
        # The unread row named claude, so a section counting it would prove
        # the file was read after all.
        self.assertNotIn("| claude | 1 |", text)

    def test_no_ledger_path_reads_nothing_and_reports_nothing(self) -> None:
        # The one ledger condition that is not a fault: a caller with no
        # ledger to offer. Reporting it would put a line on stderr for every
        # render that never asked for a ledger in the first place.
        state = _state()
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rows = render_report._ledger_rows(state, None)
        self.assertEqual(rows, [])
        self.assertEqual(err.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
