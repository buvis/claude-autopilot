"""Corrections to the phase-delegation guard predicate: linear-time scanning,
distinct-path and distinct-id scoping, negation placement, first-token slash
commands, and unbounded whitespace in the suffix and task-range probes.

Sibling of test_guard_phase_delegation.py (kept apart for the file size limit).
Every case asserts on `find_phase_delegation`: None means the dispatch is
allowed, a non-empty quoted span means it is denied. The timing tests call
`is_phase_delegation` in-process, as test_guard_phase_delegation_dispatch.py
does, and bound the same seconds-per-megabyte figure.

The last section holds controls that no single rule above owns but that all of
them lean on: the denial span really quotes the input the guard read, the two
entry points agree, an ordinary prompt is still allowed and a paraphrased order
still denied, the verdict is deterministic, and the guard neither mutates its
caller's dict nor stops guarding after a few hundred calls.
"""

from __future__ import annotations

import importlib
import sys
import time
from collections.abc import Callable
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parent

MB = 1048576
# The same bound test_guard_phase_delegation_dispatch.py pins as
# BUDGET_S_PER_MB, re-declared rather than imported across test modules.
BUDGET_S_PER_MB = 0.3
# A linear scan keeps the per-megabyte rate flat as the prompt grows; the slack
# absorbs the fixed per-call cost, which inflates the smallest size's rate. A
# quadratic scan would multiply the rate by sixteen over a fourfold size step.
LINEAR_GROWTH_SLACK = 3.0
# A denial span is an excerpt of what the guard read, not a label. Anything
# longer is prose the operator cannot locate in the dispatch they just wrote.
SPAN_MAX_CHARS = 120


def _guard_module():
    sys.path.insert(0, str(HOOKS))
    return importlib.import_module("guard_phase_delegation")


def _find(tool_input: dict[str, str]) -> str | None:
    # Input purity is checked on every case, not only in the dedicated test
    # below: a guard that pops its caller's "prompt" key would otherwise stay
    # invisible to a suite that never looks at the dict again.
    before = dict(tool_input)
    span = _guard_module().find_phase_delegation(tool_input)
    assert tool_input == before, f"the guard mutated its input into {tool_input!r}"
    return span


def _assert_allowed(prompt: str) -> None:
    span = _find({"prompt": prompt})
    assert span is None, f"expected an allow, got the span {span!r}"


def _assert_denied_input(tool_input: dict[str, str], haystack: str) -> str:
    span = _find(tool_input)
    assert isinstance(span, str), f"expected a quoted span, got {span!r}"
    assert span, "expected a non-empty quoted span"
    # The span has to quote the text the guard read, so the operator can find
    # the order it was denied for. A constant label passes truthiness alone.
    quoted = span.strip().strip("'\"")
    assert quoted in haystack, f"the span {span!r} is not an excerpt of the input"
    assert len(span) <= SPAN_MAX_CHARS, f"the span runs {len(span)} chars"
    return span


def _assert_denied(prompt: str) -> str:
    return _assert_denied_input({"prompt": prompt}, prompt)


def _time_predicate(prompt: str) -> float:
    predicate = _guard_module().is_phase_delegation
    start = time.perf_counter()
    predicate({"prompt": prompt})
    return time.perf_counter() - start


def _best_seconds_per_mb(build: Callable[[int], str]) -> float:
    # Best of three, not a mean: the figure being bounded is the predicate's
    # own cost, and a scheduler hiccup on one run is not that cost. Every
    # repetition builds a FRESH prompt, so a per-prompt memo cannot turn the
    # second and third runs into dict hits and hide the scan being timed.
    rates = []
    for repetition in range(3):
        prompt = build(repetition)
        rates.append(_time_predicate(prompt) / (len(prompt) / MB))
    return min(rates)


# 1. One very long unbroken token must not make the scan super-linear.


def _unbroken_token_builder(size: int) -> Callable[[int], str]:
    return lambda repetition: (
        f"Run the work phase for PRD 7. {'a' * size} #{repetition}"
    )


def test_rejects_a_long_unbroken_token_in_linear_time() -> None:
    sizes = (20000, 40000, 80000)
    builders = {n: _unbroken_token_builder(n) for n in sizes}
    rates = {n: _best_seconds_per_mb(b) for n, b in builders.items()}

    # Printed before the assertions so `pytest -s` shows the real numbers even
    # when one of them fails the budget.
    print("unbroken-token s/MB " + " ".join(f"{n}={rates[n]:.4f}" for n in sizes))

    for n in sizes:
        _assert_denied(builders[n](0))
        assert rates[n] < BUDGET_S_PER_MB, f"{n} chars cost {rates[n]:.4f} s/MB"

    assert rates[80000] <= rates[20000] * LINEAR_GROWTH_SLACK, (
        f"rate grew from {rates[20000]:.4f} to {rates[80000]:.4f} s/MB "
        "over a fourfold size step"
    )


def _base64_blob(repetition: int) -> str:
    # One '/' in 64 and no '.', the shape a pasted base64 payload has.
    return (
        "Run the work phase for PRD 7. " + ("A" * 63 + "/") * 1500 + f" #{repetition}"
    )


def _slash_run(repetition: int) -> str:
    return "Run the work phase for PRD 7. " + "/" * 200000 + f" #{repetition}"


@pytest.mark.parametrize(
    "build",
    [_base64_blob, _slash_run],
    ids=["base64-blob", "dense-slash-run"],
)
def test_rejects_a_long_slash_bearing_token_in_linear_time(
    build: Callable[[int], str],
) -> None:
    # A slash INSIDE the long token is what a scan of `\S*/\S+\.\w+` per '/'
    # was quadratic on (1.66 s/MB on the blob) and cubic on (3520 s/MB on the
    # slash run, a hung hook). The token checks have no per-slash cost.
    rate = _best_seconds_per_mb(build)
    print(f"slash-bearing s/MB={rate:.4f} over {len(build(0)) / MB:.2f} MB")

    _assert_denied(build(0))
    assert rate < BUDGET_S_PER_MB, f"{len(build(0))} chars cost {rate:.4f} s/MB"


# 2. Many phase mentions inside a single clause must not make it super-linear
#    either, and the whole prompt is in scope: the verdict below turns on an
#    order that sits past offset 100000.


def test_rejects_many_phase_mentions_in_one_clause_in_linear_time() -> None:
    deep = "filler words here. " * 6000 + "Now run the work phase for PRD 00412."
    assert deep.index("run the work phase") > 100000, "the probe lost its offset"
    _assert_denied(deep)

    def build(repetition: int) -> str:
        return "about the work phase and " * 160000 + f" #{repetition}"

    rate = _best_seconds_per_mb(build)
    print(f"one-clause mentions s/MB={rate:.4f} over {len(build(0)) / MB:.2f} MB")

    assert rate < BUDGET_S_PER_MB, f"{len(build(0))} chars cost {rate:.4f} s/MB"


#    A whitespace run that the weak-anchor tail itself has to walk is the third
#    shape: with no clause or sentence boundary between the phase name and the
#    run, the tail is matched over the run, and two adjacent `\s*` groups there
#    hand it back one space at a time (24.99 s/MB at 12500 spaces, 100.14 at
#    50000, doubling with the run - quadratic).


def _whitespace_tail(repetition: int) -> str:
    # No '.', ',' or '\n' anywhere: the clause and the sentence both run to the
    # end of the prompt, so the weak-anchor tail spans the whole space run.
    # 50000 spaces is the largest run the report measured (105 s/MB, about 5 s
    # of wall clock, the hook's whole timeout budget); a bigger run would take
    # minutes to fail rather than seconds, for the same verdict.
    return "Run the work phase" + " " * 50000 + f"word{repetition}"


def test_scans_a_whitespace_run_behind_a_candidate_in_linear_time() -> None:
    rate = _best_seconds_per_mb(_whitespace_tail)
    print(
        f"whitespace-tail s/MB={rate:.4f} over "
        f"{len(_whitespace_tail(0)) / MB:.2f} MB"
    )

    assert rate < BUDGET_S_PER_MB, (
        f"{len(_whitespace_tail(0))} chars cost {rate:.4f} s/MB"
    )


# 3. A negation in front of the verb, not in front of the path, still negates
#    the order to follow a phase SKILL.md.


def test_allows_a_negation_sitting_before_the_verb() -> None:
    _assert_allowed("Read skills/work/SKILL.md; you must never follow it")


def test_a_skill_md_follow_order_without_a_negation_stays_denied() -> None:
    _assert_denied("Read skills/work/SKILL.md; you must follow it")


# 4. A phase slash command counts only when the first token IS the command.


@pytest.mark.parametrize(
    "prompt",
    [
        "/autopilot:work-adjacent thing",
        "/autopilot:plan-tasks-ish thing",
        "/autopilot:design-solution-helper thing",
    ],
    ids=["work-adjacent", "plan-tasks-ish", "design-solution-helper"],
)
def test_allows_a_longer_token_that_only_begins_with_a_phase_command(
    prompt: str,
) -> None:
    _assert_allowed(prompt)


@pytest.mark.parametrize(
    "command",
    ["/autopilot:work", "/autopilot:plan-tasks", "/autopilot:design-solution"],
    ids=["work", "plan-tasks", "design-solution"],
)
@pytest.mark.parametrize(
    "shape",
    ["{c}", "   {c}", "{c} for PRD 00300", "  {c} for PRD 00300"],
    ids=["bare", "leading-space", "trailing-text", "both"],
)
def test_a_first_token_that_is_a_phase_command_stays_denied(
    command: str,
    shape: str,
) -> None:
    _assert_denied(shape.format(c=command))


# 5. A file path scopes a dispatch; the same path twice is still one path.


def test_allows_one_path_repeated() -> None:
    _assert_allowed("Run the work phase for PRD 00300. See a/b.py and a/b.py")


def test_two_distinct_paths_do_not_scope_and_stay_denied() -> None:
    _assert_denied("Run the work phase for PRD 00300. See a/b.py and c/d.py")


def test_allows_a_path_whose_only_dot_sits_before_a_later_slash() -> None:
    # The dot is in an earlier segment, not in the basename. It still makes
    # "docs/v1.2" a path, so the dispatch names one file and is scoped: a token
    # check that looked for the dot after the LAST slash only denied this.
    _assert_allowed("Run the work phase for PRD 00300, see docs/v1.2/notes")


# 6. A PRD-lifecycle store path never scopes a dispatch, however it is written.


@pytest.mark.parametrize(
    "prompt",
    [
        "Run the work phase for PRD 00300, see prds/wip/00300.md",
        "Run the work phase for PRD 00300, see "
        "docs/dev/project-management/prds/wip/00300.md",
    ],
    ids=["root-relative", "with-leading-directory"],
)
def test_rejects_a_root_relative_prd_store_path_as_scope(prompt: str) -> None:
    _assert_denied(prompt)


# 7. A task id scopes a dispatch; the same id twice is still one id.


def test_allows_one_task_id_repeated() -> None:
    _assert_allowed("Run the work phase for task 3, yes task 3")


def test_two_distinct_task_ids_do_not_scope_and_stay_denied() -> None:
    _assert_denied("Run the work phase for task 3 and task 5")


def test_a_task_id_repeated_in_another_sentence_does_not_scope() -> None:
    # Ids fold by (sentence, id), not field-wide, on purpose: a bare number is
    # a reference its own sentence carries, so a repeat in a LATER sentence
    # does not narrow the dispatch to one job and the dispatch stays denied.
    # Folding field-wide would make the padded prompt of
    # test_guard_phase_delegation_structure.py::
    # test_lookalike_far_inside_a_long_prompt_is_normalized_and_denied read as
    # scoped and allowed, weakening the normalization rule that test pins.
    _assert_denied("Run the work phase for task 3. Also do task 3.")


# 8. Range wording beside ANY task id refuses task-based scope outright.


@pytest.mark.parametrize(
    "prompt",
    [
        "Run the work phase from task 3 onwards and task 5",
        "Run the work phase from task 3 onwards",
    ],
    ids=["ranged-id-plus-unranged-id", "ranged-id-alone"],
)
def test_rejects_a_task_id_that_carries_range_wording_anywhere(prompt: str) -> None:
    _assert_denied(prompt)


# 9. The " skill" suffix and the range wording are separated from what they
#    attach to by whitespace of any length, so the long forms read like the
#    short ones.


@pytest.mark.parametrize(
    "prompt",
    [
        "Run the `autopilot:work`" + " " * 40 + "skill",
        "Run the `autopilot:work` skill",
        "Run the work phase from" + " " * 40 + "task 3",
        "Run the work phase from task 3",
    ],
    ids=[
        "suffix-long-whitespace",
        "suffix-one-space",
        "range-long-whitespace",
        "range-one-space",
    ],
)
def test_rejects_unbounded_whitespace_in_the_suffix_and_range_probes(
    prompt: str,
) -> None:
    _assert_denied(prompt)


# 10. Controls. None of the rules above names these, and all of them assume
#     them: an ordinary prompt passes, a reworded order does not, the two entry
#     points answer alike, the answer is the same twice, and the guard keeps no
#     state across calls.


def test_allows_an_ordinary_prompt_that_orders_no_phase() -> None:
    _assert_allowed("Review README.md and report typos")


def test_rejects_a_phase_order_phrased_in_other_words() -> None:
    _assert_denied("please go do the work phase for PRD 00412 end to end")


def test_the_predicate_agrees_with_the_span_finder() -> None:
    module = _guard_module()
    for prompt, denied in (
        ("Review README.md and report typos", False),
        ("Run the work phase for PRD 00412", True),
    ):
        tool_input = {"prompt": prompt}
        verdict = module.is_phase_delegation(tool_input)
        span = module.find_phase_delegation(tool_input)
        assert bool(verdict) == denied, f"{prompt!r} gave the verdict {verdict!r}"
        assert bool(verdict) == (span is not None), (
            f"is_phase_delegation said {verdict!r} while the span was {span!r}"
        )


def test_gives_the_same_verdict_on_a_repeated_call() -> None:
    module = _guard_module()
    prompts = [f"Run the work phase for PRD {400 + n:05d}" for n in range(4)]
    prompts += [f"Please review notes_{n}.md and summarise it" for n in range(4)]
    for prompt in prompts:
        first = module.find_phase_delegation({"prompt": prompt})
        second = module.find_phase_delegation({"prompt": prompt})
        assert first == second, f"{prompt!r} gave {first!r}, then {second!r}"
        verdict = module.is_phase_delegation({"prompt": prompt})
        assert bool(verdict) == (first is not None), (
            f"{prompt!r} gave the span {first!r} and the verdict {verdict!r}"
        )


def test_leaves_the_tool_input_it_was_handed_unchanged() -> None:
    tool_input = {
        "prompt": "Run the work phase for PRD 00412",
        "description": "dispatch the phase",
        "subagent_type": "general-purpose",
    }
    before = dict(tool_input)
    module = _guard_module()
    module.find_phase_delegation(tool_input)
    assert tool_input == before, f"find mutated the input into {tool_input!r}"
    module.is_phase_delegation(tool_input)
    assert tool_input == before, f"the predicate mutated it into {tool_input!r}"


def test_keeps_denying_after_six_hundred_calls() -> None:
    module = _guard_module()
    for n in range(600):
        module.is_phase_delegation({"prompt": f"Review notes_{n}.md for typos"})
    _assert_denied("Run the work phase for PRD 00412")


# The environment must not hold an off switch for a guard: the names below are
# the ones a "make it fast" or "turn it off" patch reaches for first.
KILL_SWITCH_NAMES = (
    "GUARD_PHASE_DELEGATION_OFF",
    "AUTOPILOT_GUARDS_OFF",
    "AUTOPILOT_SKIP_GUARDS",
    "AUTOPILOT_FAST",
)


def test_keeps_denying_with_every_plausible_kill_switch_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _guard_module()
    for name in KILL_SWITCH_NAMES:
        monkeypatch.setenv(name, "1")
    # Reloaded under the patched environment, so a switch read at import time
    # counts as much as one read per call.
    importlib.reload(module)
    try:
        _assert_denied("Run the work phase for PRD 00412")
    finally:
        monkeypatch.undo()
        importlib.reload(module)


def test_rejects_a_phase_order_carried_by_the_description() -> None:
    description = "Run the work phase for PRD 00412"
    _assert_denied_input(
        {"description": description, "prompt": "Proceed as described"},
        description,
    )


def test_allows_a_tool_input_that_carries_no_prompt() -> None:
    assert _find({}) is None, "an empty tool input is not a phase order"


def _dense_skill_md_mentions(repetition: int) -> str:
    # A SKILL.md reference roughly every 75 characters, each with its own
    # negated follow order ("never follow it"), so none of the thousands of
    # mentions in the ~1 MB field short-circuits the scan early: every one
    # pays the path match, the bounded _FOLLOW probe and the negation check
    # before the call can finish.
    unit = "skills/work/SKILL.md never follow it. " + "x" * 35
    return unit * (MB // len(unit)) + f" #{repetition}"


def test_dense_skill_md_mentions_stay_under_budget() -> None:
    sample = _dense_skill_md_mentions(0)
    assert sample.count("SKILL.md") > 10000
    _assert_allowed(sample)
    rate = _best_seconds_per_mb(_dense_skill_md_mentions)
    print(f"dense-skill-md s/MB={rate:.4f} over {len(sample) / MB:.2f} MB")
    assert rate < BUDGET_S_PER_MB, f"{len(sample)} chars cost {rate:.4f} s/MB"
