#!/usr/bin/env python3
"""Tests for the CLI wiring of `dirty` and `record-store`.

Driven in-process (`main(argv)`) with spies on the two git-touching
store_tree functions, so the test target is the argument parsing, the repo
resolution and the exit code / stdout contract, not the git logic in
store_tree itself.
"""

from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cli import __main__ as cli_main
from cli import custody, store_tree
from cli.store_tree_testutil import SHA, _autopilot_dir, _one_line, _write_state


def _spy(fn_name: str, answer: object, calls: list) -> object:
    """A stand-in for store_tree.<fn_name> recording its first positional
    parameters by the real signature, however the caller spelled them."""
    signature = inspect.signature(getattr(store_tree, fn_name))

    def spy(*args: object, **kwargs: object) -> object:
        calls.append(signature.bind(*args, **kwargs).args)
        return answer

    return spy


def _run(argv: list[str]) -> int:
    try:
        return cli_main.main(argv)
    except SystemExit as exc:
        return exc.code


def test_cli_dirty_exits_one_on_foreign_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
) -> None:
    repo = tmp_path / "elsewhere"
    state_path = _write_state(_autopilot_dir(tmp_path), {"repo_root": str(repo)})
    paths = ["src/b.py", "README.md", "dir with space/f.txt"]
    calls: list[tuple] = []
    monkeypatch.setattr(
        store_tree,
        "foreign_dirty",
        _spy("foreign_dirty", paths, calls),
    )

    code = _run(["dirty", "--state", str(state_path)])

    assert code == 1
    assert [args[:1] for args in calls] == [(repo,)], calls
    assert capsys.readouterr().out.splitlines() == paths


def test_cli_dirty_is_silent_and_exits_zero_on_a_clean_tree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
) -> None:
    repo = tmp_path / "elsewhere"
    state_path = _write_state(_autopilot_dir(tmp_path), {"repo_root": str(repo)})
    calls: list[tuple] = []
    monkeypatch.setattr(store_tree, "foreign_dirty", _spy("foreign_dirty", [], calls))

    code = _run(["dirty", "--state", str(state_path)])

    assert code == 0
    assert [args[:1] for args in calls] == [(repo,)], calls
    assert capsys.readouterr().out == ""


def test_cli_dirty_checks_the_project_root_when_state_has_no_repo_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
) -> None:
    state_path = _write_state(_autopilot_dir(tmp_path), {})
    calls: list[tuple] = []
    monkeypatch.setattr(store_tree, "foreign_dirty", _spy("foreign_dirty", [], calls))

    code = _run(["dirty", "--state", str(state_path)])

    assert code == 0
    assert [args[:1] for args in calls] == [(tmp_path,)], calls
    assert capsys.readouterr().out == ""


def test_cli_record_store_commits_with_the_site_and_prd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
) -> None:
    repo = tmp_path / "elsewhere"
    state_path = _write_state(_autopilot_dir(tmp_path), {"repo_root": str(repo)})
    calls: list[tuple] = []
    monkeypatch.setattr(store_tree, "record_store", _spy("record_store", SHA, calls))

    code = _run(
        [
            "record-store",
            "--state",
            str(state_path),
            "--site",
            "build",
            "--prd",
            "00007-feature-z.md",
        ],
    )

    assert code == 0
    assert [args[:3] for args in calls] == [(repo, "build", "00007-feature-z.md")]
    out = capsys.readouterr().out
    assert _one_line(out), out
    assert out.strip() == SHA


def test_cli_record_store_defaults_prd_to_empty_and_is_silent_when_nothing_changed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
) -> None:
    repo = tmp_path / "elsewhere"
    state_path = _write_state(_autopilot_dir(tmp_path), {"repo_root": str(repo)})
    calls: list[tuple] = []
    monkeypatch.setattr(store_tree, "record_store", _spy("record_store", None, calls))

    code = _run(["record-store", "--state", str(state_path), "--site", "review"])

    assert code == 0, "nothing to commit is still a success"
    assert [args[:3] for args in calls] == [(repo, "review", "")], calls
    assert capsys.readouterr().out == ""


def test_cli_record_store_refuses_to_run_without_a_site(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_path = _write_state(_autopilot_dir(tmp_path), {"repo_root": str(tmp_path)})
    calls: list[tuple] = []
    monkeypatch.setattr(store_tree, "record_store", _spy("record_store", SHA, calls))

    code = _run(["record-store", "--state", str(state_path), "--prd", "00007-x.md"])

    assert code not in (0, None)
    assert calls == [], "no record without a --site"


@pytest.mark.parametrize(
    "argv_tail",
    [["dirty"], ["record-store", "--site", "build"]],
    ids=["dirty", "record-store"],
)
@pytest.mark.parametrize(
    "state_text",
    [None, "{not json", "[]", json.dumps({"repo_root": ["x"]}), json.dumps({})],
    ids=[
        "no-state-file",
        "invalid-json",
        "list-body",
        "non-str-repo-root",
        "no-repo-root",
    ],
)
def test_cli_falls_back_to_the_project_root_of_any_state_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
    argv_tail: list[str],
    state_text: str | None,
) -> None:
    state_dir = tmp_path / "w" / "x" / "y" / "z"
    state_dir.mkdir(parents=True)
    state_path = state_dir / "state.json"
    if state_text is not None:
        state_path.write_text(state_text, encoding="utf-8")
    fn_name = "foreign_dirty" if argv_tail[0] == "dirty" else "record_store"
    answer = [] if fn_name == "foreign_dirty" else None
    calls: list[tuple] = []
    monkeypatch.setattr(store_tree, fn_name, _spy(fn_name, answer, calls))

    code = _run([argv_tail[0], "--state", str(state_path), *argv_tail[1:]])

    assert code == 0, "an unusable state.json falls back, it never crashes the CLI"
    assert [args[:1] for args in calls] == [
        (custody.project_root(state_dir),),
    ], "the repo comes from the state file's own directory, not a fixed layout"
    assert capsys.readouterr().out == ""
