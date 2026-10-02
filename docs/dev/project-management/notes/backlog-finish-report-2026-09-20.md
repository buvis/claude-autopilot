# Backlog drain report (2026-09-20)

Plan of record: `backlog-finish-plan-2026-09-20.md`. Five lanes in parallel worktrees, one
Opus subagent each, reviewed per PRD with `/autopilot:review-work-completion` in fresh
headless sessions (all lenses), integrated in the order L3, L1, L2, L4, then L5.

## Releases (committed and tagged locally; pushes pending, see Next)

| Version | Commit | Tag | Marketplace bump (claude-plugins) |
|---|---|---|---|
| 0.5.3 | 8e158ce `chore: release v0.5.3` | v0.5.3 | ad05211 |
| 0.5.4 | b78bc11 `chore: release v0.5.4` | v0.5.4 | 938f378 |

`master` is 88 commits ahead of `origin/master` (b6bdc12). `dev/bin/release patch` failed at
its first step (`git pull --ff-only` in claude-plugins needs the SSH agent, unreachable from
this session), so the local half of `release-plugin` was replayed by hand
(`scratchpad/release-local.sh`): release-checks green, CHANGELOG stamped, plugin.json and
both marketplaces bumped, commit, annotated tag, marketplace commit.

Gates at each release: `bash dev/bin/release-checks` exit 0; full suite
(`skills/run-autopilot skills/fast-track/scripts skills/work/scripts
skills/review-work-completion/scripts skills/plan-tasks/scripts skills/design-solution`)
3013 passed / 1 skipped before 0.5.3, 3493 passed / 1 skipped before 0.5.4.

## Lanes

### L1 cap-hook (00200, 00196, 00194 T3-T4) - merged 05c4cb4
- Agent died on the 5pm session limit after writing the 00194 review-1 file; all code was
  committed, deferred sections were written for 00196/00200, 00194's was written by the
  integrator from the review file.
- 00200: 8 tasks + 3 review fixes. Review 2: 18 findings. Deferred 7 (in the PRD), of which
  [High] soft-cap wording in task-boundary-handoff.md closed by the integrator (5eece09) and
  [High, partially refuted] `last_task_cost` reads the last completed task from any session.
- 00196: 4 tasks + 2 review fixes. Review 2: 6 findings; two HIGHs fixed after the cap
  (unreviewed: resume drop rule, cycle-keyed livelock). Deferred 6.
- 00194 T3-T4: review of T1-T4: 5 findings, all Medium, no re-review. Deferred 5.

### L2 work-skill (00197, 00202, findings 15 and 16) - merged 78f104e
- 00197: review 1: 1 HIGH (`--output=` after `--`), fixed; review 2 converged, 0 findings.
- 00202: review 1: 1 HIGH + 5 Medium, fixed; review 2: 1 HIGH (anchor walk stops at a feat
  commit after a mid-retry rotation) fixed in de18eb7 after the cap, unreviewed. Deferred 4.
- Finding 15 (Pat foreground, 600000 ms) and 16 (Devon skips prose pins) landed with tests.

### L3 loop-cli (00199 incl. finding 14, 00201) - merged a17bf10
- 00199: review 1: 1 HIGH / 6 Medium; review 2: 1 HIGH / 8 Medium. The HIGH (leave row
  written before `next_phase`) was out of lane and closed by the integrator (5eece09).
  Deferred 4 (Medium: batch id on handoff rows; positive controls; two Low).
- 00201: review 1: 2 CRITICAL / 1 HIGH / 6 Medium; review 2: 3 CRITICAL carried, all the
  out-of-lane sites (write-brief at the work and review handoffs, brief-first Phase 0 / Phase 4
  openings, the two prose pins). All three closed by the integrator (5eece09, pinned in
  `test_loop_prose.py`). Deferred 2 Medium.

### L4 review (00198, 00195) - merged 3f47a62
- First agent hung after 00198 (idle from 13:35); stopped at 18:00, a fresh agent finished
  00195 on the rebased branch.
- 00198: review 2: 7 findings, the 🟠 overlap signal fixed after the cap (ab3f7d2). Deferred 3.
- 00195: review 1: 1 HIGH / 9 Medium (non-atomic stub publication, fixed with `os.link`);
  review 2: 1 HIGH (shared `.tmp` sidecar, fixed with `mkstemp` in 3f47a62, unreviewed).
  Deferred 5 Medium + 2 Low; the rollover integrator line landed in 41ac424.

### L5 effort-lanes (00204, 00205, 00206) - merged f11606b, after 0.5.3
- 00204: review 1: 0 CRITICAL / 0 HIGH / 8 Medium / 6 Low; 3 Mediums fixed. Deferred 7.
- 00205: review 1: 6 HIGH; review 2: 3 HIGH; all fixed (the last three after the cap). The
  open "brief line" item was closed at integration once 00201 was on master (ac05181), then
  a third, post-rebase review ran: 8 findings, 0 CRITICAL / 0 HIGH; `_append_metrics` back at
  50 lines and the empty-`lane_effective` fallback fixed (f11606b). Deferred 2 Medium.
- 00206: review 1: 3 HIGH / 7 Medium; review 2: 1 HIGH / 3 Medium; all fixed. PRD spec line
  79-80 amended (`else empty` -> `else none`). Deferred 2 Medium + 3 Low.
- 00204 and 00206 were not re-reviewed after the rebase; their diffs changed only through
  conflict resolution (records.py comment, schema enums, state-schema rows, changelog moves).

## Integrator commits on master
- 5eece09 cross-lane lines from L1-L3 (00199, 00200, 00201, 00202); 257884a changelog wording
- 41ac424 00195 rollover line, duplicated Tess changelog line dropped
- 96192bb changelog prose pins read every `### Added` block (a release stamp emptied
  `[Unreleased]` and broke three suites)
- ac05181 (on L5) brief lane line + `metrics_rows` rebind; f11606b review-3 fixes

## Loop state
- `statectl complete-prd` recorded 00194 (16 completed PRDs in batch 202609061630); tasks 3-4
  marked completed, phase `done`, `next_phase` empty; `state.json` archived to
  `dev/local/autopilot/reports/202609061630-state-final.json`. No `state.json` remains.
- PRDs 00194-00202 and 00204-00206 are in `dev/local/prds/done/` with `### Deferred` sections.
- Worktrees l1-l5 and lane branches removed; stash "loop-blockers hand patch" dropped
  (82f2ad8, every hunk landed).

## Unreviewed-after-cap fixes (for the next review cycle to see)
3ba2753, 4bffa24 (00196), de18eb7 (00202), ab3f7d2 (00198), 3f47a62 (00195), 4be9734 and
23ab599 (00205/00206 lane fixes), f11606b (00205 review 3).

## Rate limits
Seven-day utilization peaked at 0.21; five-hour hit the session limit once (L1, 5pm reset).

## Observations for the plan
- Plain `claude -p` review sessions died when Bob/Carl were still running at turn end;
  every review that produced a file ran with `_AUTOPILOT_LOOP=1` (Watcher dispatched).
- aegis blocks `Co-Authored-By` and redirects into `dev/local/`; lanes adapted.
- loupe reflows every edited `.py` at turn end; each was discarded before committing.
