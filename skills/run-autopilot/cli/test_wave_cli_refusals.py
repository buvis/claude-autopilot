#!/usr/bin/env python3
"""Tests for the review/land/run refusal contract (task D1, PRD 00214 follow-up):
precondition and git failures must reach the operator as one `autopilot: ...`
line, not a raw traceback, and `review`/`land` must refuse a structurally
unsound `wave.json` (a hand-edited `id` such as `../x`) before building any
path from it. Split off from `test_wave_review.py` to keep that file under the
800-line style cap; its own fixtures (`_wave`/`_assembled`/`_landable`) stay
there, and this file builds its scenarios through the real `_planned`/`launch`
pipeline `test_wave_launch.py` uses instead.

`review()` uses the wave dict it is handed directly, so its precondition tests
pass a dict straight in. `land()` reloads `wave.json` fresh from `wave_path`
derived from `repo`, so its precondition tests write the scenario onto disk
and pass a dict that is never actually consulted, matching the existing
`test_land_*` tests in `test_wave_review.py`.

Every proof runs against a throwaway `git init` repo under `tmp_path`, never
this checkout's own backlog or `docs/dev/project-management/autopilot/wave.json`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cli import wave, wave_cli, wave_launch, wave_review
from cli.test_wave_launch import ONE_LANE, _FakeSpawn, _git, _parse, _planned, _repo
from cli.test_wave_review import _FakeLoop


def _no_traceback(text: str) -> bool:
    return "Traceback (most recent call last)" not in text


def _tree(root: Path) -> list[str]:
    """Every path under `root`, relative and sorted - a snapshot cheap enough
    to diff before/after a call that must refuse before touching disk."""
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*"))


def _assembled_from_a_real_launch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    status: str,
) -> tuple[Path, Path, dict]:
    """A wave that passes `_structural_errors` in full: planned and launched
    for real (so `id`, `repo`, `review_slots` and the lane shape are all
    genuine), then hand-advanced to `status` with an `assembly` block - a
    field `_structural_errors` never validates - pointing at the lane's own
    (already real) worktree."""
    repo, wave_path = _planned(tmp_path, monkeypatch, ONE_LANE, max_lanes=1)
    assert wave_launch.launch(repo, wave_path, spawn_fn=_FakeSpawn()) == 0
    saved = wave.load(wave_path)
    saved["status"] = status
    saved["assembly"] = {
        "worktree": saved["lanes"][0]["worktree"],
        "head_sha": saved["base_sha"],
        "merged": [],
    }
    wave.save(wave_path, saved)
    assert wave._structural_errors(repo, saved) == []
    return repo, wave_path, saved


# ── wave_cli.run: review/land/run report a reason instead of a traceback ──


def test_run_review_reports_a_not_yet_assembled_wave_instead_of_raising(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo, wave_path = _planned(tmp_path, monkeypatch, ONE_LANE, max_lanes=1)
    assert wave_launch.launch(repo, wave_path, spawn_fn=_FakeSpawn()) == 0
    capsys.readouterr()  # the fixture's own plan listing, not the verb's output

    exit_code = wave_cli.run(_parse(["wave", "review"]), repo, wave_path)

    assert exit_code == 1
    printed = capsys.readouterr()
    assert "autopilot: " in printed.err, printed
    assert "assembly" in printed.err, printed
    assert _no_traceback(printed.out + printed.err)


def test_run_land_reports_a_failed_git_call_instead_of_raising(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # No `wave/<id>/assembly` branch was ever created, so `_land_converged`'s
    # own `git rev-parse <branch>` fails - a real CalledProcessError, not an
    # injected fake, from the first git call land() makes past its checks.
    repo, wave_path, saved = _assembled_from_a_real_launch(
        tmp_path,
        monkeypatch,
        status="converged",
    )
    capsys.readouterr()
    before_head = _git(repo, "rev-parse", "HEAD").stdout.strip()

    exit_code = wave_cli.run(_parse(["wave", "land"]), repo, wave_path)

    assert exit_code == 1
    printed = capsys.readouterr()
    combined = printed.out + printed.err
    assert "autopilot: " in combined, printed
    assert "non-zero exit status" in combined, printed
    assert _no_traceback(combined)
    assert _git(repo, "rev-parse", "HEAD").stdout.strip() == before_head
    assert wave.load(wave_path) == saved


def test_run_land_prints_a_reason_when_review_failed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """land()'s own 4 (review failed, nothing to land) must stay the wave_cli
    return value - but the operator sees why, instead of a bare exit code."""
    repo, wave_path, _ = _assembled_from_a_real_launch(
        tmp_path,
        monkeypatch,
        status="review_failed",
    )
    capsys.readouterr()

    exit_code = wave_cli.run(_parse(["wave", "land"]), repo, wave_path)

    assert exit_code == 4
    printed = capsys.readouterr()
    assert (printed.out + printed.err).strip() != "", printed


def test_run_wave_run_reports_a_precondition_failure_instead_of_raising(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo, wave_path = _repo(tmp_path, {})
    monkeypatch.chdir(tmp_path)

    def boom(*_args: object, **_kwargs: object) -> int:
        raise RuntimeError("simulated precondition failure")

    monkeypatch.setattr(wave, "plan", boom)

    exit_code = wave_cli.run(
        _parse(["wave", "run", "--yes"]),
        repo,
        wave_path,
    )

    assert exit_code == 1
    printed = capsys.readouterr()
    combined = printed.out + printed.err
    assert "autopilot: " in combined, printed
    assert "simulated precondition failure" in combined, printed
    assert _no_traceback(combined)
    assert not wave_path.exists()


# ── review()/land(): a wave.json whose id is not a plain basename ─────────


def test_review_refuses_a_wave_id_that_is_not_a_plain_basename(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path, saved = _assembled_from_a_real_launch(
        tmp_path,
        monkeypatch,
        status="assembled",
    )
    saved["id"] = "../x"
    wave.save(wave_path, saved)
    assert wave._structural_errors(repo, saved) != []
    before = _tree(tmp_path)
    spawn = _FakeLoop()

    with pytest.raises(ValueError):
        wave_review.review(repo, saved, spawn_fn=spawn)

    assert _tree(tmp_path) == before
    assert spawn.calls == []


def test_land_refuses_a_wave_id_that_is_not_a_plain_basename(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path, saved = _assembled_from_a_real_launch(
        tmp_path,
        monkeypatch,
        status="converged",
    )
    saved["id"] = "../x"
    wave.save(wave_path, saved)
    assert wave._structural_errors(repo, saved) != []
    before = _tree(tmp_path)

    with pytest.raises(ValueError):
        wave_review.land(repo, saved)

    assert _tree(tmp_path) == before
    assert wave.load(wave_path) == saved


# ── wave_review._seed_batch: a clear failure, not a bare KeyError/FNF ─────


def _plugin_entry(version: str) -> list[dict]:
    return [{"version": version}]


def _installed(*, omit: str | None = None) -> dict:
    plugins = {
        "aegis@buvis-plugins": _plugin_entry("0.3.2"),
        "warden@buvis-plugins": _plugin_entry("1.4.0"),
    }
    if omit is not None:
        del plugins[omit]
    return {"version": 2, "plugins": plugins}


@pytest.mark.parametrize(
    "missing_plugin",
    ["aegis@buvis-plugins", "warden@buvis-plugins"],
)
def test_seed_batch_raises_naming_the_file_and_the_missing_pinned_plugin(
    tmp_path: Path,
    missing_plugin: str,
) -> None:
    plugins_json = tmp_path / "installed_plugins.json"
    plugins_json.write_text(
        json.dumps(_installed(omit=missing_plugin)),
        encoding="utf-8",
    )

    with pytest.raises((ValueError, RuntimeError)) as raised:
        wave_review._seed_batch(plugins_json, {"id": "202609281200"})

    message = str(raised.value)
    assert str(plugins_json) in message, message
    assert missing_plugin in message, message


def test_seed_batch_raises_naming_the_missing_plugins_file(tmp_path: Path) -> None:
    plugins_json = tmp_path / "installed_plugins.json"  # never written

    with pytest.raises((ValueError, RuntimeError)) as raised:
        wave_review._seed_batch(plugins_json, {"id": "202609281200"})

    assert str(plugins_json) in str(raised.value)
