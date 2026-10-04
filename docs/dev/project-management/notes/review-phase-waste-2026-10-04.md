# Review-phase waste (2026-10-04, batch 202610031511 on 0.7.0)

Sources: `loop-metrics.jsonl`, `dispatch-metrics.jsonl`, and per-call
timelines of the review-session transcripts (`scratchpad/tl.py`: each tool
call's start, duration, and the model-time gap before it). Follows
`batch-0.7.0-reflection-2026-10-03.md` (build side) and
`review-time-analysis-2026-09-30.md` (R1-R5, all shipped or queued).

## Where a review session's time goes

The reviewers themselves (Alice, Blake, Bob, Carl in parallel) take 10-11
minutes. Everything else is the orchestrator, on opus at xhigh.

| Session | Total | Before reviewers launch | Reviewers run | After reviewers finish |
|---|---|---|---|---|
| 00244 c1 | 25.5 min | 9.0 min | 9.8 min | 7.2 min |
| 00242 c1 | 38.1 min | 15.5 min | 11.3 min | 11.1 min |
| 00242 c2 | 33.4 min | ~6 min | ~7 min | ~18 min (includes a Tess+Ivan tail-sweep task and a 3-min gate) |

| 00248 c1 (0.8.0, 15:4x) | 22.4 min | 7.1 min | ~10 min | 5.0 min |
| 00248 c2 (0.8.0, converged) | 23.5 min | 5.2 min | ~14 min | 3.6 min |

00248 c2 repeated V3 exactly: `release-checks` ran at 368 s (181 s), then
again at 632 s (180 s) only "to a log", because the first run's counts could
not be read back. Three minutes of duplicate gate per cycle, still on 0.8.0.

0.8.0's lower coordinator effort trimmed the overhead a little; it did not
change its shape (still about 55%). So about **60% of a review session is orchestrator overhead**, and two
cycles per PRD is the norm. Per PRD that is roughly 30-45 minutes of
opus/xhigh time spent on work that is deterministic.

## Findings

### V1. The model hand-builds the review inputs every cycle (largest)

Before launch, the orchestrator:

- copies tasks out of `state.json` into `review-tasks-{id}.md` and the PRD
  into `review-prd-{id}.md` by hand (00242 c1: 208-459 s, three Write/Edit
  rounds on the PRD copy alone);
- reads 9 reference files (5 persona files, registry, 2 rubrics, output
  formats);
- writes each reviewer prompt with the Write tool (4 prompts, 26-73 s of
  generation each; in 00242 c2 it gave up and wrote a `/tmp` python
  assembler);
- opens dispatch rows and stamps the lens roster, one Bash call each.

Every one of these is substitution into a known template: the skill itself
says so (`SKILL.md` step 4, "assembled from the agent registry ... substitute
its placeholders"). `skills/work/scripts/render_prompt.py` already does this
for the build personas, and `autopilot enter` already cut session
orientation from ~8 min to ~45 s the same way.

**Lever:** one verb, `autopilot review-stage`, that writes the tasks/PRD
files, runs `gather-context.sh`, the mechanical-facts, tautology and replay
scripts and `engram pack`, renders every roster prompt (settled-decisions
section, incremental addendum, Blake's filesystem notes), stamps the roster
and opens the CLI dispatch rows, then prints the dispatch block. The model
keeps the one judgment call it owns: launching the reviewers.
**Estimate (guess):** 6-12 min saved per cycle, 12-25 min per PRD.

### V2. Post-review bookkeeping runs as many small model turns

After synthesis the orchestrator writes decision arrays through `/tmp` JSON
files, one Write plus one `task-add` per rework or sweep task (00244 c1: 4
sweep tasks, ~75 s), the contract card, the brief, and the handoff rows:
~5 min per cycle.

**Lever:** `autopilot review-close --review-file <f>` reads a structured
block the review file already must carry (findings with severity, file,
consensus, disposition) and does decisions, `group-rework`, `task-add`,
`rework_task_ids`, roster close-out and doubt verdicts in one call.
**Estimate (guess):** 3-5 min per cycle.

### V3. The full gate runs again inside review, sometimes twice

- 00244 c1 ran `release-checks` twice (179 s + 178 s): the second run only
  to read counts the first one printed but the pipe ban kept it from
  extracting.
- `last-verification.json` is not reused because its `sha` lags HEAD by the
  store/handoff commits, or its counts are null (00241 c2 review file, line
  270).
- Carl and Blake also run `release-checks` themselves; Carl's nested
  environment (`AUTOPILOT_DISPATCH_DEPTH`, `CODEX_SESSION_ID`, ...) makes 20
  checks fail spuriously, and he re-runs (00241 c1 and c2).

The orchestrator's run overlaps the reviewers, so this is mostly cost, not
wall time. **Lever:** reuse `last-verification.json` when the only commits
since its `sha` touch the store; when a run is needed, print one
`PASS n FAIL n EXIT c` summary line; tell reviewers the gate result instead
of having them re-run it.

### V4. The engram pack failed on every cycle (fixed today)

`engram pack` exited 1 on every review this batch: "not inside a
registered repo; register it in ~/.config/gita/repos.csv". Every review was
recorded as degraded. **Fixed 2026-10-04:** `gita add` registered this repo.
The same failure would hit any repo not in gita; the skill could say so in
its failure note instead of retrying silently each cycle.

### V5. Codex (Bob) failed twice per cycle on 00241, both cycles

Exit 1 with `turn.failed`, 97 s + 27-36 s, then a Claude fallback ran Bob's
prompt. The doubt lens survived; the cost was ~2 min and model diversity.
00242 and 00244 were fine, so this looks transient. Watch only.

### V6. Fast-track fan-out: four lenses all report exactly 969 s

00243's fast-track roster (Blake, Eve, Bob, Carl) all closed at 969-970 s
and the fanout row closed `error` at 964 s. Identical durations suggest the
rows close at the barrier, not when each lens finished, so the telemetry
cannot show which lens is slow. Worth checking before any fast-track tuning.

### V7. Closing a stub by deleting it re-mints it (fixed by hand)

Deleting hold stub 00245 as "fixed" made the 00244 finalize re-mint the same
ledger key as 00251 an hour later: `cli/triage.py` treats a key as owned only
while some PRD quotes it in its first 20 lines. Closed properly by moving
00251 to `done/` with a resolution note. A `close` verb that writes the
done/ record would remove the trap.

### V8. 00248's planning session used its whole headroom before work (0.8.0, open)

The 14:04 session ran catchup, design and planning for 00248 and hit the
gate-edge headroom check at 146,511 tokens remaining (threshold 150,000), so
it handed off before task 1 at 14:28. The cause of the ~350K-token
consumption is not yet measured (likely the design step's adversarial
review). Check the transcript before tuning.

### V9. Capped rework groups make one task carry too many findings (open)

00249 c1 rework task 8 bundles the file-grouped findings for
`review_close.py`, `review_stage.py`, `verification.py` and `__main__.py`
(00241's cap of 4 non-CRITICAL tasks). It ran from 18:48 past 20:45: Tess,
Ivan, a style-split Ivan round, then a Pat review and an "Ivan retry 2" on
the confirmed findings. One Ivan edit took 19 minutes of model time
(19:45:19 -> 20:04:45). Fewer tasks saved per-task fixed cost, but a task
this wide pays for it in retries. Worth measuring task-size vs retries across
the next batch before changing the cap.

## Not waste (kept)

- The four-lens roster, two cycles, and the cap: standing rule, and cycle 2
  found real HIGHs on 00241 and 00242.
- Reviewer wall time itself (10-11 min, bounded by codex/gemini).

## Suggested order

1. **V1 + V2** as one PRD: review stage-in and stage-out verbs. Biggest,
   deterministic, and has precedent (`enter`, `render_prompt.py`).
2. **V3** rides along (gate reuse and summary line).
3. **V6:** check the fan-out telemetry before trusting fast-track timings.

## Minutes (2026-10-04)

- **V1 + V2 + V3** → PRD 00249 (stage and close reviews in code), backlog.
- **V4** → applied: `gita add` registered this repo.
- **V5** → watch only.
- **V6** → deferred to this note; check before any fast-track tuning.
- **Hold 00246, 00247** (both still real at HEAD) → PRD 00250, which also
  deletes the two stubs.
- **Hold 00252, 00253** (minted by 00248's finalize, both confirmed at HEAD)
  → PRD 00254 (last-boundary negation trim; reviewer personas exempt), which
  deletes the two stubs.
- **00249 cap-out (10 HIGH, 1 stub 00255)** → PRD 00256, which owns all ten
  ledger keys in its frontmatter and must converge before 0.9.0 ships 00249.
- **V10, found here:** nine of the ten were never stubbed because their
  severity was written as `🟠` and `triage.qualifies` matches only words.
  Fixed in 00256 (emoji accepted; cap-out prose says to write a word).
- **Hold 00245** → kept until the 0.8.0 release: PRD 00240 fixed the pattern
  in source (`store_tree.py:33`, `autopilot/**/*.lock`), but the installed
  0.7.0 cache still writes `autopilot/*.lock`. Delete the stub with the
  release.
- **Hold 00110** → closed by the user (keep the `consensus_engine` switch).
  It could never unpark: no PRD is stamped `shadow`, and its eligibility
  check searches `dev/local/reviews`, gone since v0.6.0. Its evidence
  (`reviews/00110-flip-evidence.md`) argued against the flip: ~6.5x tokens
  for about one adopted LOW/MEDIUM finding per cycle.
