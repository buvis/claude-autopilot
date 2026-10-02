#!/usr/bin/env python3
"""Tests for cli/store_tree.py's record_store: the scoped store recorder
that stages and commits only the store pathspec, leaving other staged work
untouched.

Written from the design contract only. Every test injects a fake run_git
that records the argv it was called with, except the last test, which drives
record_store against a real git repo.
"""

from __future__ import annotations

import io
import subprocess
import sys
import unittest
from contextlib import redirect_stderr
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cli import store_tree
from cli.store_tree_testutil import (
    REPO,
    SHA,
    SUBCOMMANDS,
    FakeGit,
    _one_line,
    _subcommand,
)

STORE_PATHSPEC = ":(top)docs/dev/project-management"
OTHER_SHA = "fedcba9876543210fedcba9876543210fedcba98"
STAGED_STORE_FILE = "docs/dev/project-management/autopilot/state.json\n"


def _message_in(args: list[str], message: str) -> bool:
    return any(a == message or a.endswith("=" + message) for a in args)


def _pathspecs(args: list[str]) -> list[str]:
    """The non-option arguments after the subcommand: everything after `--`,
    plus any bare word before it that is not an option's value."""
    rest = args[args.index(_subcommand(args)) + 1 :]
    out: list[str] = []
    skip_value = False
    after_dashdash = False
    for arg in rest:
        if after_dashdash:
            out.append(arg)
        elif skip_value:
            skip_value = False
        elif arg == "--":
            after_dashdash = True
        elif arg in ("-m", "--message", "-F", "--file"):
            skip_value = True
        elif not arg.startswith("-"):
            out.append(arg)
    return out


class RecordStoreTests(unittest.TestCase):
    def _staged_git(self, sha: str = SHA) -> FakeGit:
        return FakeGit({"diff": STAGED_STORE_FILE, "rev-parse": sha + "\n"})

    def _assert_never_touches_other_staged_paths(self, git: FakeGit) -> None:
        for args, _ in git.calls:
            for forbidden in ("reset", "restore", "rm", "stash", "checkout"):
                self.assertNotIn(forbidden, args, args)
            self.assertNotIn(
                "docs/dev/project-management",
                args,
                "the plain pathspec is not top-anchored; only the magic form is",
            )
        for args in git.calls_for("add"):
            self.assertEqual(
                _pathspecs(args),
                [STORE_PATHSPEC],
                f"add stages the store pathspec and nothing else: {args}",
            )
        for args in git.calls_for("commit"):
            self.assertNotIn("-a", args, args)
            self.assertNotIn("--all", args, args)
            self.assertNotIn("--no-verify", args, "commit hooks must run")
            self.assertNotIn("-n", args, "commit hooks must run")
            self.assertEqual(
                _pathspecs(args),
                [STORE_PATHSPEC],
                f"commit is scoped to the store pathspec only: {args}",
            )

    def test_record_store_stages_only_the_store(self) -> None:
        git = self._staged_git(OTHER_SHA)

        sha = store_tree.record_store(REPO, "build", "00007-feature-z.md", run_git=git)

        self.assertEqual(sha, OTHER_SHA, "the sha is the stripped rev-parse stdout")
        self.assertEqual(len(git.calls_for("add")), 1)
        diffs = git.calls_for("diff")
        self.assertEqual(len(diffs), 1)
        for flag in ("--cached", "--name-only", STORE_PATHSPEC):
            self.assertIn(flag, diffs[0])
        commits = git.calls_for("commit")
        self.assertEqual(len(commits), 1)
        self.assertIn(
            STORE_PATHSPEC,
            commits[0],
            "the commit is scoped to the store, so a caller's other staged "
            "file stays staged and uncommitted",
        )
        self.assertTrue(
            _message_in(
                commits[0],
                "chore(autopilot): record build state for 00007-feature-z.md",
            ),
            commits[0],
        )
        self.assertEqual(git.calls_for("rev-parse"), [["rev-parse", "HEAD"]])
        self._assert_never_touches_other_staged_paths(git)
        order = [_subcommand(args) for args, _ in git.calls]
        self.assertLess(order.index("add"), order.index("diff"))
        self.assertLess(order.index("diff"), order.index("commit"))
        self.assertLess(order.index("commit"), order.index("rev-parse"))
        self.assertTrue(all(cwd == REPO for _, cwd in git.calls), git.calls)

    def test_record_store_omits_the_prd_from_the_message_when_prd_is_empty(
        self,
    ) -> None:
        git = self._staged_git()

        sha = store_tree.record_store(REPO, "review", "", run_git=git)

        self.assertEqual(sha, SHA)
        commits = git.calls_for("commit")
        self.assertEqual(len(commits), 1)
        self.assertTrue(
            _message_in(commits[0], "chore(autopilot): record review state"),
            commits[0],
        )
        self.assertFalse(any(" for " in a for a in commits[0]), commits[0])

    def test_record_store_names_any_site_in_the_message(self) -> None:
        git = self._staged_git()

        sha = store_tree.record_store(REPO, "plan", "00009-q.md", run_git=git)

        self.assertEqual(sha, SHA)
        commits = git.calls_for("commit")
        self.assertEqual(len(commits), 1)
        self.assertTrue(
            _message_in(
                commits[0],
                "chore(autopilot): record plan state for 00009-q.md",
            ),
            commits[0],
        )

    def test_record_store_returns_none_when_nothing_changed(self) -> None:
        git = FakeGit({"diff": "", "rev-parse": SHA + "\n"})

        out = store_tree.record_store(REPO, "build", "00007-feature-z.md", run_git=git)

        self.assertIsNone(out)
        self.assertEqual(len(git.calls_for("add")), 1)
        self.assertEqual(len(git.calls_for("diff")), 1)
        self.assertEqual(git.calls_for("commit"), [], "no commit when nothing staged")
        self._assert_never_touches_other_staged_paths(git)

    def test_record_store_survives_a_commit_failure(self) -> None:
        for step in SUBCOMMANDS:
            with self.subTest(step=step):
                git = FakeGit(
                    {"diff": STAGED_STORE_FILE, "rev-parse": SHA + "\n"},
                    fail_on=step,
                    error=subprocess.CalledProcessError(
                        128,
                        ["git", step],
                        output="",
                        stderr="fatal: first line\nsecond line",
                    ),
                )
                err = io.StringIO()

                with redirect_stderr(err):
                    out = store_tree.record_store(
                        REPO,
                        "build",
                        "00007-x.md",
                        run_git=git,
                    )

                self.assertIsNone(out)
                self.assertTrue(_one_line(err.getvalue()), err.getvalue())
                self.assertIn(
                    "fatal: first line second line",
                    err.getvalue(),
                    "the git stderr reason survives, collapsed to one line",
                )
                if step in ("add", "diff"):
                    self.assertEqual(git.calls_for("commit"), [])

    def test_record_store_collapses_a_multiline_error_into_one_stderr_line(
        self,
    ) -> None:
        git = FakeGit(
            {"diff": STAGED_STORE_FILE},
            fail_on="commit",
            error=subprocess.CalledProcessError(
                1, ["git", "commit"], stderr="boom first\nboom second"
            ),
        )
        err = io.StringIO()

        with redirect_stderr(err):
            out = store_tree.record_store(REPO, "build", "", run_git=git)

        self.assertIsNone(out)
        self.assertTrue(_one_line(err.getvalue()), err.getvalue())
        self.assertIn("boom first boom second", err.getvalue())


def test_record_store_commits_store_changes_and_leaves_other_staged_work_staged(
    tmp_path: Path,
) -> None:
    """Against a REAL git repo, not FakeGit: the commit's tree reflects both a
    store addition and a store deletion `record_store` was given, and a file
    outside the store staged before the call is still staged, not committed or
    unstaged, afterward."""
    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *args],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        )

    git("init", "-q", "-b", "master")
    git("config", "user.email", "wave@example.com")
    git("config", "user.name", "Wave Test")
    git("config", "commit.gpgsign", "false")
    store = repo / "docs" / "dev" / "project-management"
    (store / "autopilot").mkdir(parents=True)
    (store / "autopilot" / "old.json").write_text("{}\n", encoding="utf-8")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    git("add", "README.md", "docs/dev/project-management/autopilot/old.json")
    git("commit", "-qm", "seed")

    (store / "autopilot" / "old.json").unlink()
    (store / "autopilot" / "state.json").write_text(
        '{"phase": "build"}\n', encoding="utf-8"
    )
    (repo / "foreign.py").write_text("x = 1\n", encoding="utf-8")
    git("add", "foreign.py")

    sha = store_tree.record_store(repo, "build", "00007-x.md")

    assert sha is not None
    tree = git("ls-tree", "-r", "--name-only", sha).stdout.splitlines()
    assert "docs/dev/project-management/autopilot/state.json" in tree, tree
    assert "docs/dev/project-management/autopilot/old.json" not in tree, tree
    assert "foreign.py" not in tree, tree
    assert git("status", "--porcelain").stdout.splitlines() == ["A  foreign.py"]


if __name__ == "__main__":
    unittest.main()
