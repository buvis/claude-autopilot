#!/usr/bin/env python3
"""Tests pinning custody.marker_entry as the one builder of the custody
marker entry: the builder is pure and exact (nine keys, capture copied
verbatim, input never aliased), and after a cap_critical stall the marker
file, the journal `recorded` row and the batch.critical_on_master mirror
all hold the one entry the builder produces. Written from the requirements
only; shares custody_testutil.py with the other custody suites.

The scalars are chosen so a writer that hand-builds or normalises the entry
cannot pass by accident: the PRD name carries uppercase letters and is not
the fixture default, the batch id is not custody_testutil.BATCH_ID, and the
detail has a leading space and a trailing newline. The builder test runs
over two scalar tuples so a builder that returns constants fails, and the
stamped-builder tests patch custody.marker_entry to stamp its detail, so a
surface assembled anywhere else shows no stamp.
"""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cli import custody, records
from cli.custody_testutil import _init_repo, _StallTestCase

PRD = "00007-Feature-Y.md"
PRD_TEXT = "# 00007 Feature Y\n\n## Problem Statement\nWe need Y.\n"
BATCH = "202609140000"
RANGE = "a" * 40 + ".." + "b" * 40
OP_ID = "a1b2c3d4e5f6"
DETAIL = " cap tripped:\ntwo CRITICAL findings.\n"
OTHER_SCALARS = ("00009-Other.md", "202601010000", "ffffffffffff", " other detail\n")
SENTINEL = "detail stamped by the patched builder"
CAPTURE_KEYS = ("commit_range", "commits", "branch", "repo_root", "git_dir")


def _capture(**overrides) -> dict:
    base = {
        "commit_range": RANGE,
        "commits": 2,
        "branch": "master",
        "repo_root": "/abs/path",
        "git_dir": None,
    }
    base.update(overrides)
    return base


def _without_event(row: dict) -> dict:
    return {k: v for k, v in row.items() if k != "event"}


class MarkerEntryBuilderTests(unittest.TestCase):
    """marker_entry is pure: the expected dict is spelled out in full so a
    swapped scalar, a filtered capture key or an invented default all fail."""

    def test_returns_exactly_the_nine_keys_with_scalars_and_capture_as_given(
        self,
    ) -> None:
        for prd, batch, op_id, detail in ((PRD, BATCH, OP_ID, DETAIL), OTHER_SCALARS):
            with self.subTest(prd=prd):
                entry = custody.marker_entry(prd, batch, op_id, detail, _capture())

                self.assertEqual(
                    entry,
                    {
                        "prd": prd,
                        "batch": batch,
                        "op_id": op_id,
                        "detail": detail,
                        "commit_range": RANGE,
                        "commits": 2,
                        "branch": "master",
                        "repo_root": "/abs/path",
                        "git_dir": None,
                    },
                )
                self.assertEqual(len(entry), 9)

    def test_returns_a_new_dict_and_leaves_the_capture_unmodified(self) -> None:
        capture = _capture()
        snapshot = copy.deepcopy(capture)

        entry = custody.marker_entry(PRD, BATCH, OP_ID, DETAIL, capture)

        self.assertIsNot(entry, capture)
        self.assertEqual(capture, snapshot, "the builder never writes into its input")
        entry["commits"] = 99
        entry["extra"] = "x"
        self.assertEqual(
            capture,
            snapshot,
            "mutating the result must not reach the capture",
        )

    def test_copies_an_extra_capture_key_through_verbatim(self) -> None:
        entry = custody.marker_entry(PRD, BATCH, OP_ID, DETAIL, _capture(extra="kept"))

        self.assertEqual(entry["extra"], "kept")
        self.assertEqual(len(entry), 10, "the builder copies, never filters")

    def test_invents_no_default_for_a_missing_capture_key(self) -> None:
        for key in CAPTURE_KEYS:
            with self.subTest(key):
                capture = {k: v for k, v in _capture().items() if k != key}

                entry = custody.marker_entry(PRD, BATCH, OP_ID, DETAIL, capture)

                self.assertNotIn(key, entry)
                self.assertEqual(len(entry), 8)


class CapCriticalStallEntryTests(_StallTestCase):
    """cap_critical stalls of PRD (not the fixture default) in batch BATCH
    (not BATCH_ID) against <root>/repo (three commits, master) with
    state.work_start_sha at the first sha, so the captured range is
    <first>..<third> with two commits."""

    def setUp(self) -> None:
        super().setUp()
        self.repo = self.root / "repo"
        self.shas = _init_repo(self.repo)
        self.state = self._sample_state(
            prd=PRD,
            batch={"id": BATCH, "completed_prds": [], "parks_consecutive": 1},
            work_start_sha=self.shas[0],
            repo_root=str(self.repo),
        )

    # -- fixture views ------------------------------------------------------
    def _range(self) -> str:
        return f"{self.shas[0]}..{self.shas[2]}"

    def _repo_capture(self) -> dict:
        return {
            "commit_range": self._range(),
            "commits": 2,
            "branch": "master",
            "repo_root": str(self.repo),
            "git_dir": None,
        }

    def _seed_hold_prd(self) -> None:
        """For a direct _record_stall_custody call (no do_stall): the hold
        PRD that step 4b rewrites must already exist."""
        hold_dir = self.prds_dir / "hold"
        hold_dir.mkdir()
        (hold_dir / PRD).write_text(PRD_TEXT, encoding="utf-8")

    def _stall(self) -> dict:
        """The single stall record in this batch's deferred JSON."""
        items = self._deferred_items(batch_id=BATCH)
        self.assertEqual(len(items), 1)
        return items[0]

    def _marker_entries(self) -> list:
        return custody.load_marker(self.autopilot_dir / custody.MARKER_NAME)

    def _recorded_rows(self) -> list:
        return [
            _without_event(row)
            for row in custody.read_journal(self.autopilot_dir)
            if row.get("event") == "recorded"
        ]

    def _mirror(self) -> list:
        return self._state()["batch"]["critical_on_master"]

    # -- calls under test ---------------------------------------------------
    def _record_stall_custody(self, op_id: str) -> tuple:
        return records._record_stall_custody(
            autopilot_dir=self.autopilot_dir,
            prds_dir=self.prds_dir,
            current=self.state,
            prd=PRD,
            site="cap_critical",
            detail=DETAIL,
            op_id=op_id,
            capture=self._repo_capture(),
        )

    def _stamping(self):
        """Patch context: custody.marker_entry still builds the real entry
        but stamps its detail with SENTINEL, so only a surface assembled
        through the builder shows the stamp."""
        real = custody.marker_entry

        def stamped(*args, **kwargs) -> dict:
            return {**real(*args, **kwargs), "detail": SENTINEL}

        return mock.patch.object(custody, "marker_entry", stamped)

    # -- tests --------------------------------------------------------------
    def test_marker_journal_and_mirror_hold_the_one_entry_the_builder_produces(
        self,
    ) -> None:
        self._put_in_wip(prd=PRD, content=PRD_TEXT)
        self._write_state(self.state)

        rc = self._do_stall(prd=PRD, site="cap_critical", detail=DETAIL)

        self.assertEqual(rc, 0)
        stall = self._stall()
        expected = custody.marker_entry(
            prd=PRD,
            batch=BATCH,
            op_id=stall["op_id"],
            detail=DETAIL,
            capture={k: stall[k] for k in CAPTURE_KEYS},
        )
        # Not a vacuous match: the fixture's real range and count are in it.
        self.assertEqual(expected["commit_range"], self._range())
        self.assertEqual(expected["commits"], 2)
        self.assertEqual(expected["branch"], "master")
        self.assertEqual(expected["repo_root"], str(self.repo))

        self.assertEqual(self._marker_entries(), [expected])
        self.assertEqual(self._recorded_rows(), [expected])
        self.assertEqual(self._mirror(), [expected])

    def test_record_stall_custody_returns_the_entry_the_marker_then_holds(
        self,
    ) -> None:
        self._seed_hold_prd()

        entry, rc = self._record_stall_custody(OP_ID)

        self.assertIsNone(rc)
        expected = custody.marker_entry(PRD, BATCH, OP_ID, DETAIL, self._repo_capture())
        self.assertEqual(entry, expected)
        self.assertEqual(self._marker_entries(), [expected])
        self.assertEqual(self._recorded_rows(), [expected])

    def test_stall_marker_journal_and_mirror_all_carry_the_builders_stamp(
        self,
    ) -> None:
        self._put_in_wip(prd=PRD, content=PRD_TEXT)
        self._write_state(self.state)

        with self._stamping():
            rc = self._do_stall(prd=PRD, site="cap_critical", detail=DETAIL)

        self.assertEqual(rc, 0)
        stall = self._stall()
        expected = {
            **custody.marker_entry(
                PRD,
                BATCH,
                stall["op_id"],
                DETAIL,
                {k: stall[k] for k in CAPTURE_KEYS},
            ),
            "detail": SENTINEL,
        }
        self.assertEqual(self._marker_entries(), [expected])
        self.assertEqual(self._recorded_rows(), [expected])
        self.assertEqual(self._mirror(), [expected])

    def test_record_stall_custody_returns_and_stores_the_builders_stamp(
        self,
    ) -> None:
        self._seed_hold_prd()

        with self._stamping():
            entry, rc = self._record_stall_custody(OP_ID)

        self.assertIsNone(rc)
        expected = {
            **custody.marker_entry(PRD, BATCH, OP_ID, DETAIL, self._repo_capture()),
            "detail": SENTINEL,
        }
        self.assertEqual(entry, expected)
        self.assertEqual(self._marker_entries(), [expected])
        self.assertEqual(self._recorded_rows(), [expected])


if __name__ == "__main__":
    unittest.main()
