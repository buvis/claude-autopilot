"""The reader model behind the fast-track prose pins.

Split out of test_fast_track_prose.py to keep both files under the file size
limit; the pins themselves stay there. This module holds everything that turns
SKILL.md into the units a reader reads and then decides whether a passage tells
that reader to act.

A bare substring search cannot tell a runbook from a museum label, and neither
can a blacklist of cancelling phrases: a document can carry every pinned string,
in the right section, in copyable form, and invert the instruction around each
one. So a pin asks five things of a promise rather than one:

  * the string is there,
  * it sits where a reader acts on it - inside the section that owns it, or in
    text an operator can copy - and not parked in some unrelated list,
  * the sentence carrying it reads as an instruction - an imperative or a
    present-tense directive, with no negator in front of the verb - so a promise
    quoted in order to be refuted, or narrated as history, does not count,
  * a fenced line earns that reading only when a hand could paste it - a
    command, a `/slash-command`, a `key: value` field, or a line carrying a
    flag. A fence is not a laundry that turns English sentences into commands,
  * neither the passage, the headings above it, nor any other passage in the
    same section takes it back - by disclaimer (`retired`), by an archival frame
    (`was`, `used to`), by a rebuttal (`folklore`), or by simply stating the
    opposite one paragraph earlier.

The word lists here are a backstop. The load-bearing parts are the demand for a
live instruction in text a reader can act on, and the polarity checks the pins
run over a whole section rather than over the passage carrying the pin.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import NamedTuple

SKILL_MD = Path(__file__).resolve().parent.parent / "SKILL.md"

# The dispatches the lane makes, each with the words a kind may use to name it:
# the lens or the persona for the review lanes, the stage or the persona for the
# rest. A ledger kind has to name one of them. Counting rows says eight
# dispatches happened; naming them says which, and a row filed under
# `fast-track:aardvark` attributes its time to nothing.
_LANE_WORDS = {
    "consensus": ("consensus", "alice", "fanout"),
    "blind": ("blind", "blake"),
    "doubt": ("doubt", "eve"),
    "codex": ("codex", "bob"),
    "gemini": ("gemini", "carl"),
    "tests": ("test", "tess"),
    "implement": ("implement", "ivan"),
    "verify": ("verif", "adversarial", "victor"),
    "rework": ("rework",),
    "delta": ("delta",),
}

# Language that takes a promise back. Deliberately about decommissioning in
# general, not about any one wording: a heading that calls its contents retired,
# a bullet that says the flag does nothing, and a section that is "names only"
# all leave the reader with a string and no procedure. Words the live document
# needs are kept out on purpose - it says `refuses`, `never inside a subagent`
# and `never the diff`, and none of those cancels anything.
_DISCLAIMER = re.compile(
    r"""(?:
          \bretire(?:d|s|ment)?\b
        | \bdeprecat\w+
        | \bdecommission\w*
        | \b(?:obsolete|defunct|superseded|historical)\b
        | \bno\s+longer\b
        | \bunimplemented\b
        | \bnot\s+implemented\b
        | \bmust\s+(?:not|never)\s+be\s+(?:run|used|followed|typed|copied)\b
        | \bnever\s+typ\w+
        | \bdo(?:es)?\s+not\s+typ\w+
        | \bdo(?:es)?\s+nothing\b
        | \b(?:switched|turned|shut)\s+off\b
        | \bkept\s+(?:only|solely|purely|just)\b
        | \bnot\s+an?\s+(?:runbook|procedure|instruction)\b
        | \bno\s+(?:procedure|entry\s+point)\b
        | \b(?:names|strings?|reference)\s+only\b
    )""",
    re.IGNORECASE | re.VERBOSE,
)

# A promise told as history is not a promise. A live runbook speaks to the
# operator in front of it, so a passage carrying a pin has no business reaching
# for the past tense or for the vocabulary of an archive. This is the line
# between "the lane refuses headless sessions" and "the lane refused them, back
# when it ran" - the same six words, opposite instructions.
_ARCHIVAL = re.compile(
    r"""(?:
          \bwas\b | \bwere\b | \bhad\s+been\b | \bused\s+to\b
        | \barchiv\w+ | \bdismantl\w+ | \bdisband\w+
        | \bformer(?:ly)?\b | \bin\s+the\s+past\b
        | \bold\s+(?:note|slogan|rule|habit|wording|doc|version|draft)\w*
        | \blore\b | \bfolklore\b | \bmuseum\b
        | \bfor\s+the\s+wording\b
    )""",
    re.IGNORECASE | re.VERBOSE,
)

# A rule quoted in order to be knocked down still contains the rule. These are
# the moves a document makes when it wants the string and not the behaviour.
_REBUTTAL = re.compile(
    r"""(?:
          \bdisregard\w* | \bignor\w+ | \bsuperstition\b | \bmyth\b
        | \bmistake\b | \bmisconception\b | \bfolly\b
        | \bdo(?:es)?\s+not\s+apply\b | \bnever\s+applied\b
        | \bcan\s+be\s+(?:skipped|dropped|ignored|disregarded|flipped)\b
        | \bsafe\s+to\s+(?:skip|ignore|drop)\b
        | \bdecorat\w+ | \bcosmetic\b
    )""",
    re.IGNORECASE | re.VERBOSE,
)

CANCELS = (_DISCLAIMER, _ARCHIVAL, _REBUTTAL)

NEGATOR = re.compile(
    r"\b(?:no|not|never|nothing|nobody|none|neither|nor|cannot|avoid|skip"
    r"|without|rather\s+than|instead\s+of)\b|n't\b",
    re.IGNORECASE,
)

# Verbs a runbook uses to tell someone to do something: imperative and
# third-person present. `read` is deliberately absent - its past tense is spelt
# the same, so `the invocation line read X` would pass for an instruction.
# `push` is here because the exit rule is written in it: without it "the lane
# pushes once, after the last item" reads as narration and the multi-card pins
# would ask the document for a wording ("run the push") instead of the rule.
_PRESENT_VERBS = [
    "run",
    "runs",
    "dispatch",
    "dispatches",
    "send",
    "sends",
    "launch",
    "launches",
    "open",
    "opens",
    "close",
    "closes",
    "copy",
    "copies",
    "paste",
    "pastes",
    "set",
    "sets",
    "park",
    "parks",
    "reset",
    "resets",
    "check",
    "checks",
    "refuse",
    "refuses",
    "stop",
    "stops",
    "commit",
    "commits",
    "write",
    "writes",
    "record",
    "records",
    "create",
    "creates",
    "exit",
    "exits",
    "receive",
    "receives",
    "address",
    "addresses",
    "hand",
    "hands",
    "happen",
    "happens",
    "pass",
    "passes",
    "push",
    "pushes",
    "process",
    "processes",
    "start",
    "starts",
    "keep",
    "keeps",
    "apply",
    "applies",
    "take",
    "takes",
    "make",
    "makes",
    "name",
    "names",
    "render",
    "renders",
    "raise",
    "raises",
    "drive",
    "drives",
    "add",
    "adds",
    "move",
    "moves",
    "fail",
    "fails",
]

# The same verbs as participles. A live document reaches for these under a
# present auxiliary (`the lanes are dispatched`); a museum label reaches for
# them bare (`the lane dispatched five lanes, back when it ran`), so a
# participle only counts as an instruction when an auxiliary stands in front of
# it. That is what separates a present passive from past narration without
# needing a list of every past-tense sentence English can build.
_PARTICIPLES = [
    "dispatched",
    "sent",
    "launched",
    "opened",
    "closed",
    "copied",
    "pasted",
    "parked",
    "checked",
    "refused",
    "stopped",
    "committed",
    "written",
    "recorded",
    "created",
    "received",
    "addressed",
    "handed",
    "passed",
    "pushed",
    "processed",
    "started",
    "kept",
    "applied",
    "taken",
    "made",
    "named",
    "rendered",
    "raised",
    "driven",
    "added",
    "moved",
    "failed",
]

_PARTICIPLE_ONLY = frozenset(_PARTICIPLES)
_RUNBOOK_VERB = re.compile(
    r"\b(?:" + "|".join((*_PRESENT_VERBS, *_PARTICIPLES)) + r")\b",
    re.IGNORECASE,
)
_AUXILIARY = re.compile(
    r"\b(?:is|are|be|been|being|get|gets|must|should|shall|will|can|may)\s*$",
    re.IGNORECASE,
)

# Half these words are nouns too, and a determiner in front of one settles it:
# `the exit rule` and `a record of what happened` are not instructions to exit
# or to record anything.
_NOUN_MARKER = re.compile(
    r"\b(?:a|an|the|this|that|these|those|its|their|our|your|one|each|every"
    r"|any|no)\s+$",
    re.IGNORECASE,
)

_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_CLAUSE = re.compile(r"[;:]|(?<=[.!?])\s+|\s+-\s+")

_HEADING = re.compile(r"^ {0,3}(#{1,6})\s+(.*?)\s*#*$")
_FENCE = re.compile(r"^ {0,3}(?:```|~~~)")
_BULLET = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
_CODE_SPAN = re.compile(r"`([^`\n]+)`")

# What a fenced line has to look like before it counts as something to run.
# Without this a fence launders any text into an instruction: an English
# sentence typed between backticks satisfies a pin asking for a command line,
# and none of the verb machinery below ever looks at it. Four shapes are
# pasteable - a command, a `/slash-command`, a `key: value` field, or anything
# carrying a `-`/`--` flag. The binary list is short on purpose: it holds the
# few commands this lane types with no flag at all (`git branch fast-track/…`),
# and stays lowercase so a sentence opening with `Make` or `Run` is not a
# command.
_FIELD = re.compile(r"^[A-Za-z_][\w.-]*:[ \t]+\S")
_SLASH_COMMAND = re.compile(r"^/[A-Za-z][\w:.-]*")
_FLAG = re.compile(r"(?:^|\s)--?[A-Za-z][\w-]*\b")
_EXECUTABLE = re.compile(
    r"^(?:[A-Z_][A-Z0-9_]*=\S*\s+)*"
    r"(?:[\w.@~/-]*[\w-]\.(?:py|sh|bash|js|mjs|ts|rb|pl)\b"
    r"|[.~]?/[\w./-]+"
    r"|(?:git|uv|python3?|pytest|bash|sh|rg)\b)",
)

# Section stems, not exact titles: `## Implementation` is still the Implement
# section, and `## Exit rule` is still Exit. Only the sections the pins anchor
# to are listed.
_SECTION_STEM = {
    "Preconditions": r"\bprecondition",
    "Tests": r"\btest",
    "Gates": r"\bgate",
    "Roster": r"\broster",
    "Rework": r"\brework",
    "Exit": r"\bexit",
}

# The whole documented running order. A reader works down the page, so a
# precondition printed after the exit rule is a check nobody makes in time, and
# a ledger that floats away from its dispatches is an appendix.
_DOCUMENTED_SECTIONS = (
    ("Preconditions", r"\bprecondition"),
    ("Card", r"\bcard"),
    ("Tests", r"\btest"),
    ("Implement", r"\bimplement"),
    ("Gates", r"\bgate"),
    ("Roster", r"\broster"),
    ("Verify", r"\bverif"),
    ("Rework", r"\brework"),
    ("Delta", r"\bdelta"),
    ("Exit", r"\bexit"),
    ("Ledgers", r"\bledger"),
    ("Report", r"\breport"),
)


class Passage(NamedTuple):
    """One paragraph, one list item, or one line of a fenced code block.

    `headings` is the chain of headings above it, outermost first, so a promise
    can be placed by the section a reader would have been reading when they hit
    it. `is_code` marks the lines an operator copies rather than reads.
    """

    headings: tuple[str, ...]
    text: str
    is_code: bool


@lru_cache(maxsize=1)
def document() -> str:
    """The whole SKILL.md, frontmatter included. Read from disk exactly once.

    Cached rather than read at import or in a fixture on purpose: an absent
    document then fails each test by name, where an import-time read would be a
    collection error and a fixture an error at setup. A missing SKILL.md is the
    loudest thing these pins have to report, so it gets a real failure.
    """
    assert SKILL_MD.is_file(), (
        f"{SKILL_MD} does not exist. The fast-track lane is a document plus a "
        "handful of helper scripts; with the document gone the scripts drive "
        "nothing and no operator can run the lane."
    )
    return SKILL_MD.read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def _split() -> tuple[str, str]:
    """The document as (frontmatter, body), split on the opening `---` block."""
    text = document()
    if not text.startswith("---\n"):
        return "", text
    end = text.find("\n---", len("---\n"))
    assert end != -1, (
        f"{SKILL_MD}: the frontmatter block never closes, so the whole file "
        "reads as frontmatter and nothing below it is a documented promise."
    )
    return text[len("---\n") : end], text[end + len("\n---") :]


def frontmatter() -> str:
    """The frontmatter block: what the harness reads when it offers the skill."""
    return _split()[0]


def body() -> str:
    """The document with its opening `---` frontmatter block removed."""
    return _split()[1]


@lru_cache(maxsize=1)
def passages() -> tuple[Passage, ...]:
    """The body as the units a reader reads, each tagged with its headings.

    Hard-wrapped prose is joined back into one passage, so a promise split
    across two source lines still reads as one; a blank line, a bullet or a
    heading ends one. That is the replacement for the old character window,
    which happily satisfied a pin from the paragraph next door.
    """
    found: list[Passage] = []
    stack: list[tuple[int, str]] = []
    pending: list[str] = []
    in_code = False

    def flush() -> None:
        if pending:
            found.append(
                Passage(tuple(title for _, title in stack), " ".join(pending), False),
            )
            pending.clear()

    for line in body().splitlines():
        if _FENCE.match(line):
            flush()
            in_code = not in_code
            continue
        if in_code:
            # One command per line: a fenced block is a list of things to copy,
            # not a paragraph.
            if line.strip():
                found.append(
                    Passage(tuple(title for _, title in stack), line.strip(), True),
                )
            continue
        heading = _HEADING.match(line)
        if heading:
            flush()
            level = len(heading.group(1))
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, heading.group(2)))
            continue
        if not line.strip() or _BULLET.match(line):
            flush()
        if line.strip():
            pending.append(line.strip())
    flush()
    return tuple(found)


@lru_cache(maxsize=1)
def _section_order() -> dict[str, int]:
    """Where each documented section's `##` heading first appears, in page order.

    A heading claims the earliest documented section still unclaimed, so one
    that mentions two of them (`## Tests before the implementor`) counts once,
    for the section a reader has actually reached at that point.
    """
    found: dict[str, int] = {}
    position = 0
    in_code = False
    for line in body().splitlines():
        if _FENCE.match(line):
            in_code = not in_code
            continue
        if in_code:
            continue
        heading = _HEADING.match(line)
        if heading is None or len(heading.group(1)) != 2:
            continue
        for name, stem in _DOCUMENTED_SECTIONS:
            if name not in found and re.search(stem, heading.group(2), re.IGNORECASE):
                found[name] = position
                break
        position += 1
    return found


def _assert_documented_order() -> None:
    """Every documented section is there, and they run in the documented order."""
    order = _section_order()
    absent = [name for name, _ in _DOCUMENTED_SECTIONS if name not in order]
    assert not absent, (
        f"{SKILL_MD}: the body has no `##` section for {absent}. The lane is "
        "read top to bottom, and a stage with no heading of its own is a stage "
        "the operator walks past."
    )
    positions = [order[name] for name, _ in _DOCUMENTED_SECTIONS]
    assert positions == sorted(positions), (
        f"{SKILL_MD}: the sections run "
        f"{sorted(order, key=lambda name: order[name])}, not the documented "
        f"order {[name for name, _ in _DOCUMENTED_SECTIONS]}. Out of order, the "
        "reader meets the exit rule before the precondition that would have "
        "stopped the item, and the ledger reads as an appendix rather than a "
        "step taken at each dispatch."
    )


def section(title: str) -> list[Passage]:
    """Everything written under the `title` section, subsections included."""
    _assert_documented_order()
    stem = re.compile(_SECTION_STEM[title], re.IGNORECASE)
    found = [
        passage
        for passage in passages()
        if any(stem.search(heading) for heading in passage.headings)
    ]
    assert found, (
        f"{SKILL_MD}: the body has no `{title}` section with anything under "
        "it. The lane's promises are addressed to a reader working through the "
        "sections in order, and a promise with no section is one nobody reaches."
    )
    return found


def _disclaimer(passage: Passage) -> str | None:
    """The first phrase in the passage, or above it, that cancels its content."""
    for text in (*passage.headings, passage.text):
        for pattern in CANCELS:
            found = pattern.search(text)
            if found:
                return found.group(0)
    return None


def _live(candidates: list[Passage]) -> list[Passage]:
    """The passages a reader would act on, dropping the cancelled ones."""
    return [passage for passage in candidates if _disclaimer(passage) is None]


def _sentences(text: str) -> list[str]:
    """The passage as sentences: the unit a promise has to hold together in."""
    return [part for part in _SENTENCE.split(text) if part.strip()]


def sentences_carrying(text: str, probe: str | re.Pattern[str]) -> list[str]:
    """The sentences of `text` that hold the probe."""
    if isinstance(probe, str):
        needle = probe.lower()
        return [sentence for sentence in _sentences(text) if needle in sentence.lower()]
    return [sentence for sentence in _sentences(text) if probe.search(sentence)]


def _reads_as_instruction(text: str) -> bool:
    """True when some clause tells the reader to act rather than describing.

    Code spans are blanked first: `git reset --keep` sitting in a sentence about
    strings in a glass case is not the sentence telling anyone to run it, and
    without the blanking the command's own verb would vouch for the prose
    around it. A bare participle is read as narration, not as a rule.
    """
    prose = _CODE_SPAN.sub(" thing ", text)
    for clause in _CLAUSE.split(prose):
        for verb in _RUNBOOK_VERB.finditer(clause):
            head = clause[: verb.start()]
            if len(head.split()) > 6:
                # A verb this deep in the clause belongs to some aside, not to
                # the action the clause is about.
                break
            if NEGATOR.search(head):
                continue
            if _NOUN_MARKER.search(head):
                continue
            if verb.group(0).lower() in _PARTICIPLE_ONLY and not _AUXILIARY.search(
                head,
            ):
                # `the lane refused a headless session` is a memoir; `a headless
                # session is refused` is the rule.
                continue
            return True
    return False


def asserted(text: str, pattern: re.Pattern[str]) -> bool:
    """True when `pattern` matches where no negator in its own clause governs it.

    A rejected match never hides the text behind it. `finditer` resumes at the
    end of the match it just yielded, so one negated match swallowing the rest
    of the sentence would exempt every later match inside it - "nothing in this
    lane holds a push back for a later card, so push after every item" reads as
    denied while telling the operator to push per item, and the instruction is
    in the span the discarded match consumed. The scan restarts one character
    into a rejected match instead, so the sentence is read to its end.
    """
    position = 0
    while (match := pattern.search(text, position)) is not None:
        head = _CLAUSE.split(text[: match.start()])[-1]
        if not NEGATOR.search(head):
            return True
        position = match.start() + 1
    return False


def lanes_named(kind: str) -> set[str]:
    """The dispatches a `--kind fast-track:<kind>` slug could be naming.

    By lens or by persona, whichever the document prefers: `blind` and `blake`
    are the same row, and either tells a reader months later which dispatch
    spent the time.
    """
    slug = kind.lower()
    return {
        lane
        for lane, words in _LANE_WORDS.items()
        if any(word in slug for word in words)
    }


def _pasteable(line: str) -> bool:
    """True when an operator could select this fenced line and run it.

    A fence is not evidence of anything: `Send them in one message.` between
    backticks is a sentence, unrunnable if pasted into a shell, and reading it
    as the instruction it describes is how a document keeps every pinned string
    while telling the reader to do the opposite.
    """
    text = line.strip().lstrip("$ ").strip()
    if not text or text.startswith("#"):
        return False
    return bool(
        _FIELD.match(text)
        or _SLASH_COMMAND.match(text)
        or _FLAG.search(text)
        or _EXECUTABLE.match(text),
    )


def _instructive(
    candidates: list[Passage],
    probe: str | re.Pattern[str],
) -> list[Passage]:
    """The passages carrying the probe inside something a reader is told to do.

    A fenced line counts when it is pasteable - it is then the thing being
    copied. Everywhere else the sentence holding the probe has to read as an
    instruction, and a fenced sentence has to clear the same bar as any other.
    """
    return [
        passage
        for passage in candidates
        if (
            _pasteable(passage.text)
            if passage.is_code
            else any(
                _reads_as_instruction(sentence)
                for sentence in sentences_carrying(passage.text, probe)
            )
        )
    ]


def code_fragments(passage: Passage) -> tuple[str, ...]:
    """Everything in the passage an operator copies verbatim.

    A command named in running prose is a mention; the same command fenced or
    in a code span is the text a hand selects and pastes - as long as the fenced
    line is a command at all and not prose wearing a code block.
    """
    if passage.is_code:
        return (passage.text,) if _pasteable(passage.text) else ()
    return tuple(_CODE_SPAN.findall(passage.text))


def carrying(candidates: list[Passage], needle: str) -> list[Passage]:
    """Passages that offer `needle` as copyable text rather than as prose."""
    return [
        passage
        for passage in candidates
        if any(needle in fragment for fragment in code_fragments(passage))
    ]


def assert_live(
    candidates: list[Passage],
    probe: str | re.Pattern[str],
    missing: str,
    cancelled: str,
) -> list[Passage]:
    """The passages that still keep the promise, or a failure saying which drift.

    Three failures rather than one: a string that was never written, a string
    the document takes back, and a string the document narrates instead of
    telling anyone to act on all look identical to a substring search, and the
    operator has to be told which of the three happened.
    """
    assert candidates, f"{SKILL_MD}: {missing}"
    live = _live(candidates)
    assert live, (
        f"{SKILL_MD}: {cancelled} Every passage carrying it is cancelled by "
        f"{sorted({str(_disclaimer(passage)) for passage in candidates})}, so the "
        "document keeps the string and drops the promise."
    )
    instructive = _instructive(live, probe)
    label = probe if isinstance(probe, str) else probe.pattern
    assert instructive, (
        f"{SKILL_MD}: {label!r} is written down but never as something to do: "
        f"{sorted({passage.text for passage in live})[:3]}. Every sentence "
        "carrying it describes, narrates or refutes it - no imperative, no "
        "present-tense directive, or a negator in front of the verb - and a "
        "promise nobody is told to keep is a caption."
    )
    return instructive


def assert_unopposed(
    candidates: list[Passage],
    contradiction: re.Pattern[str],
    complaint: str,
) -> None:
    """No passage in the section states the opposite of the section's promise.

    Scoped to the section, not to the passage carrying the pin: the pins above
    ask that one passage keep the promise, and one passage is all a document
    needs to hand over while the paragraph beside it says the reverse.
    """
    opposed = sorted(
        {
            sentence.strip()
            for passage in candidates
            for sentence in _sentences(passage.text)
            if asserted(sentence, contradiction)
        },
    )
    assert not opposed, (
        f"{SKILL_MD}: {complaint} {opposed[:3]}. The pinned string is still "
        "there, in its own section, in a sentence that reads as an instruction "
        "- and the operator reads this one too, and follows whichever came last."
    )
