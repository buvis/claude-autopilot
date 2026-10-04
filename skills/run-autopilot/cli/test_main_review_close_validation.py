#!/usr/bin/env python3
"""Tests for cli/__main__.py's review-close finding validation (PRD 00249,
finding F6 at __main__.py:1017).

_is_chosen_finding is the gate `_run_review_close` runs over every row of
the findings JSON before review_close.close() is ever called, so a row it
rejects can never reach a mutation.
"""

from __future__ import annotations

from cli import __main__ as cli_main


def _row(classification: str, **overrides: object) -> dict:
    base = {
        "classification": classification,
        "severity": "\U0001f7e0",
        "file": "src/x.py",
        "issue": "something",
        "found_by": ["bob"],
    }
    base.update(overrides)
    return base


def test_rejects_an_unknown_classification_value() -> None:
    assert cli_main._is_chosen_finding(_row("fxi")) is False


def test_accepts_the_known_non_actionable_classifications() -> None:
    assert cli_main._is_chosen_finding(_row("verify")) is True
    assert cli_main._is_chosen_finding(_row("discard")) is True


def test_accepts_fix_and_defer_with_complete_string_fields() -> None:
    assert cli_main._is_chosen_finding(_row("fix")) is True
    assert cli_main._is_chosen_finding(_row("defer")) is True


def test_rejects_found_by_that_is_not_a_list() -> None:
    assert cli_main._is_chosen_finding(_row("fix", found_by="bob")) is False


def test_rejects_found_by_containing_a_non_string_element() -> None:
    assert cli_main._is_chosen_finding(_row("fix", found_by=["bob", 2])) is False


def test_accepts_found_by_as_a_list_of_strings() -> None:
    assert cli_main._is_chosen_finding(_row("fix", found_by=["bob", "carl"])) is True


def test_rejects_plain_word_severity() -> None:
    assert cli_main._is_chosen_finding(_row("fix", severity="CRITICAL")) is False
