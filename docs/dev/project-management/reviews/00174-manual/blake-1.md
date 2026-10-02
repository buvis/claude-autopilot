# Blake review — PRD 00174, cycle 1

Verdict: FAIL. Two High, two Medium, one Low finding.

Reviewed independently from the PRD and B1–B19 rubric. Located the planner, routing model, output guard, call sites, tests, and runtime references directly. No implementation diff, changed-file list, design document, implementation summary, other review report, or session log was read. Findings and line numbers describe the sources inspected before remediation.

## Findings

### BL1 — High — Tess immutability is checked only after successful Qwen exits

- Location: `skills/work/SKILL.md:339`; `skills/work/references/qwen-integration.md:99`; `skills/work/references/gate-failure.md:226`.
- Requirement: Any Qwen mutation of Tess-owned paths must be detected before staging/gating, rejected with `qwen_test_mutation`, and restored before the Sonnet attempt.
- Evidence: Step 4 requires the guard for “A Success from Qwen”; the integration reference likewise says “Immediately after Qwen exits 0.” A hung/lost process instead enters the infrastructure-failure branch, which checks general working-tree status and re-dispatches without comparing tests to the test commit. The nonzero-helper section at `qwen-integration.md:228–232` sends the next attempt to Sonnet without requiring test restoration. The watchdog's post-kill rule at `subagent-dispatch.md:72–74` can independently run the task's verify commands against the surviving tree before a success classification.
- Consequence: Qwen can alter the implementation and weaken a Tess assertion, then crash or be killed. A continuation/Sonnet attempt can inherit the weakened oracle, and the watchdog can execute it. The mandatory guard does not cover that path.
- Required correction: Once the Qwen writer has stopped, check canonical Tess content on every result path before any fallback, continuation, or independent verification. Keep exit-zero-only no-edit classification separate from unconditional test-integrity checking.
- Rubric: B1, B5, B10, B15.

### BL2 — High — Git's assume-unchanged flag hides a changed Tess oracle from the guard

- Location: `skills/work/scripts/check_qwen_output.py:51–67`, consumed at `:105–109`.
- Requirement: Compare every Tess-owned path against `<test_commit_sha>`; any difference must reject the attempt.
- Evidence: The guard uses `git diff --name-only`, its cached variant, and an untracked-file listing. None verifies actual file bytes when Git is told to trust an index entry. An isolated Git fixture reproduced the bypass:
  1. Commit `impl.py` containing `answer = 0` and `test_impl.py` containing `assert answer == 42`.
  2. Run the real `before()` guard successfully.
  3. Run `git update-index --assume-unchanged test_impl.py`.
  4. Change the implementation to `answer = 1` and the test to `assert True`.
  5. Run the real `after()` guard.
- Observed output: `{'arm': 'pass', 'next': 'proceed', 'cause': None}` while the actual test bytes were `'assert True\n'`.
- Consequence: An altered test becomes the acceptance gate despite the deterministic immutability promise. The same issue can arise from a pre-existing index flag; no change to the snapshot JSON is needed.
- Required correction: Compare canonical test blobs against actual filesystem content/mode independently of Git's cached cleanliness assumptions, or explicitly reject relevant index states without modifying the user's index flags. Cover both preparation and post-dispatch checking.
- Rubric: B1, B5, B10, B14, B15.

### BL3 — Medium — The mandatory routing self-check contradicts stale-plan reconciliation

- Location: `skills/work/SKILL.md:329`, conflicting with `:305` and `:321`.
- Requirement: A stale eligible task with multiple paths must use an effective `files` exclusion, preserve planner metadata, and fall through the existing Codex/Claude fences; write-set exclusions record null preflight because no probe ran.
- Evidence: Line 305 explicitly requires that behavior. Line 329 instead tests the persisted `state.tasks[i].qwen_eligible == true` and requires a non-healthy, non-null preflight for a Claude dispatch; null means “you skipped the table; run it now.” Its only exceptions are breaker and memory-pressure rows. It does not exempt the new effective write-set fence, the test-only path, or failed guard preparation.
- Concrete trigger: A stale two-file Sonnet task, healthy infrastructure, and `_WORK_CODEX_RUNG=off`. Correct reconciliation selects Claude with `preflight_outcome: null` while leaving the stored flag true. The mandatory self-check rejects exactly that result and sends the orchestrator back through routing. Repeating the table cannot satisfy both instructions.
- Required correction: Apply the self-check to effective Qwen eligibility and explicitly account for pre-dispatch output-guard preparation failures.
- Rubric: B1, B3, B5, B15, B16.

### BL4 — Medium — Absolute write paths can be misclassified as test-only from directories outside the repository

- Location: `skills/work/scripts/work_routing.py:124–125`; `is_test_path()` at `:233–244`.
- Requirement: The routing model consumes the exact Ivan `FILE_PATHS` text and preserves Qwen eligibility for a one-file backend task. `/work` requires those paths to be absolute (`SKILL.md:298`).
- Evidence: `route()` passes absolute paths directly to `test_only_diff()`, whose underlying predicate is documented for repo-relative paths and matches every directory segment. An independently executed call with an otherwise eligible Sonnet task and healthy Qwen produced:
  - `/srv/project/src/app.py` → `{'implementor': 'qwen', 'tier': 'sonnet', 'rule': 'row5'}`.
  - `/srv/tests/project/src/app.py` → `{'implementor': 'claude', 'tier': 'sonnet', 'rule': 'test_only'}`.
- Consequence: Moving the same backend repository under a directory named `test`, `tests`, `spec`, `fixtures`, etc. disables Qwen and Codex for its production files. The task has not become test-only. Current new routing tests use repo-relative examples, so they do not exercise the required absolute-input contract.
- Required correction: Classify paths relative to the actual Git work tree, or carry a correctly derived test-only task fact into routing.
- Rubric: B1, B3, B15.

### BL5 — Low — The state-schema overview still excludes the new valid attempt values

- Location: `skills/run-autopilot/references/state-schema.md:181`, conflicting with `:182–183`.
- Requirement: The state contract and operator references must agree on runtime `files` exclusions and Qwen output causes.
- Evidence: The main `tasks[].attempts` object restricts `qwen_excluded_reason` to `memory_pressure|memory_probe_failed`; its prose says the field is absent otherwise. It also defines `qwen_gate_failed` only for a failed step-5.5 gate. The immediately following new authority rows allow runtime `files` exclusions and require `qwen_gate_failed: true` for pre-commit Qwen output rejections.
- Consequence: A consumer following the overview can reject or omit valid PRD-00174 telemetry. Adding the detailed rows leaves the existing object contract contradictory.
- Required correction: Update or deduplicate the overview's enum and field descriptions so the existing and new authority sections agree.
- Rubric: B1, B2, B16.

## Verification

- Focused plan/work/guard checks: **241 passed** in 3.89 seconds.
- Full repository suite: **2,540 passed, 32 skipped, 459 subtests passed**, four legacy-schema warnings, in 41.16 seconds.
- Additional temporary fixtures confirmed BL2 and BL4 against the actual Python implementation. The temporary repositories were automatically removed.
- Checked the one-file planner predicate, two-file split/coupling rules, stale multi-file Codex interception matrices, zero-path fallback, normal no-edit rejection, normal test-mutation restoration, both cause authority sections, Qwen3.8 qualification guidance, and the changelog entry.
- Repository plugin-validation/release commands were not executed in this audit. The full pytest result does not claim those separate commands passed.
- No implementation, state, or PRD file was edited. This report is the sole persistent review artifact.

## Rubric applicability

The PRD has phases 0, 1, and 2. B15 evaluates its Core/Phase 1 criteria; B16 evaluates Integration/Phase 2. B17 is vacuously satisfied because no Phase 3 is specified. The Phase 0 predicate and independent split rules were checked under B1. No new authentication, rate-limit, database, migration, or external dependency requirement is specified; the corresponding rules pass for the inspected scope. Internal guard CLI flags implement the requested capability rather than adding operator-facing product features.

## B1–B19 verdicts

B1: fail
B2: fail
B3: fail
B4: pass
B5: fail
B6: pass
B7: pass
B8: pass
B9: pass
B10: fail
B11: pass
B12: pass
B13: pass
B14: fail
B15: fail
B16: fail
B17: pass
B18: pass
B19: pass
