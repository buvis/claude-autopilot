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
_SKILL_TEXT = _SKILL_MD.read_text()
_GATE_FAILURE_MD = _WORK / "references" / "gate-failure.md"


def test_style_gate_names_the_untracked_sweep() -> None:
    # The committed-range enumeration cannot see a module that exists on
    # disk but in no commit, so the gate certified files it never opened.
    # The gate must list untracked Python files and append a whole-file add
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
    assert "line per task" in skill, (
        f"{_SKILL_MD}: step 7's report line no longer promises one style_gate "
        "value per task. With the phase-end gate gone, a single value is a "
        "value for nothing - the verdicts are per task now."
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
        f"{_GATE_FAILURE_MD}: the style-files list no longer marks its "
        "directory lines, so nothing in the prompt distinguishes a directory "
        "the fixer may add to from a file it may only edit."
    )
    assert "You may create new modules" in render, (
        f"{_GATE_FAILURE_MD}: the style-fix RETRY_INSTRUCTION no longer grants "
        "creation permission. `agents/ivan.md` tells a fixer to stop and "
        "report a blocker for anything not listed, so the split never happens. "
        "The marked directory list alone does not grant it - the two strings "
        "are separate, and pinning only the list lets the grant be deleted."
    )


def test_every_step_5_6_exit_reaches_the_gate() -> None:
    # Step 5.65 sits between 5.6 and 5.7, so a 5.6 branch that jumps
    # straight to 5.7 skips the gate entirely. Both of 5.6's skip rules
    # (test-only, trivial) fire on ordinary tasks, so the branch that
    # routes past the gate is the common path, not the rare one, and the
    # task then completes with no style_gate verdict at all.
    skill = _SKILL_MD.read_text()
    step_5_6 = skill[skill.index("### 5.6.") : skill.index("### 5.65.")]
    # The reference is read-first for step 5.6, so its routing is as binding
    # as the body's: a caller who follows it skips the gate just the same.
    deslop_md = _WORK / "references" / "self-deslop-prompt.md"
    sources = ((_SKILL_MD, step_5_6), (deslop_md, deslop_md.read_text()))

    jumps = (
        "proceed to step 5.7",
        "proceed directly to step 5.7",
        "Proceed to 5.7",
    )
    for source, text in sources:
        for jump in jumps:
            assert jump not in text, (
                f"{source}: step 5.6 routes a branch straight to step 5.7 "
                f"({jump!r}), skipping the style gate at 5.65. A task taking "
                "that branch records no style_gate value and its oversize file "
                "reaches the reviewer unmeasured."
            )
    assert "step 5.65" in step_5_6, (
        f"{_SKILL_MD}: step 5.6 never names step 5.65 as what follows it, so "
        "a reader walking the steps in order has nothing pointing at the gate."
    )


def test_the_style_gate_runs_the_script_and_declares_compute_mech_facts() -> None:
    # The gate must run check_style_limits.py and stamp
    # style_gate: clean | fixed:<sha> | failed:<violations>; the function
    # walk must be declared as a cross-skill dependency on
    # compute_mech_facts.py, never a second ast walker. Since PRD 00163 the
    # procedure lives in references/style-gate.md and its base is the task's
    # own <task_base_sha>, not the phase's work_start_sha.
    for needle in (
        "check_style_limits.py",
        "style_gate: clean",
        "fixed:",
        "failed:",
        "task_base_sha",
    ):
        assert needle in _TEXT, (
            f"{_STYLE_GATE_MD}: expected the style gate to contain {needle!r} "
            "— not found."
        )

    dep_start = _SKILL_TEXT.index("## Dependencies")
    dep_end = _SKILL_TEXT.index("\n## ", dep_start)
    dependencies = _SKILL_TEXT[dep_start:dep_end]

    assert "compute_mech_facts.py" in dependencies, (
        f"{_SKILL_MD}: expected '## Dependencies' to name compute_mech_facts.py "
        "— not found."
    )


def test_step_7_stop_condition_permits_a_recorded_style_gate_failure() -> None:
    # Step 5.65 sanctions a recorded `style_gate: failed:<violations>` and
    # explicitly proceeds anyway (fail loud, never silent). Step 7's
    # stop-condition sentence sets the phase's "fully green" bar unqualified
    # today — a task that recorded a style-gate failure leaves the phase not
    # fully green, and that sentence then forbids ending the phase,
    # contradicting the sanctioned exit.
    # The paragraph that states "fully green" must itself scope that bar
    # to the test suite and name the style-gate-failure exception, so a
    # future reword of the sentence can't silently drop the exception and
    # leave the contradiction behind. Checked per-paragraph (never
    # .index()) so a full rewrite of the sentence fails this assertion
    # cleanly instead of raising.
    start = _SKILL_TEXT.index("### 7.")
    end = _SKILL_TEXT.index("## Reference Files", start)
    step_7 = _SKILL_TEXT[start:end]

    stop_condition_paragraphs = [
        paragraph for paragraph in step_7.split("\n\n") if "fully green" in paragraph
    ]

    assert stop_condition_paragraphs, (
        f"{_SKILL_MD}: expected a paragraph in step 7 to state its stop "
        "condition using 'fully green' — none found. If this wording was "
        "deliberately replaced, this test needs updating to locate the "
        "new stop-condition wording."
    )

    for paragraph in stop_condition_paragraphs:
        assert "suite" in paragraph, (
            f"{_SKILL_MD}: expected the paragraph stating step 7's 'fully "
            "green' stop condition to scope it to the test suite — "
            "'suite' not found in that paragraph. Unqualified, 'once step 7 "
            "is fully green' also covers a task's recorded style-gate "
            "failure."
        )
        assert "style_gate: failed" in paragraph, (
            f"{_SKILL_MD}: expected the paragraph stating step 7's 'fully "
            "green' stop condition to name a recorded 'style_gate: "
            "failed:' outcome as a sanctioned way to complete the phase "
            "— not found in that paragraph. Without it, the stop "
            "condition still contradicts step 5.65's 'proceed to step 5.7 "
            "anyway' instruction on a style-gate failure."
        )


def test_style_gate_bare_repo_git_flags_govern_both_diff_invocations() -> None:
    # The gate runs two `git diff` invocations: one writing the task diff
    # (--output=) and one listing changed Python files (--name-only
    # --diff-filter=d). The `--git-dir`/`--work-tree` bare-repo-home
    # parenthetical trailed only the first once, so a literal reader could
    # run the second invocation without the flags and hit
    # `fatal: not a git repository` in a bare-repo home.
    first_idx = _TEXT.index("git diff <base>..HEAD --output=")
    second_idx = _TEXT.index("git diff --name-only --diff-filter=d")

    flag_occurrences = []
    search_from = 0
    while True:
        pos = _TEXT.find("--git-dir", search_from)
        if pos == -1:
            break
        flag_occurrences.append(pos)
        search_from = pos + 1

    assert flag_occurrences, (
        f"{_STYLE_GATE_MD}: expected the gate to mention '--git-dir' at all "
        "— not found."
    )

    scopes_whole_block = any(pos < first_idx for pos in flag_occurrences)
    attached_to_second_too = any(pos >= second_idx for pos in flag_occurrences)

    assert scopes_whole_block or attached_to_second_too, (
        f"{_STYLE_GATE_MD}: expected the '--git-dir'/'--work-tree' bare-repo "
        "flags to be named before the first `git diff` invocation "
        "(scoping the whole block) or to appear again at/after the second "
        "invocation ('git diff --name-only --diff-filter=d') — every "
        "occurrence found trails only the first invocation, exactly like "
        "today's single parenthetical, and a literal reader could run the "
        "second `git diff` without the flags."
    )


def test_style_gate_branches_on_a_gate_that_could_not_run() -> None:
    # The exit-2 branch ("the gate could not run at all") must handle
    # exit 2 specifically, record a `style_gate: failed:` outcome, and must
    # NOT dispatch Ivan — there are no violation lines to hand him, and
    # dispatching on an empty findings list is the failure this branch exists
    # to prevent. The clause must also name what `<reason>` is substituted
    # from: the exit-1 clause spells out its substitution ("the violation
    # lines, joined by '; '"), but exit 2 leaves <reason> undefined today.
    # The script writes its failure message to stderr, so a correct fix
    # names stderr as the source.
    assert "Exit 2" in _TEXT, (
        f"{_STYLE_GATE_MD}: expected the gate to branch on 'Exit 2' (the gate "
        "could not run at all) — not found."
    )

    exit_2_clause = _TEXT.split("Exit 2", 1)[1]

    assert "style_gate: failed:" in exit_2_clause, (
        f"{_STYLE_GATE_MD}: expected the exit-2 branch to record a "
        "'style_gate: failed:' outcome — not found."
    )
    assert "do NOT dispatch Ivan" in exit_2_clause, (
        f"{_STYLE_GATE_MD}: expected the exit-2 branch to say it "
        "does NOT dispatch Ivan — not found. There are no violation lines "
        "to hand a fix agent on this branch, so dispatching one is the "
        "failure exit 2 was introduced to prevent."
    )
    assert "stderr" in exit_2_clause, (
        f"{_STYLE_GATE_MD}: expected the exit-2 branch to name "
        "'stderr' as the source of the '<reason>' substituted into "
        "'style_gate: failed:<reason>' — not found. The exit-1 clause "
        "spells out its substitution ('the violation lines, joined by "
        '"; "\'); exit 2 leaves <reason> undefined, so an agent executing '
        "this literally has to guess what to record."
    )
