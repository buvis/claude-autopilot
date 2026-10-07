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

