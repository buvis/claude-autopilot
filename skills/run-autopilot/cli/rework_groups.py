#!/usr/bin/env python3
"""rework_groups.py - group the decision gate's findings into rework tasks.

    group(findings) -> [{"name_hint", "critical", "findings"}, ...]

Every CRITICAL finding is its own group and never counts toward the cap. The
rest are keyed by file (trailing line suffix stripped); markdown findings share
one `prose` group. While more than NON_CRITICAL_CAP non-critical groups remain,
`general` merges into the smallest code group first, then the two groups with
the deepest shared directory merge (smallest pair on a tie). A pair sharing no
directory merges as `mixed`. Output order: critical groups in input order, then
the rest by worst severity, size (largest first), and key.
"""

from __future__ import annotations

import re

NON_CRITICAL_CAP = 4

_CRITICAL = "\U0001f534"
_RANK = {_CRITICAL: 0, "\U0001f7e0": 1, "\U0001f7e1": 2, "⚪": 3}
_LINE_SUFFIX = re.compile(r":\d+(-\d+)?$")
_UNMERGED_FIRST = ("general", "prose")


def file_key(file: str) -> str:
    """The file a finding points at, without its `:line` or `:a-b` suffix."""
    return _LINE_SUFFIX.sub("", file)


def _dirs(key: str) -> list[str]:
    """Directory components of a group key; a merged key ends with `/`."""
    parts = key.rstrip("/").split("/")
    return parts if key.endswith("/") else parts[:-1]


def _merge_pair(groups: list[dict]) -> tuple[tuple, int, int]:
    """The (sort key, i, j) of the closest pair: deepest shared directory, then
    smallest combined size, then keys."""
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
                best = (rank, i, j)
    return best


def _cap(groups: list[dict]) -> list[dict]:
    general = next((g for g in groups if g["name_hint"] == "general"), None)
    targets = [g for g in groups if g["name_hint"] not in _UNMERGED_FIRST]
    if len(groups) > NON_CRITICAL_CAP and general and targets:
        target = min(targets, key=lambda g: (len(g["findings"]), g["name_hint"]))
        merged = {**target, "findings": target["findings"] + general["findings"]}
        groups = [merged if g is target else g for g in groups if g is not general]
    while len(groups) > NON_CRITICAL_CAP:
        code = [g for g in groups if g["name_hint"] != "prose"]
        if len(code) < 2:
            prose = next(g for g in groups if g["name_hint"] == "prose")
            merged = {**code[0], "findings": code[0]["findings"] + prose["findings"]}
            groups = [merged]
            break
        (neg_shared, _, _), i, j = _merge_pair(code)
        a, b = code[i], code[j]
        prefix = _dirs(a["name_hint"])[: -neg_shared]
        name = "/".join(prefix) + "/" if prefix else "mixed"
        merged = {
            "name_hint": name,
            "critical": False,
            "findings": a["findings"] + b["findings"],
        }
        groups = [g for g in groups if g is not a and g is not b] + [merged]
    return groups


def group(findings: list[dict]) -> list[dict]:
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
