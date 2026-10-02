---
prd: docs/dev/project-management/prds/wip/00232-keep-subagent-test-runs-narrow-v1.md
review: 1
date: 2026-10-01
head_sha: be7da2c09fae53f7bda5760673b927dcd3bd7914
codex_thread_id: 01a0f47b-aab5-79a1-b1d5-648ad5808d77
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00232-keep-subagent-test-runs-narrow-v1

Diff range: `072cc7a70cacec18f5b935e3134758ab1c702aff..be7da2c09fae53f7bda5760673b927dcd3bd7914`

codex_rung_guard: not fired

pack: unavailable this cycle (`engram pack` exited 1: "not inside a registered repo; register it in
`/Users/bob/.config/gita/repos.csv`"). Every prompt that takes `{PACK_FILE}` / `{PACK_FINDINGS}`
received the sentinel `(no pack available this cycle)`. The retry was skipped deliberately: the error
is a deterministic registration gap, not a transient failure. Blake never receives a pack by design.

Diff-scope note: `gather-context.sh` was run with `--since <work_start_sha>` rather than bare. This is
a **cycle-1 full review**, not an incremental one — the repo commits straight to `master`, so the
script's default base (`git diff master`) produced an EMPTY diff on the first run. The explicit base
is `state.work_start_sha`, giving the PRD's whole work range. There is no prior review cycle.

## Review Summary

Reviewed: 3 completed tasks
PRDs checked: 00232-keep-subagent-test-runs-narrow-v1.md

### Agent Status

- Alice: ✅ Available (Claude subagent, consensus engine `legacy`)
- Blake: ✅ Available (Claude subagent, blind/PRD-only)
- Bob: ✅ Available (codex, doubt + de-slop; exit 0, first run, no retry)
- Carl: ✅ Available (gemini via copilot backend, model `gemini-3.8-flash`; exit 0)

All four lenses ran. No reviewer failed, so no fallback and no degradation.

## Consolidated Findings

`consolidate_findings.py` emitted 9 rows; this table carries 8. **One merge was applied by the
decision gate and is recorded in `autonomous_decisions`:** Bob's 🟠 row cited
`skills/work/SKILL.md:71` (the false claim) while Alice's and Blake's cited
`skills/work/references/tess-retry-prompt.md:32` (the omission that makes it false). The script merges
paraphrases only when they name the same file, so a defect cited at its cause and at its symptom stays
split. They are one finding; merged, its consensus is 3/4, not 2/4.

No ledger existed on entry (cycle 1), so `--ledger`/`--ledger-dismiss` were correctly omitted.
Carry-forward: no `checks-0.json` exists (cycle 1) — nothing to carry.
Mechanical test checks: **both blocks produced zero `[MECH]` lines**, so nothing was absorbed.

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [3/4] | 🟠 High | Narrow-run rule never reaches the Tess quality-gate retry prompt or the "Feedback to Tess" strengthen template, so the PRD-mandated sentence at `SKILL.md:71` ("every subagent prompt (Tess, Devon, Ivan): each carries the same narrow-run sentence") is false as shipped. Of up to 4 Tess dispatches per task (`SKILL.md:243`: 1 initial + 2 quality-gate retries + 1 strengthen) only the initial one carries it. Devon also carries reworded prose, not the same sentence. | skills/work/references/tess-retry-prompt.md:32 | general | Alice, Blake, Bob |
| [3/4] | 🟡 Medium | The test does not pin the NARROW literal. It holds only the opening clause plus cross-file equality between Ivan's and Tess's paragraphs, so an identical edit to both files stays green — including deleting "Never run a whole test directory or `dev/bin/release-checks`" and "never re-run a suite to recover a number" (the PRD's own acceptance grep). The PRD's Module Exports clause says the test "holds its literal as a constant and checks each file against it". "Directly after" is checked only as `index(narrow_start) > index(anchor)`, so NARROW below the `ASSUMPTIONS:` footer still passes. | skills/work/scripts/test_narrow_runs_prose.py:153 | 2 | Alice, Blake, Bob |
| [3/4] | 🟡 Medium | Devon coverage gaps: the changed Context Selection row has no test; `test_devon_rules_forbid_a_directory_run` and `test_devon_runner_is_the_tasks_test_files` match anywhere in the file rather than binding to the Rules list and the `Test runner command:` line; the `_section` helper the task's Reuse note prescribed is unused; the PRD's happy-path scenario (a `render_prompt.py` render contains NARROW once) is untested. | skills/work/scripts/test_narrow_runs_prose.py:189 | 2 | Alice, Blake, Bob |
| [3/4] | 🟡 Medium | The PRD-mandated `SKILL.md:71` sentence asserts every subagent prompt carries "the same narrow-run sentence", but the PRD's own Devon feature specifies *different* wording for Devon. The claim cannot be made true for Devon without either rewording the mandated sentence or giving Devon the NARROW paragraph. Internal PRD inconsistency. | skills/work/SKILL.md:71 | general | Alice, Blake, Bob |
| [2/4] | ⚪ Low | Devon's template still says in Process step 3 "Run the test suite against your wrong implementation" and in Rule 1 "the tests", which sits against the new Rule 6 and invites a whole-suite read. Rule 6 is also hard-wrapped mid-sentence across two lines while Rules 1-5 are single lines. | skills/work/references/adversarial-test-prompt.md:44 | 1 | Alice, Blake |
| [2/4] | ⚪ Low | NARROW hard-codes pytest flags (`-q --tb=line`) in a stack-agnostic pack (`final-verification.md:16` covers cargo/npm, where `--tb=line` is invalid), and "Read the pass count and exit code from that one run" has an ambiguous antecedent — it follows "the orchestrator runs the full suite once", which is the run the subagent cannot read. Devon's example runner has the same pytest-only slant after the npm/cargo examples were dropped. | skills/work/references/tess-prompt.md:47 | 1 | Alice, Blake |
| [1/4] | ⚪ Low | The fast-track lane reuses `agents/ivan.md`; its rework `RETRY_INSTRUCTION` ends "keep the suite green", which pulls Ivan toward the whole-suite run the new sentence forbids. Not caused by this PRD, but now contradicted by it. | skills/fast-track/SKILL.md:495 | general | Blake |
| [1/4] | ⚪ Low | Cannot statically verify: the next batch contains no Tess, Devon, or Ivan whole-directory or `release-checks` invocations. | N/A | general | Bob |

### Discarded (not defects)

- ⚪ Bob's "Cannot statically verify the next batch" row restates the PRD's own third Success Metric, an explicitly **post-release** signal measured in the next batch's `last-session.log`. Unevaluable pre-release by construction. Ledgered as `discarded`.
- ⚪ Bob's row confirming the collection errors are pre-existing **corroborates** the build session rather than contesting it. Ledgered as `discarded`.

### Verification-check queue

**No `00232-…-checks-1.json` was written: no VERIFY item qualified.** Bob's doubt lens emitted exactly
one VERIFY item — "Inspect each Tess, Devon, and Ivan Bash invocation in the next batch's
`last-session.log`". That names an inspection of an artifact that does not exist yet, not one runnable
project verification command, so per the queue's command-shape rule it is **not queued: command
shape**. It stays an ordinary finding and was discarded above. An absent queue file means no checks and
is never an error.

## Alice

Consensus lens, implementation-aware. 5 findings: 1 🟠, 2 🟡, 2 ⚪.

Checks she ran: the touched and adjacent prose and render tests (`test_narrow_runs_prose`,
`test_command_budget_prose`, `test_dispatch_prose`, `test_tess_size_limits_prose`,
`test_devon_round_prose`, `test_adversarial_cap_prose`, `test_style_gate_prose`,
`test_step_order_prose`, `test_render_prompt`, plus both fast-track render and wiring tests) —
**120 passed**. She confirmed the tool-discipline paragraph is unchanged, that
`dev/bin/release-checks:26-28` wires the new test in the work-skill prose block, and that NARROW, the
Devon line, the Context Selection row, Rule 6, the SKILL.md sentence and the CHANGELOG bullet all match
the PRD text verbatim. She independently reproduced the collection-error finding: exactly 3, all
`ModuleNotFoundError: No module named 'rich'`, unrelated to this PRD.

R1: fail
R2: fail
R3: pass
R4: fail
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
6 findings: 2 🟡, 4 ⚪. No Filesystem-notes block was needed (project root is not a dot-directory and
`docs/dev/project-management` is not a symlink).

Checks he ran: both PRD acceptance greps (1 per file, as specified); the narrow-run prose test (4
passed); `pytest skills/work/scripts` (643 passed, 1 skipped); `pytest skills/fast-track/scripts
skills/run-autopilot/scripts/test_fablectl.py` (251 passed); `bash dev/bin/release-checks` to its last
step with no failure, the new "narrow runs prose" block printing 4 passed; and a `render_prompt.py`
render of `tess-prompt.md` with all placeholders filled, which contains the narrow sentence **exactly
once** — so the PRD's happy-path scenario does hold in reality, it is simply not automated.

B1: pass
B2: pass
B3: pass
B4: pass
B5: pass
B6: pass
B7: pass
B8: pass
B9: pass
B10: pass
B11: pass
B12: pass
B13: pass
B14: pass
B15: pass
B16: fail
B17: pass
B18: pass
B19: pass

B16 (Phase 1 acceptance) fails on the unpinned-literal finding: the named test is green but lacks the
PRD's parenthetical contract and the Module statement that the test holds the literal as a constant.
B4 passes only because the PRD states no measurable pre-release threshold.

Left behind by Blake: `/tmp/blake-tess-render.md`, a scratch render from his happy-path check.

## Bob

Doubt + de-slop lens on codex (static-only sandbox), first run, exit 0, no retry.
5 findings: 1 🟠, 2 🟡, 2 ⚪. Thread id captured for cycle-2 resume.

R1: fail
R2: fail
R3: pass
R4: fail
R6: pass
R7: pass
R8: pass
R9: fail
R10: pass
R11: pass
R12: pass
R13: pass

FIX:
- Tess redispatches omit the rule — skills/work/SKILL.md:71 — Add the narrow-run instruction to tess-retry-prompt.md and the Feedback to Tess template, with prose coverage.
- Tess/Ivan pin accepts incomplete or displaced instructions — skills/work/scripts/test_narrow_runs_prose.py:41 — Compare each paragraph against a full NARROW constant, require exactly one occurrence, and assert immediate adjacency to tool discipline.
- Remaining pins ignore required locations — skills/work/scripts/test_narrow_runs_prose.py:77 — Scope Devon assertions to the template and Rules list, assert the Context Selection row, and check the rework sentence immediately follows its specified anchor.

VERIFY:
- Next-batch narrow-run behavior — Inspect each Tess, Devon, and Ivan Bash invocation in the next batch's last-session.log; verify every test command targets task test files and none invokes release-checks or a whole test directory. (**not queued: command shape**)

KNOWN:
- Tracon collection errors — Missing rich affects unchanged imports present at the base revision; repairing the verification environment is outside this prose-rule PRD.

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

Gemini lens via the copilot backend, model `gemini-3.8-flash`, exit 0. Non-empty reviewer text.

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

**Context for Carl's transcript, not a finding against this diff:** Carl's first `bash
dev/bin/release-checks` reported `SUMMARY: 6 passed, 20 failed` in the "runner recursion guard" block.
That is an artifact of running the gate *inside* a nested reviewer dispatch — his environment carried
`AUTOPILOT_DISPATCH_DEPTH`/`COPILOT_CLI`, so `codex-run.sh` correctly refused with "refusing nested
dispatch (depth=1)" and every stub assertion saw an empty capture. He diagnosed this himself and
re-ran with `env -u AUTOPILOT_DISPATCH_DEPTH -u COPILOT_CLI -u CODEX_SESSION_ID -u _AUTOPILOT_LOOP`.
The orchestrator's own recorded run of the same gate at this HEAD is exit 0. No defect here.

## Orchestrator's own verification

Run in this session, not taken on trust:

- `pytest --collect-only --continue-on-collection-errors hooks skills`: **4192 tests collected, 3
  errors**. All 3 are `ModuleNotFoundError: No module named 'rich'` in
  `skills/run-autopilot/scripts/tracon/test_panels.py`, `test_screens.py` and `test_stream.py` — none
  touched by this diff. The build session's "pre-existing and unrelated" claim is **confirmed**, three
  ways independently (orchestrator, Alice, Carl).
- `rg -o "Run only the test files this task names"` on `tess-prompt.md` and `agents/ivan.md`: exactly
  one occurrence each.
- `rg -c "never re-run a suite to recover a number"` across the four prompt files that carry the
  tool-discipline paragraph: present in `tess-prompt.md` and `agents/ivan.md`, **absent from
  `tess-retry-prompt.md`** — the evidence behind the 🟠.
- `SKILL.md:241/:243/:477` read directly: `tess-retry-prompt.md` is rendered by `render_prompt.py` for
  up to 2 quality-gate retries, and the total Tess budget is 4 dispatches. The "Feedback to Tess"
  fenced template at `adversarial-test-prompt.md:82-96` is a standalone strengthen prompt carrying
  neither the tool-discipline paragraph nor NARROW. The 🟠 is grounded, not inferred.
- Working tree clean before and after this review; no reviewer modified the repo.

## Follow-up Tasks Created

1. `[D1] Carry the narrow-run rule into the Tess retry and strengthen prompts` (S) — sonnet, task id 4
   — 🟠 3/4 plus the ⚪ Devon wording/wrap items.
2. `[D1] Pin the narrow-run prose to its literal and its anchors` (M) — sonnet, task id 5 — both 🟡 3/4
   test-pin findings; depends on task 4.

No 🔴 CRITICAL was raised, so no rework design doc was required and none was written
(`phase-review.md` Phase 6 § Dispatch rework).

## Decision gate

Convergence test: **not converged.** One unresolved 🟠 High remains (the Tess retry/strengthen
omission), which blocks convergence under the severity bar. `state.cycle` is 1 and `state.rework_cap`
is 2, so `1 < 2` — rework is allowed and the cap does not fire.

Deferred to batch end (3, each also ledgered as a settled deferral):

- 🟡 the PRD's internal Devon "same sentence" inconsistency — needs a spec decision, not a code fix.
- ⚪ NARROW's pytest-only flags and ambiguous "that one run" antecedent — the PRD mandates the sentence
  verbatim and the code reproduces it exactly, so the defect is in the spec.
- ⚪ `skills/fast-track/SKILL.md:495` "keep the suite green" — pre-existing, in a file this PRD neither
  touches nor names.

Verdict: 8 findings
Tests: 4191 passed, 0 failed, 1 skipped (reused from last-verification.json at be7da2c09fae53f7bda5760673b927dcd3bd7914)
