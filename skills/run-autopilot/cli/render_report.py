#!/usr/bin/env python3
"""cli/render_report.py - render the batch-drain report (PRD 00107).

Deterministic layout from state + loop-metrics rows, replacing the prose
recipe in references/batch-report-format.md. Four blocks, all pure text
functions the CLI appends to `reports/{batch_id}-report.md`:

- `header(batch_id, started)` - written once at file creation.
- `prd_section(state, metrics_rows, completed, json_items=None)` - the
  per-PRD section phase-done Phase 9 step 7 appends: decisions tables,
  doubt rubric verdicts (source-tagged when dual-reviewer, PRD 00038), loop
  metrics (PRD 00013/00018), implementor mix (PRD 00019/00065/00075/00077),
  and the Deferred to Batch End table over the union of
  `state.deferred_decisions` and the batch deferred JSON's items for this
  PRD (`json_items`; PRD 00146).
- `missing_from_report(report_text, json_items, prd)` - the pending,
  unresolved JSON items the rendered section does not contain; the CLI
  exits 12 naming them (PRD 00146).
- `stalled_section(prd, site, detail, stamp)` - the short STALLED form.
- `batch_summary(state, metrics_rows, deferred_count)` - the batch-end
  block; duration from the batch's metrics rows when any exist, plus the
  skipped count and, when there are any, a `### Skipped` table of the
  eligibility-gate skips (PRD 00137).

Renders never fail the report: absent fields render blank cells, empty
arrays omit their section, missing metrics render the manual-run line, and
`batch.completed_prds` entries may be dicts (documented shape) or bare
filename strings (live legacy state) - both count toward the PRD total,
but any bare string makes the summary's cycle/decision sums unresolvable,
so those three lines render `?` (R2 of PRD 00122).
"""

from __future__ import annotations

from cli import render_metrics

_PREFLIGHT_ORDER = (
    "healthy",
    "pi_missing",
    "endpoint_unreachable",
    "model_id_missing",
    "completion_failed",
)
_PLAN_EXCLUSION_ORDER = ("ui", "tier", "files", "contract", "unknown")


def _cell(value) -> str:
    """Table-safe cell text: blank for None, pipes escaped."""
    return "" if value is None else str(value).replace("|", "\\|")


def _table(columns: list[str], rows: list[list]) -> list[str]:
    lines = [
        "| " + " | ".join(columns) + " |",
        "|" + "|".join("-" * (len(c) + 2) for c in columns) + "|",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_cell(v) for v in row) + " |")
    return lines


def header(batch_id: str, started: str) -> str:
    return f"# Autopilot Batch Report {batch_id}\n\nStarted: {started}\n"


def stalled_section(prd: str, site: str, detail: str, stamp: str) -> str:
    return (
        f"## {prd} — STALLED ({site})\n\n"
        f"- Stalled: {stamp}\n"
        f"- Detail: {detail}\n"
        f"- Resume: move back to dev/local/prds/wip/ and re-run\n"
    )


def _replace_section(existing: str, heading: str) -> str:
    """Drop every section starting at the exact line `heading` (up to the
    next "## "-prefixed line or EOF) from `existing`; a no-op when `heading`
    is not present as an exact line."""
    lines = existing.splitlines(keepends=True)
    while True:
        start = None
        for i, line in enumerate(lines):
            text = line.removesuffix("\n")
            if text == heading:
                start = i
                break
        if start is None:
            break
        end = start + 1
        while end < len(lines) and not lines[end].startswith("## "):
            end += 1
        del lines[start:end]
    return "".join(lines)


def _assumptions(decisions: list[dict]) -> list[str]:
    rows = [
        [d.get("question"), d.get("assumption")]
        for d in decisions
        if d.get("type") == "assumed-ambiguity"
    ]
    if not rows:
        return []
    return (
        ["### Assumptions Made", ""] + _table(["Question", "Assumption"], rows) + [""]
    )


def _autonomous_row(d: dict) -> list:
    return [
        d.get("cycle"),
        d.get("issue") or d.get("question"),
        d.get("severity"),
        d.get("action"),
        d.get("reason") or d.get("resolution"),
    ]


def is_autonomous_row(entry) -> bool:
    """True when the Autonomous Decisions table draws a row for `entry`: a
    dict whose `type` is not `"assumed-ambiguity"` (those land in Assumptions
    Made) with at least one non-empty cell (not None, not "") among the five
    the table renders. `statectl.complete-prd` counts with this same predicate
    so the write side and the render side agree."""
    return (
        isinstance(entry, dict)
        and entry.get("type") != "assumed-ambiguity"
        and any(cell is not None and cell != "" for cell in _autonomous_row(entry))
    )


def _autonomous(decisions: list[dict]) -> list[str]:
    rows = [_autonomous_row(d) for d in decisions if is_autonomous_row(d)]
    if not rows:
        return []
    return (
        ["### Autonomous Decisions", ""]
        + _table(["Cycle", "Issue", "Severity", "Action", "Reason"], rows)
        + [""]
    )


def _is_pending(decision: dict) -> bool:
    return decision.get("status", "pending") in ("pending", "deferred")


def is_escalated_row(entry) -> bool:
    """True when the Escalated Decisions table draws a row for `entry`: a
    dict whose `status` is anything other than `"pending"` (including
    absent) or `"deferred"`. `statectl.complete-prd` counts with this same
    predicate so the write side and the render side agree."""
    return isinstance(entry, dict) and not _is_pending(entry)


def _escalated(deferred: list[dict]) -> list[str]:
    rows = [
        [
            d.get("cycle"),
            d.get("issue"),
            d.get("severity"),
            d.get("status"),
            d.get("user_decision"),
        ]
        for d in deferred
        if is_escalated_row(d)
    ]
    if not rows:
        return []
    return (
        ["### Escalated Decisions", ""]
        + _table(["Cycle", "Issue", "Severity", "Resolution", "User Decision"], rows)
        + [""]
    )


def _normalize(text) -> str:
    """Whitespace-collapsed, case-folded text: the dedup and reconciliation key."""
    return " ".join(str(text).split()).casefold()


def _is_open(entry: dict) -> bool:
    """Pending and not carrying a `resolved` block. Lives here and not in
    `_is_pending`, whose negation `is_escalated_row` is how statectl counts
    `escalated_decisions`."""
    return _is_pending(entry) and not entry.get("resolved")


def _merge_deferral_sinks(
    state_deferrals: list[dict],
    json_items: list[dict],
) -> list[dict]:
    """Union of both deferral sinks for one PRD: open entries deduplicated on
    normalized issue text, state entries first. A cap-overflow record with
    neither `disposition` nor `reason` (the pre-00146 record shape) gets a
    Reason synthesized from whichever of cycle and consensus it carries."""
    merged: dict[str, dict] = {}
    for entry in [*state_deferrals, *json_items]:
        key = _normalize(entry.get("issue", ""))
        if not _is_open(entry) or key in merged:
            continue
        if entry.get("type") == "cap-overflow" and not (
            entry.get("disposition") or entry.get("reason")
        ):
            detail = ", ".join(
                f"{k} {entry[k]}"
                for k in ("cycle", "consensus")
                if entry.get(k) is not None
            )
            reason = "rework cap reached with this finding unresolved"
            entry = {**entry, "reason": f"{reason} ({detail})" if detail else reason}
        merged[key] = entry
    return list(merged.values())


def missing_from_report(
    report_text: str, json_items: list[dict], prd: str
) -> list[dict]:
    """The open deferred-JSON items for `prd` whose issue text does not
    occur in `report_text` (both normalized the way the table renders
    them). An item without issue text is always missing: it cannot be
    found, so it fails loud instead of being dropped."""
    haystack = _normalize(report_text)
    missing = []
    for item in json_items:
        if not isinstance(item, dict) or item.get("prd") != prd or not _is_open(item):
            continue
        needle = _normalize(_cell(item.get("issue")))
        if not needle or needle not in haystack:
            missing.append(item)
    return missing


def _deferred_to_batch_end(deferred: list[dict]) -> list[str]:
    rows = [
        [d.get("issue"), d.get("severity"), d.get("disposition") or d.get("reason")]
        for d in deferred
        if _is_pending(d)
    ]
    if not rows:
        return []
    return (
        ["### Deferred to Batch End", ""]
        + _table(["Issue", "Severity", "Reason"], rows)
        + [""]
    )


def _doubt_findings(doubts: list[dict]) -> list[str]:
    rows = [[d.get("description"), d.get("severity"), d.get("status")] for d in doubts]
    if not rows:
        return []
    return (
        ["### Doubt Review Findings", ""]
        + _table(["Issue", "Severity", "Status"], rows)
        + [""]
    )


def _rubric_verdicts(verdicts: list[dict]) -> list[str]:
    """One row per rule; source-tagged combining on dual-reviewer runs
    (PRD 00038): `pass (codex) / fail (fable)`. Single-reviewer/legacy
    entries render one plain verdict per rule."""
    if not verdicts:
        return []
    by_rule: dict[str, list[dict]] = {}
    for entry in verdicts:
        by_rule.setdefault(str(entry.get("rule_id", "?")), []).append(entry)
    tagged = any("source" in entry for entry in verdicts)
    rows = []
    for rule_id, entries in by_rule.items():
        if tagged:
            cell = " / ".join(
                f"{e.get('verdict', '?')} ({e['source']})"
                if "source" in e
                else str(e.get("verdict", "?"))
                for e in sorted(entries, key=lambda e: str(e.get("source", "")))
            )
        else:
            cell = str(entries[0].get("verdict", "?"))
        rows.append([rule_id, cell])
    return ["### Doubt Rubric Verdicts", ""] + _table(["Rule", "Verdict"], rows) + [""]


def _implementor_table(attempts: list[dict]) -> list[str]:
    counts: dict[str, int] = {}
    for attempt in attempts:
        counts[attempt.get("implementor") or "unknown"] = (
            counts.get(attempt.get("implementor") or "unknown", 0) + 1
        )
    order = ["claude", "qwen", "gemini", "codex", "unknown"]
    rows = [[name, counts[name]] for name in order if counts.get(name)]
    rows += [[name, n] for name, n in counts.items() if name not in order]
    return _table(["Implementor", "Attempts"], rows) + [""]


def _preflight_outcomes_line(attempts: list[dict]) -> str | None:
    preflight: dict[str, int] = {}
    for attempt in attempts:
        outcome = attempt.get("preflight_outcome")
        if outcome is not None:
            preflight[outcome] = preflight.get(outcome, 0) + 1
    if not preflight:
        return None
    ordered = [o for o in _PREFLIGHT_ORDER if o in preflight] + sorted(
        o for o in preflight if o not in _PREFLIGHT_ORDER
    )
    return "Qwen preflight outcomes: " + ", ".join(
        f"{o} {preflight[o]}" for o in ordered
    )


def _exclusion_line(tasks: list[dict]) -> str | None:
    """Exclusion line: two populations sharing one line (batch-report format
    § Exclusion line) — plan-time buckets over ineligible tasks, then
    dispatch-time memory reroutes deduplicated by task."""
    plan: dict[str, int] = {}
    for task in tasks:
        if not task.get("qwen_eligible"):
            reason = task.get("qwen_excluded_reason") or "unknown"
            plan[reason] = plan.get(reason, 0) + 1
    dispatch: dict[str, int] = {}
    for bucket in ("memory_pressure", "memory_probe_failed"):
        hit = sum(
            1
            for task in tasks
            if any(
                a.get("qwen_excluded_reason") == bucket
                for a in (task.get("attempts") or [])
            )
        )
        if hit:
            dispatch[bucket] = hit
    if not (plan or dispatch):
        return None
    ordered = [b for b in _PLAN_EXCLUSION_ORDER if b in plan] + sorted(
        b for b in plan if b not in _PLAN_EXCLUSION_ORDER
    )
    plan_part = (
        ", ".join(f"{b} {plan[b]}" for b in ordered) + " (plan-time)"
        if plan
        else "none (plan-time)"
    )
    dispatch_part = (
        ", ".join(f"{b} {n}" for b, n in dispatch.items()) if dispatch else "none"
    )
    return f"Excluded from qwen: {plan_part}; dispatch-time reroutes: {dispatch_part}"


def _probe_line(state: dict) -> str:
    probe = state.get("codex_probe") or {}
    batch_id = (state.get("batch") or {}).get("id")
    if not probe or probe.get("batch_id") != batch_id:
        probe_line = "codex probe: not run"
    elif probe.get("verdict") == "unhealthy":
        probe_line = (
            f"codex probe: unhealthy (backend: {probe.get('backend')}; "
            f"detail: {probe.get('detail')})"
        )
    else:
        probe_line = (
            f"codex probe: {probe.get('verdict')} (backend: {probe.get('backend')})"
        )
    hook_doctor = probe.get("hook_doctor")
    if hook_doctor:
        probe_line += f"; hooks: {hook_doctor}"
    return probe_line


def _breaker_line(state: dict, attempts: list[dict]) -> str:
    breaker = state.get("qwen_breaker") or {}
    if not breaker.get("tripped"):
        return "capability breaker: not tripped"
    failed = breaker.get("failed_tasks") or ["?", "?"]
    rerouted = sum(1 for a in attempts if a.get("breaker_skipped"))
    return (
        f"capability breaker: tripped after {breaker.get('after_task')} "
        f"(2 consecutive gate failures: {failed[0]}, {failed[1]}); "
        f"{rerouted} tasks rerouted"
    )


def _implementor_mix(state: dict) -> list[str]:
    tasks = state.get("tasks") or []
    lines = ["### Implementor Mix", ""]
    if not tasks:
        return lines + ["no implementor data", ""]

    attempts = [a for t in tasks for a in (t.get("attempts") or [])]
    lines += _implementor_table(attempts)

    preflight_line = _preflight_outcomes_line(attempts)
    if preflight_line:
        lines.append(preflight_line)

    exclusion_line = _exclusion_line(tasks)
    if exclusion_line:
        lines.append(exclusion_line)

    lines.append(_probe_line(state))
    lines.append(_breaker_line(state, attempts))
    lines.append("")
    return lines


def prd_section(
    state: dict,
    metrics_rows: list[dict],
    completed: str,
    json_items: list[dict] | None = None,
) -> str:
    """The completed-PRD section appended at Phase 9 step 7. `json_items`
    are the batch deferred JSON's items for this PRD (already filtered by
    the caller); the Deferred to Batch End table renders their union with
    `state.deferred_decisions`."""
    prd = str(state.get("prd", ""))
    autonomous = [
        d for d in state.get("autonomous_decisions") or [] if isinstance(d, dict)
    ]
    deferred = [d for d in state.get("deferred_decisions") or [] if isinstance(d, dict)]
    doubts = [d for d in state.get("doubts") or [] if isinstance(d, dict)]
    completed_prds = (state.get("batch") or {}).get("completed_prds") or []
    record = next(
        (p for p in completed_prds if isinstance(p, dict) and p.get("filename") == prd),
        None,
    )
    if record is not None:
        tasks_line = (
            f"{record.get('tasks_completed', '?')}/{record.get('tasks_total', '?')}"
        )
    else:
        tasks = state.get("tasks") or []
        if tasks:
            done = sum(1 for t in tasks if t.get("status") == "completed")
            tasks_line = f"{done}/{len(tasks)}"
        else:
            tasks_line = "?/?"
    lines = [
        f"## {prd}",
        "",
        f"- Completed: {completed}",
        f"- Cycles: {state.get('cycle', '?')}",
        f"- Tasks: {tasks_line}",
        "",
    ]
    lines += _assumptions(autonomous)
    lines += _autonomous(autonomous)
    lines += _escalated(deferred)
    lines += _doubt_findings(doubts)
    lines += _rubric_verdicts(state.get("doubts_rubric_verdicts") or [])
    lines += ["### Loop Metrics", "", render_metrics.phase_table(metrics_rows), ""]
    lines += _implementor_mix(state)
    lines += _deferred_to_batch_end(_merge_deferral_sinks(deferred, json_items or []))
    return "\n".join(lines)


def _batch_rows(batch_id: str, metrics_rows: list[dict]) -> list[dict]:
    return [r for r in metrics_rows if r.get("batch") == batch_id]


def _iso(ts: int) -> str:
    from datetime import datetime, timezone

    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _started_iso(batch_id: str, batch_rows: list[dict]) -> str:
    if batch_rows:
        return _iso(min(int(r.get("ts_start", 0)) for r in batch_rows))
    return (
        f"{batch_id[0:4]}-{batch_id[4:6]}-{batch_id[6:8]}T"
        f"{batch_id[8:10]}:{batch_id[10:12]}:00Z"
    )


def batch_started(state: dict, metrics_rows: list[dict]) -> str:
    """The batch's started timestamp: earliest `ts_start` across the
    batch's metrics rows as UTC ISO-8601, or the `batch_id` (`yyyymmddHHMM`)
    parsed directly when no rows exist yet."""
    batch_id = (state.get("batch") or {}).get("id")
    return _started_iso(batch_id, _batch_rows(batch_id, metrics_rows))


def batch_summary(
    state: dict,
    metrics_rows: list[dict],
    deferred_count: int | None = None,
) -> str:
    """The batch-completion block. Cycle/decision sums need every
    `completed_prds` entry dict-shaped; a bare-string entry (live legacy
    state) makes them unresolvable, so those three lines render `?` (R2 of
    PRD 00122). The PRD total still counts bare-string entries."""
    batch = state.get("batch") or {}
    completed = batch.get("completed_prds") or []
    resolvable = all(isinstance(p, dict) for p in completed)

    def _sum(key: str) -> int | str:
        return sum(p.get(key, 0) for p in completed) if resolvable else "?"

    skips = batch.get("skips") or []
    lines = [
        "## Batch Summary",
        "",
        f"- PRDs completed: {len(completed)}",
        # Always rendered, zero included: a drain that skipped everything must
        # read as "N skipped", never as a silent 0-done batch.
        f"- PRDs skipped: {len(skips)}",
        f"- Total cycles: {_sum('cycles')}",
        f"- Autonomous decisions: {_sum('autonomous_decisions')}",
        f"- Escalated decisions: {_sum('escalated_decisions')}",
    ]
    if deferred_count is not None:
        lines.append(f"- Deferred items: {deferred_count}")
    batch_id = batch.get("id")
    batch_rows = _batch_rows(batch_id, metrics_rows)
    if batch_rows:
        last_iso = _iso(max(int(r.get("ts_end", 0)) for r in batch_rows))
        lines.append(f"- Duration: {_started_iso(batch_id, batch_rows)} to {last_iso}")
    if skips:
        lines += ["", "### Skipped", ""]
        lines += _table(
            ["PRD", "Exit code", "Command"],
            [[s.get("prd"), s.get("exit_code"), s.get("command")] for s in skips],
        )
    lines.append("")
    return "\n".join(lines)
