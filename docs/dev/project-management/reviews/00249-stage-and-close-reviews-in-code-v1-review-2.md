---
prd: docs/dev/project-management/prds/wip/00249-stage-and-close-reviews-in-code-v1.md
review: 2
date: 2026-10-04
head_sha: 5d1bf4fd52fb6608d85f9f03d056e975568cd427
codex_thread_id: 01a107c0-74ec-7b42-8214-20eb3fb3eccf
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00249-stage-and-close-reviews-in-code-v1

Diff range: `b2afd0bf0c6fbfb99d046e4a99af3a630c916914..5d1bf4fd52fb6608d85f9f03d056e975568cd427`

codex_rung_guard: not fired

Consensus engine: legacy. Incremental review, cycle 2, scoped with
`gather-context.sh --since b2afd0bf0c6fbfb99d046e4a99af3a630c916914`
(cycle 1's `head_sha`). Bob resumed his cycle-1 codex thread via
`--resume-thread 01a107c0-74ec-7b42-8214-20eb3fb3eccf`.
Context pack: `docs/dev/tmp/engram-pack-00249c2.md` (2330 tokens).
Carl ran on the copilot backend, model `gemini-3.8-flash`, exit 0.
Reviewer prompts and inputs were staged by hand (a deterministic assembler
over the agent registry): the installed pack is 0.8.0, which predates the
`review-stage` verb this PRD adds, so this cycle ran the 0.8.0 prose path
again. That is the same constraint cycle 1 recorded, not a new one.

## Consolidated Findings

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [3/4] | 🟠 | Settled-ledger and prior-findings wiring exists in code but the skill prose contradicts it. stage() now passes `prior_findings` through, and the CLI has `--settled-ledger` and `--prior-findings`. The rework left SKILL.md:216-218 ("`review-stage` takes no ledger input ... append with the Edit tool") and SKILL.md:248 ("`review-stage` renders no incremental addendum, so append it with the Edit tool") untouched. The step 3 command synopsis at SKILL.md:153 does not list either flag. Cycle 2 and later still fall back to the hand-editing this PRD removes, and the new flags have no caller | skills/review-work-completion/SKILL.md:216 | 8 | ALICE, BLAKE, BOB |
| [3/4] | 🟠 | `run_gate` is still 75 lines (verification.py:125-199) and still buffers all output through `communicate()`, so memory stays unbounded. Only `_cap` was changed to keep the tail. The cycle-1 finding asked to split the result-building and timeout branches and to drain with bounded buffers. Only the tail-keep fix landed, and the rest is deferred in assumptions.md only | skills/run-autopilot/cli/verification.py:125 | 8 | ALICE, BOB, CARL |
| [2/4] | 🟠 | Cycle-1 finding 1 only half fixed. close() now reads per-persona outcomes and maps `disabled` to `skipped`, but nothing documents the review-file frontmatter it parses. `dispatch_rows:` is still absent from skills/review-work-completion/references/output-formats.md:253 (the `agents:` block lists only alice, bob and carl) and from SKILL.md step 8, so no model stamps it and the dispatch-row ending in review_close.py:308 stays dead. Blake's (`blind`) and Eve's (`fable`) lenses are still stamped `running` by stage() and never closed. The rework deferred this in docs/dev/project-management/meta/assumptions.md only; the deferred-decisions JSON has no entry for it | skills/review-work-completion/references/output-formats.md:253 | 8 | ALICE, BOB |
| [2/4] | 🟠 | Cycle-1 finding F3 only half fixed. `_prd_body` and `prd_body` feed Blake only. Eve's run inputs (`_eve_inputs`, review_stage.py:515) still use `run["prd"]`, the merged PRD plus design doc. SKILL.md:167 states that doubt review must stay PRD-only and that the design doc belongs on neither surface. The new design-marker test covers Blake only | skills/run-autopilot/cli/review_stage.py:515 | 8 | ALICE, BOB |
| [2/4] | 🟠 | The release-checks summary line reports check-block counts, not test counts. `PASS $(grep -c '^echo "\[checks\]' "$0") FAIL 0 SKIP 0 EXIT 0` yields the number of check blocks, which run_gate writes to last-verification.json and stage() prints as the `Tests:` line. That is a misleading count later cycles reuse as real. No test pins the summary line or the grep count | dev/bin/release-checks:214 | 9 | ALICE, BOB |
| [2/4] | 🟠 | `reuse_verdict` docstring still says `git status --porcelain` must be empty (verification.py:78-80). The code now ignores dirty paths under the store. Fix the contract text. Separately, `line[3:]` on a porcelain rename entry `docs/dev/project-management/x -> src/y` passes the store-prefix check on the old path, so a staged rename out of the store is treated as clean (low risk, fail-open) | skills/run-autopilot/cli/verification.py:78 | 1 | ALICE, BOB |
| [1/4] | 🟠 | review-close does not read a findings block from the review file. It takes a separate `--findings` JSON file that the model writes with the Write tool, and `gate` never checks it against the consolidated table. The spec's "second source of truth" risk names this check as required (`gate` must verify block and table agree). `rg` of `skills/run-autopilot/cli/gate.py` for findings/json shows no such check. The finding rows can therefore drift from the review table | skills/run-autopilot/cli/__main__.py:1021 | review_close | BLAKE |
| [1/4] | 🟠 | F2: Unavailable reviewers map to unsupported dispatch outcome "failed"; record_dispatch accepts "error", so closure fails | skills/run-autopilot/cli/review_close.py:48 | 8 | BOB |
| [2/4] | 🟡 | review_stage.py is now 823 lines, over the 800-line limit. The rework added helpers (`_build_summary`, `_append_context_blocks`, `_prd_body`) plus prop-up reflow without extracting anything, so it crossed the limit. The file-length gate also failed per assumptions.md | skills/run-autopilot/cli/review_stage.py:823 | 8 | ALICE, CARL |
| [1/4] | 🟡 | The new rework behaviours are mostly untested. Added tests cover only the found_by suffix, the codex-guard pass-through, the tail-sweep skip, the dirty-store reuse, the keep-tail cap, and the `ui` lens stamp. Nothing pins `autonomous_decisions` being written (including the emoji-to-word severity map), `disabled` mapping to `skipped`, the per-status `--outcome` mapping (the only assertion, test_review_close.py:423, still expects `ok`), the `--require-codex-guard`, `--settled-ledger` or `--prior-findings` CLI flags (test_cli_review_verbs.py has none), or the CLI rejecting "fxi" with exit 2. The `_is_chosen_finding` tests are unit-level only | skills/run-autopilot/cli/test_review_close.py:403 | 8 | ALICE |
| [3/4] | 🟡 | The tail-sweep prose test still hedges: test_rework_groups_prose.py:81 keeps `"at most 4" in section or "caps at 4" in section`, and phase-review.md carries only "at most 4, never zero", so the `or` is a vestigial either-or branch. The commit split the floor into its own assert (which is the real cycle-1 complaint, now fixed), but the cap assert still passes on the pre-change prose and the fail-first replay still reports the test passing at base | skills/run-autopilot/scripts/test_rework_groups_prose.py:81 | 11 | ALICE, BOB, CARL, mech-check |
| [2/4] | 🟡 | The new test file skills/run-autopilot/cli/test_main_review_close_validation.py is not listed in the "review verbs" block of dev/bin/release-checks (lines 207-212). That block was extended for the four cycle-1 files but not this one, so the release gate never runs it. Run directly this cycle: 7 passed | dev/bin/release-checks:207 | 9 | ALICE, BOB |
| [1/4] | 🟡 | The stricter `found_by` validation (list of strings, required on fix/defer rows) is not matched by the tail-sweep prose. phase-review.md:195 says `found_by` is "copied verbatim" from the Consolidated Findings row, where it is a string such as "ALICE, BOB". Following it verbatim now fails with exit 2. Only the decision-gate prose (phase-review.md:267) says `[...]`. The stderr message at __main__.py:1068 also still mentions only "a string `classification`" and not the allowed values, emoji severities or found_by list | skills/run-autopilot/references/phase-review.md:195 | 8 | ALICE |
| [1/4] | 🟡 | The new `skipped` review_lenses value is undocumented. state-schema.md:216 and tracon/model.py:281 define only `running|done|failed`. Document it or keep `disabled` mapping to an existing state | skills/run-autopilot/references/state-schema.md:216 | 8 | ALICE |
| [1/4] | 🟡 | `review-stage` runs the gate itself when the verdict is stale. The spec says the verdict goes in the summary and "the skill runs the gate once". This adds a mandatory `--gate-command`, so a long gate runs inside the staging call. A timed-out gate yields `Tests: 0 passed, 0 failed, 0 skipped (... treated as failed)`. That line may satisfy the `Tests:` gate pattern while carrying no real counts | skills/run-autopilot/cli/review_stage.py:369 | Gate reuse | BLAKE |
| [1/4] | 🟡 | F9: Doubt verdicts are still extracted globally without source tags, replacing reviewer-attributed verdicts | skills/run-autopilot/cli/review_close.py:290 | 8 | BOB |
| [1/4] | 🟡 | F10: Newly queued pending rework is recorded as "auto-fixed" with reason "fixed by review-close" before any fix occurs | skills/run-autopilot/cli/review_close.py:218 | 8 | BOB |
| [1/4] | ⚪ | Unrelated reformatting churn: trailing commas and re-wrapped calls in functions the PRD does not touch (for example __main__.py `_check_plan_stall_lines`, `_render_audit_surface`, `_select_report_block`, `_run_wave`, `_run_record_store`, plus several single-line rewraps in review_stage.py and verification.py). It buries the real changes and violates surgical changes | skills/run-autopilot/cli/__main__.py:480 | general | ALICE |
| [1/4] | ⚪ | For a tail-sweep call, close() still returns `lenses_closed` populated (review_close.py:314) although `_set_lens_state` applied none of it, which misreports the result | skills/run-autopilot/cli/review_close.py:314 | 8 | ALICE |
| [1/4] | ⚪ | `last-verification.json` is written with a plain `write_text`, so a crash mid-write leaves a truncated record. A truncated record parses to None and counts as stale, so the failure is safe but not atomic | skills/run-autopilot/cli/verification.py:122 | verification | BLAKE |
| [1/4] | ⚪ | K1: Replay reports four additional touched tests passing at base: three acceptance guards in test_main_review_close_validation.py and the adjusted CLI forwarding test (mech-check) | skills/run-autopilot/cli/test_main_review_close_validation.py | general | BOB, mech-check |
| [1/4] | 🟡 | Public signatures differ from the spec's module contract. `stage(state_path, cycle_id, since)` is actually a 12-parameter function; `render_roster` takes seven positional arguments; `close()` also requires `batch_id` and `chosen_findings`; `run_gate` takes `(command, cwd, sha, cycle, timeout)`; `reuse_verdict` also takes `head_sha` | skills/run-autopilot/cli/review_stage.py:592 | general | BLAKE |

Row count: 22 (three separate reviewer wordings of the tail-sweep prose hedge
merged into one [3/4] row; the same for the ungated validation module, raised by
Alice and Bob at adjacent gate lines). Two non-findings were dropped rather than
tabled: Blake's ⚪ note that the review-close idempotency key "held up under
review" (a positive confirmation, not a defect) and Bob's ⚪ sandbox marker
"Cannot statically verify: acceptance suites and release-checks pass" (the
orchestrator ran both this cycle; see the `Tests:` line and
`00249-stage-and-close-reviews-in-code-v1-checks-2.json`).

Mechanical checks absorbed: the one `[MECH]` tautology line
(test_rework_groups_prose.py:81) merged into the [3/4] 🟡 row above, with
`mech-check` added to its finders. The three fail-first replay lines merged onto
Bob's K1 row (also `mech-check`): 12 of 17 touched tests fail against the base,
and the 5 that pass are three accept-valid-input guards, one CLI forwarding test
and the prose test already tabled.

Carry-forward: none. The cycle-1 queue
(`00249-stage-and-close-reviews-in-code-v1-checks-1.json`) holds one entry with
`result.exit: 0`, so nothing carried into this cycle.

### Auto-dismissed (ledger)

- [BLAKE] 🟡 The `review-stage` summary has no exact reviewer-dispatch commands, and no `diff scope` key | File: skills/run-autopilot/cli/review_stage.py:727 — Cosmetic shape of the stdout summary; every path the dispatch needs is already named in it. Deferred to batch end rather than reworked.
- [BLAKE] 🟡 Flags beyond the spec's `--state`, `--cycle-id`, `--since` ... a standalone mode was also added | File: skills/run-autopilot/cli/__main__.py:906 — The PRD's Structural Decomposition lists module sketches, not binding signatures; the reviewed design doc is the authority for the HOW and chose the richer parameter set deliberately. No behavioral defect is claimed.

Blake's "Public signatures differ" row above is the same settled discard re-raised
at a different citation (`review_stage.py:592` rather than `__main__.py:898`), so
the mechanical `--ledger-dismiss BLAKE` filter did not catch it. The decision gate
treats it as a settled discard, not a new finding.

## Alice

Alice ran as a native Claude subagent against the context, diff and pack. Her
findings are the `ALICE` rows above. She reviewed statically and did not run the
test suites this cycle.

She records as resolved and verified from cycle 1: the `ui` lens stamp
(review_stage.py:89, pinned by a test); the keep-tail output cap; dirty store
paths ignored in gate reuse, with a test; the release-checks summary line now
emitted and the four review-verb test files listed; the trailing `(found by: )`
suffix; `require_codex_guard` threaded through the CLI; the tail-sweep gating of
the lens, verdict and dispatch-row steps; the classification, severity and
`found_by` validation; and the CHANGELOG entries. Cycle-1 F3 is resolved for
Blake only.

R1: fail
R2: fail
R3: pass
R4: fail
R6: pass
R7: pass
R8: pass
R9: fail
R10: pass
R11: pass
R12: fail
R13: fail

## Blake

Blake ran blind (PRD + blind rubric + blind-lens fence only; no diff, no file
list, no design doc, no review history, no settled ledger). His findings are the
`BLAKE` rows above. He ran the 74 tests across the six review-verb and prose
test files himself and reports them all passing, noting that the passing tests
do not cover the gaps he raised.

B1: fail
B2: fail
B3: fail
B4: pass
B5: pass
B6: fail
B7: fail
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

## Bob

Bob ran on codex in the read-only sandbox, resuming his cycle-1 thread, and
carried the doubt + de-slop lens (`eve.md`'s Two lenses, bucket and rubric
sections appended to his persona). His findings are the `BOB` rows above.

Doubt buckets:

FIX: F1 review-file format still omits `dispatch_rows` and the Blake/Eve agent
entries; F2 unavailable reviewers map to the unsupported dispatch outcome
`failed`; F3 staging flags exist but the skill still prescribes manual ledger
and incremental edits; F4 Eve still receives the merged PRD containing the
design document; F5 Eve's fallback still uses Bob's prompt, whose doubt appendix
is omitted when Eve is present; F6 `communicate()` still buffers unlimited
output before truncation; F7 porcelain rename text is checked only by its
initial prefix; F8 the gate summary reports check-block counts as passed tests,
hardcodes zero skips and emits no summary on failure; F9 doubt verdicts are
extracted globally without source tags; F10 newly queued pending rework is
recorded as auto-fixed before any fix occurs; F11 `run_gate` remains 75 lines
and review_stage.py now exceeds the file limit at 823 lines; F12 the tail-sweep
test retains an either-or hedge; F13 the release checks omit the new
classification-validation test module.

VERIFY: the acceptance suites and the release gate. The exact single command
(`test_main_review_close_validation.py`) is queued in
`00249-stage-and-close-reviews-in-code-v1-checks-2.json` and was run this cycle
(7 passed, exit 0); the `bash dev/bin/release-checks` half was run directly this
cycle (exit 0), its counts in the `Tests:` line below.

KNOWN: K1 the four extra base-passing tests are accepted-input and existing-
forwarding guards, outside the fail-first requirement for newly introduced
behavior.

R1: fail
R2: fail
R3: pass
R4: fail
R6: pass
R7: pass
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

Carl ran on the copilot backend (`gemini-run.sh`, exit 0), model
`gemini-3.8-flash`. His findings are the `CARL` rows above: all three are
mechanical limit and test-shape checks, each independently confirmed by the
orchestrator (`run_gate` 75 lines, review_stage.py 823 lines, the `or` hedge at
test_rework_groups_prose.py:81). He raised no frontend findings, correctly: the
diff has no UI surface.

R1: pass
R2: fail
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

## Orchestrator verification

Five load-bearing claims were confirmed mechanically before classification, so
none of the deferrals below rests on a single reviewer's reading:

- `--settled-ledger` / `--prior-findings` are wired end to end
  (`__main__.py:918-919` → `review_stage.py:488-489, 819`), while SKILL.md:216
  and :248 still instruct the model to hand-append both. Confirmed.
- `_DISPATCH_OUTCOME` maps `unavailable` → `"failed"` (review_close.py:48) and
  `record_dispatch.OUTCOMES` is `("ok","timeout","killed","error","lost")`, so
  the closing call exits 2 for every unavailable reviewer. Confirmed.
- `_eve_inputs` uses the merged `run["prd"]` while Blake alone gets the raw
  `_prd_body` slice. Confirmed.
- `run["doubt"] = "eve" not in roster` (review_stage.py:491), so Bob's doubt
  appendix is dropped exactly when Eve is on the roster — the one case where
  `agent-invocation.md` sends Eve's fallback to Bob's assembled prompt.
  Confirmed.
- `review_stage.py` is 823 lines (over the 800 limit), `run_gate` is 75 lines
  (over 50), and `test_main_review_close_validation.py` is absent from the
  release-checks review-verbs block. Confirmed.

Verdict: 22 findings
Tests: 2564 passed, 0 failed, 0 skipped (suite run this cycle)
