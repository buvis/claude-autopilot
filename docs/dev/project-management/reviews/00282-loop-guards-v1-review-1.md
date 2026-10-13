---
prd: docs/dev/project-management/prds/wip/00282-loop-guards-v1.md
review: 1
date: 2026-10-13
head_sha: 14423e65b0145bb2e64f7a0c50d6bbb9ff0b2cff
codex_thread_id: 01a135c1-6660-7822-bd37-fb5c772d4dd4
reviewers: alice,blake,bob
agents:
  alice: available
  blake: available
  bob: available
  carl: unavailable
dispatch_rows:
  bob: ee40a525
  carl: 7dd82133
---

# Review: 00282-loop-guards-v1

Diff range: `e3ae2d3714f9d6709df7cc5c84521f78f6218fb4..14423e65b0145bb2e64f7a0c50d6bbb9ff0b2cff`

codex_rung_guard: not fired

pack: failed (engram pack exit 1: sqlite3.OperationalError: attempt to write a readonly database) — review degraded, not invalid.

carl: unavailable. First dispatch exit 1 (copilot backend authentication failed: "Your GitHub token may be invalid, expired, or lacking the required permissions"). One retry on the native `gemini` backend (`GEMINI_BACKEND=gemini`) started but stalled past the Watcher's 30-run (~50 min) budget with no output; the lane was killed and Carl counts as failed (retry budget spent). Not latched for the batch: exit 1 is a runtime failure, not the exit-4 permanent-unavailability contract.

bob: after one retry (inlined). First run returned the lack-of-input refusal shape (sandbox could not read the staged files); the inlined retry prompt produced a full review.

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [2/3] | 🟠 | Instant-exit does not follow the spec for a short session that touched state. Spec: the check runs before the `state_touched` counter reset, so an instant exit never resets `_died_retries`, and the died ladder (retry once, then park) decides. Code: `_decide` resets `_died_retries` at the state_touched block first (skills/run-autopilot/cli/loop_decision.py:242), then `_apply_instant_exit` (:255, :258) only relabels, with `then=continue`. A sub-30s, $0 session that wrote state therefore always gets then=continue and the ladder never runs. The new test deliberately uses an untouched state (skills/run-autopilot/cli/test_loop_decision.py:738), so the touched-state case in the spec's acceptance text is not covered. | skills/run-autopilot/cli/loop_decision.py | Phase 1 instant-exit | BLAKE, BOB |
| R2 | [1/3] | 🟠 | The instant-exit change (task 5) leaves 14 existing loop tests red, and assumptions.md:225 records them as "already failing" without fixing them. Fixture sessions are under 30 s with no cost log, so they are now classed `instant_exit`. Reproduced: test_loop.py::test_one_metrics_line_per_session (signal is now instant_exit, expected continue), 4 tests in test_loop_decision.py (test_fingerprint_bound_parks_a_prd_burning_sessions, test_a_wait_the_fingerprint_bound_overrides_never_reaches_the_row, test_rejected_with_overage_allowed_still_sleeps, test_younger_loop_yields_at_allowed_warning), and 9 in test_loop_record_store.py. Update those fixtures to bill a cost or advance the clock, or the suite stays red | skills/run-autopilot/cli/test_loop_record_store.py:162 | 5 | ALICE |
| R3 | [1/3] | 🟠 | The new test file skills/run-autopilot/cli/test_loop_budget.py is not named in dev/bin/release-checks. test_release_checks_counts.py::test_every_tracked_test_file_is_gated fails with "does not name ['skills/run-autopilot/cli/test_loop_budget.py']". The PRD exit criterion (`release-checks` exits 0 with FAIL 0) cannot be met until it gets a [checks] block | dev/bin/release-checks | 4 | ALICE |
| R4 | [1/3] | 🟠 | The success metric `bash dev/bin/release-checks` does not exit 0. I ran it: the `test_loop_decision` block reports "4 failed, 157 passed". Re-running `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_loop_decision.py` gives 4 failed, 55 passed. The failures are test_fingerprint_bound_parks_a_prd_burning_sessions, test_a_wait_the_fingerprint_bound_overrides_never_reaches_the_row, test_younger_loop_yields_at_allowed_warning and test_rejected_with_overage_allowed_still_sleeps. Each now gets `instant_exit` where it expected `continue` or `park` (e.g. skills/run-autopilot/cli/test_loop_decision.py:345, :440, :559, :709). Their fake sessions run 1s with no billed cost. The listed `-k` acceptance filters pass (97 passed), but the full file regresses and the Phase 2 exit criterion (`FAIL 0`) is unmet. The implementer neither adjusted these tests nor handled the signal change. | skills/run-autopilot/cli/test_loop_decision.py | Phase 1/2 | BLAKE |
| R5 | [1/3] | 🟠 | The budget guard excludes `instant_exit` with `then: continue` and every decision carrying `limit_wait`, although the PRD includes both. Normalize the effective signal and preserve the scheduled sleep when applying a budget park, rather than exempting these decisions. | skills/run-autopilot/cli/loop_decision.py:504 | 4 | BOB |
| R6 | [1/3] | 🟠 | Pre-entry failures can retain an earlier same-PRD `loop_entry`. Both exception branches return without invalidating it, allowing the child to replay stale catchup/design/stop results. Scope replay to the successful current launch and test both failure paths with an existing entry. | skills/run-autopilot/cli/loop.py:583 | 7 | BOB |
| R7 | [1/3] | 🟠 | The completion gate remains red: 82 tests failed, and the supplied assumptions identify instant-exit regressions in existing loop tests. Resolve introduced failures, then run `bash dev/bin/release-checks`; completion requires exit 0 and `FAIL 0`. | N/A | general | BOB |
| R8 | [1/3] | 🟡 | `_budget_bound` returns unless `decision["signal"] == "continue"`, so an `instant_exit` whose `then` is `continue` is never budget-checked. PRD F1 says the check applies to "`continue`, or `instant_exit` whose `then` is `continue`". Read `decision["then"]` when the signal is instant_exit, and set `signal` to "park" as well as `park_site` | skills/run-autopilot/cli/loop_decision.py:504 | 4 | ALICE |
| R9 | [1/3] | 🟡 | Downstream `signal == "continue"` consumers also skip an `instant_exit` with `then == "continue"`. `_run_loop` skips `store_tree.record_store("loop")`, so a short session that touched state is never recorded. `_fingerprint_bound` takes its else-branch and resets `_fp_repeats`/`_fp_prev`. This is the product-level cause of the red tests in the first finding. Decide deliberately whether those paths should see the `then` signal, and pin the choice with a test | skills/run-autopilot/cli/loop.py:662 | 5 | ALICE |
| R10 | [1/3] | 🟡 | SKILL.md:142 is now stale. It still says a headless turn "is never interrupted except by the wrapper's wall-clock cap", and it describes `_AUTOPILOT_SESSION_IDLE` as acting only past the cap. Task 6 now kills a silent, nothing-in-flight session before the cap. Only the CHANGELOG mentions this. Update the paragraph in the same place the budget sentence was added | skills/run-autopilot/SKILL.md:142 | 8 | ALICE |
| R11 | [1/3] | 🟡 | Test gap: nothing combines `on_warn`/`warn_secs` with `busy_fn`, and production always passes both. `_wait_under_cap` now owns the warn-window wait (cap minus warn), and the "hand-off still fires at cap - warn_secs" claim is untested with idle polling on. `runner._run_session` passing `busy_fn` is also untested | skills/run-autopilot/cli/test_watchdog.py:379 | 6 | ALICE |
| R12 | [1/3] | 🟡 | Test gap: the `args.prd is None` gate in `_replay_loop_entry` has no test. The case is a manual `autopilot enter --prd X` while a matching `loop_entry` exists. The design doc records this as a fixed review finding. The `loop_entry` delete-failure path (exit 2) and the `_pre_enter` utime-failure message are also untested | skills/run-autopilot/cli/__main__.py:369 | 7 | ALICE |
| R13 | [1/3] | 🟡 | Files over the 800-line limit, newly crossed by this diff: records.py 802, test_loop_decision.py 820, test_records_park.py 844, test_enter.py 862 (test_enter.py was 775 before, and its own footer says it was split at 800). assumptions.md:201 sanctions the test_loop_decision.py case. Split into new files, registering each in release-checks. __main__.py at 1863 lines was already over the limit | skills/run-autopilot/cli/records.py:802 | general | ALICE |
| R14 | [1/3] | 🟡 | `_run_session` grew from about 49 to 52 lines (+1 `busy_fn` line, +2 docstring lines), crossing the 50-line function limit. Trim the docstring or extract the Watchdog construction | skills/run-autopilot/cli/runner.py:244 | 6 | ALICE |
| R15 | [1/3] | 🟡 | An invalid but present `prd_budget_since` disables the budget check. The design explicitly requires an invalid timestamp to fall back to epoch zero, counting all rows for that PRD. Distinguish an absent stamp from an invalid one and implement that fallback. | skills/run-autopilot/cli/loop_decision.py:517 | 4 | BOB |
| R16 | [1/3] | 🟡 | Ledger read errors silently become zero historical spend through `except OSError: pass`. An unreadable existing ledger can therefore disable cumulative enforcement without a diagnostic. Treat a missing initial ledger separately and report other read failures explicitly. | skills/run-autopilot/cli/loop_decision.py:175 | 4 | BOB |
| R17 | [1/3] | 🟡 | `prd_spend_since` introduces another JSONL reader despite the explicit reuse requirement. Delegate row loading to `cli.render_metrics.load_rows`, retaining the PRD, timestamp, and numeric filters. | skills/run-autopilot/cli/loop_decision.py:175 | 4 | BOB |
| R18 | [1/3] | 🟡 | The budget integration test disables real pre-launch entry and asserts launch order `[A, A, A, B]`. This preserves the wasted launch F2 should eliminate. Inject real `enter()` into the loop and assert that the first launch after parking A selects B, without entering inside the child fixture. | skills/run-autopilot/cli/test_loop_budget.py:148 | general | BOB |
| R19 | [1/3] | 🟡 | Instant-exit tests assert only the metrics `signal`, leaving the design's required `then` field unpinned. Assert `then: continue` for the retry/wait rows and `then: park` for the escalation row; ensure serialization preserves them. | skills/run-autopilot/cli/test_loop_decision.py:737 | 5 | BOB |
| R20 | [1/3] | 🟡 | The supplied fail-first replay identifies nine touched cases passing against base: budget-stamp preservation, legacy park-marker shape, and seven instant-exit cases. Under the requested R2 criterion, add feature-positive controls while retaining these compatibility assertions. | N/A | general | BOB |
| R21 | [1/3] | 🟡 | Supplied AST counts show the new budget acceptance tests at 61 and 65 lines, exceeding the function limit. Extract their repeated PRD-tree/state setup into a shared fixture while retaining their behavioral assertions. | skills/run-autopilot/cli/test_loop_budget.py:148 | 4 | BOB |
| R22 | [1/3] | 🟡 | `_run_session` now spans 52 lines according to the supplied AST counts. Trim its repetitive expanded docstring to retain the existing function boundary within the limit. | skills/run-autopilot/cli/runner.py:244 | 6 | BOB |
| R23 | [1/3] | 🟡 | Added tests push three files beyond 800 lines: skills/run-autopilot/cli/test_enter.py:851, skills/run-autopilot/cli/test_records_park.py:837, and skills/run-autopilot/cli/test_loop_decision.py:810. Move older unrelated cases into companion files; keep the new acceptance tests at their pinned paths. | N/A | general | BOB |
| R24 | [1/3] | 🟡 | Operator documentation still says sessions are interrupted only by the wall cap and describes idle detection only after it. Document pre-cap idle termination and its busy-work exemption. Also correct CHANGELOG.md:14, which incorrectly excludes usage-limit sessions from instant-exit classification. | skills/run-autopilot/SKILL.md:142 | 8 | BOB |
| R25 | [1/3] | ⚪ | `_scan_busy` says it reads events tolerantly, but `(event.get("message") or {}).get("content")` raises AttributeError when `message` is a truthy non-dict. That reaches the outer `except Exception` and returns busy for the rest of the session, the latch the comment says it avoids. Add an `isinstance(message, dict)` check | skills/run-autopilot/cli/watchdog.py:77 | 2 | ALICE |
| R26 | [1/3] | ⚪ | `_record_entry` catches only `state.StateError` from `enter()`. The CLI path also catches `StateExistsError`, and an OSError or SchemaError from `enter()` would crash the unattended loop. The finally block only backdates the mtime. The spec names only StateError, but "never halts the loop" is the stated intent, so consider widening the catch | skills/run-autopilot/cli/loop.py:596 | 7 | ALICE |
| R27 | [1/3] | ⚪ | A session that follows the brief's `## Entry` section and skips `autopilot enter` never deletes `loop_entry`. The stale section then renders in the review-phase brief until a PRD reset. Normal operation is safe because the next `_pre_enter` overwrites the entry. Consider rendering `## Entry` only for the build phase | skills/run-autopilot/cli/brief.py:124 | 7 | ALICE |
| R28 | [1/3] | ⚪ | 67 further failures in test_gate_findings_unread_shapes.py (e.g. `_is_unread_line` on an emoji-bullet row) come from code this diff does not touch. I did not check them against the base commit, so they are probably pre-existing. They are part of the "82 failed" suite total (14 loop tests, the release-checks test, and these 67) | skills/run-autopilot/cli/test_gate_findings_unread_shapes.py | general | ALICE |
| R29 | [1/3] | ⚪ | Small extras beyond the spec: `budget_usd_for` also rejects negative, nan and inf values (loop_decision.py:145); `_parse_marker` normalizes any non-"budget" site to "wrapper_died" (records.py:586); `loop_entry` is added to `PER_PRD_RESET_FIELDS` (records.py:104); `_replay_loop_entry` also drops and does not replay when `--prd` is given (__main__.py:390). All are defensible and documented. They are not in the PRD. | skills/run-autopilot/cli/records.py | general | BLAKE |
| R30 | [1/3] | ⚪ | Stale docs. skills/run-autopilot/SKILL.md:142 and the `idle_secs_for` docstring (skills/run-autopilot/cli/runner.py:112) still say idle detection applies only past the wall-clock cap. Pre-cap idle kill is now live, and the CHANGELOG entry exists (CHANGELOG.md:15). | skills/run-autopilot/SKILL.md | Phase 2 | BLAKE |
| R31 | [1/3] | ⚪ | `_pre_enter` catches only `state.StateError` from `enter()` (skills/run-autopilot/cli/loop.py:596). Any other exception, such as an OSError from an unforeseen path, would crash the loop rather than launch without `loop_entry` as the spec's error case describes. `enter()` handles most OSErrors itself, so this is low risk. | skills/run-autopilot/cli/loop.py | Phase 1 loop entry | BLAKE |
| R32 | [1/3] | ⚪ | The idle watchdog treats a missing log as infinite silence (skills/run-autopilot/cli/watchdog.py:211). `session_busy` on a missing log returns False, so a session whose log is absent would be killed at the first poll. The log is created before launch (skills/run-autopilot/cli/runner.py:264), so this is not reachable in practice. | skills/run-autopilot/cli/watchdog.py | Phase 2 | BLAKE |
| R33 | [1/3] | 🟡 | 1 touched test(s) pass against the pre-change code: test_budget_since_already_in_state_survives_same_prd_reentry | skills/run-autopilot/cli/test_enter.py | general | mech-check |
| R34 | [1/3] | 🟡 | 1 touched test(s) pass against the pre-change code: test_non_budget_park_marker_carries_no_site | skills/run-autopilot/cli/test_loop_budget.py | general | mech-check |
| R35 | [1/3] | 🟡 | 7 touched test(s) pass against the pre-change code: test_instant_exit_flags_only_sub_30s_unbilled_sessions +1 more | skills/run-autopilot/cli/test_loop_decision.py | general | mech-check |

## Alice

Consensus lens (implementation-aware), legacy engine. 13 findings: 2 🟠, 7 🟡, 4 ⚪ — see R2, R3, R8-R14, R25-R28 above.

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
R12: fail
R13: fail

## Blake

Blind lens (PRD-only). 9 findings: 3 🟠, 2 🟡, 4 ⚪ — see R1, R4, R29-R32 above. Blake verified as correct: the budget park path (`_act_park` site write, `do_stall(site="budget")` with no `parks_consecutive` bump, `prd_budget_since` in the reset fields and stamped by `enter._write_prd`), the loop-entry store/replay/delete cycle and brief rendering, `session_busy`/`_wait_under_cap` behavior with the runner passing `busy_fn` and the `killed_by: "idle"` metrics row, the existence of all named tests (the `-k` filtered run: 97 passed), and every documentation row (state-schema, phase-build, SKILL.md knob, CHANGELOG Added entries).

B1: fail
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
B16: fail
B17: pass
B18: pass
B19: pass

## Bob

Doubt + de-slop lens (codex), after one retry (inlined). 14 findings: 3 🟠 FIX, 11 🟡 FIX, 1 🟠 VERIFY, no KNOWN — see R1, R5-R7, R15-R24 above.

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

Carl: unavailable (no output produced; see the top-matter note).

Verdict: 35 findings
Tests: 6349 passed, 82 failed, 32 skipped (reused from last-verification.json at 14423e65b0145bb2e64f7a0c50d6bbb9ff0b2cff)
