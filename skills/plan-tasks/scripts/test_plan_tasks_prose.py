"""Prose pins for the tier-classification rewrite (PRD 00160).

Same pattern as the other prose suites in this repo: read each markdown file
once at module level, slice the step under test by its `### ` heading, and
assert on short, reword-resistant fragments, each with a failure message
naming what drifted and where to look.

Nothing executes steps 4.6 and 4.7 but a reader, so the prose IS the
mechanism. The rewrite moves tier classification off a keyword/size rules
table onto `classify_tier.py`, and the only thing stopping a planner from
re-deriving that table out of PRD-wide prose is the evidence rules' exclusion
clauses. Those are pinned as single clauses - a bounded gap that cannot cross
a sentence break - rather than as loose substrings that still pass once the
pieces drift into separate paragraphs.

A string that is merely present is not a rule the step instructs, so the rule
pins read a MASKED view of SKILL.md in which fenced code and blockquote lines
are blanked out (a rule quoted into a blockquote and disowned is not a rule),
and step 4.7 must carry no text that disowns what it states - no "rejected
draft" to ignore, no script named only to forbid running it. Retired triggers
are pinned by meaning as well as by spelling: a size promotion respelled as
"more than eight files" is the same retired rule.

This file pins PROSE only. `test_classify_tier.py` covers the classifier.
"""

from __future__ import annotations

import re
from pathlib import Path

_PLAN_TASKS = Path(__file__).resolve().parent.parent
_SKILL_MD = _PLAN_TASKS / "SKILL.md"
_SKILL_TEXT = _SKILL_MD.read_text()
_RATIONALE_MD = _PLAN_TASKS / "references" / "design-rationale.md"
_RATIONALE_TEXT = _RATIONALE_MD.read_text()

_STEP_4_6_HEADING = "### 4.6. Split tasks (context + eligibility)"
_STEP_4_7_HEADING = "### 4.7. Assign per-task model tier"
_STEP_5_HEADING = "### 5. Set dependencies"


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

_STEP_4_6_START = _locate(_STEP_4_6_HEADING)
_STEP_4_6_END = _locate("### 4.7.", _STEP_4_6_START)
_STEP_4_6 = _SKILL_TEXT[_STEP_4_6_START:_STEP_4_6_END]
_STEP_4_6_PROSE = _MASKED_TEXT[_STEP_4_6_START:_STEP_4_6_END]

_STEP_4_7_START = _locate(_STEP_4_7_HEADING)
_STEP_4_7_END = _locate(_STEP_5_HEADING, _STEP_4_7_START)
_STEP_4_7 = _SKILL_TEXT[_STEP_4_7_START:_STEP_4_7_END]
_STEP_4_7_PROSE = _MASKED_TEXT[_STEP_4_7_START:_STEP_4_7_END]

# A gap class that excludes `.` cannot straddle a sentence break, so a clause
# pin fails the moment its halves drift into separate sentences.
_GAP = 240


def _clause_pattern(*needles: str) -> re.Pattern[str]:
    joiner = f"[^.]{{0,{_GAP}}}?"
    return re.compile(joiner.join(re.escape(n) for n in needles), re.IGNORECASE)


def _clause(text: str, *needles: str) -> re.Match[str] | None:
    return _clause_pattern(*needles).search(text)


def _near(text: str, first: str, second: str, gap: int = 160) -> bool:
    """Do two regex fragments meet inside one sentence, in either order?"""
    joiner = f"[^.]{{0,{gap}}}?"
    return any(
        re.search(joiner.join(pair), text, re.IGNORECASE)
        for pair in ((first, second), (second, first))
    )


# Shared by the algorithmic_risk exclusion pin and the `refactor across`
# containment pin: the retired Rule 1 keywords may only appear as words that
# do NOT qualify a task, listed in one sentence.
_RETIRED_KEYWORDS = _clause_pattern(
    "design",
    "architect",
    "introduce",
    "refactor across",
    "estimated_tokens",
)

_SCRIPT = r"(?:classif\w*|script)"
_RUNS = r"(?:run|runs|running|invoke|invokes|invoked|call|calls|called|execute|executes|shell\w* out)"
_REFUSES = (
    r"(?:never|do not|don't|does not|must not)\s+(?:run|call|invoke|execute|shell out)"
)

# Text that quotes a rule only to disown it. Prose that means what it says
# never needs any of these, and each one turns a pinned rule into scenery.
_DISCLAIMERS = (
    "do not follow",
    "rejected draft",
    "kept as a curiosity",
    r"means? (?:nothing|anything) here",
    "wrong for this skill",
    r"classif\w* by eye",
    "ignore any claim",
)


def test_step_4_7_classifies_through_classify_tier_py() -> None:
    # The whole point of the rewrite: the tier comes from a script, not from
    # a table the planner reads. Naming the script is not enough - a caller
    # who cannot see the flags cannot feed it, so pin the full argument
    # surface. Scoped to step 4.7 so a mention elsewhere cannot satisfy it.
    assert "classify_tier.py" in _STEP_4_7, (
        f"{_SKILL_MD}: step 4.7 never names classify_tier.py, so the tier is "
        "still decided by whatever the planner reads in this step instead of "
        "by the classifier PRD 00160 introduced."
    )
    for flag in (
        "--files-file",
        "--text-file",
        "--lines",
        "--contract-edit",
        "--algorithmic-risk",
        "--default-model",
    ):
        assert flag in _STEP_4_7, (
            f"{_SKILL_MD}: step 4.7 never names the {flag!r} flag of "
            "classify_tier.py. A planner shelling out from this prose omits "
            "it, and the classifier decides on an input it was never handed."
        )
    # Naming a script and telling the reader to run it are different acts. A
    # step that lists the flags for recognition only leaves classification
    # exactly where PRD 00160 took it from: the planner's eye.
    assert _near(_STEP_4_7_PROSE, _RUNS, _SCRIPT), (
        f"{_SKILL_MD}: step 4.7 never tells the planner to RUN the "
        "classifier - no sentence puts a run/invoke/shell-out verb next to "
        "the script. Listed flags alone document a file; they do not move "
        "the decision off the planner."
    )
    assert not _near(_STEP_4_7_PROSE, _REFUSES, _SCRIPT), (
        f"{_SKILL_MD}: step 4.7 tells the reader NOT to run the classifier. "
        "One sentence forbidding the script undoes every other mention of "
        "it, and the tier goes back to being judged by hand."
    )


def test_step_4_7_persists_tier_reason_alongside_model() -> None:
    # `tier_reason` anywhere in the file proves nothing - it has to land in
    # the task payload next to `model`, or `work` and the Phase 9 mix render
    # have no per-task record of WHY a tier was chosen. The payload has to be
    # a worked example (a fenced block), not a `{...}` quoted in a sentence
    # that then tells the reader to skip the key.
    blocks = re.findall(r"```[^\n]*\n(.*?)```", _STEP_4_7, re.DOTALL)
    payloads = [
        payload for block in blocks for payload in re.findall(r"\{[^{}]*\}", block)
    ]
    assert any(
        '"tier_reason"' in payload and '"model"' in payload for payload in payloads
    ), (
        f"{_SKILL_MD}: no worked task-add payload in step 4.7 carries "
        '"tier_reason" as a top-level key beside "model". Without it the '
        "reason is computed and dropped, and every plan reads as if the tier "
        "were unexplained."
    )
    assert _near(
        _STEP_4_7_PROSE,
        r"(?:persist|record|store|write)\w*",
        "tier_reason",
    ), (
        f"{_SKILL_MD}: step 4.7 never instructs the planner to persist "
        "`tier_reason` - the key shows up in an example but no sentence says "
        "to write it. An example nobody is told to follow is decoration."
    )


def test_step_4_7_states_the_seven_legal_tier_reason_values() -> None:
    # A reason the classifier can emit but the prose never lists is a value
    # no reader can validate. Backticked so `contract` cannot be satisfied by
    # the word "contract" in the qwen paragraphs, nor `default` by
    # `default_model`.
    for value in (
        "test_port",
        "packaging",
        "contract",
        "algorithmic_risk",
        "mechanical",
        "default",
        "floor",
    ):
        assert f"`{value}`" in _STEP_4_7_PROSE, (
            f"{_SKILL_MD}: step 4.7 never states `{value}` as a legal "
            "tier_reason value. The seven values are the contract between "
            "the classifier and every reader of a plan; an unlisted one "
            "reads as corrupt state."
        )
    # Seven words in a row are a word list. They become a contract only when
    # the step introduces them as the values the key may take, so look for
    # that framing right where the list is - not anywhere in the step.
    listing_at = _STEP_4_7_PROSE.index("`test_port`")  # the loop pinned it
    around = _STEP_4_7_PROSE[max(0, listing_at - 240) : listing_at + 120]
    assert re.search(
        r"\b(?:legal|valid|allowed|permitted|possible|one of|exactly|must be)\b",
        around,
        re.IGNORECASE,
    ), (
        f"{_SKILL_MD}: step 4.7 lists the tier_reason words without saying "
        f"they ARE the values the key may take ({around.strip()[:90]!r}). "
        "Introduced as trivia, or as words a reader may safely ignore, a plan "
        "carrying one of them tells the reader nothing."
    )


def test_step_4_7_binds_contract_edit_to_the_task_s_own_edits() -> None:
    # `contract_edit` is a fact the planner asserts, so its bound is the
    # whole rule. Unbounded, "this task is near a contract" becomes
    # "contract_edit: true" and every task escalates.
    assert _clause(_STEP_4_7_PROSE, "contract_edit", "task itself") or _clause(
        _STEP_4_7_PROSE,
        "task itself",
        "contract_edit",
    ), (
        f"{_SKILL_MD}: step 4.7's evidence rules never tie `contract_edit` to "
        "the task ITSELF changing a contract, in one sentence of live prose. "
        "Write it as '`contract_edit` is true only when the task itself "
        "changes ...' - split across sentences, or quoted into a blockquote, "
        "the bound stops binding."
    )
    assert _clause(
        _STEP_4_7_PROSE,
        "contract_edit",
        "exported API signature",
        "wire format",
        "hook registration",
    ), (
        f"{_SKILL_MD}: step 4.7 never names what `contract_edit` covers "
        "(an exported API signature, a persisted schema, a wire format, a "
        "hook registration shape) in the same sentence as the fact. The list "
        "exists elsewhere in this step for qwen routing; the evidence rule "
        "needs its own."
    )
    assert re.search(
        r"calling or documenting[^.]{0,120}?(?:does not|do not) count",
        _STEP_4_7_PROSE,
        re.IGNORECASE,
    ), (
        f"{_SKILL_MD}: step 4.7's evidence rules no longer say that calling "
        "or documenting a contract does not count as `contract_edit`. That "
        "clause is what keeps a task that merely imports an API off the "
        "contract tier - drop it and nearly every task edits a contract."
    )


def test_step_4_7_binds_algorithmic_risk_to_the_task_s_own_details() -> None:
    # The three qualifying shapes, in one sentence with the fact and the
    # task's own Details. "Implements, not calls" is the discriminator: a
    # task that calls a hashing library is not an algorithm task.
    assert _clause(
        _STEP_4_7_PROSE,
        "algorithmic_risk",
        "Details",
        "new algorithm",
        "shared mutable state",
        "migration",
    ), (
        f"{_SKILL_MD}: step 4.7's evidence rules never bind `algorithmic_risk` "
        "to the task's OWN Details naming a new algorithm, shared mutable "
        "state, or a transform of persisted data (a migration) - all in one "
        "sentence of live prose. Stated apart, or quoted into a blockquote, "
        "the three shapes stop reading as the closed list they are."
    )
    assert re.search(
        r"new algorithm[^.]{0,60}implement[^.]{0,60}call",
        _STEP_4_7_PROSE,
        re.IGNORECASE,
    ), (
        f"{_SKILL_MD}: step 4.7 no longer distinguishes an algorithm the task "
        "IMPLEMENTS from one it CALLS. Without that half-sentence, every "
        "task touching a sort, a hash, or a scheduler asserts "
        "algorithmic_risk."
    )


def test_step_4_7_excludes_prd_wide_prose_from_algorithmic_risk() -> None:
    # This is the defence against the planner re-deriving the retired
    # keyword scan out of PRD prose. Both halves live in one sentence each:
    # where the words may NOT come from, and which words never qualify.
    assert _clause(
        _STEP_4_7_PROSE,
        "PRD body",
        "title",
        "task name",
        "never qualif",
    ), (
        f"{_SKILL_MD}: step 4.7's evidence rules never say that words in the "
        "PRD body, the PRD title, or the task name alone never qualify as "
        "`algorithmic_risk` evidence. Without it the planner scans the PRD "
        "and every task in a PRD about concurrency claims the fact - the "
        "retired Rule 1 keyword scan, rebuilt by hand."
    )
    assert _RETIRED_KEYWORDS.search(_STEP_4_7_PROSE), (
        f"{_SKILL_MD}: step 4.7 no longer lists `design`, `architect`, "
        "`introduce`, `refactor across`, file count, and `estimated_tokens` "
        "together in ONE sentence of live prose as words and measures that "
        "do NOT qualify. Listed apart, quoted into a blockquote, or dropped, "
        "the retired Rule 1 triggers come back as planner judgement."
    )
    # A rule the step disowns is not a rule. These phrases only ever appear
    # to tell a reader that the surrounding text does not apply, which is how
    # every clause above survives verbatim while meaning nothing.
    for disclaimer in _DISCLAIMERS:
        assert not re.search(disclaimer, _STEP_4_7, re.IGNORECASE), (
            f"{_SKILL_MD}: step 4.7 contains {disclaimer!r}, so some rule in "
            "the step is stated and then disowned. Evidence rules a reader "
            "is told to ignore leave the fact assertions unbounded."
        )


def test_step_4_7_marks_the_contract_exclusion_unreachable_on_new_plans() -> None:
    # The reason code survives for legacy plans, so a reader who is not told
    # it is unreachable will keep looking for it in fresh batches and read
    # its absence as a bug in the mix render.
    assert _clause(
        _STEP_4_7_PROSE,
        "qwen_excluded_reason",
        "contract",
        "unreachable",
    ), (
        f"{_SKILL_MD}: step 4.7 never says that `qwen_excluded_reason: "
        "contract` is now unreachable on new plans. The classifier decides "
        "the contract case upstream, so leaving that reason documented as "
        "live makes an empty count look like an under-count."
    )


def test_step_4_7_keeps_its_keepers_when_the_rules_table_retires() -> None:
    # The rewrite deletes the classification table. The three mechanisms
    # around it are NOT part of that deletion, and a rewrite that takes them
    # with it silently drops the kill-switch, the PRD floor, and qwen
    # routing.
    assert "| Rule | Tier | Trigger |" not in _STEP_4_7, (
        f"{_SKILL_MD}: step 4.7 still carries the Rule/Tier/Trigger table. "
        "PRD 00160 retired keyword-and-size classification; while the table "
        "stands, the planner has two classifiers and picks whichever it "
        "reads first."
    )
    # Renaming the header keeps the mechanism, so pin the row shape too: no
    # table row may hand a tier to a task on the strength of words scanned
    # out of the PRD or the task title.
    keyword_scan = re.compile(
        r"\bdesign(?!-)|architect|novel algorithm|refactor across|PRD body|"
        r"task text contains|contains any of",
        re.IGNORECASE,
    )
    tier_name = re.compile(r"\b(?:opus|sonnet|haiku)\b", re.IGNORECASE)
    for line in _STEP_4_7.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        assert not (tier_name.search(line) and keyword_scan.search(line)), (
            f"{_SKILL_MD}: step 4.7 has a table row assigning a tier from "
            f"scanned words ({line.strip()[:80]!r}). That is the retired "
            "rules table under a new header - the classifier decides tiers "
            "now, and keyword rows give the planner a second answer."
        )
    for keeper, why in (
        (
            "_PLAN_TASKS_FLOOR",
            "the kill-switch the next widening attempt needs is gone",
        ),
        ("default_model", "the PRD frontmatter floor is gone"),
        ("final_tier", "the floor's max() composition is gone"),
        ("qwen_eligible", "work has no routing flag to read"),
    ):
        assert keeper in _STEP_4_7, (
            f"{_SKILL_MD}: step 4.7 no longer mentions `{keeper}` - {why}. "
            "The rewrite retires the rules table only; these mechanisms "
            "survive it."
        )


def test_step_4_6_exempts_risky_tasks_instead_of_opus_signals() -> None:
    # Step 4.6's eligibility split is skipped on risk now. The old exemption
    # pointed at Rule 1's signal list; with that list retired, a surviving
    # pointer aims at nothing and the exemption silently never fires.
    assert not re.search(r"opus[- ]signal", _STEP_4_6, re.IGNORECASE), (
        f"{_SKILL_MD}: step 4.6 still carries the opus-signal exemption. Its "
        "signal list no longer exists in step 4.7, so the exemption is a "
        "scan against nothing and every risky task gets split for "
        "eligibility."
    )
    assert "signal list" not in _STEP_4_6, (
        f"{_SKILL_MD}: step 4.6 still refers to a shared `signal list` with "
        "step 4.7. There is no such list after PRD 00160 - the exemption "
        "reads the two per-task facts instead."
    )
    for fact in ("contract_edit", "algorithmic_risk"):
        assert fact in _STEP_4_6, (
            f"{_SKILL_MD}: step 4.6 never names `{fact}` as a fact that "
            "exempts a task from the eligibility split. A task carrying it "
            "gets split into qwen-sized pieces, which is exactly the work "
            "the exemption exists to keep whole."
        )
    exemption = re.search(
        r"[^.]{0,300}not split for eligibility[^.]{0,300}",
        _STEP_4_6_PROSE,
        re.IGNORECASE,
    )
    assert exemption, (
        f"{_SKILL_MD}: step 4.6 no longer states the exemption's effect "
        "('not split for eligibility') in live prose, so nothing says what "
        "carrying a risk fact actually does to the task."
    )
    # The exemption is a RELATION, and the wrong direction reads almost the
    # same: "a task carrying neither fact is not split" exempts everything,
    # since the facts are absent by default. Pin the direction: the sentence
    # that states the effect has to hang it on a fact being present.
    clause = exemption.group(0)
    assert re.search(
        r"contract_edit|algorithmic_risk|\bfact|\brisk",
        clause,
        re.IGNORECASE,
    ), (
        f"{_SKILL_MD}: step 4.6's exemption sentence ({clause.strip()[:90]!r}) "
        "never says which fact triggers it. Named a paragraph away, the "
        "effect reads as unconditional and every task skips the split."
    )
    assert re.search(
        r"\b(?:either|both|carries|carrying|carry|with|true|any of|one of)\b",
        clause,
        re.IGNORECASE,
    ), (
        f"{_SKILL_MD}: step 4.6's exemption sentence "
        f"({clause.strip()[:90]!r}) never states that the fact is PRESENT. "
        "The exemption fires on a risk fact being true; without that, the "
        "condition is anyone's guess."
    )
    assert not re.search(
        r"\b(?:neither|nor|without|absent|lacks|false|unless)\b",
        clause,
        re.IGNORECASE,
    ), (
        f"{_SKILL_MD}: step 4.6's exemption sentence "
        f"({clause.strip()[:90]!r}) is stated in the negative, which inverts "
        "it: tasks carry neither fact by default, so an exemption keyed on "
        "their ABSENCE skips the eligibility split for every task and qwen "
        "gets nothing."
    )
    assert "estimated_tokens > THRESHOLD" in _STEP_4_6, (
        f"{_SKILL_MD}: step 4.6's context-budget trigger lost its "
        "`estimated_tokens > THRESHOLD` condition. PRD 00160 changes the "
        "eligibility exemption only; the budget trigger is unchanged, and "
        "without it oversized tasks stop being split at all."
    )


def test_skill_md_drops_the_retired_automatic_opus_promotions() -> None:
    # File-wide, not step-scoped: these two clauses promoted on size alone
    # and are exactly what the classifier replaces. Left anywhere in the
    # skill, a planner can still apply them by hand.
    for retired in ("files_touched > 8", "estimated_tokens > 120000"):
        assert retired not in _SKILL_TEXT, (
            f"{_SKILL_MD}: the retired automatic promotion `{retired}` is "
            "still in the file. PRD 00160 removed size-only escalation; "
            "while the clause survives anywhere, a wide-but-mechanical task "
            "still reads as opus work."
        )
    # Same rule, respelled, is the same rule: pin the shape, not the two
    # spellings. `files_touched >= 4` and `estimated_tokens > THRESHOLD` are
    # deliberately untouched - those are qwen eligibility and the context
    # budget, not tier promotions.
    for pattern, description in (
        (r"files_touched\s*>\s*\d", "a `files_touched > N` promotion"),
        (
            r"more than\s+(?:\d+|two|three|four|five|six|seven|eight|nine|ten)\s+files",
            "a 'more than N files' promotion",
        ),
        (r"estimated_tokens\s*[>≥]\s*\d", "an `estimated_tokens > N` promotion"),
        (r"over\s+\d+\s*[Kk]?\s*tokens", "an 'over N tokens' promotion"),
    ):
        found = re.search(pattern, _SKILL_TEXT, re.IGNORECASE)
        assert not found, (
            f"{_SKILL_MD}: {description} is back, spelled "
            f"{found.group(0)!r}. PRD 00160 retired escalation on size "
            "alone; rewording the threshold does not retire it, it hides it."
        )


def test_refactor_across_survives_only_as_a_non_qualifying_word() -> None:
    # The phrase must stay - it is named as a word that does NOT qualify -
    # but only there. Any occurrence outside that clause is the old trigger
    # wearing the new prose.
    exclusion = _RETIRED_KEYWORDS.search(_STEP_4_7_PROSE)
    assert exclusion, (
        f"{_SKILL_MD}: step 4.7 has no single sentence of live prose listing "
        "`design`, `architect`, `introduce`, `refactor across` and "
        "`estimated_tokens` as non-qualifying, so there is no clause for a "
        "surviving `refactor across` to sit in."
    )

    occurrences = [
        match.start()
        for match in re.finditer("refactor across", _SKILL_TEXT, re.IGNORECASE)
    ]
    assert occurrences, (
        f"{_SKILL_MD}: `refactor across` is gone from the file. It must "
        "survive inside step 4.7's evidence rules as an excluded word, or "
        "nothing tells the planner that the phrase alone is not evidence."
    )

    for position in occurrences:
        line_start = _SKILL_TEXT.rfind("\n", 0, position) + 1
        line_end = _SKILL_TEXT.find("\n", position)
        line = _SKILL_TEXT[line_start : line_end if line_end != -1 else None]
        assert not line.lstrip().startswith("|"), (
            f"{_SKILL_MD}: `refactor across` appears in a table row "
            f"({line.strip()[:80]!r}). A rules table is a trigger list, and "
            "the phrase is retired as a trigger."
        )
        relative = position - _STEP_4_7_START
        assert 0 <= relative < len(_STEP_4_7), (
            f"{_SKILL_MD}: `refactor across` appears outside step 4.7 "
            f"(offset {position}; step 4.6 and the rules table are the usual "
            "places). Its only sanctioned home is step 4.7's exclusion "
            "clause."
        )
        assert exclusion.start() <= relative < exclusion.end(), (
            f"{_SKILL_MD}: `refactor across` appears in step 4.7 outside the "
            f"sentence that lists it as non-qualifying (offset {position}), "
            "or inside a blockquote or code fence. Anywhere else in the step "
            "it reads as a live tier trigger again."
        )


def test_design_rationale_records_why_the_rule_1_triggers_retired() -> None:
    # SKILL.md holds the rule, this file holds the incident. Without the
    # section, the next planner sees keywords vanish with no argument
    # against putting them back.
    heading = "## Rule 1 keyword triggers retired (PRD 00160)"
    assert heading in _RATIONALE_TEXT, (
        f"{_RATIONALE_MD}: no {heading!r} section. The WHY for retiring the "
        "keyword and size triggers lives here by convention; with it "
        "missing, the removal reads as an unexplained deletion and the next "
        "widening attempt repeats it."
    )
    body_start = _RATIONALE_TEXT.index(heading) + len(heading)
    next_heading = _RATIONALE_TEXT.find("\n## ", body_start)
    body = _RATIONALE_TEXT[
        body_start : next_heading if next_heading != -1 else None
    ].strip()
    assert len(body) >= 300, (
        f"{_RATIONALE_MD}: the Rule 1 retirement section is {len(body)} "
        "characters long. A heading with no argument under it records "
        "nothing - the next widening attempt reads it and learns why "
        "nothing, which is how the keyword scan comes back."
    )
    named = [
        trigger
        for trigger in (
            "design",
            "architect",
            "introduce",
            "novel algorithm",
            "concurrency",
            "refactor across",
            "files_touched",
            "estimated_tokens",
            "keyword",
        )
        if trigger in body.lower()
    ]
    assert len(named) >= 2, (
        f"{_RATIONALE_MD}: the Rule 1 retirement section never names the "
        f"triggers it retired (found {named}). An incident story that does "
        "not say which triggers misfired cannot stop the next attempt from "
        "reintroducing them."
    )
