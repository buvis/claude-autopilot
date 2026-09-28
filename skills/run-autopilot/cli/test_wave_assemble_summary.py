#!/usr/bin/env python3
"""Tests for cli/wave_assemble.py's `summary` - a wave's markdown report
rendered from already-computed, already-loaded in-memory data (a wave dict,
this wave's migrated loop-metrics rows, and this wave's assembly_conflict
records). Pure - no disk, no git - so every wave/rows/records value here is
an in-memory literal.

Split out of the sibling cli/test_wave_assemble.py (which keeps `keep_both`,
the `assemble` merge pass, and the docs proofs) to keep both files under the
repo's 800-line limit; see that module's docstring for the wider context.
"""

from __future__ import annotations

import pytest

from cli import wave_assemble


def _lane(name: str, prds: list[str], **extra: object) -> dict:
    base = {"name": name, "prds": list(prds), "status": "assembled", "files": []}
    base.update(extra)
    return base


def _wave(
    *,
    wave_id: str = "202609261200",
    lanes: list[dict] | None = None,
    prds: list[dict] | None = None,
) -> dict:
    return {
        "id": wave_id,
        "status": "assembled",
        "lanes": list(lanes) if lanes is not None else [],
        "assembly": {},
        "prds": list(prds) if prds is not None else [],
    }


# ── summary: per-PRD lines ───────────────────────────────────────────────


def test_summary_names_every_prd_with_its_lane_and_outcome() -> None:
    wave = _wave(
        lanes=[
            _lane("l1", ["00215-foo-v1.md"]),
            _lane("l2", ["00216-bar-v1.md", "00217-baz-v1.md", "00218-qux-v1.md"]),
        ],
        prds=[
            {"prd": "00215-foo-v1.md", "lane": "l1", "label": "done"},
            {"prd": "00216-bar-v1.md", "lane": "l2", "label": "parked"},
            {"prd": "00217-baz-v1.md", "lane": "l2", "label": "unassembled"},
            {"prd": "00218-qux-v1.md", "lane": "l2", "label": "backlog"},
        ],
    )
    text = wave_assemble.summary(wave, [], [])
    assert "- 00215-foo-v1.md: Wave 202609261200, lane l1, done" in text
    assert "- 00216-bar-v1.md: Wave 202609261200, lane l2, parked" in text
    assert "- 00217-baz-v1.md: Wave 202609261200, lane l2, unassembled" in text
    assert "- 00218-qux-v1.md: Wave 202609261200, lane l2, backlog" in text


def test_summary_tolerates_a_wave_with_no_prds_key_at_all() -> None:
    # Not "prds": [] - the key is entirely absent, as a wave dict assembled
    # from a partial load or an older wave.json might arrive.
    lanes = [_lane("l1", ["00215-foo-v1.md"])]
    without_key = _wave(lanes=lanes)
    del without_key["prds"]
    with_empty_list = _wave(lanes=lanes, prds=[])
    text = wave_assemble.summary(without_key, [], [])
    # Missing key and an explicit empty list must render identically: no
    # per-PRD lines, just the section heading with nothing under it.
    assert text == wave_assemble.summary(with_empty_list, [], [])
    assert "## PRDs" in text


# ── summary: conflict records ────────────────────────────────────────────


def test_summary_lists_conflict_records_verbatim() -> None:
    wave = _wave(lanes=[_lane("l1", ["00215-foo-v1.md"])])
    records = [
        {
            "prd": "00220-example-v1.md",
            "lane": "l2",
            "reason": "conflict marker in cli/foo.py",
        },
        {"prd": "00221-other-v1.md", "lane": "l3", "reason": "binary file diverged"},
    ]
    text = wave_assemble.summary(wave, [], records)
    assert "00220-example-v1.md" in text
    assert "conflict marker in cli/foo.py" in text
    assert "00221-other-v1.md" in text
    assert "binary file diverged" in text


# ── summary: integrator notes ────────────────────────────────────────────


def test_summary_lists_integrator_trailers() -> None:
    wave = _wave(
        lanes=[
            _lane(
                "l1",
                ["00215-foo-v1.md"],
                integrator_notes=[
                    {"sha": "abc1234", "text": "Resolved import order in foo.py"},
                    {"sha": "def5678", "text": "Kept both docstring edits"},
                ],
            ),
            _lane(
                "l2",
                ["00216-bar-v1.md"],
                integrator_notes=[
                    {"sha": "aaa9999", "text": "Dropped a duplicate test case"},
                ],
            ),
        ],
    )
    text = wave_assemble.summary(wave, [], [])
    heading_index = text.index("## Integrator notes")
    for lane, sha, note_text in (
        ("l1", "abc1234", "Resolved import order in foo.py"),
        ("l1", "def5678", "Kept both docstring edits"),
        ("l2", "aaa9999", "Dropped a duplicate test case"),
    ):
        line = f"- {lane} {sha}: {note_text}"
        assert line in text, text
        assert text.index(line) > heading_index
    # Would fail if the lane names were swapped between notes.
    assert "- l2 abc1234: Resolved import order in foo.py" not in text
    assert "- l1 aaa9999: Dropped a duplicate test case" not in text


def test_summary_shows_none_when_no_integrator_notes() -> None:
    wave = _wave(
        lanes=[
            _lane("l1", ["00215-foo-v1.md"]),  # integrator_notes key omitted
            _lane("l2", ["00216-bar-v1.md"], integrator_notes=None),
        ],
    )
    text = wave_assemble.summary(wave, [], [])
    heading_index = text.index("## Integrator notes")
    assert "(none)" in text[heading_index:]


# ── summary: the report header ───────────────────────────────────────────


_HEADERS = (
    {
        "id": "202609261200",
        "base_branch": "wip/waves",
        "base_sha": "abcdef0",
        "branch": "wave/202609261200/assembly",
        "head_sha": "fedcba9",
    },
    {
        "id": "202610021545",
        "base_branch": "release/2.1",
        "base_sha": "1234567",
        "branch": "wave/202610021545/assembly",
        "head_sha": "7654321",
    },
)


@pytest.mark.parametrize(
    ("spec", "other"),
    [(_HEADERS[0], _HEADERS[1]), (_HEADERS[1], _HEADERS[0])],
    ids=["first-wave", "second-wave"],
)
def test_summary_opens_with_the_base_and_the_assembled_head(
    spec: dict,
    other: dict,
) -> None:
    wave = {
        **_wave(wave_id=spec["id"], lanes=[_lane("l1", ["00215-foo-v1.md"])]),
        "base_branch": spec["base_branch"],
        "base_sha": spec["base_sha"],
        "assembly": {
            "worktree": f"/tmp/proj-wave-{spec['id']}",
            "branch": spec["branch"],
            "head_sha": spec["head_sha"],
            "merged": ["l1"],
            "kept": [],
        },
    }
    text = wave_assemble.summary(wave, [], [])
    header = text[: text.index("## PRDs")]
    # Each value pinned to its own labelled line, not just present somewhere in
    # the header: a summary() that swapped base_sha and head_sha between the
    # "base" and "assembled head" lines would fail these two assertions even
    # though both values still appear in the header.
    assert f"# Wave {spec['id']} summary" in header, header
    assert f"- base: {spec['base_branch']} @ {spec['base_sha']}" in header, header
    assert f"- assembled head: {spec['branch']} @ {spec['head_sha']}" in header, header
    # None of the other wave's values either: a header rendered from constants
    # cannot serve both waves.
    for key in ("id", "base_branch", "base_sha", "branch", "head_sha"):
        assert other[key] not in header, header


# ── summary: the lane table ──────────────────────────────────────────────


def _cells(line: str) -> list[str]:
    """A table line's cells, outer pipes and padding dropped."""
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _cell(text: str, line: str, column: str) -> str:
    """`line`'s cell under the lane table's `column` header."""
    for each in text.splitlines():
        headers = [cell.lower() for cell in _cells(each)]
        if {"paths", "files"} <= set(headers):
            return _cells(line)[headers.index(column)]
    raise AssertionError(f"no lane table header naming paths and files:\n{text}")


def test_summary_tables_each_lane_with_its_branch_status_and_batch() -> None:
    # Neither branch name carries its own lane's name, so a missing lane-name
    # column cannot pass on the branch column's coat-tails; each lane's `prds`,
    # `paths` and `files` are disjoint, so neither column can be rendered from
    # another lane's or another column's. l1 carries two of each, pinning the
    # ", ".join(...) separator and element order; a join dropped for the first
    # element alone, or one that reordered the list, would fail l1's asserts.
    wave = _wave(
        lanes=[
            _lane(
                "l1",
                ["00215-foo-v1.md", "00219-quux-v1.md"],
                branch="wave/202609261200/alpha",
                paths=["cli/foo.py", "cli/qux.py"],
                files=["cli/renamed.py", "cli/renamed2.py"],
                batch_id="202609260900",
            ),
            _lane(
                "l2",
                ["00216-bar-v1.md"],
                status="conflict",
                branch="wave/202609261200/beta",
                paths=["cli/bar.py"],
                files=["cli/moved.py"],
                batch_id="202609261000",
            ),
        ],
    )
    text = wave_assemble.summary(wave, [], [])

    def row(branch: str) -> str:
        """The single table line that is this lane's row."""
        matching = [line for line in text.splitlines() if branch in line]
        assert len(matching) == 1, matching
        return matching[0]

    first = row("wave/202609261200/alpha")
    second = row("wave/202609261200/beta")
    for token in ("l1", "assembled", "202609260900"):
        assert token in first, first
    for token in ("l2", "conflict", "202609261000"):
        assert token in second, second
    # Exact cell contents: the join separator and element order are pinned,
    # not just each element's presence somewhere in the row.
    assert _cell(text, first, "prds") == "00215-foo-v1.md, 00219-quux-v1.md", first
    assert _cell(text, first, "paths") == "cli/foo.py, cli/qux.py", first
    assert _cell(text, first, "files") == "cli/renamed.py, cli/renamed2.py", first
    assert _cell(text, second, "prds") == "00216-bar-v1.md", second
    assert _cell(text, second, "paths") == "cli/bar.py", second
    assert _cell(text, second, "files") == "cli/moved.py", second


# ── summary: the totals ──────────────────────────────────────────────────


# Four sessions, 8100 wall seconds (2.25 hours), one captured cost (1.25): a row
# may carry no cost at all, and a row may carry no wall time either.
_FOUR_SESSIONS = [
    {"prd": "00215-foo-v1.md", "wall_secs": 5400, "cost_usd": 1.25},
    {"prd": "00215-foo-v1.md", "wall_secs": 2700, "cost_usd": None},
    {"prd": "00215-foo-v1.md", "wall_secs": 0},
    {"prd": "00215-foo-v1.md"},
]
# Three sessions, 4500 wall seconds (1.25 hours), two captured costs (7.75).
_THREE_SESSIONS = [
    {"prd": "00215-foo-v1.md", "wall_secs": 3600, "cost_usd": 7.0},
    {"prd": "00215-foo-v1.md", "wall_secs": 900, "cost_usd": 0.75},
    {"prd": "00215-foo-v1.md", "wall_secs": 0, "cost_usd": None},
]
# Five sessions, 3500 wall seconds: not a multiple of 900, so the hours total
# (0.9722... -> "0.97") pins actual rounding, not a round quarter-hour that a
# lookup-table formula could special-case. Three captured costs (6.66).
_FIVE_SESSIONS = [
    {"prd": "00215-foo-v1.md", "wall_secs": 1000, "cost_usd": 1.11},
    {"prd": "00215-foo-v1.md", "wall_secs": 2000, "cost_usd": 2.22},
    {"prd": "00215-foo-v1.md", "wall_secs": 500, "cost_usd": 3.33},
    {"prd": "00215-foo-v1.md", "wall_secs": 0, "cost_usd": None},
    {"prd": "00215-foo-v1.md"},
]


@pytest.mark.parametrize(
    ("rows", "totals", "absent"),
    [
        (
            _FOUR_SESSIONS,
            "totals: 4 sessions, 2.25 wall hours, $1.25 captured cost",
            ("3 sessions", "1.25 wall", "$7.75"),
        ),
        (
            _THREE_SESSIONS,
            "totals: 3 sessions, 1.25 wall hours, $7.75 captured cost",
            ("4 sessions", "2.25 wall", "$1.25"),
        ),
        (
            _FIVE_SESSIONS,
            "totals: 5 sessions, 0.97 wall hours, $6.66 captured cost",
            ("4 sessions", "2.25 wall", "$1.25"),
        ),
    ],
    ids=["four-sessions", "three-sessions", "five-sessions"],
)
def test_summary_totals_the_sessions_wall_hours_and_captured_cost(
    rows: list[dict],
    totals: str,
    absent: tuple[str, ...],
) -> None:
    wave = _wave(lanes=[_lane("l1", ["00215-foo-v1.md"])])
    text = wave_assemble.summary(wave, rows, [])
    # The two row sets share no total, so one constant cannot render both, and
    # neither set's numbers may leak into the other's report.
    assert totals in text, text
    for token in absent:
        assert token not in text, text


# ── _totals: edge cases ──────────────────────────────────────────────────


def test_totals_treats_an_explicit_null_wall_secs_as_zero() -> None:
    # An explicit `None` (as opposed to the key being absent, or 0) must
    # contribute nothing to the wall-hours total, same as the other two.
    rows = [
        {"wall_secs": 3600},
        {"wall_secs": None},
        {"wall_secs": 0},
        {},
    ]
    result = wave_assemble._totals(rows)
    assert result == "totals: 4 sessions, 1.00 wall hours, $0.00 captured cost"
