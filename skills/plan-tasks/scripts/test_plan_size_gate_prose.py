"""Prose pins for the plan-expansion gate rewrite of plan-tasks step 5.5.

Same pattern as the other prose suites in this repo: read SKILL.md once at
module level, slice each step under test by its `### ` heading, and assert on
short, reword-resistant fragments, each with a failure message naming what
drifted and where to look.

Nothing executes steps 4, 4.7 and 5.5 but a reader, so the prose IS the
mechanism. This file pins three things the rewrite has to say:

- step 5.5 hands the PRD to the gate (`check-plan --prd ...`), names the
  three stall rules with their numbers AND their direction (over 15, over
  3.0 with more than 8, 2 or more), the `plan_expansion` stall site, the
  exit mapping (3 stalls, 0 continues) and the `plan_expansion: allow`
  override, and tells an operator who admits an oversized plan on purpose
  to set `rework_cap: 3` explicitly, because nothing changes the cap
  automatically;
- step 4 lists `files` among the persisted top-level task payload keys, as
  the task's repo-relative paths, never as an empty or ignored key;
- step 4.7's two worked task-add payloads carry real `"files": [...]`.

Every pin comes with its inversion rejected: a step that names the right
number with the wrong direction word, the right stall site beside `never`,
or the right key beside "the gate ignores it" is a wrong rewrite that reads
like the right one, and `_near` alone cannot tell them apart.

Rule pins read a MASKED view of SKILL.md in which fenced code and blockquote
lines are blanked out (a rule quoted into a blockquote and disowned is not a
rule); inline code spans stay prose. Fence-shaped pins (the gate invocation,
the frontmatter example, the payloads) read the unmasked step.

This file pins PROSE only. The gate's own exit codes and rules are covered by
the run-autopilot CLI tests, not here.
"""

from __future__ import annotations

import re
from pathlib import Path

_PLAN_TASKS = Path(__file__).resolve().parent.parent
_SKILL_MD = _PLAN_TASKS / "SKILL.md"
_SKILL_TEXT = _SKILL_MD.read_text()

_STEP_4_HEADING = "### 4. Create tasks"
_STEP_4_5_PREFIX = "### 4.5."
_STEP_4_7_PREFIX = "### 4.7."
_STEP_5_HEADING = "### 5. Set dependencies"
# Prefix only: the title after it changes with the rewrite, the number stays.
_STEP_5_5_PREFIX = "### 5.5."
_STEP_6_HEADING = "### 6. Report summary"


def _locate(marker: str, start: int = 0) -> int:
    found = _SKILL_TEXT.find(marker, start)
    if found == -1:
        raise ValueError(
            f"{_SKILL_MD}: the heading {marker!r} is gone, so every pin scoped "
            "to that step is unverifiable. Restore the heading or retarget "
            "this suite at its replacement.",
        )
    return found


def _mask_non_prose(text: str) -> str:
    """Blank fenced code and blockquote lines, character for character.

    Offsets survive (every blanked character becomes a `.`), so a match in
    the masked text still locates itself in the original. `.` is the blanking
    character deliberately: the clause gap below is `[^.]`, so no pin can
    match inside a blanked region, nor straddle one. A rule parked in a code
    fence or quoted into a blockquote and disowned is not a rule this step
    instructs.
    """
    chars = list(text)
    in_fence = False
    offset = 0
    for line in text.splitlines(keepends=True):
        stripped = line.lstrip()
        is_fence = stripped.startswith(("```", "~~~"))
        if in_fence or is_fence or stripped.startswith(">"):
            for index in range(offset, offset + len(line)):
                if chars[index] != "\n":
                    chars[index] = "."
        if is_fence:
            in_fence = not in_fence
        offset += len(line)
    return "".join(chars)


_MASKED_TEXT = _mask_non_prose(_SKILL_TEXT)

_STEP_4_START = _locate(_STEP_4_HEADING)
_STEP_4_END = _locate(_STEP_4_5_PREFIX, _STEP_4_START)
_STEP_4_PROSE = _MASKED_TEXT[_STEP_4_START:_STEP_4_END]

_STEP_4_7_START = _locate(_STEP_4_7_PREFIX, _STEP_4_END)
_STEP_4_7_END = _locate(_STEP_5_HEADING, _STEP_4_7_START)
_STEP_4_7 = _SKILL_TEXT[_STEP_4_7_START:_STEP_4_7_END]

_STEP_5_5_START = _locate(_STEP_5_5_PREFIX, _STEP_4_7_END)
_STEP_5_5_END = _locate(_STEP_6_HEADING, _STEP_5_5_START)
_STEP_5_5 = _SKILL_TEXT[_STEP_5_5_START:_STEP_5_5_END]
_STEP_5_5_PROSE = _MASKED_TEXT[_STEP_5_5_START:_STEP_5_5_END]


def _joiner(gap: int) -> str:
    """A gap that cannot cross a sentence break.

    A period followed by whitespace (or another period) ends the gap, so a
    clause pin fails the moment its halves drift into separate sentences. A
    period glued to the next word is not a break: `step 4.7`, a `3.0`
    ratio, `plan-<n>-files.txt` and `state.json` all sit mid-sentence in
    the steps under test. Blanked regions are runs of `.` ending in a
    newline, so no gap can enter or cross one.
    """
    return f"(?:[^.]|\\.(?=[^\\s.])){{0,{gap}}}?"


def _near(text: str, first: str, second: str, gap: int = 160) -> bool:
    """Do two regex fragments meet inside one sentence, in either order?

    Each fragment is wrapped in `(?:...)` before joining, so an alternation
    like `planned|tasks` binds to the whole fragment. Joined bare, the `|`
    would split the joined pattern instead: `\\b8\\b<gap>planned|tasks`
    matches a lone `tasks` anywhere in the step, and the reversed pair
    matches a lone `planned`, so the number drops out of the pin.
    """
    joiner = _joiner(gap)
    return any(
        re.search(
            joiner.join(f"(?:{fragment})" for fragment in pair),
            text,
            re.IGNORECASE,
        )
        for pair in ((first, second), (second, first))
    )


# A rejection reads "beside": a short gap catches the inverted claim ("Exit
# 0 means the gate stalled", "the parser writes `rework_cap: 3` for you")
# without also catching a legitimate mention further along the sentence.
_BESIDE = 60

# The direction the three stall rules read in: over, not under. `>` is the
# contract's own symbol (`planned > 15`, `expansion > 3.0`).
_OVER = r"\b(?:over|above|more than|exceed\w*)\b|>"


def _at_most(text: str, number: str) -> bool:
    """Does an at-most comparison govern `number` anywhere in `text`?

    "fewer than 15", "below 3.0", "at most 8", "`planned < 15`" and
    "8 planned tasks or fewer" all invert a rule that stalls from above;
    "under every rule" two bullets away does not, which is why this reads
    adjacency rather than a sentence-wide gap.
    """
    governed = (
        r"(?:\b(?:fewer than|less than|under|below|at most|no more than|up to)\b"
        rf"|<=?|≤)\s*(?:the\s+)?{number}\b"
    )
    trailing = (
        rf"\b{number}\b[^.]{{0,24}}?\b(?:or fewer|or less|or under|or below|at most)\b"
    )
    return bool(re.search(f"{governed}|{trailing}", text, re.IGNORECASE))


def _last_sentence_before(prose: str, offset: int) -> str:
    """The last live-prose sentence that ends before `offset` in masked text.

    Sentence breaks are the joiner's: a period followed by whitespace.
    Blanked regions are runs of `.`, so they split into dot-only chunks and
    drop out; what is left is the sentence that introduces whatever sits at
    `offset`.
    """
    chunks = re.split(r"\.(?=\s|$)", prose[:offset])
    live = [chunk for chunk in chunks if chunk.strip(". \t\n")]
    return live[-1] if live else ""


_FENCE_RE = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)


def _fenced_blocks(text: str) -> list[str]:
    return [match.group(1) for match in _FENCE_RE.finditer(text)]


_CHECK_PLAN_INVOCATION = (
    "python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-autopilot/cli/__main__.py "
    "check-plan --prd dev/local/prds/wip/<state.prd>"
)


def test_step_5_5_passes_the_prd_to_check_plan() -> None:
    # The gate reads the PRD to count its `- [ ]` task lines and list its
    # modules; an invocation without `--prd` runs the ceiling rule alone.
    # Pinned on the one line that names the command, so a second spelling
    # (a prose "run `check-plan`" beside the fence) cannot hand the planner
    # the old PRD-less call.
    lines = [line for line in _STEP_5_5.splitlines() if "check-plan" in line]
    assert len(lines) == 1, (
        f"{_SKILL_MD}: step 5.5 names `check-plan` on {len(lines)} lines, "
        "not one. The command is spelled once, in its fence; prose calls it "
        "'the gate' or 'the command'. Every extra spelling is a second "
        "invocation for the planner to copy, and the one without `--prd` is "
        "the one that skips two of the three rules."
    )
    (invocation,) = lines
    assert "--prd dev/local/prds/wip/<state.prd>" in invocation, (
        f"{_SKILL_MD}: step 5.5's gate invocation ({invocation.strip()!r}) "
        "does not pass `--prd dev/local/prds/wip/<state.prd>`. Without the "
        "PRD the gate cannot compute the expansion ratio or the unlisted "
        "modules, and only the task ceiling is checked."
    )
    # A whole fence line, not a substring: `# python3 ... check-plan --prd`
    # or `echo python3 ...` holds the invocation and runs nothing.
    assert any(
        line.strip() == _CHECK_PLAN_INVOCATION
        for block in _fenced_blocks(_STEP_5_5)
        for line in block.splitlines()
    ), (
        f"{_SKILL_MD}: step 5.5 has no code fence in which a whole line is "
        f"the exact gate invocation {_CHECK_PLAN_INVOCATION!r}. A command "
        "quoted in prose, commented out, or echoed is paraphrased on the "
        "way to the shell; the fence line is what the planner copies."
    )
    # The fence can be right while the prose tells the planner to strip the
    # flag before running it; the prose is what the planner reads first.
    assert not re.search(
        r"\b(?:drop|omit|remove|strip|without|skip)\b[^.]{0,40}--prd",
        _STEP_5_5_PROSE,
        re.IGNORECASE,
    ), (
        f"{_SKILL_MD}: step 5.5's live prose tells the planner to run the "
        "gate without `--prd` (a drop/omit/remove/strip/without/skip within "
        "40 characters of `--prd`). The fence passes the PRD; prose that "
        "says to drop the flag wins over the fence, and the gate falls back "
        "to the ceiling rule alone."
    )


def test_step_5_5_states_the_three_rules_and_their_numbers() -> None:
    # Each number is pinned next to its rule's noun AND its direction word,
    # in one sentence of live prose: a bare `15` also matches "15 sessions"
    # in the incident story, a bare `8` matches "28 tasks", and a `15` beside
    # `ceiling` is still the wrong rule when the sentence says "fewer than".
    prose = _STEP_5_5_PROSE
    assert _near(prose, r"\b15\b", r"ceiling"), (
        f"{_SKILL_MD}: step 5.5 no longer states the task-ceiling rule with "
        "its number - no sentence puts `15` beside the ceiling. A planner "
        "who cannot see the ceiling cannot size a split to clear it."
    )
    assert _near(prose, r"\b15\b", _OVER), (
        f"{_SKILL_MD}: step 5.5 states the ceiling number without its "
        "direction - no sentence puts `15` beside over/above/more than/`>`. "
        "The rule is planned tasks over the loop ceiling (`planned > 15`); "
        "without the direction word the number reads either way."
    )
    assert not _at_most(prose, r"15"), (
        f"{_SKILL_MD}: step 5.5 puts the ceiling under an at-most comparison "
        "(fewer than / under / below / at most / `<` 15, or 15 or fewer). The "
        "gate stalls plans OVER 15 tasks; inverted, the planner reads a "
        "small plan as the stall and a large one as the pass."
    )


def test_step_5_5_states_the_expansion_ratio_rule_and_its_floor() -> None:
    prose = _STEP_5_5_PROSE
    assert _near(prose, r"\b3\.0\b", r"expansion|ratio"), (
        f"{_SKILL_MD}: step 5.5 no longer states the expansion-ratio rule "
        "with its number - no sentence puts `3.0` beside `expansion` or "
        "`ratio`. The ratio is planned tasks over the PRD's `- [ ]` lines; "
        "unstated, the stall reads as arbitrary."
    )
    assert _near(prose, r"\b3\.0\b", _OVER), (
        f"{_SKILL_MD}: step 5.5 states the ratio threshold without its "
        "direction - no sentence puts `3.0` beside over/above/exceeds/`>`. "
        "The rule is an expansion ratio over 3.0 (`expansion > 3.0`)."
    )
    assert not _at_most(prose, r"3\.0"), (
        f"{_SKILL_MD}: step 5.5 puts the ratio threshold under an at-most "
        "comparison (below / under / at most / `<` 3.0, or 3.0 or less). The "
        "gate stalls when the ratio is OVER 3.0; inverted, a plan that "
        "barely expands the PRD reads as the stall."
    )
    assert _near(prose, r"\b8\b", r"planned|tasks"), (
        f"{_SKILL_MD}: step 5.5 no longer states the ratio rule's floor - no "
        "sentence puts `8` beside the planned task count. The ratio only "
        "stalls above 8 planned tasks; without the floor a three-line PRD "
        "planned to six tasks reads as a stall."
    )
    assert _near(prose, r"\b8\b", _OVER), (
        f"{_SKILL_MD}: step 5.5 states the ratio rule's floor without its "
        "direction - no sentence puts `8` beside more than/over/above/`>`. "
        "The ratio rule applies with MORE THAN 8 planned tasks; state the "
        "floor from above, not as '8 or fewer'."
    )
    assert not _at_most(prose, r"8"), (
        f"{_SKILL_MD}: step 5.5 puts the ratio rule's floor under an at-most "
        "comparison (fewer than / under / at most 8, or 8 or fewer). The "
        "ratio rule applies with MORE THAN 8 planned tasks; inverted, it "
        "applies to exactly the small plans it was meant to spare."
    )


def test_step_5_5_states_the_unlisted_modules_rule_as_two_or_more() -> None:
    prose = _STEP_5_5_PROSE
    assert _near(prose, r"\b(?:2|two)\b", r"unlisted|module"), (
        f"{_SKILL_MD}: step 5.5 no longer states the unlisted-modules rule "
        "with its number - no sentence puts `2` beside unlisted modules. Two "
        "or more modules the PRD never named is the third stall rule."
    )
    assert _near(prose, r"\b(?:2|two)\b", r"\b(?:or more|at least)\b|>="), (
        f"{_SKILL_MD}: step 5.5 states the unlisted-modules number without "
        "its direction - no sentence puts `2` beside 'or more'/'at least'/"
        "`>=`. The rule is 2 OR MORE unlisted modules; 'two unlisted modules "
        "are fine' names the same number and inverts the rule."
    )
    assert not _at_most(prose, r"(?:2|two)"), (
        f"{_SKILL_MD}: step 5.5 puts the unlisted-modules number under an "
        "at-most comparison (fewer than / under / at most 2, or 2 or fewer). "
        "The gate stalls on 2 OR MORE unlisted modules."
    )


def test_step_5_5_names_plan_expansion_as_the_stall_site() -> None:
    prose = _STEP_5_5_PROSE
    # `(?!:)` keeps the override key out of it: `plan_expansion: allow`
    # beside `stall` is the override sentence, not the stall site.
    assert _near(prose, r"\bplan_expansion\b(?!:)", r"stall\w*|site"), (
        f"{_SKILL_MD}: step 5.5 never names `plan_expansion` as the stall "
        "site in live prose (the override key `plan_expansion: allow` does "
        "not count). The loop-mode stall procedure keys on the site; the "
        "old `oversized_plan` site, or none, files the stall under the "
        "wrong name."
    )
    assert "oversized_plan" not in prose, (
        f"{_SKILL_MD}: step 5.5's live prose still names `oversized_plan`. "
        "That site is retired; a step that names both sites - even as "
        "'never `plan_expansion`' - hands the planner the old one. Remove "
        "every mention of `oversized_plan` from the step's prose."
    )


def test_step_5_5_names_the_override_key() -> None:
    prose = _STEP_5_5_PROSE
    assert "plan_expansion: allow" in prose, (
        f"{_SKILL_MD}: step 5.5 never names the `plan_expansion: allow` "
        "override key in live prose. A stalled PRD has no documented way "
        "back into the batch - or the key only appears in a fence or a "
        "blockquote, where it is an example, not an instruction."
    )
    assert _near(
        prose,
        "plan_expansion: allow",
        r"frontmatter|override|skip\w*|exit 0",
    ), (
        f"{_SKILL_MD}: step 5.5 names `plan_expansion: allow` but no "
        "sentence says what it is - a frontmatter override that skips the "
        "gate (exit 0, one stderr line). Named without its effect, the key "
        "is trivia."
    )
    # The exit mapping the override sits on: 3 stalls, 0 continues. Each
    # code is pinned to its meaning and its inversion rejected, because a
    # step that swaps them reads as complete and stalls nothing.
    assert _near(prose, r"\bexit 3\b", r"stall\w*"), (
        f"{_SKILL_MD}: step 5.5 no longer says exit 3 stalls - no sentence "
        "puts `exit 3` beside `stall`. Exit 3 is the gate's stall verdict: "
        "loop mode stalls the PRD and does NOT start the build."
    )
    assert _near(prose, r"\bexit 0\b", r"\b(?:continue|proceed|under every rule)\b"), (
        f"{_SKILL_MD}: step 5.5 no longer says exit 0 continues - no "
        "sentence puts `exit 0` beside continue/proceed/'under every rule'. "
        "Exit 0 is the pass: under every rule, continue to step 6."
    )
    assert not _near(
        prose, r"\bexit 3\b", r"\bpass\w*|continue to step 6", gap=_BESIDE
    ), (
        f"{_SKILL_MD}: step 5.5 reads exit 3 as the pass (`exit 3` beside "
        "pass/'continue to step 6'). Exit 3 is the stall; a planner who "
        "reads it as the pass builds the oversized plan the gate refused."
    )
    assert not _near(prose, r"\bexit 0\b", r"stall\w*", gap=_BESIDE), (
        f"{_SKILL_MD}: step 5.5 reads exit 0 as a stall (`exit 0` within "
        f"{_BESIDE} characters of `stall` in one sentence). Exit 0 is the "
        "pass under every rule; keep the word 'stalled' out of the exit-0 "
        "clause, including the override sentence."
    )


def test_oversized_override_guidance_explicitly_sets_rework_cap_three() -> None:
    prose = _STEP_5_5_PROSE
    # The instruction: both keys in one sentence of live prose, with the
    # operator as the one who sets the cap.
    assert _near(prose, "rework_cap: 3", "plan_expansion: allow"), (
        f"{_SKILL_MD}: step 5.5 never tells the operator who admits an "
        "oversized plan to set `rework_cap: 3` alongside "
        "`plan_expansion: allow`, in one sentence of live prose. Stated "
        "apart, the override reads as complete on its own and the plan "
        "resumes unattended with the default cap."
    )
    assert _near(prose, r"\bset\w*|explicit\w*", "rework_cap: 3"), (
        f"{_SKILL_MD}: step 5.5 names `rework_cap: 3` but no sentence says "
        "the operator SETS it explicitly. Mentioned without the act, the "
        "cap reads as something the override brings along."
    )
    # "is never something you set explicitly" satisfies the pin above and
    # says the opposite; so does "the parser writes `rework_cap: 3` for
    # you". The cap is the operator's act, so nothing beside it may hand
    # the act to the gate or the parser.
    assert not _near(
        prose,
        "rework_cap: 3",
        r"\b(?:never|not|automatic\w*|for you|writes|raises)\b",
        gap=_BESIDE,
    ), (
        f"{_SKILL_MD}: step 5.5 puts `rework_cap: 3` within {_BESIDE} "
        "characters of never/not/automatic/'for you'/writes/raises. The "
        "operator sets the cap explicitly; prose that says it is written "
        "for them, raised automatically, or never set by hand reverses the "
        "instruction while keeping its words."
    )


def _paired_fences() -> list[tuple[int, list[str]]]:
    """Step 5.5's fences holding both override lines, with their offsets."""
    fences = [
        (
            match.start(),
            [line.strip() for line in match.group(1).splitlines() if line.strip()],
        )
        for match in _FENCE_RE.finditer(_STEP_5_5)
    ]
    return [
        (start, lines)
        for start, lines in fences
        if "plan_expansion: allow" in lines and "rework_cap: 3" in lines
    ]


def test_oversized_override_guidance_pairs_a_frontmatter_example_fence() -> None:
    # The worked example: a fence the operator copies, holding exactly the
    # two lines between frontmatter delimiters.
    paired = _paired_fences()
    assert paired, (
        f"{_SKILL_MD}: step 5.5 has no code fence holding both a "
        "`plan_expansion: allow` line and a `rework_cap: 3` line. The "
        "guidance paragraph needs its paired frontmatter example, or the "
        "operator copies the override key alone."
    )
    assert any(
        lines[0] == "---"
        and lines[-1] == "---"
        and sorted(lines[1:-1]) == ["plan_expansion: allow", "rework_cap: 3"]
        for _, lines in paired
    ), (
        f"{_SKILL_MD}: step 5.5's paired frontmatter example is not exactly "
        "`plan_expansion: allow` and `rework_cap: 3` between `---` "
        f"delimiters (found {paired[0][1]!r}). Extra keys or missing "
        "delimiters make it read as a whole PRD header to reproduce, not "
        "the two lines to add."
    )


def test_oversized_override_example_lead_in_names_the_operators_act() -> None:
    # The sentence that introduces the fence names the operator's act. "After
    # the parser runs, the PRD header reads:" introduces the same two lines
    # as the parser's output, and the operator adds nothing.
    paired = _paired_fences()
    lead_in = _last_sentence_before(_STEP_5_5_PROSE, paired[0][0])
    assert re.search(r"\b(?:set|add|write|carr)\w*", lead_in, re.IGNORECASE), (
        f"{_SKILL_MD}: the sentence introducing step 5.5's paired "
        f"frontmatter example ({lead_in.strip()!r}) names no act of the "
        "operator's (set/add/write/carry). The fence shows what the operator "
        "puts in the PRD header; introduced any other way, it reads as "
        "what the header looks like afterwards."
    )
    assert not re.search(r"\bparser\b", lead_in, re.IGNORECASE), (
        f"{_SKILL_MD}: the sentence introducing step 5.5's paired "
        f"frontmatter example ({lead_in.strip()!r}) names the parser. The "
        "two lines are the operator's to write; a lead-in that names the "
        "parser hands the second line to it. Keep the neither/nor sentence "
        "separate from the sentence that introduces the fence."
    )


def test_oversized_override_guidance_denies_any_automatic_cap_change() -> None:
    prose = _STEP_5_5_PROSE
    # No automatic cap mutation: the contract's own clause shape, `neither
    # ... nor ... changes the cap automatically` (or `nothing ...`). A bare
    # `not` before the clause also matched "NOT ONLY the gate but the parser
    # too changes the cap automatically", which is the positive claim.
    joiner = _joiner(120)
    assert re.search(
        rf"(?:\bneither\b{joiner}\bnor\b|\bnothing\b){joiner}changes the cap automatically",
        prose,
        re.IGNORECASE,
    ), (
        f"{_SKILL_MD}: step 5.5 never says, in one sentence of live prose, "
        "that neither the gate nor the frontmatter parser changes the cap "
        "automatically - the clause `changes the cap automatically` is "
        "missing, or no `neither ... nor` (or `nothing`) precedes it in its "
        "sentence. Stated in the positive, or not at all, the operator "
        "expects the override to raise the cap for them."
    )
    assert not _near(
        prose, r"\bnot only\b", "changes the cap automatically", gap=240
    ), (
        f"{_SKILL_MD}: step 5.5's `changes the cap automatically` sentence "
        "carries `not only`, which turns the negation into 'not only the "
        "gate but the parser too' - a positive claim wearing a `not`. "
        "Neither the gate nor the parser changes the cap."
    )


def test_step_4_persists_files_on_every_task() -> None:
    # Backticked (quoted or not) so `plan-<n>-files.txt` cannot satisfy it:
    # the key has to be listed as a key, beside the other persisted ones. The
    # key list is one long parenthetical, hence the wider gap.
    files_key = r"`\"?files\"?`"
    assert _near(_STEP_4_PROSE, files_key, "top-level key", gap=400), (
        f"{_SKILL_MD}: step 4 never lists `files` among the top-level task "
        "payload keys, in one sentence of live prose. `files` is the task's "
        "expected implementor-writable repo-relative paths - the slice step "
        "4.7 writes to `plan-<n>-files.txt` - and a key the step does not "
        "list is a key no planner persists, so the gate has no per-task "
        "modules to compare against the PRD."
    )
    assert _near(_STEP_4_PROSE, files_key, r"repo-relative|path\w*"), (
        f"{_SKILL_MD}: step 4 lists `files` but no sentence says what it "
        "holds - the task's repo-relative paths. A key named without its "
        "content is filled with whatever the planner guesses, and the gate "
        "compares the PRD's modules against that guess."
    )
    # A key listed as "always empty" or "ignored by the gate" is persisted
    # and useless. `never nested` is the step's own flattening rule for
    # every key, not a claim about `files`, so it is let through.
    assert not _near(
        _STEP_4_PROSE,
        files_key,
        r"\b(?:empty|ignore\w*|never(?!\s+nested\b)|leave .{0,20}blank)\b|\[\]",
        gap=120,
    ), (
        f"{_SKILL_MD}: step 4 puts `files` within 120 characters of empty/"
        "`[]`/ignore/never/'leave blank' in one sentence. `files` carries "
        "the task's real repo-relative paths on every task; told it is "
        "empty or ignored, the planner persists `[]` and the gate sees no "
        "per-task modules."
    )


def _worked_payloads() -> list[str]:
    """Step 4.7's worked task-add payload fences."""
    return [
        block for block in _fenced_blocks(_STEP_4_7) if '"estimated_tokens"' in block
    ]


def test_step_4_7_payloads_carry_files() -> None:
    payloads = _worked_payloads()
    assert len(payloads) == 2, (
        f"{_SKILL_MD}: step 4.7 has {len(payloads)} worked task-add payloads "
        '(fences carrying "estimated_tokens"), not two. The one-file and '
        "two-file examples are the pair this pin reads; a third, or a "
        "missing one, means the examples were reshaped and this suite no "
        "longer knows which is which."
    )
    # The pair is one eligible and one excluded for `files`; any other
    # split (both eligible, excluded for `size`) is not the pair the prose
    # around them describes.
    eligible = [p for p in payloads if '"qwen_eligible": true' in p]
    excluded = [p for p in payloads if '"qwen_excluded_reason": "files"' in p]
    assert len(eligible) == 1, (
        f"{_SKILL_MD}: {len(eligible)} of step 4.7's worked payloads carry "
        '`"qwen_eligible": true`, not one. The pair is one eligible one-file '
        "task and one `files`-excluded two-file task."
    )
    assert len(excluded) == 1, (
        f"{_SKILL_MD}: {len(excluded)} of step 4.7's worked payloads carry "
        '`"qwen_excluded_reason": "files"`, not one. The pair is one '
        "eligible one-file task and one `files`-excluded two-file task; an "
        "exclusion under any other reason is not the example the prose "
        "promises."
    )


def test_step_4_7_payload_files_are_real_repo_relative_paths() -> None:
    for payload in _worked_payloads():
        assert '"files": [' in payload, (
            f"{_SKILL_MD}: a worked task-add payload in step 4.7 "
            f'({payload.strip()[:80]!r}) carries no `"files": [` key. The '
            "payload is what the planner copies; a key missing from it is "
            "never persisted, and the gate finds no per-task modules to "
            "compare against the PRD."
        )
        listed = re.search(r'"files": \[([^\]]*)\]', payload)
        paths = re.findall(r'"([^"]*)"', listed.group(1)) if listed else []
        assert paths, (
            f"{_SKILL_MD}: a worked task-add payload in step 4.7 "
            f'({payload.strip()[:80]!r}) carries an empty `"files": []`. '
            "The example is what the planner copies; an empty list teaches "
            "an empty list on every task."
        )
        for path in paths:
            # A repo-relative file: segments of word characters, dots and
            # dashes ending in an extension; not `.`, `..`, `*`, not
            # absolute.
            assert re.fullmatch(r"(?!/)[\w./-]+\.\w+", path), (
                f"{_SKILL_MD}: a worked task-add payload in step 4.7 lists "
                f"{path!r} under `files`, which is not a repo-relative file "
                "path (like `cli/policy.py`). `.`, `..`, `*` or an absolute "
                "path is a placeholder the gate cannot map to a module."
            )


def test_step_4_7_payload_files_agree_with_their_routing_claim() -> None:
    for payload in _worked_payloads():
        listed = re.search(r'"files": \[([^\]]*)\]', payload)
        paths = re.findall(r'"([^"]*)"', listed.group(1)) if listed else []
        # Each example's `files` has to agree with its own routing claim:
        # one path where it says qwen-eligible, two or more where it says
        # excluded for `files`.
        if '"qwen_eligible": true' in payload:
            assert len(paths) == 1, (
                f"{_SKILL_MD}: step 4.7's qwen-eligible payload lists "
                f"{len(paths)} paths under `files` ({paths!r}). Eligibility "
                "needs exactly one implementor-writable file, so the example "
                "contradicts the rule it illustrates."
            )
        if '"qwen_excluded_reason": "files"' in payload:
            assert len(paths) >= 2, (
                f"{_SKILL_MD}: step 4.7's `files`-excluded payload lists "
                f"{len(paths)} paths under `files` ({paths!r}). The prose "
                "calls it a two-file task; with fewer than two paths the "
                "exclusion reads as unexplained."
            )
