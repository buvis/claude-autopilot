#!/usr/bin/env python3
"""Tests for cli/store_tree.py: the dirty-tree predicate (foreign_dirty) and
the scoped store recorder (record_store).

Written from the design contract only. Every test injects a fake run_git
that records the argv it was called with, so no real git runs here.
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

REPO = Path("/abs/repo")
STORE_PATHSPEC = ":(top)docs/dev/project-management"
STATUS_ARGS = ["status", "--porcelain", "-z", "--untracked-files=all"]
SHA = "0123456789abcdef0123456789abcdef01234567"
OTHER_SHA = "fedcba9876543210fedcba9876543210fedcba98"
SUBCOMMANDS = ("add", "diff", "commit", "rev-parse")
STAGED_STORE_FILE = "docs/dev/project-management/autopilot/state.json\n"


class FakeGit:
    """Records every (args, cwd) call and answers from canned stdout.

    `outputs` maps a git subcommand to its stdout; `fail_on` names one
    subcommand whose call raises `error` instead of answering.
    """

    def __init__(
        self,
        outputs: dict[str, str] | None = None,
        fail_on: str | None = None,
        error: Exception | None = None,
    ) -> None:
        self.outputs = outputs or {}
        self.fail_on = fail_on
        self.error = error
        self.calls: list[tuple[list[str], Path | None]] = []

    def __call__(
        self,
        args: list[str],
        cwd: Path | None = None,
    ) -> subprocess.CompletedProcess:
        self.calls.append((list(args), cwd))
        sub = _subcommand(args)
        if sub is not None and sub == self.fail_on:
            raise self.error
        return subprocess.CompletedProcess(
            ["git", *args],
            0,
            stdout=self.outputs.get(sub, ""),
            stderr="",
        )

    def calls_for(self, sub: str) -> list[list[str]]:
        return [args for args, _ in self.calls if _subcommand(args) == sub]


def _subcommand(args: list[str]) -> str | None:
    for arg in args:
        if arg in SUBCOMMANDS or arg == "status":
            return arg
    return None


def _porcelain(*fields: str) -> str:
    """NUL-terminate every field, exactly as `git status -z` does."""
    return "".join(f"{field}\0" for field in fields)


def _foreign(porcelain: str) -> tuple[list[str], FakeGit]:
    git = FakeGit({"status": porcelain})
    return store_tree.foreign_dirty(REPO, run_git=git), git


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


def _one_line(text: str) -> bool:
    return len(text.strip("\n").splitlines()) == 1


class StorePrefixesTests(unittest.TestCase):
    def test_store_prefixes_are_the_two_slash_terminated_store_roots(self) -> None:
        self.assertEqual(
            tuple(store_tree.STORE_PREFIXES),
            ("docs/dev/project-management/", "docs/dev/tmp/"),
        )


class ForeignDirtyTests(unittest.TestCase):
    def test_store_paths_are_never_foreign(self) -> None:
        porcelain = _porcelain(
            " M docs/dev/project-management/autopilot/state.json",
            "A  docs/dev/project-management/prds/wip/00001-x.md",
            "?? docs/dev/tmp/scratch.txt",
            "D  docs/dev/tmp/old/gone.txt",
            "R  docs/dev/project-management/prds/done/00001-x.md",
            "docs/dev/project-management/prds/wip/00001-x.md",
        )

        out, git = _foreign(porcelain)

        self.assertEqual(out, [])
        self.assertEqual(git.calls, [(STATUS_ARGS, REPO)])

    def test_a_clean_tree_has_no_foreign_paths(self) -> None:
        out, git = _foreign("")

        self.assertEqual(out, [])
        self.assertEqual(git.calls, [(STATUS_ARGS, REPO)])

    def test_a_path_outside_the_store_is_foreign(self) -> None:
        porcelain = _porcelain(
            " M src/app.py",
            " M docs/dev/project-management/autopilot/state.json",
            "?? docs/dev/project-management-notes/foo.txt",
            "?? docs/dev/tmpfile.txt",
            "?? dir with space/f.txt",
            "A  docs/dev/tmp/a.txt",
            "?? vendor/docs/dev/tmp/x.txt",
            "?? a/docs/dev/project-management/b",
            " D src/deleted_in_tree.py",
            "D  src/deleted_in_index.py",
            "MM src/both.py",
            "UU src/conflict.py",
        )

        out, _ = _foreign(porcelain)

        self.assertEqual(
            sorted(out),
            sorted(
                [
                    "src/app.py",
                    "docs/dev/project-management-notes/foo.txt",
                    "docs/dev/tmpfile.txt",
                    "dir with space/f.txt",
                    "vendor/docs/dev/tmp/x.txt",
                    "a/docs/dev/project-management/b",
                    "src/deleted_in_tree.py",
                    "src/deleted_in_index.py",
                    "src/both.py",
                    "src/conflict.py",
                ],
            ),
            "a sibling that only shares the prefix text, a nested path that "
            "merely contains a store root, and any outside status code "
            "(deletions and conflicts included) are all outside the store",
        )

    def test_an_untracked_store_reports_only_the_non_store_paths(self) -> None:
        porcelain = _porcelain(
            "?? docs/dev/project-management/autopilot/state.json",
            "?? docs/dev/project-management/prds/backlog/00002-y.md",
            "?? docs/dev/tmp/dispatch.txt",
            "?? README.md",
        )

        out, _ = _foreign(porcelain)

        self.assertEqual(out, ["README.md"])

    def test_a_rename_out_of_the_store_is_foreign(self) -> None:
        porcelain = _porcelain(
            "R  src/moved.md",
            "docs/dev/project-management/prds/wip/old.md",
        )

        out, _ = _foreign(porcelain)

        self.assertEqual(
            out,
            ["src/moved.md"],
            "the outside side is foreign; the store side contributes nothing",
        )

    def test_a_rename_into_the_store_reports_the_outside_old_path(self) -> None:
        porcelain = _porcelain(
            "R  docs/dev/project-management/prds/wip/new.md",
            "notes/old.md",
        )

        out, _ = _foreign(porcelain)

        self.assertEqual(
            out,
            ["notes/old.md"],
            "the old side counts even though the entry's own path slot is in the store",
        )

    def test_rename_and_copy_old_paths_are_not_misread_as_entries(self) -> None:
        porcelain = _porcelain(
            "R  docs/dev/project-management/b.md",
            "docs/dev/project-management/a.md",
            "RM docs/dev/tmp/y.txt",
            "docs/dev/tmp/x.txt",
            "C  lib/copy.py",
            "lib/orig.py",
            " M src/after.py",
        )

        out, _ = _foreign(porcelain)

        self.assertEqual(
            sorted(out),
            ["lib/copy.py", "lib/orig.py", "src/after.py"],
            "a store-to-store rename adds nothing; a copy with both sides "
            "outside reports both; the entry after a rename still parses",
        )


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
            _message_in(commits[0], "chore(autopilot): record plan state for 00009-q.md"),
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
            error=RuntimeError("boom first\nboom second"),
        )
        err = io.StringIO()

        with redirect_stderr(err):
            out = store_tree.record_store(REPO, "build", "", run_git=git)

        self.assertIsNone(out)
        self.assertTrue(_one_line(err.getvalue()), err.getvalue())
        self.assertIn("boom first boom second", err.getvalue())


if __name__ == "__main__":
    unittest.main()
