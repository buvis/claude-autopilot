"""Prose pins for the foreground command budgets and the separation rule
(PRD 00167).

Same pattern as test_dispatch_prose.py - read the file once, assert on short,
reword-resistant substrings, each with a failure message naming what drifted.
Separate file because merging these pins into test_dispatch_prose.py pushed it
to 801 lines and the pack's own step-5.65 style gate flagged the crossing
(`FILE | test_dispatch_prose.py | 801 lines`, on this PRD's first draft).

Nothing executes a budget but a reader: the Bash `timeout` parameter is a
harness feature, so the prose is the whole mechanism. A deleted rule leaves
every other suite green while foreground commands go back to hanging unbounded,
which is the failure PRD 00167 exists to stop.
"""

from __future__ import annotations

import re
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
_WORK = _SCRIPTS.parent
_REFS = _WORK / "references"
_SKILL_MD = _WORK / "SKILL.md"

_SEPARATION_SENTENCE = "Never combine an inspection"
_BUDGET_SENTENCE = "Pass an explicit `timeout` on every Bash call"


def test_the_budgets_and_the_separation_rule_live_in_one_file() -> None:
    dispatch = (_REFS / "subagent-dispatch.md").read_text()

    for heading in (
        "## Foreground command budgets",
        "## Never combine inspection with verification",
    ):
        assert heading in dispatch, (
            f"references/subagent-dispatch.md has no {heading!r} section. Every "
            "call site cites it by name, so deleting it leaves the budgets and "
            "the separation rule stated nowhere."
        )


def test_every_budget_class_keeps_its_number() -> None:
    # All three, not just one: a pin on a single value stays green while the
    # other two classes lose their deadlines and go back to unbounded.
    # Digit-bounded, because a plain substring check cannot fail here: "60000"
    # sits inside "600000", so the inspection pin would pass on a file that had
    # lost the inspection budget entirely and kept only the full-suite one.
    dispatch = (_REFS / "subagent-dispatch.md").read_text()

    for budget, klass in (
        ("60000", "inspection"),
        ("300000", "lint and narrow tests"),
        ("600000", "foreground full suite"),
    ):
        assert re.search(rf"(?<!\d){budget}(?!\d)", dispatch), (
            f"references/subagent-dispatch.md no longer states the {klass} "
            f"budget ({budget} ms). Without a number the rule is a sentiment "
            "and every call site improvises its own deadline."
        )

    assert "20 min" in dispatch, (
        "references/subagent-dispatch.md dropped the 20 min `Monitor` wait on "
        "backgrounded full suites. PRD 00167 shrinks no deadline that already "
        "existed; losing that row is exactly the shrink it forbids."
    )


def test_a_class_with_no_larger_budget_records_its_first_timeout() -> None:
    # The stamp used to key on a "second timeout" everywhere, while the full
    # suite explicitly got no re-run - so the longest command in the pack could
    # time out and be recorded nowhere. Both sites have to carry the carve-out.
    dispatch = (_REFS / "subagent-dispatch.md").read_text()
    final = (_REFS / "final-verification.md").read_text()

    assert "**first** timeout is terminal" in dispatch, (
        "references/subagent-dispatch.md § Foreground command budgets no longer "
        "says a class with no larger budget records its FIRST timeout. A "
        "re-run-then-record rule alone leaves a foreground full suite "
        "unrecordable, which is the one class the loop waits on longest."
    )
    assert "**first** timeout is terminal" in final, (
        "references/final-verification.md § Timed-out commands no longer says "
        "the full suite's first timeout is terminal, so step 7 waits for a "
        "second timeout that its own no-re-run rule can never produce."
    )


def test_a_step_7_timeout_is_recorded_where_it_can_actually_be_written() -> None:
    # `task-done` appends the last attempt entry at task exit, before step 7
    # runs, so a step-7 timeout has no live entry to stamp. Saying otherwise
    # sends the executor looking for a write path that does not exist.
    final = (_REFS / "final-verification.md").read_text()
    assert "**whole**" in final, (
        "references/final-verification.md § Timed-out commands no longer says "
        "the phase report is a step-7 timeout's whole record. Every attempt "
        "entry is already written by then; pointing at one invents a write "
        "path `task-done` and `append-attempt` do not offer."
    )

    attempt_logging = (_REFS / "attempt-logging.md").read_text()
    assert "never here" in attempt_logging, (
        "references/attempt-logging.md's `verification` row no longer excludes "
        "step-7 timeouts, so the field claims a value nothing can write."
    )
    # The red-check's neighbour case: step 2.95 takes the lint budget but keeps
    # its OWN field. Routing its timeout to `verification` would leave
    # `red_check` absent, which attempt-logging.md reads as "ran, saw red".
    assert 'red_check: "skipped:<cause>"' in attempt_logging, (
        "references/attempt-logging.md's `verification` row no longer sends a "
        "step-2.95 red-check timeout to `red_check`. Two fields would then "
        "claim one event, and an absent `red_check` reads as a check that ran."
    )


def test_the_verification_call_sites_name_the_separation_rule() -> None:
    final = (_REFS / "final-verification.md").read_text()
    assert "Never combine" in final, (
        "references/final-verification.md § What to run no longer points at the "
        "separation rule; its bare 'do not chain with &&' reads as being about "
        "chaining two verifications, which is how the combined "
        "inspect-and-verify command stayed unremarkable."
    )

    gate_failure = (_REFS / "gate-failure.md").read_text()
    assert "300000" in gate_failure, (
        "references/gate-failure.md § Narrow scope no longer names the lint and "
        "narrow-tests budget, so the step-5.5 gate commands run unbounded."
    )


def test_every_persona_that_carries_the_prologue_carries_both_rules() -> None:
    # Implementors inherit their Bash rules from the prologue line and nowhere
    # else, and the line physically lives in the persona files - SKILL.md
    # stating it changes nothing on its own. All four or the rule is partial.
    prologue_carriers = (
        _SKILL_MD,
        _WORK.parent.parent / "agents" / "ivan.md",
        _REFS / "tess-prompt.md",
        _REFS / "tess-retry-prompt.md",
    )

    for path in prologue_carriers:
        body = path.read_text()
        for sentence in (_SEPARATION_SENTENCE, _BUDGET_SENTENCE):
            assert sentence in body, (
                f"{path} no longer carries {sentence!r}. SKILL.md declares the "
                "dispatch prologue as a line every dispatch prompt must contain "
                "verbatim, and these are the files a rendered prompt is built "
                "from - a rule missing from one of them reaches that "
                "implementor not at all."
            )


def test_both_records_enumerate_the_verification_timeout_value() -> None:
    attempt_logging = (_REFS / "attempt-logging.md").read_text()
    schema = (
        _WORK.parent / "run-autopilot" / "references" / "state-schema.md"
    ).read_text()

    assert (
        '"verification": "skipped:<cause>" | "timeout:<command>" | null'
        in attempt_logging
    ), (
        "references/attempt-logging.md no longer carries the verification "
        "signature line with its timeout value; /work writes it, so a reader "
        "auditing the record cannot tell a check that never ran from one that "
        "ran and returned no verdict."
    )
    assert "timeout:<command>" in schema, (
        "run-autopilot/references/state-schema.md omits the verification "
        "timeout value from the tasks[].attempts signature, so a value /work "
        "writes is undeclared."
    )
