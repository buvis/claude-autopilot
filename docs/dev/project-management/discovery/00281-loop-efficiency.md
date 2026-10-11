# Discovery: Loop efficiency

## Classification
Depth: comprehensive | Date: 2026-10-11

## Problem
The autoclaude loop spends money and wall time on work that produces
nothing. Across 239 sessions in the agent-skills repo (about $4,888, 142 wall
hours, 2026-08-29 to 2026-10-11) one PRD (00051) burned $1,420 with nothing
to stop it, a hung session sat 2 h 10 min because only the wall cap could end
it, ten 2-7 s sessions were logged as progress, and every PRD that carries
`catchup: force` re-runs full catchup, including two steps that always fail.
Each headless session also starts at about 85K tokens of context before any
work. Fixing this matters now because the loop runs overnight unattended and
these costs compound per session and per PRD.

Evidence: one watched run (agent-skills batch 202610100952, plugin 0.9.0,
2026-10-11) plus that repo's `loop-metrics.jsonl`.

| Slice | Sessions | Cost | Note |
|---|---|---|---|
| build launched | 123 | $2,365 | 86 ended still in build ($1,844) |
| review launched | 75 | $2,454 | avg $32.7; one hit the 3 h wall cap at $117 |
| done launched | 39 | $49 | only to move to the next PRD |
| PRD 00051 alone | 33 | $1,420 | 29% of all spend |
| cost $0 | 11 | $0 | 10 lasted 2-7 s as `continue`; 1 `died` after 7,802 s |

## Requirements

Split into three PRDs (Q0).

### Must have

**PRD A - loop guards (`cli/loop.py`, `cli/loop_decision.py`, `cli/watchdog.py`, `cli/runner.py`)**
- F1: per-PRD spend budget read from `_AUTOPILOT_PRD_BUDGET_USD` (default
  300; 0 disables), summed from the `cost_usd` the metrics row already
  records over the sessions since the PRD last entered wip/ (a resume from
  hold/ starts a fresh budget). When the sum crosses it, park the PRD to
  `hold/` with `stall_reason=budget` and continue the batch (Q1, R3, R7).
- F2: before launching a build session, loop.py calls `enter()` in code,
  records `entered_by: loop` with the entered PRD in state, and writes the
  result (PRD, catchup and design verdicts) into the session brief. The
  run-autopilot prose skips its own `autopilot enter` call when that
  marker matches the current PRD, so a manual run still enters normally.
  The done session is unchanged (Q2, R1).
- F3: a session with `wall_secs < 30` and `cost_usd == 0` gets its own
  signal `instant_exit`. If the usage-limit check fires, wait; otherwise
  take the existing died/retry path (retry once, then park) (R4).
- F4: the idle watchdog arms from launch, not only after the wall cap,
  using the existing `_AUTOPILOT_SESSION_IDLE` (1200 s). The idle timer
  pauses while the session log has a `tool_use` with no matching
  `tool_result` (the wall cap still bounds it). A kill routes to the
  existing died/retry path (Q3, R6).

**PRD B - catchup (`cli/enter.py`, catchup prose)**
- F5: `catchup: force` gives full catchup unless every commit since
  `batch.catchup_head_sha` is an autopilot commit from this batch's loop;
  then delta (Q4).
- F6: probe `gh auth status` and engram registration once per batch, store
  the verdicts in a batch-scoped object (codex_probe idiom), and skip the
  failing catchup steps while the verdict holds.

**PRD C - launch context (`cli/runner.py`, `cli/brief.py`, decision validator)**
- F7: loop sessions load only the Context7 MCP server; an env var
  overrides the allowlist per repo. The mechanism (`--strict-mcp-config`,
  a setting, or an env var) is a design choice (Q5, R2).
- F9: the session brief's `repo root` falls back to
  `custody.project_root` when `state.repo_root` is unset (today it prints
  `none` on every normal run, `brief.py:109`).
- F13: the `autonomous_decisions` validator lists every missing field in
  one rejection (watched session took 5 rejected calls, one field each).

### Nice to have
- Record first-turn boot context tokens in each loop-metrics row, so F7's
  effect is visible per batch.

### Out of scope
- Moving the done phase into code or folding it into review (Q2 rejected).
- A per-PRD budget override in frontmatter (Q1 rejected).
- Deferred to this discovery doc, not in any PRD (Q6): F8 tasks-per-session
  metric (86 of 123 build sessions end in build), F12 wait-pattern prose
  (session called deferred Monitor without its schema, then a blocked
  `sleep 60`), F14 guard-hook prose (`block_working_document_redirects`
  fired 4+ times, plus `enforce_prd_location`, warden, gateguard), F10
  (session re-reads state.json despite the brief; F2 removes the main
  case), F11 (aegis `cat` block).
- Ponytail SessionStart injection in loop sessions: a user-global plugin
  choice, not autopilot's to strip.

## Constraints
- Every acceptance criterion must be checkable headlessly (the loop runs
  these PRDs unattended).
- No new external dependencies.
- Interactive sessions are unaffected; only loop-launched sessions change.
- `enter()` mutates state.json and writes a resume row; calling it from
  loop.py makes two writers at the hand-off, so ordering must be tested.

## Codebase Context
- **Relevant code** (claude-autopilot, `skills/run-autopilot/`):
  `cli/runner.py:218-241` (`build_argv`, no MCP flags today);
  `cli/loop_decision.py:161-198` (signal decision);
  `cli/loop.py:135-169, 305-343` (metrics row, already has `cost_usd`);
  `cli/watchdog.py:1-54, 171-190` (idle check, post-cap only);
  `cli/routing.py:341-358` (caps: 7200 s build/done, 10800 s review);
  `cli/enter.py:277-299` (`_catchup`), `:322` (`enter()`);
  `cli/resume.py` (`resume_target`, returns `unknown phase: done`);
  `cli/brief.py:109`; `cli/records.py:266` (only writer of `repo_root`);
  `cli/usage_limit.py:205` (`detect_from_log`).
- **Conventions**: env-var knobs named `_AUTOPILOT_*`; pure functions with
  injectable `now`/`git_head`; metrics rows append to both
  `loop-metrics.jsonl` and `ledger/loop-metrics.jsonl`.
- **Integration points**: the loop's pre-launch step (F2), the decision
  table (F1, F3), the runner's watchdog thread (F4), `build_argv` (F7),
  `_catchup` (F5).
- **Similar implementations**: `codex_probe` / `qwen_preflight`
  batch-scoped verdicts (`skills/work/references/codex-implementor.md:40-80`,
  `references/state-schema.md:47, 211`) for F6; the existing post-cap idle
  kill for F4; `_fingerprint_bound` park path
  (`loop_decision.py:396-427`) for F1's park.

## Approach
- **Chosen**: deterministic fixes in the loop CLI (code decides budget,
  hangs, instant exits, catchup mode, entry), plus a narrower launch
  environment. Matches the rule that routing on structured state belongs in
  code, not the model.
- **Why**: every finding with real cost is a structured-state decision the
  model is currently making, or a check nobody makes.
- **Rejected alternatives**:
  - Prose-only fixes (tell the session to skip steps): F10 shows sessions
    ignore the brief's "do not re-read" line.
  - Done phase in code: loses deferral judgment, largest change (Q2).
  - Measure-first for F7: one more batch pays the boot cost (Q5).

## Success Criteria
- A test drives the loop with fake sessions whose costs sum past $300 for
  one PRD and asserts that PRD lands in `hold/` with `stall_reason=budget`
  and the next PRD launches.
- A test parks a PRD at $310, moves it back to backlog, and asserts its next
  session runs without re-parking.
- A test runs the loop's pre-launch `enter()` and then the skill's enter
  step for the same PRD, and asserts exactly one resume row is written.
- A test feeds a 3 s, $0 session and asserts signal `instant_exit`, then
  the died/retry path when no usage limit is detected.
- A test with a fake session silent for 1200 s and no open `tool_use`
  asserts a kill well before the wall cap; one silent for 25 min inside an
  open Bash `tool_use` is not killed.
- A test asserts `_catchup` returns `delta` for `force` when all commits
  since `catchup_head_sha` are loop commits, and `full` when one is not.
- With a stubbed `gh` that exits 1, the first catchup in a batch records an
  `unauthenticated` verdict in a batch-scoped probe object, the second
  catchup in the same batch does not invoke `gh`, and a new `batch.id`
  re-probes (same for engram).
- A headless launch built by `build_argv` emits a stream-json
  `system/init` event whose `mcp_servers` lists Context7 only; the env
  override changes that list.
- The rendered brief shows the project root, never `none`, on a state
  without `repo_root`.
- The decision validator's rejection message names all missing fields.

## Risks
- **Idle kill hits a quiet external reviewer** (codex/gemini CLI silent
  over 20 min): the timer pauses while a `tool_use` is open (F4), so a
  working reviewer is bounded only by the wall cap; a hung tool call is
  caught by the cap, not the idle check.
- **`total_cost_usd` may not cover the whole session**: one headless
  session emits many `result` events (one per resume after background
  work); in the watched run 14 of them carried the same $18.58 before it
  rose. F1 relies on the last one being cumulative; the first PRD A task
  confirms that from a recorded log before the budget sum depends on it.
- **"Autopilot commit" misdetected** (F5): a human commit treated as a loop
  commit skips a needed catchup. Detect by a trailer or author the loop
  controls, never by message prefix alone.
- **Claude.ai connectors may not obey `--strict-mcp-config`** (they come
  from the account, not a local config): verify the flag drops them in a
  headless launch before relying on it; if not, find the setting that does.
- **Budget sum across sessions** must count every session of the PRD,
  including died and instant-exit rows, or a crash loop dodges the cap.

## Open Questions
- Which marker identifies a loop commit for F5 (author, trailer, or the
  batch's recorded commit list)? Design decides; the PRD must name one.
- Does `--strict-mcp-config` drop claude.ai connectors in `claude -p`? If
  not, which flag or env var does? (Design decides; the F7 criterion checks
  the outcome either way.)
- What really caused the ten 2-7 s `continue` sessions? They touched state,
  so not a plain refusal. PRD A's first task greps their session logs, if
  any were retained, before F3's routing is finalised.

## Discovery Log

### Q0: How to proceed from these findings?
**Answer**: Elicit, then 3 PRDs: loop guards (F1-F4), catchup (F5-F6),
launch context (F7, F9). Trigger: measured pain (inferred from metrics).

### Q1: F1 budget size and action?
**Answer**: $300 per PRD; on exceed, park the PRD to hold/ and continue the
batch.

### Q2: F2 approach for the done-to-next-PRD hop?
**Answer**: loop.py calls `enter()` in code before launching each build
session and writes the result into the session brief. Done session stays.

### Q3: F4 when should the idle watchdog act?
**Answer**: Whole session from launch, same `_AUTOPILOT_SESSION_IDLE`
(1200 s); a kill routes to the existing died/retry path.

### Q4: F5 how should `catchup: force` behave?
**Answer**: Full unless every commit since `batch.catchup_head_sha` is an
autopilot commit from this batch's loop; then delta. F6 rides along.

### Q5: F7 which MCP connectors do loop sessions get?
**Answer**: Context7 only, env-var override per repo; measure boot context
before/after.

### Q6: Which low-severity leftovers to include?
**Answer**: F3 (instant-exit signal) and F9 + F13 (brief repo root,
validator lists all missing fields). F8, F12, F14 deferred here.

### Review (review-discovery-doc, 2026-10-11)
- R1 (Blocking): in-code `enter()` collided with the skill's own enter.
  Resolved: `entered_by: loop` marker, session skips; one-resume-row test.
- R2 (Blocking): F7 criterion tested the flag, not the effect. Resolved:
  outcome requirement, `system/init` `mcp_servers` criterion.
- R3 (Blocking): budget never reset, so a resumed PRD re-parked at once.
  Resolved: budget per attempt (since last entering wip/).
- R4: no-limit branch after `instant_exit` unspecified. Resolved: died
  path; cause confirmation moved to Open Questions.
- R5: F6 had no criterion. Resolved: stubbed-gh state-level test.
- R6: F4 mitigation was a human watch. Resolved: idle timer pauses while
  a `tool_use` is open.
- R7: $300 hardcoded. Resolved: `_AUTOPILOT_PRD_BUDGET_USD`, default 300.
- Added from monitoring: risk that `total_cost_usd` is not cumulative.

### Inferred (not asked)
- F6 needs no decision: reuse the codex_probe batch-verdict idiom.
- Contradiction check: Q2's in-code `enter()` is what computes Q4's
  catchup verdict, so the two compose.
