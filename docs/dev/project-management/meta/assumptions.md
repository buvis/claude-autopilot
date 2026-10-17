## 1: Add the thirteen fail-first tests for PRD 00326's seven truths

- `selection.selectable`: a non-control Unicode name (e.g. accented "café") must stay selectable - added as a same-test continuity check per the task's own wording, not a new failing assertion.
- statectl `--help`: invoked literally as `statectl.py --help` (no state-path arg), matching the task's exact phrase, since `main()`'s own argument grammar for this isn't in the allowed files.
- statectl "never masks a present key" vs "flag-first order works": both exercised via flag-first ordering against a present key, since path-first ordering with a present key already works correctly today and wouldn't produce a failing test.
- markers `--state`: assumed its value is a path directly to `state.json` (mirroring the `--state` contract used elsewhere in this CLI), with the markers store resolved as its parent.
- markers "store" output key: assumed its value names the resolved autopilot directory as a string path; compared via `Path(...).resolve()` to tolerate resolution-detail differences.
- markers git-toplevel walk: constructed the fixture directly (nested `git init`'d dir with no store of its own, an unrelated repo's store reachable only through a symlink placed one level above it) since the task names the mechanism but not an exact fixture shape.
- `record_item.py` `STARTED_FILE`: assumed path `docs/dev/tmp/fast-track-started`, relative to the same project root the script's existing walk-up already resolves.
- `record_item.py` `--started` bound violation: assumed exit code 2, matching this script's existing argparse-style validation exits for `--rework`/`--outcome`.
- `loop.py` `prd_end`: assumed "launched PRD" is the PRD already in `state.json` before `_decide` runs, modeled via the existing `_row_for_decision` helper's `write_state(prd="p.md")`.
- `triage.qualifies`: assumed `action` is a plain string matched by a "starts with `fix in cycle`" rule, exactly as the task states.
- `test_doc_contract.py`: assumed the rejection message for the new bracketed-positional case is the same `"bare positional placeholder remains"` text the existing unbracketed case already expects.
- PRD item 4 (tracon test OR-weakness): `tracon_wrapper_alive.py` already emits both `usage` and `root` text on stderr for a missing root arg, so the tightened assertion cannot be made to fail red at base commit without asserting something false about already-correct production code. Kept the tightening (a legitimate strengthening) and recorded the discrepancy as an autonomous decision rather than forcing a false result.

## 5: [D1] skills/run-autopilot/cli/

- Markers `--state` toplevel failure: asserted "refuses" as either a raised exception or a nonzero exit (the task's "/" read as OR), and that the unrelated store's marker is never cleared, rather than pinning a specific stderr substring.
- Simulated `git rev-parse --show-toplevel` timeout/OSError via `monkeypatch.setattr(subprocess, "run", ...)` in-process rather than a real subprocess+PATH shim, matching existing test-suite convention for this kind of failure.
- Dedup of `_find_autopilot_dir_in_repo`: added an optional `stop` parameter to `_walk_up.find_autopilot_dir` rather than moving the helper into `markers.py`, since `_walk_up.py` is the documented shared walk-up helper.
- `loop.py` `launched_prd` empty-fallback: left the `= ""` default in place (dropping it would break two existing positional callers in `test_routing.py` outside the task's file allowlist) and added a regression test instead.
- `markers --state` nonexistent parent: validated only path existence (not "looks like an autopilot dir" shape), per the finding's "ideally" wording and to avoid unrequested scope.
