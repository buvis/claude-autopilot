"""Tests binding the live text of ${CLAUDE_PLUGIN_ROOT}/skills/work/SKILL.md — Suite 3 of
the PRD 00093 test debt.

PRD 00093 shipped four prose-only fixes to the dispatch steps (each persona
rendered through render_prompt.py, no dispatch step authoring prompt text by
hand, task-authored prose always crossing the shell via --set-file) with no
test at all, so a revert of that prose would go undetected with every other
suite green. Mirrors run-autopilot/scripts/test_fablectl.py's pattern for
pinning a skill file's prose: resolve the path relative to this file, read it
once, and assert on short, reword-resistant substrings (a filename, a flag
spelling), each with a failure message naming what drifted and where to look.
"""

from __future__ import annotations

from pathlib import Path

_SKILL_MD = Path(__file__).resolve().parent.parent / "SKILL.md"
_TEXT = _SKILL_MD.read_text()


def test_tess_dispatch_is_rendered_through_render_prompt_py() -> None:
    # Step 2.7 must dispatch Tess via render_prompt.py naming tess-prompt.md,
    # never author her prompt text inline.
    needle = (
        "render_prompt.py ${CLAUDE_PLUGIN_ROOT}/skills/work/references/tess-prompt.md"
    )

    assert needle in _TEXT, (
        f"{_SKILL_MD}: expected the Tess dispatch (step 2.7) to invoke "
        f"render_prompt.py naming tess-prompt.md — did not find {needle!r}. "
        "The Tess persona render call appears to have drifted or been removed."
    )


def test_ivan_dispatch_is_rendered_through_render_prompt_py() -> None:
    # Step 3 (and its step-5.5/7 retries) must dispatch Ivan via
    # render_prompt.py naming agents/ivan.md, never author his prompt by hand.
    needle = "render_prompt.py ${CLAUDE_PLUGIN_ROOT}/agents/ivan.md"

    assert needle in _TEXT, (
        f"{_SKILL_MD}: expected an Ivan dispatch to invoke render_prompt.py "
        f"naming agents/ivan.md — did not find {needle!r}. The Ivan persona "
        "render call appears to have drifted or been removed."
    )


def test_pat_dispatch_is_rendered_through_render_prompt_py() -> None:
    # Step 5.7's per-task reviewer must dispatch Pat via render_prompt.py
    # naming agents/pat.md, never author his prompt by hand.
    needle = "render_prompt.py ${CLAUDE_PLUGIN_ROOT}/agents/pat.md"

    assert needle in _TEXT, (
        f"{_SKILL_MD}: expected the step-5.7 reviewer dispatch to invoke "
        f"render_prompt.py naming agents/pat.md — did not find {needle!r}. "
        "The Pat persona render call appears to have drifted or been removed."
    )


def test_no_dispatch_step_instructs_authoring_the_code_quality_rules_block() -> None:
    # No dispatch step may tell the orchestrator to compose Ivan's
    # code-quality rules itself — the block is permanent in ivan.md.
    phrase = "code-quality rules block from"

    assert phrase not in _TEXT, (
        f"{_SKILL_MD}: found the phrase {phrase!r} — this instructs the "
        "orchestrator to author prompt text itself instead of relying on "
        "ivan.md's permanent code-quality rules block. PRD 00093 removed "
        "this phrasing; it has regressed."
    )


def test_task_authored_prose_flags_never_cross_the_shell_via_set() -> None:
    # Task-authored prose (subject, description, acceptance criteria, file
    # paths) must always cross render_prompt.py via --set-file (a path), never
    # --set (a shell word) — backticks or $() in task text would otherwise be
    # expanded by the shell before render_prompt.py ever sees them.
    banned_flags = (
        "--set TASK_SUBJECT=",
        "--set TASK_DESCRIPTION=",
        "--set TASK_ACCEPTANCE_CRITERIA=",
        "--set FILE_PATHS=",
    )

    for flag in banned_flags:
        assert flag not in _TEXT, (
            f"{_SKILL_MD}: found {flag!r} — task-authored prose must be "
            "passed with --set-file, never --set, or task text containing "
            "backticks/$() silently corrupts the rendered prompt."
        )


def test_step_5_7_gives_in_task_medium_findings_one_retry_stamped_medium_retry() -> (
    None
):
    # Step 5.7: a MEDIUM inside the task's FILES_TOUCHED gets one Ivan retry
    # and a Pat re-run before step 6, stamped "medium-retry:<fixed|unfixed>";
    # other MEDIUMs and all LOWs keep today's note-and-proceed behaviour.
    start = _TEXT.index("### 5.7.")
    end = _TEXT.index("### 6.", start)
    section = _TEXT[start:end]

    assert "FILES_TOUCHED" in section, (
        f"{_SKILL_MD}: expected step 5.7 to name FILES_TOUCHED — not found."
    )
    assert "medium-retry:" in section, (
        f"{_SKILL_MD}: expected step 5.7 to stamp 'medium-retry:' — not found."
    )


def test_step_7_runs_the_style_limit_gate_and_declares_compute_mech_facts() -> None:
    # Step 7 must run check_style_limits.py before the full suite and stamp
    # style_gate: clean | fixed:<sha> | failed:<violations>; the function
    # walk must be declared as a cross-skill dependency on
    # compute_mech_facts.py, never a second ast walker.
    start = _TEXT.index("### 7.")
    end = _TEXT.index("## Reference Files", start)
    step_7 = _TEXT[start:end]

    for needle in (
        "check_style_limits.py",
        "style_gate: clean",
        "fixed:",
        "failed:",
        "work_start_sha",
    ):
        assert needle in step_7, (
            f"{_SKILL_MD}: expected step 7 to contain {needle!r} — not found."
        )

    dep_start = _TEXT.index("## Dependencies")
    dep_end = _TEXT.index("\n## ", dep_start)
    dependencies = _TEXT[dep_start:dep_end]

    assert "compute_mech_facts.py" in dependencies, (
        f"{_SKILL_MD}: expected '## Dependencies' to name compute_mech_facts.py "
        "— not found."
    )


def test_step_7_stop_condition_permits_a_recorded_style_gate_failure() -> None:
    # Step 7.0 sanctions a recorded `style_gate: failed:<violations>` and
    # explicitly proceeds to the suite anyway (fail loud, never silent).
    # Step 7's stop-condition sentence sets the phase's "fully green" bar
    # unqualified today — step 7.0 is a sub-step of step 7, so a recorded
    # style-gate failure leaves step 7 not fully green, and that sentence
    # then forbids ending the phase, contradicting the sanctioned exit.
    # The paragraph that states "fully green" must itself scope that bar
    # to the test suite and name the style-gate-failure exception, so a
    # future reword of the sentence can't silently drop the exception and
    # leave the contradiction behind. Checked per-paragraph (never
    # .index()) so a full rewrite of the sentence fails this assertion
    # cleanly instead of raising.
    start = _TEXT.index("### 7.")
    end = _TEXT.index("## Reference Files", start)
    step_7 = _TEXT[start:end]

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
            "'suite' not found in that paragraph. Today it reads 'once "
            "step 7 is fully green', unqualified, which also covers step "
            "7.0's style gate."
        )
        assert "style_gate: failed" in paragraph, (
            f"{_SKILL_MD}: expected the paragraph stating step 7's 'fully "
            "green' stop condition to name a recorded 'style_gate: "
            "failed:' outcome as a sanctioned way to complete the phase "
            "— not found in that paragraph. Without it, the stop "
            "condition still contradicts step 7.0's 'proceed to the "
            "suite anyway' instruction on a style-gate failure."
        )


def test_step_7_0_bare_repo_git_flags_govern_both_diff_invocations() -> None:
    # Step 7.0 runs two `git diff` invocations: one writing the phase diff
    # (--output=) and one listing changed Python files (--name-only
    # --diff-filter=d). The `--git-dir`/`--work-tree` bare-repo-home
    # parenthetical trails only the first today, so a literal reader could
    # run the second invocation without the flags and hit
    # `fatal: not a git repository` in a bare-repo home.
    start = _TEXT.index("#### 7.0.")
    end = _TEXT.index("**What to run**", start)
    step_7_0 = _TEXT[start:end]

    first_idx = step_7_0.index("git diff <base>..HEAD --output=")
    second_idx = step_7_0.index("git diff --name-only --diff-filter=d")

    flag_occurrences = []
    search_from = 0
    while True:
        pos = step_7_0.find("--git-dir", search_from)
        if pos == -1:
            break
        flag_occurrences.append(pos)
        search_from = pos + 1

    assert flag_occurrences, (
        f"{_SKILL_MD}: expected step 7.0 to mention '--git-dir' at all — not found."
    )

    scopes_whole_block = any(pos < first_idx for pos in flag_occurrences)
    attached_to_second_too = any(pos >= second_idx for pos in flag_occurrences)

    assert scopes_whole_block or attached_to_second_too, (
        f"{_SKILL_MD}: expected the '--git-dir'/'--work-tree' bare-repo "
        "flags to be named before the first `git diff` invocation "
        "(scoping the whole block) or to appear again at/after the second "
        "invocation ('git diff --name-only --diff-filter=d') — every "
        "occurrence found trails only the first invocation, exactly like "
        "today's single parenthetical, and a literal reader could run the "
        "second `git diff` without the flags."
    )


def test_step_7_0_branches_on_a_gate_that_could_not_run() -> None:
    # Step 7.0's exit-2 branch ("the gate could not run at all") must handle
    # exit 2 specifically, record a `style_gate: failed:` outcome, and must
    # NOT dispatch Ivan — there are no violation lines to hand him, and
    # dispatching on an empty findings list is the failure this branch exists
    # to prevent. The clause must also name what `<reason>` is substituted
    # from: the exit-1 clause spells out its substitution ("the violation
    # lines, joined by '; '"), but exit 2 leaves <reason> undefined today.
    # The script writes its failure message to stderr, so a correct fix
    # names stderr as the source.
    start = _TEXT.index("#### 7.0.")
    end = _TEXT.index("**What to run**", start)
    step_7_0 = _TEXT[start:end]

    assert "Exit 2" in step_7_0, (
        f"{_SKILL_MD}: expected step 7.0 to branch on 'Exit 2' (the gate "
        "could not run at all) — not found."
    )

    exit_2_clause = step_7_0.split("Exit 2", 1)[1]

    assert "style_gate: failed:" in exit_2_clause, (
        f"{_SKILL_MD}: expected the exit-2 branch of step 7.0 to record a "
        "'style_gate: failed:' outcome — not found."
    )
    assert "do NOT dispatch Ivan" in exit_2_clause, (
        f"{_SKILL_MD}: expected the exit-2 branch of step 7.0 to say it "
        "does NOT dispatch Ivan — not found. There are no violation lines "
        "to hand a fix agent on this branch, so dispatching one is the "
        "failure exit 2 was introduced to prevent."
    )
    assert "stderr" in exit_2_clause, (
        f"{_SKILL_MD}: expected the exit-2 branch of step 7.0 to name "
        "'stderr' as the source of the '<reason>' substituted into "
        "'style_gate: failed:<reason>' — not found. The exit-1 clause "
        "spells out its substitution ('the violation lines, joined by "
        '"; "\'); exit 2 leaves <reason> undefined, so an agent executing '
        "this literally has to guess what to record."
    )
