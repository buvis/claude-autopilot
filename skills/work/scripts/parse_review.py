#!/usr/bin/env python3
"""Validate and parse one per-task reviewer reply — /work step 5.7's contract gate.

The reviewer's contract is three line shapes: `SEVERITY | file:line | issue | fix`,
`CLOSURE | resolved|unresolved | finding | evidence`, and the single line
`NO FINDINGS`. Anything else on a line is prose and ignored.

A line that *claims* one of those shapes and gets it wrong is the case worth
catching: it reads as a finding to a human and as nothing to a parser, so it
silently drops a real defect. Such a line is invalid, and step 5.7 spends one
correction retry on it. A reply with no contract line at all is invalid for the
same reason.

Not to be confused with `review-work-completion/scripts/consolidate_findings.py`,
which parses the PRD-level `[AGENT] {emoji} ... | File: ... | Task: ...` shape.

Exit codes: 0 valid (JSON on stdout), 1 invalid (reason on stderr), 2 the file
is missing or empty (a runner failure, not a contract failure).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_SEVERITIES = ("CRITICAL", "HIGH", "MEDIUM", "LOW")
_CLOSURE_VERDICTS = ("resolved", "unresolved")
_NO_FINDINGS = "NO FINDINGS"
_SEPARATOR = " | "


class InvalidReview(ValueError):
    """A reply that breaks the reporting contract. `line` is empty when none does."""

    def __init__(self, reason: str, line: str = "") -> None:
        super().__init__(f"{reason}: {line}" if line else reason)
        self.reason = reason
        self.line = line


def _claimed_keyword(line: str) -> str | None:
    """The contract keyword a line claims, whatever it then does with it.

    Trailing punctuation is stripped so `MEDIUM: file.py:12 - issue` is caught as
    a botched finding rather than waved through as prose, while `Low-hanging
    fruit` stays prose — the strip only reaches the end of the first word.
    """
    first_word = line.split(maxsplit=1)[0].rstrip(":;,.-|").upper()
    if first_word in _SEVERITIES or first_word == "CLOSURE":
        return first_word
    return None


def parse(text: str) -> dict:
    """Parse a reviewer reply. Raises `InvalidReview` when it breaks the contract."""
    findings: list[dict[str, str]] = []
    closures: list[dict[str, str]] = []
    no_findings = False

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line == _NO_FINDINGS:
            no_findings = True
            continue
        keyword = _claimed_keyword(line)
        if keyword is None:
            continue
        fields = [field.strip() for field in line.split(_SEPARATOR, 3)]
        if len(fields) != 4:
            raise InvalidReview(f"{keyword} line needs four ' | ' fields", line)
        if keyword == "CLOSURE":
            if fields[1].lower() not in _CLOSURE_VERDICTS:
                raise InvalidReview(
                    "CLOSURE verdict must be resolved or unresolved",
                    line,
                )
            closures.append(
                {
                    "verdict": fields[1].lower(),
                    "finding": fields[2],
                    "evidence": fields[3],
                },
            )
            continue
        findings.append(
            {
                "severity": keyword,
                "file": fields[1],
                "issue": fields[2],
                "fix": fields[3],
            },
        )

    if no_findings and findings:
        raise InvalidReview("NO FINDINGS reported alongside a finding")
    if not (findings or closures or no_findings):
        raise InvalidReview("no finding, closure or NO FINDINGS line")
    return {"no_findings": no_findings, "findings": findings, "closures": closures}


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: parse_review.py <output-file>", file=sys.stderr)
        return 2
    path = Path(argv[1])
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        print(f"parse_review: cannot read {path}: {error}", file=sys.stderr)
        return 2
    if not text.strip():
        print(f"parse_review: {path} is empty", file=sys.stderr)
        return 2
    try:
        result = parse(text)
    except InvalidReview as error:
        print(f"parse_review: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
