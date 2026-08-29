"""Prose pins for the style gate's untracked-file sweep (PRD 00162).

Same pattern as test_dispatch_prose.py — read the file once, assert on
short, reword-resistant substrings, each with a failure message naming
what drifted. Separate file because test_dispatch_prose.py is at the
800-line limit, and this PRD's own gate flags the crossing.

Nothing executes the gate but a reader, so the prose is the whole
mechanism: an untracked module absent from the task diff is a file the
gate certifies without opening. PRD 00163 moved that prose out of
SKILL.md step 7.0 into references/style-gate.md; the pins moved with it.
"""

from __future__ import annotations

import re
from pathlib import Path

_STYLE_GATE_MD = Path(__file__).resolve().parent.parent / "references" / "style-gate.md"
_TEXT = _STYLE_GATE_MD.read_text()


def test_style_gate_names_the_untracked_sweep() -> None:
    # The committed-range enumeration cannot see a module that exists on
    # disk but in no commit, so the gate certified files it never opened.
    # Step 7.0 must list untracked Python files and append a whole-file add
    # block for each, and it must say that `--no-index` exiting 1 is the
    # normal case — a reader who treats that as a command failure abandons
    # the append and the hole reopens.
    for needle in ("ls-files --others", "--no-index"):
        assert needle in _TEXT, (
            f"{_STYLE_GATE_MD}: the gate never names {needle!r}, so an "
            "uncommitted Python file is absent from the task diff and the "
            "gate reports clean over a file it never opened."
        )
    assert "exit ≥2" in _TEXT, (
        f"{_STYLE_GATE_MD}: the gate never says that only exit ≥2 is a real "
        "`--no-index` failure. It exits 1 on every file it appends, so "
        "without that line a literal reader reads the normal case as a "
        "broken command."
    )


def test_style_gate_wires_the_untracked_sweep_into_itself() -> None:
    # Every token above can survive while the sweep is disconnected from the
    # gate, so pin the three joins: the append extends the same file the
    # committed range was written to, that file reaches the path the gate is
    # handed, and the untracked paths enter the candidate list.
    staged = re.search(r"--output=(\S+/task-diff-<task-id>\.txt)", _TEXT)
    assert staged, (
        f"{_STYLE_GATE_MD}: the gate no longer writes the committed range to "
        "a task-diff-<task-id>.txt — the rest of this pin cannot be checked."
    )
    target = staged.group(1)
    assert f">> {target}" in _TEXT, (
        f"{_STYLE_GATE_MD}: the gate appends the untracked blocks somewhere "
        f"other than {target}, the file it just wrote the committed range to, "
        "so it reads a diff missing one half of the task."
    )
    assert f"mv {target} dev/local/tmp/task-diff-<task-id>.txt" in _TEXT, (
        f"{_STYLE_GATE_MD}: the gate never moves {target} to "
        "dev/local/tmp/task-diff-<task-id>.txt, which is the path it hands "
        "the script."
    )
    assert "--diff dev/local/tmp/task-diff-<task-id>.txt" in _TEXT, (
        f"{_STYLE_GATE_MD}: the gate no longer runs the script against "
        "dev/local/tmp/task-diff-<task-id>.txt, the file it assembled."
    )
    assert "plus those untracked paths" in _TEXT, (
        f"{_STYLE_GATE_MD}: the gate never adds the untracked paths to the "
        "candidate list. A path absent from that list is never inspected, "
        "however complete the diff is."
    )
