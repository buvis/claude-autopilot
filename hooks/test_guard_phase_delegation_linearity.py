"""Corrections to the phase-delegation guard predicate: linear-time scanning,
distinct-path and distinct-id scoping, negation placement, first-token slash
commands, and unbounded whitespace in the suffix and task-range probes.

Sibling of test_guard_phase_delegation.py (kept apart for the file size limit).
Every case asserts on `find_phase_delegation`: None means the dispatch is
allowed, a non-empty quoted span means it is denied. The two timing tests call
`is_phase_delegation` in-process, as test_guard_phase_delegation_dispatch.py
does, and bound the same seconds-per-megabyte figure.
"""

from __future__ import annotations

import importlib
import sys
import time
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


def _guard_module():
    sys.path.insert(0, str(HOOKS))
    return importlib.import_module("guard_phase_delegation")


def _assert_allowed(prompt: str) -> None:
    span = _guard_module().find_phase_delegation({"prompt": prompt})
    assert span is None, f"expected an allow, got the span {span!r}"


def _assert_denied(prompt: str) -> None:
    span = _guard_module().find_phase_delegation({"prompt": prompt})
    assert isinstance(span, str), f"expected a quoted span, got {span!r}"
    assert span, "expected a non-empty quoted span"


def _time_predicate(prompt: str) -> float:
    predicate = _guard_module().is_phase_delegation
    start = time.perf_counter()
    predicate({"prompt": prompt})
    return time.perf_counter() - start


def _best_seconds_per_mb(prompt: str) -> float:
    # Best of three, not a mean: the figure being bounded is the predicate's
    # own cost, and a scheduler hiccup on one run is not that cost.
    best = min(_time_predicate(prompt) for _ in range(3))
    return best / (len(prompt) / MB)


# 1. One very long unbroken token must not make the scan super-linear.


def test_rejects_a_long_unbroken_token_in_linear_time() -> None:
    sizes = (20000, 40000, 80000)
    prompts = {n: "Run the work phase for PRD 7. " + "a" * n for n in sizes}
    rates = {n: _best_seconds_per_mb(p) for n, p in prompts.items()}

    # Printed before the assertions so `pytest -s` shows the real numbers even
    # when one of them fails the budget.
    print("unbroken-token s/MB " + " ".join(f"{n}={rates[n]:.4f}" for n in sizes))

    for n in sizes:
        _assert_denied(prompts[n])
        assert rates[n] < BUDGET_S_PER_MB, f"{n} chars cost {rates[n]:.4f} s/MB"

    assert rates[80000] <= rates[20000] * LINEAR_GROWTH_SLACK, (
        f"rate grew from {rates[20000]:.4f} to {rates[80000]:.4f} s/MB "
        "over a fourfold size step"
    )


# 2. Many phase mentions inside a single clause must not make it super-linear
#    either. The budget is the rule here; no verdict is pinned.


def test_rejects_many_phase_mentions_in_one_clause_in_linear_time() -> None:
    prompt = "about the work phase and " * 160000

    rate = _best_seconds_per_mb(prompt)
    print(f"one-clause mentions s/MB={rate:.4f} over {len(prompt) / MB:.2f} MB")

    assert rate < BUDGET_S_PER_MB, f"{len(prompt)} chars cost {rate:.4f} s/MB"


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
