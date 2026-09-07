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

The word lists below are a backstop. The load-bearing parts are the demand for a
live instruction in text a reader can act on, and the polarity checks run over
the whole section rather than over the passage carrying the pin: the roster
sends in one message and never one lane at a time, its CLI lanes never run in
the foreground or inside a subagent, Blake is never handed the diff, the
preconditions never say nothing blocks a run, and the rework section neither
reuses the implementor nor drops the cap.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import NamedTuple

_SKILL_MD = Path(__file__).resolve().parent.parent / "SKILL.md"

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

# The dispatches the lane makes, each with the words a kind may use to name it:
# the lens or the persona for the review lanes, the stage or the persona for the
# rest. A ledger kind has to name one of them. Counting rows says eight
# dispatches happened; naming them says which, and a row filed under
# `fast-track:aardvark` attributes its time to nothing.
_LANE_WORDS = {
    "consensus": ("consensus", "alice", "fanout"),
    "blind": ("blind", "blake"),
    "doubt": ("doubt", "eve"),
    "codex": ("codex",),
    "gemini": ("gemini",),
    "tests": ("test",),
    "implement": ("implement", "ivan"),
    "verify": ("verif", "adversarial", "victor"),
    "rework": ("rework",),
    "delta": ("delta",),
}
_ROSTER_LANES = ("consensus", "blind", "doubt", "codex", "gemini")

_TASK_ARGUMENT = re.compile(r"--task[= ]\s*(\S+)")
_PLACEHOLDER = re.compile(r"^<[^>]+>$|^\$\{?\w+\}?$|^\{\{?\w[\w.-]*\}?\}$")

# `Pat` is a substring of `Path` and `patch`, so the ban is matched on word
# boundaries; case-insensitively, because `autopilot:pat` is the same per-task
# ceremony wearing a lowercase name.
_BANNED = ("Devon", "deslop", "Pat", "plan-tasks", "design-solution")

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

_CANCELS = (_DISCLAIMER, _ARCHIVAL, _REBUTTAL)

_NEGATOR = re.compile(
    r"\b(?:no|not|never|nothing|nobody|none|neither|nor|cannot|avoid|skip"
    r"|without|rather\s+than|instead\s+of)\b|n't\b",
    re.IGNORECASE,
)

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

# Verbs a runbook uses to tell someone to do something: imperative and
# third-person present. `read` is deliberately absent - its past tense is spelt
# the same, so `the invocation line read X` would pass for an instruction.
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
# section, and `## Exit rule` is still Exit. Only the sections these pins anchor
# to are listed.
_SECTION_STEM = {
    "Preconditions": r"\bprecondition",
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


class _Passage(NamedTuple):
    """One paragraph, one list item, or one line of a fenced code block.

    `headings` is the chain of headings above it, outermost first, so a promise
    can be placed by the section a reader would have been reading when they hit
    it. `is_code` marks the lines an operator copies rather than reads.
    """

    headings: tuple[str, ...]
    text: str
    is_code: bool


@lru_cache(maxsize=1)
def _document() -> str:
    """The whole SKILL.md, frontmatter included. Read from disk exactly once.

    Cached rather than read at import or in a fixture on purpose: an absent
    document then fails each test by name, where an import-time read would be a
    collection error and a fixture an error at setup. A missing SKILL.md is the
    loudest thing these pins have to report, so it gets a real failure.
    """
    assert _SKILL_MD.is_file(), (
        f"{_SKILL_MD} does not exist. The fast-track lane is a document plus a "
        "handful of helper scripts; with the document gone the scripts drive "
        "nothing and no operator can run the lane."
    )
    return _SKILL_MD.read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def _split() -> tuple[str, str]:
    """The document as (frontmatter, body), split on the opening `---` block."""
    document = _document()
    if not document.startswith("---\n"):
        return "", document
    end = document.find("\n---", len("---\n"))
    assert end != -1, (
        f"{_SKILL_MD}: the frontmatter block never closes, so the whole file "
        "reads as frontmatter and nothing below it is a documented promise."
    )
    return document[len("---\n") : end], document[end + len("\n---") :]


def _frontmatter() -> str:
    """The frontmatter block: what the harness reads when it offers the skill."""
    return _split()[0]


def _body() -> str:
    """The document with its opening `---` frontmatter block removed."""
    return _split()[1]


@lru_cache(maxsize=1)
def _passages() -> tuple[_Passage, ...]:
    """The body as the units a reader reads, each tagged with its headings.

    Hard-wrapped prose is joined back into one passage, so a promise split
    across two source lines still reads as one; a blank line, a bullet or a
    heading ends one. That is the replacement for the old character window,
    which happily satisfied a pin from the paragraph next door.
    """
    passages: list[_Passage] = []
    stack: list[tuple[int, str]] = []
    pending: list[str] = []
    in_code = False

    def flush() -> None:
        if pending:
            passages.append(
                _Passage(tuple(title for _, title in stack), " ".join(pending), False),
            )
            pending.clear()

    for line in _body().splitlines():
        if _FENCE.match(line):
            flush()
            in_code = not in_code
            continue
        if in_code:
            # One command per line: a fenced block is a list of things to copy,
            # not a paragraph.
            if line.strip():
                passages.append(
                    _Passage(tuple(title for _, title in stack), line.strip(), True),
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
    return tuple(passages)


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
    for line in _body().splitlines():
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
        f"{_SKILL_MD}: the body has no `##` section for {absent}. The lane is "
        "read top to bottom, and a stage with no heading of its own is a stage "
        "the operator walks past."
    )
    positions = [order[name] for name, _ in _DOCUMENTED_SECTIONS]
    assert positions == sorted(positions), (
        f"{_SKILL_MD}: the sections run "
        f"{sorted(order, key=lambda name: order[name])}, not the documented "
        f"order {[name for name, _ in _DOCUMENTED_SECTIONS]}. Out of order, the "
        "reader meets the exit rule before the precondition that would have "
        "stopped the item, and the ledger reads as an appendix rather than a "
        "step taken at each dispatch."
    )


def _section(title: str) -> list[_Passage]:
    """Everything written under the `title` section, subsections included."""
    _assert_documented_order()
    stem = re.compile(_SECTION_STEM[title], re.IGNORECASE)
    found = [
        passage
        for passage in _passages()
        if any(stem.search(heading) for heading in passage.headings)
    ]
    assert found, (
        f"{_SKILL_MD}: the body has no `{title}` section with anything under "
        "it. The lane's promises are addressed to a reader working through the "
        "sections in order, and a promise with no section is one nobody reaches."
    )
    return found


def _disclaimer(passage: _Passage) -> str | None:
    """The first phrase in the passage, or above it, that cancels its content."""
    for text in (*passage.headings, passage.text):
        for pattern in _CANCELS:
            found = pattern.search(text)
            if found:
                return found.group(0)
    return None


def _live(passages: list[_Passage]) -> list[_Passage]:
    """The passages a reader would act on, dropping the cancelled ones."""
    return [passage for passage in passages if _disclaimer(passage) is None]


def _sentences(text: str) -> list[str]:
    """The passage as sentences: the unit a promise has to hold together in."""
    return [part for part in _SENTENCE.split(text) if part.strip()]


def _sentences_carrying(text: str, probe: str | re.Pattern[str]) -> list[str]:
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
            if _NEGATOR.search(head):
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


def _asserted(text: str, pattern: re.Pattern[str]) -> bool:
    """True when `pattern` matches where no negator in its own clause governs it."""
    for match in pattern.finditer(text):
        head = _CLAUSE.split(text[: match.start()])[-1]
        if not _NEGATOR.search(head):
            return True
    return False


def _lanes_named(kind: str) -> set[str]:
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
    passages: list[_Passage],
    probe: str | re.Pattern[str],
) -> list[_Passage]:
    """The passages carrying the probe inside something a reader is told to do.

    A fenced line counts when it is pasteable - it is then the thing being
    copied. Everywhere else the sentence holding the probe has to read as an
    instruction, and a fenced sentence has to clear the same bar as any other.
    """
    return [
        passage
        for passage in passages
        if (
            _pasteable(passage.text)
            if passage.is_code
            else any(
                _reads_as_instruction(sentence)
                for sentence in _sentences_carrying(passage.text, probe)
            )
        )
    ]


def _code_fragments(passage: _Passage) -> tuple[str, ...]:
    """Everything in the passage an operator copies verbatim.

    A command named in running prose is a mention; the same command fenced or
    in a code span is the text a hand selects and pastes - as long as the fenced
    line is a command at all and not prose wearing a code block.
    """
    if passage.is_code:
        return (passage.text,) if _pasteable(passage.text) else ()
    return tuple(_CODE_SPAN.findall(passage.text))


def _carrying(passages: list[_Passage], needle: str) -> list[_Passage]:
    """Passages that offer `needle` as copyable text rather than as prose."""
    return [
        passage
        for passage in passages
        if any(needle in fragment for fragment in _code_fragments(passage))
    ]


def _assert_live(
    passages: list[_Passage],
    probe: str | re.Pattern[str],
    missing: str,
    cancelled: str,
) -> list[_Passage]:
    """The passages that still keep the promise, or a failure saying which drift.

    Three failures rather than one: a string that was never written, a string
    the document takes back, and a string the document narrates instead of
    telling anyone to act on all look identical to a substring search, and the
    operator has to be told which of the three happened.
    """
    assert passages, f"{_SKILL_MD}: {missing}"
    live = _live(passages)
    assert live, (
        f"{_SKILL_MD}: {cancelled} Every passage carrying it is cancelled by "
        f"{sorted({str(_disclaimer(passage)) for passage in passages})}, so the "
        "document keeps the string and drops the promise."
    )
    instructive = _instructive(live, probe)
    label = probe if isinstance(probe, str) else probe.pattern
    assert instructive, (
        f"{_SKILL_MD}: {label!r} is written down but never as something to do: "
        f"{sorted({passage.text for passage in live})[:3]}. Every sentence "
        "carrying it describes, narrates or refutes it - no imperative, no "
        "present-tense directive, or a negator in front of the verb - and a "
        "promise nobody is told to keep is a caption."
    )
    return instructive


def _assert_unopposed(
    passages: list[_Passage],
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
            for passage in passages
            for sentence in _sentences(passage.text)
            if _asserted(sentence, contradiction)
        },
    )
    assert not opposed, (
        f"{_SKILL_MD}: {complaint} {opposed[:3]}. The pinned string is still "
        "there, in its own section, in a sentence that reads as an instruction "
        "- and the operator reads this one too, and follows whichever came last."
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


def test_blake_receives_the_card_never_the_diff() -> None:
    # Blake's whole value is ignorance of the implementation: handed the diff,
    # he becomes a second consensus lane wearing the blind lens's name.
    promise = re.compile(
        r"never\s+(?:sees\s+|gets\s+|receives\s+|reads\s+)?the\s+diff",
        re.IGNORECASE,
    )
    both = re.compile(
        r"card\s+and\s+the\s+diff|diff\s+and\s+the\s+card|\bboth\b",
        re.IGNORECASE,
    )
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
        and promise.search(passage.text)
        and not both.search(passage.text)
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


def test_ivan_is_fresh_on_rework_and_capped_at_one_rework() -> None:
    # A reused implementor argues with the reviewers from memory instead of
    # reading the findings, and an uncapped rework loop never exits.
    rework = _section("Rework")
    cap = re.compile(r"at most once|no more than once|only once", re.IGNORECASE)
    _assert_live(
        [passage for passage in rework if cap.search(passage.text)],
        cap,
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
    fresh = re.compile(
        r"fresh\s+(?:`?autopilot:ivan`?|implementor|instance|ivan)",
        re.IGNORECASE,
    )
    reuse = re.compile(
        r"\breuse\b|\bre-use\b"
        r"|\bsame\s+(?:one|instance|implementor|ivan|agent|session|context)\b"
        r"|already\s+in\s+the\s+session|\bexisting\s+(?:instance|implementor)\b"
        r"|\bwho\s+wrote\s+the\s+(?:code|patch|implementation|line)\w*"
        r"|\bremembers?\s+writing\b"
        r"|\bkeeps?\s+the\s+(?:implementor|instance|session|context)\b",
        re.IGNORECASE,
    )
    kept = [
        passage
        for passage in ivan
        if cap.search(passage.text)
        and fresh.search(passage.text)
        and not reuse.search(passage.text)
    ]
    assert kept, (
        f"{_SKILL_MD}: no single passage dispatches `autopilot:ivan`, calls "
        "that instance fresh, and caps rework at one round. Apart, the cap "
        "reads as a note about some other loop and `fresh` hangs off whatever "
        "is nearby - a document that dispatches Ivan and then says to reuse the "
        "instance already in the session carries both words and neither promise."
    )
    _assert_unopposed(
        rework,
        reuse,
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


def test_every_dispatch_opens_a_ledger_row() -> None:
    # One row per dispatch is what makes the lane's cost measurable at all. A
    # kind that never appears is a lane whose time is spent off the books.
    starts = _assert_live(
        _carrying(list(_passages()), _START_CALL),
        _START_CALL,
        missing=(
            f"nothing in the body offers `{_START_CALL}` as a command line to "
            "copy, so no dispatch opens a ledger row and the lane costs nothing "
            "on paper."
        ),
        cancelled=(
            f"every `{_START_CALL}` line is listed as a command the reader is "
            "told not to run."
        ),
    )
    assert len(starts) >= 8, (
        f"{_SKILL_MD}: only {len(starts)} copyable lines carry `{_START_CALL}`, "
        "fewer than the eight dispatch kinds the lane documents; the missing "
        "lanes run without a ledger row."
    )
    kinds = {match.group(1) for line in starts if (match := _KIND.search(line.text))}
    assert len(kinds) >= 8, (
        f"{_SKILL_MD}: the start lines name only {len(kinds)} distinct kinds "
        f"({sorted(kinds)}); repeating one kind across dispatches makes the "
        "ledger unable to say which lane spent the time."
    )
    unnamed = sorted(kind for kind in kinds if not _lanes_named(kind))
    assert not unnamed, (
        f"{_SKILL_MD}: the ledger opens rows under kinds that name no dispatch "
        f"this lane makes ({unnamed}). The kinds are how a row is read back "
        f"months later; eight rows filed under invented words say the lane spent "
        "the time and refuse to say on what."
    )
    tasks = []
    for line in starts:
        argument = _TASK_ARGUMENT.search(line.text)
        assert argument, (
            f"{_SKILL_MD}: a start line opens its row without `--task <item>`: "
            f"{line.text!r}. A row with no item cannot be attributed to the "
            "card it was spent on."
        )
        tasks.append(argument.group(1))
    frozen_to_one_literal = len(set(tasks)) == 1 and not _PLACEHOLDER.match(tasks[0])
    assert not frozen_to_one_literal, (
        f"{_SKILL_MD}: every start line hard-codes the same `--task` argument "
        f"({tasks[0]!r}), which is neither a placeholder the reader substitutes "
        "nor the item at hand. Pasted as written, every row on every card is "
        "attributed to one literal string."
    )
    chains = {line.headings for line in starts}
    assert len(chains) >= 4, (
        f"{_SKILL_MD}: the `{_START_CALL}` lines sit under only "
        f"{len(chains)} heading chain(s) "
        f"({sorted(' > '.join(chain) for chain in chains)}). The lane "
        "dispatches from its tests, implement, roster, verify, rework and delta "
        "stages, and a row is opened beside the dispatch it times; one flat "
        "list of command lines is a table of kinds, not eight dispatches that "
        "record themselves."
    )
    roster_kinds = {
        match.group(1)
        for line in _carrying(_section("Roster"), _START_CALL)
        if (match := _KIND.search(line.text))
    }
    opened = {lane for kind in roster_kinds for lane in _lanes_named(kind)}
    unopened = [lane for lane in _ROSTER_LANES if lane not in opened]
    assert not unopened, (
        f"{_SKILL_MD}: the roster's start lines ({sorted(roster_kinds)}) open no "
        f"row for {unopened}. Five lenses go out from there in one message, and "
        "a lane whose row is opened elsewhere on the page - or under a kind that "
        "names some other lane - is a lane the operator dispatches without "
        "opening one."
    )
    ends = _assert_live(
        _carrying(list(_passages()), _END_CALL),
        _END_CALL,
        missing=(
            f"nothing offers `{_END_CALL}` as a command line to copy, so every "
            "row the lane opens stays open and no dispatch ever gets an outcome "
            "or an elapsed time."
        ),
        cancelled=f"`{_END_CALL}` is listed among commands the reader must not run.",
    )
    assert any("--outcome" in line.text for line in ends), (
        f"{_SKILL_MD}: the documented `{_END_CALL}` line carries no `--outcome`, "
        "so a closed row cannot say whether its dispatch succeeded."
    )


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
