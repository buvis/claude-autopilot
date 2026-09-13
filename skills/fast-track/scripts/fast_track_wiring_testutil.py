"""The reader model behind the fast-track wiring pins.

Split out of test_fast_track_wiring.py to keep that file under the size limit,
the way fast_track_prose_testutil.py was split out of test_fast_track_prose.py.
Where that module reads SKILL.md as passages a reader acts on, this one reads a
document as units in page order - a paragraph, a list item or a whole fenced
block - so a pin can ask whether one step sits between two others, and finds a
planner call by the line an operator would paste, in a block nothing withdraws.
"""

from __future__ import annotations

import importlib.util
import re
from functools import lru_cache
from pathlib import Path
from types import ModuleType
from typing import NamedTuple


def _sibling(name: str) -> ModuleType:
    """A helper module read from beside this file, never from an install path."""
    spec = importlib.util.spec_from_file_location(
        name,
        Path(__file__).with_name(f"{name}.py"),
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


prose = _sibling("fast_track_prose_testutil")

SKILL_MD = prose.SKILL_MD
PLAN_CALL = "python3 ${CLAUDE_PLUGIN_ROOT}/skills/fast-track/scripts/" + (
    "fast_track_plan.py"
)

_FENCE = re.compile(r"^ {0,3}(?:```|~~~)")
_HEADING = re.compile(r"^ {0,3}(#{1,6})\s+(.*?)\s*#*$")
_BULLET = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
_COMMENT = re.compile(r"(?:^|\s)#.*$", re.MULTILINE)
_JSON_ARG = re.compile(r"[\w<>.-]+\.json\b")


class Unit(NamedTuple):
    """One paragraph, list item or fenced block, with its place on the page."""

    at: int
    headings: tuple[str, ...]
    text: str
    is_code: bool


def units(text: str) -> list[Unit]:
    """Blocks, paragraphs and list items in page order; a fence is one unit."""
    found: list[Unit] = []
    stack: list[tuple[int, str]] = []
    pending: list[str] = []
    in_code = False

    def flush(is_code: bool) -> None:
        # Hard-wrapped prose is one passage again, so `Write tool` split across
        # a line break still reads as the phrase; a fenced block keeps its lines.
        if pending:
            headings = tuple(title for _, title in stack)
            text = ("\n" if is_code else " ").join(pending)
            found.append(Unit(len(found), headings, text, is_code))
            pending.clear()

    for line in text.splitlines():
        if _FENCE.match(line):
            flush(in_code)
            in_code = not in_code
            continue
        if in_code:
            pending.append(line)
            continue
        heading = _HEADING.match(line)
        if heading:
            flush(False)
            level = len(heading.group(1))
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, heading.group(2)))
            continue
        if not line.strip() or _BULLET.match(line):
            flush(False)
        if line.strip():
            pending.append(line.strip())
    flush(in_code)
    return found


@lru_cache(maxsize=1)
def skill_units() -> tuple[Unit, ...]:
    """SKILL.md's body as units, read once."""
    return tuple(units(prose.body()))


def under(unit: Unit, stem: str) -> bool:
    """True when some heading above the unit matches `stem`."""
    return any(re.search(stem, h, re.IGNORECASE) for h in unit.headings)


def live(unit: Unit) -> bool:
    """False when the unit, or a heading above it, withdraws what it says."""
    return not any(
        p.search(t) for t in (*unit.headings, unit.text) for p in prose.CANCELS
    )


def spoken(unit: Unit) -> str:
    """The unit's text as read: a fenced block loses its `#` comments, which no
    shell reads, and joins its `\\`-continued commands, one line to a hand."""
    if not unit.is_code:
        return unit.text
    return re.sub(r"\\\n\s*", " ", _COMMENT.sub("", unit.text))


def pasteable_lines(unit: Unit) -> list[str]:
    """The lines of a fenced block an operator could select and run."""
    lines = [line.strip() for line in spoken(unit).splitlines()] if unit.is_code else []
    return [
        ln
        for ln in lines
        if prose.code_fragments(prose.Passage(unit.headings, ln, True))
    ]


def first_line(pattern: str, missing: str = "") -> Unit:
    """The first fenced, pasteable line of SKILL.md matching `pattern`.

    Only from a block nothing withdraws: the same line under a `### Retired`
    heading, or beside a comment calling it history, is one nobody pastes.
    """
    withdrawn: list[str] = []
    for unit in skill_units():
        for line in pasteable_lines(unit):
            if re.search(pattern, line):
                if live(unit):
                    return unit._replace(text=line)
                withdrawn.append(line)
    missing = missing or f"no fenced, pasteable line matches {pattern!r}."
    if withdrawn:
        missing = f"`{withdrawn[0]}` sits only in a block or under a heading that " + (
            "withdraws it, so the operator reads it as history."
        )
    raise AssertionError(f"{SKILL_MD}: {missing}")


def plan_call(verb: str) -> Unit:
    """The pasteable line running the planner's `verb`."""
    return first_line(
        rf"^{re.escape(PLAN_CALL)}\s+{re.escape(verb)}\b",
        f"no fenced, pasteable line runs `{PLAN_CALL} {verb}`; cited in prose, "
        "the planner is a rule the driver applies from memory.",
    )


def json_operand(call: Unit) -> str:
    """The `.json` file a planner call opens."""
    found = _JSON_ARG.search(call.text.split(PLAN_CALL, 1)[1])
    assert found, f"{SKILL_MD}: `{call.text}` names no `.json` file."
    return found[0]


def json_written_above(call: Unit) -> list[Unit]:
    """The live Write-tool steps above the call that put its operand there."""
    operand = json_operand(call)
    writers = [
        u
        for u in skill_units()
        if not u.is_code and u.at < call.at and live(u)
        if operand in u.text and "Write tool" in u.text
    ]
    assert writers, (
        f"{SKILL_MD}: nothing above `{call.text}` writes `{operand}` with the "
        "Write tool; the command opens a file no step put there."
    )
    return writers
