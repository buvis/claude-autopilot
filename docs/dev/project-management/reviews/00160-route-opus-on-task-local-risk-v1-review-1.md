---
prd: dev/local/prds/wip/00160-route-opus-on-task-local-risk-v1.md
review: 1
date: 2026-09-01
head_sha: c6c32130e44639d09336c73aa9a0b0576ac0d1c6
codex_thread_id: 01a05eca-ece4-7ae0-8d48-6d2ae0c09dd5
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00160-route-opus-on-task-local-risk-v1

Diff range: `100eba0d6138a00dad5b9f6d4b5b178711b88864..c6c32130e44639d09336c73aa9a0b0576ac0d1c6`

codex_rung_guard: not fired

pack: unavailable this cycle (`engram pack` exited 1: "not inside a registered repo; register it in /Users/bob/.config/gita/repos.csv"). Every prompt that takes `{PACK_FILE}` / `{PACK_FINDINGS}` carried the literal `(no pack available this cycle)` instead. Not retried: the failure is a deterministic registration precondition, not a transient. The review is degraded on retrieval context, not invalid. Blake never receives a pack by design.

## Review Summary

Reviewed: 3 completed tasks
PRDs checked: 00160-route-opus-on-task-local-risk-v1

### Agent Status

- Alice: ✅ Available (Claude subagent, consensus lens)
- Blake: ✅ Available (Claude subagent, blind/PRD-only lens)
- Bob: ✅ Available (codex, consensus + doubt/de-slop lens)
- Carl: ⚠️ Available after one retry (see below)

### Run notes (fail-loud)

1. **`gather-context.sh` produced an empty diff on its first run.** The script diffs against the detected branch base (`master`), and this PRD's work landed directly on `master`, so `git diff master` was empty. It was re-run with `--since 100eba0d…` (the autopilot `work_start_sha`), which is the documented `COVERAGE_DIFF_RANGE` for a full review, yielding a 106,359-byte diff. The context file's scope line was corrected to say FULL review rather than the script's "incremental" label. **This is a latent gap in `gather-context.sh` for repos whose PRD work lands on the default branch** — worth a follow-up outside this PRD.
2. **Carl needed his one retry.** The first dispatch failed with exit 1: `Model "gemini-3.1-pro-preview" from --model flag is not available.` — the `gemini-run.sh` copilot-backend default is not served on this account. `[RETRY] carl attempt 1/1` re-dispatched with `-m auto`, which succeeded. **Carl therefore ran on a copilot-auto-selected model, not on Gemini.** He is a real fourth voice but not the Gemini voice the roster names.
3. **Bob's prompt carries three sections of `agents/eve.md`, not the two SKILL.md names.** SKILL.md step 4 says to append the "Two lenses" and "Rubric verdicts" sections. The "Categorize every residual finding" section sits between them and defines the FIX/VERIFY/KNOWN buckets that the `D1`–`D5` verdicts score and that step 6 reads to build the verification-check queue. Appending only the two named sections would have left the doubt lens's contracted output undefined, so all three were appended.
4. **Blake's saved output has one edit:** his single finding named `test_classify_tier.py` by absolute path; it was rewritten to the repo-relative path so the consolidation matcher could compare it against the other reviewers' paths. No wording changed.
5. **No follow-up tasks were created in this skill's step 7.** Under autopilot, Phase 5 classifies and Phase 6 creates the `[D1]` tasks and queues them in `state.rework_task_ids`; creating them here as well would double-create every finding. Task creation is deferred to Phase 6.
6. **Consolidation merged two of Bob's three "Cannot statically verify" lines** onto the first-seen wording (all share `File: N/A`). All three are preserved individually in the verification-check queue.

## Consolidated Findings

`consolidate_findings.py`, 4 reviewers. No settled-decisions ledger exists (cycle 1), so the `--ledger` flags were omitted.

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [3/4] | 🟡 | Commit 82d770a reformatted skills/work/scripts/test_verify_queue_prose.py (quote style + line wrap), a file outside this PRD's declared Repository Structure — cosmetic-only but out-of-scope. | skills/work/scripts/test_verify_queue_prose.py | 2 | ALICE, BOB, CARL |
| [1/4] | 🟠 | No test combines a true `contract_edit`/`algorithmic_risk` flag with genuinely mechanical-phrase text inside the haiku bounds (≤2 files, ≤50 lines); every risk-flag fixture uses non-mechanical text, so a regression that checks the mechanical rule before the risk facts would pass the whole suite undetected. | skills/plan-tasks/scripts/test_classify_tier.py | 1 | ALICE |
| [1/4] | 🟡 | `classify()` writes to stderr for invalid floors, violating the required pure-core boundary; move validation and warning to `main()` | skills/plan-tasks/scripts/classify_tier.py:147 | 1 | BOB |
| [1/4] | 🟡 | Tests never combine mechanical text with either risk flag, so moving the mechanical rule ahead of risk would pass while violating precedence | skills/plan-tasks/scripts/test_classify_tier.py:251 | 1 | BOB |
| [1/4] | 🟡 | `tier_reason` is documented as explaining the current `tasks[].model`, but escalation rewrites `model` without rewriting this plan-time reason | skills/run-autopilot/references/state-schema.md:187 | 3 | BOB |
| [1/4] | 🟡 | `_is_mechanical()` is a three-line single-caller indirection; inline its expression into the tier decision | skills/plan-tasks/scripts/classify_tier.py:137 | 1 | BOB |
| [1/4] | 🟡 | `test_a_small_mechanical_edit_is_haiku` duplicates the exact rename behavior already covered by the parametrized core and CLI tests; remove it | skills/plan-tasks/scripts/test_classify_tier.py:288 | 1 | BOB |
| [1/4] | 🟡 | `--lines` accepts negative values, allowing a negative change estimate to satisfy the mechanical `<= 50` limit and incorrectly route a task to Haiku; reject negative values and add a CLI test. | skills/plan-tasks/scripts/classify_tier.py:160 | 1 | CARL |
| [1/4] | ⚪ | test_plan_tasks_prose.py's substring/proximity prose pins passed 12/12 against Devon's deliberately inverted-meaning adversarial prose during the build (per the file's own docstring: "Prose-substring pins catch drift, not meaning") — a disclosed, repo-wide limitation of this technique, not unique to this diff, surfaced for visibility. | skills/plan-tasks/scripts/test_plan_tasks_prose.py | 2 | ALICE |
| [1/4] | ⚪ | No test exercises a genuinely mixed test+packaging file slice (e.g. one test path plus one manifest path) to pin the `is_test_path(path) or is_packaging_path(path)` OR-branch across differing types; existing packaging tests use packaging-only slices. Not required by the PRD's literal acceptance criteria and code inspection shows the behavior is correct. | skills/plan-tasks/scripts/test_classify_tier.py | 1 | ALICE |
| [1/4] | ⚪ | Packaging-outranks test coverage only checks contract_edit, not algorithmic_risk (code order is correct either way) | skills/plan-tasks/scripts/test_classify_tier.py | Phase 0 | BLAKE |
| [1/4] | ⚪ | Cannot statically verify: full pytest suite passes | N/A | general | BOB |

### Judgment-call merge for the decision gate

Rows 2 and 4 are **one defect described twice**: Alice's 🟠 and Bob's 🟡 both say the risk-flag fixtures never use mechanical-phrase text, so the mechanical-vs-risk precedence order is untested. The script kept them apart only because Bob's file string carries `:251` and Alice's does not. Read as one finding it is **🟠 High at [2/4] consensus (ALICE, BOB)** — the highest-consensus substantive finding in this cycle, and an unresolved HIGH.

This is also the exact weakness the build phase recorded and shipped anyway: `state.autonomous_decisions` cycle 0 names "mechanical/risk-flag precedence untested" among the exploits Devon found after the two adversarial rounds were exhausted. Two independent reviewers rediscovering it is the signal that the note-and-proceed call did not hold.

## Alice

Ran the classifier and prose suites (157 passed), the full pack suite (2146 passed, 1 skipped), `bash dev/bin/release-checks` (exit 0), and both `rg` acceptance checks. Traced the `parents[2]` import resolution for `is_test_path` and confirmed `work_routing.py` has no import-time side effects. Confirmed no retired trigger text (`Rule 1/2/3`, `novel algorithm`, `concurrency`, `migrate`, `files_touched > 8`, `estimated_tokens > 120000`) survives in `SKILL.md`.

```
[ALICE] 🟠 No test combines a true `contract_edit`/`algorithmic_risk` flag with genuinely mechanical-phrase text inside the haiku bounds (≤2 files, ≤50 lines); every risk-flag fixture uses non-mechanical text, so a regression that checks the mechanical rule before the risk facts would pass the whole suite undetected. | File: skills/plan-tasks/scripts/test_classify_tier.py | Task: 1
[ALICE] 🟡 Commit 82d770a reformatted skills/work/scripts/test_verify_queue_prose.py (quote style + line wrap), a file outside this PRD's declared Repository Structure — cosmetic-only but out-of-scope. | File: skills/work/scripts/test_verify_queue_prose.py | Task: 2
[ALICE] ⚪ test_plan_tasks_prose.py's substring/proximity prose pins passed 12/12 against Devon's deliberately inverted-meaning adversarial prose during the build — a disclosed, repo-wide limitation of this technique, surfaced for visibility. | File: skills/plan-tasks/scripts/test_plan_tasks_prose.py | Task: 2
[ALICE] ⚪ No test exercises a genuinely mixed test+packaging file slice to pin the `is_test_path(path) or is_packaging_path(path)` OR-branch across differing types. | File: skills/plan-tasks/scripts/test_classify_tier.py | Task: 1
```

```
R1: fail
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
```

## Blake

Blind lens, PRD-only prompt: no diff, no file list, no review history, no pack. Located the implementation himself. Ran the classifier tests (139 passed), prose pins (18 passed), the full pack suite (2146 passed, 1 skipped) and `dev/bin/release-checks` (green). Confirmed the packaging predicate's 20-basename frozenset plus the `requirements*.txt` glob and `.claude-plugin` segment check, the CLI flag surface with no extras, the `is_test_path` import (not a copy), the surviving `_PLAN_TASKS_FLOOR` / `default_model` / `final_tier` / `qwen_eligible` paragraphs, and that `refactor across` appears exactly once, inside the exclusion sentence.

```
[BLAKE] ⚪ Packaging-outranks test coverage only checks contract_edit, not algorithmic_risk (code order is correct either way) | File: skills/plan-tasks/scripts/test_classify_tier.py | Task: Phase 0
```

```
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
B16: pass
B17: pass
B18: pass
B19: pass
```

## Bob

Consensus + doubt/de-slop lens, codex, static-only sandbox.

```
[BOB] 🟡 `classify()` writes to stderr for invalid floors, violating the required pure-core boundary; move validation and warning to `main()` | File: skills/plan-tasks/scripts/classify_tier.py:147 | Task: 1
[BOB] 🟡 Tests never combine mechanical text with either risk flag, so moving the mechanical rule ahead of risk would pass while violating precedence | File: skills/plan-tasks/scripts/test_classify_tier.py:251 | Task: 1
[BOB] 🟡 `tier_reason` is documented as explaining the current `tasks[].model`, but escalation rewrites `model` without rewriting this plan-time reason | File: skills/run-autopilot/references/state-schema.md:187 | Task: 3
[BOB] 🟡 Unrelated quote and wrapping changes are scope creep; revert both formatting-only hunks | File: skills/work/scripts/test_verify_queue_prose.py:374 | Task: 2
[BOB] 🟡 `_is_mechanical()` is a three-line single-caller indirection; inline its expression into the tier decision | File: skills/plan-tasks/scripts/classify_tier.py:137 | Task: 1
[BOB] 🟡 `test_a_small_mechanical_edit_is_haiku` duplicates the exact rename behavior already covered by the parametrized core and CLI tests; remove it | File: skills/plan-tasks/scripts/test_classify_tier.py:288 | Task: 1
[BOB] ⚪ Cannot statically verify: full pytest suite passes | File: N/A | Task: general
[BOB] ⚪ Cannot statically verify: classifier help exits zero | File: N/A | Task: 1
[BOB] ⚪ Cannot statically verify: release checks pass | File: N/A | Task: general
```

```
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
```

### Doubt lens buckets

```
FIX:
- `classify()` has a stderr side effect despite being specified as pure — skills/plan-tasks/scripts/classify_tier.py:147 — Ignore invalid floors silently in the core and emit the warning from `main()`; move the warning assertion to a CLI test.
- Risk-over-mechanical precedence is untested — skills/plan-tasks/scripts/test_classify_tier.py:251 — Add a parametrized mechanical-sized fixture for `contract_edit` and `algorithmic_risk`, expecting their respective Opus reasons.
- `tier_reason` documentation becomes false after model escalation — skills/run-autopilot/references/state-schema.md:187 — Define it as the plan-time classification reason and state that later escalation may rewrite `model` without changing it.
- Formatting-only edits exceed the PRD scope — skills/work/scripts/test_verify_queue_prose.py:374 — Revert both unrelated hunks.
- `_is_mechanical()` is needless single-caller indirection — skills/plan-tasks/scripts/classify_tier.py:137 — Inline the lowercase substring check into `_tier_from_shape`.
- The standalone small-rename test is redundant — skills/plan-tasks/scripts/test_classify_tier.py:288 — Delete it; the parametrized core and CLI cases retain the same coverage.
VERIFY:
- Full pytest result was not statically verifiable — Run `uv run --no-project --with pytest --with rich --with textual python -m pytest -q skills/plan-tasks/scripts skills/work/scripts skills/run-autopilot`
- Classifier help exit status was not statically verifiable — Run `python3 skills/plan-tasks/scripts/classify_tier.py --help`
- Release-check result was not statically verifiable — Run `bash dev/bin/release-checks`
KNOWN:
- (none)
```

```
D1: pass
D2: pass
D3: pass
D4: pass
D5: pass
```

## Carl

Ran on the copilot backend with `-m auto` after the roster's `gemini-3.1-pro-preview` came back unavailable (see run note 2). Executed the targeted suites, the PRD integration suite and `dev/bin/release-checks` (the last needed `env -u AUTOPILOT_DISPATCH_DEPTH -u CODEX_SESSION_ID -u COPILOT_CLI` to clear this session's nested-dispatch guards). No frontend surface in this diff; reviewed as a generalist, as instructed.

```
[CARL] 🟡 `--lines` accepts negative values, allowing a negative change estimate to satisfy the mechanical `<= 50` limit and incorrectly route a task to Haiku; reject negative values and add a CLI test. | File: skills/plan-tasks/scripts/classify_tier.py:160 | Task: 1
[CARL] ⚪ Unrelated quote/wrapping-only changes were included outside the PRD's declared repository structure; revert them to keep the PRD diff scoped to its requested work. | File: skills/work/scripts/test_verify_queue_prose.py:374 | Task: 2
```

```
R1: fail
R2: pass
R3: pass
R4: pass
R6: pass
R7: fail
R8: pass
R9: pass
R10: pass
R11: pass
R12: pass
R13: pass
```

## Verification-check queue

Written to `dev/local/reviews/00160-route-opus-on-task-local-risk-v1-checks-1.json` — 3 entries, all from Bob's VERIFY bucket, all naming one exact runnable project verification command with no chaining. They run inside the work phase's step-7 verification pass.

## Rubric verdict divergence

`R1` (tests cover every new behavior) failed on **all four** reviewers. `R2` (tests bind to intent) and `R9` (implementation matches PRD behavior exactly) failed on Bob alone; `R7` (user input validated) failed on Carl alone, consistent with his `--lines` finding. The unanimous `R1` failure is the same precedence-coverage gap the merged 🟠 above names.

Verdict: 12 findings
Tests: 2467 passed, 0 failed, 1 skipped (reused from last-verification.json at c6c32130e44639d09336c73aa9a0b0576ac0d1c6)
