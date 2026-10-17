---
prd: docs/dev/project-management/prds/wip/00333-sweep-only-findings-two-reviewers-raised-v1.md
review: 1
date: 2026-10-17
head_sha: 6ecbc5b4450d529f176733e733176b255248dbe4
codex_thread_id: 01a14a51-c0b0-7e11-890d-36166745d40a
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
dispatch_rows:
  bob: a9242683
  carl: d9cee6f7
---

# Review: 00333-sweep-only-findings-two-reviewers-raised-v1

Diff range: `a2858cb407a2fa7b071fc603c1ba02c741203849..6ecbc5b4450d529f176733e733176b255248dbe4`

codex_rung_guard: not fired

## Review Summary

Reviewed: 3 completed tasks
PRDs checked: 00333-sweep-only-findings-two-reviewers-raised-v1.md
Consensus engine: legacy (single Alice subagent)
Pack: ok
Mechanical checks: 0 tautological test shapes in 32 test functions across 3 files; fail-first replay 4 touched tests ran, 4 failed against base, 0 passed. No `[MECH]` findings to absorb.
Carry-forward: none (cycle 1, no prior checks queue).

### Agent Status
- Alice: ✅ Available
- Blake: ✅ Available
- Bob: ✅ Available (first run was a lack-of-input refusal — `sandbox-exec: sandbox_apply: Operation not permitted`; after one retry (inlined) he produced a full review)
- Carl: ✅ Available (gemini backend)

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [3/4] | 🟡 | The prose edits are not verbatim as the PRD contract requires. Backticks are stripped in the Classification paragraph (`[1/N]`, `discard`, `disposition: "discarded"`, `single-voice`). The Select sentence reads "as discarded" without backticks and uses `->` where the PRD has `→`. The mapping row is `| Single-voice Medium or Low | "discard" |` without backticks, unlike every sibling row, which writes `"discard"` in backticks. The prose test then pins the stripped form, so the PRD's exact text is not asserted. | skills/run-autopilot/references/phase-review.md:134 | 2 | ALICE, BLAKE, BOB |
| R2 | [2/4] | 🟡 | The new refusal tests miss the negative and ordering cases. Nothing pins that a multi-voice `fix` row, a single-voice 🟠/🔴 `fix` row, a single-voice non-`fix` row (for example `discard`) or a row with no `found_by` is handled correctly at the decision gate. Dropping the severity or classification condition in `_single_voice_refusal` would still pass the whole suite, because the shared `_finding` default was raised to two finders. The tail-sweep order (after `tail_sweep_above_medium`, before `tail_sweep_duplicates_deferral`) is unpinned too: `tail_sweep_single_voice` is absent from `test_a_tail_sweep_tripping_two_refusals_reports_the_earlier_kind` and `test_cli_exits_2_on_every_tail_sweep_refusal`. Add parametrize cases. | skills/run-autopilot/cli/test_review_close_tail_sweep.py:294 | 1 | ALICE, BOB |
| R3 | [2/4] | 🟡 | `_tail_sweep_refusal` is still 55 lines (mechanical facts), over the 50-line limit. It was already about 56 before this diff and the docstring trim shaved a few lines, but it was touched again. Extracting the carry, gate and empty checks would bring it under the limit. | skills/run-autopilot/cli/review_close.py:585 | 2 | ALICE, CARL |
| R4 | [2/4] | ⚪ | The `found_by` guard counts `len(row.get("found_by") or [])`. A string value ("CARL" has length 4) or a duplicated list (["CARL", "CARL"]) passes as multi-voice. The PRD's stated aim is that a hand-built batch cannot bypass the rule. Require a list and count distinct entries, `len(set(...))`. | skills/run-autopilot/cli/review_close.py:561 | 2 | ALICE, BLAKE |
| R5 | [2/4] | ⚪ | The shared fixture `_finding` default `found_by` was changed from `["bob"]` to `["alice", "bob"]`. This was needed to keep 10 existing tests valid and is recorded in the deferred ledger and assumptions.md, so it is acceptable. It does mean the existing suites no longer exercise single-voice rows unless a test overrides `found_by`. | skills/run-autopilot/cli/test_review_close.py:101 | 2 | ALICE, BLAKE |
| R6 | [1/4] | 🟡 | Select now holds two overlapping skip sentences: "Zero such rows -> skip the sweep." followed by "**Zero actionable Medium/Low → skip the sweep entirely**". "Such rows" is ambiguous between the multi-voice rows and the actionable ones, so an orchestrator can read two different skip conditions. The PRD gave this wording, but fold the two into one clause so the skip condition is stated once. | skills/run-autopilot/references/phase-review.md:197 | 2 | ALICE |
| R7 | [1/4] | 🟡 | `phase-review.md` Classification still lists "Low severity, any consensus" and "Medium severity, 1/3 consensus" under **Auto-fix**, and the new Single-voice rule sits below them. A `[1/N]` Medium or Low row matches both, so an orchestrator reading top-down can auto-fix it. The new rule has no "takes precedence" wording. | skills/run-autopilot/references/phase-review.md:109 | single-voice-prose | BLAKE |
| R8 | [1/4] | 🟡 | Finder counting lacks type validation: a string such as `"CARL"` counts as four finders, while an integer raises TypeError. Validate `found_by` as a list of reviewer names before counting. | skills/run-autopilot/cli/review_close.py:561 | 2 | BOB |
| R9 | [1/4] | 🟡 | Prose in phase-review.md omits required code backticks and uses ASCII arrow, and test_single_voice_prose.py asserts the un-backticked strings | skills/run-autopilot/references/phase-review.md:134 | 2 | CARL |
| R10 | [1/4] | ⚪ | `_single_voice_refusal` is one function with two unrelated rule bodies, switched on `batch_id`; any non-`decision-gate` id falls into the tail-sweep rule. Two small predicates, one per call site, would be clearer. The 🟡/⚪ literals also repeat the `_DECISION_SEVERITY` keys; a `_MEDIUM_OR_LOW` constant beside `_ABOVE_MEDIUM` would be tidier. | skills/run-autopilot/cli/review_close.py:549 | 2 | ALICE |
| R11 | [1/4] | ⚪ | Single-voice is defined by `[1/N]`/`found_by < 2` with no check on `total_agents`. In a lane with one reviewer (`[1/1]`), every Medium or Low is discarded or refused, so it can never become a task. The PRD does not carve this out, so confirm it is intended. | skills/run-autopilot/references/phase-review.md:134 | general | ALICE |
| R12 | [1/4] | ⚪ | The Select sentence deviates from the spec text in three ways. `[1/N]` is not in backticks, "discarded" is not in backticks, and the arrow is `->` where the spec has `→`. It also adds a second, redundant "Zero ... skip the sweep" sentence next to the existing "Zero actionable Medium/Low" one. | skills/run-autopilot/references/phase-review.md:197 | single-voice-prose | BLAKE |
| R13 | [1/4] | ⚪ | The decision-gate check matches only the emoji severities 🟡 and ⚪. A hand-built row whose severity is the word "medium" or "low" bypasses `single_voice_fix`, and `_findings_refusal` may not catch it. The PRD says only the emoji, so this is a note, not a deviation. | skills/run-autopilot/cli/review_close.py:560 | single-voice-refusal | BLAKE |
| R14 | [1/4] | ⚪ | The tail-sweep refusal reason names `ref or file`, where the PRD says "naming the first offending `ref`". It is equivalent when `ref` is present. | skills/run-autopilot/cli/review_close.py:579 | single-voice-refusal | BLAKE |
| R15 | [1/4] | ⚪ | test_review_close.py is 835 lines long, exceeding the 800-line file limit | skills/run-autopilot/cli/test_review_close.py:1 | general | CARL |
| R16 | [1/4] | ⚪ | test_review_close_tail_sweep.py does not test missing or None found_by and omits tail_sweep_single_voice from CLI exit 2 parameterized test | skills/run-autopilot/cli/test_review_close_tail_sweep.py:242 | 1 | CARL |

Consolidation notes (from `consolidate_findings.py`): rows 1, 2 and 5 merged citations that matched only after line-suffix stripping.

## Alice

Consensus lens, implementation-aware. Findings R1, R2, R3, R4, R5, R6, R10, R11 above.

Checked and found no issue: `_prelock_refusal` calls the check before `_carry_refusal` for `decision-gate` only. The tail-sweep call sits between the above-medium and duplicate-deferral checks. The CLI maps any `refused` key to exit 2 (`__main__.py:1380`). The two review-close tests and both prose tests fail at base, 4 of 4 per the fail-first replay. The prose-test registration and the CHANGELOG entry match the PRD. The test gate reports 7156 passed, 0 failed, 3 skipped.

R1: fail
R2: fail
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: fail
R10: pass
R11: pass
R12: fail
R13: pass

## Blake

Blind lens, PRD-only. Findings R1, R4, R5, R7, R12, R13, R14 above.

Verified as correct:
- `_single_voice_refusal` (skills/run-autopilot/cli/review_close.py:549) is wired into `_tail_sweep_refusal` after `tail_sweep_above_medium` and before `tail_sweep_duplicates_deferral` (line 626). It is wired into `_prelock_refusal` for `decision-gate` before `_carry_refusal` (line 692).
- The refusal dicts and the zero-finders handling for a missing `found_by` match the spec.
- The four new tests exist, and the new prose test file is registered under `[checks] cap hook` at dev/bin/release-checks:235.
- An Unreleased entry for **run-autopilot** exists at CHANGELOG.md:32.

Blake reported one incidental pytest `ModuleNotFoundError` for `skills` from running pytest outside the repo root; it is a working-directory artefact, not a finding, and the repo-root gate run is green.

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
B15: pass
B16: pass
B17: pass
B18: pass
B19: pass

## Bob

Doubt lens + de-slop (codex), after one retry (inlined). Findings R1, R2, R8 above.

FIX:
- Validate finder-list input before counting — skills/run-autopilot/cli/review_close.py:561 — reject malformed values explicitly.
- Cover refusal boundaries — skills/run-autopilot/cli/test_review_close_tail_sweep.py:223 — parameterize missing finders, Low severity, and exempt classifications/severities.
- Restore verbatim prose — skills/run-autopilot/references/phase-review.md:134 — copy the required text and update prose assertions.

VERIFY:
- (none)

KNOWN:
- (none)

R1: fail
R2: pass
R3: pass
R4: pass
R6: pass
R7: fail
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

## Carl

UI/design specialist (gemini), generalist here. Findings R3, R9, R15, R16 above.

R1: pass
R2: pass
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: fail
R10: pass
R11: pass
R12: fail
R13: fail

## Verification-check queue

No entries: the doubt lens's VERIFY bucket is empty this cycle.

Verdict: 16 findings
Tests: 7156 passed, 0 failed, 3 skipped (reused from last-verification.json at c17d23a; review-stage gate verdict `reused` — only store/metadata commits lie between that sha and the reviewed HEAD)
