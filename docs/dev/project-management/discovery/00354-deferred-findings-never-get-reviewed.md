# Discovery: Deferred findings never get reviewed

## Classification
Depth: light | Date: 2026-10-18 | Status: pre-elicitation (written from the release-readiness review, no questions asked yet)

## Problem
Every batch ends with a deferred JSON and a set of minted hold stubs, and the
step that reviews them (`/autopilot:run-autopilot review-batch`, an attended
walkthrough) has not run for most of them. State on 2026-10-18:

| Item | Count |
|---|---|
| Batch deferred files under `autopilot/deferred/` | 12 (2026-09-01 to 2026-10-16) |
| Items in the newest one (202610161547) | 79 |
| `severity: high` triage stubs in `prds/hold/` | 9 (00328, 00329, 00336-00339, 00343, 00344, 00346) |
| Stubs the capsule says are already fixed and "should close at the next backlog review" | 3 (00219, 00220, 00228, from September) |
| Source files over the repo's own 800-line cap | 2 (`cli/__main__.py`, `test_state.py`, excluded by 00192) |

Each cap-out adds more: 00320 deferred 16 findings, 00322 16, 00324 8, 00326
17. The batch report lists them and nobody acts, so the hold directory and
the deferred files are a growing backlog nobody owns, and the release shim
only refuses on `severity: critical`. This is gate 3 of the public-release
bar: triage to zero, or a maintained known-limitations list.

## Requirements (candidate, to be elicited)

### Must have
- F1: a `review-batch` that runs unattended for the mechanical part: close a
  stub whose cited finding no longer reproduces (its check command passes at
  HEAD, or the fixing commit is named in the stub), merge duplicate stubs
  (00219/00220 are one finding), and mark deferred items whose file:line no
  longer exists as stale; leave only judgment calls for the attended
  walkthrough.
- F2: a release signal: `dev/bin/release` prints the count of open high
  stubs and unreviewed deferred items, and refuses above a threshold the
  operator sets (0 by default for stubs older than N batches).
- F3: a rendered `docs/dev/project-management/meta/known-limitations.md`
  listing every open stub by title and severity, regenerated at drain, so a
  public reader sees what is open without reading hold/.

### Nice to have
- A per-batch cap on deferred items that turns the next cap-out into a stub
  immediately instead of a deferred row.

### Out of scope
- Changing the rework cap or the cap-out policy (00310, 00321 settled those).

## Constraints
- The attended walkthrough stays attended for judgment calls; code closes
  only what a command can verify.
- Hold stubs are minted by `mint-stubs` with a fixed frontmatter; closing one
  moves it to `done/` with a note (never a delete: a deleted stub of a live
  batch is re-minted at finalize).

## Codebase Context
- `skills/run-autopilot/cli/triage.py` (`qualifies`, mint-stubs), the
  deferred JSON writer in the done phase, `references/phase-done.md` step 6.
- `dev/bin/release:11-16` (the critical-stub refusal).
- `render_report.py` deferred table.

## Approach (candidate)
Mechanical closure in code first (F1), then the release signal (F2), then the
rendered list (F3).

## Success Criteria (candidate)
- Running the mechanical pass on the 202610161547 deferred file closes the
  items whose checks pass at HEAD and reports the rest with a reason.
- The release prints the open counts and refuses when the threshold is hit.

## Risks
- A check command in a stub can pass for the wrong reason (a renamed
  symbol); closure must name the command and its output in the stub.

## Open Questions
- What threshold refuses a release: any open high stub, or only stubs older
  than one batch?
- Should deferred Medium and Low items expire after N batches, or be kept
  forever as evidence?
- Who owns the attended walkthrough cadence: a batch-end step, or a weekly
  operator task?

## Discovery Log

### Inferred (not asked)
- Counts from `ls docs/dev/project-management/autopilot/deferred/`,
  `jq '.items | length'` on the newest file, `rg -n "^severity:" prds/hold/`
  and the project capsule, 2026-10-18.
