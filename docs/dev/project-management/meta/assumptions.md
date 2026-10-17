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

## 6: [D1] skills/fast-track/scripts/

- Drove the two 24h-boundary tests via an in-process `main()` call with a monkeypatched `time.time()`, diverging from the file's dominant subprocess-CLI style, to pin the exact boundary without subprocess-startup timing slop.
- Used non-numeric text as the "malformed" started-file shape (matching the implementation's `int(text.strip())`/`ValueError` path); the brief did not specify exact malformed content.
- New tests live in a sibling file `test_record_item_started_bounds.py` rather than appended to `test_record_item.py`, which was already at 799 lines against the 800-line cap.

## 7: [D1] skills/run-autopilot/scripts/

- The usage-error message contains the literal substring "usage" (case-insensitive) in stderr; exact wording was not pinned by the finding, so the fix prints the existing `USAGE` constant alongside argparse's own usage line.
- Used `get batch.id --default 1 --default 2` (path before both flags) for the repeated-`--default` test since the finding's example order didn't pin argument placement.

## PRD 00333 task 1: Add single-voice tests (fail-first)

- `_finding`, `_state`, `_review`, `_swept`, `_table`, `TAIL_MED`, `MED` are usable exactly as already imported/used elsewhere in `test_review_close_tail_sweep.py`; inferred their shapes solely from existing call sites in the allowlisted file, without reading `test_review_close.py` itself.
- `found_by` is not yet a recognized field on finding rows in the current schema/fixtures; added it as a plain dict key via `dict(_finding(...), found_by=[...])`, consistent with how other tests already override/extend finding dicts (e.g. `ref=...`).
- For `test_tail_sweep_refuses_a_single_voice_row`'s second half ("closes the same batch without it"), built a second review/state pair in the same `tmp_path` with only the multi-voice row, since the first call never applied (state unchanged).
- `_state(tmp_path)` with no extra kwargs assumed valid (same pattern as `_state(tmp_path, **{})` used elsewhere in the file for an empty `extra`).
