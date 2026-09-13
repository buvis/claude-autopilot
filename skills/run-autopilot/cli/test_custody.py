#!/usr/bin/env python3
"""Tests for cli/custody.py and the cap_critical branch of records.do_stall.

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
import fcntl
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cli import custody, frontmatter, records, schema

FAILPOINT_ENV = "_AUTOPILOT_CLI_FAILPOINT"
BATCH_ID = "202607300000"
PRD_TEXT = "# 00004 Feature X\n\n## Problem Statement\nWe need X.\n"
CAPTURE_KEYS = ("commit_range", "commits", "branch", "repo_root", "git_dir")
NOTICE_PREFIX = f"> **Custody (cap_critical, batch {BATCH_ID}):**"
RANGE = "a" * 40 + ".." + "b" * 40
DECISIONS = [
    {"question": "q0", "status": "pending", "cycle": 1},
    {"question": "q1", "status": "resolved", "cycle": 1},
    {"question": "q2"},
    {"question": "q3", "status": "deferred", "type": "ambiguity"},
]
_GIT_ENV = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}


def _without(state: dict, *keys: str) -> dict:
    """A shallow copy of `state` with `keys` dropped, for equality checks
    that must ignore write-boundary bookkeeping fields (stall_op,
    schema_version)."""
    return {k: v for k, v in state.items() if k not in keys}


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


# -- git fixtures (real repositories, real commits) --------------------------
def _git(*args: str, cwd: Path | None = None) -> str:
    proc = subprocess.run(
        ["git", "-c", "user.email=t@example.com", "-c", "user.name=t", *args],
        cwd=cwd,
        env=_GIT_ENV,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    return proc.stdout.strip()


def _commit(work_tree: Path, name: str, git_dir: Path | None = None) -> str:
    (work_tree / name).write_text(name, encoding="utf-8")
    loc = (
        ["--git-dir", str(git_dir), "--work-tree", str(work_tree)]
        if git_dir
        else ["-C", str(work_tree)]
    )
    _git(*loc, "add", "-A", cwd=work_tree)
    _git(*loc, "commit", "-q", "-m", name, cwd=work_tree)
    return _git(*loc, "rev-parse", "HEAD", cwd=work_tree)


def _init_repo(repo: Path, commits: int = 3, branch: str = "master") -> list[str]:
    repo.mkdir(parents=True, exist_ok=True)
    _git("init", "-q", "-b", branch, str(repo))
    return [_commit(repo, f"f{i}.txt") for i in range(commits)]


def _init_bare_repo(bare: Path, work_tree: Path, commits: int = 3) -> list[str]:
    work_tree.mkdir(parents=True, exist_ok=True)
    _git("init", "-q", "--bare", "-b", "master", str(bare))
    return [_commit(work_tree, f"f{i}.txt", git_dir=bare) for i in range(commits)]


def _locator(*loc: str) -> str | None:
    """`git <loc> config --get autopilot.custodyMarker`, None when unset."""
    proc = subprocess.run(
        ["git", *loc, "config", "--get", "autopilot.custodyMarker"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return proc.stdout.strip() if proc.returncode == 0 else None


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


class _StallTestCase(unittest.TestCase):
    """Shared fixture: <root>/prds/wip (pre-created), <root>/prds/hold (left
    absent so do_stall's own mkdir -p is exercised by every success path),
    <root>/autopilot/state.json. The notifier is patched for every test.
    """

    PRD = "00004-feature-x.md"

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.prds_dir = self.root / "prds"
        self.autopilot_dir = self.root / "autopilot"
        self.state_path = self.autopilot_dir / "state.json"
        (self.prds_dir / "wip").mkdir(parents=True)
        self.autopilot_dir.mkdir(parents=True)
        self.notify = mock.patch("cli.notify_out.notify").start()
        self.addCleanup(mock.patch.stopall)

    # -- prd placement ------------------------------------------------
    def _put_in_wip(self, prd: str | None = None, content: str = "prd body") -> None:
        (self.prds_dir / "wip" / (prd or self.PRD)).write_text(
            content,
            encoding="utf-8",
        )

    def _in_wip(self, prd: str | None = None) -> bool:
        return (self.prds_dir / "wip" / (prd or self.PRD)).exists()

    def _in_hold(self, prd: str | None = None) -> bool:
        return (self.prds_dir / "hold" / (prd or self.PRD)).exists()

    # -- state ----------------------------------------------------------
    def _write_state(self, state: dict) -> None:
        self.state_path.write_text(json.dumps(state), encoding="utf-8")

    def _state(self) -> dict:
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def _sample_state(self, **overrides) -> dict:
        base = {
            "prd": self.PRD,
            "phase": "build",
            "next_phase": "build",
            "cycle": 2,
            "tasks": [{"id": "t1", "name": "x", "status": "in_progress"}],
            "batch": {
                "id": BATCH_ID,
                "completed_prds": [],
                "parks_consecutive": 1,
            },
        }
        base.update(overrides)
        return base

    # -- deferred log -----------------------------------------------------
    def _deferred_path(self, batch_id: str = BATCH_ID) -> Path:
        return self.autopilot_dir / "deferred" / f"{batch_id}-deferred.json"

    def _deferred_items(self, batch_id: str = BATCH_ID) -> list:
        path = self._deferred_path(batch_id)
        if not path.exists():
            return []
        return json.loads(path.read_text(encoding="utf-8"))["items"]

    # -- call under test --------------------------------------------------
    def _do_stall(
        self,
        *,
        prd=None,
        site="design_gate",
        detail="detail text",
        **kwargs,
    ):
        return records.do_stall(
            self.state_path,
            prd=prd if prd is not None else self.PRD,
            site=site,
            detail=detail,
            prds_dir=self.prds_dir,
            autopilot_dir=self.autopilot_dir,
            **kwargs,
        )


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

    # -- tests --------------------------------------------------------------
    def test_stall_captures_range_writes_marker_journal_locator_mirror_hold_refresh_and_notifies_once(
        self,
    ) -> None:
        self._put_in_wip(content=PRD_TEXT)
        self._write_state(self._critical_state())

        rc = self._do_stall(site="cap_critical")

        self.assertEqual(rc, 0)
        self.assertTrue(self._in_hold())
        self.assertFalse(self._in_wip())

        items = self._deferred_items()
        self.assertEqual(len(items), 1)
        op_id = items[0]["op_id"]
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
        self._put_in_wip(prd=other_prd, content=PRD_TEXT)
        state = self._critical_state(
            prd=other_prd,
            cycle=5,
            deferred_decisions=copy.deepcopy(DECISIONS),
        )
        state["batch"]["id"] = other_batch
        self._write_state(state)

        rc = self._do_stall(prd=other_prd, site="cap_critical")

        self.assertEqual(rc, 0)
        self.assertTrue(self._in_hold(other_prd))
        self.assertFalse(
            self._deferred_path(BATCH_ID).exists(),
            "records go to the state's batch ledger, not a fixed one",
        )
        items = self._deferred_items(other_batch)
        self.assertEqual(items[0]["type"], "stall")
        op_id = items[0]["op_id"]
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
        capture = {
            "commit_range": self._range(),
            "commits": 2,
            "branch": "master",
            "repo_root": str(self.repo),
            "git_dir": None,
        }
        hold.chmod(0o444)
        hold_dir.chmod(0o555)
        self.addCleanup(hold_dir.chmod, 0o755)
        self.addCleanup(hold.chmod, 0o644)

        rc = custody.record_critical(
            autopilot_dir=self.autopilot_dir,
            prds_dir=self.prds_dir,
            current=state,
            prd=self.PRD,
            op_id="0123456789ab",
            detail="detail text",
            capture=capture,
        )

        self.assertEqual(rc, 9)
        self.assertEqual(
            self.notify.call_count,
            0,
            "the hold rewrite is the last durable write; no notify before it lands",
        )
        self.assertEqual(hold.read_text(encoding="utf-8"), PRD_TEXT)

        hold_dir.chmod(0o755)
        hold.chmod(0o644)
        rc = custody.record_critical(
            autopilot_dir=self.autopilot_dir,
            prds_dir=self.prds_dir,
            current=state,
            prd=self.PRD,
            op_id="0123456789ab",
            detail="detail text",
            capture=capture,
        )

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
