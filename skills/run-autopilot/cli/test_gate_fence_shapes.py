#!/usr/bin/env python3
"""The fence shapes of the `gate --findings` unread-line check.

Split out of test_gate_findings_unread_shapes.py (past the 800-line limit in
rules/coding-style.md). Every test below pins how a fence hides or exposes
rows: what opens and closes one, and the findings-table header hidden by a
fence that indents it.
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
    _review_text,
    _verdict_and_exit,
)


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


def test_a_pseudo_opener_leaves_only_a_later_real_fence_pair_blanked() -> None:
    """A line that cannot open a fence does not swallow the rest of the file:
    the row after it stays live, a real fence pair further down blanks only
    its own body, and content after that pair is live again."""
    from cli import gate

    live_before = f"- {CRIT} crash | src/a.py:3"
    hidden = f"- {HIGH} wrong default | src/b.py:7"
    live_after = f"- {MED} stale cache | src/c.py:9"
    text = _review_text(
        alice=f"```py`\n{live_before}\n```\n{hidden}\n```\n{live_after}"
    )
    unfenced = gate._unfenced(text).splitlines()
    assert live_before in unfenced
    assert hidden not in unfenced
    assert live_after in unfenced


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
