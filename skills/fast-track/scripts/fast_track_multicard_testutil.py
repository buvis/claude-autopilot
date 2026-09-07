"""The multi-card contract the fast-track driver has to state, and its reads.

Split out of test_fast_track_prose.py the way the two stop rules and the two
reference documents were: that file sits a few lines under its ceiling, so a new
pin's vocabulary, the complaints it raises and the read behind them live here,
each beside the reasoning for it.

The contract has three limbs, and they only hold together:

  * the lane takes more than one card and works them in the order the arguments
    give them,
  * a card whose `suite` is `batch` has its repo-wide suite run after the last
    item, not once per item,
  * `--push` pushes once, after that suite comes back green.

Drop the first and the other two have no last item to wait for. Drop either of
the others and a batch of five cards pays for five repo suites and pushes the
first three while the fourth is still red - which is the one failure a lane that
commits per item cannot walk back.

`unstated` is the read every pin here runs, and the order of its three answers
is the point: a rule never written, a rule the document takes back, and a rule
never stated as a rule are three different drifts, and an operator told only
"missing" goes looking for the wrong one.

Three moves a first draft of these pins let through, each closed below:

  * A fence is no proof, and neither is a pasteable line sitting somewhere on
    the page. The copyable limb reads the entry line the intro offers - the
    first pasteable `/autopilot:fast-track <card.md>` a reader meets - so a
    repeated form parked in a block the paragraph above it calls a usage error
    buys nothing.
  * Prose limbs are read one clause at a time, and the clause has to read as an
    instruction. One report-contents bullet ("the cards the run received, each
    gate in order with the exit code given by the command line it ran") carries
    three unrelated subjects across its commas and satisfied three of these
    rules at once.
  * The words have to be about the rule's own subject, which is what `context`
    demands: "a push that happens once, at that session's clean exit" is one
    push per session - the opposite of the rule, in the rule's own words.

Three more the next draft let through, closed the same way:

  * A copyable fragment is not the entry line. Every backtick span of a
    paragraph is one, and the intro paragraph is read before the block under
    it, so parser trivia in a span answered for a fence still showing one card.
    The copyable limb reads fenced pasteable lines only, and reads every copy:
    one single-card line anywhere is the line the operator selects.
  * Tokens are not a subject. Nothing tied `--push`, the last item and the
    green suite to THIS lane, so one paragraph about `/autopilot:run-autopilot`
    - the command the preconditions refuse to run under - satisfied three rules
    at once. `forbidden` drops a passage handed to another command.
  * A blacklist is one reword behind, always. `PER_ITEM_PUSH` never saw "pushed
    the moment that card's commit lands" and `CARD_IN_HAND_SUITE` never saw
    "its last gate runs the repo-wide suite over the paths that card names".
    `PINS` inverts both: say when, every time you say a push or the repo suite
    happens, and any per-card wording fails whatever vocabulary it invents.

The bans are read over the whole body rather than under `## Exit`, because a
sentence telling the reader to push at a per-item exit works exactly as well one
heading further down. That sentence is the finding these pins exist to keep out,
so it is matched as a class - now, after each item, per item, on every clean
exit - and never as the one wording that happened to be there. Beside it sit the
claims that contradict the contract while every pinned pattern stays satisfied:
one card per run, whatever order suits you, a repo suite run for the card in
hand, and the permission-as-denial frame ("nothing holds a push back for a later
card") that grants per-item pushing in the shape of a refusal.
"""

from __future__ import annotations

import importlib.util
import re
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

# The reader model and the stop-rule helpers, by path: these scripts are not an
# installed package, so a sibling comes in the way `card.py` does. Two of them
# here, so the spec dance runs in a loop rather than twice down the page.
_SIBLINGS = {}
for _name in ("fast_track_prose_testutil", "fast_track_stop_testutil"):
    _spec = importlib.util.spec_from_file_location(
        _name,
        Path(__file__).with_name(f"{_name}.py"),
    )
    assert _spec is not None and _spec.loader is not None
    _SIBLINGS[_name] = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_SIBLINGS[_name])

_testutil = _SIBLINGS["fast_track_prose_testutil"]
_stop = _SIBLINGS["fast_track_stop_testutil"]

_SKILL_MD = _testutil.SKILL_MD

# The gap every two-limb pattern below reaches across, and it refuses to span a
# negator. `asserted` only reads the head in front of a match, so a rule whose
# negator sits *inside* it - "the batch suite never runs after the last item" -
# reads as asserted, head and all. Tempered with the reader model's own negator
# list, the pattern simply does not match there, and the pin reports the rule as
# unstated instead of counting its denial as proof.
_GAP = f"(?:(?!{_testutil.NEGATOR.pattern})[^.;])"

# The same gap with the comma taken out, for the limbs whose two halves have to
# belong to one subject. A comma is where a bullet changes the subject without
# ending anything: "the cards the run received, each gate in order with the exit
# code given by the command line it ran" is three list items, and a gap that
# crosses commas reads them as one sentence about argument order.
_TIGHT = f"(?:(?!{_testutil.NEGATOR.pattern})[^.;,])"


class Rule(NamedTuple):
    """One documented promise, with the three ways a document can drop it.

    `probe` marks the copyable limb: set, the rule is read off the entry line
    an operator pastes, and `pattern` has to hold inside that same fragment.
    Empty, the rule is read off prose clauses, where the promise has to survive
    a cancelling frame, a negator, and the test for text that tells the reader
    to act rather than listing what a report holds.

    `context` is what the clause has to carry beside the pattern - the flag or
    the suite the rule is about. Right words, wrong subject is the drift it
    closes: a document can state a single push, a green suite and a last item
    on the page and attach none of them to `--push`.

    `forbidden` is the other half of that subject test, read over the whole
    passage rather than the clause: what the promise must not be about. Every
    token these rules ask for is satisfied by a paragraph describing some other
    driver - "`/autopilot:run-autopilot` takes a queue instead. There the batch
    suite runs once after the last item" - and the clause carrying the rule
    names nothing, because the command was named in the sentence before it.
    """

    pattern: re.Pattern[str]
    missing: str
    cancelled: str
    denied: str
    probe: str = ""
    context: tuple[re.Pattern[str], ...] = ()
    forbidden: tuple[re.Pattern[str], ...] = ()


# The repeated-argument shape. One card in the usage line is a lane an operator
# runs once per card - five sessions, five repo suites, five pushes - so the line
# has to show the argument repeating, either as `[<card.md> ...]` or as a bare
# ellipsis behind the first one.
REPEATED_CARD = re.compile(
    r"""<card\.md>\s*
        (?: \.\.\.
          | \[[^\]]*(?:<card\.md>|\.\.\.)[^\]]*\]
        )""",
    re.VERBOSE,
)

# Argument order, in the words a runbook uses for it. "In the order the card
# lists them" - which the gates section already says about gate lines - is
# deliberately not enough: the order pinned here is the one the operator typed,
# so the sentence has to reach for the arguments, the command line, or the act
# of giving them. Both limbs tie the order to something the lane does with the
# items, because a bullet listing what a report holds names cards, an order and
# a command line in one breath and means none of it. Both limbs, now: the second
# asked for the items and the order and no verb at all, so "the report names the
# cards in argument order" - a claim about a column, printed beside a lane that
# takes the shortest goal first - satisfied the rule about the running order.
_WORKS = r"\b(?:run|runs|process|processes|work|works)\b"
ARGUMENT_ORDER = re.compile(
    rf"""(?:
          {_WORKS}{_TIGHT}{{0,25}}?\b(?:items?|cards?)\b{_TIGHT}{{0,25}}?
          \bin\s+(?:the\s+)?order\b{_TIGHT}{{0,30}}?
          \b(?:argument|arguments|given|typed|passed|invocation
             |command\s+line)\b
        | {_WORKS}{_TIGHT}{{0,25}}?\b(?:items?|cards?)\b{_TIGHT}{{0,25}}?
          \bin\s+(?:the\s+)?(?:argument|command-line)\s+order\b
    )""",
    re.IGNORECASE | re.VERBOSE,
)

# The repo-wide suite, tied to the last item rather than to the last gate of
# whichever item is in hand. `batch` on its own is not the suite: it is a mode
# name, a row in a table and a word in "a batch of cards", so the suite has to
# be named as `suite: batch`, as the batch suite, or as the repo suite.
_BATCH_SUITE = r"(?:\bsuite:\s*`?batch\b|\bbatch\s+suite\b|\brepo(?:-wide)?\s+suite\b)"
_LAST_ITEM = r"\blast\s+(?:item|card)\b"
_RUNS = r"\b(?:runs?|happens?|fires?)\b"
BATCH_LAST = re.compile(
    rf"""(?:
          {_BATCH_SUITE}{_GAP}{{0,40}}?{_RUNS}{_GAP}{{0,40}}?
          \bafter\b{_GAP}{{0,20}}?{_LAST_ITEM}
        | \bafter\b{_GAP}{{0,20}}?{_LAST_ITEM}{_GAP}{{0,60}}?
          {_BATCH_SUITE}{_GAP}{{0,20}}?{_RUNS}
    )""",
    re.IGNORECASE | re.VERBOSE,
)

# One push, and a green suite in front of it. Two probes rather than one: a
# document can promise a single push and never say what it waits for, and it can
# wait for the suite and still push per item, and the operator following either
# half sends out commits nothing reviewed as a whole. Both are read beside the
# flag they govern - a count with no `--push` in the clause counts something
# else, and "a push that happens once, at that session's clean exit" is the
# per-card push wearing the rule's own words.
PUSH_FLAG = re.compile(r"--push")
BATCH_SUITE = re.compile(_BATCH_SUITE, re.IGNORECASE)
# What the single push is counted against. Once per session is what the lane
# already does, and a document can say `--push` pushes once while meaning that:
# "a push that happens once, at that session's clean exit" carries the flag, the
# count and a clean exit, and still pushes every card on its own. The count only
# means anything beside the end of a run of items.
RUN_END = re.compile(rf"{_LAST_ITEM}|\b(?:whole|entire)\s+run\b", re.IGNORECASE)
PUSH_ONCE = re.compile(
    rf"""(?:
          \bpush\w*\b{_GAP}{{0,80}}?
          \b(?:once|a\s+single\s+time|one\s+push|exactly\s+one)\b
        | \b(?:once|a\s+single\s+time|one\s+push|exactly\s+one)\b
          {_GAP}{{0,80}}?\bpush\w*
    )""",
    re.IGNORECASE | re.VERBOSE,
)
PUSH_AFTER_GREEN = re.compile(
    rf"""(?:
          \bpush\w*\b{_GAP}{{0,80}}?\b(?:green|passes|passing|passed)\b
        | \b(?:green|passes|passing|passed)\b{_GAP}{{0,80}}?\bpush\w*
    )""",
    re.IGNORECASE | re.VERBOSE,
)

# The banned class: a push that happens at an item's own exit. Matched by the
# frequency it claims - now, after each item, per item, on every clean exit -
# because the sentence being removed is one wording of it and the next reword
# will be another. `per-item` with a hyphen is the card's suite mode, and stays
# out of the class on purpose.
_EACH_ITEM = (
    r"(?:(?:after|on|at|for|with)\s+(?:each|every)\s+"
    r"(?:clean\s+)?(?:item|card|exit|commit)"
    r"|per\s+(?:item|card))"
)
PER_ITEM_PUSH = re.compile(
    rf"""(?:
          \bpush\w*\s+(?:it|them|the\s+item|the\s+commits?|the\s+branch)?\s*
          \b(?:now|immediately|right\s+away|straight\s+away|at\s+once)\b
        | \bpush\w*\b{_GAP}{{0,40}}?{_EACH_ITEM}
        | {_EACH_ITEM}{_GAP}{{0,40}}?\bpush\w*
        | \bpush\w*\s+(?:this|the\s+current)\s+(?:item|card)\b
    )""",
    re.IGNORECASE | re.VERBOSE,
)

# The same move on the suite: a repo-wide run billed to every item. The frequency
# has to attach to the batch suite itself, so a sentence that contrasts
# `suite: per-item` with `suite: batch` in one breath is left alone.
BATCH_PER_ITEM = re.compile(
    rf"""(?:
          {_BATCH_SUITE}{_GAP}{{0,70}}?
          \b(?:per|once\s+per|for\s+each|after\s+each|after\s+every
             |on\s+each|on\s+every|with\s+each|with\s+every)\s+
          (?:item|card)\b
        | \b(?:per|once\s+per|for\s+each|after\s+each|after\s+every
             |on\s+each|on\s+every)\s+(?:item|card)\b
          {_GAP}{{0,70}}?\b(?:batch\s+suite|repo(?:-wide)?\s+suite)\b
    )""",
    re.IGNORECASE | re.VERBOSE,
)

# The same run billed to the card in hand without the words `each` or `per`.
# "The repo suite runs at the final gate of the card in hand" is one run per
# card in a sentence `BATCH_PER_ITEM` never sees, and it reads to the operator
# as the rule this contract replaces.
CARD_IN_HAND_SUITE = re.compile(
    rf"""(?:
          {_BATCH_SUITE}{_GAP}{{0,80}}?
          \b(?:card\s+in\s+hand|item\s+in\s+hand|of\s+the\s+card
             |of\s+each\s+session|current\s+card|this\s+card)\b
        | \b(?:final|last)\s+gate\s+of\s+(?:the|this|each)\s+card\b
    )""",
    re.IGNORECASE | re.VERBOSE,
)

# One card per run, said in the words a document reaches for when it wants the
# lane to stay what it was. None of these needs the batch patterns to fail: they
# sit beside a satisfied pattern and tell the reader the opposite.
ONE_CARD = re.compile(
    r"""(?:
          \bone\s+(?:spec\s+)?cards?\s+per\s+(?:run|session|invocation|lane)\b
        | \bexactly\s+one\s+card\b
        | \b(?:one\s+)?card\s+at\s+a\s+time\b
        | \b(?:a\s+)?second\s+card\b[^.;]{0,60}?
          \b(?:usage\s+error|an\s+error|refused|refuses|rejected
             |not\s+supported|unsupported)\b
    )""",
    re.IGNORECASE | re.VERBOSE,
)

# And the order given away. A lane free to pick its own order has no last item,
# so the batch suite and the push have nothing to wait for however carefully the
# rest of the page states them.
FREE_ORDER = re.compile(
    r"""(?:
          \bwhatever\s+(?:order|sequence)\b
        | \bany\s+order\b
        | \bno\s+particular\s+order\b
        | \border\s+(?:you|that)\s+(?:like|prefer|choose|suits)\w*
    )""",
    re.IGNORECASE | re.VERBOSE,
)

# Permission written as a denial, the frame `fast_track_stop_testutil.WAIVED`
# already catches under `## Gates`. "With `--push`, nothing in this lane holds a
# push back for a later card, so push after every item that exits clean" reads
# as negated to a polarity check that looks no further than the clause head, and
# the operator pushes per item all the same.
PUSH_WAIVED = re.compile(
    rf"""\b(?:nothing|nobody|none|no\s+\w+)\b{_GAP}{{0,60}}?
         \b(?:blocks?|stops?|holds?|prevents?|forbids?|bars?|claims?)\b""",
    re.IGNORECASE | re.VERBOSE,
)

# The subject test the rules above could not run. `context` reads tokens inside
# a clause and nothing tells it whose clause it is, so one paragraph about
# `/autopilot:run-autopilot` - the command this lane's `## Preconditions`
# refuses to run under - states the last item, the single push and the green
# suite in the loop's name and satisfies all three rules for this one. The
# command is named a sentence earlier than the promise, so this is read over the
# passage and its headings rather than over the clause.
FOREIGN_LANE = re.compile(
    r"""(?:
          /autopilot:(?!fast-track\b)[\w:-]+
        | \brun-autopilot\b
        | \bthe\s+loop\b
        | \bloop\s+session\b
    )""",
    re.IGNORECASE | re.VERBOSE,
)
_ELSEWHERE = (
    " And a clause under a passage naming another `/autopilot:` command, or the "
    "loop, promises nothing about this lane: the preconditions refuse to run "
    "there at all, so the loop's contract is not this one's."
)

# The two bans above, stated positively, because a blacklist is always one
# reword behind. `PER_ITEM_PUSH` knows `push it now` and `after each item`, and
# "with `--push` the working branch is pushed the moment that card's commit
# lands" is per-card pushing in none of those words; `CARD_IN_HAND_SUITE` knows
# `of the card` and `card in hand`, and "its last gate runs the repo-wide suite
# over the paths that card names" is the per-card repo suite in none of those
# either. Pinned this way the document has to say WHEN every time it says a push
# or the repo-wide suite happens, and a wording nobody predicted fails with the
# rest instead of walking through the gap between two listed spellings.
_PUSH_VERB = re.compile(r"\bpush(?:es|ed|ing)?\b", re.IGNORECASE)
_PUSH_PARTICIPLE = frozenset({"pushed"})
LAST_ITEM = re.compile(_LAST_ITEM, re.IGNORECASE)
RUN_END_NAMED = re.compile(
    rf"{_LAST_ITEM}|\bafter\s+the\s+last\b|\b(?:whole|entire)\s+run\b",
    re.IGNORECASE,
)
SUITE_RUN = re.compile(
    rf"(?:{_BATCH_SUITE}[^.!?]{{0,80}}?{_RUNS}|{_RUNS}[^.!?]{{0,80}}?{_BATCH_SUITE})",
    re.IGNORECASE | re.VERBOSE,
)


class Pin(NamedTuple):
    """A promise that has to name the end of the run in the sentence making it.

    `claims` decides whether a sentence promises the thing at all, `keeper` is
    the phrase tying it to the end of the run, and a sentence that promises it
    and names no end is the finding - whatever vocabulary it reached for. The
    keeper is read through `asserted` like every other promise here: "pushed
    the moment that card's commit lands, which is not the last item" carries
    the words and grants the opposite.
    """

    claims: Callable[[str], bool]
    keeper: re.Pattern[str]
    complaint: str


PUSH_UNPINNED = (
    "the body says a push happens and never says it waits for the end of the "
    "run - no last item, no whole run, no after the last - somewhere on the "
    "page:"
)
SUITE_UNPINNED = (
    "the body runs the batch or repo-wide suite in a sentence that names no "
    "last item, so the run it describes is the one billed to whichever card is "
    "in hand, somewhere on the page:"
)


def _pushes(sentence: str) -> bool:
    """True when some clause of `sentence` has a push happening in it.

    The head tests `_reads_as_instruction` runs, aimed at one verb and without
    its six-word cutoff: that cutoff stops a verb deep in a clause vouching for
    the whole clause, and a ban wants exactly the deep ones - "with `--push` the
    working branch is pushed the moment that card's commit lands" puts its push
    twenty words in. Code spans are blanked first, so the flag's own name is not
    read as a push and `--push` in a usage line promises nothing about when.
    """
    for clause in _clauses(sentence):
        prose = _testutil._CODE_SPAN.sub(" thing ", clause)
        for match in _PUSH_VERB.finditer(prose):
            head = prose[: match.start()]
            if _testutil.NEGATOR.search(head):
                continue
            if _testutil._NOUN_MARKER.search(head):
                continue
            if match.group(0).lower() in _PUSH_PARTICIPLE and not (
                _testutil._AUXILIARY.search(head)
            ):
                continue
            return True
    return False


def _runs_the_repo_suite(sentence: str) -> bool:
    """True when `sentence` has the batch or repo-wide suite running."""
    return SUITE_RUN.search(sentence) is not None


PINS = (
    Pin(_pushes, RUN_END_NAMED, PUSH_UNPINNED),
    Pin(_runs_the_repo_suite, LAST_ITEM, SUITE_UNPINNED),
)

INVOCATION = "/autopilot:fast-track"
ENTRY_LINE = f"{INVOCATION} <card.md>"

USAGE_RULE = Rule(
    pattern=REPEATED_CARD,
    probe=ENTRY_LINE,
    missing=(
        f"nothing in the body offers `{ENTRY_LINE}` as text to copy, so the "
        "lane has no entry point at all and nowhere to show that a second card "
        "is allowed."
    ),
    cancelled=(
        f"the `{ENTRY_LINE}` line survives as a form the document says nobody types."
    ),
    denied=(
        f"a copy of `{ENTRY_LINE}` on the page takes exactly one card. An "
        "operator who pastes that one runs one item per session, so a batch of "
        "cards becomes a batch of sessions: each one runs the repo-wide suite "
        "again, and each one pushes on its own. Every copy has to admit the "
        f"argument repeating - `{ENTRY_LINE} [<card.md> ...] [--push]` - "
        "because the reader types whichever line is in front of them: a "
        "repeated form in one block buys nothing while a single-card line "
        "stands in another block, or in a span of the paragraph above it."
    ),
)
ARGUMENT_ORDER_RULE = Rule(
    pattern=ARGUMENT_ORDER,
    forbidden=(FOREIGN_LANE,),
    missing=(
        "no prose sentence says the lane runs the items in the order the "
        "arguments give them. Left unsaid, the order is the reader's to pick, "
        "and the last item - the one the batch suite and the push both wait for "
        "- is not the one the operator typed last."
    ),
    cancelled=(
        "the argument order is written down and then taken back. An archival "
        "frame counts as taking it back, so state it in the present tense "
        "('the lane runs the cards in the order the arguments give them'), not "
        "as something that was, or used to be, the case."
    ),
    denied=(
        "no clause puts the items in argument order as an instruction: either a "
        "negator governs it, or the words are spread across the commas of a "
        "list - a report bullet naming the cards, an order and a command line "
        "is not the lane promising to work them in the order they arrived. The "
        "clause has to name what the lane does with the items - runs them, "
        "works them - beside the order: a sentence about the order a report "
        "prints its columns in says nothing about the order they ran in." + _ELSEWHERE
    ),
)
BATCH_LAST_RULE = Rule(
    pattern=BATCH_LAST,
    forbidden=(FOREIGN_LANE,),
    missing=(
        "no prose sentence says a card whose `suite` is `batch` has its "
        "repo-wide suite run after the last item. Tied to the last gate of "
        "whichever item is in hand, that suite runs once per card: N items pay "
        "for N full runs, and the one run that would catch a break between two "
        "items never happens. The sentence has to name the suite (`suite: "
        "batch`, the batch suite, the repo suite), the run and the last item "
        "together - a bare `batch` is a mode name, not a suite."
    ),
    cancelled=(
        "the batch suite is tied to the last item only in a passage the "
        "document disowns."
    ),
    denied=(
        "no clause runs the batch suite after the last item as an instruction: "
        "either a negator governs it, or the three words meet only across the "
        "commas of a report bullet, where the last item, the run and the batch "
        "row are three separate things a report holds." + _ELSEWHERE
    ),
)
PUSH_ONCE_RULE = Rule(
    pattern=PUSH_ONCE,
    context=(PUSH_FLAG, RUN_END),
    forbidden=(FOREIGN_LANE,),
    missing=(
        "no prose sentence says `--push` pushes once. Counted per item, the "
        "push sends the first cards out while the last is still unreviewed, "
        "and a branch that is pushed cannot be un-pushed."
    ),
    cancelled="the single push is stated in a passage the document then disowns.",
    denied=(
        "no clause holds `--push` to one push at the end of the run, as an "
        "instruction. Either a negator governs it, or the count is not "
        "attached to the flag and the last item - 'a push that happens once, "
        "at that session's clean exit' carries the flag and the count and "
        "still means one push per card, because each card is a session." + _ELSEWHERE
    ),
)
PUSH_AFTER_GREEN_RULE = Rule(
    pattern=PUSH_AFTER_GREEN,
    context=(PUSH_FLAG, BATCH_SUITE),
    forbidden=(FOREIGN_LANE,),
    missing=(
        "no prose sentence makes the push wait for a green suite. A push that "
        "waits for nothing is a push over a red repo suite, which is the one "
        "outcome the batch run exists to prevent."
    ),
    cancelled=(
        "the green suite stands in front of the push only in a passage the "
        "document disowns."
    ),
    denied=(
        "no clause makes `--push` wait for a green batch suite as an "
        "instruction. Either a negator governs it, or the push, the flag and "
        "the green suite never meet in one clause - a bullet naming the gates "
        "that passed, the lens that raised a finding and the push flag the "
        "operator typed says nothing about what the push waits for." + _ELSEWHERE
    ),
)

ARGUMENT_ORDER_RULES = (USAGE_RULE, ARGUMENT_ORDER_RULE)
LAST_ITEM_RULES = (BATCH_LAST_RULE, PUSH_ONCE_RULE, PUSH_AFTER_GREEN_RULE)

ORDER_CLAIMS = (
    (
        ONE_CARD,
        "the body tells the reader the lane takes one card per run - one card "
        "at a time, a second card an error - so the repeated form in the usage "
        "line is a shape nobody is allowed to type, somewhere on the page:",
    ),
    (
        FREE_ORDER,
        "the body leaves the order to the reader - whatever order suits you, "
        "any order - so nothing on the page names a last item for the batch "
        "suite and the push to wait for, somewhere on the page:",
    ),
)
PER_ITEM_CLAIMS = (
    (
        PER_ITEM_PUSH,
        "the body tells the reader to push at an item's own exit - push it "
        "now, push after each item, push on every clean exit - somewhere on "
        "the page:",
    ),
    (
        PUSH_WAIVED,
        "the body waives the rule instead of stating it - nothing holds a push "
        "back for a later card, nobody blocks the next one - and permission "
        "written as a denial reads as negated to every polarity check while the "
        "operator pushes per item all the same, somewhere on the page:",
    ),
    (
        BATCH_PER_ITEM,
        "the body runs the repo-wide suite per item rather than once after the "
        "last item, somewhere on the page:",
    ),
    (
        CARD_IN_HAND_SUITE,
        "the body runs the repo-wide suite for the card in hand - at that "
        "card's own final gate - which is once per card without the word "
        "`each`, somewhere on the page:",
    ),
)
FRONTMATTER_PUSH = (
    f"{_SKILL_MD}: the frontmatter tells the reader to push at an item's own "
    "exit. The harness reads that block when it offers the skill, so a "
    "per-item push parked there is the first thing a reader is told, and the "
    "body-wide ban never sees it."
)


_CODE_SPAN = re.compile(r"`[^`\n]*`")


def _clauses(text: str) -> list[str]:
    """`text` as clauses, with the punctuation inside a code span left alone.

    `key: value` is the shape half this lane's fields take, and the reader
    model's clause splitter reads that colon as a clause boundary - which cuts
    `suite: batch` in two and throws away the suite the rule is about. A code
    span is one token to the reader, so the boundaries are found in a copy with
    the spans masked to the same length, and the original text is sliced there.
    """
    masked = _CODE_SPAN.sub(lambda span: " " * len(span.group(0)), text)
    found = []
    start = 0
    for boundary in _testutil._CLAUSE.finditer(masked):
        found.append(text[start : boundary.start()])
        start = boundary.end()
    found.append(text[start:])
    return found


def _elsewhere(passage: _testutil.Passage, rule: Rule) -> bool:
    """True when the passage is about some other command, or about the loop.

    Passage-wide, headings included, because the command gets named once and
    the promises follow in the sentences under it. A clause-scoped test reads
    "There the batch suite runs once after the last item" as this lane's rule
    when the sentence in front of it handed the whole paragraph to another one.
    """
    return any(
        pattern.search(text)
        for pattern in rule.forbidden
        for text in (*passage.headings, passage.text)
    )


def _states(text: str, rule: Rule) -> bool:
    """True when one clause of `text` carries `rule` as a live instruction.

    One clause, not one passage and not one sentence: a paragraph's opening
    imperative would otherwise vouch for every list item under it, and the
    pattern's two halves would meet across a comma that changes the subject.
    The clause has to hold the pattern, everything the rule is about, no
    negator in front of the match, and a verb telling the reader what happens -
    which is what a report-contents bullet does not have.
    """
    for clause in _clauses(text):
        if not rule.pattern.search(clause):
            continue
        if any(probe.search(clause) is None for probe in rule.context):
            continue
        if not _testutil.asserted(clause, rule.pattern):
            continue
        if _testutil._reads_as_instruction(clause):
            return True
    return False


def _uncopyable(rule: Rule) -> str:
    """The complaint the copyable limb earns, read off every line a hand copies.

    Two repairs to one read. A line is one somebody types when it is fenced and
    pasteable: `code_fragments` hands back every backtick span of a paragraph
    too, and passage order puts the intro prose in front of the block under it,
    so "the first copyable fragment" was any inline mention the intro cared to
    make - parser trivia in a span, with the fence below it still single-card.

    And every copy is read, not one: the operator selects whichever line is in
    front of them, so one single-card copy anywhere on the page is the entry
    line, whatever a repeated form somewhere else shows.
    """
    passages = list(_testutil.passages())
    copies = [
        fragment
        for passage in _testutil.carrying(passages, rule.probe)
        for fragment in _testutil.code_fragments(passage)
        if rule.probe in fragment
    ]
    lines = [
        passage
        for passage in _testutil.carrying(passages, rule.probe)
        if passage.is_code
    ]
    if not lines:
        return f"{_SKILL_MD}: {rule.missing}"
    if not _testutil._live(lines):
        return f"{_SKILL_MD}: {rule.cancelled}"
    kept = all(rule.pattern.search(copy) for copy in copies)
    return "" if kept else f"{_SKILL_MD}: {rule.denied}"


def unstated(rule: Rule) -> str:
    """The complaint the document earns for dropping `rule`, or an empty string.

    Three answers, never one: never written, written and taken back, written
    and never stated as a rule. They are the same absence to a substring
    search, and three different repairs to whoever has to fix the document.

    The copyable limb goes to `_uncopyable`, which reads the lines an operator
    pastes. The prose limbs borrow `_live` from the reader model rather than
    going through `assert_live`, whose instruction test accepts any sentence of
    the passage carrying the probe. These are read clause by clause instead, so
    the imperative opening a paragraph cannot vouch for the bullet under it,
    and a passage handed to another command is dropped before either.
    """
    if rule.probe:
        return _uncopyable(rule)
    passages = list(_testutil.passages())
    carried = _stop.prose_matching(passages, rule.pattern)
    if not carried:
        return f"{_SKILL_MD}: {rule.missing}"
    standing = _testutil._live(carried)
    if not standing:
        return f"{_SKILL_MD}: {rule.cancelled}"
    kept = [
        passage
        for passage in standing
        if not _elsewhere(passage, rule) and _states(passage.text, rule)
    ]
    return "" if kept else f"{_SKILL_MD}: {rule.denied}"


def assert_pinned_to_the_run_end() -> None:
    """Every push and every repo-suite run on the page names the end of the run.

    Read over prose and over fenced text alike, minus the lines that are
    commands: `git push --force` and the usage line say nothing about when a
    push happens, while an English sentence in a ```text block reads to the
    operator exactly as it would one line above the fence.
    """
    claimable = [
        passage
        for passage in _testutil.passages()
        if not (passage.is_code and _testutil._pasteable(passage.text))
    ]
    for pin in PINS:
        loose = sorted(
            {
                sentence.strip()
                for passage in claimable
                for sentence in _testutil._sentences(passage.text)
                if pin.claims(sentence)
                and not _testutil.asserted(sentence, pin.keeper)
            },
        )
        assert not loose, (
            f"{_SKILL_MD}: {pin.complaint} {loose[:3]}. A list of the wordings "
            "somebody thought of is one reword behind; this asks the document "
            "to say when, every time it says a push or the repo-wide suite "
            "happens, so a per-card promise fails whatever words it invents."
        )
