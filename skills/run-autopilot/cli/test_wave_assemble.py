#!/usr/bin/env python3
"""Tests for cli/wave_assemble.py - keep_both and summary.

`keep_both` strips git's three-way conflict marker lines while keeping both
sides of every hunk; `summary` renders a wave's markdown report from
already-computed, already-loaded in-memory data (a wave dict, this wave's
migrated loop-metrics rows, and this wave's assembly_conflict records).
Both are pure - no disk, no git - so every wave/rows/records value here is
an in-memory literal.
"""

from __future__ import annotations

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


# ── keep_both ─────────────────────────────────────────────────────────────


def test_keep_both_keeps_both_sides_in_file_order() -> None:
    ours_marker = "<" * 7 + " HEAD"
    sep_marker = "=" * 7
    theirs_marker = ">" * 7 + " feature-branch"
    text = (
        "before\n"
        f"{ours_marker}\n"
        "our line one\n"
        "our line two\n"
        f"{sep_marker}\n"
        "their line one\n"
        "their line two\n"
        f"{theirs_marker}\n"
        "after\n"
    )
    expected = (
        "before\n"
        "our line one\n"
        "our line two\n"
        "their line one\n"
        "their line two\n"
        "after\n"
    )
    assert wave_assemble.keep_both(text) == expected


def test_keep_both_leaves_a_clean_file_alone() -> None:
    text = "one fish\ntwo fish\nred fish\nblue fish\n"
    assert wave_assemble.keep_both(text) == text


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
    for sha, note_text in (
        ("abc1234", "Resolved import order in foo.py"),
        ("def5678", "Kept both docstring edits"),
        ("aaa9999", "Dropped a duplicate test case"),
    ):
        assert sha in text
        assert note_text in text
        assert text.index(note_text) > heading_index


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
