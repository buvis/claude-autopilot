"""Tests for the contract_edit/algorithmic_risk arms of classify_tier.py.

Split out of test_classify_tier.py (which grew past the repo's 800-line file
cap) into this and its sibling test_classify_tier_*.py modules; see
_classify_tier_test_support.py for the shared classify_tier/work_routing
bootstrap and the _classify helper every one of them calls. These tests pin
that both task-local risk flags outrank the mechanical rule, and that
contract_edit outranks algorithmic_risk when both are set.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SUPPORT_PATH = Path(__file__).with_name("_classify_tier_test_support.py")
_SUPPORT_SPEC = importlib.util.spec_from_file_location(
    "classify_tier_test_support", _SUPPORT_PATH
)
assert _SUPPORT_SPEC is not None and _SUPPORT_SPEC.loader is not None
_support = importlib.util.module_from_spec(_SUPPORT_SPEC)
_SUPPORT_SPEC.loader.exec_module(_support)

classify_tier = _support.classify_tier
work_routing = _support.work_routing
_classify = _support._classify


def test_a_contract_edit_routes_to_opus() -> None:
    result = _classify(
        ["cli/schema.py"],
        "widen the result schema",
        30,
        contract_edit=True,
    )

    assert result == {"model": "opus", "tier_reason": "contract"}


def test_algorithmic_risk_routes_to_opus() -> None:
    result = _classify(
        ["cli/loop.py"],
        "fix the retry backoff",
        30,
        algorithmic_risk=True,
    )

    assert result == {"model": "opus", "tier_reason": "algorithmic_risk"}


def test_a_contract_edit_outranks_algorithmic_risk_when_both_are_flagged() -> None:
    # Both flags buy opus, so the tier hides the ordering and only the recorded
    # reason exposes it. The spec checks contract first, and the record is what
    # a later reader uses to know which risk paid for the tier.
    result = _classify(
        ["cli/x.py"],
        "",
        30,
        contract_edit=True,
        algorithmic_risk=True,
    )

    assert result == {"model": "opus", "tier_reason": "contract"}


@pytest.mark.parametrize(
    "phrase",
    ["add log", "rename", "port", "mirror", "bump version"],
)
def test_a_contract_edit_outranks_the_mechanical_rule_even_when_every_mechanical_precondition_holds(
    phrase: str,
) -> None:
    # Every existing risk-flag fixture uses text that is not a mechanical
    # phrase, so rule 5 could be checked ahead of rule 3 and the suite would
    # still pass. Here all three mechanical preconditions hold at once (a real
    # phrase, one file, a small diff) on an ordinary production path, so this
    # only passes sonnet/opus at all if contract_edit is checked first.
    files = ["src/app.py"]
    assert not work_routing.is_test_path(files[0])
    assert not classify_tier.is_packaging_path(files[0])

    result = _classify(
        files,
        f"{phrase} across the retry handler",
        10,
        contract_edit=True,
    )

    assert result == {"model": "opus", "tier_reason": "contract"}


@pytest.mark.parametrize(
    "phrase",
    ["add log", "rename", "port", "mirror", "bump version"],
)
def test_algorithmic_risk_outranks_the_mechanical_rule_even_when_every_mechanical_precondition_holds(
    phrase: str,
) -> None:
    # Mirror of the contract_edit case above with the other risk flag: same
    # mechanical-shaped input, so a mechanical-rule-first ordering would answer
    # haiku/mechanical here too.
    files = ["src/app.py"]
    assert not work_routing.is_test_path(files[0])
    assert not classify_tier.is_packaging_path(files[0])

    result = _classify(
        files,
        f"{phrase} across the retry handler",
        10,
        algorithmic_risk=True,
    )

    assert result == {"model": "opus", "tier_reason": "algorithmic_risk"}
