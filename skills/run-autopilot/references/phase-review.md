# Review Gate (`phase: "review"`)

Routed here when `state.phase` is `"review"` — or a legacy `"blind"`/`"doubt"`
value from a pre-00015 state file, which maps to `review` on resume. Each review
cycle runs in its own fresh session: review (Phase 4) → decision gate (Phase 5)
→ rework (Phase 6). On convergence, Phase 5 hands off to the finalize session
(**review → done**), skipping rework; otherwise Phase 6, after rework, hands off
to a fresh session for the next cycle (**review → review**) — until convergence
or the cap. Blind and doubt scrutiny are LENSES inside every review cycle, not
separate phases. Core `SKILL.md` (always loaded) carries the shared mechanics.

## Phase 4: Review

Read `dev/local/autopilot/session-brief.md` if it exists (PRD 00201). Its Where section replaces the state reads below; open only the files its Read next section lists. When its phase disagrees with `state.json`, fall back to the state reads.

**Skip the entire review-rework loop if:** `"review"` is in `phases_completed` — the loop already converged in a prior session and handed off (see "Hand off to the finalize session" in Phase 5). Skip Phases 4, 5, and 6, and resume directly at Phase 9 (`references/phase-done.md`).

Write the `resume` handoff row first, best-effort: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/record_dispatch.py handoff --site review --edge resume --phase review --prd <state.prd>` (`work/references/subagent-dispatch.md` § Dispatch telemetry). It sits below the loop-level skip above, whose path resumes into Phase 9 and writes the `done` row there, and above the cycle skip below, so a crash-resume with this cycle's review file already on disk still stamps its edge.

**Skip this cycle's review if:** A review file exists in `dev/local/reviews/` for the current cycle (filename pattern `{prd-name}-review-{cycle}.md`).

**Skip Phases 4 and 5 and resume at Phase 6 "Dispatch rework"** when this cycle's review file exists and `state.rework_task_ids` names a task whose status is not `completed` (PRD 00196). That is a rework session the context-cap hook rotated (it now guards review-phase rework and sets `next_phase: "review"`, so the fresh session lands here): the review and the decision gate already ran, the rework tasks are queued, and the rotated task is back to `pending`. Re-reviewing would re-run every lens against unfinished rework; resume the dispatch instead. Before invoking `/autopilot:work` there, **drop every id whose task is already `completed` from `state.rework_task_ids`** (one `statectl set` of the filtered list): rework mode re-runs every listed id whatever its status, and a task that finished before the rotation must not be implemented twice. **When the unfinished task is the Tail sweep's** (its name starts with `[D{cycle}] Tail sweep`; the cycle had converged), resume at Tail sweep step 3 and continue through its step 4 to the finalize hand-off instead: Phase 6's exit would run `phase-done --outcome rework` and reopen a converged cycle. When every listed task is `completed`, this skip does not fire and the gate continues as today.

Invoke `/autopilot:review-work-completion` skill. Every cycle runs ALL lenses (its roster, PRD 00015): Alice (consensus), Blake (blind, PRD-only), Bob (doubt rubric D1-D5 + de-slop; Claude fallback when codex is down), Carl (UI, optional), plus Eve as a fifth lens when that skill's step 1 doubt-reviewer resolution rule activates her. That rule is the single home of the Codex doubt-roster guard; this phase only invokes it. The skill's consolidation records `state.doubts_rubric_verdicts` from Bob's rubric lines (replaced each cycle; the final cycle's verdicts are what Phase 9 renders).

After completion, stay on `phase: "review"` and `next_phase: "review"` (the decision gate is part of the review surface).

## Phase 5: Decision Gate

### Cap check — evaluate after reading review, before rework dispatch

The cap is a gate on REWORK, not on Phase 5 itself. **First, read the review output** (see "Read the review output" further below). Convergence requires BOTH conditions: **no unresolved CRITICAL or HIGH finding remains**, AND the doubt-roster constraint gate certifies (the exact command lives in Outcomes "Converged (no unresolved CRITICAL/HIGH)" below — run it now when no CRITICAL/HIGH is left). If both hold, the cap is irrelevant — proceed directly to Outcomes "Converged (no unresolved CRITICAL/HIGH)" → tail sweep → finalize hand-off. The PRD success metric "passes review within three cycles is completely unaffected" requires this: a clean cycle-3 convergence at cap=3 must reach the finalize session, not cap-pause.

**"Unresolved" excludes** (PRD 00094): findings this cycle's gate discarded with a verified reason, and **settled deferrals** — a HIGH matching an entry already in `state.deferred_decisions` or recorded as deferred by a prior cycle. Counting a settled deferral blocks convergence for a decision already taken (2 of 3 oranges in the 00105 batch's cycle 2 were exactly this). Until PRD 00095's deterministic matcher lands, matching a finding to a settled deferral is this gate's judgment call on issue text plus file.

**A CRITICAL is never a settled deferral.** Classification below routes "Critical severity, always" to Defer-to-batch-end, so every CRITICAL lands in `deferred_decisions` the cycle it is raised. If the exclusion covered CRITICALs, one raised in cycle 1 would be "settled" by cycle 2 and converge — turning the cap-out branch's `site: "cap_critical"` stall into a path that ships an open CRITICAL. **Deliberate narrowing of PRD 00094**, whose text says "C/H" here but whose guard metric is zero escaped CRITICAL/HIGH, whose cap-out prose assumes C/H persists across cycles, and whose own worked test case is a HIGH. A CRITICAL blocks until it is fixed or the cap-out branch stalls the PRD.

**Medium and Low findings never block convergence.** They are swept, not dropped — see "Tail sweep" below. Nothing else about non-converged cycles changes: Classification and rework still process every severity; only the exit test moved.

If no CRITICAL/HIGH remains but the constraint gate exits 2 (unmet), this is NOT convergence — the Outcomes "Converged (no unresolved CRITICAL/HIGH)" exit-2 branch routes it forward (below cap / at cap) directly, without re-entering this Cap check.

Otherwise (an unresolved CRITICAL/HIGH remains), before evaluating the Safety Checks table below, check whether the review-rework cycle cap has been reached.

Read `state.cycle` (starts at 1; the number of the review cycle just completed) and `state.rework_cap` (the effective cap, written by Phase 0's `autopilot frontmatter` call from the PRD frontmatter — default 2; `cli/frontmatter.py` defines the accepted values, `references/phase-build.md` § Frontmatter parse shows the call).

**Rework is allowed while `cycle < cap`; when `cycle >= cap` AND rework would otherwise be dispatched, the gate pauses instead of reworking.**

Worked example, cap 3:

- cycle 1 review fails → `1 < 3` → rework → cycle 2.
- cycle 2 fails → `2 < 3` → rework → cycle 3.
- cycle 3 fails → `3 >= 3` → **pause, no 4th rework**.
- cycle 3 converges (no unresolved CRITICAL/HIGH) → cap irrelevant → sweep, then finalize hand-off (no pause).

Cap 5 yields five review cycles before the pause (cycles 1-4 → rework, cycle 5 → pause).

When the cap is hit AND the review did not converge (`state.cycle >= state.rework_cap` AND an unresolved CRITICAL/HIGH remains), branch on loop mode (PRD 00017). Under the severity bar these branches can only fire while a CRITICAL/HIGH persists; they are otherwise unchanged:

- **Loop mode (`$_AUTOPILOT_LOOP` set) — cap-out defers, never pauses.** Any unresolved CRITICAL finding → stall the PRD (follow `references/recovery.md` → "Loop-mode stall procedure", `site: "cap_critical"` — the stall itself captures the PRD's live commit range (`work_start_sha..HEAD`) into custody; there is no range flag to pass) and continue the batch. Otherwise (all unresolved findings ≤ high): append each to `deferred_decisions` as `{"type": "cap-overflow", "issue": ..., "severity": ..., "consensus": ..., "reason": "rework cap reached with this finding unresolved"}` (`reason` is the cell the report's Deferred table renders; a record without it renders a blank Reason). `state.deferred_decisions` is the ONLY sink a cap-out writes. Do NOT call `autopilot defer` here: it is Phase 9's migration tool (`references/phase-done.md` step 6), not the cap-out recording path, and a record that reaches only the batch deferred JSON is what PRD 00140's report lost. Then the wrapper records the convergence row at review-phase exit (its `outcome` reads `cap_deferred` from the cap-overflow deferrals just written; see **Convergence metric** below); write nothing. Proceed to the finalize hand-off as converged-with-deferrals, and make the banner name the deferral count (`── cap reached: {k} findings deferred to batch end ──`). Stop polishing, not the batch.
- **Interactive — perform the Cap-pause behavior** (see below) and STOP — do NOT continue into the rest of Phase 5 (no Classification, no Outcomes).

When the cap is NOT hit (or the review converged), continue with the normal Outcomes flow below.

### Cap-pause behavior

Executed only when the Cap check above fired on the INTERACTIVE branch (`state.cycle >= state.rework_cap` AND the review did not converge AND `$_AUTOPILOT_LOOP` is unset — loop mode defers/stalls instead, per the Cap check). This sub-section is the ONLY writer of the `cap_pause_reason` state field; it is a separate top-level field from `stall_reason` (which has different shapes — `oversized_task`, `subagent_prompt_overrun`, `escalation_exhausted` — and a different lifecycle).

1. **Collect unresolved findings.** Read the current review-cycle output (the same review file Phase 4 produced) and gather every finding that has not yet been resolved by an earlier cycle. Format each finding minimally — at least `{"issue": <description>, "severity": <"critical"|"high"|"medium"|"low">, "consensus": <"N/M">}` — additional fields are allowed.

2. **Set `cap_pause_reason`** with `statectl set <state.json> cap_pause_reason '<json>'` (statectl merges — sibling fields are preserved), where `<json>` is the bare object value (NOT a `"cap_pause_reason": {...}` key/value fragment — that is invalid JSON for the value arg):
   ```json
   {
     "cycle": <state.cycle>,
     "cap": <state.rework_cap>,
     "unresolved_findings": [ ... ]
   }
   ```

3. **Set `state.phase` and `state.next_phase`.** Both become `"paused"`. The Phase 0 Cap-Pause Resume Handler (`references/phase-build.md` abort handlers → `references/recovery.md`) is what clears these on resume.

4. **Best-effort dashboard hint (optional).** MAY set `state.needs_attention = true`. This is a hint only — `needs_attention` is dashboard-only state with no automatic clearer since the pidash hooks were retired (PRD 00063; tracon owns the lifecycle per PRD 00062), and it MUST NOT be relied on as the pause indicator. The authoritative cap-pause signal is `phase == "paused"` PLUS `cap_pause_reason` being set (NOT `needs_attention`).

5. **The pause halts the loop by state alone.** Step 3 set `state.phase = "paused"`; the loop driver's decision table (`cli/loop.py`) maps a paused state to "notify the user and stop the loop", leaving `state.json` intact. The user re-invokes `/autopilot:run-autopilot` to handle the pause.

6. **Print the cap-pause banner:**
   ```
   ── AUTOPILOT ── PRD: {prd-name} ── CAP PAUSE (cycle {n}/{cap}) ─────
   ── {k} unresolved findings — see state.json cap_pause_reason ───────
   ── re-invoke /autopilot:run-autopilot to resume or abandon ─────────
   ```
   Substitute `{prd-name}` from `state.prd` (strip the `.md` extension), `{n}` from `state.cycle`, `{cap}` from `state.rework_cap`, and `{k}` from `len(unresolved_findings)`.

7. **STOP.** Do NOT proceed to Phase 6. Do NOT continue into Classification, Outcomes, or the finalize hand-off sub-section. The paused `state.json` is the durable signal that this PRD is awaiting user action; the Phase 0 Cap-Pause Resume Handler picks it up on the next `/autopilot:run-autopilot` invocation.

Read the review output. Categorize each finding using `references/decision-framework.md`.

### Safety Checks — evaluate BEFORE classifying individual issues:

| Condition | Action |
|-----------|--------|
| >10 follow-up tasks from review | Interactive: PAUSE (scope alarm — ask user before proceeding). Loop mode (PRD 00017): keep the top 10 by severity, defer the rest to the batch deferred JSON as `{"type": "scope-overflow", ...}`, log one line, and continue — mirroring the doubt >5 overflow rule |
| Issue count not decreasing vs previous cycle | LOG and continue — a steady cycle is not a failure; the Phase 5 rework cap is the backstop |
| Same issue reappearing after previous fix | Route to research-then-decide Protocol B |
| A reviewer or sub-skill errored transiently during this review cycle | LOG and continue using the reviewers/sub-skills that succeeded (graceful degradation - e.g. a quota-exhausted reviewer is skipped, per the review skill). PAUSE only if the cycle cannot complete at all (no reviewer produced parseable output). A single transient error must not break an unattended run. |

### Classification (per finding):

**Auto-fix** (proceed without asking):
- Low severity, any consensus
- Medium severity, clear mechanical fix
- Medium severity, 1/3 consensus
- Any severity where fix is additive only (adds code/tests, doesn't modify signatures/types/schemas)

**Research-then-decide** (run protocol, then auto-fix or defer):
- New dependency needed -> Protocol A from `references/decision-framework.md`
- Recurring issue (appeared in previous cycle) -> Protocol B
- High + data model change -> Protocol C
- High + touches public API -> Protocol D

Execute the research protocol. If verdict is "proceed", treat as auto-fix. If verdict is "escalate", defer to batch end. Log with full `research` field in either case.

**Routed to verification** (PRD 00164) — **Medium and Low only**: a finding matching an entry in this cycle's verification-check queue (`dev/local/reviews/{prd-stem}-checks-{cycle}.json`, written by `review-work-completion` step 6) is **none of the rows above**. It is not auto-fixed, not researched, not deferred, and creates no task: its named check runs inside the work phase's one mandatory step-7 verification pass, which is where the task would have re-run the same suite anyway. Record it in `autonomous_decisions` as `routed to verification`, naming the command, so an unrun check is visible in the batch report rather than silently dropped. The entry carries every key — `{"cycle": <state.cycle>, "issue": "...", "severity": "...", "action": "...", "reason": "..."}` — a row with `cycle` alone renders blank in the Phase 9 audit. Exclude it from the follow-up task count the Safety Checks table measures, and from the Tail sweep's selection below.

**Matching is this gate's judgment call on issue text plus file** — the same standard the Cap check above uses for settled deferrals, and for the same reason: `consolidate_findings.py` folds paraphrases onto the FIRST-seen wording, so the consolidated row rarely repeats the doubt lens's own words. Verbatim identity would miss exactly the highest-consensus findings and re-create the task this row exists to remove. Match on the entry's `finding` and `file` — the same pair step 7's skip uses, so the two readers never disagree about which rows are queued.

**A cycle that converges with no work pass leaves its checks unrun** — routed findings are excluded from the sweep's selection, so an all-routed Medium/Low tail skips the sweep, and the cap-out paths have no rework pass either. This is a stated limitation, not an oversight: running checks outside a work phase would be the new verification machinery this design exists to avoid. The `autonomous_decisions` entry above is the record that makes those checks visible in the batch report, and it is the whole mitigation.

**A CRITICAL or HIGH is never routed.** It keeps today's classification — "Critical severity, always" still defers, so the invariant above ("every CRITICAL lands in `deferred_decisions` the cycle it is raised") holds unchanged — and it still counts as unresolved for the convergence test. Its command may still sit in the queue and run as evidence; routing decides only where a check runs and whether a task is created, and never resolves a finding. This is what makes the next paragraph true rather than a contradiction.

Two things this row does **not** change. **Convergence:** the test is unchanged — no unresolved CRITICAL or HIGH. Routing a Medium/Low neither blocks convergence nor suppresses one, because Medium and Low never blocked it in the first place. **Lenses:** none is removed, skipped or narrowed. Alice, Blake, Bob, Carl and Eve run exactly as before, and the doubt rubric still requires every residual finding to land in exactly one of FIX/VERIFY/KNOWN. Only the duplicate suite run is gone.

**Discard — contradicts computed facts** (PRD 00095): a finding asserting a countable value about an entity the cycle's mechanical-facts block covers, where the block says otherwise (a claimed 58-line function the block computes at 44), is **discarded, not researched**. The block is computed from `ast`; the reviewer is guessing. Record the discard in the ledger with reason `contradicts computed facts`, which is also what stops the same wrong claim returning next cycle. This applies only to values the block actually covers — a countable claim about anything else is judged normally.

**Defer to batch end** (log, don't PAUSE):
- Critical severity, always
- Requirements ambiguity (PRD says X, code does Y)
- Research-failed items (verdict "escalate" from research protocols)

**PAUSE** (present to user, block progress) — these are blocking escalations; resolve via Outcomes "Has blocking escalation" below:
- Decision blocks subsequent tasks (e.g. API shape needed before frontend can proceed)
- Data model choice that all remaining work depends on

(**Interactive:** present via `AskUserQuestion`. **Loop mode (`$_AUTOPILOT_LOOP` set):** never call `AskUserQuestion` and never pause the batch — the Outcomes "Has blocking escalation" row routes these to the **Loop-mode stall procedure** with `site: "blocking_escalation"` and continues. Scope alarm — >10 follow-ups — is deliberately NOT in this list: the Safety Checks table above already defers-and-continues it in loop mode as a `scope-overflow` record, so it never pauses AND never stalls.)

Log every decision in the state file (`autonomous_decisions` or `deferred_decisions`), each entry carrying every key — `{"cycle": <state.cycle>, "issue": "...", "severity": "...", "action": "...", "reason": "..."}` — and note the review cycle (`state.cycle`) in the entry's Decision text. The Phase 9 audit render reads these arrays — do not write `audit.md` here.

### Settled-decisions ledger (PRD 00095)

**Every deferral and every discard also appends to `dev/local/reviews/{prd-stem}-ledger.json`**, a JSON array created on first write (`{prd-stem}` = `state.prd` minus `.md`). It lives beside the review files rather than in `state.json` so it survives batch end and parked-PRD resumes, and dies with the PRD like the other review satellites.

```json
{"cycle": <state.cycle>, "disposition": "settled-deferral"|"discarded", "severity": ..., "issue": "<the finding text, verbatim>", "file": ..., "reason": "<why it was settled>"}
```

`issue` is the finding's own words, not a summary — the matcher in `consolidate_findings.py` compares against it. Write it with the Write tool (read the existing array, append, write back); a ledger that fails to write is logged and does not block the cycle.

The ledger is what stops a settled call from being re-argued every cycle. It is read in three places: `review-work-completion` step 4 appends it to the implementation-aware prompts, step 6 passes it as `--ledger` so Blake's re-raises are auto-dismissed, and the Cap check's settled-deferral exclusion above is decided from it.

### Outcomes:

The first three rows describe a cycle that did NOT converge — the Cap check above already routed a converged cycle to the last row. A cycle whose only survivors are Medium/Low has converged; it does not "proceed to Phase 6" for another cycle.

- **All auto-fixable, no deferrals, no blockers** → proceed to Phase 6
- **Has deferrals but no blockers** → run `autopilot defer --prd <filename> --batch <batch_id> --json '<record>'` for each deferred item, proceed to Phase 6 with auto-fixable items only
- **Has blocking escalation** →
  - **Interactive:** PAUSE. Present only the blocking issue(s) to user via `AskUserQuestion`. Wait for decision. After user responds, proceed to Phase 6.
  - **Loop mode (`$_AUTOPILOT_LOOP` set):** there is no human to answer — do NOT pause the batch. Follow the **Loop-mode stall procedure** (`references/recovery.md`) with `site: "blocking_escalation"`, recording the blocking issue(s) in the deferred JSON `detail`, and continue the batch. The parked PRD, on un-park, re-enters the build gate and the decision resurfaces interactively.
- **Converged (no unresolved CRITICAL/HIGH)** → before treating the cycle as converged, run `autopilot gate --review-file <this cycle's review file> --require-codex-guard --assert-constraint-met` (flag semantics: `cli/gate.py` module docstring; PRD 00107 absorbed the old `check_review_file.py` path, which survives as a shim). It checks the constraint line only, so a converging cycle may legitimately carry `Verdict: N findings`. Exit 0 → the doubt-roster constraint certified; the review-rework loop has converged (all lenses, including blind and doubt, passed this cycle). On this path the wrapper records the convergence row at review-phase exit; write nothing (see **Convergence metric** below). Run the **Tail sweep** below, then hand off to the finalize session (see below). Exit 2 → the constraint did NOT hold; do NOT converge this cycle. Do NOT re-run the Cap check above — its own convergence test already needs this same gate (see "Cap check" above), so re-entering it only recreates this same bullet. Instead, classify the unmet constraint as one unresolved CRITICAL finding and route forward directly on `state.cycle` vs `state.rework_cap`: below cap → continue to Phase 6 for another review cycle; at cap → the existing cap-out machinery applies with no new mechanism — **loop mode**: the "Any unresolved CRITICAL finding" branch above (stall via `references/recovery.md` → Loop-mode stall procedure, `site: "cap_critical"`; the batch continues); **interactive**: the Cap-pause behavior above (include the constraint among the collected `unresolved_findings`). The batch keeps draining either way; this does not create a new batch-halt class.

### Convergence metric

`cli/loop.py` (`Loop._append_metrics`) appends the `review_converged` row to `dev/local/autopilot/loop-metrics.jsonl` and its `ledger/` mirror when a session launched as `review` exits with `next_phase: "done"` - one row per PRD, written after that session's own row, never from skill prose. Both paths above (converged, and the loop-mode cap-out) exit that way, so neither writes anything. Its shape:

```json
{"event":"review_converged","prd","batch","cycles_to_converge":<state.cycle>,"outcome":"converged"|"cap_deferred","ts":<epoch>,"rework_cap":<state.rework_cap|null>,"build_models":[...],"attempt_tiers":[...],"tasks_planned":<int|null>,"tasks_completed":<int|null>,"tasks_in_prd":<int|null>,"cycles":[{"cycle":1,"reviewers":[...]|null,"verdict":"converged"|<int>|null,"findings":{"critical","high","medium","low"}|null}, ...]}
```

Where each field comes from:

- `outcome`: `cap_deferred` when `deferred_decisions` holds a cap-overflow record, else `converged`.
- `cycles[]`: one entry per cycle, read from `dev/local/reviews/<prd stem>-review-<n>.md` or `-review-<nn>.md`; null when the file is missing.
- `build_models`: this PRD's build session rows.
- `attempt_tiers`: `tasks[].attempts[].model`.
- `tasks_planned` / `tasks_completed`: `tasks_total` / `tasks_completed`, with the `state.tasks` fallback.
- `tasks_in_prd`: the wip PRD's checkbox lines.

`cli/render_metrics.load_rows` still drops event rows while `load_event_rows` reads them, and `autopilot render report` prints them as `- Run conditions:`.

### Tail sweep

Runs once, on the converged outcome above, after the review file is saved and before the finalize hand-off. The Medium/Low tail is **swept, not dropped**: one normal `/autopilot:work` task fixes it, then the PRD finalizes. No new verification machinery.

**1. Select.** Take the converging cycle's actionable Medium/Low findings. Exclude settled deferrals, findings this gate discarded, findings routed to verification (their check runs in step 7; sweeping them would rebuild the task this routing exists to remove), and anything already in `deferred_decisions` — a decision already taken is not swept again. **Zero actionable Medium/Low → skip the sweep entirely** and go straight to the finalize hand-off (today's clean path, unchanged).

**2. Create.** Build ONE `[D{cycle}]` task, named `[D{cycle}] Tail sweep: <theme>` (the `Tail sweep` prefix is what Phase 4's resume rule reads after a rotation, PRD 00196), through Phase 6's "Dispatch rework" mechanics for decision-gate follow-ups: tier from the `/autopilot:plan-tasks` classifier when its inputs are available, otherwise `sonnet`, then the `default_model` floor exactly as that section computes it; `task-add`, then append the printed id to `state.rework_task_ids` — no separate snapshot insert needed, `task-add` already wrote the `state.tasks[]` entry. **The task description carries the same `### Findings (verbatim)` block** Phase 6 D-tasks use (PRD 00095) — one line per swept finding, severity, text, file, consensus — never a summary or a count.

**Split rule:** more than 10 findings → split into 2-4 tasks grouped by file or theme per `work/references/task-splitting.md` (10 is the same constant the Phase 5 scope alarm uses). The existing max-2-parallel rework rule applies unchanged.

**3. Dispatch.** Invoke `/autopilot:work` in rework mode exactly as Phase 6 does. The mandatory one-verification-pass constraint is satisfied by `/autopilot:work`'s own pipeline — tests-first 2.7 for behavioral fixes, the 5.5 gate, 5.6 self-deslop, 5.7 per-task review. Nothing extra runs here.

**4. Finalize.** When `/autopilot:work` returns, go to the finalize hand-off below. **Do NOT increment `state.cycle`, do NOT hand off review → review, and do NOT run another review cycle.** Phase 5 never reopens after convergence — reopening rebuilds the polish loop this gate exists to remove. Print, before the hand-off banner:

```
── converged (cycle {n}): {k} medium/low findings swept ────────────
```

`{n}` is `state.cycle` (unchanged by the sweep) and `{k}` the number of findings swept, not the number of tasks.

**Verify escapes.** The sweep's work pass runs step 7, so it also runs this cycle's queued checks — and Phase 5 never reopens after convergence, so a `verify_check:` that did not pass there has no next cycle to reach. **"Did not pass" means any exit that is not the integer `0`** — a non-zero code, `timeout`, or `refused`. Read them from this cycle's `checks-{cycle}.json` results (the same entries the work pass reported as `verify_check:` lines), and give each a severity the way the carry-forward does — from what the check proves, since a queue entry carries none. Record each one via `autopilot defer --prd <filename> --batch <batch_id> --json '{"type": "verify-escape", "issue": "queued check failed: <command> -> exit <n>", "severity": ..., "command": ..., "exit": ...}'` and finalize. **The `issue` field is not optional:** Phase 9's reconciliation treats an open deferred item with no issue text as always missing (`cli/render_report.py` `missing_from_report`), so an issue-less record halts the very finalize this record exists to permit, and `_merge_deferral_sinks` would fold every such record onto one empty key. Without the record entirely, the failed check lands in a file nothing reads and the PRD finalizes green over it.

**Sweep escapes.** A CRITICAL/HIGH raised by the sweep's own step-5.7 review is handled inside step 5.7 as today (verify, fix inline, max 3 review cycles). One that survives that cap is recorded via `autopilot defer --prd <filename> --batch <batch_id> --json '{"type": "sweep-escape", "issue": ..., "severity": ...}'` and **the PRD still finalizes**. The deferred record is what keeps the escape visible at batch end; the zero-escaped-C/H guard is measured net of these entries.

### Hand off to the finalize session

When the review-rework loop has converged (the "Converged (no unresolved CRITICAL/HIGH)" outcome above, including loop-mode converged-with-deferrals from the cap check), do NOT continue into Phase 9 in this session. Run the **Session handoff procedure** (core `SKILL.md` § Session Loop) with the **review → done** site row — one `autopilot phase-done --outcome converged` call, which sets `phase`/`next_phase` to `"done"` and appends `"review"` to `phases_completed` (the marker Phase 4's loop-level skip reads on resume) in the same commit. The marker lands because this is convergence; there is no flag to pass and none to forget. The procedure's step 2 writes `python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/record_dispatch.py handoff --site review --edge leave --phase done --prd <state.prd>` here. Then print:

```
── AUTOPILOT ── PRD: {prd-name} ── review-rework loop complete ─────
── AUTOPILOT ── handing off to finalize session ────────────────────
```

The next session runs Phase 9 (`references/phase-done.md`), skipping Phases 4-6 via the loop-level skip in Phase 4.

## Phase 6: Rework

**Session model:** Phase 6 runs in the same session as Phase 4 (the `review` surface) — one review cycle (Phase 4 → 5 → 6) per session. The per-task tier escalation in `/autopilot:work` step 3 (dispatching each task as a separate Agent call at `state.tasks[i].model`) means the actual rework implementation runs at the escalated tier (haiku/sonnet/opus) regardless of the outer session. No separate *within-cycle* rework handoff is needed: the review session handles review quality; per-task dispatch handles implementation correctness. (The **review → review** handoff to the *next* cycle's session happens after `/autopilot:work` returns — see "After /autopilot:work returns" below.)

Two task kinds enter this phase:

- **Review-flagged original-plan tasks** (`[C{cycle}]` prefix): a task `/autopilot:work` already attempted that the review phase wants re-done. These are retries — escalate the model tier per the rule below.
- **Decision gate follow-ups** (`[D{cycle}]` prefix): brand-new tasks created from decision gate resolutions. These are first-pass work, not retries — they default to `sonnet` (no escalation applies). Apply the `/autopilot:plan-tasks` Tier classifier here too if you have the inputs (PRD slice, files-touched estimate); otherwise default `sonnet`.

Both prefixes use the current cycle number. Both kinds dispatch through the same rework-mode `/autopilot:work` invocation — see "Dispatch rework" below for how each gets its tier set and queued.

### Escalate review-flagged tasks by tier (PRD 00025)

**Escalation caveat — diagnose the failure before escalating.** The escalation ladder (`references/model-ladder.md` § Capability ladders) assumes a review failure means the model wasn't capable enough. That is often wrong. A review failure caused by a **spec-transmission gap** — the implementer built a self-consistent *wrong* thing because the task description never carried the PRD's exact contract (field names, enum values, hook kind, thresholds) — is not a capability failure. Escalating the tier costs more and does not address the cause: a stronger model fed the same thin task description can fail the same way. Before escalating, look at the cycle's review findings. If they are predominantly spec-misread (wrong schema, wrong API, missing feature, wrong artifact kind) rather than implementation-quality bugs (edge cases, perf, logic errors), the real fix is a **corrected task description** — and the review's follow-up tasks should already carry the exact contract verbatim. In that case keep the **same tier**; do not escalate. Record the decision and rationale in `autonomous_decisions` (the Phase 9 audit render reads it). Escalate the tier only when the prior attempt genuinely struggled on a correctly-specified task. (Root cause and the plan-tasks fix: `references/design-rationale.md` § Escalation diagnosis; the authoring rule is `plan-tasks/SKILL.md` step 4.)

For each review-flagged original-plan task in the current cycle's review output:

1. Look up `state.tasks[i].attempts[-1]` — the last `/autopilot:work` pass's entry, written by `/autopilot:work` Attempt logging.
2. If `state.tasks[i].attempts` is empty or absent (legacy-plan task with no attempt log — covered by step 3's "no prior attempt" case and the closing paragraph after step 5), skip this step entirely and proceed to step 3's next-tier computation. Otherwise, rewrite that entry's `outcome` to `"review_flagged"` (it was `"completed"` when `/autopilot:work` exited; review just flagged it).
3. Compute the next tier by climbing one rung up the capability ladder (`references/model-ladder.md` § Capability ladders):
   - terminal attempt with `implementor: "codex"` → re-dispatch Claude at the task's same tier; do not climb the tier. This branch takes precedence over the tier-only branches below: the codex rung's capability edge is codex → Claude at the task's own tier, so Claude-at-tier is the rung above codex.
   - **no prior attempt** (`state.tasks[i].attempts` empty or absent — covers both pre-PRD-00025 legacy plans and PRD-00025 tasks that crashed before the first attempt log wrote) → treat as `"sonnet"`; next is `"opus"`. **Metric caveat**: when this branch fires for a PRD-00025 task whose actual pass ran `haiku`, it inflates the apparent sonnet→opus escalation rate vs the PRD's ≤2% target. The branch is rare (crash before first attempt-log write) and the conservative jump-to-opus is the right correctness choice; just don't read sonnet→opus telemetry without accounting for it.
   - last attempt at any other tier → next is the next rung up per `references/model-ladder.md` § Capability ladders.
   - last attempt at `"opus"` or `"fable"` → **escalation exhausted**: `opus` is the top rung of the capability ladder and `"fable"` means the human-gated rescue rung above it was already spent (`references/model-ladder.md` § Rungs), so the task cannot be reworked automatically. Do NOT continue to step 4 — **follow `references/recovery.md` → "Rework escalation exhausted"** (rewrites the last attempt's `outcome` to `"rework_failed"`, moves the PRD to `dev/local/prds/hold/`, advances to the next PRD). That handler runs its **Fable rescue gate** first: on a human-approved ledger entry it queues one `fable` retry through step 4's requeue mechanics and returns here to "Dispatch rework" instead of stalling.
4. Otherwise (chain not exhausted), persist the escalated tier, then queue the task for rework:
   - `task-set-meta <task-id> <meta-json-file>` with payload `{"model": "<next_tier>", "escalation_reason": "review_flag", "escalated_from": "<prev_tier>"}` — canonical source `/autopilot:work` reads directly from `state.tasks[i]` (see `work/SKILL.md` "Per-task model dispatch"). `<prev_tier>` is the tier step 3 escalated from. These two fields carry onto the new attempt entry `/autopilot:work` writes at the escalated tier, keeping a review-driven escalation distinguishable from `/autopilot:work`'s own in-loop `escalation_reason:"gate_failure"` in `attempts[]` (`references/state-schema.md`). `task-set-meta` writes `state.tasks[i].model` in the same call — there is no separate mirror write.
   - Reset `state.tasks[i].status` back to `"pending"` via `task-set-status <task-id> pending` so `/autopilot:work` will iterate it again. **Reverse status transitions (`completed` → `pending`) are supported** — `task-set-status` writes `state.tasks[i].status` directly; the ground truth is simply whatever `statectl` wrote (the PostToolUse status-sync hook this line used to cite was retired by PRD 00063 and no longer exists).
5. Append the task ID to `state.rework_task_ids` (create the array if absent) — **after** the status reset, never before: Phase 4's resume rule drops every listed id whose task is still `completed`, so an id appended while its task still read `completed` would be dropped by a rotation landing between the two writes (PRD 00196). A rotation between the reset and the append leaves a `pending` task outside the list, which rework mode ignores and the next cycle re-flags: loud, not silent.

The "no prior attempt" case in step 3 covers both pre-PRD-00025 legacy plans (which lack `state.tasks[i].model` and `attempts[]` entirely) and PRD-00025 tasks that crash before the first attempt log writes (rare but possible). Both are treated as `"sonnet"` for the next-tier computation, so first escalation goes to `"opus"`.

**In-loop ↔ Phase-6 composition.** Step 2's outcome rewrite (`"completed"` → `"review_flagged"`) only ever touches `attempts[-1]` — the terminal rung — which is never an `"escalated"` row (those are earlier history from `/autopilot:work`'s in-loop diagnosis), so `/autopilot:work`'s widened one-entry-per-rung cardinality does not corrupt this read. If the in-loop path already escalated all the way to `opus`, `attempts[-1].model == "opus"` and step 3's next-tier computation above routes straight into the "escalation exhausted" branch — no double-count, no skipped rung. Phase 6 composes cumulatively with in-loop escalation because it always reads the terminal rung's entry.

### Dispatch rework

**Design CRITICAL rework before any task-add (PRD 00194).** When this cycle's consolidated table holds at least one 🔴 CRITICAL row AND `state.cycle < state.rework_cap`, invoke `/autopilot:design-solution dev/local/prds/wip/<state.prd> --rework <this cycle's review file>` ONCE for this cycle, before the first task is created below. Every unresolved 🔴 row of this cycle becomes (or joins) a `[D{cycle}]` task in source 2 below; its Defer-to-batch-end record (Classification) is the audit trail, not a reason to skip the fix - the Cap check reads "A CRITICAL blocks until it is fixed". This section is the only task-creation point for a 🔴 finding under autopilot: `review-work-completion` step 7 leaves 🔴 rows to it (PRD 00194) and creates the other severities as today. The skill writes `dev/local/designs/<prd-stem>-rework-<cycle>-design.md` (`<cycle>` = `state.cycle`), reviewed by its own three-dispatch loop, and ends its `## Review log` with a terminal `result:` line. **Artifact rule on entry:** first the source check - `rg -q -F 'Source review: <review-file> (head_sha <head_sha>)' dev/local/designs/<prd-stem>-rework-<cycle>-design.md`, `<review-file>` being the path passed to `--rework` and `<head_sha>` its frontmatter value; a missing doc or a non-zero exit means the doc is absent or stale (written for other findings) and the skill is invoked, which overwrites it. When the source line matches: if the pass gate below exits 0 (a crash-resume of this cycle), reuse it and skip the invocation; if it has a terminal `result: failed` line, take the failure routing below without re-invoking; if it has no terminal `result:` line (an interrupted run), invoke the skill, which overwrites it. **Pass gate**, run after the invocation or on reuse: `awk 'NF{last=$0} END{exit last!="result: ok"}' dev/local/designs/<prd-stem>-rework-<cycle>-design.md` - exit 0 means the review completed with no open cardinal sin or blocker; anything else is a rework design failure. At the cap (`state.cycle >= state.rework_cap`) the Cap check above already routed the cycle - the loop-mode `site: "cap_critical"` custody stall or the interactive Cap-pause behavior - so no rework design and no fix task is launched here. A cycle with no 🔴 row runs no rework design (the exit-2 doubt-constraint CRITICAL of the Converged outcome is not a table row and runs none either), and every other severity routes exactly as before.

**Rework design failure** - the pass gate exits non-zero: the report ended `result: failed (open cardinal sins/blockers)`, or the doc is missing after the invocation. The skill's three dispatches were the retry budget: do not re-invoke it, and create no fix task. **Loop mode (`$_AUTOPILOT_LOOP` set):** follow the **Loop-mode stall procedure** (`references/recovery.md`) with `site: "design_rework"`, recording the rework design doc path and the open cardinal-sin / blocker titles in `--detail`, and continue the batch. **Interactive:** set `state.phase = "paused"` and `state.next_phase = "paused"`, write `state.pause_reason = {"site": "sub_skill_fail", "detail": "rework design failed with open findings (cycle <state.cycle>): <rework design doc path>; resolve them, then delete the doc so the next Phase 6 entry regenerates it"}`, print `── AUTOPILOT ── PRD: {prd-name} ── PAUSED (rework design failed, cycle {n}) ──`, and STOP. Every consensus, blind and doubt/de-slop lens already ran in Phase 4; the rework design adds a step before the fix task and removes nothing from the roster.

Build the rework batch from two sources:

1. **Review-flagged `[C{cycle}]` tasks** — `state.rework_task_ids` already contains their IDs (appended in step 4 above), and their `state.tasks[i].model` already carries the escalated tier.
2. **Decision gate `[D{cycle}]` follow-ups** — for each new task created from a decision gate resolution:
   - **CRITICAL D-tasks carry the rework design (PRD 00194).** A D-task whose findings include at least one 🔴 CRITICAL line carries, in this order: the line `Design: dev/local/designs/<prd-stem>-rework-<cycle>-design.md`, then a `### Contract` block holding the rework design's `## Interfaces & contracts` section body copied verbatim - byte-identical, not paraphrased; the rework design is the sole contract source for these tasks - then the existing `### Findings (verbatim)` block below them. A D-task with no 🔴 line carries neither and is built exactly as before.
   - **Transcribe the findings verbatim (PRD 00095).** The task description carries a `### Findings (verbatim)` block: one line per source finding, quoted exactly as consolidated — severity, text, file, consensus. N findings routed into a task produce N lines. **No paraphrase, no merging findings into a theme**, and the task's acceptance criterion is "every quoted finding no longer reproduces". This is the whole point: the measured failure was an orchestrator compressing five consensus themes into three tasks, after which the finding that survived was the one nobody had written down. It also costs nothing downstream — `/autopilot:work` step 2.7 writes tests from the task description, so the tests bind to the finding's own words with no change to step 2.7, and step 5.7 checks closure against the same block.
   - Compute the tier: start with the `/autopilot:plan-tasks` Tier classifier output if the inputs are available (PRD slice, files-touched estimate); otherwise default to `sonnet`. Then apply the `default_model` floor **exactly as `/autopilot:plan-tasks` step 4.7 defines it** (the single source of truth): `final_tier = max(tier, default_model)`; re-parse the PRD frontmatter from `dev/local/prds/wip/<state.prd>` at Phase 6 runtime, tolerating the same flat `key: value` block Phase 0 reads; absent frontmatter or unset field → silent pass-through of the classifier tier; malformed YAML or invalid value → warn one line and pass through. Read `default_model` yourself here — `autopilot frontmatter` deliberately does NOT recognize it, because Phase 0 must never write it to state (the PRD frontmatter is the single source of truth for this field). `default_model` is intentionally NOT persisted to state — the PRD frontmatter is the single source of truth.
   - `task-add <task-json-file>` with a payload carrying `{"name": ..., "model": final_tier, ...}` plus any classifier-produced fields (`estimated_tokens`, `est_context_peak`) — this creates the `state.tasks[]` entry directly with `status: "pending"`. Append the printed id to `state.rework_task_ids`. The dashboard sees the new task and `/autopilot:work` rework mode iterates it.

After both sources are merged into `rework_task_ids`, update state (the sync hook maintains the task counts). Invoke `/autopilot:work` — it reads `state.rework_task_ids` and enters **rework mode** (see `work/SKILL.md` "Rework-mode task filter"), processing only the listed IDs at the tier each task carries in `state.tasks[i].model`; non-listed completed tasks are skipped.

The work skill may parallelize independent rework tasks when `superpowers:dispatching-parallel-agents` is available (see work skill's "Parallel dispatch for independent rework fixes").

### After /autopilot:work returns

Apply the whole advance with ONE call, immediately before the banner and turn-end:

```bash
autopilot phase-done --outcome rework
```

It commits all of it together: `rework_task_ids` cleared, `state.cycle` incremented, `phase`/`next_phase` re-affirmed as `"review"`. **The crash window this closes was real.** These used to be four separate `statectl set` calls whose ORDER mattered: the load-bearing one is the `cycle` increment, because the Phase 5 cap gate (`state.cycle >= state.rework_cap`) reads it, and skipping the persisted increment blinds that gate — that exact miss let a loop run past its cap once (`references/design-rationale.md` § Persisted cycle increment). A crash between the clear and the increment left the fresh session re-entering the *same* un-incremented cycle. One transaction means either every effect lands or none does; PRD 00089 closed it on 00051's writer boundary.

Do NOT rewrite `state.tasks` here — `/autopilot:work` already wrote `attempts[]` entries directly to `state.tasks` during rework; the sync hook keeps `tasks_total`/`tasks_completed` current. `phase-done` does not touch `state.tasks` at all, which is why the snapshot cannot be lost by advancing the cycle.
**Then hand off to a fresh session for the next cycle.** The loop does NOT continue in-session — a multi-cycle review session outlives the wall-clock cap and is SIGTERMed mid-cycle, discarding in-flight external-CLI reviewer work. Run the **Session handoff procedure** (core `SKILL.md` § Session Loop) with the **review → review** site row — the `phase-done` call above IS that row's state write (`phase`/`next_phase: "review"`, incremented `cycle`, `rework_task_ids` cleared, `phases_completed` untouched) — (its step 2 writes `python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/record_dispatch.py handoff --site review --edge leave --phase review --prd <state.prd>` here), print the cycle-handoff banner below, and **STOP** (do not re-enter Phase 4 in this session). The wrapper's continue branch relaunches; the fresh session routes `phase: "review"` → Phase 4, which runs `state.cycle` (the incremented cycle; no review file exists for it yet) with no re-review of the prior cycle and no skip-to-done (`phases_completed` lacks `"review"` until convergence).

Cycle-handoff banner (`{prd-name}` = `state.prd` minus `.md`). **Cycle derivation (avoid the off-by-one):** the banner prints AFTER `phase-done` committed the increment, so `state.cycle` at print time is ALREADY the next cycle — `{n}` (the just-completed cycle) = `state.cycle - 1`, `{n+1}` (the cycle handed off to) = `state.cycle`. `phase-done` echoes the committed `phase`/`next_phase` as JSON, not the cycle; read `state.cycle` if you need the number:

```
── AUTOPILOT ── PRD: {prd-name} ── Cycle {n} rework complete ───────
── AUTOPILOT ── handing off to fresh session for cycle {n+1} ───────
```

Cross-references: `references/state-schema.md` (`rework_task_ids`, `tasks[].model`, `tasks[].attempts`, `stall_reason` shapes); `work/SKILL.md` Per-task model dispatch, Attempt logging, Rework-mode task filter.

## De-slop is part of the doubt lens

There is no separate between-session de-slop pass. De-slopping happens **inside every review cycle** — Bob (codex) carries the doubt + de-slop lens in the `review-work-completion` roster, with a Claude fallback when codex is unavailable, so the lens never silently drops. If you are checking how de-slop is wired, look at the review roster, not the `autoclaude` function. (Why the standalone wrapper pass was removed: `references/design-rationale.md` § De-slop.)
