#!/usr/bin/env python3
"""consolidate_findings.py - merge reviewer findings across agents (PRD 00095).

Replaces `consolidate-findings.sh`, which matched findings by exact
normalized string: two reviewers describing one defect in different words
never merged, so every consensus read [1/N] while real 3/N agreement
existed. (The bash script also died on non-ASCII: BSD `tr` is not
multibyte-aware, so `café` lowercased into an invalid sequence and BSD
`sed` then refused the line.)

Same CLI contract as the script it replaces:

    consolidate_findings.py NAME:FILE [NAME:FILE ...]
        [--ledger PATH --ledger-dismiss AGENT]

Reads reviewer output lines in the format

    [AGENT] {emoji} {description} | File: {path} | Task: {id}

and prints the same consolidated markdown table, sorted by consensus then
severity, or the same `No issues found` sentinel. Merged rows keep the most
severe severity, the first-seen description, and every finder.

Two findings merge when their files match (line-number suffix stripped,
segment-aligned path-tail comparison) AND the token-set Jaccard of their
descriptions is at least MERGE_THRESHOLD. They also merge when their files
match and the two descriptions share at least two distinct all-digit
tokens, or when both descriptions carry at least OVERLAP_MIN_TOKENS tokens
and the shorter one's containment in the longer (the overlap coefficient)
reaches OVERLAP_THRESHOLD - the signal that catches a terse reviewer
restating a verbose one (PRD 00198, review 00186). Merging is transitive
inside a file group. `match()` is importable; the ledger filter reuses it.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Pinned by the fixture suite, not tuned in production. The PRD guessed 0.4;
# measured against the reconstructed engram cycle-2 wordings, real
# paraphrases of one defect score 0.267-0.385 against the first-seen group
# while the closest distinct same-file pair scores 0.200. The usable band is
# therefore (0.200, 0.267], and both edges are pinned by
# test_consolidate_findings.py. The band is narrow because token-set overlap
# on one line of prose is a weak signal; that is tolerable here because
# under-merging only undercounts consensus (the status quo this replaces)
# while over-merging would hide a distinct defect inside another's row.
MERGE_THRESHOLD = 0.25

# Second description signal (PRD 00198): Jaccard punishes a length mismatch,
# so Bob's one-line restatement of Alice's four-line finding scores 0.115 to
# 0.161 while the pair is one defect. The overlap coefficient
# |A & B| / min(|A|, |B|) asks instead how much of the terse wording the
# verbose one contains. Measured on the frozen review-00186 outputs
# (fixtures/review-00186, 32 findings): the four real Alice/Bob agreements
# score 0.353 to 0.471 and the closest distinct same-file pair 0.294, so the
# usable band is (0.294, 0.353]; both edges are pinned by
# test_consolidate_findings.py. Under OVERLAP_MIN_TOKENS the coefficient is
# too coarse to trust: a third of nine tokens is three shared words, which
# two distinct findings on one file share routinely (the transitive-spectrum
# fixture's extreme wordings are the pinned example). The signal is also
# only for a terse-versus-verbose pair: two near-equal wordings that share a
# third of their tokens are Jaccard's job, and there the coefficient
# over-merges (review 00198-2: two 11/12-token findings on one file, one
# about timeouts and one about logged passwords, share four tokens). The
# four real agreements have length ratios 1.65 to 2.88, the false merge 1.09,
# so the fallback needs a ratio of at least OVERLAP_MIN_RATIO.
OVERLAP_THRESHOLD = 1 / 3
OVERLAP_MIN_TOKENS = 10
OVERLAP_MIN_RATIO = 1.5

SEVERITY_ORDER = {"🔴": 1, "🟠": 2, "🟡": 3, "⚪": 4}
UNKNOWN_SEVERITY_RANK = 5

# Dropped before comparing descriptions: they carry no defect identity, so
# leaving them in inflates the overlap between unrelated findings.
STOPWORDS = frozenset(
    [
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "been",
        "but",
        "by",
        "can",
        "could",
        "does",
        "for",
        "from",
        "has",
        "have",
        "in",
        "into",
        "is",
        "it",
        "its",
        "may",
        "might",
        "must",
        "no",
        "not",
        "of",
        "on",
        "or",
        "that",
        "the",
        "their",
        "then",
        "there",
        "these",
        "this",
        "to",
        "under",
        "use",
        "used",
        "uses",
        "using",
        "was",
        "were",
        "when",
        "which",
        "while",
        "will",
        "with",
        "without",
        "would",
    ],
)

# The bracketed name is skipped, not captured: the NAME half of the caller's
# NAME:FILE pair is authoritative, so a reviewer whose output mislabels its
# own bracket is still attributed to the file it was read from.
_LINE_RE = re.compile(
    r"^\[[^\]]+\]\s+(?P<severity>.)\s+(?P<desc>.*?)"
    r"\s+\|\s+File:\s*(?P<file>.*?)"
    r"\s+\|\s+Task:\s*(?P<task>.*?)\s*$",
)
# Every line-citation suffix the personas emit (PRD 00198): `:N`, `:N-M`,
# ` (lines N-M)`, ` (lines 18-22, 423)` and `#L12` / `#L12-L20`. Applied in a
# loop because one citation can carry two forms (`a.md:12 (lines 3-4)`).
_TRAILING_LINENO_RE = re.compile(
    r"(?:\s*\(lines?\s+\d[\d,\s-]*\)|:\d+(?:-\d+)?|#L\d+(?:-L?\d+)?)$",
)
# Bob's multi-file shape (review 00191): `N/A (skills/x.py:77, skills/y.py:91)`.
# The first path inside the parentheses is the citation.
_NA_PARENS_RE = re.compile(r"^N/A\s*\(\s*([^,)]+)", re.IGNORECASE)
_WORD_RE = re.compile(r"[a-z0-9_]+")


@dataclass
class Finding:
    agent: str
    severity: str
    desc: str
    file: str
    task: str
    # Ledger entries only: why the call was settled. Rendered beside an
    # auto-dismissed finding so a wrong dismissal is visible, not silent.
    reason: str = ""
    finders: list[str] = field(default_factory=list)
    # Every member's raw `File:` citation, first-seen order; `render` reads
    # it to say when a row merged only after suffix stripping.
    files: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.finders = [self.agent] if self.agent else []
        self.files = [self.file]


def strip_citation_suffixes(path: str) -> str:
    """The citation with every trailing line marker removed, looping until
    the string stops changing so stacked forms all go."""
    cleaned = path.strip()
    na = _NA_PARENS_RE.match(cleaned)
    if na:
        cleaned = na.group(1).strip()
    while True:
        shorter = _TRAILING_LINENO_RE.sub("", cleaned)
        if shorter == cleaned:
            return cleaned
        cleaned = shorter


def _segments(path: str) -> tuple[str, ...]:
    """Comparable path segments: separators unified, `./` noise removed,
    lower-cased. No suffix handling - callers decide that."""
    cleaned = path.strip().replace("\\", "/")
    return tuple(s.lower() for s in cleaned.split("/") if s not in ("", "."))


def normalize_file(path: str) -> tuple[str, ...]:
    """Path as comparable segments: line-number suffixes dropped first,
    then `_segments` (lower-casing last)."""
    return _segments(strip_citation_suffixes(path))


def _tails_match(a: tuple[str, ...], b: tuple[str, ...]) -> bool:
    if not a or not b:
        return a == b
    short, long_ = (a, b) if len(a) <= len(b) else (b, a)
    return long_[-len(short) :] == short


def files_match(a: str, b: str) -> bool:
    """True when one path is a segment-aligned tail of the other, so
    `src/db/query.ts` and `query.ts` are the same file but `a/x.py` and
    `b/x.py` are not."""
    return _tails_match(normalize_file(a), normalize_file(b))


def _raw_tokens(desc: str) -> list[str]:
    return _WORD_RE.findall(desc.lower())


def tokens(desc: str) -> frozenset[str]:
    return frozenset(_raw_tokens(desc)) - STOPWORDS


def numeric_tokens(desc: str) -> frozenset[str]:
    """All-digit tokens of desc, taken before the stopword subtraction."""
    return frozenset(t for t in _raw_tokens(desc) if t.isdigit())


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def overlap(a: frozenset[str], b: frozenset[str]) -> float:
    """The shorter set's containment in the longer; 0.0 when either is
    shorter than OVERLAP_MIN_TOKENS (too few tokens to mean anything) or
    the two are within OVERLAP_MIN_RATIO of each other in length (not a
    terse-versus-verbose pair, so Jaccard alone decides)."""
    shorter, longer = min(len(a), len(b)), max(len(a), len(b))
    if shorter < OVERLAP_MIN_TOKENS or longer < OVERLAP_MIN_RATIO * shorter:
        return 0.0
    return len(a & b) / shorter


def match(finding_a: Finding, finding_b: Finding) -> bool:
    """Do these two findings describe the same defect?"""
    if not files_match(finding_a.file, finding_b.file):
        return False
    tokens_a, tokens_b = tokens(finding_a.desc), tokens(finding_b.desc)
    if jaccard(tokens_a, tokens_b) >= MERGE_THRESHOLD:
        return True
    if overlap(tokens_a, tokens_b) >= OVERLAP_THRESHOLD:
        return True
    shared_nums = numeric_tokens(finding_a.desc) & numeric_tokens(finding_b.desc)
    return len(shared_nums) >= 2


def parse_line(line: str, agent: str) -> Finding | None:
    """Parse one reviewer output line, or None when it is not a finding."""
    line = line.strip()
    if not line or line.startswith("```") or "No issues found" in line:
        return None
    m = _LINE_RE.match(line)
    if not m or m.group("severity") not in SEVERITY_ORDER:
        return None
    return Finding(
        agent=agent,
        severity=m.group("severity"),
        desc=m.group("desc").strip(),
        file=m.group("file").strip(),
        task=m.group("task").strip(),
    )


def parse_agent_output(path: Path, agent: str) -> list[Finding]:
    """Findings from one reviewer's file; a missing file contributes none
    (a reviewer that was skipped is not an error here)."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return [f for f in (parse_line(line, agent) for line in text.splitlines()) if f]


def _fold(group: list[Finding]) -> Finding:
    """One row from a cluster: the first-seen description, file and task,
    the most severe severity any member reported, and every finder in
    first-seen order. Returns a NEW Finding - the inputs are not mutated."""
    head = group[0]
    row = Finding(
        agent=head.agent,
        severity=head.severity,
        desc=head.desc,
        file=head.file,
        task=head.task,
    )
    for other in group[1:]:
        if SEVERITY_ORDER.get(
            other.severity,
            UNKNOWN_SEVERITY_RANK,
        ) < SEVERITY_ORDER.get(
            row.severity,
            UNKNOWN_SEVERITY_RANK,
        ):
            row.severity = other.severity
        for finder in other.finders:
            if finder not in row.finders:
                row.finders.append(finder)
        for cited in other.files:
            if cited not in row.files:
                row.files.append(cited)
    return row


def consolidate(findings: list[Finding]) -> list[Finding]:
    """Merge matching findings into one row each, first-seen order kept.

    Single-linkage and genuinely transitive: a finding joins every cluster
    any of whose members it matches, and those clusters then become one. It
    has to be transitive — reviewers word one defect along a spectrum, so
    the two extreme wordings routinely fail to match each other while both
    match the middle one. Comparing only against a cluster representative
    drops the third reviewer's concurrence and reports [2/3] plus [1/3]
    where the truth is [3/3], which is the very undercount this script
    replaced the bash matcher to fix.
    """
    clusters: list[list[Finding]] = []
    for finding in findings:
        hits = [c for c in clusters if any(match(member, finding) for member in c)]
        if not hits:
            clusters.append([finding])
            continue
        # Absorb the bridged clusters BEFORE the bridging finding, so
        # `finders` stays in first-seen order: the clusters were all seen
        # before the finding that joined them.
        first = hits[0]
        for other in hits[1:]:
            first.extend(other)
            clusters.remove(other)
        first.append(finding)
    return [_fold(cluster) for cluster in clusters]


def load_ledger(path: Path) -> list[Finding]:
    """Settled entries as Findings. A malformed or unreadable ledger warns
    once and yields nothing - a broken ledger must never drop a reviewer's
    findings."""
    try:
        entries = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"consolidate_findings: ignoring ledger {path}: {exc}", file=sys.stderr)
        return []
    if not isinstance(entries, list):
        print(
            f"consolidate_findings: ignoring ledger {path}: not a list",
            file=sys.stderr,
        )
        return []
    settled = []
    for entry in entries:
        if isinstance(entry, dict) and entry.get("issue"):
            settled.append(
                Finding(
                    agent="LEDGER",
                    severity="",
                    desc=str(entry["issue"]),
                    file=str(entry.get("file", "")),
                    task="",
                    reason=str(entry.get("reason", "")),
                ),
            )
    return settled


def split_ledger_dismissed(
    findings: list[Finding],
    settled: list[Finding],
    dismiss_agent: str,
) -> tuple[list[Finding], list[tuple[Finding, Finding]]]:
    """Partition into (kept, dismissed) where dismissed are `dismiss_agent`'s
    findings matching a settled entry, paired with the entry they matched."""
    kept, dismissed = [], []
    target = dismiss_agent.upper()
    for finding in findings:
        if finding.agent.upper() == target:
            hit = next((e for e in settled if match(e, finding)), None)
            if hit is not None:
                dismissed.append((finding, hit))
                continue
        kept.append(finding)
    return kept, dismissed


def suffix_stripped_citations(row: Finding) -> list[str]:
    """The row's raw citations when at least one pair of them would NOT have
    matched as written (`_segments`, suffixes intact) and DOES match once
    the line suffixes come off (`normalize_file`). Empty when every pair
    already agreed by path tail (`src/cli.py:4` beside `/repo/src/cli.py:4`
    is not drift) and for a transitive row whose outer citations never match
    each other at all (`a/util.py` and `b/util.py` bridged by `util.py`)."""
    for i, a in enumerate(row.files):
        for b in row.files[i + 1 :]:
            if not _tails_match(_segments(a), _segments(b)) and files_match(a, b):
                return list(row.files)
    return []


def render(merged: list[Finding], total_agents: int) -> str:
    rows = [
        "| Consensus | Severity | Issue | File | Task | Found By |",
        "|-----------|----------|-------|------|------|----------|",
    ]
    ordered = sorted(
        enumerate(merged),
        key=lambda pair: (
            -len(pair[1].finders),
            SEVERITY_ORDER.get(pair[1].severity, UNKNOWN_SEVERITY_RANK),
            pair[0],
        ),
    )
    for position, (_, f) in enumerate(ordered, start=1):
        rows.append(
            f"| [{len(f.finders)}/{total_agents}] | {f.severity} | {f.desc} | "
            f"{f.file} | {f.task} | {', '.join(f.finders)} |",
        )
        drifted = suffix_stripped_citations(f)
        if drifted:
            # Visible in the review file's script-output block, so a
            # persona drifting back to `(lines a-b)` citations is noticed.
            print(
                f"consolidate_findings: row {position} merged citations that "
                f"matched only after suffix stripping: {' ~ '.join(drifted)}",
                file=sys.stderr,
            )
    return "\n".join(rows)


def render_dismissed(dismissed: list[tuple[Finding, Finding]]) -> str:
    lines = ["### Auto-dismissed (ledger)", ""]
    for finding, entry in dismissed:
        reason = entry.reason or "settled in an earlier cycle"
        lines.append(
            f"- [{finding.agent}] {finding.severity} {finding.desc} | "
            f"File: {finding.file} — {reason}",
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Consolidate reviewer findings from NAME:FILE pairs.",
    )
    parser.add_argument("pairs", nargs="+", metavar="NAME:FILE")
    parser.add_argument("--ledger", type=Path, default=None)
    parser.add_argument("--ledger-dismiss", default=None, metavar="AGENT")
    args = parser.parse_args(argv)

    findings: list[Finding] = []
    for pair in args.pairs:
        agent, sep, path = pair.partition(":")
        if not sep or not path:
            parser.error(f"expected NAME:FILE, got {pair!r}")
        findings.extend(parse_agent_output(Path(path), agent))

    dismissed: list[tuple[Finding, Finding]] = []
    if args.ledger is not None and args.ledger_dismiss:
        findings, dismissed = split_ledger_dismissed(
            findings,
            load_ledger(args.ledger),
            args.ledger_dismiss,
        )

    merged = consolidate(findings)
    if not merged:
        print("✅ No issues found - all agents passed")
    else:
        print(render(merged, len(args.pairs)))
    if dismissed:
        print()
        print(render_dismissed(dismissed))
    return 0


if __name__ == "__main__":
    sys.exit(main())
