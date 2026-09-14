#!/usr/bin/env python3
"""cli/convergence.py - the `review_converged` row builder (PRD 00188).

The ONE definition of the event row's field set: what the review gate
appends to `dev/local/autopilot/loop-metrics.jsonl` when a PRD's review loop
ends. Pure over the state dict, the session rows already parsed from that
file, the review files under `dev/local/reviews` and the wip PRD; no state
writes, no subprocesses.

Absence reads as null, never as zero: a missing or unreadable review file
yields null reviewers/verdict/findings, a missing wip PRD yields null
`tasks_in_prd`, and a state with neither root task counts nor a task list
yields null task counts.
"""

from __future__ import annotations

import re
from pathlib import Path

from cli.gate import FRONTMATTER_REVIEWERS_RE, VERDICT_RE

# Mark -> findings bucket, in severity order; the first mark met scanning a
# consolidated table row left to right picks the bucket.
SEVERITY_MARKS = {"🔴": "critical", "🟠": "high", "🟡": "medium", "⚪": "low"}
CONSENSUS_ROW_RE = re.compile(r"^\| \[\d+/\d+\] \|")
CHECKBOX_RE = re.compile(r"^- \[[ x]\] ", re.MULTILINE)


def _read_text(path: Path) -> str | None:
    """File text, or None when the path is missing, not a readable file or
    not UTF-8."""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def read_cycle(reviews_dir: Path, prd: str, n: int) -> dict:
    """One cycle's entry from `<stem>-review-<n>.md` (bare first, then
    zero-padded); unreadable or unparseable (neither a `reviewers:` nor a
    `Verdict:` line) -> reviewers, verdict and findings all None."""
    stem = prd[:-3] if prd.endswith(".md") else prd
    text = None
    for name in (f"{stem}-review-{n}.md", f"{stem}-review-{n:02d}.md"):
        text = _read_text(reviews_dir / name)
        if text is not None:
            break
    if text is None:
        return {"cycle": n, "reviewers": None, "verdict": None, "findings": None}

    match = FRONTMATTER_REVIEWERS_RE.search(text)
    reviewers = (
        [r.strip() for r in match.group(1).split(",") if r.strip()] if match else None
    )

    match = VERDICT_RE.search(text)
    if reviewers is None and match is None:
        return {"cycle": n, "reviewers": None, "verdict": None, "findings": None}
    verdict: str | int | None = None
    if match:
        verdict = (
            "converged"
            if match.group(1) == "converged"
            else int(match.group(1).split()[0])
        )

    findings = {bucket: 0 for bucket in SEVERITY_MARKS.values()}
    for line in text.splitlines():
        if not CONSENSUS_ROW_RE.match(line):
            continue
        bucket = next((SEVERITY_MARKS[c] for c in line if c in SEVERITY_MARKS), None)
        if bucket is not None:
            findings[bucket] += 1

    return {"cycle": n, "reviewers": reviewers, "verdict": verdict, "findings": findings}


def outcome(state: dict) -> str:
    """`cap_deferred` when a cap-overflow deferral was recorded, else
    `converged`."""
    deferred = state.get("deferred_decisions") or []
    if any(isinstance(d, dict) and d.get("type") == "cap-overflow" for d in deferred):
        return "cap_deferred"
    return "converged"


def _build_models(session_rows: list[dict], prd: str, batch: str) -> list[str]:
    """Distinct non-empty models of `prd`'s build-phase sessions in `batch`,
    in first-appearance order."""
    models: list[str] = []
    for row in session_rows:
        model = row.get("model")
        if (
            row.get("prd") == prd
            and row.get("batch") == batch
            and row.get("phase_launched") == "build"
            and model
            and model not in models
        ):
            models.append(model)
    return models


def build_row(ap_dir: Path, state: dict, session_rows: list[dict], ts: int) -> dict:
    """The `review_converged` row for `state`; `ap_dir` is
    `<repo>/dev/local/autopilot`. Key order is the contract."""
    prd = state["prd"]
    batch = state["batch"]["id"]
    tasks = state.get("tasks") or []
    cycle = state.get("cycle")

    build_models = _build_models(session_rows, prd, batch)

    attempt_tiers: list[str] = []
    for task in tasks:
        for attempt in task.get("attempts") or []:
            model = attempt.get("model")
            if model and model not in attempt_tiers:
                attempt_tiers.append(model)

    planned = state.get("tasks_total")
    if not (isinstance(planned, int) and planned > 0):
        planned = len(tasks) if tasks else None
    completed = state.get("tasks_completed")
    if not (isinstance(completed, int) and completed > 0):
        completed = (
            sum(t.get("status") == "completed" for t in tasks) if tasks else None
        )

    prd_text = _read_text(ap_dir.parent / "prds" / "wip" / prd)
    reviews_dir = ap_dir.parent / "reviews"

    return {
        "event": "review_converged",
        "prd": prd,
        "batch": batch,
        "cycles_to_converge": cycle,
        "outcome": outcome(state),
        "ts": ts,
        "rework_cap": state.get("rework_cap"),
        "build_models": build_models,
        "attempt_tiers": attempt_tiers,
        "tasks_planned": planned,
        "tasks_completed": completed,
        "tasks_in_prd": None if prd_text is None else len(CHECKBOX_RE.findall(prd_text)),
        "cycles": [read_cycle(reviews_dir, prd, n) for n in range(1, (cycle or 0) + 1)],
    }
