"""Pin the review-verbs prose: ledger flags, dispatch_rows block, severity word."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SKILL = (ROOT / "skills/review-work-completion/SKILL.md").read_text(encoding="utf-8")
FORMATS = (ROOT / "skills/review-work-completion/references/output-formats.md").read_text(
    encoding="utf-8"
)
PHASE_REVIEW = (ROOT / "skills/run-autopilot/references/phase-review.md").read_text(
    encoding="utf-8"
)
RECOVERY = (ROOT / "skills/run-autopilot/references/recovery.md").read_text(
    encoding="utf-8"
)
CHANGELOG = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")


def step(number: int) -> str:
    return SKILL.split(f"### {number}. ", 1)[1].split("\n### ", 1)[0]


def test_skill_passes_ledger_and_prior_findings_flags() -> None:
    staging = step(3)
    assert "[--settled-ledger <path>] [--prior-findings <path>]" in staging
    prompts = " ".join(step(4).split())
    assert "pass `--settled-ledger <path>` on the step-3 `review-stage` call" in prompts
    assert "pass `--prior-findings <path>` on the same call" in prompts
    assert "append this section with the Edit tool" not in prompts
    assert "renders no incremental addendum" not in prompts
    assert "the only hand edits are the two appends" not in prompts
    assert "they remain hand edits" in prompts


def test_output_format_lists_dispatch_rows_and_all_lenses() -> None:
    frontmatter = FORMATS.split("agents:\n", 1)[1].split("---", 1)[0]
    assert "  blake: available\n" in frontmatter
    assert "  eve: available\n" in frontmatter
    assert "dispatch_rows:\n  <persona>: <dispatch-id>" in frontmatter
    assert "`timeout`" in FORMATS.split("Agent states:", 1)[1].split("\n", 1)[0]
    assert "_DISPATCH_OUTCOME[agents[persona]]" in FORMATS


def test_cap_out_severity_is_a_word() -> None:
    cap = PHASE_REVIEW.split('"type": "cap-overflow"', 1)[1].split("\n", 1)[0]
    assert "the word (critical/high/medium/low), not the emoji cell" in cap
    assert "Tail-sweep chosen_findings" in cap


def test_requeue_records_the_carry_link_prose() -> None:
    escalate = PHASE_REVIEW.split("### Escalate review-flagged tasks by tier", 1)[1]
    escalate = escalate.split("\n### Dispatch rework", 1)[0]
    assert '"carry_refs": ["<Ref cell, upper-cased>", ...existing entries]' in escalate
    assert '"carry_cycle": <state.cycle>' in escalate
    assert "base = current if current_cycle == state.cycle else []" in escalate
    assert "new_carry_refs = sorted(set(base) | {this_finding_ref.upper()})" in escalate
    assert "a task re-queued again in a LATER cycle starts its list fresh" in escalate
    assert "stamps no `carry_refs` entry for that flagging" in escalate
    assert (
        "re-runs `task-set-meta <task-id> <meta-json-file>` with the missing "
        "`carry_refs`/`carry_cycle` pair" in escalate
    )

    dispatch = PHASE_REVIEW.split("### Dispatch rework", 1)[1]
    assert 'refused: "carry_unmatched"`, exit 2' in dispatch
    assert "must appear in some task's `carry_refs`" in dispatch

    gate = RECOVERY.split("### Fable rescue gate", 1)[1].split("\n## ", 1)[0]
    assert '"carry_refs": ["<Ref cell, upper-cased>", ...existing entries]' in gate
    assert '"carry_cycle": <state.cycle>' in gate
    assert 'refused: "carry_unmatched"`, exit 2' in gate

    summary = FORMATS.split("## Review Summary Format", 1)[1].split(
        "## Zero Issues Handling", 1
    )[0]
    assert "| Ref | Consensus | Severity | Issue | File | Found By |" in summary
    assert "| R1 | [N/N] | 🔴 Critical |" in summary


def test_carry_creates_nothing_prose() -> None:
    """A `carry` row creates no task and no decision, next to `verify` and
    `discard`, and the changelog ships that rule with the coverage check."""
    dispatch = PHASE_REVIEW.split("### Dispatch rework", 1)[1]
    assert '`"verify"`, `"discard"` and `"carry"` rows create nothing.' in dispatch
    assert '`"verify"` and `"discard"` rows create nothing.' not in PHASE_REVIEW

    unreleased = CHANGELOG.split("## [Unreleased]", 1)[1].split("\n## [", 1)[0]
    assert unreleased.count("carry") >= 2
    assert "findings coverage check" in unreleased
    assert "`carry` classification" in unreleased
    assert "one version" in unreleased
