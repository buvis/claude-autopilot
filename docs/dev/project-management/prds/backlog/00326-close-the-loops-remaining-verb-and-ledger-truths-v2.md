---
catchup: run
design: skip
default_model: sonnet
model_tier_rationale: seven small exact fixes in known files, each with a named fail-first test
---

# Close the loop's remaining verb and ledger truths (v2)

Source: `docs/dev/project-management/audit-results/agoge-2026-10-15.md` packets 9, 16, 17, 18; the PRD 00312 cycle-1 deferred ledger (the hedged tracon test, the doc-contract sweep escape); batch 202610141430's `loop-metrics.jsonl` (the fast-track rows and the stall attribution); the stub minting of 00314-00316. Line numbers are from HEAD 807ed12b; earlier PRDs of this batch edit `__main__.py` and `triage.py` (00321 adds a `cap_regression` branch to `qualifies`), so the symbols anchor and the numbers may have moved.

## Problem

Seven truths the loop still gets wrong. (1) `_has_control_char` (`skills/run-autopilot/cli/selection.py:48-49`) checks only code points below U+0020 and U+007F, so a backlog name holding U+0085 or U+2028 passes `selectable` (`skills/run-autopilot/cli/selection.py:52-67`), `enter` selects it, and `write-brief` renders it raw: `str.splitlines()` on the brief shows a forged `## Read next` at line 8 ahead of the real one (packet 9). (2) `USAGE` (`skills/run-autopilot/cli/statectl.py:506`) lists neither `decide` nor `get --default`, and `_dispatch` (`skills/run-autopilot/scripts/statectl.py:132-141`) finds `--default` by position: flag-first order returns the default even when the key exists, a malformed path returns the default instead of the usage error because `_run_get_with_default` (`skills/run-autopilot/scripts/statectl.py:113-129`) catches `UsageError` for both, and a trailing `--default` raises IndexError (packet 16). (3) `_run_markers` (`skills/run-autopilot/cli/__main__.py:1906-1919`) resolves the store through `_walk_up_or_exit` (`skills/run-autopilot/cli/__main__.py:286-296`), whose message tells the user to pass `--state`, which the verb rejects (packet 17); the walk follows the physical cwd through a symlink and past a nested repository's root, so `markers --clear` from one checkout cleared another store's `park-requested` and named no store in its output (packet 18). (4) `test_wrapper_alive_script_requires_root_arg` (`skills/run-autopilot/scripts/tracon/test_discovery.py:1652-1667`) asserts `"usage" in stderr or "root" in stderr`, so either outcome passes (00312 ledger, 3/4); `_check_line` (`skills/run-autopilot/cli/test_doc_contract.py:71-94`) catches a bare positional only as `<...>` text outside brackets, so a documented invocation carrying `[<review-file>]` passes the sweep (00312 sweep escape). (5) The fast-track item row written by `main` (`skills/fast-track/scripts/record_item.py:69-93`) takes `--started` from the session's own memory: for 00306 the session passed 1760486400 (2025-10-15T00:00Z, a year early), giving `wall_secs` 31538728, and `--cost` was passed on none of the batch's three item rows. (6) `_metrics_line` (`skills/run-autopilot/cli/loop.py:145-179`) stamps the session row with `decision["prd"]`, the PRD the loop decided on after the session exited; when a session parks its PRD and the loop selects the next one, the row carries the next PRD: 00306's 77-minute, $25 build session is the first `00307` row of the batch, so the ledger credits 00307 with a session it never ran and 00306 with none. (7) `qualifies` (`skills/run-autopilot/cli/triage.py:156-162`) mints a stub for every open CRITICAL/HIGH ledger row with no PRD owner, including `review-critical` rows whose `action` is `fix in cycle 1 rework`: 00314, 00315 and 00316 were minted for three such rows of 00307 after its cycle 2 had recorded the replay green and downgraded the test finding, and yesterday's triage closed 00297-00299 for the same reason. A fixed finding's audit row is not open work: if the fix failed, the next cycle raises it again as its own row, and if the cap is reached with it standing, the `cap_critical` stall mints.

## Solution

(1) `_has_control_char` becomes `_has_line_break_or_control`: true when `len(name.splitlines()) > 1` or any character is in Unicode category Cc. (2) `_dispatch` parses `get` with argparse (`get <path> [--default <json>]` in either order); `parse_path` runs before any lookup so a malformed path is still the usage error; the default applies only when `get_value` raises for a missing key; `USAGE` lists `decide` and `get --default`. (3) `markers` accepts `--state <state.json>` like every other verb; without it the walk stops at `git rev-parse --show-toplevel` of the cwd, and the JSON output gains `"store": "<autopilot dir>"`. (4) The tracon test asserts `usage` on stderr and that the usage names `root`; `_check_line` also rejects a `<...>` placeholder inside brackets that is not preceded by a `--flag `. (5) `record_item.py` refuses a `--started` more than 24 hours before `ts_end` or in the future (exit 2, naming the value) and reads `docs/dev/tmp/fast-track-started` (one epoch line, written by the lane at item start) when `--started` is omitted; `skills/fast-track/references/lane-dispatch.md` names both. (6) `_append_metrics` (`skills/run-autopilot/cli/loop.py:307-345`) receives the PRD the session was launched with; `_metrics_line` stamps that as `prd` and the decision's PRD as `prd_end`. (7) `qualifies` returns false for a `review-critical` row whose `action` starts with `fix in cycle`.

## Requirements

### Must have
- A backlog name holding U+0085 or U+2028 is not selectable; a name with one line and no Cc character still is.
- `statectl.py <state> get batch.id --default null` and `get --default null batch.id` both print the stored value; `get batch..id --default 7` exits 1 with the usage error; `get batch.id --default` exits 1 with a usage error and no traceback; `statectl.py --help` names `decide` and `get --default`.
- `autopilot markers --state <state.json> --check handoff-requested` works from any cwd; without `--state`, a store above the cwd's git toplevel is never used; the output JSON carries `store`.
- The tracon test fails against a script that prints only `root` without `usage`; `_check_line` raises on `[<review-file>]`.
- `record_item.py --started <epoch a year old>` exits 2; with `--started` omitted and `docs/dev/tmp/fast-track-started` present, the row's `ts_start` is that value.
- A session row written after a stall carries the launched PRD as `prd` and the decision's PRD as `prd_end`.
- `mint-stubs` mints nothing for a `review-critical` row with `action: fix in cycle 1 rework`; a `cap-overflow` HIGH row still mints.
- CHANGELOG `[Unreleased]` Fixed entries under **run-autopilot** and **fast-track**.

### Nice to have
- None.

## Implementation

### Module: selection-names
- **Location**: `skills/run-autopilot/cli/selection.py` (`_has_control_char`, `selectable`)
- **Responsibility**: no selected name can forge a brief section
- **Exports**: `selectable()`
- New symbols: `_has_line_break_or_control`

### Module: statectl-get
- **Location**: `skills/run-autopilot/scripts/statectl.py` (`_dispatch`, `_run_get_with_default`), `skills/run-autopilot/cli/statectl.py` (`USAGE`)
- **Responsibility**: `get --default` is discoverable and never masks a present key or a malformed path
- **Exports**: `_dispatch()`

### Module: markers-state
- **Location**: `skills/run-autopilot/cli/__main__.py` (`_run_markers`, `_add_markers`), `skills/run-autopilot/cli/markers.py`
- **Responsibility**: the verb takes `--state`, stops at the git toplevel and names its store
- **Exports**: `check()`, `clear()` (unchanged)

### Module: test-truth
- **Location**: `skills/run-autopilot/scripts/tracon/test_discovery.py` (`test_wrapper_alive_script_requires_root_arg`), `skills/run-autopilot/cli/test_doc_contract.py` (`_check_line`)
- **Responsibility**: the two tests bind to their rule
- **Exports**: none

### Module: ledger-truth
- **Location**: `skills/fast-track/scripts/record_item.py` (`main`, `parse_args`), `skills/fast-track/references/lane-dispatch.md`, `skills/run-autopilot/cli/loop.py` (`_metrics_line`, `_append_metrics`), `skills/run-autopilot/cli/triage.py` (`qualifies`)
- **Responsibility**: every ledger row names the right PRD and a plausible start, and no stub is minted for a fixed finding
- **Exports**: `qualifies()`, `main()` (unchanged signatures)
- New symbols: `STARTED_FILE`, `prd_end`

### Module: truth-tests
- **Location**: `skills/run-autopilot/cli/test_selection.py`, `skills/run-autopilot/scripts/test_statectl_decide.py`, `skills/run-autopilot/cli/test_markers.py`, `skills/fast-track/scripts/test_record_item.py`, `skills/run-autopilot/cli/test_loop_metrics.py`, `skills/run-autopilot/cli/test_triage.py`
- **Responsibility**: one fail-first test per truth
- **Exports**: none
- New symbols: `test_c1_and_line_separator_names_are_not_selectable`, `test_get_default_never_masks_a_present_key`, `test_get_default_flag_first_order_works`, `test_get_default_malformed_path_is_a_usage_error`, `test_get_trailing_default_is_a_usage_error`, `test_usage_names_decide_and_get_default`, `test_markers_accepts_state_flag`, `test_markers_walk_stops_at_the_git_toplevel`, `test_markers_output_names_the_store`, `test_started_a_year_old_exits_two`, `test_started_file_is_read_when_flag_absent`, `test_session_row_keeps_the_launched_prd_after_a_stall`, `test_fixed_in_rework_critical_rows_do_not_mint`

### Dependencies
- truth-tests: No dependencies (foundation)
- selection-names: Depends on [truth-tests]
- statectl-get: Depends on [truth-tests]
- markers-state: Depends on [truth-tests]
- test-truth: Depends on [truth-tests]
- ledger-truth: Depends on [truth-tests]

## Tasks

### Phase 0: Foundation
- [ ] Add the thirteen tests named under Implementation to their files (`test_c1_and_line_separator_names_are_not_selectable` to `skills/run-autopilot/cli/test_selection.py`; the five `get` and usage tests to `skills/run-autopilot/scripts/test_statectl_decide.py`; the three `markers` tests to `skills/run-autopilot/cli/test_markers.py`, the toplevel test using a nested `git init` and a symlink into a second store; the two `record_item.py` tests to `skills/fast-track/scripts/test_record_item.py`; `test_session_row_keeps_the_launched_prd_after_a_stall` to `skills/run-autopilot/cli/test_loop_metrics.py`; `test_fixed_in_rework_critical_rows_do_not_mint` to `skills/run-autopilot/cli/test_triage.py`), tighten `test_wrapper_alive_script_requires_root_arg` in `skills/run-autopilot/scripts/tracon/test_discovery.py` to require `usage`, and add a bracketed-positional case to the `_VALIDATOR_REJECTS` self-checks of `skills/run-autopilot/cli/test_doc_contract.py` - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_selection.py skills/run-autopilot/scripts/test_statectl_decide.py skills/run-autopilot/cli/test_markers.py skills/fast-track/scripts/test_record_item.py skills/run-autopilot/cli/test_loop_metrics.py skills/run-autopilot/cli/test_triage.py skills/run-autopilot/cli/test_doc_contract.py` reports the thirteen new tests and the new self-check failing at the task's base commit and no existing test failing.

### Phase 1: Core
- [ ] Implement `_has_line_break_or_control` in `skills/run-autopilot/cli/selection.py`, the argparse `get` in `_dispatch` of `skills/run-autopilot/scripts/statectl.py` with the `USAGE` lines in `skills/run-autopilot/cli/statectl.py`, and `--state`, the toplevel stop and the `store` key in `_add_markers` and `_run_markers` of `skills/run-autopilot/cli/__main__.py` (depends on: Phase 0) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_selection.py skills/run-autopilot/scripts/test_statectl_decide.py skills/run-autopilot/scripts/test_statectl.py skills/run-autopilot/cli/test_markers.py` passes.
- [ ] Fix `_check_line` in `skills/run-autopilot/cli/test_doc_contract.py`, add `STARTED_FILE`, the 24-hour and future refusals to `skills/fast-track/scripts/record_item.py` with the matching lines in `skills/fast-track/references/lane-dispatch.md`, pass the launched PRD into `_append_metrics` and stamp `prd` and `prd_end` in `_metrics_line` of `skills/run-autopilot/cli/loop.py`, and exclude rework-fix rows in `qualifies` of `skills/run-autopilot/cli/triage.py` (depends on: Phase 0) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_doc_contract.py skills/fast-track/scripts/test_record_item.py skills/run-autopilot/cli/test_loop_metrics.py skills/run-autopilot/cli/test_triage.py skills/run-autopilot/scripts/tracon/test_discovery.py` passes (`--with rich --with textual` added for the tracon file).

### Phase 2: Integration
- [ ] Add the CHANGELOG `[Unreleased]` Fixed entries: under **run-autopilot** one line for the selection, `get --default`, `markers --state`, session-row attribution and stub-minting fixes, and under **fast-track** one line for the `--started` refusal and the started file (depends on: Phase 1) - Acceptance: `rg -n 'prd_end|fast-track-started' CHANGELOG.md` prints two hits under `[Unreleased]`.

## Success Criteria

- The packet 9 backlog name is not selected and `write-brief` renders no forged section.
- The four `get` argument orders from packet 16 give the documented answers; `statectl.py --help` names both verbs.
- From a nested repository inside a store, `markers --clear park-requested` touches nothing above the nested toplevel and names the store it used.
- `record_item.py` refuses the 00306 timestamp; a replay of the 00306 session through `_metrics_line` stamps `prd` 00306 and `prd_end` 00307.
- `mint-stubs` over the batch 202610141430 ledger mints nothing for its three `review-critical` rows.
