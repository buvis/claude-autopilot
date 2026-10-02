# PRD 00110 Flip Evidence — Clean-Cycle Audit

Verdict: **SHORTFALL — premise fails, PRD parks. Never force.**

## What was checked

- `rg -l "shadow" dev/local/reviews/` — zero matches (control query `rg -l "Alice" dev/local/reviews/` confirmed the search itself works: 15 review files matched).
- `rg -l "shadow" dev/local/tmp/` and a full listing of `dev/local/tmp/` — no `<prd-base>-consensus-shadow-{cycle}.md` render files present (checked for the exact naming pattern the PRD's Risks section names).
- Repo-wide `rg -l "shadow" dev/local/` — every hit is either PRD 00110 itself, this task's own planning JSON (`dev/local/tmp/task-00110-*.json`), or unrelated context (historical narrative mentions, an unrelated `box-shadow` CSS rule). No dedicated "shadow ledger" artifact exists anywhere under `dev/local/`.

## Cycles found

Zero. No `consensus_engine: shadow` review run has ever recorded an Alice-section shadow observation (`stats_line`, verdict divergence) in this repo's `dev/local/reviews/` files, and no shadow render has survived in `dev/local/tmp/`.

## Against the premise

- Required: ≥3 consecutive clean cycles, per the PRD's clean-cycle definition (engine completed end-to-end with `stats_line` recorded, zero findings-parse failures, the rendered shadow file passed `check_review_file.py --reviewers alice`, and the shadow verdict matched or was stricter than legacy Alice's).
- Required: ≥1 of those cycles showing raw > unique (dedup collapsing).
- Found: 0 cycles of any kind — clean or dirty.
- **Shortfall: need 3 consecutive clean cycles, have 0.**

## Disposition

Per the PRD's own Feature behavior ("Execution-time re-check: if the evidence is missing, ambiguous, or shows any dirty cycle inside the last three, write the evidence file with the shortfall and stop — park and report, never flip") and its own Phase 0 acceptance ("on shortfall the file records it and the PRD parks (premise failure, never force)"): this PRD parks. No Phase 1/2 tasks (default flip, legacy/shadow retirement, sweep, 00104 closure) were dispatched.

Un-park per the PRD's own "Premise status" note once `dev/local/reviews/` or a shadow ledger shows 3 post-batch shadow cycles — which requires `consensus_engine` to actually run in `shadow` mode across real autopilot review cycles first. No PRD currently in `wip/`/`backlog/` carries `consensus_engine: shadow` frontmatter as of this audit (2026-08-18), so that evidence cannot accrue until one does or until the operator runs one by hand.

## Addendum 2026-08-26: cost of one shadow cycle (PRD 00136 cycle 1, hand-driven)

Source: `~/.claude/dev/local/discovery/00148-autopilot-fast-track-learnings.md` § 2. Measured, not estimated.

| Engine | Agents | Subagent tokens | Wall-clock | Verdict | Blocking | Advisory |
|--------|--------|-----------------|------------|---------|----------|----------|
| legacy Alice | 1 | 118K | (inside the 4-lens batch) | same rubric | - | - |
| review-fanout shadow | 6 | 771K | 5.5 min | `converged` | 0 | 20 |

Of the 20 advisories: 4 duplicated gating reviewers, 3 were genuinely new (auto-memory root false-deny, `expanduser` on extra roots, no durable home for the export), 2 of those were adopted in the walkthrough, the rest were noise or restatements. Reading: ~6.5x tokens for about one adopted LOW/MEDIUM finding per cycle; the shadow does surface things the four lenses miss, but only as advisories.

Options this evidence supports for the flip decision: keep `legacy` as default; or arm `workflow` only on cycle 1 of PRDs whose review diff exceeds a size threshold (500 lines proposed), never on incremental cycles. This is one cycle, not the 3 clean cycles the premise needs; it does not change the parked status.

## 2026-09-21: agent-skills validation batch (0.5.4, `consensus_engine: shadow`)

The shadow leg ran once the session copied `~/.claude/workflows/review-fanout.workflow.js`
into the repo's `dev/local/tmp/` (finding V4); cycle 00052-1 fell back to legacy Alice
before that. Stamped cycles, from `dev/local/reviews/` in agent-skills:

| Review file | consensus_run_id | stats_line | Gating divergence |
|---|---|---|---|
| 00052-...-review-2.md | wf_bc133a2a-4a5 | dimensions 5, raw 11, unique 11, confirmed 0 | none (both zero C/H; workflow APPROVE, 11 advisories) |
| 00053-...-review-1.md | wf_b2d21c3d-5d4 | dimensions 4, raw 12, unique 11, confirmed 0 | not recorded as `no verdict divergence` (see V4b) |
| 00054-...-review-1.md | wf_6aecb2a9-e56 | dimensions 4, raw 5, unique 4, confirmed 0 | same |
| 00055-...-review-1.md | wf_2b0b1871-1ef | dimensions 4, raw 8, unique 8, confirmed 2 | "same orange verdict" on the one HIGH |
| 00055-...-review-2.md | wf_b445aa5c-9a1 | dimensions 5, raw 1, unique 1, confirmed 0 | none |
| 00056-...-review-1.md | wf_d832483c-707 | dimensions 5, raw 5, unique 5, confirmed 0 | none |

Six stamped cycles; two show raw > unique (00053-1, 00054-1). None writes the
literal `no verdict divergence` the eligibility command greps, so the gate counts 0
until the skill pins that phrase (finding V4b). Substantively the 3-clean-cycle
premise is met by 00052-2, 00055-2, 00056-1 (zero gating divergence each).

