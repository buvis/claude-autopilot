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
    for needle in ("foreground Bash call", "never with `run_in_background`", "`Monitor`"):
        assert needle in dispatch, (
            f"{_PER_TASK_REVIEW}: § Dispatch lacks {needle!r}, so nothing stops "
            "the orchestrator from backgrounding Pat and ending the turn."
        )
