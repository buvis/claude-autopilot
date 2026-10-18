# Discovery: The lane record contradicts the classifier

## Classification
Depth: light | Date: 2026-10-18 | Status: pre-elicitation (written from the batch 202610161547 report, no questions asked yet)

## Problem
`classify` in `skills/run-autopilot/cli/lane.py` returns one of seven
verdicts, and `uncardable` is always paired with `full`
(`return verdict("full", "uncardable")`). The batch report for 202610161547
prints, for PRD 00333, `Lane: full (classified fast-track, uncardable)`, and
`state.json` during that PRD held `lane: "fast-track"` beside `lane_reason:
"uncardable"`. No code path emits that pair, so something wrote `lane` after
the classifier ran (the selection verb, a session, or a record rewrite), and
the batch summary's lane counts (solo 3, fast-track 8, full 7) count 00333
under the wrong lane. The lane fields are the input of the cost analysis
that decides which PRDs to author as cards, so a wrong record skews the
next batch's routing. One wrong pair in 18 is small; the point is that
nothing checks the pair.

A second truth gap of the same family: the fast-track item rows in
`loop-metrics.jsonl` carry invented `--started` epochs (9 of 17 rows in the
batch, wall times up to 29,870,908 min). PRD 00326 bounds the value to 24 h
before the end; it does not derive it from the dispatch ledger where the
true start is.

## Requirements (candidate, to be elicited)

### Must have
- F1: the state validator refuses a `lane`/`lane_reason` pair the classifier
  cannot emit (the seven pairs are a closed table), the same way PRD 00342
  closed the attempt-stamp grammar.
- F2: a forensic pass over the 00333 state history names the writer of the
  wrong pair (the `record` commits are in git), and that writer is fixed.
- F3: `record_item.py` derives `--started` from the item's first dispatch
  row when the caller gives none, instead of trusting an invented epoch.

### Nice to have
- The batch report renders the lane counts from the records after validation
  and flags any PRD whose pair was corrected.

### Out of scope
- Changing the classifier's rules.

## Constraints
- The validator must accept a frontmatter override (`lane:` declared, reason
  `override`) and the escalation shape (`lane_escalated`).

## Codebase Context
- `skills/run-autopilot/cli/lane.py:392-417` (`classify`),
  `cli/frontmatter.py:178-185` (writes `lane`, `lane_reason`),
  `cli/schema.py:50` (`lane` enum), `cli/lane_check.py:87-100`
  (`lane_effective`, `lane_escalated`), `cli/render_report.py:576-581`.
- `skills/fast-track/scripts/record_item.py` and
  `test_record_item_started_bounds.py` (PRD 00326).
- Evidence: `reports/202610161547-report.md` line 609, the batch summary at
  line 845, `loop-metrics.jsonl` rows with `batch: fast-track`.

## Approach (candidate)
Close the grammar in the validator; derive the start from the ledger.

## Success Criteria (candidate)
- A state write with `lane: fast-track, lane_reason: uncardable` is refused
  with a message naming the allowed pairs.
- A fast-track row recorded without `--started` carries the first dispatch
  row's start, and the batch report's fast-track wall times are within the
  batch window.

## Risks
- Historical records keep the wrong pair; the report should mark them
  rather than rewrite history.

## Open Questions
- Is the writer of the wrong pair a session (prose) or a verb (code)? The
  forensic pass decides whether the fix is a validator alone or a verb fix.

## Discovery Log

### Inferred (not asked)
- `git log -S'uncardable' -- state.json` returned nothing on 2026-10-18, so
  the pair may have been written into the record, not the state; the
  forensic pass (F2) starts there.
