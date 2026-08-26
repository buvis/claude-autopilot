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

import re
from pathlib import Path

_SKILL_MD = Path(__file__).resolve().parent.parent / "SKILL.md"
_TEXT = _SKILL_MD.read_text()


_MAX_SKILL_MD_LINES = 500


def test_work_skill_body_stays_under_the_500_line_ceiling() -> None:
    # SKILL.md is loaded in full on every /work invocation, so its length is a
    # per-session token cost, not a style preference. Counted the way
    # create-skill's validate_skill.py counts it (content.count("\n") + 1,
    # one more than `wc -l`), so this gate and that validator agree at the
    # boundary instead of disagreeing by one line.
    lines = _TEXT.count("\n") + 1

    assert lines <= _MAX_SKILL_MD_LINES, (
        f"{_SKILL_MD} is {lines} lines, over the {_MAX_SKILL_MD_LINES}-line "
        "ceiling. Move situational prose to references/ with a read-first "
        "pointer at its trigger point (the pattern every reference in "
        "'## Reference Files' follows): leave the rule, the tables a routing "
        "or gate decision reads, and any sentence a contract test pins, and "
        "move the mechanics. Do not raise this ceiling."
    )


def test_every_reference_the_body_points_at_exists() -> None:
    # The body now delegates its situational mechanics to references/ through
    # read-first pointers, so a pointer naming a file that is not there is a
    # silently missing procedure at the worst moment (a gate failure, a handoff)
    # — the "missed pointer" risk PRD 00119-v2 names. Cross-skill paths carry
    # their own skill segment (`run-autopilot/references/...`) and resolve
    # against the skills root; bare ones resolve against this skill.
    skills_root = _SKILL_MD.parent.parent
    pattern = re.compile(r"`?([A-Za-z0-9_-]+/)?references/([A-Za-z0-9_-]+\.md)")

    missing = sorted(
        {
            match.group(0).lstrip("`")
            for match in pattern.finditer(_TEXT)
            if not (
                (
                    _SKILL_MD.parent
                    if match.group(1) is None
                    else skills_root / match.group(1).rstrip("/")
                )
                / "references"
                / match.group(2)
            ).exists()
        }
    )

    assert not missing, (
        f"{_SKILL_MD} points at reference files that do not exist: "
        f"{missing}. Either the file was renamed or deleted without updating "
        "the pointer, or the pointer has a typo — both leave the step's "
        "procedure unreachable at its trigger point."
    )


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


def test_step_5_6_treats_an_empty_description_as_absent() -> None:
    # Carried in from PRD 00120's review, decided 2026-08-23: a task whose
    # persisted description is an empty string counts as PRESENT under a bare
    # "when absent" fallback, so /work dispatched step 5.6 with an empty
    # {{task_description}} body instead of the task name — and the name is the
    # more useful payload there. No Python consumer implements the fallback
    # (render_prompt.py has no description handling), so this is a prose
    # contract and this assertion is the only thing binding it.
    start = _TEXT.index("### 5.6.")
    end = _TEXT.index("### 5.7.", start)
    section = _TEXT[start:end]

    assert "fall" in section and "description" in section, (
        f"{_SKILL_MD}: expected step 5.6 to state a `description` fallback — "
        "the section never mentions falling back. If the wording moved, "
        "retarget this test to wherever the fallback now lives."
    )

    # The two words have to be NEIGHBOURS and unnegated, not merely both
    # present: the section already says "when `description` is absent" for the
    # missing-key case, so a bare "empty" anywhere — including in a sentence
    # DENYING the contract — would satisfy a two-substring check while the rule
    # stayed unstated. Same idiom as test_fablectl.py's CLEAN_GAP patterns.
    gap = r"(?:(?!\b(?:not|never|neither|nor)\b)[^.])"
    empty_counts_as_absent = (
        # "an empty-string description counts as absent"
        re.compile(rf"empty{gap}{{0,80}}?absent", re.IGNORECASE),
        # the reverse wording, but only as one tight phrase: a loose
        # "absent ... empty" window matches the missing-key clause that
        # already sits next door, whatever the empty-string clause says.
        re.compile(r"absent or (?:an )?empty", re.IGNORECASE),
    )

    assert any(pattern.search(section) for pattern in empty_counts_as_absent), (
        f"{_SKILL_MD}: step 5.6 never states that an empty-string "
        "`description` counts as ABSENT. A bare 'when `description` is "
        "absent' reads an empty string as present and dispatches an empty "
        "description body. Say it in one clause — 'empty' and 'absent' "
        "within 80 characters of each other, no negation between them and "
        "no sentence break."
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
        # work_start_sha: pins the reworked diff base (PRD 00140 recorded
        # deviation), not a gate-behavior check
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


def test_step_2_7_includes_a_harness_contract_when_one_exists() -> None:
    # PRD 00141: Tess is briefed from requirements only, so a project whose
    # test harness has non-obvious rules (a helper that installs its own
    # sys.stdin, say) gets tests that would pass against the old code too.
    # The convention hands her that contract without handing her the module:
    # for a Contract path `<dir>/<file>`, `<dir>/tests/HARNESS_CONTRACT.md`
    # joins PUBLIC_INTERFACES when it exists. Prose contract in two places —
    # the step that renders the dispatch, and the reference that lists what
    # Tess receives.
    needle = "tests/HARNESS_CONTRACT.md"
    start = _TEXT.index("### 2.7.")
    end = _TEXT.index("### 2.8.", start)
    step_2_7 = _TEXT[start:end]

    assert needle in step_2_7, (
        f"{_SKILL_MD}: step 2.7 never names {needle!r}, so nothing tells the "
        "orchestrator to add a project's harness contract to "
        "PUBLIC_INTERFACES and each dispatch improvises."
    )
    assert "PUBLIC_INTERFACES" in step_2_7, (
        f"{_SKILL_MD}: step 2.7 must say the harness contract joins "
        "PUBLIC_INTERFACES — that is the one render flag Tess reads it from."
    )

    reference = (_SKILL_MD.parent / "references" / "test-author-prompt.md").read_text()
    assert needle in reference, (
        f"references/test-author-prompt.md never names {needle!r}. It is the "
        "file step 2.7 tells the orchestrator to read before the first Tess "
        "dispatch of a batch, so the rule has to be stated there too."
    )


def test_step_3_defines_failing_tests_for_test_only_tasks() -> None:
    # PRD 00141: step 2.7 already skips Tess for test-only, docs-only and
    # config-only tasks, but step 3 never said what fills FAILING_TESTS when
    # there are no failing tests — so each orchestrator improvised, and two
    # PRD 00122 rework tasks got hand-built implementors instead of Ivan.
    # Three pins: the checks file step 3 renders from, the three red_check
    # values (in SKILL.md AND in the reference that enumerates them), and
    # Ivan's persona yielding his blanket test-file ban to the allowlist.
    start = _TEXT.index("### 3.")
    end = _TEXT.index("### 4.", start)
    step_3 = _TEXT[start:end]

    assert "ivan-<task-id>-checks.txt" in step_3, (
        f"{_SKILL_MD}: step 3 never names 'ivan-<task-id>-checks.txt', the "
        "scratch file a test-only task's Verify line and acceptance criteria "
        "are written to and passed as FAILING_TESTS."
    )

    red_check_values = (
        "n/a:test-only-task",
        "n/a:docs-only-task",
        "n/a:config-only-task",
    )
    for value in red_check_values:
        assert value in step_3, (
            f"{_SKILL_MD}: step 3 does not name the red_check value "
            f"{value!r}; step 2.95 is skipped on this lane and an unnamed "
            "value gets recorded as a passed check."
        )

    attempt_logging = (_SKILL_MD.parent / "references" / "attempt-logging.md").read_text()
    for value in red_check_values:
        assert value in attempt_logging, (
            f"references/attempt-logging.md does not enumerate {value!r} in "
            "the red_check field; a value /work writes but the schema "
            "reference does not list reads as corrupt to anyone auditing "
            "the record."
        )

    ivan = (_SKILL_MD.parents[2] / "agents" / "ivan.md").read_text()
    assert "unless your allowlist below names them" in ivan, (
        "agents/ivan.md still bans test files outright. A test-only task "
        "lists them in the allowlist on purpose, so the blanket ban has to "
        "yield to the allowlist that already bounds every dispatch."
    )


def test_step_3_points_at_the_micro_lane_and_the_lane_carries_its_revert() -> None:
    # PRD 00148: a two-finding rework task once cost ~100K subagent tokens and
    # 15 minutes for a 25-line prose trim. The lane skips the dispatch, so its
    # escape hatch is the only thing standing between "small" and "wrong": the
    # overrun revert must be written down where the lane is, not inferred.
    start = _TEXT.index("### 3.")
    end = _TEXT.index("### 4.", start)
    step_3 = _TEXT[start:end]

    for needle in ("rework-mode.md", "Micro lane"):
        assert needle in step_3, (
            f"{_SKILL_MD}: step 3 never names {needle!r}, so nothing routes a "
            "small rework task away from the full Ivan dispatch."
        )

    rework_mode = (_SKILL_MD.parent / "references" / "rework-mode.md").read_text()
    for needle in ('implementor: "orchestrator"', 'micro_lane: "overrun"', "git checkout -- "):
        assert needle in rework_mode, (
            f"references/rework-mode.md never names {needle!r}. The lane's "
            "record and its revert are what make an un-dispatched edit "
            "auditable; without them a skipped pipeline reads as a run one."
        )


def test_step_5_runs_the_reflow_tripwire_over_the_stage_list() -> None:
    # PRD 00148: a formatter reflow (58 hunks) once rode into a task commit
    # unnoticed and the next cycle re-reviewed it as the task's work. Step 5
    # is the only place that sees the stage list before `git add`.
    start = _TEXT.index("### 5. Commit")
    end = _TEXT.index("### 5.5.", start)
    step_5 = _TEXT[start:end]

    for needle in ("check_reflow.py", "reflow:"):
        assert needle in step_5, (
            f"{_SKILL_MD}: step 5 never names {needle!r}, so a whole-file "
            "reflow is staged and committed with nothing recording it."
        )

    dispatch = (_SKILL_MD.parent / "references" / "subagent-dispatch.md").read_text()
    assert "## Reflow tripwire" in dispatch, (
        "references/subagent-dispatch.md has no '## Reflow tripwire' section; "
        "step 5 points at a procedure that is not written anywhere."
    )

    attempt_logging = (_SKILL_MD.parent / "references" / "attempt-logging.md").read_text()
    for value in ('"orchestrator"', '"n/a:micro-lane"', "micro_lane", "reflow"):
        assert value in attempt_logging, (
            f"references/attempt-logging.md does not enumerate {value!r}; a "
            "value /work writes but the schema reference does not list reads "
            "as corrupt to anyone auditing the record."
        )
