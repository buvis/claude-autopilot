"""Tests for card.py, the fast-track spec-card parser.

The cards under fixtures/ are the inputs an operator hands the lane: one valid
card, one card at the size limits, and one deliberately broken card per rule
the parser enforces. The card is the lane's only input, so every rule here is
about refusing to guess - an absent section is an error, never a default.

card.py is not an installed package, so it is loaded by path, the same idiom
the plan-tasks script tests use.
"""

from __future__ import annotations

import dataclasses
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).with_name("card.py")
_FIXTURES_DIR = Path(__file__).with_name("fixtures")

_SPEC = importlib.util.spec_from_file_location("fast_track_card", _MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_card = importlib.util.module_from_spec(_SPEC)
# Registered before exec_module on purpose: a module built with
# `from __future__ import annotations` and @dataclass resolves its own
# annotations by looking itself up in sys.modules, and an unregistered module
# makes that lookup fail at import time. Either style has to stay open to the
# implementor.
sys.modules[_SPEC.name] = _card
_SPEC.loader.exec_module(_card)

CardError = _card.CardError
load_card = _card.load_card

_TEST_ID = "skills/fast-track/scripts/test_card.py::"
_GATE_PYTEST = (
    "uv run --no-project --with pytest python -m pytest -q skills/fast-track/scripts"
)
_GATE_CLI = (
    "python3 skills/fast-track/scripts/card.py "
    "skills/fast-track/scripts/fixtures/valid.md"
)
_VALID_CARD_FILES = [
    "skills/fast-track/scripts/card.py",
    "skills/fast-track/scripts/test_card.py",
    "skills/fast-track/scripts/fixtures/valid.md",
    "skills/fast-track/scripts/fixtures/missing_docs.md",
    "skills/fast-track/scripts/fixtures/missing_transport_impact.md",
    "skills/fast-track/scripts/fixtures/unknown_model.md",
    "skills/fast-track/scripts/fixtures/gate_chained_and.md",
    "skills/fast-track/scripts/fixtures/gate_chained_semicolon.md",
    "skills/fast-track/scripts/fixtures/gate_chained_pipe.md",
    "skills/fast-track/scripts/fixtures/empty_tests_valid.md",
    "skills/fast-track/scripts/fixtures/thirteen_files.md",
    "skills/fast-track/scripts/fixtures/goal_too_long.md",
]


def _fixture(name: str) -> Path:
    path = _FIXTURES_DIR / name
    assert path.is_file(), f"missing fixture card: {path}"
    return path


def _run_cli(card_path: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_MODULE_PATH), str(card_path)],
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize(
    ("fixture_name", "section"),
    [
        ("missing_goal.md", "goal"),
        ("missing_tests.md", "tests"),
        ("missing_files.md", "files"),
        ("missing_constraints.md", "constraints"),
        ("missing_docs.md", "docs"),
        ("missing_gates.md", "gates"),
        ("missing_transport_impact.md", "transport"),
    ],
)
def test_missing_section_names_the_field(fixture_name: str, section: str) -> None:
    # A card is assembled into a review lane with no other input, so a section
    # the operator forgot must stop the load and say which one. Naming it is
    # the whole point: "invalid card" sends the operator re-reading seven
    # headings. All seven are covered - each arm deletes exactly one - so a
    # parser that only guards the sections it happens to look up by name fails
    # the rest, and one that reaches for a section it never found blows up
    # with its own traceback instead of exiting 2.
    card_path = _fixture(fixture_name)

    with pytest.raises(CardError) as excinfo:
        load_card(card_path)

    assert section in excinfo.value.field.lower()

    result = _run_cli(card_path)

    assert result.returncode == 2
    assert section in result.stderr.lower()
    assert result.stdout == ""


@pytest.mark.parametrize(
    "fixture_name",
    [
        "unknown_model.md",
        "unknown_model_gpt_4_turbo.md",
        "unknown_model_empty.md",
    ],
)
def test_unknown_model_exits_two(fixture_name: str) -> None:
    # "haiku" is a real model elsewhere but not one this lane offers,
    # "gpt-4-turbo" belongs to another vendor, and a blank value names nothing
    # at all. A parser that passed any of them through would dispatch the
    # implementor to a model the lane cannot route, so the value is refused at
    # parse time and the CLI says which field was wrong. The three arms share
    # no common shape, so only an allowlist of sonnet and opus passes them all
    # - a list of known-bad names cannot.
    card_path = _fixture(fixture_name)

    with pytest.raises(CardError) as excinfo:
        load_card(card_path)

    assert excinfo.value.field.lower() == "model"

    result = _run_cli(card_path)

    assert result.returncode == 2
    assert "model" in result.stderr.lower()
    assert result.stdout == ""


@pytest.mark.parametrize(
    "fixture_name",
    ["unknown_suite_banana.md", "unknown_suite_empty.md"],
)
def test_unknown_suite_exits_two(fixture_name: str) -> None:
    # The suite key picks how the lane runs the gates - batch or per-item -
    # and there is no third mode to fall back on, so an unrecognised value is
    # refused for the same reason an unrecognised model is. A nonsense word
    # and a blank value are both covered.
    card_path = _fixture(fixture_name)

    with pytest.raises(CardError) as excinfo:
        load_card(card_path)

    assert excinfo.value.field.lower() == "suite"

    result = _run_cli(card_path)

    assert result.returncode == 2
    assert "suite" in result.stderr.lower()
    assert result.stdout == ""


@pytest.mark.parametrize(
    "fixture_name",
    [
        "gate_chained_and.md",
        "gate_chained_semicolon.md",
        "gate_chained_pipe.md",
        "gate_chained_on_accepted_command.md",
    ],
)
def test_chained_gate_line_is_refused(fixture_name: str) -> None:
    # Gates run one command per line, so a chained line smuggles a second
    # command past the sequencer and can mask the first one's exit code. All
    # three chain characters are covered: a parser that only looks for "&&"
    # passes the first arm and fails the other two. The last arm chains onto
    # the pytest command the lane runs on every card, so the refusal has to
    # come from the chain character itself - recognising the command is not
    # enough, and a parser that waves through commands it likes fails here.
    with pytest.raises(CardError) as excinfo:
        load_card(_fixture(fixture_name))

    assert "gate" in excinfo.value.field.lower()


@pytest.mark.parametrize(
    ("fixture_name", "field_name"),
    [
        ("empty_tests_no_framework.md", "framework"),
        ("empty_tests_no_sample_test.md", "sample"),
    ],
)
def test_empty_tests_section_requires_framework_and_sample(
    fixture_name: str,
    field_name: str,
) -> None:
    # An empty Tests section means the implementor writes the tests, and then
    # the framework and the sample test are the only thing telling them what
    # to write. Each arm deletes exactly one of the two keys, so a parser that
    # only checks for "framework" fails the second arm.
    with pytest.raises(CardError) as excinfo:
        load_card(_fixture(fixture_name))

    assert field_name in excinfo.value.field.lower()


def test_an_empty_tests_section_loads_when_framework_and_sample_are_given() -> None:
    # The mirror of the rule above: with both keys present an empty Tests
    # section is legal, so a parser that simply refuses every empty Tests
    # section fails here. This card also carries the other enum values -
    # opus and per-item - which a parser hardcoded to sonnet/batch rejects.
    card = load_card(_fixture("empty_tests_valid.md"))

    assert card.tests == []
    assert card.framework == "pytest"
    assert card.sample_test == "skills/plan-tasks/scripts/test_classify_tier_cli.py"
    assert card.model == "opus"
    assert card.suite == "per-item"
    assert card.changelog == "fast-track parses spec cards before assembling the lane"


def test_a_valid_card_parses_into_every_key_and_section() -> None:
    # The lane reads nothing but this dataclass, so each frontmatter key and
    # each of the seven sections has to arrive intact, split into lines where
    # the format is one-per-line and left as prose where it is not. The
    # twelve-path allowlist is the upper bound the size rule allows, so this
    # also pins that the limit is inclusive.
    card = load_card(_fixture("valid.md"))

    assert card.item == "spec-card-parser"
    assert card.model == "sonnet"
    assert card.suite == "batch"
    assert card.changelog == "none"
    assert card.framework is None
    assert card.sample_test is None
    assert card.tests == [
        _TEST_ID + "test_missing_section_names_the_field",
        _TEST_ID + "test_unknown_model_exits_two",
    ]
    assert card.files == _VALID_CARD_FILES
    assert card.gates == [_GATE_PYTEST, _GATE_CLI]
    assert card.transport_impact.strip() == "none"
    assert "single validated input" in card.goal
    # A section that ran on to the end of the file would pass a substring
    # check while handing the lane one giant blob, so each prose section is
    # pinned to its own text and none of them may carry a heading.
    assert (
        card.constraints.strip()
        == "Standard library only. No new dependencies, no network access."
    )
    assert (
        card.docs.strip()
        == "No user-facing docs beyond the fast-track skill reference."
    )
    assert "## " not in card.goal
    assert "## " not in card.constraints
    assert "## " not in card.docs
    assert "## " not in card.transport_impact


@pytest.mark.parametrize(
    ("fixture_name", "field_name"),
    [
        ("thirteen_files.md", "files"),
        ("twenty_files.md", "files"),
        ("goal_too_long.md", "goal"),
    ],
)
def test_an_oversized_card_is_refused_and_points_at_a_prd(
    fixture_name: str,
    field_name: str,
) -> None:
    # Thirteen files and a fifty-line goal are both past the lane's bounds,
    # and twenty files is nowhere near them, so the check has to be a bound
    # rather than a match on the one size each fixture happens to have. The
    # operator needs the exit route in the message, not just a refusal, so the
    # wording is part of the contract - and the named field says which limit
    # was hit, which one branch covering both cannot get right.
    with pytest.raises(CardError) as excinfo:
        load_card(_fixture(fixture_name))

    assert "card too large for the lane; write a PRD" in str(excinfo.value)
    assert excinfo.value.field.lower() == field_name


def test_a_forty_line_goal_is_still_inside_the_lane() -> None:
    # The bound is "longer than 40 lines", so exactly forty loads. Without
    # this, an off-by-one that refuses at forty passes the oversize test.
    card = load_card(_fixture("goal_at_limit.md"))

    assert "Goal line 01 of 40" in card.goal
    assert "Goal line 40 of 40" in card.goal


def test_the_cli_prints_the_parsed_card_as_json_and_exits_zero() -> None:
    # The lane shells out to this and parses stdout, so the JSON is the whole
    # contract at the process boundary: every field of the parsed card, under
    # its own name, and exit 0.
    card_path = _fixture("valid.md")

    result = _run_cli(card_path)

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    # Spelled out against the fixture rather than against another call to the
    # parser: comparing the CLI to load_card alone would pass even if both
    # agreed on the wrong content.
    assert payload["item"] == "spec-card-parser"
    assert payload["model"] == "sonnet"
    assert payload["suite"] == "batch"
    assert payload["changelog"] == "none"
    assert payload["framework"] is None
    assert payload["sample_test"] is None
    assert payload["tests"] == [
        _TEST_ID + "test_missing_section_names_the_field",
        _TEST_ID + "test_unknown_model_exits_two",
    ]
    assert payload["files"] == _VALID_CARD_FILES
    assert payload["gates"] == [_GATE_PYTEST, _GATE_CLI]
    assert payload["transport_impact"].strip() == "none"
    assert (
        payload["constraints"].strip()
        == "Standard library only. No new dependencies, no network access."
    )
    assert (
        payload["docs"].strip()
        == "No user-facing docs beyond the fast-track skill reference."
    )
    assert payload == dataclasses.asdict(load_card(card_path))


def test_the_cli_exits_two_when_the_card_path_does_not_exist(tmp_path: Path) -> None:
    # The card path is an operator-typed argument, so a typo is the most common
    # way this CLI is used wrong. It has to land on the same refusal as a bad
    # card - exit 2, a message on stderr, nothing on stdout - rather than a
    # traceback the lane would have to parse.
    result = _run_cli(tmp_path / "no_such_card.md")

    assert result.returncode == 2
    assert result.stderr.strip() != ""
    assert result.stdout == ""
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize("bad_item", ["My Feature!", ""])
def test_a_non_slug_item_is_refused(tmp_path: Path, bad_item: str) -> None:
    # The item is a slug because the lane builds branch and file names from it,
    # so punctuation and a blank value are both refused by name. The two arms
    # share no shape, so only a [a-z0-9-]+ match passes both. The card is built
    # here at runtime under a name of its own: the fixtures are the committed
    # oracle, and a parser keying off fixture filenames has to fail this.
    lines = _fixture("valid.md").read_text(encoding="utf-8").splitlines()
    card_path = tmp_path / "runtime_card.md"
    card_path.write_text(
        "\n".join(
            f"item: {bad_item}" if line.startswith("item:") else line for line in lines
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(CardError) as excinfo:
        load_card(card_path)

    assert excinfo.value.field.lower() == "item"
