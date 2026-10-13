---
prd: docs/dev/project-management/prds/wip/00277-catch-critical-rows-in-every-shape-v1.md
review: 1
date: 2026-10-13
head_sha: 6c91948824cb82676ed7aae5120c9c5c64f0d15a
codex_thread_id: 01a13413-74f0-7131-9c00-104ec8479bca
reviewers: alice,blake,bob
agents:
  alice: available
  blake: available
  bob: available
  carl: unavailable
dispatch_rows:
  bob: 6fefed13
  carl: 64a2e920
---

# Review: 00277-catch-critical-rows-in-every-shape-v1

Diff range: `adfe6e2466f344fadac2cd60fabee92d032464d6..6c91948824cb82676ed7aae5120c9c5c64f0d15a`

codex_rung_guard: not fired

## Run notes

- Carl (Gemini) ran twice and produced no output. First dispatch: copilot backend, exit 1, GitHub token authentication failure. Retry on the native `gemini` backend was stopped at the harness background time limit (~10 min) with no output written. Carl counts as a failed reviewer this cycle; the batch latch is NOT applied (neither failure was exit 4).
- Bob (codex) first run was a lack-of-input refusal (`sandbox-exec: sandbox_apply: Operation not permitted` on every read). His one retry ran as the inlined retry prompt and produced a full review. His issue lines carry a leading `- ` bullet inside the FIX block, so `consolidate_findings.py` skipped them on the first pass; the bullet prefix was stripped and the lines re-consolidated verbatim **(format warning: Bob's issue lines were bullet-prefixed)**.
- Engram context pack failed to build (`engram pack exit 1: sqlite3.OperationalError: attempt to write a readonly database`). The cycle ran without findings precedent — degraded, not invalid.

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [2/3] | 🟠 | The PRD's headline shape (a plain "🔴 bullet with no token", natural for a model to write) is still refused only when the line ends in a case-exact `| Found by:` or the emoji is directly followed by a severity word. Probed with `gate._unread_token`: `- 🔴 crash on empty input | src/a.py:3`, `- 🔴 crash on empty input`, `1. 🔴 crash | src/a.py:3`, `* 🔴 Critical: crash` and `- **🔴** crash | src/a.py:3 | alice` all return None, so `review-close` still applies with `tasks_created: []`. The corrected contract and the PRD say "severity emoji anywhere" on a pipe-shaped line. The implementation is narrower than both, and the tests only build the `| Found by: alice` form. | skills/run-autopilot/cli/gate.py:422 | 2 | ALICE, BLAKE |
| R2 | [2/3] | 🟡 | `test_gate_findings_shapes.py` is now 1049 lines. It was 771 at base, so this diff pushed it past the 800-line limit. Split the new PRD 00277 sections (the `_unparsed_rows`, near-variant and `_NOT_FINDINGS` groups, about lines 864-1046) into a sibling file such as `test_gate_findings_unread_shapes.py`. Register the new file in the `[checks]` block as the repo's pytest convention requires. | skills/run-autopilot/cli/test_gate_findings_shapes.py:1049 | 1 | ALICE, BOB |
| R3 | [1/3] | 🟠 | Tokenless CRITICAL bullets still escape: `- 🔴 CRITICAL: stale cache survives restart` matches no arm because it lacks a pipe/HTML tag. Even `- 🔴 stale cache | src/x.py:3` escapes without the severity word or exact `Found by:` suffix. Restore detection for these PRD-required shapes and add regression cases; explicitly account for affected baseline reviews. | skills/run-autopilot/cli/gate.py:422 | 2 | BOB |
| R4 | [1/3] | 🟠 | Anchoring consensus variants hides rows with a leading reference: `R9 ［2/2］ stale cache | src/x.py:3` escapes every check. Detect variants after a reference or elsewhere on a structurally tabular line, while preserving ordinary prose-count exclusions. Add this regression case. | skills/run-autopilot/cli/gate.py:176 | 2 | BOB |
| R5 | [1/3] | 🟠 | Indenting a fenced table header bypasses the new refusal. `_table_header` requires a leading pipe at column zero, so a header beginning `  | Ref | Consensus | Severity | Issue | File | Found By |` is missed while `_unfenced` blanks the entire table. Normalize body indentation for header detection and test both fence characters with indented headers. | skills/run-autopilot/cli/gate.py:497 | 3 | BOB |
| R6 | [1/3] | 🟡 | `_FOUND_BY = "Found by:"` is matched with a case-sensitive `in`. The table header spells it "Found By", and `- 🔴 crash | a.py:3 | Found By: alice` or `found by:` returns None (verified). Use a case-insensitive regex such as `re.compile(r"found by:", re.IGNORECASE)`; this does not change the other arms. | skills/run-autopilot/cli/gate.py:186 | 2 | ALICE |
| R7 | [1/3] | 🟡 | Task 1 required rewriting the docstring of `test_an_indented_fence_still_quotes_its_rows`, but it still says "The fence rule reads the stripped line", which is no longer true. Replace it with the raw-line, at-most-3-leading-spaces wording. This is a doc-only edit. | skills/run-autopilot/cli/test_gate_findings_shapes.py:610 | 1 | ALICE |
| R8 | [1/3] | 🟡 | Simplification: `_fenced_findings_header` (gate.py:477-504) copies the fence walk of `_unfenced` (gate.py:396-410), and the two closer checks have already diverged in form. Extract one `_closed_fences(lines)` generator yielding `(open_idx, close_idx)` spans so the opener and closer rule lives once. | skills/run-autopilot/cli/gate.py:477 | 3 | ALICE |
| R9 | [1/3] | 🟡 | Simplification: `_ROW_SHAPE_RE` and `_SEVERITY_EMOJI_ANY_RE` are used only inside `_is_unread_line`, but sit as module-level regexes in a 7-arm boolean with 4 rationale comments spread across lines 149-189. Group the arms into named predicates (e.g. `_is_marker_variant`, `_is_wordless_row`, `_is_pipeless_row`). | skills/run-autopilot/cli/gate.py:414 | 2 | ALICE |
| R10 | [1/3] | 🟡 | The refusal test injects controls only through `raw`, leaving the newly escaped `boundary_desc` and `state_path` behavior unpinned. Add independently parametrized control-character cases for those arguments so removing either escape fails a test. | skills/run-autopilot/cli/test_review_stage_paths.py:114 | 4 | BOB |
| R11 | [1/3] | 🟡 | 9 touched test(s) pass against the pre-change code: test_a_fenced_example_bullet_and_row_without_header_are_not_findings, test_fenced_example_rows_without_header_still_pass, test_a_line_with_no_severity_signal_is_not_a_row +3 more | skills/run-autopilot/cli/test_gate_findings_shapes.py | general | mech-check |
| R12 | [1/3] | ⚪ | `_boundary_refusal_line` now escapes `boundary_desc` and `state_path`, but `test_refusal_line_stays_single_line_with_control_chars` forges only `prd`. Dropping `!r` from `state_path` or `boundary_desc` would pass every test. Add a case with a control character in `--state` and in the `design_doc` field. | skills/run-autopilot/cli/test_review_stage_paths.py:114 | 4 | ALICE |
| R13 | [1/3] | ⚪ | The false-refusal replay guard covers 79 saved reviews, not the 95 the PRD cites, and 46 of the 79 baseline verdicts are already "malformed". The replay therefore says little about false refusals from the widened flag. `_ACCEPTED_FLIPS` is empty, but I could not verify that no real fixture would flip under the PRD's literal emoji rule, because the implementation does not apply it | skills/run-autopilot/cli/fixtures/gate_replay_baseline.json | 2 | BLAKE |
| R14 | [1/3] | ⚪ | The output-formats.md header-fencing prose is at line 103, not line 101 as the spec says. It is a new paragraph and `rg header` hits on it, so the acceptance command passes | skills/review-work-completion/references/output-formats.md:103 | general | BLAKE |
| R15 | [1/3] | ⚪ | Beyond the spec's repo structure, the findings parser was split out into a new `findings_section.py` (refactor 494b5a7, a 50-line-limit move). The implementation also adds heuristics the PRD does not list: lenticular brackets, a "Found by:" rule and a leading-ratio rule. They are in service of the flag, so I count them as mild scope drift only | skills/run-autopilot/cli/findings_section.py | general | BLAKE |

## Alice

Consensus lens, implementation-aware. Eight findings (R1, R2, R6, R7, R8, R9, R12, and the gate.py:189 known-tradeoff comment folded into R1).

R1: fail
R2: pass
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: fail
R10: pass
R11: pass
R12: pass
R13: fail

Verification: the narrow suite (`test_gate_findings_shapes.py`, `test_gate_findings_real_fixtures.py`, `test_review_stage_paths.py`) gives 266 passed, 90 subtests passed, 0 skipped. `_ACCEPTED_FLIPS` is empty, so the real-review replay shows no flips.

## Blake

Blind lens, PRD-only. Five findings (R1, R13, R14, R15, and the both-sides-pipe narrowing folded into R1).

B1: fail
B2: pass
B3: pass
B4: pass
B5: pass
B6: pass
B7: pass
B8: pass
B9: pass
B10: fail
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

Doubt + de-slop lens, codex, after one retry (inlined). Five findings (R2, R3, R4, R5, R10). **(format warning: issue lines were bullet-prefixed)**

FIX: R3, R4, R5, R2, R10. VERIFY: (none). KNOWN: (none).

R1: fail
R2: pass
R3: pass
R4: pass
R6: pass
R7: fail
R8: pass
R9: fail
R10: pass
R11: pass
R12: pass
R13: fail

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

Carl: unavailable (copilot backend exit 1, GitHub token authentication failure; native-gemini retry stopped at the background time limit with no output).

Verdict: 15 findings
Tests: 3780 passed, 0 failed, 0 skipped (suite run this cycle)
