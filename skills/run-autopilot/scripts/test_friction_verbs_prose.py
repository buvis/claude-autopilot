#!/usr/bin/env python3
"""Prose-site tests for PRD 00309 fast-track card c1.

A census of batch 202610111300's loop transcripts found the model doing by
shell what a verb should do (ls/rm on marker files, hand-written
autonomous_decisions JSON). These tests pin that the prose sites that drove
that behavior now point at the verbs instead, so a future edit can't drift
back to the old "read the marker"/"log the decision" wording without
noticing.
"""

from __future__ import annotations

from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
_SKILL_ROOT = _SCRIPTS_DIR.parent
_REFERENCES_DIR = _SKILL_ROOT / "references"
_WORK_SKILL = _SKILL_ROOT.parent / "work" / "SKILL.md"


def test_work_skill_checks_handoff_marker_by_verb() -> None:
    text = _WORK_SKILL.read_text(encoding="utf-8")
    assert "markers --check handoff-requested" in text
    assert "<dir>/.handoff-requested" not in text


def test_phase_build_clears_markers_by_verb() -> None:
    text = (_REFERENCES_DIR / "phase-build.md").read_text(encoding="utf-8")
    assert "markers --clear handoff-requested cap-fired" in text
    assert "_walk_up.py --clear-markers" not in text


def test_phase_review_appends_decisions_by_verb() -> None:
    text = (_REFERENCES_DIR / "phase-review.md").read_text(encoding="utf-8")
    assert "statectl.py <state.json> decide" in text
