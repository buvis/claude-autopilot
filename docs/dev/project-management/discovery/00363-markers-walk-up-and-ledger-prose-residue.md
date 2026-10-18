# Discovery: Markers walk-up and ledger prose residue

## Classification
Depth: light | Date: 2026-10-18 | Status: pre-elicitation (triage of batch 202610161547's deferred findings on PRD 00326, no questions asked yet)

## Problem
PRD 00326 (close the loop's remaining verb and ledger truths, v2) capped out
at cycle 2 with one HIGH and twelve Medium/Low findings unresolved. Verified
at HEAD e8ca2f7 on 2026-10-18:

- HIGH, hold stub 00346 (ledger key ca4ddb14119d, consensus 1/4):
  `_find_autopilot_dir_in_repo` (`skills/run-autopilot/cli/__main__.py:1916-1933`)
  sets `toplevel` only when `git rev-parse --show-toplevel` exits 0 and
  otherwise calls `_walk_up.find_autopilot_dir(current, stop=None)`, so any
  nonzero git result (a corrupt repo, dubious ownership, a missing binary)
  enables an unbounded ancestor walk and `markers --clear` can clear an
  unrelated parent repository's marker. The `subprocess.run` at line 1925
  has no `try`, so `TimeoutExpired` and `OSError` escape as tracebacks
  instead of a refusal naming `--state`.
- Medium: both new git-failure tests in `test_markers.py` assert `raised or
  code != 0` (an either-or any exception satisfies); the CHANGELOG entry
  (line about `docs/dev/tmp/fast-track-started`) still calls it "the epoch
  the lane writes at item start" while `lane-dispatch.md` says optional and
  operator-written; `lane-dispatch.md:294`'s "No lane step writes that file
  today" is time-relative prose; three touched tests in
  `test_statectl_decide.py` pass against the pre-change code.
- Low: `_walk_up.find_autopilot_dir`'s new `stop` parameter has no direct
  test; `argparse.ArgumentParser(..., exit_on_error=True)` passes the
  default; `record_item.py`'s docstring still says every write exits 0 and
  shows `--started` as mandatory; `selectable()`'s docstring is stale; the
  tracon test asserts `usage` and `root` as separate substrings.

Also deferred by review-close and closed here: the formatter reflow mixed
into the diff (loupe PRD 00001 owns it) and the 800-line items (discovery
00364).

## Requirements (candidate, to be elicited)

### Must have
- F1: unbounded discovery only for an explicit "not a git repository"
  result; every other nonzero result, a timeout or a missing binary stops
  the walk at `cwd` and `markers` refuses with a message naming `--state`.
- F2: the two git-failure tests assert the one outcome each (a refusal
  message and exit code), never `raised or code != 0`.
- F3: the three stale docstrings and the CHANGELOG line say what the code
  does.

### Nice to have
- A direct test for `find_autopilot_dir(stop=...)`.

### Out of scope
- Re-opening the seven targeted fixes 00326 shipped.

## Constraints
- `markers` runs inside loop sessions; a refusal must be loud on stderr and
  non-zero, never a traceback.

## Codebase Context
- `skills/run-autopilot/cli/__main__.py` (`_find_autopilot_dir_in_repo`,
  `_run_markers`), `skills/run-autopilot/scripts/_walk_up.py`
  (`find_autopilot_dir`), `skills/run-autopilot/cli/test_markers.py`.
- `skills/fast-track/scripts/record_item.py`, `skills/run-autopilot/cli/selection.py`.
- Review evidence: `reviews/00326-close-the-loops-remaining-verb-and-ledger-truths-v2-review-2.md`.

## Approach (candidate)
One card-sized PRD on the fast-track lane: the HIGH and the two Medium
test fixes are one card; the docstrings are its tail.

## Success Criteria (candidate)
- With a fake `git` that exits 128 "dubious ownership", `markers --clear x`
  from a nested directory exits non-zero, names `--state`, and touches no
  marker above cwd.

## Risks
- Git's "not a git repository" wording is localized; detect it by exit code
  128 plus the plumbing probe `rev-parse --is-inside-work-tree`, not by
  text.

## Open Questions
- Should `markers` without `--state` exist at all in loop sessions, where
  the state path is always known?

## Discovery Log

### Inferred (not asked)
- Hold stub 00346 is closed into done/ with a note naming this document;
  the deferred ledger rows carry `disposition: discovery 00363`.
