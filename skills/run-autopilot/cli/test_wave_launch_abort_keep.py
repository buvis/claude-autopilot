#!/usr/bin/env python3
"""Tests for what `abort` PRINTS about a worktree it keeps (PRD 00214).

Split off `test_wave_launch_abort.py` to keep that file under the 800-line style
limit; that file still owns what a kept worktree does to the tree and the wave,
and these own its output. Every proof runs against a throwaway `git init` repo
under `tmp_path`, never this checkout's own backlog or
`docs/dev/project-management/autopilot/wave.json`, and no real loop is ever started.

The design specifies TWO distinct outputs for a kept worktree: the worktree's own
`git worktree list` line, and - only when it is dirty - one added note. One
synthesized `keeping <path>: <reason>` line satisfies a substring check for the
path and for the note while being neither, which is why these compare against
git's own text rather than against a substring.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cli import wave, wave_launch
from cli.test_wave_launch import TWO_LANES, _git
from cli.test_wave_launch_abort import _launched

_NOTE = "uncommitted change(s), inspect before reusing this worktree"

# The REASON a kept worktree git cannot speak for has to carry: the operator reads
# a log, so the line has to say why no `git worktree list` line stands beside it.
# The words are this suite's choice and the implementor's contract - anything that
# merely prefixes the path leaves the path as unexplained as it is today.
_UNLISTED = "git does not list it as a worktree"


def _listed_line(repo: Path, worktree: Path) -> str:
    """git's own `git worktree list` line for `worktree`, asked of git directly so
    the assertion cannot be satisfied by a line this suite composed itself."""
    for line in _git(repo, "worktree", "list").stdout.splitlines():
        if line.split()[0] == str(worktree):
            return line
    raise AssertionError(f"git does not list {worktree}")


def test_abort_reports_a_kept_worktree_in_gits_own_words(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo, wave_path = _launched(tmp_path, monkeypatch, TWO_LANES)
    lanes = wave.load(wave_path)["lanes"]
    kept = Path(lanes[0]["worktree"])
    (kept / "x").mkdir()
    (kept / "x/a.py").write_text("print('lane work')\n", encoding="utf-8")
    _git(kept, "add", "x/a.py")
    _git(kept, "commit", "-qm", "lane work")
    expected = _listed_line(repo, kept)
    capsys.readouterr()  # the fixture's plan listing, not abort's output
    assert wave_launch.abort(repo, wave_path) == 0
    printed = capsys.readouterr().out.splitlines()
    # git's line, verbatim and on a line of its own: it carries the branch and the
    # HEAD sha an operator needs to find this work again, which a synthesized
    # `keeping <path>: <reason>` line drops.
    assert expected in printed, printed
    # Clean worktree, so the second output is absent entirely - not an empty
    # fragment appended to the line above.
    assert [line for line in printed if _NOTE in line] == [], printed


def test_abort_adds_the_dirty_note_as_its_own_line(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo, wave_path = _launched(tmp_path, monkeypatch, TWO_LANES)
    lanes = wave.load(wave_path)["lanes"]
    kept = Path(lanes[0]["worktree"])
    # TWO changes, one untracked and one a tracked edit, so the reported count is
    # counted rather than a literal "1" a single-file fixture would let through.
    (kept / "NOTES.md").write_text("half-finished work\n", encoding="utf-8")
    (kept / "README.md").write_text("an uncommitted edit\n", encoding="utf-8")
    expected = _listed_line(repo, kept)
    capsys.readouterr()
    assert wave_launch.abort(repo, wave_path) == 0
    printed = capsys.readouterr().out.splitlines()
    assert expected in printed, printed
    # The note is a SECOND output, so it is its own line and does not carry the
    # path: a single `keeping <path>: <n> uncommitted change(s)...` line fails
    # both halves of this.
    notes = [line for line in printed if _NOTE in line]
    assert len(notes) == 1, printed
    assert notes[0] != expected, printed
    assert str(kept) not in notes[0], notes[0]
    assert notes[0].strip().startswith("autopilot: 2 "), notes[0]


def test_abort_explains_a_kept_worktree_git_does_not_list(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo, wave_path = _launched(tmp_path, monkeypatch, TWO_LANES)
    saved = wave.load(wave_path)
    kept = Path(saved["lanes"][0]["worktree"])
    # This wave never recorded creating that worktree, so abort must leave it
    # completely alone - and what sits at the path now is a plain directory git
    # knows nothing about, so git's own listing cannot speak for it.
    saved["lanes"][0]["worktree_created"] = False
    wave.save(wave_path, saved)
    _git(repo, "worktree", "remove", "--force", str(kept))
    kept.mkdir()
    (kept / "NOTES.md").write_text("somebody else's directory\n", encoding="utf-8")
    with pytest.raises(AssertionError):
        _listed_line(repo, kept)  # git does not list it: the branch under test
    capsys.readouterr()  # the fixture's plan listing, not abort's output
    assert wave_launch.abort(repo, wave_path) == 0
    printed = capsys.readouterr().out.splitlines()
    mentions = [line for line in printed if str(kept) in line]
    # Prefixed and explained, never a bare path among lines that all carry the
    # prefix: today's output IS that bare path, so "some line holds the path" is
    # green against the gap this pins.
    assert mentions, printed
    assert [line for line in mentions if not line.startswith("autopilot:")] == [], (
        printed
    )
    assert [line for line in printed if line.strip() == str(kept)] == [], printed
    # ONE line for this lane, and it EXPLAINS: a prefix alone turns the bare path
    # into `autopilot: <path>`, which an operator can still only guess at, and two
    # lines about one kept worktree means the reason lives away from the path.
    assert len(mentions) == 1, printed
    assert mentions[0].strip() != f"autopilot: {kept}", mentions[0]
    assert _UNLISTED in mentions[0], mentions[0]
