"""cli/gate_lead.py - the lead-stripping helpers split out of gate.py (PRD
00325 rework) to keep gate.py under the 800-line hard max.

`_strip_lead` strips a finding-shaped line's lead - any non-alphanumeric
character (Unicode category P, S, Z, C or M), repeated and nested freely -
plus the handful of lead shapes that span more than one character and so
cannot be expressed as a single-character category test: an ordinal
(`\\d+[.)]`, `[A-Za-z]+\\)`, `(\\d+)`), a checkbox, an HTML comment or
`<details>` block, inline code, and a markdown link.
"""

from __future__ import annotations

import re
import unicodedata

if __package__:
    from .findings_section import _SEVERITY_EMOJI
else:
    from findings_section import _SEVERITY_EMOJI

# Unicode general-category classes that are never the start of a real word
# or number: Punctuation, Symbol, Separator, Other/control/format, Mark.
# "Any non-alphanumeric lead" (PRD 00325) is exactly this test.
_NON_ALNUM_CATEGORIES = ("P", "S", "Z", "C", "M")
# Open/close punctuation (brackets and parens) are deliberately excluded from
# the bare single-character sweep: they are consumed only through the
# explicit multi-character shapes above (an ordinal "(1)", a checkbox
# "[ ]", a link "[x](y)") - never swept one bracket at a time, which would
# read a stray "(x)" or "#)" as lead and expose the letter behind it.
_BRACKET_CATEGORIES = ("Ps", "Pe")
# Hangul Filler (U+3164): Unicode classifies it Lo (letter) for the Hangul
# syllable-composition algorithm, but it renders invisible and shows up as
# lead in the wild. Category alone cannot single it out without also
# catching ordinary letters, so it is named explicitly.
_INVISIBLE_LEAD_EXTRA = frozenset("ㅤ")
# No `^`: re's `^` anchors to the real string start even with `.match(line,
# i)`'s `pos` argument, which would silently stop this ever matching past
# index 0 (`re.compile(r"^\d+[.)]").match("  1. x", 2)` is None, checked) —
# an unanchored pattern plus `.match(line, i)` is what actually anchors the
# match at `i`.
_ORDINAL_LEAD_RE = re.compile(r"\d+[.)]|[A-Za-z]+\)|\(\d+\)")
# Multi-character lead shapes consumed whole: a checkbox, an HTML comment or
# `<details>` block, inline code, and a markdown link.
_CHECKBOX_LEAD_RE = re.compile(r"\[[ xX]?\]")
_HTML_COMMENT_LEAD_RE = re.compile(r"<!--.*?-->")
_DETAILS_LEAD_RE = re.compile(r"<details>.*?</details>", re.IGNORECASE | re.DOTALL)
_INLINE_CODE_LEAD_RE = re.compile(r"`[^`\n]*`")
_LINK_LEAD_RE = re.compile(r"\[[^\]\n]*\]\([^)\n]*\)")
_LEAD_SHAPE_RES = (
    _ORDINAL_LEAD_RE,
    _CHECKBOX_LEAD_RE,
    _HTML_COMMENT_LEAD_RE,
    _DETAILS_LEAD_RE,
    _INLINE_CODE_LEAD_RE,
    _LINK_LEAD_RE,
)


def _strip_lead(line: str) -> str:
    """Strip `line`'s lead, repeatedly, in any combination: the multi-
    character shapes above (tried first, since a lone digit or letter of an
    ordinal would otherwise be read as plain alphanumeric text) and any
    single character outside Unicode categories L (letter) and N (number) -
    i.e. any non-alphanumeric lead, including whitespace, bullets,
    blockquote markers, emphasis, and the Hangul Filler exception above.
    Stops at the first character none of these consume. Returns the
    remainder, which may be empty. A mark repeats and nests freely: "> > ",
    "-- " and "> > - **" are all lead, so a nested row's emoji is still the
    first character of the content."""
    i, n = 0, len(line)
    while i < n:
        matched = False
        for lead_re in _LEAD_SHAPE_RES:
            m = lead_re.match(line, i)
            if m:
                i = m.end()
                matched = True
                break
        if matched:
            continue
        ch = line[i]
        if ch in _SEVERITY_EMOJI:
            # The target character itself, never its own lead.
            break
        category = unicodedata.category(ch)
        if ch in _INVISIBLE_LEAD_EXTRA or (
            category[0] in _NON_ALNUM_CATEGORIES and category not in _BRACKET_CATEGORIES
        ):
            i += 1
            continue
        break
    return line[i:]
