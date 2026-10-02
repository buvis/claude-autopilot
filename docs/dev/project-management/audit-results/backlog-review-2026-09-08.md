# Backlog review - claude-autopilot - 2026-09-08

Verdict: **GO — 8 READY, 0 unresolved Blocking findings, 0 pending reshapes.**

Apply pass completed **2026-09-13**. All accepted decisions are applied; no Blocking finding was waived. This is a PRD readiness review, not implementation or completed-work verification.

Initial baseline: `fa632e3` on master. Final checkout: `ff42cbd`; the intervening commit changes only the autoclaude launch test's caffeinate stub, not these PRDs' change surfaces. The existing user edit in `skills/fast-track/SKILL.md` is preserved. WIP, hold and done contents are untouched.

## Map

| # | PRD | template | lines | subsystems | depends on | verdict |
|---|---|---|---:|---|---|---|
| 00187 | [Keep cap-out CRITICALs under custody](../prds/backlog/00187-keep-cap-out-criticals-off-master-and-home-deferred-highs-v1.md) | standard | 146 | stall, custody, Git guard/resolve, stalled report | existing records/state/rendering | READY |
| 00188 | [Record convergence cap and roster per PRD](../prds/backlog/00188-record-convergence-cap-and-roster-per-prd-v1.md) | minimal | 96 | convergence telemetry, loop emission, report | existing 00168/00183/00185; preserves 00187 cap branch | READY |
| 00189 | [Stall to split on plan expansion](../prds/backlog/00189-stall-to-split-on-plan-expansion-v1.md) | minimal | 93 | policy, frontmatter, planner/CLI | existing task ceiling; 00188 is complementary | READY |
| 00190 | [Bind the codex-run tests and dedupe their split](../prds/backlog/00190-bind-the-codex-run-tests-and-dedupe-their-split-v1.md) | standard | 127 | test harnesses, release checks | existing 00180/00182 | READY |
| 00191 | [Clear the handoff marker at phase edges](../prds/backlog/00191-clear-the-handoff-marker-at-phase-edges-v1.md) | standard | 131 | hook, work handoff, lifecycle cleanup | existing 00182; preserve 00187 stall contract | READY |
| 00192 | [Split loop.py and its tests under the cap](../prds/backlog/00192-split-loop-py-and-its-tests-under-the-cap-v1.md) | standard | 110 | loop implementation/test seams | retain 00188 behavior/tests and 00191 lifecycle behavior | READY |
| 00194 | [Design CRITICAL rework before task dispatch](../prds/backlog/00194-design-critical-rework-before-task-dispatch-v1.md) | standard | 110 | design skill, review rework routing | existing design procedure; preserve 00187/00188 prose | READY |
| 00195 | [Mint hold stubs for unowned deferred findings](../prds/backlog/00195-mint-hold-stubs-for-unowned-deferred-findings-v1.md) | standard | 122 | ledger ownership, numbering, lifecycle calls | 00187 custody/migration; preserve 00194 routing | READY |

Frontmatter parses with **zero warnings**. Existing choices remain, except the accepted 00192 correction from invalid `design: force` to `design: run`. New split PRDs use reviewed design and opus for their cross-skill/persisted contracts. `model_tier_rationale` is valid authoring metadata under the live create-prd law, intentionally ignored by runtime parsing. No blanket optional tuning was applied.

## Findings

All locations below name the final PRD sections; quoted defects describe the original review baseline.

### Blocking — resolved

| ID | PRD / location | Original failure and evidence | Applied resolution |
|---|---|---|---|
| B1 | 00192 Success Metrics, Seams, Phase 1/2 | Rework thrash: the cap applied to every CLI file after every seam; __main__.py and test_state.py were already oversized outside scope. | Cap only loop.py, test_loop.py and extracted siblings at final completion; per-seam tests, golden hashes and assertion/case inventory remain required. |
| B2 | 00191 hook/consumer Features, Phase 0/1 | Wrong-TDD lock-in: the existing marker carries a task ID, while the proposed JSON omitted it and wrote on unreadable state. Hook _request_handoff and existing task-x/task-old tests establish the current contract. | Four-field phase/session/at/task_id JSON, same-task deduplication, changed-task overwrite, non-empty and empty legacy formats, malformed handling, build-only and unreadable-state no-write guards. |
| B3 | 00191 Lifecycle edges Feature, edge matrix, Phase 0 | Wrong-TDD lock-in: phase-edge module/test placeholders with design skipped could produce an unused helper or erase valid same-phase requests. | Bind cleanup to _run_phase_done, _run_reset_prd and do_stall successful commits; keep transitions.apply/reset_prd_fields pure; real-entrypoint tests cover every clear/preserve row. |
| B4 | 00188 Module render_report, Phase 1 report task | Wrong-TDD lock-in/rework thrash: replacing positional argument five would lose the shipped attempts_ledger caller and implementor mix. | Retain all five positional arguments, add keyword-only convergence, and require a combined ledger-only-attempt/convergence regression. |
| B5 | 00188/00189 Success Criteria and Post-release signals; 00187 validation | Unattended hang: a later installed batch was a completion gate for checkout changes; installed cache is a separate artifact. | Checkout subprocess/fixture proofs gate completion. Later batch signals are non-gating and filtered by batch/completed PRDs as appropriate. |
| B6 | 00187 Retry-stable critical record, Phase 0, Error case | Wrong-TDD lock-in: original error acceptance kept the PRD in wip although do_stall moves it before appending records. | Preserve move-before-record order; exit 9 leaves hold plus durable intent and unreset per-PRD state; retry reuses capture/op_id without duplicate custody or migrated records. |
| B7 | 00195 allocation Feature, Phase 0 | Selection break: original allocator omitted discovery and collision retry, which could claim reserved 00193. | Scan all lifecycle directories plus discovery, recheck after writing and renumber only this attempt on concurrent claim. |
| B8 | 00187 Command-aware push guard, Phase 0 | Wrong-TDD lock-in: adjacent git/push tokens miss -C/-c pushes and match quoted echo arguments. | Executable-position parsing, supported global options/compound forms, effective-repo resolution, negative argument cases and explicit ambiguous-command fallback. |
| B9 | 00190 Success Metrics/Phase 0; 00187 Phase 2 | Rework thrash: unescaped helper search counted definitions and calls; original changelog total rejected existing unrelated entries. | Anchored definition-only search plus both source assertions; new changelog subjects checked within Unreleased, preserving unrelated entries. |

### Non-blocking — resolved

- **N1, template/module closure:** standard PRDs now have complete Feature fields, concrete file ownership, module/layer mappings, phase goals/tasks/exits and task dependencies/acceptance. Minimal PRDs retain their live template headings and explicit modules. 00192's design must fix exact extracted filenames before task planning.
- **N2, 00192 frontmatter:** design: run replaces the invalid force value; forced catchup and cap 3 remain.
- **N3, 00189 diagnostics:** missing/empty file lists and skipped drift remain visible on successful checks, including combined override diagnostics; no added stall rule.
- **N4, 00189 directory coverage — option 1 accepted:** only leaf directory modules grant recursive coverage. Grouping parents do not allow unlisted siblings; directly listed grouping/root files are allowed individually. Nested-tree and root-file fixtures pin this. The accepted tradeoff is that a new sibling module can count as drift under a known grouping parent.
- **N5, 00195 historical fixture:** explicitly filter source PRDs 00167–00170, preserving their rows verbatim; assert 12 then zero on that frozen slice, not the full ledger (which also contains a qualifying 00171 row).
- **N6, 00190 premises and labels:** execution-time rechecks precede moves/rewrites; preserve distinct assertions with named duplicate-fold, root SKIP and three-path label exceptions. Assert exact unreadable-file error and replay the revised harness/helper against the old runner, using a shim for the root branch.

### Questions — settled

- **Q1 / 00187:** derive work_start_sha..HEAD inside stall, capture once in the durable operation and reuse on retry. No caller range override; invalid recorded build state fails loudly.
- **Q2 / 00189:** an operator intentionally allowing an oversized plan explicitly sets rework_cap: 3 alongside plan_expansion: allow before unattended resume. No automatic cap mutation. Planner/recovery prose and tests own this guidance.

## Reshapes

**R1 applied:** 00187 retains custody, push guarding, attended resolution, hold refresh and stalled reporting. New **00194** owns reviewed CRITICAL rework design. New **00195** owns stub minting, all three mint call sites and the batch notification count.

Fresh allocation scanned backlog/wip/hold/done/discovery before writing; 00193 remains reserved by discovery. Post-write scan found no collision. The original 00187 file/number remains in place; no lifecycle copies, deletions or parking were needed. No earlier PRD calls a command introduced only by a later split PRD.

## Gaps

- Discovery 00193's broader loop guard rails, handoff/session policy and session brief remain future authoring work; preserve its order after 00191/00192 when converting it. No extra PRDs were invented from it.
- Generated 00195 artifacts are held triage stubs. They require attended ownership/promotion/closure and are not ready repair PRDs.
- Held 00110's consensus-default flip is not a dependency. WIP 00186 fast-track work is distinct and remains untouched.
- Shared reference docs, release-checks and CHANGELOG edits are additive. 00188 and 00191 remain before 00192; the split preserves their behavior and verification.
- Attended resolution/triage are product behaviors tested with fixtures, not human steps required during implementation.

## End state after this batch

The plugin will record critical custody and guard supported pushes until explicit resolution, design severe rework before dispatch, give unowned severe deferred findings a hold file, record convergence conditions mechanically, detect plan expansion, share the codex harness setup, clear stale handoff markers and split the loop into smaller modules. Every required review lens remains.

Critical commits may remain locally present pending attended resolution. Stub triage, release/cache refresh and discovery 00193 remain separate follow-up work. Re-measurement is a post-release signal; the conditional cap policy is now explicitly owned by operator guidance.

## Verification and lens coverage

- All lenses **A–H** completed. Read every original PRD before findings; reread/rechecked the eight final artifacts. Used the live create-prd skill/templates as law, including valid same-unit revisions and model rationale metadata.
- Installed autopilot 0.5.1 plan-tasks steps 4–4.7 reviewed: 150K task threshold, 75K replan threshold, 55K estimated fixed overhead and task-local tier classifier. These differ from the unchanged 500K runtime context cap. No unsplittable-task budget failure was proven or fabricated.
- Final structural check: **8 valid filenames, 33 tasks with Acceptance/dependencies, complete required headings/fields, no leftover guesses/placeholders, no trailing whitespace, zero frontmatter warnings**. All final PRDs are under 200 lines.
- Inventory: eight backlog PRDs, one WIP (00186), one hold (00110), done history and discoveries 00157/00177/00193. Only shared sequence is done 00093 v1/v2, valid revisions of the same work unit.
- Required citation checker rerun, filtered to backlog/WIP: **zero unresolved dangling citations, zero scan errors**. It emits two raw hits for the same future critical-on-master runtime marker (00187 Outputs and Repository Structure). Both are declared outputs, exempt under the review skill's forward-reference rule; no waiver added and no marker created during review.
- Grounding rechecked with rg/direct reads: actual stall ordering/intent, report signature/caller, marker producer/consumer and lifecycle entrypoints, hook registration, helper definitions, release registration, loop sizes and installed wrapper routing.
- Installed plugin runs from a separate cache; checkout code edits do not change the machinery executing this batch. No run-last workaround is needed. Every acceptance requiring new CLI behavior explicitly exercises checkout code.
- Final launch context read-only check: state names **00186, phase review, next_phase review, cycle 1**, with no pause_reason/stall_op or blocking lifecycle marker. No loop registry entry exists for this repo. Running autoclaude here resumes that review before selecting backlog work.
- No implementation tests or proposed Git mutations were executed: this pass changed only ignored backlog documents and this report. No release/cache update, external write, temporary file, worktree or branch was created. The existing dirty fast-track file remains the sole tracked worktree change.

## Decisions applied

B1–B9: accepted fixes applied. R1: three-way split applied. Q1/Q2: settled policies applied. N1–N6: contract corrections applied, including the final leaf-directory option 1 choice. The full decision summary was printed before the batch apply pass.

**Final readiness: GO.**
