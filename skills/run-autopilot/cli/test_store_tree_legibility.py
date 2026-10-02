#!/usr/bin/env python3
"""Tests for [D1]: store failures must be legible, not silent or open.

Three behaviors, each additive error reporting with no change to the
success path:

1. `autopilot dirty` must not let a failed/timed-out `git status` escape
   `_run_dirty` as an uncaught traceback (exit 1, which already means
   "usage error"); it must print one stderr line and return a distinct
   exit code, and the module docstring must document `dirty` and that code.
2. A failed store `.gitignore` write (`ensure-store` CLI verb, and
   `enter._prepare_tree`) must still keep exit 0 / Phase 0 running, but
   must name the path and the OSError on stderr instead of being swallowed.
3. `record_store` must treat a store pathspec refused because it is
   ignored by a `.gitignore`/exclude pattern as "nothing to record" (quiet
   None), not as the loud `store record failed` failure.

Written from the design contract only. Every test injects a fake run_git
or monkeypatches the store_tree seam, so no real git runs here.
"""

from __future__ import annotations

import io
import json
import re
import subprocess
import sys
import unittest
from contextlib import redirect_stderr
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cli import __main__ as cli_main
from cli import enter, store_tree

REPO = Path("/abs/repo")
SUBCOMMANDS = ("add", "diff", "commit", "rev-parse")
STAGED_STORE_FILE = "docs/dev/project-management/autopilot/state.json\n"
SHA = "0123456789abcdef0123456789abcdef01234567"
IGNORED_STDERR = (
    "The following paths are ignored by one of your .gitignore files:\n"
    "docs/dev/project-management\n"
    "hint: Use -f if you really want to add them."
)


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
            ["git", *args], 0, stdout=self.outputs.get(sub, ""), stderr="",
        )

    def calls_for(self, sub: str) -> list[list[str]]:
        return [args for args, _ in self.calls if _subcommand(args) == sub]


def _subcommand(args: list[str]) -> str | None:
    for arg in args:
        if arg in SUBCOMMANDS or arg == "status":
            return arg
    return None


def _one_line(text: str) -> bool:
    return len(text.strip("\n").splitlines()) == 1


def _raiser(error: Exception):
    def fn(*args: object, **kwargs: object) -> object:
        raise error

    return fn


def _autopilot_dir(root: Path) -> Path:
    path = root / "docs" / "dev" / "project-management" / "autopilot"
    path.mkdir(parents=True)
    return path


def _write_state(autopilot_dir: Path, state: dict) -> Path:
    path = autopilot_dir / "state.json"
    path.write_text(json.dumps(state), encoding="utf-8")
    return path


def _run(argv: list[str]) -> int:
    try:
        return cli_main.main(argv)
    except SystemExit as exc:
        return exc.code


# -- 1. `autopilot dirty` must not fail open on a git failure -----------------


@pytest.mark.parametrize(
    "error",
    [
        store_tree.StoreGitError("git status failed: fatal: boom"),
        RuntimeError("boom"),
    ],
    ids=["StoreGitError", "plain-RuntimeError"],
)
def test_cli_dirty_reports_a_git_failure_on_stderr_with_a_distinct_exit_code(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
    error: Exception,
) -> None:
    repo = tmp_path / "elsewhere"
    state_path = _write_state(_autopilot_dir(tmp_path), {"repo_root": str(repo)})
    monkeypatch.setattr(store_tree, "foreign_dirty", _raiser(error))

    code = _run(["dirty", "--state", str(state_path)])

    assert isinstance(code, int), f"must not crash out with a non-exit-code result: {code!r}"
    assert code not in (0, 1), (
        "0 is a clean tree and 1 already means paths-found / usage error; "
        f"a crashed probe needs its own code, got {code}"
    )
    out = capsys.readouterr()
    assert out.out == "", "no paths to print when the probe itself failed"
    assert _one_line(out.err), out.err


def test_cli_dirty_still_exits_one_on_genuine_foreign_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
) -> None:
    """Regression guard: the new failure code must not swallow the existing
    "paths found" meaning of exit 1."""
    repo = tmp_path / "elsewhere"
    state_path = _write_state(_autopilot_dir(tmp_path), {"repo_root": str(repo)})
    monkeypatch.setattr(store_tree, "foreign_dirty", lambda *a, **k: ["src/x.py"])

    code = _run(["dirty", "--state", str(state_path)])

    assert code == 1
    assert capsys.readouterr().out == "src/x.py\n"


# -- 2. a failed store .gitignore write must be named on stderr ---------------


def test_cli_ensure_store_reports_a_gitignore_write_failure_on_stderr_and_still_exits_zero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
) -> None:
    autopilot_dir = _autopilot_dir(tmp_path)
    state_path = _write_state(autopilot_dir, {})
    store_dir = autopilot_dir.parent
    monkeypatch.setattr(
        store_tree, "ensure_store_gitignore", _raiser(OSError("Permission denied")),
    )

    code = _run(["ensure-store", "--state", str(state_path)])

    assert code == 0, "a write failure must not halt Phase 0"
    out = capsys.readouterr()
    assert out.out == "", "nothing was written, so no .gitignore path is printed"
    assert _one_line(out.err), out.err
    assert str(store_dir) in out.err, out.err
    assert "Permission denied" in out.err, out.err


def test_cli_ensure_store_is_silent_and_exits_zero_on_a_successful_write(
    tmp_path: Path,
    capsys: pytest.CaptureFixture,
) -> None:
    """Regression guard: the success path keeps its own existing contract."""
    autopilot_dir = _autopilot_dir(tmp_path)
    state_path = _write_state(autopilot_dir, {})
    store_dir = autopilot_dir.parent

    code = _run(["ensure-store", "--state", str(state_path)])

    assert code == 0
    out = capsys.readouterr()
    assert out.out.strip() == str(store_dir / ".gitignore")
    assert out.err == ""


def test_prepare_tree_reports_a_gitignore_write_failure_on_stderr_and_keeps_phase_zero_running(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    autopilot_dir = _autopilot_dir(tmp_path)
    prds_dir = autopilot_dir.parent / "prds"
    state_path = autopilot_dir / "state.json"
    store_dir = autopilot_dir.parent
    monkeypatch.setattr(
        store_tree, "ensure_store_gitignore", _raiser(OSError("Permission denied")),
    )
    err = io.StringIO()

    with redirect_stderr(err):
        enter._prepare_tree(state_path, prds_dir, autopilot_dir)

    assert _one_line(err.getvalue()), err.getvalue()
    assert str(store_dir) in err.getvalue(), err.getvalue()
    assert "Permission denied" in err.getvalue(), err.getvalue()
    assert state_path.exists(), "the rest of Phase 0's bootstrap still ran"
    assert (prds_dir / "backlog").is_dir(), "the lifecycle dirs still got created"


# -- 3. an ignored store is "nothing to record", not a failure ----------------


class RecordStoreIgnoredStoreTests(unittest.TestCase):
    def test_record_store_treats_an_ignored_store_pathspec_as_nothing_to_record(
        self,
    ) -> None:
        git = FakeGit(
            {},
            fail_on="add",
            error=subprocess.CalledProcessError(
                1, ["git", "add"], output="", stderr=IGNORED_STDERR,
            ),
        )
        err = io.StringIO()

        with redirect_stderr(err):
            out = store_tree.record_store(REPO, "build", "00007-x.md", run_git=git)

        self.assertIsNone(out)
        self.assertEqual(
            err.getvalue(),
            "",
            "an ignored store is nothing to record, not a reportable failure",
        )
        self.assertEqual(git.calls_for("diff"), [], "no further git calls after add is refused")
        self.assertEqual(git.calls_for("commit"), [])

    def test_record_store_still_reports_a_genuinely_refused_add(self) -> None:
        """Regression guard: only the "ignored by .gitignore" refusal goes
        quiet. Any other `git add` failure stays loud."""
        git = FakeGit(
            {},
            fail_on="add",
            error=subprocess.CalledProcessError(
                128, ["git", "add"], output="", stderr="fatal: not a git repository",
            ),
        )
        err = io.StringIO()

        with redirect_stderr(err):
            out = store_tree.record_store(REPO, "build", "00007-x.md", run_git=git)

        self.assertIsNone(out)
        self.assertTrue(_one_line(err.getvalue()), err.getvalue())
        self.assertIn("autopilot: store record failed", err.getvalue())


# -- the module docstring must document `dirty` and its failure code ----------


def _subcommands_section(doc: str) -> str:
    return doc.split("Subcommands:\n", 1)[1].split("\n\n--state,", 1)[0]


def _exit_code_descriptions(doc: str) -> dict[int, str]:
    section = doc.split("Exit codes:\n", 1)[1]
    entries: dict[int, list[str]] = {}
    current: int | None = None
    for line in section.splitlines():
        top = re.match(r" {4}(\d+) {1,3}(.*)", line)
        if top:
            current = int(top.group(1))
            entries[current] = [top.group(2)]
        elif line.startswith(" " * 8) and current is not None:
            entries[current].append(line.strip())
        elif not line.strip():
            current = None
    return {code: " ".join(parts) for code, parts in entries.items()}


def test_module_docstring_lists_dirty_as_a_subcommand() -> None:
    section = _subcommands_section(cli_main.__doc__)

    assert re.search(r"(?m)^    dirty\b", section), section


def test_module_docstring_exit_table_names_dirty_for_the_code_it_actually_returns(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "elsewhere"
    state_path = _write_state(_autopilot_dir(tmp_path), {"repo_root": str(repo)})
    monkeypatch.setattr(
        store_tree, "foreign_dirty",
        _raiser(store_tree.StoreGitError("git status failed: fatal: boom")),
    )

    code = _run(["dirty", "--state", str(state_path)])

    descriptions = _exit_code_descriptions(cli_main.__doc__)
    assert code in descriptions, (
        f"exit code {code} is not documented in the Exit codes table at all"
    )
    assert "dirty" in descriptions[code].lower(), (
        f"code {code}'s table entry does not mention dirty: {descriptions[code]!r}"
    )


if __name__ == "__main__":
    unittest.main()
