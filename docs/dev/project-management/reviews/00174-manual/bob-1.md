# Bob doubt + de-slop review — PRD 00174, cycle 1

**Changes required.** Ten concrete items: **4 FIX, 5 VERIFY (checked and dismissed), 1 KNOWN**. No implementation or live-state edits were made. FIX items are handed to root because this reviewer was explicitly read-only.

## Isolation and method

Initial product context was only the PRD `dev/local/prds/backlog/00174-align-qwen-routing-with-single-file-trust-v1.md` and scoped `cycle-1.diff`. I independently read the actual implementation and directly connected routing, attempt-writing, and report-rendering code. I read no design documents, parent-session evidence, or other reviewer reports and invoked no external model CLI or subagent. Findings describe the frozen cycle-1 implementation and the checks completed before root's repairs.

Applied `/Users/bob/.agents/skills/review-with-doubt/SKILL.md` in full and `skills/run-autopilot/references/doubt-review-rubric.md` D1–D5. One review pass was performed. No reviewer-authored code fixes occurred, so the review-of-fixes iteration has not yet been triggered.

## FIX findings

### B01 — HIGH — Git index shortcuts hide changed Tess tests

**FIX.** `skills/work/scripts/check_qwen_output.py:51` and `:105`.

`changed()` relies on `git diff <commit>`, `git diff --cached <commit>`, and untracked enumeration. These all report no difference for a tracked test marked `assume-unchanged` or `skip-worktree`. Preparation accepts those entries. After a real implementation edit and replacement of the test with `assert True`, `after` exits 0 with `{"arm":"pass","next":"proceed","cause":null}`. The modified test remains on disk and can become the oracle, violating the PRD's deterministic comparison with the test commit.

**Executed:** `/tmp/00174-bob-review.py`, cases `--assume-unchanged` and `--skip-worktree`. Each initializes a separate Git repository, sets the flag before preparation, verifies preparation exits 0, edits implementation and test, and asserts the incorrect exit-0 acceptance and mutated disk content. No mocks.

**Bounded fix:** compare committed content/type/mode to actual disk state without trusting index shortcuts, retaining a separate index comparison. Alternatively reject unsupported index flags both before and after dispatch. Cover flags present initially and introduced during dispatch; restoration verification must use the reliable comparison too.

### B02 — MEDIUM — The self-check rejects the new permitted fallback

**FIX.** `skills/work/SKILL.md:308` and `:332` in cycle 1.

Runtime reconciliation preserves persisted `qwen_eligible:true`, changes only an effective copy, and requires null preflight for a stale wider task falling back to Claude. The later self-check still says persisted eligibility true plus Claude and null/healthy preflight means the table was skipped and must run again. Only breaker and memory-pressure cases are exceptions. A stale two-file task with Codex disabled therefore obeys the new fallback and violates the mandatory self-check simultaneously. Guard-preparation failure has the same missing exception when preflight was healthy.

**Executed:** `/tmp/00174-bob-review.py`, `runtime-self-check-conflict`: actual `route()` with two paths, persisted eligibility true, and `_WORK_CODEX_RUNG=off` returns Claude/Sonnet/row7 and runtime `files`, preserving the task dictionary. The reproducer also asserts the two contradictory literal self-check clauses. New prose tests inspect the earlier fence only and pass despite this conflict.

**Bounded fix:** make the self-check use effective eligibility and account explicitly for preparation/test-only/zero-path fallbacks while preserving the prohibition on arbitrary rerouting. Pin the complete path through the self-check.

### B03 — MEDIUM — Duplicated schema authorities contradict the new contract

**FIX; slop candidate 1.** `skills/run-autopilot/references/state-schema.md:181`, `:182`, `:183` in cycle 1.

The new dedicated cause/exclusion rows correctly describe output rejection and runtime `files`. The giant parent `tasks[].attempts` row still limits its inline exclusion enum to memory reasons, describes that field as absent on non-eligible tasks, and defines `qwen_gate_failed` only as a step-5.5 failure. Those descriptions conflict with the adjacent new rows and `work/references/attempt-logging.md`.

**Verified:** direct comparison of the parent row, the added rows, and attempt-logging's effective-eligibility/output-guard definitions. The new exactly-once authority test reads narrow new sections, leaving the contradictory parent definition unchecked.

**Bounded fix:** update the parent signature/semantics or replace its repeated field explanations with links to the dedicated definitions. One authority per behavior is smaller and avoids this drift. Pin consistency of the full schema.

### B04 — MEDIUM — Batch telemetry drops runtime file exclusions

**FIX.** Actual consumer: **`skills/run-autopilot/cli/render_report.py:311`**, `_exclusion_line`.

The new fence leaves a stale task's persisted eligibility true and records `files` on its attempt. `_exclusion_line()` counts plan reasons only on persisted-ineligible tasks and counts runtime reasons only for `memory_pressure` and `memory_probe_failed`. Consequently runtime `files` disappears from the Implementor Mix exclusion report. Raw attempt storage works; its report consumer is incomplete.

**Executed:** `/tmp/00174-bob-telemetry.py`, `stale-runtime-files-exclusion`. Actual `statectl.do_task_done` records the completed Claude attempt with null preflight and runtime `files`. Actual `_exclusion_line(state['tasks'])` returns `None`; the reproducer asserts this omission.

**Bounded fix:** include runtime `files` in the dispatch population, deduplicate by task as existing runtime reasons do, synchronize the report-format description, and cover repeated attempts without changing plan counts.

## VERIFY findings — checked and dismissed

### B05 — Foreign dirt might make a no-op appear productive

**VERIFY — dismissed.** Exact check: actual guard fixtures plus source of `changed(..., files, index=False)` and `qwen_attempt_outcome`.

The foreign-dirty fixture stages foreign work, prepares the snapshot, and runs an empty output through `after`. It gets `qwen_no_edit`, escalated outcome, and Sonnet next; HEAD and the foreign staged content remain unchanged. The index-only implementation fixture also returns no-edit when disk content is restored to baseline. Real tracked/new implementation edits proceed without staging. These tests passed. B01 separately covers index shortcuts; this dismissal covers normal entries.

### B06 — Restoration might erase foreign work or commits

**VERIFY — dismissed within the documented ownership precondition.** Exact checks: staged/unstaged mutation restoration, moved-HEAD refusal, and independent foreign-staged restoration.

Passing fixtures prove canonical tests are restored, implementation edits remain, and foreign unstaged content remains. HEAD movement causes exit 2 before restoration and preserves both modified tests and the foreign commit. My independent `foreign-staged-restoration` case additionally leaves `foreign.txt` staged and unchanged while restoring only Tess paths; exit remains 1 with `tests_restored:true` and Sonnet next.

`gate-failure.md` requires an exited helper, exclusive test ownership throughout dispatch, and no concurrent writer; otherwise it prohibits live restoration and requires isolation or a stop. The restore flag is a caller assertion of that prerequisite. The CLI performs no branch reset. This is an adequate scoped design when the preconditions hold; B01 still requires fixing the comparison itself.

### B07 — Narrowing might break task boundaries or the existing routing fences

**VERIFY — dismissed.** Exact checks: focused planner/work suites and source of the predicate, splitting contract, `route`, `_table_row`, and `_intercepted_by_codex`.

The planner counts distinct nonempty implementor writes, excludes zero and two-or-more, and retains `ui → tier → contract → files`. The context-budget trigger is unchanged in the diff. Splits require independent compilation/gates and explicitly retain correlated implementation/test, interface/implementation, and implementation/caller edits. Tests pin separable and inseparable examples.

Passing matrices cover one-file Qwen, stale two-/three-file rejection, Codex off/legacy/unhealthy/terminal fences, zero-path Claude fallback, and prior exclusion precedence. The existing suite retains preflight, breaker, memory, tier, and contract behavior with explicit one-file input. Named test-only paths stay on Claude, and the input dictionary remains unchanged. B02/B04 are separate downstream defects.

### B08 — The outcome helper might be unnecessary indirection

**VERIFY — dismissed; slop candidate 2.** Definition `skills/work/scripts/work_routing.py:157`; single production caller `skills/work/scripts/check_qwen_output.py:106` in cycle 1.

Exact check: inspect references and execute all four outcome combinations plus real CLI callers. This small pure helper owns mutation precedence, capability metadata, and the one-shot Sonnet target; the executable guard imports the same implementation. The PRD explicitly requires a pure routing/outcome model. Sharing this decision with the I/O boundary has a current architectural and testability purpose; inlining would remove that seam or duplicate the classifier.

### B09 — Prose pins might merely test strings or framework behavior

**VERIFY — dismissed; slop candidate 3.** `skills/work/scripts/test_qwen_trust_prose.py:12`, `:25`, `:53`; `skills/plan-tasks/scripts/test_plan_tasks_prose.py:642`.

Exact check: inspect assertions against their real consumers and execute them. This plugin runs model-followed Markdown contracts, so ordering, fences, retry edges, and authority text are product behavior. These are not mock-call confirmations or library-correctness tests. Their limitation is incomplete adjacent-authority coverage demonstrated by B02/B03. The actual Git fixtures also assert effects on disk, index, and HEAD rather than only return-object shape.

## KNOWN limitation

### B10 — Live autonomous dispatch and escalation were not executed

**KNOWN.** Source, pure decisions, the actual Git guard CLI, and state-writer functions verify deterministic components. They cannot prove a live orchestrator captures all Tess paths, establishes exclusive ownership, follows every instruction, updates the breaker exactly once, and writes both rung rows correctly during a real Qwen/Sonnet run.

The isolated review explicitly prohibits external agent CLIs and implementation/state mutation. A live dispatch would exceed that scope and consume external model/runtime resources. The PRD also leaves the external Qwen skill and multi-file qualification rerun unchanged. This is a validation boundary, not grounds to omit B01–B04 or claim a new multi-file qualification.

The state-writing component was checked: `/tmp/00174-bob-telemetry.py` uses actual `do_append_attempt` to record rejected Qwen while the task remains open, then `do_task_done` for Sonnet. Two rows are retained, `escalated_from:qwen` stays on the higher row only, and completion increments once. No live state file was touched.

## All six doubt questions

1. **Least confident:** canonical comparison and recovery, B01/B06. Normal recovery survived; index shortcuts caused a real acceptance bypass.
2. **Possibly wrong assumptions:** Git diff always sees test changes (B01, disproved), effective routing survives later instructions (B02, disproved), and consumers read new telemetry (B04, disproved). Exclusive ownership was checked as an explicit B06 prerequisite.
3. **Fully complete:** planner/splitting/routine routing pass B07; ordinary no-edit passes B05. Universal test immutability fails B01; fallback/schema/report integration has B02–B04. This lens ran focused tests, not independent full-suite/release certification.
4. **Practical failures:** index flags B01, self-check fallback conflict B02, dropped telemetry B04. Foreign staged work and moved HEAD were exercised in B06.
5. **Different approach:** compare actual test state with committed blobs and retain one schema authority (B01/B03). Keep the outcome helper after B08's one-caller review.
6. **Missing checks:** regression coverage for index shortcuts, the complete self-check, full-schema consistency, and runtime report consumption is needed with B01–B04. Live orchestration remains B10. Ordinary no-op, mutation, real edit, and foreign-HEAD cases already have meaningful coverage.

## All five de-slop questions

1. **Bloat ratio:** frozen diff has 754 added, 32 removed, **722 net lines**. Its eight task `Acceptance:` clauses have **213 whitespace-delimited words**; measured ratio **3.39**, below the 5–10x warning range. The 154-line guard and actual Git fixtures are justified by the safety requirements. B03 is a concrete duplicate-authority issue.
2. **Defensive impossibility:** checked empty lists, implementation/test overlap, noncanonical/symlink paths, dirty baselines, missing snapshots, and moved HEAD. None is impossible at a standalone CLI/file boundary; files can change and the CLI can be called directly. Dirty-baseline/missing-snapshot tests exercise two of these conditions. No additional impossible guard surfaced. Eager Git queries retain failure visibility; the concrete comparison defect is B01.
3. **Single-caller abstraction:** B08 names its definition/caller and verifies its present purpose.
4. **Comment paraphrasing:** checked added helper docstrings, symlink comment, split explanations, and restoration prose. They express exit contracts, trust boundaries, or recovery reasons. No additional comment-only FIX surfaced. B03's repeated contract is counted once.
5. **Framework-verification tests:** B09 examines prose pins and actual Git effects. Markdown is product guidance, and fixtures inspect filesystem/index/HEAD effects. No framework-only test surfaced; coverage gaps are B01–B04.

## Exact validation evidence

- `mise exec -- uv run pytest -q skills/plan-tasks/scripts/test_plan_tasks_prose.py skills/work/scripts/test_work_routing.py skills/work/scripts/test_qwen_trust.py skills/work/scripts/test_check_qwen_output.py skills/work/scripts/test_qwen_trust_prose.py` — **exit 0; 241 passed in 4.08s**.
- `mise exec -- uv run python /tmp/00174-bob-review.py` — **exit 0**: assertions confirm two wrong acceptances under index flags, foreign-staged restoration preservation, the routing/self-check conflict, and line/word counts. Exit 0 confirms reproduction of the defects, not their correctness.
- `mise exec -- uv run python /tmp/00174-bob-telemetry.py` — **exit 0**: assertions confirm the missing exclusion line and correct two-rung state writing.
- `rg -n 'Qwen3\.6|<= ?3|≤ ?3|files_touched <= 3|files_touched >= 4|<=3.file' skills/work/references/qwen-integration.md skills/plan-tasks skills/work/SKILL.md skills/run-autopilot/references/model-ladder.md skills/run-autopilot/references/state-schema.md` — **exit 1, no matches**. Passing prose tests also pin Qwen3.8, single-file trust, and pending clean multi-file rerun.
- Combined heredoc/uv commands initially encountered uv-cache sandbox denial; explicit approved reruns completed. No denied command was counted as a passing check.
- Temporary reproducers/repos live only under `/tmp` or the configured temporary root and remain available as repair evidence. Implementation and live state stayed read-only.

This isolated reviewer did not run the full repository suite, plugin validation, release checks, or a real model dispatch and makes no claims about their results.

## D1–D5 and count conservation

| Rule | Verdict | Evidence |
|---|---|---|
| D1 — full categorization | PASS | Every B01–B10 has exactly one category. |
| D2 — FIX validity | PASS | B01–B04 identify in-scope files, reproduced/source-proven defects, and bounded repairs. Pending for root because review was read-only. |
| D3 — VERIFY validity | PASS | B05–B09 name exact checks, actual evidence, and dismissals; no uncertain VERIFY remains untested. |
| D4 — KNOWN validity | PASS | B10 explains the live-dispatch boundary and explicit external-runtime prohibition. |
| D5 — count conservation | PASS | **10 input findings = 4 FIX + 5 VERIFY + 1 KNOWN.** Three named slop candidates are included, never double-counted. |

Reviewer fixes: **0**. Verified/dismissed: **5**. Actionable unresolved: **4**. Known: **1**. No findings dropped; no subjective confidence score assigned.
