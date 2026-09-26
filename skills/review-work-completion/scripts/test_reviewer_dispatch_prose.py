"""Pin the reviewer dispatch shape that keeps the CLI lanes alive.

An Agent call dispatched with `run_in_background: false` makes the harness
hold the background Bash calls in the same message until that Agent returns;
the Watcher only returns once those Bash lanes have written their outputs, so
a single `false` idles the cycle for the Watcher's whole budget. Seen twice on
2026-09-26 (52 min each). The skill must say `true`, in words a session cannot
read as optional.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SKILL = (ROOT / "skills/review-work-completion/SKILL.md").read_text(encoding="utf-8")


def step(number: int) -> str:
    return SKILL.split(f"### {number}. ", 1)[1].split("\n### ", 1)[0]


def _paragraph(text: str, opener: str) -> str:
    body = text.split(opener, 1)[1].split("\n\n", 1)[0]
    return " ".join((opener + body).split())


def test_reviewer_agents_are_dispatched_in_the_background() -> None:
    launch = _paragraph(step(5), "**Launch ALL active reviewers in a SINGLE message")
    assert "Alice, Blake, and Eve (when active)" in launch
    assert "`run_in_background: true`" in launch
    assert "never `false`" in launch
    assert "hold the background Bash calls" in launch


def test_watcher_is_dispatched_in_the_background() -> None:
    watcher = _paragraph(step(5), "**Watcher (headless keep-alive")
    assert "general-purpose, `run_in_background: true`" in watcher
