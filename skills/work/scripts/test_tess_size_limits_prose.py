"""Pins PRD 00197: Tess is told the style limits up front (rule 12) and the
step-2.8 quality gate runs the style script over the test files, so an
oversized test file is fixed by a cheap Tess retry, not an Ivan split after
implementation.

Same pattern as test_dispatch_prose.py: read each file once, assert on short,
reword-resistant substrings, each with a failure message naming what drifted.
Run by dev/bin/release-checks (`[checks] loop blockers prose`).
"""

from __future__ import annotations

from pathlib import Path

_WORK_DIR = Path(__file__).resolve().parent.parent
_SKILL_MD = _WORK_DIR / "SKILL.md"
_TESS_PROMPT = _WORK_DIR / "references" / "tess-prompt.md"
_TESS_RETRY = _WORK_DIR / "references" / "tess-retry-prompt.md"
_TEST_AUTHOR = _WORK_DIR / "references" / "test-author-prompt.md"


def _rule(text: str, path: Path, number: str) -> str:
    anchor = f"\n{number}. "
    assert anchor in text, f"{path}: no rule {number} - renumbered or removed?"
    start = text.index(anchor)
    end = text.index("\n", start + 1)
    return text[start:end]


def test_tess_prompt_states_both_limits() -> None:
    rule_12 = _rule(_TESS_PROMPT.read_text(), _TESS_PROMPT, "12")
    for needle in ("SIZE LIMITS", "under 50 lines", "under 800 lines"):
        assert needle in rule_12, (
            f"{_TESS_PROMPT}: rule 12 lacks {needle!r}, so Tess learns the "
            "limit from the step-5.65 gate after Ivan has implemented, and "
            "an extra Ivan dispatch splits the file."
        )


def test_tess_retry_prompt_treats_style_lines_as_issues() -> None:
    rule_8 = _rule(_TESS_RETRY.read_text(), _TESS_RETRY, "8")
    for needle in ("SIZE LIMITS", "under 50 lines", "under 800 lines", "style-gate"):
        assert needle in rule_8, (
            f"{_TESS_RETRY}: rule 8 lacks {needle!r}, so a style-gate line in "
            "the retry feedback is not something the retry is told to fix."
        )


def test_quality_gate_runs_the_style_script_on_test_files() -> None:
    # SKILL.md step 2.8 keeps the rule, the invocation and a read-first
    # pointer (the body is at its 500-line ceiling); test-author-prompt.md
    # § Quality gate carries the diff construction. Both halves are pinned: a
    # pointer to a missing section is a gate nobody runs, and a section
    # nothing points at is the same.
    text = _SKILL_MD.read_text()
    start = text.index("### 2.8.")
    step_2_8 = text[start : text.index("### 2.85.", start)]
    for needle in (
        "check_style_limits.py --diff dev/local/tmp/test-diff-<task-id>.txt",
        "over the test files only",
        "Style limits on the test files",
        "Exit 1 is a quality-gate failure",
        "counts toward the two quality-gate retries",
    ):
        assert needle in step_2_8, f"{_SKILL_MD}: step 2.8 lacks {needle!r}"

    reference = _TEST_AUTHOR.read_text()
    section_start = reference.index("### Style limits on the test files")
    section = reference[section_start : reference.index("\n## ", section_start)]
    for needle in (
        "check_style_limits.py --diff dev/local/tmp/test-diff-<task-id>.txt",
        "git diff --no-index -- /dev/null",
        "git diff <task_base_sha> -- <tracked test files>",
        "Exit 1 is a quality-gate failure",
        "counts toward the two quality-gate retries",
    ):
        assert needle in section, (
            f"{_TEST_AUTHOR}: § Style limits on the test files lacks {needle!r}"
        )
