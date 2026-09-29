"""Prose pins for the one-call Phase 0 entry: the `### Enter in one call`
subsection of `references/phase-build.md` § "Phase 0: PRD Selection" (after the
session-brief paragraph, before `### Ensure lifecycle directories exist`), the
`autopilot enter` mention beside core `SKILL.md` § "Phase 0 invariants", the
`release-checks` wiring of both enter test files, and the changelog entry.

Same pattern as test_triage_prose.py: slice the section that must carry the
instruction, assert short reword-resistant substrings in order, and sweep each
slice for the negation that would invert it. The stop-value table is checked
against `cli.enter.STOPS` read at test time, so a stop value added later with
no row fails here instead of leaving an undocumented halt.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cli.custody_prose_testutil import (
    _SKILL_DIR,
    _added_bullets,
    _assert_absent,
    _assert_in_order,
    _assert_matches,
    _assert_present,
    _section,
)
from cli.enter import STOPS

_PHASE_BUILD = _SKILL_DIR / "references" / "phase-build.md"
_BUILD_TEXT = _PHASE_BUILD.read_text()
_SKILL = _SKILL_DIR / "SKILL.md"
_SKILL_TEXT = _SKILL.read_text()
_REPO_ROOT = _SKILL_DIR.parent.parent
_RELEASE_CHECKS = _REPO_ROOT / "dev" / "bin" / "release-checks"
_CHANGELOG = _REPO_ROOT / "CHANGELOG.md"

_PHASE_0 = "## Phase 0: PRD Selection"
_PHASE_1 = "## Phase 1: Catchup"
_ENTER_HEADING = "### Enter in one call"
_MKDIR_HEADING = "### Ensure lifecycle directories exist"

# Every Phase 0 subsection that predates the one-call entry. The new section
# points at these; it replaces none of them.
_SURVIVING_HEADINGS = (
    _MKDIR_HEADING,
    "### Clear inherited hand-off markers",
    "### Handle park request (FIRST abort-handler check)",
    "### Handle Work-phase abort (from a prior session)",
    "### Handle pending custody",
    "### Normal PRD selection",
    "### Frontmatter parse (step 5)",
    "### 5.5. Route by lane",
)

# Paraphrases that keep the verb but tell the operator not to run it.
_ENTER_NEGATIONS = (
    "Do NOT run `autopilot enter`",
    "do not run `autopilot enter`",
    "never run `autopilot enter`",
    "`autopilot enter` is retired",
    "skip the enter call",
)


def _phase_0() -> str:
    return _section(_BUILD_TEXT, _PHASE_BUILD, _PHASE_0, _PHASE_1)


def _enter_section() -> str:
    return _section(_phase_0(), _PHASE_BUILD, _ENTER_HEADING, _MKDIR_HEADING)


def _table_rows(scope: str) -> str:
    """The markdown table rows of `scope`, minus the header separator."""
    rows = [
        line
        for line in scope.splitlines()
        if line.strip().startswith("|") and not set(line.strip()) <= set("|-: ")
    ]
    return "\n".join(rows)


def test_phase_0_opens_with_autopilot_enter() -> None:
    phase_0 = _phase_0()
    where = f"the {_ENTER_HEADING!r} section"
    assert _ENTER_HEADING in phase_0, (
        f"{_PHASE_BUILD}: expected a {_ENTER_HEADING!r} subsection inside "
        f"{_PHASE_0!r} — not found."
    )
    assert phase_0.index(_ENTER_HEADING) < phase_0.index(_MKDIR_HEADING), (
        f"{_PHASE_BUILD}: expected {_ENTER_HEADING!r} before {_MKDIR_HEADING!r} — "
        "the one-call entry must be the first thing Phase 0 says to do."
    )
    assert "session-brief.md" in phase_0[: phase_0.index(_ENTER_HEADING)], (
        f"{_PHASE_BUILD}: expected the session-brief paragraph to stay ahead of "
        f"{_ENTER_HEADING!r}."
    )
    section = _enter_section()
    _assert_in_order(
        section,
        _PHASE_BUILD,
        where,
        ("`autopilot enter`", "one Bash call", "`stop`", "null", "Phase 1", "`stop` is set"),
    )
    _assert_present(section, _PHASE_BUILD, where, ("`catchup`", "`design`"))
    _assert_absent(section, _PHASE_BUILD, where, _ENTER_NEGATIONS)


def test_every_stop_value_has_a_row() -> None:
    section = _enter_section()
    rows = _table_rows(section)
    assert rows, (
        f"{_PHASE_BUILD}: expected a stop-value table in {_ENTER_HEADING!r} — "
        "no table rows found."
    )
    missing = [stop for stop in STOPS if stop not in rows]
    assert not missing, (
        f"{_PHASE_BUILD}: {_ENTER_HEADING!r}'s stop-value table has no row for "
        f"{missing!r} — every value of cli.enter.STOPS needs the section that "
        "owns its halt."
    )


def test_the_null_stop_path_reuses_the_returned_decisions() -> None:
    section = _enter_section()
    where = f"the {_ENTER_HEADING!r} section"
    _assert_present(section, _PHASE_BUILD, where, ("banner", "without re-running"))
    _assert_matches(
        section,
        _PHASE_BUILD,
        where,
        r"(?i)without re-running[^.]{0,120}Phase 0",
        "say the null-stop path re-runs none of the Phase 0 steps by hand",
    )


def test_skill_names_enter_as_the_first_build_call() -> None:
    start = _SKILL_TEXT.index("## Phase 0 invariants")
    before = _SKILL_TEXT.rfind("\n## ", 0, start)
    region = _section(
        _SKILL_TEXT[before if before != -1 else 0 :],
        _SKILL,
        "## Phase 0 invariants",
        "## Phase 3 invariants",
    )
    where = "core SKILL.md § 'Phase 0 invariants' and its neighbour"
    _assert_present(region, _SKILL, where, ("`autopilot enter`",))
    _assert_matches(
        region,
        _SKILL,
        where,
        r"(?i)first[^\n]{0,140}`autopilot enter`|`autopilot enter`[^\n]{0,140}first",
        "name `autopilot enter` as the FIRST Bash call of a build session",
    )
    _assert_absent(region, _SKILL, where, _ENTER_NEGATIONS)


def test_every_existing_phase_0_subsection_survives_with_its_own_steps() -> None:
    phase_0 = _phase_0()
    for heading in _SURVIVING_HEADINGS:
        assert phase_0.count(heading) == 1, (
            f"{_PHASE_BUILD}: expected exactly one {heading!r} subsection in "
            f"{_PHASE_0!r} — found {phase_0.count(heading)}. The one-call entry "
            "is a pointer, not a replacement."
        )
    # Each surviving subsection still carries its own body, not just a heading.
    offsets = sorted(phase_0.index(h) for h in _SURVIVING_HEADINGS)
    for start in offsets:
        heading_end = phase_0.index("\n", start)
        nexts = [o for o in offsets if o > start]
        body = phase_0[heading_end : nexts[0] if nexts else len(phase_0)]
        assert len(body.strip()) > 200, (
            f"{_PHASE_BUILD}: the subsection at {phase_0[start:heading_end]!r} lost "
            "its step-by-step instructions (body under 200 chars)."
        )


def test_release_checks_runs_both_enter_test_files() -> None:
    text = _RELEASE_CHECKS.read_text()
    unit = "skills/run-autopilot/cli/test_enter.py"
    prose = "skills/run-autopilot/cli/test_enter_prose.py"
    for path in (unit, prose):
        assert text.count(path) == 1, (
            f"{_RELEASE_CHECKS}: expected exactly one {path} argument — found "
            f"{text.count(path)}."
        )
    at = text.index(unit)
    block_start = text.rfind('echo "[checks]', 0, at)
    assert block_start != -1, (
        f"{_RELEASE_CHECKS}: {unit} does not sit under a `[checks]` block."
    )
    block = text[block_start:].split("\necho ", 1)[0]
    _assert_present(
        block,
        _RELEASE_CHECKS,
        "the `[checks]` block that runs the enter tests",
        ("uv run --no-project --with pytest python -m pytest -q", unit, prose),
    )


def test_changelog_added_carries_the_enter_entry() -> None:
    # The whole file's Added blocks, not [Unreleased]: a release moves the
    # entry under its version heading.
    added = _added_bullets(_CHANGELOG.read_text(), _CHANGELOG)
    bullets = [b for b in re.split(r"(?m)^- ", added) if b.strip()]
    hits = [
        b for b in bullets if b.startswith("**run-autopilot**") and "`autopilot enter`" in b
    ]
    assert hits, (
        f"{_CHANGELOG}: expected an Added bullet prefixed `- **run-autopilot**` "
        "that mentions `autopilot enter` — not found."
    )
