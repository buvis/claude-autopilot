---
prd: docs/dev/project-management/prds/wip/00232-keep-subagent-test-runs-narrow-v1.md
review: 2
date: 2026-10-01
head_sha: f5c0bd2173b799dc9d00c1495e9cacabd6dca5ee
codex_thread_id: 01a0f47b-aab5-79a1-b1d5-648ad5808d77
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00232-keep-subagent-test-runs-narrow-v1

Diff range: `be7da2c09fae53f7bda5760673b927dcd3bd7914..f5c0bd2173b799dc9d00c1495e9cacabd6dca5ee`

codex_rung_guard: not fired

pack: unavailable this cycle (`engram pack` exited 1: "not inside a registered repo; register it in
`/Users/bob/.config/gita/repos.csv`"). Every prompt that takes `{PACK_FILE}` / `{PACK_FINDINGS}`
received the sentinel `(no pack available this cycle)`. The retry was skipped deliberately, as in
cycle 1: the error is a deterministic registration gap, not a transient failure. Blake never
receives a pack by design.

Diff-scope note: this is a genuine **incremental** cycle. `gather-context.sh` ran with
`--since be7da2c09fae53f7bda5760673b927dcd3bd7914`, the `head_sha` of the cycle-1 review file, so
the diff covers only the two rework commits (`5d3a1e1` task 4, `f5c0bd2` task 5) — 3 files,
+192/−46. Bob resumed his cycle-1 codex thread `01a0f47b` via `--resume-thread`, so his verdicts
are a continuation of his own critique rather than a fresh read.

## Review Summary

Reviewed: 5 completed tasks (3 from cycle 1, 2 rework tasks in this cycle's diff)
PRDs checked: 00232-keep-subagent-test-runs-narrow-v1.md

### Agent Status

- Alice: ✅ Available (Claude subagent, consensus engine `legacy`)
- Blake: ✅ Available (Claude subagent, blind/PRD-only; no Filesystem-notes block needed — project
  root is not a dot-directory and `docs/dev/project-management` is not a symlink)
- Bob: ✅ Available (codex, doubt + de-slop; exit 0, first run, no retry, resumed thread `01a0f47b`)
- Carl: ✅ Available (gemini via copilot backend; exit 0, non-empty reviewer text)

All four lenses ran. No reviewer failed, so no fallback and no degradation. Eve did not run: the
resolved `doubt_reviewer` is `codex` and the codex doubt-roster guard did not fire (no task in
`state.tasks[].attempts[].implementor` is `codex` — the five attempts are `claude` ×4 and
`orchestrator` ×1), so she is not part of this roster.

## Consolidated Findings

`consolidate_findings.py` emitted 4 rows and **merged Alice's and Bob's fence-placement findings by
itself** this cycle (`row 1 merged citations that matched only after suffix stripping:
test_narrow_runs_prose.py:139 ~ :146`) — the same defect at two line citations in one file. No
manual merge was needed at the gate. Consolidation was the script's, not model-side.

The settled-decisions ledger existed on entry (4 cycle-1 entries), so `--ledger` and
`--ledger-dismiss BLAKE` were both passed. **Nothing was auto-dismissed**: Blake's one finding
matched no ledger entry, so there is no `### Auto-dismissed (ledger)` section to copy.

Carry-forward: no `00232-…-checks-1.json` exists (cycle 1 queued no VERIFY item), so nothing was
carried forward.

Mechanical test checks: the tautological-shapes block produced **zero** `[MECH]` lines across 8 test
functions. The fail-first replay produced **one**, absorbed below as its own row (no existing row
named the same tests) with `Found by: mech-check`.

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [2/4] | 🟡 Medium | `test_adversarial_prompt_carries_narrow_in_feedback_section` only proves NARROW appears once in the file and somewhere after the "## Feedback to Tess" heading. It does not prove NARROW sits inside the fenced template. Task 4's contract put it inside the fence, after "Do not change tests that Devon could NOT break." and before the closing fence, because the strengthen dispatch's whole prompt is that fence. Moving the paragraph below the closing fence still passes, and Tess would again never receive it. The failure message even says "inside the 'Feedback to Tess' fenced template". Slice from the heading's opening fence to its closing fence, or assert the paragraph follows the "Do not change tests that Devon could NOT break." line within the fence. | skills/work/scripts/test_narrow_runs_prose.py:139 | 5 | Alice, Bob |
| [1/4] | 🟡 Medium | 6 touched test(s) pass against the pre-change code: test_tess_and_ivan_carry_the_narrow_sentence, test_devon_runner_is_the_tasks_test_files, test_devon_rules_forbid_a_directory_run, test_devon_context_selection_includes_test_runner_row, test_work_skill_names_rework_mode, test_render_tess_prompt_contains_narrow_once | skills/work/scripts/test_narrow_runs_prose.py | general | mech-check |
| [1/4] | 🟡 Medium | Redundant `.rstrip()` follows `_norm()`, which already removes leading and trailing whitespace; simplify to `normalized = _norm(rules_section)` without changing behavior | skills/work/scripts/test_narrow_runs_prose.py:182 | 5 | Bob |
| [1/4] | ⚪ Low | Task 4's Process step 3 rewording ("Run the test runner command above against your wrong implementation") has no pin. Nothing fails if "Run the test suite against your wrong implementation" comes back, so the wording that sits against Rule 6 can regress silently. The Rule 6 single-line rejoin is also unpinned, because `_norm` hides the wrap. | skills/work/scripts/test_narrow_runs_prose.py:174 | 5 | Alice |
| [1/4] | ⚪ Low | Scope beyond the PRD's four insertion points: the NARROW sentence is also inserted in skills/work/references/tess-retry-prompt.md:34 and inside Devon's "Feedback to Tess" template at skills/work/references/adversarial-test-prompt.md:96. A context-selection row and Rules item are also pinned by extra tests. The PRD names only tess-prompt, ivan, adversarial (runner line, row, last rule) and SKILL.md. The extras are consistent with the intent, are harmless, and pass. They are still unrequested prose. | skills/work/references/tess-retry-prompt.md | 1 | Blake |

**No 🔴 CRITICAL and no 🟠 High was raised this cycle.** Every cycle-1 blocker is closed (see below).

### Cycle-1 findings: closure status

| Cycle-1 finding | Severity | Status | Evidence |
|-----------------|----------|--------|----------|
| Narrow-run rule never reaches the Tess quality-gate retry prompt or the "Feedback to Tess" strengthen template, making `skills/work/SKILL.md:71` false as shipped | 🟠 High 3/4 | **RESOLVED** | NARROW is its own paragraph after the tool-discipline paragraph and before `ASSUMPTIONS:` at `skills/work/references/tess-retry-prompt.md:34`, and inside the fenced "Feedback to Tess" template at `skills/work/references/adversarial-test-prompt.md:96`. Confirmed independently by Alice, Blake (blind) and Carl; the orchestrator's own `rg -c "never re-run a suite to recover a number"` prints 1 for each of the two files. |
| The test does not pin the NARROW literal (opening clause plus cross-file equality only; "directly after" checked as index ordering) | 🟡 Medium 3/4 | **RESOLVED** | `NARROW` is now a full module-level constant; `_assert_narrow_once_and_adjacent` asserts it appears exactly once per file and as the very next blank-line paragraph after the anchor, replacing the old `index()` ordering check. Covers `tess-prompt.md`, `agents/ivan.md` and `tess-retry-prompt.md`. |
| Devon coverage gaps (untested Context Selection row; whole-file matching; `_section` unused; untested happy-path render) | 🟡 Medium 3/4 | **RESOLVED except one residual** | The runner needle is scoped to the `Test runner command:` line; the Rules test is scoped to the Rules list and requires the rule to be last; `test_devon_context_selection_includes_test_runner_row` is added; `_section` is used; `test_render_tess_prompt_contains_narrow_once` adds the PRD's happy path; the rework sentence is pinned as directly adjacent to its predecessor. The residual is the fence-placement row above — the one Devon-adjacent pin that is still not anchored to its fence. |
| PRD-internal inconsistency: `SKILL.md:71` claims "the same narrow-run sentence" while the PRD specifies different wording for Devon | 🟡 Medium 3/4 | **DEFERRED (cycle 1)** | Unchanged; needs a spec decision. Blake's cycle-2 scope row is the same root and is deferred alongside it. |
| Devon's Process step 3 "Run the test suite against your wrong implementation" and Rule 6's mid-sentence hard wrap | ⚪ Low 2/4 | **RESOLVED in prose** | `rg -c "Run the test suite against your wrong implementation"` prints 0 (Carl reproduced this). Rule 6 is one line. Rule 1's "the tests" was deliberately left alone — Rule 1 governs not modifying test files, not how much to run. The prose is fixed but unpinned, which is the ⚪ row above. |
| NARROW's pytest-only flags and the ambiguous "that one run" antecedent | ⚪ Low 2/4 | **SETTLED DEFERRAL** | Ledgered cycle 1; not re-raised by any lens this cycle. |
| fast-track `RETRY_INSTRUCTION` ends "keep the suite green" | ⚪ Low 1/4 | **SETTLED DEFERRAL** | Ledgered cycle 1; not re-raised this cycle. |
| Cannot statically verify the next batch's invocations | ⚪ Low 1/4 | **DISCARDED** | Ledgered cycle 1; Bob did not re-raise it (his cycle-2 VERIFY bucket is empty). |

### Discarded (not defects)

- 🟡 The `mech-check` fail-first replay row (6 of 8 touched tests pass at `be7da2c`). Task 5's whole
  contract was to strengthen pins over prose cycle 1 had already shipped, so a pin over
  already-correct prose necessarily passes against a base carrying that prose; its value is failing
  on a future deletion, which task 5's acceptance criteria verified by temporary local edit. This is
  the replay block's own documented carve-out. The two tests covering task 4's **new** prose
  (`test_tess_retry_prompt_carries_the_narrow_sentence`,
  `test_adversarial_prompt_carries_narrow_in_feedback_section`) **do** fail at base, which is the
  correct fail-first signal for what this diff added. Alice reviewed the same block, accepted it for
  this reason, and passed R2. Ledgered as `discarded`; **kept in the table above** rather than
  hidden, and excluded from the tail sweep.

### Verification-check queue

**No `00232-…-checks-2.json` was written.** Bob's doubt lens emitted `VERIFY: - (none)` this cycle,
and Eve is not on this roster, so no VERIFY item existed to queue. An absent queue file means no
checks and is never an error. Nothing was routed to verification, so the tail sweep's selection
excludes nothing on that ground.

## Alice

Consensus lens, implementation-aware. 2 findings: 1 🟡, 1 ⚪.

Checks she ran: the five narrow-run-adjacent test files at HEAD `f5c0bd2` — **63 passed**. She
verified each cycle-1 finding against the code and reported the closure evidence reproduced in the
table above, including the exact new line numbers
(`tess-retry-prompt.md:34`, `adversarial-test-prompt.md:96`,
`test_narrow_runs_prose.py:151` replacing the old index-ordering check). She reviewed the
fail-first replay block explicitly and accepted it as a behavior-preserving artifact of pinning
already-shipped prose.

R1: pass
R2: pass
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: pass
R10: pass
R11: pass
R12: pass
R13: pass

## Blake

Blind lens — PRD only, no diff, no file list, no review history. He located the code himself.
1 finding: 1 ⚪.

Checks he ran: both PRD acceptance greps (1 per file, as specified); `test_narrow_runs_prose.py`
(**8 passed**); `test_review_prompt_contracts.py`, the tool-discipline parity suite (**12 passed**).
He confirmed NARROW is verbatim and adjacent after the anchor paragraph in
`skills/work/references/tess-prompt.md:47` and `agents/ivan.md:73` with the tool-discipline
paragraph untouched; Devon's runner line (`adversarial-test-prompt.md:31`), Context Selection row
(`:69`) and last rule (`:54`) matching the PRD text exactly; the rework-mode sentence at
`skills/work/SKILL.md:71` directly after its predecessor; the CHANGELOG `[Unreleased]`
`### Changed` `**work**` line at `CHANGELOG.md:12`; and the prose test wired at
`dev/bin/release-checks:26`. He did not re-run `release-checks`, per the narrow-run instruction in
his own run inputs.

B1: pass
B2: pass
B3: pass
B4: pass
B5: pass
B6: fail
B7: pass
B8: pass
B9: pass
B10: pass
B11: pass
B12: pass
B13: pass
B14: pass
B15: pass
B16: pass
B17: pass
B18: pass
B19: pass

B16 (Phase 2 acceptance) now **passes** — it failed in cycle 1 on the unpinned-literal gap, which
task 5 closed. B6 (no functionality beyond the PRD) is his one fail, and it is the scope row above:
deferred, not fixed, because reverting the extras would re-open the cycle-1 🟠.

## Bob

Doubt + de-slop lens on codex (static-only sandbox), first run, exit 0, no retry, resumed cycle-1
thread `01a0f47b`. 2 findings: 2 🟡. Thread id re-emitted for a possible cycle-3 resume.

R1: fail
R2: fail
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: fail
R10: pass
R11: pass
R12: pass
R13: pass

His R1/R2/R9 fails rest on the fence-placement coverage gap, which is the 🟡 row he and Alice share
— not on any new High. Both of his issue lines are 🟡, and his own FIX bucket names only those two
items, so nothing he raised blocks convergence under the severity bar. R4 and R9 moved from fail to
pass on the Tess-retry closure; R9's remaining fail is the same fence gap.

FIX:
- Feedback pin does not enforce fence placement — skills/work/scripts/test_narrow_runs_prose.py:146 — Extract the fenced body under "Feedback to Tess" and assert NARROW occurs inside it, immediately after the specified instruction and before the closing fence.
- Redundant whitespace stripping — skills/work/scripts/test_narrow_runs_prose.py:182 — Remove `.rstrip()` after `_norm(rules_section)`.

VERIFY:
- (none)

KNOWN:
- (none)

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

All three cycle-1 FIX items are closed by his own reckoning: he re-raises neither the Tess-retry
omission nor the literal-pin gap nor the location-scoping gap, and his cycle-1 VERIFY and KNOWN
items are both absent this cycle.

## Carl

Gemini lens via the copilot backend, exit 0. Non-empty reviewer text.

`[CARL] ✅ No issues found`

R1: pass
R2: pass
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: pass
R10: pass
R11: pass
R12: pass
R13: pass

Checks he ran: the five-file targeted work-skill suite; direct reads of `tess-retry-prompt.md`,
`adversarial-test-prompt.md`, `test_narrow_runs_prose.py`, `test_render_prompt.py`,
`test_devon_round_prose.py`, `test_command_budget_prose.py`, `dev/bin/release-checks` and
`CHANGELOG.md`; `git log` over the diff range; and greps confirming NARROW present in both newly
edited prompts and `"Run the test suite against your wrong implementation"` gone. He did not run
`release-checks`, as instructed — which also avoided cycle 1's nested-dispatch artifact.

## Orchestrator's own verification

Run in this session, not taken on trust:

- **Full suite, foreground:** `uv run --no-project --with pytest python -m pytest -q
  --continue-on-collection-errors hooks skills` → **4195 passed, 1 skipped, 3 errors**, 1049
  subtests passed, 283.78s. The 3 errors are the settled-discarded `ModuleNotFoundError: No module
  named 'rich'` collection failures in `tracon/test_panels.py`, `test_screens.py` and
  `test_stream.py`. Zero test failures.
- **Why the suite ran at all:** `docs/dev/project-management/autopilot/last-verification.json`
  carries the right `sha` (`f5c0bd2…`) but **null `passed`/`failed`/`skipped`**, so the reuse
  precondition fails and a fresh run was mandatory. Fail loud: the counts in the `Tests:` line below
  are this cycle's own run, not a reused record.
- **Correction to the reviewer prompts:** Alice's and Carl's assembled prompts stated the recorded
  verification as "4192 passed, 0 failed, 1 skipped". That number was the orchestrator's inference
  from cycle 1's collect count, not a value present in `last-verification.json` (whose counts are
  null). The real measured figure is 4195 passed / 0 failed / 1 skipped. Neither reviewer's verdict
  depended on it — both ran their own narrow test selections and reported those counts — but the
  slip is recorded here rather than left in the prompts unremarked.
- Working tree clean before and after this review; no reviewer modified the repo.

## Follow-up Tasks Created

Step 7 created **no** per-finding tasks this cycle. The cycle converges (no unresolved 🔴/🟠), so the
Medium/Low tail is owned by the Phase 5 **tail sweep**, which builds ONE `[D2]` task. Creating
per-finding tasks here as well would double-implement the same three findings.

1. `[D2] Tail sweep: anchor the remaining narrow-run pins to their sections` — the three actionable
   Medium/Low rows (fence placement, redundant `.rstrip()`, unpinned step-3 wording and Rule 6
   rejoin). Excluded from the sweep: the `mech-check` replay row (discarded) and Blake's scope row
   (deferred).

No 🔴 CRITICAL was raised, so no rework design doc was required and none was written
(`phase-review.md` Phase 6 § Dispatch rework).

## Decision gate

Convergence test: **CONVERGED.** No unresolved 🔴 CRITICAL and no unresolved 🟠 High remains — the
cycle-1 🟠 is closed and verified three ways, and every cycle-2 row is 🟡 or ⚪, which never block
convergence. `state.cycle` is 2 and `state.rework_cap` is 2, so the cap would have fired on a
non-convergent cycle; because the cycle converged, the cap is irrelevant and the gate proceeds to
the tail sweep and the finalize hand-off rather than the interactive cap-pause.

Deferred to batch end (1 new this cycle, ledgered as a settled deferral):

- ⚪ Blake's scope row — the PRD's four-file enumeration versus the universal claim in the sentence
  the PRD mandates at `skills/work/SKILL.md:71`. Same root as the cycle-1 deferral of the Devon
  "same sentence" inconsistency; both want one spec decision against the PRD text, not a code fix.

Carried forward unchanged from cycle 1: 3 deferrals (the Devon "same sentence" PRD inconsistency,
NARROW's pytest-only flags and ambiguous antecedent, and `skills/fast-track/SKILL.md:495`).

Discarded this cycle (1, ledgered): the `mech-check` fail-first replay row, for the
behavior-preserving reason recorded above.

Verdict: 5 findings
Tests: 4195 passed, 0 failed, 1 skipped (suite run this cycle)
