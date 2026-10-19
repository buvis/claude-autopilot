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
CLI_MAIN = (ROOT / "skills/run-autopilot/cli/__main__.py").read_text(encoding="utf-8")
GATE = (ROOT / "skills/run-autopilot/cli/gate.py").read_text(encoding="utf-8")


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


def test_gate_help_describes_the_two_way_check() -> None:
    """The `gate`/`review-close` help and `cli/gate.py`'s module docstring
    document the findings check as two-way and name every refusal it can
    return: an uncovered review row, a findings section with no Ref column,
    an unknown classification, and the two `carry` refusals."""
    cli_doc = CLI_MAIN.split('"""', 2)[1]
    gate_doc = GATE.split('"""', 2)[1]
    for doc in (cli_doc, gate_doc):
        assert "no `--findings` row names a" in doc  # the uncovered review row
        assert "no Ref column" in doc
        assert "unknown classification" in doc
    assert "BOTH directions" in gate_doc
    assert "every review row must be" in gate_doc
    assert "Coverage runs the other way too" not in gate_doc  # the one-way prose
    assert "no matching re-queued task" in cli_doc
    assert "a `carry` row inside a tail-sweep batch" in cli_doc


def test_help_names_the_token_sweep_and_no_verdict_refusals() -> None:
    """The `gate` and `review-close` help and `cli/gate.py`'s module
    docstring name the unconsumed-token sweep refusal, the no-Verdict exit 2,
    and describe the carry match by its stamps - never by a `[C]`-prefix
    naming rule, which the match no longer checks."""
    cli_doc = CLI_MAIN.split('"""', 2)[1]
    gate_doc = GATE.split('"""', 2)[1]
    assert "a [m/n] token or table row the findings parser did not read" in cli_doc
    assert "token or pipe row the findings parser did not read" in gate_doc
    assert "no_verdict" in cli_doc
    assert "no matching re-queued task" in cli_doc
    assert "`[C]`-prefixed" not in cli_doc
    assert "`[C]`-prefixed" not in gate_doc


def test_carry_rule_prose_has_no_d_name_test() -> None:
    """The carry rule's prose used to also require the backing task's name
    not start with `[D`, mirroring the `_carry_unmatched` clause task 6
    removed (a carry row is matched by its stamps now, never by name) - the
    prose must not still state the removed name test."""
    dispatch = PHASE_REVIEW.split("### Dispatch rework", 1)[1]
    assert "name not starting with `[D`" not in dispatch
    assert "must appear in some task's `carry_refs`" in dispatch


def test_output_formats_tells_writers_to_fence_example_rows() -> None:
    """A reviewer who quotes a worked example of a findings row outside a
    code fence writes an unconsumed token the sweep refuses - output-formats
    must tell writers to fence any example row."""
    assert (
        "A [m/n] token or a pipe-table row anywhere outside the Consolidated "
        "Findings table makes gate --findings and review-close refuse the "
        "file (exit 2); quote an example row inside a code fence."
    ) in FORMATS


def _shipped_notes() -> str:
    """`[Unreleased]` plus the newest released section. A release moves an
    entry from the first into the second, and the prose these tests pin must
    survive that move: the v0.10.0 cut (2026-10-18) redded this file on bare
    master because both tests read `[Unreleased]` alone."""
    after = CHANGELOG.split("## [Unreleased]", 1)[1]
    return "\n## [".join(after.split("\n## [")[:2])


def test_changelog_states_what_review_close_refuses_truthfully() -> None:
    """The old `[Unreleased]` claim - "refuses exactly what `autopilot gate`
    refuses ... every refusal exits 2" - is false: a no-section, empty-
    findings file is a gate shape gap (exit 1) review-close still applies.
    The entry must state the true claim instead."""
    unreleased = _shipped_notes()
    assert "refuses exactly what" not in unreleased
    assert (
        "review-close` refuses, exit 2, every findings file `gate --findings`"
        " refuses with exit 2" in unreleased
    )
    assert "a file with no Verdict line exits 2" in unreleased


def test_carry_creates_nothing_prose() -> None:
    """A `carry` row creates no task and no decision, next to `verify` and
    `discard`, and the changelog ships that rule with the coverage check."""
    dispatch = PHASE_REVIEW.split("### Dispatch rework", 1)[1]
    assert '`"verify"`, `"discard"` and `"carry"` rows create nothing.' in dispatch
    assert '`"verify"` and `"discard"` rows create nothing.' not in PHASE_REVIEW

    unreleased = _shipped_notes()
    assert unreleased.count("carry") >= 2
    assert "findings coverage check" in unreleased
    assert "`carry` classification" in unreleased
    assert "one version" in unreleased
