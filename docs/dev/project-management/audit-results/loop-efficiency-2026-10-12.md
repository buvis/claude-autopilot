# Batch 202610111300 progress and inefficiencies (measured 2026-10-12 21:45 CEST)

Scope: read-only look at state.json, loop-metrics.jsonl, dispatch-metrics.jsonl, the
four build-session transcripts of today, the installed 0.9.0 loop code, and the
launcher (`autoclaude` -> `caffeinate -is run-agent ...`, sandboxed since 2026-10-11 16:38).

## Progress

| item | value |
|---|---|
| PRD in flight | 00271 (10 tasks), full lane, opus low |
| build | DONE 21:35, 10/10 tasks, handed to review cycle 1 (session live now) |
| sessions this batch | 9 (2 paused on 10-10/10-11, 6 build, 1 review running) |
| build wall / cost | 5.8 h / $211 (paused sessions $16 of that) |
| per task | ~35 min, ~$20 |
| suite at hand-off | PASS 3436 FAIL 9 SKIP 0 (all 9 pre-exist at the PRD base, see #1) |
| deferred for review | 12 entries (2 HIGH on task 9, 2 MEDIUM on task 7) |
| behind it | 00276, 00277, 00282 (opus), 00278, 00279, 00283, 00284 (sonnet) |
| prior batch reference | 00269: build 107 min + review 70 min, $86; 00270: build 78 + 75 min, $92 (sonnet, 2 cycles each) |

Forecast (guess from the rows above): 00271 review 1.5-2 h at opus, then 3 opus PRDs
at 4-6 h and 4 sonnet PRDs at 2-3 h each. About 30 h and $600-900 if nothing pauses.
Finding #1 adds to that unless fixed.

## Inefficiencies, ranked

### 1. The sandbox makes the release gate permanently red and blinds the loop's pid checks

Facts (measured):
- `autoclaude` launches the loop as `caffeinate -is run-agent python3 ... loop` since
  buvis commit dd29672d (2026-10-11 16:38). Today's 19:35 launch is the first loop
  under the seatbelt profile. The 10-10 batch ran green (2943/0/0 at 709864f).
- `/bin/ps` is `-rwsr-xr-x root` (setuid). Inside the sandbox `/bin/ps -p <pid>`
  fails at exec with EPERM ("Operation not permitted", exit 126). `/usr/bin/pgrep`
  is not setuid and works. The profile allows process-exec, process-info*, sysctl*,
  so no profile edit fixes a setuid exec refusal.
- The build session proved the 9 failures identical at base b57e425 in a throwaway
  worktree (~6 min of opus): 7 wave tests (`test_wave_launch.py`,
  `test_wave_launch_status.py`, `test_wave_launch_refusals.py`,
  `test_wave_assemble.py[l1,l2,l3]`) and the codex/gemini runner lane-marker shell
  tests. Each resolves a live pid's command via `ps`.

Product code that goes blind under the sandbox (every call swallows the failure):
- `cli/loop_gates._pid_tagged` -> False: the registry prune treats every live loop as
  recycled; the "a live loop already owns this checkout" refusal cannot fire.
- `cli/loop._cleanup_orphans` -> no-op: orphaned tagged processes are never HUP'd.
- `scripts/tracon/discovery._pid_tagged` -> False: tracon cannot see loops.
- `scripts/codex_review_run._descendants` / `_cpu_seconds` -> empty / None: Bob's
  hang detector (the 1h44m-at-0-CPU precedent) reports "unknown" forever. The review
  phase running right now is the first codex review under the sandbox.

Cost to the batch:
- `verification.reuse_verdict` needs `failed == 0`, so `review_stage.run_gate_line`
  re-runs the full suite every review cycle instead of reusing the record: ~5-8 min
  per cycle, 2-3 cycles per PRD, 7 PRDs -> roughly 1.5-2.5 h.
- Every queued PRD carries "release-checks exits 0 / FAIL 0" (00276 x1, 00277 x1,
  00278 x2, 00279 x1, 00282 x3, 00283 x2, 00284 x2). None can pass. Each build ends
  with an unmet criterion: a re-proof session like today's, a HIGH deferred entry,
  and a Tests line that reads red at finalize.
- Bob asks for `bash dev/bin/release-checks` every cycle; each lands as a
  `verify-escape` deferred record per cycle.

Options:
- A. Relaunch the loop outside the sandbox (ctrl+c in tracon exits 130 with the state
  untouched at phase review; `run-agent --no-sandbox` is already supported, the
  function hardcodes `run-agent` at `development.plugin.bash:401`). Loses the live
  review session's partial work (~$10-20). Everything above goes green again.
- B. Keep the sandbox, add a PRD "resolve pid tags without setuid ps" (sysctl
  KERN_PROCARGS2 via ctypes, or a tag file instead of the env) at the head of the
  queue. M effort; needs a loop stop anyway to edit the backlog safely.
- C. Keep running as is and accept the costs above. The batch still completes
  (00271 did), with red gate records and blind guards.

### 2. A build session asked the user a question and stopped (cost today ~$12, 17 min)

Session 761a5f25 (18:36Z-19:11Z, $22) built task 9, found the acceptance criterion
"live replay exits 0" unreachable (a pinned-deny id is correctly refused, which forces
exit 1), wrote "That needs your call" and ended its turn. No task-complete write, no
leave handoff, no deferred entry. The loop relaunched: session 6bf1d73e ran 6 turns in
40 s ($1.11), printed the enter banner and stopped; session d431c705 spent its first
6 minutes reconciling, filed the HIGH `contract-conflict` entry, and continued.

Root cause: `skills/work/SKILL.md:216` says "If scope ... unclear, stop and ask the
user rather than picking silently", contradicting `SKILL.md:40-42` ("automated loop,
the user is not watching"). Task 7 hit the same impossible-criterion shape and
deferred instead. The deferred JSON already has an `assumed-ambiguity` type.

Fix (S): rewrite line 216 for loop mode (record `assumed-ambiguity` or
`contract-conflict` with the assumption taken, continue; never end the turn on a
question) plus one prose test. Lives in this checkout, so after the loop stops or as
a PRD. 00282's health signals (instant exit F3, idle watchdog F4) do not cover it.

### 3. Full catchup on every build-session resume (est. ~$40 and ~1.5 h over the batch)

`enter._catchup` (cache `cli/enter.py:294-299`) returns delta only when
`catchup_completed_at` is under 4 h old AND `catchup_head_sha == HEAD`. Every task
commit and loop record commit moves HEAD, so a `catchup: run` PRD gets a full
`/git-ferry:catchup` (~50K tokens, 60-95 s per 00283's numbers) at every resume.
PRD 00283 adds `loop_only(root, sha, committer)` but applies it only to the `force`
first-entry branch and says "the `run` mode and the tasks-present `force` path are
unchanged".

Fix (S): in 00283, make `head != catchup_head_sha` return full only when
`loop_only(...)` is False; one positive and one negative test. Same helper, same PRD.

Side note: `catchup_completed_at` is model-written (`phase-build.md:289`). Today's
value is `2026-10-12T21:00:00Z`: local time stamped Z, rounded to the hour, two hours
in the future. Code should stamp it (statectl), same class as 00276.

### 4. Dispatch records left open (4 of 44 this batch, 9%)

`pat` on task 1 (twice), `pat` on task 5, `tess` on task 7 ended as
`lost: open at build/leave handoff`. For task 7 the strengthen commit landed 2 min
after the dispatch, so the result was used and only `record_dispatch end` was skipped.
Task 1 has no closed patch-review record at all.

Fix (M): close the record from the dispatch call site, not from the model remembering
a second CLI call. Next efficiency discovery round.

### 5. Measured and NOT worth acting on

- Short "continue" sessions overall: 14 of 406, $4 total. Today's 40-second session
  is a blip.
- Subagent time 223 of ~345 build minutes (65%); orchestrator overhead 35%.
- `dispatch-metrics.jsonl` written twice (top level GC-rotated, `ledger/` durable):
  by design.
- Devon strengthen rounds: 46 min this batch, broke 7 of 8 wrong guards on tasks 7
  and 9. Earning their cost.
- One loop running (pid 85771); the agent-skills loop is not live.

## Expect at batch end

- A hold stub or walkthrough item for the task 9 HIGH: the design doc's exit rule
  needs a human decision (exempt pinned-deny ids from the bucket-refusal clause).
- The task 7 timing bound (0.3 s/MB inside this machine's noise band) is a human
  call per the PRD's own Risks section.
