#!/usr/bin/env python3
"""Tests pinning custody.py's fail-loud and input-validation behaviors: a
cap_critical stall whose custody write fails prints its exit-9 reason on
stderr, marker entries and journal rows must carry a string op_id
(CustodyError, never a KeyError traceback), and refresh_hold_prd renders
a multi-line detail as one notice line. Written from the requirements
only; shares custody_testutil.py with the other custody suites.
"""

from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cli import custody
from cli.custody_testutil import (
    _GIT_ENV,
    BATCH_ID,
    NOTICE_PREFIX,
    _init_repo,
    _StallTestCase,
)

CLI_MAIN = Path(__file__).resolve().parent / "__main__.py"
RANGE = "a" * 40 + ".." + "b" * 40
STDERR_PREFIX = "autopilot: cap_critical custody write failed: "
PRD_TEXT = "# 00004 Feature X\n\n## Problem Statement\nWe need X.\n"
TWO_LINE_DETAIL = "line one\nline two"
FRESH_BLOCK = (
    f"---\ncritical_on_master: {RANGE}\n"
    f"ledger: deferred/{BATCH_ID}-deferred.json#a1b2c3d4e5f6\n---\n"
)
ONE_LINE_NOTICE = (
    f"{NOTICE_PREFIX} line one line two Commits {RANGE} (2) are live on master. "
    "Resolve with autopilot custody resolve."
)


def _entry(op_id: str, **overrides) -> dict:
    """A marker entry with every required key."""
    base = {
        "prd": "00004-feature-x.md",
        "batch": BATCH_ID,
        "op_id": op_id,
        "commit_range": RANGE,
        "commits": 2,
        "detail": "cap tripped.",
        "repo_root": "/abs/path",
        "git_dir": None,
        "branch": "master",
    }
    base.update(overrides)
    return base


def _without_op_id(row: dict) -> dict:
    return {k: v for k, v in row.items() if k != "op_id"}


def _run(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CLI_MAIN), *args],
        capture_output=True,
        text=True,
        cwd=str(cwd),
        env=_GIT_ENV,
        timeout=120,
    )


def _notice_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.startswith(NOTICE_PREFIX)]


class CapCriticalStallFailsLoudTests(_StallTestCase):
    """cap_critical stalls against <root>/repo (three commits, master) with
    the PRD in wip and state.work_start_sha at the first sha, so every
    custody write is reachable and only the fixture decides which fails."""

    def setUp(self) -> None:
        super().setUp()
        self.repo = self.root / "repo"
        self.shas = _init_repo(self.repo)
        self._put_in_wip(content=PRD_TEXT)
        self._write_state(
            self._sample_state(work_start_sha=self.shas[0], repo_root=str(self.repo)),
        )

    def _stall(self, **kwargs) -> tuple[int, str]:
        """Run the cap_critical stall in-process; returns (rc, stderr)."""
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rc = self._do_stall(site="cap_critical", **kwargs)
        return rc, err.getvalue()

    def _hold_text(self) -> str:
        return (self.prds_dir / "hold" / self.PRD).read_text(encoding="utf-8")

    def _assert_loud_exit_9(self, rc: int, err: str, *needles: str) -> None:
        """rc 9 and exactly one prefixed stderr line whose tail is the
        underlying error's own text: every needle must appear in it."""
        self.assertEqual(rc, 9, err)
        lines = err.splitlines()
        self.assertEqual(len(lines), 1, f"exactly one stderr line, got {err!r}")
        self.assertTrue(lines[0].startswith(STDERR_PREFIX), err)
        self.assertTrue(err.endswith("\n"), err)
        reason = lines[0][len(STDERR_PREFIX) :]
        for needle in needles:
            self.assertIn(needle, reason, "the tail is the underlying error's text")

    def test_exit_9_prints_one_stderr_line_naming_the_failed_custody_write(
        self,
    ) -> None:
        # A regular file where the ledger directory belongs: the journal
        # append cannot create its directory, so the custody write fails
        # with the OS's own "[Errno 17] File exists: '<ledger>'".
        ledger = self.autopilot_dir / "ledger"
        ledger.write_text("occupied", encoding="utf-8")

        rc, err = self._stall()

        self._assert_loud_exit_9(rc, err, "File exists", str(ledger))

    def test_exit_9_names_the_corrupt_marker_that_could_not_be_read(self) -> None:
        # Not an OSError: the marker read raises CustodyError, which must
        # be just as loud as a failed directory create.
        marker = self.autopilot_dir / custody.MARKER_NAME
        marker.write_text("not json", encoding="utf-8")

        rc, err = self._stall()

        self._assert_loud_exit_9(rc, err, "marker", str(marker))

    def test_exit_9_names_the_git_config_write_that_could_not_take_its_lock(
        self,
    ) -> None:
        # A stale config.lock: the read-only range capture still succeeds,
        # only the locator write (git config --local) fails, via git's own
        # "could not lock config file" text.
        (self.repo / ".git" / "config.lock").write_text("", encoding="utf-8")

        rc, err = self._stall()

        self._assert_loud_exit_9(rc, err, "could not lock config file")

    def test_a_successful_stall_prints_nothing_to_stderr(self) -> None:
        rc, err = self._stall()

        self.assertEqual(rc, 0)
        self.assertEqual(err, "")

    def test_a_two_line_detail_stays_verbatim_in_the_marker_but_renders_one_notice_line(
        self,
    ) -> None:
        rc, err = self._stall(detail=TWO_LINE_DETAIL)

        self.assertEqual(rc, 0, err)
        entries = custody.load_marker(self.autopilot_dir / custody.MARKER_NAME)
        self.assertEqual(
            [e["detail"] for e in entries],
            [TWO_LINE_DETAIL],
            "the marker entry itself is not normalised",
        )
        hold = self._hold_text()
        notice = _notice_lines(hold)
        self.assertEqual(len(notice), 1, hold)
        self.assertIn(" line one line two Commits ", notice[0])
        self.assertNotIn("\nline two", hold)


class MarkerOpIdTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.autopilot_dir = Path(self._tmp.name) / "autopilot"
        self.autopilot_dir.mkdir()
        self.marker = self.autopilot_dir / custody.MARKER_NAME

    def _write_marker(self, entries: list[dict]) -> None:
        self.marker.write_text(json.dumps({"entries": entries}), encoding="utf-8")

    def test_load_marker_raises_custody_error_for_an_entry_without_a_string_op_id(
        self,
    ) -> None:
        cases = {
            "absent": _without_op_id(_entry("x")),
            "int": {**_entry("x"), "op_id": 7},
            "null": {**_entry("x"), "op_id": None},
        }
        for label, bad in cases.items():
            with self.subTest(label):
                # A valid entry first: every entry is checked, not just the head.
                self._write_marker([_entry("ok"), bad])
                with self.assertRaises(custody.CustodyError) as ctx:
                    custody.load_marker(self.marker)
                # The reason names the field and the file, never an empty message.
                self.assertIn("op_id", str(ctx.exception))
                self.assertIn(str(self.marker), str(ctx.exception))

    def test_pending_raises_custody_error_for_a_marker_entry_without_op_id(
        self,
    ) -> None:
        self._write_marker([_without_op_id(_entry("x"))])

        with self.assertRaises(custody.CustodyError) as ctx:
            custody.pending(self.autopilot_dir)
        self.assertIn("op_id", str(ctx.exception))


class JournalOpIdTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def _dir_with_rows(self, label: str, rows: list[dict]) -> Path:
        """A fresh autopilot dir whose journal holds exactly `rows`."""
        autopilot_dir = self.root / label
        journal = autopilot_dir / custody.JOURNAL_REL
        journal.parent.mkdir(parents=True)
        journal.write_text(
            "".join(json.dumps(row) + "\n" for row in rows),
            encoding="utf-8",
        )
        return autopilot_dir

    def test_rows_without_a_string_op_id_raise_custody_error_never_key_or_type_error(
        self,
    ) -> None:
        resolving = {
            "event": "resolving",
            "op_id": "ok",
            "choice": "keep",
            "head_before": "c" * 40,
        }
        resolved = {
            "event": "resolved",
            "op_id": "ok",
            "prd": "00004-feature-x.md",
            "choice": "keep",
            "at": "t",
        }
        cases = {
            "recorded-absent": _without_op_id({"event": "recorded", **_entry("x")}),
            "recorded-int": {"event": "recorded", **_entry("x"), "op_id": 7},
            "resolving-absent": _without_op_id(resolving),
            "resolving-null": {**resolving, "op_id": None},
            "resolved-absent": _without_op_id(resolved),
            "resolved-int": {**resolved, "op_id": 7},
        }
        for label, row in cases.items():
            with self.subTest(label):
                # The bad row sits on journal line 2, after one valid row.
                autopilot_dir = self._dir_with_rows(
                    label,
                    [{"event": "recorded", **_entry("ok")}, row],
                )
                with self.assertRaises(custody.CustodyError) as ctx:
                    custody.unresolved_from_journal(autopilot_dir)
                self.assertIn("op_id", str(ctx.exception))
                self.assertIn("line 2", str(ctx.exception))
                with self.assertRaises(custody.CustodyError) as ctx:
                    custody.pending(autopilot_dir)
                self.assertIn("op_id", str(ctx.exception))
                self.assertIn("line 2", str(ctx.exception))


class CustodyListCliTests(_StallTestCase):
    def test_custody_list_exits_9_without_a_traceback_for_a_marker_entry_without_op_id(
        self,
    ) -> None:
        self._write_state(self._sample_state(schema_version=1, phases_completed=[]))
        (self.autopilot_dir / custody.MARKER_NAME).write_text(
            json.dumps({"entries": [_without_op_id(_entry("x"))]}),
            encoding="utf-8",
        )

        proc = _run("custody", "list", "--state", str(self.state_path), cwd=self.root)

        self.assertEqual(proc.returncode, 9, proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertNotIn("KeyError", proc.stderr)
        self.assertIn("op_id", proc.stderr, "the exit-9 line names the missing field")


class RefreshHoldPrdMultiLineDetailTests(unittest.TestCase):
    """refresh_hold_prd is pure; the expected text is spelled out in full so
    the one-line notice is proven byte for byte."""

    def _refresh(self, text: str, detail: str) -> str:
        return custody.refresh_hold_prd(text, _entry("a1b2c3d4e5f6", detail=detail))

    def test_renders_a_two_line_detail_as_exactly_one_notice_line(self) -> None:
        entry = _entry("a1b2c3d4e5f6", detail=TWO_LINE_DETAIL)

        out = custody.refresh_hold_prd(PRD_TEXT, entry)

        self.assertEqual(_notice_lines(out), [ONE_LINE_NOTICE], out)
        self.assertEqual(
            out,
            FRESH_BLOCK
            + "# 00004 Feature X\n\n## Problem Statement\n\n"
            + ONE_LINE_NOTICE
            + "\n\nWe need X.\n",
        )
        self.assertEqual(
            entry["detail"],
            TWO_LINE_DETAIL,
            "only the rendered notice is normalised, never the entry",
        )

    def test_collapses_every_whitespace_run_in_the_detail_to_one_space(self) -> None:
        # Tab/space runs and a lone CR get their own cases: a collapse that
        # only fires when a line feed is present must fail on them.
        cases = {
            "mixed, with line feeds": (
                "cap\t\ttripped:\n\n  two   CRITICAL\r\nfindings.",
                " cap tripped: two CRITICAL findings. Commits ",
            ),
            "tabs and spaces, no line feed": (
                "cap\t\ttripped   twice",
                " cap tripped twice Commits ",
            ),
            "lone carriage return": ("a\rb", " a b Commits "),
        }
        for label, (detail, expected) in cases.items():
            with self.subTest(label):
                out = self._refresh(PRD_TEXT, detail)

                notice = _notice_lines(out)
                self.assertEqual(len(notice), 1, out)
                self.assertIn(expected, notice[0])
                self.assertNotIn("\r", out)
                self.assertNotIn("\t", out)
                self.assertEqual(
                    out.count("\n"),
                    (FRESH_BLOCK + PRD_TEXT).count("\n") + 3,
                    "the notice adds its own line plus one blank line on each side",
                )

    def test_a_retry_with_a_two_line_detail_is_idempotent(self) -> None:
        once = self._refresh(PRD_TEXT, TWO_LINE_DETAIL)

        twice = self._refresh(once, TWO_LINE_DETAIL)

        self.assertEqual(twice, once)
        self.assertEqual(once.count(NOTICE_PREFIX), 1)
        self.assertEqual(once.count("line two"), 1)


if __name__ == "__main__":
    unittest.main()
