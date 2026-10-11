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
    ("raw", "expected"),
    [
        ("plan\u2011tasks", "plan-tasks"),
        ("plan\u2212tasks", "plan-tasks"),
        ("plan\u2014tasks", "plan-tasks"),
        ("wo\ufeffrk", "work"),
        ("wo\u2061rk", "work"),
        ("wo\u180erk", "work"),
        ("w\u00f3rk", "work"),
        ("wo\u0347rk", "work"),
        ("don\u2018t", "don't"),
        ("don\u2019t", "don't"),
        ("**work**", "work"),
        ("Run the **work** phase", "Run the work phase"),
    ],
    ids=[
        "non-breaking-hyphen",
        "minus-sign",
        "em-dash",
        "zero-width-no-break-space",
        "function-application",
        "mongolian-vowel-separator",
        "precomposed-acute",
        "combining-equals-below",
        "left-curly-quote",
        "right-curly-quote",
        "emphasis-markers",
        "emphasis-markers-mid-string",
    ],
)
def test_normalize_reduces_lookalike_text_to_its_plain_form(
    raw: str,
    expected: str,
) -> None:
    assert _guard_module()._normalize(raw) == expected


def test_normalize_leaves_homoglyph_letters_alone() -> None:
    """Homoglyphs are out of scope: a Cyrillic "o" is a different letter, not a
    compatibility form, so normalization must not fold it into an ASCII "o"."""
    assert _guard_module()._normalize("w\u043erk") == "w\u043erk"


def test_normalize_leaves_plain_ascii_text_untouched() -> None:
    assert _guard_module()._normalize("Run the work phase for PRD 00300.") == (
        "Run the work phase for PRD 00300."
    )
