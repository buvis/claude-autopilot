"""Frontmatter pins for every skill in the pack (skills/*/SKILL.md).

The frontmatter is the one part of a skill the host reads by machine: `name`
and `description` are what the skill index lists and what the trigger matcher
reads. The host parses that block as YAML, and YAML has opinions a reader never
notices - a `: ` inside an unquoted description ends the scalar and opens a
mapping, a ` #` starts a comment and drops the rest of the line, a `"` that
opens has to close. The fast-track description shipped with `loop: fresh`
unquoted, and a strict parser refuses the whole block at that colon.

PyYAML is not in this test environment, so the parse here is a plain-Python
reading of the shape every frontmatter in this pack has: a flat block between
two `---` lines, one `key: value` per line, no nesting, no multi-line scalars.
Within that shape it refuses what `yaml.safe_load` refuses and hands back the
same strings. The documents come from a glob, so a skill added tomorrow is read
tomorrow, and an empty glob fails rather than skips.

These pins live here rather than in test_fast_track_prose.py because that file
is at the project's file size limit.
"""

from __future__ import annotations

import re
from pathlib import Path

_PACK_ROOT = Path(__file__).resolve().parents[3]
_SKILL_DOCS = sorted(_PACK_ROOT.glob("skills/*/SKILL.md"))
_FAST_TRACK = _PACK_ROOT / "skills" / "fast-track" / "SKILL.md"

_KEY_VALUE = re.compile(r"^([A-Za-z0-9_-]+): (.*)$")
# `:` followed by whitespace or the end of the value is a mapping indicator
# inside a plain scalar: "mapping values are not allowed here".
_MAPPING_INDICATOR = re.compile(r":(?:\s|$)")
# Characters a plain scalar cannot open with; `-` and `?` only when a space or
# the end of the value follows them.
_RESERVED_START = re.compile(r"^(?:[\[\]{}&*!|>%@`#,]|[-?](?:\s|$))")
# The whole escape table YAML defines for a double-quoted scalar; a backslash
# followed by anything else is "found unknown escape character".
_DQ_ESCAPES = {
    "0": "\0",
    "a": "\a",
    "b": "\b",
    "t": "\t",
    "\t": "\t",
    "n": "\n",
    "v": "\v",
    "f": "\f",
    "r": "\r",
    "e": "\x1b",
    " ": " ",
    '"': '"',
    "/": "/",
    "\\": "\\",
    "N": "\x85",
    "_": "\xa0",
    "L": " ",
    "P": " ",
}
_DQ_HEX_WIDTH = {"x": 2, "u": 4, "U": 8}
_HEX = re.compile(r"[0-9A-Fa-f]+")


class _FrontmatterError(ValueError):
    """One line a strict YAML parser refuses, and why."""

    def __init__(self, line: int, reason: str) -> None:
        super().__init__(reason)
        self.line = line


def _double_quoted(value: str) -> str:
    """The string YAML reads from a `"`-opened value, decoding escapes left to right.

    Every backslash has to open an escape from YAML's table, so it can never
    reach the closing quote: the first unescaped `"` after the opening one is
    the close, and it has to be the last character of the value. A value that
    ends in `\\"` is not closed - the parser runs on into the next line.
    """
    decoded: list[str] = []
    position = 1
    while position < len(value):
        char = value[position]
        if char == '"':
            if position != len(value) - 1:
                raise ValueError('text after the closing " of a double-quoted value')
            return "".join(decoded)
        if char != "\\":
            decoded.append(char)
            position += 1
            continue
        code = value[position + 1 : position + 2]
        if code in _DQ_HEX_WIDTH:
            width = _DQ_HEX_WIDTH[code]
            digits = value[position + 2 : position + 2 + width]
            if len(digits) != width or not _HEX.fullmatch(digits):
                raise ValueError(
                    f"\\{code} needs exactly {width} hexadecimal digits, got {digits!r}",
                )
            decoded.append(chr(int(digits, 16)))
            position += 2 + width
        elif code in _DQ_ESCAPES:
            decoded.append(_DQ_ESCAPES[code])
            position += 2
        else:
            raise ValueError(f"a backslash escape YAML does not define: \\{code}")
    raise ValueError('a value opened with " never closes with it')


def _scalar(raw: str) -> str:
    """The string a YAML parser reads from a flat line's value, or a ValueError.

    Quoted values must close with their own quote and carry no unescaped copy
    of it inside, and a double-quoted value may use only the escapes YAML
    defines; plain values must not open with an indicator, hold a mapping
    colon, or hold a comment start.
    """
    value = raw.strip()
    if value[:1] == '"':
        return _double_quoted(value)
    if value[:1] == "'":
        if len(value) < 2 or not value.endswith("'"):
            raise ValueError("a value opened with ' never closes with it")
        inner = value[1:-1]
        if "'" in inner.replace("''", ""):
            raise ValueError("an unescaped ' inside a single-quoted value")
        return inner.replace("''", "'")
    if _RESERVED_START.match(value):
        raise ValueError(f"a plain value opening with the YAML indicator {value[0]!r}")
    if _MAPPING_INDICATOR.search(value):
        raise ValueError(
            "a `: ` inside a plain value (mapping values are not allowed here)",
        )
    if " #" in value:
        raise ValueError(
            "a ` #` inside a plain value (YAML starts a comment there and drops the rest)",
        )
    return value


def _frontmatter(doc: Path) -> dict[str, str]:
    """The mapping a strict parse of `doc`'s frontmatter returns.

    Raises _FrontmatterError, carrying the 1-based line, on anything a YAML
    parser would refuse in this pack's flat shape.
    """
    lines = doc.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---":
        raise _FrontmatterError(1, "line 1 is not the opening `---`")
    mapping: dict[str, str] = {}
    for number, line in enumerate(lines[1:], start=2):
        if line == "---":
            return mapping
        match = _KEY_VALUE.match(line)
        if match is None:
            raise _FrontmatterError(number, f"not a `key: value` line: {line!r}")
        try:
            mapping[match[1]] = _scalar(match[2])
        except ValueError as err:
            raise _FrontmatterError(number, f"{err}: {line!r}") from None
    raise _FrontmatterError(
        len(lines),
        "the block opened on line 1 never closes with `---`",
    )


def _rel(doc: Path) -> str:
    return doc.relative_to(_PACK_ROOT).as_posix()


def _mappings() -> tuple[dict[Path, dict[str, str]], list[str]]:
    """Every skill's parsed frontmatter, plus one complaint per skill that does not parse."""
    parsed: dict[Path, dict[str, str]] = {}
    broken: list[str] = []
    for doc in _SKILL_DOCS:
        try:
            parsed[doc] = _frontmatter(doc)
        except _FrontmatterError as err:
            broken.append(f"{_rel(doc)}:{err.line}: {err}")
    return parsed, broken


_NO_SKILLS = (
    f"{_PACK_ROOT}: no `skills/*/SKILL.md` found. The pack ships eleven, so an "
    "empty glob means this test is running from the wrong place - and every "
    "pin below it would pass by having nothing to read."
)


def test_every_skill_frontmatter_parses_under_a_strict_yaml_reading() -> None:
    # The host reads the block with a real YAML parser, which stops at the
    # first thing it cannot scan and takes the whole skill down with it. This
    # is the live defect: fast-track's description holds `loop: fresh`
    # unquoted, a colon-space inside a plain scalar, and the parser reports
    # `mapping values are not allowed here` at that column. Every skill in the
    # pack is read here, by path and by line, so the same slip in another
    # skill fails the same way.
    assert _SKILL_DOCS, _NO_SKILLS

    _, broken = _mappings()

    assert not broken, (
        f"{len(broken)} skill frontmatter(s) do not parse as YAML: {broken}. "
        "A real parser refuses the whole block at that line, so the skill "
        "never reaches the index. Quote the value (and escape any quote of "
        "the same kind inside it), or reword it so no `: `, ` #`, or leading "
        "indicator remains in the plain scalar."
    )


def test_every_skill_frontmatter_names_its_own_directory() -> None:
    # `name` is what the index lists and what `/name` resolves; a skill whose
    # frontmatter names a different directory is listed under one name and
    # found under another. A skill that does not parse has no name to check,
    # which is a failure of the same rule, not a pass.
    assert _SKILL_DOCS, _NO_SKILLS

    parsed, complaints = _mappings()
    complaints += [
        f"{_rel(doc)}: `name` is {mapping.get('name')!r}, directory is "
        f"{doc.parent.name!r}"
        for doc, mapping in parsed.items()
        if mapping.get("name") != doc.parent.name
    ]

    assert not complaints, (
        f"{len(complaints)} skill(s) do not carry a `name` equal to their "
        f"directory: {complaints}."
    )


def test_every_skill_frontmatter_carries_a_description() -> None:
    # The description is the trigger matcher's whole input: without one the
    # skill is never suggested. Present and non-blank is the floor; the
    # fast-track pins below ask more of their own.
    assert _SKILL_DOCS, _NO_SKILLS

    parsed, complaints = _mappings()
    complaints += [
        f"{_rel(doc)}: `description` is {mapping.get('description')!r}"
        for doc, mapping in parsed.items()
        if not mapping.get("description", "").strip()
    ]

    assert not complaints, (
        f"{len(complaints)} skill(s) carry no usable `description`: {complaints}."
    )


def _fast_track_description() -> str:
    try:
        parsed = _frontmatter(_FAST_TRACK)
    except _FrontmatterError as err:
        raise AssertionError(
            f"{_rel(_FAST_TRACK)}:{err.line}: {err}. The lane's own frontmatter "
            "has to parse before its description can be read at all.",
        ) from None
    description = parsed.get("description", "")
    assert description.strip(), (
        f"{_rel(_FAST_TRACK)}: the frontmatter carries no `description`, so "
        "the lane has nothing to be triggered on."
    )
    return description


def test_the_fast_track_description_opens_with_use_when() -> None:
    # Trigger-led is the pack's convention: the matcher reads the opening
    # words first, and a description that opens with what the lane is rather
    # than when to use it is a description that never fires. Fixing the YAML
    # by rewording must not lose the opening.
    description = _fast_track_description()

    assert description.startswith("Use when"), (
        f"{_rel(_FAST_TRACK)}: the description opens with "
        f"{description[:24]!r}, not `Use when`. Quoting or rewording the "
        "value to make it parse has to keep it trigger-led."
    )


def test_the_fast_track_description_names_the_lane() -> None:
    # The lane is invoked by name - "fast-track this card" - and a description
    # that parses but no longer says `fast-track` is one the matcher cannot
    # tie to that request.
    description = _fast_track_description()

    assert "fast-track" in description, (
        f"{_rel(_FAST_TRACK)}: the description never says `fast-track`: "
        f"{description!r}. A rewording that drops the lane's name drops the "
        "trigger with it."
    )


_TRIGGER_PHRASES = ('"fast-track this card"', '"run the fast-track lane"')


def test_the_fast_track_description_keeps_both_quoted_trigger_phrases() -> None:
    # Every description in the pack closes with `Triggers on "...", "..."`:
    # the quoted phrases are what the matcher ties a request to. `Use when
    # fast-track.` is valid YAML that opens with `Use when` and names the lane,
    # and it fires on nothing. Fixing the colon by rewording, quoting, or
    # escaping has to hand back the same two phrases, quotes included.
    description = _fast_track_description()

    missing = [
        phrase
        for phrase in ("Triggers on", *_TRIGGER_PHRASES)
        if phrase not in description
    ]

    assert not missing, (
        f"{_rel(_FAST_TRACK)}: the parsed description lacks {missing}: "
        f"{description!r}. The index entry has to say how to invoke the lane, "
        f"so it must still read `Triggers on {', '.join(_TRIGGER_PHRASES)}`."
    )


def test_the_fast_track_description_fits_the_skill_validator_cap() -> None:
    # The pack's skill validator caps a description at 250 characters, and the
    # parsed value - not the quoted line - is what it measures. Quoting adds
    # nothing; a rewording that explains more can push it over.
    description = _fast_track_description()

    assert len(description) <= 250, (
        f"{_rel(_FAST_TRACK)}: the description is {len(description)} "
        "characters, over the validator's 250. Cut it before the validator "
        "refuses the skill."
    )
