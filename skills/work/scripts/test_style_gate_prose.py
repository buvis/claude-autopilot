"""Prose pins for the per-task style-limit gate (PRDs 00162, 00163).

Same pattern as test_dispatch_prose.py — read the file once, assert on
short, reword-resistant substrings, each with a failure message naming
what drifted. Separate file because test_dispatch_prose.py is near its
800-line limit, and the gate's own arithmetic flags the crossing.

Nothing executes the gate but a reader, so the prose is the whole
mechanism: an untracked module absent from the task diff is a file the
gate certifies without opening. PRD 00163 moved that prose out of
SKILL.md step 7.0 into references/style-gate.md and made the gate run per
task; the pins moved with it.
"""

from __future__ import annotations

import re
from pathlib import Path

_WORK = Path(__file__).resolve().parent.parent
_STYLE_GATE_MD = _WORK / "references" / "style-gate.md"
_TEXT = _STYLE_GATE_MD.read_text()
_SKILL_MD = _WORK / "SKILL.md"
_GATE_FAILURE_MD = _WORK / "references" / "gate-failure.md"


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


def test_skill_md_calls_the_gate_at_the_task_boundary() -> None:
    # PRD 00163: the gate runs per task, so SKILL.md must call it at step
    # 5.65 and must no longer carry step 7.0. Both halves matter — a 5.65
    # that lands while 7.0 survives doubles the fix dispatches this move
    # exists to cut, and the haiku row has to name its stamp or a skipped
    # gate reads as a passed one.
    skill = _SKILL_MD.read_text()

    assert "5.65" in skill, (
        f"{_SKILL_MD}: no step 5.65. The style gate has no call site, so it "
        "runs for no task at all."
    )
    assert "7.0" not in skill, (
        f"{_SKILL_MD}: step 7.0 is back. The phase-end gate re-measures every "
        "task's diff at once, which is the dispatch PRD 00163 removed."
    )
    assert "skipped:tier" in skill, (
        f"{_SKILL_MD}: step 5.65 never names the `skipped:tier` stamp, so a "
        "haiku task that skipped the gate records nothing and reads as one "
        "that passed it."
    )


def test_the_style_fix_dispatch_has_its_own_allowlist() -> None:
    # The fix for an oversize file is a split, and a split needs a sibling
    # module that is by construction absent from the task's Contract paths.
    # gate-failure.md must render that one dispatch from the style-files
    # list; without it Ivan can only report a blocker.
    render = _GATE_FAILURE_MD.read_text()

    assert "style-files" in render, (
        f"{_GATE_FAILURE_MD}: the style-fix render no longer names the "
        "style-files list, so it falls back to the task's Contract paths and "
        "a split has nowhere to put the module it creates."
    )
    assert "new modules may be created here" in render, (
        f"{_GATE_FAILURE_MD}: the style-fix RETRY_INSTRUCTION no longer grants "
        "creation permission. `agents/ivan.md` tells a fixer to stop and "
        "report a blocker for anything not listed, so the split never happens."
    )
