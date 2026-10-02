---
prd: dev/local/prds/wip/00160-route-opus-on-task-local-risk-v1.md
review: 2
date: 2026-09-02
head_sha: 0c0c80107c9d297d372ff2429f5cd57af4bd07e8
codex_thread_id: 01a05eca-ece4-7ae0-8d48-6d2ae0c09dd5
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00160-route-opus-on-task-local-risk-v1

Diff range: `c6c32130e44639d09336c73aa9a0b0576ac0d1c6..0c0c80107c9d297d372ff2429f5cd57af4bd07e8`

codex_rung_guard: not fired

pack: unavailable this cycle (`engram pack` exited 1: "not inside a registered repo; register it in /Users/bob/.config/gita/repos.csv"). Every prompt taking `{PACK_FILE}` / `{PACK_FINDINGS}` carried the literal `(no pack available this cycle)` instead. Not retried — the same deterministic registration precondition that failed in cycle 1, not a transient. Review is degraded on retrieval context, not invalid. Blake never receives a pack by design.

## Review Summary

Reviewed: 6 completed tasks (3 original-plan, 3 `[D1]` rework)
PRDs checked: 00160-route-opus-on-task-local-risk-v1
Scope: **incremental** — diff scoped to the six rework commits since cycle 1's `head_sha`.

### Agent Status

- Alice: ✅ Available (Claude subagent, consensus lens)
- Blake: ✅ Available (Claude subagent, blind/PRD-only lens)
- Bob: ✅ Available (codex, consensus + doubt/de-slop lens, resumed cycle-1 thread `01a05eca…`)
- Carl: ✅ Available (copilot backend, `-m auto`)

### Run notes (fail-loud)

1. **Carl was dispatched with `-m auto` up front**, not on the retry. Cycle 1 established that the roster default `gemini-3.1-pro-preview` is not served on this account (its dispatch failed exit 1 and needed the one retry). Dispatching at `-m auto` directly spent no retry budget, but it means **Carl again ran on a copilot-auto-selected model, not on Gemini** — a real fourth voice, not the Gemini voice the roster names.
2. **Bob resumed his cycle-1 codex thread** via `--resume-thread 01a05eca-ece4-7ae0-8d48-6d2ae0c09dd5`, so his cycle-2 output verifies fixes against his own cycle-1 critique rather than re-reviewing from zero.
3. **Bob's prompt again carried three sections of `agents/eve.md`, not the two SKILL.md names.** Same reason as cycle 1: the "Categorize every residual finding" section sits between "Two lenses" and "Rubric verdicts" and defines the FIX/VERIFY/KNOWN buckets the `D1`–`D5` verdicts score. Appending only the two named sections would leave the doubt lens's contracted output undefined.
4. **Native-lane prompts (Alice, Blake) were written to `dev/local/tmp/{agent}-prompt-00160c2.md` and also passed inline** in the Task dispatch, because a registered persona's `{PLACEHOLDER}` tokens are only filled by the run inputs the dispatch carries.
5. **Consolidation left one defect split across two rows.** `consolidate_findings.py` merged Alice's, Blake's and Carl's wording of the deleted-test-file defect into one `[3/4]` row but kept Bob's much shorter wording as a separate `[1/4]` row, despite the identical `File:`. Read as one finding it is **[4/4] — unanimous**. See "Judgment-call merge" below.
6. **No follow-up tasks created in this skill's step 7.** Under autopilot, Phase 5 classifies and Phase 6 creates the `[D2]` tasks and queues them in `state.rework_task_ids`; creating them here as well would double-create every finding. Same convention as cycle 1.
7. **Cycle-1 verification-check queue: all three entries ran and exited 0**, so the step-6 carry-forward added nothing to this cycle's table.
8. **Cycle counts are not comparable to cycle 1's.** Cycle 1's `Tests:` line read 2467 passed / 1 skipped; this cycle's record reads 2366 / 1. The gap is a different command set in the two `last-verification.json` records, **not a loss of tests**: collecting the identical four subtrees at both revisions gives **2351 at `c6c3213` → 2367 at HEAD (+16)**, and the classifier's own cases went **139 → 155**. Verified by orchestrator with a throwaway worktree at `c6c3213` (since removed).

## Consolidated Findings

`consolidate_findings.py`, 4 reviewers. No settled-decisions ledger exists for this PRD, so the `--ledger` flags were omitted.

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [3/4] | 🔴 | The PRD's own literal acceptance command (`uv run --no-project --with pytest python -m pytest -q skills/plan-tasks/scripts/test_classify_tier.py`) — stated in Phase 0's task, in Task 1's original acceptance criteria, and repeated verbatim as this cycle's Task 4 D1 rework acceptance bar — now exits 4 with "file or directory not found," confirmed by running it. The rework deleted `test_classify_tier.py` (grew past the repo's 800-line file cap once new coverage was added — the five split files total 879 lines, plus 77 in the new support module) and split it into five thematic `test_classify_tier_*.py` modules without leaving anything at the PRD-named path. Test coverage survived and was extended (verified empirically), so this is a naming/acceptance-criteria break, not a coverage regression, but it is a confirmed, unresolved deviation from the PRD text as written. | skills/plan-tasks/scripts/test_classify_tier.py | 4 | ALICE, BLAKE, CARL |
| [2/4] | ⚪ | `test_plan_tasks_prose.py`'s module docstring ("This file pins PROSE only. `test_classify_tier.py` covers the classifier.") still names the file this rework deleted. The reference is inert (a comment, not an assertion) but now points at a nonexistent path. | skills/plan-tasks/scripts/test_plan_tasks_prose.py | general | ALICE, BLAKE |
| [1/4] | 🟠 | Deleting the explicitly required `test_classify_tier.py` breaks the PRD's repository structure and exact pytest acceptance command | skills/plan-tasks/scripts/test_classify_tier.py | 4 | BOB |
| [1/4] | 🟡 | classify_tier.py's CLI rejects a negative --lines value with exit 1 (see test_the_cli_rejects_a_negative_lines_value), a third error path the PRD never specifies — the PRD's CLI Outputs section states only "exit 1 on a missing flag or unreadable file with the cause on stderr." The CHANGELOG entry itself flags this as an addition beyond the PRD text. Functionally defensible, but it is new functionality not called for by the spec. | skills/plan-tasks/scripts/classify_tier.py | Phase 0 | BLAKE |
| [1/4] | 🟡 | The contract and algorithmic-risk precedence tests are near-identical mirror functions; one parametrized test can preserve both cases without duplication | skills/plan-tasks/scripts/test_classify_tier_risk_flags.py:72 | 4 | BOB |
| [1/4] | 🟡 | The `tier_reason` row repeats both escalation ladders and their attempt fields; retain the plan-time invariant and caveat in one concise sentence | skills/run-autopilot/references/state-schema.md:187 | 6 | BOB |
| [1/4] | ⚪ | PRD 00160 is still parked in wip/ although the implementation is complete, all Phase 1/2 acceptance commands and the full release-checks pass — per the repo's own PRD-lifecycle rule this should move to dev/local/prds/done/ once verified. Process note, not a code defect. | N/A | general | BLAKE |
| [1/4] | ⚪ | Prose pins still cannot detect deliberately inverted meaning; cycle 2 does not touch this disclosed repo-wide limitation | skills/plan-tasks/scripts/test_plan_tasks_prose.py | general | BOB |

### Judgment-call merge for the decision gate

**Rows 1 and 3 are one defect described twice.** Both name
`skills/plan-tasks/scripts/test_classify_tier.py`; both say the rework deleted
the file the PRD names, breaking its literal acceptance command. The script kept
them apart only because Bob's one-line wording shares too few tokens with
Alice's paragraph. Read as one finding it is **[4/4] — every reviewer that ran,
including the blind lens that had only the PRD** — at a severity of 🔴 from
Blake and 🟠 from Alice, Bob and Carl.

This is the highest-consensus finding either cycle has produced, and it is a
**regression the rework itself introduced**: at cycle 1 the file existed and the
command passed.

### Blake's `wip/` finding is a false positive

Blake's `[1/4] ⚪` process note says PRD 00160 should already be in
`dev/local/prds/done/`. It should not: the wip→done move is Phase 9's verified
finalize step, which by construction has not run while the review gate is still
open. Recorded for the audit trail, not actionable.

## Alice

Ran the RED-check experiment the rework was given as its acceptance bar:
reordered the mechanical check ahead of the risk checks in `_tier_from_shape`,
ran the five split modules, got **10 failures** (both
`..._outranks_the_mechanical_rule_...` parametrized tests in
`test_classify_tier_risk_flags.py`), then restored the file and confirmed
`git diff` on it is empty. Cycle 1's 🟠 precedence-coverage gap is genuinely
closed, not merely renamed. Verified all 12 of cycle 1's consolidated findings
resolved in the code.

```
[ALICE] 🟠 The PRD's own literal acceptance command (`uv run --no-project --with pytest python -m pytest -q skills/plan-tasks/scripts/test_classify_tier.py`) — stated in Phase 0's task, in Task 1's original acceptance criteria, and repeated verbatim as this cycle's Task 4 D1 rework acceptance bar — now exits 4 with "file or directory not found," confirmed by running it. The rework deleted `test_classify_tier.py` and split it into five thematic modules without leaving anything at the PRD-named path. Test coverage survived and was extended, so this is a naming/acceptance-criteria break, not a coverage regression, but it is a confirmed, unresolved deviation from the PRD text as written. | File: skills/plan-tasks/scripts/test_classify_tier.py | Task: 4
[ALICE] ⚪ `test_plan_tasks_prose.py`'s module docstring still names the file this rework deleted. The reference is inert (a comment, not an assertion) but now points at a nonexistent path. | File: skills/plan-tasks/scripts/test_plan_tasks_prose.py | Task: general
```

```
R1: pass
R2: pass
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
```

## Blake

Blind lens, PRD-only prompt: no diff, no file list, no review history, no pack.
Located the implementation himself and **ran every acceptance command the PRD
names**, which is how the blind lens reached the same defect independently. He
also re-derived every Phase 0 fixture by loading `classify_tier.py` directly;
all matched the PRD's stated outputs exactly. `release-checks` exit 0.

```
[BLAKE] 🔴 The PRD's Phase 0 task and Repository Structure both name skills/plan-tasks/scripts/test_classify_tier.py as the deliverable, and the Phase 0 Acceptance line literally reads "uv run --no-project --with pytest python -m pytest -q skills/plan-tasks/scripts/test_classify_tier.py green". That file does not exist — running the command verbatim gives "ERROR: file or directory not found ... no tests ran". The tests were instead split into five differently-named files plus a shared support module, and the underlying tests do pass under those names, but the PRD's own named acceptance command fails as written. | File: skills/plan-tasks/scripts/test_classify_tier.py | Task: Phase 0
[BLAKE] 🟡 classify_tier.py's CLI rejects a negative --lines value with exit 1, a third error path the PRD never specifies — the PRD's CLI Outputs section states only "exit 1 on a missing flag or unreadable file with the cause on stderr." Functionally defensible, but it is new functionality not called for by the spec. | File: skills/plan-tasks/scripts/classify_tier.py | Task: Phase 0
[BLAKE] ⚪ test_plan_tasks_prose.py's module docstring still says "This file pins PROSE only. test_classify_tier.py covers the classifier," naming a file that no longer exists under that name after the test-file split. | File: skills/plan-tasks/scripts/test_plan_tasks_prose.py | Task: Phase 0
[BLAKE] ⚪ PRD 00160 is still parked in wip/ although the implementation is complete. Process note, not a code defect. | File: N/A | Task: general
```

```
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
B15: fail
B16: pass
B17: pass
B18: pass
B19: pass
```

## Bob

Consensus + doubt/de-slop lens, codex, static-only sandbox, resumed from his
cycle-1 thread.

```
[BOB] 🟠 Deleting the explicitly required `test_classify_tier.py` breaks the PRD's repository structure and exact pytest acceptance command | File: skills/plan-tasks/scripts/test_classify_tier.py | Task: 4
[BOB] 🟡 The contract and algorithmic-risk precedence tests are near-identical mirror functions; one parametrized test can preserve both cases without duplication | File: skills/plan-tasks/scripts/test_classify_tier_risk_flags.py:72 | Task: 4
[BOB] 🟡 The `tier_reason` row repeats both escalation ladders and their attempt fields; retain the plan-time invariant and caveat in one concise sentence | File: skills/run-autopilot/references/state-schema.md:187 | Task: 6
[BOB] ⚪ Prose pins still cannot detect deliberately inverted meaning; cycle 2 does not touch this disclosed repo-wide limitation | File: skills/plan-tasks/scripts/test_plan_tasks_prose.py | Task: general
```

```
R1: pass
R2: pass
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
```

### Doubt lens buckets

```
FIX:
- The canonical test module was deleted, so the PRD's exact `pytest -q skills/plan-tasks/scripts/test_classify_tier.py` command cannot run — skills/plan-tasks/scripts/test_classify_tier.py — Restore that path as the suite entrypoint and ensure invoking it collects every thematic classifier test; prune or consolidate tests if needed to remain below 800 lines.
- Two risk-over-mechanical tests duplicate setup and assertions — skills/plan-tasks/scripts/test_classify_tier_risk_flags.py:72 — Replace them with one parametrized test over risk kwargs and expected reason.
- The escalation caveat duplicates detailed ladder documentation — skills/run-autopilot/references/state-schema.md:187 — Reduce it to: the field is written at planning, later model escalation does not rewrite it, and attempts carry escalation history.
VERIFY:
- (none)
KNOWN:
- Prose-substring tests cannot reliably verify natural-language meaning — Robust semantic verification is a repo-wide testing limitation and unchanged by this incremental rework.
```

```
D1: pass
D2: pass
D3: pass
D4: pass
D5: pass
```

## Carl

Ran on the copilot backend with `-m auto` (see run note 1). Read the diff and
the changed sources, ran the cross-skill pytest suite, and checked each cycle-1
finding for closure. He confirmed **seven of cycle 1's findings individually
fixed** — negative `--lines` rejected at the CLI boundary before file reads;
`classify()`/`_apply_floor()` no longer write stderr; the mechanical+risk-flag
precedence tests present and load-bearing; `_is_mechanical` inlined;
`test_a_small_mechanical_edit_is_haiku` gone with no duplicate left; the
`tier_reason` row carrying plan-time semantics plus the escalation caveat; and
the out-of-scope reformat reverted (`git diff <base>..HEAD` on that file empty).
No frontend surface in this diff; reviewed as a generalist, as instructed.

```
[CARL] 🟠 Task 4's rework deleted `skills/plan-tasks/scripts/test_classify_tier.py` and split it into five thematic modules, but the PRD's Repository Structure and Phase 0's acceptance criterion (and task 4's own given acceptance criteria) verbatim invoke `uv run --no-project --with pytest python -m pytest -q skills/plan-tasks/scripts/test_classify_tier.py`; that exact command now errors with "file or directory not found" instead of passing green — an unmet literal PRD/acceptance-criterion path, not a cosmetic drift. | File: skills/plan-tasks/scripts/test_classify_tier.py | Task: 4
```

```
R1: pass
R2: pass
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
```

## Verification-check queue

Bob's VERIFY bucket is `(none)` this cycle — he had run out of things he could
not settle statically, because cycle 1's three VERIFY entries were queued, run
and all exited 0 during the rework pass. `checks-2.json` is therefore written as
an empty array.

## Rubric verdict divergence

`R9` (implementation matches PRD feature behavior exactly) failed on **all four**
reviewers — the unanimous signal behind the merged finding above. `R4` (changed
components integrate with existing callers) failed on Bob alone, consistent with
his framing of the deleted module as a broken entrypoint. `R1` and `R2`, which
failed across the panel in cycle 1, now **pass on all four** — the
precedence-coverage rework closed them, and Alice's RED-check experiment is the
empirical proof.

Blake's `B6` and `B15` failed: `B6` on the unspecified negative-`--lines` error
path, `B15` on the Phase 0 acceptance criterion the deleted file breaks. Every
other `B{n}` passed, and every `D{n}` passed.

Verdict: 8 findings
Tests: 2366 passed, 0 failed, 1 skipped (reused from last-verification.json at 0c0c80107c9d297d372ff2429f5cd57af4bd07e8)

## Walkthrough minutes (operator, 2026-09-02)

| # | Finding | Decision | Status |
|---|---------|----------|--------|
| 1 | CRITICAL 4/4: PRD names deleted `test_classify_tier.py` | Amend PRD to name the five `test_classify_tier_*.py` modules and the support module; acceptance command becomes `pytest -q skills/plan-tasks/scripts/test_classify_tier_*.py` | applied (PRD in `done/`) |
| 2 | MEDIUM: negative `--lines` rejection unspecified | Keep the check (CLI is a trust boundary); PRD CLI Outputs line amended | applied |
| 3 | MEDIUM: mirror precedence tests | One test parametrized over `(risk_flag, reason)` x phrase | applied (6b8e087) |
| 4 | MEDIUM: verbose `tier_reason` row | Trimmed to the plan-time invariant + caveat | applied (39705c4) |
| 5 | LOW: stale docstring in `test_plan_tasks_prose.py` | Points at the `test_classify_tier_*.py` modules | applied (6b8e087) |
| 6 | LOW: Blake's wip/ process note | False positive (finalize had not run) | rejected |
| 7 | LOW: prose pins cannot detect inverted meaning | Repo-wide limitation, out of scope | deferred (settled in ledger) |

Tests at 39705c4: 155 passed (classifier modules); 2201 passed, 1 skipped (Phase 2 suite); release-checks green.
