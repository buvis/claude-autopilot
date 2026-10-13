"""Pin that SKILL.md step 6 composes the `Tests:` line from gate.tests_line,
with no sha/counts reuse rule."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SKILL = (ROOT / "skills/review-work-completion/SKILL.md").read_text(encoding="utf-8")


def step(number: int) -> str:
    return SKILL.split(f"### {number}. ", 1)[1].split("\n### ", 1)[0]


def _tests_line_slice() -> str:
    marker = "**Compose the `Tests:` line.**"
    after_marker = step(6).split(marker, 1)[1]
    next_heading = re.search(r"\n\*\*[^*\n]+\.\*\*", after_marker)
    return after_marker[: next_heading.start()] if next_heading else after_marker


def test_step_6_composes_from_gate_tests_line() -> None:
    slice_ = _tests_line_slice()
    assert "gate.tests_line" in slice_ or "## Test gate" in slice_


def test_step_6_has_no_sha_counts_reuse_rule() -> None:
    slice_ = _tests_line_slice()
    assert not re.search(r"sha\b.{0,40}(==|equals|matches).{0,40}HEAD", slice_, re.IGNORECASE)
