"""Tests binding the live text of the narrow-test-run sentence — the
instruction that Tess, Devon, and Ivan each run only the task's own test
files (never a whole suite or a whole directory) mid-task, with the full
suite running once at the end.

Mirrors test_adversarial_cap_prose.py's and test_devon_round_prose.py's
pattern: resolve each target file's path relative to this file, read it
once at module level, and assert on short, reword-resistant substrings,
each with a failure message naming what drifted.
"""

from __future__ import annotations

from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
_WORK_DIR = _SCRIPTS_DIR.parent
_SKILLS_DIR = _WORK_DIR.parent
_REPO_ROOT = _SKILLS_DIR.parent

_SKILL_MD = _WORK_DIR / "SKILL.md"
_SKILL_TEXT = _SKILL_MD.read_text()

_TESS_PROMPT = _WORK_DIR / "references" / "tess-prompt.md"
_TESS_PROMPT_TEXT = _TESS_PROMPT.read_text()

_IVAN_AGENT = _REPO_ROOT / "agents" / "ivan.md"
_IVAN_AGENT_TEXT = _IVAN_AGENT.read_text()

_ADVERSARIAL_TEST_PROMPT = _WORK_DIR / "references" / "adversarial-test-prompt.md"
_ADVERSARIAL_TEXT = _ADVERSARIAL_TEST_PROMPT.read_text()


def _norm(text: str) -> str:
    """Collapse every run of whitespace (including line-wrap newlines) to a
    single space, so a substring check doesn't break when markdown wraps a
    sentence across lines at a point the needle spells as a plain space."""
    return " ".join(text.split())


def test_tess_and_ivan_carry_the_narrow_sentence() -> None:
    anchor = _norm("Read every file before your first Edit to it.")
    narrow_start = _norm(
        "Run only the test files this task names (the tests you wrote, "
        "or the failing tests in your prompt)"
    )

    def _paragraph(text: str, path: Path) -> str:
        norm_text = _norm(text)
        assert anchor in norm_text, f"{path}: expected {anchor!r} — not found."
        assert narrow_start in norm_text, (
            f"{path}: expected the narrow-run paragraph starting "
            f"{narrow_start!r} — not found."
        )
        assert norm_text.index(narrow_start) > norm_text.index(anchor), (
            f"{path}: expected the narrow-run paragraph to come directly "
            f"after {anchor!r} — found before it instead."
        )
        for para in text.split("\n\n"):
            if _norm(para).startswith(narrow_start):
                return para
        raise AssertionError(
            f"{path}: found the narrow-run paragraph in the normalized "
            "whole-file text but could not locate it as a standalone "
            "paragraph split on a blank line."
        )

    ivan_paragraph = _paragraph(_IVAN_AGENT_TEXT, _IVAN_AGENT)
    tess_paragraph = _paragraph(_TESS_PROMPT_TEXT, _TESS_PROMPT)
    assert _norm(ivan_paragraph) == _norm(tess_paragraph), (
        f"{_IVAN_AGENT} and {_TESS_PROMPT}: the narrow-run paragraph "
        "differs between the two files — expected verbatim text "
        "(ignoring markdown line-wrap whitespace)."
    )


def test_devon_runner_is_the_tasks_test_files() -> None:
    norm_text = _norm(_ADVERSARIAL_TEXT)
    assert _norm("runs ONLY this task's test files") in norm_text, (
        f"{_ADVERSARIAL_TEST_PROMPT}: expected \"runs ONLY this task's "
        'test files" in the Test runner command placeholder — not '
        "found. It appears to have drifted or been removed."
    )
    assert _norm("e.g. npm test, pytest, cargo test") not in norm_text, (
        f"{_ADVERSARIAL_TEST_PROMPT}: found the old generic runner-"
        "command placeholder 'e.g. npm test, pytest, cargo test' — it "
        "should have been replaced by the narrow, task-scoped wording."
    )


def test_devon_rules_forbid_a_directory_run() -> None:
    needle = _norm(
        "Run only the test runner command above, once per exploit; "
        "never a whole test directory."
    )
    assert needle in _norm(_ADVERSARIAL_TEXT), (
        f"{_ADVERSARIAL_TEST_PROMPT}: expected the Devon Rules list to "
        f"end with {needle!r} — not found."
    )


def test_work_skill_names_rework_mode() -> None:
    needle = _norm(
        "This holds in rework mode and for every subagent prompt (Tess, "
        "Devon, Ivan): each carries the same narrow-run sentence."
    )
    assert needle in _norm(_SKILL_TEXT), (
        f"{_SKILL_MD}: expected {needle!r} — not found. The rework-mode "
        "prose pin for the narrow-run sentence appears to have drifted "
        "or been removed."
    )
