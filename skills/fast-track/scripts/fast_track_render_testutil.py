"""The fast-track runbook's render blocks, read as flags rather than as prose.

Split out of test_fast_track_renders.py to keep both files under the file size
limit; the pins themselves stay there. Same division as the reader model in
fast_track_prose_testutil.py, which this module reads the document through, and
as the three vocabularies beside it: the parsing and the reasoning behind it
live here, so each pin stays one readable run down the page.

Every prompt this lane sends is rendered by `render_prompt.py` from a fenced
`bash` block, and that script opens each path it is handed: `--set-file` and
`--set-cmd` name files it reads, `--out` names the one file it writes. A render
block is therefore not prose about paths, it is a list of files to open, and the
questions worth asking of it are questions about files - does anything write
this one, does it write it before the operator runs the block, is the read aimed
at a path the item has not created yet. `render_prompt.py` exits 4 on a missing
input, and it does so in the operator's terminal, halfway through an item that
has already spent a dispatch.

That is why nothing here greps. A pin matched on the string
`fast-track-<item>-files.txt` is answered by deleting the string, which leaves
the flag pointed somewhere else and the defect exactly where it was. These
helpers take the block apart into `(name, key, value)` triples and hand the pins
the paths, so a document that rewords every sentence around a broken flag still
fails.

Line numbers ride along because "before" is the whole rule for half of these
pins. A reader works down the page, so a file staged two sections below the
block that reads it is a file that does not exist at the moment of the read, and
only the line number can tell that from a file staged two sections above.

Two things a flag reader has to keep hold of, both learned the hard way. A
missing flag is not a smaller prompt, it is a stopped render - the persona's own
`{PLACEHOLDER}` tokens are the contract, and the renderer exits 1 on the first
one nothing fills - so every question here is asked against the persona rather
than against the flags alone. And a flag value is prose when the document writes
it as English in angle brackets, so it goes through the reader model's polarity
check exactly like the sentences next door: `<... never the ones the card
creates>` carries every word the rule is matched on and instructs the opposite.
"""

from __future__ import annotations

import importlib.util
import re
from functools import cache, lru_cache
from pathlib import Path
from typing import NamedTuple

_TESTUTIL_PATH = Path(__file__).with_name("fast_track_prose_testutil.py")
_TESTUTIL_SPEC = importlib.util.spec_from_file_location(
    "fast_track_prose_testutil",
    _TESTUTIL_PATH,
)
assert _TESTUTIL_SPEC is not None and _TESTUTIL_SPEC.loader is not None
_testutil = importlib.util.module_from_spec(_TESTUTIL_SPEC)
_TESTUTIL_SPEC.loader.exec_module(_testutil)

SKILL_MD = _testutil.SKILL_MD
Passage = _testutil.Passage

# The pack root the document's own banner names: `${CLAUDE_PLUGIN_ROOT}` is
# substituted when the skill loads, and every persona a render block opens hangs
# off it. Taken from the document's own location rather than from an install
# path, because these scripts are not an installed package.
PLUGIN_ROOT_TOKEN = "${CLAUDE_PLUGIN_ROOT}"
PACK_ROOT = SKILL_MD.parent.parent.parent

_HEADING = re.compile(r"^ {0,3}(#{1,6})\s+(.*?)\s*#*$")
_FENCE = re.compile(r"^ {0,3}(?:```|~~~)\s*(\w*)")
_BULLET = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")

# A flag and the value that follows it, up to the next flag. Shell tokenising is
# no use here: the document writes its arguments as placeholders, and
# `<the card's sample_test>` carries an apostrophe that opens a quote a real
# lexer never closes, swallowing the three flags behind it. The flags are what
# the pins read, so the split is on the flags themselves.
_FLAG = re.compile(r"(?:^|\s)(--[A-Za-z][\w-]*)(?:[ \t]+|=)")

# What the renderer substitutes, and what it refuses to leave standing: a
# `{PLACEHOLDER}` no flag fills exits 1 before the prompt file is written. The
# document already says so, about the blind lane's three. That makes the
# persona's own placeholder list the contract a render block is written
# against - drop a flag and the block stops rendering, rather than quietly
# sending a thinner prompt.
PLACEHOLDER = re.compile(r"\{([A-Z_][A-Z0-9_]*)\}")

# How this document writes an argument it cannot spell out: the operator
# substitutes `<each Files entry that exists today>` by hand before pasting. So
# a persona path carrying one is a path with no single file behind it.
ANGLE = re.compile(r"<[^<>]*>")

# The one directory the lane both writes and reads inside a single run, so the
# only one where a read can outrun its write. A render reading the pack's own
# `references/rubric.md` reads a file the plugin ships, and a card's `## Files`
# entry is the operator's to have on disk; neither is this lane's to stage.
TMP_PATH = re.compile(r"(?:\$PWD/)?dev/local/tmp/[^\s'\"`)]+")

# What a step has to claim before it counts as the thing that puts a file there.
# Deliberately narrow: `read`, `hand` and `name` are all things the document
# says about a path it never creates, and a mention is not a write. `render` is
# left out on purpose - a rendered file is already covered, by the `--out` of
# the block that renders it, and letting the word count would make "render the
# prompt from that file" read as writing the file it reads.
WRITES = re.compile(
    r"""(?:
          \bwrit(?:e|es|ing|ten)\b
        | \bstag(?:e|es|ed|ing)\b
        | \bsave[sd]?\b | \bsaving\b
        | \bcop(?:y|ies|ied)\b
        | \bappend\w*
        | \bcreat(?:e|es|ed)\b
        | \bputs?\b
    )""",
    re.IGNORECASE | re.VERBOSE,
)

# The card's `## Files` list splits in two, and the document already has words
# for both halves: `--require-file <each Files entry that exists today>` against
# `--require-parent <each Files entry the card creates>`. An interface read
# aimed at the first half opens files that are there; aimed at the whole list it
# opens one the item is about to write, and `cat` on a missing path takes the
# render down with it.
EXISTING = re.compile(
    r"\bexists?\b|\bexisting\b|\balready\b|\bon\s+disk\b|\bpresent\b",
    re.IGNORECASE,
)
PLANNED = re.compile(
    r"""(?:
          \bcreat\w+ | \bplanned\b
        | \bwill\s+(?:add|write|exist)\b
        | \bdo(?:es)?\s+not\s+exist\b
        | \bnot\s+yet\b
        | \btargets?\s+paths?\b
    )""",
    re.IGNORECASE | re.VERBOSE,
)

# Words that take the restriction back off. A read can carry an existence word
# and still ask for the whole list - `every Files entry, present or absent` says
# `present` and means both halves - so naming one half is not enough on its own:
# nothing in the operand may reach for the other. Kept to words that only ever
# widen; `each` and `every` are how the honest wording counts the half it wants.
UNRESTRICTED = re.compile(
    r"""(?:
          \babsent\b | \bmissing\b | \bwhole\b
        | \bentire\b | \bcomplete\b | \bunfiltered\b
        | \bregardless\b
    )""",
    re.IGNORECASE | re.VERBOSE,
)

# Which block is which. The persona names the dispatch a render is dressing, so
# `agents/ivan.md` is the implementor's render wherever it is printed, and the
# heading is what tells the rework's render from the first one.
IVAN = re.compile(r"\bivan\b", re.IGNORECASE)
TESS = re.compile(r"\btess\b", re.IGNORECASE)
REWORK = re.compile(r"\brework", re.IGNORECASE)

# The confirmed findings, which are the rework's spec the way the test files are
# the first implementor's.
FINDINGS = re.compile(r"finding", re.IGNORECASE)

# Round one's spec. A rework render that reaches for it again is the first
# implementor's prompt wearing a new output path: the tests already pass, so it
# asks for work that is done and says nothing about what the reviewers found.
ROUND_ONE = re.compile(r"\btests?\b", re.IGNORECASE)

CONSTRAINTS = re.compile(r"constraints", re.IGNORECASE)
AGENTS_MD = re.compile(r"\bAGENTS\.md\b")

_CAT = re.compile(r"^\s*cat\b")
_PROMPT_FILE = re.compile(r"--prompt-file[= ]\s*(\S+)")
_KIND = re.compile(r"--kind[= ]\s*(\S+)")


class Command(NamedTuple):
    """One command of a fenced `bash` block, continuation lines joined.

    `line` is the body line the command starts on, and `section` the `##`
    heading a reader was under when they reached it.
    """

    line: int
    section: str
    text: str


class Flag(NamedTuple):
    """One argument of a render call: `--set-file KEY=value` split three ways.

    `key` is empty for the flags that take a bare path (`--out`,
    `--require-file`), which keeps `flag.key == "FILE_PATHS"` an honest question
    to ask of any flag in the block.
    """

    name: str
    key: str
    value: str


class Render(NamedTuple):
    """A `render_prompt.py` call: the persona it fills, and every flag."""

    line: int
    section: str
    persona: str
    out: str
    flags: tuple[Flag, ...]
    text: str


class Dispatch(NamedTuple):
    """A `record_dispatch.py start` call: the lane, and the prompt it sends."""

    line: int
    section: str
    kind: str
    prompt_file: str


class Prose(NamedTuple):
    """A passage a reader reads, with the body line it starts on."""

    line: int
    text: str


def bare(path: str) -> str:
    """A path as the document writes it elsewhere, so two spellings compare.

    One block writes `$PWD/dev/local/tmp/x.txt` and the paragraph above it
    writes the same file without the prefix; a sentence ends in a full stop that
    is not part of the filename. Neither difference is a different file.
    """
    return path.removeprefix("$PWD/").rstrip(".,;:`\"'")


@lru_cache(maxsize=1)
def _scan() -> tuple[tuple[Command, ...], tuple[Prose, ...]]:
    """The body as bash commands and prose passages, each with its line.

    The same split `passages()` makes, with two changes these pins need. A
    fenced block is cut into commands rather than into lines, because a render
    call is one command wrapped over ten lines with backslashes and its flags
    have to be read together. And every unit carries the line it starts on,
    because these pins are about order: which step writes a file, and whether it
    runs before the step that opens it.
    """
    commands: list[Command] = []
    prose: list[Prose] = []
    pending: list[str] = []
    pending_line = 0
    buffer: list[str] = []
    buffer_line = 0
    section = ""
    language = ""
    in_code = False

    def flush_prose() -> None:
        if pending:
            prose.append(Prose(pending_line, " ".join(pending)))
            pending.clear()

    def flush_command() -> None:
        if buffer:
            commands.append(Command(buffer_line, section, " ".join(buffer)))
            buffer.clear()

    for index, line in enumerate(_testutil.body().splitlines()):
        fence = _FENCE.match(line)
        if fence:
            if in_code:
                flush_command()
            else:
                flush_prose()
                language = fence.group(1).lower()
            in_code = not in_code
            continue
        if in_code:
            if language != "bash":
                continue
            stripped = line.strip()
            if not stripped:
                flush_command()
                continue
            if not buffer:
                buffer_line = index
            buffer.append(stripped.removesuffix("\\").strip())
            if not stripped.endswith("\\"):
                flush_command()
            continue
        heading = _HEADING.match(line)
        if heading:
            flush_prose()
            if len(heading.group(1)) == 2:
                section = heading.group(2)
            continue
        if not line.strip() or _BULLET.match(line):
            flush_prose()
        if line.strip():
            if not pending:
                pending_line = index
            pending.append(line.strip())
    flush_prose()
    flush_command()
    return tuple(commands), tuple(prose)


def _unquoted(value: str) -> str:
    """The value without the one pair of quotes the shell would have eaten."""
    text = value.strip()
    for quote in ('"', "'"):
        if len(text) > 1 and text.startswith(quote) and text.endswith(quote):
            return text[1:-1]
    return text


def _flags(text: str) -> tuple[Flag, ...]:
    """Every `--flag value` of one command, the value read up to the next flag.

    A value can hold spaces - `"cat $(printf '%q ' <the card's Files entries>)"`
    is one argument - so the value is everything between this flag and the next,
    quotes peeled off.
    """
    found: list[Flag] = []
    matches = list(_FLAG.finditer(text))
    for position, match in enumerate(matches):
        following = matches[position + 1].start() if position + 1 < len(matches) else -1
        end = len(text) if following == -1 else following
        raw = text[match.end() : end].strip()
        name = match.group(1)
        if name.startswith("--set"):
            key, _, value = raw.partition("=")
            found.append(Flag(name, key.strip(), _unquoted(value)))
        else:
            found.append(Flag(name, "", _unquoted(raw)))
    return tuple(found)


def _render(command: Command) -> Render:
    flags = _flags(command.text)
    matches = list(_FLAG.finditer(command.text))
    head = command.text[: matches[0].start()] if matches else command.text
    words = head.split()
    return Render(
        line=command.line,
        section=command.section,
        persona=words[-1] if len(words) > 2 else "",
        out=next((flag.value for flag in flags if flag.name == "--out"), ""),
        flags=flags,
        text=command.text,
    )


@lru_cache(maxsize=1)
def renders() -> tuple[Render, ...]:
    """Every `render_prompt.py` call the document offers, in page order."""
    commands, _ = _scan()
    return tuple(
        _render(command) for command in commands if "render_prompt.py" in command.text
    )


def persona_file(render: Render) -> Path | None:
    """The persona a block renders, resolved against the pack root.

    None when the document writes the persona as a placeholder: the three
    implementation-aware review lanes share one block over
    `agents/<persona>.md`, and which file that opens is the operator's choice,
    so no fixed set of placeholders belongs to the block.
    """
    spelling = render.persona.replace(PLUGIN_ROOT_TOKEN, str(PACK_ROOT))
    if not spelling or ANGLE.search(spelling):
        return None
    path = Path(spelling)
    return path if path.is_absolute() else PACK_ROOT / path


def _persona_body(path: Path) -> str:
    """The persona as the renderer reads it, its frontmatter dropped."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return text
    end = text.find("\n---", len("---\n"))
    return text if end == -1 else text[end:]


@cache
def persona_keys(render: Render) -> frozenset[str]:
    """Every placeholder the persona this block renders demands a value for.

    Empty for a block whose persona is a placeholder itself, and for one whose
    persona is not on disk - there the document has named no contract, and the
    complaint belongs to `unfilled_placeholders`, not to a caller asking which
    keys count.
    """
    path = persona_file(render)
    if path is None or not path.is_file():
        return frozenset()
    return frozenset(PLACEHOLDER.findall(_persona_body(path)))


def filled_keys(render: Render) -> tuple[str, ...]:
    """The placeholder names the block assigns, duplicates kept.

    Duplicates are kept because they are the interesting case: the renderer
    builds one dictionary, so a second flag for one key silently wins, and the
    block reads as if both values were handed over when only one was.
    """
    return tuple(
        flag.key for flag in render.flags if flag.name.startswith("--set") and flag.key
    )


def reaches_prompt(render: Render, flag: Flag) -> bool:
    """True when this flag's value lands in the text the dispatch receives.

    `--require-file` and `--require-parent` are guards: the renderer checks the
    path and drops it, so a promise written into one is a promise the subagent
    never reads. A `--set*` key the persona has no placeholder for is dropped
    just as quietly, with no error either way.
    """
    if not flag.name.startswith("--set") or not flag.key:
        return False
    keys = persona_keys(render)
    return flag.key in keys if keys else True


def unfilled_placeholders() -> list[str]:
    """One complaint per render block that cannot fill the persona it names."""
    complaints: list[str] = []
    for render in renders():
        path = persona_file(render)
        if path is None:
            continue
        where = f"line {render.line + 1} (`## {render.section}`)"
        if not path.is_file():
            complaints.append(
                f"{where} renders `{render.persona}`, which this pack does not "
                "ship: the renderer exits 2 before it reads a single flag",
            )
            continue
        missing = sorted(persona_keys(render) - set(filled_keys(render)))
        if missing:
            complaints.append(
                f"{where} renders `{path.name}` and leaves {missing} unfilled",
            )
    return complaints


def _first(pattern: re.Pattern[str], text: str) -> str:
    found = pattern.search(text)
    return found.group(1) if found else ""


@lru_cache(maxsize=1)
def dispatches() -> tuple[Dispatch, ...]:
    """Every `record_dispatch.py start` call, with the prompt file it names."""
    commands, _ = _scan()
    return tuple(
        Dispatch(
            line=command.line,
            section=command.section,
            kind=_first(_KIND, command.text),
            prompt_file=_first(_PROMPT_FILE, command.text),
        )
        for command in commands
        if "record_dispatch.py start" in command.text
    )


def read_paths(render: Render) -> tuple[tuple[Flag, str], ...]:
    """The staged files a render opens, one entry per path, with its flag.

    `--set-file` hands `render_prompt.py` a path to read and `--set-cmd` hands
    it a command that reads one, so a `dev/local/tmp` path under either is a
    file that has to be there already. `--out` is the block's own write and
    `--set` is a literal, so neither is here.
    """
    return tuple(
        (flag, bare(found))
        for flag in render.flags
        if flag.name in ("--set-file", "--set-cmd")
        for found in TMP_PATH.findall(flag.value)
    )


def writers(path: str) -> tuple[int, ...]:
    """The body lines at which the document says the lane writes `path`.

    Two ways to write a file, and the document uses both: an earlier render's
    `--out`, or a passage telling the operator to stage, save or copy something
    there with the Write tool. The passage has to say it as a claim that stands
    - polarity comes from the reader model, so "nothing writes X here" is not a
    step that writes X.
    """
    found = [render.line for render in renders() if bare(render.out) == path]
    _, prose = _scan()
    for passage in prose:
        if path not in {bare(name) for name in TMP_PATH.findall(passage.text)}:
            continue
        if any(
            _testutil.asserted(sentence, WRITES)
            for sentence in _testutil.sentences_carrying(passage.text, path)
        ):
            found.append(passage.line)
    return tuple(sorted(found))


def unwritten_inputs() -> list[str]:
    """One complaint per staged file a render opens before anything writes it.

    Named down to the flag, because that is what the operator has to change:
    the key says which placeholder went hungry, and the line says which block
    exits 4 when they run it.
    """
    complaints: list[str] = []
    for render in renders():
        for flag, path in read_paths(render):
            written = writers(path)
            if any(line < render.line for line in written):
                continue
            where = (
                f"staged only at line {written[0] + 1}, below it"
                if written
                else "staged nowhere in the document"
            )
            complaints.append(
                f"`{flag.name} {flag.key or flag.value}` at line "
                f"{render.line + 1} (`## {render.section}`) reads `{path}`, "
                f"{where}",
            )
    return complaints


def unqualified_read(render: Render) -> str:
    """What the interface read opens that nothing promises is on disk.

    A path the lane staged itself is covered by the write-before-read pin, so it
    is dropped here; what is left is the operator's own list, and that list has
    to say which half of it. It has to say so as a claim, too, and reach for
    nothing wider: `every Files entry, whether or not it exists` carries the
    word `exists` while asking for the half that does not, and `present or
    absent` carries it while asking for both. Empty means the read is safe.
    """
    value = " ".join(
        flag.value for flag in render.flags if flag.key == "PUBLIC_INTERFACES"
    )
    operand = TMP_PATH.sub(" ", _CAT.sub(" ", value, count=1)).strip()
    if not operand:
        return ""
    restricted = (
        _testutil.asserted(operand, EXISTING)
        and not PLANNED.search(operand)
        and not UNRESTRICTED.search(operand)
    )
    return "" if restricted else operand


def context_complaint(render: Render) -> str:
    """Why this implementor render starves ARCHITECTURE_CONTEXT, or ''.

    Three ways to fill the placeholder with nothing usable. Two flags fighting
    over it: the renderer keeps one, and which one is not the document's to say.
    A `--set` literal: the implementor then reads the operator's sentence about
    the constraints instead of the constraints themselves, and a sentence is
    where a document can say a thing is withheld while naming it. And a value
    that names the two halves in order to deny them, which is what the polarity
    check next door exists for - a flag value written as English is prose too.
    """
    flags = [flag for flag in render.flags if flag.key == "ARCHITECTURE_CONTEXT"]
    if len(flags) != 1:
        return f"{len(flags)} flag(s) fill ARCHITECTURE_CONTEXT"
    flag = flags[0]
    if flag.name == "--set":
        return (
            f"ARCHITECTURE_CONTEXT is the literal {flag.value!r}, not a file "
            "the render reads"
        )
    missing = [
        name
        for name, rule in (
            ("`## Constraints`", CONSTRAINTS),
            ("`AGENTS.md`", AGENTS_MD),
        )
        if not _testutil.asserted(flag.value, rule)
    ]
    if missing:
        return f"ARCHITECTURE_CONTEXT={flag.value!r} does not name {missing}"
    return ""


def planned_flags(render: Render) -> tuple[Flag, ...]:
    """The block's flags that hand the dispatch the paths the item will create.

    A flag counts on two conditions. Its value has to reach the prompt, so a
    `--require-file` guard is out: the renderer checks that path and drops it,
    and the subagent never sees the wording. And it has to state the naming
    rather than deny it, so `<each Files entry that exists today, never the ones
    the card creates>` is not a flag that names them. `PUBLIC_INTERFACES` is out
    too - it is the read the other pin restricts, and one broken flag should not
    answer both.
    """
    return tuple(
        flag
        for flag in render.flags
        if flag.key != "PUBLIC_INTERFACES"
        and reaches_prompt(render, flag)
        and _testutil.asserted(flag.value, PLANNED)
    )


def unspecced_rework(render: Render) -> str:
    """What this rework render hands its implementor instead of the findings.

    The confirmed findings are the rework's spec the way the failing tests were
    round one's, and the document stages them into a file of their own. So the
    flag has to name that file and the document has to write it above the block:
    a name with nothing behind it renders exit 4, and a `cat` of the test files
    renders round one's prompt again under a new output path. The word
    `findings` in a shell comment is neither.
    """
    value = " ".join(flag.value for flag in render.flags if flag.key == "FAILING_TESTS")
    if not value:
        return "no `--set*` flag fills FAILING_TESTS"
    if ROUND_ONE.search(TMP_PATH.sub(" ", _CAT.sub(" ", value, count=1))):
        return f"FAILING_TESTS reads round one's tests again: {value!r}"
    staged = [
        path
        for path in (bare(found) for found in TMP_PATH.findall(value))
        if FINDINGS.search(path) and any(line < render.line for line in writers(path))
    ]
    if not staged:
        return (
            f"FAILING_TESTS={value!r} names no findings file the document "
            "writes above this block"
        )
    return ""


def fills(render: Render, key: str) -> bool:
    """True when some flag of the block assigns this placeholder.

    A question about presence only. Reading the values back out is each pin's
    own job, and joining them was how a block that filled one placeholder twice
    read as one satisfied placeholder: two flags fighting over a key are two
    different prompts, and the renderer picks one of them without saying which.
    """
    return any(flag.key == key for flag in render.flags)


def sentences_asserting(
    candidates: list[Passage],
    rule: re.Pattern[str],
) -> list[str]:
    """The section's sentences that state `rule` rather than deny it.

    The pins reach for this where a promise may live in prose instead of in a
    flag. Polarity is the reader model's, for the reason every sibling pin has
    it: "the entries the card creates are not named here" carries every word the
    rule is matched on and says the opposite.
    """
    return [
        sentence.strip()
        for passage in candidates
        if not passage.is_code
        for sentence in _testutil.sentences_carrying(passage.text, rule)
        if _testutil.asserted(sentence, rule)
    ]
