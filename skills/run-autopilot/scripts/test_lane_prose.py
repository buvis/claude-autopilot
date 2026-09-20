#!/usr/bin/env python3
"""Prose pins for the effort-lane routing (PRD 00204): Phase 0 step 5.5 in
`references/phase-build.md` names the three lanes, the shadow rule and the
kill switch, so the text cannot drift away from what `cli/lane.py` does.

Stdlib only; pytest collects the module-level tests with no config.
"""

from __future__ import annotations

import re
from pathlib import Path

_REFERENCES = Path(__file__).resolve().parents[1] / "references"
_PHASE_BUILD = _REFERENCES / "phase-build.md"


def _section(text: str, heading: str) -> str:
    """The body from the line that is exactly `heading` to the next heading of
    the same or a higher level, so a pinned phrase elsewhere in the file
    cannot satisfy the pin."""
    lines = text.splitlines()
    if heading not in lines:
        raise AssertionError(f"no heading line {heading!r}")
    level = len(heading) - len(heading.lstrip("#"))
    body: list[str] = []
    fenced = False
    for line in lines[lines.index(heading) + 1 :]:
        if line.startswith("```"):
            fenced = not fenced
        elif not fenced and re.match(rf"^#{{1,{level}}} ", line):
            break
        body.append(line)
    return "\n".join(body)


def _step_5_5() -> str:
    return _section(_PHASE_BUILD.read_text(encoding="utf-8"), "### 5.5. Route by lane")


def test_step_5_5_sits_between_the_frontmatter_parse_and_phase_1() -> None:
    text = _PHASE_BUILD.read_text(encoding="utf-8")
    parse = text.index("### Frontmatter parse (step 5)")
    route = text.index("### 5.5. Route by lane")
    catchup = text.index("## Phase 1: Catchup")
    assert parse < route < catchup


def test_step_5_5_names_three_lanes_and_the_shadow_sentence() -> None:
    step = _step_5_5()
    for token in ("`solo`", "`fast-track`", "`full`", "RELEASED_LANES"):
        assert token in step, token
    assert "── AUTOPILOT ── lane: <lane> (<reason>), running full ──" in step
    assert "_AUTOPILOT_LANES=off" in step
    assert "`state.lane_effective`" in step
    assert "`cli/lane.py` decides" in step


# ── the solo runbook (PRD 00205) ─────────────────────────────────────────────

_LANE_SOLO = _REFERENCES / "lane-solo.md"
# Signal -> the section that raises it and the exact form the runbook uses.
_SOLO_SIGNALS = {
    "unnamed_path": ("## 4. Escalation checks", "- `unnamed_path`"),
    "security_diff": ("## 4. Escalation checks", "- `security_diff`"),
    "check_failed": ("## 4. Escalation checks", "- `check_failed`"),
    "critical_finding": ("## 5. Review", "--signal critical_finding"),
    "high_unresolved": ("## 5. Review", "--signal high_unresolved"),
    "suite_red": ("## 5. Review", "--signal suite_red"),
    "review_failed": ("## 5. Review", "--signal review_failed"),
}


def _solo() -> str:
    return _LANE_SOLO.read_text(encoding="utf-8")


def _headings(text: str, level: str = "## ") -> list[str]:
    return [line[len(level) :] for line in text.splitlines() if line.startswith(level)]


def test_step_5_5_solo_branch_names_the_runbook() -> None:
    step = _step_5_5()
    assert "acted on by nothing" not in step
    assert "`solo`: read `references/lane-solo.md` and follow it" in step
    assert "Phases 1 to 3 do not run for this PRD" in step


def test_solo_runbook_orders_mirror_implement_suite_check_review_close() -> None:
    words = ("Mirror", "Implement", "Suite", "Escalation checks", "Review", "Close")
    heads = _headings(_solo())
    positions = [next(i for i, h in enumerate(heads) if word in h) for word in words]
    assert positions == sorted(positions), heads


def test_solo_runbook_names_six_signals_and_their_outcomes() -> None:
    # The PRD's six signals plus `review_failed`, added by the 00205 review
    # (a failed sole review pass must escalate, never converge); the name is
    # the one the PRD's acceptance criteria list.
    text = _solo()
    for signal, (heading, form) in _SOLO_SIGNALS.items():
        assert form in _section(text, heading), signal
    close = _section(text, "## 6. Close")
    assert "**Escalation**" in close and "--outcome tasks_done" in close
    assert "**Close**" in close and "--outcome lane_reviewed" in close
    assert close.index("--outcome tasks_done") < close.index("--outcome lane_reviewed")
    check = _section(text, "## 4. Escalation checks")
    assert "autopilot lane-check" in check
    assert "`lane: escalate <signal>`" in check


def test_solo_runbook_guards_resume_reruns_the_check_and_gates_the_review() -> None:
    text = " ".join(_solo().split())
    mirror = " ".join(_section(_solo(), "## 1. Mirror").split())
    assert mirror.index("Capture `work_start_sha`") < mirror.index("Then mirror")
    assert "whose text is not already the `name` of a task in `state.tasks`" in mirror
    assert "mirrors only the lines still missing" in mirror
    assert "mirrors nothing and goes to step 2" in mirror
    review = " ".join(_section(_solo(), "## 5. Review").split())
    assert "run `autopilot lane-check` again without `--signal`" in review
    assert "at least one `[ALICE]` line and all twelve `R{n}: pass|fail`" in review
    assert "`[ALICE] ✅ No issues found` or a finding line carrying `| File:` and `| Task:`" in review
    assert "row count equals the number of finding lines" in review
    assert "never converges on an empty table" in review
    assert "rows the delta confirmed fixed are removed, rows it raised on the fix are added" in review
    close = " ".join(_section(_solo(), "## 6. Close").split())
    assert "first write `dev/local/reviews/<prd-stem>-review-1.md`" in close
    assert "updated with the delta's outcome" in close
    assert "`-review-1.md` is written only on the close exit of step 6" in text


def test_solo_runbook_never_reads_the_handoff_marker() -> None:
    sentences = [
        s for s in re.split(r"(?<=[.!])\s+", _solo()) if ".handoff-requested" in s
    ]
    assert sentences, "the runbook must say what it does with the soft marker"
    assert all("is not read" in s for s in sentences), sentences


def test_solo_review_file_shape_is_gate_shaped() -> None:
    review = _section(_solo(), "## 5. Review")
    for token in (
        "head_sha:",
        "reviewers: alice",
        "Verdict: converged",
        "Tests:",
        "codex_rung_guard: not fired",
        "-solo-pass.md",
        "-review-1.md",
    ):
        assert token in review, token


def test_solo_attempt_record_uses_orchestrator_and_solo_pipeline() -> None:
    implement = " ".join(_section(_solo(), "## 2. Implement").split())
    assert '"implementor": "orchestrator"' in implement
    assert '"pipeline": "solo"' in implement
    assert "no subagent" in implement
    assert "task-done" in implement
