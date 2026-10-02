# Why reviews take 3-9 hours (2026-09-30)

Scope: PRDs 00215, 00216, 00217, 00218 and 00223 (cycle 1 rework still
running at 07:41), all on plugin 0.5.6. Sources are `loop-metrics.jsonl`, the
review files in `dev/local/reviews/`, commit times, and the render log
(`scratchpad/loop.log`, 19.5K lines). Follows
`autoclaude-observation-2026-09-28.md`.

## The shape

| PRD | c1 findings | Rework tasks | c2 findings | Outcome | Review+rework wall |
|---|---|---|---|---|---|
| 00215 | 25 | 9 | 10 | cap 2, deferrals | 6h16m |
| 00216 | 33 (1 CRITICAL) | 8 | 21 | cap 2, 1 HIGH deferred | 7h00m |
| 00217 | 11 | 2 | 14 | cap 2, 1 HIGH deferred | 3h30m |
| 00218 | 32 (1 CRITICAL) | 7 | 15 | cap 2, deferrals | 5h10m |
| 00223 | 35 | 10 | - | rework running | 9h05m so far |

- **The review sessions themselves are short**: 27-48 minutes each, on opus
  at xhigh.
- **Rework is where the hours go.** A cycle-1 review designs 7-10 `[D1]`
  tasks, and each one runs the full per-task pipeline: Tess, Devon (on
  opus/fable tiers), a strengthen pass, Ivan, the style gate, and Pat.
- **Every PRD reached cycle 2 and capped out.** Cycle 2 still found 10-21
  issues each time, and the unresolved ones were deferred or minted as hold
  stubs.

## Findings, ranked by wall time

### R1. Rework tasks inherit the PRD's model floor, so small fixes run the opus pipeline

00223 carries `default_model: opus`, which I set when writing it, so all ten
of its rework tasks run at opus. Per-task rework time, from commit times:

| 00223 (opus floor) | min | 00218 (sonnet floor) | min |
|---|---|---|---|
| task 4, error-to-stop | ~110 | task 8, golden regen | ~10 |
| task 5, reject non-basename `--prd` (2-line fix) | 71 | task 9, malformed stamps | ~12 |
| task 6, surface warnings | 117 | task 10, idle rule | ~14 |
| task 7, docs rows | ~15 | task 11, stamp contract | ~21 |
| task 8, prose obligations | ~40 | task 13, Devon prose | ~33 |
| task 9, lift select/frontmatter | 118 | task 14, time term (opus, Devon ran) | ~46 |

- **Opus-tier rework tasks take 46-118 minutes; sonnet-tier ones take 10-33.**
- The gap comes from Devon plus repeated strengthen rounds. 00223 task 5 made
  4 test commits for a 2-line validation fix, and task 9's commits say "close
  the four exploits the exhausted adversarial round left open".
- The opus floor exists for the initial build's design risk. A rework fix is
  usually a pinned regression, the case the classifier already sends to
  sonnet.

Lever: route `[D1]` rework tasks on the classifier's own tier per finding,
ignoring the PRD floor unless the finding is 🔴 or names a contract change.
Estimate: 00223's rework would drop from about 9h to 3-4h (guess, from the
table above).

### R2. The 4-minute suite runs about 72 times, often to re-read a number

- Full `cli` suite and `release-checks` runs each take about 4:04. The log
  shows at least 72 of them, roughly 4.8h of pure test wall time.
- Runners: Tess, Ivan, Devon (once per exploit, e.g. "Run the full cli test
  suite with exploit 1 in place"), the self-deslop pass, the orchestrator's
  independent re-verification, and the Pat verification record.
- Many are pure repeats: "Re-run release-checks capturing its exit code in
  the same call", "Rerun cli suite for the final count line", "Get the
  pass/fail tally for the acceptance suite".

Levers:
- **Make repeats unnecessary.** Tee every suite run to a log and read the
  count and exit code from it. The skill's Shell Command Rules forbid pipes,
  so this needs a small `run_suite` helper that prints `PASS n / FAIL n /
  exit c` on its last line.
- **Narrow the scope.** Devon and Tess run the target test files, not the
  whole directory. The full suite runs once per task, at the orchestrator's
  gate.
- **Parallelize.** `pytest -n auto` measured 87 s against about 240 s for
  `cli/`. But 7-8 wave tests fail under xdist, a different set each run, and
  all pass serially, so the wave tests share state. Fix that (a per-test git
  config or HOME, or an `xdist_group` for wave tests) before switching.
- Estimate: 2-3h of a 5-PRD run (guess).

### R3. Improvements already written are not running yet

- The loop runs the installed 0.5.6 cache, so none of 00213-00223 affects it
  until a release.
- Devon still runs two rounds, and the re-check exhausts every time.
- The observation-report fixes (one Devon round with every weak point listed,
  00218; `autopilot enter`, 00223) wait for a version bump and
  `/plugin update`.

Lever: release after 00223 converges, before the next batch. That costs
nothing extra.

### R4. Rework volume: one task per finding group, each paying the full pipeline

- Cycle 1 turns 25-35 findings into 7-10 tasks, and each task pays the
  pipeline's fixed cost: prompt renders, Tess, the red-check, Ivan, the style
  gate, Pat, and verification.
- 00223 tasks 7 and 8 were prose-only edits to the same `phase-build.md`
  section but ran as two tasks (6 min apart in commits, each with its own
  gates).

Lever: merge rework findings that touch the same file into one task, and
treat prose-only findings as one lean task (no Tess or Devon, since their
pins are prose tests). Estimate: 20-40 min per cycle (guess).

### R5. Cycle 2 never converges (observation, no lever proposed)

Cycle 2 found 10-21 issues on all four finished PRDs, and all four capped
out. The standing rule forbids thinning the review, so this note makes no
suggestion to cut it. One thing may be worth a look: cycle 2 findings that
restate cycle-1 deferrals versus genuinely new ones. The review files don't
currently separate them.

## Suggested order

1. **R3: release** once 00223 converges. Free.
2. **R1: rework tasks ignore the PRD model floor.** The largest lever,
   probably a small change in `plan-tasks`/`review-work-completion` rework
   task creation.
3. **R2: a `run_suite` helper plus narrow scope,** then xdist once the wave
   tests are isolated.
4. **R4: merge rework tasks by file.**
