"""The two stop rules the fast-track pins read for, and the complaints they raise.

Split out of test_fast_track_prose.py to keep both files under the file size
limit; the two pins themselves stay there. Same division as the reader model in
fast_track_prose_testutil.py, which this module reads the document through: the
vocabulary and the reasoning behind it live here, so each pin stays one readable
run down the page.
"""

from __future__ import annotations

import importlib.util
import re
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
_Passage = _testutil.Passage


def prose_matching(
    candidates: list[_Passage],
    pattern: re.Pattern[str],
) -> list[_Passage]:
    """The passages carrying `pattern` that a reader reads rather than copies.

    An outcome string is a rule only where the document says what fires it. A
    fence reads `stopped: <anything>` as a `key: value` field, so the literal
    parked alone in a ```text block is pasteable text that skips the verb and
    polarity machinery entirely, while the paragraph above it calls the string
    report vocabulary and disowns it for free.
    """
    return [
        passage
        for passage in candidates
        if not passage.is_code and pattern.search(passage.text)
    ]


def stating(
    candidates: list[_Passage],
    probe: str | re.Pattern[str],
    rule: re.Pattern[str],
) -> list[_Passage]:
    """The passages whose sentence carrying `probe` asserts `rule`.

    One sentence rather than one passage: a rule stated in the paragraph next
    door is a coincidence of words. And polarity, as every sibling pin runs it -
    "a green suite stops the item" and "nobody stops an item over a green suite"
    carry the same words, and only one of them is the rule.
    """
    return [
        passage
        for passage in candidates
        if any(
            _testutil.asserted(sentence, rule)
            for sentence in _testutil.sentences_carrying(passage.text, probe)
        )
    ]


# The two stop rules, each a full halt carrying its own outcome string. The
# string is what the ledger row and the report end up holding, and "the item
# stopped" is indistinguishable from a lane that fell over; a phrase nobody else
# writes says which rule fired, and at which step.
_GREEN_OUTCOME = "stopped: tests-green-before-implementation"
_GATE_OUTCOME = "stopped: gate"

# Each outcome is pinned to a prose sentence naming its own trigger - the green
# suite, the non-zero gate - and a fenced copy counts as a convenience beside
# that sentence, never as the promise.
_GREEN_TRIGGER = r"\b(?:green|passes|passing)\b"
_GATE_TRIGGER = r"(?:\bnon-?zero\b|\bred\b|\bfail\w*)"
GREEN_STOP = re.compile(
    rf"{_GREEN_TRIGGER}[^.!?]{{0,200}}?{re.escape(_GREEN_OUTCOME)}"
    rf"|{re.escape(_GREEN_OUTCOME)}[^.!?]{{0,200}}?{_GREEN_TRIGGER}",
    re.IGNORECASE,
)
GATE_STOP = re.compile(
    rf"{_GATE_TRIGGER}[^.!?]{{0,200}}?{re.escape(_GATE_OUTCOME)}"
    rf"|{re.escape(_GATE_OUTCOME)}[^.!?]{{0,200}}?{_GATE_TRIGGER}",
    re.IGNORECASE,
)

NO_GREEN_STOP = (
    "the tests section never says in prose that a green suite stops "
    f"the item with `{_GREEN_OUTCOME}`. Fenced on its own the literal "
    "is a string to copy into a report; the rule is the sentence "
    "naming what fires it, and without that sentence a suite passing "
    "before a line of the item exists flows straight on to the "
    "implementor."
)
GREEN_STOP_CANCELLED = (
    f"`{_GREEN_OUTCOME}` sits in the tests section as an outcome the "
    "lane no longer reports."
)
GREEN_STOP_DENIED = (
    f"{_SKILL_MD}: every sentence tying a green suite to `{_GREEN_OUTCOME}` "
    "is governed by a negator, so the tests section names the stop only to "
    "deny it and the item carries on with a suite that pins nothing."
)
NO_GATE_STOP = (
    "the gates section never says in prose that a gate exiting "
    f"non-zero stops the item with `{_GATE_OUTCOME} <n>`. An outcome "
    "string with no sentence naming what fires it is report "
    "vocabulary, and the reader carries on to the roster."
)
GATE_STOP_CANCELLED = (
    f"`{_GATE_OUTCOME} <n>` sits in the gates section as an outcome "
    "nothing records."
)
GATE_STOP_DENIED = (
    f"{_SKILL_MD}: every sentence tying a non-zero gate to "
    f"`{_GATE_OUTCOME} <n>` is governed by a negator, so the section names "
    "the stop only to deny it and a red gate stops nothing."
)

# The red check: the card's first `## Gates` line, run against the new tests
# while nothing implements them yet. Named by position or by number, whichever
# the document prefers.
FIRST_GATE = re.compile(
    r"""(?:
          \bfirst\b[^.;]{0,40}?\bgates?\b
        | \bgates?\b[^.;]{0,20}?\bfirst\b
        | \bgate\s*1\b
    )""",
    re.IGNORECASE | re.VERBOSE,
)
TEST_COMMIT = re.compile(r"\bcommit\w*", re.IGNORECASE)

NO_RED_CHECK = (
    "the tests section never tells the reader in prose to run the "
    "card's first `## Gates` line, so nothing here shows the new tests "
    "failing before they are committed as the item's spec."
)
RED_CHECK_CANCELLED = (
    "the tests section names the red check only to say it is skipped."
)

# A check that only looks. `rg` over the staged card, a `git log`, a
# collect-only or dry-run pass: each one names the gate, exits zero whatever
# the suite would have done, and proves nothing about a test file that pins
# nothing.
SEARCH_ONLY = re.compile(
    r"""(?:
          (?:^|[\s`("'])(?:rg|grep|ack|ag)\b
        | \bgit\s+(?:log|grep)\b
        | --collect-only\b | --dry-run\b | --fixed-strings\b
    )""",
    re.IGNORECASE | re.VERBOSE,
)
SEARCHING_CHECK = (
    f"{_SKILL_MD}: the tests section's red check searches instead of "
    "running: {found}. A grep over the card exits zero whatever "
    "the suite does, so the one check standing between a test file that "
    "pins nothing and the implementor reports on nothing."
)

# A check rigged to come back red whatever the tests hold. Banning the search
# tools closes one shape and leaves the other open: the run is real, and aimed
# away from the new tests - at the tip of `HEAD`, or at a tree where the test
# file is still unstaged and untracked. Red on every card is a formality, not a
# check, and the green stop it exists to fire can then never fire at all.
RIGGED_CHECK = re.compile(
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
RIGGED = (
    "the tests section rigs the red check to a fixed answer - run from the "
    "tip of HEAD, with the new tests unstaged and untracked, red on every "
    "card - somewhere in the section:"
)

# And what the check has to be pointed at. A run named with no input is a run
# anybody can aim elsewhere; naming the new test files is what makes it load
# the file whose emptiness this whole step exists to catch.
TESTS_AS_INPUT = re.compile(
    r"\bnew\s+tests?\b|\btests?\s+files?\b|\btests?\s+just\s+(?:written|added)\b",
    re.IGNORECASE,
)
UNAIMED_CHECK = (
    f"{_SKILL_MD}: no sentence naming the card's first `## Gates` line says "
    "it runs the new test files. A check with no named input is one the "
    "next reader points at the committed tree, where the new tests are not "
    "yet present - it comes back red on every card, and a vacuous test file "
    "passes the step that exists to catch it."
)

# The stated order rather than the printed one: a sentence that puts the run in
# front of the commit. Page position is satisfied by parking the words high in
# the section, which is not the document telling anyone which comes first.
GATE_BEFORE_COMMIT = re.compile(
    r"""(?:
          \brun\w*[^.;]{0,80}?\bbefore\b[^.;]{0,60}?\bcommit\w*
        | \bbefore\b[^.;]{0,60}?\bcommit\w*[^.;]{0,80}?\brun\w*
    )""",
    re.IGNORECASE | re.VERBOSE,
)
UNORDERED_CHECK = (
    f"{_SKILL_MD}: no sentence naming the card's first `## Gates` line puts "
    "that run before the test commit - the section never says to run it "
    "before the tests are committed. Run afterwards, the red check reports "
    "on a spec that is already committed and already handed on."
)

# Position on top of the stated rule: run after the commit the check still
# happens, and still catches nothing in time - the tests are the spec by then.
TESTS_UNCOMMITTED = (
    f"{_SKILL_MD}: the tests section never commits the tests, so the item "
    "has no spec to hand on and the red check has nothing to run in front "
    "of."
)
COMMITTED_FIRST = (
    f"{_SKILL_MD}: the tests section commits the tests before it runs the "
    "card's first gate. A red check run afterwards reports on a spec that "
    "is already committed and already handed on."
)

# One reword per limb of the first rule: a green suite waved through, and the
# commit moved back in front of the check that would have caught it. A suite is
# waved through in the words of whoever writes it - green, passing, "moves on
# to Implement whatever the tests say" - so the trigger is matched by all three
# spellings; and the plainest wrong order carries no `before` at all, which is
# why `commit ... then run` is its own limb.
GREEN_WAVED_THROUGH = re.compile(
    r"""(?:
          \b(?:green|passes|passing)\b[^.;]{0,120}?
          \b(?:continue|proceed|carry\s+on|fine|harmless|ok|okay
             |moves?\s+on|goes?\s+on|whatever\s+the\s+tests\s+say)\b
        | \b(?:continue|proceed|carry\s+on|moves?\s+on|goes?\s+on)\b
          [^.;]{0,120}?\b(?:green|passes|passing)\b
    )""",
    re.IGNORECASE | re.VERBOSE,
)
WAVED_THROUGH = (
    "the tests section waves a green suite through instead of stopping the "
    "item, somewhere in the section:"
)
COMMIT_FIRST = re.compile(
    r"""(?:
          \bcommit\w*[^.;]{0,60}?\bbefore\b[^.;]{0,40}?\b(?:gate|run)\w*
        | \bcommit\w*[^.;]{0,60}?\bthen\b[^.;]{0,40}?\brun\b
        | \bcommit\s+(?:them|it|the\s+tests?)\s+first\b
        | \bfirst\s+commit\s+the\s+tests?\b
    )""",
    re.IGNORECASE | re.VERBOSE,
)
COMMIT_BEFORE_CHECK = (
    "the tests section puts the commit in front of the red check, somewhere "
    "in the section:"
)

# The second rule's two escapes: the reviewers going out over a red gate, and
# the gate being given another go. `NO_REVIEWER` carries its own negation, so
# the pin reads it directly rather than through `assert_live`, whose instruction
# test asks for no negator in front of the verb - the one shape a rule about
# nothing being dispatched can never take.
NO_REVIEWER = re.compile(
    r"""(?:
          \bno\s+(?:reviewer|review|roster|lens|lenses|lane)\w*
        | \b(?:reviewer|roster|lens|lenses|lane)\w*[^.;]{0,40}?
          \b(?:is|are|go|goes)\s+(?:not|never)\b
        | \b(?:never|not|no)\b[^.;]{0,30}?\bdispatch\w*
        | \bskip\w*\s+the\s+(?:roster|review\w*|lenses)\b
    )""",
    re.IGNORECASE | re.VERBOSE,
)
NO_REFUSAL = (
    f"{_SKILL_MD}: the gates section never says, unopposed, that no "
    "reviewer is dispatched when a gate fails. Silence reads as the roster "
    "going out anyway, and five lenses then review a change its own gate "
    "rejected."
)

# The slug and the word behind it. Matched on the slug alone the ban sees only
# a document that spells `autopilot:ivan` out; "dispatch a fresh implementor"
# names the same agent, sends the same prompt, and reads to the operator as the
# same instruction, so the word has to be banned beside the slug.
IVAN = re.compile(r"autopilot:ivan|\bimplementor\b", re.IGNORECASE)
IVAN_DISPATCHED = (
    f"{_SKILL_MD}: the gates section dispatches `autopilot:ivan` over a red "
    "gate: {found}. A gate that hands the item back to an "
    "implementor is not a stop, and the implementor it hands to writes to "
    "the gate rather than to the card."
)

# The symmetric half of the no-reviewer promise. A sentence saying nobody
# denies the roster its early start keeps every pinned word and still sends
# five lenses at a change the gate already rejected.
ROSTER_DISPATCHED = re.compile(
    r"""(?:
          \bsend\w*[^.;]{0,40}?\b(?:lenses|roster|reviewers?)\b
        | \broster\b[^.;]{0,30}?\bgoes\s+out\b
    )""",
    re.IGNORECASE | re.VERBOSE,
)
ROSTER_OVER_RED = (
    "the gates section sends the roster out over a gate it has not passed, "
    "somewhere in the section:"
)

# Permission written as a denial. "Nothing in this section stops you sending a
# fresh implementor in" reads as negated to every polarity check - the negator
# governs the sentence from the front, so the mention it authorises is exempt -
# and the reader dispatches all the same. The frame itself is the drift.
WAIVED = re.compile(
    r"""\b(?:nothing|nobody|none|no\s+\w+)\b[^.;]{0,40}?
        \b(?:blocks?|stops?|prevents?|forbids?|bars?|claims?)\b""",
    re.IGNORECASE | re.VERBOSE,
)
STOP_WAIVED = (
    "the gates section waives its own stop - nothing here blocks, nobody "
    "claims - somewhere in the section:"
)

GATE_RETRY = re.compile(
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
GATE_RETRIED = (
    "the gates section gives a red gate another go - rerun, re-render, hand "
    "it back, walk the list over - somewhere in the section:"
)

# The same ban stated positively, because a list of spellings loses this race:
# "evaluate the card's gate list top to bottom a further time" is a rerun in
# words `GATE_RETRY` does not hold, and the next paraphrase will be different
# again. A retry has to name something to send - a dispatch, an implementor,
# the allowlist it goes out with - so the section is pinned to send nothing at
# all, and the whole class fails rather than the wordings somebody predicted.
GATE_SENDS = re.compile(
    r"\bdispatch\w*|\bimplementor\b|\ballowlist\b",
    re.IGNORECASE,
)
GATE_STILL_SENDS = (
    "the gates section still sends something out - a dispatch, an "
    "implementor, an allowlist to hand it - and a stop that dispatches is "
    "not a stop:"
)

# The roster's escape from this section: the sentence sending five lenses over
# a red gate reads the same wherever it is printed, so it simply moves one
# heading down and no section-scoped pin ever sees it. Read over the whole body
# for that reason - a gate the document declares irrelevant is not a gate.
GATE_IRRELEVANT = re.compile(
    r"""(?:
          \b(?:whether|regardless|irrespective|no\s+matter)\b[^.;]{0,60}?\bgate
        | \bgate\w*[^.;]{0,80}?\b(?:clean|green|passed|passing)\s+or\s+red\b
        | \b(?:clean|green|passed|passing)\s+or\s+red\b[^.;]{0,80}?\bgate\w*
        | \bred\s+or\s+(?:clean|green|passed|passing)\b
    )""",
    re.IGNORECASE | re.VERBOSE,
)
GATE_SIDELINED = (
    "the body declares the gate list irrelevant to the roster - whether it "
    "came back clean or red, regardless of the gates - somewhere on the "
    "page:"
)
