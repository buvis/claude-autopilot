#!/usr/bin/env python3
"""Tests for cli/custody.py's functions and the records/schema/frontmatter
field changes that ride with it. The cap_critical branch of records.do_stall
is covered in test_custody_stall.py; both share custody_testutil.py.

Written from the design contract only. Git-backed tests build a REAL
repository (git init plus real commits) in a temp dir.
"""

from __future__ import annotations

import copy
import fcntl
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cli import custody, frontmatter, records, schema
from cli.custody_testutil import (
    BATCH_ID,
    DECISIONS,
    NOTICE_PREFIX,
    _commit,
    _git,
    _init_bare_repo,
    _init_repo,
)

RANGE = "a" * 40 + ".." + "b" * 40


def _entry(op_id: str, **overrides) -> dict:
    """A marker entry with every required key, for the pure-function tests."""
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


def _block_closing_at(index: int) -> str:
    """A frontmatter block whose closing `---` sits at 0-based line `index`."""
    filler = ["pause_on_ambiguity: true"] * (index - 2)
    return "\n".join(["---", "design_gate: user", *filler, "---", "# Body", ""])


class ContractConstantsTests(unittest.TestCase):
    def test_constants_match_the_design_contract(self) -> None:
        self.assertEqual(custody.CUSTODY_SITE, "cap_critical")
        self.assertEqual(custody.MARKER_NAME, "critical-on-master")
        self.assertEqual(custody.JOURNAL_REL, "ledger/custody.jsonl")
        self.assertEqual(custody.CONFIG_KEY, "autopilot.custodyMarker")
        self.assertEqual(custody.EMPTY_TREE, "4b825dc642cb6eb9a060e54bf8d69288fbee4904")
        self.assertEqual(custody.GIT_TIMEOUT_SECS, 30)
        self.assertTrue(issubclass(custody.CustodyError, Exception))

    def test_git_argv_uses_git_dir_and_work_tree_only_when_git_dir_is_set(self) -> None:
        self.assertEqual(
            custody.git_argv("/wt", "/bare"),
            ["git", "--git-dir", "/bare", "--work-tree", "/wt"],
        )
        self.assertEqual(custody.git_argv("/wt", None), ["git", "-C", "/wt"])

    def test_project_root_strips_dev_local_autopilot_else_uses_the_parent(self) -> None:
        self.assertEqual(
            custody.project_root(Path("/x/y/dev/local/autopilot")),
            Path("/x/y"),
        )
        self.assertEqual(
            custody.project_root(Path("/x/y/other/autopilot")),
            Path("/x/y/other"),
        )


class CaptureRangeTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.repo = self.root / "repo"
        self.shas = _init_repo(self.repo)

    def test_captures_base_to_head_with_the_commit_count_and_branch(self) -> None:
        self.assertEqual(
            custody.capture_range(str(self.repo), None, self.shas[0]),
            (f"{self.shas[0]}..{self.shas[2]}", 2, "master"),
        )
        self.assertEqual(
            custody.capture_range(str(self.repo), None, self.shas[2]),
            (f"{self.shas[2]}..{self.shas[2]}", 0, "master"),
        )

    def test_empty_tree_base_counts_every_commit(self) -> None:
        self.assertEqual(
            custody.capture_range(str(self.repo), None, custody.EMPTY_TREE),
            (f"{custody.EMPTY_TREE}..{self.shas[2]}", 3, "master"),
        )

    def test_reports_the_checked_out_branch_and_head_when_detached(self) -> None:
        repo = self.root / "topic"
        shas = _init_repo(repo, branch="topic/x")

        self.assertEqual(
            custody.capture_range(str(repo), None, shas[0]),
            (f"{shas[0]}..{shas[2]}", 2, "topic/x"),
        )

        _git("-C", str(repo), "checkout", "-q", shas[1])

        self.assertEqual(
            custody.capture_range(str(repo), None, shas[0]),
            (f"{shas[0]}..{shas[1]}", 1, "HEAD"),
            "a detached HEAD reports 'HEAD' and the end sha is the detached one",
        )

    def test_counts_the_commits_in_range_and_snapshots_head_at_call_time(
        self,
    ) -> None:
        repo = self.root / "five"
        shas = _init_repo(repo, commits=5)

        captured = custody.capture_range(str(repo), None, shas[0])

        self.assertEqual(captured, (f"{shas[0]}..{shas[4]}", 4, "master"))
        self.assertEqual(
            custody.capture_range(str(repo), None, shas[3]),
            (f"{shas[3]}..{shas[4]}", 1, "master"),
        )
        self.assertEqual(
            custody.capture_range(str(repo), None, custody.EMPTY_TREE),
            (f"{custody.EMPTY_TREE}..{shas[4]}", 5, "master"),
        )

        later = _commit(repo, "later.txt")

        self.assertEqual(
            captured,
            (f"{shas[0]}..{shas[4]}", 4, "master"),
            "the end sha is the one captured at call time, never re-read",
        )
        self.assertEqual(
            custody.capture_range(str(repo), None, shas[0]),
            (f"{shas[0]}..{later}", 5, "master"),
        )

    def test_raises_custody_error_for_a_bad_base_or_a_missing_repo_root(self) -> None:
        for label, base in (
            ("not hex", "not-a-sha"),
            ("39 hex", "a" * 39),
            ("41 hex", "a" * 41),
            ("abbreviated sha git would resolve", self.shas[0][:12]),
            ("branch name git would resolve", "master"),
            ("relative ref git would resolve", "HEAD~1"),
            ("unknown sha", "f" * 40),
        ):
            with self.subTest(label):
                with self.assertRaises(custody.CustodyError):
                    custody.capture_range(str(self.repo), None, base)
        for label, root in (
            ("missing", self.root / "missing"),
            ("a file", self.repo / "f0.txt"),
        ):
            with self.subTest(root=label):
                with self.assertRaises(custody.CustodyError):
                    custody.capture_range(str(root), None, self.shas[0])

    def test_bare_repo_with_a_separate_work_tree_captures_through_git_dir(self) -> None:
        bare = self.root / "bare.git"
        work_tree = self.root / "wt"
        shas = _init_bare_repo(bare, work_tree)
        self.assertFalse((work_tree / ".git").exists())

        self.assertEqual(
            custody.capture_range(str(work_tree), str(bare), shas[0]),
            (f"{shas[0]}..{shas[2]}", 2, "master"),
        )
        with self.assertRaises(
            custody.CustodyError,
            msg="a repo_root that is not a directory is refused even though the "
            "bare repo can answer every rev-parse/rev-list without a work tree",
        ):
            custody.capture_range(str(self.root / "missing"), str(bare), shas[0])


class MarkerTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.marker = Path(self._tmp.name) / "critical-on-master"

    def test_load_marker_returns_empty_list_when_absent(self) -> None:
        self.assertEqual(custody.load_marker(self.marker), [])

    def test_load_marker_rejects_anything_but_an_entries_list_of_dicts(self) -> None:
        for raw in (
            "[]",
            '{"foo": []}',
            '{"entries": "x"}',
            '{"entries": [1]}',
            "not json",
        ):
            with self.subTest(raw):
                self.marker.write_text(raw, encoding="utf-8")
                with self.assertRaises(custody.CustodyError):
                    custody.load_marker(self.marker)

    def test_write_marker_round_trips_entries_and_deletes_the_file_when_empty(
        self,
    ) -> None:
        entries = [_entry("op1"), _entry("op2")]

        custody.write_marker(self.marker, entries)

        self.assertEqual(
            json.loads(self.marker.read_text(encoding="utf-8")),
            {"entries": entries},
        )
        self.assertEqual(custody.load_marker(self.marker), entries)

        custody.write_marker(self.marker, [])

        self.assertFalse(self.marker.exists())
        self.assertEqual(custody.load_marker(self.marker), [])

    def test_upsert_entry_appends_new_and_replaces_same_op_id_without_mutating_input(
        self,
    ) -> None:
        entries = [_entry("op1"), _entry("op2")]
        snapshot = copy.deepcopy(entries)

        appended, created = custody.upsert_entry(entries, _entry("op3"))
        replaced, created_again = custody.upsert_entry(
            entries,
            _entry("op2", commits=9),
        )

        self.assertEqual(
            (appended, created),
            ([_entry("op1"), _entry("op2"), _entry("op3")], True),
        )
        self.assertEqual(
            (replaced, created_again),
            ([_entry("op1"), _entry("op2", commits=9)], False),
        )
        self.assertEqual(entries, snapshot, "upsert_entry must return a new list")

    def test_marker_lock_holds_an_exclusive_flock_on_the_lock_sidecar(self) -> None:
        lock_path = Path(f"{self.marker}.lock")

        with custody.marker_lock(self.marker):
            self.assertTrue(lock_path.exists())
            with open(lock_path, "a", encoding="utf-8") as other:
                with self.assertRaises(
                    OSError,
                    msg="a second holder must not get the lock",
                ):
                    fcntl.flock(other.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

        with open(lock_path, "a", encoding="utf-8") as other:
            fcntl.flock(other.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(other.fileno(), fcntl.LOCK_UN)


class JournalTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.autopilot_dir = Path(self._tmp.name) / "autopilot"
        self.autopilot_dir.mkdir(parents=True)
        self.journal = self.autopilot_dir / "ledger" / "custody.jsonl"

    def _rows(self) -> list[dict]:
        return [
            json.loads(line)
            for line in self.journal.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    @staticmethod
    def _canon(rows: list[dict]) -> list[str]:
        return sorted(json.dumps(r, sort_keys=True) for r in rows)

    def test_append_journal_creates_the_ledger_dir_and_appends_one_line_per_row(
        self,
    ) -> None:
        first = {"event": "recorded", **_entry("op1")}
        second = {
            "event": "resolving",
            "op_id": "op1",
            "choice": "keep",
            "head_before": "c" * 40,
        }

        custody.append_journal(self.autopilot_dir, first)
        custody.append_journal(self.autopilot_dir, second)

        self.assertEqual(self._rows(), [first, second])
        self.assertEqual(custody.read_journal(self.autopilot_dir), [first, second])

    def test_read_journal_returns_empty_for_an_absent_file_and_raises_on_a_corrupt_line(
        self,
    ) -> None:
        self.assertEqual(custody.read_journal(self.autopilot_dir), [])

        custody.append_journal(
            self.autopilot_dir,
            {"event": "recorded", **_entry("op1")},
        )
        with self.journal.open("a", encoding="utf-8") as fh:
            fh.write("{not json\n")

        with self.assertRaises(custody.CustodyError):
            custody.read_journal(self.autopilot_dir)
        with self.assertRaises(custody.CustodyError):
            custody.pending(self.autopilot_dir)

    def _write_history(self) -> tuple[dict, dict]:
        """op a: recorded twice (v2 last) then resolving; op b: recorded,
        resolving, resolved; op c: recorded only. Returns (a_v2, c)."""
        a_v2 = _entry("a", commits=5)
        c = _entry("c")
        for row in (
            {"event": "recorded", **_entry("a")},
            {"event": "recorded", **_entry("b")},
            {
                "event": "resolving",
                "op_id": "b",
                "choice": "keep",
                "head_before": "c" * 40,
            },
            {
                "event": "resolved",
                "op_id": "b",
                "prd": "00004-feature-x.md",
                "choice": "keep",
                "at": "t",
            },
            {"event": "recorded", **a_v2},
            {
                "event": "resolving",
                "op_id": "a",
                "choice": "revert",
                "head_before": "d" * 40,
            },
            {"event": "recorded", **c},
        ):
            custody.append_journal(self.autopilot_dir, row)
        return a_v2, c

    def test_unresolved_from_journal_keeps_the_last_recorded_entry_of_each_unresolved_op(
        self,
    ) -> None:
        a_v2, c = self._write_history()

        self.assertEqual(
            self._canon(custody.unresolved_from_journal(self.autopilot_dir)),
            self._canon([a_v2, c]),
        )

    def test_compact_journal_drops_resolved_history_and_keeps_last_recorded_plus_resolving(
        self,
    ) -> None:
        a_v2, c = self._write_history()

        custody.compact_journal(self.autopilot_dir)

        expected = [
            {"event": "recorded", **a_v2},
            {
                "event": "resolving",
                "op_id": "a",
                "choice": "revert",
                "head_before": "d" * 40,
            },
            {"event": "recorded", **c},
        ]
        self.assertEqual(self._canon(self._rows()), self._canon(expected))
        self.assertEqual(
            self._canon(custody.read_journal(self.autopilot_dir)),
            self._canon(expected),
        )

    def test_pending_unions_marker_and_journal_entries_with_the_marker_copy_winning(
        self,
    ) -> None:
        self.assertEqual(custody.pending(self.autopilot_dir), [])
        marker = self.autopilot_dir / "critical-on-master"
        custody.write_marker(marker, [_entry("a", detail="marker copy")])
        custody.append_journal(
            self.autopilot_dir,
            {"event": "recorded", **_entry("a", detail="journal copy")},
        )
        custody.append_journal(self.autopilot_dir, {"event": "recorded", **_entry("b")})
        custody.append_journal(self.autopilot_dir, {"event": "recorded", **_entry("c")})
        custody.append_journal(
            self.autopilot_dir,
            {
                "event": "resolved",
                "op_id": "c",
                "prd": "00004-feature-x.md",
                "choice": "keep",
                "at": "t",
            },
        )

        out = custody.pending(self.autopilot_dir)

        self.assertEqual(len(out), 2)
        self.assertEqual(
            {e["op_id"]: e for e in out},
            {"a": _entry("a", detail="marker copy"), "b": _entry("b")},
        )

    def test_pending_raises_when_the_marker_is_present_but_unreadable(self) -> None:
        (self.autopilot_dir / "critical-on-master").write_text(
            '{"entries": "x"}',
            encoding="utf-8",
        )

        with self.assertRaises(custody.CustodyError):
            custody.pending(self.autopilot_dir)


REFRESH_ENTRY = _entry("a1b2c3d4e5f6")
KEYS = f"critical_on_master: {RANGE}\nledger: deferred/{BATCH_ID}-deferred.json#a1b2c3d4e5f6\n"
FRESH_BLOCK = f"---\n{KEYS}---\n"
NOTICE = (
    f"{NOTICE_PREFIX} cap tripped. Commits {RANGE} (2) are live on master. "
    "Resolve with autopilot custody resolve."
)


class RefreshHoldPrdTests(unittest.TestCase):
    """refresh_hold_prd is pure; expected texts are spelled out in full so
    every other byte is proven preserved."""

    T_PROBLEM = (
        "# 00004 Feature X\n\n## Problem Statement\nWe need X.\n\n## Goals\n- g1\n"
    )
    T_H1_ONLY = "Intro.\n# Title\nBody.\n"
    T_NO_HEADING = "just text\n"
    T_BLOCK = "---\ndesign_gate: user\npause_on_ambiguity: true\n---\n# Title\n\n## Problem Statement\nWe need X.\n"
    T_BLOCK_WITH_KEYS = (
        f"---\ncritical_on_master: {'c' * 40}..{'d' * 40}\ndesign_gate: user\n"
        "ledger: deferred/old-deferred.json#old\n---\n## Problem Statement\nX.\n"
    )
    FILLER = "".join(f"k{i}: v{i}\n" for i in range(24))
    T_UNCLOSED = (
        f"---\n{FILLER}---\n## Problem Statement\nX.\n"  # closes on 0-based line 25
    )
    T_STALE_NOTICE = (
        f"## Problem Statement\n\n{NOTICE_PREFIX} stale. Commits x..y (9) are live on dev. "
        "Resolve with autopilot custody resolve.\n\nX.\n"
    )

    def _refresh(self, text: str) -> str:
        return custody.refresh_hold_prd(text, REFRESH_ENTRY)

    def test_prepends_a_fresh_block_and_inserts_the_notice_after_problem_statement(
        self,
    ) -> None:
        self.assertEqual(
            self._refresh(self.T_PROBLEM),
            FRESH_BLOCK
            + "# 00004 Feature X\n\n## Problem Statement\n\n"
            + NOTICE
            + "\n\nWe need X.\n\n## Goals\n- g1\n",
        )

    def test_falls_back_to_the_first_h1_then_to_the_end_of_text(self) -> None:
        self.assertEqual(
            self._refresh(self.T_H1_ONLY),
            FRESH_BLOCK + "Intro.\n# Title\n\n" + NOTICE + "\n\nBody.\n",
        )

        out = self._refresh(self.T_NO_HEADING)

        self.assertTrue(
            out.startswith(FRESH_BLOCK + "just text\n\n" + NOTICE + "\n"),
            out,
        )
        self.assertTrue(out.rstrip("\n").endswith(NOTICE), out)
        self.assertEqual(out.count(NOTICE_PREFIX), 1)

    def test_appends_both_keys_before_the_closing_delimiter_and_keeps_existing_keys_parsable(
        self,
    ) -> None:
        out = self._refresh(self.T_BLOCK)

        self.assertEqual(
            out,
            "---\ndesign_gate: user\npause_on_ambiguity: true\n"
            + KEYS
            + "---\n# Title\n\n## Problem Statement\n\n"
            + NOTICE
            + "\n\nWe need X.\n",
        )
        parsed, warnings = frontmatter.parse(out)
        self.assertNotIn(frontmatter.MALFORMED_WARNING, warnings)
        self.assertEqual(parsed.get("design_gate"), "user")

    def test_replaces_existing_custody_keys_and_a_same_batch_notice_in_place(
        self,
    ) -> None:
        self.assertEqual(
            self._refresh(self.T_BLOCK_WITH_KEYS),
            f"---\ncritical_on_master: {RANGE}\ndesign_gate: user\n"
            f"ledger: deferred/{BATCH_ID}-deferred.json#a1b2c3d4e5f6\n---\n## Problem Statement\n\n"
            + NOTICE
            + "\n\nX.\n",
        )
        self.assertEqual(
            self._refresh(self.T_STALE_NOTICE),
            FRESH_BLOCK + "## Problem Statement\n\n" + NOTICE + "\n\nX.\n",
        )

    def test_treats_a_block_that_does_not_close_within_20_lines_as_no_block(
        self,
    ) -> None:
        self.assertEqual(
            self._refresh(self.T_UNCLOSED),
            FRESH_BLOCK
            + f"---\n{self.FILLER}---\n## Problem Statement\n\n"
            + NOTICE
            + "\n\nX.\n",
        )

    def test_takes_batch_commit_count_and_branch_from_the_entry(self) -> None:
        entry = _entry(
            "0f0f0f0f0f0f",
            batch="202609130001",
            commits=7,
            branch="topic/x",
            detail="over cap.",
        )

        out = custody.refresh_hold_prd(self.T_BLOCK, entry)

        self.assertEqual(
            out,
            "---\ndesign_gate: user\npause_on_ambiguity: true\n"
            f"critical_on_master: {RANGE}\n"
            "ledger: deferred/202609130001-deferred.json#0f0f0f0f0f0f\n"
            "---\n# Title\n\n## Problem Statement\n\n"
            "> **Custody (cap_critical, batch 202609130001):** over cap. "
            f"Commits {RANGE} (7) are live on topic/x. "
            "Resolve with autopilot custody resolve."
            "\n\nWe need X.\n",
        )
        self.assertNotIn(BATCH_ID, out)
        self.assertNotIn("live on master", out)
        self.assertNotIn("(2)", out)
        self.assertEqual(custody.refresh_hold_prd(out, entry), out)

    def test_is_idempotent_for_every_text_shape(self) -> None:
        shapes = {
            "problem statement": self.T_PROBLEM,
            "h1 only": self.T_H1_ONLY,
            "no heading": self.T_NO_HEADING,
            "block": self.T_BLOCK,
            "block with keys": self.T_BLOCK_WITH_KEYS,
            "unclosed block": self.T_UNCLOSED,
            "stale notice": self.T_STALE_NOTICE,
        }
        for label, text in shapes.items():
            with self.subTest(label):
                once = self._refresh(text)
                self.assertEqual(self._refresh(once), once)
                self.assertEqual(once.count(NOTICE_PREFIX), 1)
                self.assertEqual(once.count("\ncritical_on_master: "), 1)
                self.assertEqual(once.count("\nledger: "), 1)


class MigrationRecordsTests(unittest.TestCase):
    PRD = "00017-other-y.md"

    @staticmethod
    def _sans_prd(recs: list[dict]) -> list[dict]:
        return [{k: v for k, v in r.items() if k != "prd"} for r in recs]

    def test_migrates_pending_decisions_by_original_index_with_own_type_and_cycle(
        self,
    ) -> None:
        state = {"cycle": 5, "deferred_decisions": copy.deepcopy(DECISIONS)}
        snapshot = copy.deepcopy(state)

        out = custody.migration_records(state, "abc", self.PRD)

        self.assertEqual(
            self._sans_prd(out),
            [
                {
                    "question": "q0",
                    "status": "pending",
                    "cycle": 1,
                    "type": "deferred_decision",
                    "op_id": "abc-dd0",
                },
                {
                    "question": "q2",
                    "type": "deferred_decision",
                    "cycle": 5,
                    "op_id": "abc-dd2",
                },
                {
                    "question": "q3",
                    "status": "deferred",
                    "type": "ambiguity",
                    "cycle": 5,
                    "op_id": "abc-dd3",
                },
            ],
        )
        for rec in out:
            self.assertEqual(
                rec.get("prd", self.PRD),
                self.PRD,
                "a record may leave prd to record_defer, but must never name "
                "another PRD",
            )
        self.assertEqual(
            state,
            snapshot,
            "migration_records must not mutate the state or its decisions",
        )

    def test_returns_nothing_when_no_decision_is_pending(self) -> None:
        state = {
            "cycle": 1,
            "deferred_decisions": [{"status": "resolved"}, {"status": "dismissed"}],
        }

        self.assertEqual(custody.migration_records(state, "abc", self.PRD), [])
        self.assertEqual(custody.migration_records({"cycle": 1}, "abc", self.PRD), [])


class MirrorMutatorTests(unittest.TestCase):
    def test_upserts_by_op_id_into_batch_critical_on_master_without_mutating_input(
        self,
    ) -> None:
        state = {"batch": {"id": BATCH_ID}}
        snapshot = copy.deepcopy(state)

        first = custody.mirror_mutator(_entry("op1"))(state)
        second = custody.mirror_mutator(_entry("op2"))(first)
        third = custody.mirror_mutator(_entry("op1", commits=7))(second)

        self.assertEqual(state, snapshot)
        self.assertEqual(
            first["batch"],
            {"id": BATCH_ID, "critical_on_master": [_entry("op1")]},
        )
        self.assertEqual(
            second["batch"]["critical_on_master"],
            [_entry("op1"), _entry("op2")],
        )
        self.assertEqual(
            third["batch"]["critical_on_master"],
            [_entry("op1", commits=7), _entry("op2")],
        )
        self.assertEqual(
            second["batch"]["critical_on_master"],
            [_entry("op1"), _entry("op2")],
            "the replace must not reach back into the earlier state",
        )


class FieldAndSchemaTests(unittest.TestCase):
    def test_git_dir_follows_repo_root_in_the_reset_fields_and_the_reset_drops_it(
        self,
    ) -> None:
        fields = records.PER_PRD_RESET_FIELDS
        self.assertEqual(fields[fields.index("repo_root") + 1], "git_dir")

        out = records.reset_prd_fields(
            {"git_dir": "/bare", "repo_root": "/wt", "batch": {"id": BATCH_ID}},
        )

        self.assertNotIn("git_dir", out)
        self.assertNotIn("repo_root", out)
        self.assertEqual(out["batch"], {"id": BATCH_ID})

    def test_schema_accepts_a_string_git_dir_and_rejects_other_types(self) -> None:
        schema.validate({"git_dir": "/x"})
        with self.assertRaises(schema.SchemaError):
            schema.validate({"git_dir": 5})

    def test_frontmatter_reads_22_head_lines_so_a_block_closing_on_line_21_or_22_parses(
        self,
    ) -> None:
        self.assertEqual(frontmatter._HEAD_LINES, 22)
        for closing_index in (20, 21):
            with self.subTest(line=closing_index + 1):
                parsed, warnings = frontmatter.parse(_block_closing_at(closing_index))
                self.assertNotIn(frontmatter.MALFORMED_WARNING, warnings)
                self.assertEqual(parsed.get("design_gate"), "user")

        parsed, warnings = frontmatter.parse(_block_closing_at(22))

        self.assertIn(frontmatter.MALFORMED_WARNING, warnings)
        self.assertEqual(parsed, frontmatter.defaults())


class StallOpMalformedTests(unittest.TestCase):
    def test_cap_critical_intent_must_carry_a_complete_valid_capture(self) -> None:
        valid = {
            "op_id": "0123456789ab",
            "prd": "00004-feature-x.md",
            "site": "cap_critical",
            "detail": "d",
            "commit_range": RANGE,
            "commits": 2,
            "branch": "master",
            "repo_root": "/r",
            "git_dir": None,
        }
        self.assertFalse(records._stall_op_malformed(valid))
        self.assertFalse(
            records._stall_op_malformed({**valid, "git_dir": "/bare", "commits": 0}),
        )
        self.assertFalse(
            records._stall_op_malformed(
                {
                    "op_id": "x",
                    "prd": "00004-feature-x.md",
                    "site": "design_gate",
                    "detail": "d",
                },
            ),
            "the capture clause is keyed on site == cap_critical only",
        )

        bad = {
            "missing commits": {k: v for k, v in valid.items() if k != "commits"},
            "missing commit_range": {
                k: v for k, v in valid.items() if k != "commit_range"
            },
            "short range": {**valid, "commit_range": "abc..def"},
            "negative commits": {**valid, "commits": -1},
            "string commits": {**valid, "commits": "2"},
            "empty branch": {**valid, "branch": ""},
            "empty repo_root": {**valid, "repo_root": ""},
            "int git_dir": {**valid, "git_dir": 5},
        }
        for label, stall_op in bad.items():
            with self.subTest(label):
                self.assertTrue(records._stall_op_malformed(stall_op))


if __name__ == "__main__":
    unittest.main()
