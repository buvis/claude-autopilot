"""Prose pins for the fast-track driver skill (skills/fast-track/SKILL.md).

Nothing executes this document but a reader: its command lines are copied by a
human operator, so a dropped flag, a lane quietly missing from the roster, or a
per-task ceremony creeping back in leaves every script test in this directory
green while the documented procedure rots. That is the failure these pins exist
to end.

Same pattern as the other prose pins in this repo: read the file once, assert on
short, reword-resistant substrings, each with a failure message naming what
drifted. A missing SKILL.md is a failure, never a skip - the day the document is
gone is exactly the day these tests are supposed to shout.

The machinery each pin runs on - the passages, the sections, the test for a
sentence that reads as an instruction, and the word lists that spot a promise
taken back - lives in fast_track_prose_testutil.py, which carries the reasoning
behind it. What is pinned here: the roster sends in one message and never one
lane at a time, its CLI lanes never run in the foreground or inside a subagent,
Blake is never handed the diff, the preconditions never say nothing blocks a
run, and the rework section neither reuses the implementor nor drops the cap.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

_TESTUTIL_PATH = Path(__file__).with_name("fast_track_prose_testutil.py")
_TESTUTIL_SPEC = importlib.util.spec_from_file_location(
    "fast_track_prose_testutil",
    _TESTUTIL_PATH,
)
assert _TESTUTIL_SPEC is not None and _TESTUTIL_SPEC.loader is not None
_testutil = importlib.util.module_from_spec(_TESTUTIL_SPEC)
_TESTUTIL_SPEC.loader.exec_module(_testutil)

_SKILL_MD = _testutil.SKILL_MD
_CANCELS = _testutil.CANCELS
_NEGATOR = _testutil.NEGATOR
_document = _testutil.document
_frontmatter = _testutil.frontmatter
_body = _testutil.body
_passages = _testutil.passages
_section = _testutil.section
_carrying = _testutil.carrying
_code_fragments = _testutil.code_fragments
_sentences_carrying = _testutil.sentences_carrying
_asserted = _testutil.asserted
_lanes_named = _testutil.lanes_named
_assert_live = _testutil.assert_live
_assert_unopposed = _testutil.assert_unopposed

_START_CALL = "record_dispatch.py start --kind fast-track:"
_END_CALL = "record_dispatch.py end"
_KIND = re.compile(r"--kind fast-track:([A-Za-z0-9:_-]+)")

# The five lanes plus the consensus fallback. `review-fanout.workflow.js` and
# `autopilot:alice` are one lane with two backends, so both names must survive.
_ROSTER = (
    "autopilot:blake",
    "autopilot:eve",
    "codex-run.sh",
    "gemini-run.sh",
    "review-fanout.workflow.js",
    "autopilot:alice",
)
_ROSTER_LANES = ("consensus", "blind", "doubt", "codex", "gemini")

_TASK_ARGUMENT = re.compile(r"--task[= ]\s*(\S+)")
_PLACEHOLDER = re.compile(r"^<[^>]+>$|^\$\{?\w+\}?$|^\{\{?\w[\w.-]*\}?\}$")

# `Pat` is a substring of `Path` and `patch`, so the ban is matched on word
# boundaries; case-insensitively, because `autopilot:pat` is the same per-task
# ceremony wearing a lowercase name.
_BANNED = ("Devon", "deslop", "Pat", "plan-tasks", "design-solution")

# One contradiction per pinned promise, matched over the whole section rather
# than over the passage carrying the pin. A document does not have to retract a
# promise in the passage that carries it when it can simply contradict it in the
# passage before: every `assert any(...)` is satisfied by one good passage, so
# the paragraph above the fence is free to say the opposite.
_SEQUENTIAL = re.compile(
    r"""(?:
          \bone\s+(?:at\s+a\s+time|by\s+one)\b
        | \bin\s+(?:sequence|turn)\b
        | \bsequential(?:ly)?\b | \bserial(?:ly)?\b
        | \bwait(?:s|ing)?\s+for\s+(?:each|the\s+(?:previous|last|first|earlier))\b
        | \bbefore\s+(?:you\s+)?\w+\s+the\s+next\b
        | \bafter\s+the\s+(?:previous|earlier|first)\s+\w+\s+(?:finish|return|land)\w*
    )""",
    re.IGNORECASE | re.VERBOSE,
)
_FOREGROUND = re.compile(
    r"""(?:
          \b(?:inside|within|in)\s+(?:a|the)\s+subagent\b
        | \bin\s+the\s+foreground\b | \bforeground\s+bash\b
        | \bfalse\b
    )""",
    re.IGNORECASE | re.VERBOSE,
)
_UNCAPPED = re.compile(
    r"""(?:
          \bno\s+(?:ceiling|cap|limit|maximum|bound)\b
        | \bunlimited\b
        | \b(?:until|while)\s+the\s+findings\s+\w+
        | \b(?:repeat|loop|rework|cycle)(?:s|ing)?\s+until\b
        | \bas\s+many\s+(?:rounds|times|passes)\s+as\b
    )""",
    re.IGNORECASE | re.VERBOSE,
)
_UNGUARDED = re.compile(
    r"""(?:
          \b(?:nothing|no\s+\w+)\s+(?:here\s+)?(?:blocks?|stops?|refuses?|prevents?)\b
        | \bstart\s+(?:the\s+lane\s+)?(?:wherever|anywhere)\b
        | \bloop\s+session\s+included\b
        | \b(?:headless|loop)\s+(?:sessions?\s+)?(?:is|are)\s+
          (?:fine|ok|okay|allowed|supported|welcome)\b
        | \bruns?\s+(?:fine\s+)?(?:headless|in\s+a\s+loop\s+session)\b
    )""",
    re.IGNORECASE | re.VERBOSE,
)


def test_skill_names_the_invocation_form() -> None:
    # The operator types this line. If the document never spells it out, the
    # lane has no entry point that anyone but its author can find.
    assert "/autopilot:fast-track <card.md>" in _body(), (
        f"{_SKILL_MD}: the body no longer spells out "
        "`/autopilot:fast-track <card.md>`, so the one line an operator types "
        "to start the lane is undocumented."
    )
    usage = _assert_live(
        _carrying(list(_passages()), "/autopilot:fast-track <card.md>"),
        "/autopilot:fast-track <card.md>",
        missing=(
            "`/autopilot:fast-track <card.md>` appears only in running prose, "
            "never fenced or in a code span. An entry point a reader cannot "
            "select and paste is a description of a lane, not a way into it."
        ),
        cancelled=(
            "the invocation form is written down but withdrawn in the same breath."
        ),
    )
    assert any(
        "--push" in fragment for line in usage for fragment in _code_fragments(line)
    ), (
        f"{_SKILL_MD}: the copyable usage line dropped `--push`; an operator "
        "who pastes the documented line cannot ask for the push, and a flag "
        "parked in some other list is one they will never find."
    )
    for pattern in _CANCELS:
        disclaimer = pattern.search(_frontmatter())
        assert disclaimer is None, (
            f"{_SKILL_MD}: the frontmatter disclaims the lane "
            f"({disclaimer.group(0)!r} in the block the harness reads when it "
            "offers the skill). A document that introduces itself as switched "
            "off, or as a record of something that once ran, has no entry "
            "point, whatever its body still spells out."
        )


def test_every_lens_is_dispatched_in_one_message() -> None:
    # The point of the roster is that no lens is optional. A lane silently
    # dropped from the document is a review dimension nobody notices missing.
    roster = _section("Roster")
    for lane in _ROSTER:
        _assert_live(
            [passage for passage in roster if lane in passage.text],
            lane,
            missing=(
                f"the roster section never names {lane!r}; that lens is gone "
                "from the review and its findings will never be raised."
            ),
            cancelled=(f"the roster names {lane!r} only to say it no longer runs."),
        )
    one_message = re.compile(r"(?:one|a single) message", re.IGNORECASE)
    together = _assert_live(
        [passage for passage in roster if one_message.search(passage.text)],
        one_message,
        missing=(
            "the roster section no longer says the lanes go out in one message, "
            "so a reader dispatches them one at a time and the reviewers run in "
            "sequence instead of together."
        ),
        cancelled="the roster mentions one message only to withdraw it.",
    )
    # Polarity. "Send them in one message" and "one message is the mistake most
    # crews make" carry the same phrase, and only one of them is the rule.
    stated = [
        passage
        for passage in together
        if any(
            _asserted(sentence, one_message)
            for sentence in _sentences_carrying(passage.text, one_message)
        )
    ]
    assert stated, (
        f"{_SKILL_MD}: the roster names one message only to deny it - every "
        "sentence carrying the phrase has a negator in front of it. Dispatched "
        "one at a time, the five lanes run in sequence, and each one reads a "
        "session the one before it has already coloured."
    )
    _assert_unopposed(
        roster,
        _SEQUENTIAL,
        "the roster sends the lanes out one at a time, in sequence, or waiting "
        "for each, somewhere in the section:",
    )


def test_cli_reviewers_run_as_background_bash_never_inside_a_subagent() -> None:
    # A subagent cannot hold a background Bash job, so a codex or gemini lane
    # nested inside one blocks the driver for the whole run.
    roster = _section("Roster")
    _assert_live(
        _carrying(roster, "run_in_background: true"),
        "run_in_background: true",
        missing=(
            "the roster no longer hands the CLI lanes `run_in_background: true` "
            "as a field to copy; run in the foreground they serialise the "
            "roster and stall the driver."
        ),
        cancelled=(
            "`run_in_background: true` survives in the roster as a string the "
            "document says is not honoured."
        ),
    )
    _assert_unopposed(
        roster,
        _FOREGROUND,
        "the roster puts a lane in the foreground, inside a subagent, or flips "
        "the background field to false, somewhere in the section:",
    )
    _assert_live(
        [
            passage
            for passage in roster
            if "never inside a subagent" in passage.text.lower()
        ],
        "never inside a subagent",
        missing=(
            "the roster dropped `never inside a subagent`, the one rule that "
            "keeps the codex and gemini lanes out of a wrapper that cannot run "
            "background Bash."
        ),
        cancelled=(
            "`never inside a subagent` is quoted in the roster as something the "
            "lane used to promise."
        ),
    )


# Blake's two probes. `_CARD_AND_DIFF` is the passage that hands him both: the
# promise and the betrayal are one sentence apart, so the pin below has to read
# them together.
_NEVER_THE_DIFF = re.compile(
    r"never\s+(?:sees\s+|gets\s+|receives\s+|reads\s+)?the\s+diff",
    re.IGNORECASE,
)
_CARD_AND_DIFF = re.compile(
    r"card\s+and\s+the\s+diff|diff\s+and\s+the\s+card|\bboth\b",
    re.IGNORECASE,
)


def test_blake_receives_the_card_never_the_diff() -> None:
    # Blake's whole value is ignorance of the implementation: handed the diff,
    # he becomes a second consensus lane wearing the blind lens's name.
    roster = _section("Roster")
    blake = _assert_live(
        [passage for passage in roster if "autopilot:blake" in passage.text.lower()],
        "autopilot:blake",
        missing=(
            "the roster documents no `autopilot:blake` dispatch, so the blind "
            "lens is not in the review at all."
        ),
        cancelled="the roster names `autopilot:blake` only as a lane that is gone.",
    )
    assert any(
        "card" in passage.text.lower()
        and _NEVER_THE_DIFF.search(passage.text)
        and not _CARD_AND_DIFF.search(passage.text)
        for passage in blake
    ), (
        f"{_SKILL_MD}: no single passage about `autopilot:blake` says he "
        "receives the card and never the diff, or the passage that says it also "
        "hands him both. Split across paragraphs the promise is a coincidence "
        "of words; handed the diff beside the card he reviews the "
        "implementation instead of the spec. Either way the lane loses its only "
        "spec-side lens."
    )
    # Section-wide, because the promise passage does not have to be the one that
    # breaks it: any sentence anywhere under Roster that names Blake and the
    # diff with nothing negating it hands him the implementation.
    handed = sorted(
        {
            sentence.strip()
            for passage in roster
            for sentence in _sentences_carrying(passage.text, "blake")
            if "diff" in sentence.lower() and not _NEGATOR.search(sentence)
        },
    )
    assert not handed, (
        f"{_SKILL_MD}: the roster hands `autopilot:blake` the diff: {handed[:3]}. "
        "One sentence keeping the promise does not undo another giving him the "
        "implementation - the operator sends what the section told him to send, "
        "and the blind lens reviews the code like everybody else."
    )


# The three rework probes and the complaint they share. One passage has to
# carry the cap and the fresh instance at once, so all three are read against
# the same text rather than against whichever paragraph happens to match.
_REWORK_CAP = re.compile(r"at most once|no more than once|only once", re.IGNORECASE)
_FRESH_IVAN = re.compile(
    r"fresh\s+(?:`?autopilot:ivan`?|implementor|instance|ivan)",
    re.IGNORECASE,
)
_REUSED_IVAN = re.compile(
    r"\breuse\b|\bre-use\b"
    r"|\bsame\s+(?:one|instance|implementor|ivan|agent|session|context)\b"
    r"|already\s+in\s+the\s+session|\bexisting\s+(?:instance|implementor)\b"
    r"|\bwho\s+wrote\s+the\s+(?:code|patch|implementation|line)\w*"
    r"|\bremembers?\s+writing\b"
    r"|\bkeeps?\s+the\s+(?:implementor|instance|session|context)\b",
    re.IGNORECASE,
)
_IVAN_PROMISE_SPLIT = (
    f"{_SKILL_MD}: no single passage dispatches `autopilot:ivan`, calls "
    "that instance fresh, and caps rework at one round. Apart, the cap "
    "reads as a note about some other loop and `fresh` hangs off whatever "
    "is nearby - a document that dispatches Ivan and then says to reuse the "
    "instance already in the session carries both words and neither promise."
)


def test_ivan_is_fresh_on_rework_and_capped_at_one_rework() -> None:
    # A reused implementor argues with the reviewers from memory instead of
    # reading the findings, and an uncapped rework loop never exits.
    rework = _section("Rework")
    _assert_live(
        [passage for passage in rework if _REWORK_CAP.search(passage.text)],
        _REWORK_CAP,
        missing=(
            "the rework section no longer caps rework at one round, so an item "
            "whose findings keep coming back can cycle through implementors "
            "forever. A cap stated anywhere else is a cap the reader reworking "
            "an item never sees."
        ),
        cancelled="the rework cap is stated and then taken back.",
    )
    ivan = _assert_live(
        [passage for passage in rework if "autopilot:ivan" in passage.text.lower()],
        "autopilot:ivan",
        missing=(
            "the rework section dispatches no `autopilot:ivan`, so nothing in "
            "the lane addresses the confirmed findings."
        ),
        cancelled="the rework section names `autopilot:ivan` only in the past tense.",
    )
    assert any("fresh" in passage.text.lower() for passage in ivan), (
        f"{_SKILL_MD}: nothing in the rework section says its `autopilot:ivan` "
        "is fresh; a reused implementor carries its own defence of the code the "
        "reviewers just faulted."
    )
    kept = [
        passage
        for passage in ivan
        if _REWORK_CAP.search(passage.text)
        and _FRESH_IVAN.search(passage.text)
        and not _REUSED_IVAN.search(passage.text)
    ]
    assert kept, _IVAN_PROMISE_SPLIT
    _assert_unopposed(
        rework,
        _REUSED_IVAN,
        "the rework section sends the round back to the implementor that wrote "
        "the code, somewhere in the section:",
    )
    _assert_unopposed(
        rework,
        _UNCAPPED,
        "the rework section lifts the cap it states, somewhere in the section:",
    )


def test_exit_rule_branches_and_resets_with_keep() -> None:
    # The exit rule is the only thing standing between a confirmed CRITICAL and
    # the working branch.
    exit_rule = _section("Exit")
    _assert_live(
        _carrying(exit_rule, "fast-track/<item>"),
        "fast-track/<item>",
        missing=(
            "the exit rule no longer offers `fast-track/<item>` as text to "
            "copy, so an item that fails review has no named branch to park its "
            "commits on."
        ),
        cancelled="`fast-track/<item>` survives in the exit rule as a branch never created.",
    )
    _assert_live(
        _carrying(exit_rule, "git reset --keep"),
        "git reset --keep",
        missing=(
            "the exit rule no longer offers `git reset --keep` as text to copy; "
            "any other reset either leaves the faulted commits on the branch or "
            "clobbers a foreign change instead of refusing."
        ),
        cancelled=(
            "`git reset --keep` is written in the exit rule as an incantation "
            "the reader is told not to run."
        ),
    )


def test_headless_sessions_are_refused() -> None:
    # Headless sessions kill background Bash, which is where two of the five
    # review lanes live: the lane would run and quietly review with three.
    preconditions = _section("Preconditions")
    named = _assert_live(
        [passage for passage in preconditions if "_AUTOPILOT_LOOP" in passage.text],
        "_AUTOPILOT_LOOP",
        missing=(
            "the preconditions never name `_AUTOPILOT_LOOP`, so the lane will "
            "start inside a headless loop session that cannot keep its "
            "background CLI reviewers alive."
        ),
        cancelled=(
            "`_AUTOPILOT_LOOP` appears in the preconditions as a variable the "
            "lane no longer checks."
        ),
    )
    refusal = re.compile(
        r"refus\w*|declin\w*|will not run|does not run|abort\w*",
        re.IGNORECASE,
    )
    assert any(refusal.search(passage.text) for passage in named), (
        f"{_SKILL_MD}: `_AUTOPILOT_LOOP` is named in the preconditions but the "
        "same passage never refuses the run. A refusal a paragraph away is a "
        "coincidence of words; a mention without a refusal is a note, not a "
        "precondition."
    )
    refused = [
        passage
        for passage in named
        if any(
            _asserted(sentence, refusal)
            for sentence in _sentences_carrying(passage.text, "_AUTOPILOT_LOOP")
        )
    ]
    assert refused, (
        f"{_SKILL_MD}: the sentence naming `_AUTOPILOT_LOOP` does not refuse "
        "the run - the refusal sits in a neighbouring sentence, or is itself "
        "negated ('nothing here refuses a run'). Then the variable is trivia, "
        "the lane starts headless, and its two background CLI reviewers die on "
        "the spot."
    )
    _assert_unopposed(
        preconditions,
        _UNGUARDED,
        "the preconditions wave the run through - nothing blocks it, start "
        "anywhere, a loop session is fine - somewhere in the section:",
    )


# The ledger complaints. Each names the drift its assertion caught and holds a
# slot for the count or the list that proves it; they sit here so the test that
# raises them stays one readable run down the page.
_NO_START_LINE = (
    f"nothing in the body offers `{_START_CALL}` as a command line to "
    "copy, so no dispatch opens a ledger row and the lane costs nothing "
    "on paper."
)
_START_LINES_CANCELLED = (
    f"every `{_START_CALL}` line is listed as a command the reader is told not to run."
)
_TOO_FEW_STARTS = (
    f"{_SKILL_MD}: only {{count}} copyable lines carry `{_START_CALL}`, "
    "fewer than the eight dispatch kinds the lane documents; the missing "
    "lanes run without a ledger row."
)
_TOO_FEW_KINDS = (
    f"{_SKILL_MD}: the start lines name only {{count}} distinct kinds "
    "({kinds}); repeating one kind across dispatches makes the "
    "ledger unable to say which lane spent the time."
)
_UNNAMED_KINDS = (
    f"{_SKILL_MD}: the ledger opens rows under kinds that name no dispatch "
    "this lane makes ({unnamed}). The kinds are how a row is read back "
    "months later; eight rows filed under invented words say the lane spent "
    "the time and refuse to say on what."
)
_START_LINE_WITHOUT_TASK = (
    f"{_SKILL_MD}: a start line opens its row without `--task <item>`: "
    "{text!r}. A row with no item cannot be attributed to the "
    "card it was spent on."
)
_FROZEN_TASK = (
    f"{_SKILL_MD}: every start line hard-codes the same `--task` argument "
    "({task!r}), which is neither a placeholder the reader substitutes "
    "nor the item at hand. Pasted as written, every row on every card is "
    "attributed to one literal string."
)
_TOO_FEW_CHAINS = (
    f"{_SKILL_MD}: the `{_START_CALL}` lines sit under only "
    "{count} heading chain(s) "
    "({chains}). The lane "
    "dispatches from its tests, implement, roster, verify, rework and delta "
    "stages, and a row is opened beside the dispatch it times; one flat "
    "list of command lines is a table of kinds, not eight dispatches that "
    "record themselves."
)
_UNOPENED_LANES = (
    f"{_SKILL_MD}: the roster's start lines ({{kinds}}) open no "
    "row for {unopened}. Five lenses go out from there in one message, and "
    "a lane whose row is opened elsewhere on the page - or under a kind that "
    "names some other lane - is a lane the operator dispatches without "
    "opening one."
)
_NO_END_LINE = (
    f"nothing offers `{_END_CALL}` as a command line to copy, so every "
    "row the lane opens stays open and no dispatch ever gets an outcome "
    "or an elapsed time."
)
_END_LINES_CANCELLED = (
    f"`{_END_CALL}` is listed among commands the reader must not run."
)
_NO_OUTCOME = (
    f"{_SKILL_MD}: the documented `{_END_CALL}` line carries no `--outcome`, "
    "so a closed row cannot say whether its dispatch succeeded."
)


def test_every_dispatch_opens_a_ledger_row() -> None:
    # One row per dispatch is what makes the lane's cost measurable at all. A
    # kind that never appears is a lane whose time is spent off the books.
    starts = _assert_live(
        _carrying(list(_passages()), _START_CALL),
        _START_CALL,
        missing=_NO_START_LINE,
        cancelled=_START_LINES_CANCELLED,
    )
    assert len(starts) >= 8, _TOO_FEW_STARTS.format(count=len(starts))
    kinds = {match.group(1) for line in starts if (match := _KIND.search(line.text))}
    assert len(kinds) >= 8, _TOO_FEW_KINDS.format(count=len(kinds), kinds=sorted(kinds))
    unnamed = sorted(kind for kind in kinds if not _lanes_named(kind))
    assert not unnamed, _UNNAMED_KINDS.format(unnamed=unnamed)
    tasks = []
    for line in starts:
        argument = _TASK_ARGUMENT.search(line.text)
        assert argument, _START_LINE_WITHOUT_TASK.format(text=line.text)
        tasks.append(argument.group(1))
    frozen_to_one_literal = len(set(tasks)) == 1 and not _PLACEHOLDER.match(tasks[0])
    assert not frozen_to_one_literal, _FROZEN_TASK.format(task=tasks[0])
    chains = {line.headings for line in starts}
    assert len(chains) >= 4, _TOO_FEW_CHAINS.format(
        count=len(chains),
        chains=sorted(" > ".join(chain) for chain in chains),
    )
    roster_kinds = {
        match.group(1)
        for line in _carrying(_section("Roster"), _START_CALL)
        if (match := _KIND.search(line.text))
    }
    opened = {lane for kind in roster_kinds for lane in _lanes_named(kind)}
    unopened = [lane for lane in _ROSTER_LANES if lane not in opened]
    assert not unopened, _UNOPENED_LANES.format(
        kinds=sorted(roster_kinds),
        unopened=unopened,
    )
    ends = _assert_live(
        _carrying(list(_passages()), _END_CALL),
        _END_CALL,
        missing=_NO_END_LINE,
        cancelled=_END_LINES_CANCELLED,
    )
    assert any("--outcome" in line.text for line in ends), _NO_OUTCOME


def test_no_per_task_ceremony() -> None:
    # The lane's reason to exist is the ceremony it does not run. Each of these
    # names is a phase that, once mentioned, a reader will dutifully perform.
    # The whole document, frontmatter included: a banned name in the trigger
    # description sells the lane on ceremony it does not run.
    document = _document()
    for word in _BANNED:
        assert not re.search(rf"\b{re.escape(word)}\b", document, re.IGNORECASE), (
            f"{_SKILL_MD}: the document mentions {word!r}. The fast-track lane "
            "runs no per-task ceremony - no test validator, no self-review "
            "pass, no patch reviewer, no planning or design phase - and a name "
            "in the document is a step a reader will run."
        )


# The two stop rules, each a full halt carrying its own outcome string. The
# string is what the ledger row and the report end up holding, and "the item
# stopped" is indistinguishable from a lane that fell over; a phrase nobody
# else writes says which rule fired, and at which step.
_GREEN_OUTCOME = "stopped: tests-green-before-implementation"
_GATE_OUTCOME = "stopped: gate"

# An outcome string is a rule only where the document says what fires it. A
# fence reads `stopped: <anything>` as a `key: value` field, so the literal
# parked alone in a ```text block is pasteable text and skips the verb and
# polarity machinery entirely, while the paragraph above it calls the string
# report vocabulary and disowns it for free. So each outcome is pinned to a
# prose sentence naming its own trigger - the green suite, the non-zero gate -
# and a fenced copy counts as a convenience beside that sentence, never as the
# promise.
_GREEN_TRIGGER = r"\b(?:green|passes|passing)\b"
_GATE_TRIGGER = r"(?:\bnon-?zero\b|\bred\b|\bfail\w*)"
_GREEN_STOP = re.compile(
    rf"{_GREEN_TRIGGER}[^.!?]{{0,200}}?{re.escape(_GREEN_OUTCOME)}"
    rf"|{re.escape(_GREEN_OUTCOME)}[^.!?]{{0,200}}?{_GREEN_TRIGGER}",
    re.IGNORECASE,
)
_GATE_STOP = re.compile(
    rf"{_GATE_TRIGGER}[^.!?]{{0,200}}?{re.escape(_GATE_OUTCOME)}"
    rf"|{re.escape(_GATE_OUTCOME)}[^.!?]{{0,200}}?{_GATE_TRIGGER}",
    re.IGNORECASE,
)

# The red check: the card's first `## Gates` line, run against the new tests
# while nothing implements them yet. Named by position or by number, whichever
# the document prefers.
_FIRST_GATE = re.compile(
    r"""(?:
          \bfirst\b[^.;]{0,40}?\bgates?\b
        | \bgates?\b[^.;]{0,20}?\bfirst\b
        | \bgate\s*1\b
    )""",
    re.IGNORECASE | re.VERBOSE,
)
_TEST_COMMIT = re.compile(r"\bcommit\w*", re.IGNORECASE)

# A check that only looks. `rg` over the staged card, a `git log`, a
# collect-only or dry-run pass: each one names the gate, exits zero whatever
# the suite would have done, and proves nothing about a test file that pins
# nothing.
_SEARCH_ONLY = re.compile(
    r"""(?:
          (?:^|[\s`("'])(?:rg|grep|ack|ag)\b
        | \bgit\s+(?:log|grep)\b
        | --collect-only\b | --dry-run\b | --fixed-strings\b
    )""",
    re.IGNORECASE | re.VERBOSE,
)

# A check rigged to come back red whatever the tests hold. Banning the search
# tools closes one shape and leaves the other open: the run is real, and aimed
# away from the new tests - at the tip of `HEAD`, or at a tree where the test
# file is still unstaged and untracked. Red on every card is a formality, not a
# check, and the green stop it exists to fire can then never fire at all.
_RIGGED_CHECK = re.compile(
    r"""(?:
          \b(?:run|gate|check|suite)\w*[^.;]{0,80}?
          (?:\bunstaged\b | \buntracked\b | \bas\s+it\s+stands\b
            | \bthe\s+tip\s+of\b | \bevery\s+card\s+reports\b
            | \balways\s+(?:red|fail\w*)\b)
        | (?:\bunstaged\b | \buntracked\b | \bas\s+it\s+stands\b
            | \bthe\s+tip\s+of\b | \bevery\s+card\s+reports\b
            | \balways\s+(?:red|fail\w*)\b)
          [^.;]{0,80}?\b(?:run|gate|check|suite)\w*
    )""",
    re.IGNORECASE | re.VERBOSE,
)
# And what the check has to be pointed at. A run named with no input is a run
# anybody can aim elsewhere; naming the new test files is what makes it load
# the file whose emptiness this whole step exists to catch.
_TESTS_AS_INPUT = re.compile(
    r"\bnew\s+tests?\b|\btests?\s+files?\b|\btests?\s+just\s+(?:written|added)\b",
    re.IGNORECASE,
)

# The stated order rather than the printed one: a sentence that puts the run in
# front of the commit. Page position is satisfied by parking the words high in
# the section, which is not the document telling anyone which comes first.
_GATE_BEFORE_COMMIT = re.compile(
    r"""(?:
          \brun\w*[^.;]{0,80}?\bbefore\b[^.;]{0,60}?\bcommit\w*
        | \bbefore\b[^.;]{0,60}?\bcommit\w*[^.;]{0,80}?\brun\w*
    )""",
    re.IGNORECASE | re.VERBOSE,
)
# One reword per limb of the first rule: a green suite waved through, and the
# commit moved back in front of the check that would have caught it. A suite is
# waved through in the words of whoever writes it - green, passing, "moves on
# to Implement whatever the tests say" - so the trigger is matched by all three
# spellings; and the plainest wrong order carries no `before` at all, which is
# why `commit ... then run` is its own limb.
_GREEN_WAVED_THROUGH = re.compile(
    r"""(?:
          \b(?:green|passes|passing)\b[^.;]{0,120}?
          \b(?:continue|proceed|carry\s+on|fine|harmless|ok|okay
             |moves?\s+on|goes?\s+on|whatever\s+the\s+tests\s+say)\b
        | \b(?:continue|proceed|carry\s+on|moves?\s+on|goes?\s+on)\b
          [^.;]{0,120}?\b(?:green|passes|passing)\b
    )""",
    re.IGNORECASE | re.VERBOSE,
)
_COMMIT_FIRST = re.compile(
    r"""(?:
          \bcommit\w*[^.;]{0,60}?\bbefore\b[^.;]{0,40}?\b(?:gate|run)\w*
        | \bcommit\w*[^.;]{0,60}?\bthen\b[^.;]{0,40}?\brun\b
        | \bcommit\s+(?:them|it|the\s+tests?)\s+first\b
        | \bfirst\s+commit\s+the\s+tests?\b
    )""",
    re.IGNORECASE | re.VERBOSE,
)

# The second rule's two escapes: the reviewers going out over a red gate, and
# the gate being given another go. `_NO_REVIEWER` carries its own negation, so
# the pin below reads it directly rather than through `_assert_live`, whose
# instruction test asks for no negator in front of the verb - the one shape a
# rule about nothing being dispatched can never take.
_NO_REVIEWER = re.compile(
    r"""(?:
          \bno\s+(?:reviewer|review|roster|lens|lenses|lane)\w*
        | \b(?:reviewer|roster|lens|lenses|lane)\w*[^.;]{0,40}?
          \b(?:is|are|go|goes)\s+(?:not|never)\b
        | \b(?:never|not|no)\b[^.;]{0,30}?\bdispatch\w*
        | \bskip\w*\s+the\s+(?:roster|review\w*|lenses)\b
    )""",
    re.IGNORECASE | re.VERBOSE,
)
# The slug and the word behind it. Matched on the slug alone the ban sees only
# a document that spells `autopilot:ivan` out; "dispatch a fresh implementor"
# names the same agent, sends the same prompt, and reads to the operator as the
# same instruction, so the word has to be banned beside the slug.
_IVAN = re.compile(r"autopilot:ivan|\bimplementor\b", re.IGNORECASE)
# The symmetric half of the no-reviewer promise. A sentence saying nobody
# denies the roster its early start keeps every pinned word and still sends
# five lenses at a change the gate already rejected.
_ROSTER_DISPATCHED = re.compile(
    r"""(?:
          \bsend\w*[^.;]{0,40}?\b(?:lenses|roster|reviewers?)\b
        | \broster\b[^.;]{0,30}?\bgoes\s+out\b
    )""",
    re.IGNORECASE | re.VERBOSE,
)
# Permission written as a denial. "Nothing in this section stops you sending a
# fresh implementor in" reads as negated to every polarity check - the negator
# governs the sentence from the front, so the mention it authorises is exempt -
# and the reader dispatches all the same. The frame itself is the drift.
_WAIVED = re.compile(
    r"""\b(?:nothing|nobody|none|no\s+\w+)\b[^.;]{0,40}?
        \b(?:blocks?|stops?|prevents?|forbids?|bars?|claims?)\b""",
    re.IGNORECASE | re.VERBOSE,
)
_GATE_RETRY = re.compile(
    r"""(?:
          \bre-?run\b | \bre-?render\b | \bre-?try\b | \bretries\b
        | \b(?:run|render|dispatch|send)\w*[^.;]{0,40}?\bagain\b
        | \bfrom\s+the\s+top\b | \bonce\s+more\b
        | \b(?:second|another)\s+(?:attempt|pass|try|round|implementor)\b
        | \bhand\w*\s+(?:it|the\s+item|the\s+card)\s+back\b
        | \bback\s+to\s+the\s+implementor\b
        | \bas\s+often\s+as\b
        | \b(?:walk|start|work)\w*[^.;]{0,30}?\bover\b
    )""",
    re.IGNORECASE | re.VERBOSE,
)
# The same ban stated positively, because a list of spellings loses this race:
# "evaluate the card's gate list top to bottom a further time" is a rerun in
# words `_GATE_RETRY` does not hold, and the next paraphrase will be different
# again. A retry has to name something to send - a dispatch, an implementor,
# the allowlist it goes out with - so the section is pinned to send nothing at
# all, and the whole class fails rather than the wordings somebody predicted.
_GATE_SENDS = re.compile(
    r"\bdispatch\w*|\bimplementor\b|\ballowlist\b",
    re.IGNORECASE,
)
# The roster's escape from this section: the sentence sending five lenses over
# a red gate reads the same wherever it is printed, so it simply moves one
# heading down and no section-scoped pin ever sees it. Read over the whole body
# for that reason - a gate the document declares irrelevant is not a gate.
_GATE_IRRELEVANT = re.compile(
    r"""(?:
          \b(?:whether|regardless|irrespective|no\s+matter)\b[^.;]{0,60}?\bgate
        | \bgate\w*[^.;]{0,80}?\b(?:clean|green|passed|passing)\s+or\s+red\b
        | \b(?:clean|green|passed|passing)\s+or\s+red\b[^.;]{0,80}?\bgate\w*
        | \bred\s+or\s+(?:clean|green|passed|passing)\b
    )""",
    re.IGNORECASE | re.VERBOSE,
)


def test_a_green_red_check_stops_the_item() -> None:
    # A suite that is already green pins nothing. Run after the commit, its
    # emptiness surfaces with an implementor already at work; never run at all,
    # a vacuous test file becomes the item's whole spec.
    tests = _section("Tests")
    # In prose, and in a sentence that names the green result the string
    # answers to: a fence reads the literal as a `key: value` field and hands
    # it over as pasteable text, so the outcome can sit in a ```text block
    # under a paragraph calling it report vocabulary while no branch anywhere
    # reports it.
    stop = _assert_live(
        [
            passage
            for passage in tests
            if not passage.is_code and _GREEN_STOP.search(passage.text)
        ],
        _GREEN_STOP,
        missing=(
            "the tests section never says in prose that a green suite stops "
            f"the item with `{_GREEN_OUTCOME}`. Fenced on its own the literal "
            "is a string to copy into a report; the rule is the sentence "
            "naming what fires it, and without that sentence a suite passing "
            "before a line of the item exists flows straight on to the "
            "implementor."
        ),
        cancelled=(
            f"`{_GREEN_OUTCOME}` sits in the tests section as an outcome the "
            "lane no longer reports."
        ),
    )
    # Polarity, as every sibling pin runs it: "a green suite stops the item"
    # and "nobody stops an item over a green suite" carry the same words.
    assert any(
        _asserted(sentence, _GREEN_STOP)
        for passage in stop
        for sentence in _sentences_carrying(passage.text, _GREEN_STOP)
    ), (
        f"{_SKILL_MD}: every sentence tying a green suite to `{_GREEN_OUTCOME}` "
        "is governed by a negator, so the tests section names the stop only to "
        "deny it and the item carries on with a suite that pins nothing."
    )
    red_check = _assert_live(
        [
            passage
            for passage in tests
            if not passage.is_code and _FIRST_GATE.search(passage.text)
        ],
        _FIRST_GATE,
        missing=(
            "the tests section never tells the reader in prose to run the "
            "card's first `## Gates` line, so nothing here shows the new tests "
            "failing before they are committed as the item's spec."
        ),
        cancelled="the tests section names the red check only to say it is skipped.",
    )
    # The red check has to execute the suite. A search over the staged card, a
    # `git log`, a collect-only pass: each names the gate, exits zero whatever
    # the tests would have done, and reports nothing about a vacuous test file.
    searching = sorted(
        {passage.text for passage in red_check if _SEARCH_ONLY.search(passage.text)},
    )
    assert not searching, (
        f"{_SKILL_MD}: the tests section's red check searches instead of "
        f"running: {searching[:3]}. A grep over the card exits zero whatever "
        "the suite does, so the one check standing between a test file that "
        "pins nothing and the implementor reports on nothing."
    )
    # And it has to load the new tests. A run named with no input is a run
    # anybody can aim at the tip of `HEAD`, where the file being checked does
    # not exist yet: red on every card, and the green stop never fires.
    pointed = [
        passage
        for passage in red_check
        if any(
            _asserted(sentence, _TESTS_AS_INPUT)
            for sentence in _sentences_carrying(passage.text, _FIRST_GATE)
        )
    ]
    assert pointed, (
        f"{_SKILL_MD}: no sentence naming the card's first `## Gates` line says "
        "it runs the new test files. A check with no named input is one the "
        "next reader points at the committed tree, where the new tests are not "
        "yet present - it comes back red on every card, and a vacuous test file "
        "passes the step that exists to catch it."
    )
    # Ordering as a stated rule, not as page position: a first-gate mention
    # parked above the commit satisfies an index comparison while the document
    # never tells anyone which of the two comes first.
    ordered = [
        passage
        for passage in red_check
        if any(
            _asserted(sentence, _GATE_BEFORE_COMMIT)
            for sentence in _sentences_carrying(passage.text, _FIRST_GATE)
        )
    ]
    assert ordered, (
        f"{_SKILL_MD}: no sentence naming the card's first `## Gates` line puts "
        "that run before the test commit - the section never says to run it "
        "before the tests are committed. Run afterwards, the red check reports "
        "on a spec that is already committed and already handed on."
    )
    # Position on top of the stated rule: run after the commit the check still
    # happens, and still catches nothing in time - the tests are the spec by
    # then. The passages carrying the red check are not counted as the commit
    # step: the sentence above has to name the commit to order itself against
    # it, and a passage that puts the commit first is caught by `ordered` and
    # by `_COMMIT_FIRST` rather than by where it sits on the page.
    ran_at = min(index for index, passage in enumerate(tests) if passage in red_check)
    committed = [
        index
        for index, passage in enumerate(tests)
        if _TEST_COMMIT.search(passage.text) and passage not in red_check
    ]
    assert committed, (
        f"{_SKILL_MD}: the tests section never commits the tests, so the item "
        "has no spec to hand on and the red check has nothing to run in front "
        "of."
    )
    assert ran_at < min(committed), (
        f"{_SKILL_MD}: the tests section commits the tests before it runs the "
        "card's first gate. A red check run afterwards reports on a spec that "
        "is already committed and already handed on."
    )
    _assert_unopposed(
        tests,
        _GREEN_WAVED_THROUGH,
        "the tests section waves a green suite through instead of stopping the "
        "item, somewhere in the section:",
    )
    _assert_unopposed(
        tests,
        _COMMIT_FIRST,
        "the tests section puts the commit in front of the red check, somewhere "
        "in the section:",
    )
    _assert_unopposed(
        tests,
        _RIGGED_CHECK,
        "the tests section rigs the red check to a fixed answer - run from the "
        "tip of HEAD, with the new tests unstaged and untracked, red on every "
        "card - somewhere in the section:",
    )


def test_a_red_gate_stops_the_item_with_no_retry_and_no_reviewer() -> None:
    # The gates are the item's own definition of done. Given a retry they are a
    # suggestion, and a roster sent out over a red gate spends five lenses on a
    # change the operator already knows is broken.
    gates = _section("Gates")
    # In prose, and in a sentence naming the non-zero exit it answers to. The
    # bare literal in a ```text fence is a `key: value` field to any reader
    # model, which is how a document keeps the outcome string while the
    # paragraph above it calls the string report vocabulary and the procedure
    # below it hands the item back to the implementor.
    stop = _assert_live(
        [
            passage
            for passage in gates
            if not passage.is_code and _GATE_STOP.search(passage.text)
        ],
        _GATE_STOP,
        missing=(
            "the gates section never says in prose that a gate exiting "
            f"non-zero stops the item with `{_GATE_OUTCOME} <n>`. An outcome "
            "string with no sentence naming what fires it is report "
            "vocabulary, and the reader carries on to the roster."
        ),
        cancelled=(
            f"`{_GATE_OUTCOME} <n>` sits in the gates section as an outcome "
            "nothing records."
        ),
    )
    assert any(
        _asserted(sentence, _GATE_STOP)
        for passage in stop
        for sentence in _sentences_carrying(passage.text, _GATE_STOP)
    ), (
        f"{_SKILL_MD}: every sentence tying a non-zero gate to "
        f"`{_GATE_OUTCOME} <n>` is governed by a negator, so the section names "
        "the stop only to deny it and a red gate stops nothing."
    )
    # Polarity here too, and in prose: "no reviewer is dispatched" is the rule,
    # "nobody here claims no reviewer waits for a green gate" is the same words
    # granting the opposite, and a fenced English sentence is neither.
    refused = [
        sentence.strip()
        for passage in gates
        if not passage.is_code
        for sentence in _sentences_carrying(passage.text, _NO_REVIEWER)
        if _asserted(sentence, _NO_REVIEWER)
    ]
    assert refused, (
        f"{_SKILL_MD}: the gates section never says, unopposed, that no "
        "reviewer is dispatched when a gate fails. Silence reads as the roster "
        "going out anyway, and five lenses then review a change its own gate "
        "rejected."
    )
    # The symmetric guard: saying no reviewer goes out is worth nothing beside
    # a sentence sending the lenses in while the gate list runs.
    _assert_unopposed(
        gates,
        _ROSTER_DISPATCHED,
        "the gates section sends the roster out over a gate it has not passed, "
        "somewhere in the section:",
    )
    # `_asserted` rather than a whole-sentence negator search: a negator
    # anywhere used to exempt the mention, so "the gate hands the item back to
    # `autopilot:ivan`, never to a reviewer" read as a ban on both.
    dispatched = sorted(
        {
            sentence.strip()
            for passage in gates
            for sentence in _sentences_carrying(passage.text, _IVAN)
            if _asserted(sentence, _IVAN)
        },
    )
    assert not dispatched, (
        f"{_SKILL_MD}: the gates section dispatches `autopilot:ivan` over a red "
        f"gate: {dispatched[:3]}. A gate that hands the item back to an "
        "implementor is not a stop, and the implementor it hands to writes to "
        "the gate rather than to the card."
    )
    # And the shape no polarity check can see: a permission written as a
    # denial. "Nothing in this section stops you sending a fresh implementor
    # in" negates from the front, exempting the very dispatch it authorises.
    _assert_unopposed(
        gates,
        _WAIVED,
        "the gates section waives its own stop - nothing here blocks, nobody "
        "claims - somewhere in the section:",
    )
    _assert_unopposed(
        gates,
        _GATE_RETRY,
        "the gates section gives a red gate another go - rerun, re-render, hand "
        "it back, walk the list over - somewhere in the section:",
    )
    # The same ban from the other side. `_GATE_RETRY` lists the wordings a
    # rerun has worn so far; this asks that nothing goes out from here at all,
    # which is the one thing every retry needs however it is phrased.
    _assert_unopposed(
        gates,
        _GATE_SENDS,
        "the gates section still sends something out - a dispatch, an "
        "implementor, an allowlist to hand it - and a stop that dispatches is "
        "not a stop:",
    )
    # Document-wide, because the sentence that sends the roster over a red gate
    # reads the same under any heading: scoped to this section it just moves
    # down to the roster, where no pin about gates would ever look at it.
    _assert_unopposed(
        list(_passages()),
        _GATE_IRRELEVANT,
        "the body declares the gate list irrelevant to the roster - whether it "
        "came back clean or red, regardless of the gates - somewhere on the "
        "page:",
    )


# The two reference documents the driver sends a reader to. Resolved from this
# file, never from the working directory, so the suite says the same thing from
# the repo root and from here. A missing document is a failure, never a skip.
_REFERENCES = Path(__file__).resolve().parent.parent / "references"
_SPEC_CARD_MD = _REFERENCES / "spec-card.md"
_LANE_DISPATCH_MD = _REFERENCES / "lane-dispatch.md"

# The real parser, loaded from beside this file: these scripts are not an
# installed package, so `card.py` comes in the same way the reader model does.
_CARD_PATH = Path(__file__).with_name("card.py")
_CARD_SPEC = importlib.util.spec_from_file_location("fast_track_card_pins", _CARD_PATH)
assert _CARD_SPEC is not None and _CARD_SPEC.loader is not None
_card = importlib.util.module_from_spec(_CARD_SPEC)
# Registered before exec_module, and under a name of this file's own: a module
# built with `from __future__ import annotations` and @dataclass looks itself up
# in sys.modules while it imports, and test_card.py registers the parser too.
sys.modules[_CARD_SPEC.name] = _card
_CARD_SPEC.loader.exec_module(_card)

_Card = _card.Card
_CardError = _card.CardError
_load_card = _card.load_card
_Passage = _testutil.Passage

# The vocabulary a reference has to teach, read out of the parser at runtime: a
# list copied into this file is a second contract that drifts on the next field.
_VOCABULARY = (*_card._SECTIONS, *_card._MODELS, *_card._SUITES)

# Fences of three backticks or more, so a card wrapped in a longer fence to
# carry its own snippets is read whole instead of cut at the first inner fence.
_FENCE = re.compile(
    r"^(?P<ticks>`{3,})[^\n]*\n(?P<body>.*?)^(?P=ticks)[ \t]*$",
    re.MULTILINE | re.DOTALL,
)
# An HTML comment renders nowhere, so a kind or a rule written inside one is
# documented for nobody. Both references are read with the comments gone.
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_FENCE_LINE = re.compile(r"^ {0,3}(?:```|~~~)")


def _copyable_lines(text: str) -> list[str]:
    """The fenced lines an operator could select and paste.

    The testutil's reader model is wired to SKILL.md through its own
    `document()`, so the walk is local and only the pasteable bar is shared.
    """
    found: list[str] = []
    in_code = False
    for line in text.splitlines():
        if _FENCE_LINE.match(line):
            in_code = not in_code
        elif in_code and line.strip():
            found.extend(_code_fragments(_Passage((), line.strip(), True)))
    return found


def _lifted_from_fixture(block: str) -> str:
    """The parser fixture this block is a copy of, whitespace ignored."""
    wanted = " ".join(block.split())
    for fixture in sorted(Path(__file__).with_name("fixtures").glob("*.md")):
        if " ".join(fixture.read_text(encoding="utf-8").split()) == wanted:
            return fixture.name
    return ""


# The card is picked out by its own shape - a `---` block on top, `## ` sections
# under it - and never by where it sits on the page, so a paragraph or a command
# line added above the example does not quietly move the pin to another block.
_CARD_SHAPE = re.compile(r"---\n.*?^## ", re.MULTILINE | re.DOTALL)
_DECLARED_ITEM = re.compile(r"^item:[ \t]*(\S+)[ \t]*$", re.MULTILINE)
# What a reader can learn from, counted in words and in path-shaped names: one
# character satisfies a non-empty string, and the example is copied whole.
_MIN_GOAL_WORDS = 12
_MIN_EXAMPLE_FILES = 2
_REAL_PATH = re.compile(r"\S*[/.]\w+$")

_NO_SPEC_CARD = (
    f"{_SPEC_CARD_MD} is gone. The card is the lane's only input, and with no "
    "format to copy a reader writes one from memory for a parser that answers "
    "a field name and exit 2."
)
_NO_LOADABLE_EXAMPLE = (
    f"{_SPEC_CARD_MD}: no fenced block in the document loads as a card "
    "({blocks} fenced block(s) read, refusals: {refusals}). An example the real "
    "parser throws back teaches every reader the one card the lane will not take."
)
_EXAMPLE_WITHOUT_ITEM = (
    f"{_SPEC_CARD_MD}: the example that parsed declares no `item:` line to read "
    "back, so nothing here shows the parse came from the document rather than "
    "from some other block on the page."
)
_ITEM_DRIFTED = (
    f"{_SPEC_CARD_MD}: the parsed card carries item {{item!r}} while the example "
    "declares {declared!r}. The block under test is not the one on the page."
)
_LIFTED_EXAMPLE = (
    f"{_SPEC_CARD_MD}: the worked example is a copy of {{fixture!r}} from the "
    "parser's fixtures, and those are bent into refusals whenever a parser test "
    "needs one. The reference then teaches whatever a test needed last."
)
_THIN_EXAMPLE = (
    f"{_SPEC_CARD_MD}: the example is a shell, not a worked card ({{words}} "
    "word(s) of goal, {paths} named as files). A reader copies the example "
    "whole, so a one-word goal and a file called `x` shape every card after it."
)
_UNTAUGHT = (
    f"{_SPEC_CARD_MD}: the prose around the example never names {{untaught}}, "
    "read out of `card.py` as the vocabulary it takes. A page that shows a card "
    "and teaches no field leaves one shape to copy and nothing to change, and "
    "prose that teaches some other model is answered with exit 2."
)


def test_reference_card_example_loads(tmp_path: Path) -> None:
    # A card the document shows and the parser refuses is worse than no example
    # at all, so the example goes through `load_card`, and the prose around it
    # is read against the parser rather than against memory.
    assert _SPEC_CARD_MD.is_file(), _NO_SPEC_CARD
    text = _HTML_COMMENT.sub(" ", _SPEC_CARD_MD.read_text(encoding="utf-8"))
    blocks = [match.group("body") for match in _FENCE.finditer(text)]
    shaped = [block for block in blocks if _CARD_SHAPE.match(block)]
    parsed = None
    loaded = ""
    refusals: list[str] = []
    for index, block in enumerate(shaped):
        example = tmp_path / f"example-{index}.md"
        example.write_text(block, encoding="utf-8")
        try:
            parsed = _load_card(example)
        except _CardError as refusal:
            refusals.append(str(refusal))
            continue
        loaded = block
        break
    assert isinstance(parsed, _Card), _NO_LOADABLE_EXAMPLE.format(
        blocks=len(blocks),
        refusals=refusals,
    )
    declared = _DECLARED_ITEM.search(loaded)
    assert declared is not None, _EXAMPLE_WITHOUT_ITEM
    assert parsed.item == declared.group(1), _ITEM_DRIFTED.format(
        item=parsed.item,
        declared=declared.group(1),
    )
    lifted = _lifted_from_fixture(loaded)
    assert not lifted, _LIFTED_EXAMPLE.format(fixture=lifted)
    words = len(parsed.goal.split())
    paths = [name for name in parsed.files if _REAL_PATH.fullmatch(name)]
    assert words >= _MIN_GOAL_WORDS and len(paths) >= _MIN_EXAMPLE_FILES, (
        _THIN_EXAMPLE.format(words=words, paths=paths)
    )
    prose = _FENCE.sub(" ", text).lower()
    untaught = [term for term in _VOCABULARY if term.lower() not in prose]
    assert not untaught, _UNTAUGHT.format(untaught=untaught)


# The eight kinds the lane dispatches under. The reference documents conditional
# lanes too (`fast-track:tess`, `fast-track:alice`), so the pin asks that these
# eight are present and never that the document names only these.
_LANE_KINDS = tuple(
    f"fast-track:{lane}"
    for lane in ("ivan", "fanout", "blake", "eve", "bob", "carl", "victor", "delta")
)
# The call that opens the row, matched apart from the flag so the two can be
# written in either order. A kind counts as documented when one pasteable line
# carries both; named anywhere else it is a word on a page.
_LEDGER_CALL = "record_dispatch.py"
_NO_LANE_REFERENCE = (
    f"{_LANE_DISPATCH_MD} is gone, and every lane's command block went with it. "
    "A dispatch assembled from memory goes out with the wrong inputs and no row "
    "to show for it."
)
_MISSING_KINDS = (
    f"{_LANE_DISPATCH_MD}: no line an operator could paste names {{missing}} "
    "beside `record_dispatch.py`. A kind carried only by prose, or by an HTML "
    "comment that renders nowhere, is a lane dispatched from guesswork and a "
    "ledger row nobody knows to open."
)
_KINDS_RETIRED = (
    f"{_LANE_DISPATCH_MD}: the reference takes its own kinds back: {{retired}}. "
    "A block called retired, historical or safe to disregard is one nobody runs."
)


def test_lane_reference_names_every_kind() -> None:
    # One command block per lane is what an operator reads before sending one.
    # A kind absent here is a lane dispatched from guesswork, or not at all.
    assert _LANE_DISPATCH_MD.is_file(), _NO_LANE_REFERENCE
    text = _HTML_COMMENT.sub(" ", _LANE_DISPATCH_MD.read_text(encoding="utf-8"))
    dispatched = {
        kind
        for line in _copyable_lines(text)
        for kind in _LANE_KINDS
        if _LEDGER_CALL in line and f"--kind {kind}" in line
    }
    missing = [kind for kind in _LANE_KINDS if kind not in dispatched]
    assert not missing, _MISSING_KINDS.format(missing=missing)
    retired = sorted(
        sentence.strip()
        for sentence in _sentences_carrying(text, "fast-track:")
        if any(pattern.search(sentence) for pattern in _CANCELS)
    )
    assert not retired, _KINDS_RETIRED.format(retired=retired[:3])
