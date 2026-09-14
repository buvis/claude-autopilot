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
        },
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


def test_step_2_8_runs_the_shape_check_before_the_four_check_rubric() -> None:
    # A tautological test that reaches the review comes back as a mech-check
    # finding and a rework cycle; step 2.8 is where it is cheapest to catch.
    # Two pins: the step names the check, and the reference the step routes
    # to carries the script plus the every-hit-is-a-failure rule.
    needle = "detect_tautological_tests.py"
    start = _TEXT.index("### 2.8.")
    end = _TEXT.index("### 2.85.", start)
    step_2_8 = _TEXT[start:end]

    assert "shape check" in step_2_8, (
        f"{_SKILL_MD}: step 2.8 no longer tells the orchestrator to run the "
        "computed shape check before the four-check rubric."
    )

    reference = (_SKILL_MD.parent / "references" / "test-author-prompt.md").read_text()
    gate = reference[reference.index("## Quality gate") :]
    assert needle in gate, (
        f"references/test-author-prompt.md § Quality gate never names {needle!r}, "
        "so the gate is back to judging tautologies by eye alone."
    )
    assert "Every `[MECH]` line is a check-4 failure" in gate, (
        "references/test-author-prompt.md § Quality gate must say every [MECH] "
        "line is a gate failure, or a hit is advisory and gets waved through."
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

    attempt_logging = (
        _SKILL_MD.parent / "references" / "attempt-logging.md"
    ).read_text()
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
    for needle in (
        'implementor: "orchestrator"',
        'micro_lane: "overrun"',
        "git checkout -- ",
    ):
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

    attempt_logging = (
        _SKILL_MD.parent / "references" / "attempt-logging.md"
    ).read_text()
    for value in ('"orchestrator"', '"n/a:micro-lane"', "micro_lane", "reflow"):
        assert value in attempt_logging, (
            f"references/attempt-logging.md does not enumerate {value!r}; a "
            "value /work writes but the schema reference does not list reads "
            "as corrupt to anyone auditing the record."
        )


# --- PRD 00159: the test-only gate, the tool-less Pat, the output contract ----


def test_step_2_captures_a_task_base_sha_for_every_task() -> None:
    # Steps 5.6, 5.7 and BASE_SHA all diff against this one base. Before PRD
    # 00159 they used the parent of the test commit, which does not exist for a
    # test-only, docs-only, config-only or micro-lane task — so BASE_SHA was
    # simply undefined there and the review diffed from nowhere.
    start = _TEXT.index("### 2. Claim")
    end = _TEXT.index("### 2.5.", start)
    step_2 = _TEXT[start:end]

    assert "task_base_sha" in step_2, (
        f"{_SKILL_MD}: step 2 never captures `<task_base_sha>`, so steps 5.6 "
        "and 5.7 have no base to diff against on a task that commits no tests."
    )

    gate_failure = (_SKILL_MD.parent / "references" / "gate-failure.md").read_text()
    assert "task_base_sha" in gate_failure, (
        "references/gate-failure.md § Test-commit SHA still derives step 5.7's "
        "BASE_SHA from the test commit; it must name `<task_base_sha>`."
    )


def test_step_5_6_skips_the_deslop_pass_on_a_test_only_diff() -> None:
    start = _TEXT.index("### 5.6.")
    end = _TEXT.index("### 5.7.", start)
    step_5_6 = _TEXT[start:end]

    for needle in ("test_only_diff", "skipped:test-only"):
        assert needle in step_5_6, (
            f"{_SKILL_MD}: step 5.6 never names {needle!r}, so a test-only "
            "diff pays a de-slop dispatch that is forbidden to touch tests."
        )


def test_step_5_7_skips_the_review_and_renders_the_two_new_placeholders() -> None:
    # The skip and the placeholders travel together: skipping the review is what
    # makes the lane cheap, and the placeholders are what make the review that
    # DOES run judge the prompt alone instead of reading around the repo.
    start = _TEXT.index("### 5.7.")
    end = _TEXT.index("### 6.", start)
    step_5_7 = _TEXT[start:end]

    for needle in (
        "test_only_gate",
        "skipped:test-only",
        "VERIFICATION_RESULT",
        "CONTRACT_CORRECTION",
    ):
        assert needle in step_5_7, (
            f"{_SKILL_MD}: step 5.7 never names {needle!r}. Without it the "
            "reviewer either runs where PRD 00159 says it should not, or runs "
            "without the evidence its tool-less dispatch depends on."
        )


def test_per_task_review_carries_the_tool_less_dispatch_and_the_output_gate() -> None:
    review = (_SKILL_MD.parent / "references" / "per-task-review.md").read_text()

    for needle in ('-t ""', "parse_review.py", "failed:invalid_output"):
        assert needle in review, (
            f"references/per-task-review.md never names {needle!r}. The "
            "dispatch would grant tools the persona says it does not use, or a "
            "malformed reply would pass as an empty review."
        )


def test_attempt_logging_enumerates_both_new_review_values() -> None:
    attempt_logging = (
        _SKILL_MD.parent / "references" / "attempt-logging.md"
    ).read_text()

    for value in ("skipped:test-only", "failed:invalid_output"):
        assert value in attempt_logging, (
            f"references/attempt-logging.md does not enumerate {value!r}; /work "
            "writes it, so a reader auditing the record cannot tell a skipped "
            "review from a broken one."
        )


def test_pat_persona_carries_both_new_placeholders() -> None:
    pat = _SKILL_MD.parent.parent.parent / "agents" / "pat.md"
    body = pat.read_text()

    for placeholder in ("{VERIFICATION_RESULT}", "{CONTRACT_CORRECTION}"):
        assert placeholder in body, (
            f"agents/pat.md is missing {placeholder}. Step 5.7 passes it to "
            "render_prompt.py, and a set placeholder with nowhere to land is "
            "silently dropped rather than reaching the reviewer."
        )


# --- PRD 00165: the resumable reviewer session and its delta re-run ----------


def test_step_5_7_mints_a_reviewer_session_id_and_moves_the_review_base() -> None:
    # Without both handles a re-run has nothing to resume and nothing to diff
    # from, so it silently degrades to re-sending the whole task diff — the
    # 369 KB double dispatch PRD 00165 exists to stop.
    start = _TEXT.index("### 5.7.")
    end = _TEXT.index("### 6.", start)
    step_5_7 = _TEXT[start:end]

    for needle in ("pat_session_id", "last_reviewed_sha"):
        assert needle in step_5_7, (
            f"{_SKILL_MD}: step 5.7 never names {needle!r}. The per-task review "
            "then has no id to resume and no moving base, and every re-review "
            "re-reads the diff the reviewer already read."
        )


def test_step_5_7_mints_the_reviewer_id_with_python_before_uuidgen() -> None:
    # Unattended sessions on a host without a warden allow for uuidgen would
    # lose the id (and with it the resumable session and the delta re-run), so
    # the python form must be the one the step names first; uuidgen is only
    # the fallback (fix(work) fda6abd). The test above passes in either order.
    start = _TEXT.index("### 5.7.")
    end = _TEXT.index("### 6.", start)
    step_5_7 = _TEXT[start:end]
    python_form = 'python3 -c "import uuid,sys;sys.stdout.write(str(uuid.uuid4()))"'

    assert python_form in step_5_7, (
        f"{_SKILL_MD}: step 5.7 never names the python uuid4 form, so a host "
        "without uuidgen mints no reviewer session id."
    )
    assert step_5_7.index(python_form) < step_5_7.index("`uuidgen`"), (
        f"{_SKILL_MD}: step 5.7 names uuidgen before the python form; the "
        "allowlist-free form must come first and uuidgen stay the fallback."
    )


def test_per_task_review_carries_the_delta_rerun_and_its_fallback() -> None:
    review = (_SKILL_MD.parent / "references" / "per-task-review.md").read_text()

    for needle in ('-S "', '-R "', "pat-rerun-prompt.md", "resume_failed"):
        assert needle in review, (
            f"references/per-task-review.md never names {needle!r}. Either the "
            "first dispatch stopped fixing a session id, the re-run stopped "
            "resuming it, or a failed resume lost its fallback — and a review "
            "that silently did not happen is the one failure this lane must "
            "never have."
        )


def test_the_delta_rerun_advances_its_base_and_never_resumes_a_dead_session() -> None:
    # Token presence alone would pass while the lane still re-sent the whole
    # diff every cycle: the base has to MOVE, and the two paths with no live
    # session (never minted, or dropped after a fallback) have to route to the
    # full-diff dispatch instead of aiming `-R ""` at nothing.
    review = (_SKILL_MD.parent / "references" / "per-task-review.md").read_text()

    start = review.index("## Delta re-runs")
    delta = review[start : review.index("## Result handling", start)]

    assert "Advance `<last_reviewed_sha>`" in delta, (
        "references/per-task-review.md § Delta re-runs never says to advance "
        "`<last_reviewed_sha>`. Without that step every cycle re-sends the "
        "range the reviewer already read, which is the whole cost PRD 00165 "
        "set out to remove."
    )
    # The PROHIBITION, not the token: a bare `'-R ""' in delta` would pass just
    # as happily on prose that told the executor to dispatch it.
    assert 'Never dispatch `-R ""`' in delta, (
        "references/per-task-review.md § Delta re-runs never forbids "
        'dispatching `-R ""`. A task whose id could not be generated, or whose '
        "session was dropped by a failed resume, then resumes nothing on every "
        "remaining cycle."
    )

    fallback = review[review.index("## Resume failure") :]
    assert "drop `<pat_session_id>`" in fallback, (
        "references/per-task-review.md § Resume failure never drops "
        "`<pat_session_id>` after the fallback. The session is known dead at "
        "that point, so every later cycle aims a `-R` at it and burns another "
        "doomed dispatch."
    )
    # The fallback is ONE dispatch out of an existing budget. Unbounded, a
    # flapping resume turns each cycle into two full-diff reviews — more
    # expensive than the lane this PRD replaced.
    assert "re-dispatches **once**" in fallback, (
        "references/per-task-review.md § Resume failure does not bound the "
        "fallback to a single dispatch."
    )
    assert "not an extra" in fallback, (
        "references/per-task-review.md § Resume failure no longer says the "
        "fallback spends the runner-failure row's existing retry rather than "
        "adding one. Without that, a resume that keeps failing gets a fresh "
        "budget every cycle."
    )


def test_the_correction_retry_never_reuses_the_session_id_it_already_created() -> None:
    # Verified live 2026-08-28: a second --session-id carrying the same uuid
    # exits 1 on "Session ID <id> is already in use." The correction retry gets
    # exactly one dispatch, so spending it on that error costs the whole review.
    review = (_SKILL_MD.parent / "references" / "per-task-review.md").read_text()

    exit_1_clause = review.split("**Exit 1**", 1)[1].split("**Exit 2**", 1)[0]

    assert "already in use" in exit_1_clause, (
        "references/per-task-review.md's exit-1 branch does not say why the "
        "correction retry must not re-pass `-S`. Its dispatch flags went "
        "unstated once § Dispatch grew a `-S`, and the naive reading reuses an "
        "id claude rejects."
    )
    assert "never `-S`" in exit_1_clause, (
        "references/per-task-review.md's exit-1 branch does not forbid `-S` on "
        "the correction retry — the one dispatch it gets would die on a "
        "duplicate session id instead of re-asking for the line shape."
    )


def test_the_rerun_template_keeps_all_three_placeholders() -> None:
    # render_prompt.py exits 1 on an UNFILLED placeholder, but a placeholder
    # DELETED from the template is a --set that lands nowhere: the render
    # succeeds and the reviewer silently never sees the delta.
    template = (_SKILL_MD.parent / "references" / "pat-rerun-prompt.md").read_text()

    for placeholder in ("{PRIOR_FINDINGS}", "{DELTA_DIFF}", "{UNCHANGED_NOTE}"):
        assert placeholder in template, (
            f"references/pat-rerun-prompt.md is missing {placeholder}. The "
            "re-run render sets it, and a set value with nowhere to land is "
            "dropped without an error."
        )


def test_the_rerun_template_will_not_let_an_unresolved_finding_vanish() -> None:
    # The template tells the reviewer not to re-report the earlier range. Left
    # there, an unfixed HIGH plus a clean-looking delta yields a parseable
    # NO FINDINGS, the ladder proceeds to step 6, and the defect ships — a
    # coverage regression against the full-diff re-review this replaces. So an
    # unresolved finding must come back as a contract line, and NO FINDINGS must
    # require BOTH a clean delta and no unresolved finding.
    template = (_SKILL_MD.parent / "references" / "pat-rerun-prompt.md").read_text()

    assert "unresolved as a contract line" in template, (
        "references/pat-rerun-prompt.md never tells the reviewer to re-emit an "
        "unresolved prior finding as a contract line. Silence then reads as "
        "fixed: parse_review.py sees no finding, the ladder proceeds, and the "
        "defect ships."
    )
    assert "only when the delta is clean AND" in template, (
        "references/pat-rerun-prompt.md does not reserve NO FINDINGS for a "
        "clean delta AND every prior finding resolved. A reviewer reading "
        "'NO FINDINGS when the delta has none' emits it with a prior HIGH "
        "still open."
    )


def test_attempt_logging_enumerates_the_resume_failure_note() -> None:
    attempt_logging = (
        _SKILL_MD.parent / "references" / "attempt-logging.md"
    ).read_text()

    assert "resume_failed" in attempt_logging, (
        "references/attempt-logging.md does not enumerate 'resume_failed'; "
        "/work writes it, so a reader auditing the record cannot tell a delta "
        "re-review from one that fell back to the full diff."
    )


def test_the_simplification_mandate_maps_simplifications_to_low() -> None:
    # The whole point of PRD 00159's severity split: a behavior-preserving
    # simplification must not cost an Ivan dispatch and a Pat re-run. While the
    # mandate still said "Important, not Minor", every naming nit did.
    mandate = (
        _SKILL_MD.parent / "references" / "simplification-mandate.md"
    ).read_text()

    assert "Important, not Minor" not in mandate, (
        "references/simplification-mandate.md still classifies simplifications "
        "as Important, which routes them into the MEDIUM-in-task retry PRD "
        "00159 removed them from."
    )
    assert "LOW" in mandate, (
        "references/simplification-mandate.md no longer maps simplifications "
        "to a severity at all; LOW is the value the retry rule keys on."
    )


def test_step_5_65_runs_split_hygiene_over_the_test_subset() -> None:
    # PRD 00166. The check is worthless if the body never names it: a reader
    # following step 5.65 has to reach the script and the empty-subset value
    # from SKILL.md alone, because that is the only file /work loads in full.
    step = _TEXT.split("### 5.65.")[1].split("### 5.7.")[0]

    assert "check_split_hygiene.py" in step, (
        "SKILL.md step 5.65 never names check_split_hygiene.py, so the "
        "split-hygiene check is documented in a reference nothing points at."
    )
    assert "skipped:no-tests" in step, (
        "SKILL.md step 5.65 does not say what a task touching no test file "
        "records, so a reader has to guess between skipping and stamping."
    )


def test_split_hygiene_fix_is_deletion_only_and_derives_its_own_file_list() -> None:
    # The whole safety argument rests on these two: the fixer may only delete
    # the named bindings, and its file list is built from the violation lines
    # with no directory lines - not the task's own list (which cannot reach a
    # sibling module the style gate just created) and not the style gate's
    # widened one (which would let a deletion-only pass create modules).
    gate = (_SKILL_MD.parent / "references" / "style-gate.md").read_text()

    assert "**Three** lines differ from that shape, not two" in gate, (
        "references/style-gate.md no longer states that THREE lines differ "
        "from the Retry render. A reader trusting a 'two lines differ' "
        "headline keeps FILE_PATHS at the ivan-<task-id>-files.txt default "
        "and resurrects the unreachable-fixer bug."
    )

    assert (
        "Delete only the listed unused or shadowed bindings. Do not change any "
        "assertion, test function, fixture or parametrization. Do not add code."
    ) in gate, (
        "references/style-gate.md no longer carries the split-hygiene "
        "RETRY_INSTRUCTION verbatim; a paraphrase is what lets a fixer decide "
        "an assertion is dead weight."
    )
    assert "no widened allowlist here" in gate, (
        "references/style-gate.md dropped the rule that the split-hygiene fix "
        "gets no directory lines; routing it through the style-fix allowlist "
        "would let a deletion-only pass create modules."
    )
    assert "ivan-<task-id>-hygiene-files.txt" in gate, (
        "references/style-gate.md no longer builds the hygiene file list from "
        "the violation lines. Reusing the task's own ivan-<task-id>-files.txt "
        "dead-ends the fixer on a sibling test module the style gate just "
        "created, which is absent from the task's Contract paths."
    )


def test_both_records_enumerate_every_split_hygiene_value() -> None:
    attempt_logging = (
        _SKILL_MD.parent / "references" / "attempt-logging.md"
    ).read_text()
    schema = (
        _SKILL_MD.parent.parent / "run-autopilot" / "references" / "state-schema.md"
    ).read_text()

    # Assert the whole signature line, not the values one at a time: three of
    # the four already appear in attempt-logging.md via the style_gate row, so
    # a per-value substring check stays green even if split_hygiene's own
    # enumeration is deleted outright.
    assert (
        '"split_hygiene": "clean" | "fixed:<sha>" | "failed:<detail>" '
        '| "skipped:no-tests" | null'
    ) in attempt_logging, (
        "references/attempt-logging.md no longer carries the split_hygiene "
        "signature line; /work writes that field on the attempt, so a reader "
        "auditing the record cannot tell a clean check from one that never ran."
    )
    assert "split_hygiene" in schema, (
        "run-autopilot/references/state-schema.md omits split_hygiene from the "
        "tasks[].attempts signature, so the field /work writes is undeclared."
    )
    assert "skipped:no-tests" in schema, (
        "run-autopilot/references/state-schema.md declares split_hygiene "
        "without its no-tests value, the one a docs-only task records."
    )


def test_the_deslop_prompt_no_longer_asks_for_a_removal_it_forbids() -> None:
    # PRD 00166's other half: step 2 used to ask the agent to evaluate every
    # test added in the diff, and the rules then forbade acting on the answer.
    prompt = (_SKILL_MD.parent / "references" / "self-deslop-prompt.md").read_text()

    assert "docstring, or test" not in prompt, (
        "references/self-deslop-prompt.md step 2 still lists tests as removal "
        "candidates while its own rules forbid modifying them."
    )
    assert "Do not modify tests" in prompt, (
        "references/self-deslop-prompt.md dropped the ban on modifying tests; "
        "PRD 00166 keeps that ban and only removes the contradiction."
    )
    assert "check_split_hygiene" in prompt, (
        "references/self-deslop-prompt.md bans touching tests without naming "
        "what does handle test hygiene, so the finding travels to Pat instead."
    )


# --- Task-boundary handoff (step 6.5): honour the marker's own phase --------
#
# Both files currently treat ANY present `.handoff-requested` marker as an
# unconditional build-phase handoff: task-boundary-handoff.md step 3d always
# writes `--phase build` and always sets `next_phase: "build"`, so a
# review-phase soft-cap request gets misrouted into a build handoff. The fix
# makes the marker carry its own phase (a typed JSON contract, with a legacy
# plain-task-id form kept for back-compat) and makes both files route on
# whether that phase matches the session's current one.


def test_task_boundary_handoff_names_the_four_typed_json_fields() -> None:
    # The new marker format is JSON with four required fields. Pinned as
    # backtick-wrapped identifiers, matching how every other identifier in
    # this file (`.handoff-requested`, `state.tasks`, `next_phase`, ...) is
    # already rendered — a bare "phase" would collide with this file's own
    # "Phase 3" prose (run-autopilot's phase, not the marker's JSON field).
    text = (_SKILL_MD.parent / "references" / "task-boundary-handoff.md").read_text()

    for field in ("`phase`", "`session`", "`at`", "`task_id`"):
        assert field in text, (
            f"references/task-boundary-handoff.md never names the JSON "
            f"marker field {field} — the typed four-field contract (phase, "
            "session, at, task_id) is unstated, so nothing tells a reader "
            "what shape a valid marker has."
        )


def test_task_boundary_handoff_treats_a_nonempty_legacy_marker_as_a_build_request() -> (
    None
):
    # A plain (non-JSON) marker holding a task id is the pre-fix format. It
    # keeps meaning "hand off to build" — only the empty-marker and
    # JSON-marker cases gain phase awareness.
    text = (_SKILL_MD.parent / "references" / "task-boundary-handoff.md").read_text()
    gap = r"(?:(?!\b(?:not|never|neither|nor)\b)[^.])"

    nonempty_legacy_is_build = (
        re.compile(rf"non-empty{gap}{{0,120}}?legacy{gap}{{0,80}}?build", re.IGNORECASE),
        re.compile(rf"legacy{gap}{{0,120}}?non-empty{gap}{{0,80}}?build", re.IGNORECASE),
    )

    assert any(p.search(text) for p in nonempty_legacy_is_build), (
        "references/task-boundary-handoff.md never states that a non-empty "
        "legacy (plain, non-JSON) task-ID marker is treated as a build "
        "request."
    )


def test_task_boundary_handoff_treats_an_empty_legacy_marker_as_the_current_phase() -> (
    None
):
    # An empty legacy marker (the format the context-cap hook wrote before
    # this fix) must read as "the session's current phase", not a hardcoded
    # build — this is what lets a review-phase soft-cap request hand off
    # inside review instead of always landing in build.
    text = (_SKILL_MD.parent / "references" / "task-boundary-handoff.md").read_text()
    gap = r"(?:(?!\b(?:not|never|neither|nor)\b)[^.])"

    # (?<!non-) keeps this off the "non-empty" clause above — "non-empty"
    # contains "empty" as a substring, and that clause is about the OPPOSITE
    # case (always build, not the current phase).
    empty_legacy_is_current_phase = (
        re.compile(
            rf"(?<!non-)empty{gap}{{0,120}}?legacy{gap}{{0,80}}?current phase",
            re.IGNORECASE,
        ),
        re.compile(
            rf"legacy{gap}{{0,120}}?(?<!non-)empty{gap}{{0,80}}?current phase",
            re.IGNORECASE,
        ),
    )

    assert any(p.search(text) for p in empty_legacy_is_current_phase), (
        "references/task-boundary-handoff.md never states that an empty "
        "legacy marker is treated as the current phase — a bare 'empty "
        "marker' rule that does not say CURRENT PHASE still reads as "
        "hardcoded to build."
    )


def test_task_boundary_handoff_no_longer_assumes_every_handoff_is_mid_build() -> None:
    # The current step 3d justifies its unconditional `next_phase: "build"`
    # with "it already is during the build gate, since this is a mid-build
    # task-boundary handoff" — stated as a universal truth. Post-fix that is
    # false whenever the marker (or the session) is in review, so this exact
    # justification cannot survive the fix.
    text = (_SKILL_MD.parent / "references" / "task-boundary-handoff.md").read_text()
    phrase = "since this is a mid-build task-boundary handoff"

    assert phrase not in text, (
        f"references/task-boundary-handoff.md still contains {phrase!r} — "
        "this sentence asserts every task-boundary handoff is mid-build, "
        "which is exactly the bug: a review-phase handoff is not mid-build."
    )


def test_task_boundary_handoff_states_the_stale_marker_stderr_note() -> None:
    # Exact fixed prefix pinned by the task: a phase mismatch prints this
    # note (with the marker's own phase filled in) before removing both
    # markers and continuing as if none were present.
    text = (_SKILL_MD.parent / "references" / "task-boundary-handoff.md").read_text()
    needle = "autopilot: stale handoff marker from phase"

    assert needle in text, (
        f"references/task-boundary-handoff.md never contains the fixed "
        f"stderr prefix {needle!r} for a phase-mismatched marker."
    )


def test_task_boundary_handoff_gives_malformed_json_its_own_distinct_note() -> None:
    # JSON-looking but invalid marker text (bad shape, missing field, empty
    # task_id) is a different failure than a clean phase mismatch, and gets
    # its own wording so a reader can tell the two apart in a log.
    text = (_SKILL_MD.parent / "references" / "task-boundary-handoff.md").read_text()

    assert "malformed" in text.lower(), (
        "references/task-boundary-handoff.md never mentions a 'malformed' "
        "marker note. JSON-looking but invalid marker text (bad field "
        "shapes, an empty task_id) needs its own note, distinct from the "
        "phase-mismatch note."
    )


def test_task_boundary_handoff_removes_both_markers_and_continues_as_absent_on_mismatch() -> (
    None
):
    # A phase mismatch (or a malformed marker) must clean up BOTH marker
    # files and then behave exactly as if no marker had been present — not
    # partially clean up, and not still hand off on the stale phase.
    text = (_SKILL_MD.parent / "references" / "task-boundary-handoff.md").read_text()
    anchor = text.find("autopilot: stale handoff marker from phase")

    assert anchor != -1, (
        "references/task-boundary-handoff.md never states the stale-marker "
        "stderr note — see test_task_boundary_handoff_states_the_stale_"
        "marker_stderr_note; nothing to anchor the removal check to."
    )

    window = text[max(0, anchor - 200) : anchor + 600]

    for marker_file in (".handoff-requested", ".cap-fired"):
        assert marker_file in window, (
            f"references/task-boundary-handoff.md's phase-mismatch handling "
            f"never names {marker_file!r} — both markers must be removed, "
            "not just one."
        )

    assert re.search(r"as if|no marker|absent|return to step 1", window, re.IGNORECASE), (
        "references/task-boundary-handoff.md's phase-mismatch handling "
        "never says to continue exactly as if no marker had been present."
    )


def test_task_boundary_handoff_never_hands_off_on_an_unreadable_state_json() -> None:
    # An unreadable state.json leaves nothing to compare the marker's phase
    # against: no handoff, no invented phase, AND the markers stay in place
    # (this is not a mismatch — there is simply no state to judge them by).
    text = (_SKILL_MD.parent / "references" / "task-boundary-handoff.md").read_text()
    gap = r"(?:(?!\b(?:not|never|neither|nor)\b)[^.])"

    anchor = re.search(
        rf"state\.json{gap}{{0,60}}?(?:unreadable|cannot be read|can.t be read)"
        rf"|(?:unreadable|cannot be read|can.t be read){gap}{{0,60}}?state\.json",
        text,
        re.IGNORECASE,
    )
    assert anchor, (
        "references/task-boundary-handoff.md never describes what happens "
        "when `state.json` cannot be read — there is nothing to compare "
        "the marker's own phase against in that case."
    )

    window = text[max(0, anchor.start() - 60) : anchor.end() + 300]

    assert re.search(r"not\b[^.]{0,50}hand.?off|no\s+handoff", window, re.IGNORECASE), (
        "references/task-boundary-handoff.md's unreadable-state.json case "
        "never says NOT to hand off."
    )
    assert re.search(
        r"not\b[^.]{0,50}(?:invent|assume|guess)[^.]{0,20}phase",
        window,
        re.IGNORECASE,
    ), (
        "references/task-boundary-handoff.md's unreadable-state.json case "
        "never says NOT to invent or assume a phase."
    )
    assert re.search(r"not\b[^.]{0,60}remove", window, re.IGNORECASE), (
        "references/task-boundary-handoff.md's unreadable-state.json case "
        "never says the markers must NOT be removed."
    )


def test_task_boundary_handoff_keeps_review_as_the_target_for_a_valid_empty_marker_in_review() -> (
    None
):
    # The worked case the fix exists for: a valid legacy EMPTY marker seen
    # while the session is in review hands off to review, not build.
    text = (_SKILL_MD.parent / "references" / "task-boundary-handoff.md").read_text()
    gap = r"(?:(?!\b(?:not|never|neither|nor)\b)[^.])"

    review_stays_review = (
        re.compile(
            rf"review{gap}{{0,150}}?(?<!non-)empty{gap}{{0,100}}?legacy", re.IGNORECASE
        ),
        re.compile(
            rf"(?<!non-)empty{gap}{{0,150}}?legacy{gap}{{0,100}}?review", re.IGNORECASE
        ),
        re.compile(
            rf"legacy{gap}{{0,150}}?(?<!non-)empty{gap}{{0,100}}?review", re.IGNORECASE
        ),
    )

    assert any(p.search(text) for p in review_stays_review), (
        "references/task-boundary-handoff.md never states (or shows an "
        "example) that a valid legacy EMPTY marker seen during the review "
        "phase preserves review as the handoff target — this is the case "
        "the fix exists for."
    )


def test_step_6_5_trigger_summary_no_longer_names_an_unconditional_build_next_phase() -> (
    None
):
    # SKILL.md's step 6.5 trigger summary currently spells out
    # `next_phase: "build"` as part of the "Present" branch, unconditionally
    # — the same bug the reference procedure carries. A present marker now
    # routes on whether its own phase matches the session's, so this literal
    # cannot stay as an unconditional list item.
    start = _TEXT.index("### 6.5.")
    end = _TEXT.index("### 7.", start)
    section = _TEXT[start:end]
    phrase = 'next_phase: "build"'

    assert phrase not in section, (
        f"{_SKILL_MD}: step 6.5's trigger summary still contains {phrase!r} "
        "unconditionally — a present marker must route on whether its own "
        "phase matches the current session's phase, not always land on "
        "build."
    )
