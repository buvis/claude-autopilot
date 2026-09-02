# Task-Boundary Handoff (step 6.5)

Moved verbatim out of `SKILL.md` step 6.5 (PRD 00119-v2; situational: read only
once `.handoff-requested` is present). SKILL.md keeps the trigger rule and the
no-pending-tasks skip; this file owns the handoff procedure.

The autopilot context-cap hook (`autopilot_context_cap_hook.py`) writes a `.handoff-requested` marker into the autopilot dir once this session's context crosses the **soft** threshold — below the **hard** cap that triggers the destructive abort+replan. Handing off at a task boundary, where every task through step 6 is committed and `state.tasks` is synced, is lossless: the next `/autopilot:run-autopilot` session re-enters Phase 3 and `/autopilot:work` resumes with the remaining pending tasks (Phase 3's skip rule only skips when *no* tasks are pending). This keeps a multi-task Work phase from ballooning into the hard cap.

## Procedure

1. **If no pending tasks remain**, skip this step — proceed to step 7. Final verification runs in whichever session finishes the last task.
2. Resolve the autopilot dir and check for the marker:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-autopilot/scripts/_walk_up.py --bash
   ```
   It prints the absolute autopilot dir. Read `<dir>/.handoff-requested`. **If it is absent**, return to step 1 for the next task — no handoff.
3. **If `.handoff-requested` is present:**
   a. Confirm the working tree is clean (`git status --short` empty). Every task through step 6 commits its tests (step 2.9) and implementation (step 5), so it should be. If it is NOT clean, do not hand off — investigate and commit or resolve the uncommitted work first.
   b. Remove both `<dir>/.handoff-requested` and `<dir>/.cap-fired`, inlining the absolute paths from step 2 (no shell variable, so the permission matcher resolves the command). The fresh session re-evaluates its budget from a clean slate.
   c. Print the handoff banner:
      ```
      ── WORK ── handoff at task boundary ────────────────────────────
      ── {completed} tasks done, {pending} pending — context near soft cap
      ── fresh session resumes the remaining tasks ───────────────────
      ```
   d. **Write the contract card** (run-autopilot § Contract card): the current step, the active invariants, and the next gate, so a session compacted after this boundary re-anchors instead of drifting. Write the body to `dev/local/autopilot/contract-card.md` with the **Write tool**, then (autopilot only) load it with `statectl.py <state.json> set-contract-card dev/local/autopilot/contract-card.md`. Never pass the card as an inline shell argument — it carries quotes, newlines and `$`, and the inline form failed three times in a row on quoting in a real build session. Interactive runs stop after the file write. Write the `leave` handoff row — `python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/record_dispatch.py handoff --site build --edge leave --phase build --prd <state.prd>` — best-effort, never a reason not to hand off (`references/subagent-dispatch.md` § Dispatch telemetry). Then ensure `state.next_phase == "build"` (it already is during the build gate, since this is a mid-build task-boundary handoff with pending tasks remaining), then STOP — end the turn. In loop mode the wrapper reads the non-empty `next_phase: "build"` and relaunches a fresh session (the headless hand-off contract in `run-autopilot/SKILL.md` § Session Loop); the model writes no signal.

   **Do NOT return to step 1, and do NOT run step 7.** `phases_completed` stays without `"work"` (this session did not finish the phase), so `/autopilot:run-autopilot` re-enters Phase 3 and re-invokes `/autopilot:work`, which reads the pending tasks directly from `state.tasks`.
