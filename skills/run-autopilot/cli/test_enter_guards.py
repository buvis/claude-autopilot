#!/usr/bin/env python3
"""Tests for cli/enter.py - the side effects that must return a `stop`
instead of raising: the backlog->wip move, the three state writes, the
design-doc read, an unmapped do_park exit code, and a `prds_dir` with no
grandparent. `enter()` promises exactly one dict naming where the session
goes next, so every failure below has to arrive as a `stop`, never as a
traceback. Split from test_enter.py for size; shares its Env harness.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from cli import enter, notify_out, schema, state, statectl
from cli.enter_harness import (
    HEAD,
    NOW,
    OTHER,
    PRD,
    Env,
    _cache,
    _design_doc,
    _fake_park,
    _open_state,
    _prd_text,
)


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Env:
    monkeypatch.setattr(notify_out, "notify", lambda *a, **k: None)
    monkeypatch.delenv("_AUTOPILOT_LANES", raising=False)
    return Env(tmp_path)


# -- the backlog -> wip move ---------------------------------------------------


def test_stops_mv_verify_when_the_move_raises(env: Env, monkeypatch) -> None:
    env.write_state(_open_state())
    src = env.put("backlog")
    dst = env.prds_dir / "wip" / PRD

    def raise_denied(*a, **k):
        raise PermissionError("denied")

    monkeypatch.setattr(shutil, "move", raise_denied)

    out = env.run()

    assert out["stop"] == "mv_verify"
    assert str(src) in out["detail"]
    assert str(dst) in out["detail"]
    assert "denied" in out["detail"]
    assert env.has("backlog")
    assert not env.has("wip")


# -- the three state writes ----------------------------------------------------


@pytest.mark.parametrize(
    "err",
    [
        OSError("disk full"),
        state.StateError("lock lost"),
        schema.SchemaError("batch.skips is not a list"),
    ],
    ids=["oserror", "stateerror", "schemaerror"],
)
def test_stops_state_write_failed_when_recording_a_skip_raises(
    env: Env,
    monkeypatch,
    err: Exception,
) -> None:
    env.write_state(_open_state())
    env.put("backlog", PRD, _prd_text(eligibility='"exit 1"'))  # skipped
    env.put("backlog", OTHER)  # eligible: selection still has a pick

    def raise_err(*a, **k):
        raise err

    monkeypatch.setattr(statectl, "mutate", raise_err)

    out = env.run()

    assert out["stop"] == "state_write_failed"
    assert str(err) in out["detail"]
    assert env.read_state()["batch"].get("skips", []) == []


def test_stops_state_write_failed_when_dropping_pause_reason_raises(
    env: Env,
    monkeypatch,
) -> None:
    err = OSError("state.json is read-only")
    pause = {"site": "reviewer_fail", "detail": "carl hung"}
    env.write_state(_open_state(pause_reason=pause))
    env.put("wip")

    def raise_err(*a, **k):
        raise err

    monkeypatch.setattr(statectl, "mutate", raise_err)

    out = env.run()

    assert out["stop"] == "state_write_failed"
    assert str(err) in out["detail"]
    assert env.read_state()["pause_reason"] == pause  # the drop never landed


def test_stops_state_write_failed_when_rewriting_catchup_mode_raises(
    env: Env,
    monkeypatch,
) -> None:
    err = OSError("disk full")
    env.write_state(_open_state(batch=_cache()))
    env.put("wip", PRD, _prd_text(catchup="skip"))
    real_mutate = statectl.mutate

    def raise_once_catchup_mode_is_skip(*a, **k):
        # only the rewrite of the frontmatter's `skip` into `skipped` fails
        if env.read_state().get("catchup_mode") == "skip":
            raise err
        return real_mutate(*a, **k)

    monkeypatch.setattr(statectl, "mutate", raise_once_catchup_mode_is_skip)

    out = env.run()

    assert out["stop"] == "state_write_failed"
    assert str(err) in out["detail"]
    assert env.read_state()["catchup_mode"] == "skip"  # the rewrite never landed


# -- the design-doc read -------------------------------------------------------


def test_stops_fs_error_when_the_design_doc_is_a_directory(env: Env) -> None:
    env.write_state(_open_state())
    env.put("wip", PRD, _prd_text(design="run"))
    doc = _design_doc(env)
    doc.mkdir(parents=True)

    out = env.run()

    assert out["stop"] == "fs_error"
    assert str(doc) in out["detail"]
    assert "Is a directory" in out["detail"]


def test_stops_fs_error_when_the_design_doc_is_not_utf8(env: Env) -> None:
    env.write_state(_open_state())
    env.put("wip", PRD, _prd_text(design="run"))
    doc = _design_doc(env)
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_bytes(b"# Design\n\n## Review log\n\n- dispatch 1 (codex): \xff\xfe\n")

    out = env.run()

    assert out["stop"] == "fs_error"
    assert str(doc) in out["detail"]
    assert "can't decode" in out["detail"]


# -- an unmapped do_park exit code ---------------------------------------------


def test_stops_park_halt_when_do_park_returns_an_unmapped_code(
    env: Env,
    monkeypatch,
) -> None:
    env.write_state(_open_state())
    env.put("wip")
    env.marker(PRD)
    _fake_park(monkeypatch, 7)

    out = env.run()

    assert out["stop"] == "park_halt"
    assert "7" in out["detail"]
    assert env.rows == []


# -- a prds_dir with no grandparent --------------------------------------------


def test_stops_fs_error_when_prds_dir_has_no_grandparent(
    tmp_path: Path,
    monkeypatch,
) -> None:
    # Env's prds_dir is deep, so this one builds its own shallow tree: a
    # relative one-component path has no `parents[1]` to hang docs/dev/tmp on.
    monkeypatch.setattr(notify_out, "notify", lambda *a, **k: None)
    monkeypatch.delenv("_AUTOPILOT_LANES", raising=False)
    monkeypatch.chdir(tmp_path)
    autopilot_dir = tmp_path / "autopilot"
    autopilot_dir.mkdir()
    state_path = autopilot_dir / "state.json"
    state_path.write_text(json.dumps(_open_state()), encoding="utf-8")

    out = enter.enter(
        state_path,
        prds_dir=Path("prds"),
        autopilot_dir=autopilot_dir,
        prd_arg=None,
        in_loop=False,
        now=lambda: NOW,
        git_head=lambda repo_root: HEAD,
        record_resume_row=lambda prd, site: None,
    )

    assert out["stop"] == "fs_error"
    assert "prds" in out["detail"]
