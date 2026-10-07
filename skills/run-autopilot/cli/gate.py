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
Findings` section, so a batch cannot apply a finding no reviewer recorded.
That section is read in both shapes it is written in: the bullet list and the
pipe table `| Ref | Consensus | Severity | Issue | File | Task | Found By |`.
A chosen row carrying a `"ref"` is backed by the review row holding that exact
ref, severity and file; a row carrying none falls back to an exact (severity,
file, normalized issue) match. Coverage runs the other way too: every review row
needs a findings row naming its ref. A review file with no such section is a
shape gap (exit 1); one whose findings table cannot be read, or whose rows carry
no ref for a findings row to name, is a refusal (exit 2): the gate cannot say a
batch covers rows it was unable to read.

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
       or a --findings row the review file never recorded; or a findings section
       the gate could not read or could not check coverage against
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import NamedTuple

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
# `| [2/3] | 🟠 | wrong default | src/b.py:10 | 4 | alice, bob |` and the
# Ref-bearing form `| R2 | [2/3] | 🟠 | ... |`. Public, no leading underscore,
# because convergence.py counts severities with it: the optional leading cell
# is what keeps every row of every existing review file matching once the Ref
# column lands.
TABLE_DATA_ROW_RE = re.compile(r"^\|(?:\s*R\d+\s*\|)?\s*\[\d+/\d+\]\s*\|", re.MULTILINE)
# Row-shape detection inside a findings table, private on purpose: once the
# header is found, every pipe line that is not the |---| rule is a data row, so
# an off-shape cell is refused instead of silently dropping the row (and the
# finding it carried).
_CANDIDATE_ROW_RE = re.compile(r"^\|")
_SEPARATOR_ROW_RE = re.compile(r"^\|(\s*:?-{3,}:?\s*\|)+\s*$")
_REF_CELL_RE = re.compile(r"^R\d+$", re.IGNORECASE)
_CONSENSUS_CELL_RE = re.compile(r"^\[\d+/\d+\]$")
# `| Consensus | Severity | Issue | File | Task | Found By |`
_TABLE_HEADER_RE = re.compile(r"^\|(.+)\|\s*$", re.MULTILINE)
# The three columns a findings table must name; a header missing any of them
# contributes no keys.
_TABLE_COLUMNS = ("severity", "issue", "file")
_SEVERITY_EMOJI = {
    "\U0001f534": "critical",
    "\U0001f7e0": "high",
    "\U0001f7e1": "medium",
    "⚪": "low",
}
_SEVERITY_WORDS = frozenset(_SEVERITY_EMOJI.values())
# What `_reviewed_keys` could not read, as the operator has to hear it. The two
# must stay distinct: "the section is missing" and "the section is there and its
# table is what failed" are different repairs.
_FINDINGS_PROBLEMS = {
    "no-section": "no '## Consolidated Findings' section in the review file",
    "unreadable-table": (
        "found a findings table whose header or rows could not be read: "
        "expected a header naming Severity, Issue and File, and rows shaped "
        "| [m/n] | ... | (optionally led by a | R1 | ref cell)"
    ),
    "ref-required": (
        "coverage requires a Ref column; this section has at least one row "
        "with none - R1 R2 ... are keys the gate normalizes case-insensitively "
        "from the pipe table's Ref column"
    ),
}
# verify/discard rows are never applied to state, so nothing of theirs has to
# be backed by a review row. Only those two classifications are exempt: a row
# with a missing or unknown classification is checked like any applied row, and
# so is a `carry` row - a re-queued finding still names a real review row.
_SKIPPED_CLASSIFICATIONS = ("verify", "discard")
KNOWN_CLASSIFICATIONS = ("verify", "discard", "fix", "defer", "carry")


def known_classification(value: object) -> bool:
    """True for exactly the five dispositions, spelled exactly."""
    return isinstance(value, str) and value in KNOWN_CLASSIFICATIONS


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


def _normalize_issue(issue: str) -> str:
    """Issue text as both sides of the cross-check compare it, bar the case:
    escaped pipes collapsed (a row quoting a table carries `\\|`), a leading
    severity word dropped, whitespace squeezed."""
    return " ".join(_split_severity_cell(issue.replace("\\|", "|"))[1].split())


def _finding_key(severity: str, file: str, issue: str) -> tuple[str, str, str]:
    """Both sides of the cross-check run the issue through the same split, so
    an issue that begins with a severity word (`High coupling ...`) keys the
    same whether that word was written in the severity cell or the text. Escape
    collapsing lives here for the same reason: a row copied verbatim out of a
    table cell carries `\\|` where the hand-written one carries `|`."""
    return (
        _split_severity_cell(severity)[0],
        file.replace("\\|", "|").strip(),
        _normalize_issue(issue).lower(),
    )


class Row(NamedTuple):
    """One consolidated-findings row, from either shape the section is written
    in. `ref` is "" for a bullet row or a table carrying no Ref column."""

    ref: str
    severity: str
    file: str
    issue: str


def _table_cells(line: str) -> list[str]:
    """A pipe row's cells, deliberately UNSTRIPPED: stripping here would delete
    the space that followed an embedded `\\|`, and no later escape collapse
    restores it. The caller strips once it knows which cell is which."""
    return line.strip().strip("|").split("|")


def _row_from_table(header: list[str], cells: list[str]) -> Row | None:
    """The row's (ref, severity, file, issue), or None when it is truncated.

    `| [2/4] |` matches the data-row shape yet splits to a single cell, so a
    header naming Severity at index 1 cannot be read off it. Such a row is
    unreadable, not empty: indexing it would raise, and the gate owes the
    caller `malformed`, never a traceback.

    The Ref and Consensus cells are checked before anything is built: a ref must
    be a single `R<digits>` (read case-insensitively, kept upper case) and a
    consensus must be a bracketed `[m/n]`. A trailing dot, a second ref in the
    same cell, an empty cell or an unbracketed `2/2` makes the row unreadable
    too - dropping it quietly would hide the finding it carried.
    """
    sev_i = header.index("severity")
    issue_i = header.index("issue")
    file_i = header.index("file")
    ref_i = header.index("ref") if "ref" in header else 0
    consensus_i = header.index("consensus") if "consensus" in header else 0
    if len(cells) <= max(sev_i, issue_i, file_i, ref_i, consensus_i):
        return None
    ref = ""
    if "ref" in header:
        matched = _REF_CELL_RE.match(cells[ref_i].strip())
        if matched is None:
            return None
        ref = matched.group(0).upper()
    if "consensus" in header and not _CONSENSUS_CELL_RE.match(
        cells[consensus_i].strip(),
    ):
        return None
    if len(cells) == len(header):
        issue, file = cells[issue_i], cells[file_i]
    else:
        # The issue cell absorbed one or more `|`. Rejoin the Issue..File span
        # BEFORE stripping - that is what puts a halved `\|` back together with
        # its whitespace intact - then take the file off its right end.
        trailing = len(header) - 1 - file_i
        span = "|".join(cells[issue_i : len(cells) - trailing]).strip()
        issue, _, file = span.rpartition("|")
    severity, file, _ = _finding_key(cells[sev_i], file, issue)
    return Row(ref, severity, file, _normalize_issue(issue))


def _table_keys(section: str) -> tuple[list[Row], str | None]:
    """Rows of the pipe-table form of the consolidated-findings section.

    The header row names the columns, so the documented 5-column shape
    (Consensus, Severity, Issue, File, Found By), the 6-column shape this
    repo's `consolidate_findings.py` emits (… Issue, File, Task, Found By) and
    the Ref-bearing form of either are all read without guessing positions. An
    issue cell may itself contain an unescaped `|` — `consolidate_findings.py`
    does not escape it — so the Issue and File cells are split from the RIGHT
    out of the span between them, exactly as the bullet branch already does. A
    data row too short to reach those columns makes the whole table unreadable:
    dropping it quietly would hand the caller a short row list and a clean
    `None`, so a chosen row the truncated row carried would be reported as a
    refusal (exit 2) instead of the table gap it really is. For the same reason
    every pipe line under the header is a data row, the |---| rule aside: a row
    the shape checks reject is refused, never skipped. Two rows sharing a ref
    make every findings row naming it ambiguous, so that table is unreadable too.
    """
    header: list[str] | None = None
    rows: list[Row] = []
    refs: set[str] = set()
    for line in section.splitlines():
        if header is None:
            cells = [c.strip().lower() for c in _table_cells(line)]
            if _TABLE_HEADER_RE.match(line) and all(c in cells for c in _TABLE_COLUMNS):
                header = cells
            continue
        if _CANDIDATE_ROW_RE.match(line) and not _SEPARATOR_ROW_RE.match(line):
            row = _row_from_table(header, _table_cells(line))
            if row is None or (row.ref and row.ref in refs):
                return [], "unreadable-table"
            refs.add(row.ref)
            rows.append(row)
    if rows:
        return rows, None
    if header is None and not TABLE_DATA_ROW_RE.search(section):
        return [], None  # no table here at all; the bullet rows are the section
    return [], "unreadable-table"


def _reviewed_keys(text: str) -> tuple[list[Row], str | None]:
    """Every row of the `## Consolidated Findings` section, in both shapes it
    is written in, and what went wrong reading them: None, `"no-section"` when
    the review file carries no such section, or `"unreadable-table"` when it
    holds a findings table whose header or rows could not be read. The third
    problem the caller can report, `"ref-required"`, is not read here: it is a
    verdict on the rows this returns, not a reading failure."""
    heading = _FINDINGS_HEADING_RE.search(text)
    if heading is None:
        return [], "no-section"
    section = text[heading.end() :]
    following = _NEXT_H2_RE.search(section)
    if following is not None:
        section = section[: following.start()]
    rows: list[Row] = []
    for row in _FINDING_ROW_RE.findall(section):
        # From the right: the row always ends `| {file} | Found by: {agents}`,
        # so an issue text carrying a pipe cannot shift the file cell.
        cells = [c.strip() for c in row.rsplit("|", 2)]
        severity, issue = _split_severity_cell(cells[0])
        key = _finding_key(severity, cells[1] if len(cells) > 1 else "", issue)
        rows.append(Row("", key[0], key[1], _normalize_issue(issue)))
    table, problem = _table_keys(section)
    return rows + table, problem


def _backed(row: dict, reviewed: list[Row]) -> bool:
    """Is this chosen row carried by a review row?

    A row naming a `ref` is backed by the review row holding that exact ref,
    with an agreeing severity and file, and by nothing else — its issue text is
    not compared at all, because the orchestrator re-words it. A ref-less row is
    backed by an exact (severity, file, normalized issue) match, as before. An
    empty issue backs nothing: it would otherwise key as a substring of
    everything.
    """
    severity, file, issue = _finding_key(
        str(row.get("severity", "")),
        str(row.get("file", "")),
        str(row.get("issue", "")),
    )
    ref = str(row.get("ref", "")).strip().upper()
    if ref:
        return any(
            r.ref == ref and (r.severity, r.file) == (severity, file) for r in reviewed
        )
    if not issue:
        return False
    return any(
        (r.severity, r.file, r.issue.lower()) == (severity, file, issue)
        for r in reviewed
    )


def _ref_conflict_verdict(findings: list[dict]) -> tuple[str, str | None] | None:
    """("mismatch", why) when one ref is given two different classifications
    anywhere in `findings`, else None. The same ref twice carrying the SAME
    classification is not a conflict."""
    dispositions: dict[str, object] = {}
    for row in findings:
        ref = str(row.get("ref", "")).strip().upper()
        if not ref:
            continue
        classification = row.get("classification")
        if ref in dispositions and dispositions[ref] != classification:
            return "mismatch", (
                f"finding ref {ref} given two classifications: "
                f"{dispositions[ref]} and {classification}"
            )
        dispositions[ref] = classification
    return None


def _unbacked_verdict(
    findings: list[dict],
    reviewed: list[Row],
) -> tuple[str, str | None] | None:
    """("mismatch", the first chosen row no review row carries), else None.
    verify/discard rows are never applied, so they are not checked."""
    for row in findings:
        if row.get("classification") in _SKIPPED_CLASSIFICATIONS:
            continue
        if not _backed(row, reviewed):
            ref = str(row.get("ref", "")).strip()
            named = f"ref {ref} " if ref else ""
            return "mismatch", (
                "chosen finding absent from the review file's consolidated "
                f"findings: {named}{row.get('severity', '')} "
                f"{row.get('file', '')} | {row.get('issue', '')}"
            )
    return None


def _cross_check_findings(
    text: str,
    findings: list[dict],
    require_coverage: bool = True,
) -> tuple[str, str | None]:
    """Check every chosen finding against the review file's consolidated rows,
    in both directions: a chosen row the review never recorded is refused, and
    (when `require_coverage` is true) a review row no chosen finding names is
    refused too. Returns ("ok", None), ("mismatch", <the first unbacked row, or
    the first ref given two classifications>), ("uncovered", <the first review
    row no chosen finding named>), ("ref-required", <why coverage cannot be
    checked>) when a review row carries no ref for a findings row to name, or
    ("malformed", <why>) when the review file has no consolidated-findings
    section to check against, or holds a findings table that cannot be read.

    `require_coverage=False` (the tail-sweep batch) skips the reverse check:
    a tail-sweep findings JSON is a deliberate, documented subset of the
    consolidated table (actionable Medium/Low rows only), so its rows not
    naming every review-row ref is expected, not an error.
    """
    reviewed, problem = _reviewed_keys(text)
    if problem is not None:
        return "malformed", _FINDINGS_PROBLEMS[problem]
    conflict = _ref_conflict_verdict(findings)
    if conflict is not None:
        return conflict
    if require_coverage and any(row.ref == "" for row in reviewed):
        return "ref-required", _FINDINGS_PROBLEMS["ref-required"]
    unbacked = _unbacked_verdict(findings, reviewed)
    if unbacked is not None:
        return unbacked
    if not require_coverage:
        return "ok", None
    covered_refs = {str(row.get("ref", "")).strip().upper() for row in findings}
    uncovered = [
        row.ref for row in reviewed if row.ref and row.ref not in covered_refs
    ]
    if uncovered:
        # Every uncovered ref, not just the first: naming one costs the
        # operator a whole re-run per row still missing.
        return "uncovered", (
            "review rows with no findings-JSON row naming their ref and a "
            f"classification: {', '.join(uncovered)} "
            "(re-queued [C] rows use classification carry)"
        )
    return "ok", None


def findings_verdict(
    text: str,
    findings: list[dict],
    require_coverage: bool = True,
) -> tuple[str, str | None]:
    """The findings cross-check under its public name, for callers outside the
    gate: "ok" | "mismatch" | "uncovered" | "ref-required" | "malformed"."""
    return _cross_check_findings(text, findings, require_coverage)


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
    rows, error = _load_findings(findings_file)
    if rows is None:
        sys.stderr.write(f"{error}\n")
        return 1
    # Every row, in batch order, before the cross-check runs: a disposition the
    # gate cannot read is what the operator fixes first, and `review-close`
    # would refuse it anyway. The expected list is joined here, not hoisted, so
    # a sixth disposition reaches the line the day it joins the tuple.
    for row in rows:
        if not known_classification(row.get("classification")):
            sys.stderr.write(
                f"row {row.get('ref', '?')}: unknown classification "
                f"{row.get('classification')!r} (expected "
                f"{'|'.join(KNOWN_CLASSIFICATIONS)})\n",
            )
            return 2
    tag, detail = findings_verdict(text, rows)
    if tag == "ok":
        return 0
    sys.stderr.write(f"{detail}\n")
    if tag in ("mismatch", "uncovered", "ref-required"):
        return 2
    # The two malformed reasons part ways here, on the tag's own detail and
    # never on words sniffed out of it: a table the gate could not read is a
    # refusal (it may hold the finding nobody covered), while a review file
    # carrying no findings section at all is the operator's own shape gap.
    return 2 if detail == _FINDINGS_PROBLEMS["unreadable-table"] else 1


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
