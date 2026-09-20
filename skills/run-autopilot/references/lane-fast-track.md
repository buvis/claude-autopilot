# Fast-track lane runbook

The procedure Phase 0 step 5.5 (`references/phase-build.md`) follows when
`state.lane_effective == "fast-track"`: a card-sized PRD (at most two cards
of at most 12 paths each, `cli/lane.plan_cards`) runs the existing fast-track
lane (`skills/fast-track/SKILL.md`) once per card inside the batch, then
closes with the same `lane_reviewed` transition the solo lane uses. Phases
1 to 3 do not run for this PRD unless the runbook falls back to full. Five
steps, in this order; the section that stops the lane says so.

## 1. Render

Fast-track's staging precondition first, one Bash call:

```bash
mkdir -p dev/local/autopilot dev/local/tmp
```

Then render the cards from the PRD; `<prd-stem>` is `state.prd` minus `.md`:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/fast-track/scripts/cards_from_prd.py dev/local/prds/wip/<state.prd> --out dev/local/tmp/<prd-stem>-cards
```

Exit 0 prints one card path per line, in card order; hold that list. Exit 2
prints `cards_from_prd.py: <field>: <message>` on stderr and leaves nothing
under `--out`: the PRD is not cardable after all, so write
`lane_effective: "full"` and `lane_reason: "uncardable"` with two `statectl
set` calls and continue to Phase 1 (the PRD takes the full loop; `state.lane`
stays `fast-track`, so the report reads `Lane: full (classified fast-track,
uncardable)`).

## 2. Mirror

Mirror one `state.tasks` entry per card, in card order, so tracon and the
task counts stay live:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-autopilot/scripts/statectl.py dev/local/autopilot/state.json task-add <task-json-file>
```

Each `<task-json-file>` (written with the Write tool) is `{"name": "<item>"}`
where `<item>` is the card's `item` field (`<prd-stem>-c<n>`); no `model`
key. Capture the printed id per card.

Then capture `work_start_sha` and `repo_root` (and `git_dir` for a bare-repo
root) exactly per the Phase 3 invariants (core `SKILL.md` § Phase 3
invariants): once per PRD, only when unset.

## 3. Run

For each card in order:

1. `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-autopilot/scripts/statectl.py dev/local/autopilot/state.json task-start <id>`.
2. Invoke `/autopilot:fast-track <card path>` through the Skill tool, one
   run per card, with no `--push`: the loop defers pushes (core `SKILL.md`
   § Loop Detection), so `--push` is never passed here. The skill runs its
   § Card to § Exit as written and prints its own report; invoking it is what
   resolves the `${CLAUDE_PLUGIN_ROOT}` references in its body, so never
   `Read` `skills/fast-track/SKILL.md` as a file to follow it by hand. In a
   loop session its § Preconditions dispatch the Watcher beside the roster.
3. Read the exit line of its report. `committed`: `task-done` with the
   attempt record `{"attempt": 1, "model": <the card's model>, "outcome": "completed", "review_cycle": null, "cause": null, "implementor": "claude", "preflight_outcome": null, "pipeline": "full"}`
   (Ivan implemented it through the full fast-track roster) and take the next
   card. `branched` (the exit rule printed `branch`, a confirmed CRITICAL or
   HIGH survived): stop the runbook here, see § Stall below. `stopped` (a
   red gate, a green-before-implementation suite, a failed branch or reset):
   also stop the runbook with the same stall, its detail naming the
   `stopped:` reason.

### Stall

A card whose exit rule prints `branch` stops the runbook. Run the Loop-mode
stall procedure (`references/recovery.md`) with the site `fast_track_blocked`:

```bash
autopilot stall --prd <state.prd> --site fast_track_blocked --detail "fast-track/<item>: <surviving findings>"
```

Every earlier card's commits stay on the working branch, since each passed
its roster; the parked card's commits sit under the `fast-track/<item>`
branch fast-track created. The PRD lands in `hold/` with the branch name in
its detail; a human resolves the findings and moves it back to `backlog/`.
Then continue the batch (end the turn; the loop relaunches on `next_phase:
"build"`).

## 4. Consolidate

After the last card, consolidate every card's table into one review file the
gate accepts, `dev/local/reviews/<prd-stem>-review-1.md`, written with the
Write tool in the shape of
`review-work-completion/references/review-coverage-format.md`:

```
---
head_sha: <git rev-parse HEAD>
reviewers: <the union of the lenses that ran across the cards: alice or fanout, blake, eve, bob, carl>
---

## Alice

### <item 1>
<that card's rows from this lens, or its one-line all-clear>

### <item 2>
...

## Blake
...

Verdict: converged
Tests: N passed, M failed, K skipped (fast-track batch suite)
codex_rung_guard: not fired
```

`reviewers:` names the lanes that ran (`alice` when the consensus lane ran
as the subagent, `fanout` when the workflow ran it; `blake`, `eve`, `bob`,
`carl` when they reported), one `## <Name>` section per reviewer holding
each card's rows from that lens (or its one-line all-clear), `Verdict:
converged` when no row survived any card else `Verdict: N findings` (N =
the surviving rows across the cards), the `Tests:` counts from the last
card's `suite: batch` run, and `codex_rung_guard: not fired` always (no
codex-implemented task exists in this lane).

## 5. Close

`autopilot phase-done --outcome lane_reviewed` (the `("build",
"lane_reviewed")` row of `cli/transitions.py`: `phase`/`next_phase: "done"`
and `"review"` appended once to `phases_completed`, so
`review_coverage_hook.py` gates the consolidated file exactly as a full-lane
cycle's), then the Session handoff procedure (core `SKILL.md` § Session
Loop). The done session finalizes as today (`references/phase-done.md`).

Print, before ending the turn:

```
── AUTOPILOT ── PRD: {prd-name} ── fast-track lane: {n} cards committed ──
```
