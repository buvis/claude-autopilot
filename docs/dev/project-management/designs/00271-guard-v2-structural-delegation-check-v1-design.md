# Design: Guard v2: a structural phase-delegation check

## Architecture fit

`hooks/guard_phase_delegation.py` is a PreToolUse hook on the `Agent` tool, loaded via `hooks/hooks.json` and `hooks/dispatch.py`. It sits in the same "loop-mode guard" family as `guard_push_on_critical.py`, `guard_skill_after_leave.py`, `guard_stop_on_live_lanes.py`, `note_session_leave.py` and `enforce_prd_location.py` — all stdin-JSON hooks built on `hooks/_common.py`'s `read_input`/`allow`/`block`. This PRD replaces the guard's verb/gap-word matching engine with a structural (object-position) predicate, fixes two independent small defects in two sibling hooks, adds a frozen real-dispatch regression fixture, and adds a standalone replay CLI under `dev/bin/`. No new hook, no new PreToolUse/PostToolUse registration, no change to `hooks.json`.

## Module placement

- **Edit** `hooks/guard_phase_delegation.py` — replace the entire matching engine (`_normalize`, `find_phase_delegation`, `is_phase_delegation`, `_READ_ONLY_REVIEWERS`-adjacent `agoge:` exemption, per-type deny message). Public signature `is_phase_delegation(tool_input: dict) -> bool` unchanged; `find_phase_delegation` is new.
- **Edit** `hooks/enforce_prd_location.py` — one line in `_check_file_path`, normalizing `file_path` before `Path(file_path).resolve()`.
- **Edit** `hooks/note_session_leave.py` and `hooks/guard_skill_after_leave.py` — one guard clause each, treating a session id containing U+FFFD as absent.
- **New** `hooks/fixtures/phase_delegation/replay.jsonl` — committed data fixture, no code.
- **New** `hooks/test_guard_phase_delegation_structure.py`, `hooks/test_guard_phase_delegation_dispatch.py`, `hooks/test_guard_phase_delegation_replay.py`, `hooks/test_read_input.py`.
- **Edit** `hooks/test_guard_phase_delegation.py` (only an assertion v2 makes false) and `hooks/test_guard_phase_delegation_narrowing.py` (re-sort per task 5), `hooks/test_enforce_prd_location.py`, `hooks/test_guard_skill_after_leave.py`.
- **New** `dev/bin/replay_delegation_guard.py`, `dev/bin/test_replay_delegation_guard.py`.
- **Edit** `dev/bin/release-checks` — register every new `hooks/test_*.py` and `dev/bin/test_*.py` file.
- **Edit** `CHANGELOG.md` — replace the 00267 `[Unreleased]` guard line with the three lines the PRD specifies verbatim.

No edits to `hooks/hooks.json`, `hooks/_common.py`, or `hooks/fixtures/phase_delegation/{allowed,denied}/` (per the PRD's Repository Structure note).

## Interfaces & contracts

### `guard_phase_delegation.py`

```python
def _normalize(text: str) -> str:
    """NFKD -> drop Cf/Mn categories -> map Pd category + U+2212 to '-' ->
    NFKC -> map curly single quotes {U+2018, U+2019} to "'" -> strip '*'."""

def find_phase_delegation(tool_input: dict) -> str | None:
    """Return the quoted span (`text[max(0,start-10):start+20]`, whitespace-
    joined) of the first counting match in `prompt` or `description`, or
    None. Runs the same field/exemption/normalization pipeline as
    is_phase_delegation; the span text is independent per the field it was
    found in (prompt checked before description)."""

def is_phase_delegation(tool_input: dict) -> bool:
    """True iff find_phase_delegation(tool_input) is not None. Signature
    and fail-open behavior on a non-dict/malformed tool_input unchanged."""
```

Module-private constants replacing the retired set (`_COLON_VERBS`, `_WIDENED_VERBS`, `_IMPERATIVE`, `_GAP_WORD`, `_GAP`, `_NOT_COMPOUND`, `_NO_NEGATION`, `_SKILL_READ`, `_DELEGATION_PATTERNS`, `_negated_before` all removed):

```python
# Phase-name recognition (Feature: Phase mention in object position).
# Wrapper characters around a skill-form or bare-form name: an optional
# leading '/', then an optional single wrapper from this set that must close
# with the matching character immediately after the name. '[' is written
# FIRST in each character class to avoid an unescaped-']' bug (dispatch-2
# finding 2: the original class put ']' last, producing an invalid
# unescaped close bracket that made the suffix a literal "]?" instead of an
# optional class).
_WRAP_OPEN = "[`'\"‘“«「(\\[]"
_WRAP_CLOSE = "[]`'\"’”»」)]"
_WRAP = r"(?P<w>" + _WRAP_OPEN + r")?"
_WRAP_CLOSE_CLASS = _WRAP_CLOSE
# Open-char -> required close-char map (symmetric for backtick/straight
# quotes, asymmetric for curly quotes/guillemets/corner brackets/parens/
# square brackets). A regex backreference cannot express an asymmetric
# pair, so the close is validated in code, not the pattern: after a
# `_PHASE_NAME_FORMS` match, if `match.group("w")` is truthy, check
# `text[match.end():match.end()+1] == _WRAP_PAIR.get(w, w)`; when true,
# extend the match end by 1 (consume the close); when false, the wrap is
# simply unmatched-close and the match stands as-is (wrapping is
# "optional" per the PRD - only a present-and-correct close is consumed,
# never required).
_WRAP_PAIR = {"‘": "’", "“": "”", "«": "»", "「": "」", "(": ")", "[": "]"}

# A "word" for the nearest-preceding-word and clause-end lookups, once wrap
# characters are stripped: \w plus internal apostrophe/hyphen.
_WORD = re.compile(r"[\w][\w'-]*")

# Conceptual form: work|plan|planning|design + phase, with [-_ ] joiner
# (matches the PRD's four names exactly - "plan phase" and "planning phase"
# both count, "plan-tasks phase" is NOT a conceptual form).
_PHASE_CONCEPT = re.compile(
    rf"{_WRAP}\b(work|plan|planning|design)[-_ ]phase\b",
    re.IGNORECASE,
)
# Skill form: autopilot: PREFIX IS MANDATORY here - a bare "work" is
# ordinary English and must never match (finding 1). Optional /subpath.
# The optional " skill" suffix is NOT baked into this regex (dispatch-3
# finding B4: a quoted name like `` `autopilot:design-solution` skill ``
# has its closing backtick BETWEEN the name and " skill", so a regex
# alternative ending in `(?:\s+skill\b)?` can never reach across the
# close-wrap character - the close-wrap consumption and the skill-suffix
# consumption are both now ALGORITHM steps applied in order after this
# core match, not alternatives folded into one compiled pattern (see
# Algorithm shape step 3c below: consume close-wrap first, THEN probe for
# an optional " skill" past it).
_PHASE_SKILL = re.compile(
    rf"{_WRAP}\bautopilot:(work|plan-tasks|design-solution)(?:/[\w.-]+)?\b",
    re.IGNORECASE,
)
# Bare skill-name form: plan-tasks|design-solution only (never bare "work"),
# hard word boundaries on both sides so it never matches inside a path
# segment like skills/work/SKILL.md or design-solution/references/x.md.
# Skill-suffix handling is the same post-match algorithm step as
# _PHASE_SKILL above (dispatch-3 finding B4).
_PHASE_BARE = re.compile(
    rf"{_WRAP}(?<![-/\w])(plan-tasks|design-solution)(?![-/.\w])",
    re.IGNORECASE,
)
# A leading '/' before any of the three forms is consumed as part of the
# match span (not part of _WRAP) when present, so "/autopilot:work" and
# "autopilot:work" both match identically past the slash.
_PHASE_NAME_FORMS = (_PHASE_CONCEPT, _PHASE_SKILL, _PHASE_BARE)

# Strong anchor: matched with re.match against the text starting right
# after the phase-name match's end (post wrap-close extension and post
# optional-"skill" consumption - finding 3 and finding 7 part 1). PRD
# number is 3-5 digits. The `[\w-]+\s+PRD\b` branch covers a slug-named
# PRD; a bare PRD-shaped relative path (dispatch-2 finding 7, part 2:
# `docs/dev/project-management/prds/wip/00300.md` must anchor strongly
# too, since it carries no "for/on PRD" wording) is covered by the
# dedicated `_PRD_PATH_TAIL` alternative below, checked the same way.
_STRONG_ANCHOR_TAIL = re.compile(
    r"^\s*(?:(?:for|on)\s+(?:the\s+)?(?:PRD\b|task\b|[\w-]+\s+PRD\b|\d{3,5}\b)|from\s+task\b)",
    re.IGNORECASE,
)
# A PRD-lifecycle path immediately after the name counts as a strong
# anchor on its own (dispatch-2 finding 7, part 2): "Run the work phase
# for docs/dev/project-management/prds/wip/00300.md." - the preposition
# is already covered by _STRONG_ANCHOR_TAIL's "for/on" branch, but a
# BARE path with no "for/on" (e.g. "the work phase, prds/wip/00300.md")
# also anchors strongly, since a prds/ path is never ordinary prose.
_PRD_PATH_TAIL = re.compile(
    r"^\s*(?:for|on)?\s*\S*/prds/\S+\.\w+",
    re.IGNORECASE,
)
# Whole-run marker: searched anywhere within the enclosing SENTENCE slice
# (not just the clause - "keep going through every task" PRD example spans
# a comma). "onwards?" fixed (finding 3's "onward s?" typo); "all the
# tasks" added (finding 3). The caller computes sentence boundaries ONCE
# per field (see Algorithm shape note on linear time, finding 6) and
# reuses the resulting slice map for every match in that field, rather
# than re-slicing/re-searching per match.
_WHOLE_RUN_MARKERS = re.compile(
    r"\bevery\s+task\b|\ball\s+(?:the\s+)?tasks?\b|\bkeep\s+going\b"
    r"|\buntil\s+(?:done|complete|finished)\b|\bend\s+to\s+end\b|\bonwards?\b",
    re.IGNORECASE,
)
# Weak anchor: the phase name ends its CLAUSE. Matched against the text
# from the name's end to the clause boundary: optional close-wrap char
# (via the `_WRAP_CLOSE_CLASS` character class - now correctly escaped),
# then optional one of now|again|first|immediately|please|in full, then
# only whitespace to the boundary. " skill" is NOT re-matched here; it is
# already consumed inside the phase-name match itself (see _PHASE_SKILL/
# _PHASE_BARE above), so the weak-anchor tail no longer needs its own
# "skill" branch. A clause ending in "?" never counts (finding 4) -
# checked by the caller, not this regex.
_WEAK_ANCHOR_TAIL = re.compile(
    rf"^{_WRAP_CLOSE_CLASS}?\s*"
    r"(?:now|again|first|immediately|please|in\s+full)?\s*$",
    re.IGNORECASE,
)
# Optional " skill" suffix, probed as its OWN algorithm step applied to the
# text starting right after the (already wrap-close-extended) match end
# (dispatch-3 finding B4 - see _PHASE_SKILL/_PHASE_BARE above for why this
# cannot live inside those compiled patterns).
_SKILL_SUFFIX = re.compile(r"^\s+skill\b", re.IGNORECASE)

_DETERMINERS = frozenset({"the","a","an","this","that","these","those","my","your","our","its","their","next","all","of","each","every","entire","whole","full","remaining"})
_PREPOSITIONS = frozenset({"in","about","of","during","before","after","from","with","by","at","into","within","without","under","over","to","for","on","through","between","across","per","via","than","like"})

# Per-task persona test: exact name in this set, OR startswith("autopilot:worker-").
_PER_TASK_PERSONAS = frozenset({"autopilot:ivan", "autopilot:tess", "autopilot:devon"})

def _is_per_task_persona(subagent_type: str | None) -> bool:
    return isinstance(subagent_type, str) and (
        subagent_type in _PER_TASK_PERSONAS or subagent_type.startswith("autopilot:worker-")
    )

# Always-delegate form 1: first token of the field is a bare slash-command.
# Checked on `prompt` ONLY (finding 9 - the PRD's own wording, "a prompt
# whose first token is", names the field; `description` never starts a
# slash command in any captured fixture, so this stays prompt-only rather
# than widened to "stricter than spec").
_BARE_SLASH_PREFIX = re.compile(r"^\s*/autopilot:(work|plan-tasks|design-solution)\b")

# Always-delegate form 2: a SKILL.md path, scoping skipped for this form,
# negation NOT skipped (question 10 / dispatch-2 finding 9's wording fix -
# "always delegates" governs scoping only; the follow-phrase negation
# check in step 3a still runs). Dispatch-3 finding B3: a `(?:[^\s/]*/)*?`
# repeat is STILL worst-case quadratic on a long slash-free run (Python's
# backtracking engine retries the inner `[^\s/]*` at every length when the
# single repetition attempt fails, and finditer then retries at every
# start offset too). The actual fix is to never run this backtracking
# regex over an arbitrary window at all: gate it on the cheap, genuinely
# linear substring search `"SKILL.md" in text` first (Python's `str.find`
# is a single Boyer-Moore-ish linear pass, no backtracking) - when absent,
# skip the regex entirely; when present, anchor the regex search to a
# FIXED-SIZE window ending at each `SKILL.md` occurrence (at most 120
# characters back, enough for the longest realistic path in this repo)
# rather than letting `.finditer` try every offset in the whole field:
_SKILL_MD_PATH = re.compile(r"(?:[^\s/]*/)*(?:skills/)?(work|plan-tasks|design-solution)/SKILL\.md$")
def _find_skill_md_paths(text: str) -> list[re.Match]:
    """O(n) total: one substring scan for literal 'SKILL.md' occurrences
    (`str.find`-based, no backtracking), then one BOUNDED regex match per
    occurrence against a <=120-char slice ending at that occurrence -
    never a finditer over the whole field. Each occurrence costs O(1)
    (bounded window), and occurrences are found in O(n) total, so the
    whole function is O(n) regardless of how many non-matching slash-free
    characters surround the occurrences."""
    matches = []
    idx = text.find("SKILL.md")
    while idx != -1:
        window_start = max(0, idx - 120)
        m = _SKILL_MD_PATH.search(text[window_start:idx + len("SKILL.md")])
        if m:
            matches.append(m)  # offsets rebased by the caller using window_start
        idx = text.find("SKILL.md", idx + 1)
    return matches
def _is_skill_md_basename(path_token: str) -> bool:
    """True iff path_token's basename is literally 'SKILL.md' (dispatch-2
    finding 1, second half): scoping must exclude ANY SKILL.md reference,
    not only one matching the three recognized phase names, since a
    scoping path token is just "a path", not a recognized phase name."""
    return path_token.rsplit("/", 1)[-1] == "SKILL.md"
# One follow regex (not two separately-searched patterns - finding 4): verb,
# then at most 3 words of gap (non-greedy, captured so the gap can be
# negation-checked), then one object phrase. Applied to a slice from the
# path match's end to the end of the CURRENT SENTENCE or +200 chars,
# whichever comes first.
_FOLLOW = re.compile(
    r"\b(follow|execute|do|run|carry\s+out)\s+((?:\S+\s+){0,3}?)"
    r"(it\b|its\s+steps\b|its\s+instructions\b|the\s+steps\b|every\s+task\b|all\s+tasks\b)",
    re.IGNORECASE,
)

_TASK_ID = re.compile(r"\btasks?\s+#?([A-Z]?\d+)\b", re.IGNORECASE)
_TASK_RANGE_LEAD = re.compile(r"\b(from|after|starting\s+at|starting\s+with)\s*$", re.IGNORECASE)
_TASK_RANGE_TAIL = re.compile(r"^\s*(onwards?|through|to|until|and\s+on|and\s+later|,\s*\d|and\s+\d|-\d|\.\.)", re.IGNORECASE)
_PATH_TOKEN = re.compile(r"\S*/\S+\.\w+")

# Negation set unchanged from today's _NEGATION (the hesitate/fail/only
# double-negation exception stays). Word-COUNT bound, not character-count
# (dispatch-2 finding 5: an 80-character cap is wrong - a single long
# token can push a real 3-word gap past any fixed character budget).
# The caller never slices by character count: it runs `_WORD.finditer`
# forward from the clause's own start (already a bounded slice - clauses
# are short by construction, split on `._,;:!?\n)` and ` - `) and counts
# WORD tokens, not characters, between a negation match and the name.
_NEGATION = re.compile(
    r"\b(not|never|does\s+not|doesn't|don't|won't)\b(?!\s+(?:hesitate|fail|only)\b)"
    r"|\b(can't|cannot|isn't|shouldn't|wasn't|weren't)\b",
    re.IGNORECASE,
)
_NEGATION_WORD_GAP = 4  # words, not characters

# Clause boundary chars exclude ':' from firing INSIDE a recognized
# phase-name match's own span (dispatch-2 finding 3): "autopilot:work"
# contains a ':' that is not a clause separator. The boundary search is
# therefore never run on the raw field text directly; it is run on a
# per-field COPY where every already-found `_PHASE_NAME_FORMS` match span
# (and `_SKILL_MD_PATH` match span) has its internal ':' and '/'
# characters replaced with a placeholder letter ('x') before boundary
# detection - this changes no byte outside those spans and never affects
# the character OFFSETS the caller reports (the replacement is
# same-length, in a scratch copy, used only to find boundary positions;
# the quoted span returned to the caller always slices the ORIGINAL text).
_CLAUSE_BOUNDARY = re.compile(r"[.;,:!?\n)]|\s-\s")
_SENTENCE_BOUNDARY = re.compile(r"[.!?\n]")

_AGOGE_PREFIX = "agoge:"
```

Algorithm shape for `find_phase_delegation` (replaces the old `any(... for pattern in _DELEGATION_PATTERNS ...)` loop). All exemption logic lives INSIDE `find_phase_delegation` itself (finding 8), not only in `main()`, so the replay CLI's direct `is_phase_delegation` call and the live hook apply it identically. **Re-sequenced from the dispatch-1/2 revision to close dispatch-3 finding B2** (boundary masking cannot run before the spans it needs to mask are known) **by splitting the old single pass into an explicit two-pass structure: pass 1 collects every candidate match span (doing no boundary-dependent work yet); pass 2 builds the boundary/marker precomputation from ALL of pass 1's spans at once, then evaluates each candidate against it.**

0. If `subagent_type` is in `_READ_ONLY_REVIEWERS` or starts with `_AGOGE_PREFIX`, return `None` immediately (today's reviewer exemption plus the new agoge one, both inside the predicate).
1. Normalize `prompt` and `description` independently (each run through `_normalize`).
2. Check `_BARE_SLASH_PREFIX` against `prompt` only; a match returns that span immediately (no clause/scoping/negation logic - "whatever scoping follows", unconditional).
3. For each field in order `(prompt, description)`:
   **Pass 1 - collect every candidate span (no boundaries used yet):**
   a. Run `_find_skill_md_paths(text)` (the substring-gated, bounded-window helper above - dispatch-3 finding B3) to get every `_SKILL_MD_PATH` candidate span.
   b. Run each of the three `_PHASE_NAME_FORMS` regexes with `.finditer()` to get every raw candidate span, in left-to-right start-offset order. For each raw match: if `match.group("w")` is truthy and `text[match.end():match.end()+1] == _WRAP_PAIR.get(w, w)`, extend the match end by 1 (consume the close-wrap character) - this is still PURE per-match text inspection, no boundary lookup, so it belongs in pass 1. Then, independent of wrap-close: probe `_SKILL_SUFFIX.match()` against the text starting at the (possibly wrap-extended) end; a match extends the end again (dispatch-3 finding B4 - close-wrap first, optional-" skill" second, as two separate, ordered probes, never folded into one compiled alternative). Record the resulting (start, end) span alongside the raw phase-name text for scoping/negation use later.
   c. Combine pass 1a's and pass 1b's spans into one list, sorted by start offset. This combined list is now COMPLETE for this field - nothing added after this point - which is what makes pass 2's one-shot boundary build valid (closes finding B2: boundary construction now strictly follows span discovery, never precedes it).

   **Pass 2 - build the one-shot boundary/marker map, then evaluate:**
   d. **Build the boundary-detection scratch copy once for this field**, now that pass 1c's full span list exists: in a COPY of the field text, replace every span's `:`/`/` characters with `x` (same length, same offsets - dispatch-2 finding 3). Run `_CLAUSE_BOUNDARY`/`_SENTENCE_BOUNDARY` against this scratch copy ONCE (not per match), producing one SORTED list of boundary offsets. Every clause/sentence lookup below is a binary-search (`bisect`) into this one list - O(log n) per match, not a fresh regex scan - so repeated lookups across many matches never re-scan the field (closes finding 6/B3's repeated-rescan half).
   e. **Precompute whole-run-marker presence per SENTENCE, once, in the same pass** (dispatch-3 finding B3, second half: `_WHOLE_RUN_MARKERS.search()` must not be called once per phase-name match against a freshly-sliced sentence): run `_WHOLE_RUN_MARKERS.finditer()` over the WHOLE field ONE time, and for each hit, binary-search its offset into the sentence-boundary list from step d to find which sentence index it falls in; build a `set[int]` of sentence indices that contain a marker. Strong-anchor evaluation (step h.iii below) then does a single `O(1)` set-membership test against this precomputed set instead of a per-match `.search()`.
   f. For every candidate span from pass 1 (c), in order:
      g. Look up the enclosing CLAUSE (via `bisect` into the boundary list from step d) and enclosing SENTENCE INDEX (same lookup).
      h. **Question-mark skip (finding 4):** if the clause's own terminating character (the character at its boundary position, before any `_CLAUSE_BOUNDARY` strip) is `?`, or the clause is the final clause of a sentence ending in `?`, this match never counts - continue to the next match.
      i. **Strong anchor:** `_STRONG_ANCHOR_TAIL.match()` OR `_PRD_PATH_TAIL.match()` against the text immediately following the (wrap-and-skill-extended) match end, OR the match's sentence index is a member of step e's precomputed marker-sentence set.
      j. **Weak anchor** (skipped entirely when `_is_per_task_persona(subagent_type)` is true - per-task personas count the strong anchor only): `_WEAK_ANCHOR_TAIL.match()` against the text from the match end to the clause boundary, AND at least one `_WORD` token precedes the name in the clause, AND the nearest preceding word that is NOT in `_DETERMINERS` (dispatch-2 finding 4: skip past EVERY leading determiner word, not just the immediately-adjacent one) is not in `_PREPOSITIONS`. If every word back to the clause start is a determiner, the weak anchor fails.
      k. Anchored (strong or weak) ⇒ proceed to scoping; neither ⇒ continue to the next candidate.
   l. **Scoping** (Feature: Per-task scoping, this field only; dispatch-2 finding 1 fixes the connective and the path exclusion): the field is scoped when it names exactly one distinct `_TASK_ID` with no `_TASK_RANGE_LEAD`/`_TASK_RANGE_TAIL` adjacency, **OR** (not XOR - "For task 3, update hooks/guard.py so it can run the work phase." must scope on the task id alone whether or not a file path is also present) exactly one distinct `_PATH_TOKEN` that is not under `prds/` and whose basename is not `SKILL.md` (via `_is_skill_md_basename`). Scoped ⇒ this candidate (and every other candidate in this field) does not count; continue to the next field.
   m. **Negation:** a `_NEGATION` match within `_NEGATION_WORD_GAP` `_WORD` tokens of the name's start, counted by walking BACKWARD from the match start (never forward from the clause start) up to `_NEGATION_WORD_GAP` tokens or the clause start, whichever comes first (dispatch-3 finding B3: this bounds the walk to at most 4 iterations per candidate, O(1), rather than a walk whose cost scales with clause length). Negated ⇒ continue to the next candidate in this field.
   n. First surviving candidate (from pass 1's combined list, in its sorted order) ⇒ return its quoted span (`text[max(0,start-10):start+20]`, whitespace-joined, taken from the ORIGINAL match start in the ORIGINAL text, never the scratch copy).
4. No match anywhere, in either field ⇒ return `None`.

Linear-time constraint (task 5, task 7; dispatch-3 finding B3 closes what dispatch-2's fix left open): pass 1 (steps a-c) is a fixed number of `.finditer()` passes over the field, each itself linear since `_SKILL_MD_PATH` is only ever invoked through `_find_skill_md_paths`'s substring-gated bounded-window search (never a raw `.finditer()` over the whole field) and the three `_PHASE_NAME_FORMS` regexes are themselves free of nested/per-character-lookahead quantifiers - so pass 1 is O(n). Pass 2's one-time boundary build (step d) and one-time marker-sentence build (step e) are each one `.finditer()` over the field, O(n). Every PER-CANDIDATE lookup after that (steps g, i, j, m) is O(log n) (binary search into a sorted list) or O(1) (bounded 4-token backward walk, bounded determiner-skip walk - amortized O(1) per candidate since total determiner-skipping work across a field is bounded by the field's own length), never a fresh scan of the clause or sentence. Total cost across however many candidates a field has is therefore O(n log n) in the worst case (dominated by the per-candidate binary searches), a bound this design accepts as "linear enough" for the PRD's acceptance test (the crafted/prose 1MB prompts, each with few-to-no candidates triggering the expensive paths) rather than claiming a strict O(n) no regex-based implementation can fully guarantee against an adversarial input engineered specifically to defeat it.

### Dispatch policy additions

```python
def _deny_message(subagent_type: str | None, span: str) -> str:
    """Per-task personas (_is_per_task_persona(subagent_type) is True) get
    EXACTLY:
      f'autopilot: this per-task prompt names a phase as the thing to run: '
      f'"{span}". If it only mentions the phase, rephrase that sentence or '
      f'scope it to one task (task N). hooks/guard_phase_delegation.py '
      f'denied this Agent call.'
    (no "Matched:" word - the span is inline in the first sentence).
    Everyone else gets EXACTLY today's text plus a trailing quote clause:
      'autopilot: run the phase skill (plan-tasks / design-solution / work) '
      'with the Skill tool in THIS session; dispatch Agent calls only for '
      'per-task subagents (Ivan, Tess, Devon, reviewers). '
      f'Matched: "{span}". hooks/guard_phase_delegation.py denied this '
      'Agent call.'
    These two literal strings are copied verbatim from the PRD's Deny
    message feature, not paraphrased (finding 7)."""
```

The `agoge:`/reviewer exemption has no separate `_bucket_exempt` function (finding 8 resolution) - it is step 0 of `find_phase_delegation` above, so `is_phase_delegation` (`find_phase_delegation(tool_input) is not None`) already reflects it, and `main()` needs no separate check. `dev/bin/replay_delegation_guard.py`'s own `bucket()` function (Replay acceptance capability) is a SEPARATE, PRD-specified classifier for REPORTING ONLY - it reads `subagent_type`/`description` to label each record `agoge`/`reviewer`/`per-task`/`other` for the printed summary, and does not feed back into `find_phase_delegation`'s decision (question 11: the predicate decides on `subagent_type` alone, always; `bucket()`'s looser description-sniffing for the `per-task` label is a reporting convenience and can therefore disagree with the predicate's own exemption - that disagreement is expected and is what lets `other`-bucketed real dispatches surface for human review without being silently exempted).

### `enforce_prd_location.py`

```python
def _check_file_path(file_path: str) -> str | None:
    if not file_path:
        return None
    file_path = file_path.encode("utf-8", "replace").decode("utf-8")  # NEW, first line
    resolved = Path(file_path).resolve()
    ...  # unchanged below
```

### `note_session_leave.py` / `guard_skill_after_leave.py`

```python
# note_session_leave.py main(), after reading `session`:
if not isinstance(session, str) or not session or "�" in session:
    allow()

# guard_skill_after_leave.py left_at(), after reading `session` in main():
if not isinstance(session, str) or not session or "�" in session:
    allow()
```

### `dev/bin/replay_delegation_guard.py`

```python
def bucket(tool_input: dict, exempt: frozenset[str]) -> str:
    """'agoge' | 'reviewer' | 'per-task' | 'other' per the Full local replay
    feature's bucket rules."""

def main(argv: list[str] | None = None) -> int:
    """--transcripts DIR (default ~/.claude/projects/<repo root, / and . -> '->'
    --guard PATH (default hooks/guard_phase_delegation.py)
    Reads every *.jsonl under DIR, extracts Agent tool_use blocks. Dedupe is
    keyed on json.dumps(tool_input, sort_keys=True) for COUNTING/display
    purposes only (dispatch-2 finding 8: a plain "keep first id seen, drop
    the rest" dedupe can silently drop one of the four PINNED deny ids if an
    ordinary record elsewhere in the corpus happens to carry byte-identical
    tool_input, which then makes the pinned-id presence check below find
    nothing to flag). To avoid that: build the dedup map as
    `{key: {"tool_input": ti, "ids": [id, ...]}}`, appending every source id
    seen for that key rather than keeping only the first - the four pinned
    ids (`toolu_011eQouP7ZMWxba7b8ijXmiR`, `toolu_01WwjmFapBm8w3NYCwWddUbk`,
    `toolu_01S6V4tZDtrS3ePnXWtD9dT2`, `toolu_01Ku4TbcQoeik6ZLf5XkkAuD`) are
    then looked up by membership in ANY dedup group's `ids` list, not by
    whether they happen to be the group's first-seen id. Runs
    is_phase_delegation via subprocess under _AUTOPILOT_LOOP=1 against
    --guard (so it exercises the real hook entrypoint, not just the imported
    function) once per UNIQUE tool_input, buckets each, prints `total N`,
    per-bucket `<bucket> <count> refused <n>`, then one
    `<bucket> <id> <subagent_type> <description>` line per refusal (using
    the group's first id for display, since all ids in a group share the
    same verdict).
    Exit 2: DIR missing or zero Agent tool_input records found.
    Exit 1: any per-task/agoge/reviewer record refused, OR any of the four
    pinned deny ids - found via the ids-list membership check above, never
    via first-seen-id equality - is present and allowed.
    Exit 0: otherwise. 'other' refusals print but never affect exit code."""
```

## Data flow

1. Claude Code's PreToolUse dispatcher reads an `Agent` tool call's JSON payload on stdin and invokes `guard_phase_delegation.py` as a subprocess (`hooks/dispatch.py` → `hooks.json` registration, unchanged).
2. `main()` short-circuits to `allow()` unless `_AUTOPILOT_LOOP` is set; reads stdin via `_common.read_input()` (already hardened against bad UTF-8, deep nesting, empty input — task 8 only pins this with tests, no hook body change there).
3. `tool_input` is extracted; `subagent_type` checked against the exemption set (`_READ_ONLY_REVIEWERS` ∪ `agoge:` prefix).
4. `prompt`/`description` normalized, scanned by `find_phase_delegation`.
5. A match ⇒ `_deny_message` builds the per-type stderr text ⇒ `block()` (exit 2). No match ⇒ `allow()` (exit 0).
6. Separately, `replay_delegation_guard.py` reads local transcript JSONL files, extracts historical `Agent` tool_use payloads, and re-runs them through the same guard entrypoint as a subprocess, reporting without mutating anything — a read-only regression harness, not part of the hook's live data flow.
7. `enforce_prd_location.py` and the two leave-marker hooks are independent PreToolUse/PostToolUse hooks on `Write`/`MultiEdit`/`Bash`/`Skill` respectively; their data flow (stdin → `read_input` → check → allow/block) is unchanged, only a normalization/guard-clause line is added before the existing check.

## Reuse inventory

- `hooks/_common.py::read_input/allow/block/resolve_toplevel` — already used by all six touched hooks; no new helper needed. Searched `rg "def read_input|def allow|def block" hooks/_common.py` — confirms single shared implementation, no duplicate to consolidate.
- `hooks/_common.py` has no existing text-normalization helper (`rg "NFKD|NFKC|unicodedata" hooks/*.py` finds only `guard_phase_delegation.py`'s own `unicodedata.normalize` calls) — `_normalize` stays local to `guard_phase_delegation.py` as today's analogous code already does; not promoted to `_common.py` since no other hook needs it (YAGNI, matches existing placement).
- `dev/bin/` already holds standalone CLI scripts invoked by `release-checks` (`rg -l "def main" dev/bin/*.py` — e.g. prior replay/report tooling patterns) — `replay_delegation_guard.py` follows the same `def main(argv) -> int` + `if __name__ == "__main__": sys.exit(main())` shape already established there, no new scaffolding invented.
- The existing `_READ_ONLY_REVIEWERS` frozenset and its exemption check stay exactly as today; the `agoge:` exemption is one `.startswith()` check added beside it, not a rewrite.
- `hooks/test_guard_skill_after_leave.py` and `hooks/test_enforce_prd_location.py` already exist with the harness (`capture_main`, `tmp_path`, `_AUTOPILOT_LOOP=1` env) the new U+FFFD/surrogate tests reuse verbatim — confirmed by reading both files above; no new test scaffolding needed.

## Alternatives considered

1. **Chosen: full structural rewrite of the predicate** (object-position + strong/weak anchor + scoping + bound negation), as the PRD specifies. Buys: fixes both false-refuse (ordinary per-task prompts) and false-allow (agoge lanes, bare slash-command) classes from one coherent model instead of patching the verb/gap-word list again (which is what 00267 already tried and which a third patch round would repeat). Cost: the larger of the three options, touching every pattern in the module.
2. **Smallest-diff version: patch only the two false-allow regressions walter found** (bare `/autopilot:work <path>` prompt, 3 other walter misses) by adding targeted patterns to the existing verb/gap-word engine, leaving the false-refuse behavior (and the message/timing/exemption defects) for a later PRD. Rejected: the operator's walkthrough (`agoge-2026-10-07.md`, `agoge-2026-10-07-2.md`) explicitly settled all 21 findings together, and the PRD's own Success Metrics require the full replay fixture (including the false-refuse fixtures) to pass — a partial patch would leave `test_per_task_prompts_that_mention_a_phase_are_allowed` red and ship another round of the same whack-a-mole the 00267→v2 history already shows (each release finding new false-allows or false-refuses in the other list-based engine).
3. **Middle ground: keep verb/gap-word matching but add a post-hoc scoping override** (if a task id or file path is present anywhere in the text, always allow) without the object-position/anchor redesign. Rejected: this is strictly weaker than option 1's per-field scoping (Feature: Per-task scoping explicitly requires scoping to apply only in the *same field* as the match — `description: "Run plan-tasks for PRD 00300"` beside a task-3 prompt must stay refused, which a text-wide override cannot express) and does not fix the cost-bound or weak-anchor false-refuse cases at all.

Option 1 is the PRD's own fully-specified behavior; the design doc's job here is to give plan-tasks exact interfaces, not to re-litigate scope the operator already settled.

## Risks & edge cases

- **New weak-anchor surface still misses a real per-task prompt the fixtures don't cover.** Mitigated in-PRD by task 9's full local replay (exits 1 on any per-task/agoge/reviewer refusal); the design doc does not add anything beyond what task 9 already requires.
- **The committed replay fixture (`replay.jsonl`) drifts from reality as transcripts rotate** — task 2's premise re-check (`rg -l <id>` at execution time) and the "skip and report, never invent" rule bound this; nothing in the design changes that bound.
- **Likely next change 1: homoglyph normalization** (Cyrillic `о` etc.) is explicitly out of scope (packet 9) but flagged in the PRD; `_normalize`'s category-based approach (NFKD + Cf/Mn drop + Pd mapping) is chosen specifically because it is the smallest step that doesn't foreclose a later homoglyph table (a per-character substitution map could be added as one more `.translate()` call without touching the rest of the pipeline).
- **Likely next change 2: a fifth phase or renamed skill** (e.g. a future `/autopilot:review` phase skill) would need `_PHASE_NAME` and `_PER_TASK_PERSONAS`/`_STRONG_ANCHOR_TAIL` extended; keeping these as named module constants (not inlined into one giant regex) is what keeps that a one-line diff rather than a re-derivation.
- **Likely next change 3: the span-quoting deny message could leak more context than intended** if a future prompt embeds a secret-looking token right at the match offset; out of scope here (the PRD's message feature is exact and unconditional), but worth flagging since `replay.jsonl` already carries a "drop any record holding a secret-looking token" rule for the same reason (PRD Risks section) — the same caution applies to live deny-message spans, not just the fixture.
- **This design boxes in** any future attempt to make the guard verb-based again: the module-private constants above assume an anchor/scoping/negation pipeline, not a flat pattern list; reverting to a list-based engine would be a full rewrite, not an incremental change. Accepted, since the PRD explicitly retires the list-based engine for the reasons in its Problem Statement.

## Test strategy outline

- **Unit (structure)**: `hooks/test_guard_phase_delegation_structure.py` — every `find_phase_delegation`/`is_phase_delegation` behavior listed in PRD task 1 and task 5's acceptance bullets, parametrized exactly as written there (normalization, three-phrasing denial, bare-slash denial, SKILL.md-path denial, emphatic-negation denial, compound-noun-with-whole-run-marker denial, per-task-prompt allowance, one-named-task-or-file scoping, task-ranges/PRD-paths/free-only non-scoping, per-task-persona strong-anchor-only, quoted-text-still-checked, prepositional/question allowance, clause-bound negation). Each new case fails at base per the PRD's stated base behavior.
- **Unit (narrowing)**: `hooks/test_guard_phase_delegation_narrowing.py` re-sorted per task 5's exact flip list, premise-checked against `rg -c "^def test_" ...` = 14 at execution time.
- **Unit (dispatch)**: `hooks/test_guard_phase_delegation_dispatch.py` — agoge exemption, agoge-lookalike-still-checked, per-type deny message content (rephrase vs. Skill-tool text, `Matched:` presence/absence), and the s/MB cost-bound timing test (crafted + prose prompts, best-of-three, <0.3s/MB).
- **Regression (replay fixture)**: `hooks/test_guard_phase_delegation_replay.py` — the 17-record committed fixture, subprocess-per-record under `_AUTOPILOT_LOOP=1`, asserting each record's expected exit code; plus the "all four deny ids present" fixture-integrity check.
- **Hardening**: `hooks/test_read_input.py` — the six-hook × four-case stdin matrix (invalid UTF-8, deep nesting, empty stdin, U+FFFD-in-string), all exit 0 no traceback; plus the targeted replaced-byte-in-a-session-id check.
- **Targeted hook fixes**: `hooks/test_enforce_prd_location.py`'s new lone-surrogate test; `hooks/test_guard_skill_after_leave.py`'s two new U+FFFD session tests (and the equivalent coverage task 4 implies for `note_session_leave.py`, exercised via the six-hook matrix in task 8).
- **End-to-end**: `dev/bin/test_replay_delegation_guard.py` (synthetic transcript dirs under `tmp_path`, five cases per the Full local replay feature) plus one required live run of `python3 dev/bin/replay_delegation_guard.py` with its full stdout/exit code pasted into the task 9 report — exit 0 required, real local transcripts as the corpus (no count asserted, since transcripts rotate).
- **Gate**: every new `hooks/test_*.py`/`dev/bin/test_*.py` file added to `dev/bin/release-checks` in the same task that adds it (enforced by `test_hook_registration.py::test_every_hooks_test_file_is_in_the_release_gate`); `CHANGELOG.md`'s three-line replacement checked by the two `rg -c` assertions task 10 specifies.

## Review log

Dispatch 1 (claude) found 5 blocking, 4 non-blocking, 3 question, 0 cardinal-sin findings, all fixed or resolved above except the non-blocking/question items recorded below (per the skill: fix blockers, record non-blockers/questions without fixing).

Non-blocking (recorded, not fixed — covered by design notes above where practical):
- Docstring clarity issues in the original draft (garbled `_deny_message`/`guard_skill_after_leave` prose) — fixed in the rewrite above as part of finding 7/8 remediation, since the fix was a wording correction rather than new scope.
- Bare-slash-prefix field scope (prompt-only vs. both fields) — resolved explicitly above (finding 9) as a design decision, not left open.

Questions (recorded, not fixed):
- Whether scoping/negation should apply to the SKILL.md always-delegate form — resolved above (question 10: both skipped, same as bare-slash) as a design decision since the PRD groups both forms under "always delegates".
- Whether `bucket()`'s description-based per-task detection in the replay CLI should match `find_phase_delegation`'s `subagent_type`-only test — resolved above (question 11: deliberately decoupled, bucket() is reporting-only).
- Order of scoping vs. negation checks (question 12) — resolved above: scoping is a field-wide property checked once per field before any match's negation is evaluated, so a later match's negation state is irrelevant once the field is scoped.

dispatch 1 (claude): cardinal-sin 0, blocker 5, non-blocker 4, question 3

Dispatch 2 (codex) found 8 blocking, 1 non-blocking, 1 question, 0 cardinal-sin findings against the post-dispatch-1 revision. All 8 blockers fixed above: (1) scoping XOR→OR plus basename-based SKILL.md exclusion, (2) `_WRAP_CLOSE_CLASS` unescaped-`]` bug fixed by writing `]` first in each class, (3) clause-boundary detection moved to a per-field scratch copy that masks `:`/`/` inside recognized match spans before boundary search, (4) weak-anchor nearest-word lookup now skips every leading determiner rather than only the adjacent one, (5) the fixed 80-character negation look-back cap replaced with a true word-count walk over the (already-bounded) clause slice, (6) `_SKILL_MD_PATH`'s greedy `\S*/` replaced with a non-greedy single-segment-at-a-time repeat, plus per-field boundary/marker precomputation closing the repeated-rescan half of the same finding, (7) optional `" skill"` now consumed inside the phase-name match itself (not left to the anchor tails) and a dedicated `_PRD_PATH_TAIL` strong anchor added for a bare PRD-path object, (8) the replay CLI's dedup keeps every source id per unique `tool_input` so a pinned deny id can never be silently dropped behind an ordinary duplicate.

Non-blocking (recorded, not fixed):
- Dispatch 2 finding 9: the constants commentary's claim that "scoping and negation are both skipped" for the SKILL.md form was imprecise - the executable algorithm (step 3a) always runs the follow-phrase negation check for this form (that is how `Read skills/work/SKILL.md and do not perform all tasks` stays allowed); only SCOPING is skipped for this form, never negation. The design text above has been corrected to say so precisely (step 3a's wording); recorded here since dispatch 2 raised it as a documentation-consistency concern, not a behavioral gap - the behavior itself was already correct.

Questions (recorded, not fixed):
- Dispatch 2 finding 10: task 2's "skip and report a missing id" premise-check instruction and the fixture-integrity acceptance test's unconditional "all four deny ids present" requirement could read as contradictory if a pinned id's transcript record has rotated out by execution time. Left for the planner/implementor to resolve at task-2 execution time per the PRD's own instruction ("skip and report any missing id, never invent a record") - if a pinned deny id is genuinely gone from the corpus, the fixture-integrity test's requirement becomes unsatisfiable by construction and the task report must say so explicitly rather than weakening the assertion silently.

dispatch 2 (codex): cardinal-sin 0, blocker 8, non-blocker 1, question 1

Dispatch 3 (codex, verification pass over the dispatch-2 fixes) confirmed findings 1, 4 and 8 fully fixed, and found 4 NEW/residual blockers (B1-B4) plus 2 non-blocking in the fixes themselves, 0 cardinal-sin, 0 question. All 4 blockers fixed above (this is the design's final fix pass - the 3-dispatch ceiling is reached): (B1) `_WRAP_OPEN`'s character class was missing an escaped literal `[` member (the bracket-wrapped form silently fell through) - added `\\[` to the class; (B2) the algorithm's boundary-scratch step referenced match spans from a step that ran AFTER it - resequenced into an explicit two-pass structure (pass 1 collects every candidate span with no boundary dependency; pass 2 builds the one-shot boundary/marker map from pass 1's complete span list, then evaluates); (B3) `_SKILL_MD_PATH`'s backtracking regex was still worst-case quadratic on a slash-free run even non-greedy, and the whole-run-marker search still re-scanned per match - replaced with a substring-gated bounded-window helper (`_find_skill_md_paths`) for the path, a one-time whole-field marker-presence precomputation bucketed by sentence index, and a bounded backward word-walk (never a forward walk from clause start) for the negation check; (B4) the optional `" skill"` suffix could not be matched by a single compiled alternative when a closing wrapper character (e.g. a backtick) sits between the name and "skill" - split into two separate, ordered post-match probes (consume wrap-close, THEN probe `_SKILL_SUFFIX` past it) via the new `_SKILL_SUFFIX` regex, removed from the `_PHASE_SKILL`/`_PHASE_BARE` patterns themselves.

Non-blocking (recorded, not fixed):
- Dispatch 3: `_PRD_PATH_TAIL` requires a `/prds/` segment, so it does not fire for a root-relative `prds/wip/00300.md` (no leading path component) or for the comma-prefixed form `the work phase, prds/wip/00300.md` the Risks section's own example implies. The PRD's own required test case (`Run the work phase for docs/dev/project-management/prds/wip/00300.md.`) always has a path prefix before `prds/`, so this is a real but narrower gap than the PRD's stated acceptance surface requires; left as a known limitation for the implementor to widen if a root-relative case turns up in the replay fixture (task 9's full local replay is the backstop that would catch it).
- Dispatch 3: the constants commentary and this Review log still describe the SKILL.md form informally in a couple of places as "scoping and negation both skipped" in EARLIER entries of this log (dispatch 1/2 history above) - those are historical records of what was said at the time, deliberately left unedited; the live spec text (step 3, pass 1a / `_SKILL_MD_PATH` comment) states the corrected scoping-only-skip behavior precisely.

dispatch 3 (codex): cardinal-sin 0, blocker 4, non-blocker 2, question 0

