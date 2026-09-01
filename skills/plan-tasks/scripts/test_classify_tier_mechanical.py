"""Tests for the mechanical (haiku) rule of classify_tier.py and its bounds.

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

# The closed list of phrases that may buy a task the cheap tier. A tenth phrase
# would be a routing decision nobody made; a missing one silently overprices
# every task that says it.
_MECHANICAL_PHRASES = (
    "add log",
    "rename",
    "add test for",
    "port",
    "mirror",
    "inline",
    "extract constant",
    "update import",
    "bump version",
)


@pytest.mark.parametrize("phrase", _MECHANICAL_PHRASES)
def test_every_mechanical_phrase_routes_to_haiku(phrase: str) -> None:
    # Parametrized over the whole list because a classifier that recognises
    # five of the nine still passes any single-phrase test.
    assert _classify(["src/app.py"], f"{phrase} in the parser module", 10) == {
        "model": "haiku",
        "tier_reason": "mechanical",
    }


@pytest.mark.parametrize("phrase", _MECHANICAL_PHRASES)
@pytest.mark.parametrize(
    "carrier",
    [
        "before the release we {phrase}",
        "cleanup task: {phrase} across the two helpers, nothing else",
    ],
)
def test_a_mechanical_phrase_is_matched_anywhere_in_the_text(
    carrier: str,
    phrase: str,
) -> None:
    # The gate is a substring search over the whole lowercased text, not a
    # match against the sentence one earlier test happened to use. Here each
    # phrase ends the sentence once and sits mid-sentence once, so recognising
    # a fixed carrier string buys nothing.
    assert _classify(["src/app.py"], carrier.format(phrase=phrase), 10) == {
        "model": "haiku",
        "tier_reason": "mechanical",
    }


@pytest.mark.parametrize(
    "text",
    [
        "Rename Foo To Bar",
        "BUMP VERSION TO 2.0",
        "Add Log lines around the retry",
        "InLiNe the tiny helper",
    ],
)
def test_a_mechanical_phrase_is_matched_case_insensitively(text: str) -> None:
    # Task titles arrive capitalised, shouted, and everything between; the
    # match runs on lowercased text, so four phrases in four casings all land.
    assert _classify(["src/app.py"], text, 10) == {
        "model": "haiku",
        "tier_reason": "mechanical",
    }


@pytest.mark.parametrize(
    "text",
    [
        "make the parser handle nested quotes",
        # Near misses: each carries one bare word out of a two-word phrase
        # without the phrase itself. A gate loosened to "version", "log",
        # "constant", or "test" alone prices all four at haiku, and these are
        # exactly the tasks (a decision, a design, a refactor, a test suite)
        # that the cheap tier must not get.
        "the API version is stale, decide what to do",
        "improve the logging strategy for the scheduler",
        "extract the constant folding pass",
        "add tests for the new parser",
    ],
)
def test_text_without_a_mechanical_phrase_is_not_haiku(text: str) -> None:
    # Small and cheap-sounding is not enough: the phrase list is the whole gate.
    assert _classify(["src/app.py"], text, 10) == {
        "model": "sonnet",
        "tier_reason": "default",
    }


@pytest.mark.parametrize(
    ("files", "lines_changed", "expected"),
    [
        (["a.py", "b.py"], 50, {"model": "haiku", "tier_reason": "mechanical"}),
        (["a.py", "b.py", "c.py"], 50, {"model": "sonnet", "tier_reason": "default"}),
        (["a.py", "b.py"], 51, {"model": "sonnet", "tier_reason": "default"}),
    ],
)
def test_the_mechanical_bounds_are_inclusive_at_two_files_and_fifty_lines(
    files: list[str],
    lines_changed: int,
    expected: dict,
) -> None:
    # Both bounds are "at or below". One off-by-one here either prices a real
    # refactor at haiku or denies the cheap tier to the edits it exists for.
    assert _classify(files, "rename foo to bar", lines_changed) == expected


@pytest.mark.parametrize("lines_changed", [0, 49, 50, 51, 200])
@pytest.mark.parametrize("file_count", [1, 2, 3, 4])
def test_the_cheap_tier_tracks_both_bounds_across_the_whole_range(
    file_count: int,
    lines_changed: int,
) -> None:
    # A sweep, not three named rows: every cell is derived from the rule
    # itself (at most two files AND at most fifty lines), so the two inputs
    # have to be counted and compared rather than recognised.
    files = [f"src/mod_{i}.py" for i in range(file_count)]
    cheap = file_count <= 2 and lines_changed <= 50
    expected = (
        {"model": "haiku", "tier_reason": "mechanical"}
        if cheap
        else {"model": "sonnet", "tier_reason": "default"}
    )

    assert _classify(files, "rename foo to bar", lines_changed) == expected


@pytest.mark.parametrize(
    ("files", "text", "lines_changed", "expected"),
    [
        (
            ["lib/util.rb"],
            "mirror the retry helper into the worker",
            8,
            {"model": "haiku", "tier_reason": "mechanical"},
        ),
        (
            ["docs/guide.md", "docs/index.md"],
            "update import paths in the guide",
            40,
            {"model": "haiku", "tier_reason": "mechanical"},
        ),
        (
            ["api/handler.go", "api/router.go", "api/middleware.go"],
            "extract constant for the timeout",
            12,
            {"model": "sonnet", "tier_reason": "default"},
        ),
        (
            ["web/render.ts"],
            "rewrite the layout engine",
            22,
            {"model": "sonnet", "tier_reason": "default"},
        ),
    ],
)
def test_fresh_task_shapes_classify_from_the_stated_rules(
    files: list[str],
    text: str,
    lines_changed: int,
    expected: dict,
) -> None:
    # Inputs that appear nowhere else in this file, in languages the other
    # fixtures never use. They are ordinary cases, not edges: the point is
    # that the rules answer them, so a lookup of the fixtures above cannot.
    assert _classify(files, text, lines_changed) == expected


def test_a_multi_file_design_task_is_the_sonnet_default() -> None:
    files = ["cache/store.py", "cache/keys.py", "cli/main.py"]

    assert _classify(files, "design and migrate the cache layer", 120) == {
        "model": "sonnet",
        "tier_reason": "default",
    }


def test_a_nine_file_slice_is_never_mechanical() -> None:
    # Mechanical text, tiny diff, nine files. Breadth alone disqualifies it.
    files = [f"src/mod_{i}.py" for i in range(9)]

    assert _classify(files, "rename foo to bar", 10) == {
        "model": "sonnet",
        "tier_reason": "default",
    }


def test_an_empty_slice_is_the_sonnet_default() -> None:
    # No files means no test_port and no packaging: an empty list must not be
    # read as "every path qualifies".
    assert _classify([], "", 0) == {"model": "sonnet", "tier_reason": "default"}
