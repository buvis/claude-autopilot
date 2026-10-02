# Review: PRD 00165 — make reviewer re-runs delta-aware

Session 2 of the 00159-00168 fast-track drain. Diff range
`c4c303484f803ed1f50b80c365990c96f0cc28fb..HEAD`. Converged after **1 rework
cycle**: no CRITICAL and no HIGH left open.

## Panel

Four lenses, four fresh contexts, three vendors. All four ran; none degraded.

| Lens | Agent | Model | Verdict |
|------|-------|-------|---------|
| Consensus, implementation-aware | Alice | Sonnet | 1 finding + 1 minor; rubric R1-R13 all pass |
| Blind, PRD only | Blake | Sonnet | 0 findings; 22 derived rules B1-B22 all pass |
| Doubt + de-slop | Eve | Fable | 8 FIX, 2 VERIFY, 3 KNOWN; D1-D5 all pass |
| Rubric + doubt, different vendor | Bob | codex | 4 findings; R1/R2/R4/R9/R10 fail, rest pass |

Bob's rework pass resumed his own thread (`--resume-thread`) rather than
re-reading the diff — the same mechanism this PRD gives Pat.

## Findings

Deduped: Bob #1, Alice's finding and Eve FIX 1/2 are one defect; Bob #3 and Eve
FIX 4 are one; Bob #2 and part of Eve FIX 5 are one.

| # | Sev | Finding | Raised by | Status |
|---|-----|---------|-----------|--------|
| 1 | HIGH | `-S`/`-R` case arms duplicated verbatim in `sonnet-run.sh` (second copy unreachable), and `SESSION_ARGS`/`RESUME_PRINT_ID` never declared | Bob, Alice, Eve | applied `3dc5bb5` |
| 2 | HIGH | Re-run template lets an unresolved prior finding vanish: "don't re-report the earlier range" + "NO FINDINGS when the delta has none" yields a parseable `NO FINDINGS` with a HIGH still open | Eve | applied `3dc5bb5` |
| 3 | HIGH | Correction retry (exit 1) had no session mode; the `-S` it would inherit collides with an id `claude` already created | Eve, Bob | applied `3dc5bb5` |
| 4 | MEDIUM | Post-fallback state undefined — dead `<pat_session_id>` still drove later cycles, and a task with no id would dispatch `-R ""` | Eve, Bob | applied `3dc5bb5` |
| 5 | MEDIUM | `attempt-logging.md` schema said "alternative value", prose said "appended" | Eve | applied `3dc5bb5` |
| 6 | MEDIUM | SKILL.md called § Delta re-runs the session id's "one reader"; § Dispatch's `-S` reads it too, so a literal reader could skip `-S` and kill every resume | Eve | applied `3dc5bb5` |
| 7 | MEDIUM | New pins asserted token presence only | Bob | applied `3dc5bb5`, completed `b0857f0` |
| 8 | LOW | Template restated the persona's read-only rule that `-t ""` already enforces | Eve | applied `3dc5bb5` |
| 9 | LOW | Empty delta diff exits `render_prompt.py` 4 (`--set-cmd` with no output) | self, during build | applied `3dc5bb5` |

Nothing was declined and nothing deferred.

## The live checks the tests cannot make

The drain plan mandates exercising the real CLI whenever a PRD changes what
reaches one — the PRD 00159 lesson, where a green suite and four reviewers
passed over a dead flag because the only test asserted on a stubbed binary's
argv. Run against the real `claude`, 2026-08-28:

| Check | Result |
|-------|--------|
| `-S <uuid>` then `-R <same uuid>` | first printed `OK`, second printed `4271` — the resumed run answered from the first run's context, exit 0 both |
| `-R <unknown uuid>` | exit 1, `No conversation found with session ID: ...` — the trigger § Resume failure keys on |
| `-S <uuid>` twice with the same id | exit 1, `Error: Session ID <id> is already in use.` |

The third is what turned finding 3 from an argument into a fact: Eve raised it
as "hinges on whether claude rejects a reused id, downgrade to a doc nit if it
does not". It does not.

Blake separately re-ran `test_sonnet_run.sh` under macOS system bash 3.2.57 as
well as bash 5.3 (23/23 both), closing the array-declaration portability
question the same finding raised.

## What the panel could not check

- The multi-cycle delta flow is executed by the orchestrating model at runtime.
  This repo has no seam to drive a live per-task review, so the flow is bound by
  prose pins in `test_dispatch_prose.py`, not by an integration test. Eve and
  Bob both said so; it is accepted, not fixed.
- A resumed reviewer can trust a stale memory of unchanged code whose meaning a
  later fix quietly changed. The PRD lists this as an accepted risk; the
  PRD-level lenses re-review the whole change every cycle as the backstop.
- Per project memory, an autopilot batch here runs the marketplace cache, so
  none of this takes effect until `dev/bin/release` plus `/plugin update`.

## Suite

| Point | Result |
|-------|--------|
| Session baseline (after S1) | 2111 passed |
| After build, before review | 2115 passed, 4 warnings, 459 subtests, 55.93s |
| After rework | 2118 passed, 4 warnings, 459 subtests, 55.70s |
| `test_sonnet_run.sh` (not collected by pytest; `dev/bin/release-checks:22`) | 23 passed, 0 failed |

Zero failures, zero skips at every point.

## Deviations from the PRD

- CHANGELOG entries landed per-commit (`**use-sonnet**` Added in `6a5bcf4`,
  `**work**` Changed in `1a12929`) rather than all in the Phase 2 task, per the
  drain plan's rule that the entry ships with the commit introducing the
  behavior.
- `-R` is rejected with `-c`/`-i` as well as the PRD-specified `-r`. All three
  drop `--print`, so it is one condition either way.
- The re-run section is named `## Delta re-runs`; the PRD named only
  `## Resume failure` explicitly.
- The correction retry resumes with `-R` (PRD did not specify its session mode;
  the live check above forced the choice).

## Note for whoever writes the next PRD in this drain

Finding 1 was mine, and it was caused by the workflow rather than the design: a
fact-forcing gate blocked one edit of a three-edit parallel batch, and the retry
re-applied an edit that had already succeeded. Two of the three reviewers who
found it found it by reading the file directly rather than the diff. When a gate
blocks one call in a parallel batch, re-read the file before retrying — the diff
of a partially-applied batch looks exactly like the diff of a correct one.
