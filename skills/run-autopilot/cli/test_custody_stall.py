#!/usr/bin/env python3
"""Tests for the cap_critical branch of records.do_stall (custody step 4b).

Written from the design contract only. Git-backed tests build a REAL
repository (git init plus real commits) in a temp dir; the notifier
(cli.notify_out.notify) is the one external boundary that is patched.

Fixture layout mirrors test_records_stall.py: <root>/prds/wip (pre-created),
<root>/prds/hold (absent), <root>/autopilot/state.json, plus <root>/repo with
three commits whose first sha is state.work_start_sha, so a cap_critical stall
captures "<first>..<third>" with two commits on branch master.
"""

from __future__ import annotations

import contextlib
import copy
import io
import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cli import custody
from cli.custody_testutil import (
    BATCH_ID,
    DECISIONS,
    NOTICE_PREFIX,
    _StallTestCase,
    _commit,
    _init_bare_repo,
    _init_repo,
    _locator,
)

FAILPOINT_ENV = "_AUTOPILOT_CLI_FAILPOINT"
PRD_TEXT = "# 00004 Feature X\n\n## Problem Statement\nWe need X.\n"
CAPTURE_KEYS = ("commit_range", "commits", "branch", "repo_root", "git_dir")


def _without(state: dict, *keys: str) -> dict:
    """A shallow copy of `state` with `keys` dropped, for equality checks
    that must ignore write-boundary bookkeeping fields (stall_op,
    schema_version)."""
    return {k: v for k, v in state.items() if k not in keys}


class CapCriticalStallTests(_StallTestCase):
    """cap_critical stalls against <root>/repo (three commits, branch master);
    state.work_start_sha is the first sha, so the captured range is
    <first>..<third> with two commits."""

    def setUp(self) -> None:
        super().setUp()
        self.repo = self.root / "repo"
        self.shas = _init_repo(self.repo)

    # -- expectations -----------------------------------------------------
    def _range(self) -> str:
        return f"{self.shas[0]}..{self.shas[2]}"

    def _critical_state(self, **overrides) -> dict:
        return self._sample_state(
            work_start_sha=self.shas[0],
            repo_root=str(self.repo),
            **overrides,
        )

    def _stall_entry(self, op_id: str, **overrides) -> dict:
        entry = {
            "prd": self.PRD,
            "batch": BATCH_ID,
            "op_id": op_id,
            "commit_range": self._range(),
            "commits": 2,
            "detail": "detail text",
            "repo_root": str(self.repo),
            "git_dir": None,
            "branch": "master",
        }
        entry.update(overrides)
        return entry

    def _expected_stall_op(self, op_id: str) -> dict:
        return {
            "op_id": op_id,
            "prd": self.PRD,
            "site": "cap_critical",
            "detail": "detail text",
            "commit_range": self._range(),
            "commits": 2,
            "branch": "master",
            "repo_root": str(self.repo),
            "git_dir": None,
        }

    def _expected_hold(
        self,
        op_id: str,
        *,
        batch: str = BATCH_ID,
        commit_range: str | None = None,
        commits: int = 2,
        branch: str = "master",
    ) -> str:
        rng = commit_range or self._range()
        return (
            "---\n"
            f"critical_on_master: {rng}\n"
            f"ledger: deferred/{batch}-deferred.json#{op_id}\n"
            "---\n"
            "# 00004 Feature X\n\n## Problem Statement\n\n"
            f"> **Custody (cap_critical, batch {batch}):** detail text "
            f"Commits {rng} ({commits}) are live on {branch}. "
            "Resolve with autopilot custody resolve.\n\n"
            "We need X.\n"
        )

    # -- observations -----------------------------------------------------
    def _marker_path(self) -> Path:
        return self.autopilot_dir / "critical-on-master"

    def _marker_entries(self) -> list:
        return json.loads(self._marker_path().read_text(encoding="utf-8"))["entries"]

    def _journal_rows(self) -> list:
        path = self.autopilot_dir / "ledger" / "custody.jsonl"
        if not path.exists():
            return []
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def _hold_text(self, prd: str | None = None) -> str:
        return (self.prds_dir / "hold" / (prd or self.PRD)).read_text(
            encoding="utf-8",
        )

    def _run_with_failpoint(self, boundary: str) -> None:
        with mock.patch.dict(os.environ, {FAILPOINT_ENV: boundary}):
            with self.assertRaises(RuntimeError) as ctx:
                self._do_stall(site="cap_critical")
        self.assertEqual(str(ctx.exception), f"failpoint: {boundary}")

    def _assert_intent_retained_without_reset(self, before: dict) -> str:
        partial = self._state()
        self.assertIn("stall_op", partial)
        op_id = partial["stall_op"]["op_id"]
        self.assertEqual(partial["stall_op"], self._expected_stall_op(op_id))
        self.assertEqual(
            _without(partial, "stall_op", "schema_version"),
            _without(before, "schema_version"),
            "no reset may apply while the custody step is incomplete",
        )
        self.assertNotIn("critical_on_master", partial["batch"])
        return op_id

    # -- runs -------------------------------------------------------------
    def _run_critical_stall(
        self, state: dict, prd: str | None = None
    ) -> tuple[str, list]:
        """Put the PRD in wip/, write `state`, run a cap_critical stall and
        assert it stalled (rc 0, PRD moved from wip/ to hold/). Returns the
        stall record's op_id and the deferred items of the state's batch."""
        self._put_in_wip(prd=prd, content=PRD_TEXT)
        self._write_state(state)
        rc = self._do_stall(prd=prd, site="cap_critical")
        self.assertEqual(rc, 0)
        self.assertTrue(self._in_hold(prd))
        self.assertFalse(self._in_wip(prd))
        items = self._deferred_items(state["batch"]["id"])
        return items[0]["op_id"], items

    def _record_critical(self, state: dict, op_id: str) -> int | None:
        """custody.record_critical called directly (no do_stall) with this
        fixture's capture, to exercise its retry path."""
        return custody.record_critical(
            autopilot_dir=self.autopilot_dir,
            prds_dir=self.prds_dir,
            current=state,
            prd=self.PRD,
            op_id=op_id,
            detail="detail text",
            capture={
                "commit_range": self._range(),
                "commits": 2,
                "branch": "master",
                "repo_root": str(self.repo),
                "git_dir": None,
            },
        )

    # -- tests --------------------------------------------------------------
    def test_stall_captures_range_writes_marker_journal_locator_mirror_hold_refresh_and_notifies_once(
        self,
    ) -> None:
        op_id, items = self._run_critical_stall(self._critical_state())
        self.assertEqual(len(items), 1)
        self.assertEqual(
            items[0],
            {
                "type": "stall",
                "site": "cap_critical",
                "detail": "detail text",
                "op_id": op_id,
                "prd": self.PRD,
                "commit_range": self._range(),
                "commits": 2,
                "branch": "master",
                "repo_root": str(self.repo),
                "git_dir": None,
            },
        )

        entry = self._stall_entry(op_id)
        self.assertEqual(self._marker_entries(), [entry])
        self.assertEqual(self._journal_rows(), [{"event": "recorded", **entry}])

        locator = _locator("-C", str(self.repo))
        self.assertIsNotNone(locator)
        self.assertTrue(Path(locator).is_absolute())
        self.assertEqual(Path(locator).resolve(), self._marker_path().resolve())

        self.assertEqual(self._hold_text(), self._expected_hold(op_id))
        self.assertEqual(self.notify.call_count, 1)
        self.assertEqual(
            self.notify.call_args,
            mock.call(
                "autopilot 🔒 custody",
                f"{self.PRD}: commits {self._range()} (2) live on master; run autopilot custody resolve",
            ),
        )

        final = self._state()
        self.assertEqual(final["batch"]["critical_on_master"], [entry])
        self.assertEqual(final["batch"]["id"], BATCH_ID)
        self.assertNotIn("stall_op", final)
        self.assertNotIn("tasks", final, "reset_prd_fields must have run")
        self.assertNotIn("work_start_sha", final)
        self.assertNotIn("repo_root", final)
        self.assertEqual(final["cycle"], 1)
        self.assertEqual(final["phase"], "build")

    def test_exit_2_when_capture_fails_leaves_state_prd_and_hold_untouched(
        self,
    ) -> None:
        cases = {"missing": None, "not hex": "not-a-sha", "unknown sha": "f" * 40}
        for label, base in cases.items():
            with self.subTest(label):
                self._put_in_wip(content=PRD_TEXT)
                state = self._critical_state()
                if base is None:
                    del state["work_start_sha"]
                else:
                    state["work_start_sha"] = base
                self._write_state(state)
                raw_before = self.state_path.read_bytes()
                err = io.StringIO()

                with contextlib.redirect_stderr(err):
                    rc = self._do_stall(site="cap_critical")

                self.assertEqual(rc, 2)
                self.assertIn(
                    "autopilot: cap_critical custody capture failed: ",
                    err.getvalue(),
                )
                self.assertEqual(
                    self.state_path.read_bytes(),
                    raw_before,
                    "state must be byte-unchanged",
                )
                self.assertTrue(self._in_wip())
                self.assertFalse(
                    (self.prds_dir / "hold").exists(),
                    "capture fails before mkdir hold",
                )
                self.assertFalse(self._marker_path().exists())
                self.assertEqual(self._deferred_items(), [])
                self.assertEqual(self.notify.call_count, 0)

    def test_exit_2_for_a_half_written_cap_critical_intent_leaves_state_and_prd_untouched(
        self,
    ) -> None:
        complete = self._expected_stall_op("0123456789ab")
        cases = {
            "missing commits": {k: v for k, v in complete.items() if k != "commits"},
            "short range": {**complete, "commit_range": "abc..def"},
        }
        for label, stall_op in cases.items():
            with self.subTest(label):
                self._put_in_wip(content=PRD_TEXT)
                self._write_state(self._critical_state(stall_op=stall_op))
                raw_before = self.state_path.read_bytes()
                err = io.StringIO()

                with contextlib.redirect_stderr(err):
                    rc = self._do_stall(site="cap_critical")

                self.assertEqual(rc, 2)
                self.assertIn(
                    "autopilot: malformed stall_op in state; refusing",
                    err.getvalue(),
                )
                self.assertEqual(
                    self.state_path.read_bytes(),
                    raw_before,
                    "state must be byte-unchanged",
                )
                self.assertTrue(self._in_wip())
                self.assertFalse(self._in_hold())
                self.assertEqual(self._deferred_items(), [])
                self.assertFalse(self._marker_path().exists())

    def test_retry_after_head_advances_reuses_the_persisted_capture_and_never_recaptures(
        self,
    ) -> None:
        self._put_in_wip(content=PRD_TEXT)
        self._write_state(self._critical_state())

        self._run_with_failpoint("after-intent-before-move")

        partial = self._state()
        op_id = partial["stall_op"]["op_id"]
        self.assertEqual(partial["stall_op"], self._expected_stall_op(op_id))
        self.assertTrue(self._in_wip())

        new_head = _commit(self.repo, "later.txt")
        self.assertNotEqual(new_head, self.shas[2])

        rc = self._do_stall(site="cap_critical")

        self.assertEqual(rc, 0)
        entry = self._stall_entry(op_id)
        self.assertEqual(
            self._marker_entries(),
            [entry],
            "the ORIGINAL range and count must survive the retry",
        )
        items = self._deferred_items()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["op_id"], op_id)
        self.assertEqual(items[0]["commit_range"], self._range())
        self.assertEqual(items[0]["commits"], 2)
        self.assertEqual(self._journal_rows(), [{"event": "recorded", **entry}])
        self.assertEqual(self._state()["batch"]["critical_on_master"], [entry])
        self.assertEqual(self._hold_text(), self._expected_hold(op_id))

    def test_migrates_pending_deferred_decisions_before_the_reset_drops_them(
        self,
    ) -> None:
        self._put_in_wip(content=PRD_TEXT)
        self._write_state(
            self._critical_state(deferred_decisions=copy.deepcopy(DECISIONS)),
        )

        rc = self._do_stall(site="cap_critical")

        self.assertEqual(rc, 0)
        items = self._deferred_items()
        self.assertEqual(items[0]["type"], "stall")
        op_id = items[0]["op_id"]
        self.assertEqual(
            {i["op_id"]: i for i in items[1:]},
            {
                f"{op_id}-dd0": {
                    "question": "q0",
                    "status": "pending",
                    "cycle": 1,
                    "type": "deferred_decision",
                    "op_id": f"{op_id}-dd0",
                    "prd": self.PRD,
                },
                f"{op_id}-dd2": {
                    "question": "q2",
                    "cycle": 2,
                    "type": "deferred_decision",
                    "op_id": f"{op_id}-dd2",
                    "prd": self.PRD,
                },
                f"{op_id}-dd3": {
                    "question": "q3",
                    "status": "deferred",
                    "type": "ambiguity",
                    "cycle": 2,
                    "op_id": f"{op_id}-dd3",
                    "prd": self.PRD,
                },
            },
        )
        final = self._state()
        self.assertNotIn(
            "deferred_decisions",
            final,
            "the reset still drops deferred_decisions",
        )
        self.assertNotIn("stall_op", final)

    def test_stall_stamps_the_state_batch_id_and_the_prd_name_into_every_artifact(
        self,
    ) -> None:
        other_prd = "00017-other-y.md"
        other_batch = "202609130001"
        state = self._critical_state(
            prd=other_prd,
            cycle=5,
            deferred_decisions=copy.deepcopy(DECISIONS),
        )
        state["batch"]["id"] = other_batch

        op_id, items = self._run_critical_stall(state, prd=other_prd)

        self.assertFalse(
            self._deferred_path(BATCH_ID).exists(),
            "records go to the state's batch ledger, not a fixed one",
        )
        self.assertEqual(items[0]["type"], "stall")
        self.assertEqual(items[0]["prd"], other_prd)
        self.assertEqual(
            {i["op_id"]: (i["prd"], i["cycle"]) for i in items[1:]},
            {
                f"{op_id}-dd0": (other_prd, 1),
                f"{op_id}-dd2": (other_prd, 5),
                f"{op_id}-dd3": (other_prd, 5),
            },
            "migrated records name THIS prd and fall back to the state's cycle",
        )
        entry = self._stall_entry(op_id, prd=other_prd, batch=other_batch)
        self.assertEqual(self._marker_entries(), [entry])
        self.assertEqual(self._journal_rows(), [{"event": "recorded", **entry}])
        self.assertEqual(self._state()["batch"]["critical_on_master"], [entry])
        hold = self._hold_text(other_prd)
        self.assertEqual(hold, self._expected_hold(op_id, batch=other_batch))
        self.assertNotIn(BATCH_ID, hold)
        self.assertNotIn(self.PRD, json.dumps(items))
        self.assertEqual(
            self.notify.call_args,
            mock.call(
                "autopilot 🔒 custody",
                f"{other_prd}: commits {self._range()} (2) live on master; "
                "run autopilot custody resolve",
            ),
        )

    def test_stall_records_the_checked_out_branch_and_the_real_commit_count(
        self,
    ) -> None:
        repo = self.root / "topic-repo"
        shas = _init_repo(repo, commits=5, branch="topic/x")
        rng = f"{shas[0]}..{shas[4]}"
        self._put_in_wip(content=PRD_TEXT)
        self._write_state(
            self._sample_state(work_start_sha=shas[0], repo_root=str(repo)),
        )

        rc = self._do_stall(site="cap_critical")

        self.assertEqual(rc, 0)
        entries = self._marker_entries()
        self.assertEqual(len(entries), 1)
        op_id = entries[0]["op_id"]
        entry = self._stall_entry(
            op_id,
            commit_range=rng,
            commits=4,
            branch="topic/x",
            repo_root=str(repo),
        )
        self.assertEqual(entries, [entry])
        self.assertEqual(self._journal_rows(), [{"event": "recorded", **entry}])
        items = self._deferred_items()
        self.assertEqual(
            (items[0]["commit_range"], items[0]["commits"], items[0]["branch"]),
            (rng, 4, "topic/x"),
        )
        hold = self._hold_text()
        self.assertEqual(
            hold,
            self._expected_hold(op_id, commit_range=rng, commits=4, branch="topic/x"),
        )
        self.assertNotIn("live on master", hold)
        self.assertNotIn("(2)", hold)
        self.assertEqual(
            self.notify.call_args,
            mock.call(
                "autopilot 🔒 custody",
                f"{self.PRD}: commits {rng} (4) live on topic/x; "
                "run autopilot custody resolve",
            ),
        )
        self.assertEqual(self._state()["batch"]["critical_on_master"], [entry])

    @unittest.skipIf(os.geteuid() == 0, "root ignores file modes")
    def test_exit_9_without_notification_when_the_hold_rewrite_fails_then_the_retry_notifies_once(
        self,
    ) -> None:
        hold_dir = self.prds_dir / "hold"
        hold_dir.mkdir()
        hold = hold_dir / self.PRD
        hold.write_text(PRD_TEXT, encoding="utf-8")
        state = self._critical_state()
        hold.chmod(0o444)
        hold_dir.chmod(0o555)
        self.addCleanup(hold_dir.chmod, 0o755)
        self.addCleanup(hold.chmod, 0o644)

        rc = self._record_critical(state, "0123456789ab")

        self.assertEqual(rc, 9)
        self.assertEqual(
            self.notify.call_count,
            0,
            "the hold rewrite is the last durable write; no notify before it lands",
        )
        self.assertEqual(hold.read_text(encoding="utf-8"), PRD_TEXT)

        hold_dir.chmod(0o755)
        hold.chmod(0o644)
        rc = self._record_critical(state, "0123456789ab")

        self.assertIsNone(rc)
        entry = self._stall_entry("0123456789ab")
        self.assertEqual(self._marker_entries(), [entry])
        self.assertEqual(custody.unresolved_from_journal(self.autopilot_dir), [entry])
        self.assertEqual(self._hold_text(), self._expected_hold("0123456789ab"))
        self.assertEqual(self.notify.call_count, 1)

    def test_design_gate_stall_writes_no_custody_artifacts(self) -> None:
        self._put_in_wip(content=PRD_TEXT)
        self._write_state(self._critical_state())

        rc = self._do_stall(site="design_gate")

        self.assertEqual(rc, 0)
        self.assertTrue(self._in_hold())
        self.assertFalse(self._marker_path().exists())
        self.assertFalse((self.autopilot_dir / "ledger").exists())
        self.assertIsNone(_locator("-C", str(self.repo)))
        self.assertEqual(self._hold_text(), PRD_TEXT)
        items = self._deferred_items()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["site"], "design_gate")
        for key in CAPTURE_KEYS:
            self.assertNotIn(key, items[0])
        final = self._state()
        self.assertNotIn("critical_on_master", final["batch"])
        self.assertNotIn("stall_op", final)

    def test_exit_9_when_ledger_is_a_file_then_the_retry_completes_idempotently(
        self,
    ) -> None:
        self._put_in_wip(content=PRD_TEXT)
        self._write_state(
            self._critical_state(deferred_decisions=copy.deepcopy(DECISIONS)),
        )
        before = self._state()
        (self.autopilot_dir / "ledger").write_text("occupied", encoding="utf-8")

        rc = self._do_stall(site="cap_critical")

        self.assertEqual(rc, 9)
        self.assertTrue(self._in_hold())
        self.assertFalse(self._in_wip())
        op_id = self._assert_intent_retained_without_reset(before)
        self.assertEqual(
            self.notify.call_count,
            0,
            "no notification before every custody write succeeded",
        )

        (self.autopilot_dir / "ledger").unlink()
        rc = self._do_stall(site="cap_critical")

        self.assertEqual(rc, 0)
        entry = self._stall_entry(op_id)
        self.assertEqual(self._marker_entries(), [entry])
        self.assertEqual(custody.unresolved_from_journal(self.autopilot_dir), [entry])
        self.assertEqual(
            sorted(i["op_id"] for i in self._deferred_items()),
            sorted([op_id, f"{op_id}-dd0", f"{op_id}-dd2", f"{op_id}-dd3"]),
            "one stall record plus one migration record per pending deferral, no duplicates",
        )
        self.assertEqual(self._hold_text(), self._expected_hold(op_id))
        self.assertEqual(
            self.notify.call_count,
            1,
            "the notification fires exactly once across both attempts",
        )
        final = self._state()
        self.assertNotIn("stall_op", final)
        self.assertEqual(final["batch"]["critical_on_master"], [entry])
        self.assertEqual(final["cycle"], 1)

    def test_failpoint_after_append_before_custody_leaves_no_custody_write_and_retry_completes_once(
        self,
    ) -> None:
        self._put_in_wip(content=PRD_TEXT)
        self._write_state(
            self._critical_state(deferred_decisions=copy.deepcopy(DECISIONS)),
        )
        before = self._state()

        self._run_with_failpoint("after-append-before-custody")

        self.assertTrue(self._in_hold())
        items = self._deferred_items()
        self.assertEqual(
            [i["type"] for i in items],
            ["stall"],
            "the append landed; migration has not",
        )
        op_id = self._assert_intent_retained_without_reset(before)
        self.assertEqual(items[0]["op_id"], op_id)
        self.assertFalse(self._marker_path().exists())
        self.assertEqual(self._journal_rows(), [])
        self.assertIsNone(_locator("-C", str(self.repo)))
        self.assertEqual(
            self._hold_text(),
            PRD_TEXT,
            "no notice before the custody step",
        )
        self.assertEqual(self.notify.call_count, 0)

        rc = self._do_stall(site="cap_critical")

        self.assertEqual(rc, 0)
        entry = self._stall_entry(op_id)
        self.assertEqual(self._marker_entries(), [entry])
        self.assertEqual(self._journal_rows(), [{"event": "recorded", **entry}])
        self.assertEqual(
            sorted(i["op_id"] for i in self._deferred_items()),
            sorted([op_id, f"{op_id}-dd0", f"{op_id}-dd2", f"{op_id}-dd3"]),
        )
        self.assertEqual(self._hold_text(), self._expected_hold(op_id))
        self.assertEqual(self.notify.call_count, 1)
        final = self._state()
        self.assertNotIn("stall_op", final)
        self.assertEqual(final["batch"]["critical_on_master"], [entry])

    def test_second_run_of_the_same_operation_replaces_entry_row_and_notice_in_place(
        self,
    ) -> None:
        self._put_in_wip(content=PRD_TEXT)
        state = self._critical_state(deferred_decisions=copy.deepcopy(DECISIONS))
        self._write_state(state)
        self.assertEqual(self._do_stall(site="cap_critical"), 0)
        op_id = self._marker_entries()[0]["op_id"]
        hold_after_first = self._hold_text()
        items_after_first = self._deferred_items()
        capture = {
            "commit_range": self._range(),
            "commits": 2,
            "branch": "master",
            "repo_root": str(self.repo),
            "git_dir": None,
        }

        rc = custody.record_critical(
            autopilot_dir=self.autopilot_dir,
            prds_dir=self.prds_dir,
            current=state,
            prd=self.PRD,
            op_id=op_id,
            detail="detail text",
            capture=capture,
        )

        self.assertIsNone(rc)
        entry = self._stall_entry(op_id)
        self.assertEqual(self._marker_entries(), [entry])
        self.assertEqual(custody.unresolved_from_journal(self.autopilot_dir), [entry])
        self.assertEqual(custody.pending(self.autopilot_dir), [entry])
        self.assertEqual(self._hold_text(), hold_after_first)
        self.assertEqual(self._hold_text().count(NOTICE_PREFIX), 1)
        self.assertEqual(self._deferred_items(), items_after_first)
        self.assertEqual(
            self.notify.call_count,
            1,
            "a repeat of the same operation must not notify again",
        )

    def test_pending_survives_marker_deletion_through_the_journal(self) -> None:
        self._put_in_wip(content=PRD_TEXT)
        self._write_state(self._critical_state())
        self.assertEqual(self._do_stall(site="cap_critical"), 0)
        op_id = self._marker_entries()[0]["op_id"]

        self._marker_path().unlink()

        self.assertEqual(
            custody.pending(self.autopilot_dir),
            [self._stall_entry(op_id)],
        )

    def test_bare_repo_stall_captures_through_git_dir_and_sets_the_locator_in_the_bare_config(
        self,
    ) -> None:
        bare = self.root / "bare.git"
        work_tree = self.root / "wt"
        shas = _init_bare_repo(bare, work_tree)
        self._put_in_wip(content=PRD_TEXT)
        self._write_state(
            self._sample_state(
                work_start_sha=shas[0],
                repo_root=str(work_tree),
                git_dir=str(bare),
            ),
        )

        rc = self._do_stall(site="cap_critical")

        self.assertEqual(rc, 0)
        entries = self._marker_entries()
        self.assertEqual(len(entries), 1)
        op_id = entries[0]["op_id"]
        expected = {
            "prd": self.PRD,
            "batch": BATCH_ID,
            "op_id": op_id,
            "commit_range": f"{shas[0]}..{shas[2]}",
            "commits": 2,
            "detail": "detail text",
            "repo_root": str(work_tree),
            "git_dir": str(bare),
            "branch": "master",
        }
        self.assertEqual(entries, [expected])
        items = self._deferred_items()
        self.assertEqual(items[0]["git_dir"], str(bare))
        self.assertEqual(items[0]["repo_root"], str(work_tree))
        locator = _locator("--git-dir", str(bare))
        self.assertIsNotNone(locator)
        self.assertEqual(Path(locator).resolve(), self._marker_path().resolve())
        self.assertFalse((work_tree / ".git").exists())
        final = self._state()
        self.assertEqual(final["batch"]["critical_on_master"], [expected])
        self.assertNotIn("git_dir", final, "git_dir is a per-PRD field and is reset")

    def test_repo_root_falls_back_to_the_project_root_above_dev_local_autopilot(
        self,
    ) -> None:
        project = self.root / "project"
        shas = _init_repo(project)
        self.autopilot_dir = project / "dev" / "local" / "autopilot"
        self.autopilot_dir.mkdir(parents=True)
        self.state_path = self.autopilot_dir / "state.json"
        self._put_in_wip(content=PRD_TEXT)
        self._write_state(self._sample_state(work_start_sha=shas[0]))

        rc = self._do_stall(site="cap_critical")

        self.assertEqual(rc, 0)
        entries = self._marker_entries()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["repo_root"], str(project))
        self.assertEqual(entries[0]["commit_range"], f"{shas[0]}..{shas[2]}")
        self.assertEqual(entries[0]["commits"], 2)
        locator = _locator("-C", str(project))
        self.assertIsNotNone(locator)
        self.assertEqual(Path(locator).resolve(), self._marker_path().resolve())


if __name__ == "__main__":
    unittest.main()
