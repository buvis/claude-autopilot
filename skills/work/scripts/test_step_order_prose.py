"""Pins PRD 00202: Tess's tests are committed as soon as they pass the 2.8
quality gate, before Devon (2.85 commit, 2.9 Devon, 2.95 red-check), the
strengthened tests are committed again before Devon's second dispatch, and a
fresh session resumes from a `wip - rotated mid-task` commit instead of
re-dispatching Tess.

Same pattern as test_dispatch_prose.py: read each file once, assert on short,
reword-resistant substrings, each with a failure message naming what drifted.
Run by dev/bin/release-checks (`[checks] loop blockers prose`).
"""

from __future__ import annotations

from pathlib import Path

_WORK_DIR = Path(__file__).resolve().parent.parent
_SKILL_MD = _WORK_DIR / "SKILL.md"
_ADVERSARIAL = _WORK_DIR / "references" / "adversarial-test-prompt.md"

_COMMIT_HEADING = "### 2.85. Commit tests"
_DEVON_HEADING = "### 2.9. Adversarial validation"
_STRENGTHEN_SENTENCE = (
    "Commit the strengthened tests as test(<scope>): strengthen <feature> "
    "before the second Devon dispatch."
)


def _section(text: str, path: Path, start: str, end: str) -> str:
    assert start in text, f"{path}: no {start!r} heading - renumbered or removed?"
    i = text.index(start)
    assert end in text[i:], f"{path}: no {end!r} heading after {start!r}"
    return text[i : text.index(end, i)]


def test_tests_commit_before_devon() -> None:
    # The whole point: the quality-gated tests must not sit uncommitted
    # through the longest dispatches of a task (a rotation mid-Devon lost a
    # 603-line test file; a rotation after a committed file re-ran Tess).
    text = _SKILL_MD.read_text()
    commit_step = _section(text, _SKILL_MD, _COMMIT_HEADING, _DEVON_HEADING)
    assert 'git commit -m "test(' in commit_step, (
        f'{_SKILL_MD}: the `git commit -m "test(` block is not between the '
        "2.85 commit heading and the 2.9 Devon heading, so the tests are not "
        "committed before Devon runs."
    )
    devon_step = _section(text, _SKILL_MD, _DEVON_HEADING, "### 2.95.")
    assert "proceed to step 2.95" in devon_step, (
        f"{_SKILL_MD}: the Devon tier gate's skip row no longer routes to "
        "step 2.95 (the red-check), the step that follows him now."
    )
    assert "Devon (step 2.85)" not in text and "Devon at 2.85" not in text, (
        f"{_SKILL_MD}: a cross-reference still places Devon at step 2.85."
    )
    red_check = (_WORK_DIR / "references" / "red-check.md").read_text()
    assert "per step 2.9," not in red_check and "per step 2.85" in red_check, (
        "references/red-check.md still sends the strengthen path to step 2.9 "
        "(Devon) to re-capture <test_commit_sha>; the capture is step 2.85."
    )


def test_strengthened_tests_are_committed_before_devon_round_two() -> None:
    # Without this, the strengthen round's tests sit uncommitted through the
    # second Devon dispatch, which is exactly the window the reorder closed.
    text = _SKILL_MD.read_text()
    devon_step = _section(text, _SKILL_MD, _DEVON_HEADING, "### 2.95.")
    assert _STRENGTHEN_SENTENCE in devon_step, (
        f"{_SKILL_MD}: step 2.9 lacks the sentence {_STRENGTHEN_SENTENCE!r}."
    )
    commit_step = _section(text, _SKILL_MD, _COMMIT_HEADING, _DEVON_HEADING)
    assert "the last test commit" in commit_step, (
        f"{_SKILL_MD}: step 2.85 no longer says <test_commit_sha> is the last "
        "test commit, so an ESCALATE reset after a strengthen round would "
        "throw the strengthened tests away."
    )
    outcomes = _section(
        _ADVERSARIAL.read_text(),
        _ADVERSARIAL,
        "**Outcomes:**",
        "## Prompt Template",
    )
    for needle in (
        "strengthen <feature>",
        "step 2.85",
        "before the second Devon dispatch",
    ):
        assert needle in outcomes, (
            f"{_ADVERSARIAL}: the outcome table lacks {needle!r}, so the "
            "strengthen round never commits before Devon's re-check."
        )


def test_step_2_resumes_from_a_wip_commit() -> None:
    # The rotation envelope commits dirty allowlisted files as
    # `chore(<scope>): wip - rotated mid-task`; without this step-2 read the
    # next session re-dispatches Tess with the identical prompt (33 minutes
    # duplicated on 2026-09-13, task 13).
    text = _SKILL_MD.read_text()
    step_2 = _section(text, _SKILL_MD, "### 2. Claim and start task", "### 2.5.")
    # Both anchors are re-derived on a resume (00202 review 1, Bob): item 1's
    # HEAD is the wip commit itself, so without this the pre-rotation half of
    # the task is outside every per-task gate and step 5.5 has no test SHA.
    for needle in (
        "git log -1 --format=%s",
        'ends in "wip - rotated mid-task"',
        "continue at the step it names instead of dispatching Tess",
        "continues at step 2.9",
        "parent of the earliest",
        "newest `test(` commit",
        "stopping at the first commit that is not this task's",
    ):
        assert needle in step_2, (
            f"{_SKILL_MD}: step 2 lacks {needle!r}, so a session after a "
            "rotation cannot resume from the wip commit."
        )
