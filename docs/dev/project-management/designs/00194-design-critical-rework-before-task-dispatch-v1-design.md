# Design: 00194-design-critical-rework-before-task-dispatch-v1

PRD: `dev/local/prds/wip/00194-design-critical-rework-before-task-dispatch-v1.md`

## Architecture fit

This is a prose-contract change to the skill pack, not a runtime change. The
pack's lifecycle is catchup → design → plan-tasks → work → review-rework loop
→ done (capsule § Architecture Decisions). Today the build gate runs
`/autopilot:design-solution` once (Phase 1.5, `references/phase-build.md`) and
the review gate's Phase 6 (`references/phase-review.md` § Dispatch rework)
turns a consolidated CRITICAL straight into an Ivan `[D{cycle}]` task. The
PRD adds one more design invocation - the same skill, a rework mode - between
Phase 5's decision gate and Phase 6's first `task-add`, so the CRITICAL fix
task carries a reviewed contract the way build tasks do (plan-tasks step 4
copies `## Interfaces & contracts` verbatim; here Phase 6 does the copy).

Layers touched:

- `skills/design-solution/SKILL.md` - the skill grows a `## Rework mode`
  section; the nine-section doc shape, the three-dispatch cross-model review,
  its ceiling, the Claude fallback and the exit report are reused unchanged.
- `skills/run-autopilot/references/phase-review.md` - Phase 6 § Dispatch
  rework gains the routing (design first, once, below the cap), the CRITICAL
  D-task contract block, and the failure routing.
- `skills/run-autopilot/references/recovery.md` and
  `references/state-schema.md` - the new stall site slug `design_rework`
  joins the slug lists. `cli/records.do_stall` accepts any slug string (no
  enum), so `autopilot stall --site design_rework` needs no CLI change.
- Contract tests pin the prose (`scripts/test_design_review_contract.py`
  extended; `cli/test_design_rework_prose.py` new), `dev/bin/release-checks`
  runs both, `CHANGELOG.md` describes the routing.

No `state.json` field is added: the rework doc path is a pure function of
`state.prd` and `state.cycle`. No lens, cap, task budget or classification
row changes. The 00187 cap-out custody branch and the 00188 convergence prose
are untouched (the routing sits inside Phase 6, which the Cap check already
bypasses at the cap).

## Module placement

Edits to existing files (no new runtime code):

| File | Change |
|---|---|
| `skills/design-solution/SKILL.md` | frontmatter `argument-hint`; `## Inputs` rework bullet; `## Output` rework path sentence; new `## Rework mode` section between `## Output` and `## Workflow`; `## Exit report` first-line note |
| `skills/run-autopilot/references/phase-review.md` | two new paragraphs at the top of `### Dispatch rework`; one new bullet in source 2 (`[D{cycle}]` follow-ups) |
| `skills/review-work-completion/SKILL.md` | one paragraph in `### 7. Create follow-up tasks` leaving 🔴 rows to Phase 6 (C2b; the single file outside the PRD's Repository Structure) |
| `skills/run-autopilot/references/recovery.md` | one `design_rework` bullet in `### Stall \`site\` slugs`, after `blocking_escalation` |
| `skills/run-autopilot/references/state-schema.md` | `design_rework` added to the `stall` bullet's slug list under `## Batch Deferred Log` |
| `skills/run-autopilot/scripts/test_design_review_contract.py` | seven new `unittest` methods for rework mode |
| `dev/bin/release-checks` | one new `[checks] design rework prose` block, appended last |
| `CHANGELOG.md` | two `### Added` bullets under `[Unreleased]` |

New file:

| File | Content |
|---|---|
| `skills/run-autopilot/cli/test_design_rework_prose.py` | pytest functions pinning the Phase 6 routing, task contract order, cap/non-CRITICAL behavior, failure routing, slug lists, roster sentence, release-checks block and changelog bullets; imports helpers from `cli.custody_prose_testutil` |

## Interfaces & contracts

Every block below is verbatim-ready. The prose tests pin the quoted
substrings, so the planner copies these strings byte-for-byte.

### C1. `skills/design-solution/SKILL.md`

Frontmatter:

```
argument-hint: "<prd-path> [--rework <review-file>]"
```

`## Inputs`, new bullet after the PRD-path bullet:

```
- **Rework mode** (`--rework <review-file>`): design one review cycle's
  CRITICAL fixes instead of the PRD's first implementation - see
  `## Rework mode`.
```

`## Output`, appended sentence:

```
In rework mode the output is `dev/local/designs/<prd-stem>-rework-<cycle>-design.md`,
where `<cycle>` is the review file's `review:` frontmatter value.
```

New section, placed between `## Output` and `## Workflow`:

```
## Rework mode

`/autopilot:design-solution <prd-path> --rework <review-file>` designs one
review cycle's CRITICAL fixes (PRD 00194). `/autopilot:run-autopilot` Phase 6
invokes it once per cycle, before any fix task is created. Steps 1-5 run as
in default mode except where a bullet below says otherwise.

- **Inputs** (step 1): the PRD, plus from `<review-file>`: `<cycle>` = its
  `review:` frontmatter value, and the CRITICAL rows = every
  `## Consolidated Findings` table row whose Severity cell is `🔴 Critical`.
  `<work_start_sha>` = the left side of the `Diff range:` line in the cycle-1
  review file beside it, `<prd-stem>-review-1.md` (or `-review-01.md`) - under
  autopilot that range is `work_start_sha..HEAD`, so no flag carries it. Run
  `git diff --stat <work_start_sha>..HEAD` for the PRD's whole work range, and
  on cycle 2 or later also `git diff --stat` over `<review-file>`'s own
  `Diff range:` (the prior cycle's rework commits, the range the prior fix
  changed); a `Diff range:` holding a single SHA `X` is read as
  `X..<head_sha>`, `<head_sha>` being `<review-file>`'s frontmatter value. A
  review file with no `🔴 Critical` row, or no cycle-1 review file with a
  `Diff range:` line, is a usage error: print
  `design-solution: --rework needs a 🔴 Critical row and a cycle-1 Diff range` and
  stop without writing a doc.
- **Output**: `dev/local/designs/<prd-stem>-rework-<cycle>-design.md` with the
  same nine sections, same headings, same order as step 3, preceded by one
  source line directly under the H1 title, exactly
  `Source review: <review-file> (head_sha <head_sha>)` - the review file path
  as given and its frontmatter `head_sha`. Phase 6 compares that line before
  reusing a doc, so a design reviewed for one cycle's findings never supplies
  the contract for another's. An existing file at that path is overwritten.
- **`## Architecture fit` opens with a `Prior fix:` paragraph** -
  what the prior fix changed and why it regressed, quoting the CRITICAL rows'
  evidence and the files the prior-cycle `git diff --stat` names, and saying
  whether each CRITICAL was introduced by that fix or only exposed by it. On
  cycle 1 it reads exactly `Prior fix: none - there was no prior rework fix.`
- **`## Interfaces & contracts` is the sole contract source** for the cycle's
  CRITICAL fix tasks: Phase 6 copies it verbatim into each CRITICAL
  `[D{cycle}]` task's `### Contract` block, so name every symbol exactly, and
  open each entry with the 🔴 row it closes (`Closes: <row text>`) so a task
  owner is readable from the shared block.
- **Review** (step 4): the same three-dispatch procedure, the same 3-dispatch
  ceiling, prompt package, minimum-engagement check and Claude fallback,
  unchanged. The prompt additionally carries the CRITICAL rows verbatim so a
  reviewer judges the fix design against the finding it must close.
- **Terminal result line** (step 5): after the exit report is decided, append
  its `result:` value as the last line of `## Review log`, unindented - exactly
  `result: ok` or `result: failed (open cardinal sins/blockers)`. The Review log
  is the ninth section, so this is the doc's last non-empty line; Phase 6 reads
  it as the pass gate. Default mode writes no such line.
- **Exit report**: the first line is `design-solution: <prd-stem> (rework cycle <n>)`
  and `doc:` names the rework path; the remaining lines are unchanged. Open
  cardinal sins or blockers after dispatch 3 end the report with
  `result: failed (open cardinal sins/blockers)` exactly as step 5 describes;
  the caller routes the failure.
```

`## Exit report`, appended sentence after the code block:

```
In rework mode the first line reads `design-solution: <prd-stem> (rework cycle <n>)`.
```

### C2. `skills/run-autopilot/references/phase-review.md` § `### Dispatch rework`

Insert these two paragraphs directly under the `### Dispatch rework` heading,
before `Build the rework batch from two sources:`:

```
**Design CRITICAL rework before any task-add (PRD 00194).** When this cycle's consolidated table holds at least one 🔴 CRITICAL row AND `state.cycle < state.rework_cap`, invoke `/autopilot:design-solution dev/local/prds/wip/<state.prd> --rework <this cycle's review file>` ONCE for this cycle, before the first task is created below. Every unresolved 🔴 row of this cycle becomes (or joins) a `[D{cycle}]` task in source 2 below; its Defer-to-batch-end record (Classification) is the audit trail, not a reason to skip the fix - the Cap check reads "A CRITICAL blocks until it is fixed". This section is the only task-creation point for a 🔴 finding under autopilot: `review-work-completion` step 7 leaves 🔴 rows to it (PRD 00194) and creates the other severities as today. The skill writes `dev/local/designs/<prd-stem>-rework-<cycle>-design.md` (`<cycle>` = `state.cycle`), reviewed by its own three-dispatch loop, and ends its `## Review log` with a terminal `result:` line. **Artifact rule on entry:** first the source check - `rg -q -F 'Source review: <review-file> (head_sha <head_sha>)' dev/local/designs/<prd-stem>-rework-<cycle>-design.md`, `<review-file>` being the path passed to `--rework` and `<head_sha>` its frontmatter value; a missing doc or a non-zero exit means the doc is absent or stale (written for other findings) and the skill is invoked, which overwrites it. When the source line matches: if the pass gate below exits 0 (a crash-resume of this cycle), reuse it and skip the invocation; if it has a terminal `result: failed` line, take the failure routing below without re-invoking; if it has no terminal `result:` line (an interrupted run), invoke the skill, which overwrites it. **Pass gate**, run after the invocation or on reuse: `awk 'NF{last=$0} END{exit last!="result: ok"}' dev/local/designs/<prd-stem>-rework-<cycle>-design.md` - exit 0 means the review completed with no open cardinal sin or blocker; anything else is a rework design failure. At the cap (`state.cycle >= state.rework_cap`) the Cap check above already routed the cycle - the loop-mode `site: "cap_critical"` custody stall or the interactive Cap-pause behavior - so no rework design and no fix task is launched here. A cycle with no 🔴 row runs no rework design (the exit-2 doubt-constraint CRITICAL of the Converged outcome is not a table row and runs none either), and every other severity routes exactly as before.

**Rework design failure** - the pass gate exits non-zero: the report ended `result: failed (open cardinal sins/blockers)`, or the doc is missing after the invocation. The skill's three dispatches were the retry budget: do not re-invoke it, and create no fix task. **Loop mode (`$_AUTOPILOT_LOOP` set):** follow the **Loop-mode stall procedure** (`references/recovery.md`) with `site: "design_rework"`, recording the rework design doc path and the open cardinal-sin / blocker titles in `--detail`, and continue the batch. **Interactive:** set `state.phase = "paused"` and `state.next_phase = "paused"`, write `state.pause_reason = {"site": "sub_skill_fail", "detail": "rework design failed with open findings (cycle <state.cycle>): <rework design doc path>; resolve them, then delete the doc so the next Phase 6 entry regenerates it"}`, print `── AUTOPILOT ── PRD: {prd-name} ── PAUSED (rework design failed, cycle {n}) ──`, and STOP. Every consensus, blind and doubt/de-slop lens already ran in Phase 4; the rework design adds a step before the fix task and removes nothing from the roster.
```

Insert this bullet in source 2 (`**Decision gate `[D{cycle}]` follow-ups**`),
as the FIRST sub-bullet, before `**Transcribe the findings verbatim (PRD 00095).**`:

```
   - **CRITICAL D-tasks carry the rework design (PRD 00194).** A D-task whose findings include at least one 🔴 CRITICAL line carries, in this order: the line `Design: dev/local/designs/<prd-stem>-rework-<cycle>-design.md`, then a `### Contract` block holding the rework design's `## Interfaces & contracts` section body copied verbatim - byte-identical, not paraphrased; the rework design is the sole contract source for these tasks - then the existing `### Findings (verbatim)` block below them. A D-task with no 🔴 line carries neither and is built exactly as before.
```

Unchanged and pinned: the roster sentence (`_ROSTER_SENTENCE` in
`cli/custody_prose_testutil.py`) appears exactly once; the paragraph
beginning `**Escalation caveat — diagnose the failure before escalating.**`
appears exactly once; the loop-mode cap-out bullet keeps
`site: "cap_critical"`.

### C2b. `skills/review-work-completion/SKILL.md` § `### 7. Create follow-up tasks`

Insert this paragraph directly after the line
`**If issues found, and `dev/local/autopilot/state.json` exists (autopilot run):** Create each follow-up with `task-add`, prioritizing multi-agent consensus:`
and before its `- Process 🔴 → 🟠 → 🟡 order` bullet list:

```
A 🔴 CRITICAL finding gets no task here (PRD 00194): `run-autopilot/references/phase-review.md` Phase 6 § Dispatch rework creates it after the cycle's rework design, so a CRITICAL fix never starts without a reviewed contract. Every other severity is created below as today.
```

Two existing sentences in the same step contradict that paragraph and are
amended in the same edit (codex, dispatch 3):

- In the verification-queue paragraph, replace
  `A queued **CRITICAL or HIGH is not skipped**: it is never routed (`run-autopilot/references/phase-review.md` Phase 5), so it gets its task as today.`
  with
  `A queued **HIGH is not skipped**: it is never routed (`run-autopilot/references/phase-review.md` Phase 5), so it gets its task as today; a queued CRITICAL is never routed either, and its task is Phase 6's (below).`
- Replace the bullet `- Process 🔴 → 🟠 → 🟡 order` with
  `- Process 🟠 → 🟡 order (🔴 rows belong to Phase 6, above)`.

This is the one file outside the PRD's Repository Structure (the
plan-expansion gate stalls at two unlisted modules, not one): the review
skill is today's first `task-add` owner for a cycle's findings, so without
this sentence the "design before task-add" rule has two owners and the
review skill's step 7 would create the CRITICAL task before Phase 5's cap
check or the rework design ever ran.

### C3. `skills/run-autopilot/references/recovery.md` § `### Stall \`site\` slugs`

New bullet directly after the `blocking_escalation` bullet:

```
- `design_rework` — a loop-mode Phase 6 rework design (`/autopilot:design-solution
  --rework`, PRD 00194) that ended with open cardinal sins / blockers after its
  three dispatches, a missing doc, or an empty `## Review log`; records the
  rework design doc path and the open finding titles in the deferred `detail`.
  No fix task was created. On un-park the PRD re-enters the build gate; read
  the rework doc's open findings before moving it back.
```

### C4. `skills/run-autopilot/references/state-schema.md` § `## Batch Deferred Log`

In the `- \`stall\`` bullet's slug list, insert after
`` `blocking_escalation` (a loop-mode Phase 5 blocking escalation), ``:

```
`design_rework` (a loop-mode Phase 6 rework design that failed, PRD 00194; `detail` names the rework design doc path and the open findings),
```

### C5. `dev/bin/release-checks`

Append as the last block:

```
echo "[checks] design rework prose"
uv run --no-project --with pytest python -m pytest -q \
  skills/run-autopilot/scripts/test_design_review_contract.py \
  skills/run-autopilot/cli/test_design_rework_prose.py
```

### C6. `CHANGELOG.md` `## [Unreleased]` / `### Added`

```
- **design-solution**: `--rework <review-file>` designs one review cycle's CRITICAL fixes into `dev/local/designs/<prd-stem>-rework-<cycle>-design.md`, opening with what the prior fix changed and why it regressed, under the same three-dispatch review, and ends its review log with a `result:` line
- **run-autopilot**: a review cycle with a CRITICAL below the rework cap now runs the rework design before any fix task is created (the review skill leaves CRITICAL rows to Phase 6), and each CRITICAL `[D{cycle}]` task carries the design path and its `## Interfaces & contracts` verbatim above the findings; a failed rework design stalls the PRD under site `design_rework` in loop mode and pauses interactively
```

### C7. `skills/run-autopilot/scripts/test_design_review_contract.py` - new methods

Same `unittest.TestCase`, same `self.design` text. Each asserts one literal
from C1:

| method | literal |
|---|---|
| `test_rework_mode_takes_a_review_file` | `--rework <review-file>` |
| `test_rework_output_is_cycle_scoped` | `dev/local/designs/<prd-stem>-rework-<cycle>-design.md` |
| `test_rework_keeps_the_nine_sections` | `same nine sections, same headings, same order as step 3` |
| `test_rework_architecture_fit_explains_the_prior_fix` | `what the prior fix changed and why it regressed` AND `Prior fix: none - there was no prior rework fix.` |
| `test_rework_keeps_the_three_dispatch_procedure` | `the same 3-dispatch` AND (existing) `3-dispatch ceiling` |
| `test_rework_summary_line_is_cycle_specific` | `design-solution: <prd-stem> (rework cycle <n>)` |
| `test_rework_contract_is_the_sole_source` | `is the sole contract source` |
| `test_rework_derives_the_work_base_from_the_cycle_1_review` | `<prd-stem>-review-1.md` AND `Diff range:` |
| `test_rework_review_log_ends_with_the_result_line` | `result: ok` AND `result: failed (open cardinal sins/blockers)` AND `last line of \`## Review log\`` |
| `test_rework_doc_names_its_source_review` | `Source review: <review-file> (head_sha <head_sha>)` |

### C8. `skills/run-autopilot/cli/test_design_rework_prose.py` - new file

Header mirrors `test_custody_prose.py`: `sys.path.insert(0, parent.parent)`,
`from cli.custody_prose_testutil import _PHASE_REVIEW, _REVIEW_TEXT, _RECOVERY,
_RECOVERY_TEXT, _STATE_SCHEMA, _ROSTER_SENTENCE, _SKILL_DIR, _section, _bullet,
_deferred_log_section, _h2_section, _rows_starting_with, _assert_present,
_assert_absent, _assert_in_order`. The repo-level paths are NOT in the
testutil (they are module-level in `test_custody_prose.py`, and a test must
not import another test module), so the new file re-derives them:

```python
_REPO_ROOT = _SKILL_DIR.parent.parent
_RELEASE_CHECKS = _REPO_ROOT / "dev" / "bin" / "release-checks"
_RELEASE_CHECKS_TEXT = _RELEASE_CHECKS.read_text()
_CHANGELOG = _REPO_ROOT / "CHANGELOG.md"
_CHANGELOG_TEXT = _CHANGELOG.read_text()
_REVIEW_SKILL = _SKILL_DIR.parent / "review-work-completion" / "SKILL.md"
_REVIEW_SKILL_TEXT = _REVIEW_SKILL.read_text()
_DISPATCH = _section(_REVIEW_TEXT, _PHASE_REVIEW, "### Dispatch rework", "### After /autopilot:work returns")
_STEP_7 = _section(_REVIEW_SKILL_TEXT, _REVIEW_SKILL, "### 7. Create follow-up tasks", "### 8. Save review file")
```

`_section` has no to-EOF form (it asserts the end anchor exists), so the
release-checks block is sliced as `_RELEASE_CHECKS_TEXT[_RELEASE_CHECKS_TEXT.index('echo "[checks] design rework prose"'):]`
after asserting the echo line is present.

Test functions and what each pins (presence via `_assert_present`, order via
`_assert_in_order`, inversion via `_assert_absent`):

| function | pins |
|---|---|
| `test_dispatch_rework_designs_critical_rework_once_before_any_task_add` | in `_DISPATCH`: `--rework <this cycle's review file>`, `state.cycle < state.rework_cap`, `ONCE for this cycle`; order (first occurrences): `ONCE for this cycle`, then `Build the rework batch from two sources:`, then `` `task-add <task-json-file>` `` (the real creation step, not the bare token); absent: `Do NOT invoke \`/autopilot:design-solution\``, `after the tasks are created` |
| `test_every_critical_row_becomes_a_d_task_with_one_owner` | in `_DISPATCH`: `Every unresolved 🔴 row of this cycle becomes (or joins) a \`[D{cycle}]\` task`, `audit trail, not a reason to skip the fix`, `only task-creation point for a 🔴 finding`; in `_STEP_7`: `A 🔴 CRITICAL finding gets no task here (PRD 00194)`, `Phase 6`, `A queued **HIGH is not skipped**`, `- Process 🟠 → 🟡 order`; absent in `_STEP_7`: `CRITICAL or HIGH is not skipped`, `Process 🔴 → 🟠 → 🟡 order`, `creates the CRITICAL task here` |
| `test_rework_design_reuse_needs_the_source_check_and_the_pass_gate` | in `_DISPATCH`: `rg -q -F 'Source review:`, `stale`, the literal `awk 'NF{last=$0} END{exit last!="result: ok"}'`, `result: failed`, `interrupted run`, `reuse it and skip the invocation`; order: `Source review:` before `Pass gate`; absent: `reuse it unconditionally`, `skip the pass gate`, `skip the source check` |
| `test_critical_d_task_carries_design_then_contract_then_findings` | in `_DISPATCH`, in order: `Design: dev/local/designs/<prd-stem>-rework-<cycle>-design.md`, `### Contract`, `### Findings (verbatim)`; presence `copied verbatim`, `sole contract source`; absent: `paraphrase the contract`, `below its \`### Findings (verbatim)\`` |
| `test_at_cap_keeps_the_custody_stall_and_launches_no_rework_design` | in `_DISPATCH`: `state.cycle >= state.rework_cap`, `site: "cap_critical"`, `no rework design and no fix task`; the loop-mode cap-out bullet (same slice as `test_loop_cap_out_captures_the_range_internally_with_no_range_flag`) still says `site: "cap_critical"` |
| `test_non_critical_rework_routing_is_unchanged` | in `_DISPATCH`: `A cycle with no 🔴 row runs no rework design`, `every other severity routes exactly as before`, `A D-task with no 🔴 line carries neither` |
| `test_rework_design_failure_stalls_in_loop_and_pauses_interactively` | in `_DISPATCH`: `site: "design_rework"`, `Loop-mode stall procedure`, `"site": "sub_skill_fail"`, `state.phase = "paused"`, `do not re-invoke it`, `create no fix task`, `delete the doc so the next Phase 6 entry regenerates it`; order: `Loop mode` before `Interactive`; absent: `re-invoke the sub-skill ONCE`, `never stall` |
| `test_recovery_and_schema_list_the_design_rework_slug` | `_bullet(slugs section, _RECOVERY, "design_rework")` contains `Phase 6`, `--rework`, `detail`; the schema `stall` bullet (`_bullet(_deferred_log_section(), _STATE_SCHEMA, "stall")`) contains `` `design_rework` `` |
| `test_roster_sentence_and_escalation_caveat_survive` | `_REVIEW_TEXT.count(_ROSTER_SENTENCE) == 1`; `_REVIEW_TEXT.count("**Escalation caveat — diagnose the failure before escalating.**") == 1` |
| `test_release_checks_runs_both_design_contract_suites` | `dev/bin/release-checks` contains the C5 block verbatim (both paths inside the `[checks] design rework prose` block, sliced from that echo line to EOF as shown above) |
| `test_changelog_unreleased_added_carries_both_design_rework_entries` | `_h2_section(CHANGELOG, "## [Unreleased]")` → `### Added` slice → a `- **design-solution**:` bullet containing `--rework` and a `- **run-autopilot**:` bullet containing `design_rework` |

Run command (PRD acceptance, verbatim):

```
uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/scripts/test_design_review_contract.py skills/run-autopilot/cli/test_design_rework_prose.py
bash dev/bin/release-checks
```

## Data flow

1. Phase 4 writes `dev/local/reviews/<prd-stem>-review-<cycle>.md` with the
   consolidated table (`| [n/m] | 🔴 Critical | ... |` rows) and `review: <cycle>`
   frontmatter. `review-work-completion` step 7 creates follow-up tasks for
   every severity except 🔴 (C2b), which it leaves to Phase 6.
2. Phase 5's Cap check reads it. `cycle >= rework_cap` with a CRITICAL → the
   existing cap-out (loop `cap_critical` custody stall / interactive cap-pause)
   and Phase 6 is never reached. Otherwise classification runs as today (a
   CRITICAL still gets its Defer-to-batch-end record).
3. Phase 6 § Dispatch rework, new first step: ≥1 🔴 row AND
   `cycle < rework_cap` → artifact rule (source check, then reuse / fail /
   invoke), then `/autopilot:design-solution <wip prd> --rework <review file>`.
4. design-solution reads the PRD, the 🔴 rows, `review:` and `head_sha` from
   the review file, `work_start_sha` from the cycle-1 review's `Diff range:`,
   runs `git diff --stat` over the PRD range (and the prior cycle's range on
   cycle ≥ 2), writes `dev/local/designs/<prd-stem>-rework-<cycle>-design.md`
   (`Source review:` line under the title; nine sections; `## Architecture
   fit` opens with `Prior fix:`), runs its three-dispatch review, appends
   `result: ok` / `result: failed (...)` as the last Review-log line, prints
   `design-solution: <prd-stem> (rework cycle <n>)` + exit report.
5. Phase 6 runs the pass gate (`awk` last-non-empty-line == `result: ok`).
   Pass → every unresolved 🔴 row lands in a `[D{cycle}]` task carrying
   `Design: <path>`, `### Contract` = verbatim `## Interfaces & contracts`
   body, then `### Findings (verbatim)`; `task-add` as today. Fail → loop:
   `autopilot stall --site design_rework`; interactive: PAUSE `sub_skill_fail`.
   No fix task either way.
6. `/autopilot:work` rework mode: step 2.7 (Tess) writes tests from the task
   description, which now carries the reviewed contract; step 5.7 checks
   closure against the findings block as today. Micro lane is unaffected
   (CRITICAL never qualifies).
7. `autopilot phase-done --outcome rework` → next cycle. With `rework_cap: 2`
   (the pack default) a PRD runs at most one rework design.

## Reuse inventory

- `skills/design-solution/SKILL.md` steps 3-5 and `## Exit report` - the
  nine-section shape, the three-dispatch cross-model review, ceiling,
  minimum-engagement check, Claude fallback and the pinned dispatch-summary
  line; rework mode reuses all of it and only changes inputs, output path,
  the `## Architecture fit` opener and the exit report's first line.
- Core `SKILL.md` § Design-gate invariant (the section-scoped `awk` gate) -
  the pass gate copies its shape (one `awk`, exit-code based, no pipe, no
  shell variable) but reads the terminal `result:` line instead, because the
  empty-review-log gate proves a review ran, not that it passed (codex,
  dispatch 2: that awk returned 0 on a dispatch-1-only log and on a failed
  dispatch-3 log).
- `references/phase-build.md` Phase 1.5 artifact-skip - the crash-resume
  reuse rule copies its shape, with the pass gate as the reuse condition.
- `review-work-completion/SKILL.md` step 7 - today's first `task-add` owner
  for a cycle's findings; C2b narrows it by one severity rather than adding a
  second creation path.
- `autopilot stall --prd --site --detail` (`cli/records.do_stall`) - the
  loop-mode failure path; slug strings are free-form (grep: `rg -n "site" cli/records.py cli/schema.py` - no enum), so `design_rework` needs no code.
- `references/recovery.md` "Loop-mode stall procedure" exit table - referenced,
  not copied.
- `review-work-completion/references/output-formats.md` - `review:` frontmatter
  and the consolidated table's Severity cell (`🔴 Critical`, the same marks
  `cli/convergence.SEVERITY_MARKS` reads) are the rework inputs.
- `plan-tasks/SKILL.md` step 4 "Contract source when a design doc exists" -
  the verbatim-copy discipline the `### Contract` block mirrors.
- `cli/custody_prose_testutil.py` - `_section`, `_bullet`, `_h2_section`,
  `_deferred_log_section`, `_rows_starting_with`, `_assert_present`,
  `_assert_absent`, `_assert_in_order`, `_ROSTER_SENTENCE`; the new prose test
  imports them instead of re-implementing slicing.
- Greps that found nothing (proved with a known-present control each):
  `rg -n "rework|--rework" skills/design-solution/` (control: `dispatch`);
  `rg -n -i "design.*rework|before.*task-add" skills/run-autopilot/references/phase-review.md`
  (control: `task-add`).

## Alternatives considered

1. **Smallest diff**: one sentence in `### Dispatch rework` ("run
   `/autopilot:design-solution --rework` before task-add") and no new stall
   site, new test file or design-solution section. Rejected: the PRD names
   the `design_rework` site, the cycle-scoped filename, the `Prior fix:`
   opener and `cli/test_design_rework_prose.py` as acceptance; and a
   sentence with no pinned literals is what drifts.
2. **Chosen - prose-only, one flag, no state field**: `--rework <review-file>`
   (the PRD's own invocation). The review file carries `review:` and the 🔴
   rows; `work_start_sha` is the left SHA of the cycle-1 review file's
   `Diff range:` (a cycle-2 review's own range is the incremental
   `prior head..HEAD`, which is the prior fix's range and is used for that),
   so no second flag and no state read. The rework doc path derives from
   `state.prd` + `state.cycle`, so nothing new is written to `state.json` and
   `PER_PRD_RESET_FIELDS` is untouched. The pass gate is a terminal
   `result:` line rather than a state field for the same reason. The extra
   size over (1) buys the pinned contracts, the single task-creation owner
   and the failure routing.
3. **Larger - a CLI subcommand** (`autopilot design-rework` extracting the 🔴
   rows into a prompt file, a `state.rework_design_doc` field, and custody
   capture on the `design_rework` stall). Rejected: it edits `cli/` modules
   the PRD's Repository Structure never names (the 00189 plan-expansion gate
   stalls at two unlisted modules), and the model already reads the table.

## Risks & edge cases

- **`design-rework` spelling is forbidden.** `cli/test_custody_prose.py`
  (`_ABSENT_NEEDLES`) sweeps every `.md` under `skills/run-autopilot` for the
  hyphenated `design-rework` (a 00187 scope fence). All new prose uses the
  slug `design_rework` and the phrase "rework design"; the doc filename
  `<prd-stem>-rework-<cycle>-design.md` does not contain the needle. The
  same sweep forbids `--range`, so no range flag exists. Task authors must
  not "fix" the needle list; run `test_custody_prose.py` as a check.
- **A CRITICAL parked under `design_rework` has no custody record.** Custody
  (marker, journal, push guard) fires only for `site == cap_critical`
  (`cli/custody.CUSTODY_SITE`). A below-cap CRITICAL whose rework design
  fails is parked with its commits on master and only the batch-end STALLED
  block naming it - the same exposure `blocking_escalation` already has. Likely
  next change: extend the custody capture to `design_rework` (one predicate
  in `records._stall_preflight`); nothing here boxes it in.
- **Crash-resume mid-Phase 6** re-enters the review session at Phase 5/6
  (Phase 4 skips on the existing review file). The artifact rule covers the
  states: stale or absent (no `Source review:` line matching this cycle's
  review file and `head_sha`) → invoke, the skill overwrites; matching and
  interrupted (no terminal `result:` line) → invoke; matching `result: ok` →
  reuse; matching `result: failed` → the failure routing, no re-invocation.
  An un-parked PRD that reaches Phase 6 again with a new review file fails
  the source check, so its old `-rework-<cycle>-design.md` is regenerated,
  never reused against different 🔴 rows (codex, dispatch 3 re-run). The
  interactive remedy's "delete the doc" covers the matching-failed case.
- **Multiple CRITICAL D-tasks in one cycle** share one rework doc and the
  same `### Contract` block; the design covers every 🔴 row of the cycle and
  each contract entry opens with `Closes: <row>` so ownership is readable. A
  D-task mixing a 🔴 and a 🟠 line is a CRITICAL D-task. The block rides
  into the implementor prompt; the existing 50K `subagent_prompt_overrun`
  stall (`state-schema.md` `stall_reason`) is the ceiling, unchanged - a
  rework contract of this doc's size (~10K chars) sits well under it.
- **Discarded CRITICAL rows.** The design covers every 🔴 table row; a row
  Phase 5 discarded (contradicts computed facts) gets a contract entry but no
  task. Surplus, not a contradiction: the trigger and the design set are the
  same "any 🔴 row", the task set is Phase 5's "unresolved".
- **`rework_cap: 2`** (default) means: cycle 1 CRITICAL → rework design;
  cycle 2 CRITICAL → cap-out. At most one rework design per PRD at the
  default cap; a raised cap allows one per below-cap cycle.
- **Interactive PAUSE vs loop stall asymmetry** is the PRD's own routing and
  matches Phase 1.5 (PAUSE `sub_skill_fail`) / loop stall convention. The
  generic Error Handling row's "re-invoke ONCE" is deliberately not applied:
  the three dispatches are the retry.
- **Phase 5 classification is untouched.** "Critical severity, always → defer
  to batch end" keeps writing the `deferred_decisions` record (the 00187
  invariant that a CRITICAL is never a settled deferral); C2 now states
  explicitly that the record is an audit trail and every unresolved 🔴 row
  still gets its `[D{cycle}]` task - the rule the prose only implied before
  ("A CRITICAL blocks until it is fixed").
- **The exit-2 doubt-constraint CRITICAL** (Converged outcome, gate exit 2)
  is not a table row; C2 says it runs no rework design and the next cycle
  re-reviews, as today.
- Likely next changes: (a) custody on `design_rework` (above); (b) 00195's
  hold stubs for unowned deferred findings will list `design_rework` stalls
  like any other; (c) 00196 guarding review-phase rework sessions may want
  the rework doc path in the session brief - the deterministic path makes
  that a one-liner.

## Test strategy outline

- Prose contracts only; no runtime code changes, so no behavioral tests.
- `scripts/test_design_review_contract.py` (extended, C7): each new method
  fails on the pre-change `SKILL.md` (RED-first by construction - the
  literals do not exist yet).
- `cli/test_design_rework_prose.py` (new, C8): every function fails against
  the current `phase-review.md` / `recovery.md` / `state-schema.md` /
  `release-checks` / `CHANGELOG.md`; the roster/caveat test is the one that
  passes before and after (it pins preservation).
- Regression: `cli/test_custody_prose.py` and `cli/test_custody_prose_schema.py`
  must stay green (absent-needle sweep, roster sentence, `cap_critical`
  bullet, changelog custody bullets), and the review skill's own prose pins
  (`review-work-completion/scripts/test_retry_policy_prose.py`,
  `test_carl_skip_prose.py`) after the C2b paragraph lands.
- Pass-gate sanity (manual, once): the `awk` one-liner exits 0 on a file
  whose last non-empty line is `result: ok`, non-zero on `result: failed (open
  cardinal sins/blockers)`, on a file with no terminal line, and on a missing
  file.
- Gate: `bash dev/bin/release-checks` runs the new block last.

## Review log

Dispatch 1 (Claude subagent). Blockers fixed in place: (1) the C7 literal `what the prior fix changed and why it regressed` was line-wrapped in C1 - re-wrapped onto one line; (2) the C2 D-task bullet named `### Findings (verbatim)` before `Design:`/`### Contract`, defeating the C8 order pin - reworded in task order. Also corrected C8's helper contract (Q3 below): `_section` has no to-EOF form and the changelog / release-checks paths are not in the testutil; the spec now re-derives them and slices the release-checks block by `index()`.

- non-blocker: mandatory `--base` makes the PRD's bare `--rework <review-file>` invocation a usage error; the cycle-1 review file's `Diff range:` already carries `work_start_sha..HEAD` under autopilot. Suggested: optional `--base` defaulting to the cycle-1 review's left SHA. Also the "reverse" usage message names the wrong missing flag.
- non-blocker: the `Prior fix:` opener needs the prior fix's own range (the review file's incremental `Diff range:`), while rework mode only runs `git diff --stat <work_start_sha>..HEAD`; add the second stat.
- non-blocker: crash-resume reuse cannot tell a `result: failed` doc from a good one - open cardinal sins / blockers live only in the exit report, never in `## Review log`, so a failed doc passes the awk gate on an interactive resume; state the remedy in `pause_reason.detail` and/or write the open titles into the doc.
- non-blocker: the "design before first task-add" order pin is tautological (both first occurrences sit in C2 paragraph 1); pin `ONCE for this cycle` before `Build the rework batch from two sources:` and the literal `task-add <task-json-file>` step line.
- non-blocker: every CRITICAL D-task carries the whole `## Interfaces & contracts` body; plan-tasks copies per-task entries, and the 50K `subagent_prompt_overrun` stall is the ceiling - scope the block or name the exposure in Risks.
- question: which Phase 6 rule creates the CRITICAL D-task the new bullet decorates? Classification defers a CRITICAL to batch end and Outcomes says "proceed to Phase 6 with auto-fixable items only"; no sentence in `### Dispatch rework` says a deferred CRITICAL still yields a `[D{cycle}]` task.
- question: does the Converged exit-2 doubt-constraint "CRITICAL" (no 🔴 table row) trigger a rework design? C2 triggers on table rows only and C1 makes a no-🔴 review file a usage error.
- question (applied, see above): C8 helper contract - `_section` to-EOF form and testutil paths.

dispatch 1 (claude): cardinal-sin 0, blocker 2, non-blocker 5, question 3

Dispatch 2 (codex, `gpt-6-astra`, read-only; the first run's `-o` file looked truncated because the Watcher's 20s mtime-stable heuristic fired while codex was still thinking - the run completed with findings ~10 min later; a bounded-reading retry launched in the meantime was stopped unread). Blockers fixed in place: (1) `review-work-completion` step 7 already `task-add`s 🔴 findings in Phase 4 - C2b now leaves 🔴 rows to Phase 6, one task-creation owner; (2) no rule created the CRITICAL D-task - C2 now says every unresolved 🔴 row becomes (or joins) a `[D{cycle}]` task, the deferral record being the audit trail; (3) the empty-review-log awk gate accepted a dispatch-1-only log and a failed dispatch-3 log - replaced by a terminal `result:` line the skill appends in rework mode and a last-non-empty-line `awk` pass gate, with an explicit absent / interrupted / failed / ok artifact rule (verified: the awk exits 0/1/2/1 on ok / failed / missing / no-terminal-line files); (4) the C8 order pin was tautological - it now pins `ONCE for this cycle` before `Build the rework batch from two sources:` before the `task-add <task-json-file>` step. Also applied while there (both reviewers raised them): `--base` dropped, `work_start_sha` read from the cycle-1 review's `Diff range:`, so the PRD's bare `--rework <review-file>` invocation is valid; the `Prior fix:` opener also reads the prior cycle's own `Diff range:`; the discard exclusion dropped so trigger and design set are the same "any 🔴 row"; each contract entry opens with `Closes: <row>`; the exit-2 constraint CRITICAL is named as running no design; the failure line is the exact `result: failed (open cardinal sins/blockers)`.

- non-blocker: design and dispatch used different CRITICAL sets (discarded rows) - resolved by the same-set rule above; recorded, no further action.
- non-blocker: mandatory `--base` broke the PRD's invocation - resolved above.
- non-blocker: the prior-fix diagnosis lacked the prior fix's own changes - resolved above (prior cycle's `Diff range:`); the introduced-vs-exposed distinction is now asked of the `Prior fix:` paragraph.
- non-blocker: whole-cycle contracts obscure per-task ownership and enlarge prompts - mitigated by `Closes: <row>` entries and the Risks note on the 50K overrun ceiling; not scoped per task (the design is one document per cycle by PRD).
- question: empty-log recovery both regenerates and stalls - resolved by the four-state artifact rule.
- question: failure-report suffix inconsistent - resolved (exact line pinned).
- question: synthetic (exit-2 constraint) CRITICALs had no design policy - resolved (exempt, stated in C2).

dispatch 2 (codex): cardinal-sin 0, blocker 4, non-blocker 4, question 3

Dispatch 3 (codex verification). All four dispatch-2 blockers verified resolved with anchors (C2b insertion point real at step 7; C2 D-task rule explicit; terminal `result:` line and awk gate agree, four artifact states consistent; C8 order pin reaches `phase-review.md` `Build the rework batch` and the `task-add <task-json-file>` step; every C7/C8 literal present; `_ABSENT_NEEDLES` and `_ROSTER_SENTENCE` respected).

- non-blocker (applied - it was the unfinished half of blocker 1): step 7 kept two sentences that contradict C2b (`A queued **CRITICAL or HIGH is not skipped** ... gets its task as today` and `Process 🔴 → 🟠 → 🟡 order`). C2b now amends both and C8 pins the new wording and the absence of the old.

Dispatch 3 engagement re-run (codex, sharper section-by-section prompt; the first pass returned one finding, under the three-finding floor). Returned a seven-item anchored CHECKED list plus: blocker - a stale `result: ok` doc (written for another review of the same cycle number, e.g. after an un-park) would be reused against different 🔴 rows. Fixed in place: the skill writes `Source review: <review-file> (head_sha <head_sha>)` under the title and Phase 6's artifact rule runs an `rg -q -F` source check before the pass gate; a non-matching doc is stale and regenerated. Non-blocker (applied, same field): an incremental `Diff range:` may be a single SHA (`review-work-completion/SKILL.md:150`) or `a..b` (`output-formats.md:271`); C1 now reads a single SHA as `X..<head_sha>`. Engagement satisfied - not WEAK.

dispatch 3 (codex): cardinal-sin 0, blocker 1, non-blocker 2, question 0
