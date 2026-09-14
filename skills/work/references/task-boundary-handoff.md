# Task-Boundary Handoff (step 6.5)

Moved verbatim out of `SKILL.md` step 6.5 (PRD 00119-v2; situational: read only
once `.handoff-requested` is present). SKILL.md keeps the trigger rule and the
no-pending-tasks skip; this file owns the handoff procedure.

The autopilot context-cap hook (`autopilot_context_cap_hook.py`) writes a `.handoff-requested` marker into the autopilot dir once this session's context crosses the **soft** threshold — below the **hard** cap that triggers the destructive abort+replan. Handing off at a task boundary, where every task through step 6 is committed and `state.tasks` is synced, is lossless: the next session re-enters the phase it left and resumes with the remaining pending tasks. This keeps a multi-task phase from ballooning into the hard cap.

## Marker format

`.handoff-requested` is JSON with four required fields: `phase`, `session`, `at`, `task_id` — the phase the writer was in when it wrote the marker, the writing session's id, an ISO-8601 timestamp, and the in-flight task id. `/work` compares the marker's own `phase` against the session's current phase (`state.phase` in `state.json`) instead of assuming every handoff is a build handoff.

For back-compat, a legacy marker (plain text, not JSON) is also accepted. A non-empty legacy marker (a bare task id) is treated as a build request, matching the original behavior. An empty legacy marker is treated as the session's current phase — this is the format the context-cap hook wrote before this fix, not hardcoded to build. Worked example — the case this fix exists for: a legacy empty marker present while the session is in the review phase keeps review as the handoff target, never build.

## Procedure

1. **If no pending tasks remain**, skip this step — proceed to step 7. Final verification runs in whichever session finishes the last task.
2. Resolve the autopilot dir and check for the marker:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-autopilot/scripts/_walk_up.py --bash
   ```
   It prints the absolute autopilot dir. Read `<dir>/.handoff-requested`. **If it is absent**, return to step 1 for the next task — no handoff.
3. **If `.handoff-requested` is present:**
   a. Read `<dir>/state.json` for the session's current phase (`state.phase`). **If `state.json` cannot be read**, there is nothing to compare the marker's phase against: do not hand off, do not invent or assume a phase, and do not remove the markers — leave both in place and return to step 1; re-check at the next task boundary.
   b. Resolve the marker's own phase:
      - Valid JSON with all four fields and a non-empty `task_id` → the marker's phase is its `phase` field.
      - Legacy, non-empty (a bare task id, not JSON) → the marker's phase is `"build"`.
      - Legacy, empty (no content) → the marker's phase is the session's current phase (`state.phase`).
      - JSON-looking but invalid — fails to parse, missing a field, or an empty `task_id` — is **malformed**, a different failure than a clean phase mismatch: print `autopilot: malformed handoff marker (invalid JSON or missing field) — treating as absent` to stderr, remove both `<dir>/.handoff-requested` and `<dir>/.cap-fired`, and continue exactly as if no marker had been present (return to step 1, no handoff).
   c. **If the marker's phase does not match `state.phase`**, it is stale: print `autopilot: stale handoff marker from phase {marker phase}, expected {state.phase}` to stderr, remove both `<dir>/.handoff-requested` and `<dir>/.cap-fired`, and continue exactly as if no marker had been present (return to step 1 for the next task, no handoff).
   d. **Otherwise the marker's phase matches `state.phase`** — hand off within that phase:
      e. Confirm the working tree is clean (`git status --short` empty). Every task through step 6 commits its tests (step 2.9) and implementation (step 5), so it should be. If it is NOT clean, do not hand off — investigate and commit or resolve the uncommitted work first.
      f. Remove both `<dir>/.handoff-requested` and `<dir>/.cap-fired`, inlining the absolute paths from step 2 (no shell variable, so the permission matcher resolves the command). The fresh session re-evaluates its budget from a clean slate.
      g. Print the handoff banner:
         ```
         ── WORK ── handoff at task boundary ────────────────────────────
         ── {completed} tasks done, {pending} pending — context near soft cap
         ── fresh session resumes the remaining tasks ───────────────────
         ```
      h. **Write the contract card** (run-autopilot § Contract card): the current step, the active invariants, and the next gate, so a session compacted after this boundary re-anchors instead of drifting. Write the body to `dev/local/autopilot/contract-card.md` with the **Write tool**, then (autopilot only) load it with `statectl.py <state.json> set-contract-card dev/local/autopilot/contract-card.md`. Never pass the card as an inline shell argument — it carries quotes, newlines and `$`, and the inline form failed three times in a row on quoting in a real build session. Interactive runs stop after the file write. Write the `leave` handoff row — `python3 ${CLAUDE_PLUGIN_ROOT}/skills/work/scripts/record_dispatch.py handoff --site build --edge leave --phase build --prd <state.prd>` — best-effort, never a reason not to hand off (`references/subagent-dispatch.md` § Dispatch telemetry). Then set `state.next_phase` to the marker's (matching) phase, then STOP — end the turn. In loop mode the wrapper reads the non-empty `next_phase` and relaunches a fresh session in that phase (the headless hand-off contract in `run-autopilot/SKILL.md` § Session Loop); the model writes no signal.

      **Do NOT return to step 1, and do NOT run step 7.** `phases_completed` stays without the current phase (this session did not finish it), so `/autopilot:run-autopilot` re-enters that phase and resumes with the remaining pending work. This applies only to the match path (d-h) — the mismatch and malformed paths above (b's last bullet, c) already return to step 1 on their own.
