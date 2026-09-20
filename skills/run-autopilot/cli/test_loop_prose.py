"""Prose pins for run-autopilot SKILL.md § Session Loop: the stand-down
procedure paragraph (PRD 00199, ask-first rule and the repo-basename peer
filter behind the 2026-09-14 false stand-downs, inefficiencies note finding
14) and the operator-runbook cross-reference that points at it.

The paragraph is located by its literal bold opening, never by a heading
(there is none), and each pin is a short substring so a reword that keeps the
rule passes while a dropped rule fails.
"""

from __future__ import annotations

from pathlib import Path

_SKILL = Path(__file__).resolve().parent.parent / "SKILL.md"
_TEXT = _SKILL.read_text(encoding="utf-8")

_OPENING = "**Stand-down procedure (a peer session owns the PRD).**"
_CLOSING = "The model's only job at a hand-off"


def _stand_down_paragraph() -> str:
    assert _OPENING in _TEXT, f"{_SKILL}: the stand-down paragraph lost its opening"
    start = _TEXT.index(_OPENING)
    assert _CLOSING in _TEXT[start:], f"{_SKILL}: the stand-down paragraph lost its end"
    return _TEXT[start : _TEXT.index(_CLOSING, start)]


def _session_loop() -> str:
    start = _TEXT.index("\n## Session Loop")
    return _TEXT[start : _TEXT.index("\n## ", start + 1)]


def _assert_all(scope: str, where: str, needles: tuple[str, ...]) -> None:
    for needle in needles:
        assert needle in scope, f"{_SKILL}: {where} lacks {needle!r}"


def test_stand_down_requires_a_same_repo_peer() -> None:
    procedure = _stand_down_paragraph()
    _assert_all(
        procedure,
        "the stand-down paragraph",
        (
            "starts with this repository's directory basename",
            'basename "$PWD"',
            "another repository is never evidence",
        ),
    )
    assert "busy interactive peer session in this repo AND" not in _TEXT
    # The rule lives in § Session Loop, once: a second copy elsewhere would
    # drift from this one.
    assert _OPENING in _session_loop()
    assert _TEXT.count(_OPENING) == 1


def test_stand_down_asks_the_peer_before_pausing() -> None:
    procedure = _stand_down_paragraph()
    _assert_all(
        procedure,
        "the stand-down paragraph",
        (
            "`SendMessage`",
            "at most 120 s",
            "`git status --porcelain`",
            '`edge: "leave"`',
            "never answers, never pauses a batch",
            "skip the mtime test",
        ),
    )
    assert "changed within the last 15 minutes" not in procedure


def test_state_after_leave_compares_whole_seconds_against_this_prds_leave_row() -> None:
    # Review 00199: the rows carry no batch id (filter by `prd`), `at` is an
    # int second (truncate the mtime), and the rule is only sound when every
    # site writes its `leave` row after its last state write.
    procedure = _stand_down_paragraph()
    _assert_all(
        procedure,
        "the state_after_leave rule",
        (
            "truncated to whole seconds",
            "and this PRD's `prd`",
            "writes its `leave` row AFTER its last state and card write",
            "must set `next_phase` before its row",
        ),
    )


def test_stand_down_names_the_three_conditions_in_the_marker() -> None:
    procedure = _stand_down_paragraph()
    for condition in ("peer_claimed", "dirty_tree", "state_after_leave"):
        assert f"condition `{condition}`" in procedure, (
            f"{_SKILL}: the stand-down paragraph does not define {condition!r}"
        )
    _assert_all(
        procedure,
        "the stand-down marker line",
        (
            '"condition": "<peer_claimed | dirty_tree | state_after_leave>"',
            "`stood_down_condition`",
        ),
    )


def test_operator_runbook_points_at_the_ask_first_rule() -> None:
    pause_bullet = _TEXT[_TEXT.index("- **Pause**:") :]
    pause_bullet = pause_bullet[: pause_bullet.index("\n")]
    _assert_all(
        pause_bullet,
        "the operator runbook's Pause bullet",
        ("`condition`", "after asking the peer first", "stand-down procedure"),
    )
