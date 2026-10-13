---
prd: docs/dev/project-management/prds/wip/00279-run-one-exact-reuse-rule-v1.md
review: 1
date: 2026-10-13
head_sha: aea2279cefd7d80dfbaaabb27cc877ea5a0ddb80
codex_thread_id: 01a1350d-08df-7163-a06a-f989dbf517e6
reviewers: alice,blake,bob
agents:
  alice: available
  blake: available
  bob: available
  carl: unavailable
dispatch_rows:
  bob: dfb83e8d
  carl: e3f50135
---

# Review: 00279-run-one-exact-reuse-rule-v1

Diff range: `d17dde6ddcfafed84689b50f47b787fde5bb9775..aea2279cefd7d80dfbaaabb27cc877ea5a0ddb80`

codex_rung_guard: not fired

## Review Summary

Reviewed: 3 completed tasks
PRDs checked: 00279-run-one-exact-reuse-rule-v1.md

### Agent Status

- Alice: ✅ Available (consensus engine: legacy)
- Blake: ✅ Available (blind lens)
- Bob: ✅ Available (codex, doubt lens) — after one retry (inlined). First run was a lack-of-input refusal (`sandbox-exec: sandbox_apply: Operation not permitted` on both read attempts); the inlined retry prompt (`docs/dev/tmp/bob-prompt-00279-c1-retry.md`, 137 KB) carried context and diff verbatim and produced a full review.
- Carl: ⚠️ Unavailable: gemini-run backend=copilot model=gemini-3.8-flash, exit 1, `Error: Authentication failed` (GitHub Copilot token invalid/expired). Retried once, same failure. Not exit 4, so not latched for the batch.
- Eve: ⏸️ Disabled: `doubt_reviewer: codex` and no codex-implemented task, so the codex doubt-roster guard did not fire.

Notes:
- `pack: failed (engram pack exit 1: sqlite3.OperationalError: attempt to write a readonly database)` — the cycle ran without the engram findings-precedent pack. Degraded, not invalid.
- Consolidation ran through `consolidate_findings.py`. Bob's issue lines arrived as `- [BOB] …` list items (inside his FIX/VERIFY/KNOWN buckets), which the parser's `^[BOB]` shape drops; the leading `- ` was stripped in `bob-output-00279-c1.txt` before the second consolidation run (raw copy kept at `docs/dev/tmp/bob-output-00279-c1-raw.txt`). Without that normalization all six of Bob's findings were silently missing from the table.
- No ledger existed (cycle 1), so no `--ledger` dismissal ran.
- No verification-check queue was written: the only VERIFY-bucket item is the release-gate HIGH below, and a HIGH is never routed to verification.

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [2/3] | 🟡 | Stale reader contract: final-verification.md still says step 6 "composes the `Tests:` line from the record when its `sha` equals the reviewed HEAD and the three counts are non-null". That is the exact rule this PRD removes. Rewrite it to "step 6 copies `gate.tests_line` (the `## Test gate` section) and runs `autopilot verify` only when that line is not a counts line". The "review composes its Tests: line from it" clause in skills/work/SKILL.md:462 needs the same fix. | skills/work/references/final-verification.md:136 | 3 | ALICE, BLAKE |
| R2 | [2/3] | 🟡 | The retargeted prose pin is partly tautological. `"gate.tests_line" in review or "## Test gate" in review` and `"suite run this cycle" in review` scan the whole SKILL.md and are already true at base (SKILL.md:181 has both tokens, and the old step 6 had the suffix). Only the "never re-derive reuse" assertion binds the change. The test name still says "gated_on_the_sha", which is no longer true. Scope the assertions to the step-6 slice and rename the test. | skills/work/scripts/test_verify_queue_prose.py:175 | 2 | ALICE, BOB, mech-check |
| R3 | [2/3] | 🟡 | test_step_6_has_no_sha_counts_reuse_rule matches only the `sha … equals/==/matches … HEAD` shape, so a rephrased sha-or-counts condition would pass. The new step-6 sentence "Fail loud: a copied counts line must never read as a fresh run" is also confusing, because a copied `(suite run this cycle)` line is a fresh run. Reword it. | skills/review-work-completion/SKILL.md:402 | 2 | ALICE, BOB |
| R4 | [1/3] | 🟠 | The supplied release gate reports 67 failures, so the required `FAIL 0` exit criterion is unmet; attribution to this change is unproven. Resolve the reported failures and verify with `bash dev/bin/release-checks`. | dev/bin/release-checks:355 | general | BOB |
| R5 | [1/3] | 🟡 | The CHANGELOG bullet landed under `### Fixed` (the section runs from line 18 to 64), but the PRD and task 3 require `[Unreleased] ### Changed`. The assumptions note claims it was placed in Changed, which is false. Move the bullet to Changed (line 14) and correct the note. | CHANGELOG.md:63 | 3 | ALICE |
| R6 | [1/3] | 🟡 | The `or` hedge in test_step_6_composes_from_gate_tests_line (also flagged by the mech block) is satisfied by either token. The new text contains both, so assert both separately. Optionally also pin the TESTS_RE-match and `autopilot verify` fallback wording. | skills/review-work-completion/scripts/test_tests_line_source_prose.py:24 | 2 | ALICE, mech-check |
| R7 | [1/3] | 🟡 | The recorded Test gate line reads "6301 passed, 67 failed, 32 skipped". The touched files pass for me (154 passed across the touched test modules). I could not attribute the 67 failures or show they predate this diff. Name them before the review calls the work green. | N/A | general | ALICE |
| R8 | [1/3] | 🟡 | The `[Unreleased]` CHANGELOG entry for the `normalize_command` change sits under `### Fixed`. The PRD asks for it under `### Changed`, and the existing `### Changed` section holds only the Python 3.11 line. It also appears as a single line deep in the Fixed list, which makes it easy to miss. | CHANGELOG.md:63 | 3 | BLAKE |
| R9 | [1/3] | 🟡 | Source test checks only that either source name appears; removing the counts-shaped guard or verbatim-copy instruction still passes. Assert those requirements within the step-6 slice. | skills/review-work-completion/scripts/test_tests_line_source_prose.py:24 | 2 | BOB |
| R10 | [1/3] | 🟡 | Added tests push this file beyond the 800-line limit: the supplied mechanical facts place the final function through line 805. Move the command-normalization tests into a focused test module and register it. | skills/run-autopilot/cli/test_verification_dirty.py:776 | 1 | BOB |
| R11 | [1/3] | 🟡 | Existing functions exceed the 50-line limit, including `_run_locked_gate` at 52 lines and `run_gate` at 53. Their bodies are unchanged; refactoring them is outside this normalization/prose change. | skills/run-autopilot/cli/verification.py:551 | general | BOB |
| R12 | [1/3] | 🟡 | 4 touched test(s) pass against the pre-change code, including test_normalize_command_collapses_whitespace_only: the new whitespace-only tests do not pin this change at base. | skills/run-autopilot/cli/test_verification_dirty.py | general | mech-check |
| R13 | [1/3] | ⚪ | Out-of-scope formatter churn in this diff: quote-style flips in test_verify_queue_prose.py and a `run_gate(...)` argument reflow in test_verification_dirty.py. Neither traces to the PRD, so revert them. | skills/run-autopilot/cli/test_verification_dirty.py:627 | general | ALICE |
| R14 | [1/3] | ⚪ | Step 6 runs `autopilot verify` in more cases than the PRD says. The PRD says only when `gate.tests_line` is absent. The prose also runs it when the section holds a non-counts line (`counts unavailable`, `dirty`, `failed to run`). This is defensible, and the prose test does not pin it, but it goes beyond the spec. | skills/review-work-completion/SKILL.md:402 | 1 | BLAKE |
| R15 | [1/3] | ⚪ | The prose test `test_step_6_has_no_sha_counts_reuse_rule` is weak. Its single regex needs `sha`, then `==`/`equals`/`matches`, then `HEAD` within 40 characters each. A reworded sha/counts rule, such as "record sha is the reviewed HEAD", would pass it. The positive test accepts any mention of `## Test gate`. | skills/review-work-completion/scripts/test_tests_line_source_prose.py:29 | 1 | BLAKE |
| R16 | [1/3] | ⚪ | `_write_record` stores `normalize_command(command)`, which is the whitespace-collapsed command, not the raw command the PRD's module text names. This matches the PRD's prose wording ("exactly as run, whitespace collapsed") and `final-verification.md:131`, and the PRD contradicts itself here. It is harmless: reuse normalizes both sides anyway. | skills/run-autopilot/cli/verification.py:379 | 1 | BLAKE |
| R17 | [1/3] | ⚪ | The working tree carries uncommitted formatter-only quote reflow in `skills/work/scripts/test_verify_queue_prose.py` and `skills/run-autopilot/cli/test_verification_dirty.py`. It is unrelated to the PRD and has no behavioral effect. Revert or commit it separately. | skills/work/scripts/test_verify_queue_prose.py:274 | general | BLAKE |

## Alice

Her findings are rows R1, R2, R3, R5, R6, R7, R13 above. Consensus rubric verdicts:

R1: pass
R2: fail
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: fail
R10: pass
R11: pass
R12: pass
R13: pass

## Blake

Blind lens, PRD-only. His findings are rows R1, R8, R14, R15, R16, R17 above. He reported compliant: `normalize_command` collapses whitespace only; both new tests exist; the `bash ./` case became `stale` while the extra-spaces case stays `reused`; step 6 now takes the line from `gate.tests_line`; the docs-only check and suffix rules are kept; the new prose test is registered in `dev/bin/release-checks:359`. He ran the PRD's exit-criteria pytest command: 80 passed. Blind rubric verdicts:

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
B16: pass
B17: pass
B18: pass
B19: pass

## Bob

Doubt + de-slop lens (codex), after one retry (inlined). FIX: rows R2, R3, R9, R10. VERIFY: row R4. KNOWN: row R11.

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

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

Carl: unavailable (no reviewer output; copilot backend authentication failed, exit 1, retried once).

Verdict: 17 findings
Tests: 6301 passed, 67 failed, 32 skipped (suite run this cycle)
