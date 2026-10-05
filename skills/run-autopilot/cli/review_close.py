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
# agents: status -> review_lenses state. "disabled" names a persona the
# roster never included (never invoked, so not a failed attempt); anything
# else unlisted (e.g. "unavailable") stays "failed".
_LENS_STATUS = {"available": "done", "disabled": "skipped"}
# agents: status -> the dispatch row's closing --outcome (SKILL.md step 6's
# attempt-outcome table). A persona absent from the agents: block at all
# (status None) defaults to "ok", same as the prior hardcoded value.
_DISPATCH_OUTCOME = {"available": "ok", "unavailable": "error", "timeout": "timeout"}
_NO_ROW = ("", "null", "None")
# A finding's severity is one of rework_groups.py's emoji; schema.py's
# DECISION_SEVERITIES vocabulary for an `autonomous_decisions` entry is the
# lowercase word instead.
_DECISION_SEVERITY = {
    "\U0001f534": "critical",
    "\U0001f7e0": "high",
    "\U0001f7e1": "medium",
    "⚪": "low",
}


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


def _end_dispatch_rows(rows: list[tuple[str, str]], cwd: Path) -> None:
    """Best-effort: a row left open is re-ended by a later call, never raised."""
    for row_id, outcome in rows:
        try:
            subprocess.run(
                [
                    sys.executable,
                    str(_RECORD_DISPATCH),
                    "end",
                    row_id,
                    "--outcome",
                    outcome,
                ],
                cwd=cwd,
                check=True,
                capture_output=True,
                timeout=30,
            )
        except (OSError, subprocess.SubprocessError) as err:
            sys.stderr.write(f"review_close: dispatch row {row_id} not ended: {err}\n")


def _dispatch_outcomes(frontmatter: list[str]) -> list[tuple[str, str]]:
    """(row id, --outcome) for every open `dispatch_rows:` entry, the
    outcome read from that persona's `agents:` status."""
    agents = _nested_pairs(frontmatter, "agents")
    rows = _nested_pairs(frontmatter, "dispatch_rows")
    return [
        (row_id, _DISPATCH_OUTCOME.get(agents.get(persona), "ok"))
        for persona, row_id in rows.items()
        if row_id not in _NO_ROW
    ]


def _lens_states(frontmatter: list[str]) -> dict[str, str]:
    """`review_lenses` state per lens, from the `agents:` status of every
    persona that lens maps to."""
    return {
        _PERSONA_LENS.get(name, name): _LENS_STATUS.get(status, "failed")
        for name, status in _nested_pairs(frontmatter, "agents").items()
    }


def _gate_refusal(review_file: Path, text: str | None, reviewer_csv: str | None) -> str:
    """The one-line reason a gate-failing review file is refused."""
    if text is None:
        return f"missing or unreadable review file {review_file}"
    reviewers = [r for r in (reviewer_csv or "").split(",") if r.strip()]
    return gate.check(text, reviewers) or "review gate failed"


def _gate_review(
    review_file: Path,
    require_codex_guard: bool,
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
        review_file,
        reviewers=reviewer_csv,
        require_codex_guard=require_codex_guard,
    )
    # run_gate fails open (0) on an unreadable file; close() cannot, since it
    # has nothing to apply.
    if rc != 0 or text is None:
        return text, _gate_refusal(review_file, text, reviewer_csv)
    return text, None


def _add_rework_tasks(
    state: dict,
    fixes: list[dict],
    prefix: str,
    default_tier: str,
) -> list[str]:
    """One rework task per `rework_groups.group` group; returns the created ids."""
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
    return created


def _add_decisions(state: dict, fixes: list[dict], defers: list[dict]) -> None:
    """`deferred_decisions` for every defer row, `autonomous_decisions` for
    every fix row (the rework task itself is recorded separately)."""
    cycle = state.get("cycle", 1)
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
    for f in fixes:
        severity = f["severity"]
        statectl.do_append(
            state,
            statectl.parse_path("autonomous_decisions"),
            {
                "cycle": cycle,
                "issue": f["issue"],
                "severity": _DECISION_SEVERITY.get(severity, severity.lower()),
                "action": "auto-fixed",
                "reason": "fixed by review-close",
            },
        )


def _set_lens_state(
    state: dict,
    batch_id: str,
    verdicts: list[dict],
    lenses: dict[str, str],
) -> None:
    """Tail sweeps never touch the doubt verdicts or the lens close-out."""
    if batch_id == "tail-sweep":
        return
    if verdicts:
        statectl.do_set(state, statectl.parse_path("doubts_rubric_verdicts"), verdicts)
    for lens, status in lenses.items():
        statectl.do_set(state, statectl.parse_path(f"review_lenses.{lens}"), status)


def _close_mutator(ctx: dict[str, Any]):
    """The `statectl.mutate()` callback that applies one classified batch.

    `ctx` carries identity, fixes, defers, prefix, default_tier, batch_id,
    verdicts, lenses and outcome (the same values the old positional
    signature took, now as one object)."""

    def _apply(state: dict) -> dict:
        identity = ctx["identity"]
        outcome = ctx["outcome"]
        if identity in state.get("applied_review_batches", []):
            outcome["already"] = True
            return state
        created = _add_rework_tasks(
            state, ctx["fixes"], ctx["prefix"], ctx["default_tier"]
        )
        _add_decisions(state, ctx["fixes"], ctx["defers"])
        _set_lens_state(state, ctx["batch_id"], ctx["verdicts"], ctx["lenses"])
        statectl.do_append(
            state, statectl.parse_path("applied_review_batches"), identity
        )
        outcome["created"] = created
        outcome["rework_task_ids"] = list(state.get("rework_task_ids", []))
        return state

    return _apply


def _mutation_context(
    review_file: Path,
    text: str,
    frontmatter: list[str],
    batch_id: str,
    chosen_findings: list[dict],
    default_tier: str,
) -> dict[str, Any]:
    """The `_close_mutator` ctx for one batch: the apply-once identity, the
    findings split by classification, the doubt verdicts, the lens states and
    the empty `outcome` the mutator writes back through."""
    return {
        "identity": f"{review_file.resolve()}::{batch_id}",
        "fixes": [f for f in chosen_findings if f["classification"] == "fix"],
        "defers": [f for f in chosen_findings if f["classification"] == "defer"],
        "prefix": "Tail sweep: " if batch_id == "tail-sweep" else "",
        "default_tier": default_tier,
        "batch_id": batch_id,
        "verdicts": [
            {"rule_id": rule, "verdict": verdict}
            for rule, verdict in _DOUBT_RE.findall(text)
        ],
        "lenses": _lens_states(frontmatter),
        "outcome": {},
    }


def _close_result(ctx: dict[str, Any], cross_check: str | None) -> dict:
    """The applied-result dict for a committed batch."""
    outcome = ctx["outcome"]
    result = {
        "applied": True,
        "tasks_created": outcome["created"],
        "rework_task_ids": outcome["rework_task_ids"],
        "lenses_closed": ctx["lenses"],
    }
    if cross_check == "malformed":
        # Surfaced, never refused: a legacy review file carries no
        # consolidated-findings section, and refusing it would be a
        # behaviour change of its own.
        result["findings_cross_check"] = cross_check
    return result


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

    A chosen finding the review file's consolidated-findings section never
    recorded is refused before any lock, with "refused": "findings_mismatch".
    A review file carrying no such section is not refused: the fact lands on
    the applied result as "findings_cross_check": "malformed".
    """
    review_file = Path(review_file)
    state_path = Path(state_path)
    text, refusal = _gate_review(review_file, require_codex_guard)
    if refusal is not None:
        return {"applied": False, "reason": refusal}
    cross_check, detail = gate._cross_check_findings(text, chosen_findings)
    if cross_check == "mismatch":
        return {"applied": False, "refused": "findings_mismatch", "reason": detail}

    frontmatter = _frontmatter_lines(text)
    ctx = _mutation_context(
        review_file, text, frontmatter, batch_id, chosen_findings, default_tier
    )
    statectl.mutate(state_path, _close_mutator(ctx))
    if ctx["outcome"].get("already"):
        return {"applied": False, "reason": "already applied"}

    if batch_id != "tail-sweep":
        _end_dispatch_rows(_dispatch_outcomes(frontmatter), state_path.parent)
    return _close_result(ctx, cross_check)
