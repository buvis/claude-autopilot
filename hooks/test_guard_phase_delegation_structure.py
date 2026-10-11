"""Lookalike-text normalization in front of the phase-delegation guard:
compatibility forms, invisible format characters, combining marks and the
Unicode dash family are reduced to plain text before any matching.

Sibling of test_guard_phase_delegation.py (kept apart for the file size limit).
Every lookalike code point is written as an escaped literal, never pasted: the
characters are invisible or combining and an editor would silently destroy them.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parent


def _guard_module():
    sys.path.insert(0, str(HOOKS))
    return importlib.import_module("guard_phase_delegation")


@pytest.mark.parametrize(
    "prompt",
    [
        "Invoke /autopilot:plan\u2011tasks for PRD 00300.",
        "Invoke /autopilot:plan\u2212tasks for PRD 00300.",
        "Run the wo\ufeffrk phase for PRD 00300.",
        "Run the wo\u2061rk phase for PRD 00300.",
        "Run the wo\u180erk phase for PRD 00300.",
        "Run the w\u00f3rk phase for PRD 00300.",
        "Run the wo\u0347rk phase for PRD 00300.",
    ],
    ids=[
        "non-breaking-hyphen",
        "minus-sign",
        "zero-width-no-break-space",
        "function-application",
        "mongolian-vowel-separator",
        "precomposed-acute",
        "combining-equals-below",
    ],
)
def test_lookalike_dashes_and_invisible_marks_are_normalized_and_denied(
    prompt: str,
) -> None:
    assert _guard_module().is_phase_delegation({"prompt": prompt}) is True


@pytest.mark.parametrize(
    "prompt",
    [
        "Invoke /autopilot:plan\u301ctasks for PRD 00300.",
        "Invoke /autopilot:plan\u05betasks for PRD 00300.",
    ],
    ids=["wave-dash", "hebrew-maqaf"],
)
def test_a_dash_outside_the_common_block_is_normalized_and_denied(
    prompt: str,
) -> None:
    """Every Pd code point folds to "-", not only the U+2010-U+2015 block: a
    wave dash hides a skill name from the patterns just as well."""
    assert _guard_module().is_phase_delegation({"prompt": prompt}) is True


@pytest.mark.parametrize(
    "tool_input",
    [
        {"prompt": "Summarize the wo\ufeffrk you finished for PRD 00300."},
        {"prompt": "Write the regression test for PRD 00300, report the count."},
    ],
    ids=["lookalike-but-no-phase-instruction", "plain-per-task-prompt"],
)
def test_per_task_dispatch_without_a_phase_instruction_is_allowed(
    tool_input: dict,
) -> None:
    """Normalization may not turn an ordinary per-task dispatch into a denial:
    cleaning the text is not itself grounds to deny."""
    assert _guard_module().is_phase_delegation(tool_input) is False


@pytest.mark.parametrize(
    "tool_input",
    [
        {"description": "Run the wo\ufeffrk phase for PRD 00300."},
        {
            "prompt": "Tess, retry task 1.",
            "description": "Invoke /autopilot:plan\u2011tasks for PRD 00300.",
        },
    ],
    ids=["description-only", "clean-prompt-lookalike-description"],
)
def test_lookalike_hidden_in_the_description_is_normalized_and_denied(
    tool_input: dict,
) -> None:
    assert _guard_module().is_phase_delegation(tool_input) is True


def test_lookalike_far_inside_a_long_prompt_is_normalized_and_denied() -> None:
    """Real dispatch prompts are hundreds of lines; a lookalike past the first
    line must be reduced too, so normalization cannot stop after a prefix."""
    prompt = "Tess, task 1 of PRD 00300. " * 10 + "Run the wo\ufeffrk phase now."
    assert len(prompt) > 200
    assert _guard_module().is_phase_delegation({"prompt": prompt}) is True


def test_negation_on_an_earlier_line_does_not_hide_a_later_delegation() -> None:
    """The newline between the lines is a sentence boundary for the negation
    window, so it must survive normalization intact."""
    prompt = "Do not stop now\nRun the wo\ufeffrk phase for PRD 00300."
    assert _guard_module().is_phase_delegation({"prompt": prompt}) is True


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
    ("wo\ufeffrk", "work", "zero-width-no-break-space"),
    ("wo\u2061rk", "work", "function-application"),
    ("wo\u180erk", "work", "mongolian-vowel-separator"),
    ("wo\u200brk", "work", "zero-width-space"),
    ("wo\u200crk", "work", "zero-width-non-joiner"),
    ("wo\u200drk", "work", "zero-width-joiner"),
    ("wo\u2060rk", "work", "word-joiner"),
    ("wo\u00adrk", "work", "soft-hyphen"),
    ("w\u00f3rk", "work", "precomposed-acute"),
    ("wo\u0301rk", "work", "decomposed-acute"),
    ("wo\u0347rk", "work", "combining-equals-below"),
    ("\uff57ork", "work", "fullwidth-letter"),
    ("don\u2018t", "don't", "left-curly-quote"),
    ("don\u2019t", "don't", "right-curly-quote"),
    ("**work**", "work", "emphasis-markers"),
    ("*work*", "work", "single-emphasis-markers"),
    ("**the work phase**", "the work phase", "emphasis-around-a-phrase"),
    ("Run the **work** phase", "Run the work phase", "emphasis-markers-mid-string"),
]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(raw, expected) for raw, expected, _ in _LOOKALIKE_CASES],
    ids=[case_id for _, _, case_id in _LOOKALIKE_CASES],
)
def test_normalize_reduces_lookalike_text_to_its_plain_form(
    raw: str,
    expected: str,
) -> None:
    normalize = _guard_module()._normalize
    assert normalize(raw) == expected
    assert normalize(f"the {raw} helper") == f"the {expected} helper"
    assert normalize(expected) == expected


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


def test_normalize_leaves_whitespace_unchanged() -> None:
    """Nothing in the contract collapses whitespace: the newline between prompt
    and description, and every newline inside a prompt, must stay put."""
    assert _guard_module()._normalize("a\n\nb\tc  d") == "a\n\nb\tc  d"
