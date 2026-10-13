#!/usr/bin/env python3
"""The CONTENT rule of the `gate --findings` unread-line check.

A sibling of test_gate_findings_shapes.py (1049 lines, past the 800-line limit
in rules/coding-style.md), whose fixtures are imported here rather than
re-spelled. Every test below pins what makes an unconsumed line a finding, as
opposed to where it sits: a severity emoji ANYWHERE on the line with nothing
else to back it, a severity word with pipes around it, a consensus-marker
variant after a finding reference or on a structurally tabular line, and the
findings-table header hidden by a fence that indents it. The negative half
matters as much: counting prose, a consensus heading and a hyphenated severity
compound must still pass, and the rows the findings parser does read must never
be reported as unread.
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
    assert gate._is_unread_line(row) is True
    assert gate._unread_token(text) == _unread_detail(text, row)
    assert _verdict_and_exit(text, _COVERED, tmp_path) == (
        "malformed",
        _unread_detail(text, row),
        2,
    )


@pytest.mark.parametrize(
    "template",
    [
        "- {} crash on empty input",
        "- crash {} on empty input",
        "- crash on empty input {}",
    ],
    ids=["leading", "mid-line", "trailing"],
)
@pytest.mark.parametrize(
    "emoji",
    [CRIT, HIGH, MED, LOW],
    ids=["critical", "high", "medium", "low"],
)
def test_every_severity_emoji_counts_wherever_it_sits_on_the_line(
    emoji: str,
    template: str,
    tmp_path: Path,
) -> None:
    """All four severity emoji count, and position is irrelevant: a sweep that
    only looks after the bullet marker misses the trailing one."""
    row = template.format(emoji)
    text = _review_text(alice=row)
    assert _verdict_and_exit(text, _COVERED, tmp_path) == (
        "malformed",
        _unread_detail(text, row),
        2,
    )


@pytest.mark.parametrize("word", ["CRITICAL", "HIGH", "MEDIUM", "LOW"])
def test_a_severity_word_with_pipes_around_it_is_a_finding(
    word: str,
    tmp_path: Path,
) -> None:
    """Rule (b): the pipes are what make a severity word a row. With them the
    line is refused even with no emoji on it; the same word in prose, with no
    pipe anywhere, stays prose."""
    from cli import gate

    row = f"Row 3: | {word} | stale cache survives restart | src/x.py:3"
    text = _review_text(alice=row)
    assert gate._is_unread_line(row) is True
    assert _verdict_and_exit(text, _COVERED, tmp_path) == (
        "malformed",
        _unread_detail(text, row),
        2,
    )
    assert gate._is_unread_line(f"- the reviewer called the risk {word}") is False


_MARKER_VARIANTS = ("[2 / 2]", "［2/2］", "【2/2】", "(2/2)")
_MARKER_IDS = ("spaced", "fullwidth", "lenticular", "parenthesized")


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


@pytest.mark.parametrize("line", list(_NOT_A_FINDING.values()), ids=list(_NOT_A_FINDING))
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
