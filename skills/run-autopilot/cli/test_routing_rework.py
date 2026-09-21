"""PRD 00207: `route("review")` on a rework resume.

Split out of test_routing.py (over the 800-line ceiling): the rework-resume
route, its edge cases, the exact stderr line, and the two docs that name the
rule. Fixtures build `state.json` and the cycle's review file in `tmp_path`.
"""

from __future__ import annotations

import json
from pathlib import Path

from cli.routing import OPUS, SONNET, Route, rework_resume, route


# ── route("review") on a rework resume (PRD 00207) ──────────────────────────

_REWORK_PRD = "00052-example-v1.md"


def _rework_box(
    tmp_path: Path,
    tasks: list[dict],
    rework_ids: list[str],
    *,
    cycle: int = 1,
    review_file: bool = True,
) -> Path:
    ap_dir = tmp_path / "dev/local/autopilot"
    ap_dir.mkdir(parents=True, exist_ok=True)
    (ap_dir / "state.json").write_text(
        json.dumps(
            {
                "prd": _REWORK_PRD,
                "cycle": cycle,
                "rework_task_ids": rework_ids,
                "tasks": tasks,
            },
        ),
    )
    if review_file:
        reviews = tmp_path / "dev/local/reviews"
        reviews.mkdir(parents=True, exist_ok=True)
        (reviews / f"00052-example-v1-review-{cycle}.md").write_text(
            "Verdict: 3 findings\n"
        )
    return ap_dir


def test_rework_resume_with_sonnet_tasks_routes_sonnet(tmp_path, capsys):
    tasks = [
        {"id": "4", "status": "completed", "model": "opus"},
        {"id": "5", "status": "pending", "model": "sonnet"},
        {"id": "6", "status": "pending"},
    ]
    ap_dir = _rework_box(tmp_path, tasks, ["4", "5", "6"])
    got = route("review", ap_dir, env={})
    assert got == Route(model=SONNET, effort="xhigh", cap_secs=10800)
    assert "rework resume, 2 task(s) left, routing" in capsys.readouterr().err


def test_rework_resume_with_one_opus_task_routes_opus(tmp_path):
    tasks = [
        {"id": "5", "status": "pending", "model": "sonnet"},
        {"id": "6", "status": "in_progress", "model": "opus"},
    ]
    ap_dir = _rework_box(tmp_path, tasks, ["5", "6"], cycle=2)
    got = route("review", ap_dir, env={})
    assert got.model == OPUS
    assert got.effort == "high"


def test_fresh_review_without_review_file_routes_opus(tmp_path, capsys):
    tasks = [{"id": "5", "status": "pending", "model": "sonnet"}]
    ap_dir = _rework_box(tmp_path, tasks, ["5"], review_file=False)
    assert route("review", ap_dir, env={}).model == OPUS
    assert "rework resume" not in capsys.readouterr().err


def test_rework_resume_with_all_tasks_completed_routes_opus(tmp_path):
    # A stale list left by a crash before phase-done is a fresh review.
    tasks = [{"id": "5", "status": "completed", "model": "sonnet"}]
    ap_dir = _rework_box(tmp_path, tasks, ["5", "9"])
    assert route("review", ap_dir, env={}).model == OPUS


def test_rework_resume_env_model_override_still_wins(tmp_path):
    tasks = [{"id": "5", "status": "pending", "model": "sonnet"}]
    ap_dir = _rework_box(tmp_path, tasks, ["5"])
    got = route("review", ap_dir, env={"_AUTOPILOT_MODEL_REVIEW": OPUS})
    assert got.model == OPUS


def test_docs_name_the_rework_resume_rule():
    # PRD 00207: the ladder and the core skill both state the route.
    skill_dir = Path(__file__).resolve().parent.parent
    ladder = (skill_dir / "references" / "model-ladder.md").read_text()
    core = (skill_dir / "SKILL.md").read_text()
    assert (
        "## Review sessions" in ladder or "**Review sessions (PRD 00207).**" in ladder
    )
    for text, where in ((ladder, "model-ladder.md"), (core, "SKILL.md")):
        assert "rework resume" in text, f"{where} does not name the rework resume rule"
    assert "cli/routing.rework_resume" in ladder
