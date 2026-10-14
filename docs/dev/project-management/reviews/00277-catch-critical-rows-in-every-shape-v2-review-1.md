---
prd: docs/dev/project-management/prds/wip/00277-catch-critical-rows-in-every-shape-v2.md
review: 1
date: 2026-10-15
head_sha: 95ff83943d5edbb16391802fc3080d59642f97e6
codex_thread_id: 01a13c6e-f048-76f0-a42d-adad7638af36
agents:
  alice: available
  blake: available
  bob: available
  carl: available
reviewers: alice,blake,bob,carl
dispatch_rows:
  bob: 429e5b3c
  carl: 6861ee1b
---

# Review: 00277-catch-critical-rows-in-every-shape-v2

Diff range: `86f571cea51154c27888773b27c1545d1a9f6494..95ff83943d5edbb16391802fc3080d59642f97e6`

codex_rung_guard: not fired

## Review Summary

Reviewed: 3 completed tasks
PRDs checked: 00277-catch-critical-rows-in-every-shape-v2.md

### Agent Status

- Alice: ✅ Available (Claude subagent, consensus lens)
- Blake: ✅ Available (Claude subagent, blind lens, PRD-only)
- Bob: ✅ Available (codex, doubt lens) — after one retry (inlined). The first
  dispatch exited 0 but returned a lack-of-input refusal
  (`sandbox-exec: sandbox_apply: Operation not permitted`; codex never read the
  supplied files), confirmed against all three conditions of the refusal shape.
  The one-retry budget was spent on the inlined retry prompt
  (`docs/dev/tmp/bob-prompt-20261014-2210-retry.md`, 161 KB: context and full
  diff pasted verbatim), which produced a complete review. The first run's
  output is kept at `docs/dev/tmp/bob-output-20261014-2210-firstrun.txt`.
- Carl: ✅ Available (gemini-run `backend=copilot model=gemini-3.8-flash`)

Degradations this cycle:

- Engram context pack failed: `engram pack exit 1: sqlite3.OperationalError:
  attempt to write a readonly database`. Every prompt carried
  `(no pack available this cycle)`. The review is degraded on findings
  precedent, not invalid.
- No verification-check queue was written. The only VERIFY item this cycle is
  Bob's `_ACCEPTED_FLIPS` departure-report check, which names a two-step
  comparison rather than one runnable command — **not queued: command shape**.
  It stays an ordinary finding (R12).

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [3/4] | 🟡 | CHANGELOG line 31 was not reworded, although the PRD and Task 3 require it. It still reads "wordless/bracket/fullwidth row", the claim the PRD says is wrong. Only a new line (CHANGELOG.md:36) was added. The PRD must-have "CHANGELOG line 31 describes the lead-normalised rule" is unmet | CHANGELOG.md:31 | 3 | ALICE, BLAKE, CARL |
| R2 | [2/4] | 🟠 | _strip_lead adds a "same lead mark may not repeat" rule (last_mark/break) that is in neither the PRD nor the design, so nested leads are not stripped. `> > 🔴 crash`, `- - 🔴 crash`, `– – 🔴 x` and `> > - 🔴 x` return _is_emoji_row False. I ran each one. The old `_BULLET_LEAD_RE.match` plus `search` arm refused all of them, so a CRITICAL row in a nested blockquote or nested list now passes the gate. This is a regression of the trust boundary the PRD exists to close, and the PRD says leads are stripped "in any combination". The `-- 🔴` case it was added for is unspecified. Fix: drop the last_mark logic (design `_strip_lead` has none) and delete the `-- 🔴` expectation | skills/run-autopilot/cli/gate.py:240 | 2 | ALICE, BLAKE |
| R3 | [2/4] | 🟠 | `_strip_lead` stops at any repeated non-emphasis mark, so a nested lead hides the row. `> > 🔴 crash x.py:3`, `- - 🔴 crash` and `• • 🔴 x` all returned None (read as prose) in my probes. The spec says the lead is stripped "in any combination". The cause is the `ch == last_mark and ch not in ("*","_")` break, which skips the second mark. `test_non_letter_junk_before_the_emoji_is_not_a_lead` pins `-- 🔴` as not a row, so the gap is deliberate. A nested blockquote or nested bullet row with a CRITICAL emoji and a file cell still passes the gate. | skills/run-autopilot/cli/gate.py:243 | Phase 1 | BLAKE, BOB |
| R4 | [2/4] | ⚪ | Style and size: the new `_fence_close` is followed directly by the unrelated `# The malformed detail...` comment with no blank lines (PEP8 expects two). gate.py is at 796 of 800 lines, and test_gate_findings_shapes.py (1056 lines) grew again past the limit | skills/run-autopilot/cli/gate.py:794 | general | ALICE, BLAKE |
| R5 | [1/4] | 🟠 | test_non_letter_junk_before_the_emoji_is_not_a_lead pins the `-- 🔴` doubled-dash case as prose, so it locks in the nested-lead bypass above. No test covers `> > 🔴` or `- - 🔴`, which must be rows. R9 and R1 fail on this | skills/run-autopilot/cli/test_gate_findings_unread_shapes.py:1092 | 1 | ALICE |
| R6 | [1/4] | 🟡 | Dead code: `_BULLET_LEAD_RE` is now unused (rg finds only its definition, gate.py:203), and its comment still describes the deleted bullet-lead arm. The design assumed it was "still used elsewhere"; only `_SEVERITY_EMOJI_ANY_RE` is. Remove it and the comment | skills/run-autopilot/cli/gate.py:198 | 2 | ALICE |
| R7 | [1/4] | 🟡 | `_ACCEPTED_FLIPS` accepts 00269-sweep-every-findings-token-v1-review-1 (comment: `🔴 row while the unmatched opener itself stays live (R6)...`). That line looks like a wrapped prose continuation that starts with a mention of the emoji. It meets the mechanical join rule but is probably a false refusal of the same kind packet 5 describes. The comment justifies it only as "newly caught under the no-lead-needed rule", with no check that it is a real finding row | skills/run-autopilot/cli/test_gate_findings_real_fixtures.py:916 | 3 | ALICE |
| R8 | [1/4] | 🟡 | The design's pseudo-opener followed by a real closed fence case is untested. The current test ends with an unclosed opener. Add a visible row before a real fence pair and visible content afterward, asserting that only the real fenced span is blanked. | skills/run-autopilot/cli/test_gate_findings_unread_shapes.py:284 | 1 | BOB |
| R9 | [1/4] | 🟡 | Simplification: _strip_lead tests single-character membership via regex _LEAD_MARK_RE.match(ch) where a frozenset lookup is simpler and avoids regex evaluation overhead | skills/run-autopilot/cli/gate.py:242 | 2 | CARL |
| R10 | [1/4] | ⚪ | `_BULLET_LEAD_RE` is now dead code (no readers) and its comment describes the removed rule. | skills/run-autopilot/cli/gate.py:198 | Phase 1 | BLAKE |
| R11 | [1/4] | ⚪ | Task 3's required rewrite of the existing changelog entry is missing; the diff only adds a Fixed entry. Update the original entry to describe the first-character-after-lead-normalisation rule. | CHANGELOG.md:31 | 3 | BOB |
| R12 | [1/4] | ⚪ | The supplied context lacks the required report quoting every departing baseline entry's refusal line. Compare `_ACCEPTED_FLIPS` between 86f571cea511 and 95ff83943d5e, then check that Task 3's report quotes the previous refusal line for every departure and the current refusal line for every addition. | skills/run-autopilot/cli/test_gate_findings_real_fixtures.py:179 | 3 | BOB |
| R13 | [1/4] | ⚪ | The shared test file exceeds the 800-line limit; its final test starts at line 1041. This predates the diff, and splitting it exceeds this task's prescribed helper and closer-test edits. | skills/run-autopilot/cli/test_gate_findings_shapes.py:1041 | general | BOB |
| R14 | [1/4] | 🟡 | 7 touched test(s) pass against the pre-change code: test_a_longer_closer_closes_and_a_4_space_closer_does_not, test_a_4_space_opener_does_not_open_a_fence, test_a_line_with_no_severity_signal_is_not_refused +1 more | skills/run-autopilot/cli/test_gate_findings_unread_shapes.py | general | mech-check |

R14 is the mechanical fail-first replay finding, absorbed from the context
file's computed block. Replay totals: 74 touched tests ran, 67 failed against
the base, 7 passed. No row in the table named that test file, so it is its own
row. The tautological-shapes block found nothing across 85 test functions in 3
files.

**Overlap note (for the decision gate).** R2, R3 and R5 are one defect — the
`last_mark` guard in `_strip_lead` and the test that pins it — split across
three rows only because the reviewers cited `gate.py:240`, `gate.py:243` and
the test file. Counting distinct reviewers, the nested-lead bypass is a 3/4
finding (Alice, Blake, Bob), the strongest signal in the cycle. R1 and R11 are
likewise the same CHANGELOG defect (4/4 across Alice, Blake, Carl, Bob), and
R6/R10 are the same dead-`_BULLET_LEAD_RE` observation.

## Alice

6 findings, listed above as R2, R5, R6, R1, R7, R4. She ran the four gate test
files together: 439 passed, 93 subtests passed. She reports the fence rule, the
emoji wording, the helper fix and the closer re-pin otherwise match the design,
and that R2 (test-intent) passes because the fence tests fail against the old
`_FENCE_RE`.

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

## Blake

5 findings, listed above as R3, R1, R10, R4, plus an awareness-only note that
`~~🔴 x~~`, fullwidth `＊`, `### 🔴`, `[ ] ` and `<b>` leads are not stripped
(the spec does not list them). He confirms the packet 4 shapes are refused with
the new wording, the packet 5 prose shapes are read, the CommonMark open and
close rules hold, and that his own replay of the baseline files shows exactly
the seven `_ACCEPTED_FLIPS` entries newly flipping, each with an emoji first
after lead normalisation and each carrying a quoting comment, with the four
bold-lead paths absent. He could not run the Phase 0 base-commit check, so that
acceptance criterion is unverified by him.

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
B15: pass
B16: pass
B17: pass
B18: pass
B19: pass

## Bob

After one retry (inlined). Doubt lens, with buckets:

FIX:
- 🟠 `_strip_lead` adds an unauthorized repeated-marker exception: `> > 🔴 crash`
  stops at the second `>` instead of reaching the emoji. Remove `last_mark` and
  its guard; correct the double-dash test and add repeated-blockquote coverage
  to enforce "repeatedly, in any combination." (R3)
- 🟡 The design's pseudo-opener followed by a real closed fence case is untested.
  (R8)
- ⚪ Task 3's required rewrite of the existing changelog entry is missing. (R11)

VERIFY:
- ⚪ The supplied context lacks the required report quoting every departing
  baseline entry's refusal line. (R12 — not queued: command shape)

KNOWN:
- ⚪ `test_gate_findings_shapes.py` exceeds the 800-line limit; its final test
  starts at line 1041. Predates the diff. (R13)

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
R12: pass
R13: fail

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

2 findings, listed above as R9 and R11-adjacent (CHANGELOG line 31, folded into
R1). He ran the four gate test suites and probed `_strip_lead`, `_is_emoji_row`,
`_fence_open` and `_fence_close` directly, including the nested `>> 🔴` case,
and checked all seven `_ACCEPTED_FLIPS` lines against `_is_emoji_row`. He passed
every consensus rule.

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

Verdict: 14 findings
Tests: 6593 passed, 0 failed, 34 skipped (suite run this cycle)
