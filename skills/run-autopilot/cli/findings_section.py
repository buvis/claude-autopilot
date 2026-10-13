"""cli/findings_section.py - reads the `## Consolidated Findings` section of a
review file into rows, in both shapes it is written in (the `- [m/n]` bullet
list and the pipe table). Split out of cli/gate.py, which re-exports the names
other modules reach through it.
"""

from __future__ import annotations

import re
from typing import NamedTuple

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
# finding it carried). Leading whitespace is tolerated — some renderers indent
# a data row under an unindented header — and the closing pipe is required, so
# a row truncated at its last cell is refused rather than silently accepted.
_CANDIDATE_ROW_RE = re.compile(r"^\s*\|")
_SEPARATOR_ROW_RE = re.compile(r"^\s*\|(\s*:?-{3,}:?\s*\|)+\s*$")
_TERMINATED_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")
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


def _table_header(line: str) -> list[str] | None:
    """The lower-cased cells of a findings-table header naming Severity, Issue
    and File, else None."""
    cells = [c.strip().lower() for c in _table_cells(line)]
    if _TABLE_HEADER_RE.match(line) and all(c in cells for c in _TABLE_COLUMNS):
        return cells
    return None


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
            header = _table_header(line)
            continue
        if _CANDIDATE_ROW_RE.match(line) and not _SEPARATOR_ROW_RE.match(line):
            if not _TERMINATED_ROW_RE.match(line):
                return [], "unreadable-table"
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


def _section_bounds(
    text: str,
) -> tuple[re.Match[str] | None, re.Match[str] | None]:
    """The `## Consolidated Findings` heading match and the next live `## `
    heading's match after it, both against `text`'s own offsets - or
    (None, None) when `text` carries no such heading at all. Shared by every
    reader of the section's bounds, so a change to how a heading or its end
    is found lands in one place."""
    heading = _FINDINGS_HEADING_RE.search(text)
    if heading is None:
        return None, None
    following = _NEXT_H2_RE.search(text, heading.end())
    return heading, following


def _reviewed_keys(text: str) -> tuple[list[Row], str | None]:
    """Every row of the `## Consolidated Findings` section, in both shapes it
    is written in, and what went wrong reading them: None, `"no-section"` when
    the review file carries no such section, or `"unreadable-table"` when it
    holds a findings table whose header or rows could not be read. The third
    problem the caller can report, `"ref-required"`, is not read here: it is a
    verdict on the rows this returns, not a reading failure."""
    heading, following = _section_bounds(text)
    if heading is None:
        return [], "no-section"
    section = text[heading.end() : following.start() if following else len(text)]
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
