"""Structure of the phase-delegation guard: the structural object-position
rule that decides a delegation without any verb list. Lookalike-text
normalization (compatibility forms, invisible format characters, combining
marks, the Unicode dash family) moved to
test_guard_phase_delegation_normalize.py (PRD 00271, task 14 - file size
limit).

Sibling of test_guard_phase_delegation.py (kept apart for the file size limit).

_CORPUS replays every case here through both entry points,
`is_phase_delegation` and `find_phase_delegation`.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parent


def _guard_module():
    sys.path.insert(0, str(HOOKS))
    return importlib.import_module("guard_phase_delegation")


def _params(cases: list[tuple]) -> list:
    """(value, ..., case id) tuples as pytest params: every case list below
    keeps its ids beside its values, never in a parallel list."""
    return [pytest.param(*case[:-1], id=case[-1]) for case in cases]


def _persona_input(prompt: str, subagent_type: str | None) -> dict:
    # subagent_type absent (not None) when a case names no persona: the
    # contract's default is "no type at all", not a null type.
    tool_input: dict = {"prompt": prompt}
    if subagent_type is not None:
        tool_input["subagent_type"] = subagent_type
    return tool_input


# --- Lookalike normalization ------------------------------------------------

# (prompt, case id). Each hides one code point of a normalized family inside a
# skill or phase name that the plain text would match.
_LOOKALIKE_DENIED = [
    ("Invoke /autopilot:plan\u2011tasks for PRD 00300.", "non-breaking-hyphen"),
    ("Invoke /autopilot:plan\u2212tasks for PRD 00300.", "minus-sign"),
    ("Run the wo\ufeffrk phase for PRD 00300.", "zero-width-no-break-space"),
    ("Run the wo\u2061rk phase for PRD 00300.", "function-application"),
    ("Run the wo\u180erk phase for PRD 00300.", "mongolian-vowel-separator"),
    ("Run the wo\u2066rk phase for PRD 00300.", "left-to-right-isolate"),
    ("Run the wo\u061crk phase for PRD 00300.", "arabic-letter-mark"),
    ("Run the w\u00f3rk phase for PRD 00300.", "precomposed-acute"),
    ("Run the wo\u0347rk phase for PRD 00300.", "combining-equals-below"),
    ("Run the wo\u0300rk phase for PRD 00300.", "combining-grave"),
    ("Run the wo\u0323rk phase for PRD 00300.", "combining-dot-below"),
    ("Run the w\uff4frk phase for PRD 00300.", "fullwidth-o"),
]


@pytest.mark.parametrize("prompt", _params(_LOOKALIKE_DENIED))
def test_lookalike_dashes_and_invisible_marks_are_normalized_and_denied(
    prompt: str,
) -> None:
    assert _guard_module().is_phase_delegation({"prompt": prompt}) is True


_DASH_DENIED = [
    ("Invoke /autopilot:plan\u301ctasks for PRD 00300.", "wave-dash"),
    ("Invoke /autopilot:plan\u05betasks for PRD 00300.", "hebrew-maqaf"),
    ("Invoke /autopilot:plan\u058atasks for PRD 00300.", "armenian-hyphen"),
    ("Invoke /autopilot:plan\u2e3atasks for PRD 00300.", "two-em-dash"),
    ("Invoke /autopilot:plan\u2015tasks for PRD 00300.", "horizontal-bar"),
]


@pytest.mark.parametrize("prompt", _params(_DASH_DENIED))
def test_a_dash_outside_the_common_block_is_normalized_and_denied(
    prompt: str,
) -> None:
    """Every Pd code point folds to "-", not only the U+2010-U+2015 block: a
    wave dash hides a skill name from the patterns just as well."""
    assert _guard_module().is_phase_delegation({"prompt": prompt}) is True


_LOOKALIKE_NO_PHASE = {"prompt": "Summarize the wo\ufeffrk you finished for PRD 00300."}
_PLAIN_PER_TASK = {
    "prompt": "Write the regression test for PRD 00300, report the count.",
}
_NO_PHASE_ALLOWED = [
    (_LOOKALIKE_NO_PHASE, "lookalike-but-no-phase-instruction"),
    (_PLAIN_PER_TASK, "plain-per-task-prompt"),
]


@pytest.mark.parametrize("tool_input", _params(_NO_PHASE_ALLOWED))
def test_per_task_dispatch_without_a_phase_instruction_is_allowed(
    tool_input: dict,
) -> None:
    """Normalization may not turn an ordinary per-task dispatch into a denial:
    cleaning the text is not itself grounds to deny."""
    assert _guard_module().is_phase_delegation(tool_input) is False


_DESCRIPTION_ONLY = {"description": "Run the wo\ufeffrk phase for PRD 00300."}
_LOOKALIKE_DESCRIPTION = {
    "prompt": "Tess, retry task 1.",
    "description": "Invoke /autopilot:plan\u2011tasks for PRD 00300.",
}
_DESCRIPTION_DENIED = [
    (_DESCRIPTION_ONLY, "description-only"),
    (_LOOKALIKE_DESCRIPTION, "clean-prompt-lookalike-description"),
]


@pytest.mark.parametrize("tool_input", _params(_DESCRIPTION_DENIED))
def test_lookalike_hidden_in_the_description_is_normalized_and_denied(
    tool_input: dict,
) -> None:
    assert _guard_module().is_phase_delegation(tool_input) is True


# A verb dangling at the end of the prompt and the phase name opening the
# description, then a negation ending the prompt with the delegation in the
# description: the pair pins the field boundary in both directions.
_DANGLING_VERB = {
    "prompt": "Tess, finish task 1 and then run the",
    "description": "work phase",
}
_NEGATION_THEN_DESCRIPTION = {
    "prompt": "Do not",
    "description": "run the work phase for PRD 7.",
}
_FIELD_BOUNDARY_CASES = [
    (_DANGLING_VERB, False, "verb-ends-the-prompt-phase-opens-the-description"),
    (_NEGATION_THEN_DESCRIPTION, True, "negation-in-the-other-field"),
]


@pytest.mark.parametrize(("tool_input", "expected"), _params(_FIELD_BOUNDARY_CASES))
def test_the_prompt_and_description_are_two_separate_fields(
    tool_input: dict, expected: bool
) -> None:
    """Each field is read on its own: a verb left dangling at the end of the
    prompt may not join the phase name that opens the description (a label
    there, with no word before it), and a negation in the prompt may not reach
    into the description to excuse a delegation sitting in it."""
    assert _guard_module().is_phase_delegation(tool_input) is expected


_LONG_LOOKALIKE = "Tess, task 1 of PRD 00300. " * 10 + "Run the wo\ufeffrk phase now."
_EARLIER_LINE = "Do not stop now\nRun the wo\ufeffrk phase for PRD 00300."
_LONG_DENIED = [
    (_LONG_LOOKALIKE, "lookalike-far-inside-a-long-prompt"),
    (_EARLIER_LINE, "negation-on-an-earlier-line"),
]


def test_lookalike_far_inside_a_long_prompt_is_normalized_and_denied() -> None:
    """Real dispatch prompts are hundreds of lines; a lookalike past the first
    line must be reduced too, so normalization cannot stop after a prefix."""
    assert len(_LONG_LOOKALIKE) > 200
    assert _guard_module().is_phase_delegation({"prompt": _LONG_LOOKALIKE}) is True


def test_negation_on_an_earlier_line_does_not_hide_a_later_delegation() -> None:
    """The newline between the lines is a sentence boundary for the negation
    window, so it must survive normalization intact."""
    assert _guard_module().is_phase_delegation({"prompt": _EARLIER_LINE}) is True


# --- Structural object-position rule (no verb list) -------------------------
# A phase name counts when it stands as the thing to run: either a strong
# anchor (`for`/`on` + PRD/task/number, `from task`, or a whole-run marker in
# the same sentence) or a weak anchor (the name ends its clause, with a word
# before it that is not a preposition). Nothing below depends on which verb
# introduces the phrase.

# The four phase spellings every generated matrix sweeps, covering the space,
# "-" and "_" separators the contract allows between the two words.
_PHASE_SPELLINGS = ("work phase", "plan-phase", "planning_phase", "design phase")


def _slug(text: str) -> str:
    return text.lower().replace(" ", "-").replace("_", "-")


# Verb x determiner x phase-name matrix, each anchored by "for PRD 00300".
# None of the four verbs appears in any verb list the guard ever shipped, so a
# surviving verb list - or a table of the sentences below - fails here.
_PACKET_MATRIX = [
    (
        f"{verb} {determiner} {phase} for PRD 00300.",
        f"{_slug(verb)}-{_slug(determiner)}-{_slug(phase)}",
    )
    for verb in ("Take over", "Shepherd", "Handle", "Drive")
    for determiner in ("the", "your", "the next")
    for phase in _PHASE_SPELLINGS
]

# (prompt, case id). Hoisted so each test function stays short.
_PACKET_PHRASINGS = [
    ("Run your work phase for PRD 00300 now.", "your"),
    ("Run our work phase for PRD 00300.", "our"),
    ("Run its work phase for PRD 00300.", "its"),
    ("Run the next work phase for PRD 00300.", "the-next"),
    ("Run all of the work phase for PRD 00300.", "all-of-the"),
    ("Kick off the work phase for PRD 00300 and finish every task.", "kick-off"),
    ("Begin the work phase for PRD 00300.", "begin"),
    ("Proceed with the work phase for PRD 00300.", "proceed-with"),
    ("Finish the work phase for PRD 00300.", "finish"),
    ("Go through the work phase for PRD 00300.", "go-through"),
    ("Carry out the work phase for PRD 00300.", "carry-out"),
    ("Run the work-phase for PRD 00300.", "hyphenated-phase"),
    ("Run the **work phase** for PRD 00300.", "emphasized-phase"),
    ("Run \u201c/autopilot:work\u201d now.", "curly-double-quotes"),
    ("Run \u00ab/autopilot:work\u00bb now.", "guillemets"),
    ("Run \u300c/autopilot:work\u300d now.", "corner-brackets"),
    ("Please start the entire work phase for PRD 00300 now.", "please-start-entire"),
    *_PACKET_MATRIX,
]


@pytest.mark.parametrize("prompt", _params(_PACKET_PHRASINGS))
def test_packet_three_phrasings_are_denied(prompt: str) -> None:
    """Every phrasing names the phase as the thing to run, anchored by "for
    PRD 00300" (or a whole-run marker), so the verdict may not depend on the
    introducing verb, the determiner, or the wrapper around the name."""
    assert _guard_module().is_phase_delegation({"prompt": prompt}) is True


_ANCHOR_FLIP_CASES = [
    ("Please take over the design phase for PRD 00300.", True, "strong-anchor"),
    ("Please take over the design phase doc", False, "compound-noun-head"),
]


@pytest.mark.parametrize(("prompt", "expected"), _params(_ANCHOR_FLIP_CASES))
def test_the_same_verb_phrase_flips_on_the_anchor_alone(
    prompt: str, expected: bool
) -> None:
    """One near-miss pair on the same words: with "for PRD 00300" the phase is
    the thing handed over; with a noun after it ("design phase doc") it is a
    document to touch. Only the anchor differs."""
    assert _guard_module().is_phase_delegation({"prompt": prompt}) is expected


_SLASH_PROMPTS = [
    (
        "/autopilot:work docs/dev/project-management/prds/wip/00300.md",
        "work-with-a-prd-path",
    ),
    ("/autopilot:plan-tasks 00300 task 3 only", "plan-tasks-with-one-task"),
]


@pytest.mark.parametrize("prompt", _params(_SLASH_PROMPTS))
def test_bare_slash_command_prompt_is_always_denied(prompt: str) -> None:
    """A prompt whose FIRST token is the slash command hands the phase over
    whatever scoping follows it, so neither a PRD path nor a single task id
    rescues it."""
    assert _guard_module().is_phase_delegation({"prompt": prompt}) is True


_SKILL_MD_PROMPTS = [
    (
        "Read /Users/bob/.claude/plugins/cache/buvis-plugins/autopilot/0.9.0"
        "/skills/work/SKILL.md and follow it for every task.",
        "installed-cache-path",
    ),
    (
        "Read ${CLAUDE_PLUGIN_ROOT}/skills/work/SKILL.md and execute its steps"
        " for PRD 00300.",
        "plugin-root-placeholder",
    ),
]


@pytest.mark.parametrize("prompt", _params(_SKILL_MD_PROMPTS))
def test_skill_md_read_via_any_path_prefix_is_denied(prompt: str) -> None:
    """The path prefix in front of `work/SKILL.md` is arbitrary: an absolute
    cache path and a `${CLAUDE_PLUGIN_ROOT}` placeholder both reach the same
    phase skill, and the follow-it instruction sits within 200 characters."""
    assert _guard_module().is_phase_delegation({"prompt": prompt}) is True


_EMPHATIC_NEGATION = [
    ("This is not optional: run the work phase for PRD 00300.", "not-optional-colon"),
    ("Do not stop - run the work phase for PRD 00300.", "do-not-stop-dash"),
    ("Don't stop: run the work phase.", "dont-stop-colon"),
]


@pytest.mark.parametrize("prompt", _params(_EMPHATIC_NEGATION))
def test_emphatic_negation_before_a_colon_or_dash_is_denied(prompt: str) -> None:
    """The negation belongs to an earlier clause ("not optional", "do not
    stop") and the colon or " - " closes that clause, so it cannot bind the
    phase name that follows: these are emphatic orders, not prohibitions."""
    assert _guard_module().is_phase_delegation({"prompt": prompt}) is True


_COMPOUND_COVER = [
    (
        "Start the work phase review of PRD 00300, then keep going through"
        " every task until done.",
        "review-head-with-keep-going",
    ),
    ("Work phase for PRD 00300: start it now.", "phase-first-then-order"),
]


@pytest.mark.parametrize("prompt", _params(_COMPOUND_COVER))
def test_compound_noun_cover_with_a_whole_run_marker_is_denied(prompt: str) -> None:
    """A compound-noun head ("work phase review") reads as a thing, not an
    order - but a whole-run marker in the same sentence ("keep going", "every
    task", "until done") or a strong "for PRD" anchor overrides that cover."""
    assert _guard_module().is_phase_delegation({"prompt": prompt}) is True


_NO_SCOPE_PROMPTS = [
    ("Run the work phase for PRD 7 from task 2 onward.", "task-range-onward"),
    ("Run the work phase for PRD 7, tasks 1 and 2.", "two-task-ids"),
    (
        "Run the work phase for docs/dev/project-management/prds/wip/00300.md.",
        "prd-path",
    ),
    ("Run the work phase for PRD 7; use only the repo tools.", "free-only"),
]


@pytest.mark.parametrize("prompt", _params(_NO_SCOPE_PROMPTS))
def test_task_ranges_prd_paths_and_a_free_only_do_not_scope(prompt: str) -> None:
    """Only exactly one distinct task id, or one distinct non-PRD file path,
    narrows a dispatch. A range ("from task 2 onward"), two ids, a path under
    `prds/`, and a bare "only" all leave the whole phase delegated."""
    assert _guard_module().is_phase_delegation({"prompt": prompt}) is True


# One carrier sentence, one varying suffix: the scoping count is the only
# difference between a denial and an allow, so nothing short of counting the
# task ids and the paths in the field decides this matrix.
_CARRIER = "Make the hook run the work phase"
_SCOPE_MATRIX = [
    (f"{_CARRIER}.", True, "no-task-id-and-no-path"),
    (f"{_CARRIER}, task 3.", False, "one-task-id"),
    (f"{_CARRIER}, tasks 1 and 2.", True, "two-task-ids"),
    (f"{_CARRIER}, from task 2 onward.", True, "one-task-id-in-a-range"),
    (f"{_CARRIER}, then update hooks/guard.py.", False, "one-plain-path"),
    (
        f"{_CARRIER}, then update hooks/guard.py and hooks/other.py.",
        True,
        "two-plain-paths",
    ),
    (
        f"{_CARRIER}, see docs/dev/project-management/prds/wip/00300.md.",
        True,
        "one-path-under-prds",
    ),
    (f"{_CARRIER}, use only the repo tools.", True, "one-free-only"),
]


@pytest.mark.parametrize(("prompt", "expected"), _params(_SCOPE_MATRIX))
def test_exactly_one_task_id_or_one_plain_path_scopes_the_same_carrier(
    prompt: str, expected: bool
) -> None:
    """Same sentence throughout; only the scoping suffix moves. One task id or
    one plain path narrows it to a single job, while none, two of either, a
    range form, a `prds/` path and a free "only" leave the phase delegated."""
    assert _guard_module().is_phase_delegation({"prompt": prompt}) is expected


_QUOTED_PROMPTS = [
    ('"Run the work phase for PRD 7."', "whole-sentence-quoted"),
    ('Insert the line "Invoke `/autopilot:work` skill."', "quoted-phrase-to-edit"),
]


@pytest.mark.parametrize("prompt", _params(_QUOTED_PROMPTS))
def test_quoted_text_is_still_checked(prompt: str) -> None:
    """Quotes get no exemption outside the per-task personas: a general-purpose
    dispatch can hand a phase over just as well inside quotation marks."""
    tool_input = {"prompt": prompt, "subagent_type": "general-purpose"}
    assert _guard_module().is_phase_delegation(tool_input) is True


# Two allowed carriers swept over every phase spelling: an allow-list of exact
# sentences cannot cover them, and each sits one word from a denial ("run the
# work phase" and "the work phase review" both appear inside them).
_IVAN_CARRIERS = (
    ("Explain why we run the {phase} in this repo.", "explain-why-we-run"),
    ("Add a row to the {phase} review table in docs/x.md.", "review-table-row"),
)

_IVAN_ALLOWED = [
    (
        "Complete the planning phase notes in"
        " docs/dev/project-management/plans/00300.md; task 3 only.",
        "plan-notes-one-task",
    ),
    ("Call the plan-tasks helper script with --dry-run", "plan-tasks-helper-script"),
    ("Do design-solution/references/x.md first", "design-solution-reference-path"),
    ("Do the work phase tests pass on this branch?", "question-about-the-tests"),
    ("Do the work phase handoff test", "handoff-test"),
    ("Call the work phase helper", "phase-helper"),
    ("Start the design phase doc review", "doc-review"),
    ("Launch the work phase timer test", "timer-test"),
    (
        "Quote this line verbatim: ...every `task-add` call"
        " `/autopilot:plan-tasks` made...",
        "quoted-skill-prose",
    ),
    *[
        (carrier.format(phase=phase), f"{carrier_id}-{_slug(phase)}")
        for carrier, carrier_id in _IVAN_CARRIERS
        for phase in _PHASE_SPELLINGS
    ],
]


@pytest.mark.parametrize("prompt", _params(_IVAN_ALLOWED))
def test_per_task_prompts_that_mention_a_phase_are_allowed(prompt: str) -> None:
    """Real per-task work names phase jargon constantly: as a noun modifier
    ("work phase tests"), inside a path, in a question, quoted as prose to
    edit, or as the subject of an explanation ("why we run the work phase in
    this repo"). None of them puts the phase in object position of an order."""
    tool_input = {"prompt": prompt, "subagent_type": "autopilot:ivan"}
    assert _guard_module().is_phase_delegation(tool_input) is False


_SCOPED_ALLOWED = [
    ("Update hooks/guard.py so it can run the work phase.", "one-file-scopes"),
    ("For task 3, make the hook run the work phase.", "one-task-id-scopes"),
]


@pytest.mark.parametrize("prompt", _params(_SCOPED_ALLOWED))
def test_one_named_task_or_file_scopes_a_phase_mention(prompt: str) -> None:
    """Exactly one distinct task id, or one distinct path that is neither
    under `prds/` nor a SKILL.md, narrows the dispatch to a single job even
    though the phase name ends its clause."""
    assert _guard_module().is_phase_delegation({"prompt": prompt}) is False


_PREPOSITIONAL_ALLOWED = [
    ("Tasks complete in the work phase", "trailing-in-the"),
    ("In the work phase: do not skip tests", "leading-in-the"),
    ("Decide what to do about the work phase", "about-the"),
    ("Decide what to do about /autopilot:plan-tasks", "about-a-slash-command"),
    ("Update the (work phase) docs", "parenthesised-modifier-docs"),
    ("Do the (work phase) tests", "parenthesised-modifier-tests"),
    ("Work phase: complete", "phase-as-a-label"),
    ("Did you run the work phase?", "question"),
]


@pytest.mark.parametrize("prompt", _params(_PREPOSITIONAL_ALLOWED))
def test_prepositional_and_question_mentions_are_allowed(prompt: str) -> None:
    """The weak anchor needs a non-preposition word before the phase name, so
    "in the work phase" and "about the work phase" stay prose - the skill form
    included, which the bare form may not shadow from inside; and a phase name
    in brackets ("the (work phase) docs") is still a noun modifier, since the
    close bracket belongs to the name, not to the end of the clause. A clause
    with no word before the name is a label, and a clause ending in "?" is a
    question, not an order."""
    assert _guard_module().is_phase_delegation({"prompt": prompt}) is False


# (prompt, subagent_type or None for "key absent", expected, case id). The
# middle block holds one sentence fixed while only the persona moves, so the
# verdict cannot be reached without reading subagent_type.
_QUOTED_SKILL_PROSE = (
    'Insert one sentence before the line "Invoke `/autopilot:work` skill.'
    ' It runs until all tasks complete."'
)
_PERSONA_CASES = [
    (_QUOTED_SKILL_PROSE, "autopilot:worker-opus", False, "quoted-prose-to-edit"),
    ('Run "/autopilot:work" for PRD 7.', "autopilot:worker-opus", True, "for-prd-7"),
    ("Run the work phase.", "autopilot:worker-opus", False, "weak-anchor-worker-opus"),
    ("Run the work phase.", "autopilot:ivan", False, "weak-anchor-ivan"),
    ("Run the work phase.", "general-purpose", True, "weak-anchor-general-purpose"),
    ("Run the work phase.", None, True, "weak-anchor-no-persona"),
    (
        "Run the work phase for PRD 00300.",
        "autopilot:blake",
        False,
        "read-only-reviewer-never-delegates",
    ),
]


@pytest.mark.parametrize(
    ("prompt", "subagent_type", "expected"), _params(_PERSONA_CASES)
)
def test_per_task_personas_count_only_the_strong_anchor(
    prompt: str, subagent_type: str | None, expected: bool
) -> None:
    """A worker persona's prompt quotes skill prose as an edit target, so the
    weak anchor never fires for it - not even for the bare order "Run the work
    phase.", which the same sentence turns into a denial under general-purpose
    or under no persona at all. The strong "for PRD 7" anchor still denies a
    worker, and a read-only reviewer is exempt even from that."""
    tool_input = _persona_input(prompt, subagent_type)
    assert _guard_module().is_phase_delegation(tool_input) is expected


# The verdict is invariant under the PRD number and a trailing adverb (a
# prohibition is a prohibition for PRD 7, PRD 9 and PRD 00300 alike), and the
# four-word window is pinned at its edge: four words between the negation and
# the phase name still allow, five no longer do.
_NEGATION_CASES = [
    ("Do not run the work phase for PRD 7.", False, "same-clause-negation"),
    (
        "Never fail to report; do not run the work phase.",
        False,
        "double-negation-scoped-to-an-earlier-clause",
    ),
    ("Code review isn't only running the work phase", False, "isnt-only-is-a-state"),
    (
        "Do not wait for me. Run the work phase for PRD 7.",
        True,
        "negation-in-an-earlier-sentence",
    ),
    (
        "Do not, under any circumstances, run the work phase.",
        True,
        "negation-five-words-away-across-commas",
    ),
    ("Do not run the work phase for PRD 9.", False, "same-clause-negation-prd-9"),
    ("Do not run the work phase for PRD 00300.", False, "same-clause-prd-00300"),
    ("Do not run the work phase for PRD 7 today.", False, "same-clause-adverb"),
    (
        "Do not wait for me. Run the work phase for PRD 9.",
        True,
        "earlier-sentence-prd-9",
    ),
    ("Do not run the whole remaining work phase.", False, "four-word-window"),
    ("Do not run the whole entire remaining work phase.", True, "five-word-window"),
]


@pytest.mark.parametrize(("prompt", "expected"), _params(_NEGATION_CASES))
def test_a_negation_binds_only_inside_its_clause(prompt: str, expected: bool) -> None:
    """A negation allows the dispatch only from inside the same clause, within
    four words of the phase name: an earlier sentence, or four commas and five
    words of hedging, leaves the order standing. Which PRD it names, and an
    adverb after the number, change nothing."""
    assert _guard_module().is_phase_delegation({"prompt": prompt}) is expected


def test_negation_does_not_reach_past_and_then_but() -> None:
    """A negation of an UNRELATED verb ("don't stop", "never pause", "do not
    wait") joined to the real order by "and" must not excuse that order:
    "and" starts a new clause just as a comma does, so the negation binds
    only "stop"/"pause"/"wait", never the order that follows it."""
    for prompt in (
        "Don't stop and run the work phase for PRD 00300.",
        "Never pause and run /autopilot:work for PRD 00300 end to end.",
        "Do not wait and run plan-tasks for PRD 00300 for every task.",
    ):
        assert _guard_module().is_phase_delegation({"prompt": prompt}) is True
    # Control: the same negation with a comma instead of "and" already denies
    # today, so this test isolates the conjunction, not the negation verb.
    assert (
        _guard_module().is_phase_delegation(
            {"prompt": "Don't stop, run the work phase for PRD 00300."}
        )
        is True
    )


@pytest.mark.parametrize("conjunction", ["and", "then", "but"])
def test_negation_does_not_reach_past_the_bare_conjunction(conjunction: str) -> None:
    """PRD 00324 finding: the test above names "and"/"then"/"but" but only
    ever exercises "and" - its "then"/"but" controls elsewhere all carry a
    comma that already stops negation on its own, so the conjunction itself
    was never isolated. This payload has no comma: the conjunction alone
    must start the new clause."""
    prompt = f"Don't stop {conjunction} run the work phase for PRD 00300."
    assert _guard_module().is_phase_delegation({"prompt": prompt}) is True


@pytest.mark.parametrize("emoticon", [";(", ";)", "=)", "=("])
def test_emoticon_variants_beyond_colon_are_not_brackets(emoticon: str) -> None:
    """PRD 00324 finding: only ":(" / ":)" were tested, but `_EMOTICON`
    also covers ";" and "=" mouths - neither paren of those is a bracket."""
    text = f"ok {emoticon} done"
    pos = text.index(emoticon[1])
    assert _guard_module()._emoticon_paren(text, pos) is True


def test_single_backtick_inside_a_doubled_backtick_span_is_literal() -> None:
    """PRD 00324 finding: backticks pair by RUN LENGTH - a doubled run
    ("``...``") is one token, and a single backtick inside it is literal,
    never a fresh opener of its own pair."""
    pairs, literal_runs = _guard_module()._nested_run_pairs("``a`b``")
    assert pairs == [(0, 5)]
    assert literal_runs == [(0, 5)]


def test_bracket_opener_defers_while_a_quote_run_is_open() -> None:
    """PRD 00324 finding: a bracket opener encountered while a quote run is
    already open is a literal character of that run, never a fresh opener
    of its own - so it never reaches `pairs`, and the LATER unrelated
    closer it would otherwise have paired with is left alone too."""
    pairs, literal_runs = _guard_module()._nested_run_pairs('"a(b" c)')
    assert pairs == [(0, 4)]
    assert literal_runs == [(0, 4)]


def test_nested_bracket_chain_selects_the_innermost_pair() -> None:
    """PRD 00324 finding: nested brackets form a chain, and the span-merge
    walk must pick the INNERMOST enclosing pair around a candidate - it
    alone decides `_cited`'s sentence-window test."""
    runs = _guard_module()._quoted_runs("(a[b]c)", [(3, 4, False)])
    assert runs[(3, 4)] == [(2, 4)]


# --- The two entry points must agree, case for case ------------------------
# Every predicate case above, replayed through `is_phase_delegation` and
# `find_phase_delegation`.


def _corpus_group(
    prefix: str,
    cases: list[tuple],
    expected: bool | None = None,
    subagent_type: str | None = None,
) -> list[tuple[dict, bool, str]]:
    """Case list -> (tool_input, expected verdict, globally unique case id). A
    case is (value, id) when the whole list shares one verdict and (value,
    verdict, id) otherwise; `value` is a prompt or a whole tool_input."""
    entries = []
    for case in cases:
        value = case[0]
        verdict = expected if expected is not None else case[-2]
        tool_input = dict(value) if isinstance(value, dict) else {"prompt": value}
        if subagent_type:
            tool_input["subagent_type"] = subagent_type
        entries.append((tool_input, verdict, f"{prefix}-{case[-1]}"))
    return entries


_CORPUS = [
    *_corpus_group("lookalike", _LOOKALIKE_DENIED, True),
    *_corpus_group("dash", _DASH_DENIED, True),
    *_corpus_group("packet", _PACKET_PHRASINGS, True),
    *_corpus_group("slash", _SLASH_PROMPTS, True),
    *_corpus_group("skill-md", _SKILL_MD_PROMPTS, True),
    *_corpus_group("emphatic", _EMPHATIC_NEGATION, True),
    *_corpus_group("compound", _COMPOUND_COVER, True),
    *_corpus_group("unscoped", _NO_SCOPE_PROMPTS, True),
    *_corpus_group("long", _LONG_DENIED, True),
    *_corpus_group("description", _DESCRIPTION_DENIED, True),
    *_corpus_group("quoted", _QUOTED_PROMPTS, True, "general-purpose"),
    *_corpus_group("scoped", _SCOPED_ALLOWED, False),
    *_corpus_group("prepositional", _PREPOSITIONAL_ALLOWED, False),
    *_corpus_group("no-phase", _NO_PHASE_ALLOWED, False),
    *_corpus_group("ivan", _IVAN_ALLOWED, False, "autopilot:ivan"),
    *_corpus_group("negation", _NEGATION_CASES),
    *_corpus_group("scope-count", _SCOPE_MATRIX),
    *_corpus_group("anchor-flip", _ANCHOR_FLIP_CASES),
    *_corpus_group("fields", _FIELD_BOUNDARY_CASES),
    *[
        (_persona_input(prompt, agent), expected, f"persona-{case_id}")
        for prompt, agent, expected, case_id in _PERSONA_CASES
    ],
]


def _normalized_fields(guard, tool_input: dict) -> str:
    """Both fields, normalized and whitespace-collapsed, as the span is."""
    return " ".join(
        " ".join(guard._normalize(value).split())
        for value in (tool_input.get("prompt"), tool_input.get("description"))
        if isinstance(value, str)
    )


@pytest.mark.parametrize(("tool_input", "expected"), _params(_CORPUS))
def test_the_quoted_span_is_present_exactly_when_the_call_is_denied(
    tool_input: dict, expected: bool
) -> None:
    """`find_phase_delegation` is the reason behind the verdict, so the two can
    never disagree: a span for every denial, None for every allow, and the span
    has to be text that occurs in the normalized input, not a canned phrase."""
    guard = _guard_module()
    span = guard.find_phase_delegation(tool_input)
    assert guard.is_phase_delegation(tool_input) is expected
    assert (span is not None) is expected
    if expected:
        assert span
        assert span in _normalized_fields(guard, tool_input)


@pytest.mark.parametrize(
    "tool_input",
    [
        {},
        {"prompt": ""},
        {"prompt": None, "description": None},
        {"prompt": "Write the regression test for PRD 00300, report the count."},
    ],
    ids=["empty-dict", "empty-prompt", "both-none", "per-task-prompt"],
)
def test_no_span_is_quoted_when_nothing_is_delegated(tool_input: dict) -> None:
    """Nothing to quote means None, the empty payload included."""
    assert _guard_module().find_phase_delegation(tool_input) is None
