# Discovery: Stand-down reads formatter dirt as a peer

## Classification
Depth: light | Date: 2026-10-18 | Status: pre-elicitation (written from the monitoring findings of batch 202610161547, no questions asked yet)

## Problem
The stand-down procedure (`skills/run-autopilot/SKILL.md` § Stand-down) reads
two signals as evidence of a second writer: a dirty tracked path reported by
`autopilot dirty`, and a busy interactive session whose name starts with the
repo basename (`ListAgents`). Both were true on 2026-10-17 at 04:32 CEST for
reasons that had nothing to do with a second writer: the dirt was loupe's
end-of-turn formatter pass on three hook files the session itself had just
committed (ruff strips an unused re-import, ruff format reflows a lexicon),
and the busy session was the operator's monitoring session, named for the
repo because it ran in the repo. The 00324 session wrote `pause-requested`
with condition `dirty_tree`, the driver exited "paused by operator", and the
batch sat idle 3 h 46 min until the operator noticed. The 2026-09-28 pause
(11 h idle, `dirty_tree_foreign`) had the same shape.

Loupe's unattended guard (loupe PRD 00001, honor unattended sessions) removes
the dirt at its source once released. The pack's own reading of the signals
stays as it is, so any other formatter, editor save or watcher that touches
a tracked file while a session runs will pause the batch again, and a
monitoring session will keep counting as a peer.

## Requirements (candidate, to be elicited)

### Must have
- F1: a formatter-only diff is never writer evidence: before counting a
  dirty path, the stand-down runs the existing `check_reflow.py` (or `ruff
  format --check` plus `ruff check --diff` on that path) and, when the diff
  is formatting only, reverts it with `git checkout --` and continues,
  recording one ledger line.
- F2: the peer check names what it saw: the pause marker carries the peer's
  session name and its last tool call, so an operator can tell a monitoring
  session from a writer at a glance.
- F3: a session that is only reading (no Edit, Write or git write in its
  last N tool calls) is not a peer.

### Nice to have
- The driver, not the session, decides the stand-down: `autopilot dirty`
  classifies the diff and prints `formatter` or `foreign`, and the prose
  branches on that word.

### Out of scope
- Disabling loupe per project (a user config), or renaming the operator's
  sessions.

## Constraints
- A real second writer must still pause the batch; F1 reverts only diffs a
  formatter produces, never content.
- `ListAgents` exposes a name and a busy flag, not tool history, so F3 may
  need a different source (the session's transcript tail).

## Codebase Context
- `skills/run-autopilot/SKILL.md` § Stand-down procedure (cache 0.9.0 line
  182 at the time).
- `skills/run-autopilot/cli/dirty.py` or the `autopilot dirty` verb (the
  writer-evidence source), `check_reflow.py` in the work skill scripts.
- Evidence: session 830c03d5's transcript (2026-10-17 04:32 CEST), commit
  f8bbd31c (a reflow committed under a misleading message), 2660f314 (the
  replay script made independent of the hook's re-export).

## Approach (candidate)
Classify the dirt in code before the prose reads it; keep the pause for a
real foreign diff.

## Success Criteria (candidate)
- With a tracked file reflowed by `ruff format` and no other change, the
  stand-down reverts it and the session continues; with one content line
  changed, it pauses.
- The pause marker names the peer session.

## Risks
- A formatter that also fixes code (`ruff --fix` removing an unused import
  that a replay script imported) is not formatting-only; F1 must treat an
  import removal as content, which is what broke the replay tests on
  2026-10-17.

## Open Questions
- Is the monitoring session's name under the operator's control, or should
  the peer check ignore sessions whose transcript holds no writes?
- Should a formatter-only revert be committed as a ledger note or stay
  silent?

## Discovery Log

### Inferred (not asked)
- Sources: memory notes of the monitoring session; `wrapper.log` of the
  2026-10-17 04:32 pause; loupe `hooks/agent_end.py` (the deferred format
  pass) and loupe PRD 00001.
