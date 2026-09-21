"""Prose pins for run-autopilot SKILL.md § Session Loop: the stand-down
procedure paragraph (PRD 00199, ask-first rule and the repo-basename peer
filter behind the 2026-09-14 false stand-downs, inefficiencies note finding
14) and the operator-runbook cross-reference that points at it.

The paragraph is located by its literal bold opening, never by a heading
(there is none), and each pin is a short substring so a reword that keeps the
rule passes while a dropped rule fails.
"""

from __future__ import annotations

import re
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


def _handoff_procedure() -> str:
    start = _TEXT.index("### Session handoff procedure")
    return _TEXT[start : _TEXT.index("\n### ", start + 1)]


_WRITE_BRIEF = r"statectl\.py \S+ write-brief dev/local/autopilot/session-brief\.md"
_SKILLS = _SKILL.parent.parent
_WORK_HANDOFF = _SKILLS / "work" / "references" / "task-boundary-handoff.md"
_REVIEW_SKILL = _SKILLS / "review-work-completion" / "SKILL.md"
_PHASE_BUILD = _SKILLS / "run-autopilot" / "references" / "phase-build.md"
_PHASE_REVIEW = _SKILLS / "run-autopilot" / "references" / "phase-review.md"


def test_every_handoff_site_writes_the_brief() -> None:
    # PRD 00201: the run-autopilot site, the work task-boundary handoff
    # (step h) and the review-work-completion cycle transition each write
    # the brief right after their contract card.
    procedure = _handoff_procedure()
    match = re.search(_WRITE_BRIEF, procedure)
    assert match, f"{_SKILL}: the handoff procedure has no write-brief line"
    _assert_all(
        procedure,
        "the handoff procedure",
        ("after the contract card", "A failed write is one stderr line, never a phase failure"),
    )
    # The brief is rendered from the committed transition and before the
    # leave row: transition (step 1) < write-brief < record_dispatch.
    assert procedure.index("phase-done --outcome") < match.start() < procedure.index(
        "record_dispatch.py handoff"
    )
    work = _WORK_HANDOFF.read_text(encoding="utf-8")
    step_h = work[work.index("h. **Write the contract card**") :]
    work_match = re.search(_WRITE_BRIEF, step_h)
    assert work_match, f"{_WORK_HANDOFF}: step h has no write-brief line"
    assert step_h.index("set-contract-card") < work_match.start() < step_h.index(
        "record_dispatch.py handoff"
    ), f"{_WORK_HANDOFF}: step h writes the brief outside card < brief < leave row"
    review = _REVIEW_SKILL.read_text(encoding="utf-8")
    card = review[review.index("**Write the contract card** at this cycle transition") :]
    card = card[: card.index("\n")]
    assert re.search(_WRITE_BRIEF, card), (
        f"{_REVIEW_SKILL}: the cycle-transition card paragraph has no write-brief line"
    )


def test_phase_0_opens_with_the_brief() -> None:
    # PRD 00201: the first paragraph under the build and review gate headings
    # points at the brief, and names the fallback when it disagrees with state.
    for path, heading in (
        (_PHASE_BUILD, "## Phase 0: PRD Selection\n"),
        (_PHASE_REVIEW, "## Phase 4: Review\n"),
    ):
        text = path.read_text(encoding="utf-8")
        start = text.index(heading) + len(heading)
        opening = text[start : text.index("\n\n", start + 2)]
        for needle in (
            "Read `dev/local/autopilot/session-brief.md` if it exists",
            "Where section replaces the state reads",
            "Read next section lists",
            "fall back to the state reads",
        ):
            assert needle in opening, f"{path}: the {heading.strip()} opening lacks {needle!r}"


def test_operator_runbook_points_at_the_ask_first_rule() -> None:
    pause_bullet = _TEXT[_TEXT.index("- **Pause**:") :]
    pause_bullet = pause_bullet[: pause_bullet.index("\n")]
    _assert_all(
        pause_bullet,
        "the operator runbook's Pause bullet",
        ("`condition`", "after asking the peer first", "stand-down procedure"),
    )


def test_handoff_names_the_skill_guard() -> None:
    # PRD 00211: the leave row is the point of no return, enforced by a hook.
    procedure = _handoff_procedure()
    _assert_all(
        procedure,
        "the handoff procedure",
        (
            "hooks/note_session_leave.py",
            "hooks/guard_skill_after_leave.py",
            "point of no return",
        ),
    )
    assert procedure.index("record_dispatch.py handoff") < procedure.index(
        "guard_skill_after_leave.py"
    )

