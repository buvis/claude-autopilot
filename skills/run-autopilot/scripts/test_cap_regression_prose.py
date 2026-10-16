"""Pins the cap_regression prose: the loop-mode cap-out deferral bullet in
phase-review.md must run `autopilot cap-check` before deferring and route a
regression (exit 1) to a `cap_regression` stall, and the `cap_regression` slug
must appear beside `cap_critical` in both recovery.md and state-schema.md
(PRD 00310).
"""

from __future__ import annotations

import re

from pathlib import Path

_REFERENCES = Path(__file__).resolve().parent.parent / "references"
_PHASE_REVIEW = _REFERENCES / "phase-review.md"
_RECOVERY = _REFERENCES / "recovery.md"
_STATE_SCHEMA = _REFERENCES / "state-schema.md"

_CAP_OUT_BULLET_START = 'Otherwise (all unresolved findings ≤ high)'
_CAP_OVERFLOW_DEFER_SENTENCE = (
    'Append each to `deferred_decisions` as `{"type": "cap-overflow"'
)
# The Exit 1 clause runs from its own marker up to "Exit 2" - the sub-skill
# failure handler that follows also contains the literal string
# `autopilot stall`, so a bare substring match against the whole bullet would
# pass even if the Exit 1 clause itself never mentioned it.
_EXIT_1_START = "Exit 1 ("
_EXIT_2_START = "Exit 2 ("
# The adjacency ceiling for "the slugs sit within one list": generous enough
# to span a multi-sentence list item, tight enough to refuse a slug that
# landed in an unrelated section of the file.
_ADJACENCY_CEILING = 2000


def _cap_out_bullet() -> str:
    text = _PHASE_REVIEW.read_text()
    assert _CAP_OUT_BULLET_START in text, (
        f"{_PHASE_REVIEW}: the cap-out deferral bullet is gone"
    )
    start = text.index(_CAP_OUT_BULLET_START)
    assert _CAP_OVERFLOW_DEFER_SENTENCE in text[start:], (
        f"{_PHASE_REVIEW}: the cap-overflow deferral sentence is gone"
    )
    end = text.index(_CAP_OVERFLOW_DEFER_SENTENCE, start)
    return text[start:end]


def _exit_1_clause(bullet: str) -> str:
    assert _EXIT_1_START in bullet, f"{_PHASE_REVIEW}: the cap-out bullet has no Exit 1 clause"
    start = bullet.index(_EXIT_1_START)
    assert _EXIT_2_START in bullet[start:], (
        f"{_PHASE_REVIEW}: the cap-out bullet's Exit 1 clause never ends at Exit 2"
    )
    end = bullet.index(_EXIT_2_START, start)
    return bullet[start:end]


def test_cap_out_runs_cap_check_before_deferring() -> None:
    bullet = _cap_out_bullet()
    assert "autopilot cap-check" in bullet, (
        f"{_PHASE_REVIEW}: the cap-out bullet never mentions `autopilot cap-check`"
        " ahead of the cap-overflow deferral"
    )


def test_exit_1_routes_to_cap_regression_stall() -> None:
    """Restricted to the Exit 1 clause itself (PRD 00310 review finding):
    the Exit 2 sub-skill-failure handler also says `autopilot stall`, so a
    match against the whole bullet would pass even if Exit 1 never mentioned
    `cap_regression` at all."""
    clause = _exit_1_clause(_cap_out_bullet())
    assert "Loop-mode stall procedure" in clause and "cap_regression" in clause, (
        f"{_PHASE_REVIEW}: the Exit 1 clause never routes a cap-check regression"
        " through the Loop-mode stall procedure with site cap_regression"
    )
    assert "site: \"cap_regression\"" in clause, (
        f"{_PHASE_REVIEW}: the Exit 1 clause's stall instruction never names"
        " `site: \"cap_regression\"` directly"
    )


def test_recovery_lists_cap_regression_slug() -> None:
    """A file may mention `cap_critical` in several unrelated places (an
    error-handling table row, a custody section) before ever listing the
    slugs together - so this must find the CLOSEST pair of occurrences, not
    just the first of each, and verify that pair sits in one list."""
    for path in (_RECOVERY, _STATE_SCHEMA):
        text = path.read_text()
        critical_positions = [m.start() for m in re.finditer("cap_critical", text)]
        regression_positions = [m.start() for m in re.finditer("cap_regression", text)]
        assert critical_positions and regression_positions, (
            f"{path}: `cap_regression` must appear beside `cap_critical`"
        )
        closest_gap = min(
            abs(c - r) for c in critical_positions for r in regression_positions
        )
        assert closest_gap <= _ADJACENCY_CEILING, (
            f"{path}: the closest `cap_critical`/`cap_regression` pair is"
            f" {closest_gap} chars apart - not next to each other in the same list"
        )
        c, r = min(
            ((c, r) for c in critical_positions for r in regression_positions),
            key=lambda pair: abs(pair[0] - pair[1]),
        )
        gap = text[min(c, r) : max(c, r)]
        assert not re.search(r"^#", gap, re.MULTILINE), (
            f"{path}: a heading sits between the closest `cap_critical`/"
            "`cap_regression` pair - they are not in the same list"
        )


# --- PRD 00321 ---------------------------------------------------------------

_CAP_REGRESSION_ENTRY_START = "- `cap_regression`"
# How far past a "rename" mention the limit wording may sit and still count
# as the same sentence-sized statement.
_RENAME_WINDOW = 300


def _cap_out_line() -> str:
    """The whole cap-out bullet (one markdown line), not cut at the
    cap-overflow sentence - the rename limit may sit anywhere in it."""
    text = _PHASE_REVIEW.read_text()
    assert _CAP_OUT_BULLET_START in text, (
        f"{_PHASE_REVIEW}: the cap-out deferral bullet is gone"
    )
    start = text.rfind("\n", 0, text.index(_CAP_OUT_BULLET_START)) + 1
    end = text.find("\n", start)
    return text[start : end if end != -1 else len(text)]


def _recovery_cap_regression_entry() -> str:
    text = _RECOVERY.read_text()
    assert _CAP_REGRESSION_ENTRY_START in text, (
        f"{_RECOVERY}: the `cap_regression` stall-site entry is gone"
    )
    start = text.index(_CAP_REGRESSION_ENTRY_START)
    end = text.find("\n- `", start + 1)
    return text[start : end if end != -1 else len(text)]


def test_cap_out_records_every_unresolved_row_before_the_stall() -> None:
    """The Exit 1 clause writes the cap-overflow records into
    state.deferred_decisions FIRST, then stalls at cap_regression, then runs
    mint-stubs - so the regressed rows reach the ledger and a stub."""
    clause = _exit_1_clause(_cap_out_bullet())
    for needle in ("cap-overflow", "deferred_decisions", "autopilot mint-stubs"):
        assert needle in clause, f"{_PHASE_REVIEW}: the Exit 1 clause never names {needle}"
    records = clause.index("cap-overflow")
    stall = clause.index('site: "cap_regression"')
    mint = clause.index("autopilot mint-stubs")
    assert records < stall < mint, (
        f"{_PHASE_REVIEW}: the Exit 1 clause must order the cap-overflow"
        " records, then the cap_regression stall, then mint-stubs"
    )
    assert re.search(r"\b(?:every|all) unresolved\b", clause[:stall]), (
        f"{_PHASE_REVIEW}: the Exit 1 clause must record every unresolved row"
        " before the stall"
    )
    assert "mints no hold stub" not in clause, (
        f"{_PHASE_REVIEW}: the Exit 1 clause still says a cap_regression"
        " stall mints no hold stub"
    )


def test_recovery_names_the_real_resume_steps() -> None:
    entry = _recovery_cap_regression_entry()
    assert "exactly like `cap_critical`" not in entry, (
        f"{_RECOVERY}: the cap_regression entry still resumes through"
        " cap_critical's custody path"
    )
    for needle in ("hold/", "-deferred.json", "stub", "v2", "backlog/", "autopilot custody"):
        assert needle in entry, f"{_RECOVERY}: the cap_regression resume steps never name {needle}"
    assert re.search(r"\bno\b[^.]{0,40}`autopilot custody", entry), (
        f"{_RECOVERY}: the cap_regression entry must say no `autopilot custody`"
        " command applies"
    )


def test_phase_review_names_the_rename_limit() -> None:
    line = _cap_out_line()
    match = re.search(r"renam", line, re.IGNORECASE)
    assert match, f"{_PHASE_REVIEW}: the cap-out bullet never names the rename limit"
    window = line[match.start() : match.start() + _RENAME_WINDOW].lower()
    assert "blame" in window and "limit" in window, (
        f"{_PHASE_REVIEW}: the cap-out bullet's rename mention must say a"
        " rename's blame is a documented limit"
    )
