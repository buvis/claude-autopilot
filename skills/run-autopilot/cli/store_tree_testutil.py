#!/usr/bin/env python3
"""Shared test doubles and fixtures for the test_store_tree_*.py modules.

`FakeGit` records every (args, cwd) call and answers from canned stdout, so
no test using it runs real git. `_autopilot_dir`/`_write_state` build a fake
autopilot store's state.json for the CLI- and custody-facing tests.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO = Path("/abs/repo")
SHA = "0123456789abcdef0123456789abcdef01234567"
SUBCOMMANDS = ("add", "diff", "commit", "rev-parse")


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


def _one_line(text: str) -> bool:
    return len(text.strip("\n").splitlines()) == 1


def _autopilot_dir(root: Path) -> Path:
    path = root / "docs" / "dev" / "project-management" / "autopilot"
    path.mkdir(parents=True)
    return path


def _write_state(autopilot_dir: Path, state: dict) -> Path:
    path = autopilot_dir / "state.json"
    path.write_text(json.dumps(state), encoding="utf-8")
    return path
