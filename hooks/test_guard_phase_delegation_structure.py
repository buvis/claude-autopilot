"""Structure of the phase-delegation guard: lookalike-text normalization in
front of it (compatibility forms, invisible format characters, combining marks
and the Unicode dash family reduced to plain text before any matching), then
the structural object-position rule that decides a delegation without any verb
list.

Sibling of test_guard_phase_delegation.py (kept apart for the file size limit).
Every lookalike code point is written as an escaped literal, never pasted: the
characters are invisible or combining and an editor would silently destroy them.
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


@pytest.mark.parametrize(
    "prompt",
    [
        "Invoke /autopilot:plan\u2011tasks for PRD 00300.",
        "Invoke /autopilot:plan\u2212tasks for PRD 00300.",
        "Run the wo\ufeffrk phase for PRD 00300.",
        "Run the wo\u2061rk phase for PRD 00300.",
        "Run the wo\u180erk phase for PRD 00300.",
        "Run the w\u00f3rk phase for PRD 00300.",
        "Run the wo\u0347rk phase for PRD 00300.",
    ],
    ids=[
        "non-breaking-hyphen",
        "minus-sign",
        "zero-width-no-break-space",
        "function-application",
        "mongolian-vowel-separator",
        "precomposed-acute",
        "combining-equals-below",
    ],
)
def test_lookalike_dashes_and_invisible_marks_are_normalized_and_denied(
    prompt: str,
) -> None:
    assert _guard_module().is_phase_delegation({"prompt": prompt}) is True


@pytest.mark.parametrize(
    "prompt",
    [
        "Invoke /autopilot:plan\u301ctasks for PRD 00300.",
        "Invoke /autopilot:plan\u05betasks for PRD 00300.",
    ],
    ids=["wave-dash", "hebrew-maqaf"],
)
def test_a_dash_outside_the_common_block_is_normalized_and_denied(
    prompt: str,
) -> None:
    """Every Pd code point folds to "-", not only the U+2010-U+2015 block: a
    wave dash hides a skill name from the patterns just as well."""
    assert _guard_module().is_phase_delegation({"prompt": prompt}) is True


@pytest.mark.parametrize(
    "tool_input",
    [
        {"prompt": "Summarize the wo\ufeffrk you finished for PRD 00300."},
        {"prompt": "Write the regression test for PRD 00300, report the count."},
    ],
    ids=["lookalike-but-no-phase-instruction", "plain-per-task-prompt"],
)
def test_per_task_dispatch_without_a_phase_instruction_is_allowed(
    tool_input: dict,
) -> None:
    """Normalization may not turn an ordinary per-task dispatch into a denial:
    cleaning the text is not itself grounds to deny."""
    assert _guard_module().is_phase_delegation(tool_input) is False


@pytest.mark.parametrize(
    "tool_input",
    [
        {"description": "Run the wo\ufeffrk phase for PRD 00300."},
        {
            "prompt": "Tess, retry task 1.",
            "description": "Invoke /autopilot:plan\u2011tasks for PRD 00300.",
        },
    ],
    ids=["description-only", "clean-prompt-lookalike-description"],
)
def test_lookalike_hidden_in_the_description_is_normalized_and_denied(
    tool_input: dict,
) -> None:
    assert _guard_module().is_phase_delegation(tool_input) is True


def test_lookalike_far_inside_a_long_prompt_is_normalized_and_denied() -> None:
    """Real dispatch prompts are hundreds of lines; a lookalike past the first
    line must be reduced too, so normalization cannot stop after a prefix."""
    prompt = "Tess, task 1 of PRD 00300. " * 10 + "Run the wo\ufeffrk phase now."
    assert len(prompt) > 200
    assert _guard_module().is_phase_delegation({"prompt": prompt}) is True


def test_negation_on_an_earlier_line_does_not_hide_a_later_delegation() -> None:
    """The newline between the lines is a sentence boundary for the negation
    window, so it must survive normalization intact."""
    prompt = "Do not stop now\nRun the wo\ufeffrk phase for PRD 00300."
    assert _guard_module().is_phase_delegation({"prompt": prompt}) is True


# (raw, expected plain form, case id). Each case is also asserted inside a
# carrier phrase and re-normalized, so a lookup table keyed on these exact
# strings cannot stand in for the rule.
_LOOKALIKE_CASES = [
    ("plan\u2011tasks", "plan-tasks", "non-breaking-hyphen"),
    ("plan\u2212tasks", "plan-tasks", "minus-sign"),
    ("plan\u2014tasks", "plan-tasks", "em-dash"),
    ("plan\u2010tasks", "plan-tasks", "hyphen"),
    ("plan\u2013tasks", "plan-tasks", "en-dash"),
    # Pd code points outside the U+2010-U+2015 block, neither folded by NFKD:
    # the contract names the whole Pd category, so folding a literal dash
    # range is not enough.
    ("plan\u301ctasks", "plan-tasks", "wave-dash"),
    ("plan\u05betasks", "plan-tasks", "hebrew-maqaf"),
    ("wo\ufeffrk", "work", "zero-width-no-break-space"),
    ("wo\u2061rk", "work", "function-application"),
    ("wo\u180erk", "work", "mongolian-vowel-separator"),
    ("wo\u200brk", "work", "zero-width-space"),
    ("wo\u200crk", "work", "zero-width-non-joiner"),
    ("wo\u200drk", "work", "zero-width-joiner"),
    ("wo\u2060rk", "work", "word-joiner"),
    ("wo\u00adrk", "work", "soft-hyphen"),
    ("w\u00f3rk", "work", "precomposed-acute"),
    ("wo\u0301rk", "work", "decomposed-acute"),
    ("wo\u0347rk", "work", "combining-equals-below"),
    ("\uff57ork", "work", "fullwidth-letter"),
    ("don\u2018t", "don't", "left-curly-quote"),
    ("don\u2019t", "don't", "right-curly-quote"),
    ("**work**", "work", "emphasis-markers"),
    ("*work*", "work", "single-emphasis-markers"),
    ("**the work phase**", "the work phase", "emphasis-around-a-phrase"),
    ("Run the **work** phase", "Run the work phase", "emphasis-markers-mid-string"),
]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(raw, expected) for raw, expected, _ in _LOOKALIKE_CASES],
    ids=[case_id for _, _, case_id in _LOOKALIKE_CASES],
)
def test_normalize_reduces_lookalike_text_to_its_plain_form(
    raw: str,
    expected: str,
) -> None:
    normalize = _guard_module()._normalize
    assert normalize(raw) == expected
    assert normalize(f"the {raw} helper") == f"the {expected} helper"
    assert normalize(expected) == expected


@pytest.mark.parametrize(
    "letter",
    ["\u0430", "\u0435", "\u0440", "\u0441", "\u043e", "\u03bf"],
    ids=[
        "cyrillic-a",
        "cyrillic-ie",
        "cyrillic-er",
        "cyrillic-es",
        "cyrillic-o",
        "greek-omicron",
    ],
)
def test_normalize_leaves_homoglyph_letters_alone(letter: str) -> None:
    """Homoglyphs are out of scope: a Cyrillic "o" is a different letter, not a
    compatibility form, so normalization must not fold it into an ASCII "o"."""
    assert _guard_module()._normalize(f"pre{letter}post") == f"pre{letter}post"


def test_normalize_leaves_plain_ascii_text_untouched() -> None:
    assert _guard_module()._normalize("Run the work phase for PRD 00300.") == (
        "Run the work phase for PRD 00300."
    )


def test_normalize_keeps_text_outside_the_normalized_families() -> None:
    """Only the contract's families change: accents (Mn) are dropped and every
    asterisk goes, while other non-ASCII letters survive untouched."""
    assert _guard_module()._normalize("Tom\u00e1\u0161 2**8 *args \u65e5\u672c") == (
        "Tomas 28 args \u65e5\u672c"
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            "\ud55c\uae00 run the work phase",
            "\ud55c\uae00 run the work phase",
        ),
        ("\u1112\u1161\u11ab\u1100\u1173\u11af", "\ud55c\uae00"),
        ("5 \u212b of travel", "5 A of travel"),
    ],
    ids=["hangul-syllables", "hangul-jamo", "angstrom-sign"],
)
def test_normalize_returns_composed_text(raw: str, expected: str) -> None:
    """The plain form is COMPOSED, so the character count a caller sees is the
    one it would read in the source text: _negated_before measures its window
    in characters, and text left split into jamo inflates that count and moves
    the window. A compatibility sign still lands on its plain ASCII letter."""
    assert _guard_module()._normalize(raw) == expected


def test_normalize_leaves_whitespace_unchanged() -> None:
    """Nothing in the contract collapses whitespace: the newline between prompt
    and description, and every newline inside a prompt, must stay put."""
    assert _guard_module()._normalize("a\n\nb\tc  d") == "a\n\nb\tc  d"


# --- Structural object-position rule (no verb list) -------------------------
# A phase name counts when it stands as the thing to run: either a strong
# anchor (`for`/`on` + PRD/task/number, `from task`, or a whole-run marker in
# the same sentence) or a weak anchor (the name ends its clause, with a word
# before it that is not a preposition). Nothing below depends on which verb
# introduces the phrase.

# (prompt, case id). Hoisted so each test function stays short.
_PACKET_PHRASINGS = [
    ("Run your work phase for PRD 00300 now.", "your"),
    ("Run our work phase for PRD 00300.", "our"),
    ("Run its work phase for PRD 00300.", "its"),
    ("Run the next work phase for PRD 00300.", "the-next"),
    ("Run all of the work phase for PRD 00300.", "all-of-the"),
    (
        "Kick off the work phase for PRD 00300 and finish every task.",
        "kick-off",
    ),
    ("Begin the work phase for PRD 00300.", "begin"),
    ("Proceed with the work phase for PRD 00300.", "proceed-with"),
    ("Finish the work phase for PRD 00300.", "finish"),
    ("Go through the work phase for PRD 00300.", "go-through"),
    ("Carry out the work phase for PRD 00300.", "carry-out"),
    ("Run the work-phase for PRD 00300.", "hyphenated-phase"),
    ("Run the **work phase** for PRD 00300.", "emphasized-phase"),
    ("Run “/autopilot:work” now.", "curly-double-quotes"),
    ("Run «/autopilot:work» now.", "guillemets"),
    ("Run 「/autopilot:work」 now.", "corner-brackets"),
    (
        "Please start the entire work phase for PRD 00300 now.",
        "please-start-entire",
    ),
]


@pytest.mark.parametrize(
    "prompt",
    [prompt for prompt, _ in _PACKET_PHRASINGS],
    ids=[case_id for _, case_id in _PACKET_PHRASINGS],
)
def test_packet_three_phrasings_are_denied(prompt: str) -> None:
    """Every phrasing names the phase as the thing to run, anchored by "for
    PRD 00300" (or a whole-run marker), so the verdict may not depend on the
    introducing verb, the determiner, or the wrapper around the name."""
    assert _guard_module().is_phase_delegation({"prompt": prompt}) is True


@pytest.mark.parametrize(
    "prompt",
    [
        "/autopilot:work docs/dev/project-management/prds/wip/00300.md",
        "/autopilot:plan-tasks 00300 task 3 only",
    ],
    ids=["work-with-a-prd-path", "plan-tasks-with-one-task"],
)
def test_bare_slash_command_prompt_is_always_denied(prompt: str) -> None:
    """A prompt whose FIRST token is the slash command hands the phase over
    whatever scoping follows it, so neither a PRD path nor a single task id
    rescues it."""
    assert _guard_module().is_phase_delegation({"prompt": prompt}) is True


@pytest.mark.parametrize(
    "prompt",
    [
        "Read /Users/bob/.claude/plugins/cache/buvis-plugins/autopilot/0.9.0"
        "/skills/work/SKILL.md and follow it for every task.",
        "Read ${CLAUDE_PLUGIN_ROOT}/skills/work/SKILL.md and execute its steps"
        " for PRD 00300.",
    ],
    ids=["installed-cache-path", "plugin-root-placeholder"],
)
def test_skill_md_read_via_any_path_prefix_is_denied(prompt: str) -> None:
    """The path prefix in front of `work/SKILL.md` is arbitrary: an absolute
    cache path and a `${CLAUDE_PLUGIN_ROOT}` placeholder both reach the same
    phase skill, and the follow-it instruction sits within 200 characters."""
    assert _guard_module().is_phase_delegation({"prompt": prompt}) is True


@pytest.mark.parametrize(
    "prompt",
    [
        "This is not optional: run the work phase for PRD 00300.",
        "Do not stop - run the work phase for PRD 00300.",
        "Don't stop: run the work phase.",
    ],
    ids=["not-optional-colon", "do-not-stop-dash", "dont-stop-colon"],
)
def test_emphatic_negation_before_a_colon_or_dash_is_denied(prompt: str) -> None:
    """The negation belongs to an earlier clause ("not optional", "do not
    stop") and the colon or " - " closes that clause, so it cannot bind the
    phase name that follows: these are emphatic orders, not prohibitions."""
    assert _guard_module().is_phase_delegation({"prompt": prompt}) is True


@pytest.mark.parametrize(
    "prompt",
    [
        "Start the work phase review of PRD 00300, then keep going through"
        " every task until done.",
        "Work phase for PRD 00300: start it now.",
    ],
    ids=["review-head-with-keep-going", "phase-first-then-order"],
)
def test_compound_noun_cover_with_a_whole_run_marker_is_denied(prompt: str) -> None:
    """A compound-noun head ("work phase review") reads as a thing, not an
    order - but a whole-run marker in the same sentence ("keep going", "every
    task", "until done") or a strong "for PRD" anchor overrides that cover."""
    assert _guard_module().is_phase_delegation({"prompt": prompt}) is True


@pytest.mark.parametrize(
    "prompt",
    [
        "Run the work phase for PRD 7 from task 2 onward.",
        "Run the work phase for PRD 7, tasks 1 and 2.",
        "Run the work phase for docs/dev/project-management/prds/wip/00300.md.",
        "Run the work phase for PRD 7; use only the repo tools.",
    ],
    ids=["task-range-onward", "two-task-ids", "prd-path", "free-only"],
)
def test_task_ranges_prd_paths_and_a_free_only_do_not_scope(prompt: str) -> None:
    """Only exactly one distinct task id, or one distinct non-PRD file path,
    narrows a dispatch. A range ("from task 2 onward"), two ids, a path under
    `prds/`, and a bare "only" all leave the whole phase delegated."""
    assert _guard_module().is_phase_delegation({"prompt": prompt}) is True


@pytest.mark.parametrize(
    "prompt",
    [
        '"Run the work phase for PRD 7."',
        'Insert the line "Invoke `/autopilot:work` skill."',
    ],
    ids=["whole-sentence-quoted", "quoted-phrase-as-an-edit-target"],
)
def test_quoted_text_is_still_checked(prompt: str) -> None:
    """Quotes get no exemption outside the per-task personas: a general-purpose
    dispatch can hand a phase over just as well inside quotation marks."""
    tool_input = {"prompt": prompt, "subagent_type": "general-purpose"}
    assert _guard_module().is_phase_delegation(tool_input) is True


@pytest.mark.parametrize(
    "prompt",
    [
        "Complete the planning phase notes in"
        " docs/dev/project-management/plans/00300.md; task 3 only.",
        "Call the plan-tasks helper script with --dry-run",
        "Do design-solution/references/x.md first",
        "Do the work phase tests pass on this branch?",
        "Do the work phase handoff test",
        "Call the work phase helper",
        "Start the design phase doc review",
        "Launch the work phase timer test",
        "Quote this line verbatim: ...every `task-add` call"
        " `/autopilot:plan-tasks` made...",
    ],
    ids=[
        "plan-notes-one-task",
        "plan-tasks-helper-script",
        "design-solution-reference-path",
        "question-about-the-tests",
        "handoff-test",
        "phase-helper",
        "doc-review",
        "timer-test",
        "quoted-skill-prose",
    ],
)
def test_per_task_prompts_that_mention_a_phase_are_allowed(prompt: str) -> None:
    """Real per-task work names phase jargon constantly: as a noun modifier
    ("work phase tests"), inside a path, in a question, or quoted as prose to
    edit. None of them puts the phase in object position of an order."""
    tool_input = {"prompt": prompt, "subagent_type": "autopilot:ivan"}
    assert _guard_module().is_phase_delegation(tool_input) is False


@pytest.mark.parametrize(
    "prompt",
    [
        "Update hooks/guard.py so it can run the work phase.",
        "For task 3, make the hook run the work phase.",
    ],
    ids=["one-file-scopes", "one-task-id-scopes"],
)
def test_one_named_task_or_file_scopes_a_phase_mention(prompt: str) -> None:
    """Exactly one distinct task id, or one distinct path that is neither
    under `prds/` nor a SKILL.md, narrows the dispatch to a single job even
    though the phase name ends its clause."""
    assert _guard_module().is_phase_delegation({"prompt": prompt}) is False


@pytest.mark.parametrize(
    "prompt",
    [
        "Tasks complete in the work phase",
        "In the work phase: do not skip tests",
        "Decide what to do about the work phase",
        "Work phase: complete",
        "Did you run the work phase?",
    ],
    ids=[
        "trailing-in-the",
        "leading-in-the",
        "about-the",
        "phase-as-a-label",
        "question",
    ],
)
def test_prepositional_and_question_mentions_are_allowed(prompt: str) -> None:
    """The weak anchor needs a non-preposition word before the phase name, so
    "in the work phase" and "about the work phase" stay prose; a clause with
    no word before the name is a label, and a clause ending in "?" is a
    question, not an order."""
    assert _guard_module().is_phase_delegation({"prompt": prompt}) is False


@pytest.mark.parametrize(
    ("prompt", "expected"),
    [
        (
            'Insert one sentence before the line "Invoke `/autopilot:work`'
            ' skill. It runs until all tasks complete."',
            False,
        ),
        ('Run "/autopilot:work" for PRD 7.', True),
    ],
    ids=["quoted-skill-prose-as-an-edit-target", "strong-anchor-for-prd"],
)
def test_per_task_personas_count_only_the_strong_anchor(
    prompt: str, expected: bool
) -> None:
    """A worker persona's prompt quotes skill prose as an edit target, so the
    weak anchor never fires for it - even with "until all tasks complete" in
    the quote. The strong "for PRD 7" anchor still denies."""
    tool_input = {"prompt": prompt, "subagent_type": "autopilot:worker-opus"}
    assert _guard_module().is_phase_delegation(tool_input) is expected


@pytest.mark.parametrize(
    ("prompt", "expected"),
    [
        ("Do not run the work phase for PRD 7.", False),
        ("Never fail to report; do not run the work phase.", False),
        ("Code review isn't only running the work phase", False),
        ("Do not wait for me. Run the work phase for PRD 7.", True),
        ("Do not, under any circumstances, run the work phase.", True),
    ],
    ids=[
        "same-clause-negation",
        "double-negation-scoped-to-an-earlier-clause",
        "isnt-only-is-a-state",
        "negation-in-an-earlier-sentence",
        "negation-five-words-away-across-commas",
    ],
)
def test_a_negation_binds_only_inside_its_clause(prompt: str, expected: bool) -> None:
    """A negation allows the dispatch only from inside the same clause, within
    four words of the phase name: an earlier sentence, or four commas and five
    words of hedging, leaves the order standing."""
    assert _guard_module().is_phase_delegation({"prompt": prompt}) is expected
