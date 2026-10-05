#!/usr/bin/env python3
"""cli/gate.py - the review-file shape gate (PRD 00016, absorbed by PRD 00107).

Moved here from review-work-completion/scripts/check_review_file.py so the
deterministic review gate lives in the tested CLI codebase; that path remains
as a re-export shim because four skills and several suites name it. Wired as
`autopilot gate` in cli/__main__.py; also runnable directly
(`python3 cli/gate.py <flags>`) with the identical contract.

Validates exactly four things about a consolidated review file:

1. every launched reviewer has a non-empty section,
2. a parseable verdict line (`Verdict: converged` / `Verdict: N findings`),
3. a test-summary line (`Tests: N passed ...` / `Tests: none (docs-only)`),
4. a codex_rung_guard line — `codex_rung_guard: not fired`, plain
   `fired (N codex-implemented task(s))`, or that fired form suffixed
   `; eve unavailable, doubt lens fell back to claude` or
   `; constraint UNMET` — checked ONLY when --require-codex-guard is
   passed, and checked for CONSISTENCY as well as grammar: a well-formed
   line can still lie. `fired (0 ...)` is self-contradictory (the guard
   fires only when at least one task was codex-implemented), and plain
   `fired (N)` asserts a non-codex doubt reviewer covered the lens, which
   requires a non-empty eve section to back it. The two suffixed forms are
   exempt from that second rule: each already records why Eve did not run.

This gate checks several different kinds of review file (consolidated
reviews, blind reviews, shadow-run renders), and only the consolidated
review carries a codex_rung_guard line — so that check is opt-in, not
imposed on every caller.

No git, no subprocesses, no PRD parsing. A missing element exits 1 with a
one-line gap description on stderr. An unreadable file system exits 0 with a
loud stderr note — an infrastructure error must not masquerade as a coverage
gap (the old gate's DIFF_ERROR philosophy).

--assert-constraint-met is an opt-in semantic check on top of the shape
check above: when the codex_rung_guard line records `; constraint UNMET`
(the doubt lens ran on codex alone), exit 2 instead of the usual 0 — a
failure class distinct from a shape gap, so a caller can tell "malformed
file" (exit 1) apart from "constraint not certified" (exit 2). A shape gap
still wins when both are present: a file that fails the shape check cannot
be trusted for a constraint reading, so it exits 1, not 2. Without this
flag, `; constraint UNMET` remains a validly-shaped, exit-0 recorded form.

--findings <path> is a second opt-in check: every row of that chosen-findings
JSON array must be backed by a row of the review file's `## Consolidated
Findings` section (severity, file and issue, normalized), so a batch cannot
apply a finding no reviewer recorded. One direction only — the review may
carry rows the batch is not applying. A review file with no such section is
reported as a shape gap (exit 1), not a mismatch.

CLI: autopilot gate --review-file <path> [--reviewers alice,bob,...]
[--require-codex-guard] [--assert-constraint-met] [--findings <path>]
When --reviewers is omitted, the file's frontmatter `reviewers:` line (a
comma-separated list written by consolidation) is used; if neither names any
reviewer, only the verdict and tests lines are checked.

Exit codes (gate-scoped, unchanged from check_review_file.py):
    0  shape holds (or unreadable file — fail open, loud)
    1  shape gap (or missing review file, or an unusable --findings file, or
       no consolidated-findings section to check --findings against)
    2  --assert-constraint-met and the guard line records `; constraint UNMET`;
       or a --findings row the review file never recorded
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

VERDICT_RE = re.compile(r"^Verdict: (converged|\d+ findings?)\s*$", re.MULTILINE)
TESTS_RE = re.compile(
    r"^Tests: (\d+ passed.*|none \(docs-only\))\s*$",
    re.MULTILINE,
)
CODEX_RUNG_GUARD_RE = re.compile(
    r"^codex_rung_guard: ("
    r"fired \(\d+ codex-implemented task\(s\)\)"
    r"(; eve unavailable, doubt lens fell back to claude|; constraint UNMET)?"
    r"|not fired)\s*$",
    re.MULTILINE,
)
CONSTRAINT_UNMET_RE = re.compile(
    r"^codex_rung_guard: fired \(\d+ codex-implemented task\(s\)\); constraint UNMET\s*$",
    re.MULTILINE,
)
# Same fired branch as CODEX_RUNG_GUARD_RE, but capturing the count and the
# suffix so the consistency check below can read them. Only ever consulted
# AFTER the shape check has passed, so the line is already known well-formed.
FIRED_GUARD_RE = re.compile(
    r"^codex_rung_guard: fired \((\d+) codex-implemented task\(s\)\)"
    r"(; eve unavailable, doubt lens fell back to claude|; constraint UNMET)?\s*$",
    re.MULTILINE,
)
FRONTMATTER_REVIEWERS_RE = re.compile(r"^reviewers:\s*(.+)$", re.MULTILINE)
_FINDINGS_HEADING_RE = re.compile(r"^##\s+Consolidated Findings\s*$", re.MULTILINE)
_NEXT_H2_RE = re.compile(r"^##\s", re.MULTILINE)
# `- [2/3] 🟠 wrong default | src/b.py:10 | Found by: alice, bob`
_FINDING_ROW_RE = re.compile(r"^-\s*\[\d+/\d+\]\s*(.+)$", re.MULTILINE)
_SEVERITY_EMOJI = {
    "\U0001f534": "critical",
    "\U0001f7e0": "high",
    "\U0001f7e1": "medium",
    "⚪": "low",
}
_SEVERITY_WORDS = frozenset(_SEVERITY_EMOJI.values())
# verify/discard rows are never applied to state, so nothing of theirs has to
# be backed by a review row.
_APPLIED_CLASSIFICATIONS = ("fix", "defer")


def reviewer_section_nonempty(lines: list[str], name: str) -> bool:
    """True when a heading names the reviewer and its body has content."""
    needle = name.strip().lower()
    for i, line in enumerate(lines):
        if line.lstrip().startswith("#") and needle in line.lower():
            for follow in lines[i + 1 :]:
                if follow.lstrip().startswith("#"):
                    return False
                if follow.strip():
                    return True
            return False
    return False


def check(
    text: str,
    reviewers: list[str],
    require_codex_guard: bool = False,
) -> str | None:
    """Return a one-line gap description, or None when the shape holds."""
    lines = text.splitlines()
    for reviewer in reviewers:
        if not reviewer_section_nonempty(lines, reviewer):
            return f"reviewer section missing or empty: {reviewer}"
    if not VERDICT_RE.search(text):
        return (
            "no verdict line (expected 'Verdict: converged' or 'Verdict: N findings')"
        )
    if not TESTS_RE.search(text):
        return "no tests line (expected 'Tests: N passed ...' or 'Tests: none (docs-only)')"
    if require_codex_guard:
        if not CODEX_RUNG_GUARD_RE.search(text):
            return (
                "no codex_rung_guard line (expected 'codex_rung_guard: not fired', "
                "'codex_rung_guard: fired (N codex-implemented task(s))', or that "
                "fired form suffixed with '; eve unavailable, doubt lens fell back "
                "to claude' or '; constraint UNMET')"
            )
        gap = _guard_matches_roster(text, lines)
        if gap is not None:
            return gap
    return None


def _guard_matches_roster(text: str, lines: list[str]) -> str | None:
    """Check the guard's RECORD against the roster, not just its grammar.

    A well-formed line can still lie. Two ways it does:

    - `fired (0 ...)` is self-contradictory — the guard fires only when at
      least one task was codex-implemented.
    - plain `fired (N)` asserts a non-codex doubt reviewer covered the lens,
      which means Eve. If the file carries no Eve section, nothing backs that
      claim. The two documented suffixes are exempt: `; eve unavailable ...`
      self-documents her absence (Bob's Claude fallback covered doubt), and
      `; constraint UNMET` already records the constraint as not certified.
    """
    fired = FIRED_GUARD_RE.search(text)
    if fired is None:  # `not fired` — nothing to cross-check
        return None
    if int(fired.group(1)) == 0:
        return (
            "codex_rung_guard records 'fired (0 codex-implemented task(s))', which "
            "is self-contradictory: the guard fires only when at least one task "
            "was codex-implemented"
        )
    if fired.group(2) is None and not reviewer_section_nonempty(lines, "eve"):
        return (
            "codex_rung_guard records a plain 'fired (N codex-implemented "
            "task(s))', which claims a non-codex doubt reviewer covered the lens, "
            "but the file carries no non-empty eve section; use the "
            "'; eve unavailable, doubt lens fell back to claude' or "
            "'; constraint UNMET' form when Eve did not run"
        )
    return None


def _split_severity_cell(cell: str) -> tuple[str, str]:
    """(severity word, remaining text) for a cell written `🟠`, `high`,
    `🟠 wrong default` or `🟠 High wrong default`."""
    rest = cell.strip()
    severity = ""
    if rest[:1] in _SEVERITY_EMOJI:
        severity, rest = _SEVERITY_EMOJI[rest[:1]], rest[1:].strip()
    word, _, tail = rest.partition(" ")
    if word.lower() in _SEVERITY_WORDS:
        severity, rest = severity or word.lower(), tail
    return severity, rest


def _finding_key(severity: str, file: str, issue: str) -> tuple[str, str, str]:
    """The comparison tuple: severity as a word, file as written, issue with
    its whitespace collapsed and its case folded away."""
    return (
        _split_severity_cell(severity)[0],
        file.strip(),
        " ".join(issue.split()).lower(),
    )


def _reviewed_keys(text: str) -> set[tuple[str, str, str]] | None:
    """Every row of the `## Consolidated Findings` section, or None when the
    review file carries no such section."""
    heading = _FINDINGS_HEADING_RE.search(text)
    if heading is None:
        return None
    section = text[heading.end() :]
    following = _NEXT_H2_RE.search(section)
    if following is not None:
        section = section[: following.start()]
    keys = set()
    for row in _FINDING_ROW_RE.findall(section):
        cells = [c.strip() for c in row.split("|")]
        severity, issue = _split_severity_cell(cells[0])
        keys.add(_finding_key(severity, cells[1] if len(cells) > 1 else "", issue))
    return keys


def _cross_check_findings(
    text: str,
    findings: list[dict],
) -> tuple[str, str | None]:
    """Check every chosen finding against the review file's consolidated rows.

    One direction only: a review row the batch is not applying is fine, a
    chosen row the review never recorded is not. Returns ("ok", None),
    ("mismatch", <the first unbacked row>) or ("malformed", <why>) when the
    review file has no consolidated-findings section to check against.
    """
    reviewed = _reviewed_keys(text)
    if reviewed is None:
        return "malformed", "no '## Consolidated Findings' section in the review file"
    for row in findings:
        if row.get("classification") not in _APPLIED_CLASSIFICATIONS:
            continue
        severity = str(row.get("severity", ""))
        file = str(row.get("file", ""))
        issue = str(row.get("issue", ""))
        if _finding_key(severity, file, issue) not in reviewed:
            return "mismatch", (
                "chosen finding absent from the review file's consolidated "
                f"findings: {severity} {file} | {issue}"
            )
    return "ok", None


def _load_findings(path: Path) -> tuple[list[dict] | None, str | None]:
    """(rows, None) for a JSON array of objects, else (None, one-line error)."""
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        return None, f"cannot read findings file {path} ({exc})"
    except ValueError as exc:
        return None, f"cannot parse findings file {path} ({exc})"
    if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
        return None, f"findings file {path} is not a JSON array of objects"
    return rows, None


def _findings_exit(text: str, findings_file: Path) -> int:
    """The exit code --findings contributes: 0 when every chosen row is backed
    by a review row, 2 on a mismatch, 1 on an unusable findings file or a
    review file with no consolidated-findings section to check against."""
    rows, error = _load_findings(findings_file)
    if rows is None:
        sys.stderr.write(f"{error}\n")
        return 1
    tag, detail = _cross_check_findings(text, rows)
    if tag == "ok":
        return 0
    sys.stderr.write(f"{detail}\n")
    return 2 if tag == "mismatch" else 1


def run_gate(
    review_file: Path,
    reviewers: str | None = None,
    require_codex_guard: bool = False,
    assert_constraint_met: bool = False,
    findings_file: Path | None = None,
) -> int:
    """The full gate flow behind both entry points (`autopilot gate` and the
    direct script/shim invocation): read, resolve reviewers, check, exit code."""
    if not review_file.exists():
        sys.stderr.write(f"missing review file {review_file}\n")
        return 1
    try:
        text = review_file.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        # Fail open: infra error, not a coverage gap. Loud, never silent.
        sys.stderr.write(
            f"check_review_file: cannot read {review_file} ({exc}); "
            "allowing hand-off (infrastructure error, not a coverage gap)\n",
        )
        return 0

    if reviewers is not None:
        reviewer_list = [r for r in reviewers.split(",") if r.strip()]
    else:
        match = FRONTMATTER_REVIEWERS_RE.search(text)
        reviewer_list = (
            [r for r in match.group(1).split(",") if r.strip()] if match else []
        )

    gap = check(text, reviewer_list, require_codex_guard)
    if gap is not None:
        sys.stderr.write(gap + "\n")
        return 1

    # After the shape check, never before: a file that fails the shape check
    # cannot be trusted for a findings reading either.
    if findings_file is not None:
        rc = _findings_exit(text, findings_file)
        if rc != 0:
            return rc

    if assert_constraint_met and CONSTRAINT_UNMET_RE.search(text):
        sys.stderr.write(
            "codex_rung_guard: constraint UNMET; doubt-roster constraint not certified\n",
        )
        return 2
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-file", type=Path, required=True)
    parser.add_argument("--reviewers", default=None)
    parser.add_argument("--require-codex-guard", action="store_true", default=False)
    parser.add_argument("--assert-constraint-met", action="store_true", default=False)
    parser.add_argument("--findings", type=Path, default=None)
    args = parser.parse_args()
    return run_gate(
        args.review_file,
        args.reviewers,
        args.require_codex_guard,
        args.assert_constraint_met,
        args.findings,
    )


if __name__ == "__main__":
    sys.exit(main())
