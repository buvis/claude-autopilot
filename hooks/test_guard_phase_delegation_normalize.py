"""Lookalike-text normalization in front of the phase-delegation guard:
compatibility forms, invisible format characters, combining marks and the
Unicode dash family reduced to plain text before any matching.

Split off `test_guard_phase_delegation_structure.py` (PRD 00271, task 14) to
keep that file under the repo's 800-line limit. Sibling of both
test_guard_phase_delegation.py and test_guard_phase_delegation_structure.py.
Every lookalike code point is written as an escaped literal, never pasted:
the characters are invisible or combining and an editor would silently
destroy it.

The category sweeps walk the whole Pd/Cf/Mn code-point space instead of a
sample, which is a cross-cutting pin that makes a sentence table or an
allow-list useless as an implementation.
"""

from __future__ import annotations

import importlib
import sys
import unicodedata
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parent


def _guard_module():
    sys.path.insert(0, str(HOOKS))
    return importlib.import_module("guard_phase_delegation")


def _params(cases: list[tuple]) -> list:
    """(value, ..., case id) tuples as pytest params: every case list below
    keeps its ids beside its values, never in a parallel list."""
    return [pytest.param(*case[:-1], id=case[-1]) for case in cases]


# (raw, expected plain form, case id). Each case is also asserted inside a
# carrier phrase and re-normalized, so a lookup table keyed on these exact
# strings cannot stand in for the rule.
_LOOKALIKE_CASES = [
    ("plan\u2011tasks", "plan-tasks", "non-breaking-hyphen"),
    ("plan\u2212tasks", "plan-tasks", "minus-sign"),
    ("plan\u2014tasks", "plan-tasks", "em-dash"),
    ("plan\u2010tasks", "plan-tasks", "hyphen"),
    ("plan\u2013tasks", "plan-tasks", "en-dash"),
    # Pd code points outside the U+2010-U+2015 block, neither folded by NFKD:
    # the contract names the whole Pd category, so folding a literal dash
    # range is not enough.
    ("plan\u301ctasks", "plan-tasks", "wave-dash"),
    ("plan\u05betasks", "plan-tasks", "hebrew-maqaf"),
    ("plan\u058atasks", "plan-tasks", "armenian-hyphen"),
    ("plan\u2e3atasks", "plan-tasks", "two-em-dash"),
    ("plan\u2015tasks", "plan-tasks", "horizontal-bar"),
    ("wo\ufeffrk", "work", "zero-width-no-break-space"),
    ("wo\u2061rk", "work", "function-application"),
    ("wo\u180erk", "work", "mongolian-vowel-separator"),
    ("wo\u200brk", "work", "zero-width-space"),
    ("wo\u200crk", "work", "zero-width-non-joiner"),
    ("wo\u200drk", "work", "zero-width-joiner"),
    ("wo\u2060rk", "work", "word-joiner"),
    ("wo\u2066rk", "work", "left-to-right-isolate"),
    ("wo\u061crk", "work", "arabic-letter-mark"),
    ("wo\u00adrk", "work", "soft-hyphen"),
    ("w\u00f3rk", "work", "precomposed-acute"),
    ("wo\u0301rk", "work", "decomposed-acute"),
    ("wo\u0300rk", "work", "combining-grave"),
    ("wo\u0323rk", "work", "combining-dot-below"),
    ("wo\u0347rk", "work", "combining-equals-below"),
    ("\uff57ork", "work", "fullwidth-letter"),
    ("w\uff4frk", "work", "fullwidth-o"),
    ("don\u2018t", "don't", "left-curly-quote"),
    ("don\u2019t", "don't", "right-curly-quote"),
    ("**work**", "work", "emphasis-markers"),
    ("*work*", "work", "single-emphasis-markers"),
    ("**the work phase**", "the work phase", "emphasis-around-a-phrase"),
    ("Run the **work** phase", "Run the work phase", "emphasis-markers-mid-string"),
]


@pytest.mark.parametrize(("raw", "expected"), _params(_LOOKALIKE_CASES))
def test_normalize_reduces_lookalike_text_to_its_plain_form(
    raw: str,
    expected: str,
) -> None:
    normalize = _guard_module()._normalize
    assert normalize(raw) == expected
    assert normalize(f"the {raw} helper") == f"the {expected} helper"
    assert normalize(expected) == expected


def _nfkd_stable_by_category(*categories: str) -> dict[str, list[str]]:
    """Every assigned code point of each named category whose NFKD form is
    itself, so the category is the only variable: a code point NFKD rewrites
    into another category (U+0F77 into a Tibetan letter) says nothing about
    what a category-level contract promises."""
    found: dict[str, list[str]] = {category: [] for category in categories}
    for code_point in range(0x110000):
        char = chr(code_point)
        category = unicodedata.category(char)
        if category in found and unicodedata.normalize("NFKD", char) == char:
            found[category].append(char)
    return found


_STABLE = _nfkd_stable_by_category("Pd", "Cf", "Mn")


def test_normalize_drops_every_invisible_or_combining_code_point() -> None:
    """The contract names the whole Cf and Mn categories, not a table of the
    code points someone thought of: every one of them, dropped from inside a
    word, must leave the plain word behind."""
    marks = _STABLE["Cf"] + _STABLE["Mn"]
    # Controls: the sweep is real, and holds the families a hand table misses.
    assert len(marks) > 500
    for control in ("\u2066", "\u061c", "\u0300", "\u0323", "\ufeff"):
        assert control in marks, hex(ord(control))
    normalize = _guard_module()._normalize
    survivors = [hex(ord(char)) for char in marks if normalize(f"wo{char}rk") != "work"]
    assert survivors == []


def test_normalize_folds_every_dash_punctuation_code_point() -> None:
    """Same for Pd: every dash code point reads as "-" between two words, so a
    skill name cannot hide behind the one dash nobody listed."""
    dashes = _STABLE["Pd"]
    assert len(dashes) > 15
    for control in ("-", "\u2015", "\u058a", "\u2e3a", "\u301c"):
        assert control in dashes, hex(ord(control))
    normalize = _guard_module()._normalize
    unfolded = [
        hex(ord(char))
        for char in dashes
        if normalize(f"plan{char}tasks") != "plan-tasks"
    ]
    assert unfolded == []


@pytest.mark.parametrize(
    "letter",
    ["\u0430", "\u0435", "\u0440", "\u0441", "\u043e", "\u03bf"],
    ids=[
        "cyrillic-a",
        "cyrillic-ie",
        "cyrillic-er",
        "cyrillic-es",
        "cyrillic-o",
        "greek-omicron",
    ],
)
def test_normalize_leaves_homoglyph_letters_alone(letter: str) -> None:
    """Homoglyphs are out of scope: a Cyrillic "o" is a different letter, not a
    compatibility form, so normalization must not fold it into an ASCII "o"."""
    assert _guard_module()._normalize(f"pre{letter}post") == f"pre{letter}post"


def test_normalize_leaves_plain_ascii_text_untouched() -> None:
    assert _guard_module()._normalize("Run the work phase for PRD 00300.") == (
        "Run the work phase for PRD 00300."
    )


def test_normalize_keeps_text_outside_the_normalized_families() -> None:
    """Only the contract's families change: accents (Mn) are dropped and every
    asterisk goes, while other non-ASCII letters survive untouched."""
    assert _guard_module()._normalize("Tom\u00e1\u0161 2**8 *args \u65e5\u672c") == (
        "Tomas 28 args \u65e5\u672c"
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("\ud55c\uae00 run the work phase", "\ud55c\uae00 run the work phase"),
        ("\u1112\u1161\u11ab\u1100\u1173\u11af", "\ud55c\uae00"),
        ("5 \u212b of travel", "5 A of travel"),
    ],
    ids=["hangul-syllables", "hangul-jamo", "angstrom-sign"],
)
def test_normalize_returns_composed_text(raw: str, expected: str) -> None:
    """The plain form is COMPOSED, so the character count a caller sees is the
    one it would read in the source text: _negated_before measures its window
    in characters, and text left split into jamo inflates that count and moves
    the window. A compatibility sign still lands on its plain ASCII letter."""
    assert _guard_module()._normalize(raw) == expected


def test_normalize_leaves_whitespace_unchanged() -> None:
    """Nothing in the contract collapses whitespace: the newline between prompt
    and description, and every newline inside a prompt, must stay put."""
    assert _guard_module()._normalize("a\n\nb\tc  d") == "a\n\nb\tc  d"
