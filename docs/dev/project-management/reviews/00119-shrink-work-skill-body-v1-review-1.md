---
prd: dev/local/prds/wip/00119-shrink-work-skill-body-v1.md
review: 1
date: 2026-08-15
head_sha: 16c9bbce7d2ecd97bcbf3e14a8ccdf9fc847f6c5
codex_thread_id: 01a006e9-035b-7623-9538-d9898acd15ce
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00119-shrink-work-skill-body-v1

Diff range: `e39296e60249c49baa624ba5261622f812f34646..16c9bbce7d2ecd97bcbf3e14a8ccdf9fc847f6c5`

codex_rung_guard: not fired

## Review Summary

Reviewed: 4 completed tasks
PRDs checked: 00119-shrink-work-skill-body-v1.md
Cycle: 1 of a rework cap of 2. Full review (no prior cycle).

### Agent Status

- Alice (consensus, Claude subagent): ✅ Available
- Blake (blind lens, PRD-only): ✅ Available
- Bob (doubt + de-slop, codex): ✅ Available
- Carl (UI/generalist, gemini via copilot): ✅ Available
- Eve (Fable doubt lens): ⏸️ Disabled: codex doubt-roster guard did not fire — every `state.tasks[].attempts[].implementor` on this PRD is `claude`, so the doubt leg is not codex-alone and Eve was not added.

Consensus engine: `legacy` (single Alice subagent; no `review-fanout` workflow run, so no `consensus_run_id`).

### Run degradations (recorded, not hidden)

- **Engram context pack unavailable.** `engram pack` exits 1 here with
  "engram pack must run inside a git worktree" — the documented bare-repo-home
  failure. Every prompt received the sanctioned literal `(no pack available this
  cycle)` for `{PACK_FILE}` and `{PACK_FINDINGS}`. Not retried, per the skill.
- **`gather-context.sh` unusable** in this bare-repo home. The diff, PRD, design
  doc, task table, context file and mechanical-facts block were built by hand and
  staged under `/tmp`, per the skill's bare-repo carve-out.
- **Foreign worktree WIP.** `skills/run-autopilot/scripts/test_fablectl.py`
  carries 106+/67− lines of uncommitted, unrelated reformatting belonging to other
  work. The committed state was staged at `/tmp/HEAD-test_fablectl.py` and every
  reviewer was told to judge that, not the live file. No finding in this review is
  about that reformatting.

## Mechanical facts (computed, authoritative)

| Fact | Value |
|------|-------|
| `work/SKILL.md` before this PRD (at `e39296e60`) | **813 lines** |
| `work/SKILL.md` at HEAD | **683 lines** (`wc -l`) / **684** (`validate_skill.py`, which counts `text.count("\n")+1`) |
| Reduction delivered | **130 lines** |
| PRD ceiling | **500 lines** |
| Still over ceiling | **183 lines** |
| PRD's own stated baseline | 737 — **stale**; the design doc's 813 is correct |
| `references/gate-failure.md` | 124 lines (new) |
| `references/adversarial-test-prompt.md` | 94 lines (after +16) |
| `test_fablectl.py` | 1776 lines at HEAD (1815 live, incl. foreign WIP) |

## Consolidated Findings

28 findings consolidated by `consolidate_findings.py` across 4 reviewers. The
size-metric finding was raised by all four but under three different path
spellings (`/Users/bob/.claude/skills/work/SKILL.md`, `.claude/skills/work/SKILL.md`,
`N/A`), so the script's same-file merge rule left it as five separate `[1/4]`
rows. **The decision gate merged those five by hand into one 4/4 finding.** That
merge is recorded here rather than silently applied.

### Full / majority consensus

- **[4/4] 🟠 PRD Success Metric 1 and Exit Criteria unmet, and unreachable within the PRD's own Non-Goals.** `work/SKILL.md` is 683/684 lines against ≤500; the validator still WARNs. Both scoped extractions shipped complete and verbatim. Found by: Alice, Blake, Bob, Carl. → **DEFERRED to batch end** (see Decision gate below).
- **[3/4] 🟠 The design doc's own named mitigation never shipped.** `gate-failure.md` carries no HTML comment and no test pinning the "no `##`/`###` headings below" constraint that the `_section("### 5.5.")` merge depends on. Alice measured the failure mode precisely: a `##` heading inserted *above* the pseudocode block IS caught (2–3 checks fail), but one inserted before `**Attribution row ownership**` is **silent — all 11 checks still pass** while the whole tail vanishes from every section-scoped check's view. Found by: Carl (🟠), Alice (🟡), Bob (🟡).
- **[2/4] 🟠 Devon extraction has no rejection power at all.** `adversarial-test-prompt.md` is not in `TIER_TABLE_FILES` and no fixture patches it, so the moved Procedure can be gutted with every suite green. PRD Phase 1 explicitly set the "same bar" for this task (a spot mutation REJECTED by a retargeted fixture); it is unmet, not merely weak. Found by: Blake, Bob.
- **[2/4] 🟠 Success Metric 4 is only half met.** The 5.5 pointer mandates reading ("Read it before the first gate failure of a batch"); the 2.85 pointer is a bare "See `references/adversarial-test-prompt.md` § Procedure…" with no read-before-dispatch mandate, unlike the `codex-implementor.md` precedent it was supposed to mirror. Found by: Alice, Blake.
- **[2/4] 🟡 Dangling cross-reference** — step-2.85 tier-gate rows still say "dispatch Devon (below)" but nothing about how Devon runs is below any more. Found by: Alice, Blake.
- **[2/4] 🟡 References list only half updated** — `gate-failure.md` was added, but the `adversarial-test-prompt.md` entry still reads "Adversarial validator (Devon) prompt template" with no mention of the § Procedure content moved into it. Found by: Alice, Blake.

### Minority findings that survived the gate

- **[1/4] 🟠 The qwen-breaker gate-PASS reset was moved behind a gate-FAILURE-only pointer.** The rule "gate pass → reset `qwen_gate_failures_consecutive = 0`" now lives only in `gate-failure.md:120`, whose sole pointer says "Read it before the first gate failure of a batch". `rg` confirms SKILL.md has zero gate-pass reset text. So on a qwen task whose tests PASS, `/work` never reads the file and never resets the counter, and two *non-consecutive* qwen failures can trip a breaker documented as consecutive-only (`state-schema.md:182`: "Only a qwen gate PASS resets it to 0 … Owned entirely by `/work`"). Found by: Alice. **This is the most consequential defect in the review** — a behavioural regression the PRD introduced, found by one reviewer, and invisible to the suite because no test pins a gate-pass path.
- **[1/4] 🟠 Pointer integrity is untested.** Deleting the SKILL.md pointer line to `references/gate-failure.md` leaves all 11 contract checks silently clean (Blake's probe: `REJECTED_BY=NOTHING`). The PRD names "autopilot regression from a missed pointer" as a risk; it has zero test mitigation. Found by: Blake.
- **[1/4] 🟡 Destructive-op guard split from its trigger.** SKILL.md steps 2.9/2.95 still say "step 5.5's ESCALATE reset resets to exactly this commit", but the CAS `update-ref` guard, porcelain check, rev-list scoping and fix-forward fallback now live only behind the untested pointer. Found by: Blake.
- **[1/4] 🟡 Reference rot.** `references/attempt-logging.md` still routes readers to "`SKILL.md` step 5.5 ESCALATE point 2 … cleared at point 3"; that prose is no longer in SKILL.md. Found by: Blake.
- **[1/4] 🟡 Phase-0 anchor inventory is stale by construction.** The 77-line block is written in the future tense ("are shrinking", "MOVES to") and cites pre-move line numbers that no longer exist. Found by: Alice, Bob.
- **[1/4] ⚪ `WorkSkillFableContractTest.setUp`** asserts only `WORK_SKILL.exists()` before calling `combined_doc(WORK_SKILL, GATE_FAILURE_REF)`, so a missing reference raises a raw `FileNotFoundError` instead of this file's own "missing tier-table file" message. Found by: Alice.
- **[1/4] ⚪ `combined_doc(primary, extra)`** shipped with a single `extra: Path`, not the design's `*extra: Path`. The simpler signature is the right call, but the design's claim that the mechanism "generalizes to a third file with no further changes" is now false. Found by: Alice.
- **[1/4] ⚪ `_section` semantics widened** from `break`-at-next-heading to a re-entrant union of every occurrence, so a future duplicate heading in either file silently widens a pinned section. Found by: Blake. (Alice measured the single-file case: 0 diffs across all pinned headings on all four files, so the design's "byte-for-byte unaffected" claim holds for today's inputs.)
- **[1/4] ⚪ Fixture drift guard degraded** — `patch()` is first-match-wins across two files, so text duplicated into both mutates only the SKILL.md copy and reports "must reject" instead of "fixture drift … re-anchor it". Found by: Blake.
- **[1/4] ⚪ Citations misdirect** — `combined_doc` reports `primary`'s path with line numbers counted through the concatenation, so a violation inside the reference cites a SKILL.md line beyond the file's length. Accepted in the design; recorded, not actioned. Found by: Blake.
- **[1/4] ⚪ No recorded evidence** of the PRD's stated risk mitigation (one live work-phase smoke), and every task checkbox in the wip PRD is still unchecked. Found by: Blake.

### Discarded at the gate (with reasons — see the ledger)

- ⚪ "Rubric B17 has no counterpart in the spec" — artefact of a fixed 19-rule blind rubric on a two-phase PRD, not a defect in the work.
- ⚪ Bob's "Cannot statically verify the four-suite green run" — his sandbox is static-only by design; the claim was verified at runtime three times over this cycle.
- 🟡 `test_fablectl.py` 1776 > 800-line limit — pre-existing (the file was already ~1626 lines before this PRD); `rules/operating-principles.md` § Surgical Changes says leave it. The discretionary part of the increase is addressed by rework task 5.

## Alice

Ran all four contract suites plus every other suite in both script dirs, and ran
deliberate mutations against the merged doc to test rejection power.

Verification performed (facts, not claims):

- `test_fablectl.py` 48 tests OK; `test_work_routing*.py` + `test_golden_contracts.py` 148 passed; full `work/scripts` 268 passed; full `run-autopilot/scripts` 696 passed, 31 skipped (all pre-existing `tracon/test_screens.py` textual-dependency skips, unrelated).
- Verbatim relocation confirmed programmatically: of 114 non-blank lines removed from `SKILL.md`, 113 appear byte-identical in a reference file; the 1 exception is the replaced pointer sentence.
- Design claim 2 confirmed: every one of the 17 fixture anchor strings resolves to exactly one file, exactly once — no fixture body needed editing, and the `patch()` `self.fail("fixture drift…")` fallthrough still fires.
- `_section` change measured, not assumed: old-vs-new section extraction is identical on all four files single-file (0 diffs across all pinned headings), and differs only on the combined doc (`### 5.5.`: 30 rows → 149).
- Merge is load-bearing: emptying `gate-failure.md` makes 3 checks fail; re-attaching "no rung above" to opus in the moved copy is caught.
- Design claim 1 (the footgun): no guard shipped, and the footgun is real but narrower than the design feared — a `##` above the pseudocode block is caught loudly; one before `**Attribution row ownership**` is silent.

Findings: 2 🟠, 4 🟡, 4 ⚪ (listed above).

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
R12: pass
R13: fail

## Blake

Blind lens — PRD only, no diff, no file list, no design doc. Found the code himself.

Verified positively:

- Relocation is byte-for-byte verbatim: the 118 removed SKILL.md lines equal `gate-failure.md` lines 7–124 exactly; the Devon block equals the new § Procedure exactly.
- All four named suites green as run by him: `test_fablectl.py` 48 passed / 101 subtests; the other three 148 passed. Full `skills/work/scripts/` run: 268 passed.
- **Rejection power over the moved gate-failure prose survives.** Five independent out-of-band mutations were each rejected by the expected check: no-rung-above reattributed to opus → `no rung above`; fable granted a feedback retry → `retry/repair fable exclusion`; budget folded into the Claude rungs → `per-rung budget`; `opus → fable` edge added → `auto-escalation`; reference emptied → three checks fire.
- Phase 0's anchor table is accurate: pre-move line numbers re-derived against the pre-move blob and they match; all 11 checks and 12 fixtures still exist, none deleted.
- B9/B10/B11/B13/B14 pass vacuously — this PRD specifies no auth, no rate limiting, no migrations, and touches no runtime data path.

Findings: 2 🔴, 3 🟠, 4 🟡, 5 ⚪ (listed above). His two 🔴s were both the size metric; the gate recorded that finding HIGH and his dissent verbatim — see Decision gate.

B1: fail
B2: pass
B3: pass
B4: fail
B5: pass
B6: pass
B7: pass
B8: pass
B9: pass
B10: pass
B11: pass
B12: fail
B13: pass
B14: pass
B15: fail
B16: pass
B17: fail
B18: pass
B19: pass

## Bob

Doubt + de-slop lens, codex, static-only sandbox. Findings: 2 🟠, 2 🟡, 1 ⚪.

FIX:
- Devon Procedure has no mutation-rejection contract — `test_fablectl.py:657` — add a targeted contract check for the moved Procedure and read-first pointer, plus an exploit fixture that mutates its operational content and asserts rejection
- Secondary headings can silently truncate gate-failure checks — `gate-failure.md:1` — add the documented warning and a regression test rejecting any later `##`/`###` heading
- Phase-0 inventory bloats executable test code — `test_fablectl.py:646` — move the table to a checked-in reference and leave a short source link

VERIFY:
- Recorded runtime validation is not statically verifiable — rerun the four named Python test scripts and the toy work-phase smoke, confirming both extracted references are read at their trigger points

KNOWN:
- SKILL.md remains 683 lines against the ≤500 exit criterion — further extraction would violate this PRD's explicit Non-Goals, so the operator must amend/re-baseline the PRD or authorize additional scope

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

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

Gemini via the copilot backend. This diff has no frontend surface (three markdown
files, one Python test file), so Carl reviewed as a generalist, as his persona
directs. Findings: 1 🟠, 1 🟡, 1 ⚪.

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
R12: pass
R13: fail

## Decision gate (Phase 5)

**Outcome: NOT converged.** Unresolved HIGH findings remain, so the cycle fails
the convergence test. `state.cycle` (1) < `state.rework_cap` (2), so the cap is
not reached and rework is dispatched — no cap-pause, no stall.

**Deferred to batch end (1 finding):** the [4/4] unmet ≤500 size metric.
Classified under `decision-framework.md` → "Requirements ambiguity (PRD says X,
code does Y)". Autopilot cannot resolve it: closing the remaining 183 lines needs
a third extraction the PRD's Non-Goals forbid, and amending the metric is an
operator call. Recorded in `dev/local/autopilot/deferred/202607202320-deferred.json`,
in this PRD's ledger, and in `state.deferred_decisions`.

**Severity call, recorded deliberately.** Blake rated the size metric CRITICAL
(twice); Alice and Bob rated it HIGH; Carl MEDIUM. The gate recorded **HIGH**.
Reasons: nothing is broken or unsafe (the framework's CRITICAL examples are
security, data loss, broken functionality); both scoped extractions shipped
complete and verbatim with rejection power independently re-verified by two
reviewers running live mutation probes; and the ceiling was unreachable from the
PRD's own numbers before any code was written. Blake could not see that baseline
history — his prompt is PRD-only by construction. This call has a real
consequence and is not cosmetic: a CRITICAL is never a settled deferral, so
leaving it CRITICAL would stall this PRD to `hold/` at the cycle-2 cap despite all
its scoped work being finished and verified. Blake's dissent is preserved verbatim
in the deferred record and the ledger.

**Auto-fixed in cycle-1 rework (6 tasks).** All remaining findings are additive or
mechanical: no signature, schema, or public-interface changes. No blocking
escalation, so no stall. No research protocol triggered (no new dependency, no
recurring issue, no data-model or public-API change).

Scope alarm not triggered: 6 follow-up tasks, under the limit of 10.

Verdict: 28 findings
Tests: 196 passed, 0 failed, 0 skipped

Tests note: the four contract suites (`test_fablectl.py`, `test_work_routing.py`,
`test_work_routing_ladder_fence.py`, `test_golden_contracts.py`) run together;
101 unittest subtests also passed. Run against the live work-tree, which carries
the foreign uncommitted reformatting of `test_fablectl.py` described above.
Alice and Blake independently ran the same suites and got matching counts.
