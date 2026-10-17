"""PRD 00307: a phase name inside a longer quoted or wrapped run is a citation.

Also pins the `_ordered_to_follow` negation floor (a negation in the clause
before the follow verb must not excuse it) and the enumerated agoge roster
(only the real personas are exempt, not anything spelled `agoge:*`).

Every fixture that expects None is paired with a control differing in the one
feature under test, so neither a memorized prompt list nor a content-word
heuristic can satisfy this file: the three wrapper tests carry a
wrapper-stripped twin, the citation-window tests cross their reporting verb
("says" against "reads"), the exemption tests carry near-miss persona names,
and every deny assertion quotes the span back out of the prompt text.
"""

from __future__ import annotations

import importlib
import inspect
import re
import sys
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parent
GP = "general-purpose"


def _guard_module():
    sys.path.insert(0, str(HOOKS))
    return importlib.import_module("guard_phase_delegation")


def _find(
    prompt: str,
    subagent_type: str | None = GP,
    description: str | None = None,
) -> str | None:
    tool_input = {"prompt": prompt}
    if subagent_type is not None:
        tool_input["subagent_type"] = subagent_type
    if description is not None:
        tool_input["description"] = description
    return _guard_module().find_phase_delegation(tool_input)


def _assert_quotes(span: str | None, prompt: str, name: str) -> None:
    """A deny must quote the real field text back: the span has to carry the
    phase name AND be a run of the prompt, so neither a canned string nor a
    bare "something matched" flag can stand in for it."""
    assert span is not None
    assert name in span
    assert span in " ".join(prompt.split())


def test_backtick_run_opening_before_the_name_is_a_citation() -> None:
    assert (
        _find("The report line reads `run plan-tasks for PRD 00300` verbatim.") is None
    )
    # Control: same words, same "reads"/"verbatim" vocabulary, no wrapper - so
    # the citation above must come from the backticks, not from a content word.
    _assert_quotes(
        _find("The report line reads run plan-tasks for PRD 00300 verbatim."),
        "The report line reads run plan-tasks for PRD 00300 verbatim.",
        "plan-tasks",
    )


def test_double_quote_run_is_a_citation() -> None:
    assert _find('The log line reads "run plan-tasks for PRD 00300" verbatim.') is None
    _assert_quotes(
        _find("The log line reads run plan-tasks for PRD 00300 verbatim."),
        "The log line reads run plan-tasks for PRD 00300 verbatim.",
        "plan-tasks",
    )


def test_paren_aside_is_a_citation() -> None:
    assert (
        _find("The fallback (run plan-tasks for PRD 00300) sits in the old docs.")
        is None
    )
    _assert_quotes(
        _find("The fallback run plan-tasks for PRD 00300 sits in the old docs."),
        "The fallback run plan-tasks for PRD 00300 sits in the old docs.",
        "plan-tasks",
    )


def test_a_run_closing_at_the_sentence_tail_cites_the_name_inside_it() -> None:
    # The tightly wrapped narrative shape: the backtick opens right before the
    # skill name and closes only at the sentence tail, so the name is quoted
    # prose. This is the shape the deleted invented corpus fixture had moved
    # the closer for; it is pinned here as a shape instead, because the id it
    # came from (toolu_015DM18ubZLJZbA65ozvuw8c) has no recoverable payload
    # and inventing one is the defect the recorded corpus exists to kill.
    assert (
        _find(
            "The orchestrator automatically re-invokes `/autopilot:work, which "
            "then proceeds to the next task`.",
            None,
        )
        is None
    )
    # Control, in the same test: a name wrapped on its OWN is a standalone
    # label and must still be refused, so this pin cannot be satisfied by
    # letting any backtick before the name excuse the order.
    label = "Run `/autopilot:work` for PRD 00300."
    _assert_quotes(_find(label), label, "autopilot:work")


@pytest.mark.parametrize(
    ("prompt", "name"),
    [
        ("Run `plan-tasks` for PRD 00300.", "plan-tasks"),
        ('Run "plan-tasks" for PRD 00300.', "plan-tasks"),
        ("Run (plan-tasks) for PRD 00300.", "plan-tasks"),
        ("Run `/autopilot:work` for PRD 00300.", "autopilot:work"),
    ],
    ids=["backtick", "double-quote", "paren", "backtick-slash-skill"],
)
def test_wrapper_closing_right_after_the_name_still_counts(
    prompt: str,
    name: str,
) -> None:
    # A name wrapped on its own (open right before, close right after) is a
    # label, not a citation: it still anchors as a delegation, as today.
    _assert_quotes(_find(prompt), prompt, name)


def test_already_closed_aside_before_the_name_is_not_a_citation() -> None:
    # The "(an aside)" closes before plan-tasks; the later, unrelated ")" must
    # not make plan-tasks read as wrapped.
    prompt = "Note (an aside) then also run plan-tasks for PRD 00300 cleanup)"
    _assert_quotes(_find(prompt), prompt, "plan-tasks")


def test_negation_in_previous_clause_does_not_excuse_follow() -> None:
    assert (
        _find("Read skills/work/SKILL.md, do not stop, then follow it for every task.")
        is not None
    )


def test_negation_inside_the_verb_clause_still_excuses() -> None:
    assert (
        _find("Read skills/work/SKILL.md and do not follow it for every task.") is None
    )


# The negation floor, as a matrix instead of two pinned sentences: where the
# negation sits decides, not which words the sentence happens to use. A
# negation in the clause BEFORE the verb negates something else; one in the
# verb-object gap or in the few words before the verb negates the order.
_NEGATION_SHAPES = [
    ("absent", "Read skills/work/SKILL.md and {verb} {obj}.", True),
    (
        "prior-clause",
        "Read skills/work/SKILL.md, do not stop, then {verb} {obj}.",
        True,
    ),
    ("verb-object-gap", "Read skills/work/SKILL.md and do not {verb} {obj}.", False),
    ("before-verb", "Read skills/work/SKILL.md and you must not {verb} {obj}.", False),
]


@pytest.mark.parametrize("obj", ["it", "its steps", "every task"])
@pytest.mark.parametrize("verb", ["follow", "execute", "run", "carry out"])
@pytest.mark.parametrize(
    ("template", "ordered"),
    [(template, ordered) for _, template, ordered in _NEGATION_SHAPES],
    ids=[shape for shape, _, _ in _NEGATION_SHAPES],
)
def test_where_the_negation_sits_decides_the_follow_order(
    template: str,
    ordered: bool,
    verb: str,
    obj: str,
) -> None:
    prompt = template.format(verb=verb, obj=obj)
    span = _find(prompt)
    if ordered:
        _assert_quotes(span, prompt, "skills/work/SKILL.md")
    else:
        assert span is None


def test_period_inside_a_dotted_identifier_does_not_end_the_citation_sentence() -> None:
    assert (
        _find(
            "The dispatcher (which handles cli/frontmatter.parse and plan-tasks) "
            "looks for the next phase.",
        )
        is None
    )


def test_period_before_a_closing_backtick_does_not_end_the_citation_sentence() -> None:
    assert (
        _find(
            "The fixture prompt text is `Run the work phase for PRD 00300.` "
            "(verbatim, from the log)",
        )
        is None
    )


@pytest.mark.parametrize("verb", ["says", "reads"], ids=["says", "reads"])
def test_a_real_sentence_end_still_bounds_the_citation_window(verb: str) -> None:
    # The quote opens in the first sentence; ". " ends that sentence, so the
    # bare order in the next one is outside the citation window. Crossed over
    # the reporting verb: the window is punctuation, not vocabulary.
    prompt = f'The log {verb} "ready. Run plan-tasks for PRD 00300, every task.'
    _assert_quotes(_find(prompt), prompt, "plan-tasks")


@pytest.mark.parametrize("verb", ["says", "reads"], ids=["says", "reads"])
def test_balanced_quotes_in_one_clause_do_not_hide_an_order(verb: str) -> None:
    prompt = (
        f'The log {verb} "ready, done" then run plan-tasks for PRD 00300 '
        'and print "ok".'
    )
    _assert_quotes(_find(prompt), prompt, "plan-tasks")


@pytest.mark.parametrize("verb", ["says", "reads"], ids=["says", "reads"])
def test_a_quoted_order_inside_one_sentence_is_a_citation(verb: str) -> None:
    # The allow side of the same verb pair: "says" is not what makes a prompt
    # an order, and "reads" is not what makes one a citation.
    assert _find(f'The log {verb} "run plan-tasks for PRD 00300" verbatim.') is None


def test_inch_marks_around_an_order_do_not_wrap_it() -> None:
    # A '"' behind a digit is a unit mark, not a delimiter: pairing the two
    # would put the order inside one quoted run and excuse it.
    prompt = 'the 5" gap, run /autopilot:work, it is 6" wide'
    _assert_quotes(_find(prompt), prompt, "autopilot:work")
    # Control: the same two marks with the digits dropped ARE quotes, and the
    # order between them is a citation.
    assert _find('the x" gap, run /autopilot:work, it is y" wide') is None


def test_a_backtick_right_after_a_digit_still_opens_its_run() -> None:
    # The inch-mark rule belongs to '"' alone: no unit is written with a
    # backtick. Skipping a backtick opener behind a digit hands the opener role
    # to its own closer, and the bogus run that pairing makes reaches over the
    # bare order after it and excuses it.
    prompt = "The log says 5`ready`, run plan-tasks for PRD 00300, print `ok`."
    _assert_quotes(_find(prompt), prompt, "plan-tasks")
    # The same shape spelled with '"' must ALSO be refused. The digit
    # suppresses that opener, which leaves every later '"' ambiguous - the mark
    # after `ready` may be the suppressed one's close or a fresh open - and a
    # guard resolves an ambiguity by denying, so the field gets no '"' runs.
    quoted = 'The log says 5"ready", run plan-tasks for PRD 00300, print "ok".'
    _assert_quotes(_find(quoted), quoted, "plan-tasks")


def test_a_unit_mark_after_a_citation_does_not_un_cite_it() -> None:
    # Pairing stops at the first suppressed mark, but pairs completed BEFORE it
    # are unambiguous and still cite: denying them would refuse a real citation
    # that merely happens to precede a unit mark.
    assert (
        _find('The log reads "run plan-tasks for PRD 00300" verbatim, in the 5" column.')
        is None
    )


@pytest.mark.parametrize(
    "prompt",
    [
        '"Run the work phase for PRD 7."',
        'Insert the line "Invoke `/autopilot:work` skill."',
    ],
    ids=["quoted-order", "quoted-skill-line"],
)
def test_a_terminator_before_only_closing_wrappers_still_ends_the_sentence(
    prompt: str,
) -> None:
    name = "work phase" if "work phase" in prompt else "autopilot:work"
    _assert_quotes(_find(prompt), prompt, name)


def test_ordered_to_follow_uses_bisect() -> None:
    source = inspect.getsource(_guard_module()._ordered_to_follow)
    assert "bisect_left" in source
    assert "_negated(text, end, match.start())" not in source
    assert "next(" not in source


def _follow_fixture(text: str) -> tuple:
    """`_ordered_to_follow`'s five arguments for the SKILL.md span in `text`,
    built the way `_field_delegation` builds them, so the behavioural tests
    below drive the real function on real boundary lists."""
    module = _guard_module()
    normalized = module._normalize(text)
    spans = module._candidates(normalized)
    end = min(end for _, end, is_skill_md in spans if is_skill_md)
    clause_starts, clause_ends, sentences, *_ = module._boundaries(normalized, spans)
    return normalized, end, sentences, clause_starts, clause_ends


@pytest.mark.parametrize(
    ("text", "ordered"),
    [
        ("Read skills/work/SKILL.md and follow it for every task.", True),
        (
            "Read skills/work/SKILL.md, do not stop, then follow it for every task.",
            True,
        ),
        ("Read skills/work/SKILL.md and do not follow it for every task.", False),
        ("Read skills/work/SKILL.md and you must not follow it for every task.", False),
        ("Read skills/work/SKILL.md for the exit-line wording.", False),
    ],
    ids=[
        "plain-order",
        "prior-clause-negation",
        "gap-negation",
        "pre-verb-negation",
        "no-order",
    ],
)
def test_ordered_to_follow_returns_the_negation_floor(text: str, ordered: bool) -> None:
    assert _guard_module()._ordered_to_follow(*_follow_fixture(text)) is ordered


class _CountingSentences(list):
    """A sentence list that records how it is consumed: a linear scan iterates
    it (or indexes every element), a binary search indexes about log2(n) of
    them. Counted instead of timed, so the pin is a machine-independent fact
    about the lookup rather than a wall-clock budget."""

    def __init__(self, items: list[int]) -> None:
        super().__init__(items)
        self.iterations = 0
        self.lookups = 0

    def __iter__(self):
        self.iterations += 1
        return super().__iter__()

    def __getitem__(self, index):
        self.lookups += 1
        return super().__getitem__(index)


def test_ordered_to_follow_does_not_walk_the_sentence_list() -> None:
    """The behavioural half of the bisect must-have: with the SKILL.md path
    sitting behind 5000 sentence boundaries, the sentence lookup must index the
    list a handful of times and never iterate it end to end."""
    text = "x. " * 5_000 + "Read skills/work/SKILL.md and follow it for every task."
    normalized, end, sentences, clause_starts, clause_ends = _follow_fixture(text)
    counting = _CountingSentences(sentences)
    assert len(counting) > 5_000
    assert (
        _guard_module()._ordered_to_follow(
            normalized,
            end,
            counting,
            clause_starts,
            clause_ends,
        )
        is True
    )
    assert counting.iterations == 0
    assert counting.lookups <= 32


class _CountingRuns(dict):
    """The symmetric-delimiter run map, recording how often it is consulted: a
    rescan per candidate shows up as work growing with the SQUARE of the
    candidate count, one map read per candidate as work growing with the count
    itself. Counted, not timed, so the pin is machine-independent."""

    def __init__(self, mapping: dict) -> None:
        super().__init__(mapping)
        self.consultations = 0

    def get(self, key, default=None):
        self.consultations += 1
        return super().get(key, default)


def _count_run_consultations(monkeypatch: pytest.MonkeyPatch, repeats: int) -> tuple:
    """(candidate count, run-map consultations) for a prompt carrying `repeats`
    anchored citations in ONE sentence - every candidate passes the anchor and
    reaches the citation check, which is the shape that used to rescan."""
    module = _guard_module()
    build = module._quoted_runs
    maps = []

    def counting(scratch: str, spans: list) -> dict:
        maps.append(_CountingRuns(build(scratch, spans)))
        return maps[-1]

    monkeypatch.setattr(module, "_quoted_runs", counting)
    prompt = "The log says " + '"run plan-tasks for PRD 00300" ' * repeats + "verbatim."
    assert module.find_phase_delegation({"prompt": prompt, "subagent_type": GP}) is None
    candidates = len(module._candidates(module._normalize(prompt)))
    return candidates, sum(runs.consultations for runs in maps)


@pytest.mark.parametrize("repeats", [8, 64])
def test_citation_checking_reads_the_run_map_once_per_candidate(
    monkeypatch: pytest.MonkeyPatch,
    repeats: int,
) -> None:
    candidates, consultations = _count_run_consultations(monkeypatch, repeats)
    assert candidates == repeats
    assert consultations == repeats


class _CountingText(str):
    """A field that records how many characters every `find`/`rfind` over it
    sweeps. The run-map count above cannot see the other half of the cost: a
    `text.find(closer, end, sentence_end)` per wrap pair per candidate reads
    the map exactly once and still scans to the end of the field, so the SCAN
    gets its own counter. Counted, not timed, so the pin stays
    machine-independent."""

    def __new__(cls, value: str) -> _CountingText:
        text = super().__new__(cls, value)
        text.scanned = 0
        return text

    def _charge(self, start: int, end: int | None) -> None:
        stop = len(self) if end is None else min(end, len(self))
        self.scanned += max(0, stop - max(start, 0))

    def find(self, sub: str, start: int = 0, end: int | None = None) -> int:
        self._charge(start, end)
        return str.find(self, sub, start, end)

    def rfind(self, sub: str, start: int = 0, end: int | None = None) -> int:
        self._charge(start, end)
        return str.rfind(self, sub, start, end)


def _count_scanned(repeats: int) -> tuple[int, int, int]:
    """(candidate count, field length, characters scanned) for the same
    many-citations-in-one-sentence prompt, driven through the real
    `_field_delegation` on a field that charges every find/rfind over it."""
    module = _guard_module()
    prompt = "The log says " + '"run plan-tasks for PRD 00300" ' * repeats + "verbatim."
    text = _CountingText(module._normalize(prompt))
    assert module._field_delegation(text, False) is None
    return len(module._candidates(str(text))), len(text), text.scanned


@pytest.mark.parametrize("repeats", [8, 64])
def test_citation_checking_does_not_scan_the_field_per_candidate(repeats: int) -> None:
    candidates, length, scanned = _count_scanned(repeats)
    assert candidates == repeats
    # The one field-wide pass that belongs here is `_find_skill_md_paths`'
    # single `find("SKILL.md")`. Every citation question on top of it must be a
    # bisect into the precomputed mark positions, so the per-candidate scan
    # budget is a constant: a `find`-to-sentence-end _cited spends roughly
    # 7 * candidates * length instead and blows this by two orders of
    # magnitude at repeats=64.
    assert scanned <= length + 64 * candidates


_AGOGE_PROMPT = "Run /autopilot:work for PRD 00300, every task."
_AGOGE_PERSONA_NAMES = [
    "agoge:olivia",
    "agoge:walter",
    "agoge:heidi",
    "agoge:judy",
    "agoge:wendy",
    "agoge:peggy",
    "agoge:trudy",
]


def test_the_agoge_roster_is_exactly_the_seven_personas() -> None:
    # The exemption is driven by this enumerated set, so a prefix test ("any
    # agoge:* name") cannot hide behind the names the tests happen to list.
    assert frozenset(_AGOGE_PERSONA_NAMES) == _guard_module()._AGOGE_PERSONAS


@pytest.mark.parametrize("subagent_type", _AGOGE_PERSONA_NAMES)
def test_each_agoge_persona_is_exempt(subagent_type: str) -> None:
    # Control: the same prompt is a delegation for a non-exempt agent.
    assert _find(_AGOGE_PROMPT, GP) is not None
    assert _find(_AGOGE_PROMPT, subagent_type) is None


@pytest.mark.parametrize(
    "subagent_type",
    [
        "agoge:",
        "agoge:not-a-real-agent",
        "agoge:evil",
        "agoge:olivia2",
        "agoge:oilvia",
        "AGOGE:olivia",
        "agoge:olivia ",
        " agoge:olivia",
        "agoge:olivia:work",
    ],
    ids=[
        "bare-prefix",
        "unknown-name",
        "hyphen-free-unknown",
        "suffixed-persona",
        "transposed-persona",
        "upper-case-prefix",
        "trailing-space",
        "leading-space",
        "extended-name",
    ],
)
def test_unknown_agoge_prefix_is_not_exempt(subagent_type: str) -> None:
    assert _find(_AGOGE_PROMPT, subagent_type) is not None


_READ_ONLY_REVIEWER_NAMES = [
    "autopilot:alice",
    "autopilot:blake",
    "autopilot:bob",
    "autopilot:carl",
    "autopilot:cora",
    "autopilot:eve",
    "autopilot:grace",
    "autopilot:mallory",
    "autopilot:pat",
    "autopilot:rita",
    "autopilot:toby",
    "autopilot:trent",
    "autopilot:victor",
]


@pytest.mark.parametrize("subagent_type", _READ_ONLY_REVIEWER_NAMES)
def test_each_read_only_reviewer_is_exempt(subagent_type: str) -> None:
    # Control: the same prompt is a delegation for a non-exempt agent.
    assert _find(_AGOGE_PROMPT, GP) is not None
    assert _find(_AGOGE_PROMPT, subagent_type) is None


@pytest.mark.parametrize(
    "subagent_type",
    [
        "autopilot:",
        "autopilot:alice2",
        "AUTOPILOT:alice",
        "autopilot:alice ",
        "autopilot:allice",
    ],
    ids=[
        "bare-prefix",
        "suffixed",
        "upper-case-prefix",
        "trailing-space",
        "misspelled",
    ],
)
def test_a_near_miss_reviewer_name_is_not_exempt(subagent_type: str) -> None:
    assert _find(_AGOGE_PROMPT, subagent_type) is not None


_WEAK_ANCHOR_PROMPT = "Run plan-tasks, then report back."
_STRONG_ANCHOR_PROMPT = "Run plan-tasks for PRD 00300."


@pytest.mark.parametrize(
    "subagent_type",
    [
        "autopilot:ivan",
        "autopilot:tess",
        "autopilot:devon",
        "autopilot:worker-opus",
    ],
)
def test_a_per_task_persona_counts_the_strong_anchor_only(subagent_type: str) -> None:
    # Control: the weak anchor (name ends its clause) still denies a general
    # agent, so the allow below is the persona rule, not a dead predicate.
    _assert_quotes(_find(_WEAK_ANCHOR_PROMPT), _WEAK_ANCHOR_PROMPT, "plan-tasks")
    assert _find(_WEAK_ANCHOR_PROMPT, subagent_type) is None
    # ...and the exemption is not a blanket pass: a strong anchor still denies.
    _assert_quotes(
        _find(_STRONG_ANCHOR_PROMPT, subagent_type),
        _STRONG_ANCHOR_PROMPT,
        "plan-tasks",
    )


def test_an_order_in_the_description_alone_still_counts() -> None:
    span = _find("Review the notes I left.", description=_STRONG_ANCHOR_PROMPT)
    _assert_quotes(span, _STRONG_ANCHOR_PROMPT, "plan-tasks")
    # Control: the same two-field shape with no order in either field.
    assert (
        _find("Review the notes I left.", description="Summarize the design docs.")
        is None
    )


# Every lookalike code point is built with chr(), never pasted: a fullwidth
# "o" is unreadable in source and the soft hyphen is invisible, so an editor or
# a formatter could silently destroy a pasted one (same convention as
# _DROPPED_CATEGORIES in the hook).
_FULLWIDTH_O = chr(0xFF4F)  # fullwidth latin small letter o -> "o" under NFKD
_NB_HYPHEN = chr(0x2011)  # non-breaking hyphen, category Pd -> "-"
_MATH_MINUS = chr(0x2212)  # minus sign, category Sm, folded by _FOLDED
_SOFT_HYPHEN = chr(0x00AD)  # soft hyphen, category Cf -> dropped


@pytest.mark.parametrize(
    ("prompt", "name"),
    [
        (
            f"Run /autopilot:w{_FULLWIDTH_O}rk for PRD 00300, every task.",
            "autopilot:work",
        ),
        (f"Run plan{_NB_HYPHEN}tasks for PRD 00300.", "plan-tasks"),
        (f"Run plan{_MATH_MINUS}tasks for PRD 00300.", "plan-tasks"),
        (f"Run /autopilot:w{_SOFT_HYPHEN}ork for PRD 00300.", "autopilot:work"),
    ],
    ids=["fullwidth-o", "non-breaking-hyphen", "math-minus", "soft-hyphen"],
)
def test_a_lookalike_spelling_is_normalized_before_matching(
    prompt: str,
    name: str,
) -> None:
    # The quoted span comes out of the NORMALIZED field, so it carries the
    # plain name even though the prompt never spells it.
    assert name not in prompt
    span = _find(prompt)
    assert span is not None
    assert name in span


@pytest.mark.parametrize(
    "payload",
    [
        "not a dict",
        None,
        42,
        ["prompt"],
        {},
        {"prompt": None},
        {"prompt": 42, "description": None},
        {"subagent_type": GP},
    ],
    ids=[
        "string",
        "none",
        "int",
        "list",
        "empty-dict",
        "none-prompt",
        "non-string-fields",
        "no-fields",
    ],
)
def test_an_unusable_payload_fails_open(payload: object) -> None:
    module = _guard_module()
    assert module.find_phase_delegation(payload) is None
    assert module.is_phase_delegation(payload) is False


def test_is_phase_delegation_mirrors_find_phase_delegation() -> None:
    module = _guard_module()
    assert module.is_phase_delegation({"prompt": _AGOGE_PROMPT}) is True
    assert module.is_phase_delegation({"prompt": "Review the attached diff."}) is False


def test_backtick_inside_closed_quote_run_does_not_pair_outside_it() -> None:
    # The backtick right before "x" sits INSIDE an already-closed '"..."' run:
    # it is a literal character of that quote, not a fresh citation opener.
    # Pairing it with an unrelated LATER backtick swallows every bare order in
    # between as if the whole span were wrapped prose.
    prompt = (
        'Note "see `x" then run /autopilot:work for PRD 00300 end to end, '
        "report `done`."
    )
    _assert_quotes(_find(prompt), prompt, "autopilot:work")
    prompt2 = (
        'Then "edit `a.py" and run plan-tasks for prd 00300 for every task '
        "and print `ok`."
    )
    _assert_quotes(_find(prompt2), prompt2, "plan-tasks")


def test_emoticon_pair_is_not_a_citation() -> None:
    # ":(" and ":)" are emoticons, not a grammatical parenthetical aside: the
    # ")" of the trailing smiley must not pair with the "(" of the leading
    # frown to wrap the whole order between them as cited prose.
    prompt = "Sorry :( run plan-tasks for prd 00300 for every task :)"
    _assert_quotes(_find(prompt), prompt, "plan-tasks")


def test_cjk_terminators_end_the_citation_window() -> None:
    # The CJK ideographic full stop "。" ends a sentence exactly as "."
    # does. A citation window that only recognizes ASCII terminators runs
    # straight past it, so an unrelated LATER ")" (an emoticon, not a real
    # closing paren) can pair with an EARLIER "(" and wrap the whole order
    # between them.
    prompt = "Hi (all。 Run plan-tasks for PRD 00300 for every task。 Thanks :)"
    _assert_quotes(_find(prompt), prompt, "plan-tasks")


def test_digit_preceded_quote_never_opens_an_own_wrapper_run() -> None:
    # The '"' right after "5" is a unit mark and opens no run of its own: it
    # must not let a LATER, unrelated '"' pair up as if the skipped mark had
    # really opened one, wrapping the bare order between them as cited prose.
    prompt = 'The log says 5"plan-tasks for PRD 00300 and print "ok".'
    _assert_quotes(_find(prompt), prompt, "plan-tasks")


def test_doubled_backtick_citation_is_allowed() -> None:
    # A Markdown doubled-backtick code span ("``...``") wraps its content as
    # surely as a single-backtick pair does. Pairing every backtick
    # independently (1st with 2nd, 3rd with 4th) instead of recognizing the
    # doubled delimiter turns both backtick pairs into zero-width runs and
    # leaves the order between them unwrapped.
    assert (
        _find("``run plan-tasks for PRD 00300`` then some other prose.") is None
    )


def test_backtick_exclusion_in_cite_boundary_can_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The backtick-exclusion character class in _CITE_SENTENCE_BOUNDARY (see
    # its comment in guard_phase_delegation_lexicon.py) is the only thing
    # stopping a multi-backtick closer from giving the `+` run a backtick
    # back as its own "real text after the wrapper" character, which would
    # wrongly end the citation sentence early. Removing that one exclusion
    # must flip the guard's verdict on a fixture that depends on it, so a
    # future rewrite cannot silently drop the exclusion without this test
    # noticing.
    module = _guard_module()
    fixture = '"Run plan-tasks for PRD 00300 z.``(w)" end of quote here now.'
    original = module.find_phase_delegation({"prompt": fixture})
    original_pattern = module._CITE_SENTENCE_BOUNDARY.pattern
    broken_pattern = original_pattern.replace("[^(\\s`]", "[^(\\s]")
    assert broken_pattern != original_pattern
    monkeypatch.setattr(
        module, "_CITE_SENTENCE_BOUNDARY", re.compile(broken_pattern)
    )
    patched = module.find_phase_delegation({"prompt": fixture})
    assert (original is None) != (patched is None), (
        f"removing the backtick exclusion did not flip the verdict: "
        f"original={original!r} patched={patched!r}"
    )
