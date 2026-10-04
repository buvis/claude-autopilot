---
prd: docs/dev/project-management/prds/wip/00254-tighten-the-phase-delegation-guard-v1.md
review: 1
date: 2026-10-04
head_sha: 1671d88ef2f0215f035fd6753798bef3f2011cfa
codex_thread_id: 01a108df-b310-72f1-a8c9-706d4ca72429
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00254-tighten-the-phase-delegation-guard-v1

Diff range: `f2e0f66f33b513ffbb7b2238232aa2483c5c0597..1671d88ef2f0215f035fd6753798bef3f2011cfa`

codex_rung_guard: not fired

pack: `docs/dev/tmp/engram-pack-00254-1.md` (1956 tokens)

Verification-check queue: not written. The doubt lens this cycle was Bob (codex);
`agents/bob.md` defines no FIX/VERIFY/KNOWN buckets, and Eve did not run (the
codex doubt-roster guard did not fire). Per `references/output-formats.md`
§ Verification-check queue, `source: "bob"` is reserved, so no entry is queued.
Bob's two "Cannot statically verify" lines named exact commands and both were
run in this session; see Discards below.

## Review Summary

Reviewed: 3 completed tasks
PRDs checked: `00254-tighten-the-phase-delegation-guard-v1.md` (no design doc, `design: skip`)

### Agent Status

- Alice: ✅ Available
- Blake: ✅ Available
- Bob: ✅ Available (codex, exit 0)
- Carl: ✅ Available (gemini via copilot backend, exit 0)

## Consolidated Findings

Produced by `consolidate_findings.py` over four reviewer outputs. The script
merged two rows after citation-suffix stripping; it did not merge three further
pairs that describe the same defect at different line numbers, so the true
agreement is higher than the printed `[n/4]` on three rows — noted per row below.

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [2/4] | 🟡 | The exemption set deviates from the PRD contract. The PRD pins `_READ_ONLY_REVIEWERS` as a frozenset of `autopilot:`-prefixed names, with a plain membership test on `subagent_type`. The diff instead defines `_EXEMPT_REVIEWERS` holding bare names and tests `subagent_type.removeprefix("autopilot:") in _EXEMPT_REVIEWERS`. A bare `alice`, `bob` or `pat` from any other plugin or user agent is now exempt from the guard. Use the literal prefixed frozenset and `tool_input.get("subagent_type") in _READ_ONLY_REVIEWERS`. | hooks/guard_phase_delegation.py:55 | 2 | ALICE, BLAKE |
| [2/4] | 🟡 | `_negated_before` uses `list(finditer)` plus an `if boundaries:` block, not the PRD's pinned `preceding = _SENTENCE_BOUNDARY_RE.split(preceding)[-1]`. The two behave the same, but the PRD form is one line and removes the branch. Use it. | hooks/guard_phase_delegation.py:98 | 1 | ALICE, CARL |
| [1/4] | 🟡 | The reviewer-exemption branch is wider than specified, and no test covers the widening. The `isinstance` plus `removeprefix` branch on one long line is not in the PRD, which pins a plain membership test. Nothing tests that a bare `blake` or a differently namespaced type is still checked. Replacing the branch with the exact-match form from the PRD fixes both. | hooks/guard_phase_delegation.py:115 | 2 | ALICE |
| [1/4] | 🟡 | `test_every_exempt_reviewer_lacks_the_skill_tool` iterates its own copy, `_READ_ONLY_REVIEWER_NAMES`, not the guard module's exemption set. A persona added to or changed in the guard, or a `Skill` grant added to an agent file outside that tuple, cannot fail this test. It also passes against the pre-change code, per the fail-first replay. Derive the names from the guard's frozenset (stripping `autopilot:`) so the safety invariant is bound to the real set. | hooks/test_guard_phase_delegation.py:273 | 2 | ALICE |
| [1/4] | 🟡 | `bash dev/bin/release-checks` exited 1 in my run, so the "exits 0" success criterion is not confirmed. The failure is in the "custody core" stage, a `subprocess` git call (`git -c user.name=t ...`) returning 255. That looks environmental (sandbox or git config) and not related to the guard. The run I watched through the background output file had not finished by the time I stopped reading. Nothing in the hooks stages of release-checks failed. | dev/bin/release-checks | general | BLAKE |
| [1/4] | 🟡 | FIX: `_negated_before` materializes regex matches and branches to select the last boundary; replace lines 97–99 with the behavior-preserving, PRD-specified `preceding = _SENTENCE_BOUNDARY_RE.split(preceding)[-1]`. | hooks/guard_phase_delegation.py:97 | 1 | BOB |
| [1/4] | 🟡 | FIX: Prefix stripping exempts bare identities such as `blake`, beyond the specified `autopilot:blake`; use the exact qualified allowlist while retaining input type validation. | hooks/guard_phase_delegation.py:115 | 2 | BOB |
| [1/4] | 🟡 | FIX: The frontmatter test checks a duplicated reviewer list rather than the production exemption set, so adding an unsafe exemption would leave it green; bind the safety check to the actual exempt identities. | hooks/test_guard_phase_delegation.py:255 | 2 | BOB |
| [1/4] | 🟡 | FIX: Only Blake's exemption is behavior-tested; parameterize the dispatch test across all 13 required identities so removing another reviewer's exemption fails a test. | hooks/test_guard_phase_delegation.py:245 | 2 | BOB |
| [1/4] | 🟡 | FIX: Supplied fail-first replay reports `test_direct_negation_still_allows`, `test_worker_dispatch_is_still_checked`, and `test_every_exempt_reviewer_lacks_the_skill_tool` passing at base; these preserve existing invariants but do not satisfy the rubric's requirement that every added test fail at base. | hooks/test_guard_phase_delegation.py:231 | general | BOB, mech-check |
| [1/4] | 🟡 | Replace removeprefix logic with tool_input.get("subagent_type") in _READ_ONLY_REVIEWERS | hooks/guard_phase_delegation.py:114 | 2 | CARL |
| [1/4] | ⚪ | `test_direct_negation_still_allows` and `test_worker_dispatch_is_still_checked` pass against the pre-change code. That is expected, since both are preservation guards, but neither pins the change itself. | hooks/test_guard_phase_delegation.py:265 | general | ALICE |
| [1/4] | ⚪ | Counting a comma as a boundary now denies prompts like "Do not, under any circumstances, run the work phase". This follows from the PRD, but no test records it. | hooks/guard_phase_delegation.py:51 | 1 | ALICE |
| [1/4] | ⚪ | The `isinstance(subagent_type, str)` guard in place of the spec's bare `.get(...) in frozenset` is a harmless hardening: a non-hashable `subagent_type` would raise `TypeError` under the spec form. No action needed. | hooks/guard_phase_delegation.py:114 | 2 | BLAKE |
| [1/4] | ⚪ | Cannot statically verify: VERIFY by running `python3 -m pytest hooks/test_guard_phase_delegation.py` and confirming exit 0. | N/A | general | BOB |
| [1/4] | ⚪ | Redundant _READ_ONLY_REVIEWER_NAMES duplicates the guard module reviewer persona set | hooks/test_guard_phase_delegation.py:238 | 2 | CARL |

### True agreement after manual merge

Three defects are split across rows because reviewers cited different lines for
the same code. Merged, the consensus is:

- **Exemption set deviates from the PRD contract** (rows 1, 3, 7, 11) — **4/4**:
  Alice, Blake, Bob, Carl. The spec pins a frozenset of `autopilot:`-prefixed
  names with exact membership; the code holds bare names and strips the prefix,
  so a bare `alice`/`bob`/`pat` from any other namespace is exempt.
- **`_negated_before` shape deviates from the pinned one-liner** (rows 2, 6) —
  **3/4**: Alice, Bob, Carl. Behavior-equivalent, confirmed by Blake.
- **`test_every_exempt_reviewer_lacks_the_skill_tool` iterates a duplicated
  list, not the guard's set** (rows 4, 8, 16) — **3/4**: Alice, Bob, Carl.

### Discards

- **Blake's `release-checks` exit 1** (row 5) — **discarded: contradicts a
  measured fact.** Re-run in this session with the inherited nested-dispatch
  env vars stripped (`env -u AUTOPILOT_DISPATCH_DEPTH -u COPILOT_CLI -u
  CODEX_SESSION_ID -u _AUTOPILOT_LOOP bash dev/bin/release-checks`): `PASS 25
  FAIL 0 SKIP 0 EXIT 0`. Carl independently located the cause — the `runner
  recursion guard` stage fails 20 of 26 assertions when `codex-run.sh` refuses
  nested dispatch because the loop session exports those markers. This is a
  property of running the suite inside a loop session, not a regression in this
  diff, and nothing in the diff touches it.
- **Bob's pytest VERIFY line** (row 15) — **answered.** `python3 -m pytest
  hooks/test_guard_phase_delegation.py` reported 91 passed in both Alice's and
  Blake's independent runs, and the file runs inside release-checks, which
  exits 0 above.
- **Bob's release-checks VERIFY line** — **answered** by the clean run above.
- **Blake's `isinstance` hardening note** (row 14) — not a defect; Blake states
  no action needed. Retained in the table as ⚪ for the record.

## Alice

Six findings, listed in the table above. Her own run of
`python3 -m pytest hooks/test_guard_phase_delegation.py` gave 91 passed.

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

Blind lens, PRD only, no diff. Three findings in the table above. He verified
independently: `_SENTENCE_BOUNDARY_RE` is `[.;,\n]`; `_negated_before` honors
the LAST boundary and the docstring says so; all six named tests exist and the
file passes (91 passed); all 13 reviewer persona files declare `tools:` without
`Skill`; worker personas are not exempt and `autopilot:worker-sonnet` is still
denied; hold stubs 00252 and 00253 are gone (deleted by dfa5521). He did not run
the fail-first check himself.

B1: pass
B2: pass
B3: pass
B4: pass
B5: pass
B6: fail
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

Doubt + de-slop lens on codex, static-only sandbox. Seven findings in the table
above; five FIX, two static-verification limits.

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
R13: pass
D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

Gemini via the copilot backend. Three findings in the table above. No frontend
surface in this diff, so he reviewed as a generalist. He also ran
`bash dev/bin/release-checks` twice and isolated the nested-dispatch env-var
cause of the `runner recursion guard` failures, which is what let the discard
above be decided on evidence.

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

- **Function/file sizes** (computed from `ast`): every changed function is well
  under 50 lines (largest: `main` at 26, `is_phase_delegation` at 24). No file
  near the 800-line cap.
- **Tautological test shapes**: 25 test functions checked in 1 test file, no
  `[MECH]` line — no test whose shape cannot fail.
- **Fail-first replay**: 6 touched tests ran against `f2e0f66f33b5`; 3 failed at
  base (the three new True-asserting tests the PRD requires to fail there) and 3
  passed (`test_direct_negation_still_allows`,
  `test_worker_dispatch_is_still_checked`,
  `test_every_exempt_reviewer_lacks_the_skill_tool`). The three that pass are
  preservation guards; the PRD's acceptance criterion names only the first two
  as required to fail at base, and both do.

Verdict: 16 findings
Tests: 25 passed, 0 failed, 0 skipped (suite run this cycle; `bash dev/bin/release-checks` own stage summary `PASS 25 FAIL 0 SKIP 0 EXIT 0`, with the loop session's nested-dispatch env markers stripped)
