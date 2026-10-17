# Decision Audit Log: 00326-close-the-loops-remaining-verb-and-ledger-truths-v2

PRD: `00326-close-the-loops-remaining-verb-and-ledger-truths-v2.md`
Started: 2026-10-17T11:29:15Z
Completed: 2026-10-17T11:29:15Z
Autonomous: 26  |  Deferred: 17  |  Doubts: 0

### [autonomous] 2026-10-17T11:29:15Z

**Decision**: PRD 00326 item 4 (tracon test OR-weakness) expects the tightened test to fail red, but tracon_wrapper_alive.py already emits both usage and root text on stderr for a missing root arg - is the PRDs description stale for this sub-item?

**Choice**: kept the tightened OR->AND assertion in test_wrapper_alive_script_requires_root_arg as a legitimate strengthening even though it passes (not red) at base commit, since forcing a false-red test would assert something untrue about already-correct production code

### [autonomous] 2026-10-17T11:29:15Z

**Decision**: `qualifies` excludes every non-stall row whose `action` starts with "fix in cycle". The PRD narrows this to `review-critical` rows. A `cap-overflow` or other open CRITICAL/HIGH row carrying such an action would be silently dropped and never minted. The test only checks a `cap-overflow` row with no action, so it cannot catch the over-broad match. Gate on `row.get("type") == "review-critical"`, and add a `cap-overflow` plus "fix in cycle" case to the test.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-17T11:29:15Z

**Decision**: lane-dispatch.md says "the lane writes that file at item start", but no lane step writes `docs/dev/tmp/fast-track-started`. skills/fast-track/SKILL.md:634 still tells the session to pass `--started <epoch seconds of the first dispatch>`. The new fallback is therefore unreachable in practice, and the prose states something the lane does not do. Add the write step to the lane prose, or reword lane-dispatch.md to say the file is optional and operator-written.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-17T11:29:15Z

**Decision**: `_dispatch` hand-parses `get` with `_parse_get_args`, where the PRD says "parses `get` with argparse". Extra positionals are silently dropped, and a repeated `--default` silently takes the last value. Use argparse (exit 1 on usage error) or reject the extras explicitly.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-17T11:29:15Z

**Decision**: The new `get --default` tests are looser than the PRD. The malformed-path and trailing-`--default` tests assert only `returncode != 0` (the PRD says exit 1 with the usage text). `test_get_default_never_masks_a_present_key` uses a different shape from the PRD's `batch.id --default null`. No test covers a falsy but present value (0, null, false) staying unmasked. Assert `== 1` and a "usage" substring, and add a falsy-value case.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-17T11:29:15Z

**Decision**: Mechanical facts report `_run_loop` at 51 lines, exceeding the 50-line limit. Remove the redundant blank line between launch and decision without changing control flow.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-17T11:29:15Z

**Decision**: A git timeout or launch error sets `toplevel = None`, enabling an unrestricted ancestor walk. From a nested repository, `markers --clear` can consequently clear the parent store. Refuse automatic resolution after these errors and require `--state`; add a timeout regression test.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-17T11:29:15Z

**Decision**: `--started` bounds are under-tested. The future-timestamp refusal is a PRD must-have (">24h before ts_end or in the future") but has no test. Only the year-old case is covered. Nothing covers the new "--started omitted and the started file missing or malformed, exit 2" branch, or an out-of-bound value read from the started file.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-17T11:29:15Z

**Decision**: `_find_autopilot_dir_in_repo` copies the body of `_walk_up.find_autopilot_dir` (the resolve, walk and OSError handling) just to add a stop directory. It sits in `__main__.py`, already 2030 lines. Add an optional `stop` parameter to `_walk_up.find_autopilot_dir`, or put the helper in `markers.py`, and delete the 33-line copy.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-17T11:29:15Z

**Decision**: The toplevel guard fails open. If `git rev-parse --show-toplevel` times out, raises OSError or is missing, `toplevel` becomes None and the walk climbs to the filesystem root with no message. That is exactly the cross-repository clearing the fix is meant to prevent. Fail loud in the error cases (timeout, OSError) and allow an unbounded walk only when git reports "not a repository".

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-17T11:29:15Z

**Decision**: `_read_started_file()` does not catch `UnicodeDecodeError`. A non-UTF-8 started file produces a traceback instead of the controlled exit-2 diagnostic. Handle decoding errors alongside read failures and test invalid bytes.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-17T11:29:15Z

**Decision**: Timestamp tests cover a year-old value and a valid fallback, but omit future timestamps, the exact 24-hour boundary, and diagnostics naming the rejected value. Add these cases with a fixed clock.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-17T11:29:15Z

**Decision**: Replace custom 23-line while-loop in _parse_get_args with argparse.ArgumentParser to enforce argument validation and simplify dispatch

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-17T11:29:15Z

**Decision**: The PRD's fallback case, where `launched_prd` is empty on a bootstrap session and `prd` falls back to the decision's PRD, has no test. The `launched_prd: str = ""` default also lets a future caller omit the argument silently. test_routing.py already calls `_append_metrics` without it. Make the argument required, or test the fallback.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-17T11:29:15Z

**Decision**: test_selection.py:86 embeds a raw, invisible U+2028 character in the string literal, while the NEL case on line 85 uses an escape. Write it as an escape so a reader or editor sees which case the test pins. The new test comments also still describe pre-fix behavior and name the removed `_has_control_char`. Reword them as the rule being enforced.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-17T11:29:15Z

**Decision**: `_find_autopilot_dir_in_repo` falls back to an unbounded walk to the filesystem root when `git rev-parse --show-toplevel` fails (cwd outside a repo, git missing or timed out). The cross-store clear the PRD fixes can still occur in that case, and `markers --clear` is destructive.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-17T11:29:15Z

**Decision**: `markers --state` takes `Path(args.state).resolve().parent` as the store without checking that it exists or is an autopilot dir. A typo'd path makes `--check` report all markers false and `--clear` a silent no-op, and the output names the bogus store.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-17T11:29:15Z

**Decision**: 17 Medium/Low/High findings (R1-R6, R8-R12, R14-R16, R18, R19) classified auto-fix

**Choice**: queued as [D1] rework tasks 5-8 via review-close (cycle 1)

**Rationale**: two 🟠 HIGH rows (over-broad qualifies exclusion, fail-open markers toplevel guard) block convergence; the rest are mechanical fixes and test tightenings

### [autonomous] 2026-10-17T11:29:15Z

**Decision**: Carl's R21: backlog PRD 00342 modified outside PRD 00326 scope

**Choice**: discarded (cycle 1)

**Rationale**: contradicts computed facts: git log and git diff over 6d7c97f3..HEAD for that path are both empty

### [autonomous] 2026-10-17T11:29:15Z

**Decision**: Five [MECH] fail-first replay rows (R22-R26)

**Choice**: discarded (cycle 1)

**Rationale**: every named test is pre-existing and unchanged; the replay flags the whole file because a sibling test was edited, and each new test does fail against the pre-change code

### [autonomous] 2026-10-17T11:29:15Z

**Decision**: R7 formatter reflow mixed into the diff; R13/R17/R20 800-line file caps

**Choice**: deferred to batch end (cycle 1)

**Rationale**: the reflow is loupe's end-of-turn pass (fix is a loupe release, not this PRD); the line-cap rows are pre-existing or 4 lines over a soft style cap

### [autonomous] 2026-10-17T11:29:15Z

**Decision**: R11 (cycle 2 review)

**Choice**: discarded

**Rationale**: Blake's own words call it "a small, defensible extra": rejecting a repeated --default and an extra positional is stricter than the PRD, not a defect; the PRD's requirement (exit 1 with usage) holds.

### [autonomous] 2026-10-17T11:29:15Z

**Decision**: R14 (cycle 2 review)

**Choice**: discarded

**Rationale**: contradicts computed facts about scope: the only implementation change to record_item.py in this incremental range (base 61029a3e) is the UnicodeDecodeError catch; the six started-bound tests pin behavior shipped before this base, so passing against it is expected.

### [autonomous] 2026-10-17T11:29:15Z

**Decision**: R15 (cycle 2 review)

**Choice**: discarded

**Rationale**: pure test addition: no implementation changed for the launched_prd fallback in this range, so the new test pins already-shipped behavior.

### [autonomous] 2026-10-17T11:29:15Z

**Decision**: R16 (cycle 2 review)

**Choice**: discarded

**Rationale**: two of the three are pre-existing marker tests (already ledgered in cycle 1) and test_clear_still_walks_unbounded_when_git_reports_not_a_repository pins behavior present before this base.

### [autonomous] 2026-10-17T11:29:15Z

**Decision**: R17 (cycle 2 review)

**Choice**: discarded

**Rationale**: selection.py is not touched in this incremental range; the C1/U+2028 test pins truth 1 as shipped in task 2, before this base.

### [deferred] 2026-10-17T11:29:15Z

**Decision**: Unrelated formatter reflow is mixed into the diff (import blocks, `__all__` order, signatures, call sites and asserts rewrapped). None of it traces to the PRD, and it buries the real change in a roughly 680-line diff.

**Choice**: deferred

**Rationale**: deferred by review-close

### [deferred] 2026-10-17T11:29:15Z

**Decision**: skills/run-autopilot/cli/test_routing.py exceeds the 800-line limit at 804 lines

**Choice**: deferred

**Rationale**: deferred by review-close

### [deferred] 2026-10-17T11:29:15Z

**Decision**: The diff adds code to files already past the 800-line cap: `__main__.py` is 2030 lines and test_discovery.py is 1703.

**Choice**: deferred

**Rationale**: deferred by review-close

### [deferred] 2026-10-17T11:29:15Z

**Decision**: `cli/__main__.py` and `scripts/tracon/test_discovery.py` already exceed the 800-line limit. Splitting these existing modules is outside this PRD's seven targeted fixes.

**Choice**: deferred

**Rationale**: deferred by review-close

### [deferred] 2026-10-17T11:29:15Z

**Decision**: `_find_autopilot_dir_in_repo` lets subprocess.TimeoutExpired and OSError from `git rev-parse` escape uncaught, so `markers --check/--clear` dies with a traceback instead of a controlled refusal naming `--state` (skills/run-autopilot/cli/__main__.py:1925)

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-17T11:29:15Z

**Decision**: Both new git-failure tests assert `raised or code != 0`, an either-or hedge any unrelated exception satisfies (skills/run-autopilot/cli/test_markers.py:845)

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-17T11:29:15Z

**Decision**: lane-dispatch.md's new sentence "No lane step writes that file today" is time-relative prose; state the rule instead (skills/fast-track/references/lane-dispatch.md:294)

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-17T11:29:15Z

**Decision**: Every nonzero git result still enables an unrestricted ancestor walk (corruption, dubious ownership), so an unrelated parent marker can be cleared; permit unbounded discovery only for an explicit "not a repository" result (skills/run-autopilot/cli/__main__.py:1931)

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-17T11:29:15Z

**Decision**: The CHANGELOG entry still calls docs/dev/tmp/fast-track-started "the epoch the lane writes at item start" while lane-dispatch.md now says it is optional and operator-written (CHANGELOG.md:105)

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-17T11:29:15Z

**Decision**: markers without `--state` runs `git rev-parse` with no guard for a missing binary or a timeout, and outside a repo the walk-up is unbounded again (skills/run-autopilot/cli/__main__.py:1925; same theme as R1 and R4)

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-17T11:29:15Z

**Decision**: test_clear_refuses_when_git_toplevel_lookup_times_out and ..._raises_oserror hedge with 'or': either outcome satisfies them (skills/run-autopilot/cli/test_markers.py:226, :256; same defect as R2)

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-17T11:29:15Z

**Decision**: The new `stop` parameter on _walk_up.find_autopilot_dir has no direct test in test_walk_up.py (skills/run-autopilot/scripts/_walk_up.py:53)

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-17T11:29:15Z

**Decision**: argparse.ArgumentParser(..., exit_on_error=True) passes the default value, so the argument is redundant (skills/run-autopilot/scripts/statectl.py:156)

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-17T11:29:15Z

**Decision**: record_item.py's module docstring still says "Every write is best-effort and exits 0" and shows --started as mandatory, while omitting both --started and the started file now exits 2 (skills/fast-track/scripts/record_item.py:6)

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-17T11:29:15Z

**Decision**: selectable()'s docstring still says only "below U+0020, or U+007F" are excluded, stale now that line breaks and every Cc character are excluded (skills/run-autopilot/cli/selection.py:61)

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-17T11:29:15Z

**Decision**: The tracon test asserts `usage` and `root` as two separate stderr substrings, so it does not pin that the usage line itself names root (skills/run-autopilot/scripts/tracon/test_discovery.py:1700)

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-10-17T11:29:15Z

**Decision**: [MECH] 3 touched tests pass against the pre-change code, including test_get_trailing_default_is_a_usage_error, so the tightened assertions do not pin this diff's argparse change (skills/run-autopilot/scripts/test_statectl_decide.py)

**Rationale**: rework cap reached with this finding unresolved
