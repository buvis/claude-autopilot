"""Tests binding the live text of the single-Devon-round prose — cutting the
second Devon dispatch, documenting the new `exploit_fixed` attempt value and
the `devon_weak_points` / `devon_in_contract` / `devon_exploit` attempt-
record fields, and keeping the Devon/Tess prose internally consistent
(CHANGELOG, the Feedback-to-Tess template, and the Tess-budget line).

Mirrors test_adversarial_cap_prose.py's pattern: resolve each target file's
path relative to this file, read it once at module level, and assert on
short, reword-resistant substrings, each with a failure message naming what
drifted. Only the assertions that name a specific section (via `_section`
below) are section-scoped; every other presence or absence assertion is
whole-file on purpose, so wording that moves elsewhere in the file, rather
than vanishing outright, still fails it.
"""

from __future__ import annotations

from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
_WORK_DIR = _SCRIPTS_DIR.parent
_SKILLS_DIR = _WORK_DIR.parent
_REPO_ROOT = _SKILLS_DIR.parent

_SKILL_MD = _WORK_DIR / "SKILL.md"
_SKILL_TEXT = _SKILL_MD.read_text()

_ADVERSARIAL_TEST_PROMPT = _WORK_DIR / "references" / "adversarial-test-prompt.md"
_ADVERSARIAL_TEXT = _ADVERSARIAL_TEST_PROMPT.read_text()

_ATTEMPT_LOGGING = _WORK_DIR / "references" / "attempt-logging.md"
_ATTEMPT_LOGGING_TEXT = _ATTEMPT_LOGGING.read_text()

_STATE_SCHEMA = _SKILLS_DIR / "run-autopilot" / "references" / "state-schema.md"
_STATE_SCHEMA_TEXT = _STATE_SCHEMA.read_text()

_CHANGELOG = _REPO_ROOT / "CHANGELOG.md"
_CHANGELOG_TEXT = _CHANGELOG.read_text()


def _section(
    text: str, path: Path, start_anchor: str, end_anchor: str | None = None
) -> str:
    """Slice `text` from `start_anchor` up to `end_anchor`, or to the end of
    `text` when `end_anchor` is None — for a section that is the last one in
    its file, so there is no next heading to bound it against.

    Asserts `start_anchor` is present (and, when given, that `end_anchor`
    follows it) first, naming `path` and the missing anchor, so a drifted
    heading fails loudly instead of raising a bare `ValueError: substring
    not found`.
    """
    assert start_anchor in text, (
        f"{path}: expected section anchor {start_anchor!r} — not found."
    )
    start = text.index(start_anchor)
    if end_anchor is None:
        return text[start:]
    assert end_anchor in text[start:], (
        f"{path}: expected section anchor {end_anchor!r} after "
        f"{start_anchor!r} — not found."
    )
    end = text.index(end_anchor, start)
    return text[start:end]


def test_step_2_9_runs_devon_once() -> None:
    # "\n### " (not a literal next-heading title) bounds the section at
    # whatever heading follows 2.9, without hardcoding its number.
    step_2_9 = _section(_SKILL_TEXT, _SKILL_MD, "### 2.9", "\n### ")
    assert "runs once per task" in step_2_9, (
        f"{_SKILL_MD}: expected step 2.9 to say 'runs once per task' — "
        "not found. The single-round Devon cap appears to have drifted "
        "or been removed."
    )

    # Whole-file on purpose: an absence assertion scoped to 2.9 would
    # let this wording reappear elsewhere in the file and still pass.
    for needle in ("re-run Devon", "second Devon dispatch"):
        assert needle not in _SKILL_TEXT, (
            f"{_SKILL_MD}: found {needle!r} — the second Devon round "
            "appears to still be documented."
        )

    assert "round exhausted" not in _SKILL_TEXT, (
        f"{_SKILL_MD}: found 'round exhausted' — step 2.9's prose gate "
        "still promises a second-round ceiling that no longer exists "
        "now that Devon runs at most once per task."
    )


def test_outcomes_table_has_no_re_check_row() -> None:
    for needle in ("re-run Devon", "1 round exhausted"):
        assert needle not in _ADVERSARIAL_TEXT, (
            f"{_ADVERSARIAL_TEST_PROMPT}: found {needle!r} — the old "
            "two-round outcome row appears to still be documented."
        )


def test_attempt_logging_lists_exploit_fixed() -> None:
    assert '"exploit_fixed"' in _ATTEMPT_LOGGING_TEXT, (
        f"{_ATTEMPT_LOGGING}: expected the `devon` attempt field to "
        "list \"exploit_fixed\" as a value — not found."
    )


def test_devon_lists_every_weak_point() -> None:
    for needle in (
        "show every other weak point",
        "a numbered `Weak points:` list",
    ):
        assert needle in _ADVERSARIAL_TEXT, (
            f"{_ADVERSARIAL_TEST_PROMPT}: expected {needle!r} — not "
            "found. Devon's every-weak-point instruction appears to "
            "have drifted or been removed."
        )

    # Whole-file: the old single-exploit instruction must be gone
    # everywhere, not just out of whatever section replaced it.
    assert "Report the exploit." not in _ADVERSARIAL_TEXT, (
        f"{_ADVERSARIAL_TEST_PROMPT}: found 'Report the exploit.' — "
        "the old single-exploit instruction appears to still be "
        "documented."
    )


def test_tess_answers_each_weak_point() -> None:
    # Scoped to the Feedback to Tess section itself (the file's last
    # section, no heading follows it): the Outcomes table row also
    # mentions "in-contract:" in passing, so a whole-file check here
    # would still pass if this wording moved out of Feedback to Tess
    # entirely, as long as it landed anywhere else in the file.
    feedback_section = _section(
        _ADVERSARIAL_TEXT,
        _ADVERSARIAL_TEST_PROMPT,
        "## Feedback to Tess (when Devon succeeds)",
    )
    for needle in (
        "Address every numbered weak point",
        "strengthened:",
        "in-contract:",
    ):
        assert needle in feedback_section, (
            f"{_ADVERSARIAL_TEST_PROMPT}: expected {needle!r} in the "
            "'## Feedback to Tess (when Devon succeeds)' section — not "
            "found there (even if present elsewhere in the file, such "
            "as the Outcomes table). The per-weak-point feedback "
            "wording appears to have moved out of that section or "
            "drifted."
        )


def test_feedback_to_tess_drops_weak_points_placeholder() -> None:
    needle = "{Devon's explanation of which tests are weak}"
    assert needle not in _ADVERSARIAL_TEXT, (
        f"{_ADVERSARIAL_TEST_PROMPT}: found {needle!r} in the Feedback "
        "to Tess template — Devon's actual numbered `Weak points:` list "
        "must be what the template says gets passed to Tess, not a "
        "paraphrased placeholder."
    )


def test_orchestrator_never_dismisses_a_weak_point() -> None:
    needle = "the orchestrator never dismisses one itself"
    assert needle in _ADVERSARIAL_TEXT, (
        f"{_ADVERSARIAL_TEST_PROMPT}: expected {needle!r} in the "
        "outcomes row about unresolved weak points — not found."
    )


def test_correction_retry_does_not_contradict_tess_budget() -> None:
    # The Outcomes row and step 2.8's Total Tess budget line must agree on
    # how many dispatches a weak-point correction costs: either the budget
    # line explicitly folds the correction retry into the one adversarial-
    # strengthen dispatch, or the Outcomes row drops the "correction retry"
    # phrase in favor of language that doesn't imply a second dispatch.
    outcomes_row = _section(
        _ADVERSARIAL_TEXT,
        _ADVERSARIAL_TEST_PROMPT,
        "## Procedure",
        "## Context Selection",
    )
    step_2_8 = _section(_SKILL_TEXT, _SKILL_MD, "### 2.8.", "### 2.85.")
    if "correction retry" in outcomes_row:
        assert "correction" in step_2_8, (
            f"{_SKILL_MD} and {_ADVERSARIAL_TEST_PROMPT}: the Outcomes "
            "row still promises a 'correction retry' but step 2.8's "
            "Total Tess budget line never accounts for it as part of "
            "the one adversarial-strengthen dispatch — the two "
            "contradict on how many dispatches a weak-point correction "
            "costs."
        )


def test_attempt_logging_lists_weak_point_fields() -> None:
    for needle in ("devon_weak_points", "devon_in_contract"):
        assert needle in _ATTEMPT_LOGGING_TEXT, (
            f"{_ATTEMPT_LOGGING}: expected {needle!r} — not found. The "
            "new weak-point attempt-record field appears to be missing "
            "from attempt-logging.md."
        )
        assert needle in _STATE_SCHEMA_TEXT, (
            f"{_STATE_SCHEMA}: expected {needle!r} — not found. The new "
            "weak-point attempt-record field appears to be missing from "
            "state-schema.md."
        )


def test_attempt_logging_lists_devon_exploit_field() -> None:
    for path, text in (
        (_ATTEMPT_LOGGING, _ATTEMPT_LOGGING_TEXT),
        (_STATE_SCHEMA, _STATE_SCHEMA_TEXT),
    ):
        assert "devon_exploit" in text, (
            f"{path}: expected 'devon_exploit' — not found. The "
            "Outcomes table's devon_exploit attempt-record field "
            "appears to be undocumented."
        )


def test_attempt_logging_devon_mirror_not_pending() -> None:
    needle = "integrator hand-off"
    assert needle not in _ATTEMPT_LOGGING_TEXT, (
        f"{_ATTEMPT_LOGGING}: found {needle!r} — the state-schema.md "
        "mirror already documents devon/devon_weak_points/"
        "devon_in_contract, so the devon field bullet should not call "
        "it a pending hand-off."
    )


def test_changelog_unreleased_has_one_changed_heading() -> None:
    unreleased = _section(_CHANGELOG_TEXT, _CHANGELOG, "## [Unreleased]", "\n## [")
    count = unreleased.count("### Changed")
    assert count <= 1, (
        f"{_CHANGELOG}: expected at most one '### Changed' heading in "
        f"the [Unreleased] section — found {count}. Merge every "
        "'### Changed' bullet list into a single heading."
    )
