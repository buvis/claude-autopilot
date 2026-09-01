"""Tests for the default_model floor in classify_tier.py's ``_apply_floor()``.

Split out of test_classify_tier.py (which grew past the repo's 800-line file
cap) into this and its sibling test_classify_tier_*.py modules; see
_classify_tier_test_support.py for the shared classify_tier bootstrap and the
_classify helper every one of them calls.
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

_classify = _support._classify


def test_a_higher_default_model_raises_the_tier_and_renames_the_reason() -> None:
    # The batch floor overrides the classification, and the record has to say
    # so: keeping "test_port" here would hide why the task ran on opus.
    result = _classify(
        ["tests/test_x.py"],
        "port the concurrency tests",
        10,
        default_model="opus",
    )

    assert result == {"model": "opus", "tier_reason": "floor"}


@pytest.mark.parametrize("default_model", ["haiku", "sonnet"])
def test_a_default_model_at_or_below_the_tier_changes_nothing(
    default_model: str,
) -> None:
    # A floor only lifts. Equal is not a raise, so the reason stays "default".
    result = _classify(
        ["cache/store.py", "cache/keys.py", "cli/main.py"],
        "design and migrate the cache layer",
        120,
        default_model=default_model,
    )

    assert result == {"model": "sonnet", "tier_reason": "default"}


def test_a_default_model_floor_lifts_haiku_to_sonnet(
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = _classify(
        ["src/app.py"],
        "rename foo to bar",
        10,
        default_model="sonnet",
    )

    assert result == {"model": "sonnet", "tier_reason": "floor"}
    # A valid floor is routine, so it says nothing. Without this the stderr
    # assertion in the "fable" test passes on a classifier that warns on every
    # single call.
    assert capsys.readouterr().err == ""


def test_a_default_model_of_opus_leaves_an_opus_classification_alone() -> None:
    # The top of the ordering floored at the top of the ordering. Nothing was
    # raised, so nothing is renamed: recording "floor" here would erase the
    # real reason the task went to opus and make the floor look responsible.
    result = _classify(
        ["cli/schema.py"],
        "widen the result schema",
        30,
        contract_edit=True,
        default_model="opus",
    )

    assert result == {"model": "opus", "tier_reason": "contract"}


def test_classify_never_writes_to_stderr_even_for_an_unknown_default_model(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # classify() is a pure core, not the CLI: a caller that imports this
    # module as a library (a batch driver, another skill) has to be able to
    # classify a task without the module writing to the process's stderr
    # behind its back. The CLI test right below pins the same "fable" input
    # at the process boundary; this one pins that the core itself never
    # touches stderr, so the only way both stay true is for the warning to
    # live in main(), not in classify().
    result = _classify(
        ["cache/store.py", "cache/keys.py", "cli/main.py"],
        "design and migrate the cache layer",
        120,
        default_model="fable",
    )

    assert result == {"model": "sonnet", "tier_reason": "default"}
    assert capsys.readouterr().err == ""
