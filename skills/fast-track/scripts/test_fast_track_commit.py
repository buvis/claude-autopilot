"""Commit pins for the fast-track driver skill (skills/fast-track/SKILL.md).

The lane ends every item with a commit the operator types, and that commit is
the one step here no later section can take back. `git commit -m` with no
pathspec commits the index as it stands, and the index is shared: a path
somebody else staged before the lane started ships under the item's message.
The card's `changelog` field is the other gap - `card.py` parses it and
`spec-card.md` documents it, but the implementor never sees the card, so the
entry reaches `CHANGELOG.md` by the operator's hand or not at all.

So these pins read the commit step the way the prose pins next door read the
roster, and they read the command lines the way git does. A flag cluster is
read letter by letter (`-qi` is `-i`), a quoted `':/'` is `:/`, a `#` opens a
comment and not a path, and the pathspec has to be the footer's paths and only
those: one placeholder that reads as the footer's paths, `CHANGELOG.md` beside
it when the card asks, nothing else. Every commit line a section offers has to
carry that section's one message, because a second line under another message
is a second commit. The changelog rule has to be a live instruction with its
polarity intact, and polarity is read past the verb as well as before it:
`write nothing` and `stays out of the paths` are denials wearing a write verb.
`none` needs care: it is the field's empty value in this document, and the
reader model's NEGATOR lists it, so every polarity check here swaps the literal
out before it asks.

These pins live here rather than in test_fast_track_prose.py because that file
is at the project's file size limit. Same split as the render pins beside it.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from types import ModuleType


def _sibling(name: str) -> ModuleType:
    """A helper module read from beside this file, never from an install path.

    These scripts are not an installed package, so the reader model comes in by
    path, the way `card.py` does.
    """
    spec = importlib.util.spec_from_file_location(
        name,
        Path(__file__).with_name(f"{name}.py"),
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_testutil = _sibling("fast_track_prose_testutil")

_SKILL_MD = _testutil.SKILL_MD
_Passage = _testutil.Passage
_CANCELS = _testutil.CANCELS
_NEGATOR = _testutil.NEGATOR
_section = _testutil.section
_carrying = _testutil.carrying
_code_fragments = _testutil.code_fragments
_sentences_carrying = _testutil.sentences_carrying
_asserted = _testutil.asserted
_assert_live = _testutil.assert_live
_assert_unopposed = _testutil.assert_unopposed

# The commit line an operator pastes, read as git reads it: the quoted message,
# then `--`, then the pathspec. Without the pathspec `git commit` takes the
# index as it stands, and the index is shared with whoever staged something
# before the lane started.
_GIT_COMMIT = re.compile(r"^git\s+commit\b")
_GIT_ADD = re.compile(r"^git\s+add\b(?P<operands>.*)$")
_SCOPED_COMMIT = re.compile(
    r"""^git\s+commit\b(?P<flags>.*?)
        \s-m\s+(?P<message>"[^"]*"|'[^']*')
        \s+--\s+(?P<paths>\S.*)$""",
    re.VERBOSE,
)
# The one message each section's commit carries. A commit line under any other
# message is a second commit, whatever its pathspec says.
_ITEM_MESSAGE = "<type>(<scope>): <description>"
_REWORK_MESSAGE = "fix(<item>): address confirmed findings"
# A shell word: a `<placeholder>`, a quoted string, or a run of non-blanks. A
# word opening with `#` starts a comment that runs to the end of the line.
_WORD = re.compile(r"""<[^>]*>|"[^"]*"|'[^']*'|\S+""")
# Flags that hand the command more than the paths it names, read letter by
# letter: `-i` commits the index alongside the pathspec whether it is typed as
# `-i`, `-qi` or `-iq`; `-a` and `-A` take every tracked or every dirty path;
# `-u` every tracked one. Git also takes any unambiguous prefix of a long
# option, so `--inc` and `--al` are the options they abbreviate.
_SHORT_SWEEP = re.compile(r"^-[a-zA-Z]*[aiAu][a-zA-Z]*$")
_LONG_SWEEP_NAMES = ("all", "include", "interactive", "update")
# The one operand a scoped command may carry: a placeholder that reads as the
# footer's paths. One that names a place those paths live in (`<the repo root,
# where every footer path lives>`) is the whole tree under another name.
_FOOTER_PLACEHOLDER = re.compile(
    r"""^<(?=[^>]*\bpaths?\b)(?=[^>]*\b(?:footer|touched)\b)
        (?![^>]*\b(?:root|tree|repo\w*|whole|entire|every\s*thing|all\s+files
                     |director\w*|dir|folder|under|below|beneath|inside|within
                     |contain\w*|live\w*|sit\w*|parent|glob|pattern|wildcard)\b)
        [^>]*>$""",
    re.IGNORECASE | re.VERBOSE,
)

# Prose that hands the commit the whole index. Read with `asserted`, so a
# sentence forbidding it is exempt; the patterns ask for the act of committing
# everything, not for the word `staged`, because the promise itself says what
# is left staged.
_SWEEPING_COMMIT = re.compile(
    r"""(?:
          \bcommits?\s+(?:everything|whatever)\b
        | \bcommits?\s+(?:all|any)\s+(?:the\s+|of\s+the\s+)?(?:staged|index)\w*
        | \b(?:everything|whatever|all)\s+(?:that\s+is\s+|already\s+)?staged\s+
          (?:is|gets|goes|lands)\s+(?:committed|in(?:to)?\s+the\s+commit)\b
        | \bcommits?\s+the\s+(?:whole\s+|entire\s+|full\s+)?
          (?:index|tree|worktree|working\s+tree)\b
        | \bgit\s+add\s+(?:-A|--all|\.)(?=\s|$)
        | \bgit\s+commit\s+(?:-a|--all)\b
    )""",
    re.IGNORECASE | re.VERBOSE,
)

# The card's field and the file it feeds. The field is lowercase `changelog`
# and `CHANGELOG.md` is the file, so the field is matched case-sensitively and
# never as the file's stem.
_FIELD = re.compile(r"\bchangelog\b(?!\.md)")
_FILE = "CHANGELOG.md"
_UNRELEASED = "[Unreleased]"
# Any of the rule's four literals: the sentences the rule is written in.
_ABOUT_THE_CHANGELOG = re.compile(r"changelog|\[unreleased\]|\bnone\b", re.IGNORECASE)
# `none` is a value here, not a negator. The reader model's NEGATOR lists it, so
# every polarity check below swaps the literal for a word that negates nothing
# before asking whether a sentence writes or denies. `not none` is swapped
# first, as one word: it is the entry branch's condition, not a negation of
# the verb that follows it.
_NONE = re.compile(r"`none`|\bnone\b", re.IGNORECASE)
# `none` governed by a negation or an exception is the branch that carries an
# entry; bare `none` is the other branch.
_NOT_NONE = re.compile(
    r"""\b(?:not|isn't|other\s+than|anything\s+but|any\s+\w+\s+but|except|unless
        |besides|apart\s+from|rather\s+than|instead\s+of)\b
        (?:\s+[\w'`.-]+){0,4}?\s*`?\bnone\b`?""",
    re.IGNORECASE | re.VERBOSE,
)
# The clause breaks inside one sentence, as the reader model draws them.
_CLAUSE = re.compile(r"[;:]|\s+-\s+")
# What the entry branch does to the file, and what the none branch denies. No
# `commit` here: in this section it is the noun (`the commit names`), and a
# none branch that mentions the commit would read as a write.
_WRITES = re.compile(
    r"\b(?:write|writes|written|add|adds|added|append|appends|appended|edit|edits"
    r"|edited|put|puts|insert|inserts|inserted|stage|stages|staged|touch|touches"
    r"|touched|update|updates|updated)\b",
    re.IGNORECASE,
)
# A write verb under a determiner is a noun: `the Write tool` writes nothing.
_DETERMINER = re.compile(
    r"\b(?:a|an|the|this|that|these|those|its|their|your|one|each|every|any|no)\s+$",
    re.IGNORECASE,
)
# A denial sitting right after the verb: `write nothing`, `add no line`.
_DENIED_OBJECT = re.compile(
    r"\b(?:nothing|nowhere|no|none|nobody|neither)\b", re.IGNORECASE
)
_DENIES = re.compile(
    r"\b(?:no|not|never|nothing|nowhere|nobody|neither|nor|cannot|avoid|skip|skips"
    r"|skipped|without|alone|untouched|unchanged|unmodified|stays?)\b|n't\b",
    re.IGNORECASE,
)
# The entry lands in the item's commit: the file, `it`, the entry or the line
# added to the paths the commit names, or named as the same commit. The span
# between verb and object stops at a clause break, not at a dot: inside one
# sentence a dot is part of a token, and `CHANGELOG.md` is the token that sits
# there. No verb-less alternative: `stays out of the paths the commit names`
# carries the words and keeps the file out.
_INTO_THE_COMMIT = re.compile(
    r"""(?:
          \b(?:add|adds|added|stage|stages|staged|include|includes|included
             |name|names|named|put|puts|list|lists|join|joins|joined)\b
          (?P<span>[^;:]*?)\b(?:paths?|pathspec|commit)\b
        | \bsame\s+commit\b
    )""",
    re.IGNORECASE | re.VERBOSE,
)
_THE_ENTRY = re.compile(
    r"CHANGELOG\.md|\bit\b|\bthe\s+(?:entry|file|line)\b", re.IGNORECASE
)
# Words that keep the file out of the commit while the sentence talks about it.
_KEPT_OUT = re.compile(
    r"""\b(?:out\s+of|outside|away\s+from|off|stays?|stayed|remains?|remained
        |left|leaves?|excluded?|omit\w*|drop\w*|apart\s+from|instead\s+of
        |rather\s+than|waits?)\b""",
    re.IGNORECASE | re.VERBOSE,
)
# A changelog entry committed anywhere but with the implementation.
_APART_FROM_THE_ITEM = re.compile(
    r"""(?:
          \b(?:separate|second|third|extra|fresh|new|another|different|dedicated
             |standalone|later|follow-?up|its\s+own|of\s+its\s+own)\s+commit\b
        | \bcommit\s+of\s+its\s+own\b
        | \bcommit\w*\s+(?:it\s+|them\s+)?
          (?:separately|apart|alone|by\s+itself|on\s+its\s+own|later|afterwards?)\b
        | \bby\s+itself\b | \bon\s+its\s+own\b
        | \bafter\s+the\s+(?:implementation|item's|first|main)\s+commit\b
        | \b(?:implementation|item's)\s+commit\s+(?:above\s+)?stays\b
        | \bleaves?\s+(?:it\s+)?(?:unstaged|uncommitted|out)\b
        | \bwaits?\s+(?:in\s+the\s+card\s+)?(?:for|until)\b
    )""",
    re.IGNORECASE | re.VERBOSE,
)
# The entry written whatever the field says.
_UNCONDITIONAL = re.compile(
    r"\balways\b|\bregardless\b|\bwhatever\s+(?:the\s+)?(?:field|value|card)\b"
    r"|\bevery\s+(?:item|card)\s+(?:gets|receives|writes|adds)\b",
    re.IGNORECASE,
)

_NO_CHANGELOG = (
    "the `Implement` section never names `CHANGELOG.md`, so the card's "
    "`changelog` entry is parsed by `card.py`, staged in the card file and "
    "written by nobody: the commit lands without it and the release notes "
    "miss the change."
)
_CHANGELOG_CANCELLED = (
    "the `Implement` section names `CHANGELOG.md` only to say the lane no "
    "longer writes it."
)
_NO_COMMIT_LINE = (
    "the `{title}` section offers no `git commit` line to copy, so the "
    "implementor's work is committed by whatever the operator types, and "
    "nothing on the page says which paths."
)
_COMMIT_LINE_CANCELLED = (
    "the `{title}` section's `git commit` line is one the reader is told not to run."
)
_COMMIT_SWEEPS = (
    "{skill}: the `{title}` section's commit sweeps past the footer's paths: "
    "{faulted}. `git commit -m` with no pathspec commits the index as it "
    "stands, and the index is shared: a path somebody else staged before the "
    "lane started ships under the item's message. The one commit line the "
    "section offers carries `{message}` and, after `--`, the paths the "
    "`FILES_TOUCHED:` footer names - with `CHANGELOG.md` beside them when the "
    "card asks - and leaves every other index entry where it was, staged and "
    "uncommitted."
)
_STAGE_SWEEPS = (
    "{skill}: the `{title}` section stages past the footer's paths: {faulted}. "
    "`git add -A`, `git add .` and a `-u` hidden in a flag cluster put every "
    "dirty path in the tree into the index, foreign edits included, and the "
    "commit that follows carries them under the item's message."
)
_INVERTED = (
    "{skill}: the `Implement` section writes the file when the field is "
    "`none`: {inverted}. That is the rule inverted - the word `none` lands "
    "under `[Unreleased]` on a card that asked for no entry, and a card "
    "carrying an entry writes nothing."
)


def _neutral(sentence: str) -> str:
    """The sentence with the card's `none` value swapped for words that negate nothing."""
    return _NONE.sub("that-value", _NOT_NONE.sub("an-entry", sentence))


def _bare_none(sentence: str) -> bool:
    """True when the sentence names `none` with nothing negating or excepting it."""
    return bool(_NONE.search(sentence)) and not _NOT_NONE.search(sentence)


def _cancelled(passage: _Passage) -> bool:
    """True when the passage, or a heading above it, takes its content back."""
    return any(
        pattern.search(text)
        for text in (*passage.headings, passage.text)
        for pattern in _CANCELS
    )


def _words(operands: str) -> list[str]:
    """The operands as shell words: quotes stripped, the `#` comment dropped.

    A `<placeholder>` is one word however many blanks it holds, `':/'` is `:/`
    once the shell has had it, and nothing after `#` reaches git at all.
    """
    found: list[str] = []
    for word in _WORD.findall(operands):
        if word.startswith("#"):
            break
        found.append(word.strip("\"'"))
    return found


def _sweeps(flag: str) -> bool:
    """True when the flag widens the command past the paths it names."""
    if flag.startswith("--"):
        stem = flag[2:].split("=", maxsplit=1)[0]
        return bool(stem) and any(name.startswith(stem) for name in _LONG_SWEEP_NAMES)
    return bool(_SHORT_SWEEP.match(flag))


def _strays(operands: list[str]) -> list[str]:
    """The operands that are neither the footer's paths nor `CHANGELOG.md`."""
    return [
        word
        for word in operands
        if word != _FILE and not _FOOTER_PLACEHOLDER.match(word)
    ]


def _lines(passages: list[_Passage], opener: re.Pattern[str]) -> list[str]:
    """Every fenced or code-span line opening with `opener` that a hand could paste."""
    return [
        fragment.lstrip("$ ")
        for passage in passages
        for fragment in _code_fragments(passage)
        if opener.match(fragment.lstrip("$ "))
    ]


def _commit_complaint(line: str, message: str) -> str | None:
    """Why this commit line is not the section's scoped commit, or None when it is."""
    scoped = _SCOPED_COMMIT.match(line)
    if scoped is None:
        return "no `-- <pathspec>` after the message, so git commits the index as it stands"
    if message not in scoped.group("message"):
        return f"a message other than `{message}`: a second commit, not the item's"
    swept = [flag for flag in _words(scoped.group("flags")) if _sweeps(flag)]
    if swept:
        return f"{swept} commits the index alongside the pathspec"
    operands = _words(scoped.group("paths"))
    if not any(_FOOTER_PLACEHOLDER.match(word) for word in operands):
        return "no operand reading as the paths the footer names"
    if strays := _strays(operands):
        return f"{strays} beside the footer's paths: the whole tree, or a path the footer never named"
    return None


def _add_complaint(line: str) -> str | None:
    """Why this `git add` line stages past the footer's paths, or None when it does not."""
    add = _GIT_ADD.match(line)
    assert add is not None
    words = _words(add.group("operands"))
    flags = [word for word in words if word.startswith("-") and word != "--"]
    operands = [word for word in words if not word.startswith("-")]
    if swept := [flag for flag in flags if _sweeps(flag)]:
        return (
            f"{swept} stages every dirty or every tracked path, foreign edits included"
        )
    if not operands:
        return "no path named, so the flags alone decide what is staged"
    if strays := _strays(operands):
        return f"{strays} beside the footer's paths"
    return None


def _assert_commit_scoped_to_the_footer(title: str, message: str) -> None:
    """The section's commit lines, each carrying the footer's paths as its pathspec.

    Every `git commit` and `git add` the section offers to copy is read, not
    just the one a pin happens to find: a scoped line added beside the bare one
    leaves the operator two lines to paste and the defect in one of them, and a
    second commit under another message is a second commit.
    """
    passages = _section(title)
    _assert_live(
        _carrying(passages, "git commit"),
        "git commit",
        missing=_NO_COMMIT_LINE.format(title=title),
        cancelled=_COMMIT_LINE_CANCELLED.format(title=title),
    )
    faulted = [
        f"{line!r}: {complaint}"
        for line in _lines(passages, _GIT_COMMIT)
        if (complaint := _commit_complaint(line, message))
    ]
    assert not faulted, _COMMIT_SWEEPS.format(
        skill=_SKILL_MD,
        title=title,
        faulted=faulted,
        message=message,
    )
    sweeping = [
        f"{line!r}: {complaint}"
        for line in _lines(passages, _GIT_ADD)
        if (complaint := _add_complaint(line))
    ]
    assert not sweeping, _STAGE_SWEEPS.format(
        skill=_SKILL_MD,
        title=title,
        faulted=sweeping,
    )
    _assert_unopposed(
        passages,
        _SWEEPING_COMMIT,
        f"the `{title}` section hands the commit everything staged - the whole "
        "index, `git add -A`, `commit -a` - somewhere in the section:",
    )


def test_the_implement_commit_names_only_the_footers_paths() -> None:
    # The preconditions promise that the lane stages the card's files and
    # leaves every other dirty path untouched. A bare `git commit -m` breaks
    # that promise one section later: it commits whatever the index already
    # holds, so a path somebody else staged before the lane started ships
    # under the item's message. The pathspec after `--` is what keeps that
    # entry in the index while the footer's paths go out - as long as no flag
    # cluster smuggles `-i` back in and no second operand widens the pathspec.
    _assert_commit_scoped_to_the_footer("Implement", _ITEM_MESSAGE)


def test_the_rework_commit_uses_the_same_scoped_form() -> None:
    # The rework commits a second time from the same shared index, so the same
    # foreign entry ships here if the scoped form stops at the first commit.
    # The message is the one the lane has always given this commit; a scoped
    # line under some other message leaves the operator to invent one, and a
    # commit nobody can find as the rework afterwards.
    _assert_commit_scoped_to_the_footer("Rework", _REWORK_MESSAGE)


def _writes(text: str) -> bool:
    """True when some clause of `text` writes the file.

    A write verb counts when no negator governs it in its own clause, no
    determiner makes it a noun (`the Write tool`), and no denial sits right
    after it as its object (`write nothing`, `add no line`). The verb alone is
    not a write; `Write nothing under [Unreleased]` carries every pinned word
    and tells the operator to leave the file alone.
    """
    for clause in _CLAUSE.split(_neutral(text)):
        for verb in _WRITES.finditer(clause):
            head = clause[: verb.start()]
            if _NEGATOR.search(head) or _DETERMINER.search(head):
                continue
            tail = " ".join(clause[verb.end() :].split()[:3])
            if _DENIED_OBJECT.search(tail):
                continue
            return True
    return False


def _committed_with_the_item(sentence: str) -> bool:
    """True when the sentence puts the entry into the item's own commit.

    The verb has to act on the file, `it`, the entry or the line; the clause in
    front of it may not negate it or keep it out (`stays out of the paths the
    commit names`); and the span between verb and object may not deny it
    (`adds nothing to the paths`).
    """
    for clause in _CLAUSE.split(_neutral(sentence)):
        for match in _INTO_THE_COMMIT.finditer(clause):
            head = clause[: match.start()]
            if _NEGATOR.search(head) or _KEPT_OUT.search(head):
                continue
            span = match.group("span") or ""
            if _DENIES.search(span) or _KEPT_OUT.search(span):
                continue
            if match.group("span") is not None and not _THE_ENTRY.search(head + span):
                continue
            return True
    return False


def _writes_when_none(passages: list[_Passage]) -> list[str]:
    """Sentences anywhere in the passages that write with the field at bare `none`.

    Read over every prose sentence, not only the ones naming the file: the
    inverted branch can sit one sentence after the one that names it (`A
    changelog of none leaves CHANGELOG.md untouched. The file still takes its
    line from you: put the word none under [Unreleased]`). The clause carrying
    `none` is the one asked whether it writes, so a sentence that writes in one
    clause and denies `none` in the next is not the inversion.
    """
    return sorted(
        {
            sentence.strip()
            for passage in passages
            if not passage.is_code and not _cancelled(passage)
            for sentence in _sentences_carrying(passage.text, _NONE)
            if _bare_none(sentence)
            and any(
                _writes(clause)
                for clause in _CLAUSE.split(sentence)
                if _NONE.search(clause)
            )
        },
    )


def _assert_the_changelog_rule_is_live(implement: list[_Passage]) -> list[_Passage]:
    """The live passages that name both the file and the card's field."""
    live = _assert_live(
        [passage for passage in implement if _FILE.lower() in passage.text.lower()],
        _FILE,
        missing=_NO_CHANGELOG,
        cancelled=_CHANGELOG_CANCELLED,
    )
    naming = [passage for passage in live if _FIELD.search(passage.text)]
    assert naming, (
        f"{_SKILL_MD}: the passage that writes `CHANGELOG.md` never names the "
        "card's `changelog` field, so what goes into the file - and whether "
        "anything does - is the operator's guess rather than the card's value."
    )
    return naming


def _assert_committed_with_the_item(
    implement: list[_Passage], naming: list[_Passage]
) -> None:
    """The entry goes out in the item's commit, and in no commit of its own."""
    committed = [
        sentence
        for passage in naming
        for sentence in _sentences_carrying(passage.text, _FILE)
        if _committed_with_the_item(sentence)
    ] or [
        match.group(0)
        for line in _lines(implement, _GIT_COMMIT)
        if (match := _SCOPED_COMMIT.match(line))
        and _FILE in _words(match.group("paths"))
        and _ITEM_MESSAGE in match.group("message")
    ]
    assert committed, (
        f"{_SKILL_MD}: `CHANGELOG.md` is written but never added to the paths "
        "the commit names. Once the commit is scoped to the footer's paths, a "
        "file outside them stays dirty in the tree: the item commits without "
        "its entry and the next card's precondition finds a foreign path."
    )
    apart = sorted(
        {
            sentence.strip()
            for passage in implement
            for sentence in _sentences_carrying(passage.text, "changelog")
            if _asserted(sentence, _APART_FROM_THE_ITEM)
        },
    )
    assert not apart, (
        f"{_SKILL_MD}: the `Implement` section commits the changelog entry apart "
        f"from the implementation: {apart}. The entry describes the change it "
        "ships with; in its own commit it describes a change that is not there, "
        "and a blocked exit parks the implementation and leaves the entry."
    )


def test_a_changelog_entry_is_written_under_unreleased_and_committed_with_the_item() -> (
    None
):
    # `card.py` parses the card's `changelog` field, and nothing downstream
    # reads it unless this section does: the implementor never sees the card,
    # so the entry the card author wrote reaches `CHANGELOG.md` by the
    # operator's hand or not at all. Read for polarity as well as presence -
    # `none` is the field's empty value, and a sentence that writes the entry
    # when the field is `none`, or writes nothing when it carries one, holds
    # every pinned string and inverts the rule.
    implement = _section("Implement")
    naming = _assert_the_changelog_rule_is_live(implement)
    writing = [
        sentence
        for passage in naming
        for sentence in _sentences_carrying(passage.text, _FILE)
        if _writes(sentence)
    ]
    assert writing, (
        f"{_SKILL_MD}: `CHANGELOG.md` and the `changelog` field share a passage "
        "in the `Implement` section, but no sentence there writes the entry "
        "into the file - or the only write verb there writes nothing. Named and "
        "never written, the entry stays in the card."
    )
    inverted = _writes_when_none(implement)
    assert not inverted, _INVERTED.format(skill=_SKILL_MD, inverted=inverted)
    assert any(_UNRELEASED in sentence for sentence in writing), (
        f"{_SKILL_MD}: the sentence writing `CHANGELOG.md` never says the entry "
        "goes under `[Unreleased]`, so the operator appends it wherever the "
        "file ends - under the last release, or after nothing."
    )
    _assert_committed_with_the_item(implement, naming)


def test_a_changelog_of_none_leaves_changelog_md_untouched() -> None:
    # The other half of the rule. Without it the entry branch reads as the
    # whole rule, and an operator handed `changelog: none` writes the word
    # `none` under `[Unreleased]` or invents an entry: either way the release
    # notes carry a line no card asked for. The branch is a denial, so it is
    # read as one - bare `none`, a denying word, and no write asserted - and
    # only in a passage that is not cancelled; and no sentence anywhere in the
    # section, naming the file or not, may write with the field at `none`.
    implement = _section("Implement")
    about = [
        passage
        for passage in implement
        if not _cancelled(passage) and _FILE.lower() in passage.text.lower()
    ]
    assert about, f"{_SKILL_MD}: {_NO_CHANGELOG}"
    untouched = sorted(
        {
            sentence.strip()
            for passage in about
            for sentence in _sentences_carrying(passage.text, _NONE)
            if _bare_none(sentence)
            and _DENIES.search(_neutral(sentence))
            and not _writes(sentence)
        },
    )
    assert untouched, (
        f"{_SKILL_MD}: no sentence beside `CHANGELOG.md` in the `Implement` "
        "section says what happens when `changelog` is `none`, or the sentence "
        "that names `none` still writes the file. The entry branch alone is a "
        "rule with no off switch: a card that asked for no entry gets one."
    )
    inverted = _writes_when_none(implement)
    assert not inverted, _INVERTED.format(skill=_SKILL_MD, inverted=inverted)
    always = sorted(
        {
            sentence.strip()
            for passage in implement
            if not passage.is_code
            for sentence in _sentences_carrying(passage.text, _ABOUT_THE_CHANGELOG)
            if _asserted(_neutral(sentence), _UNCONDITIONAL)
        },
    )
    assert not always, (
        f"{_SKILL_MD}: the `Implement` section writes the changelog whatever "
        f"the field says: {always}. The `none` branch is then a sentence the "
        "operator reads and a rule they do not follow, and `CHANGELOG.md` "
        "changes on every item."
    )
