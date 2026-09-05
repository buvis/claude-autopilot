"""Pin PRD 00175's batch skip at its read, write, and reporting steps."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SKILL = (ROOT / "skills/review-work-completion/SKILL.md").read_text(encoding="utf-8")
SCHEMA = (ROOT / "skills/run-autopilot/references/state-schema.md").read_text(
    encoding="utf-8"
)


def step(number: int) -> str:
    return SKILL.split(f"### {number}. ", 1)[1].split("\n### ", 1)[0]


def test_step_one_checks_batch_before_binary_probe() -> None:
    prerequisite = " ".join(step(1).split())
    assert prerequisite.index("state.batch.unavailable_reviewers") < prerequisite.index(
        "AND a backend CLI resolves"
    )
    assert "no dispatch, no retry" in prerequisite
    assert "no `ui` key" in prerequisite
    assert "no `state.json`" in prerequisite


def test_step_five_latches_only_permanent_rejection_with_provenance() -> None:
    dispatch = step(5)
    assert "On exit 4" in dispatch
    assert "state.batch.unavailable_reviewers" in dispatch
    assert "state.batch.unavailable_reviewer_details.carl" in dispatch
    assert '"cycle": state.cycle, "prd": state.prd' in dispatch
    assert "sibling fields untouched" in dispatch
    assert "never overwrite the first failure" in dispatch
    assert "Do not latch" in dispatch


def test_step_six_emits_skip_and_omits_carl() -> None:
    consolidation = step(6)
    assert (
        "carl: skipped (permanently unavailable since cycle {n} of {prd})"
        in consolidation
    )
    assert "unavailable_reviewer_details.carl" in consolidation
    assert "reviewers:" in consolidation
    assert "omit Carl" in consolidation


def test_schema_defines_batch_lifetime_and_origin() -> None:
    assert "`batch.unavailable_reviewers` | string[]?" in SCHEMA
    assert "`batch.unavailable_reviewer_details` | object?" in SCHEMA
    row = next(
        line
        for line in SCHEMA.splitlines()
        if line.startswith("| `batch.unavailable_reviewers`")
    )
    assert "per-PRD reset" in row
    assert "next batch" in row
    assert "[]" in row


def test_watcher_finishes_when_reviewer_produces_no_file_on_exit_four() -> None:
    dispatch = " ".join(step(5).split())
    assert "or reached a terminal failure/unavailability result" in dispatch
    assert "do not wait for that missing file" in dispatch


def test_closed_batch_rollover_clears_carl_latch_without_clearing_on_resume() -> None:
    autopilot = (ROOT / "skills/run-autopilot/SKILL.md").read_text(encoding="utf-8")
    rollover = autopilot.split("**Batch-identity rollover.**", 1)[1].split("\n## ", 1)[
        0
    ]
    assert 'phase == "done"' in rollover
    assert 'next_phase == ""' in rollover
    assert "delete `batch.unavailable_reviewers`" in rollover
    assert "`batch.unavailable_reviewer_details`" in rollover
    assert "in-progress resume preserves both" in rollover
    build = (ROOT / "skills/run-autopilot/references/phase-build.md").read_text(
        encoding="utf-8"
    )
    assert "clears `batch.unavailable_reviewers`" in build
    assert "`batch.unavailable_reviewer_details`" in build
