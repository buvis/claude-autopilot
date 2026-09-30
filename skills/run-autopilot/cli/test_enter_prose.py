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

The obligations the section must carry beyond that table — the STALLED banner
behind a non-null `parked`, the loop-mode custody line behind
`custody_pending`, exits 1/2/6, the missing JSON line on a non-zero exit, and
§ "Normal PRD selection" step 6's Active Work read — are pinned unit by unit:
every half of such a pin must sit in ONE table row or ONE paragraph, so a row
cannot borrow its meaning from the row below.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cli.custody_prose_testutil import (
    _SELECTION_HEADING,
    _SKILL_DIR,
    _added_bullets,
    _assert_absent,
    _assert_in_order,
    _assert_matches,
    _assert_present,
    _prose,
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
_FRONTMATTER_HEADING = "### Frontmatter parse (step 5)"

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

# The loop-mode custody line § "Handle pending custody" tells a session to
# print, minus its `<n>` so a reworded count cannot break the pin.
_CUSTODY_LINE = "entries await an attended resume"

# Loop mode, named either way the file names it elsewhere.
_LOOP_MODE = r"loop mode|_AUTOPILOT_LOOP"

# Who prints the banners: the CLI prints the JSON line, the skill prints every
# banner itself from the returned fields. Several honest phrasings, so the pin
# measures the obligation and not one sentence.
_SKILL_PRINTS_THE_BANNERS = (
    r"(?i)prints? no banner"
    r"|prints? (?:only|just) (?:the |one )?JSON line"
    r"|JSON line (?:is all|and nothing else)"
    r"|banners? (?:are|stay|remain) (?:yours|the skill's|this skill's)"
    r"|print(?:s|ing)? (?:the |each |every )?banners? yourself"
)

# Each non-zero exit `autopilot enter` can take, with the substrings that turn
# the bare code into a cause a session can act on.
_EXIT_MEANINGS = (
    (1, (r"autopilot dir", r"--state")),
    (2, (r"corrupt", r"Error Handling")),
    (6, (r"schema", r"future")),
)


def _phase_0() -> str:
    return _section(_BUILD_TEXT, _PHASE_BUILD, _PHASE_0, _PHASE_1)


def _enter_section() -> str:
    return _section(_phase_0(), _PHASE_BUILD, _ENTER_HEADING, _MKDIR_HEADING)


def _selection_section() -> str:
    return _section(_phase_0(), _PHASE_BUILD, _SELECTION_HEADING, _FRONTMATTER_HEADING)


def _table_rows(scope: str) -> str:
    """The markdown table rows of `scope`, minus the header separator."""
    rows = [
        line
        for line in scope.splitlines()
        if line.strip().startswith("|") and not set(line.strip()) <= set("|-: ")
    ]
    return "\n".join(rows)


def _units(scope: str) -> list[str]:
    """`scope` split into binding units: each table row alone, the rest by blank
    line.

    A binding pin asks for every half inside ONE unit. `_assert_bound`'s gap
    forbids newlines, which this file's ~80-column hard wraps would break, and
    `_paragraph` needs a lead sentence a pin may not dictate; a table row must
    still not borrow its meaning from the row below. Fences drop first, so a
    token dump inside a code block satisfies no pin.
    """
    units: list[str] = []
    for block in re.split(r"\n[ \t]*\n", _prose(scope)):
        lines = block.splitlines()
        rows = [line for line in lines if line.lstrip().startswith("|")]
        units.extend(rows)
        units.append("\n".join(line for line in lines if line not in rows))
    return [unit for unit in units if unit.strip()]


def _unit_with(scope: str, *patterns: str) -> str | None:
    """The first unit of `scope` matching every pattern, case-insensitively."""
    return next(
        (
            unit
            for unit in _units(scope)
            if all(re.search(pattern, unit, re.IGNORECASE) for pattern in patterns)
        ),
        None,
    )


def _assert_one_unit(
    scope: str,
    path: Path,
    where: str,
    patterns: tuple[str, ...],
    what: str,
) -> None:
    assert _unit_with(scope, *patterns) is not None, (
        f"{path}: expected {where} to {what} — no single table row or paragraph "
        f"there carries all of {patterns!r}."
    )


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


def test_release_checks_runs_every_enter_test_file() -> None:
    text = _RELEASE_CHECKS.read_text()
    unit = "skills/run-autopilot/cli/test_enter.py"
    enter_tests = (
        unit,
        "skills/run-autopilot/cli/test_enter_prose.py",
        "skills/run-autopilot/cli/test_enter_guards.py",
        "skills/run-autopilot/cli/test_enter_decisions.py",
    )
    for path in enter_tests:
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
        ("uv run --no-project --with pytest python -m pytest -q", *enter_tests),
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


def test_a_non_null_parked_prompts_the_stalled_banner_the_skill_prints() -> None:
    section = _prose(_enter_section())
    where = f"the {_ENTER_HEADING!r} section"
    _assert_present(section, _PHASE_BUILD, where, ("`parked`", "STALLED"))
    _assert_one_unit(
        section,
        _PHASE_BUILD,
        where,
        (r"`parked`", r"STALLED", r"non-null|not null|is set|\bset\b|present"),
        "tell a session that a non-null `parked` means it prints the STALLED "
        "banner (§ Handle park request's exit-0 row: 'print the STALLED banner, "
        "continue selection')",
    )
    _assert_matches(
        section,
        _PHASE_BUILD,
        where,
        _SKILL_PRINTS_THE_BANNERS,
        "say `autopilot enter` prints no banner of its own — the CLI prints the "
        "JSON line and the skill still prints every banner itself, from the "
        "returned fields",
    )


def test_a_non_zero_custody_pending_in_loop_mode_prompts_the_custody_line() -> None:
    section = _prose(_enter_section())
    where = f"the {_ENTER_HEADING!r} section"
    _assert_present(section, _PHASE_BUILD, where, ("`custody_pending`", _CUSTODY_LINE))
    _assert_one_unit(
        section,
        _PHASE_BUILD,
        where,
        (
            r"`custody_pending`",
            re.escape(_CUSTODY_LINE),
            _LOOP_MODE,
            r"non-?zero|not (?:zero|0)",
        ),
        "tie a non-zero `custody_pending` in loop mode to printing "
        f"`custody: <n> {_CUSTODY_LINE}` (§ Handle pending custody's loop-mode "
        "branch)",
    )


def test_every_non_zero_exit_names_what_it_means() -> None:
    section = _prose(_enter_section())
    where = f"the {_ENTER_HEADING!r} section"
    for code, needles in _EXIT_MEANINGS:
        token = (
            rf"\bexits?[ \t]*(?:with |status |code )?{code}\b"
            rf"|^[ \t]*\|[ \t]*`?{code}`?[ \t]*\|"
        )
        _assert_one_unit(
            section,
            _PHASE_BUILD,
            where,
            (token, *needles),
            f"document exit {code} beside what it means, so a session that gets "
            "it knows the cause instead of re-running the call",
        )


def test_no_json_line_accompanies_a_non_zero_exit() -> None:
    section = _prose(_enter_section())
    where = f"the {_ENTER_HEADING!r} section"
    _assert_present(section, _PHASE_BUILD, where, ("stderr",))
    _assert_one_unit(
        section,
        _PHASE_BUILD,
        where,
        (
            r"JSON line",
            r"non-zero",
            r"\b(?:no|not|never|nothing|absent|missing)\b",
        ),
        "say no JSON line is printed on a non-zero exit, so a session reads "
        "stderr and the exit code instead of waiting for a `stop` value that "
        "never comes",
    )


def test_the_enter_section_keeps_the_capsule_active_work_read() -> None:
    _assert_one_unit(
        _prose(_enter_section()),
        _PHASE_BUILD,
        f"the {_ENTER_HEADING!r} section",
        (r"Active Work", r"\bread\b"),
        "tell the reader to read the Active Work section of "
        "`docs/dev/project-management/meta/project-capsule.md` before Phase 1 — "
        f"that is {_SELECTION_HEADING!r} step 6, which `autopilot enter` cannot "
        "perform, so the one-call section has to hand it back",
    )


def test_the_selection_pointer_names_step_6_as_outside_enter() -> None:
    _assert_one_unit(
        _prose(_selection_section()),
        _PHASE_BUILD,
        f"the pointer closing {_SELECTION_HEADING!r}",
        (
            r"`autopilot enter`",
            r"step 6|Active Work",
            r"\b(?:not|never|cannot|can't|excludes?|excluded|except|outside)\b",
        ),
        "say plainly that step 6 (the capsule's Active Work read) is NOT covered "
        "by `autopilot enter`, instead of claiming enter runs `these steps` and "
        "leaving that read silently dropped",
    )
