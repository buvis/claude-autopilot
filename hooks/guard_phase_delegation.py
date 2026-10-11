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
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import allow, block, read_input

# Unicode categories dropped outright by _normalize. Mn (combining marks) so a
# decomposed accent cannot split a word ("work" with U+0301 after the "o"); Cf
# (format characters) because they are invisible and do the same (U+200B,
# U+200C, U+200D, U+2060, U+FEFF, U+2061, U+180E, and U+00AD the soft hyphen).
# Nothing else: a Cyrillic "o" (U+043E) is a different letter, not a lookalike
# form, and folding letters would be guesswork.
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

# --- Phase-name recognition (a phase mention in object position) ------------
# Wrapper characters around a skill-form or bare-form name: an optional
# leading '/', then an optional single wrapper from this set that must close
# with the matching character immediately after the name. '[' is written
# FIRST in each character class to avoid an unescaped-']' bug.
_WRAP_OPEN = "[`'\"‘“«「(\\[]"
_WRAP_CLOSE = "[]`'\"’”»」)]"
_WRAP = r"(?P<w>" + _WRAP_OPEN + r")?"
# Open-char -> required close-char map (symmetric for backtick/straight
# quotes, asymmetric for curly quotes/guillemets/corner brackets/parens/
# square brackets). A regex backreference cannot express an asymmetric pair,
# so the close is validated in code, not in the pattern: wrapping is optional
# per the PRD, so only a present-and-correct close is consumed, never
# required.
_WRAP_PAIR = {
    "‘": "’", "“": "”", "«": "»",
    "「": "」", "(": ")", "[": "]",
}

# A "word" for the nearest-preceding-word and clause-end lookups, once wrap
# characters are stripped: \w plus internal apostrophe/hyphen.
_WORD = re.compile(r"[\w][\w'-]*")

# Conceptual form: work|plan|planning|design + phase, with [-_ ] joiner.
# "plan phase" and "planning phase" both count, "plan-tasks phase" does not.
_PHASE_CONCEPT = re.compile(
    rf"{_WRAP}/?\b(work|plan|planning|design)[-_ ]phase\b",
    re.IGNORECASE,
)
# Skill form: the autopilot: prefix is MANDATORY - a bare "work" is ordinary
# English and must never match. Optional /subpath. The optional " skill"
# suffix is NOT baked in: a quoted name like `` `autopilot:design-solution`
# skill `` has its closing backtick BETWEEN the name and " skill", so the
# close-wrap consumption and the skill-suffix probe are ordered algorithm
# steps (see _candidates), not alternatives folded into one pattern.
_PHASE_SKILL = re.compile(
    rf"{_WRAP}/?\bautopilot:(work|plan-tasks|design-solution)(?:/[\w.-]+)?\b",
    re.IGNORECASE,
)
# Bare skill-name form: plan-tasks|design-solution only (never bare "work"),
# hard word boundaries on both sides so it never matches inside a path
# segment like skills/work/SKILL.md or design-solution/references/x.md.
_PHASE_BARE = re.compile(
    rf"{_WRAP}(?<![-/\w])(plan-tasks|design-solution)(?![-/.\w])",
    re.IGNORECASE,
)
# A leading '/' before any of the three forms is consumed as part of the match
# span (not part of _WRAP) when present, so "/autopilot:work" and
# "autopilot:work" match identically past the slash.
_PHASE_NAME_FORMS = (_PHASE_CONCEPT, _PHASE_SKILL, _PHASE_BARE)
# Optional " skill" suffix, probed as its own step on the text right after the
# (already wrap-close-extended) match end.
_SKILL_SUFFIX = re.compile(r"^\s+skill\b", re.IGNORECASE)

# Strong anchor: matched against the text starting right after the phase-name
# match's end (post wrap-close extension and post optional-" skill"). PRD
# number is 3-5 digits; the `[\w-]+\s+PRD\b` branch covers a slug-named PRD.
_STRONG_ANCHOR_TAIL = re.compile(
    r"^\s*(?:(?:for|on)\s+(?:the\s+)?(?:PRD\b|task\b|[\w-]+\s+PRD\b|\d{3,5}\b)"
    r"|from\s+task\b)",
    re.IGNORECASE,
)
# A PRD-lifecycle path immediately after the name anchors on its own, with or
# without the preposition: "the work phase, prds/wip/00300.md" is never
# ordinary prose.
_PRD_PATH_TAIL = re.compile(r"^\s*(?:for|on)?\s*\S*/prds/\S+\.\w+", re.IGNORECASE)
# Whole-run marker: searched anywhere within the enclosing SENTENCE ("keep
# going through every task" spans a comma, so a clause is too narrow).
_WHOLE_RUN_MARKERS = re.compile(
    r"\bevery\s+task\b|\ball\s+(?:the\s+)?tasks?\b|\bkeep\s+going\b"
    r"|\buntil\s+(?:done|complete|finished)\b|\bend\s+to\s+end\b|\bonwards?\b",
    re.IGNORECASE,
)
# Weak anchor: the phase name ends its CLAUSE. Matched against the text from
# the name's end to the clause boundary: optional close-wrap character, then
# optionally one of now|again|first|immediately|please|in full, then only
# whitespace to the boundary. " skill" is already consumed by the phase-name
# step. A clause ending in "?" never counts - checked by the caller.
_WEAK_ANCHOR_TAIL = re.compile(
    rf"^{_WRAP_CLOSE}?\s*(?:now|again|first|immediately|please|in\s+full)?\s*$",
    re.IGNORECASE,
)

_DETERMINERS = frozenset({"the","a","an","this","that","these","those","my","your","our","its","their","next","all","of","each","every","entire","whole","full","remaining"})
_PREPOSITIONS = frozenset({"in","about","of","during","before","after","from","with","by","at","into","within","without","under","over","to","for","on","through","between","across","per","via","than","like"})

# Per-task personas count the strong anchor only: their prompts quote phase
# prose as an edit target all day long.
_PER_TASK_PERSONAS = frozenset({"autopilot:ivan", "autopilot:tess", "autopilot:devon"})

# Always-delegate form 1: the first token of the prompt is a bare slash
# command. Checked on `prompt` only - the PRD's own wording names that field,
# and no captured `description` ever starts with a slash command.
_BARE_SLASH_PREFIX = re.compile(r"^\s*/autopilot:(work|plan-tasks|design-solution)\b")

# Always-delegate form 2: a SKILL.md path. Scoping is skipped for this form,
# negation is not.
_SKILL_MD_PATH = re.compile(
    r"(?:[^\s/]*/)*(?:skills/)?(work|plan-tasks|design-solution)/SKILL\.md$"
)
# One follow regex, not two: verb, then at most 3 words of gap (non-greedy,
# captured so the gap can be negation-checked), then one object phrase.
_FOLLOW = re.compile(
    r"\b(follow|execute|do|run|carry\s+out)\s+((?:\S+\s+){0,3}?)"
    r"(it\b|its\s+steps\b|its\s+instructions\b|the\s+steps\b|every\s+task\b|all\s+tasks\b)",
    re.IGNORECASE,
)

_TASK_ID = re.compile(r"\btasks?\s+#?([A-Z]?\d+)\b", re.IGNORECASE)
_TASK_RANGE_LEAD = re.compile(r"\b(from|after|starting\s+at|starting\s+with)\s*$", re.IGNORECASE)
_TASK_RANGE_TAIL = re.compile(r"^\s*(onwards?|through|to|until|and\s+on|and\s+later|,\s*\d|and\s+\d|-\d|\.\.)", re.IGNORECASE)
_PATH_TOKEN = re.compile(r"\S*/\S+\.\w+")

# "not/never/don't ... hesitate|fail|only" is a double negation ("do not
# hesitate to run ..."), so it does not count. The other contractions keep no
# exception: "isn't only" is a state, not an instruction wrapped in a double
# negation. The bound is a WORD count, not a character count: a single long
# token can push a real 3-word gap past any fixed character budget.
_NEGATION = re.compile(
    r"\b(not|never|does\s+not|doesn't|don't|won't)\b(?!\s+(?:hesitate|fail|only)\b)"
    r"|\b(can't|cannot|isn't|shouldn't|wasn't|weren't)\b",
    re.IGNORECASE,
)
_NEGATION_WORD_GAP = 4  # words between the negation and the name, not characters

# ':' must not fire INSIDE a recognized name's own span ("autopilot:work"),
# and neither must the '.' a SKILL.md span carries by construction, so
# boundary detection runs on a per-field scratch copy where every candidate
# span's internal ':', '/' and '.' are replaced by 'x'. Same length, same
# offsets: the quoted span always slices the ORIGINAL text.
_MASKED_IN_SPAN = ":/."
_CLAUSE_BOUNDARY = re.compile(r"[.;,:!?\n)]|\s-\s")
_SENTENCE_BOUNDARY = re.compile(r"[.!?\n]")

_AGOGE_PREFIX = "agoge:"

# Read-only reviewer personas: none of their persona files grant the Skill
# tool (test_every_exempt_reviewer_lacks_the_skill_tool), so exempting them
# from the delegation check cannot be exploited to delegate a phase skill.
_READ_ONLY_REVIEWERS = frozenset(
    {
        "autopilot:alice", "autopilot:blake", "autopilot:bob", "autopilot:carl",
        "autopilot:cora", "autopilot:eve", "autopilot:grace", "autopilot:mallory",
        "autopilot:pat", "autopilot:rita", "autopilot:toby", "autopilot:trent",
        "autopilot:victor",
    }
)


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
    """
    kept = []
    for char in unicodedata.normalize("NFKD", text):
        category = unicodedata.category(char)
        if category in _DROPPED_CATEGORIES:
            continue
        kept.append("-" if category == "Pd" else char)
    return unicodedata.normalize("NFKC", "".join(kept)).translate(_FOLDED)


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
                end += 1  # consume a present-and-correct close-wrap character
            suffix = _SKILL_SUFFIX.match(text[end:end + 16])
            if suffix:
                end += suffix.end()
            spans.append((match.start(), end, False))
    return sorted(spans)


def _boundaries(
    text: str, spans: list[tuple[int, int, bool]]
) -> tuple[list[int], list[int], list[int]]:
    """Pass 2's one-shot boundary build: clause starts, clause ends and
    sentence starts for the whole field, from a scratch copy that masks the
    punctuation inside pass 1's spans. Every later clause/sentence lookup is a
    binary search into these sorted lists, never a fresh scan."""
    scratch = list(text)
    for start, end, _ in spans:
        for index in range(start, end):
            if scratch[index] in _MASKED_IN_SPAN:
                scratch[index] = "x"
    scratch = "".join(scratch)
    clauses = [(m.start(), m.end()) for m in _CLAUSE_BOUNDARY.finditer(scratch)]
    sentences = [m.start() for m in _SENTENCE_BOUNDARY.finditer(scratch)]
    return [c[0] for c in clauses], [c[1] for c in clauses], sentences


def _is_scoped(text: str) -> bool:
    """Per-task scoping, this field only: exactly one task id with no range
    wording beside it, OR exactly one path that is neither under `prds/` nor a
    SKILL.md. Either one on its own narrows the dispatch to a single job."""
    ids = [
        match
        for match in _TASK_ID.finditer(text)
        if not _TASK_RANGE_LEAD.search(text[max(0, match.start() - 24):match.start()])
        and not _TASK_RANGE_TAIL.match(text[match.end():match.end() + 24])
    ]
    paths = [
        token
        for token in (m.group(0) for m in _PATH_TOKEN.finditer(text))
        if "/prds/" not in token and not _is_skill_md_basename(token)
    ]
    return len(ids) == 1 or len(paths) == 1


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
    if not _WEAK_ANCHOR_TAIL.match(text[end:clause_end]):
        return False
    for word in reversed(list(_WORD.finditer(text, clause_start, start))):
        token = word.group(0).lower()
        if token in _DETERMINERS:
            continue  # skip past EVERY leading determiner, not just the adjacent one
        return token not in _PREPOSITIONS
    return False  # a label: no word before the name, or determiners only


def _ordered_to_follow(text: str, end: int, sentences: list[int]) -> bool:
    """A SKILL.md path counts when an order to follow it sits in the rest of
    the sentence (or the next 200 characters, whichever ends first), with no
    negation in the gap between that verb and its object."""
    sentence_end = next((s for s in sentences if s >= end), len(text))
    match = _FOLLOW.search(text[end:min(sentence_end, end + 200)])
    return bool(match) and not _NEGATION.search(match.group(2))


def _negated(text: str, clause_start: int, start: int) -> bool:
    """True iff a negation sits at most _NEGATION_WORD_GAP words before the
    name, inside its own clause. Walks BACKWARD from the name over at most
    _NEGATION_WORD_GAP + 1 word tokens (the gap words plus the negation
    itself), so the cost is O(1) per candidate."""
    words = list(_WORD.finditer(text, clause_start, start))[-(_NEGATION_WORD_GAP + 1):]
    window_start = words[0].start() if words else clause_start
    return bool(_NEGATION.search(text[window_start:start]))


def _quote(text: str, start: int) -> str:
    return " ".join(text[max(0, start - 10):start + 20].split())


def _field_delegation(text: str, per_task: bool) -> str | None:
    spans = _candidates(text)
    if not spans:
        return None
    clause_starts, clause_ends, sentences = _boundaries(text, spans)
    marked = {
        bisect_left(sentences, match.start())
        for match in _WHOLE_RUN_MARKERS.finditer(text)
    }
    scoped = _is_scoped(text)
    for start, end, is_skill_md in spans:
        index = bisect_left(clause_starts, start)
        clause_start = clause_ends[index - 1] if index else 0
        clause_end = clause_starts[index] if index < len(clause_starts) else len(text)
        if text[clause_end:clause_end + 1] == "?":
            continue  # a question about the phase, not an order to run it
        if is_skill_md:
            if not _ordered_to_follow(text, end, sentences):
                continue
        else:
            anchored = _strongly_anchored(text, start, end, sentences, marked) or (
                not per_task
                and _weakly_anchored(text, start, end, clause_start, clause_end)
            )
            if not anchored or scoped:
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
        subagent_type in _READ_ONLY_REVIEWERS or subagent_type.startswith(_AGOGE_PREFIX)
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
    """The per-task personas get the rephrase-or-scope wording with the span
    inline; everyone else gets the run-it-here wording plus `Matched:`."""
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
