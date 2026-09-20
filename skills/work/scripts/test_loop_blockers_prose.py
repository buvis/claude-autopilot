"""Pins the two loop-blocker prose fixes landed by hand on 2026-09-20
(inefficiencies note findings 15 and 16): Pat runs in the foreground, and
Devon skips prose-pin tasks.

Same pattern as test_dispatch_prose.py: read each file once, assert on short,
reword-resistant substrings, each with a failure message naming what drifted.
Run by dev/bin/release-checks (`[checks] loop blockers prose`).
"""

from __future__ import annotations

from pathlib import Path

_WORK_DIR = Path(__file__).resolve().parent.parent
_WORK_SKILL = _WORK_DIR / "SKILL.md"
_PER_TASK_REVIEW = _WORK_DIR / "references" / "per-task-review.md"


def _section(text: str, path: Path, start: str, end: str) -> str:
    assert start in text, f"{path}: no {start!r} heading - renamed or removed?"
    i = text.index(start)
    assert end in text[i:], f"{path}: no {end!r} heading after {start!r}"
    return text[i : text.index(end, i)]


def test_pat_dispatch_is_foreground_never_backgrounded() -> None:
    # A headless session that ends its turn with a background Bash still
    # running is torn down with it: `[killed]` in the output file, Pat's row
    # `lost`, and a relaunch that re-runs him (2026-09-14, 00191 T1 and
    # agent-skills 00052 T2, one session lost each).
    dispatch = _section(
        _PER_TASK_REVIEW.read_text(), _PER_TASK_REVIEW, "## Dispatch", "## Delta re-runs"
    )
    # `600000` is pinned too: the Bash tool's maximum, and the parked patch
    # said 900000, which the tool rejects.
    for needle in (
        "foreground Bash call",
        "never with `run_in_background`",
        "`Monitor`",
        "600000",
    ):
        assert needle in dispatch, (
            f"{_PER_TASK_REVIEW}: § Dispatch lacks {needle!r}, so nothing stops "
            "the orchestrator from backgrounding Pat and ending the turn."
        )


def test_devon_skips_prose_pin_tasks() -> None:
    # A substring pin cannot see negation, inversion or past-tense narration,
    # so every Devon round on a prose-pin task ends `round exhausted` at that
    # ceiling (four of four on 2026-09-14/15, about 55 minutes of Opus time,
    # nothing kept). Devon is step 2.9 since PRD 00202.
    step_2_9 = _section(_WORK_SKILL.read_text(), _WORK_SKILL, "### 2.9.", "### 2.95.")
    for needle in ("ends in `_prose.py`", "skip Devon", "devon: skipped:prose"):
        assert needle in step_2_9, (
            f"{_WORK_SKILL}: step 2.9 lacks {needle!r}, so a prose-pin task "
            "still pays for a Devon round that cannot keep anything."
        )
    schema = (_WORK_DIR / "references" / "attempt-logging.md").read_text()
    assert '"devon": "skipped:prose"' in schema, (
        "references/attempt-logging.md does not define the `devon` attempt "
        "field, so step 2.9 writes a stamp the schema never names."
    )
