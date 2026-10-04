#!/usr/bin/env python3
"""rework_groups.py - group the decision gate's findings into rework tasks.

    group(findings) -> [{"name_hint", "critical", "findings"}, ...]

Every CRITICAL finding is its own group and never counts toward the cap. The
rest are keyed by file (trailing citation suffix stripped, `N/A` normalized to
`general`); markdown findings share one `prose` group. While more than
NON_CRITICAL_CAP non-critical groups remain, `general` merges into the smallest
code group first, then the two groups with the deepest shared directory merge
(smallest pair on a tie). A pair sharing no
directory merges as `mixed`. Output order: critical groups in input order, then
the rest by worst severity, size (largest first), and key.
"""

from __future__ import annotations

import re

NON_CRITICAL_CAP = 4

_CRITICAL = "\U0001f534"
_RANK = {_CRITICAL: 0, "\U0001f7e0": 1, "\U0001f7e1": 2, "⚪": 3}
# Every citation suffix the findings table uses, anchored at the end so a path
# that merely contains a space or a `#` keeps it.
_LINE_SUFFIX = re.compile(r"(?:\s*\(lines?\s+\d[\d,\s-]*\)|:\d+(?:-\d+)?|#L\d+(?:-L?\d+)?)$")
# The table's own "no file" marker, bare or wrapping a citation.
_NOT_APPLICABLE = re.compile(r"n/a(\s*\(.*\))?", re.IGNORECASE)
_NOT_A_MERGE_TARGET = ("general", "prose")


def file_key(file: str) -> str:
    """The file a finding points at, without its citation suffix (`:line`,
    `:a-b`, ` (line N)`, ` (lines a-b)`, ` (lines a-b, c)`, `#Ln`, `#La-Lb`);
    `N/A` in any shape is `general`."""
    key = file
    while True:
        stripped = _LINE_SUFFIX.sub("", key)
        if stripped == key:
            break
        key = stripped
    return "general" if _NOT_APPLICABLE.fullmatch(key) else key


def _dirs(key: str) -> list[str]:
    """Directory components of a group key; a merged key ends with `/`."""
    parts = key.rstrip("/").split("/")
    return parts if key.endswith("/") else parts[:-1]


def _merge_pair(groups: list[dict]) -> tuple[int, int, int]:
    """The (shared directory depth, i, j) of the closest pair: deepest shared
    directory, then smallest combined size, then keys."""
    best = None
    for i, a in enumerate(groups):
        for j in range(i + 1, len(groups)):
            b = groups[j]
            shared = 0
            for x, y in zip(_dirs(a["name_hint"]), _dirs(b["name_hint"])):
                if x != y:
                    break
                shared += 1
            pair_keys = sorted([a["name_hint"], b["name_hint"]])
            rank = (-shared, len(a["findings"]) + len(b["findings"]), pair_keys)
            if best is None or rank < best[0]:
                best = (rank, (shared, i, j))
    return best[1]


def _cap(groups: list[dict]) -> list[dict]:
    general = next((g for g in groups if g["name_hint"] == "general"), None)
    targets = [g for g in groups if g["name_hint"] not in _NOT_A_MERGE_TARGET]
    if len(groups) > NON_CRITICAL_CAP and general and targets:
        target = min(targets, key=lambda g: (len(g["findings"]), g["name_hint"]))
        merged = {**target, "findings": target["findings"] + general["findings"]}
        groups = [merged if g is target else g for g in groups if g is not general]
    while len(groups) > NON_CRITICAL_CAP:
        code = [g for g in groups if g["name_hint"] != "prose"]
        if len(code) < 2:
            # Spec rule 5's last clause - fold `prose` into the one remaining
            # code group - which is unreachable while NON_CRITICAL_CAP is 4.
            # An empty `code` needs a cap of 0; the guard keeps `code[0]` safe.
            if not code:
                break
            prose = next(g for g in groups if g["name_hint"] == "prose")
            merged = {**code[0], "findings": code[0]["findings"] + prose["findings"]}
            groups = [merged]
            break
        shared, i, j = _merge_pair(code)
        a, b = code[i], code[j]
        prefix = _dirs(a["name_hint"])[:shared]
        name = "/".join(prefix) + "/" if prefix else "mixed"
        merged = {
            "name_hint": name,
            "critical": False,
            "findings": a["findings"] + b["findings"],
        }
        groups = [g for g in groups if g is not a and g is not b] + [merged]
    return groups


def group(findings: list[dict]) -> list[dict]:
    """Group `findings` into rework tasks, leaving the input untouched.

    Critical groups come out first, in input order: that is deliberate. The
    rule's "then by severity, size, key" clauses order the non-critical groups
    only, and "critical groups first" says nothing about their internal order,
    so the critical groups are never sorted.
    """
    critical = []
    by_key: dict[str, list[dict]] = {}
    for finding in findings:
        key = file_key(finding["file"])
        if finding["severity"] == _CRITICAL:
            critical.append({"name_hint": key, "critical": True, "findings": [finding]})
            continue
        by_key.setdefault("prose" if key.endswith(".md") else key, []).append(finding)
    rest = [
        {"name_hint": key, "critical": False, "findings": items}
        for key, items in by_key.items()
    ]
    # A merge concatenates two buckets, so a merged group holds its findings in
    # bucket order, not table order. Re-sort every group by input position to
    # put the verbatim findings block back in the order the reviewer wrote it.
    position = {id(f): n for n, f in enumerate(findings)}
    rest = [
        {**g, "findings": sorted(g["findings"], key=lambda f: position[id(f)])}
        for g in _cap(rest)
    ]
    rest.sort(
        key=lambda g: (
            min(_RANK.get(f["severity"], len(_RANK)) for f in g["findings"]),
            -len(g["findings"]),
            g["name_hint"],
        )
    )
    return critical + rest
