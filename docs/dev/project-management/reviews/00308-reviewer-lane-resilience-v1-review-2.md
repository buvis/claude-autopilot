---
prd: docs/dev/project-management/prds/wip/00308-reviewer-lane-resilience-v1.md
review: 2
date: 2026-10-15
head_sha: 978894efd7e89db7be9456781a220de9ebb7ab2d
codex_thread_id: 01a13e87-7260-7323-9bf8-66daafe91726
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
dispatch_rows:
  bob: 3399f6c0
  bob_retry: a8ddba68
  carl: 514274f6
---

# Review: 00308-reviewer-lane-resilience-v1

Diff range: `322e9abbf209125f434af4c4fcbaa0778cd03105..978894efd7e89db7be9456781a220de9ebb7ab2d`

codex_rung_guard: not fired

## Review Summary

Reviewed: 8 completed tasks (4 original plan, 4 cycle-1 rework)
PRDs checked: 00308-reviewer-lane-resilience-v1.md
Scope: incremental — the rework commits since cycle 1's head.

### Agent Status

- Alice: ✅ Available (consensus lens, engine `legacy`)
- Blake: ✅ Available (blind lens, PRD-only)
- Bob: ✅ Available (doubt lens + de-slop, codex) — **first dispatch refused for lack of input; the one retry, dispatched as the inlined prompt, produced this review** (see Degradations)
- Carl: ✅ Available (UI/design lens, backend `copilot`) — no issues found
- Eve: ⏸️ Disabled (doubt_reviewer is `codex` and no task was codex-implemented, so the codex doubt-roster guard did not fire)

### Degradations this cycle

- **engram context pack: failed** (`engram pack exit 1: sqlite3.OperationalError: attempt to write a readonly database`), same as cycle 1. Every prompt carried the `(no pack available this cycle)` sentinel; Blake never receives a pack by design. The review is degraded, not invalid.
- **Bob's first dispatch refused** with `The read tools failed during sandbox initialization (sandbox_apply: Operation not permitted). Please paste the 0750 context and diff inline` — zero `R{n}` verdicts, zero issue lines. The one retry was dispatched as the inlined prompt (158 KB: context + full diff inlined), which succeeded. **This is exactly the defect this PRD fixes**; the fix is in the repo source while this batch runs the installed `0.9.0` pack, so the old behavior is expected here and is not a finding against the work. The first dispatch's ledger row is closed `error / lack-of-input`, the retry's `ok / retry`.

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [2/4] | ⚪ | Bob's dispatch-ledger `prompt_bytes` is measured by `review-stage` from the roughly 9 KB staged prompt. The inlined prompt now overwrites that file afterwards (about 187 KB in cycle 1), so the row understates what codex received. SKILL.md does not tell the operator to re-measure. A note, or re-measuring the file at dispatch, would keep the metric honest. | skills/review-work-completion/SKILL.md:260 | 6 | ALICE, BLAKE |
| R2 | [1/4] | 🟠 | The auth-failure stderr line does not match the spec. The PRD requires `ERROR: copilot permanently unavailable (authentication failed).`. The code prints `ERROR: $BACKEND authentication failed (permanent; no fallback).`, and no test asserts the specified text, so the drift is unguarded. The exit code (4) and the latch still work, so the effect is limited to anything or anyone matching the specified string. | skills/use-gemini/scripts/gemini-run.sh:266 | general | BLAKE |
| R3 | [1/4] | 🟡 | `skills/review-work-completion/SKILL.md:260`, the cycle-1 high-severity fix, has no regression test. `test_bob_inlined_first_prose.py` pins only `retry-policy.md`, the absence of "lack-of-input", and the retry verb. Deleting the step-5 "Bob's prompt is always the inlined shape" paragraph would pass every test. Add an assert that SKILL.md step 5 names the inlined section and the `bob-prompt-{id}.md` overwrite. | skills/review-work-completion/scripts/test_bob_inlined_first_prose.py:45 | 6 | ALICE |
| R4 | [1/4] | 🟡 | `run_cmd` is now 61 lines (`gemini-run.sh:220` to `:280`) against the 50-line limit. The cycle-1 version was under it; the watchdog and stderr-drain rework pushed it over. Move the watchdog launch and teardown into a helper, for example `start_watchdog` and `stop_watchdog`, without changing behavior. | skills/use-gemini/scripts/gemini-run.sh:220 | 5 | ALICE |
| R5 | [1/4] | 🟡 | "Partial output is not published" holds only with `-o`. Without `-o`, `run_streamed` streams the fallback's stdout straight through, so output printed before the deadline has already reached the caller when the run exits 4. Carl's dispatch always uses `-o`, so the PRD's use case is covered. | skills/use-gemini/scripts/gemini-run.sh:210 | general | BLAKE |
| R6 | [1/4] | 🟡 | `GEMINI_FALLBACK_TIMEOUT` caps total wall-clock time, not "no output". The message reads "produced no output within Ns" even when the fallback was producing output. `skills/use-gemini/SKILL.md:42` documents the whole-run cap, so this is a known divergence from the PRD wording. A value of `0` arms an immediate kill, because only non-numeric values fall back to 900. | skills/use-gemini/scripts/gemini-run.sh:226 | general | BLAKE |
| R7 | [1/4] | 🟡 | Timeout classification still depends on successfully creating `timed_out`. If `touch` fails after Gemini exits successfully but leaves a child holding stderr, the watchdog kills that child, yet the parent can publish output and return 0. Propagate expiry independently of marker creation and add a failed-marker regression test. | skills/use-gemini/scripts/gemini-run.sh:241 | 5 | BOB |
| R8 | [1/4] | 🟡 | Removing `prompt_bytes` contradicts the explicit retry-row contract, which deliberately requires `prompt_bytes: None` for an unmeasured prompt. Restore the field and its test expectation. | skills/work/scripts/record_dispatch.py:109 | 8 | BOB |
| R9 | [1/4] | 🟡 | The rework adds no test assertion for step 5's overwrite-before-dispatch instruction. The existing first-dispatch test already passed when that wiring was missing; the added assertions check other documents. Add a regression assertion that fails when step 5's unconditional inlined assembly is removed. | skills/review-work-completion/scripts/test_bob_inlined_first_prose.py:45 | 6 | BOB |
| R10 | [1/4] | ⚪ | If `touch` of the `timed_out` marker fails, the watchdog now still kills the group and reports the failure. The run then returns the raw kill status (137) instead of the specified exit 4, and no test covers that branch (`gemini-run.sh:241` to `:244`). It is a rare filesystem failure inside an already-created mktemp dir, but the exit contract is not met there. Consider deriving the timeout verdict from the kill itself, for example a flag file written after the kill, or accept and document it. | skills/use-gemini/scripts/gemini-run.sh:241 | 5 | ALICE |
| R11 | [1/4] | ⚪ | The exit-code table still describes exit 4 only as "Model unavailable or client tier ineligible". It does not mention the auth failure or the fallback timeout. | skills/use-gemini/SKILL.md:90 | general | BLAKE |
| R12 | [1/4] | 🟡 | 1 touched test(s) pass against the pre-change code: test_retry_case_uses_the_retry_verb | skills/review-work-completion/scripts/test_bob_inlined_first_prose.py | general | mech-check |
| R13 | [1/4] | 🟡 | 2 touched test(s) pass against the pre-change code: test_inlined_prompt_restricts_review_to_inlined_text, test_inlined_prompt_tells_bob_the_sandbox_supplied_everything | skills/review-work-completion/scripts/test_retry_policy_prose.py | general | mech-check |
| R14 | [1/4] | 🟡 | 1 touched test(s) pass against the pre-change code: test_auth_failure_exits_4_without_fallback | skills/use-gemini/scripts/test_gemini_run_unavailable.py | general | mech-check |

### Mechanical test checks absorbed

Three `[MECH]` replay lines were produced by `replay_tests_against_base.py`; `detect_tautological_tests.py` produced none. None matched an existing row's test, so each became its own row (R12, R13, R14). **This cycle's replay base is cycle 1's head**, not the PRD's start, so "passes against the pre-change code" here only states that the rework did not change that behavior — which is what a rework touching other files is supposed to do.

No cycle-1 verification-check queue file exists (cycle 1 queued nothing), so nothing was carried forward.

## Alice

Consensus lens, incremental. Four new findings (2 🟡, 2 ⚪): R1, R3, R4, R10. She ran the five changed test files: 48 passed. She did not run the full suite.

She verified cycle 1's findings resolved: R1, R2, R3, R4/R12, R5/R11, R6/R10/R13, R7, R8, R9 (partly — see R10 here), R14, R15, R16, R19. R17, R18 and R20 were settled in the ledger and not re-raised.

```
R1: fail
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
R13: pass
```

## Blake

Blind lens, PRD-only. Five findings (1 🟠, 2 🟡, 2 ⚪): R2, R5, R6, R11, and the `prompt_bytes` observation folded into R1. He ran the PRD's named test files: 53 passed. He did not run `dev/bin/release-checks` in full, but confirmed by reading that the new test files are registered in it.

He reports all five PRD features implemented: Bob's first dispatch is the inlined shape and the lack-of-input retry is gone; `permanently_unavailable` matches auth failures and the fallback is skipped for them; the native fallback has a deadline and kills its process group; `record_dispatch.py retry` exists; the replay kills its process group on timeout. Both CHANGELOG entries are present, and no extra flags or dependencies were added.

```
B1: fail
B2: pass
B3: pass
B4: pass
B5: fail
B6: pass
B7: pass
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
```

## Bob

Doubt lens + de-slop, codex, **after one retry (inlined)**. Three findings, all 🟡: R7, R8, R9.

FIX / VERIFY / KNOWN buckets as emitted:

```
FIX:
- 🟡 Timeout classification still depends on successfully creating `timed_out`. | skills/use-gemini/scripts/gemini-run.sh:241
- 🟡 Removing `prompt_bytes` contradicts the explicit retry-row contract. | skills/work/scripts/record_dispatch.py:109
- 🟡 The rework adds no test assertion for step 5's overwrite-before-dispatch instruction. | skills/review-work-completion/scripts/test_bob_inlined_first_prose.py:45

VERIFY:
- (none)

KNOWN:
- (none)
```

```
R1: fail
R2: pass
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: fail
R10: fail
R11: pass
R12: pass
R13: pass

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass
```

## Carl

UI/design lens, backend `copilot`. **No issues found.** He read the diff and the mechanical-facts block and cross-checked the 50-line function rule against a prior review.

```
[CARL] ✅ No issues found
```

```
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
R12: pass
R13: pass
```

## Verification-check queue

No entries this cycle. Bob emitted an empty VERIFY bucket and Eve did not run, so no queue file was written.

Verdict: 14 findings
Tests: 6846 passed, 0 failed, 34 skipped (reused from last-verification.json at 978894efd7e89db7be9456781a220de9ebb7ab2d, written by this cycle's review-stage gate run)
