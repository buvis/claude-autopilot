#!/usr/bin/env python3
"""Tests for the two REPO FILES the wave feature has to keep honest (PRD 00214):
`dev/bin/release-checks`, whose `[checks] waves` block must run every wave test
file, and `references/waves.md`, whose `wave abort` section must describe what
`abort` really prints for a worktree it keeps.

A sibling of `test_wave.py`'s `test_docs_name_the_wave_files` rather than two more
tests inside it: that file sits at this repo's 800-line style limit, and these
pins are about files outside `cli/` anyway. Both read this checkout's own text -
no repo under `tmp_path`, no wave verb, no loop.

Both pins are ANCHORED to a block inside their file, because the strings they look
for are not unique to it. The gate script is one `[checks] <name>` block after
another and every wave test basename starts with `test_wave`, so a search over the
whole script passes while the waves block names nothing; `note` likewise appears
in the runbook's plan section and in a heading while the abort section says no
such thing.
"""

from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_RELEASE_CHECKS = _ROOT / "dev" / "bin" / "release-checks"
_WAVES = Path(__file__).resolve().parent.parent / "references" / "waves.md"

_MARKER = 'echo "[checks] '

# The seven wave test files that exist today plus this one, which is a wave test
# file and belongs in the same gate.
_WAVE_TEST_FILES = (
    "test_wave.py",
    "test_wave_launch.py",
    "test_wave_launch_status.py",
    "test_wave_launch_abort.py",
    "test_wave_launch_abort_keep.py",
    "test_wave_launch_abort_kill.py",
    "test_wave_launch_refusals.py",
    "test_wave_docs.py",
)


def _checks_block(name: str) -> str:
    """`release-checks`' lines under `echo "[checks] <name>"`, up to the next
    `[checks]` line or the end of the file, with comment lines dropped: a file
    named in a comment is not a file the gate runs."""
    lines = _RELEASE_CHECKS.read_text(encoding="utf-8").splitlines()
    heads = [i for i, line in enumerate(lines) if line.startswith(_MARKER)]
    start = next((i for i in heads if lines[i].startswith(f'{_MARKER}{name}"')), None)
    assert start is not None, f"{_RELEASE_CHECKS}: no `[checks] {name}` block"
    end = next((i for i in heads if i > start), len(lines))
    body = [
        line for line in lines[start + 1 : end] if not line.lstrip().startswith("#")
    ]
    return "\n".join(body)


def _test_paths(block: str) -> set[str]:
    """The basenames of the test file PATHS `block` hands to pytest."""
    return {
        Path(token).name
        for token in block.split()
        if "/" in token and token.endswith(".py")
    }


def test_the_release_gate_runs_every_wave_test_file() -> None:
    # Taken from the waves block alone and compared basename-to-basename against
    # that block's own path tokens, so neither another block's pytest line nor a
    # longer name that merely starts the same way answers for a missing file.
    named = _test_paths(_checks_block("waves"))
    for basename in _WAVE_TEST_FILES:
        assert basename in named, (
            f"{_RELEASE_CHECKS}: the `[checks] waves` block does not run {basename}"
        )


_ABORT_HEADING = "## `autopilot wave abort`"
_KEEP_ANCHOR = "Steps 2 and 3 are skipped"


def _abort_keep_region() -> str:
    """`waves.md` on the worktrees `abort` keeps: from the `Steps 2 and 3 are
    skipped` sentence to the end of the `wave abort` section. Anchored on that
    sentence rather than a line number, and cut at the section end so wording
    elsewhere in the runbook cannot satisfy the pins below."""
    text = _WAVES.read_text(encoding="utf-8")
    heading = f"\n{_ABORT_HEADING}\n"
    assert heading in text, f"{_WAVES}: no `{_ABORT_HEADING}` section"
    section = text[text.index(heading) + len(heading) :]
    end = section.find("\n## ")
    section = section if end == -1 else section[:end]
    assert _KEEP_ANCHOR in section, (
        f"{_WAVES}: § wave abort no longer says {_KEEP_ANCHOR!r}, so this pin lost "
        "its anchor - re-anchor it on whatever now introduces the kept worktrees"
    )
    return section[section.index(_KEEP_ANCHOR) :]


def test_the_runbook_matches_what_abort_prints_for_a_kept_worktree() -> None:
    region = _abort_keep_region().lower()
    # The wrong claim this guards against, as the runbook words it today: "...or
    # the worktree has uncommitted changes. The reason is printed - those PRDs are
    # the only record of what the lane was doing." No reason is printed for a
    # worktree git lists: git's own `worktree list` line is the output there, and
    # only the dirty case adds a note on top of it.
    assert "the reason is printed" not in region, region
    assert "worktree list" in region, (
        f"{_WAVES}: § wave abort does not say git's own `worktree list` line is "
        "what gets printed for a kept worktree git lists"
    )
    assert "note" in region, (
        f"{_WAVES}: § wave abort does not say that only a dirty worktree gets an "
        "added note"
    )
