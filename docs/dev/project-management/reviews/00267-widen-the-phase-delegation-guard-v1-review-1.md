---
prd: docs/dev/project-management/prds/wip/00267-widen-the-phase-delegation-guard-v1.md
review: 1
date: 2026-10-07
head_sha: 20ef80228427ecdfb4194e5244e71e0c5b2bd8da
codex_thread_id: 01a1152d-0707-7891-ac73-3795c14e83b4
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
dispatch_rows:
  bob: 25fba6ce
  carl: 358a77db
---

# Review: 00267-widen-the-phase-delegation-guard-v1

Diff range: `494ee1d133506d0de2788f55f2ccfbb60eb5e1ee..20ef80228427ecdfb4194e5244e71e0c5b2bd8da`

codex_rung_guard: not fired

Engine: `legacy` (single consensus subagent). Pack: ok. Doubt reviewer: codex (Bob); Eve not activated.

Consolidation notes (fail loud):

- `consolidate_findings.py` produced the table below. Bob's bucketed output used `- [BOB]` bullets, which its line pattern does not match; the bullets were stripped and the script re-run once, after which all four of his FIX findings appear (R7-R10).
- The script merged row R1 across four distinct citations after line-suffix stripping (`guard_phase_delegation.py:64 ~ :44 ~ :43 ~ :97`). Blake's three separate low-severity observations (whitespace not normalized inside the `work phase` jargon at :44, curly **double** quotes not accepted at :43, and the negation exception being broader than a pure double-negation reading at :64) and his 🟡 widened-verb false-positive surface at :97 are folded into that one row. They are preserved verbatim in Blake's section below.

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [2/4] | 🟡 | `Don't hesitate to run the work phase` is still allowed. Only `not`/`never` get the `hesitate\|fail\|only` double-negation exception. The contraction `don't` (and `doesn't`, `won't`) stays a plain negation and hides the delegation (probe returns False). This is the same missed class as the PRD's own `Do not hesitate...` and is the more common spelling. It matches the PRD's literal wording, so extend the exception to the contractions or record the gap as a deliberate limit | hooks/guard_phase_delegation.py:64 | 3 | ALICE, BLAKE |
| R2 | [1/4] | 🟡 | The new verbs `do`/`complete`/`start` plus the 3-word gap over-match ordinary prose and falsely deny. Probes that return True (deny): "Tell me what we do in the work phase", "Decide what to do about the work phase", "Tasks complete in the work phase", "Start with the work phase fixtures", "Review diff; complete the work phase checklist", "Fix the bug. Do tests for the design phase". Gap words may be prepositions or nouns, so verb plus any 3 words plus jargon fires. PRD says a false deny costs a session. The allowed corpus still passes, but it holds no case for these verbs. Safer shape: limit gap words to determiners and modifiers (the\|this\|entire\|whole\|full\|all\|complete), or require a non-preposition gap for the six new verbs | hooks/guard_phase_delegation.py:97 | 3 | ALICE |
| R3 | [1/4] | 🟡 | The false-positive side of the widened verbs has no test. `test_non_delegating_verb_before_a_phase_name_is_allowed` uses only `Review`, `Document` and `Test`, which were never delegating verbs. It passes against the pre-change code and cannot fail if `do`/`complete`/`start`/`call` over-match. Add negative cases that use the new verbs, such as "what we do in the work phase" or "Tasks complete in the work phase". Those currently deny, so the fix above has to land first | hooks/test_guard_phase_delegation.py:284 | 3 | ALICE |
| R4 | [1/4] | 🟡 | The `_IMPERATIVE_COLON` restriction is untested. It keeps the colon-lead pattern off the new verbs so "Work phase: complete" and "In the work phase: do not skip tests" stay allowed. Nothing pins this: no test asserts those strings are allowed, so swapping in `_IMPERATIVE` would pass if the corpus lacks them | hooks/test_guard_phase_delegation.py:284 | 3 | ALICE |
| R5 | [1/4] | 🟡 | The `Never fail to report; do not run the work phase.` case does not pin the `hesitate\|fail\|only` exception. It is allowed with or without the exception, because the `;` ends the sentence and the later `do not run` is a real negation. It passes against the pre-change code. Use a case where the exception changes the outcome | hooks/test_guard_phase_delegation.py:207 | 3 | ALICE |
| R6 | [1/4] | 🟡 | Simplification: the six original verbs are spelled out twice, in `_IMPERATIVE` and `_IMPERATIVE_COLON`. Build `_IMPERATIVE` from the colon list plus `\|start\|do\|perform\|complete\|launch\|call`. `_BARE_SKILL` and `_PREFIXED_SKILL` also repeat the same skill alternation and quote group. The new `_PREFIXED_SKILL` pattern subsumes the prefixed alternatives of `_BARE_SKILL`, so that pattern only needs the bare names | hooks/guard_phase_delegation.py:31 | 3 | ALICE |
| R7 | [1/4] | 🟡 | `_SKILL_READ` newly denies `Read skills/work/SKILL.md and do not perform all tasks`: negation is checked before `Read`, missing the prohibition inside the match. Check negation around the execution verb and add this allowed regression case. | hooks/guard_phase_delegation.py:58 | 3 | BOB |
| R8 | [1/4] | 🟡 | Non-UTF-8 tests only exercise payloads that remain invalid JSON after replacement; catching UnicodeDecodeError and returning `{}` also passes. Add invalid bytes inside a JSON string alongside a valid delegation, asserting the hook still denies it after replacement decoding. | hooks/test_guard_phase_delegation.py:495 | 2 | BOB |
| R9 | [1/4] | 🟡 | Tests omit the `only` negation exception, exactly-three/four-word gap boundaries, and a prefixed skill with intervening words. Add explicit cases pinning these contracts; current examples cannot detect their removal or incorrect limits. | hooks/test_guard_phase_delegation.py:235 | 3 | BOB |
| R10 | [1/4] | 🟡 | Replay reports 12 touched cases passing against base. Preservation controls have a purpose, but `test_positive_controls_carry_raw_non_ascii_bytes_and_exceed_4kib` only tests generated fixture data. Move those checks into the subprocess test's setup and remove the standalone helper-only test. | hooks/test_guard_phase_delegation.py:488 | 2 | BOB, mech-check |
| R11 | [1/4] | ⚪ | Beyond the PRD: double-quote and curly-quote skill names are now accepted (`_CURLY_QUOTES`, soft hyphen and word joiner stripping). The PRD asks only for single quotes and zero-width characters. The extras are harmless and tested, but they widen the match surface unrequested | hooks/guard_phase_delegation.py:41 | 3 | ALICE |
| R12 | [1/4] | ⚪ | The denied-corpus count is hard-coded as 17 in two places. The next fixture added breaks both asserts. This continues the existing hard-coded 4 | hooks/test_guard_phase_delegation.py:53 | 1 | ALICE |
| R13 | [1/4] | ⚪ | `read_input` silently falls back to text `sys.stdin.read()` when `sys.stdin.buffer` is absent. The fallback exists for `capture_main`'s StringIO swap, but the docstring does not mention it or the new bytes-then-replace decode path | hooks/_common.py:30 | 2 | ALICE |
| R14 | [1/4] | ⚪ | Test brittleness. `_denied()` and the committed-allowed test hard-pin fixture counts (17 and 24). Adding a fixture later breaks them for no behavioral reason. | hooks/test_guard_phase_delegation.py:53 | general | BLAKE |
| R15 | [1/4] | ⚪ | The zero-width fixture is a single file covering both "inside Run" and "inside work". The spec lists the two together, so this is compliant, but a regression that handled only one of the two would still pass the fixture. The mid-prompt parametrized tests cover each of the five invisible code points separately. | hooks/fixtures/phase_delegation/denied/zero-width-run-work.txt:1 | 1 | BLAKE |
| R16 | [1/4] | ⚪ | Cannot statically verify: tests and release checks pass at the reviewed revision. Run `python3 -m pytest hooks/test_guard_phase_delegation.py` and `bash dev/bin/release-checks`; require exit 0 from both. The supplied gate reports 2620 passing tests, but execution was prohibited for this review. | N/A | general | BOB |
| R17 | [1/4] | ⚪ | The added design document contains 1022 lines, exceeding the rubric's 800-line limit. It belongs to held PRD 00265, outside this guard's tasks; the repository's mechanical style gate explicitly skips non-Python files. | docs/dev/project-management/designs/00265-close-the-critical-row-escapes-v1-design.md:1022 | general | BOB |

## Alice

Consensus lens, implementation-aware. Nine findings (six 🟡, three ⚪), all in the table above as R1-R6, R11-R13. No CRITICAL, no HIGH. Her central point: the widened verb list plus the 3-word gap creates new false-deny surface that the allowed corpus does not cover, and the contraction `don't hesitate` form of the PRD's own example phrasing is still allowed.

R1: fail
R2: fail
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

## Blake

Blind lens, PRD-only. Six findings (one 🟡, five ⚪), verbatim:

- ⚪ Whitespace is not normalized after NFKC. The literal single space in `_PHASE_JARGON` ("work phase") means a double-spaced `Run the work  phase` is allowed (probed: returns False). Other whitespace runs between verb and gap words are handled via `\s+`, so only the jargon's internal space is exploitable. The guard targets model drift, not a hostile user, so this is low severity. | File: hooks/guard_phase_delegation.py:44
- ⚪ Curly double quotes around a skill name are not accepted. `Run “/autopilot:work”` is allowed (probed: returns False), while curly single quotes are mapped to `'` at line 43. The spec only requires single quotes, so this is a minor gap and not a spec violation. | File: hooks/guard_phase_delegation.py:43
- 🟡 The widened verb list plus the 3-word gap creates new false-positive surface, and the allowed corpus does not cover it. Probed denials: `Do review the work phase diff`, `Call the work phase reviewer`, `Start with the work phase review`, `Run all the work phase tests now`, `Start reviewing the design phase`. In loop mode each costs an Agent dispatch. This follows from the spec's own design, so it is a spec-inherent tradeoff and not an implementation defect. | File: hooks/guard_phase_delegation.py:97
- ⚪ Negation exception is broader than a pure double-negation reading. `not|never` followed by `hesitate|fail|only` is exempt, as the spec says. So `Do not only run the work phase` and `never only run the work phase` are now denied (probed: both True). | File: hooks/guard_phase_delegation.py:64
- ⚪ Test brittleness. `_denied()` and the committed-allowed test hard-pin fixture counts (17 and 24). | File: hooks/test_guard_phase_delegation.py:53
- ⚪ The zero-width fixture is a single file covering both "inside Run" and "inside work". | File: hooks/fixtures/phase_delegation/denied/zero-width-run-work.txt:1

His verification summary: every phrasing in the PRD's list has a denied fixture and each is denied when probed directly; both controls are denied; `read_input` keeps its signature and fails open; `is_phase_delegation` keeps its signature; `python3 -m pytest hooks/test_guard_phase_delegation.py` gives 146 passed; `bash dev/bin/release-checks` ended `PASS 2620 FAIL 0 SKIP 0 EXIT 0`. No new dependencies, no security or data-safety regression.

B1-B19: pass (all nineteen).

## Bob

Doubt lens plus de-slop, via codex (first run, no retry). Four 🟡 FIX findings (R7-R10), one ⚪ VERIFY (R16, queued to `00267-widen-the-phase-delegation-guard-v1-checks-1.json`), one ⚪ KNOWN (R17).

R1: fail
R2: fail
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: pass
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

UI and design lens, via gemini (copilot backend). `[CARL] ✅ No issues found`. He ran the guard's own test file and `dev/bin/release-checks` himself.

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

## Mechanical checks

- Tautological test shapes: 36 test functions checked, no finding.
- Fail-first replay: 41 touched tests ran against base `494ee1d13350`, 29 failed, 12 passed. The one `[MECH]` 🟡 line is folded into R10, which raises the same fact.

Verdict: 17 findings
Tests: 2620 passed, 0 failed, 0 skipped (suite run this cycle)
