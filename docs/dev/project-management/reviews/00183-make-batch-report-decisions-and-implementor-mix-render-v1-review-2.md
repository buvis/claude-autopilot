---
prd: dev/local/prds/wip/00183-make-batch-report-decisions-and-implementor-mix-render-v1.md
review: 2
date: 2026-09-07
head_sha: 72481d2be19bc7f3fa901ded29afca2ea04a8062
codex_thread_id: 01a07a92-48e9-73f1-9afc-2647a705c50a
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00183-make-batch-report-decisions-and-implementor-mix-render-v1

Diff range: `91c1ab32f9cc4e5dc6f66564c02980a56d989c28..72481d2be19bc7f3fa901ded29afca2ea04a8062`

codex_rung_guard: not fired

pack: unavailable (`engram pack` exited 1 — "not inside a registered repo; register it in /Users/bob/.config/gita/repos.csv"). Same deterministic configuration failure as cycle 1, not retried. Control-checked this cycle: `repos.csv` holds 26 lines, 18 match `buvis`, 0 match `claude-autopilot`, so the cause is confirmed rather than assumed. The review is degraded on retrieval context, not invalid. Blake never receives a pack by design.

## Review Summary

Reviewed: 12 completed tasks (cycle 2 scopes the 5 `[D1]` rework tasks, 8-12)
PRDs checked: 00183-make-batch-report-decisions-and-implementor-mix-render-v1

Cycle 2, **incremental review** of the rework since cycle 1's head `91c1ab3`.
8 commits, 10 files, 1372 insertions / 715 deletions. Bob resumed his cycle-1
codex thread rather than re-reviewing from zero.

### Agent Status

- Alice: ✅ Available (consensus lens, `legacy` engine)
- Blake: ✅ Available (blind lens, PRD-only)
- Bob: ✅ Available (doubt + de-slop lens, codex — thread `01a07a92-48e9-73f1-9afc-2647a705c50a` resumed from cycle 1)
- Carl: ✅ Available (backend `copilot`, model `gemini-3.8-flash`)
- Eve: ⏸️ Disabled — the codex doubt-roster guard did not fire (0 codex-implemented tasks; all 12 attempts across 12 tasks carry `implementor: claude`)

### Cycle notes (fail-loud)

1. **The mechanical blocks were staged in a sibling file, not appended to the
   context file.** `aegis/hooks/block_devlocal_redirects.py` blocks a shell
   append into `dev/local/`, so the three computed blocks live in
   `dev/local/tmp/review-mechchecks-00183-c2.md` and every implementation-aware
   reviewer was given both paths. This is an improvement on cycle 1, where the
   block was staged in `/tmp` and Carl's sandbox refused to read it: this cycle
   Carl read the sibling file successfully (it is inside the repo).
2. **The fail-first replay block was wrong again, in the same way, and this is
   again the cycle's most important methodological finding.** It reported 59 of
   67 touched tests as passing against the pre-change code. All six `[MECH]`
   rows are discarded in the ledger with measurements. The orchestrator built a
   base worktree at `91c1ab3`, overlaid HEAD's test files, and replayed;
   **Alice independently did the same in her own worktree and reached identical
   results.** Two distinct causes: `replay_tests_against_base.py` credits a
   pytest `subTest` parent node as passed (the known defect, already deferred),
   and this cycle's base is the END of cycle 1, so task 11 (tests-only
   strengthening) and task 12 (a pure file move) produce tests that pass at
   base *by construction*.
3. **Every one of cycle 1's 12 routed findings was verified closed by direct
   measurement, not by reading the diff.** Measured refutations against base:
   task 8's 3 duplicate-append discriminators FAIL at base; task 9's 3 alias
   discriminators FAIL at base; task 10's 4 discriminators FAIL at base. Two
   mutation tests: deleting the ledger argument at `cli/__main__.py:787` makes
   the new CLI test FAIL, and the combined filter+dedup mutation that DEFEATED
   the cycle-1 fixture now makes it FAIL (3 failed, 13 passed).
4. **Task 12's own acceptance criterion carried a stale number.** It says the
   split must preserve "the 109 currently in `test_schema.py`". The real
   pre-split count was 119, because tasks 8 and 11 added tests to that file
   after the criterion was written. Measured: 119 `def test_` at `ea3eee0`
   (1608 lines), 119 after the split (73 + 26 + 20), no name changed. The
   intent — no test lost, every file at or under 800 — is satisfied exactly.
   This was already recorded as an autonomous decision at build time.
5. **No verification-check queue was written.** Eve did not run, and
   `references/output-formats.md` reserves `source: "bob"`, so Bob's VERIFY
   bucket produces no queue entries. His single VERIFY item was executed by the
   orchestrator instead: `pytest -q -rs skills/run-autopilot/cli/test_render_attempt_ledger.py`
   gives **16 passed, 0 skipped**, so both regular-file permission tests
   execute rather than skipping. Resolved.
6. **One orchestrator self-correction, recorded.** The first probe of PRD
   success metric 2 ran the INSTALLED plugin cache
   (`~/.claude/plugins/cache/.../0.5.1/skills/run-autopilot/scripts/statectl.py`),
   which predates this PRD, and returned exit 0 — proving nothing about the
   work under review. Re-run against the repo's own script it exits 1 with
   exactly `rejected: autonomous_decisions entry missing issue`, leaving the
   state file byte-identical (md5 `b37ef078...` unchanged before and after).
   Metric 2 holds.
7. **Alice and Bob disagree about one finding, and the disagreement is
   recorded rather than resolved silently.** Alice inspected the `_ledger_rows`
   double read and judged it "a defensible, minimal fix given the constraint,
   not a defect"; Bob raised it as a Medium. Both positions are in the table
   below; the decision gate routes it.

## Consolidated Findings

15 findings: 9 from the reviewers, plus 6 `[MECH]` replay rows absorbed from the
mechanical test-check blocks. **All 6 `[MECH]` rows are discarded** with measured
reasons (cycle note 2). **No unresolved Critical or High.**

| Consensus | Severity | Issue | File | Found By |
|-----------|----------|-------|------|----------|
| [1/4] | 🟡 Medium | At line 269, occurrence matching conflates Python-equal values of different JSON types. With an existing valid `cycle: 1` entry, appending its `cycle: True` counterpart consumes that occurrence and the invalid boolean is accepted, although `_validate_decision_entry` rejects bool cycles outright. **Orchestrator-confirmed by reproduction.** | skills/run-autopilot/cli/schema.py | Bob |
| [1/4] | 🟡 Medium | At line 450, `_ledger_rows` reads the whole file via `read_bytes()` purely as a readability probe, then `load_rows` opens and reads it again; an `OSError` on that second read is still swallowed with no warning. **Confirmed in code.** Alice inspected the same lines and judged it a defensible minimal fix rather than a defect — see cycle note 7. | skills/run-autopilot/cli/render_report.py | Bob |
| [1/4] | 🟡 Medium | At lines 343 and 378 the two permission tests duplicate setup, permission probe, cleanup and assertions. Extract a shared helper while keeping both named tests and both modes. | skills/run-autopilot/cli/test_render_attempt_ledger.py | Bob |
| [1/4] | 🟡 Medium | At line 240 the alias test nests five blocks deep (`for` / `for` / `for` / `with subTest` / `for`), past the project's 4-level limit. **Confirmed**, and `check_style_limits.py` gates only function length (50) and file length (800), so nothing automated catches it. | skills/run-autopilot/cli/test_render_autonomous_blank_rows.py | Bob |
| [1/4] | 🟡 Medium | At line 118 the new `assertEqual(count(anchor), 1)` already guarantees `find(anchor)` cannot return -1, so the following `assertNotEqual(start, -1)` is redundant. **Confirmed.** | skills/run-autopilot/scripts/test_review_prompt_contracts.py | Bob |
| [1/4] | 🟡 Medium | Phase 2 task 2's literal acceptance check `rg -n 'implementor mix' CHANGELOG.md` returns zero matches because ripgrep is case-sensitive; the file carries "Implementor Mix". **Confirmed:** the literal command exits 1, the case-insensitive control returns 3 hits. The substance — a `### Fixed` entry under `[Unreleased]` — is present and correct; only the PRD's literal grep fails. | CHANGELOG.md | Blake |
| [1/4] | 🟡 Medium | At line 120, `assertIs(row[CYCLE], cycle)` imposes object identity where the report contract asks only for value equality. **Judged weak by the gate:** the cell returns `d.get("cycle")`, the very object passed in, so `assertIs` holds by construction and can never false-fail; it is strictly stronger than `assertEqual` and matches the test's own stated intent. Recorded, not actioned. | skills/run-autopilot/cli/test_render_autonomous_blank_rows.py | Bob |
| [1/4] | ⚪ Low | Phase 1 task 1 names `test_complete_prd_count_matches_rendered_rows`; no test with that literal name exists. Equivalent coverage exists as `test_persisted_autonomous_count_matches_rendered_autonomous_data_rows` and its escalated sibling, and both pass. Already recorded as an autonomous decision at build time and raised again in cycle 1. | skills/run-autopilot/scripts/test_statectl_complete_prd.py | Blake |
| [1/4] | ⚪ Low | Cannot statically verify that the cycle-2 suites and release checks pass with the permission tests executing rather than skipping (codex sandbox). Answered by the recorded verification and by the orchestrator's `-rs` run: 16 passed, 0 skipped. | N/A | Bob |
| [1/4] | 🟡 Medium | `[MECH]` 5 touched tests pass against pre-change code | skills/run-autopilot/cli/test_render_attempt_ledger.py | mech-check |
| [1/4] | 🟡 Medium | `[MECH]` 8 touched tests pass against pre-change code | skills/run-autopilot/cli/test_render_autonomous_blank_rows.py | mech-check |
| [1/4] | 🟡 Medium | `[MECH]` 1 touched test passes against pre-change code | skills/run-autopilot/cli/test_render_cli.py | mech-check |
| [1/4] | 🟡 Medium | `[MECH]` 26 touched tests pass against pre-change code | skills/run-autopilot/cli/test_schema_decision_entries.py | mech-check |
| [1/4] | 🟡 Medium | `[MECH]` 18 touched tests pass against pre-change code | skills/run-autopilot/cli/test_schema_decision_scope.py | mech-check |
| [1/4] | 🟡 Medium | `[MECH]` 1 touched test passes against pre-change code | skills/run-autopilot/scripts/test_review_prompt_contracts.py | mech-check |

### Discarded this cycle (all six `[MECH]` replay rows)

Each is recorded in `dev/local/reviews/00183-...-ledger.json` with its measurement.
Two causes, both established by direct replay in a base worktree at `91c1ab3`:

- **subTest defect** — `test_render_autonomous_blank_rows.py` and
  `test_schema_decision_scope.py`: the named tests FAIL at base; the tool credits
  a `subTest` parent node as passed. Alice reproduced this independently.
- **Correct by construction** — `test_schema_decision_entries.py` and
  `test_schema_decision_scope.py` are task 12's pure relocation;
  `test_render_cli.py`, `test_review_prompt_contracts.py` and most of
  `test_render_attempt_ledger.py` are task 11's tests-only strengthening against
  production code already correct at base. The cycle-2 base is the END of cycle 1,
  so tests-only work must pass there.

### Deferred to batch end

| Consensus | Severity | Issue | Reason |
|-----------|----------|-------|--------|
| [1/4] | 🟠 High | `cli/statectl.py` defines `main()` but never calls it: `python3 -m cli.statectl <state> append autonomous_decisions '{"cycle": 1}'` exits 0 with empty output and leaves the state byte-unchanged — a fail-open that looks like success | **Enriches** the cycle-1 deferral of this file rather than restating it. Consolidation auto-dismissed Blake's finding against that entry, but the cycle-1 reason rested on the failure being LOUD ("exits 1 with ImportError"), and Blake surfaced a second invocation form that fails SILENTLY — a materially worse fact the settled reason did not cover. Reproduced: no `__main__` guard (only `def main()` at line 625); `-m cli.statectl` on a clean state exits 0, md5 unchanged. Still deferred, not fixed here: it predates this PRD (created without the guard in `3f4ef75`, outside this diff), no product path invokes `-m cli.statectl` (every skill doc uses the `scripts/` shim, which is correct and was re-verified this cycle), and Surgical Changes forbids repairing unrelated pre-existing code inside this PRD. The batch-end item is upgraded from "PRD wording correction" to "PRD wording correction PLUS close the fail-open". |

### Auto-dismissed (ledger)

- [BLAKE] 🟠 The PRD's literal Success-Metric/Phase-0 acceptance command `python3 skills/run-autopilot/cli/statectl.py <state> append autonomous_decisions '{"cycle": 1}'` does not produce the specified `rejected: autonomous_decisions entry missing issue` / exit 1. Run as a bare script it crashes with ImportError. Run as `python3 -m cli.statectl`, it silently does nothing: exit 0, empty stdout/stderr, state file byte-unchanged, because cli/statectl.py defines main() but never calls it. | File: skills/run-autopilot/cli/statectl.py — matched the cycle-1 settled deferral: "Requirements ambiguity, not an implementation defect... Adding a __main__ guard to a library module to satisfy a PRD typo would be fixing the test. Deferred to batch end for a PRD-wording correction."

**Gate judgment on this dismissal: partially wrong, and corrected above.** The
match is right on the PRD-wording half and the decision is unchanged (do not fix
it inside this PRD). But Blake, who is blind and never sees the ledger, surfaced a
NEW fact the settled reason did not account for — a silent fail-open rather than a
loud ImportError. Rather than let the dismissal swallow it, the batch-end deferral
is enriched with the reproduction and upgraded in scope. This is why the section
is copied here rather than dropped.

## Alice

Consensus lens, implementation-aware, `legacy` engine. **No issues found.**
Verified all 12 routed cycle-1 findings closed, one by one. Independently
distrusted the supplied replay block and built her own detached worktree at
`91c1ab3` to replay the touched tests against base, reaching the same conclusion
the orchestrator reached separately: the rows are subTest false positives, and
tasks 8, 9 and 10 are genuinely pinned. Ran the full suite (2728 passed, 32
skipped, 664 subtests, none of the 32 skips in the 7 touched files, confirmed with
`-rs`), `bash dev/bin/release-checks` (exit 0), and `git diff --exit-code` on the
golden (exit 0). Cleaned up her worktree. She also inspected the `_ledger_rows`
double read and explicitly judged it defensible rather than a defect.

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

Blind lens, PRD-only, no diff and no file list. Located the implementation himself
and ran the PRD's literal acceptance commands by hand. Three findings, and he is
the only reviewer who found the `cli/statectl.py` fail-open — a genuine catch that
the ledger then auto-dismissed and the gate has re-surfaced as an enriched
deferral. His B1/B5/B16 fails all trace to that finding and to the case-sensitive
CHANGELOG grep; the substance behind both is present and correct. He marked B17
pass as vacuous, correctly: this PRD has no Phase 3.

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
B16: fail
B17: pass
B18: pass
B19: pass

## Bob

Doubt + de-slop lens (codex, static-only sandbox), resumed from his cycle-1 thread
so he verified fixes against his own prior critique. Six Medium findings and one
Low, no Critical or High. Two reproduce under direct measurement — the `cycle: True`
occurrence hole and the swallowed second read — and two more (5-level nesting, the
redundant anchor assertion) are confirmed by reading. His `assertIs` finding is the
one the gate judged weak. His single VERIFY item was executed: 16 passed, 0 skipped.

FIX: 6 items. VERIFY: 1 item (executed, clean). KNOWN: 0 items.

R1: fail
R2: fail
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

Backend `copilot`, model `gemini-3.8-flash`. **No issues found.** Read all three
staged inputs including the sibling mechanical-checks file — the staging fix that
cycle 1's `/tmp` placement defeated. Ran the full suite and `dev/bin/release-checks`
himself (including a re-run with the recursion-guard env vars unset), checked the
golden with `git diff`, and ran `check_style_limits.py` directly against the three
schema test files and against the diff.

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

## Mechanical checks (computed)

- **Tautological test shapes:** clean. 186 test functions across 7 changed test
  files; no constant, self-comparing, hedged, exception-swallowing or
  assertion-free test found.
- **Fail-first replay:** 6 `[MECH]` rows, **all discarded** — see cycle note 2 and
  the ledger. 67 touched tests ran, 8 reported failing at base; direct replay shows
  the true figure is higher, because the tool miscounts `subTest` failures.
- **Mechanical facts:** full `ast` table inlined in
  `dev/local/tmp/review-mechchecks-00183-c2.md`. Countable claims citing it:
  `_implementor_mix` 45 lines, `_ledger_rows` 24, `prd_section` 42,
  `_validate_added_decision_entries` 21, `_first_text` 9 — all under the 50-line
  limit. File sizes 752 / 516 / 392 / 602 / 333 / 439 / 444 / 313, all at or under
  800.

Verdict: 15 findings
Tests: 2728 passed, 0 failed, 32 skipped (reused from last-verification.json at 72481d2be19bc7f3fa901ded29afca2ea04a8062)
