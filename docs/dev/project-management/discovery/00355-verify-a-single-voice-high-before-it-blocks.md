# Discovery: Verify a single-voice HIGH before it blocks

## Classification
Depth: comprehensive | Date: 2026-10-18 | Status: pre-elicitation (written from the monitoring findings of two batches, no questions asked yet)

## Problem
The full lane's review cycle treats a HIGH raised by one reviewer alone as
blocking. Measured on batch 202610161547: both second cycles of the first two
PRDs were forced by a `[1/4]` HIGH (00320 R5 by Carl; 00321 R3/R4, the same
case-insensitive-SHA claim twice, on input git never produces), each costing
a sonnet rework session plus an opus re-review, about 70 min and $40; six of
the eight HIGHs that survived to a cap-out or a hold stub were `[1/4]`; three
of seven full-lane PRDs capped out at two cycles. Across the batch, 85% of
consolidated rows were single-voice (20 of 22 on 00312, 19 of 23 on 00320).
PRD 00333 (done) discards single-voice Medium and Low rows; it leaves HIGHs
untouched on purpose, because a real HIGH can be single-voice (00322 R4) and
the convergence test depends on them.

The fast-track lane already solves this: every CRITICAL and HIGH goes to
Victor, who tries to refute it, and only a shown broken path confirms. On the
same batch every HIGH Victor or a direct run confirmed was real (00323 two,
00332 four, 00334 two, 00342 two) and each cost one in-session rework, not a
second cycle. The full lane has a verification engine too (`consensus_engine:
workflow`, the review-fanout workflow), but it cannot load under the loop:
the Workflow tool refuses a `scriptPath` under `~/.claude/workflows` in a
headless session, so `shadow` and `workflow` both fall back to a plain Alice
agent. Gate 4 of the public-release bar is a convergence target; this is the
lever with measured cost behind it.

## Requirements (candidate, to be elicited)

### Must have
- F1: in the full lane's decision gate, every 🔴 or 🟠 row with one voice
  (`[1/N]`) is handed to `autopilot:victor` with the row, the diff and the
  cited file before it can block; a refuted row is recorded in the ledger as
  `refuted:<reason>` and drops to the sweep, a confirmed row blocks as today.
- F2: the review file's per-row ledger shows the verification outcome, so
  the batch report can count confirmed against refuted single-voice HIGHs.
- F3: multi-voice HIGHs are unchanged; every lens still runs every cycle
  (the user's standing rule).

### Nice to have
- The same Victor pass on the workflow engine's rows once that engine loads
  under the loop (`--add-dir ~/.claude/workflows` in the runner, or the
  script passed inline), so `shadow` can compare the two engines.

### Out of scope
- Discounting HIGH severity, or lowering the rework cap.

## Constraints
- Victor is read-and-run: he needs the repo at the reviewed HEAD and the test
  command; one dispatch per row, bounded by the roster's wait rule (PRD
  00332's one-call wait).
- A verification that cannot run (sandbox, missing tool) confirms by default:
  "uncertainty refutes" applies only to a finding Victor could probe.

## Codebase Context
- `skills/review-work-completion/scripts/consolidate_findings.py` (consensus
  counts, `[n/N]`), `review_close.py` (the decision gate, PRD 00333's
  single-voice discard for Medium/Low).
- `skills/fast-track/SKILL.md` § Verify and `references/lane-dispatch.md`
  § Victor: the existing adversarial verification shape and its prompt.
- `agents/victor.md`.
- `skills/run-autopilot/cli/runner.py` (`build_argv`): where `--add-dir`
  would go for the workflow engine.
- Memory and review evidence: `reviews/00320-*-review-1.md` R5,
  `reviews/00321-*-review-1.md` R3/R4, `reviews/00324-*-review-2.md` R3/R4,
  `reviews/00326-*-review-2.md` R4.

## Approach (candidate)
Reuse the fast-track Victor dispatch inside the full lane's close step, code
deciding which rows go to him (single-voice CRITICAL/HIGH only). No new
engine, no workflow dependency.

## Success Criteria (candidate)
- Replaying the 00321 cycle-1 review file through the new gate sends R3 and
  R4 to Victor and, with his refutation, converges without a second cycle.
- The batch report shows confirmed and refuted counts per PRD.
- Over a batch, full-lane PRDs converging within the cap rise from 4 of 7.

## Risks
- Victor refutes a real finding (he could not reproduce an environment-bound
  bug); mitigated by "cannot probe confirms" and by keeping the row in the
  ledger with his reasoning.
- Cost: one opus-tier dispatch per single-voice HIGH, roughly 2 to 5 min
  each, against the 70 min cycle it prevents.

## Open Questions
- Does a refuted HIGH still count toward the cap-out ledger, or is it closed?
- Should Blake's single-voice HIGHs (blind lens, often spec re-reads of
  settled design decisions, 00324 R3) be verified against the design doc as
  well as the code?
- Is the workflow engine still wanted once F1 exists, or can `shadow` be
  retired?

## Discovery Log

### Inferred (not asked)
- Cost figures from `loop-metrics.jsonl` rows of 00320 and 00321 (rework
  sessions 26 and 28 min, $7 each; re-reviews 39 and 42 min, $14 and $33).
