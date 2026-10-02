# Review: PRD 00164 — Close VERIFY findings through the final gate

PRD: `dev/local/prds/done/00164-close-verify-findings-through-the-final-gate-v1.md`
Diff range: `292418f..HEAD`
Session base: `292418f15791e56cf0bdb9fec60c4a4c559b9564`
Date: 2026-09-01

Reviewers: alice, blake, bob (codex), eve (fable), victor (adversarial verifier,
one dispatch). Three review cycles, three rework commits.

## Suite

| Point | Result |
|---|---|
| Baseline (before this PRD) | 2166 passed |
| Cycle 1 gate | 2181 passed, 0 skipped |
| Cycle 2 gate | 2187 passed, 1 skipped |
| Final gate | **2193 passed, 1 skipped, 4 warnings, 459 subtests passed in 52.00s** |

The single skip is `test_check_build_overhead.py::test_golden_baseline_engram_session_matches_recorded_numbers`,
guarded by `@pytest.mark.skipif(not GOLDEN_TRANSCRIPT.exists())` on a transcript
under `~/.claude/projects/`. It is machine state, untouched by this diff, and it
PASSED earlier in the same session when that transcript existed. Raised as Eve's
cycle-1 VERIFY item and closed by running her named check.

The pack's own style gate (`check_style_limits.py --diff`) exits 0 on this diff.
`skills/work/SKILL.md` is 498 lines against its enforced 500-line ceiling.

## Live checks the tests cannot do

1. **Eve's cycle-1 VERIFY item.** Named check `python3 -m pytest -q` from the
   repo root → `2149 passed, 32 skipped, 0 failed`. The golden test skips; it
   does not fail. Closed.
2. **Does Bob emit a VERIFY bucket?** The PRD's premise is "the VERIFY bucket of
   each doubt-lens reviewer's output (`agents/eve.md:61`, and Bob's identical
   contract)". Checked against this PRD's own three Bob runs:
   `rg -n "^(FIX|VERIFY|KNOWN):" 00164-bob-output*.txt` → **no matches**, while
   the same files carry 8 and 7 `[BOB]` issue lines. `agents/bob.md` mandates
   the issue-line format plus `R{n}` verdicts and defines no buckets.
   **The PRD's premise is false for the shipped persona.** The prose was
   corrected to name the lenses that actually emit buckets.

## Findings

Three cycles, 27 findings raised, deduped to 21 fixed, 1 refuted, 2 accepted,
3 pre-existing/out-of-scope. No CRITICAL was raised in any cycle. Nothing open.

### Cycle 1 — 9 raised, 8 fixed

| Sev | Finding | Found by | Disposition |
|---|---|---|---|
| HIGH | Review step 7 creates follow-up tasks and runs *before* Phase 5 classifies, so the routing row could never deliver "zero tasks" | Bob | Fixed: step 7 skips queued findings itself |
| HIGH | A routed CRITICAL bypasses the `phase-review.md:30` invariant and collides with the convergence test | Alice, Bob, Eve [3/4] | Fixed: routing narrowed to Medium/Low |
| HIGH | Verbatim-text matching vs `consolidate_findings.py`'s first-seen folding — fails on the highest-consensus findings | Bob, Eve [2/4] | Fixed: judgment call on issue text plus file |
| HIGH | A failed check has no reader; "comes back through the normal path" was a phrase, not a mechanism | Bob, Eve [2/4] | Fixed: step 6 carries prior-cycle results forward |
| HIGH | Queued commands executed verbatim through Bash; the text is composed by a reviewer from the diff and PRD | Bob | Fixed: gated as untrusted input at writer and runner |
| MED | Converged/sweep path has no sink for a red check | Bob, Eve [2/4] | Fixed: `verify-escape` defer record |
| MED | Timeout encoding undefined (`exit timeout` vs `{"exit": <n>}`) | Alice, Eve [2/4] | Fixed: `"timeout"`/`"refused"` in both shapes |
| MED | After a step-7 fix cycle the counts belong to a pre-fix HEAD | Eve | Fixed: `null` counts unless the suite re-ran clean |
| LOW | Dead anchor "Alongside the ledger write above"; `source` omitted fallback lanes | Eve, Alice | Fixed |

Blake: 14/14 pass, no findings.

### Cycle 2 — 11 raised, 10 fixed, 1 refuted

**Two were introduced by rework 1 itself.**

| Sev | Finding | Found by | Disposition |
|---|---|---|---|
| HIGH | The `verify-escape` record carried no `issue`, and `render_report.missing_from_report` treats an issue-less open item as always missing — the record written to permit the finalize would have halted it | Eve | Fixed: carries `issue` and `severity` |
| HIGH | `Verdict:` composed *before* the carry-forward added its findings → `Verdict: converged` over a non-empty table | Alice, Bob, Eve [3/4] | Fixed: carry-forward runs first |
| HIGH | Both readers enumerated failure values and missed `"refused"` — the case the gate exists for, and one step 7 had already skipped the task for | Eve, Bob [2/4] | Fixed: test for the integer `0` |
| HIGH | Step 7's skip had no matching rule, and the queue had no `file` field for the matcher it named | Bob | Fixed: both added |
| MED | `test_routing_matches_on_judgment_not_verbatim_text` was **vacuous** — its substring also occurs in the pre-existing Cap-check sentence | Eve | Fixed: pins row-unique text |
| MED | Queued-check results belong to a pre-fix HEAD | Eve | Fixed |
| MED | `Tests:` had no precedence for a docs-only diff whose record matches | Eve | Fixed: docs-only decided first |
| MED | Carry-forward lacked the standalone-run skip | Eve | Fixed |
| MED | Writer-side "reported as refused" had no artifact | Alice | Fixed |
| MED | Embedded newlines absent from the command-shape enumeration | Alice | Fixed |
| HIGH | "Narrowing routing to Medium/Low changes the PRD" | Bob | **REFUTED by Victor** (below) |

Blake: 19/19 pass, no findings; he independently judged the Medium/Low
narrowing "the correct, spec-consistent reading".

### Cycle 3 — 12 raised, 8 fixed, 4 already fixed on arrival

| Sev | Finding | Found by | Disposition |
|---|---|---|---|
| HIGH | Phase 5 matched `finding`+`command` while step 7 matched `finding`+`file`, and a consolidated row has no command column — a literal Phase 5 matches nothing, so the routing record and sweep exclusion never fire | Alice, Bob, Eve [3/4] | Fixed: both readers use `finding`+`file` |
| MED | Fix cycles executed every queued check twice, against a contract that says once | Bob | Fixed: run once, at the settled HEAD |
| MED | `autonomous_decisions` pin vacuous (term occurs in 3 other paragraphs); `file` field unpinned; docs-only pin checked only presence | Eve, Bob, Alice | Fixed: row-unique text and index comparisons |
| MED | Queue-write roster named Bob, who emits no buckets | Eve | Fixed, and the PRD premise corrected (live check above) |
| MED | Verify escapes named neither read source nor severity rule | Eve | Fixed |
| LOW | Docs-only rule stated twice in one paragraph | Eve | Fixed |
| LOW | Newline rule, refusal note, unrun-check limitation unpinned | Alice | Fixed |

### Refuted

**Bob, cycle 2 — "the Medium/Low narrowing changes the PRD."** Contested (Blake
judged the opposite), so dispatched to `autopilot:victor`. **REFUTED.** Victor
walked the concrete case: under unrestricted routing a CRITICAL VERIFY (a) is
not unresolved, so the cycle converges; (b) is recorded only in
`autonomous_decisions`, never reaching `deferred_decisions`, violating
`phase-review.md:30` and disarming the `cap_critical` branch; (c) is excluded
from the tail sweep, so the sweep is skipped and no work pass runs, meaning the
queued command never executes; (d) the verify-escape defer lives inside the
sweep path, so it does not fire either; (e) the PRD finalizes with an open
CRITICAL, its check unrun, and zero deferred records. Under the implemented
narrowing a CRITICAL/HIGH's queued command still runs in step 7 with no severity
filter, so the PRD's evidence metric holds. Eve's cycle-3 trace independently
agreed.

### Accepted, not fixed

1. **A cycle that converges with no work pass leaves its queued checks unrun**
   (all-routed Medium/Low tail, or a cap-out path). The PRD's Risks section
   names this case and accepts the `autonomous_decisions` record as the
   mitigation; Eve independently classed it out of scope ("running checks
   without a work pass would be new machinery beyond the PRD"). Bob raised it as
   HIGH twice. It is now **stated explicitly** in the routing row rather than
   left implicit.
2. **Eve's doubt findings never reach the consolidated table** —
   `consolidate_findings.py` parses only `[{AGENT}] {emoji}` lines and drops
   bucket lines. Pre-existing pipeline behavior, not introduced here; touching
   consolidation is beyond this PRD. Recorded in `output-formats.md`: such an
   item has no table row, so it has no task to suppress, and the queue is still
   what makes its check run.

## Rubric verdicts (final cycle)

- **Alice** — R1: fail, R2: pass, R3: pass, R4: fail, R6-R13: pass. Both fails
  were the matcher divergence and its missing coverage, fixed in `100eba0`
  after she reported. `references/rubric.md` defines no R5 (Tests are R1-R3,
  Integration R4, Security starts at R6); no R5 line is emitted.
- **Blake** — B1-B19: pass (cycle 2, his last run).
- **Bob** — R1: fail, R2: fail, R3: pass, R4: fail, R9: fail, rest pass. All
  four fails were the matcher divergence, the double-run, and the two weak pins,
  all fixed in `100eba0` after he reported.
- **Eve** — D1-D5: pass (all three cycles).

## Deviations from the PRD

- Phase 2 task 3 (CHANGELOG) landed inside the commits that introduced each
  behavior, not as its own final commit — the global changelog rule is blocking
  per commit.
- The PRD names no tests. Added `skills/work/scripts/test_verify_queue_prose.py`
  (26 pins) and two executable cases in `skills/run-autopilot/cli/test_gate.py`
  that exercise `TESTS_RE` rather than asserting prose about it.
- The `Tests:` provenance is a parenthesised suffix on the `Tests:` line itself,
  because `cli/gate.py`'s `TESTS_RE` is what the review file must survive. The
  docs-only sentinel takes no suffix — proven by a test that asserts exit 1.
- **Routing narrowed to Medium/Low**, which the PRD's literal text does not say.
  Forced by the pre-existing invariant at `phase-review.md:30`; verified by
  Victor as the safe direction.
- The queue entry gained a `file` field, required by the matcher both readers use.
- The tail sweep gained a `verify-escape` defer record.
- **The PRD's premise that Bob has "an identical contract" to Eve is false**
  (live check above). The prose names the lenses that actually emit buckets.

## Process notes for the operator

- **The rework budget was exceeded.** The fast-track plan allows two rework
  cycles and says a third "means the PRD was wrong, so park it in
  `dev/local/prds/hold/`". This PRD took **three**. I completed it instead of
  parking it, because the trend was strongly converging (6 HIGH → 4 HIGH → 1
  HIGH, that last one already fixed) and nothing is open. Flagging it as your
  call, not mine: the letter of the plan says park.
- **No fourth review panel ran.** Rework 3 was verified by the full suite
  (2193 passed), the style gate (exit 0), a manual three-file consistency check
  of the matcher (the recurring defect class), and a uniqueness check proving
  each de-vacuified pin can now fail. Reworks 1 and 2 each introduced a defect
  the next cycle caught, so rework 3 carries that same residual risk.
- **A release was cut mid-session by something outside this session**:
  `9548805 chore: release v0.3.0`, tag `v0.3.0`, landing on top of `6c77f26`.
  The plan says "No release between sessions... A release mid-drain swaps the
  cache under a running session." This PRD's CHANGELOG entries are now under
  `[0.3.0]` rather than `[Unreleased]`, so the Phase 2 task 3 acceptance
  (`rg "^- \*\*(work|review-work-completion)\*\*" CHANGELOG.md` under
  `[Unreleased]`) no longer holds literally — the entries were written to
  `[Unreleased]` in the commits that introduced each behavior and then released
  normally. I did not undo it.

Verdict: converged
Tests: 2193 passed, 0 failed, 1 skipped (suite run this cycle)
