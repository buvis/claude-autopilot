---
prd: docs/dev/project-management/prds/wip/00248-keep-phase-skills-in-the-session-v1.md
review: 2
date: 2026-10-04
head_sha: 8c0ad1af33f82d7f5524f9d9f34f3a2fe5f97f12
codex_thread_id: 01a10746-a6a6-7230-b5b4-9e1f2c891be7
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00248-keep-phase-skills-in-the-session-v1

Diff range: `9c0150af9b5f8b05ff85fcae56eb6ee78a98d186..8c0ad1af33f82d7f5524f9d9f34f3a2fe5f97f12`

codex_rung_guard: not fired

Cycle 2, **incremental** review of the cycle-1 rework (tasks 5-8) since cycle 1's
`head_sha`. All four reviewers ran: Alice (consensus, Claude subagent), Blake
(blind, PRD-only), Bob (doubt + de-slop, codex, fresh thread - cycle 1 captured
no thread id), Carl (consensus, Gemini on copilot, exit 0, non-empty review).
Eve did not run: the codex doubt-roster guard did not fire (no task has a codex
implementor). Consensus engine: `legacy`.

Pack: `docs/dev/tmp/engram-pack-00248-c2.md` (2783 tokens).

## Consolidated Findings

12 findings after consolidation (0 🔴, 2 🟠, 5 🟡, 5 ⚪). `consolidate_findings.py`
merged three groups on suffix-stripped citations; the merges are noted below the
table because one of them folded three materially different claims about
`guard_phase_delegation.py` into a single [3/4] row.

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [3/4] | 🟠 | The predicate fix narrows the deny surface more than the PRD's candidate signals imply. Tight forward adjacency plus a colon-gated reverse form now ALLOWS "Do the work phase for PRD 7", "Start the work phase now" and "Complete the work phase". Only run/execute/invoke/follow/continue/resume plus the jargon is denied. All four observed fixtures still deny, so the PRD's acceptance holds. This is an accepted-gap tradeoff, but no test documents it, and the design doc's Risks section still describes the old bidirectional 40-char gap. Blake's own 🟠 folded here: a negation word within 20 characters before the match, in the SAME sentence, suppresses a real delegation - orchestrator-confirmed, `"Never stop, run the work phase for PRD 7."` returns False (allowed). | hooks/guard_phase_delegation.py:62 | 5 | ALICE, BLAKE, BOB |
| [2/4] | 🟡 | The non-string fail-open fix in the predicate has no discriminating test. `is_phase_delegation` now ignores non-string fields (hooks/guard_phase_delegation.py:103), but the only test touching it is `test_non_string_prompt_never_crashes_the_hook`, which uses `{"prompt": 5}`. That passes against the pre-change code too (the fail-first replay lists it), because `5` stringifies to a harmless "5". The cycle-1 repro `{"prompt": ["run plan-tasks"]}` is still uncovered. If the `isinstance` guard were reverted no test would fail. Add list and dict cases carrying delegation text and assert False. | hooks/test_guard_phase_delegation.py:276 | 6 | ALICE, BOB, mech-check |
| [2/4] | ⚪ | `_REVIEWER_FIXTURES` is built at import from a glob, and an empty glob parametrizes to a silently skipped test. `test_committed_allowed_prompts_pass_the_hook_in_the_loop` asserts 24 files in total, but nothing asserts the reviewer-* subset is non-empty. If the reviewer-* files were renamed, the allow-set gate would skip instead of fail - the same vacuous shape task 6 was meant to close. Assert the count (4), as `_denied()` now does. Blake adds that the hard-coded `len(samples) == 24` breaks on any fixture add/remove, and that no Watcher prompt is covered. | hooks/test_guard_phase_delegation.py:137 | 6 | ALICE, BLAKE |
| [1/4] | 🟠 | Prior reviewer-blocking HIGH remains: `blake-prompt-00248-c1.md:23` contains "Execute work phase", which the tightened pattern still denies. The new Blake fixture contains no embedded specification, and the dispatch corpus still excludes every prompt mentioning the guard. | hooks/guard_phase_delegation.py:62 | 5 | BOB |
| [1/4] | 🟡 | The predicate misses other wordings. Probes that returned False: "Run /work for PRD 3", "Run the PRD 5 work phase.", "Execute work for PRD 00242 task by task" and "Run work-phase tasks 1-5". The `_PHASE_JARGON_TIGHT` pattern needs the verb directly next to "work phase". The PRD accepts "delegation by other words" as a risk, but the post-release signal is the only backstop. | hooks/guard_phase_delegation.py:62 | 1 | BLAKE |
| [1/4] | 🟡 | The `work/SKILL.md` STOP-line addition departs from the spec text. The PRD says to add "In loop mode a hook enforces this (`hooks/guard_phase_delegation.py`)." The implementation says the hook "denies dispatching a whole phase skill... it does not enforce the one-task-per-dispatch rule in general". This is more accurate, because the hook does not enforce one task per dispatch. The test pins the reworded text, so the PRD's sentence is not present. | skills/work/SKILL.md:51 | 2 | BLAKE |
| [1/4] | 🟡 | New negation cases all pass against cycle 1 and cover none of the newly recognized contractions. The "negated first match" test contains no negated delegation match, so scanning past one remains untested. | hooks/test_guard_phase_delegation.py:204 | 6 | BOB, mech-check |
| [1/4] | 🟡 | Gate-prose test checks banned words and imperative counts on the hard-coded expected paragraph; these assertions cannot fail. Remove them while retaining actual-file equality, uniqueness, placement, and neighbour checks. | hooks/test_guard_phase_delegation.py:361 | 6 | BOB |
| [1/4] | 🟡 | Bob's sentence-boundary variant: the trim takes the FIRST boundary, not the last, so `"OK; not now. Run the work phase for PRD 7."` retains "not" and allows the delegation. Orchestrator-confirmed: returns False. Same root cause as the [3/4] 🟠 row's negation half. | hooks/guard_phase_delegation.py:86 | 5 | BOB |
| [1/4] | ⚪ | The `phase-build.md` sentences differ slightly from the spec. Phase 2 reads "Invoke `/autopilot:plan-tasks` with the selected PRD, using the Skill tool in this session; never delegate planning to an Agent." Phase 3 reads "...never delegate work execution to an Agent. It runs until all tasks complete." The PRD asked for the same sentence in both phases. Meaning is preserved. | skills/run-autopilot/references/phase-build.md:344 | 2 | BLAKE |
| [1/4] | ⚪ | Accepted predicate and prose limitations remain: quoted examples and task-boundary wording can match; STOP prose, verb widening, and generic denial wording deliberately differ from PRD examples. | hooks/guard_phase_delegation.py:30 | general | BOB |
| [1/4] | ⚪ | `test_phase_3_records_git_dir_for_the_bare_repo_case` and `test_spawn_scrub_notice_sorts_multiple_markers_comma_space_joined` pass against the pre-change code (fail-first replay). Both are behavior-preserving by design - the first re-anchors on task 7's merged sentence, the second is task 8's revert of a reflow - so neither is a defect. Recorded, not actioned. | skills/run-autopilot/cli/test_custody_prose.py:164 | 7 | mech-check |

Consolidator merge notes (suffix-stripped citation matches, verbatim from its
stderr):

- row 1: `guard_phase_delegation.py:62 ~ :135 ~ :77 ~ :86`
- row 2: `test_guard_phase_delegation.py:276 ~ :35`
- row 3: `test_guard_phase_delegation.py:137 ~ :123`

Row 1's merge is coarse: Alice's accepted-gap ⚪, Blake's negation 🟠 and Bob's
reviewer-blocking 🟠 are three different claims. Bob's was split back out as its
own `[1/4]` row above; Blake's was folded into row 1's text rather than lost.

## Orchestrator verification

Every claim below was probed directly against `hooks/guard_phase_delegation.py`
at the reviewed HEAD, not taken on trust.

**Cycle 1's 🟠 HIGH is materially fixed, residually open.** The probe over
`docs/dev/tmp/*-prompt-*.md` now denies **5 of 235** prompts, down from 21 of
231 in cycle 1. All five are *this PRD's own* review prompts
(`alice-prompt-00248-c2.md`, `blake-prompt-00248-c1.md`,
`blake-prompt-00248-c2.md`, `bob-prompt-00248-c2.md`,
`carl-prompt-00248-c2.md`), each of which quotes the denied phrases verbatim
because it is a review *of this guard*. Every ordinary reviewer prompt in the
corpus - 230 of them, Alice, Blake, Bob and Carl prompts across 00160, 00187,
00188, 00189, 00215 and more - is now allowed. The PRD's requirement ("allow the
review roster's Alice, Blake and Watcher prompts") therefore holds for every
prompt that does not quote a delegation; it does not hold for a prompt reviewing
the guard itself. Bob's HIGH is real at that narrowed scope.

**Blake's 🟠 negation false-negative: CONFIRMED.**
`"Never stop, run the work phase for PRD 7."` → `False` (allowed). The clause
"Never stop," sits within the window and is read as a prohibition on the verb
that follows it.

**Bob's sentence-boundary 🟡: CONFIRMED.**
`"OK; not now. Run the work phase for PRD 7."` → `False` (allowed). The trim
cuts at the first boundary rather than the last.

**Cycle 1's negation repro is fixed.**
`"Do not wait for me. Run the work phase for PRD 7."` → `True` (denied), where
cycle 1 measured `False`.

**Cycle 1's non-string fail-open repro is fixed.** `{"prompt": ["run
plan-tasks"]}` → `False`, `{"description": {"a": "execute the work phase"}}` →
`False`, `{"prompt": 5}` → `False`. Alice and Bob are right that no test would
fail if the `isinstance` guard were reverted.

**The four observed delegations still deny.**
`"Execute work phase for harden-wave-verbs PRD 00242"` → `True`.

**Blake's ⚪ release-checks failure: REFUTED.** Blake, Carl and this
orchestrator all saw `dev/bin/release-checks` exit 1 on a first run, with three
*different* failure sites (a bare-repo store-commit subprocess rc=255, five
`test_gemini_run.sh` cases with `Cannot allocate memory` / `fork: retry:
Resource temporarily unavailable`, and a `git rebase` killed with rc=-9). All
three are resource exhaustion from four reviewers plus an xdist suite running
concurrently, not defects. A clean re-run with nothing else in flight exits
**0**. Carl's own re-run also exited 0. Not a finding.

**Bob's ⚪ "cannot statically verify": RESOLVED.** Both PRD gate commands were
run by this orchestrator at the reviewed HEAD
(`8c0ad1af33f82d7f5524f9d9f34f3a2fe5f97f12`): the named pytest command gives
245 passed, and `bash dev/bin/release-checks` exits 0. Results are written into
`-checks-2.json`.

## Carry-forward of cycle 1's verification checks

`-checks-1.json` queued two checks and neither carried a `result`: cycle 1's
rework ran as orchestrator-direct edits, so no `/autopilot:work` step 7 ever ran
them. Per the carry-forward rule an unrun entry returns as a finding. **Stated
plainly: rather than file them as findings, this orchestrator ran both commands
itself at the reviewed HEAD and both passed** (245 passed; release-checks exit
0). They are recorded as resolved in `-checks-2.json` with the SHA they ran at,
not as cycle-2 findings. No check in this PRD's history is unrun.

## Alice

Four findings (1 🟡, 3 ⚪), no Critical or High of her own. She verified the
cycle-1 HIGH is mostly closed by re-running the probe (5 of 235, down from 21 of
231) and accepts the residual self-referential denials as a tradeoff, while
noting nothing pins the exclusion list small. Her one 🟡 is that the non-string
fix has no discriminating test.

R1: fail
R2: fail
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

Seven findings, one 🟠. He found the code himself and confirmed the hook, its
`Agent` registration at `hooks/hooks.json:39`, the 4 denied plus 24 allowed
fixtures, the `CLI_SUFFIX` sentence at `skills/run-autopilot/cli/runner.py:83`
with `prompt_for` unchanged, the release-checks line at `dev/bin/release-checks:41`
and the CHANGELOG entry at `CHANGELOG.md:12`. His 🟠 is the "Never stop, run
the work phase" false negative, confirmed above. His B16 fail is the Phase 2
acceptance criterion read literally; his release-checks ⚪ is refuted above.

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

## Bob

Seven findings (1 🟠, 4 🟡, 2 ⚪) plus the doubt buckets. Static-only, as his
sandbox requires. Ran on a fresh codex thread (cycle 1 captured no thread id).

FIX:
- Reviewer-blocking HIGH remains — hooks/guard_phase_delegation.py:62 — Commit the actual failing Blake prompt, distinguish its quoted specification from execution instructions, and restore excluded real dispatches to the allow gate.
- First-boundary trimming permits delegation — hooks/guard_phase_delegation.py:86 — Trim after the last boundary and add the multiple-boundary example above.
- Non-string behavior is unpinned — hooks/test_guard_phase_delegation.py:276 — Add list/dict delegation-text cases in both input fields that fail against cycle 1.
- Negation coverage misses changed behavior and scanning — hooks/test_guard_phase_delegation.py:204 — Add newly supported contractions and "Do not run plan-tasks. Run the work phase for PRD 7."
- Constant gate assertions add redundancy — hooks/test_guard_phase_delegation.py:361 — Remove checks against expected-string literals; retain checks against file contents.

VERIFY:
- Runtime acceptance at reviewed HEAD — Run `uv run --no-project --with pytest python -m pytest -q hooks/test_guard_phase_delegation.py skills/run-autopilot/cli/test_runner.py`, then `bash dev/bin/release-checks`; retain SHA, exit codes, and counts.

KNOWN:
- Other accepted predicate/prose limitations — The design and assumptions explicitly accept these; broader semantic classification and wording churn exceed tasks 5-8. This excludes the concrete reviewer-blocking requirement above.

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
D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

Backend: copilot (`gemini-run.sh`, exit 0), non-empty review.
`[CARL] ✅ No issues found`, all twelve rubric rules pass. He executed both PRD
acceptance commands himself (245 passed; release-checks exit 0 on his re-run
after a first resource-starved failure) and judged every cycle-1 finding
resolved. No frontend surface in this diff, so he reviewed as a generalist and
invented no frontend findings. His clean verdict is the outlier against Alice,
Blake and Bob; the orchestrator probes above side with the three.

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

## Mechanical blocks

- **Tautological test shapes**: clean. 63 test functions checked across 3 test
  files, zero `[MECH]` lines. Cycle 1's four vacuous `_denied()` loops and two
  hedged asserts are gone - task 6 closed them.
- **Fail-first replay**: 11 touched tests ran, 4 failed against base, 7 passed.
  Three `[MECH]` rows, all absorbed into the table above: two into existing rows
  (the non-string test and the negation tests), one as its own ⚪ row for the two
  behavior-preserving re-anchors.

## Verification-check queue

Two entries in
`docs/dev/project-management/reviews/00248-keep-phase-skills-in-the-session-v1-checks-2.json`
(source `bob`). **This cycle is a cap-out: there is no rework pass, so step 7
never runs.** Both were therefore run by this orchestrator at the reviewed HEAD
and their results written into the queue file - exit 0 each. Nothing is left
unrun.

## Pre-existing suite failures (not this PRD's)

Unchanged from cycle 1, and cycle 1 reproduced both at the PRD base `36e236ba`
in a throwaway worktree:

- `skills/work/scripts/test_dispatch_prose.py::test_work_skill_body_stays_under_the_500_line_ceiling`
- `skills/work/scripts/test_dispatch_telemetry_prose.py::test_step_6_5_writes_the_leave_row_before_the_stop`

Two further environmental collection problems are excluded from the count, and
neither is this PRD's: three `skills/run-autopilot/scripts/tracon/test_*.py`
ImportErrors (missing optional dep), and ~127 `docs/dev/tmp/` collection errors
from stale scratch copies of the repo's own test files under
`docs/dev/tmp/render-pin-check/`. Neither tree is wired into
`dev/bin/release-checks`, which is why the PRD's own gate is green while a bare
`pytest` at the repo root is not.

Verdict: 12 findings
Tests: 4571 passed, 2 failed, 1 skipped (suite run this cycle, --ignore=docs/dev/tmp --ignore=skills/run-autopilot/scripts/tracon; both failures reproduce at base 36e236ba and are not this PRD's)
