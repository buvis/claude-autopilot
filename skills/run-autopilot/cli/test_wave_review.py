#!/usr/bin/env python3
"""Tests for cli/wave_review.py - stub_text and review_paths.

Both functions are pure: they render the assembly stub PRD body and compute
its diff-scope path list from an already-assembled wave dict (`wave.json`
after `wave_assemble.assemble` has populated `wave["assembly"]`), never
touching git, disk, or a PRD file.
"""

from __future__ import annotations

import pytest

from cli import frontmatter, wave_review


def _lane(name: str, prds: list[str], files: list[str] | None = None) -> dict:
    """A minimal lane entry: `files` omitted entirely when not given, so a
    lane that never recorded it is exercised the way assemble() leaves one."""
    lane = {"name": name, "prds": prds}
    if files is not None:
        lane["files"] = files
    return lane


def _wave(**overrides: object) -> dict:
    """A wave whose assembly merged both lanes l1 and l2, in order."""
    base = {
        "id": "202609281200",
        "base_sha": "1111111",
        "assembly": {"head_sha": "2222222", "merged": ["l1", "l2"]},
        "lanes": [
            _lane("l1", ["00001-a.md"], files=["cli/records.py", "cli/x.py"]),
            _lane("l2", ["00002-b.md", "00003-c.md"], files=["cli/records.py"]),
        ],
    }
    base.update(overrides)
    return base


# ── stub_text ────────────────────────────────────────────────────────────


def test_stub_prd_names_every_merged_lane_and_the_range() -> None:
    text = wave_review.stub_text(_wave())
    lines = text.splitlines()
    assert "- l1 (00001-a.md)" in lines
    assert "- l2 (00002-b.md, 00003-c.md)" in lines
    assert "Diff range: 1111111..2222222" in lines


def test_stub_prd_carries_the_headings_plan_tasks_parses() -> None:
    text = wave_review.stub_text(_wave())
    assert "#### Feature: Lane merges" in text
    assert "### Phase 0: Assembly" in text
    lines = text.splitlines()
    assert "- [x] Merge lane l1 (00001-a.md) - Acceptance: release-checks green" in lines
    assert (
        "- [x] Merge lane l2 (00002-b.md, 00003-c.md) - Acceptance: release-checks green"
        in lines
    )


def test_stub_frontmatter_is_the_five_pairs() -> None:
    text = wave_review.stub_text(_wave())
    assert frontmatter.declared(text) == {
        "catchup": "skip",
        "design": "skip",
        "rework_cap": "2",
        "default_model": "sonnet",
        "model_tier_rationale": (
            "fixes to conflict resolutions and lane interactions found by the"
            " assembly review"
        ),
    }
    _, warnings = frontmatter.parse(text)
    assert warnings == []


def test_stub_prd_lists_the_diff_scope() -> None:
    wave_dict = _wave()
    text = wave_review.stub_text(wave_dict)
    assert "Diff scope:" in text
    lines = text.splitlines()
    for path in wave_review.review_paths(wave_dict):
        # The exact bullet styling is not pinned, only that each path gets
        # its own line rather than being folded into one comma list.
        assert path in lines or f"- {path}" in lines, (path, text)


def test_stub_text_raises_without_an_assembly() -> None:
    wave_dict = _wave()
    del wave_dict["assembly"]
    with pytest.raises(ValueError):
        wave_review.stub_text(wave_dict)


# ── review_paths ─────────────────────────────────────────────────────────


def test_review_paths_are_the_multi_lane_files_plus_append_only() -> None:
    wave_dict = _wave(
        assembly={"head_sha": "2222222", "merged": ["l1"]},
        lanes=[
            _lane("l1", ["00001-a.md"], files=["cli/records.py", "cli/x.py"]),
            # l2 could not merge (conflict/checks_failed) but still counts.
            _lane("l2", ["00002-b.md"], files=["cli/records.py"]),
            # l3 never recorded a files list at all.
            _lane("l3", ["00003-c.md"]),
        ],
    )
    assert wave_review.review_paths(wave_dict) == [
        "CHANGELOG.md",
        "cli/records.py",
        "dev/bin/release-checks",
    ]
