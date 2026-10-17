#!/usr/bin/env python3
"""Single-voice Medium/Low findings get discarded, not turned into tasks:
phase-review.md's Classification section and its tail-sweep Select step must
both say so."""

from __future__ import annotations

from pathlib import Path

PHASE_REVIEW = Path(__file__).resolve().parent.parent / "references" / "phase-review.md"


def _section(start: str, end: str) -> str:
    text = PHASE_REVIEW.read_text()
    begin = text.index(start) + len(start)
    stop = text.index(end, begin)
    return text[begin:stop]


def test_classification_discards_single_voice_rows() -> None:
    """A Medium or Low row only one reviewer raised is a discard, not a task:
    the Classification section has to carry the rule, and the classification
    mapping table has to carry its "discard" row, or an orchestrator reading
    either alone would miss it."""
    classification_section = _section(
        "### Classification (per finding):", "### Settled-decisions ledger"
    )
    assert "**Single-voice Medium or Low**" in classification_section

    text = PHASE_REVIEW.read_text()
    assert '| Single-voice Medium or Low | `"discard"` |' in text


def test_tail_sweep_select_excludes_single_voice_rows() -> None:
    """The tail sweep's Select step has to exclude single-voice rows before it
    sweeps, or a sweep would promote a row the Classification rule above
    already discards."""
    select_section = _section("**1. Select.**", "**2. Create.**")
    assert "Consensus cell is `[1/N]`" in select_section
    assert "reason `single-voice`" in select_section
