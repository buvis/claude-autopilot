---
prd: dev/local/prds/wip/00183-make-batch-report-decisions-and-implementor-mix-render-v1.md
review: 1
date: 2026-09-07
head_sha: 91c1ab32f9cc4e5dc6f66564c02980a56d989c28
codex_thread_id: 01a07a92-48e9-73f1-9afc-2647a705c50a
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00183-make-batch-report-decisions-and-implementor-mix-render-v1

Diff range: `479142e61a38418b4da53c21cd773ca1767c589f..91c1ab32f9cc4e5dc6f66564c02980a56d989c28`

codex_rung_guard: not fired

pack: unavailable (`engram pack` exited 1 — "not inside a registered repo; register it in /Users/bob/.config/gita/repos.csv"). Deterministic configuration failure, not retried. The review is degraded on retrieval context, not invalid. Blake never receives a pack by design.

## Review Summary

Reviewed: 7 completed tasks
PRDs checked: 00183-make-batch-report-decisions-and-implementor-mix-render-v1

Cycle 1, **full review** of the PRD's whole work range (18 commits). This repo
commits onto `master`, so `gather-context.sh`'s branch-base detection resolves
`master == HEAD` and would have produced an EMPTY diff; the script was run with
`--since <work_start_sha>` instead, and the context file's diff-scope line was
corrected to say full review. 124 KB diff, 15 files.

### Agent Status

- Alice: ✅ Available (consensus lens, `legacy` engine)
- Blake: ✅ Available (blind lens, PRD-only)
- Bob: ✅ Available (doubt + de-slop lens, codex — fresh thread `01a07a92-48e9-73f1-9afc-2647a705c50a`, first dispatch succeeded)
- Carl: ✅ Available (backend `copilot`, model `gemini-3.8-flash`)
- Eve: ⏸️ Disabled — the codex doubt-roster guard did not fire (0 codex-implemented tasks; all 8 attempts across 7 tasks carry `implementor: claude`)

### Cycle notes (fail-loud)

1. **The fail-first replay block fed to the reviewers was substantially wrong,
   and this is the cycle's most important finding.** It reported 51 of 89 touched
   tests as "passing against the pre-change code". Alice independently
   distrusted it and re-ran the replay herself; the orchestrator did the same in
   a separate `git worktree` at `479142e`. Both reached the same conclusion:
   **`replay_tests_against_base.py` credits a pytest `subTest` parent node as
   passed.** A `unittest` test using `self.subTest` whose every subtest fails
   surfaces as `SUBFAILED(...)` lines with the parent node reported `.`, and the
   script reads that as a pass. Measured refutations against base:
   `test_cycles_falls_back_to_completed_prd_record` (2 subtests failed,
   `'- Cycles: 4' not found`, base renders `?`), `test_every_issue_alias_feeds_the_issue_cell`
   (4 subtests failed), `test_every_reason_alias_feeds_the_reason_cell` (2 failed),
   `test_an_empty_earlier_alias_falls_through_to_the_next_one` (3 failed),
   `test_disposition_renders_as_action` (failed outright), and the whole
   `AlternativeVocabularyEntryTest` / `AssumedAmbiguityEntryTest` /
   `AddedDecisionScopeTest` / `ExistingDecisionEntriesTest` group. All six
   `[MECH]` replay rows are discarded in the ledger with their measurement, and
   the tool defect is deferred to batch end. **R2 passes on the evidence, not on
   the block.**
2. **Five tests genuinely do pass against base, and that is correct.** Verified
   separately: `test_cycles_ignores_bare_string_and_other_prd_entries`,
   `test_cycles_renders_question_mark_when_the_record_lacks_cycles`,
   `test_present_zero_state_cycle_is_not_replaced_by_the_batch_record`,
   `test_state_cycle_wins_over_a_differing_batch_record`, and
   `test_the_existing_positional_calls_read_no_ledger` are precedence and
   backward-compatibility guards — they pin behavior that must NOT change.
3. **The build gate's carry-forward item 4 was disputed and is resolved AGAINST
   the code.** Alice showed that removing the `prd`/`batch_id` filter alone makes
   `test_rows_for_another_prd_or_batch_are_not_counted` fail, and called the item
   resolved. The orchestrator then ran the COMBINED mutation the carry-forward
   actually described — no filter AND a dedup keyed on `(attempt, implementor)`
   instead of `(task_id, attempt)` — and the test **passes**. So the fixture does
   not independently pin the filter. Bob and Carl are upheld; Alice's refutation
   covered only the single mutation.
4. **Consolidation needed a documented hand-merge.** `consolidate_findings.py`
   ran clean but under-merged three defects that all four reviewers described in
   different words at the same file: the unreadable-ledger gap (3 separate rows),
   the `test_schema.py` size (2 rows), and the `str.find` anchor weakness (2
   rows). They are merged below with their true consensus; the script's raw
   output is unmodified on disk.
5. **The mechanical-facts block was passed by reference, not inlined.** The full
   `ast` table (32 KB across 15 files) was written to `/tmp/mechfacts-00183-c1.md`
   and the context file carries a pointer plus the subset of functions this diff
   touches. Cost: Carl's sandbox refused to read `/tmp` ("Permission denied"), so
   he computed his own counts with `wc -l` and an `ast` script instead. No wrong
   line-count claim resulted — his numbers agree with the block — but the block
   did not reach every reviewer as intended.
6. **No verification-check queue was written.** Eve did not run, and
   `references/output-formats.md` reserves `source: "bob"`, so Bob's VERIFY
   bucket produces no queue entries. Both his VERIFY items were executed by the
   orchestrator during this cycle instead (note 1 above, and the recorded
   verification below).
7. **Four orchestrator-verified confirmations.** Findings 1, 5, 6 and 7 in the
   table below were reproduced directly rather than taken on a reviewer's word.

## Consolidated Findings

24 script rows → 7 merged into 3 → **18 findings**, of which 6 `[MECH]` replay
rows are discarded and 2 are deferred as out of scope. **2 unresolved High.**

| Consensus | Severity | Issue | File | Found By |
|-----------|----------|-------|------|----------|
| [3/4] | 🟠 High | `test_schema.py` is 1400 lines against the project's 800-line maximum, and 648 of those lines came from this diff. The build's own style gate flagged it (`failed:FILE ... 1400 lines`) and left it unfixed. Split the decision-contract suite into a sibling module. | skills/run-autopilot/cli/test_schema.py | Alice, Bob, Carl |
| [1/4] | 🟠 High | `_validate_added_decision_entries` decides "added" by value membership (`entry not in before`), so appending a second copy of an entry that already exists skips validation entirely. **Verified:** with `before` holding `{"cycle": 1}`, appending another `{"cycle": 1}` is ACCEPTED, while the same append against an empty list is correctly rejected. The PRD's Behavior line says the contract applies to "entries that were added", and a duplicate WAS added. Use a multiset diff (consume each existing occurrence once). | skills/run-autopilot/cli/schema.py | Bob |
| [3/4] | 🟡 Medium | `_ledger_rows` emits no stderr line when the ledger exists but cannot be opened, because `is_file()` succeeds and `load_rows` swallows the `OSError`. **Verified:** missing file → warns; directory → warns; `chmod 000` regular file → **silent**. The PRD requires "a missing or unreadable ledger is an empty list and one stderr line". | skills/run-autopilot/cli/render_report.py | Alice, Bob, Carl |
| [3/4] | 🟡 Medium | `test_phase_review_append_names_the_decision_keys` locates each append site with `str.find`, which returns the first match, so an earlier decoy section repeating both anchors plus the literal shape shadows the real sites. One-line closure: `self.assertEqual(self.phase_review.count(anchor), 1)` before each `find`. Also the build gate's own carry-forward item 1. | skills/run-autopilot/scripts/test_review_prompt_contracts.py | Alice, Bob, Carl |
| [2/4] | 🟡 Medium | The ledger fixtures do not isolate the `prd`/`batch_id` filter from dedup collisions. **Verified by combined mutation:** unmutated → PASS; filter removed only → FAIL; filter removed **and** dedup keyed on `(attempt, implementor)` → **PASS**. Give each foreign row an implementor that appears nowhere locally, and add two local tasks sharing both an attempt number and an implementor asserting the count is 2. | skills/run-autopilot/cli/test_render_attempt_ledger.py | Bob, Carl |
| [1/4] | 🟡 Medium | `_implementor_mix`'s early return on an empty attempts union also drops the exclusion, codex-probe and breaker lines. **Verified as a REGRESSION:** for populated tasks with zero attempts, base `479142e` rendered `Excluded from qwen: ui 1, tier 1 ...`, `codex probe: not run` and `capability breaker: not tripped`; HEAD renders only `no implementor data`. Base guarded on `if not tasks`, HEAD on `if not attempts`. The task brief said `_exclusion_line` is "unchanged by this task". Reachable whenever the ledger is missing or unreadable — which finding 3 makes silent. | skills/run-autopilot/cli/render_report.py | Bob |
| [1/4] | 🟡 Medium | Truthy non-string values shadow a valid prose alias in the Issue cell. **Verified:** `{"cycle": 1, "issue": 7, "question": "actual finding", ...}` is ACCEPTED by the schema (the pair is satisfied by `question`) and renders `7` as the Issue while the real text is dropped. Validator and renderer disagree about which key wins. Select the first non-empty **string** across the chain. | skills/run-autopilot/cli/render_report.py | Bob |
| [1/4] | 🟡 Medium | `_autonomous_row`'s Issue chain checks `decision` before `finding`, so the observed `{type, task, finding, decision}` shape renders the resolution text as the Issue and drops the finding text. The investigation file maps `finding` → `issue` but `decision` → "issue (short ones) or reason". | skills/run-autopilot/cli/render_report.py | Alice |
| [1/4] | 🟡 Medium | The schema tests exercise `validate_changed` directly but never pin the CLI contract the PRD's own success metric names: exit 1, the exact `rejected: autonomous_decisions entry missing issue` line, and a byte-identical state file. Add a subprocess regression test. | skills/run-autopilot/cli/test_schema.py | Bob |
| [1/4] | 🟡 Medium | Nothing pins the CLI ledger wiring. **Verified:** `attempts_ledger` appears only inside `render_report.py`; `__main__.py:787` passes the path positionally, and `test_render_cli.py` contains no occurrence of `ledger` or `attempts`. Deleting line 787 would leave every added ledger test green, because they all call `prd_section` directly. This is PRD success metric 3, untested end to end. | skills/run-autopilot/cli/test_render_cli.py | Bob |
| [1/4] | 🟡 Medium | The missing-ledger and directory-ledger cases each repeat setup and rendering across two tests. Consolidate each pair while keeping the heading, no-data, path and exactly-one-warning assertions. | skills/run-autopilot/cli/test_render_attempt_ledger.py | Bob |
| [1/4] | ⚪ Low | `test_unreadable_ledger_is_reported_once_on_stderr` and `test_unreadable_ledger_renders_without_implementor_rows` use `self.ledger.mkdir()` — a directory, not an unreadable file — so despite their names they exercise the `is_file()` branch and never reach the permission-denied path that finding 3 shows is silent. | skills/run-autopilot/cli/test_render_attempt_ledger.py | Carl |
| [1/4] | ⚪ Low | Two new cycle tests do not discriminate against pre-change code for their chosen inputs, since the old code renders `?` unconditionally; each is paired with a sibling that does pin the real behavior. | skills/run-autopilot/cli/test_render.py | Alice |
| [1/4] | ⚪ Low | Phase 1's acceptance names `test_complete_prd_count_matches_rendered_rows`, which does not exist; `test_persisted_autonomous_count_matches_rendered_autonomous_data_rows` covers the same intent. Already recorded as an autonomous decision at build time. | skills/run-autopilot/scripts/test_statectl_complete_prd.py | Blake |
| [1/4] | ⚪ Low | Cannot statically verify that the final test suites and release checks pass (codex sandbox). Answered by the recorded verification below. | N/A | Bob |

### Deferred to batch end (out of this PRD's scope)

| Consensus | Severity | Issue | Reason |
|-----------|----------|-------|--------|
| [2/4] | 🟡 Medium | `_run_render` is 111 lines against a 50-line limit | Pre-existing: `ast` puts it at 105 lines in base `479142e`; this PRD added 6 lines of argument wiring. Bob placed it in KNOWN for the same reason. Restructuring an unrelated dispatcher breaks the surgical-changes rule. |
| [1/4] | 🟡 Medium | The PRD's Phase 0 acceptance command names `cli/statectl.py`, which exits 1 with `ImportError` | Requirements ambiguity, not an implementation defect. **Verified:** `scripts/statectl.py` prints exactly `rejected: autonomous_decisions entry missing issue`, exits 1, and leaves the state file byte-identical (md5 unchanged). PRD wording needs the correction, not the code. |
| [2/4] | 🟡 Medium | `replay_tests_against_base.py` credits a `subTest` parent node as passed | Not in this diff. Silently weakens the fail-first evidence every future cycle depends on. See cycle note 1. |

### Auto-dismissed (ledger)

None — cycle 1 had no prior ledger, so the `--ledger` flags were correctly omitted.

## Alice

Consensus lens, implementation-aware. Six findings (1 High, 3 Medium, 2 Low).
Independently re-ran the fail-first replay in her own base worktree and corrected
the supplied block before using it — the same conclusion the orchestrator reached
separately. Ran all three PRD success-metric commands directly. Judged the entry
contract, the alias logic, the ledger-backed mix, the Cycles fallback, the doc
updates and the `__main__.py` wiring to match the PRD precisely.

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
R12: fail
R13: fail

## Blake

Blind lens, PRD-only, no diff and no file list. Located the implementation
himself and ran the PRD's literal acceptance commands. Two findings; his B15
fail is the Phase 0 acceptance command that names a library module rather than
the CLI entry point — reproduced and deferred as a PRD-wording correction.

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
B15: fail
B16: pass
B17: pass
B18: pass
B19: pass

## Bob

Doubt + de-slop lens (codex, static-only sandbox). Thirteen findings — the
deepest set this cycle, and the only reviewer to find the validation hole
(finding 2), the diagnostic regression (finding 6) and the non-string alias
shadowing (finding 7), all three of which the orchestrator then reproduced. His
prompt inlined the context and diff verbatim (157 KB) because the codex sandbox
cannot open paths, and forbade line-number suffixes on `File:` values;
consolidation ran clean with no hand-merge needed on his rows. Both his VERIFY
items were executed this cycle.

FIX: 10 items. VERIFY: 2 items (both executed — see cycle note 1 and the
recorded verification). KNOWN: 1 item (oversized render dispatcher, deferred).

R1: fail
R2: fail
R3: pass
R4: pass
R6: pass
R7: fail
R8: pass
R9: fail
R10: fail
R11: pass
R12: fail
R13: fail

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

Backend `copilot`, model `gemini-3.8-flash`. Five findings. Ran the full test
suite and `dev/bin/release-checks` himself. First to isolate that the two
`test_unreadable_ledger_*` tests use a directory rather than an unreadable file,
which is what masks the silent permission-denied path. His sandbox refused to
read `/tmp/mechfacts-00183-c1.md`, so he recomputed the line counts himself; they
agree with the block.

R1: pass
R2: pass
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: pass
R10: fail
R11: pass
R12: pass
R13: fail

## Mechanical checks (computed)

- **Tautological test shapes:** clean. 251 test functions across 8 changed test
  files; no constant, self-comparing, hedged or assertion-free test found.
- **Fail-first replay:** 6 `[MECH]` rows, **all discarded** — see cycle note 1
  and the ledger. The tool miscounts `subTest` failures.
- **Mechanical facts:** full `ast` table at `/tmp/mechfacts-00183-c1.md`. Two
  countable claims in this review cite it: `test_schema.py` at 1400 lines
  (`wc -l`, independently confirmed by Alice and Carl) and `_run_render` at 111
  lines (`ast`, base 105).

Verdict: 18 findings
Tests: 2737 passed, 0 failed, 1 skipped (reused from last-verification.json at 91c1ab32f9cc4e5dc6f66564c02980a56d989c28)
