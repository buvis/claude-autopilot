"""Lexical layer for hooks/guard_phase_delegation.py: the regex and frozenset
constants the guard matches with, and nothing executable.

Split out of guard_phase_delegation.py to keep that file under the repo's
800-line limit. Every name here is imported back into
guard_phase_delegation's namespace by hand, so it still resolves as
`guard_phase_delegation.<name>` for the hook's own code and for the test
modules that introspect it. Add a constant here, and add it to that import.
"""

from __future__ import annotations

import re

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
# Hoisted out of _cited: the pair list is fixed, and rebuilding it per
# candidate is pure overhead on a hot path. The straight single quote is
# deliberately absent even though it appears in _WRAP_OPEN - contractions and
# possessives ("don't run plan-tasks") would read as an open quote and excuse
# a real order. _WRAP_OPEN governs what the span matcher may absorb as the
# name's own wrapper; this tuple governs what may open a citation run around
# it, and the two are not the same question.
_WRAP_SCAN_PAIRS = (*_WRAP_PAIR.items(), ("`", "`"), ('"', '"'))
# Every character _WRAP_SCAN_PAIRS pairs on, as one class: _delim_positions
# buckets a single pass over the field by character, so _cited answers each
# "is there a mark in this range" with a bisect instead of a str.find that
# scans to the sentence end once per candidate.
_WRAP_SCAN_CHARS = re.compile(
    "["
    + re.escape("".join(sorted({c for pair in _WRAP_SCAN_PAIRS for c in pair})))
    + "]"
)
# The tokens _quoted_runs walks, in one position-ordered pass: a maximal run
# of backticks is ONE token (its length is what it pairs by), every other
# _WRAP_SCAN_PAIRS character is a token of its own.
_NEST_TOKEN = re.compile(
    "`+|["
    + re.escape("".join(sorted({c for pair in _WRAP_SCAN_PAIRS for c in pair} - {"`"})))
    + "]",
)
# An emoticon's paren (":(", ";)", "=)") is a face, not a bracket: matched at
# the character before the paren, it is dropped from every paren position list.
_EMOTICON = re.compile(r"[:;=][)(]")

# A "word" for the nearest-preceding-word and negation-gap lookups, once wrap
# characters are stripped: \w plus internal apostrophe/hyphen. The class is
# split in two because _words_before walks it BACKWARD one character at a
# time, matching at an offset of the field instead of scanning a range of it:
# _WORD_CHAR is what a word is made of, _WORD_START what it may begin with.
_WORD_CHAR = re.compile(r"[\w'-]")
_WORD_START = re.compile(r"\w")

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
    rf"{_WRAP}(?<![-/:\w])(plan-tasks|design-solution)(?![-/.\w])",
    re.IGNORECASE,
)
# A leading '/' before any of the three forms is consumed as part of the match
# span (not part of _WRAP) when present, so "/autopilot:work" and
# "autopilot:work" match identically past the slash.
_PHASE_NAME_FORMS = (_PHASE_CONCEPT, _PHASE_SKILL, _PHASE_BARE)
# Optional " skill" suffix, probed as its own step on the text right after the
# (already wrap-close-extended) match end. Matched at an offset, never on a
# fixed-width slice: the whitespace before "skill" is unbounded, so a probe
# over the next 16 characters reads a run of spaces and nothing else.
_SKILL_SUFFIX = re.compile(r"\s+skill\b", re.IGNORECASE)

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
# Weak anchor: the phase name ends its CLAUSE. Matched from the name's end
# with the clause boundary as the regex's endpos (never on a slice of the
# field: slicing costs the clause length per candidate, and a clause with no
# boundary in it is the whole field): optional close-wrap character, then
# optionally one of now|again|first|immediately|please|in full, then only
# whitespace to the boundary. "$" honours endpos, so it still means "the clause
# ends here". " skill" is already consumed by the phase-name step. A clause
# ending in "?" never counts - checked by the caller.
# The trailing `\s*` sits INSIDE the optional keyword group, so no two `\s*`
# groups are adjacent: the same language (close-wrap, spaces, optional keyword,
# spaces) but written so one run of whitespace can only be split one way. With
# the two groups side by side, a clause holding no boundary between the name and
# a long whitespace run made the pair hand the run back one space at a time,
# which is quadratic (25 s/MB at 12500 spaces, 100 s/MB at 50000, against a
# 0.3 s/MB budget).
_WEAK_ANCHOR_TAIL = re.compile(
    rf"{_WRAP_CLOSE}?\s*(?:(?:now|again|first|immediately|please|in\s+full)\s*)?$",
    re.IGNORECASE,
)

_DETERMINERS = frozenset({"the","a","an","this","that","these","those","my","your","our","its","their","next","all","of","each","every","entire","whole","full","remaining"})
_PREPOSITIONS = frozenset({"in","about","of","during","before","after","from","with","by","at","into","within","without","under","over","to","for","on","through","between","across","per","via","than","like"})

# Per-task personas count the strong anchor only: their prompts quote phase
# prose as an edit target all day long.
_PER_TASK_PERSONAS = frozenset({"autopilot:ivan", "autopilot:tess", "autopilot:devon"})

# Always-delegate form 1: the first token of the prompt IS a bare slash
# command. Checked on `prompt` only - the PRD's own wording names that field,
# and no captured `description` ever starts with a slash command. The trailing
# lookahead is what makes it the whole token: `\b` alone also fires inside
# "/autopilot:work-adjacent", where the first token merely BEGINS with a phase
# command and names something else.
_BARE_SLASH_PREFIX = re.compile(
    r"^\s*/autopilot:(work|plan-tasks|design-solution)(?![-\w])",
)

# Always-delegate form 2: a SKILL.md path. Scoping is skipped for this form,
# negation is not.
_SKILL_MD_PATH = re.compile(
    r"(?:[^\s/]*/)*(?:skills/)?(work|plan-tasks|design-solution)/SKILL\.md$",
)
# One follow regex, not two: verb, then at most 3 words of gap (non-greedy,
# captured so the gap can be negation-checked), then one object phrase.
_FOLLOW = re.compile(
    r"\b(follow|execute|do|run|carry\s+out)\s+((?:\S+\s+){0,3}?)"
    r"(it\b|its\s+steps\b|its\s+instructions\b|the\s+steps\b|every\s+task\b|all\s+tasks\b)",
    re.IGNORECASE,
)

_TASK_ID = re.compile(r"\btasks?\s+#?([A-Z]?\d+)\b", re.IGNORECASE)
# The lead is looked for in the 24 characters before the id's whitespace run,
# not before the id itself, and the tail is matched at the id's end instead of
# on a 24-character slice: the whitespace between the range word and the id is
# unbounded, so "from" + 40 spaces + "task 3" reads like "from task 3".
_TASK_RANGE_LEAD = re.compile(r"\b(from|after|starting\s+at|starting\s+with)\s*$", re.IGNORECASE)
_TASK_RANGE_TAIL = re.compile(r"\s*(onwards?|through|to|until|and\s+on|and\s+later|,\s*\d|and\s+\d|-\d|\.\.)", re.IGNORECASE)
# The PRD-lifecycle store, as a path SEGMENT: "prds/wip/00300.md" names the
# store exactly as "docs/dev/project-management/prds/wip/00300.md" does, so a
# leading-slash test ("/prds/" in token) misses the root-relative form.
_PRD_STORE_PATH = re.compile(r"(?:^|/)prds/")

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
# A conjunction starts a new clause as a comma does: a negation before it
# binds its own verb ("don't stop and run ..."), never the name after it.
_NEGATION_REACH_END = re.compile(r"\b(and|then|but)\b", re.IGNORECASE)

# ':' must not fire INSIDE a recognized name's own span ("autopilot:work"),
# and neither must the '.' a SKILL.md span carries by construction, so
# boundary detection runs on a per-field scratch copy where every candidate
# span's internal ':', '/' and '.' are replaced by 'x'. Same length, same
# offsets: the quoted span always slices the ORIGINAL text.
_MASKED_IN_SPAN = ":/."
_MASK_TABLE = str.maketrans(_MASKED_IN_SPAN, "x" * len(_MASKED_IN_SPAN))
_CLAUSE_BOUNDARY = re.compile(r"[.;,:!?\n)]|\s-\s")
_SENTENCE_BOUNDARY = re.compile(r"[.!?\n]")
# A sentence terminator for CITATION purposes only: `.`, `!` or `?` that is
# actually followed by whitespace or end-of-text, plus a bare newline. A `.`
# inside a dotted identifier ("cli/frontmatter.parse") or immediately before a
# closing wrapper ("`... PRD 00300.`") is NOT a sentence end, and treating it
# as one is what made the guard refuse two legitimate corpus dispatches.
# Deliberately separate from _SENTENCE_BOUNDARY: that list feeds _is_scoped's
# (sentence, id) folding, _strongly_anchored and the whole-run marker set,
# whose behaviour is pinned by the existing suite and must not move.
#
# The closing-wrapper class before \Z is load-bearing, not decoration. A
# terminator followed ONLY by closing wrappers to end-of-text IS a real
# sentence end: '"Run the work phase for PRD 7."' is a whole quoted order and
# must stay denied. Without that class the window runs to len(text), the final
# quote is found as a close, and the guard allows it -- measured, 4 pinned
# tests in hooks/test_guard_phase_delegation_structure.py go red.
_CITE_SENTENCE_BOUNDARY = re.compile(
    # The trailing class excludes the backtick itself: with a bare [^(\s] the
    # `+ run gives one backtick back on a multi-backtick closer ("PRD 00300.``(
    # verbatim)"), the class matches that backtick, and the terminator wrongly
    # ends the citation sentence.
    # The CJK full stop, exclamation and question marks end a sentence
    # unconditionally, with no lookahead: unlike `.`, `!`, `?` they carry no
    # dotted-identifier ambiguity, and CJK prose is normally written with no
    # space after them (PRD 00324 finding: a spaced payload closed the
    # window, the same unspaced one did not).
    r"""[。！？]|[.!?](?=\s|[]'"’”»」)]|`*\s*(?:\Z|\n)|`+[ \t]*[^(\s`])|\n""",
)

_AGOGE_PREFIX = "agoge:"
# The agoge personas, enumerated: the exemption fails closed, so a new persona
# must be added here by hand, and "agoge:anything" is not exempt.
_AGOGE_PERSONAS = frozenset({
    "agoge:olivia", "agoge:walter", "agoge:heidi", "agoge:judy",
    "agoge:wendy", "agoge:peggy", "agoge:trudy",
})

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
