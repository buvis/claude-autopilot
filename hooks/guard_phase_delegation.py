#!/usr/bin/env python3
"""PreToolUse hook (Agent): deny an Agent call that hands a whole phase skill
to a subagent.

PRD 00248. The 2026-10-03 00242 build session dispatched Agent calls that told
a subagent to run /autopilot:work, /autopilot:plan-tasks or
/autopilot:design-solution instead of running the phase skill itself with the
Skill tool. Phase skills must stay in the session; Agent calls are for
per-task subagents (Ivan, Tess, Devon, reviewers) only.

Denies (exit 2, reason on stderr) iff `_AUTOPILOT_LOOP` is set, the tool is
`Agent`, and `find_phase_delegation` quotes a span of the prompt or the
description. The rule is structural, not a verb list: a recognized phase name
counts when it stands as the thing to run - a strong anchor ("for"/"on" a PRD,
task or number, "from task", a PRD-lifecycle path, or a whole-run marker in the
same sentence) or a weak one (the name ends its clause, behind a word that is
not a preposition). Any unparseable payload fails open.
"""

from __future__ import annotations

import os
import re
import sys
import unicodedata
from bisect import bisect_left
from collections.abc import Iterator
from itertools import islice
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import allow, block, read_input

# The lexical layer, kept in a sibling module for the file-size limit and
# imported back by name so every constant still resolves as
# `guard_phase_delegation.<name>` (the hook's own code reads them as module
# globals, and the test modules introspect them there).
from guard_phase_delegation_lexicon import (
    _AGOGE_PERSONAS,
    _AGOGE_PREFIX,
    _BARE_SLASH_PREFIX,
    _CITE_SENTENCE_BOUNDARY,
    _CLAUSE_BOUNDARY,
    _DETERMINERS,
    _FOLLOW,
    _MASK_TABLE,
    _MASKED_IN_SPAN,
    _NEGATION,
    _NEGATION_WORD_GAP,
    _PER_TASK_PERSONAS,
    _PHASE_BARE,
    _PHASE_CONCEPT,
    _PHASE_NAME_FORMS,
    _PHASE_SKILL,
    _PRD_PATH_TAIL,
    _PRD_STORE_PATH,
    _PREPOSITIONS,
    _READ_ONLY_REVIEWERS,
    _SENTENCE_BOUNDARY,
    _SKILL_MD_PATH,
    _SKILL_SUFFIX,
    _STRONG_ANCHOR_TAIL,
    _SYMMETRIC_DELIMS,
    _TASK_ID,
    _TASK_RANGE_LEAD,
    _TASK_RANGE_TAIL,
    _WEAK_ANCHOR_TAIL,
    _WHOLE_RUN_MARKERS,
    _WORD_CHAR,
    _WORD_START,
    _WRAP,
    _WRAP_CLOSE,
    _WRAP_OPEN,
    _WRAP_PAIR,
    _WRAP_SCAN_PAIRS,
)

# Unicode categories dropped outright by _normalize. Mn (combining marks) so a
# decomposed accent cannot split a word ("work" with U+0301 after the "o"); Cf
# (format characters) because they are invisible and do the same (U+200B,
# U+200C, U+200D, U+2060, U+FEFF, U+2061, U+180E, and U+00AD the soft hyphen).
# Nothing else: a Cyrillic "o" (U+043E) is a different letter, not a lookalike
# form, and folding letters would be guesswork. So a cross-script homoglyph such
# as "/autopilot:w<U+043E>rk" passes this guard unflagged: NFKD/NFKC fold
# compatibility and combining forms, never cross-script lookalikes, and the
# harness itself would not resolve such a spelling as a real skill name, so this
# is an accepted, documented gap rather than a defect.
# Every code point here is NAMED, never pasted: these characters are invisible
# or combining, so a pasted one is unreadable in a comment and an editor or
# formatter would silently destroy it.
_DROPPED_CATEGORIES = frozenset({"Mn", "Cf"})
# Characters NFKD leaves alone but that read as plain ASCII around a skill
# name: the math minus (U+2212) in "/autopilot:plan<U+2212>tasks", which is
# category Sm and so is missed by the Pd fold in _normalize; the curly single
# quotes (U+2018, U+2019); and the Markdown emphasis asterisks in "Run the
# **work** phase". The dash family itself is NOT listed here: _normalize folds
# the whole Pd category per character instead, because a literal U+2010-U+2015
# range leaves the other Pd code points (U+301C, U+05BE) unfolded.
_FOLDED = {0x2212: "-", 0x2018: "'", 0x2019: "'", 0x002A: None}
# The runs _normalize's per-character pass has to walk: everything outside
# ASCII. The equivalence argument for skipping the ASCII runs is in _normalize.
_NON_ASCII_RUN = re.compile(r"[^\x00-\x7f]+")


def _fold_run(match: re.Match[str]) -> str:
    """_normalize's per-character pass, over one run of non-ASCII characters:
    drop every combining mark and format character, fold every
    dash-punctuation (Pd) code point to "-", keep everything else."""
    kept = []
    for char in match.group(0):
        category = unicodedata.category(char)
        if category in _DROPPED_CATEGORIES:
            continue
        kept.append("-" if category == "Pd" else char)
    return "".join(kept)


def _normalize(text: str) -> str:
    """Reduce lookalike text to its plain form, so a dispatch cannot dodge the
    patterns by spelling a skill name in compatibility or invisible characters.

    NFKD folds the compatibility forms (U+FF57 fullwidth "w", U+2011
    non-breaking hyphen) and splits precomposed accents apart, then one pass
    drops every combining mark and format character (_DROPPED_CATEGORIES) and
    folds every dash-punctuation (Pd) code point to "-". A trailing NFKC
    recomposes what survived, so the caller reads the character count of the
    source text. Finally the math minus, curly quotes and emphasis asterisks
    fold to ASCII (_FOLDED). Whitespace is untouched: a newline inside a field
    is a clause and sentence boundary.

    That per-character pass runs on the non-ASCII runs ONLY (_NON_ASCII_RUN),
    which is the same result for EVERY input, not a sampling or a cutoff: on an
    ASCII character the loop is the identity, because no ASCII code point is
    category Mn or Cf (so nothing is dropped) and the single ASCII code point
    in category Pd is U+002D, the hyphen-minus, which the Pd fold maps to
    itself. The stages around it still see the whole string: NFKD and NFKC stay
    full-string calls (both are the identity on ASCII, so skipping the loop on
    an ASCII run cannot change what they recompose), and the _FOLDED translate
    stays a full-string call because one of its keys, U+002A, the asterisk, IS
    ASCII. So the cost follows a field's non-ASCII content, not its length: a
    field with no non-ASCII character costs two C-level normalization scans,
    one C-level regex scan and one translate, instead of a Python iteration per
    character.
    """
    folded = _NON_ASCII_RUN.sub(_fold_run, unicodedata.normalize("NFKD", text))
    return unicodedata.normalize("NFKC", folded).translate(_FOLDED)


def _is_per_task_persona(subagent_type: str | None) -> bool:
    return isinstance(subagent_type, str) and (
        subagent_type in _PER_TASK_PERSONAS or subagent_type.startswith("autopilot:worker-")
    )


def _is_skill_md_basename(path_token: str) -> bool:
    """True iff path_token's basename is literally 'SKILL.md': a scoping path
    token is just "a path", so scoping must exclude ANY SKILL.md reference,
    not only one naming a recognized phase."""
    return path_token.rsplit("/", 1)[-1] == "SKILL.md"


def _find_skill_md_paths(text: str) -> list[tuple[int, int]]:
    """Spans of every SKILL.md phase-skill path in `text`, O(n) total: one
    substring scan for the literal 'SKILL.md' (`str.find`, no backtracking),
    then one bounded regex match per occurrence against a <=120-char slice
    ending at it. A `.finditer` of _SKILL_MD_PATH over the whole field is
    worst-case quadratic on a long slash-free run, so it is never run."""
    spans = []
    idx = text.find("SKILL.md")
    while idx != -1:
        window_start = max(0, idx - 120)
        match = _SKILL_MD_PATH.search(text[window_start:idx + len("SKILL.md")])
        if match:
            spans.append((window_start + match.start(), window_start + match.end()))
        idx = text.find("SKILL.md", idx + 1)
    return spans


def _find_path_tokens(text: str) -> set[str]:
    """Every distinct path-shaped token in `text`, O(n) total: one split into
    whitespace-delimited tokens, then plain string checks per token - a '/' in
    it, a '.' at least two characters past its FIRST '/', and a word character
    after that '.'. The first '/', not the last, is what the regex this
    replaced took as the start of its `\\S+\\.\\w+`, so a dot in an earlier
    segment still makes a path ("docs/v1.2/notes" is the path "docs/v1.2").
    The token is cut after the word run that '.' opens, so trailing punctuation
    stays out of the path ("hooks/guard.py." at the end of a sentence is the
    path "hooks/guard.py", and "skills/work/SKILL.md;" keeps its SKILL.md
    basename), exactly where that regex ended its `\\w+`. The RIGHTMOST
    qualifying '.' wins, as that greedy regex's did: "a/b.tar.gz" is one path,
    not "a/b.tar".

    Nothing per slash, and every probe is an offset test (`rfind` for the '.',
    _WORD_START matched AT a position) rather than a scan over a range: a
    `.search` of `\\S*/\\S+\\.\\w+` per '/' over the token around it rescans
    the token from every start offset, which is quadratic on a slash-bearing
    blob (1.66 s/MB on one '/' in 64, against a 0.3 s/MB budget) and cubic on a
    dense run of slashes (3520 s/MB, a hung hook), and a `.finditer` over the
    whole field is worse still (see _find_skill_md_paths). The `rfind` walk
    over the dots stays linear in the token because each call scans back only
    to the next '.', and those ranges are disjoint.

    Distinct, so the same path written twice is one path: the token names one
    file wherever it is written.
    """
    tokens = set()
    for token in text.split():
        slash = token.find("/")
        if slash == -1:
            continue
        dot = token.rfind(".")
        while dot > slash + 1 and not _WORD_START.match(token, dot + 1):
            dot = token.rfind(".", 0, dot)
        if dot <= slash + 1:
            continue
        end = dot + 1
        while _WORD_START.match(token, end):
            end += 1
        tokens.add(token[:end])
    return tokens


def _nonspace_end(text: str, idx: int) -> int:
    """`idx` moved back over the whitespace run ending just before it, so a
    lookback window can start at the previous WORD however much whitespace sits
    between. The walk costs that one run, and the runs before two distinct task
    ids are disjoint, so the total stays linear in the field."""
    while idx and text[idx - 1].isspace():
        idx -= 1
    return idx


def _words_before(text: str, floor: int, start: int) -> Iterator[tuple[int, int]]:
    """Word spans ending at or before `start` and never reaching below `floor`,
    NEAREST FIRST and lazily, so a caller that wants the last few words pays
    for those words only. A forward `finditer` from `floor` paid the whole
    distance from `floor` instead - the whole field whenever the clause holds no
    boundary, which is quadratic over a field with many candidates.

    A word is a maximal run of _WORD_CHAR with its leading non-\\w characters
    dropped, which is exactly what `[\\w][\\w'-]*` matches going forward.
    """
    idx = start
    while idx > floor:
        while idx > floor and not _WORD_CHAR.match(text, idx - 1):
            idx -= 1
        end = idx
        while idx > floor and _WORD_CHAR.match(text, idx - 1):
            idx -= 1
        word_start = idx
        while word_start < end and not _WORD_START.match(text, word_start):
            word_start += 1
        if word_start < end:
            yield word_start, end


def _candidates(text: str) -> list[tuple[int, int, bool]]:
    """Pass 1: every candidate span as (start, end, is_skill_md), sorted by
    start. Pure per-match text inspection - no clause or sentence lookup - so
    the list is COMPLETE before any boundary is computed from it."""
    spans = [(start, end, True) for start, end in _find_skill_md_paths(text)]
    for pattern in _PHASE_NAME_FORMS:
        for match in pattern.finditer(text):
            end = match.end()
            wrap = match.group("w")
            if wrap and text[end:end + 1] == _WRAP_PAIR.get(wrap, wrap):
                end += 1
            suffix = _SKILL_SUFFIX.match(text, end)
            if suffix:
                end = suffix.end()
            spans.append((match.start(), end, False))
    return sorted(spans)


def _scratch(text: str, spans: list[tuple[int, int, bool]]) -> str:
    """`text` with the punctuation inside pass 1's spans masked, so no boundary
    scan ever finds a boundary inside a recognized name. Same length, same
    offsets, so every boundary list it feeds (clause, sentence, citation
    sentence) indexes the ORIGINAL text.

    The scratch copy is built from slices (_MASK_TABLE over each span, the text
    between spans left alone) rather than from a character list, so the field is
    never expanded into a list of one-character strings. Same scratch, character
    for character: _MASK_TABLE maps exactly _MASKED_IN_SPAN to "x" and leaves
    every other character alone, and where two spans overlap the shared part is
    masked once - masking is per character, so masking it twice changed
    nothing.

    The slice walk consumes `spans` in start order, unlike the per-index loop
    it replaced, which did not care: an out-of-order span would be clamped to
    the cursor, hit the `end <= start` skip, and be left UNMASKED, putting a
    clause boundary inside a quoted span with no error raised. `sorted` is what
    keeps that unreachable (Timsort is O(n) on the already-sorted list
    `_candidates` returns, against a 0.034 s stage)."""
    pieces = []
    cursor = 0
    for start, end, _ in sorted(spans):
        start = max(start, cursor)
        if end <= start:
            continue  # a span wholly inside the previous one: already masked
        pieces.append(text[cursor:start])
        pieces.append(text[start:end].translate(_MASK_TABLE))
        cursor = end
    pieces.append(text[cursor:])
    return "".join(pieces)


def _quoted_runs(
    scratch: str,
    spans: list[tuple[int, int, bool]],
) -> dict[tuple[int, int], list[tuple[int, int]]]:
    """Every candidate span mapped to the symmetric-delimiter runs that
    STRICTLY enclose it (opening before `start`, closing at or after `end`),
    from one left-to-right pairing pass per delimiter over the whole field.

    A delimiter's marks pair in order (first with second, third with fourth,
    ...), so no punctuation inside a quoted run can desynchronise the pairing
    the way a clause-local parity count does (see _cited). A '"' behind a digit
    with nothing open is an inch/unit mark and opens nothing: that is what keeps
    `the 5" gap, run /autopilot:work, it is 6" wide` from pairing into one run
    around the name. Behind a digit with a quote already open it still closes,
    because an order quoted off a log ends on a PRD number all day long
    ("run plan-tasks for PRD 00300").

    Within one delimiter the pairs are disjoint and increasing, so the last
    pair opening before a span is the only one that can enclose it: the merge
    walk over the start-sorted spans costs one probe per span, and _cited then
    reads one map entry per candidate instead of rescanning the field around
    each one."""
    runs: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for pattern in _SYMMETRIC_DELIMS:
        pairs: list[tuple[int, int]] = []
        open_at = -1
        for match in pattern.finditer(scratch):
            if open_at == -1:
                if match.start() and scratch[match.start() - 1].isdigit():
                    continue
                open_at = match.start()
            else:
                pairs.append((open_at, match.start()))
                open_at = -1
        index = 0
        for start, end, _ in spans:
            while index < len(pairs) and pairs[index][0] < start:
                index += 1
            if index and pairs[index - 1][1] >= end:
                runs.setdefault((start, end), []).append(pairs[index - 1])
    return runs


def _boundaries(
    text: str,
    spans: list[tuple[int, int, bool]],
) -> tuple[
    list[int],
    list[int],
    list[int],
    list[int],
    dict[tuple[int, int], list[tuple[int, int]]],
]:
    """Pass 2's one-shot boundary build: clause starts, clause ends, sentence
    starts, CITATION sentence starts and the symmetric-delimiter runs for the
    whole field, from one masked scratch copy. Every later clause/sentence
    lookup is a binary search into these sorted lists, never a fresh scan.
    `cite_sentences` and the runs come from the same scratch as `sentences`, so
    all of them index the same coordinate space."""
    scratch = _scratch(text, spans)
    clauses = [(m.start(), m.end()) for m in _CLAUSE_BOUNDARY.finditer(scratch)]
    sentences = [m.start() for m in _SENTENCE_BOUNDARY.finditer(scratch)]
    cite_sentences = [m.start() for m in _CITE_SENTENCE_BOUNDARY.finditer(scratch)]
    return (
        [c[0] for c in clauses],
        [c[1] for c in clauses],
        sentences,
        cite_sentences,
        _quoted_runs(scratch, spans),
    )


def _is_scoped(text: str, sentences: list[int]) -> bool:
    """Per-task scoping, this field only: exactly one task id, with no range
    wording beside ANY id in the field, OR exactly one path that is neither
    under `prds/` nor a SKILL.md. Either one on its own narrows the dispatch to
    a single job.

    Naming the same thing twice still names one thing: "for task 3, yes task 3"
    and "see a/b.py and a/b.py" each name a single job. A path folds by its
    token, which names one file wherever it is written. An id folds only inside
    ONE SENTENCE, as the (sentence, id) pair it makes, because a bare number is
    a reference its sentence carries: forty sentences naming task 1 before a
    bare "Run the work phase now." describe a whole run, not one job, and
    folding them field-wide would excuse that order. So a repeat of the same id
    in a DIFFERENT sentence does not scope, and such a dispatch stays denied on
    purpose. A path has no sentence to fold by in any case - its own "." is a
    sentence boundary, so the two halves of "a/b.py and a/b.py" sit in
    different ones.

    Range wording beside one id disqualifies TASK-based scope outright, not
    just that id: "from task 3 onwards and task 5" names a run of tasks, so the
    surviving unranged id is not the single job the dispatch is about.
    """
    ids = set()
    ranged = False
    for match in _TASK_ID.finditer(text):
        head = _nonspace_end(text, match.start())
        if _TASK_RANGE_LEAD.search(text[max(0, head - 24):head]) or (
            _TASK_RANGE_TAIL.match(text, match.end())
        ):
            ranged = True
        else:
            ids.add((bisect_left(sentences, match.start()), match.group(1).lower()))
    paths = {
        token
        for token in _find_path_tokens(text)
        if not _PRD_STORE_PATH.search(token) and not _is_skill_md_basename(token)
    }
    return (not ranged and len(ids) == 1) or len(paths) == 1


def _strongly_anchored(
    text: str, start: int, end: int, sentences: list[int], marked: set[int]
) -> bool:
    tail = text[end:end + 200]  # bounded: every anchor tail is a few words long
    if _STRONG_ANCHOR_TAIL.match(tail) or _PRD_PATH_TAIL.match(tail):
        return True
    return bisect_left(sentences, start) in marked


def _weakly_anchored(
    text: str, start: int, end: int, clause_start: int, clause_end: int
) -> bool:
    if not _WEAK_ANCHOR_TAIL.match(text, end, clause_end):
        return False
    for word_start, word_end in _words_before(text, clause_start, start):
        token = text[word_start:word_end].lower()
        if token in _DETERMINERS:
            continue  # skip past EVERY leading determiner, not just the adjacent one
        return token not in _PREPOSITIONS
    return False  # a label: no word before the name, or determiners only


def _ordered_to_follow(
    text: str,
    end: int,
    sentences: list[int],
    clause_starts: list[int],
    clause_ends: list[int],
) -> bool:
    """A SKILL.md path counts when an order to follow it sits in the rest of
    the sentence (or the next 200 characters, whichever ends first), with no
    negation in the gap between that verb and its object, and none in the few
    words before the verb either: "you must never follow it" negates the order
    from in front of the verb, where the gap cannot see it. Those few words
    stop at the verb's OWN clause start: a negation in an earlier clause ("do
    not stop, then follow it") negates something else."""
    sentence_index = bisect_left(sentences, end)
    sentence_end = (
        sentences[sentence_index] if sentence_index < len(sentences) else len(text)
    )
    match = _FOLLOW.search(text, end, min(sentence_end, end + 200))
    if not match or _NEGATION.search(match.group(2)):
        return False
    verb_start = match.start()
    index = bisect_left(clause_starts, verb_start)
    verb_clause_start = clause_ends[index - 1] if index else 0
    return not _negated(text, verb_clause_start, verb_start)


def _cited(
    text: str,
    start: int,
    end: int,
    runs: dict[tuple[int, int], list[tuple[int, int]]],
    sentence_start: int,
    sentence_end: int,
) -> bool:
    """True iff the name at [start, end) sits inside a longer wrapped run - a
    quote, backtick or bracket that opens at or before `start` and closes only
    past `end` - so it is cited text, not an order.

    An opener AT `start` is the match's own captured wrap: it cites unless its
    close was consumed into the span (`plan-tasks` wrapped on its own is a
    label and anchors as before). An earlier ASYMMETRIC opener counts while no
    close has come since it, looked for from `sentence_start` because "("
    always opens ("(which handles catchup, design, parse and plan-tasks)").
    The straight single quote is left out: contractions and possessives would
    read as open quotes.

    A symmetric delimiter ('"', '`') has no open form of its own, so an earlier
    one of those counts only when the field-wide pairing (_quoted_runs) put the
    name strictly inside one of its pairs - a map lookup here, built once per
    field. Pairing is field-wide rather than clause-local because a parity
    count from the clause start desynchronises on punctuation INSIDE a quoted
    run: the scratch masks punctuation only inside recognized name spans, so in
    `The log says "ready, done" then run plan-tasks for PRD 00300 and print
    "ok".` the comma inside the quote started the clause, the quote after
    `done` counted as an opener, and the order was excused (measured). The
    pairing opens no run on an inch/unit mark, which is what still leaves "the
    5\" gap, run /autopilot:work, it is 6\" wide" with no run around the name.

    The close may land anywhere before `sentence_end`: a quoted run routinely
    spans a ',' or ':' ("`design-solution: <prd-stem>`"). A pair closing past
    the citation sentence is no run around this name, so '"Run the work phase
    for PRD 7."' stays a whole quoted order and is denied."""
    for opener, closer in _WRAP_SCAN_PAIRS:
        if text.find(closer, end, sentence_end) == -1:
            continue
        if text[start] == opener and text.find(closer, start + 1, end) == -1:
            return True
        if opener != closer:
            open_at = text.rfind(opener, sentence_start, start)
            if open_at != -1 and text.find(closer, open_at, start) == -1:
                return True
    return any(
        sentence_start <= open_at and close_at < sentence_end
        for open_at, close_at in runs.get((start, end), ())
    )


def _negated(text: str, clause_start: int, start: int) -> bool:
    """True iff a negation sits at most _NEGATION_WORD_GAP words before the
    name, inside its own clause. Takes at most _NEGATION_WORD_GAP + 1 word
    tokens (the gap words plus the negation itself) from _words_before, which
    walks BACKWARD from the name, so the cost is O(1) per candidate."""
    words = list(
        islice(_words_before(text, clause_start, start), _NEGATION_WORD_GAP + 1)
    )
    window_start = words[-1][0] if words else clause_start
    return bool(_NEGATION.search(text[window_start:start]))


def _quote(text: str, start: int) -> str:
    return " ".join(text[max(0, start - 10):start + 20].split())


def _field_delegation(text: str, per_task: bool) -> str | None:
    spans = _candidates(text)
    if not spans:
        return None
    clause_starts, clause_ends, sentences, cite_sentences, runs = _boundaries(
        text,
        spans,
    )
    marked = {
        bisect_left(sentences, match.start())
        for match in _WHOLE_RUN_MARKERS.finditer(text)
    }
    scoped = _is_scoped(text, sentences)
    for start, end, is_skill_md in spans:
        index = bisect_left(clause_starts, start)
        clause_start = clause_ends[index - 1] if index else 0
        # Searched from `end`, never from `start`: a wrap character taken into
        # the span can itself be a boundary (the ')' of "(work phase)" is not
        # masked), and a clause_end before `end` would make the weak-anchor
        # tail an empty string, so every wrapped mention would end its clause.
        tail_index = bisect_left(clause_starts, end)
        clause_end = (
            clause_starts[tail_index] if tail_index < len(clause_starts) else len(text)
        )
        if text[clause_end:clause_end + 1] == "?":
            continue  # a question about the phase, not an order to run it
        if is_skill_md:
            if not _ordered_to_follow(text, end, sentences, clause_starts, clause_ends):
                continue
        else:
            anchored = _strongly_anchored(text, start, end, sentences, marked) or (
                not per_task
                and _weakly_anchored(text, start, end, clause_start, clause_end)
            )
            if not anchored or scoped:
                continue
            # Checked after the anchor so an unanchored candidate costs no
            # scan: many mentions in one clause would otherwise go quadratic.
            head = bisect_left(cite_sentences, start)
            sentence_start = cite_sentences[head - 1] + 1 if head else 0
            tail = bisect_left(cite_sentences, end)
            sentence_end = (
                cite_sentences[tail] if tail < len(cite_sentences) else len(text)
            )
            if _cited(text, start, end, runs, sentence_start, sentence_end):
                continue
        if _negated(text, clause_start, start):
            continue
        return _quote(text, start)
    return None


def find_phase_delegation(tool_input: dict) -> str | None:
    """The quoted span of the first counting phase mention in `prompt` or
    `description` (prompt first), or None when this dispatch delegates no
    phase. A phase name counts when it stands as the thing to run; the
    reviewer and agoge exemptions, normalization and scoping all live here, so
    the hook and any direct caller apply them identically.
    """
    if not isinstance(tool_input, dict):
        return None
    subagent_type = tool_input.get("subagent_type")
    if isinstance(subagent_type, str) and (
        subagent_type in _READ_ONLY_REVIEWERS or subagent_type in _AGOGE_PERSONAS
    ):
        return None
    fields = []
    for key in ("prompt", "description"):
        value = tool_input.get(key)
        fields.append(_normalize(value) if isinstance(value, str) else "")
    prefix = _BARE_SLASH_PREFIX.search(fields[0])
    if prefix:
        return _quote(fields[0], prefix.start())
    per_task = _is_per_task_persona(subagent_type)
    for text in fields:
        span = _field_delegation(text, per_task)
        if span is not None:
            return span
    return None


def is_phase_delegation(tool_input: dict) -> bool:
    """True iff this Agent dispatch instructs the subagent to run a phase
    skill (/autopilot:work, /autopilot:plan-tasks, /autopilot:design-solution,
    or a phase SKILL.md) rather than a single per-task job.

    Looks at tool_input["prompt"] and tool_input["description"] (both
    optional, default ""). A payload where tool_input is not a dict, or has
    neither key present as a non-empty string, returns False (fail open).
    """
    return find_phase_delegation(tool_input) is not None


def _deny_message(subagent_type: str | None, span: str) -> str:
    if _is_per_task_persona(subagent_type):
        return (
            "autopilot: this per-task prompt names a phase as the thing to run: "
            f'"{span}". If it only mentions the phase, rephrase that sentence or '
            "scope it to one task (task N). hooks/guard_phase_delegation.py "
            "denied this Agent call."
        )
    return (
        "autopilot: run the phase skill (plan-tasks / design-solution / work) "
        "with the Skill tool in THIS session; dispatch Agent calls only for "
        "per-task subagents (Ivan, Tess, Devon, reviewers). "
        f'Matched: "{span}". hooks/guard_phase_delegation.py denied this '
        "Agent call."
    )


def main() -> None:
    if not os.environ.get("_AUTOPILOT_LOOP"):
        allow()
    payload = read_input()
    if not payload:
        print("guard_phase_delegation: empty/unparseable payload, allowing", file=sys.stderr)
        allow()
    if payload.get("tool_name") != "Agent":
        allow()
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        print("guard_phase_delegation: unparseable tool_input, allowing", file=sys.stderr)
        allow()
    try:
        span = find_phase_delegation(tool_input)
    except Exception:
        print("guard_phase_delegation: predicate raised, allowing", file=sys.stderr)
        allow()  # fail open, defensive - predicate is pure regex, should not raise
    if span is None:
        allow()
    block(_deny_message(tool_input.get("subagent_type"), span))


if __name__ == "__main__":
    main()
