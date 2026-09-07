"""Tests for fast_track_plan.py, the fast-track lane planner.

Four decisions live here and nothing else: which lanes an item dispatches,
which raised findings earn an adversarial verification, whether the item's
commits land on the working branch, and how many dispatches an item actually
cost. Every rule is about not spending a dispatch twice - the roster is fixed
before any finding exists, the workflow's own findings are not re-verified, and
a lane with no backend is dropped rather than attempted.

The two ledger fixtures are recordings of whole lane runs: one item that came
back clean and one that had a single HIGH confirmed, written in the row shape
record_dispatch.py appends. Each carries end rows, a handoff row and rows for a
second item, so the counting rules are exercised rather than assumed. The
smaller ledgers built with tmp_path are the other half of that: they hold their
rows and their expected counts in one place, so the count has to come out of
the file rather than out of the item's name.

fast_track_plan.py is not an installed package, so it is loaded by path, the
same idiom test_card.py uses.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).with_name("fast_track_plan.py")
_FIXTURES_DIR = Path(__file__).with_name("fixtures")

_SPEC = importlib.util.spec_from_file_location("fast_track_plan", _MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_plan = importlib.util.module_from_spec(_SPEC)
# Registered before exec_module on purpose: a module built with
# `from __future__ import annotations` and @dataclass resolves its own
# annotations by looking itself up in sys.modules, and an unregistered module
# makes that lookup fail at import time. Either style has to stay open to the
# implementor.
sys.modules[_SPEC.name] = _plan
_SPEC.loader.exec_module(_plan)

Finding = _plan.Finding
plan_lanes = _plan.plan_lanes
verify_targets = _plan.verify_targets
exit_action = _plan.exit_action
count_item_dispatches = _plan.count_item_dispatches

# The roster every happy-path item dispatches, in order.
_BASE_ROSTER = [
    "fast-track:ivan",
    "fast-track:fanout",
    "fast-track:blake",
    "fast-track:eve",
    "fast-track:bob",
    "fast-track:carl",
]

_CLEAN_LEDGER = _FIXTURES_DIR / "ledger_clean_item.jsonl"
_HIGH_LEDGER = _FIXTURES_DIR / "ledger_one_confirmed_high.jsonl"

_MEDIUM = Finding(
    severity="MEDIUM",
    title="Roster order is only implied by the docstring",
    file="skills/fast-track/scripts/fast_track_plan.py",
    lane="fast-track:bob",
)
_LOW = Finding(
    severity="LOW",
    title="Fixture ids read as random hex with no scenario hint",
    file="skills/fast-track/scripts/fixtures/ledger_clean_item.jsonl",
    lane="fast-track:eve",
)


def _ledger(path: Path) -> Path:
    assert path.is_file(), f"missing fixture ledger: {path}"
    return path


def _write_ledger(path: Path, rows: list[dict[str, object]]) -> Path:
    # One JSON object per line, the shape record_dispatch.py appends.
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )
    return path


def test_clean_item_dispatches_one_ivan_and_the_roster_and_no_rework() -> None:
    # A clean item is the lane's cheapest shape and its cost is the whole
    # point of the ledger: one implementor, one pass of the roster, and
    # nothing after it. The zeros are the assertion that matters - the
    # fixture does hold victor and delta rows, but they belong to a second
    # item, so a counter that ignored `task` would report them here.
    counts = count_item_dispatches(_ledger(_CLEAN_LEDGER), "clean-item")

    for kind in _BASE_ROSTER:
        assert counts[kind] == 1, kind
    assert counts["fast-track:victor"] == 0
    assert counts["fast-track:delta"] == 0
    # Nothing else was counted either: the end rows and the handoff row in
    # this fixture are not dispatches, so six start rows is the whole item.
    assert sum(counts.values()) == 6


def test_one_confirmed_high_dispatches_two_ivans_one_victor_and_one_delta() -> None:
    # One HIGH that survived verification costs exactly three extra
    # dispatches: the verifier that confirmed it, the rework, and the delta
    # review of that rework. Two ivans and one delta is what "one rework"
    # means in dispatch terms - a second rework or a delta per lane would
    # show up here as a different number.
    counts = count_item_dispatches(_ledger(_HIGH_LEDGER), "confirmed-high-item")

    assert counts["fast-track:ivan"] == 2
    assert counts["fast-track:victor"] == 1
    assert counts["fast-track:delta"] == 1
    for kind in _BASE_ROSTER:
        if kind != "fast-track:ivan":
            assert counts[kind] == 1, kind
    assert sum(counts.values()) == 9


def test_a_closed_dispatch_is_counted_once_not_twice() -> None:
    # The rework's end row in this fixture repeats the kind and the task of
    # its start row, so a counter keyed on `task` alone reports three ivans
    # for an item that ran two. Only `queued_at` separates the row that opens
    # a dispatch from the row that closes it.
    counts = count_item_dispatches(_ledger(_HIGH_LEDGER), "confirmed-high-item")

    assert counts["fast-track:ivan"] == 2


def test_an_item_with_no_rows_has_no_dispatches() -> None:
    # Asking about an item that never ran is the ordinary case before the
    # first dispatch, so it answers zero rather than raising - and the ledger
    # it reads is full of other items' rows, which a counter that ignored
    # `task` would hand back.
    counts = count_item_dispatches(_ledger(_HIGH_LEDGER), "never-dispatched-item")

    assert counts["fast-track:ivan"] == 0
    assert sum(counts.values()) == 0


def test_the_counts_come_out_of_the_rows_the_ledger_actually_holds(
    tmp_path: Path,
) -> None:
    # The two fixture tests above read a recording nobody edits, so their
    # totals could be answered from the item's name alone. Here the rows and
    # the expected counts sit side by side: eve ran twice, blake's second row
    # belongs to another item, the handoff and the end row open nothing, and
    # carl never ran at all.
    rows: list[dict[str, object]] = [
        {
            "id": "0a0a0a0a",
            "kind": "fast-track:ivan",
            "task": "widget",
            "queued_at": 1757280000,
            "prompt_bytes": 4096,
        },
        {
            "id": "0a0a0a0a",
            "ended_at": 1757280600,
            "elapsed_s": 600,
            "outcome": "ok",
            "detail": None,
        },
        {
            "id": "0b0b0b0b",
            "kind": "fast-track:blake",
            "task": "widget",
            "queued_at": 1757280610,
            "prompt_bytes": 3001,
        },
        {
            "id": "0c0c0c0c",
            "kind": "fast-track:blake",
            "task": "sprocket",
            "queued_at": 1757280611,
            "prompt_bytes": 3002,
        },
        {
            "kind": "handoff",
            "site": "build",
            "edge": "leave",
            "at": 1757280620,
            "phase": "fast-track",
            "prd": "none",
        },
        {
            "id": "0d0d0d0d",
            "kind": "fast-track:eve",
            "task": "widget",
            "queued_at": 1757280630,
            "prompt_bytes": 3100,
        },
        {
            "id": "0b0b0b0b",
            "kind": "fast-track:blake",
            "task": "widget",
            "ended_at": 1757280990,
            "elapsed_s": 380,
            "outcome": "ok",
            "detail": None,
        },
        {
            "id": "0e0e0e0e",
            "kind": "fast-track:eve",
            "task": "widget",
            "queued_at": 1757281000,
            "prompt_bytes": 3101,
        },
    ]

    counts = count_item_dispatches(
        _write_ledger(tmp_path / "mixed_rows.jsonl", rows),
        "widget",
    )

    assert counts == Counter(
        {"fast-track:eve": 2, "fast-track:ivan": 1, "fast-track:blake": 1},
    )
    assert counts["fast-track:carl"] == 0


def test_dropping_queued_at_from_one_row_drops_exactly_one_dispatch(
    tmp_path: Path,
) -> None:
    # `queued_at` is the whole definition of a start row, so the same row with
    # and without that one key is the smallest edit that may change an answer -
    # and it must change it by exactly one blake, leaving every other count
    # where it was.
    toggled: dict[str, object] = {
        "id": "1b1b1b1b",
        "kind": "fast-track:blake",
        "task": "widget",
        "queued_at": 1757281100,
        "prompt_bytes": 2900,
    }
    rest: list[dict[str, object]] = [
        {
            "id": "1a1a1a1a",
            "kind": "fast-track:ivan",
            "task": "widget",
            "queued_at": 1757281000,
            "prompt_bytes": 4096,
        },
        {
            "id": "1c1c1c1c",
            "kind": "fast-track:blake",
            "task": "widget",
            "queued_at": 1757281200,
            "prompt_bytes": 2901,
        },
    ]
    unqueued = {key: value for key, value in toggled.items() if key != "queued_at"}

    with_row = count_item_dispatches(
        _write_ledger(tmp_path / "with_queued_at.jsonl", [*rest, toggled]),
        "widget",
    )
    without_row = count_item_dispatches(
        _write_ledger(tmp_path / "without_queued_at.jsonl", [*rest, unqueued]),
        "widget",
    )

    assert with_row["fast-track:blake"] == 2
    assert without_row["fast-track:blake"] == 1
    assert sum(with_row.values()) - sum(without_row.values()) == 1
    assert with_row - Counter({"fast-track:blake": 1}) == without_row


def test_a_ledger_that_was_never_written_reports_no_dispatches(
    tmp_path: Path,
) -> None:
    # Before the first dispatch of a batch there is no ledger file, and a
    # report over the ledger must not fail because the batch has not written
    # its first row yet: a missing path is an empty ledger, not an error, the
    # same reading record_dispatch.py gives it. The item asked about here is
    # the one the committed fixture records, so an implementation answering
    # out of a hardcoded table hands back that fixture's six kinds instead of
    # nothing.
    missing = tmp_path / "never_written" / "dispatch_ledger.jsonl"
    assert not missing.exists()

    assert count_item_dispatches(missing, "clean-item") == Counter()


def test_surviving_critical_leaves_master_untouched() -> None:
    # Branching is what keeps the working branch at its base commit, so a
    # CRITICAL nobody could refute must never end on "commit". Position is
    # what the three calls pin: the delta review hands back its rows in
    # whatever order it found them, so a rule that reads the head of the list,
    # or its tail, or anything short of every row, lands a CRITICAL on the
    # working branch.
    critical = Finding(
        severity="CRITICAL",
        title="Carl is dispatched with no backend CLI installed",
        file="skills/fast-track/scripts/fast_track_plan.py",
        lane="fast-track:blake",
    )

    assert exit_action([_MEDIUM, critical]) == "branch"
    assert exit_action([critical, _LOW]) == "branch"
    assert exit_action([_LOW, critical, _MEDIUM]) == "branch"


def test_exit_action_commits_only_when_no_critical_or_high_survives() -> None:
    # The mirror of the rule above, across the three shapes the delta review
    # can hand back. MEDIUM and LOW never block, so an implementation that
    # branches on any surviving finding fails the second case; the HIGH sits
    # last in the third call and in the middle in the fourth, so neither a
    # head-only nor a tail-only rule survives.
    high = Finding(
        severity="HIGH",
        title="A handoff row is counted as a dispatch",
        file="skills/fast-track/scripts/fast_track_plan.py",
        lane="fast-track:carl",
    )

    assert exit_action([]) == "commit"
    assert exit_action([_MEDIUM, _LOW]) == "commit"
    assert exit_action([_LOW, high]) == "branch"
    assert exit_action([_LOW, high, _MEDIUM]) == "branch"


def test_workflow_absent_dispatches_legacy_alice() -> None:
    # The review-fanout workflow is the consensus lane when the file is
    # there; without it the legacy single Alice subagent takes the same slot,
    # so the roster keeps its length and its order. Dropping the slot instead
    # would cost the item its consensus lens.
    lanes = plan_lanes(
        tests_present=True,
        workflow_available=False,
        carl_available=True,
    )

    assert "fast-track:alice" in lanes
    assert "fast-track:fanout" not in lanes
    assert lanes == [
        "fast-track:ivan",
        "fast-track:alice",
        "fast-track:blake",
        "fast-track:eve",
        "fast-track:bob",
        "fast-track:carl",
    ]


def test_carl_skipped_when_no_backend() -> None:
    # Carl runs on Gemini, and dispatching him without the CLI buys a failed
    # lane rather than a review. He is dropped, and nothing else moves - a
    # substitution or a reorder would show up in the equality below.
    lanes = plan_lanes(
        tests_present=True,
        workflow_available=True,
        carl_available=False,
    )

    assert "fast-track:carl" not in lanes
    assert lanes == [
        "fast-track:ivan",
        "fast-track:fanout",
        "fast-track:blake",
        "fast-track:eve",
        "fast-track:bob",
    ]


def test_the_happy_path_roster_runs_ivan_then_the_five_reviewers() -> None:
    # The oracle the two flag tests are read against: without it, a planner
    # that shuffled the reviewers or dropped one would still satisfy "alice
    # replaces fanout" and "carl is absent".
    lanes = plan_lanes(tests_present=True, workflow_available=True, carl_available=True)

    assert lanes == _BASE_ROSTER


def test_an_item_without_tests_writes_them_before_it_implements() -> None:
    # Tests are the implementor's only spec, so when the card ships none, the
    # lane writes them first. Tess goes in front of ivan, not somewhere in
    # the roster: an item implemented before its tests exist has nothing to
    # implement against.
    lanes = plan_lanes(
        tests_present=False,
        workflow_available=True,
        carl_available=True,
    )

    assert lanes[0] == "fast-track:tess"
    assert lanes[1] == "fast-track:ivan"
    assert lanes == ["fast-track:tess"] + _BASE_ROSTER


def test_the_three_lane_flags_compose() -> None:
    # Each flag is decided from a different fact - the card, the filesystem,
    # the installed CLIs - so they arrive in any combination. A planner built
    # as a chain of exclusive branches gets one of them right and loses the
    # other two.
    lanes = plan_lanes(
        tests_present=False,
        workflow_available=False,
        carl_available=False,
    )

    assert lanes == [
        "fast-track:tess",
        "fast-track:ivan",
        "fast-track:alice",
        "fast-track:blake",
        "fast-track:eve",
        "fast-track:bob",
    ]


@pytest.mark.parametrize(
    ("tests_present", "workflow_available", "carl_available", "expected"),
    [
        (
            True,
            True,
            True,
            [
                "fast-track:ivan",
                "fast-track:fanout",
                "fast-track:blake",
                "fast-track:eve",
                "fast-track:bob",
                "fast-track:carl",
            ],
        ),
        (
            True,
            True,
            False,
            [
                "fast-track:ivan",
                "fast-track:fanout",
                "fast-track:blake",
                "fast-track:eve",
                "fast-track:bob",
            ],
        ),
        (
            True,
            False,
            True,
            [
                "fast-track:ivan",
                "fast-track:alice",
                "fast-track:blake",
                "fast-track:eve",
                "fast-track:bob",
                "fast-track:carl",
            ],
        ),
        (
            True,
            False,
            False,
            [
                "fast-track:ivan",
                "fast-track:alice",
                "fast-track:blake",
                "fast-track:eve",
                "fast-track:bob",
            ],
        ),
        (
            False,
            True,
            True,
            [
                "fast-track:tess",
                "fast-track:ivan",
                "fast-track:fanout",
                "fast-track:blake",
                "fast-track:eve",
                "fast-track:bob",
                "fast-track:carl",
            ],
        ),
        (
            False,
            True,
            False,
            [
                "fast-track:tess",
                "fast-track:ivan",
                "fast-track:fanout",
                "fast-track:blake",
                "fast-track:eve",
                "fast-track:bob",
            ],
        ),
        (
            False,
            False,
            True,
            [
                "fast-track:tess",
                "fast-track:ivan",
                "fast-track:alice",
                "fast-track:blake",
                "fast-track:eve",
                "fast-track:bob",
                "fast-track:carl",
            ],
        ),
        (
            False,
            False,
            False,
            [
                "fast-track:tess",
                "fast-track:ivan",
                "fast-track:alice",
                "fast-track:blake",
                "fast-track:eve",
                "fast-track:bob",
            ],
        ),
    ],
    ids=[
        "tests-workflow-carl",
        "tests-workflow-nocarl",
        "tests-noworkflow-carl",
        "tests-noworkflow-nocarl",
        "notests-workflow-carl",
        "notests-workflow-nocarl",
        "notests-noworkflow-carl",
        "notests-noworkflow-nocarl",
    ],
)
def test_each_flag_combination_plans_its_whole_roster(
    tests_present: bool,
    workflow_available: bool,
    carl_available: bool,
    expected: list[str],
) -> None:
    # Three independent facts decide these flags, so the lane meets all eight
    # combinations in production and each expected roster is written out here
    # by hand rather than derived - a table built from the combinations the
    # other tests happen to ask would answer them and raise on the rest.
    lanes = plan_lanes(
        tests_present=tests_present,
        workflow_available=workflow_available,
        carl_available=carl_available,
    )

    assert lanes == expected


def test_workflow_findings_are_not_re_verified() -> None:
    # The review-fanout workflow runs its own adversarial verifier over its
    # own findings before it reports, so verifying them again here buys
    # nothing and costs a dispatch each. The fanout HIGH is in the table too:
    # severity is not what rescues a workflow row, its lane is what excludes
    # it. Two lanes reporting the same problem is the ordinary case in a
    # consensus roster, so the excluded CRITICAL carries the same title and
    # the same file as the returned one: the lane is the only field that may
    # decide.
    fanout_critical = Finding(
        severity="CRITICAL",
        title="A surviving CRITICAL still commits to the working branch",
        file="skills/fast-track/scripts/fast_track_plan.py",
        lane="fast-track:fanout",
    )
    fanout_high = Finding(
        severity="HIGH",
        title="Ledger path is resolved against the cwd",
        file="skills/fast-track/scripts/fast_track_plan.py",
        lane="fast-track:fanout",
    )
    blake_critical = Finding(
        severity="CRITICAL",
        title="A surviving CRITICAL still commits to the working branch",
        file="skills/fast-track/scripts/fast_track_plan.py",
        lane="fast-track:blake",
    )

    targets = verify_targets([fanout_critical, fanout_high, blake_critical])

    assert targets == [blake_critical]
    assert fanout_critical not in targets
    assert fanout_high not in targets


def test_only_critical_and_high_are_worth_a_verification() -> None:
    # MEDIUM and LOW neither rework nor block the exit, so verifying one
    # spends a dispatch on a finding whose answer changes nothing. The
    # returned rows keep the table's order, and the HIGH is listed before the
    # CRITICAL so a verifier that sorted by severity fails here. The dropped
    # MEDIUM repeats the HIGH's title, file and lane, because a reviewer who
    # raises the same problem at two severities is ordinary and severity is
    # the only field that may separate them.
    carl_high = Finding(
        severity="HIGH",
        title="Tess is appended instead of prepended",
        file="skills/fast-track/scripts/fast_track_plan.py",
        lane="fast-track:carl",
    )
    carl_medium = Finding(
        severity="MEDIUM",
        title="Tess is appended instead of prepended",
        file="skills/fast-track/scripts/fast_track_plan.py",
        lane="fast-track:carl",
    )
    alice_critical = Finding(
        severity="CRITICAL",
        title="End rows are counted as dispatches",
        file="skills/fast-track/scripts/fast_track_plan.py",
        lane="fast-track:alice",
    )

    targets = verify_targets([_MEDIUM, carl_medium, carl_high, _LOW, alice_critical])

    assert targets == [carl_high, alice_critical]
    assert verify_targets([]) == []
    assert verify_targets([_MEDIUM, _LOW]) == []


@pytest.mark.parametrize(
    "lane",
    ["fast-track:blake", "fast-track:eve", "fast-track:bob", "fast-track:carl"],
)
def test_every_non_workflow_lane_earns_a_verification(lane: str) -> None:
    # Fanout is the only excluded lane, so each remaining reviewer is checked
    # by name: an exclusion list that named a second lane, or an allowlist
    # that forgot one, passes the mixed-table test above and fails an arm
    # here.
    raised = Finding(
        severity="HIGH",
        title="Carl runs without a backend check",
        file="skills/fast-track/scripts/fast_track_plan.py",
        lane=lane,
    )

    assert verify_targets([raised]) == [raised]
