"""Prose pins for step 7.0's untracked-file sweep (PRD 00162).

Same pattern as test_dispatch_prose.py — read SKILL.md once, assert on
short, reword-resistant substrings, each with a failure message naming
what drifted. Separate file because test_dispatch_prose.py is at the
800-line limit, and this PRD's own gate flags the crossing.

Nothing executes step 7.0 but a reader, so the prose is the whole
mechanism: an untracked module absent from the phase diff is a file the
gate certifies without opening.
"""

from __future__ import annotations

import re
from pathlib import Path

_SKILL_MD = Path(__file__).resolve().parent.parent / "SKILL.md"
_TEXT = _SKILL_MD.read_text()


def _step_7_0() -> str:
    start = _TEXT.index("#### 7.0.")
    return _TEXT[start : _TEXT.index("**What to run**", start)]


def test_step_7_0_names_the_untracked_sweep() -> None:
    # The committed-range enumeration cannot see a module that exists on
    # disk but in no commit, so the gate certified files it never opened.
    # Step 7.0 must list untracked Python files and append a whole-file add
    # block for each, and it must say that `--no-index` exiting 1 is the
    # normal case — a reader who treats that as a command failure abandons
    # the append and the hole reopens.
    step_7_0 = _step_7_0()

    for needle in ("ls-files --others", "--no-index"):
        assert needle in step_7_0, (
            f"{_SKILL_MD}: step 7.0 never names {needle!r}, so an uncommitted "
            "Python file is absent from the phase diff and the gate reports "
            "clean over a file it never opened."
        )
    assert "exit ≥2" in step_7_0, (
        f"{_SKILL_MD}: step 7.0 never says that only exit ≥2 is a real "
        "`--no-index` failure. It exits 1 on every file it appends, so "
        "without that line a literal reader reads the normal case as a "
        "broken command."
    )


def test_step_7_0_wires_the_untracked_sweep_into_the_gate() -> None:
    # Every token above can survive while the sweep is disconnected from the
    # gate, so pin the three joins: the append extends the same file the
    # committed range was written to, that file reaches the path the gate is
    # handed, and the untracked paths enter the candidate list.
    step_7_0 = _step_7_0()

    staged = re.search(r"--output=(\S+/phase-diff\.txt)", step_7_0)
    assert staged, (
        f"{_SKILL_MD}: step 7.0 no longer writes the committed range to a "
        "phase-diff.txt — the rest of this pin cannot be checked."
    )
    target = staged.group(1)
    assert f">> {target}" in step_7_0, (
        f"{_SKILL_MD}: step 7.0 appends the untracked blocks somewhere other "
        f"than {target}, the file it just wrote the committed range to, so "
        "the gate reads a diff missing one half of the phase."
    )
    assert f"mv {target} dev/local/tmp/phase-diff.txt" in step_7_0, (
        f"{_SKILL_MD}: step 7.0 never moves {target} to "
        "dev/local/tmp/phase-diff.txt, which is the path it hands the gate."
    )
    assert "--diff dev/local/tmp/phase-diff.txt" in step_7_0, (
        f"{_SKILL_MD}: step 7.0 no longer runs the gate against "
        "dev/local/tmp/phase-diff.txt, the file it assembled."
    )
    assert "plus those untracked paths" in step_7_0, (
        f"{_SKILL_MD}: step 7.0 never adds the untracked paths to the "
        "candidate list. A path absent from that list is never inspected, "
        "however complete the diff is."
    )
