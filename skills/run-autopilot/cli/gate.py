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

--findings <path> is a second opt-in check, and it runs in BOTH directions:
every row of that chosen-findings JSON array must be backed by a row of the
review file's `## Consolidated Findings` section, AND every review row must be
named by a `--findings` row carrying a classification - so a batch can neither
apply a finding no reviewer recorded nor leave a recorded finding undisposed.
That section is read in both shapes it is written in: the bullet list and the
pipe table `| Ref | Consensus | Severity | Issue | File | Task | Found By |`.
A chosen row carrying a `"ref"` is backed by the review row holding that exact
ref, severity and file; a row carrying none falls back to an exact (severity,
file, normalized issue) match. `verify` and `discard` rows need no backing
review row (nothing of theirs is applied); a `carry` row needs one like every
other applied row. A review file with no such section, no [m/n] token or pipe
row anywhere and an empty `--findings` array is a shape gap (exit 1).
The refusals (exit 2) are a review row no `--findings` row names a
classification for, a findings table the gate could not read, a findings
section with no Ref column for a findings row to name, a `--findings` row
with an unknown classification, a missing section under a non-empty
`--findings` array, a second findings heading, and any [m/n] token or pipe
row outside a closed fence that the findings parser did not read - the gate
cannot say a batch covers rows it was unable to read.

CLI: autopilot gate --review-file <path> [--reviewers alice,bob,...]
[--require-codex-guard] [--assert-constraint-met] [--findings <path>]
When --reviewers is omitted, the file's frontmatter `reviewers:` line (a
comma-separated list written by consolidation) is used; if neither names any
reviewer, only the verdict and tests lines are checked.

Exit codes (gate-scoped, unchanged from check_review_file.py):
    0  shape holds (or unreadable file — fail open, loud)
    1  shape gap (or missing review file, or an unusable --findings file, or
       no consolidated-findings section, no token and an empty --findings)
    2  --assert-constraint-met and the guard line records `; constraint UNMET`;
       a `--findings` row the review file never recorded; a review row no
       `--findings` row names a classification for; a `--findings` row with an
       unknown classification; a findings section the gate could not read,
       missed, repeated, or one with no Ref column to check coverage against;
       or a token or pipe row the findings parser did not read
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Run by path (review_coverage_hook.py) there is no package, and the cli dir is
# sys.path[0]. The two `X as X` imports are explicit re-exports, unused here:
# convergence.py and review_close.py still reach them through gate.
if __package__:
    from .findings_section import (
        _CANDIDATE_ROW_RE,
        _FINDING_ROW_RE,
        _FINDINGS_HEADING_RE,
        Row,
        _finding_key,
        _reviewed_keys,
        _section_bounds,
        _table_header,
    )
    from .findings_section import TABLE_DATA_ROW_RE as TABLE_DATA_ROW_RE
    from .findings_section import _split_severity_cell as _split_severity_cell
else:
    from findings_section import (
        _CANDIDATE_ROW_RE,
        _FINDING_ROW_RE,
        _FINDINGS_HEADING_RE,
        Row,
        _finding_key,
        _reviewed_keys,
        _section_bounds,
        _table_header,
    )
    from findings_section import TABLE_DATA_ROW_RE as TABLE_DATA_ROW_RE
    from findings_section import _split_severity_cell as _split_severity_cell

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
# Any `[m/n]` anywhere on a line: the token every findings row carries.
_CONSENSUS_TOKEN_RE = re.compile(r"\[\d+/\d+\]")
# A line that already looks like structured tabular data: a pipe anywhere, or
# an HTML <table>/<td> tag anywhere. Deliberately no bare bullet/blockquote
# marker: a reviewer's plain "- 🟡 Name: free-text comment" bullet stays unread.
_ROW_SHAPE_RE = re.compile(r"\||<t(?:able|d)\b", re.IGNORECASE)
_SEVERITY_EMOJI_ANY_RE = re.compile("[\U0001f534\U0001f7e0\U0001f7e1⚪]")
# A severity word anywhere on the line; only ever consulted beside
# _LEADING_RATIO_RE, so ordinary prose naming a severity is never flagged.
_SEVERITY_WORD_ANY_RE = re.compile(r"\b(CRITICAL|HIGH|MEDIUM|LOW)\b", re.IGNORECASE)
_SEVERITY_WORD_CELL_RE = re.compile(
    r"\|\s*(CRITICAL|HIGH|MEDIUM|LOW)\s*\|",
    re.IGNORECASE,
)
# A consensus-marker variant leading the line, after any bullet or blockquote
# markers: spaced or asymmetric brackets, fullwidth or lenticular brackets, or
# parentheses, open and close matched independently. Anchored so a count in
# prose ("(1092/1092)") or a heading ("### Full Consensus (3/3)") stays unread.
_CONSENSUS_VARIANT_RE = re.compile(
    r"^[ \t]{0,3}(?:[-*+>][ \t]*)*[\[(［【]\s*\d+\s*/\s*\d+\s*[\])］】]",
)
# A severity emoji followed by its severity word ("🔴 CRITICAL"): a reviewer's
# "[BLAKE] 🟡 issue | File: x" lens bullet names no word and stays unread.
_SEVERITY_EMOJI_WORD_RE = re.compile(
    "[\U0001f534\U0001f7e0\U0001f7e1⚪]\\s*(CRITICAL|HIGH|MEDIUM|LOW)\\b",
    re.IGNORECASE,
)
# A bare m/n leading the line (up to 3 spaces/tabs of indent): the pipe-less
# table's only structural signal, read only beside a severity signal.
_LEADING_RATIO_RE = re.compile(r"^[ \t]{0,3}\d+\s*/\s*\d+\b")
# A fence opener or closer, read off the RAW line: at most 3 leading spaces
# (CommonMark's ceiling; a tab or a 4th space makes an indented code block, not
# a fence), then the run. Trailing text (```markdown) is allowed.
_FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
# What `_reviewed_keys` could not read, as the operator has to hear it. The two
# must stay distinct: "the section is missing" and "the section is there and its
# table is what failed" are different repairs.
_FINDINGS_PROBLEMS = {
    "no-section": "no '## Consolidated Findings' section in the review file",
    "unreadable-table": (
        "found a findings table whose header or rows could not be read: "
        "expected a header naming Severity, Issue and File, and rows shaped "
        "| [m/n] | ... | (optionally led by a | R1 | ref cell), each closed "
        "with its own trailing | ; a Ref-less table that cannot be covered is "
        "reported separately as 'ref-required', not here"
    ),
    "ref-required": (
        "coverage requires a Ref column; this section has at least one row "
        "with none - R1 R2 ... are keys the gate normalizes case-insensitively "
        "from the pipe table's Ref column"
        "; review files from autopilot 0.9.0 or earlier have no Ref column; "
        "finish or restart the batch on one version"
    ),
    "repeated-section": (
        "more than one '## Consolidated Findings' heading in the review file: "
        "there is no single findings section to read"
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


def _unfenced(text: str) -> str:
    """`text` with every line of a CLOSED fence blanked, opener and closer
    included, so a quoted example is no heading and no row while line numbers
    hold. The raw line decides, through `_FENCE_RE`: a fence opens or closes
    only on a line indented at most 3 spaces, and closes only on a run of its
    own character at least as long as the opener's (trailing text allowed);
    one that never closes quotes nothing - and stops the scan
    right there, so a later run of the fence character further down (which
    would otherwise read as its own, separate fence) cannot blank content
    that is really just unclosed-fence text."""
    lines = text.splitlines()
    live = list(lines)
    i = 0
    while i < len(lines):
        opener = _FENCE_RE.match(lines[i])
        if opener is not None:
            run = opener.group(1)
            closed = False
            for j in range(i + 1, len(lines)):
                closer = _FENCE_RE.match(lines[j])
                if closer is not None and closer.group(1).startswith(run):
                    live[i : j + 1] = [""] * (j + 1 - i)
                    i = j
                    closed = True
                    break
            if not closed:
                break
        i += 1
    return "\n".join(live)


def _unread_token(live: str) -> str | None:
    """The first line of `live` holding a [m/n] token or a pipe row that the
    findings parser does not read, named by number and text, else None.

    Read means: in the one findings section, a `- [m/n]` bullet row, the table
    header, or a pipe row below that header. Every other token line - under a
    reviewer heading, above the header, in a comment, a blockquote or an
    indented block - is a finding nobody would disposition.
    """
    lines = live.split("\n")
    consumed: set[int] = set()
    heading, following = _section_bounds(live)
    if heading is not None:
        stop = live.count("\n", 0, following.start()) if following else len(lines)
        in_table = False
        for i in range(live.count("\n", 0, heading.end()), stop):
            line = lines[i]
            if not line.strip():
                # A blank line ends a table block: the next pipe row has to
                # be re-evaluated as a header, not treated as more data of
                # whatever table came before it.
                in_table = False
                continue
            in_table = in_table or _table_header(line) is not None
            if (in_table and _CANDIDATE_ROW_RE.match(line)) or _FINDING_ROW_RE.match(
                line,
            ):
                consumed.add(i)
    for i, line in enumerate(lines):
        if i in consumed:
            continue
        if (
            _CONSENSUS_TOKEN_RE.search(line)
            or _CANDIDATE_ROW_RE.match(line)
            or _CONSENSUS_VARIANT_RE.search(line)
            or _SEVERITY_WORD_CELL_RE.search(line)
            or (_ROW_SHAPE_RE.search(line) and _SEVERITY_EMOJI_WORD_RE.search(line))
            or (
                _LEADING_RATIO_RE.match(line)
                and (
                    _SEVERITY_EMOJI_ANY_RE.search(line)
                    or _SEVERITY_WORD_ANY_RE.search(line)
                )
            )
        ):
            return (
                f"line {i + 1}: a [m/n] token or table row the findings parser "
                f"did not read: {line.strip()[:120]}"
            )
    return None


def _malformed_detail(
    live: str,
    findings: list[dict],
    problem: str | None,
) -> str | None:
    """The `malformed` detail for `live` (already fence-blanked) given the
    section-reading `problem` the caller's own `_reviewed_keys(live)` call
    already returned, or None when the review file's section is readable: a
    repeated findings heading, an unread [m/n] token or pipe row, a missing
    section under a non-empty findings array, or whatever `problem` itself
    names."""
    if len(_FINDINGS_HEADING_RE.findall(live)) > 1:
        return _FINDINGS_PROBLEMS["repeated-section"]
    unread = _unread_token(live)
    if unread is not None:
        return unread
    if problem == "no-section" and findings:
        return (
            "no '## Consolidated Findings' section, yet the findings JSON names "
            f"{len(findings)} rows: the findings heading is missing or misspelled"
        )
    if problem is not None:
        return _FINDINGS_PROBLEMS[problem]
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
    section to check against, more than one, a [m/n] token or pipe row the
    parser did not read, or a findings table that cannot be read. Closed
    fences are blanked first: a quoted example is neither a heading nor a row.

    `require_coverage=False` (the tail-sweep batch) skips the reverse check:
    a tail-sweep findings JSON is a deliberate, documented subset of the
    consolidated table (actionable Medium/Low rows only), so its rows not
    naming every review-row ref is expected, not an error.
    """
    live = _unfenced(text)
    reviewed, problem = _reviewed_keys(live)
    malformed = _malformed_detail(live, findings, problem)
    if malformed is not None:
        return "malformed", malformed
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
    uncovered = [row.ref for row in reviewed if row.ref and row.ref not in covered_refs]
    if uncovered:
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
            # A ref names the row on its own. A row carrying none still has to
            # be findable, so its issue text (else its file) is appended.
            tail = "" if row.get("ref") else f" [{row.get('issue') or row.get('file')}]"
            sys.stderr.write(
                f"row {row.get('ref', '?')}: unknown classification "
                f"{row.get('classification')!r} (expected "
                f"{'|'.join(KNOWN_CLASSIFICATIONS)}){tail}\n",
            )
            return 2
    tag, detail = findings_verdict(text, rows)
    if tag == "ok":
        return 0
    sys.stderr.write(f"{detail}\n")
    # The one exit-1 reason, matched on the whole detail and never on words
    # sniffed out of it: no findings section, no unread token and an empty
    # batch is the operator's own shape gap. Every other verdict is a refusal.
    if tag == "malformed" and detail == _FINDINGS_PROBLEMS["no-section"]:
        return 1
    return 2


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
