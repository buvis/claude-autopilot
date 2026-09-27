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

Inside their anchor both pins ask for a CLAIM rather than for words. The gate pin
reads the block's own `pytest` arguments, so a file the block merely talks about
answers for nothing, and the runbook pin asks two words to share one SENTENCE and
quotes `_NOTE`, the dirty-worktree note text the sibling suite pins against
`abort`'s real output - prose that quotes the code cannot drift from it in silence.
"""

from __future__ import annotations

import re
from pathlib import Path

from cli.test_wave_launch_abort_keep import _NOTE

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
    "test_wave_assemble.py",
    "test_wave_assemble_migrate.py",
    "test_wave_cli_assemble.py",
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


def _pytest_paths(block: str) -> list[str]:
    """The test file paths `block` hands to the RUNNER: the arguments of each of
    its `-m pytest` lines, following the `\\` continuations that carry the rest of
    the invocation. A token anywhere else in the block - an `echo`, a skip list, a
    variable - names a file the gate talks about but does not run."""
    args: list[str] = []
    following = False
    for line in block.splitlines():
        if "-m pytest" in line:
            args.extend(line.split("-m pytest", 1)[1].split())
        elif following:
            args.extend(line.split())
        else:
            continue
        following = line.rstrip().endswith("\\")
    return [token for token in args if token.endswith(".py")]


def test_the_release_gate_runs_every_wave_test_file() -> None:
    # Taken from the waves block's own pytest invocation alone, so a file the block
    # merely mentions - in an echo, or in a line announcing it as skipped - does not
    # answer for a file the gate runs.
    paths = _pytest_paths(_checks_block("waves"))
    named = {Path(path).name for path in paths}
    for basename in _WAVE_TEST_FILES:
        assert basename in named, (
            f"{_RELEASE_CHECKS}: the `[checks] waves` block does not run {basename}"
        )
    # EQUALITY, not containment: a stray or misspelled path in the invocation is a
    # wave file the gate thinks it runs and does not, which is the same hole as an
    # omitted one.
    assert named == set(_WAVE_TEST_FILES), (
        f"{_RELEASE_CHECKS}: the `[checks] waves` block runs "
        f"{sorted(named - set(_WAVE_TEST_FILES))} on top of the wave test files"
    )
    absent = [path for path in paths if not (_ROOT / path).is_file()]
    assert absent == [], (
        f"{_RELEASE_CHECKS}: the `[checks] waves` block names {absent}, which is "
        "not a file in this checkout - pytest would fail on the path, or worse, "
        "collect nothing"
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


def _sentences(region: str) -> list[str]:
    """`region` split on end punctuation followed by whitespace, so `wave.json` and
    `base_sha` stay inside their sentence. Two words in one SENTENCE is a pin on one
    claim; the same two words anywhere in the region is satisfied by a claim and its
    opposite standing side by side."""
    return [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", region)]


def _claims(sentences: list[str], anchor: str, *marks: str) -> list[str]:
    """The sentences of `sentences` holding `anchor` together with one of `marks`."""
    return [
        sentence
        for sentence in sentences
        if anchor in sentence and any(mark in sentence for mark in marks)
    ]


def test_the_runbook_matches_what_abort_prints_for_a_kept_worktree() -> None:
    region = _abort_keep_region().lower()
    sentences = _sentences(region)
    # The wrong claim this guards against, as the runbook words it today: "...or
    # the worktree has uncommitted changes. The reason is printed - those PRDs are
    # the only record of what the lane was doing." No reason is printed for a
    # worktree git lists: git's own `worktree list` line is the output there, and
    # only the dirty case adds a note on top of it.
    assert "the reason is printed" not in region, region
    # The claim, in one sentence, that the listing is abort's OWN output: an
    # instruction to run `git worktree list` yourself afterwards is the opposite of
    # this requirement and reads as satisfying it word for word.
    assert _claims(sentences, "worktree list", "print", "reports"), (
        f"{_WAVES}: § wave abort does not say, in one sentence, that git's own "
        "`worktree list` line is what abort PRINTS for a kept worktree git lists"
    )
    # ...and the note claim scoped to the dirty case, in one sentence.
    assert _claims(sentences, "note", "uncommitted", "dirty"), (
        f"{_WAVES}: § wave abort does not say that the added note belongs to the "
        "dirty worktree"
    )
    # The inverse claims, banned outright: either would make the runbook wrong while
    # leaving every word the pins above look for in place.
    for lie in ("nothing is printed", "nothing at all is printed"):
        assert lie not in region, region
    assert _claims(sentences, "note", "clean") == [], (
        f"{_WAVES}: § wave abort ties the added note to a CLEAN worktree - a clean "
        "one adds no second line at all, so state the note positively: only a dirty "
        "worktree gets one"
    )
    # Strongest of the lot: the note's own text, owned by the code and pinned
    # against abort's real output by `_NOTE`'s sibling tests. Prose quoting it
    # cannot drift from the code without this failing.
    assert _NOTE in region, (
        f"{_WAVES}: § wave abort does not quote the note abort really prints "
        f"({_NOTE!r}), so the runbook can drift from the code in silence"
    )


_SKILL = Path(__file__).resolve().parent.parent / "SKILL.md"
_RETENTION_HEADING = "### Retention"


def _retention_region() -> str:
    """SKILL.md's `### Retention` section: from its heading to the next `## `/
    `### ` heading, so wording elsewhere in SKILL.md cannot satisfy the pin
    below."""
    text = _SKILL.read_text(encoding="utf-8")
    heading = f"\n{_RETENTION_HEADING}\n"
    assert heading in text, f"{_SKILL}: no `{_RETENTION_HEADING}` section"
    section = text[text.index(heading) + len(heading) :]
    ends = [i for i in (section.find("\n## "), section.find("\n### ")) if i != -1]
    return section[: min(ends)] if ends else section


def test_retention_names_the_ledger_copy_of_the_wave_report_as_durable() -> None:
    region = _retention_region().lower()
    sentences = _sentences(region)
    # The corrected claim: one sentence naming the `ledger/` mirror of the wave
    # report as the durable copy, the same shape already used for
    # `ledger/loop-metrics.jsonl` ("the GC-exempt mirror, the durable copy to
    # read").
    assert _claims(sentences, "ledger/<wave id>-wave.md", "durable", "never delete"), (
        f"{_SKILL}: § Retention does not say, in one sentence, that the `ledger/` "
        "copy of the wave report (`ledger/<wave id>-wave.md`) is the durable one"
    )
    # The wrong comparison this guards against, as SKILL.md words it today: the
    # `reports/` copy called "durable like the per-batch report it sits beside" -
    # while the per-batch report is listed as NOT durable two lines below.
    assert "like the per-batch report" not in region, region
    # No sentence may claim durability for the `reports/` copy of the wave
    # report: only the `ledger/` mirror survives cleanup.
    assert _claims(sentences, "reports/<wave id>-wave.md", "durable", "never delete") == [], (
        f"{_SKILL}: § Retention still calls a `reports/` copy of the wave report "
        "durable, but only the `ledger/` mirror is"
    )
