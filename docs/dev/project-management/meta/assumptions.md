# Assumption ledger — PRD 00265 (close the critical-row escapes)

## 1: gate: fail-closed findings-table parse plus the Ref-column fixture migration

Test author (Tess):
- `R1 | R3` ("two refs in one cell") is written as raw unescaped text, so the row carries one cell too many; an escaped `R1 \| R3` single-cell variant is not tested.
- "An EMPTY findings section" means a section with no findings rows at all, not a table header with zero data rows (the latter is `unreadable-table` today).
- The migrated shared fixtures use refs `R1`, `R2`, `R3` in table order and drop the `### Full Consensus (n/n)` subsection headings, so each section holds one contiguous table.
- `known_classification` returns `False` (not raises) for non-strings and for wrong-case strings such as `"FIX"`.
- `_cross_check_findings`'s third parameter is positional-or-keyword; the alias test calls it both ways.
- A `discard` row may be a bare `{"ref": ..., "classification": "discard"}` when it goes straight to `_cross_check_findings`, but needs the full severity/file/issue/found_by fields when it passes through the CLI's `_is_chosen_finding` gate.
- Header-name matching case and padding (`| ref |`, `|  Ref  |`) are unpinned by the requirements, so neither was asserted.
- Ghost `verify` and `discard` rows stay exempt from the cross-check; only `fix`, `defer`, `carry` were asserted.
- A findings row carrying only `ref` + `classification` is checked on its ref alone (severity/file only when present).
- A bullet-shaped row inside a Ref-bearing table section parses as a row with an empty ref.
- `gate._findings_exit` takes the findings file, not a verdict tuple, so requirement 10's mapping is asserted through the `gate --findings` CLI, one run per verdict tag.

Implementor (Ivan):
- "One new problem value in `_reviewed_keys`'s vocabulary: `ref-required`" was read as "add the message under that key to `_FINDINGS_PROBLEMS`", not "let `_reviewed_keys` return it" — three tests assert `_reviewed_keys` returns `err is None` for a ref-less section.
- A findings row with an empty or missing `"ref"` is skipped by the duplicate-classification check; otherwise the 18 ref-less rows of the real 00256 fixture would collide with each other.
- The duplicate-classification check runs before the ref-required check, per the design's numbered order; no test exercises a section that would hit both.
- Conflict detection reports the FIRST ref whose classification disagrees with its first-seen value, naming those two classifications in first-seen then conflicting order.
- Missing `classification` is compared as `None` in that check, so a ref carrying one row with a classification and one without is reported as a conflict. No test covers that pair.
- The style limit counts a function from its `def` line through its last body line inclusive.
- `_ref_conflict_verdict` / `_unbacked_verdict` naming and placement were free choices; extracting the two helpers the prompt named as examples would have reached only 52 lines.
- The comment above `TABLE_HEADER_5` documented only that binding, so it was removed with it; the design doc's prose reference to `TABLE_HEADER_5` was left alone (docs outside the allowlist).

## 2: review_close: findings_verdict, refuse unreadable-table, refuse an unmatched carry pre-lock

Test author (Tess):
- The six refusal kinds with unspecified preconditions (`carry_in_tail_sweep`, `tail_sweep_before_decision_gate`, `tail_sweep_empty`, `tail_sweep_above_medium`, `tail_sweep_duplicates_deferral`, `already_applied_duplicate`) are exercised through `cli_main.main()` with `review_close.close` stubbed, not through a real refusal.
- Any result carrying a `refused` key maps to exit 2, including a kind not in today's list; the spec's "anything else still exits 1" example is a result with no `refused` key.
- The `carry_unmatched` refusal names the FIRST unmatched carry row in findings-JSON order (the spec gives one reason template but no ordering rule).
- `close()` reads `gate._FINDINGS_PROBLEMS` at call time, not a module-level snapshot, so a test may re-word the no-section problem.
- A batch whose table reads cleanly returns no `findings_cross_check` key at all.
- `status="failed"` and `status="parked"` back a carry; only `completed` disqualifies, per the literal requirement.
- `escalation_reason: "model_floor"` is an invented stand-in for "an escalation reason that is neither `review_flag` nor `fable_rescue`".
- The tail-sweep carry test asserts only `refused != "carry_unmatched"`, because task 3 may add a `carry_in_tail_sweep` refusal on the same input.
- `test_review_close.py` exceeding 800 lines was treated as a size-limit violation and fixed by splitting 17 pre-existing tests verbatim into `test_review_close_apply.py`.

Implementor (Ivan):
- **The design contract's `_EXIT_2_REFUSALS` tuple was NOT implemented**; the mapping is `return 2 if result.get("refused") else 1`, because `test_a_refusal_kind_outside_todays_list_also_exits_2` requires an unlisted kind to exit 2 and the enumerated tuple cannot pass it. The enumerated list survives only in the design doc and the CHANGELOG prose.
- The carry loop lives in `_carry_refusal` rather than inlined in `close()`, and the style-limit fix further extracted `_findings_refusal` and `_prelock_refusal`; all pure extractions, same order and payloads.
- `state_mod.load()` raising `state.StateError` on a missing or corrupt state file is acceptable in its new, earlier position: `statectl.mutate` raised the same error slightly later and `_run_review_close` catches it and exits 2.
- The pre-lock already-applied check rebuilds `f"{review_file.resolve()}::{batch_id}"`, duplicating the identity `_mutation_context` builds; no test pins where the string is built.
- The style-limit fix moved `close()`'s refusal-name prose into `_findings_refusal`'s docstring, since the docstring counts toward the measured span.

## 3: review_close: tail sweep refused before the decision gate, above medium, or empty

Orchestrator:
- The task's write-set was extended by `cli/test_review_close_apply.py`: its `test_close_tail_sweep_skips_lens_verdict_and_dispatch_row_steps` asserted that an empty tail sweep applies, which this task deliberately turns into a refusal. The test was updated (decision-gate entry seeded, one Medium row passed), never weakened.
- The acceptance criteria name `cli/test_review_close.py`, but that module reached 750 of its 800-line limit, so the four non-acceptance tests live in a new sibling `cli/test_review_close_tail_sweep.py` that imports its fixtures. That new file is NOT yet listed in `dev/bin/release-checks` - task 7's scope.
- `check_split_hygiene.py` reports `LOW` at `test_review_close.py:188` as an unused module-level binding. It is a false positive of a per-file checker (the sibling module imports and uses it), so no deletion was dispatched and the gate is recorded as `failed:` rather than fixed.

Test author (Tess):
- An accepted tail sweep writes through the same classification machinery as a decision-gate batch (fix -> rework task + `rework_task_ids`, defer -> `deferred_decisions`): taken from already-passing tests in `test_review_close_apply.py`, not from the task text.
- Nothing is asserted about an `autonomous_decisions` key for a swept row: no requirement or existing test pins its name or shape, so pinning it would have invented a contract.
- A gate failure's reason contains "no verdict line" and its result may carry no `refused` key at all; the gate test asserts only that the kind is not a `tail_sweep_*` one. The gate's ordering against the five tail-sweep checks is not asserted.
- A LOW-severity `fix` row's task-creation behaviour is unspecified, so the clean-sweep test asserts task creation only for the Medium row.
- Refusal reason wording is asserted by substring (the colliding ref/file, the severity emoji), never by exact phrasing, except the two reasons the contract gives verbatim.

Implementor (Ivan):
- `(severity, file)` normalization for the deferral match is `str(value).strip()` on each field. The task said to reuse a `_backed()`/`_finding_key` helper "already in this module"; neither exists in `review_close.py` (they are private to `cli/gate.py`, and `_finding_key` is a three-part key including the issue), so a local `_severity_file_key` was written instead.
- A `deferred_decisions` entry that is not a dict is skipped rather than raising; no test exercises a malformed entry.
- The above-medium reason names a row by `ref` only when `ref` is truthy (falling back to `file` for an empty-string ref), rather than the design block's `dict.get`-default semantics, which would name an empty string.

