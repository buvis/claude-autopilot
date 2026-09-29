"""Tests binding the live text of the single-Devon-round prose — cutting the
second Devon dispatch and documenting the new `exploit_fixed` attempt value
plus the `devon_weak_points` / `devon_in_contract` attempt-record fields.

Mirrors test_adversarial_cap_prose.py's pattern: resolve each target file's
path relative to this file, read it once at module level, and assert on
short, reword-resistant substrings, each with a failure message naming what
drifted. Presence assertions are scoped to the section that is supposed to
carry them via `_section`, so the pin still catches text that has moved out
of its section rather than only text that has vanished outright. Absence
assertions stay whole-file on purpose: scoping an absence check to one
section would let the old wording reappear anywhere else in the file and
still pass.
"""

from __future__ import annotations

from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
_WORK_DIR = _SCRIPTS_DIR.parent
_SKILLS_DIR = _WORK_DIR.parent

_SKILL_MD = _WORK_DIR / "SKILL.md"
_SKILL_TEXT = _SKILL_MD.read_text()

_ADVERSARIAL_TEST_PROMPT = _WORK_DIR / "references" / "adversarial-test-prompt.md"
_ADVERSARIAL_TEXT = _ADVERSARIAL_TEST_PROMPT.read_text()

_ATTEMPT_LOGGING = _WORK_DIR / "references" / "attempt-logging.md"
_ATTEMPT_LOGGING_TEXT = _ATTEMPT_LOGGING.read_text()

_STATE_SCHEMA = _SKILLS_DIR / "run-autopilot" / "references" / "state-schema.md"
_STATE_SCHEMA_TEXT = _STATE_SCHEMA.read_text()


def _section(text: str, path: Path, start_anchor: str, end_anchor: str) -> str:
    """Slice `text` from `start_anchor` up to `end_anchor`.

    Asserts both anchors are present first, naming `path` and the missing
    anchor, so a drifted heading fails loudly instead of raising a bare
    `ValueError: substring not found`.
    """
    assert start_anchor in text, (
        f"{path}: expected section anchor {start_anchor!r} — not found."
    )
    start = text.index(start_anchor)
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
    for needle in (
        "Address every numbered weak point",
        "strengthened:",
        "in-contract:",
    ):
        assert needle in _ADVERSARIAL_TEXT, (
            f"{_ADVERSARIAL_TEST_PROMPT}: expected {needle!r} in the "
            "Feedback to Tess section — not found. The per-weak-point "
            "feedback wording appears to have drifted or been removed."
        )

def test_orchestrator_never_dismisses_a_weak_point() -> None:
    needle = "the orchestrator never dismisses one itself"
    assert needle in _ADVERSARIAL_TEXT, (
        f"{_ADVERSARIAL_TEST_PROMPT}: expected {needle!r} in the "
        "outcomes row about unresolved weak points — not found."
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
