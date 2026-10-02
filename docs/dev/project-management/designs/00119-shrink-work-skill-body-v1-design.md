# Design: Shrink work/SKILL.md Under The 500-Line Ceiling

## Architecture fit

`skills/work/SKILL.md` is the always-loaded orchestrator body `/work` executes
every task against (currently 813 lines, measured at catchup — the PRD's 737
baseline is stale; PRD 00093's rework tail grew it further). It already has a
`references/` layer for situational content consulted conditionally
(`codex-implementor.md`, `attempt-logging.md`, `adversarial-test-prompt.md`,
etc.) with a "read at trigger point" pointer convention. This PRD extends that
same layer with one new file and enlarges an existing one; it does not
introduce a new architectural pattern.

The harder part of this PRD lives one layer down: `run-autopilot/scripts/
test_fablectl.py` contract-tests the fable-rescue-rung documentation by
scanning `work/SKILL.md`'s own text for specific section headings
(`### 5.5.`, `### 2.85.`) and pattern-matching sentences inside them. Moving
prose out from under those headings is a change to that test's addressing
layer, not just to SKILL.md.

## Module placement

**New file:** `skills/work/references/gate-failure.md` — the step-5.5
diagnose/repair/escalate machinery, verbatim.

**Edited (content moves within, no new file):**
`skills/work/references/adversarial-test-prompt.md` gains a `## Procedure`
section holding step 2.85's Devon narrative (receives/job/outcomes). The file
already exists (Tess/Devon prompt templates); this is an addition to it, not
a new file.

**Edited (prose removed, pointer added):** `skills/work/SKILL.md` — step 5.5
and step 2.85 shrink in place; every other section (routing table, state
sync, per-task loop, commit rules) is untouched per the PRD's Non-Goals.

**Edited (test addressing layer):**
`skills/run-autopilot/scripts/test_fablectl.py` — see Interfaces & contracts.
No test *behavior* changes; only how it locates the text it already checks.

## Interfaces & contracts

### What moves out of step 5.5 (lines 501-648 today) vs. what stays inline

**Stays inline in `SKILL.md`** (the heading plus what the PRD calls "the
legacy branch summary"):
- The `### 5.5.` heading itself, verbatim, unchanged.
- Lines 501-529 today: the "run only Tess's tests" scope note, the retry
  render-prompt snippet, the `_AUTOPILOT_ESCALATION == "legacy"` branch.
- A new one-line pointer immediately after the legacy branch:
  `**Any other value / absent — diagnose→repair/escalate flow (default):**
  see \`references/gate-failure.md\` for the full flow. Read it before the
  first gate failure of a batch.`

**Moves to `references/gate-failure.md`** (lines 530-648 today, verbatim,
no rewording — Non-Goals forbids "improving" the prose):
- The per-rung budget citation sentence.
- The codex attempt classification (three arms) + the no-edit detector
  paragraphs.
- The `\`\`\`` pseudocode block (gate fail #1/#2, DIAGNOSE, REPAIR, ESCALATE).
- Attribution row ownership table.
- Pipeline stamping, qwen capability breaker counter, deterministic
  precedence paragraphs.

`gate-failure.md`'s own top-of-file structure, to stay `_section()`-safe (see
below): a single `#` title line, one short intro sentence, then **one**
`### 5.5.` heading immediately followed by all the moved content. No `##` or
`###` sub-headings anywhere after that point — internal structure uses bold
paragraph lead-ins (`**Codex attempt classification — three arms.**` etc.),
exactly the style the moved prose already uses today. This mirrors
`codex-implementor.md`'s "extract + pointer" shape but *without* that file's
internal `##` sections, because this file must re-merge by heading string
match (below) and a competing `##`/`###` line would truncate the merge.

### What moves out of step 2.85 (lines 287-315 today) vs. what stays inline

**Stays inline:** the tier-gate table (lines 289-297, including the `fable`
row) — `check_devon_row` reads this table and nothing else; leaving it in
place means zero test-addressing changes are needed for 2.85 at all.

**Moves to `adversarial-test-prompt.md` § Procedure:** lines 299-311 today
("Devon runs as...", "Devon receives only...", "Devon's job:", the Outcomes
table). The SKILL.md pointer at (today's) line 313 — "See
`references/adversarial-test-prompt.md` for the full prompt template" —
becomes "See `references/adversarial-test-prompt.md` § Procedure for how
Devon runs, and the file's prompt template section for what it receives."

### `test_fablectl.py` changes

Every symbol referenced below is existing code in this file today
(`SKILLS_DIR`, `WORK_SKILL`, `TIER_TABLE_FILES`, `Doc`, `_section`,
`WorkSkillFableContractTest`, `WorkSkillExploitRejectionTest`,
`check_pinned_enumerations`) unless marked **NEW**.

1. **NEW constant**, placed beside `WORK_SKILL`:
   ```python
   GATE_FAILURE_REF = SKILLS_DIR / "work" / "references" / "gate-failure.md"
   ```

2. **`TIER_TABLE_FILES` gains a fourth entry:**
   ```python
   TIER_TABLE_FILES = (WORK_SKILL, STATE_SCHEMA, MODEL_LADDER, GATE_FAILURE_REF)
   ```
   `FableTierEnumerationTest` already loops this tuple generically
   (`check_line_enumerations`, `check_denials`, plus the per-file positive
   control asserting the file has ≥1 line naming all three Claude tiers).
   Adding the file here is the *entire* fix for those two checks' coverage
   of the moved content — no other code change. The positive control holds:
   the moved budget sentence ("Claude rungs (haiku/sonnet/opus) get 2
   dispatches... the `fable` rescue rung gets 1 capability dispatch...") is
   one line naming all four tiers.

3. **NEW helper**, placed after `Doc`:
   ```python
   def combined_doc(primary: Path, *extra: Path) -> Doc:
       """A Doc over `primary`'s text with `extra` files' text appended.

       Existing headings that repeat across files (e.g. `### 5.5.` restated
       verbatim at the top of an extracted reference file) are merged by
       `_section`, which does not stop scanning at the first following
       heading - it re-enters on a later match of the same heading text.
       Citations from `extra` content report `primary`'s path and a line
       number counted through the concatenation, not the physical file - a
       precision loss accepted because `_cite` output is diagnostic only;
       no check's PASS/FAIL verdict depends on it.
       """
       text = primary.read_text()
       for path in extra:
           text += "\n" + path.read_text()
       return Doc(primary, text=text)
   ```
   Uses `Doc`'s existing `text: str | None = None` constructor parameter -
   no change to `Doc` itself.

4. **`_section` change (one line):** replace the `break` that ends the
   section on the next `## `/`### ` line with `inside = False; continue`, so
   scanning resumes rather than stopping - the only behavior change is that
   the SAME heading text can now open the section a second time later in
   `self.lines` (only possible today via `combined_doc`, since a single real
   file never repeats a heading). Every single-file call site is unaffected
   byte-for-byte.

5. **Three call sites switch from `Doc(WORK_SKILL)` to
   `combined_doc(WORK_SKILL, GATE_FAILURE_REF)`:**
   - `FableTierEnumerationTest.test_pinned_sections_name_fable_even_when_rewrapped`
     (today's `check_pinned_enumerations(Doc(WORK_SKILL))`).
   - `WorkSkillFableContractTest.setUp`'s `self.doc = Doc(WORK_SKILL)`.
   - `WorkSkillExploitRejectionTest`'s baseline test
     (`test_the_unmodified_real_file_passes_every_check`), via its `setUp`
     change below.

6. **`WorkSkillExploitRejectionTest` generalizes from one mutable copy to
   two.** Contract (replaces `setUp`/`patch`/`write`/`exploited`):
   ```python
   def setUp(self) -> None:
       self.tmp = tempfile.TemporaryDirectory()
       self.skill_copy = Path(self.tmp.name) / "SKILL.md"
       self.gate_copy = Path(self.tmp.name) / "gate-failure.md"
       shutil.copyfile(WORK_SKILL, self.skill_copy)
       shutil.copyfile(GATE_FAILURE_REF, self.gate_copy)

   def patch(self, skill_text: str, gate_text: str, patches: tuple) -> tuple[str, str]:
       for old, new in patches:
           if old in skill_text:
               skill_text = skill_text.replace(old, new, 1)
           elif old in gate_text:
               gate_text = gate_text.replace(old, new, 1)
           else:
               self.fail(
                   f"fixture drift: neither {WORK_SKILL} nor {GATE_FAILURE_REF} "
                   f"contains {old[:70]!r} - re-anchor it"
               )
       return skill_text, gate_text

   def write(self, skill_text: str, gate_text: str) -> Doc:
       self.skill_copy.write_text(skill_text)
       self.gate_copy.write_text(gate_text)
       return combined_doc(self.skill_copy, self.gate_copy)

   def exploited(self, *patches: tuple) -> Doc:
       skill_text, gate_text = self.patch(
           self.skill_copy.read_text(), self.gate_copy.read_text(), patches
       )
       return self.write(skill_text, gate_text)
   ```
   Every fixture call site (`self.exploited(...)`) is unchanged - the file
   each patch lands in is resolved automatically by which copy currently
   contains the `old` substring, so the ~10 fixture bodies need no edits
   beyond whatever text drift Phase 0's anchor inventory finds from the
   verbatim relocation itself (line-number shifts don't matter; substring
   matching does). Fixtures anchored to content that stays in SKILL.md
   (accepted-values line, pipeline-mapping step-6 exploits, routing-override
   comment exploit, Devon-row exploit, review-row exploit) resolve in the
   `skill_text` branch exactly as today. Fixtures anchored to moved content
   (per-rung budget, auto-escalation chain, no-rung-above, the three
   retry/repair exclusions, the anti-vacuity re-wording test) resolve in the
   `gate_text` branch.

No other function in `test_fablectl.py` changes. `check_budget`,
`check_no_auto_escalation`, `check_no_rung_above`,
`check_retry_repair_excludes_fable`, `check_devon_row`, `check_review_row`,
`ESCALATION_SECTION`, `PINNED_SECTIONS`, `EXEMPTIONS` are all untouched - they
operate on whatever `Doc`/`Flow` hand them, and the redirection is entirely
inside the addressing layer.

## Data flow

Today: `/work` reads `SKILL.md` top to bottom every task; step 5.5 and step
2.85 are read inline. After this change: `/work` reads the same SKILL.md,
hits the step-5.5 pointer only on a gate failure (the situational case) and
the step-2.85 table inline as before; on a gate failure it reads
`gate-failure.md` before proceeding, mirroring how the codex rung already
reads `codex-implementor.md` before its first probe/dispatch.

For the test suite: `combined_doc()` builds one `Doc` whose `.lines` is
SKILL.md's lines followed by `gate-failure.md`'s lines. `Doc.flow("### 5.5.")`
walks those lines once, collecting every span that starts at a `### 5.5.`
heading and ends at the next `##`/`### ` heading (now possibly re-entering a
second time, per the `_section` change) - so `check_budget` etc. see the
legacy-branch summary and the diagnose/repair/escalate flow as one joined
string, exactly as they saw one contiguous section before the move.

## Reuse inventory

- **`Doc.__init__`'s existing `text: str | None = None` parameter**
  (`test_fablectl.py:776-779`) - already exists to let
  `WorkSkillExploitRejectionTest` build a `Doc` from mutated text without
  touching disk twice; `combined_doc()` reuses it rather than adding a new
  Doc-construction path. Greps run: `def combined|multi.?file|concat.*text`
  across `test_fablectl.py` and `run-autopilot/cli/*.py` - nothing found, so
  this genuinely does not exist yet.
- **`codex-implementor.md`** (`skills/work/references/codex-implementor.md`)
  - the "extract situational mechanics verbatim, leave a read-before-acting
    pointer" pattern this PRD's Feature 1 mirrors exactly (PRD's own words).
    Its internal `##`-sectioned structure is explicitly *not* copied for
    `gate-failure.md`, because that file must re-merge by heading string
    match (see Interfaces & contracts) and competing headings would break
    that.
- **`references/adversarial-test-prompt.md`** (existing file, confirmed on
  disk at catchup) - Devon's extraction target per the PRD; this PRD adds a
  `## Procedure` section to it rather than creating a new file.
- **`FableTierEnumerationTest`'s `TIER_TABLE_FILES` loop** - already generic
  over "any tier-table file"; registering `GATE_FAILURE_REF` there reuses it
  for two of the four affected checks (`check_line_enumerations`,
  `check_denials`) with zero new code.

## Alternatives considered

1. **Per-row `Flow`/`Hit` path tracking** (each row carries its own source
   path, not just the Doc's single outer path). Highest citation fidelity -
   every failure message names the exact physical file and real line number.
   Rejected as the primary approach: it touches `Flow.__init__`, `Hit`,
   `_cite`'s call sites across every `check_*` function (not just the four
   ESCALATION_SECTION-anchored ones), a much larger diff for a benefit
   (nicer failure messages) the PRD's Success Metrics don't ask for -
   rejection power is the bar, not citation precision. Noted as a follow-up
   if a real debugging session is ever slowed by an imprecise citation.

2. **Smallest-diff version: leave step 5.5 and 2.85 untouched, extract a
   *different* ~120-line block instead** (e.g., trim the Subagent Dispatch
   Budget section or the Assumptions footer). Rejected: the PRD's own
   Problem Statement already ruled this out - those are "read-every-run"
   sections excluded by Non-Goals, and only step 5.5 (gate-failure-only) and
   step 2.85 (opus/fable-tier-only, table-preserved) are genuinely
   situational enough to extract without degrading the common path.

3. **Chosen: `combined_doc()` + one-line `_section` change.** Smallest diff
   that keeps every existing check function, every existing regex constant,
   and every existing fixture's patch call unchanged. The extra size over
   alternative 1 buys nothing; the extra size over "don't touch the test at
   all" (impossible - Doc only reads one file today) buys the PRD's stated
   requirement that all ~25 assertions keep their rejection power.

## Risks & edge cases

- **Silent anchor loss during the verbatim move.** A copy-paste that drops a
  line, or that reformats a line-wrap, could shift a regex anchor (e.g.
  `FEEDBACK_RETRY_ANCHOR`'s exact phrase) without any test noticing until the
  *exploit* fixture fails to find its `old` substring - which does fail loud
  (`self.fail("fixture drift...")`), not silently. Mitigated by: doing the
  move as a literal cut-paste of the exact line ranges identified above, and
  running the full suite (not just the moved tests) immediately after.
- **`gate-failure.md` growing its own `##`/`###` heading later** (a future
  editor reorganizing it for readability) would silently truncate the
  `_section("### 5.5.")` merge - the section would stop at the new heading,
  and everything after it would vanish from every check's view with no
  test failure (the checks would just see less text, and most would still
  pass since the surviving text may still be fable-safe). This is the design's
  main latent footgun. Mitigated by the module-placement note above (no
  sub-headings after the top `### 5.5.` marker) - worth a one-line HTML
  comment at the top of the new file itself pointing back at this
  constraint, since that survives independently of this design doc's
  lifetime.
- **Citation imprecision** (see `combined_doc` docstring) - accepted, not
  mitigated; a human debugging a `test_fablectl.py` failure that cites a
  `gate-failure.md`-sourced line will see a `SKILL.md` path and a line number
  that doesn't correspond to either physical file's own numbering. The
  `problems` message text itself (not just the citation) still names the
  actual offending phrase, so this slows diagnosis, it doesn't block it.
- **Likely next changes after this PRD** (per the PRD's own framing and the
  cap-findings record for PRD 00093): (1) a follow-up may need to extract
  step 5.7's per-task review section too if SKILL.md grows again - the
  `combined_doc`/`_section` mechanism generalizes to a third file with no
  further changes; (2) `TIER_TABLE_FILES` becoming a longer list as more
  situational content moves out - already future-proofed by being a plain
  tuple; (3) the ~500-line ceiling itself may need revisiting if the
  remaining read-every-run sections alone approach it - out of scope here,
  flagged only.

## Test strategy outline

Per the PRD: the contract suites ARE the test strategy. Concretely, in this
order:

1. Phase 0 (anchor inventory) produces a checked-in table (test name → exact
   anchor substring → post-move file) covering every `WORK_SKILL_CHECKS`
   entry and every `WorkSkillExploitRejectionTest` fixture that touches
   step-5.5/2.85 content - built by re-reading the current line ranges named
   in Interfaces & contracts above and grepping each candidate substring
   against both post-move files once drafted.
2. After each extraction (gate-failure.md, then the Devon procedure), run
   `python3 run-autopilot/scripts/test_fablectl.py` in full before touching
   anything else - a break surfaces immediately, scoped to the single move
   just made.
3. Deliberately mutate the *moved* copy of a fable-critical phrase (e.g.
   delete "no rung above" from `gate-failure.md`) and confirm
   `WorkSkillFableContractTest`/the exploit fixture rejects it - proves
   rejection power survived the move, not just that the suite is green
   (green alone doesn't distinguish "still checking" from "checking
   nothing").
4. Run `test_work_routing.py`, `test_work_routing_ladder_fence.py`,
   `test_golden_contracts.py` - expected unaffected (they test
   `work_routing.py`'s hand-maintained model, not SKILL.md's prose), run to
   confirm rather than assumed.
5. `create-skill` validator against `skills/work/SKILL.md` for the line-count
   WARN.
6. One live work-phase smoke on a toy PRD (PRD's own Risks section) -
   confirms both pointers (step 5.5's, step 2.85's) actually get read at
   their trigger points, not just that the text exists on disk.

## Review log

**Dispatch 1 (claude):** verified the step-5.5/2.85 split, the `combined_doc`
+ `_section` mechanism (traced by hand against `check_budget`,
`check_no_auto_escalation`, `check_no_rung_above`,
`check_retry_repair_excludes_fable`), and all ~10 exploit fixtures against
the real file content. No cardinal sins or blockers.

- **[non-blocking]** The "three call sites" contract (Interfaces & contracts
  item 5/6) doesn't show `WorkSkillExploitRejectionTest.
  test_the_unmodified_real_file_passes_every_check`'s body changing from
  `Doc(self.copy)` to `combined_doc(self.skill_copy, self.gate_copy)` -
  implied by the `setUp` rename but not spelled out; an implementor copying
  only the shown contract hits an `AttributeError` there (fails loud, not
  silent, but worth stating explicitly). Planning/implementation should
  include this line.
- **[question]** The one-line `_section` change (`break` → `inside = False;
  continue`) is behaviorally identical on a single real file only if no
  pinned heading string (`### 3.`, `### 5.5.`, etc.) repeats verbatim later
  in the same file. Not verified against `WORK_SKILL`/`STATE_SCHEMA`/
  `MODEL_LADDER` as they exist today. Cheap to confirm with one grep per
  file during Phase 0 (anchor inventory).
- **[question]** Today's step-2.85 pointer sentence "Devon prompts must
  satisfy the Subagent Dispatch Budget" has no stated disposition (keep /
  drop / fold in) in the design's replacement pointer text. No test anchors
  it, so not a correctness risk - just underspecified.

dispatch 1 (claude): cardinal-sin 0, blocker 0, non-blocker 1, question 2
