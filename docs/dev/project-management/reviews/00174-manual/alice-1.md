[ALICE] 🟠 Failed Qwen processes bypass the Tess-test guard before Sonnet fallback | File: skills/work/SKILL.md:339 | Task: general
[ALICE] 🟡 The dispatch self-check rejects the newly authorized runtime-exclusion and preparation-failure fallbacks | File: skills/work/SKILL.md:329 | Task: general
[ALICE] 🟡 The active split example still advertises a two-file task as Qwen-eligible | File: skills/plan-tasks/references/task-examples.md:125 | Task: general

R1: fail
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

Review scope: PRD `dev/local/prds/backlog/00174-align-qwen-routing-with-single-file-trust-v1.md`, scoped `cycle-1.diff`, and relevant existing callers/references. Base `ad1b20721ec2f5e0b724008fc7a15175a54a8ada`. Reviewed independently as Alice against `agents/alice.md`, all review dimensions, and every supplied R rule. No external agent CLI or autopilot-state mutation. The context named no separate review-pack artifact; reuse and caller context were inspected directly.

Evidence and remediation:

1. Failed Qwen processes can leave a mutated oracle.

   The new call site requires `check_qwen_output.py after` only for a Qwen **Success**. `qwen-integration.md:99` narrows this explicitly to exit 0. Its existing `Helper exits non-zero` path at lines 228–232 still directs the next attempt to Sonnet without requiring the guard or canonical-test restoration. The generic lost/hung-result recovery also has no Tess immutability check.

   Reproduction by following these model-executed instructions: prepare the clean snapshot; Qwen changes an implementation file and replaces a Tess assertion with `assert True`; its process then exits nonzero; follow the documented Sonnet fallback; Sonnet succeeds against those changed tests. Step 4 treats this as an ordinary Claude success and proceeds to staging/gating. None of the required call sites runs the guard on this sequence. A timeout after those writes creates the same missing check once the helper has stopped.

   PRD requirement: **any** Qwen mutation must be detected before staging or gate execution, and Sonnet must receive the original committed tests. Only the no-edit requirement is explicitly restricted to exit-zero success. Require canonical-test verification after every Qwen process termination, before accepting partial output or dispatching a fallback; preserve existing infra classification for non-success attempts whose tests are unchanged. Verify that a hung writer has stopped before restoration. Add a regression for mutation followed by nonzero exit and the timeout/recovery call site. The current tests exercise successful-output checks and therefore miss this integration path.

2. The dispatch self-check contradicts the new routing rules.

   `work/SKILL.md:305` deliberately retains persisted `qwen_eligible: true` on stale multi-file plans and stamps the eventual Claude attempt with `preflight_outcome: null` and runtime `qwen_excluded_reason: "files"`. At line 329 the self-check still reads the persisted eligibility and says that a Claude dispatch with null or healthy preflight means the table was skipped and must be run again. It explicitly permits only the breaker and memory-gate exceptions.

   Concrete case: `{model: "sonnet", qwen_eligible: true}`, two implementation paths, `_WORK_CODEX_RUNG=off`, no breaker or pressure event. The new model correctly selects Claude through row 7 and leaves the original task unchanged. The prose mandates null preflight. The immediately following self-check rejects precisely that valid result. Empty write sets and stale test-only sets have the same conflict. A one-file task whose healthy preflight succeeds but `check_qwen_output.py before` fails also intentionally selects Claude at line 321; the old self-check rejects its healthy preflight.

   Make the self-check consume the effective routing decision and explicitly recognize preparation failure as an authorized fallback. Keep the original protection against unexplained discretionary Claude dispatches. Pin these cases together with the self-check text so a local routing test cannot pass while the model-executed caller contradicts it.

3. A worked example still teaches the previous trust scope.

   `skills/plan-tasks/references/task-examples.md:102` describes eligibility splitting from `>=3` into `<=2` files. Lines 125–129 then keep `metrics.rs` plus its required `mod.rs` export together and say every resulting subtask routes to Qwen. That two-file verdict was permitted by the old three-file predicate but is false after this PRD. This is an active Step 4.6 example, not historical evidence.

   Phase 0 explicitly requires updating every worked example. Keep the correlated two-file implementation/export task together and mark it ineligible with `files`, subject to Codex/Claude routing; the independent one-file subtasks may use Qwen. Update the example's boundary language and prose coverage. The current absence checks only search the main SKILL or three-file spellings, so they miss this two-file claim.

Verification and remaining rubric assessment:

- Independently ran the five focused suites: plan prose, existing work routing, new trust routing, executable guard, and trust prose. Result: **241 passed in 4.38s**, no skips or xfails.
- Ran an additional temporary fixture through the actual guard CLI with a separate bare Git directory, an implementation filename containing spaces and `[abc]`, and a deleted canonical Tess test. Preparation and clean implementation acceptance returned 0; deletion rejection/restoration returned 1 with `qwen_test_mutation` and `tests_restored: true`. Canonical test contents and the clean index were verified. The fixture removed itself on exit.
- Parent supplied full-suite and completed release-check evidence: **2540 passed, 32 pre-existing skipped, 459 subtests passed**; plugin validation/release checks passed. Those broader checks were not redundantly rerun by this reviewer.
- New tests assert concrete routing, cause, restoration, index, worktree, and attribution outcomes; no constant assertions or either-or hedges were found. Context records fail-first execution before implementation. R2 passes; R1 fails on the uncovered integration paths above.
- Reviewed path validation, explicit Git context, literal pathspecs, subprocess argument lists, error exits, mutation precedence, foreign-dirt preservation, direct Sonnet escalation, and default/legacy breaker semantics. No new secret, command injection, swallowed error, debug/TODO placeholder, or unsafe restoration defect was found in the executable guard.
- Simplification review covered every scoped changed file: no additional concrete behavior-preserving simplification justified a finding. The guard reuses the routing classifier and existing test-path recognition. New/changed production functions remain within 50 lines. New files remain within 800 lines. The pre-existing 1,150-line `test_work_routing.py` only gains the required caller argument; its existing size excess is not reported as a new defect (R13 is scoped to introduced violations).

Disposition: rework the three findings, then repeat the independent review lenses.
