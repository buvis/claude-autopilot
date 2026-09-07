"""Lane planner for /fast-track — the four decisions that spend a dispatch.

The roster is fixed before any finding exists: tess only when the card ships no
tests, fanout or the legacy Alice in the consensus slot, carl only when his
backend is installed. Findings then decide two things and no more — which ones
earn an adversarial verification (never the workflow's own, it verified them
already) and whether the item's commits land on the working branch. The ledger
counter answers what an item actually cost, reading dispatches out of the rows
record_dispatch.py appended rather than out of the item's name.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

_BLOCKING = ("CRITICAL", "HIGH")
_WORKFLOW_LANE = "fast-track:fanout"


@dataclass
class Finding:
    """One raised finding, as a review lane reports it."""

    severity: str
    title: str
    file: str
    lane: str


def plan_lanes(
    tests_present: bool,
    workflow_available: bool,
    carl_available: bool,
) -> list[str]:
    """The lanes this item dispatches, in order. Each flag is independent."""
    lanes = [] if tests_present else ["fast-track:tess"]
    lanes.append("fast-track:ivan")
    lanes.append(_WORKFLOW_LANE if workflow_available else "fast-track:alice")
    lanes += ["fast-track:blake", "fast-track:eve", "fast-track:bob"]
    if carl_available:
        lanes.append("fast-track:carl")
    return lanes


def verify_targets(findings: list[Finding]) -> list[Finding]:
    """The findings worth an adversarial verification, in the order raised.

    A MEDIUM or a LOW neither reworks nor blocks the exit, and the workflow
    lane verified its own rows before it reported.
    """
    return [
        finding
        for finding in findings
        if finding.severity in _BLOCKING and finding.lane != _WORKFLOW_LANE
    ]


def exit_action(findings: list[Finding]) -> str:
    """``"branch"`` when any surviving finding blocks, else ``"commit"``."""
    if any(finding.severity in _BLOCKING for finding in findings):
        return "branch"
    return "commit"


def count_item_dispatches(ledger: Path, item: str) -> Counter[str]:
    """Dispatches opened for ``item``, by kind. A missing ledger counts none.

    ``queued_at`` is what opens a dispatch: an end row repeating its start
    row's kind and task would otherwise be counted a second time.
    """
    try:
        lines = ledger.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return Counter()
    counts: Counter[str] = Counter()
    for line in lines:
        row = json.loads(line)
        if row.get("task") == item and "queued_at" in row:
            counts[row["kind"]] += 1
    return counts
