#!/usr/bin/env python3
"""review_close.py - apply a classified review to state.json (PRD 00249).

    close(review_file, state_path, batch_id, chosen_findings) -> dict

The review file must first pass the shape gate (`gate.run_gate`); a failing
file is refused before any lock is taken. Everything else lands in ONE
`statectl.mutate()` transaction: rework tasks for the "fix" findings (one per
`rework_groups.group` group), `rework_task_ids`, `deferred_decisions` for the
"defer" findings, the doubt-rubric verdicts, the lens close-out, and the
`applied_review_batches` stamp. The idempotency check reads that stamp INSIDE
the lock, so two racing calls for the same `<review path>::<batch_id>` apply
once. Closing the stage-time dispatch rows comes after the commit and is
best-effort: they are telemetry, never part of the state's atomicity.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from . import gate, rework_groups, statectl

_RECORD_DISPATCH = (
    Path(__file__).resolve().parents[2] / "work" / "scripts" / "record_dispatch.py"
)
_DOUBT_RE = re.compile(r"^(D\d+):\s+(pass|fail)\s*$", re.MULTILINE)
# The `agents:` block names personas; `review_lenses` is keyed by lens
# (state-schema.md: consensus=Alice, blind=Blake, doubt=Bob, ui=Carl,
# fable=Eve). A key that is already a lens name passes through unchanged.
_PERSONA_LENS = {
    "alice": "consensus",
    "blake": "blind",
    "bob": "doubt",
    "carl": "ui",
    "eve": "fable",
}
_NO_ROW = ("", "null", "None")


def _frontmatter_lines(text: str) -> list[str]:
    """The lines between the opening `---` line and the next `---` line."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return []
    for end, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return lines[1:end]
    return []


def _nested_pairs(frontmatter: list[str], key: str) -> dict[str, str]:
    """The indented `name: value` lines under a top-level `key:` line."""
    pairs: dict[str, str] = {}
    inside = False
    for line in frontmatter:
        if not line.startswith((" ", "\t")):
            inside = line.strip() == f"{key}:"
            continue
        if inside and ":" in line:
            name, _, value = line.strip().partition(":")
            pairs[name.strip()] = value.strip()
    return pairs


def _findings_block(findings: list[dict]) -> str:
    lines = []
    for f in findings:
        found_by = f.get("found_by") or []
        suffix = f" (found by: {', '.join(found_by)})" if found_by else ""
        lines.append(f"- {f['severity']} {f['file']}: {f['issue']}{suffix}")
    return "### Findings (verbatim)\n" + "\n".join(lines) + "\n"


def _end_dispatch_rows(row_ids: list[str], cwd: Path) -> None:
    """Best-effort: a row left open is re-ended by a later call, never raised."""
    for row_id in row_ids:
        try:
            subprocess.run(
                [sys.executable, str(_RECORD_DISPATCH), "end", row_id, "--outcome", "ok"],
                cwd=cwd,
                check=True,
                capture_output=True,
                timeout=30,
            )
        except (OSError, subprocess.SubprocessError) as err:
            sys.stderr.write(f"review_close: dispatch row {row_id} not ended: {err}\n")


def _gate_refusal(review_file: Path, text: str | None, reviewer_csv: str | None) -> str:
    """The one-line reason a gate-failing review file is refused."""
    if text is None:
        return f"missing or unreadable review file {review_file}"
    reviewers = [r for r in (reviewer_csv or "").split(",") if r.strip()]
    return gate.check(text, reviewers) or "review gate failed"


def _gate_review(
    review_file: Path, require_codex_guard: bool
) -> tuple[str | None, str | None]:
    """Read and shape-gate `review_file`. Returns (text, None) when it may be
    applied, or (text-or-None, refusal reason) when close() must refuse."""
    try:
        text: str | None = review_file.read_text(encoding="utf-8")
    except OSError:
        text = None
    reviewers = gate.FRONTMATTER_REVIEWERS_RE.search(text or "")
    reviewer_csv = reviewers.group(1) if reviewers else None
    rc = gate.run_gate(
        review_file, reviewers=reviewer_csv, require_codex_guard=require_codex_guard
    )
    # run_gate fails open (0) on an unreadable file; close() cannot, since it
    # has nothing to apply.
    if rc != 0 or text is None:
        return text, _gate_refusal(review_file, text, reviewer_csv)
    return text, None


def _close_mutator(
    identity: str,
    fixes: list[dict],
    defers: list[dict],
    prefix: str,
    default_tier: str,
    batch_id: str,
    verdicts: list[dict],
    lenses: dict[str, str],
    outcome: dict[str, Any],
):
    """The `statectl.mutate()` callback that applies one classified batch."""

    def _apply(state: dict) -> dict:
        if identity in state.get("applied_review_batches", []):
            outcome["already"] = True
            return state
        cycle = state.get("cycle", 1)
        created = [
            statectl.do_task_add(
                state,
                {
                    "name": f"[D{cycle}] {prefix}{grp['name_hint']}",
                    "description": _findings_block(grp["findings"]),
                    "model": default_tier,
                },
            )
            for grp in (rework_groups.group(fixes) if fixes else [])
        ]
        for task_id in created:
            statectl.do_append(state, statectl.parse_path("rework_task_ids"), task_id)
        for f in defers:
            statectl.do_append(
                state,
                statectl.parse_path("deferred_decisions"),
                {
                    "issue": f["issue"],
                    "severity": f["severity"],
                    "file": f["file"],
                    "reason": "deferred by review-close",
                },
            )
        if batch_id != "tail-sweep":
            if verdicts:
                statectl.do_set(
                    state, statectl.parse_path("doubts_rubric_verdicts"), verdicts
                )
            for lens, status in lenses.items():
                statectl.do_set(
                    state, statectl.parse_path(f"review_lenses.{lens}"), status
                )
        statectl.do_append(state, statectl.parse_path("applied_review_batches"), identity)
        outcome["created"] = created
        outcome["rework_task_ids"] = list(state.get("rework_task_ids", []))
        return state

    return _apply


def close(
    review_file: Path,
    state_path: Path,
    batch_id: str,
    chosen_findings: list[dict],
    default_tier: str = "sonnet",
    require_codex_guard: bool = False,
) -> dict:
    """Apply one classified review batch to `state_path`, at most once.

    Returns {"applied": True, "tasks_created", "rework_task_ids" (the state's
    whole list after the write), "lenses_closed"}, or {"applied": False,
    "reason"} when the review file fails the shape gate, cannot be read, or
    this batch was already applied.
    """
    review_file = Path(review_file)
    state_path = Path(state_path)
    text, refusal = _gate_review(review_file, require_codex_guard)
    if refusal is not None:
        return {"applied": False, "reason": refusal}

    identity = f"{review_file.resolve()}::{batch_id}"
    frontmatter = _frontmatter_lines(text)
    verdicts = [
        {"rule_id": rule, "verdict": verdict} for rule, verdict in _DOUBT_RE.findall(text)
    ]
    lenses = {
        _PERSONA_LENS.get(name, name): "done" if status == "available" else "failed"
        for name, status in _nested_pairs(frontmatter, "agents").items()
    }
    fixes = [f for f in chosen_findings if f["classification"] == "fix"]
    defers = [f for f in chosen_findings if f["classification"] == "defer"]
    prefix = "Tail sweep: " if batch_id == "tail-sweep" else ""
    outcome: dict[str, Any] = {}

    statectl.mutate(
        state_path,
        _close_mutator(
            identity, fixes, defers, prefix, default_tier, batch_id, verdicts, lenses, outcome
        ),
    )
    if outcome.get("already"):
        return {"applied": False, "reason": "already applied"}

    if batch_id != "tail-sweep":
        rows = _nested_pairs(frontmatter, "dispatch_rows").values()
        _end_dispatch_rows([r for r in rows if r not in _NO_ROW], state_path.parent)
    return {
        "applied": True,
        "tasks_created": outcome["created"],
        "rework_task_ids": outcome["rework_task_ids"],
        "lenses_closed": lenses,
    }
