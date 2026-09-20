#!/usr/bin/env python3
"""Prose pins for the effort-lane routing (PRD 00204): Phase 0 step 5.5 in
`references/phase-build.md` names the three lanes, the shadow rule and the
kill switch, so the text cannot drift away from what `cli/lane.py` does.

Stdlib only; pytest collects the module-level tests with no config.
"""

from __future__ import annotations

import re
from pathlib import Path

_REFERENCES = Path(__file__).resolve().parents[1] / "references"
_PHASE_BUILD = _REFERENCES / "phase-build.md"


def _section(text: str, heading: str) -> str:
    """The body from the line that is exactly `heading` to the next heading of
    the same or a higher level, so a pinned phrase elsewhere in the file
    cannot satisfy the pin."""
    start = re.search(rf"^{re.escape(heading)}$", text, re.MULTILINE)
    if start is None:
        raise AssertionError(f"no heading line {heading!r}")
    level = len(heading) - len(heading.lstrip("#"))
    rest = text[start.end() :]
    end = re.search(rf"^#{{1,{level}}} ", rest, re.MULTILINE)
    return rest if end is None else rest[: end.start()]


def _step_5_5() -> str:
    return _section(_PHASE_BUILD.read_text(encoding="utf-8"), "### 5.5. Route by lane")


def test_step_5_5_sits_between_the_frontmatter_parse_and_phase_1() -> None:
    text = _PHASE_BUILD.read_text(encoding="utf-8")
    parse = text.index("### Frontmatter parse (step 5)")
    route = text.index("### 5.5. Route by lane")
    catchup = text.index("## Phase 1: Catchup")
    assert parse < route < catchup


def test_step_5_5_names_three_lanes_and_the_shadow_sentence() -> None:
    step = _step_5_5()
    for token in ("`solo`", "`fast-track`", "`full`", "RELEASED_LANES"):
        assert token in step, token
    assert "── AUTOPILOT ── lane: <lane> (<reason>), running full ──" in step
    assert "_AUTOPILOT_LANES=off" in step
    assert "`state.lane_effective`" in step
    assert "`cli/lane.py` decides" in step
