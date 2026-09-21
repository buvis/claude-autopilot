"""Tests binding the PRD 00194 rework-design prose — the `### Dispatch rework`
section of run-autopilot's `references/phase-review.md` and step 7 of
`review-work-completion/SKILL.md`. They pin one `/autopilot:design-solution
--rework` call per cycle below the cap, before any task-add; the source check
and pass gate that decide reuse; CRITICAL `[D{cycle}]` tasks carrying
`Design:` then `### Contract` then `### Findings (verbatim)`; the at-cap
custody stall left untouched; non-CRITICAL routing unchanged; the loop-mode
`design_rework` stall and the interactive `sub_skill_fail` pause; and the
review-lens roster sentence plus the escalation caveat surviving byte-identical.

Mirrors test_custody_prose.py's pattern: each target file is read once (the
run-autopilot references via `custody_prose_testutil.py`, the review skill
here), both sections pass through `_prose` so a token dump inside a fence
satisfies no pin, presence pins are scoped to the section that must carry
them via `_section`, order pins use first occurrences via `_assert_in_order`,
each instruction binds its noun to its verb on one line via `_assert_bound`,
and the paragraph carrying each pin is swept via `_assert_no_negation` for
the negations and the override vocabulary (`optional`, `regardless`,
`retired`, `supersedes`) that would invert it while keeping its tokens.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cli.custody_prose_testutil import (
    _PHASE_REVIEW,
    _RECOVERY,
    _RECOVERY_TEXT,
    _REVIEW_TEXT,
    _ROSTER_SENTENCE,
    _SKILL_DIR,
    _STATE_SCHEMA,
    _assert_absent,
    _assert_bound,
    _assert_in_order,
    _assert_matches,
    _assert_no_match,
    _assert_no_negation,
    _assert_present,
    _bullet,
    _deferred_log_section,
    _added_bullets,
    _paragraph,
    _prose,
    _rows_starting_with,
    _section,
    _single_row,
)

_REVIEW_SKILL = _SKILL_DIR.parent / "review-work-completion" / "SKILL.md"
_REVIEW_SKILL_TEXT = _REVIEW_SKILL.read_text()
_REPO_ROOT = _SKILL_DIR.parent.parent
_RELEASE_CHECKS = _REPO_ROOT / "dev" / "bin" / "release-checks"
_RELEASE_CHECKS_TEXT = _RELEASE_CHECKS.read_text()
_CHANGELOG = _REPO_ROOT / "CHANGELOG.md"
_CHANGELOG_TEXT = _CHANGELOG.read_text()
_DISPATCH = _prose(
    _section(
        _REVIEW_TEXT,
        _PHASE_REVIEW,
        "### Dispatch rework",
        "### After /autopilot:work returns",
    ),
)
_STEP_7 = _prose(
    _section(
        _REVIEW_SKILL_TEXT,
        _REVIEW_SKILL,
        "### 7. Create follow-up tasks",
        "### 8. Save review file",
    ),
)

_DISPATCH_WHERE = "the `### Dispatch rework` section"
_STEP_7_WHERE = "the `### 7. Create follow-up tasks` step"
_ESCALATION_CAVEAT = "**Escalation caveat — diagnose the failure before escalating.**"
_PASS_GATE = "awk 'NF{last=$0} END{exit last!=\"result: ok\"}'"
_DESIGN_LINE = "Design: dev/local/designs/<prd-stem>-rework-<cycle>-design.md"

_DESIGN_LEAD = "**Design CRITICAL rework before any task-add (PRD 00194).**"
_DESIGN_WHERE = "the `Design CRITICAL rework before any task-add` paragraph"
_FAILURE_LEAD = "**Rework design failure**"
_FAILURE_WHERE = "the `Rework design failure` paragraph"
_CRITICAL_BULLET_LEAD = "- **CRITICAL D-tasks carry the rework design (PRD 00194).**"
_CRITICAL_BULLET_WHERE = "the `CRITICAL D-tasks carry the rework design` bullet"
_TRANSCRIBE_LEAD = "- **Transcribe the findings verbatim (PRD 00095).**"
_NO_TASK_HERE = "A 🔴 CRITICAL finding gets no task here (PRD 00194)"
_NO_TASK_WHERE = "the `A 🔴 CRITICAL finding gets no task here` paragraph"
_QUEUE_LEAD = "**Skip every finding this cycle queued for verification**"
_QUEUE_WHERE = "the verification-queue paragraph"
_PROCESS_BULLET = (
    r"(?m)^- Process 🟠 → 🟡 order \(🔴 rows belong to Phase 6, above\)[ \t]*$"
)

# Override vocabulary: prose that keeps every pinned token but tells the
# reader to disregard it reaches for one of these; none occurs in the
# contract, so both sections are swept whole. `as before` is legitimate in
# the Dispatch section ("routes exactly as before") and banned only in step 7.
_OVERRIDE = (
    "optional|regardless|uninvoked|omit|unnecessary|retired|supersede|"
    "no operative force|in your own words|kept for the pin|in this step too|"
    "ahead of Phase 6|🔴 last"
)
_STEP_7_OVERRIDE = f"{_OVERRIDE}|as before"
_OVERRIDE_WHAT = (
    "override vocabulary that tells the reader to disregard the pinned prose"
)

# The contract's own negatives, blanked before each paragraph sweep.
_DESIGN_ALLOW = (
    "not a reason to skip the fix",
    "no rework design and no fix task",
    "runs no rework design",
    "is not a table row",
)
_FAILURE_ALLOW = (
    "do not re-invoke it",
    "create no fix task",
    "removes nothing from the roster",
)
_QUEUE_ALLOW = (
    "never verbatim identity",
    "it is never routed",
    "is never routed either",
)


def _design_paragraph() -> str:
    return _paragraph(_DISPATCH, _PHASE_REVIEW, _DESIGN_LEAD)


def _failure_paragraph() -> str:
    return _paragraph(_DISPATCH, _PHASE_REVIEW, _FAILURE_LEAD)


def _critical_bullet() -> str:
    return _single_row(_DISPATCH, _PHASE_REVIEW, _DISPATCH_WHERE, _CRITICAL_BULLET_LEAD)


def _assert_design_bound(noun: str, verbs: str) -> None:
    design = _design_paragraph()
    _assert_bound(design, _PHASE_REVIEW, _DESIGN_WHERE, noun=noun, verbs=verbs)


def _assert_failure_bound(noun: str, verbs: str) -> None:
    failure = _failure_paragraph()
    _assert_bound(failure, _PHASE_REVIEW, _FAILURE_WHERE, noun=noun, verbs=verbs)


def _assert_bullet_bound(noun: str, verbs: str) -> None:
    bullet = _critical_bullet()
    _assert_bound(bullet, _PHASE_REVIEW, _CRITICAL_BULLET_WHERE, noun=noun, verbs=verbs)


def _assert_design_no_negation(banned: str = _OVERRIDE) -> None:
    design = _design_paragraph()
    _assert_no_negation(
        design,
        _PHASE_REVIEW,
        _DESIGN_WHERE,
        banned=banned,
        allow=_DESIGN_ALLOW,
    )


def _assert_bullet_no_negation(banned: str = _OVERRIDE) -> None:
    _assert_no_negation(
        _critical_bullet(),
        _PHASE_REVIEW,
        _CRITICAL_BULLET_WHERE,
        banned=banned,
        allow=("not paraphrased",),
    )


def _assert_step_7_critical_paragraph() -> None:
    # The CRITICAL sentence opens its own paragraph (not a quoted "retired
    # wording"), binds Phase 6 to the creation, and carries no override.
    _assert_matches(
        _STEP_7,
        _REVIEW_SKILL,
        _STEP_7_WHERE,
        r"(?m)^A 🔴 CRITICAL finding gets no task here \(PRD 00194\):",
        "open a paragraph with the CRITICAL no-task sentence",
    )
    critical = _paragraph(_STEP_7, _REVIEW_SKILL, _NO_TASK_HERE)
    _assert_bound(
        critical,
        _REVIEW_SKILL,
        _NO_TASK_WHERE,
        noun="Phase 6",
        verbs="creates",
    )
    _assert_present(
        critical,
        _REVIEW_SKILL,
        _NO_TASK_WHERE,
        (
            "never starts without a reviewed contract",
            "Every other severity is created below as today",
        ),
    )
    _assert_no_negation(
        critical,
        _REVIEW_SKILL,
        _NO_TASK_WHERE,
        banned=_STEP_7_OVERRIDE,
        allow=("never starts without a reviewed contract",),
    )


def _assert_step_7_queue_paragraph() -> None:
    # The queue paragraph hands a queued CRITICAL to Phase 6 too.
    queue = _paragraph(_STEP_7, _REVIEW_SKILL, _QUEUE_LEAD)
    _assert_present(
        queue,
        _REVIEW_SKILL,
        _QUEUE_WHERE,
        ("a queued CRITICAL is never routed either", "its task is Phase 6's"),
    )
    _assert_bound(
        queue,
        _REVIEW_SKILL,
        _QUEUE_WHERE,
        noun="a queued CRITICAL",
        verbs="routed",
    )
    _assert_no_negation(
        queue,
        _REVIEW_SKILL,
        _QUEUE_WHERE,
        banned=_STEP_7_OVERRIDE,
        allow=_QUEUE_ALLOW,
    )


def test_dispatch_rework_designs_critical_rework_once_before_any_task_add() -> None:
    pins = (
        "--rework <this cycle's review file>",
        "state.cycle < state.rework_cap",
        "ONCE for this cycle",
    )
    _assert_present(_DISPATCH, _PHASE_REVIEW, _DISPATCH_WHERE, pins)

    # First occurrences: the single design call must sit above the batch
    # build, and the batch build above the real creation step — the
    # backticked `task-add <task-json-file>` line, not a bare `task-add`.
    order = (
        "ONCE for this cycle",
        "Build the rework batch from two sources:",
        "`task-add <task-json-file>`",
    )
    _assert_in_order(_DISPATCH, _PHASE_REVIEW, _DISPATCH_WHERE, order)
    negations = (
        "Do NOT invoke `/autopilot:design-solution`",
        "after the tasks are created",
    )
    _assert_absent(_DISPATCH, _PHASE_REVIEW, _DISPATCH_WHERE, negations)

    # The instruction itself, on one line each: the sub-skill bound to an
    # action verb, the below-cap condition bound to that call, and the ONCE
    # call bound to `before` the first task — so a bare token dump fails.
    _assert_design_bound(noun="design-solution", verbs="invoke|run|dispatch")
    _assert_design_bound(
        noun=r"state\.cycle < state\.rework_cap",
        verbs="invoke|run|dispatch",
    )
    _assert_design_bound(noun="ONCE for this cycle", verbs="before")
    _assert_present(
        _design_paragraph(),
        _PHASE_REVIEW,
        _DESIGN_WHERE,
        ("before the first task is created",),
    )
    _assert_design_no_negation()
    _assert_no_match(
        _DISPATCH,
        _PHASE_REVIEW,
        _DISPATCH_WHERE,
        f"(?i){_OVERRIDE}",
        _OVERRIDE_WHAT,
    )


def test_every_critical_row_becomes_a_d_task_with_one_owner() -> None:
    dispatch_pins = (
        "Every unresolved 🔴 row of this cycle becomes (or joins) a `[D{cycle}]` task",
        "audit trail, not a reason to skip the fix",
        "only task-creation point for a 🔴 finding",
    )
    _assert_present(_DISPATCH, _PHASE_REVIEW, _DISPATCH_WHERE, dispatch_pins)
    _assert_design_bound(noun="Every unresolved 🔴 row", verbs="becomes|joins")
    _assert_design_bound(noun="step 7", verbs="leaves")
    _assert_design_no_negation()

    # The review skill hands 🔴 rows to Phase 6 and keeps the other
    # severities; the two old sentences that gave CRITICAL a task here must
    # be gone, not merely joined by the new paragraph.
    step_7_pins = (
        _NO_TASK_HERE,
        "Phase 6",
        "A queued **HIGH is not skipped**",
        "- Process 🟠 → 🟡 order",
    )
    _assert_present(_STEP_7, _REVIEW_SKILL, _STEP_7_WHERE, step_7_pins)
    negations = (
        "CRITICAL or HIGH is not skipped",
        "Process 🔴 → 🟠 → 🟡 order",
        "creates the CRITICAL task here",
    )
    _assert_absent(_STEP_7, _REVIEW_SKILL, _STEP_7_WHERE, negations)

    # The CRITICAL paragraph and the queue paragraph each hand a CRITICAL to
    # Phase 6; the Process bullet is the whole line, so no `, then 🔴 last`
    # tail can ride on it.
    _assert_step_7_critical_paragraph()
    _assert_matches(
        _STEP_7,
        _REVIEW_SKILL,
        _STEP_7_WHERE,
        _PROCESS_BULLET,
        "keep the whole line `- Process 🟠 → 🟡 order (🔴 rows belong to Phase 6, above)`",
    )
    _assert_step_7_queue_paragraph()
    _assert_no_match(
        _STEP_7,
        _REVIEW_SKILL,
        _STEP_7_WHERE,
        f"(?i){_STEP_7_OVERRIDE}",
        _OVERRIDE_WHAT,
    )


def test_rework_design_reuse_needs_the_source_check_and_the_pass_gate() -> None:
    pins = (
        "rg -q -F 'Source review:",
        "stale",
        _PASS_GATE,
        "result: failed",
        "interrupted run",
        "reuse it and skip the invocation",
    )
    _assert_present(_DISPATCH, _PHASE_REVIEW, _DISPATCH_WHERE, pins)
    _assert_in_order(
        _DISPATCH,
        _PHASE_REVIEW,
        _DISPATCH_WHERE,
        ("Source review:", "Pass gate"),
    )
    negations = (
        "reuse it unconditionally",
        "skip the pass gate",
        "skip the source check",
    )
    _assert_absent(_DISPATCH, _PHASE_REVIEW, _DISPATCH_WHERE, negations)

    # Each reuse outcome bound to its trigger on one line: a failed source
    # check means stale, the pass gate is run, a `result: failed` line takes
    # the failure routing, an interrupted run re-invokes the skill, and only
    # a pass-gate exit 0 reuses the doc — with no "may be omitted" override.
    _assert_design_bound(noun="stale", verbs="means")
    _assert_design_bound(noun=re.escape(_PASS_GATE), verbs="run|exits?|gate")
    _assert_design_bound(noun="result: failed", verbs="take|takes|routing")
    _assert_design_bound(noun="interrupted run", verbs="invoke|invokes|overwrites")
    _assert_design_bound(noun="reuse it and skip the invocation", verbs="exits?")
    _assert_design_no_negation(
        banned=(
            f"{_OVERRIDE}|may be omitted|skip the pass gate|skip the source check|"
            "reuse it unconditionally"
        ),
    )


def test_critical_d_task_carries_design_then_contract_then_findings() -> None:
    # First occurrences: the new CRITICAL sub-bullet must be the first one in
    # source 2, so its `### Findings (verbatim)` mention lands before the
    # transcribe bullet's — a sub-bullet placed after it fails the order.
    blocks = (_DESIGN_LINE, "### Contract", "### Findings (verbatim)")
    _assert_in_order(_DISPATCH, _PHASE_REVIEW, _DISPATCH_WHERE, blocks)
    _assert_in_order(
        _DISPATCH,
        _PHASE_REVIEW,
        _DISPATCH_WHERE,
        (_CRITICAL_BULLET_LEAD, _TRANSCRIBE_LEAD),
    )
    pins = ("copied verbatim", "sole contract source")
    _assert_present(_DISPATCH, _PHASE_REVIEW, _DISPATCH_WHERE, pins)
    negations = ("paraphrase the contract", "below its `### Findings (verbatim)`")
    _assert_absent(_DISPATCH, _PHASE_REVIEW, _DISPATCH_WHERE, negations)

    # Inside the one bullet: a 🔴 line is what makes a D-task carry the
    # design, the three blocks sit in order on that bullet, the Contract
    # block holds the design's section byte-identical, and nothing on the
    # bullet tells the reader to summarise instead.
    bullet = _critical_bullet()
    _assert_in_order(bullet, _PHASE_REVIEW, _CRITICAL_BULLET_WHERE, blocks)
    _assert_bullet_bound(noun="🔴 CRITICAL line", verbs="carries")
    _assert_bullet_bound(noun="### Contract", verbs="holding|holds")
    _assert_present(
        bullet,
        _PHASE_REVIEW,
        _CRITICAL_BULLET_WHERE,
        (
            "in this order",
            "copied verbatim",
            "byte-identical, not paraphrased",
            "sole contract source",
        ),
    )
    _assert_bullet_no_negation(
        banned=f"{_OVERRIDE}|summari[sz]e|paraphrase the contract",
    )


def test_at_cap_keeps_the_custody_stall_and_launches_no_rework_design() -> None:
    pins = (
        "state.cycle >= state.rework_cap",
        'site: "cap_critical"',
        "no rework design and no fix task",
    )
    _assert_present(_DISPATCH, _PHASE_REVIEW, _DISPATCH_WHERE, pins)

    # The Phase 5 loop-mode cap-out bullet keeps its own custody stall slug;
    # the rework design must not have re-routed the at-cap path.
    cap_out = _section(
        _REVIEW_TEXT,
        _PHASE_REVIEW,
        "- **Loop mode (`$_AUTOPILOT_LOOP` set) — cap-out defers, never pauses.**",
        "- **Interactive — perform the Cap-pause behavior**",
    )
    _assert_present(
        cap_out,
        _PHASE_REVIEW,
        "the loop-mode cap-out bullet",
        ('site: "cap_critical"',),
    )

    # The at-cap sentence itself: the cap condition and the "no rework design
    # and no fix task" outcome on one line, the custody stall keeping its
    # slug, and the Cap check named as what already routed the cycle.
    _assert_bound(
        _design_paragraph(),
        _PHASE_REVIEW,
        _DESIGN_WHERE,
        noun=r"state\.cycle >= state\.rework_cap",
        verbs="no rework design and no fix task",
        window=160,
    )
    _assert_design_bound(noun=r'site: "cap_critical"', verbs="stall")
    _assert_design_bound(noun="Cap check", verbs="routed")
    _assert_design_no_negation()


def test_non_critical_rework_routing_is_unchanged() -> None:
    pins = (
        "A cycle with no 🔴 row runs no rework design",
        "every other severity routes exactly as before",
        "A D-task with no 🔴 line carries neither",
    )
    _assert_present(_DISPATCH, _PHASE_REVIEW, _DISPATCH_WHERE, pins)

    # Bound on one line each: no 🔴 row is what runs no design, every other
    # severity is what routes as before, and no 🔴 line is what carries
    # neither block — and neither paragraph carries an override.
    _assert_design_bound(noun="no 🔴 row", verbs="runs")
    _assert_design_bound(noun="every other severity", verbs="routes")
    _assert_design_no_negation()
    _assert_bullet_bound(noun="no 🔴 line", verbs="carries")
    _assert_bullet_no_negation()


def test_rework_design_failure_stalls_in_loop_and_pauses_interactively() -> None:
    pins = (
        'site: "design_rework"',
        "Loop-mode stall procedure",
        '"site": "sub_skill_fail"',
        'state.phase = "paused"',
        "do not re-invoke it",
        "create no fix task",
        "delete the doc so the next Phase 6 entry regenerates it",
    )
    _assert_present(_DISPATCH, _PHASE_REVIEW, _DISPATCH_WHERE, pins)
    modes = ("Loop mode", "Interactive")
    _assert_in_order(_DISPATCH, _PHASE_REVIEW, _DISPATCH_WHERE, modes)
    negations = ("re-invoke the sub-skill ONCE", "never stall")
    _assert_absent(_DISPATCH, _PHASE_REVIEW, _DISPATCH_WHERE, negations)

    # Inside the failure paragraph: the loop slug bound to the stall, the
    # interactive site bound to the pause, each branch carrying its own
    # site, the retry budget named as spent — and no "re-invoke it twice"
    # or "stalling is unnecessary" override.
    _assert_failure_bound(noun=r'site: "design_rework"', verbs="stall")
    _assert_failure_bound(noun=r'"site": "sub_skill_fail"', verbs="paused")
    failure = _failure_paragraph()
    branches = (
        "Loop mode",
        'site: "design_rework"',
        "Interactive",
        '"site": "sub_skill_fail"',
    )
    _assert_in_order(failure, _PHASE_REVIEW, _FAILURE_WHERE, branches)
    budget = (
        "three dispatches were the retry budget",
        "do not re-invoke it",
        "create no fix task",
    )
    _assert_present(failure, _PHASE_REVIEW, _FAILURE_WHERE, budget)
    _assert_no_negation(
        failure,
        _PHASE_REVIEW,
        _FAILURE_WHERE,
        banned=(
            f"{_OVERRIDE}|re-invoke it twice|re-invoke the sub-skill|"
            "stalling is unnecessary|never stall"
        ),
        allow=_FAILURE_ALLOW,
    )


def test_recovery_and_schema_list_the_design_rework_slug() -> None:
    slugs = _section(
        _RECOVERY_TEXT,
        _RECOVERY,
        "### Stall `site` slugs",
        "### Systemic-park breaker interaction",
    )
    bullet = _bullet(slugs, _RECOVERY, "design_rework")
    _assert_present(
        bullet,
        _RECOVERY,
        "the `design_rework` slug bullet",
        ("Phase 6", "--rework", "detail"),
    )
    stall = _bullet(_deferred_log_section(), _STATE_SCHEMA, "stall")
    _assert_present(
        stall,
        _STATE_SCHEMA,
        "the deferred-log `stall` bullet",
        ("`design_rework`",),
    )


def test_release_checks_runs_both_design_contract_suites() -> None:
    echo = 'echo "[checks] design rework prose"'
    assert echo in _RELEASE_CHECKS_TEXT, (
        f"{_RELEASE_CHECKS}: expected the {echo!r} block — not found."
    )
    block = _RELEASE_CHECKS_TEXT[_RELEASE_CHECKS_TEXT.index(echo) :]
    _assert_present(
        block,
        _RELEASE_CHECKS,
        "the `[checks] design rework prose` block",
        (
            "skills/run-autopilot/scripts/test_design_review_contract.py",
            "skills/run-autopilot/cli/test_design_rework_prose.py",
        ),
    )


def test_changelog_added_carries_both_design_rework_entries() -> None:
    # The whole file's Added blocks, not [Unreleased]: a release moves the
    # entry under its version heading.
    added = _added_bullets(_CHANGELOG_TEXT, _CHANGELOG)
    for lead, needle in (
        ("- **design-solution**:", "--rework"),
        ("- **run-autopilot**:", "design_rework"),
    ):
        bullets = _rows_starting_with(added, lead)
        assert any(needle in bullet for bullet in bullets), (
            f"{_CHANGELOG}: expected a {lead!r} bullet under a "
            f"### Added heading mentioning {needle!r} — found {len(bullets)} {lead!r} "
            "bullet(s), none of which does."
        )


def test_roster_sentence_and_escalation_caveat_survive() -> None:
    assert _REVIEW_TEXT.count(_ROSTER_SENTENCE) == 1, (
        f"{_PHASE_REVIEW}: expected the review-lens roster sentence exactly "
        f"once, byte-identical — found {_REVIEW_TEXT.count(_ROSTER_SENTENCE)}. "
        "It must read exactly:\n" + _ROSTER_SENTENCE
    )
    assert _REVIEW_TEXT.count(_ESCALATION_CAVEAT) == 1, (
        f"{_PHASE_REVIEW}: expected the paragraph lead {_ESCALATION_CAVEAT!r} "
        f"exactly once — found {_REVIEW_TEXT.count(_ESCALATION_CAVEAT)}."
    )


def test_loop_mode_hands_off_after_task_add_before_work() -> None:
    # PRD 00208: in loop mode the session that designed the rework and created
    # the tasks ends before any fix runs; the fresh session resumes the
    # dispatch through Phase 4's existing skip.
    _assert_in_order(
        _DISPATCH,
        _PHASE_REVIEW,
        _DISPATCH_WHERE,
        (
            "`task-add <task-json-file>`",
            "**Loop mode (`$_AUTOPILOT_LOOP` set): hand off here, before any fix runs (PRD 00208).**",
            "rework designed, handing off",
            "END TURN",
            "**Interactive (no `$_AUTOPILOT_LOOP`):** invoke `/autopilot:work` now",
        ),
    )
    _assert_present(
        _DISPATCH,
        _PHASE_REVIEW,
        _DISPATCH_WHERE,
        ("no `phase-done`, the cycle is not over", "cli/routing.rework_resume"),
    )
    _assert_absent(
        _DISPATCH,
        _PHASE_REVIEW,
        _DISPATCH_WHERE,
        ("invoke `/autopilot:work` in this session", "hand-off is optional"),
    )

def test_phase_4_skip_is_the_rework_handoff_entry() -> None:
    skip = _paragraph(
        _REVIEW_TEXT,
        _PHASE_REVIEW,
        "**Skip Phases 4 and 5 and resume at Phase 6 \"Dispatch rework\"**",
    )
    _assert_present(
        skip,
        _PHASE_REVIEW,
        "the Phase 4 skip paragraph",
        ("after a rework hand-off", "PRD 00208"),
    )
    row = _single_row(_STATE_SCHEMA.read_text(), _STATE_SCHEMA, "the state schema", "| `rework_task_ids` |")
    assert "dispatch pending" in row, f"{_STATE_SCHEMA}: the rework_task_ids row lacks the resume note"

