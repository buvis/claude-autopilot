#!/usr/bin/env python3
"""Tests for cli/enter.py - the Phase 0 step chain run as one call.

`enter()` composes existing modules (state, records.do_park, custody,
selection, frontmatter, lane, resume) and returns one JSON-serializable dict.
These tests drive it against a real on-disk project-management tree; only
the three injected side effects (clock, `git rev-parse HEAD`, the cross-pack
handoff row) are faked, plus the few failure modes a real tree cannot
produce on demand (a do_park exit 4/9, a failed move, a failed write).
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from cli import custody, enter, enter_io, frontmatter, handoff, notify_out, records, resume, state
from cli.enter_harness import (
    BATCH_ID,
    DISPATCH_LINE,
    EARLY,
    EXPECTED_STOPS,
    HEAD,
    OTHER,
    PRD,
    Env,
    _arrange,
    _cache,
    _custody_entry,
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


# -- STOPS ---------------------------------------------------------------------


def test_every_stop_value_is_in_STOPS() -> None:
    assert enter.STOPS == EXPECTED_STOPS
    assert len(set(enter.STOPS)) == len(enter.STOPS)


# `cli/enter.py`'s import hygiene (no import-time `sys.path` mutation, no
# `importlib`, the marker tuple reached by a plain package import) is pinned
# structurally in `test_enter_guards.py`; the behavioural half lives below.


# -- the null-stop path --------------------------------------------------------


def test_fresh_wip_prd_continues_with_null_stop(env: Env, capsys) -> None:
    env.write_state(_open_state())
    env.put("wip")
    for name in handoff.MARKERS:
        (env.autopilot_dir / name).write_text("x", encoding="utf-8")

    out = env.run()

    assert out == {
        "stop": None,
        "detail": "",
        "prd": PRD,
        "source": "wip",
        "parked": None,
        "custody_pending": 0,
        "lane_effective": "full",
        "catchup": "full",
        "design": "skip",
        "resume_target": "build: catchup then planning",
        "batch": "open",
        "warnings": [],
    }
    assert env.read_state()["prd"] == PRD
    assert env.rows == [(PRD, "build")]
    for name in handoff.MARKERS:
        assert not (env.autopilot_dir / name).exists()
    assert capsys.readouterr().out == ""


def test_the_marker_clear_step_removes_exactly_cli_handoff_MARKERS(
    env: Env, monkeypatch
) -> None:
    # The behavioural half of requirement A: the names must be READ from
    # `cli.handoff.MARKERS` when the step runs. A hardcoded tuple, the
    # `scripts/_walk_up.py` duplicate, or a module-level copy taken at import
    # time all ignore this patch and leave the sentinel on disk, while a merely
    # structural `from . import handoff` pin would call them all satisfied.
    monkeypatch.setattr(handoff, "MARKERS", (".sentinel-marker",))
    env.write_state(_open_state())
    env.put("wip")
    (env.autopilot_dir / ".sentinel-marker").write_text("x", encoding="utf-8")
    (env.autopilot_dir / ".handoff-requested").write_text("x", encoding="utf-8")

    out = env.run()

    assert out["stop"] is None
    assert not (env.autopilot_dir / ".sentinel-marker").exists(), (
        "cli/enter.py: the marker clear step must remove every basename in "
        "`cli.handoff.MARKERS` as read at call time — `.sentinel-marker` "
        "survived, so the names came from somewhere else."
    )
    assert (env.autopilot_dir / ".handoff-requested").exists(), (
        "cli/enter.py: the marker clear step removed `.handoff-requested`, a "
        "name `cli.handoff.MARKERS` does not hold here — the step must clear "
        "that tuple, not a second list of hand-off filenames of its own."
    )


def test_a_fresh_cache_and_a_reviewed_design_doc_reuse_both(env: Env) -> None:
    # The counterpart of the run above, and the reason both dicts are written
    # out in full: these two fixtures differ in their catchup AND design
    # decisions, so no single canned reply can satisfy both.
    env.write_state(_open_state(batch=_cache()))
    env.put("wip", PRD, _prd_text(design="run"))
    doc = _design_doc(env)
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text(
        f"# Design\n\n## Review log\n\n{DISPATCH_LINE}\n",
        encoding="utf-8",
    )

    out = env.run()

    assert out == {
        "stop": None,
        "detail": "",
        "prd": PRD,
        "source": "wip",
        "parked": None,
        "custody_pending": 0,
        "lane_effective": "full",
        "catchup": "delta",
        "design": "reuse",
        "resume_target": "build: catchup then planning",
        "batch": "open",
        "warnings": [],
    }


def test_bootstrap_without_state_json_proceeds_through_selection(env: Env) -> None:
    env.put("wip")
    assert not env.state_path.exists()

    out = env.run()

    assert out["stop"] == "batch_init"
    assert out["batch"] == "absent"
    assert (out["prd"], out["source"]) == (PRD, "wip")
    assert env.state_path.exists()
    for name in ("backlog", "wip", "done", "hold"):
        assert (env.prds_dir / name).is_dir()
    assert (env.pm / "reviews").is_dir()
    assert (env.root / "docs" / "dev" / "tmp").is_dir()
    assert (env.autopilot_dir / "reports").is_dir()
    assert (env.autopilot_dir / "deferred").is_dir()


def test_resume_target_matches_the_resume_target_verb(env: Env) -> None:
    tasks = [
        {"id": "t1", "name": "a", "status": "completed"},
        {"id": "t2", "name": "b", "status": "pending"},
    ]
    fixture = _open_state(tasks=tasks)
    env.write_state(fixture)
    env.put("wip")

    out = env.run()

    assert out["resume_target"] == resume.resume_target(fixture)
    assert out["resume_target"] == "/work continues at first non-completed task t2"


def test_raising_resume_row_is_swallowed_to_stderr(env: Env, capsys) -> None:
    env.write_state(_open_state())
    env.put("wip")

    def boom(prd: str, site: str, autopilot_dir: Path) -> None:
        raise OSError("record_dispatch unreachable")

    out = env.run(record_resume_row=boom)

    assert out["stop"] is None
    assert out["prd"] == PRD
    captured = capsys.readouterr()
    assert captured.err.strip() != ""
    assert captured.out == ""


def test_default_record_dispatch_path_exists_in_the_repo() -> None:
    assert enter_io._RECORD_DISPATCH.exists()
    assert enter_io._RECORD_DISPATCH.parts[-3:] == (
        "work",
        "scripts",
        "record_dispatch.py",
    )


# -- selection -----------------------------------------------------------------


def test_backlog_pick_is_moved_and_verified(env: Env) -> None:
    env.write_state(_open_state())
    env.put("backlog")

    out = env.run()

    assert (out["stop"], out["prd"], out["source"]) == (None, PRD, "backlog")
    assert env.has("wip")
    assert not env.has("backlog")


def test_failed_move_stops_mv_verify(env: Env, monkeypatch) -> None:
    env.write_state(_open_state())
    env.put("backlog")
    monkeypatch.setattr(shutil, "move", lambda src, dst, *a, **k: str(dst))

    out = env.run()

    assert out["stop"] == "mv_verify"
    assert out["detail"] != ""
    assert out["resume_target"] is not None
    assert env.has("backlog")
    assert not env.has("wip")


def test_drained_stops(env: Env) -> None:
    env.write_state(_open_state())
    env.put("backlog", "FASTTRACK-PLAN-v5.md")

    out = env.run()

    assert out["stop"] == "drained"
    assert (out["prd"], out["source"], out["batch"]) == (None, None, None)


def test_ineligible_backlog_prd_is_skipped_and_recorded(env: Env) -> None:
    env.write_state({"phase": "build", "next_phase": "build"})
    env.put("backlog", PRD, _prd_text(eligibility='"exit 1"'))
    env.put("backlog", OTHER)

    out = env.run()

    assert (out["prd"], out["source"]) == (OTHER, "backlog")
    assert env.has("backlog", PRD)
    skips = env.read_state()["batch"]["skips"]
    assert len(skips) == 1
    # field names are not pinned here; the record must carry these values
    assert PRD in skips[0].values()
    assert "exit 1" in skips[0].values()
    assert 1 in [v for v in skips[0].values() if type(v) is int]
    # skips alone carry no batch.id, so the batch still reads absent
    assert (out["stop"], out["batch"]) == ("batch_init", "absent")


@pytest.mark.parametrize(
    "command",
    ["true", "test -f 00010-eligibility-evidence.md"],
    ids=["exit-0", "repo-relative-check"],
)
def test_eligible_backlog_prd_is_picked_without_a_skip_record(
    env: Env, command: str
) -> None:
    # the evidence file exists only at the project root: the check must run there
    (env.root / "00010-eligibility-evidence.md").write_text("x", encoding="utf-8")
    env.write_state(_open_state())
    env.put("backlog", PRD, _prd_text(eligibility=f'"{command}"'))
    env.put("backlog", OTHER)

    out = env.run()

    assert (out["stop"], out["prd"], out["source"]) == (None, PRD, "backlog")
    assert env.has("wip", PRD)
    assert env.read_state()["batch"].get("skips", []) == []


@pytest.mark.parametrize("folder", ["wip", "backlog"])
def test_prd_arg_is_taken_from_wip_or_backlog(env: Env, folder: str) -> None:
    env.write_state(_open_state())
    env.put(folder)
    env.put("wip", "00001-lower-in-wip.md")

    out = env.run(prd_arg=PRD)

    assert (out["stop"], out["prd"], out["source"]) == (None, PRD, "arg")
    assert env.has("wip")
    assert not env.has("backlog")


def test_prd_arg_absent_from_wip_and_backlog_stops_prd_not_found(env: Env) -> None:
    env.write_state(_open_state())
    env.put("wip", OTHER)
    env.put("hold")

    out = env.run(prd_arg=PRD)

    assert out["stop"] == "prd_not_found"
    assert "bare basename" not in out["detail"].lower()
    assert out["batch"] is None
    assert env.has("hold")


# -- park (step 4) -------------------------------------------------------------


def test_park_exit_three_continues(env: Env) -> None:
    env.write_state(_open_state())
    env.put("wip")
    env.marker("00001-stale-not-in-wip.md")  # stale marker: do_park exits 3

    out = env.run()

    assert (out["stop"], out["parked"], out["prd"]) == (None, None, PRD)


def test_park_exit_zero_sets_parked(env: Env, capsys) -> None:
    env.write_state(_open_state(prd=PRD))
    env.put("wip")
    env.put("backlog", OTHER)
    env.marker(PRD)

    out = env.run()

    assert out["parked"] == PRD
    assert (out["stop"], out["prd"], out["source"]) == (None, OTHER, "backlog")
    assert env.has("hold")
    assert not (env.autopilot_dir / "park-requested").exists()
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize(
    ("code", "stop"),
    [(5, "park_halt"), (4, "mv_verify"), (9, "deferred_io"), (10, "stall_op_conflict")],
)
def test_park_halt_codes_map_to_their_stops(
    env: Env, monkeypatch, code: int, stop: str
) -> None:
    env.write_state(_open_state())
    env.put("wip")
    env.marker(PRD)
    _fake_park(monkeypatch, code)

    out = env.run()

    assert out["stop"] == stop
    assert (out["resume_target"], out["batch"], out["prd"]) == (None, None, None)
    assert env.rows == []
    assert out["detail"] != ""
    if code == 5:
        assert (
            out["detail"]
            == f"parked {PRD}; systemic halt (2+ consecutive wrapper_died parks)"
        )
    # One expectation per code, stated OUTSIDE the branch. Exit 5 parked the PRD
    # and then halted, so both facts are reported; 4, 9 and 10 halt with the park
    # INCOMPLETE (the move to hold/ or the record write failed), so `parked` has
    # to stay null. A collapse of these branches into one leaks in both
    # directions — dropping `parked` on 5, or claiming a park that never
    # happened on the rest — and every assertion above still passes either way.
    expected_parked = PRD if code == 5 else None
    assert out["parked"] == expected_parked, (
        f"cli/enter.py: a do_park exit of {code} must report `parked` as "
        f"{expected_parked!r} — 5 is the one halt code that parked {PRD} first; "
        "4, 9 and 10 mean the park did not complete, so naming a parked PRD "
        "there tells the session a PRD reached hold/ while it is still in wip/. "
        f"Got {out['parked']!r}."
    )


def test_park_exit_two_from_reconciliation_stops_park_precondition_failed(
    env: Env,
) -> None:
    # A well-formed pending stall_op passes step 3; do_stall's own guard then
    # refuses the missing batch.id inside do_park -> exit 2.
    env.write_state(
        {
            "prd": PRD,
            "phase": "build",
            "next_phase": "build",
            "batch": {"skips": []},
            "stall_op": {
                "op_id": "op-1",
                "prd": PRD,
                "site": "design_gate",
                "detail": "d",
            },
        }
    )
    env.put("wip")

    out = env.run()

    assert out["stop"] == "park_precondition_failed"
    assert "2" in out["detail"]
    assert "do_stall" in out["detail"]
    assert out["resume_target"] is None


# -- state load + stall_op precheck (step 3) -----------------------------------


@pytest.mark.parametrize("stall_op", ["junk", {"prd": PRD}, {"op_id": "op-1"}])
def test_malformed_stall_op_stops_before_park(env: Env, monkeypatch, stall_op) -> None:
    env.write_state(_open_state(stall_op=stall_op))
    env.put("wip")
    calls: list[object] = []
    monkeypatch.setattr(records, "do_park", lambda *a, **k: calls.append(a) or 3)

    out = env.run()

    assert out["stop"] == "stall_op_malformed"
    assert out["resume_target"] is None
    assert calls == []


def test_absent_stall_op_does_not_stop_malformed(env: Env) -> None:
    env.write_state(_open_state())
    env.put("wip")

    assert env.run()["stop"] != "stall_op_malformed"


def test_corrupt_state_file_raises_state_error_not_a_stop(env: Env) -> None:
    env.state_path.write_text("{not json", encoding="utf-8")
    env.put("wip")

    with pytest.raises(state.StateError):
        env.run()


# -- stall / cap-pause (step 5) ------------------------------------------------


def test_prompt_overrun_stops_replan(env: Env) -> None:
    stall = {"stalled": "subagent_prompt_overrun"}
    env.write_state(_open_state(prd=PRD, stall_reason=stall))
    env.put("wip")

    out = env.run()

    assert out["stop"] == "replan"
    assert (out["resume_target"], out["batch"]) == (None, None)
    assert env.read_state()["stall_reason"] == stall


def test_escalation_exhausted_stops(env: Env) -> None:
    stall = {"stalled": "escalation_exhausted"}
    env.write_state(_open_state(prd=PRD, stall_reason=stall))
    env.put("wip")

    out = env.run()

    assert out["stop"] == "escalation_exhausted"
    assert (out["resume_target"], out["batch"]) == (None, None)
    assert env.read_state()["stall_reason"] == stall


def test_cap_pause_stops(env: Env) -> None:
    cap = {"cycle": 3, "cap": 3, "unresolved_findings": []}
    env.write_state(_open_state(phase="paused", next_phase="", cap_pause_reason=cap))
    env.put("wip")

    out = env.run()

    assert out["stop"] == "cap_pause"
    assert (out["resume_target"], out["batch"]) == (None, None)
    assert env.read_state()["phase"] == "paused"


def test_paused_without_cap_reason_does_not_stop_cap_pause(env: Env) -> None:
    env.write_state(_open_state(phase="paused", next_phase=""))
    env.put("wip")

    assert env.run()["stop"] != "cap_pause"


def test_pause_reason_is_deleted_before_the_checks(env: Env) -> None:
    pause = {"site": "reviewer_fail", "detail": "carl hung"}
    env.write_state(
        _open_state(
            pause_reason=pause,
            stall_reason={"stalled": "escalation_exhausted"},
        )
    )
    env.put("wip")

    out = env.run()

    assert out["stop"] == "escalation_exhausted"
    assert "pause_reason" not in env.read_state()


# -- custody (step 7) ----------------------------------------------------------


@pytest.mark.parametrize("in_loop", [False, True])
def test_custody_stops_outside_the_loop_only(env: Env, in_loop: bool) -> None:
    env.write_state(_open_state())
    env.put("wip")
    custody.write_marker(env.autopilot_dir / "critical-on-master", [_custody_entry()])

    out = env.run(in_loop=in_loop)

    assert out["custody_pending"] == 1
    if in_loop:
        assert (out["stop"], out["prd"]) == (None, PRD)
    else:
        assert (out["stop"], out["prd"], out["batch"]) == ("custody", None, None)
        assert out["resume_target"] is not None


def test_unreadable_custody_record_stops_deferred_io(env: Env) -> None:
    env.write_state(_open_state())
    env.put("wip")
    (env.autopilot_dir / "critical-on-master").write_text(
        '{"entries": "x"}', encoding="utf-8"
    )

    out = env.run(in_loop=True)

    assert out["stop"] == "deferred_io"
    assert out["detail"] != ""
    assert out["resume_target"] is not None


# -- batch report (step 9) -----------------------------------------------------


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ({"phase": "build", "next_phase": "build"}, "absent"),
        ({"phase": "build", "next_phase": "build", "batch": {"skips": []}}, "absent"),
        (_open_state(phase="done", next_phase=""), "closed"),
    ],
    ids=["no-batch", "batch-without-id", "closed"],
)
def test_absent_and_closed_batch_stop_batch_init(
    env: Env, data: dict, expected: str
) -> None:
    env.write_state(data)
    env.put("wip")

    out = env.run()

    assert (out["stop"], out["batch"]) == ("batch_init", expected)
    assert env.rows == []


# -- lane + frontmatter write (step 10) ----------------------------------------


def test_non_full_lane_stops_lane(env: Env) -> None:
    env.write_state(_open_state())
    env.put("wip", PRD, _prd_text(lane="solo"))

    out = env.run()

    assert out["stop"] == "lane"
    assert out["lane_effective"] == "solo"
    assert out["detail"] == "lane: solo (override)"
    assert (out["catchup"], out["design"]) == (None, None)
    # the handoff row and the prd write land BEFORE the lane stop
    assert env.rows == [(PRD, "build")]
    assert env.read_state()["prd"] == PRD


@pytest.mark.parametrize("err", [OSError("disk full"), state.StateError("lock lost")])
def test_failed_frontmatter_write_stops_state_write_failed(
    env: Env, monkeypatch, err
) -> None:
    env.write_state(_open_state())
    env.put("wip")

    def raise_err(prd_path, state_path):
        raise err

    monkeypatch.setattr(frontmatter, "apply", raise_err)

    out = env.run()

    assert out["stop"] == "state_write_failed"
    assert out["detail"] == str(err)


# -- catchup decision (step 11) ------------------------------------------------


@pytest.mark.parametrize(
    ("catchup_key", "tasks", "batch", "head", "expected"),
    [
        (None, None, _cache(), HEAD, "delta"),
        (
            "force",
            [{"id": "t1", "name": "a", "status": "pending"}],
            _cache(),
            HEAD,
            "delta",
        ),
        ("force", None, _cache(), HEAD, "full"),
        (None, None, _cache(catchup_completed_at="2026-09-29T07:00:00Z"), HEAD, "full"),
        (None, None, {"id": BATCH_ID, "catchup_head_sha": HEAD}, HEAD, "full"),
        (None, None, _cache(catchup_head_sha="d" * 40), HEAD, "full"),
        (None, None, _cache(), None, "full"),
    ],
    ids=[
        "all-hold",
        "force-with-tasks",
        "force-no-tasks",
        "stale",
        "never-ran",
        "head-moved",
        "head-unreadable",
    ],
)
def test_catchup_delta_needs_all_three_conditions(
    env: Env,
    catchup_key,
    tasks,
    batch,
    head,
    expected,
) -> None:
    extra = {"tasks": tasks} if tasks is not None else {}
    env.write_state(_open_state(batch=batch, **extra))
    keys = {"catchup": catchup_key} if catchup_key else {}
    env.put("wip", PRD, _prd_text(**keys))
    env.head = head

    out = env.run()

    assert (out["stop"], out["catchup"]) == (None, expected)


def test_git_head_is_asked_about_the_project_root(env: Env) -> None:
    env.write_state(_open_state(batch=_cache()))
    env.put("wip")

    env.run()

    assert env.head_calls == [custody.project_root(env.autopilot_dir)]
    assert env.head_calls[0] == env.root


def test_catchup_skip_is_reported_and_written_as_skipped(env: Env) -> None:
    env.write_state(_open_state(batch=_cache()))
    env.put("wip", PRD, _prd_text(catchup="skip"))

    out = env.run()

    assert (out["stop"], out["catchup"]) == (None, "skip")
    assert env.read_state()["catchup_mode"] == "skipped"


# -- design decision (step 12) -------------------------------------------------


def test_design_runs_when_no_design_doc_exists(env: Env) -> None:
    env.write_state(_open_state())
    env.put("wip", PRD, _prd_text(design="run"))

    out = env.run()

    assert (out["stop"], out["design"]) == (None, "run")
    assert not _design_doc(env).exists()


@pytest.mark.parametrize(
    "line",
    [
        DISPATCH_LINE,
        "- dispatch 2 (claude): cardinal-sin 1, blocker 3, non-blocker 0, question 0",
        "dispatch 3 (claude-fallback): cardinal-sin 0, blocker 0, non-blocker 0, question 0",
    ],
    ids=["codex", "claude", "claude-fallback"],
)
def test_design_reuse_needs_a_review_log_line(env: Env, line: str) -> None:
    env.write_state(_open_state())
    env.put("wip", PRD, _prd_text(design="run"))
    doc = _design_doc(env)
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text(
        f"# Design\n\n## Review log\n\n{line}\n\n## Appendix\n", encoding="utf-8"
    )

    out = env.run()

    assert (out["stop"], out["design"]) == (None, "reuse")


@pytest.mark.parametrize(
    "body",
    [
        "# Design\n\n## Review log\n\n(none yet)\n",
        f"# Design\n\n## Review log\n\n## Notes\n\n{DISPATCH_LINE}\n",
        f"# Design\n\n{DISPATCH_LINE}\n\n## Review log\n",
        "# Design\n\n## Review log\n\n- dispatch 1 (gemini): cardinal-sin 0, blocker 0, "
        "non-blocker 0, question 0\n",
    ],
    ids=["empty", "line-in-later-section", "line-before-section", "unknown-engine"],
)
def test_empty_review_log_stops(env: Env, body: str) -> None:
    env.write_state(_open_state())
    env.put("wip", PRD, _prd_text(design="run"))
    doc = _design_doc(env)
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text(body, encoding="utf-8")

    out = env.run()

    assert out["stop"] == "design_review_log_empty"
    assert out["detail"] == f"{doc} has empty ## Review log (review never ran)"


# -- fs_error (steps 0/2) ------------------------------------------------------


@pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0, reason="root ignores modes"
)
def test_permission_denied_mkdir_stops_fs_error(env: Env) -> None:
    env.write_state(_open_state())
    env.pm.chmod(0o555)
    try:
        out = env.run()
    finally:
        env.pm.chmod(0o755)

    assert out["stop"] == "fs_error"
    assert out["detail"]
    assert (out["resume_target"], out["batch"]) == (None, None)


# -- null fields on early stops ------------------------------------------------


@pytest.mark.parametrize("stop", EARLY)
def test_resume_target_is_null_on_every_stop_before_step_six(
    env: Env, monkeypatch, stop
) -> None:
    _arrange(env, monkeypatch, stop)

    out = env.run()

    assert out["stop"] == stop
    assert out["resume_target"] is None


@pytest.mark.parametrize("stop", [*EARLY, "custody", "drained"])
def test_batch_is_null_on_every_stop_before_step_nine(
    env: Env, monkeypatch, stop
) -> None:
    _arrange(env, monkeypatch, stop)

    out = env.run()

    assert out["stop"] == stop
    assert out["batch"] is None
    assert env.rows == []


# The `enter` CLI verb's own tests live in `test_enter_cli.py`: the subprocess
# lane was split out of this file when it passed the 800-line limit.
