#!/usr/bin/env python3
"""The CONTENT rule of the `gate --findings` unread-line check.

A sibling of test_gate_findings_shapes.py (1049 lines, past the 800-line limit
in rules/coding-style.md), whose fixtures are imported here rather than
re-spelled. Every test below pins what makes an unconsumed line a finding, as
opposed to where it sits: a severity emoji as the FIRST character remaining
after stripping the line's lead (indent, bullets, blockquote, ordinals,
emphasis markers, invisible Unicode space/format characters) - an emoji
after other text is prose, not a row - a severity word with pipes around
it, a consensus-marker
variant after a finding reference or on a structurally tabular line, and the
findings-table header hidden by a fence that indents it. The negative half
matters as much: counting prose, a consensus heading and a hyphenated severity
compound must still pass, and the rows the findings parser does read must never
be reported as unread. The verdict space is pinned at both ends - a covered file
exits 0, an uncovered one is refused without being called malformed - and so is
the refusal text: the FIRST unread line, stripped and cut at 120 characters.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cli.test_gate import CRIT, HIGH, MED
from cli.test_gate_findings_shapes import (
    _COVERED,
    _REF_TABLE,
    _review_text,
    _unread_detail,
    _verdict_and_exit,
)

# The fourth severity emoji, which the gate tests keep no constant for.
LOW = "⚪"

# Real CRITICAL rows that escaped the check: every one of them carries a
# severity emoji and NOTHING else a reader could key on - no `[m/n]` token, and
# for some no pipe, no severity word and no attribution suffix either.
_EMOJI_SHAPES = {
    "emoji bullet with a file": f"- {CRIT} crash on empty input | src/a.py:3",
    "emoji bullet, nothing else": f"- {CRIT} crash on empty input",
    "ordinal bullet": f"1. {CRIT} crash | src/a.py:3",
    "star bullet, severity word after the emoji": f"* {CRIT} Critical: crash",
    "emphasised emoji": f"- **{CRIT}** crash | src/a.py:3 | alice",
    "emoji then upper-case severity word": (
        f"- {CRIT} CRITICAL: stale cache survives restart"
    ),
    "emoji, issue and file": f"- {CRIT} stale cache | src/x.py:3",
    "mixed-case attribution": f"- {CRIT} crash | a.py:3 | Found By: alice",
    "tab indent, no bullet": f"\t{CRIT} crash on empty input",
    "plus bullet": f"+ {CRIT} crash on empty input",
    "paren ordinal": f"1) {CRIT} crash | src/a.py:3",
}


@pytest.mark.parametrize("row", list(_EMOJI_SHAPES.values()), ids=list(_EMOJI_SHAPES))
def test_a_severity_emoji_alone_makes_an_unread_line_a_finding(
    row: str,
    tmp_path: Path,
) -> None:
    """A severity emoji is sufficient on its own: a reader that also demands a
    pipe, a severity word, a `Found by:` suffix or a consensus token lets at
    least one of these rows through."""
    from cli import gate

    text = _review_text(alice=row)
    assert gate._is_emoji_row(row) is True
    assert gate._unread_token(text) == _emoji_detail(text, row)
    assert _verdict_and_exit(text, _COVERED, tmp_path) == (
        "malformed",
        _emoji_detail(text, row),
        2,
    )


_EMOJI_DETAIL = "a severity emoji row the findings parser did not read: "


def _emoji_detail(text: str, line: str) -> str:
    """The emoji-row refusal naming `line`, spelled out literally."""
    n = text.splitlines().index(line) + 1
    return f"line {n}: {_EMOJI_DETAIL}{line.strip()[:120]}"


def _assert_emoji_row_refused(row: str, tmp_path: Path) -> None:
    from cli import gate

    text = _review_text(alice=row)
    assert gate._is_emoji_row(row) is True
    assert gate._unread_token(text) == _emoji_detail(text, row)
    assert _verdict_and_exit(text, _COVERED, tmp_path) == (
        "malformed",
        _emoji_detail(text, row),
        2,
    )


def _assert_prose_read(line: str) -> None:
    from cli import gate

    text = _review_text(alice=line)
    assert gate._is_emoji_row(line) is False
    assert gate._unread_token(text) is None
    assert gate.findings_verdict(text, _COVERED) == ("ok", None)


@pytest.mark.parametrize(
    "template",
    [
        "- {} crash on empty input",
        "1. {} crash on empty input",
        "{} crash",
        "        {} crash on empty input",
        "> > > > > - **{}** x",
    ],
    ids=["dash bullet", "ordinal", "no lead", "8-space indent", "deep nested lead"],
)
@pytest.mark.parametrize(
    "emoji",
    [CRIT, HIGH, MED, LOW],
    ids=["critical", "high", "medium", "low"],
)
def test_every_severity_emoji_counts_as_the_first_character_after_the_lead(
    emoji: str,
    template: str,
    tmp_path: Path,
) -> None:
    """All four severity emoji (the real _SEVERITY_EMOJI keys) count when they
    are the first character left once the lead is stripped, however long the
    lead is: an 8-space indent and a five-deep quote nest leave the emoji
    first too, past any fixed window into the start of the line."""
    from cli.findings_section import _SEVERITY_EMOJI

    assert emoji in _SEVERITY_EMOJI
    _assert_emoji_row_refused(template.format(emoji), tmp_path)


_EMOJI_NOT_FIRST = {
    "mid-line": "- crash {} on empty input",
    "trailing": "- crash on empty input {}",
    "digit before": "- 3 {} crash",
    "other digit before": "- 7 {} crash",
    "colon before": "- : {} crash",
    "parenthesized word before": "- (x) {} crash",
    "letter ordinal before": "a. {} crash",
    "hash paren before": "#) {} x",
    "number and hashes before": "- 42 ### {} x",
}


@pytest.mark.parametrize(
    "template",
    list(_EMOJI_NOT_FIRST.values()),
    ids=list(_EMOJI_NOT_FIRST),
)
@pytest.mark.parametrize(
    "emoji",
    [CRIT, HIGH, MED, LOW],
    ids=["critical", "high", "medium", "low"],
)
def test_an_emoji_past_the_first_character_after_the_lead_is_prose(
    emoji: str,
    template: str,
) -> None:
    """Mid-line and trailing emoji are prose, and so is one behind junk that
    is not a lead: only the listed lead shapes are stripped, so any digit,
    `#)`, `###`, a parenthesized word or a letter ordinal in front of the
    emoji keeps it from being first. The junk is varied so that no fixed set
    of literal prefixes covers these lines."""
    _assert_prose_read(template.format(emoji))


# Both halves of the rule are closed sets: the severity emoji, and the lead
# marks that may precede one.
_NOT_AN_EMOJI_ROW = {
    "check mark": "- ✅ all green",
    "purple circle": "- 🟣 note",
    "puzzle piece": "🧩 follow-up",
    "parenthesized emoji": f"( {CRIT} )",
    "leading table pipe": f"| {CRIT} crash | src/a.py:3 |",
    "bangs": f"!!! {CRIT} x",
    "slashes": f"/// {CRIT} x",
}


@pytest.mark.parametrize(
    "line",
    list(_NOT_AN_EMOJI_ROW.values()),
    ids=list(_NOT_AN_EMOJI_ROW),
)
def test_only_a_severity_emoji_behind_lead_marks_alone_is_a_row(line: str) -> None:
    """A reader that asks "is the first character an emoji" refuses a green
    tick, a purple circle or a puzzle piece; one that strips any punctuation
    reads a table cell, a shouted note and a comment slash as finding rows."""
    from cli import gate

    assert gate._is_emoji_row(line) is False


def test_strip_lead_removes_quote_bullet_emphasis_and_zero_width_space() -> None:
    """The lead goes and nothing else does: the remainder is the content
    verbatim (closing `**` included), and a lead with no emoji behind it
    strips just the same - the lead marks are what is sought, not the emoji."""
    from cli import gate

    assert gate._strip_lead(f"> - **\u200b{CRIT}** x") == f"{CRIT}** x"
    assert gate._strip_lead("> - **x") == "x"
    assert gate._strip_lead("\t> 1. x") == "x"


# A lead mark that repeats back to back, or nests inside another kind, is
# still lead: the emoji behind it is the first character of the content.
_NESTED_LEADS = {
    "nested blockquote": "> > ",
    "nested dash bullet": "- - ",
    "nested typographic bullet": "• • ",
    "doubled dash": "-- ",
    "doubled en dash": "– – ",
    "quote nesting a bullet": "> > - ",
    "deep quote nest with emphasis": "> > > > > - **",
}
_NESTED_BODY = "crash src/a.py:3"
_NESTED_LEAD_PARAM = pytest.mark.parametrize(
    "lead",
    list(_NESTED_LEADS.values()),
    ids=list(_NESTED_LEADS),
)
_SEVERITY_PARAM = pytest.mark.parametrize(
    "emoji",
    [CRIT, HIGH, MED, LOW],
    ids=["critical", "high", "medium", "low"],
)


@_NESTED_LEAD_PARAM
@_SEVERITY_PARAM
def test_a_repeated_or_nested_lead_mark_is_still_stripped(
    emoji: str,
    lead: str,
) -> None:
    """A lead is stripped however often it repeats and however the marks nest,
    for every severity emoji, and nothing past the lead is touched: a reader
    that strips one mark and stops leaves `>`, `-` or `•` in front of the
    emoji, and one that returns the bare emoji drops the finding's text."""
    from cli import gate

    content = f"{emoji} {_NESTED_BODY}"
    assert gate._strip_lead(f"{lead}{content}") == content


@_NESTED_LEAD_PARAM
@_SEVERITY_PARAM
def test_an_emoji_row_behind_a_nested_lead_is_a_row(emoji: str, lead: str) -> None:
    """The emoji is first after the whole nested lead goes, so the row counts
    as a finding row - including `-- 🔴`, which was once pinned as junk."""
    from cli import gate

    assert gate._is_emoji_row(f"{lead}{emoji} {_NESTED_BODY}") is True


def test_bare_emoji_row_without_bullet_is_unread(tmp_path: Path) -> None:
    """No lead at all: the emoji is the first character, so it is a row."""
    _assert_emoji_row_refused(f"{CRIT} crash on empty input | src/a.py:3", tmp_path)


@pytest.mark.parametrize(
    "bullet",
    ["•", "◦", "‣", "–", "—", "－"],
    ids=[
        "bullet",
        "white bullet",
        "triangular bullet",
        "en dash",
        "em dash",
        "fullwidth dash",
    ],
)
def test_typographic_bullet_emoji_row_is_unread(bullet: str, tmp_path: Path) -> None:
    """A typographic bullet is a lead like `-`: stripped before the emoji."""
    _assert_emoji_row_refused(f"{bullet} {HIGH} wrong default", tmp_path)


_INVISIBLE_LEADS = {
    "zero-width space": "\u200b",
    "byte order mark": "\ufeff",
    "em space": "\u2003",
    "left-to-right mark": "\u200e",
    "no-break space": "\u00a0",
    "bullet then zwsp": "- \u200b",
    "nbsp then bullet": "\u00a0\u00a0- ",
}


@pytest.mark.parametrize(
    "lead",
    list(_INVISIBLE_LEADS.values()),
    ids=list(_INVISIBLE_LEADS),
)
def test_invisible_lead_emoji_row_is_unread(lead: str, tmp_path: Path) -> None:
    """Invisible space characters before the emoji are lead, not content - the
    whole Zs and Cf space, not two hardcoded code points: a BOM, an em space
    and a bidi mark lead a row just as a zero-width space does."""
    _assert_emoji_row_refused(f"{lead}{MED} stale cache", tmp_path)


@pytest.mark.parametrize(
    "row",
    [
        f"**{CRIT} crash on empty input** | src/a.py:3",
        f"__{LOW} cosmetic nit__",
        f"> {CRIT} crash",
        f"> - **{HIGH}** wrong default",
    ],
    ids=["bold", "underscore emphasis", "blockquote", "quoted bold bullet"],
)
def test_emphasis_wrapped_emoji_row_is_unread(row: str, tmp_path: Path) -> None:
    """Emphasis and blockquote leads are stripped before the emoji is read."""
    _assert_emoji_row_refused(row, tmp_path)


@pytest.mark.parametrize(
    "line",
    [
        f"**Note.** The cycle carries no {CRIT} finding",
        f"*Note:* the cycle carries no {CRIT} finding",
    ],
    ids=["bold", "italic"],
)
def test_bold_prose_mentioning_an_emoji_is_read(line: str) -> None:
    _assert_prose_read(line)


def test_blockquote_prose_mentioning_an_emoji_is_read() -> None:
    _assert_prose_read(f"> The reviewer saw a {CRIT} earlier")


def test_ordinal_year_prose_is_read() -> None:
    """A year read as an ordinal lead leaves prose, not an emoji, in front."""
    _assert_prose_read(f"2026. The year closed with one {CRIT} open")


def test_severity_split_line_is_read() -> None:
    _assert_prose_read(f"Severity split: 0 {CRIT} Critical, 2 {HIGH} High")


def test_refusal_names_the_matched_emoji() -> None:
    """An emoji row that would also match the [m/n] arm is named with the
    emoji wording, never the generic token wording."""
    from cli import gate

    row = f"- {CRIT} crash [1/3] | src/a.py:3"
    text = _review_text(alice=row)
    n = text.splitlines().index(row) + 1
    detail = gate._unread_token(text)
    assert detail == (
        f"line {n}: a severity emoji row the findings parser did not read: "
        f"- {CRIT} crash [1/3] | src/a.py:3"
    )
    assert "[m/n] token" not in detail


def test_a_consensus_token_before_the_emoji_blocks_the_emoji_wording() -> None:
    """`- [1/3] 🔴 crash` outside the findings section is unconsumed, but the
    `[1/3]` token is not a stripped lead character: `_strip_lead` stops at
    `[`, so the first remaining character is `[`, not the emoji.
    `_is_emoji_row` is False, and the line is still refused - but through the
    consensus-token arm of `_is_unread_line`, with the GENERIC `[m/n] token`
    wording, not the emoji wording. Only an emoji that leads (with nothing
    but stripped lead characters before it) earns the emoji wording -
    see test_refusal_names_the_matched_emoji for that case, where the emoji
    leads and a `[m/n]` token sits after it instead."""
    from cli import gate

    row = f"- [1/3] {CRIT} crash"
    text = _review_text(alice=row)
    assert gate._is_emoji_row(row) is False
    assert gate._unread_token(text) == _unread_detail(text, row)


@pytest.mark.parametrize(
    "opener",
    ["```python`", "```py` x"],
    ids=["trailing backtick", "mid backtick"],
)
def test_backtick_in_info_string_is_not_a_fence(opener: str) -> None:
    """A backtick anywhere in the info string means the line cannot open a
    backtick fence, so the row after it stays live and the later bare ```
    opens a fence that never closes."""
    from cli import gate

    row = f"- {CRIT} crash | src/a.py:3"
    text = _review_text(alice=f"{opener}\n{row}\n```")
    assert row in gate._unfenced(text).splitlines()
    assert gate.findings_verdict(text, _COVERED)[0] == "malformed"


def test_a_longer_closer_closes_and_a_4_space_closer_does_not() -> None:
    """CommonMark: a closer at least as long as the opener closes; one
    indented 4 spaces is content, not a closer."""
    from cli import gate

    row = f"- {CRIT} crash | src/a.py:3"
    longer = _review_text(alice=f"```\n{row}\n````")
    assert row not in gate._unfenced(longer).splitlines()
    indented = _review_text(alice=f"```\n{row}\n    ```")
    assert row in gate._unfenced(indented).splitlines()


def test_a_4_space_opener_does_not_open_a_fence() -> None:
    """CommonMark caps fence indent at 3 spaces: a 4-space ``` is no opener,
    so the row below it stays live even with a flush ``` after it."""
    from cli import gate

    row = f"- {CRIT} crash | src/a.py:3"
    text = _review_text(alice=f"    ```\n{row}\n```")
    assert row in gate._unfenced(text).splitlines()


def test_closer_with_trailing_text_does_not_close() -> None:
    """``` trailing text is no closer: the fence never closes, nothing is
    blanked. A bare ``` closer still blanks a ```python block."""
    from cli import gate

    row = f"- {CRIT} crash | src/a.py:3"
    open_text = _review_text(alice=f"```\n{row}\n``` trailing text")
    assert row in gate._unfenced(open_text).splitlines()
    assert gate.findings_verdict(open_text, _COVERED)[0] == "malformed"

    closed_text = _review_text(alice=f"```python\n{row}\n```")
    assert row not in gate._unfenced(closed_text).splitlines()
    assert gate.findings_verdict(closed_text, _COVERED) == ("ok", None)


# The three rules that are NOT the emoji rule, each in the shape whose escape
# the check was written for: a bare `[m/n]` token with no pipe and no emoji, a
# pipe row whose only severity signal is that token, and the pipe-less table
# whose structure is a leading `m/n`. A content rule holding the emoji branch
# alone passes every emoji test above and still lets all three through.
_OTHER_CONTENT_RULES = {
    "token alone, no pipe": "- [1/3] crash on empty input",
    "bare pipe row": "| R3 | [1/3] | stale cache | src/d.py:1 |",
    "pipe-less table row": (
        f"2/2    {CRIT} CRITICAL    stale cache    skills/x.py:3    alice"
    ),
}


@pytest.mark.parametrize(
    "row",
    list(_OTHER_CONTENT_RULES.values()),
    ids=list(_OTHER_CONTENT_RULES),
)
def test_the_token_pipe_row_and_pipeless_table_rules_each_stand_alone(
    row: str,
) -> None:
    """The emoji rule is one of four: the `[m/n]` token, a pipe row carrying
    one and a pipe-less table row beside a severity each make a line unread on
    their own, with no emoji-and-nothing-else fixture to lean on."""
    from cli import gate

    assert gate._is_unread_line(row) is True


@pytest.mark.parametrize(
    "template",
    [
        "Row 3: | {} | stale cache survives restart | src/x.py:3",
        "Row 3: |{}| stale cache survives restart | src/x.py:3",
    ],
    ids=["spaced pipes", "tight pipes"],
)
@pytest.mark.parametrize(
    "word",
    ["CRITICAL", "HIGH", "MEDIUM", "LOW", "Critical", "medium"],
)
def test_a_severity_word_with_pipes_around_it_is_a_finding(
    word: str,
    template: str,
    tmp_path: Path,
) -> None:
    """Rule (b): the pipes are what make a severity word a row, in any case and
    with or without padding inside them. With them the line is refused even
    with no emoji on it; the same word in prose, with no pipe anywhere, stays
    prose."""
    from cli import gate

    row = template.format(word)
    text = _review_text(alice=row)
    assert gate._is_unread_line(row) is True
    assert _verdict_and_exit(text, _COVERED, tmp_path) == (
        "malformed",
        _unread_detail(text, row),
        2,
    )
    assert gate._is_unread_line(f"- the reviewer called the risk {word}") is False


# The marker variants, every one of them spelled with three different ratios:
# a sweep that knows a finite set of literal marker strings ("[2/2]", "(2/2)")
# cannot cover them, and the ratio's digit counts are not symmetric either.
_MARKER_FORMS = ("[{} / {}]", "［{}/{}］", "【{}/{}】", "({}/{})")
_MARKER_FORM_IDS = ("spaced", "fullwidth", "lenticular", "parenthesized")
_MARKER_RATIOS = ((2, 2), (10, 12), (11, 2))
_MARKER_VARIANTS = tuple(
    form.format(m, n) for form in _MARKER_FORMS for m, n in _MARKER_RATIOS
)
_MARKER_IDS = tuple(
    f"{name} {m}/{n}" for name in _MARKER_FORM_IDS for m, n in _MARKER_RATIOS
)


@pytest.mark.parametrize("marker", _MARKER_VARIANTS, ids=_MARKER_IDS)
def test_a_marker_variant_after_a_finding_reference_is_a_finding(
    marker: str,
    tmp_path: Path,
) -> None:
    """Rule (c): a leading finding reference such as `R9` sits between the
    indent and the marker, and does not stop the marker starting the line."""
    from cli import gate

    row = f"R9 {marker} stale cache | src/x.py:3"
    text = _review_text(alice=row)
    assert gate._is_unread_line(row) is True
    assert _verdict_and_exit(text, _COVERED, tmp_path) == (
        "malformed",
        _unread_detail(text, row),
        2,
    )


@pytest.mark.parametrize(
    "template",
    [
        "<table><tr><td>notes {}</td><td>src/x.py:3</td></tr></table>",
        "stale cache <td>{}</td> src/x.py:3",
    ],
    ids=["table tag", "td tag"],
)
@pytest.mark.parametrize("marker", _MARKER_VARIANTS, ids=_MARKER_IDS)
def test_a_marker_variant_anywhere_on_a_tabular_line_is_a_finding(
    marker: str,
    template: str,
    tmp_path: Path,
) -> None:
    """On a line that is already structurally tabular the marker needs no
    anchor: it counts mid-line, with no severity emoji and no severity word to
    help (the same HTML row without a marker is not a finding today)."""
    from cli import gate

    row = template.format(marker)
    text = _review_text(alice=row)
    assert gate._is_unread_line(row) is True
    assert _verdict_and_exit(text, _COVERED, tmp_path) == (
        "malformed",
        _unread_detail(text, row),
        2,
    )


_NOT_A_FINDING = {
    "counting prose": "The suite ran 1092/1092 green.",
    "consensus heading": "### Full Consensus (3/3)",
    "low-hanging compound": "This is a low-hanging follow-up",
    "high-level compound": "a high-level overview",
    "severity word in prose": "The reviewer called the risk high.",
}


@pytest.mark.parametrize(
    "line",
    list(_NOT_A_FINDING.values()),
    ids=list(_NOT_A_FINDING),
)
def test_a_line_with_no_severity_signal_is_not_refused(line: str) -> None:
    """No false refusals: counting prose, a parenthesized count that does not
    start its line, a hyphenated severity compound and a bare severity word
    with no pipes all leave the covered batch passing."""
    from cli import gate

    text = _review_text(alice=line)
    assert gate._is_unread_line(line) is False
    assert gate._unread_token(text) is None
    assert gate.findings_verdict(text, _COVERED) == ("ok", None)


def test_the_read_findings_table_rows_are_not_reported_as_unread() -> None:
    """The header row, the separator row and the `| [m/n] | ... |` data rows of
    the one `## Consolidated Findings` section are read, so widening the
    content rule must not turn them into unread lines."""
    from cli import gate

    text = _review_text()
    lines = text.splitlines()
    for row in (line for line in _REF_TABLE.splitlines() if line.strip()):
        assert row in lines
    assert gate._unread_token(text) is None
    assert gate.findings_verdict(text, _COVERED) == ("ok", None)


def test_a_consensus_bullet_row_in_the_findings_section_is_not_unread() -> None:
    """A `- [m/n] ...` bullet row inside the one findings section is a shape the
    findings parser consumes, emoji and pipes and all."""
    from cli import gate

    bullet = f"- [2/2] {CRIT} crash on empty input | src/a.py:3 | Found by: alice"
    text = _review_text(f"## Consolidated Findings\n\n{bullet}\n")
    assert bullet in text.splitlines()
    assert gate._unread_token(text) is None


def test_a_stray_row_inside_the_findings_section_is_still_named(
    tmp_path: Path,
) -> None:
    """Being inside the findings section is not what makes a row read: only the
    shapes the parser consumes are. An emoji row below the table, in the same
    section, is still the unread line the refusal names - a walker that stops
    looking at the findings heading reports nothing here."""
    from cli import gate

    stray = f"- {CRIT} crash | src/a.py:3"
    text = _review_text(f"{_REF_TABLE}\n{stray}\n")
    assert stray in text.splitlines()
    assert gate._unread_token(text) == _unread_detail(text, stray)
    assert _verdict_and_exit(text, _COVERED, tmp_path) == (
        "malformed",
        _unread_detail(text, stray),
        2,
    )


def test_a_covered_review_with_nothing_unread_passes_with_exit_0(
    tmp_path: Path,
) -> None:
    """The other end of the exit space: the plain covered pair is `ok` and
    exits 0, so widening the content rule cannot be bought by refusing
    everything."""
    assert _verdict_and_exit(_review_text(), _COVERED, tmp_path) == ("ok", None, 0)


def test_a_review_row_no_finding_names_is_uncovered_not_malformed() -> None:
    """A non-malformed refusal: the coverage half of the cross-check still
    runs, so the unread-line check cannot stand in for the whole verdict."""
    from cli import gate

    assert gate.findings_verdict(_review_text(), [])[0] == "uncovered"


def test_the_detail_strips_the_indent_and_cuts_the_quote_at_120_chars() -> None:
    """The quoted text is `line.strip()[:120]`: an indented, overlong row is
    named without its indent and cut, so the refusal stays one readable line."""
    from cli import gate

    row = f"   - {CRIT} " + "stale cache survives restart; " * 8
    text = _review_text(alice=row)
    detail = gate._unread_token(text)
    assert len(row.strip()) > 200
    assert detail == _unread_detail(text, row)
    assert detail.endswith(row.strip()[:120])
    assert not detail.endswith(row.strip())
    assert "   " not in detail


def test_the_first_unread_line_is_the_one_named_not_the_last() -> None:
    """Two unread lines in one file: the refusal names the earlier one, the one
    the operator reaches first when repairing the file."""
    from cli import gate

    first = f"- {CRIT} crash on empty input"
    second = f"- {HIGH} wrong default | src/b.py:10"
    text = _review_text(alice=f"{first}\n{second}")
    lines = text.splitlines()
    assert lines.index(first) < lines.index(second)
    assert gate._unread_token(text) == _unread_detail(text, first)
    assert gate._unread_token(text) != _unread_detail(text, second)


_HEADER_ROW = "| Ref | Consensus | Severity | Issue | File | Found By |"
_DATA_ROW = f"| R9 | [2/2] | {CRIT} | stale cache | src/x.py:1 | alice |"
_FENCES = ("```", "~~~")
_FENCE_IDS = ("backticks", "tildes")


@pytest.mark.parametrize(
    ("fence_indent", "header_indent"),
    [("", "  "), ("   ", "  "), ("  ", "   "), (" ", "")],
    ids=[
        "flush fence, indented header",
        "3-space fence, indented header",
        "2-space fence, 3-space header",
        "1-space fence, flush header",
    ],
)
@pytest.mark.parametrize("fence", _FENCES, ids=_FENCE_IDS)
def test_a_closed_fence_finds_its_header_however_the_two_are_indented(
    fence: str,
    fence_indent: str,
    header_indent: str,
) -> None:
    """A closed fence whose body holds the findings-table header is found for
    both fence characters, with up to 3 spaces before either fence line and
    whatever indent the header line itself carries inside the body."""
    from cli import gate

    text = (
        f"notes above\n{fence_indent}{fence}\n"
        f"{header_indent}{_HEADER_ROW}\n{header_indent}{_DATA_ROW}\n"
        f"{fence_indent}{fence}\nnotes below\n"
    )
    assert gate._fenced_findings_header(text) is True


_NO_HEADER_BODIES = {
    "data row only": f"  - [2/2] {CRIT} crash | src/a.py:3",
    "header without Severity": "  | Ref | Consensus | Issue | File | Found By |",
    "prose": "  not a table at all",
}


@pytest.mark.parametrize(
    "body",
    list(_NO_HEADER_BODIES.values()),
    ids=list(_NO_HEADER_BODIES),
)
@pytest.mark.parametrize("fence", _FENCES, ids=_FENCE_IDS)
def test_a_fenced_example_without_the_findings_header_is_not_found(
    fence: str,
    body: str,
) -> None:
    """A worked example in a fence whose body names no Severity/Issue/File
    header is still just an example, indent and all."""
    from cli import gate

    text = f"notes above\n{fence}\n{body}\n{fence}\nnotes below\n"
    assert gate._fenced_findings_header(text) is False


# Three files that DO hold both a fence and the findings-table header and are
# still not a fenced header: the header sits outside the fence, the fence never
# closes, or the "fence" is indented 4 spaces and so is a code block, not a
# fence at all. A two-substring sniff ("```" in text and "Severity" in text)
# calls all three True.
_NOT_A_FENCED_HEADER = {
    "header outside, example inside": "{h}\n{d}\n{f}\n  - [2/2] example\n{f}\n",
    "unclosed fence holds the header": "notes above\n{f}\n{h}\n{d}\nnotes below\n",
    "4-space fence is a code block": (
        "notes above\n    {f}\n    {h}\n    {d}\n    {f}\nnotes below\n"
    ),
}


@pytest.mark.parametrize(
    "template",
    list(_NOT_A_FENCED_HEADER.values()),
    ids=list(_NOT_A_FENCED_HEADER),
)
@pytest.mark.parametrize("fence", _FENCES, ids=_FENCE_IDS)
def test_a_header_no_closed_fence_encloses_is_not_a_fenced_header(
    fence: str,
    template: str,
) -> None:
    """Only a CLOSED fence whose body holds the header counts: the detection
    walks fence blocks, so a header beside a fence, a header under an opener
    that never closes, and a header inside an indented code block all answer
    False."""
    from cli import gate

    text = template.format(f=fence, h=_HEADER_ROW, d=_DATA_ROW)
    assert "Severity" in text
    assert fence in text
    assert gate._fenced_findings_header(text) is False


@pytest.mark.parametrize("fence", _FENCES, ids=_FENCE_IDS)
def test_a_review_whose_fence_indents_the_header_is_malformed(
    fence: str,
    tmp_path: Path,
) -> None:
    """A review file that hides the real header behind a fence, indented inside
    it, is refused by the fenced-header detail - not by the unread-line one."""
    from cli import gate

    hidden = f"{fence}\n  {_HEADER_ROW}\n  {_DATA_ROW}\n{fence}"
    text = _review_text(alice=hidden)
    assert _verdict_and_exit(text, _COVERED, tmp_path) == (
        "malformed",
        gate._FENCED_HEADER_DETAIL,
        2,
    )


if __name__ == "__main__":
    unittest.main()
