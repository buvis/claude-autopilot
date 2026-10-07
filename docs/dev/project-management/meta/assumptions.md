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

## 4: gate: per-row classification validation in gate --findings

Orchestrator:
- The acceptance criteria name `cli/test_gate_findings_table.py`, but that module is at 781 of its 800-line limit, so the tests live in a new sibling `cli/test_gate_findings_classification.py`. Like `cli/test_review_close_tail_sweep.py` from task 3, it is NOT yet listed in `dev/bin/release-checks` - task 7's scope.

Test author (Tess):
- `gate._findings_exit(text, ...)` accepts just the consolidated-findings section text, not necessarily a whole review file (the shape the sibling `_check` helper already feeds `_cross_check_findings`).
- The refusal line is the gate's whole stderr output (exactly one non-blank line); a prefix such as `gate: ` before it would still pass.
- `uncovered`/`mismatch` detail may land on stdout or stderr, so the ordering test asserts absence against the concatenation of both.
- `"fix "` and `1` were included as unknown values, extrapolated from "False for a non-string and for a wrong-case string".
- `"park"`/`"parked"` is the sixth-disposition probe for the derive-at-call-time test; the task names no such value, it is only a word absent from the real tuple.
- Four extra review rows (`R3`/`stale comment`/`src/d.py:30`, `R4`/`missing guard`/`src/e.py:40`) were invented for the four-row fixture; the task pinned no refs beyond R1/R2.
- Weak point 7 is pinned as `findings_verdict(...) != ("ok", None)` rather than by naming a new verdict tag, because the task describes only `_findings_exit` and the CLI. Today's unfiltered code already satisfies it; only a row-dropping implementation fails.
- `_is_chosen_finding`'s severity/file/issue/`found_by` validation is NOT re-pinned here: five tests in `cli/test_main_review_close_validation.py` already cover it.

Implementor (Ivan):
- The existing `return 2 if detail == _FINDINGS_PROBLEMS["unreadable-table"] else 1` tail was left as-is rather than reformatted into the design doc's two-statement form; behaviourally identical.
- `_is_chosen_finding` was wired to keep reading the module-level `_KNOWN_CLASSIFICATIONS` (now aliased to the gate's tuple) rather than calling `gate.known_classification`; the brief permitted either, and this needed no change inside the function.
- `cli/__main__.py` is 1671 lines, already far over the 800-line limit before this task. Pre-existing; untouched beyond the one-line change.

## 5: phase-review and recovery prose: the re-queue records the carry link the code checks

Implementor (Ivan):
- `recovery.md` cross-references phase-review's conditional-union computation instead of repeating the five-line block; the task said "computed the same way" without demanding duplication. The test therefore asserts the union lines in phase-review only, and the keys in both payloads.
- The `### Full Consensus` / `### Majority Consensus` / `### Minority` subheadings were dropped from the Review Summary Format template, their information preserved in the table's Consensus column; a single pipe table has no room for bucket subheadings and `consolidate_findings.py` emits one flat table.
- Step 4's "These two fields" phrase was rewritten to name `escalation_reason` and `escalated_from`, because the payload now carries four fields and the phrase no longer resolved. The task did not name that phrase.
- The decision-gate refusal sentence said "Phase 5 step 4", following phase-review.md's own wording, even though recovery.md calls the same step "Phase 6 step 4"; the pre-existing inconsistency was left alone. (The deslop pass then removed that sentence as duplicative.)
- Test line width targeted at 88 columns (black default), inferred from the existing wrapped constants rather than read from `pyproject.toml`.

Self-deslop pass:
- Removed the "Phase 5 step 4 and the Fable rescue gate ... are the only two sites" sentence from phase-review.md's `chosen_findings` paragraph and the "(the existing list is kept only when `carry_cycle` already equals `state.cycle`)" parenthetical from recovery.md, both as duplicative of adjacent text. The 4 prose tests stayed green after each removal.

## 6: low-severity review-verb corrections #12, #13, #14, #17, #20, #24

Orchestrator:
- The acceptance criteria name tests in `cli/test_review_close.py`, but that module is at 763 of its 800-line limit, so the seven tests live in a new sibling `cli/test_review_close_lowsev.py`. Like task 3's and task 4's siblings, it is NOT yet listed in `dev/bin/release-checks` - task 7's scope, which now has SIX files to add, not five.
- The task's file list omitted `cli/test_review_close_apply.py`, but three pins there encode the old contract #13 and #17 replace. The implementor reported it as a blocker rather than editing outside its allowlist; the orchestrator verified the three failures and retargeted them (absent-persona lens map to `lost`, the deferral entry to six keys, the dispatch assertion to per-row `ok`/`lost`). A planning gap in the file list, not a defect.
- `cli/state.py` arrived dirty with a loupe trailing-comma reflow and was reverted with `git checkout`, not committed. The `.bak` rollback write at `state.py:161` was confirmed intact afterwards - Devon had edited that exact line as an exploit and restored it correctly.
- Five LOW findings from the per-task review were noted and not fixed, per the LOW-only ladder. One is a real contract deviation worth the review phase's attention: #24 specifies the shape check `^[A-Za-z0-9._][A-Za-z0-9._-]*$`, and the implementation tests only `startswith("-")`, so an id containing whitespace still reaches the argv. The other four: a stale `_cross_check_findings` docstring, no de-duplication of repeated refs in the uncovered message, the `lost` mapping expressed two different ways across the two planes, and `test_refused_repeat_leaves_backup_untouched` pinning three first-time refusals rather than a repeat call.

Test author (Tess):
- `#17`'s `"skipped"` clause is lens-plane only: `record_dispatch.OUTCOMES` has no `"skipped"` member and `test_every_dispatch_outcome_is_recordable` pins `_DISPATCH_OUTCOME.values() <= OUTCOMES`, so a `disabled` persona's dispatch row keeps `"ok"` while its lens stays `"skipped"`.
- `#24`'s refusal lands in the producer (`review_close`'s dispatch-row path) and drops only the offending row while the batch still applies, matching the existing best-effort dispatch-row behaviour.
- A consolidated-findings ref must match gate's `_REF_CELL_RE` (`^R\d+$`), so the runtime-minted refs that defeat a constant refusal message are `R` + digits from one `uuid4()` with +1/+2 offsets.
- The lens vocabulary: absent from `agents:` is `"lost"`, an unrecognized status (e.g. `unavailable`) is `"failed"`, `disabled` is `"skipped"`. The requirements pin only the dispatch plane's `"lost"` explicitly; `schema.py` constrains no `review_lenses` value.
- A `decision-gate` close with an empty findings list and a review file carrying no consolidated section applies (the legacy "malformed" verdict is surfaced, not refused); used as the applied control in the backup test.

Implementor (Ivan):
- The uncovered-refs message wording is the implementor's; the tests pin only that it contains each uncovered ref, contains "classification", excludes the covered ref, and ends with the carry hint.
- Uncovered refs are listed in consolidated-table order, since no test pins an order.
- An absent persona's dispatch outcome is expressed as a `None` key in `_DISPATCH_OUTCOME` rather than a branch; a status present but unrecognized keeps today's `"ok"` dispatch default.
- Tail-sweep `lenses_closed` is emptied in `_mutation_context` (one place feeding both the result and the mutator) rather than only in `_close_result`.
- `skills/work/scripts/record_dispatch.py` was not changed: `argparse` already rejects a dash-led positional and `"lost"` was already in `OUTCOMES`.
- `state-schema.md`'s lens vocabulary was not updated to document `"lost"` (outside the allowlist) - a follow-on.

