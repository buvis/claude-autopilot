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
from cli import notify_out, store_tree
from cli.enter_harness import PRD, Env, _arrange, _open_state


@pytest.mark.parametrize(
    "breakage",
    ["missing-store-dir", "unreadable", "invalid-utf8"],
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


def _recorder(monkeypatch: pytest.MonkeyPatch, *, fail: bool = False) -> list[Path]:
    """Record every `store_tree.ensure_store_gitignore` store dir, then do the
    real write (or raise, when `fail`). A caller that hand-copies the writer
    instead of calling the shared one records nothing."""
    calls: list[Path] = []
    real = store_tree.ensure_store_gitignore

    def record(store_dir: Path) -> bool:
        calls.append(Path(store_dir))
        if fail:
            raise OSError("read-only store")
        return real(store_dir)

    monkeypatch.setattr(store_tree, "ensure_store_gitignore", record)
    return calls


@pytest.mark.parametrize(
    "layout",
    [
        "docs/dev/project-management/autopilot/state.json",
        "docs/dev/project-management/elsewhere/state.json",
        "store/autopilot/nested/state.json",
    ],
)
def test_cli_ensure_store_writes_the_gitignore_under_the_states_grandparent(
    tmp_path: Path,
    capsys: pytest.CaptureFixture,
    layout: str,
) -> None:
    state_path = tmp_path / layout
    state_path.parent.mkdir(parents=True)
    state_path.write_text(json.dumps({"phase": "build"}), encoding="utf-8")

    code = _run(["ensure-store", "--state", str(state_path)])

    gitignore = state_path.parents[1] / ".gitignore"
    assert code == 0
    assert gitignore.read_text(encoding="utf-8") == store_tree.STORE_GITIGNORE
    out = capsys.readouterr().out
    assert _one_line(out), out
    assert Path(out.strip()) == gitignore, "it reports the path it wrote"


def test_cli_ensure_store_routes_through_the_shared_writer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
) -> None:
    store_dir, state_path = _store(tmp_path)
    state_path.parent.mkdir(parents=True)
    calls = _recorder(monkeypatch)

    code = _run(["ensure-store", "--state", str(state_path)])

    assert code == 0
    assert calls == [store_dir], "the body may not fork from STORE_GITIGNORE"
    assert (store_dir / ".gitignore").read_text(
        encoding="utf-8",
    ) == store_tree.STORE_GITIGNORE
    assert Path(capsys.readouterr().out.strip()) == store_dir / ".gitignore"


def test_cli_ensure_store_rewrites_a_differing_body_then_leaves_a_matching_one(
    tmp_path: Path,
    capsys: pytest.CaptureFixture,
) -> None:
    store_dir, state_path = _store(tmp_path)
    state_path.parent.mkdir(parents=True)
    gitignore = store_dir / ".gitignore"
    gitignore.write_text("junk\n", encoding="utf-8")

    assert _run(["ensure-store", "--state", str(state_path)]) == 0

    first = capsys.readouterr().out
    assert Path(first.strip()) == gitignore, first
    assert gitignore.read_text(encoding="utf-8") == store_tree.STORE_GITIGNORE
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
        encoding="utf-8",
    ) == store_tree.STORE_GITIGNORE
    assert _one_line(capsys.readouterr().out)


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Env:
    monkeypatch.setattr(notify_out, "notify", lambda *a, **k: None)
    monkeypatch.delenv("_AUTOPILOT_LANES", raising=False)
    return Env(tmp_path)


@pytest.mark.parametrize(
    ("arrangement", "expected_stop"),
    [("open-batch", None), ("no-state-json", "batch_init"), ("drained", "drained")],
)
def test_enter_writes_the_store_gitignore_in_its_lifecycle_step(
    env: Env,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
    arrangement: str,
    expected_stop: str | None,
) -> None:
    calls = _recorder(monkeypatch)
    if arrangement == "no-state-json":
        env.put("wip")  # a from-empty batch: enter() bootstraps state.json
    elif arrangement == "drained":
        _arrange(env, monkeypatch, "drained")
    else:
        env.write_state(_open_state())
        env.put("wip")

    out = env.run()

    assert out["stop"] == expected_stop, out
    assert calls == [env.pm], "the step calls store_tree's writer on the store dir"
    assert (env.pm / ".gitignore").read_text(
        encoding="utf-8",
    ) == store_tree.STORE_GITIGNORE
    if arrangement == "open-batch":
        assert capsys.readouterr().out == "", "the step stays silent on stdout"


def test_enter_survives_a_failing_store_gitignore_write(
    env: Env,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _recorder(monkeypatch, fail=True)
    env.write_state(_open_state())
    env.put("wip")

    out = env.run()

    assert calls == [env.pm], "the raising writer is the one enter() called"
    assert out["stop"] is None, "a .gitignore failure must not halt Phase 0"
    assert out["prd"] == PRD


if __name__ == "__main__":
    unittest.main()
