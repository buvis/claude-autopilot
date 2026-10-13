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
    assert "gate.tests_line" in slice_, "slice lost the gate.tests_line source"
    assert "## Test gate" in slice_, "slice lost the `## Test gate` section source"


def test_step_6_copies_the_counts_line_verbatim() -> None:
    assert "verbatim" in _tests_line_slice(), "verbatim-copy instruction missing"


def test_step_6_guards_the_copy_with_a_counts_line_check() -> None:
    slice_ = _tests_line_slice()
    assert "counts line" in slice_, "counts-line guard missing"
    assert "TESTS_RE" in slice_, "TESTS_RE match requirement missing"


def test_step_6_falls_back_to_autopilot_verify_for_non_counts_lines() -> None:
    assert "autopilot verify" in _tests_line_slice(), "autopilot verify fallback missing"


REUSE_RULE_PATTERNS = [
    r"sha\b.{0,40}(==|equals|matches).{0,40}HEAD",
    r"sha\b.{0,40}\bis\b.{0,40}\bHEAD\b",
    r"\bHEAD\b.{0,40}(==|equals|matches|is).{0,40}sha\b",
    r"counts?\b.{0,40}non-?null",
    r"non-?null.{0,40}counts?\b",
    r"three counts",
]


def test_step_6_has_no_sha_counts_reuse_rule() -> None:
    slice_ = _tests_line_slice()
    for pattern in REUSE_RULE_PATTERNS:
        assert not re.search(pattern, slice_, re.IGNORECASE | re.DOTALL), pattern
