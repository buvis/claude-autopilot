#!/usr/bin/env python3
"""Tests for store_tree.ensure_store_gitignore's unreadable-input behavior (a
.gitignore body it cannot read must never be reported as already matching),
the `autopilot ensure-store` verb, and enter.py's lifecycle-directory step.

Split out of test_store_tree.py, which holds the rest of the writer's
contract. Written from the design contract only.
"""

from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cli import __main__ as cli_main
from cli import enter, notify_out, store_tree
from cli.enter_harness import PRD, Env, _open_state


@pytest.mark.parametrize(
    "breakage", ["missing-store-dir", "unreadable", "invalid-utf8"]
)
def test_ensure_store_gitignore_never_reports_a_match_it_cannot_read(
    tmp_path: Path,
    breakage: str,
) -> None:
    store_dir = tmp_path / "project-management"
    gitignore = store_dir / ".gitignore"
    if breakage != "missing-store-dir":
        store_dir.mkdir()
    if breakage == "unreadable":
        gitignore.write_text(store_tree.STORE_GITIGNORE, encoding="utf-8")
        gitignore.chmod(0)
        if os.access(gitignore, os.R_OK):
            gitignore.chmod(0o600)
            pytest.skip("running with privileges that ignore file modes")
    elif breakage == "invalid-utf8":
        gitignore.write_bytes(b"\xff\xfe\n")

    try:
        wrote = store_tree.ensure_store_gitignore(store_dir)
    except (OSError, UnicodeDecodeError):
        return  # failing loudly is allowed; a silent "already matching" is not
    finally:
        if breakage == "unreadable":
            gitignore.chmod(0o600)

    assert wrote is True, "a body it could not read counts as differing"
    assert gitignore.read_text(encoding="utf-8") == store_tree.STORE_GITIGNORE


def _one_line(text: str) -> bool:
    return len(text.strip("\n").splitlines()) == 1


def _run(argv: list[str]) -> int:
    try:
        return cli_main.main(argv)
    except SystemExit as exc:
        return exc.code


def _store(root: Path) -> tuple[Path, Path]:
    """`<root>/docs/dev/project-management` and the state path inside it."""
    store_dir = root / "docs" / "dev" / "project-management"
    return store_dir, store_dir / "autopilot" / "state.json"


def test_cli_ensure_store_writes_the_gitignore_under_the_states_grandparent(
    tmp_path: Path,
    capsys: pytest.CaptureFixture,
) -> None:
    store_dir, state_path = _store(tmp_path)
    state_path.parent.mkdir(parents=True)
    state_path.write_text(json.dumps({"phase": "build"}), encoding="utf-8")

    code = _run(["ensure-store", "--state", str(state_path)])

    gitignore = store_dir / ".gitignore"
    assert code == 0
    assert gitignore.read_text(encoding="utf-8") == store_tree.STORE_GITIGNORE
    out = capsys.readouterr().out
    assert _one_line(out), out
    assert Path(out.strip()) == gitignore, "it reports the path it wrote"


def test_cli_ensure_store_is_a_silent_no_op_on_a_second_run(
    tmp_path: Path,
    capsys: pytest.CaptureFixture,
) -> None:
    store_dir, state_path = _store(tmp_path)
    state_path.parent.mkdir(parents=True)
    assert _run(["ensure-store", "--state", str(state_path)]) == 0
    capsys.readouterr()
    gitignore = store_dir / ".gitignore"
    stamp = gitignore.stat().st_mtime_ns

    code = _run(["ensure-store", "--state", str(state_path)])

    assert code == 0
    assert capsys.readouterr().out == "", "nothing written means nothing printed"
    assert gitignore.read_text(encoding="utf-8") == store_tree.STORE_GITIGNORE
    assert gitignore.stat().st_mtime_ns == stamp, "a matching body is left alone"


def test_cli_ensure_store_works_before_state_json_exists(
    tmp_path: Path,
    capsys: pytest.CaptureFixture,
) -> None:
    store_dir, state_path = _store(tmp_path)
    store_dir.mkdir(parents=True)

    code = _run(["ensure-store", "--state", str(state_path)])

    assert code == 0, "a from-empty batch has no state.json yet"
    assert not state_path.exists(), "the verb neither reads nor creates it"
    assert (store_dir / ".gitignore").read_text(
        encoding="utf-8"
    ) == store_tree.STORE_GITIGNORE
    assert _one_line(capsys.readouterr().out)


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Env:
    monkeypatch.setattr(notify_out, "notify", lambda *a, **k: None)
    monkeypatch.delenv("_AUTOPILOT_LANES", raising=False)
    return Env(tmp_path)


def test_enter_writes_the_store_gitignore_in_its_lifecycle_step(
    env: Env,
    capsys: pytest.CaptureFixture,
) -> None:
    env.write_state(_open_state())
    env.put("wip")

    out = env.run()

    assert out["stop"] is None, out
    assert (env.pm / ".gitignore").read_text(
        encoding="utf-8"
    ) == store_tree.STORE_GITIGNORE
    assert capsys.readouterr().out == "", "the step stays silent on stdout"


def test_enter_survives_a_failing_store_gitignore_write(
    env: Env,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def explode(store_dir: Path) -> bool:
        raise OSError("read-only store")

    monkeypatch.setattr(store_tree, "ensure_store_gitignore", explode)
    env.write_state(_open_state())
    env.put("wip")

    out = env.run()

    assert out["stop"] is None, "a .gitignore failure must not halt Phase 0"
    assert out["prd"] == PRD


if __name__ == "__main__":
    unittest.main()
