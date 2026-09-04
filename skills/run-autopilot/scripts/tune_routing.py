#!/usr/bin/env python3
"""Propose routing rule changes from recorded outcomes (PRD 00170).

Reads `dev/local/autopilot/ledger/attempts.jsonl`, computes three signals
(S1 mechanical-row escalation rate, S2 repair-budget completion rate, S3
codex-rung failure rate) plus a report-only escalation-by-reason table, and
writes a markdown proposal (`routing-proposal-<date>.md`) and, when S1
proposes, a unified-diff patch (`routing-proposal-<date>.patch`) against
`skills/plan-tasks/scripts/classify_tier.py`.

Propose-only: the tuner never edits a rule surface, never touches
state.json, never runs git, never sets a kill-switch, and never writes
outside `--out-dir`. Below the per-signal minimum-sample floor it emits an
honest HOLD naming how many more rows are needed, never a guessed verdict.

Stdlib only. Self-contained apart from the shared `_walk_up` helper.

CLI:
    tune_routing.py [--ledger PATH] [--classifier PATH] [--out-dir DIR]
                     [--date YYYY-MM-DD]

Exit codes:
    0  a proposal was written (every signal PROPOSE or HOLD).
    1  the ledger could not be read, every row was UNPARSED, or the
       proposal could not be written.
    2  bad arguments (argparse).
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _walk_up import find_autopilot_dir

MIN_ROWS = 12
S1_ESCALATION_RATE = 0.5
S2_COMPLETED_RATE = 0.5
S3_FAILURE_RATE = 0.5
MECHANICAL_LINES_LITERAL = "_MECHANICAL_MAX_LINES"

# opus and operator floors are out of tuning scope (PRD 00170 § Signal
# extraction); S2 and S3 skip rows carrying these tier reasons so a
# contract/algorithmic_risk/floor row can never move a signal even though
# it is filtered on attempt fields only. S1 needs no such guard: its filter
# already requires task_tier_reason == "mechanical".
_OUT_OF_SCOPE_REASONS = frozenset({"contract", "algorithmic_risk", "floor"})

_REPORT_REASONS = (
    "contract", "algorithmic_risk", "floor", "test_port",
    "packaging", "default", "mechanical", "unattributed",
)


def _reason(row: dict) -> str:
    """The row's tier reason, `"unattributed"` when absent or null."""
    value = row.get("task_tier_reason")
    return value if isinstance(value, str) else "unattributed"


def parse_rows(text: str) -> tuple[list[dict], list[str]]:
    """Parse ledger JSONL text into `(rows, unparsed_reasons)`.

    Every non-blank line must parse as a JSON object carrying a dict
    `attempt`, a `task_model` key (value may be null), `attempt["outcome"]`
    (value may be null) and an int `attempt["attempt"]` (the dedupe key and
    the S1/S3 rung index); a line failing any check is dropped and recorded
    as an `"line <n>: UNPARSED: <field>"` reason.
    """
    rows: list[dict] = []
    reasons: list[str] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            reasons.append(f"line {lineno}: UNPARSED: json")
            continue
        if not isinstance(obj, dict):
            reasons.append(f"line {lineno}: UNPARSED: json")
            continue
        attempt = obj.get("attempt")
        if not isinstance(attempt, dict):
            reasons.append(f"line {lineno}: UNPARSED: attempt")
            continue
        if "task_model" not in obj:
            reasons.append(f"line {lineno}: UNPARSED: task_model")
            continue
        if "outcome" not in attempt:
            reasons.append(f"line {lineno}: UNPARSED: attempt.outcome")
            continue
        if not isinstance(attempt.get("attempt"), int):
            reasons.append(f"line {lineno}: UNPARSED: attempt.attempt")
            continue
        rows.append(obj)
    return rows, reasons


def dedupe_rows(rows: list[dict]) -> list[dict]:
    """Drop rows sharing `(batch_id, prd, task_id, attempt.attempt)`.

    First occurrence wins, preserving file order (PRD 00170, `state-schema.md`
    § Attempt ledger dedupe key).
    """
    seen: set[tuple] = set()
    deduped: list[dict] = []
    for row in rows:
        key = (row.get("batch_id"), row.get("prd"), row.get("task_id"),
               row["attempt"].get("attempt"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def load_rows(path: Path) -> tuple[list[dict], list[str]]:
    """Read, parse and dedupe the ledger at `path`.

    Raises `OSError` when `path` cannot be read; the caller (`main`) turns
    that into the `cannot read ledger` exit.
    """
    text = path.read_text(encoding="utf-8")
    rows, reasons = parse_rows(text)
    return dedupe_rows(rows), reasons


def _signal_s1(rows: list[dict]) -> dict:
    matched = [r for r in rows
               if _reason(r) == "mechanical" and r["attempt"].get("attempt") == 1]
    n = len(matched)
    escalated = sum(1 for r in matched if r["attempt"].get("outcome") == "escalated")
    rate = escalated / n if n else 0.0
    unattributed = sum(1 for r in rows
                        if r["attempt"].get("attempt") == 1 and _reason(r) == "unattributed")
    verdict = "PROPOSE" if n >= MIN_ROWS and rate >= S1_ESCALATION_RATE else "HOLD"
    prds = sorted({r["prd"] for r in matched if r.get("prd") is not None})
    return {
        "verdict": verdict, "n": n, "rate": rate, "prds": prds,
        "needed": max(0, MIN_ROWS - n), "unattributed": unattributed,
    }


def _signal_s2(rows: list[dict]) -> dict:
    matched = [r for r in rows
               if _reason(r) not in _OUT_OF_SCOPE_REASONS
               and r["attempt"].get("repair_used") is True]
    n = len(matched)
    completed = sum(1 for r in matched if r["attempt"].get("outcome") == "completed")
    rate = completed / n if n else 0.0
    verdict = "PROPOSE" if n >= MIN_ROWS and rate < S2_COMPLETED_RATE else "HOLD"
    prds = sorted({r["prd"] for r in matched if r.get("prd") is not None})
    return {
        "verdict": verdict, "n": n, "rate": rate, "prds": prds,
        "needed": max(0, MIN_ROWS - n),
    }


def _s3_escalated_next(matched: list[dict], rows: list[dict]) -> int:
    """Count `matched` rows whose same-task next attempt escalated from codex."""
    by_key = {}
    for r in rows:
        key = (r.get("batch_id"), r.get("prd"), r.get("task_id"),
               r["attempt"].get("attempt"))
        by_key[key] = r
    escalated = 0
    for r in matched:
        attempt_no = r["attempt"]["attempt"]
        key = (r.get("batch_id"), r.get("prd"), r.get("task_id"), attempt_no + 1)
        nxt = by_key.get(key)
        if nxt is not None and nxt["attempt"].get("escalated_from") == "codex":
            escalated += 1
    return escalated


def _signal_s3(rows: list[dict]) -> dict:
    matched = [r for r in rows
               if _reason(r) not in _OUT_OF_SCOPE_REASONS
               and r["attempt"].get("implementor") == "codex"]
    n = len(matched)
    no_edit = sum(1 for r in matched if r["attempt"].get("cause") == "codex_no_edit")
    escalated = _s3_escalated_next(matched, rows)
    no_edit_rate = no_edit / n if n else 0.0
    escalated_rate = escalated / n if n else 0.0
    verdict = "PROPOSE" if n >= MIN_ROWS and (
        no_edit_rate >= S3_FAILURE_RATE or escalated_rate >= S3_FAILURE_RATE
    ) else "HOLD"
    prds = sorted({r["prd"] for r in matched if r.get("prd") is not None})
    return {
        "verdict": verdict, "n": n, "rate": max(no_edit_rate, escalated_rate),
        "no_edit_rate": no_edit_rate, "escalated_rate": escalated_rate,
        "prds": prds, "needed": max(0, MIN_ROWS - n),
    }


def _report(rows: list[dict]) -> dict:
    counts = {reason: 0 for reason in _REPORT_REASONS}
    for r in rows:
        if r["attempt"].get("outcome") == "escalated":
            reason = _reason(r)
            counts[reason] = counts.get(reason, 0) + 1
    return {"escalations_by_reason": counts}


def signals(rows: list[dict]) -> dict[str, dict]:
    """Aggregate deduped ledger `rows` into `S1`, `S2`, `S3` and `report`."""
    return {
        "S1": _signal_s1(rows), "S2": _signal_s2(rows),
        "S3": _signal_s3(rows), "report": _report(rows),
    }


def _hold_suffix(needed: int, comparison: str, constant_name: str) -> str:
    if needed > 0:
        return f"   needed: {needed} more rows"
    return f"   {comparison} {constant_name}"


def _mechanical_literal(classifier_text: str | None) -> int | None:
    """The single `_MECHANICAL_MAX_LINES = <int>` value, else `None`."""
    if classifier_text is None:
        return None
    matches = re.findall(
        rf"^{MECHANICAL_LINES_LITERAL} = (\d+)$", classifier_text, re.MULTILINE
    )
    return int(matches[0]) if len(matches) == 1 else None


def _build_s1_patch(classifier_text: str, old: int, new: int) -> str:
    old_lines = classifier_text.splitlines(keepends=True)
    new_text = re.sub(
        rf"^{MECHANICAL_LINES_LITERAL} = {old}$",
        f"{MECHANICAL_LINES_LITERAL} = {new}",
        classifier_text, count=1, flags=re.MULTILINE,
    )
    new_lines = new_text.splitlines(keepends=True)
    diff = difflib.unified_diff(
        old_lines, new_lines,
        fromfile="a/skills/plan-tasks/scripts/classify_tier.py",
        tofile="b/skills/plan-tasks/scripts/classify_tier.py",
    )
    return "".join(diff)


def _render_s1(sig: dict, classifier_text: str | None, date: str) -> tuple[list[str], str | None]:
    lines = ["## S1 mechanical row", ""]
    old = _mechanical_literal(classifier_text)
    if old is None:
        lines.append(f"- UNPARSED: {MECHANICAL_LINES_LITERAL}")
    verdict = sig["verdict"]
    prds_str = ", ".join(sig["prds"]) if sig["prds"] else "none"
    line = f"- {verdict}: n={sig['n']} rate={sig['rate']:.2f} prds={prds_str}"
    if verdict == "HOLD":
        line += _hold_suffix(sig["needed"], "rate below", "S1_ESCALATION_RATE")
    lines.append(line)
    lines.append(f"- unattributed: {sig['unattributed']}")
    patch = None
    if verdict == "PROPOSE" and old is not None:
        new = old // 2
        lines.append(f"- proposal: halve {MECHANICAL_LINES_LITERAL} {old} -> {new}")
        lines.append(f"- patch: routing-proposal-{date}.patch")
        lines.append(
            "- Revert: git revert the accepting commit; _PLAN_TASKS_FLOOR is "
            "read by no script, so it does not guard the constant."
        )
        patch = _build_s1_patch(classifier_text, old, new)
    lines.append("")
    return lines, patch


def _render_s2(sig: dict) -> list[str]:
    lines = ["## S2 repair budget", ""]
    verdict = sig["verdict"]
    prds_str = ", ".join(sig["prds"]) if sig["prds"] else "none"
    line = f"- {verdict}: n={sig['n']} rate={sig['rate']:.2f} prds={prds_str}"
    if verdict == "HOLD":
        line += _hold_suffix(sig["needed"], "rate at or above", "S2_COMPLETED_RATE")
    lines.append(line)
    if verdict == "PROPOSE":
        lines.append(
            "- proposal: remove the Repair row from model-ladder.md "
            "§ Per-rung budgets"
        )
        lines.append("- Revert: git revert the accepting commit.")
    lines.append("")
    return lines


def _render_s3(sig: dict) -> list[str]:
    lines = ["## S3 codex rung", ""]
    verdict = sig["verdict"]
    prds_str = ", ".join(sig["prds"]) if sig["prds"] else "none"
    line = (f"- {verdict}: n={sig['n']} no_edit_rate={sig['no_edit_rate']:.2f} "
            f"escalated_rate={sig['escalated_rate']:.2f} prds={prds_str}")
    if verdict == "HOLD":
        line += _hold_suffix(sig["needed"], "rates below", "S3_FAILURE_RATE")
    lines.append(line)
    if verdict == "PROPOSE":
        lines.append(
            "- proposal: set _WORK_CODEX_RUNG=off for the next batch "
            "(operator action; code never sets it)"
        )
        lines.append("- Revert: unset _WORK_CODEX_RUNG.")
    lines.append("")
    return lines


def _render_report(report: dict) -> list[str]:
    lines = [
        "## Escalations by tier reason", "",
        "| tier_reason | escalated |", "|---|---|",
    ]
    counts = report["escalations_by_reason"]
    # A reason value the classifier does not emit today still shows, after
    # the fixed eight, rather than vanishing from the table.
    extra = sorted(set(counts) - set(_REPORT_REASONS))
    for reason in (*_REPORT_REASONS, *extra):
        lines.append(f"| {reason} | {counts.get(reason, 0)} |")
    lines.append("")
    return lines


def _render_sources(sources: dict) -> list[str]:
    prds_str = ", ".join(sources["prds"]) if sources["prds"] else "none"
    if sources["recorded_at_min"] is None:
        recorded = "n/a"
    else:
        recorded = f"{sources['recorded_at_min']} .. {sources['recorded_at_max']}"
    audit_qwen = sources["audit_qwen"] or "none"
    return [
        "## Sources", "",
        f"- ledger: {sources['ledger']}",
        f"- rows: {sources['rows']}",
        f"- deduped rows: {sources['deduped_rows']}",
        f"- prds: {prds_str}",
        f"- recorded_at: {recorded}",
        f"- unparsed: {sources['unparsed']}",
        f"- audit-qwen: {audit_qwen}",
        "",
    ]


def render(
    signals: dict, sources: dict, date: str, classifier_text: str | None
) -> tuple[str, str | None]:
    """Render the markdown proposal and, on S1 PROPOSE, the S1 patch."""
    lines: list[str] = [
        f"# Routing proposal {date}", "",
        f"Floors: MIN_ROWS = {MIN_ROWS}; S1_ESCALATION_RATE = {S1_ESCALATION_RATE}; "
        f"S2_COMPLETED_RATE = {S2_COMPLETED_RATE}; S3_FAILURE_RATE = {S3_FAILURE_RATE}",
        "",
    ]
    lines.extend(_render_sources(sources))
    s1_lines, patch = _render_s1(signals["S1"], classifier_text, date)
    lines.extend(s1_lines)
    lines.extend(_render_s2(signals["S2"]))
    lines.extend(_render_s3(signals["S3"]))
    lines.extend(_render_report(signals["report"]))
    markdown = "\n".join(lines).rstrip("\n") + "\n"
    return markdown, patch


def _newest_audit_qwen(out_dir: Path) -> str | None:
    try:
        candidates = sorted(out_dir.glob("audit-qwen-*.md"))
    except OSError:
        return None
    return candidates[-1].name if candidates else None


def _build_sources(ledger_path: Path, out_dir: Path, raw_rows: list[dict],
                    rows: list[dict], unparsed: list[str]) -> dict:
    prds = sorted({r["prd"] for r in rows if r.get("prd") is not None})
    recorded_ats = sorted(
        r["recorded_at"] for r in rows if isinstance(r.get("recorded_at"), str)
    )
    return {
        "ledger": str(ledger_path), "rows": len(raw_rows), "deduped_rows": len(rows),
        "prds": prds,
        "recorded_at_min": recorded_ats[0] if recorded_ats else None,
        "recorded_at_max": recorded_ats[-1] if recorded_ats else None,
        "unparsed": len(unparsed), "audit_qwen": _newest_audit_qwen(out_dir),
    }


def _valid_date(value: str) -> str:
    datetime.strptime(value, "%Y-%m-%d")
    return value


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Propose routing rule changes from ledger outcomes (PRD 00170)."
    )
    parser.add_argument("--ledger", type=Path, default=None)
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--classifier", type=Path, default=None)
    parser.add_argument("--date", type=_valid_date, default=None)
    return parser.parse_args(argv)


def _default_classifier_path() -> Path:
    # scripts/ -> run-autopilot/ -> skills/ -> repo root
    return (Path(__file__).resolve().parents[3] / "skills" / "plan-tasks"
            / "scripts" / "classify_tier.py")


def _resolve_paths(args: argparse.Namespace) -> tuple[Path, Path, Path, str] | int:
    """Resolve ledger/out-dir/classifier/date, or return an exit code on failure."""
    cwd = Path.cwd()
    need_walkup = args.ledger is None or args.out_dir is None
    autopilot_dir = find_autopilot_dir(cwd) if need_walkup else None
    if need_walkup and autopilot_dir is None:
        print(
            f"tune_routing: no dev/local/autopilot dir above {cwd}; "
            "pass --ledger/--out-dir",
            file=sys.stderr,
        )
        return 1
    ledger_path = args.ledger or (autopilot_dir / "ledger" / "attempts.jsonl")
    out_dir = args.out_dir or (autopilot_dir.parent / "audit-results")
    classifier_path = args.classifier or _default_classifier_path()
    date = args.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return ledger_path, out_dir, classifier_path, date


def _write_proposal(out_dir: Path, date: str, markdown: str, patch: str | None) -> int:
    """Write the proposal (and patch), removing a stale patch when none is due."""
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"tune_routing: cannot write {out_dir}: {exc}", file=sys.stderr)
        return 1
    md_path = out_dir / f"routing-proposal-{date}.md"
    try:
        md_path.write_text(markdown, encoding="utf-8")
    except OSError as exc:
        print(f"tune_routing: cannot write {md_path}: {exc}", file=sys.stderr)
        return 1
    patch_path = out_dir / f"routing-proposal-{date}.patch"
    try:
        if patch is not None:
            patch_path.write_text(patch, encoding="utf-8")
        elif patch_path.exists():
            patch_path.unlink()
    except OSError as exc:
        print(f"tune_routing: cannot write {patch_path}: {exc}", file=sys.stderr)
        return 1
    print(str(md_path))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    resolved = _resolve_paths(args)
    if isinstance(resolved, int):
        return resolved
    ledger_path, out_dir, classifier_path, date = resolved

    try:
        text = ledger_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"tune_routing: cannot read ledger {ledger_path}: {exc}",
              file=sys.stderr)
        return 1
    raw_rows, unparsed = parse_rows(text)
    if not raw_rows:
        print(
            f"tune_routing: UNPARSED: no rows parsed ({len(unparsed)} unparsed)",
            file=sys.stderr,
        )
        return 1
    rows = dedupe_rows(raw_rows)

    try:
        classifier_text = classifier_path.read_text(encoding="utf-8")
    except OSError:
        classifier_text = None

    sig = signals(rows)
    sources = _build_sources(ledger_path, out_dir, raw_rows, rows, unparsed)
    markdown, patch = render(sig, sources, date, classifier_text)

    rc = _write_proposal(out_dir, date, markdown, patch)
    if rc != 0:
        return rc
    for name in ("S1", "S2", "S3"):
        s = sig[name]
        print(f"{name} {s['verdict']} n={s['n']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
