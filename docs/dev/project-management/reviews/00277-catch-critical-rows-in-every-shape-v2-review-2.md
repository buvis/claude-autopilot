---
prd: docs/dev/project-management/prds/wip/00277-catch-critical-rows-in-every-shape-v2.md
review: 2
date: 2026-10-15
head_sha: 2963c098cd822e537bc6834461b8ac8ab2bf961b
codex_thread_id: 01a13ca9-18ea-70e1-9282-7722cf711154
agents:
  alice: available
  blake: available
  bob: available
  carl: available
reviewers: alice,blake,bob,carl
dispatch_rows:
  bob: 2d760c05, 29161edc (retry)
  carl: a37c7e21
---

# Review: 00277-catch-critical-rows-in-every-shape-v2

Diff range: `95ff83943d5edbb16391802fc3080d59642f97e6..2963c098cd822e537bc6834461b8ac8ab2bf961b`

codex_rung_guard: not fired

## Review Summary

Reviewed: 7 completed tasks (incremental review of cycle 1's rework)
PRDs checked: 00277-catch-critical-rows-in-every-shape-v2.md

### Agent Status

- Alice: ✅ Available (Claude subagent, consensus lens)
- Blake: ✅ Available (Claude subagent, blind lens, PRD-only)
- Bob: ✅ Available (codex, doubt lens) — after one retry (inlined). The first
  dispatch (resumed thread `01a13c6e-f048-76f0-a42d-adad7638af36`) exited 0 but
  returned a lack-of-input refusal asking for the context and diff to be pasted;
  it had read neither supplied file. The one-retry budget was spent on the
  inlined retry prompt (`docs/dev/tmp/bob-prompt-20261015-0030-retry.md`, 167 KB:
  context and full diff pasted verbatim, no `--resume-thread`), which produced a
  complete review. The first run's output is kept at
  `docs/dev/tmp/bob-output-20261015-0030-firstrun.txt`.
- Carl: ✅ Available (gemini-run, backend copilot)

Degradations this cycle:

- Engram context pack failed: `engram pack exit 1: sqlite3.OperationalError:
  attempt to write a readonly database`. Every prompt carried
  `(no pack available this cycle)`. The review is degraded on findings
  precedent, not invalid.
- No verification-check queue was written: Bob's VERIFY bucket is `(none)` and
  Eve did not run (the codex doubt-roster guard did not fire).

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [1/4] | 🟡 | `_replay_verdict` only replays the 318 files in `gate_replay_baseline.json`. I ran `_unread_token` over every current review file with a Consolidated Findings section. Three of the loop's own newer files are refused with the emoji detail on a `- 🟠`/`- 🟡` lens bullet: 00277-catch-critical-rows-in-every-shape-v2-review-1.md:145, 00278-make-release-checks-tell-truth-v1-review-1.md:118 and 00278-make-release-checks-tell-truth-v1-review-2.md:128. The success criterion says the loop's own format is not among the new flips, and the replay guard cannot confirm that for these files. The old bullet rule refused the same lines, so this is not a flip caused by the new rule. | skills/run-autopilot/cli/fixtures/gate_replay_baseline.json | 3 | BLAKE |
| R2 | [1/4] | ⚪ | The spec names the new symbol `_LEAD_RE`, and it does not exist. The lead is implemented as `_LEAD_MARKS` plus `_ORDINAL_LEAD_RE` plus a character loop in `_strip_lead`. Behaviour matches the spec. | skills/run-autopilot/cli/gate.py:208 | 2 | BLAKE |
| R3 | [1/4] | ⚪ | `test_backtick_in_info_string_is_not_a_fence` and `test_closer_with_trailing_text_does_not_close` live in the new `test_gate_fence_shapes.py`, not in `test_gate_findings_unread_shapes.py` as the spec names. The existing `test_a_closer_with_trailing_text_still_closes_the_fence` was inverted and renamed rather than kept. This is forced by the new rule, but it is a changed pre-existing test against "no test deleted". | skills/run-autopilot/cli/test_gate_fence_shapes.py:32 | 1 | BLAKE |
| R4 | [1/4] | ⚪ | The refusal detail quotes `line.strip()[:120]`. An emoji row whose lead is longer than 120 characters (for example repeated `> ` or many zero-width characters) is cut before the emoji. The detail then says "a severity emoji row" without showing the emoji. The spec requires the detail to contain the matched emoji. | skills/run-autopilot/cli/gate.py:553 | 2 | BLAKE |
| R5 | [1/4] | ⚪ | `_is_emoji_row` runs before the token and pipe arms. A row like `🔴 \| x \| [1/2]` gets the emoji wording, not the `[m/n]` wording. The spec says the `[m/n]` wording "stays for token and pipe rows", so this is an ambiguous reading. | skills/run-autopilot/cli/gate.py:552 | 2 | BLAKE |
| R6 | [1/4] | ⚪ | CHANGELOG line 31 was reworded as asked. A second, overlapping Fixed entry at line 36 repeats the same rule instead of one entry covering the no-bullet shapes, the bold-lead false refusal and the pseudo-fence. `rg 'lead' CHANGELOG.md` hits under `[Unreleased]`, so the acceptance criterion holds. | CHANGELOG.md:36 | 3 | BLAKE |
| R7 | [1/4] | 🟡 | 28 touched test(s) pass against the pre-change code: test_backtick_in_info_string_is_not_a_fence, test_a_pseudo_opener_leaves_only_a_later_real_fence_pair_blanked, test_a_longer_closer_closes_and_a_4_space_closer_does_not, test_a_4_space_opener_does_not_open_a_fence, test_closer_with_trailing_text_does_not_close +22 more | skills/run-autopilot/cli/test_gate_fence_shapes.py | general | mech-check |
| R8 | [1/4] | 🟡 | 72 touched test(s) pass against the pre-change code: test_every_severity_emoji_counts_as_the_first_character_after_the_lead +66 more | skills/run-autopilot/cli/test_gate_findings_unread_shapes.py | general | mech-check |

R7 and R8 are the mechanical fail-first replay findings, absorbed from the
context file's computed block. This is an **incremental** diff
(`95ff839..2963c09`), so its base already carries cycle 1's implementation: the
replayed tests pin behaviour that was already green at that base, which is what
the replay measures. The tautological-shapes block found nothing.

### Auto-dismissed (ledger)

- [BLAKE] 🟡 The rule still refuses wrapped prose. Two real reviews (00269 review-1 line 137 and review-2 line 65) are accepted as flips, though both named lines are the second line of a wrapped prose paragraph that begins with `🔴` or `⚪`. | File: skills/run-autopilot/cli/test_gate_findings_real_fixtures.py:190 — Confirmed in rework cycle 1 (task 7): both 00269 entries ARE false refusals, kept deliberately because nothing in such a line distinguishes it from a real no-lead finding row the PRD requires the gate to catch. Recorded as a known limitation. Do not re-raise.

## Alice

[ALICE] ✅ No issues found. Every cycle-1 finding verified resolved in code:
R1/R11 (CHANGELOG line 31 reworded, CHANGELOG.md:9), R2/R3/R5 (the `last_mark`
repeat guard is gone at gate.py:218; `> > `, `- - `, `• • `, `-- ` and
`> > - **` all strip, with new tests covering all four severity emoji),
R4 (two blank lines at gate.py:272-273, gate.py down to 786 lines, fence tests
split into test_gate_fence_shapes.py and registered in release-checks),
R6/R10 (`_BULLET_LEAD_RE` removed, no readers remain), R7 (settled deferral, now
documented plainly plus the flips report), R8 (new
test_a_pseudo_opener_leaves_only_a_later_real_fence_pair_blanked), R9
(`_LEAD_MARKS` frozenset at gate.py:208), R12 (the flips report quotes the
refusal line for 12 departures and 7 additions). R13 and R14 are settled
deferrals, not re-raised. Regression check: gate suites plus
test_release_checks_counts.py, 550 passed, 93 subtests, 0 failures; the
`_ACCEPTED_FLIPS` replay set is unchanged by the nested-lead fix.

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

## Blake

Findings: the seven `[BLAKE]` lines above (one auto-dismissed by the ledger, six
in the consolidated table). Verified independently: the four named test files
pass (505 passed, 93 subtests); the four bold-lead paths are absent from
`_ACCEPTED_FLIPS`; all 7 `_ACCEPTED_FLIPS` entries quote an emoji-led line; a
backtick opener with a backtick in its info string returns None from
`_fence_open`; a closer with trailing text returns False from `_fence_close`;
`review_close.py:626` goes through `gate.findings_verdict`, so `review-close`
gets the same checks.

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
B15: pass
B16: pass
B17: pass
B18: pass
B19: pass

## Bob

[BOB] ✅ No issues found

FIX:
- (none)

VERIFY:
- (none)

KNOWN:
- (none)

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

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

[CARL] ✅ No issues found (backend copilot). Read the full rework diff, checked
the changed-file line counts, ran the gate suites and
test_release_checks_counts.py.

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

Verdict: 8 findings
Tests: 6687 passed, 0 failed, 34 skipped (reused from last-verification.json at 701f4f7)
