"""Port of the `test_autoclaude_build_model.sh` contract (PRD 00106).

Every unit scenario from the bash suite lands here with its rationale
compressed into the test name; the bash e2e rows (launch-line --model
assertions through a real `autoclaude` run) are re-expressed against
the loop driver in test_loop.py. The bash suite's stdout/stderr/exit-0
rows become "returns a string, never raises" by construction.

Contract pinned:
* target PRD = lowest 00XXX- basename in wip/, else backlog/ - never
  state.prd, which between PRDs still names the FINISHED one;
* OPUS when ANY of: (1) target frontmatter session_model: opus (PRD 00200;
  default_model floors the task tier and no longer promotes the session),
  (2) state.replan_count > 0, (3a) state.stall_reason != null,
  (3b) a type:"stall" item naming the target in the 2 NEWEST
  deferred logs by FILENAME, (4) state.cap_rotations non-empty,
  (5) a ledger key equal to the target; 2/3a/4 fire ONLY when
  state.prd == target;
* loop metrics are IGNORED (signal 6 retired, PRD 00111);
* promotion is recomputed every call - no latch.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cli.loop import Loop
from cli.routing import (
    OPUS,
    SONNET,
    Route,
    build_model,
    build_target,
    review_cycle,
    route,
)


def _box(tmp_path: Path) -> Path:
    for sub in ("prds/wip", "prds/backlog", "prds/done", "prds/hold", "deferred"):
        (tmp_path / sub).mkdir(parents=True, exist_ok=True)
    (tmp_path / "ledger.json").write_text("{}\n")
    return tmp_path


def _write_prd(path: Path, session_model: str | None = None) -> None:
    text = ""
    if session_model is not None:
        text = (
            "---\ncatchup: skip\nrework_cap: 3\n"
            f"session_model: {session_model}\ndesign: skip\n---\n"
        )
    text += f"\n# {path.name}\n\n## Problem\n\nFixture PRD.\n"
    path.write_text(text)


def _write_prd_fm(path: Path, body: str) -> None:
    path.write_text(f"---\n{body}\n---\n\n# {path.name}\n\nFixture PRD.\n")


def _state(box: Path, prd: str, **overrides) -> None:
    state = {
        "prd": prd,
        "next_phase": "build",
        "replan_count": 0,
        "cap_rotations": [],
        "stall_reason": None,
        "batch": {"id": "20260701-a"},
    }
    state.update(overrides)
    (box / "state.json").write_text(json.dumps(state))


def _model(box: Path) -> str:
    return build_model(
        box / "state.json",
        box / "prds",
        box / "ledger.json",
        box / "deferred",
    )


def test_no_signals_routes_sonnet(tmp_path):
    # Fields present and EXPLICITLY ZERO - presence-testing routes every
    # session to Opus, the regression PRD 00076 exists to stop. The
    # ledger holds a DIFFERENT PRD's key: signal 5 is target-keyed.
    box = _box(tmp_path)
    prd = "00021-rotate-session-logs-v1.md"
    _write_prd(box / "prds/wip" / prd)
    _state(box, prd)
    (box / "ledger.json").write_text(
        json.dumps({"00097-unrelated-rescue-v1.md": {"status": "approved"}}),
    )
    assert _model(box) == SONNET


def test_finished_prds_scratch_never_promotes_the_next_prd(tmp_path):
    # PRD-to-PRD launch: state.json still describes the DONE PRD (replan,
    # rotation, stall, ledger key, deferred stall, opus frontmatter).
    # None of it may promote the fresh backlog PRD.
    box = _box(tmp_path)
    done, nxt = "00034-purge-orphan-worktrees-v1.md", "00035-stamp-release-notes-v1.md"
    _write_prd(box / "prds/done" / done, "opus")
    _write_prd(box / "prds/backlog" / nxt)
    _state(
        box,
        done,
        replan_count=1,
        cap_rotations=[{"task_id": "task-2", "cycle": 1}],
        stall_reason={"stalled": "oversized_task", "detail": "task-2 overflowed"},
    )
    (box / "ledger.json").write_text(json.dumps({done: {"status": "consumed"}}))
    (box / "deferred" / "20260701-b-deferred.json").write_text(
        json.dumps({"items": [{"type": "stall", "site": "x", "prd": done}]}),
    )
    assert _model(box) == SONNET


def test_a_wip_siblings_scratch_never_promotes_the_target(tmp_path):
    # The .prd guard with BOTH PRDs in wip/: the scratch belongs to the
    # higher-numbered sibling state.json names, not to the target.
    box = _box(tmp_path)
    target = "00037-trim-the-boot-scan-v1.md"
    sibling = "00039-cache-the-catchup-capsule-v1.md"
    _write_prd(box / "prds/wip" / target)
    _write_prd(box / "prds/wip" / sibling, "opus")
    _state(
        box,
        sibling,
        replan_count=2,
        cap_rotations=[{"task_id": "task-5", "cycle": 1}],
        stall_reason={"stalled": "oversized_task", "detail": "sibling overflowed"},
    )
    assert _model(box) == SONNET


def test_lowest_wip_prd_wins_over_backlog_and_higher_wip(tmp_path):
    box = _box(tmp_path)
    _write_prd(box / "prds/wip" / "00048-rehome-the-cache-dir-v1.md", "opus")
    _write_prd(box / "prds/wip" / "00061-split-render-stream-v1.md", "sonnet")
    _write_prd(box / "prds/backlog" / "00012-fix-the-banner-typo-v1.md", "sonnet")
    _state(box, "")
    assert _model(box) == OPUS


def test_done_and_hold_are_not_candidates(tmp_path):
    box = _box(tmp_path)
    done = "00071-ship-the-marketplace-v1.md"
    _write_prd(box / "prds/done" / done, "opus")
    _write_prd(box / "prds/hold" / "00072-park-the-design-gate-v1.md", "opus")
    _state(box, done)
    assert _model(box) == SONNET
    assert build_target(box / "prds") is None


def test_signal1_session_model_opus_promotes(tmp_path):
    box = _box(tmp_path)
    prd = "00007-emit-the-batch-summary-v1.md"
    _write_prd(box / "prds/wip" / prd, "opus")
    _state(box, prd)
    assert _model(box) == OPUS


def test_default_model_opus_no_longer_promotes(tmp_path):
    # PRD 00200: `default_model` is the per-task tier floor for
    # /autopilot:plan-tasks. Alone in the frontmatter, with no other signal,
    # it buys no opus orchestrator - $283 of $556 build spend went to
    # sessions that only orchestrated.
    box = _box(tmp_path)
    prd = "00200-decouple-the-session-model-v1.md"
    _write_prd_fm(
        box / "prds/wip" / prd,
        "catchup: skip\ndefault_model: opus\ndesign: skip",
    )
    _state(box, prd)
    assert _model(box) == SONNET


def test_session_model_sonnet_is_explicit_sonnet(tmp_path):
    # An explicit sonnet beside an opus task floor is still a sonnet session.
    box = _box(tmp_path)
    prd = "00201-explicit-sonnet-v1.md"
    _write_prd_fm(
        box / "prds/wip" / prd,
        "catchup: skip\ndefault_model: opus\nsession_model: sonnet\ndesign: skip",
    )
    _state(box, prd)
    assert _model(box) == SONNET


def test_signal1_body_mention_is_not_frontmatter(tmp_path):
    # The BODY quotes "session_model: opus" (PRDs about model routing
    # really do); only the frontmatter block counts. The control first: the
    # same key IN the block promotes, so a router that ignores the key
    # altogether cannot pass on the rejection alone.
    box = _box(tmp_path)
    prd = "00082-tune-the-echo-stopwords-v1.md"
    path = box / "prds/wip" / prd
    _write_prd(path, "opus")
    _state(box, prd)
    assert _model(box) == OPUS
    _write_prd(path, "sonnet")
    path.write_text(path.read_text() + "\n## Notes\n\n    session_model: opus\n")
    assert _model(box) == SONNET


def test_signal1_no_frontmatter_at_all_ignores_body(tmp_path):
    # No block to find: taking the FIRST session_model: line anywhere in
    # the file wrongly promotes here. Control first, as above.
    box = _box(tmp_path)
    prd = "00019-widen-the-qwen-gate-v1.md"
    path = box / "prds/wip" / prd
    _write_prd(path, "opus")
    _state(box, prd)
    assert _model(box) == OPUS
    _write_prd(path)
    path.write_text(path.read_text() + "\nBody prose:\n\n    session_model: opus\n")
    assert _model(box) == SONNET


@pytest.mark.parametrize(
    ("label", "want", "body"),
    [
        (
            "no space after colon",
            OPUS,
            "catchup: skip\nsession_model:opus\ndesign: skip",
        ),
        (
            "whitespace around key and value",
            OPUS,
            "catchup: skip\n  session_model  :  opus  \ndesign: skip",
        ),
        ("double-quoted", OPUS, 'catchup: skip\nsession_model: "opus"\ndesign: skip'),
        ("single-quoted", OPUS, "catchup: skip\nsession_model: 'opus'\ndesign: skip"),
        ("letter suffix", SONNET, "catchup: skip\nsession_model: opusX\ndesign: skip"),
        (
            "word suffix",
            SONNET,
            "catchup: skip\nsession_model: opus-extra\ndesign: skip",
        ),
        ("any suffix", SONNET, "catchup: skip\nsession_model: opusy\ndesign: skip"),
        (
            "commented no indent",
            SONNET,
            "catchup: skip\n# session_model: opus\ndesign: skip",
        ),
        (
            "commented indented",
            SONNET,
            "catchup: skip\n  # session_model: opus\ndesign: skip",
        ),
        (
            "trailing comment on another key",
            SONNET,
            "catchup: skip # session_model: opus\ndesign: skip",
        ),
        (
            "mismatched quotes",
            SONNET,
            "catchup: skip\nsession_model: \"opus'\ndesign: skip",
        ),
        (
            "real sonnet beside a commented opus decoy",
            SONNET,
            "catchup: skip\nsession_model: sonnet\n# session_model: opus\ndesign: skip",
        ),
        (
            "glued hash is part of the value",
            SONNET,
            "catchup: skip\nsession_model: opus#suffix\ndesign: skip",
        ),
        (
            "glued hash repeating the word",
            SONNET,
            "catchup: skip\nsession_model: opus#opus\ndesign: skip",
        ),
        (
            "whitespace-preceded inline comment",
            OPUS,
            "catchup: skip\nsession_model: opus  # rationale\ndesign: skip",
        ),
    ],
)
def test_signal1_frontmatter_edge_grammar(tmp_path, label, want, body):
    box = _box(tmp_path)
    prd = "00001-sigfm-edge-case-v1.md"
    _state(box, prd)
    # Control: the plain key promotes, so every rejection row below proves
    # the grammar rejected it rather than the key being ignored.
    _write_prd(box / "prds/wip" / prd, "opus")
    assert _model(box) == OPUS
    _write_prd_fm(box / "prds/wip" / prd, body)
    assert _model(box) == want, label


def test_signal2_replan_count_promotes(tmp_path):
    box = _box(tmp_path)
    prd = "00015-cap-the-review-cycles-v1.md"
    _write_prd(box / "prds/wip" / prd)
    _state(box, prd, replan_count=1)
    assert _model(box) == OPUS


def test_signal3a_stall_reason_promotes(tmp_path):
    box = _box(tmp_path)
    prd = "00023-guard-the-park-loop-v1.md"
    _write_prd(box / "prds/wip" / prd)
    _state(box, prd, stall_reason={"stalled": "escalation_exhausted", "detail": "x"})
    assert _model(box) == OPUS


def test_signal3b_stall_in_two_newest_deferred_by_filename(tmp_path):
    # The stall sits in the 2nd-newest file BY FILENAME while the mtimes
    # DISAGREE (the stall file is the oldest on disk): an mtime-ordered
    # window drops it.
    import os

    box = _box(tmp_path)
    prd = "00044-tier-the-work-pipeline-v1.md"
    _write_prd(box / "prds/wip" / prd)
    _state(box, prd)
    old = box / "deferred" / "202605120000-deferred.json"
    mid = box / "deferred" / "202606180000-deferred.json"
    new = box / "deferred" / "202607040000-deferred.json"
    old.write_text(json.dumps({"items": [{"type": "deferred-finding", "prd": "x"}]}))
    mid.write_text(
        json.dumps(
            {
                "items": [
                    {"type": "deferred_decision", "prd": "00041-y-v1.md"},
                    {"type": "stall", "site": "wrapper_died", "prd": prd},
                ],
            },
        ),
    )
    new.write_text(json.dumps({"items": [{"type": "doubt", "prd": "z"}]}))
    os.utime(mid, (1, 1))
    os.utime(new, (2_000_000_000, 2_000_000_000))
    os.utime(old, (2_100_000_000, 2_100_000_000))
    assert _model(box) == OPUS


def test_signal3b_a_lone_deferred_log_is_still_scanned(tmp_path):
    # The 2-newest window must be a bounds-safe positive offset; the
    # negative-slice form returns ZERO elements on a 1-element array.
    box = _box(tmp_path)
    prd = "00046-catch-the-one-file-window-v1.md"
    _write_prd(box / "prds/wip" / prd)
    _state(box, prd)
    (box / "deferred" / "202607060000-deferred.json").write_text(
        json.dumps({"items": [{"type": "stall", "site": "design_gate", "prd": prd}]}),
    )
    assert _model(box) == OPUS


def test_signal3b_stall_outside_the_window_does_not_promote(tmp_path):
    # The target's stall exists only in the 3rd-newest file by name -
    # and that file is the NEWEST on disk, so an mtime window pulls it
    # in and wrongly promotes.
    import os

    box = _box(tmp_path)
    prd = "00052-fold-metrics-into-the-ledger-v1.md"
    _write_prd(box / "prds/wip" / prd)
    _state(box, prd)
    oldest = box / "deferred" / "202604010000-deferred.json"
    mid = box / "deferred" / "202605020000-deferred.json"
    newest = box / "deferred" / "202606030000-deferred.json"
    oldest.write_text(
        json.dumps({"items": [{"type": "stall", "site": "design_gate", "prd": prd}]}),
    )
    mid.write_text(
        json.dumps({"items": [{"type": "stall", "site": "c", "prd": "00050-o-v1.md"}]}),
    )
    newest.write_text(
        json.dumps({"items": [{"type": "deferred-finding", "prd": prd}]}),
    )
    os.utime(oldest, (2_100_000_000, 2_100_000_000))
    os.utime(mid, (1, 1))
    os.utime(newest, (2, 2))
    assert _model(box) == SONNET


def test_signal3b_type_and_prd_must_match_on_the_same_item(tmp_path):
    # The newest file holds a stall (another PRD) and a non-stall entry
    # naming the target: per-FILE matching wrongly promotes.
    box = _box(tmp_path)
    prd = "00058-stamp-the-work-start-sha-v1.md"
    _write_prd(box / "prds/wip" / prd)
    _state(box, prd)
    (box / "deferred" / "202606100000-deferred.json").write_text(
        json.dumps({"items": []}),
    )
    (box / "deferred" / "202607150000-deferred.json").write_text(
        json.dumps(
            {
                "items": [
                    {"type": "stall", "site": "design_gate", "prd": "00057-g-v1.md"},
                    {"type": "deferred-finding", "prd": prd},
                ],
            },
        ),
    )
    assert _model(box) == SONNET


def test_signal4_cap_rotation_promotes(tmp_path):
    box = _box(tmp_path)
    prd = "00056-rotate-on-the-context-cap-v1.md"
    _write_prd(box / "prds/wip" / prd)
    _state(box, prd, cap_rotations=[{"task_id": "task-7", "cycle": 2}])
    assert _model(box) == OPUS


def test_signal5_ledger_key_any_status_promotes(tmp_path):
    box = _box(tmp_path)
    prd = "00076-rescue-the-ladder-with-fable-v1.md"
    _write_prd(box / "prds/wip" / prd)
    _state(box, prd)
    (box / "ledger.json").write_text(
        json.dumps(
            {
                "00075-gate-on-memory-pressure-v1.md": {"status": "approved"},
                prd: {"status": "rejected"},
            },
        ),
    )
    assert _model(box) == OPUS


def test_signal5_target_as_a_value_never_promotes(tmp_path):
    # A KEY lookup, not a substring scan of the file.
    box = _box(tmp_path)
    prd = "00081-prevent-the-defect-class-v1.md"
    _write_prd(box / "prds/wip" / prd)
    _state(box, prd)
    (box / "ledger.json").write_text(
        json.dumps({"00080-diagnose-v1.md": {"status": "approved", "supersedes": prd}}),
    )
    assert _model(box) == SONNET


def test_promote_then_clear_never_latches(tmp_path):
    # PRD 00111's decay acceptance as three consecutive calls on one box:
    # signal-free -> Sonnet; rotation -> Opus; cleared -> Sonnet again.
    box = _box(tmp_path)
    prd = "00031-promote-then-clear-v1.md"
    _write_prd(box / "prds/wip" / prd)
    _state(box, prd)
    assert _model(box) == SONNET
    _state(box, prd, cap_rotations=[{"task_id": "t-3", "cycle": 1}])
    assert _model(box) == OPUS
    _state(box, prd)
    assert _model(box) == SONNET


def test_no_state_json_is_not_fatal_and_lowest_backlog_wins(tmp_path):
    box = _box(tmp_path)
    _write_prd(box / "prds/backlog" / "00003-register-the-running-loop-v1.md")
    _write_prd(box / "prds/backlog" / "00009-escalate-the-model-ladder-v1.md", "opus")
    assert _model(box) == SONNET


def test_no_state_json_still_evaluates_frontmatter_of_lowest(tmp_path):
    box = _box(tmp_path)
    _write_prd(box / "prds/backlog" / "00004-pin-the-plugin-versions-v1.md", "opus")
    _write_prd(box / "prds/backlog" / "00011-render-the-brief-v1.md", "sonnet")
    assert _model(box) == OPUS


def test_malformed_state_and_ledger_json_route_sonnet(tmp_path):
    # The bash contract: never fatal, nothing on stderr. Malformed
    # sidecars are false signals, not crashes.
    box = _box(tmp_path)
    prd = "00060-tolerate-garbage-v1.md"
    _write_prd(box / "prds/wip" / prd)
    (box / "state.json").write_text("{not json")
    (box / "ledger.json").write_text("[]not json")
    (box / "deferred" / "202601010000-deferred.json").write_text("{broken")
    assert _model(box) == SONNET


# ── route(): the per-phase case table ────────────────────────────────────────


def _route(phase: str, tmp_path: Path, env: dict | None = None) -> Route:
    ap_dir = tmp_path / "dev/local/autopilot"
    ap_dir.mkdir(parents=True, exist_ok=True)
    return route(phase, ap_dir, env=env or {})


def test_route_build_defaults_to_sonnet_xhigh_7200(tmp_path):
    got = _route("build", tmp_path)
    assert got == Route(model=SONNET, effort="xhigh", cap_secs=7200)


def test_route_absent_phase_is_a_build_launch(tmp_path):
    assert _route("", tmp_path).model == SONNET


def test_route_build_kill_switch_wins_over_routing(tmp_path):
    got = _route("build", tmp_path, {"_AUTOPILOT_MODEL_BUILD": OPUS})
    assert got.model == OPUS
    assert got.effort == "xhigh"


def test_route_review_is_opus_xhigh_10800(tmp_path):
    assert _route("review", tmp_path) == Route(
        model=OPUS,
        effort="xhigh",
        cap_secs=10800,
    )


def test_route_done_is_sonnet_medium_7200(tmp_path):
    assert _route("done", tmp_path) == Route(
        model=SONNET,
        effort="medium",
        cap_secs=7200,
    )


def test_route_unknown_phase_fails_expensive(tmp_path):
    # Opus xhigh, and deliberately NO env model override on this branch.
    got = _route("mystery", tmp_path, {"_AUTOPILOT_MODEL_REVIEW": SONNET})
    assert got == Route(model=OPUS, effort="xhigh", cap_secs=7200)


def test_route_env_caps_and_efforts_apply(tmp_path):
    got = _route(
        "review",
        tmp_path,
        {"_AUTOPILOT_SESSION_MAX_REVIEW": "60", "_AUTOPILOT_EFFORT_REVIEW": "high"},
    )
    assert got.cap_secs == 60
    assert got.effort == "high"


def test_route_build_reads_the_real_signal_paths(tmp_path):
    # route() wires build_model to the wrapper's exact sidecar paths:
    # ledger/fable-requests.json under the autopilot dir, prds beside it.
    ap_dir = tmp_path / "dev/local/autopilot"
    (ap_dir / "ledger").mkdir(parents=True)
    prds = tmp_path / "dev/local/prds/wip"
    prds.mkdir(parents=True)
    prd = "00013-route-from-the-ledger-v1.md"
    _write_prd(prds / prd)
    (ap_dir / "ledger" / "fable-requests.json").write_text(
        json.dumps({prd: {"status": "approved"}}),
    )
    assert route("build", ap_dir, env={}).model == OPUS


# ── review_cycle() and route()'s cycle-aware review effort ──────────────────


def _ap_dir_with_cycle(tmp_path: Path, cycle: int | None) -> Path:
    ap_dir = tmp_path / "dev/local/autopilot"
    ap_dir.mkdir(parents=True, exist_ok=True)
    if cycle is not None:
        (ap_dir / "state.json").write_text(json.dumps({"cycle": cycle}))
    return ap_dir


def test_review_cycle_reads_the_int_value_from_state(tmp_path):
    ap_dir = _ap_dir_with_cycle(tmp_path, 5)
    assert review_cycle(ap_dir) == 5


def test_review_cycle_defaults_to_one_when_state_file_missing(tmp_path):
    ap_dir = _ap_dir_with_cycle(tmp_path, None)
    assert review_cycle(ap_dir) == 1
    assert not (ap_dir / "state.json").exists()


def test_review_cycle_defaults_to_one_when_state_json_is_malformed(tmp_path):
    ap_dir = _ap_dir_with_cycle(tmp_path, None)
    (ap_dir / "state.json").write_text("{not json")
    assert review_cycle(ap_dir) == 1


def test_review_cycle_survives_an_unreadable_state_file(tmp_path, monkeypatch):
    # An OSError from the read itself (PermissionError, not malformed JSON)
    # must be swallowed exactly like a missing or malformed state: cycle 1,
    # xhigh, nothing raised, and the file left untouched.
    ap_dir = _ap_dir_with_cycle(tmp_path, None)
    state_path = ap_dir / "state.json"
    state_path.write_text(json.dumps({"cycle": 5}))
    before = state_path.read_bytes()
    original_read_text = Path.read_text

    def _raise(self, *args, **kwargs):
        if self == state_path:
            raise PermissionError("denied")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _raise)
    assert review_cycle(ap_dir) == 1
    assert route("review", ap_dir, env={}).effort == "xhigh"
    assert state_path.read_bytes() == before


def test_review_cycle_defaults_to_one_when_cycle_is_not_an_int(tmp_path):
    ap_dir = _ap_dir_with_cycle(tmp_path, None)
    (ap_dir / "state.json").write_text(json.dumps({"cycle": "two"}))
    assert review_cycle(ap_dir) == 1


def test_review_cycle_treats_json_true_as_int_one_not_bool(tmp_path):
    # bool is an int subclass in Python; an isinstance(..., int) check
    # alone lets True/False leak through where an int is promised.
    ap_dir = _ap_dir_with_cycle(tmp_path, None)
    (ap_dir / "state.json").write_text(json.dumps({"cycle": True}))
    got = review_cycle(ap_dir)
    assert got == 1
    assert type(got) is int
    assert route("review", ap_dir, env={}).effort == "xhigh"


def test_review_cycle_treats_json_false_as_int_one_not_bool(tmp_path):
    ap_dir = _ap_dir_with_cycle(tmp_path, None)
    (ap_dir / "state.json").write_text(json.dumps({"cycle": False}))
    got = review_cycle(ap_dir)
    assert got == 1
    assert type(got) is int
    assert route("review", ap_dir, env={}).effort == "xhigh"


def test_review_cycle_defaults_to_one_when_cycle_key_is_absent(tmp_path):
    ap_dir = _ap_dir_with_cycle(tmp_path, None)
    (ap_dir / "state.json").write_text(json.dumps({"prd": "00001-x-v1.md"}))
    assert review_cycle(ap_dir) == 1


def test_review_first_cycle_keeps_xhigh(tmp_path):
    ap_dir = _ap_dir_with_cycle(tmp_path, 1)
    got = route("review", ap_dir, env={})
    assert got.effort == "xhigh"


def test_review_cycle_zero_or_below_keeps_xhigh(tmp_path):
    # The contract is explicitly "1 or lower", not "not equal to 1".
    ap_dir = _ap_dir_with_cycle(tmp_path, 0)
    got = route("review", ap_dir, env={})
    assert got.effort == "xhigh"


def test_review_rerun_drops_effort_to_high(tmp_path):
    ap_dir = _ap_dir_with_cycle(tmp_path, 2)
    got = route("review", ap_dir, env={})
    assert got.effort == "high"
    assert got.model == OPUS


def test_review_rerun_env_effort_overrides_high(tmp_path):
    ap_dir = _ap_dir_with_cycle(tmp_path, 2)
    got = route(
        "review",
        ap_dir,
        env={"_AUTOPILOT_EFFORT_REVIEW_RERUN": "medium"},
    )
    assert got.effort == "medium"


def test_review_effort_override_wins_on_reruns(tmp_path):
    ap_dir = _ap_dir_with_cycle(tmp_path, 3)
    got = route("review", ap_dir, env={"_AUTOPILOT_EFFORT_REVIEW": "xhigh"})
    assert got.effort == "xhigh"


def test_review_effort_override_wins_over_rerun_override_when_both_set(tmp_path):
    # _AUTOPILOT_EFFORT_REVIEW forces every cycle; _AUTOPILOT_EFFORT_REVIEW_RERUN
    # only sets cycle 2+. With both set on a rerun, the always-wins override
    # must beat the rerun-only value.
    ap_dir = _ap_dir_with_cycle(tmp_path, 3)
    got = route(
        "review",
        ap_dir,
        env={
            "_AUTOPILOT_EFFORT_REVIEW": "xhigh",
            "_AUTOPILOT_EFFORT_REVIEW_RERUN": "medium",
        },
    )
    assert got.effort == "xhigh"


def test_review_effort_override_wins_even_when_empty_string(tmp_path):
    # The override branch is a membership test ("that key is set in env"),
    # not the file's usual `.get(key) or default` idiom used elsewhere in
    # route() - an explicitly set empty string still wins over the
    # cycle-computed effort.
    ap_dir = _ap_dir_with_cycle(tmp_path, 2)
    got = route("review", ap_dir, env={"_AUTOPILOT_EFFORT_REVIEW": ""})
    assert got.effort == ""


def test_review_missing_state_keeps_xhigh(tmp_path):
    ap_dir = _ap_dir_with_cycle(tmp_path, None)
    got = route("review", ap_dir, env={})
    assert got.effort == "xhigh"


# ── Loop._append_metrics(): the effort the router chose, persisted ──────────


def _decision(**overrides) -> dict:
    decision = {
        "prd": "00090-persist-the-chosen-effort-v1.md",
        "batch": "20260907-a",
        "phase_end": "review",
        "signal": "continue",
    }
    decision.update(overrides)
    return decision


def _rows(path: Path) -> list[dict]:
    return [json.loads(ln) for ln in path.read_text().splitlines() if ln.strip()]


def test_metrics_row_carries_effort(tmp_path):
    # Empty and unknown efforts must persist verbatim; repeated calls must append.
    lp = Loop()
    efforts = ["xhigh", "", "unrecognized-level", "medium"]
    for effort in efforts:
        lp._append_metrics(
            tmp_path,
            1000.0,
            1060.0,
            _decision(),
            "build",
            SONNET,
            effort,
        )
    rows = _rows(tmp_path / "loop-metrics.jsonl")
    assert [row["effort"] for row in rows] == efforts
    assert [row["model"] for row in rows] == [SONNET] * len(efforts)


def test_metrics_effort_follows_model_and_displaces_no_other_field(tmp_path):
    # Additive only: every pre-existing key keeps its name, its order and
    # its computation (the timestamps still truncate toward zero), with
    # effort inserted directly after model.
    lp = Loop()
    decision = _decision(phase_end="done", signal="drain")
    lp._append_metrics(
        tmp_path,
        1_700_000_000.6,
        1_700_000_123.2,
        decision,
        "b",
        "m",
        "e",
    )
    row = _rows(tmp_path / "loop-metrics.jsonl")[-1]
    assert list(row) == [
        "ts_start",
        "ts_end",
        "wall_secs",
        "prd",
        "batch",
        "phase_launched",
        "phase_end",
        "signal",
        "model",
        "effort",
    ]
    assert row["ts_start"] == 1_700_000_000
    assert row["ts_end"] == 1_700_000_123
    assert row["wall_secs"] == 123
    assert row["prd"] == decision["prd"]
    assert row["batch"] == decision["batch"]
    assert row["phase_launched"] == "b"
    assert row["phase_end"] == "done"
    assert row["signal"] == "drain"


def test_metrics_effort_reaches_the_ledger_copy_verbatim(tmp_path):
    # The ledger copy is the same encoded line, not a second rendering
    # that could drop the new field.
    ap_dir = tmp_path / "autopilot"
    ap_dir.mkdir()
    lp = Loop()
    lp._append_metrics(ap_dir, 5.0, 9.0, _decision(), "review", OPUS, "high")
    written = (ap_dir / "loop-metrics.jsonl").read_text()
    assert (ap_dir / "ledger" / "loop-metrics.jsonl").read_text() == written
    assert json.loads(written)["effort"] == "high"


def test_metrics_append_with_effort_still_never_raises(tmp_path):
    # The one sanctioned silent failure survives the new parameter: an
    # unwritable target is swallowed, and no file appears.
    lp = Loop()
    missing = tmp_path / "never-created"
    lp._append_metrics(missing, 1.0, 2.0, _decision(), "build", SONNET, "xhigh")
    assert not missing.exists()
