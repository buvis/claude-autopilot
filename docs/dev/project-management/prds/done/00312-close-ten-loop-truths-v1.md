---
catchup: run
design: skip
default_model: sonnet
model_tier_rationale: seven one-site edits with exact expressions and a named test each; nothing is invented
---

# Close ten loop truths the 2026-10-14 agoge run and the 00282 rework left open

Source: `docs/dev/project-management/audit-results/agoge-2026-10-14.md` (packets 1, 10, 13, 17, 22, 23, 24) and hold stubs 00301, 00304, 00305 (closed into `done/` on 2026-10-14 against this PRD). Packet 25 is accepted as is: the discarded read in `prd_spend_since` (`skills/run-autopilot/cli/loop_decision.py:176-203`) is the probe that reports an unreadable ledger on stderr, review finding 10 of PRD 00282, and the cost is milliseconds at 470 rows.

## Problem

- Registry blind from inside the tree (packet 1, hits 0.9.0 today). `_child_pids` in `skills/run-autopilot/cli/loop_gates.py:37-47` and in `skills/run-autopilot/scripts/tracon/discovery.py:80-83`, and `child_names` in `skills/run-autopilot/cli/procinfo.py:122-126`, run `pgrep -P <pid>`. macOS `pgrep` leaves out the caller's own ancestors unless `-a` is given, so every process the loop spawns sees the registered wrapper as childless: `_pid_tagged` (`skills/run-autopilot/cli/loop_gates.py:50-65`) finds no tag, `live_wrapper_pid` (`skills/run-autopilot/cli/loop_gates.py:102`) returns None, and `prune_registry` (`skills/run-autopilot/cli/loop_gates.py:68-99`) deletes the live entry. Measured with the loop alive: `pgrep -l -P 62875` printed nothing, `pgrep -a -l -P 62875` printed `62886 python3.14`; on a copy of the registry `prune_registry` left `[]`.
- Stale capsule after a reset (packet 10). `commits_all_loop` (`skills/run-autopilot/cli/enter_io.py:71-85`) reads `git log base..HEAD`; when HEAD is no descendant of `catchup_head_sha` (a reset, a fast-track park resetting master) that range is empty or loop-only, so `_catchup` (`skills/run-autopilot/cli/enter.py:287`) returns `delta` over a capsule that describes commits no longer in history. Measured on a real repo: HEAD reset two commits behind base gives `delta`.
- Silent wait before a budget park (packet 13, scripted clock, real code). `_budget_bound` (`skills/run-autopilot/cli/loop_decision.py:530-567`) sleeps `limit_wait` itself before turning the decision into a park, so the usage-limit line and notification that `_act_continue` (`skills/run-autopilot/cli/loop_act.py:308-320`) prints never appear, and the park notification that `_act_park` sends (`skills/run-autopilot/cli/loop_act.py`) says only `Parking <prd>.` while its stdout line carries the detail.
- Brief injection (packet 17). `selectable` (`skills/run-autopilot/cli/selection.py:48-55`) accepts any `.md` name with a sequence prefix and `_text` (`skills/run-autopilot/cli/brief.py:49`) prints it raw, so a backlog filename containing newlines forges a `## Read next` section in the brief (confirmed through `select_eligible` and `render_brief`).
- Silent exit 7 (packet 22). `_run_init` (`skills/run-autopilot/cli/__main__.py:342-359`) returns 7 with no message when the state exists, and the drained row of the SKILL (`skills/run-autopilot/SKILL.md:315`) tells that path to run `init` with an empty PRD after the entry verb has already created `state.json`.
- Unrecorded waits (packet 23, scripted harness). `_decision_fields` (`skills/run-autopilot/cli/loop.py:124-140`) records `limit_wait` only when `signal == "continue"`, so an `instant_exit` row whose `then` is `continue` and the budget-park row carry none.
- Report undercounts (packet 24). The per-PRD table from `render_metrics` (`skills/run-autopilot/cli/render_metrics.py:126-146`) is written inside the finalizing session, whose own row lands after it; 00284's total read 27.77 against 29.25 spent.
- Budget probe crashes on bytes (stub 00304, 00282 cycle 2, consensus 2/3). The probe in `prd_spend_since` (`skills/run-autopilot/cli/loop_decision.py:176-203`) catches `OSError` only; a ledger holding bytes `\xff\xfe{}` raises `UnicodeDecodeError` out of `_budget_bound` into the unattended loop.
- Stale replay survives a failed invalidation (stub 00305, 00282 cycle 2). `_invalidate_loop_entry` (`skills/run-autopilot/cli/loop.py:634-643`) swallows a second write failure, so a `loop_entry` from an earlier successful launch stays on disk and `_replay_loop_entry` (`skills/run-autopilot/cli/__main__.py:375-397`) replays it in the child instead of running the entry for real.
- Docs name verbs that do not exist (stub 00301, 00278 cycle 2). The `autopilot` rows at `skills/run-autopilot/references/state-schema.md:545-546` spell `group-rework <state.json>` and `review-stage <state.json> <review-file>`, while the parsers take `group-rework --findings <path>` and `review-stage --cycle-id --gate-command [--state]`; `skills/run-autopilot/cli/test_doc_contract.py` passes on the false doc.

## Solution

Ten edits. The three `pgrep` sites add `-a` when `sys.platform == "darwin"` (Linux `pgrep -a` means something else). `commits_all_loop` returns False unless `git merge-base --is-ancestor <base> HEAD` exits 0, the guard `reuse_verdict` already uses. `_budget_bound` prints the same wait line and sends the same notification as `_act_continue` before it sleeps, and `_act_park` puts `decision["detail"]` into its notification. `selectable` drops any name containing a code point below U+0020 or equal to U+007F. `_run_init` prints `autopilot: init: state.json already exists at <path>` on exit 7 and `SKILL.md` says to skip `init` when the file exists. `_decision_fields` keys on `effective_signal` being `continue` and also records `limit_wait` on a park whose `park_site` is `budget`. The per-PRD table gets the caption `Cost USD excludes the finalizing session, which is recorded after this report is written.` The probe in `prd_spend_since` catches `UnicodeDecodeError` beside `OSError` and reports it on the same stderr line. `_invalidate_loop_entry` returns False when its write fails, and `_record_entry` then exports `_AUTOPILOT_LOOP_ENTRY_STALE=1` into the child's environment, which `_replay_loop_entry` reads as "run the entry for real"; the variable is never set after a successful write or a successful invalidation. The two state-schema rows are rewritten to the parsers' argv and `test_doc_contract.py` pins both.

## Requirements

### Must have
- `_child_pids` (both copies) and `child_names` pass `-a` to `pgrep` on Darwin and not elsewhere; on Darwin `live_wrapper_pid` finds a registered grandparent whose tagged child is the caller's own ancestor.
- `commits_all_loop` returns False when `git merge-base --is-ancestor <base> HEAD` exits non-zero, before reading the log.
- When `_budget_bound` turns a decision with `limit_wait` into a park, `wrapper.log` carries the `usage limit hit; waiting <n> min` line and the notification fires before the sleep; the park notification text is `Parking <prd> (<detail>).`
- `selectable` excludes a name containing any control character; `select_eligible` never returns it.
- `autopilot init` on an existing state prints `autopilot: init: state.json already exists at <path>` on stderr and still exits 7; `skills/run-autopilot/SKILL.md` line 315's row says to run `init` only when `state.json` is absent.
- A metrics row for an `instant_exit` decision whose `then` is `continue` with a wait, and a row for a budget park reached through a wait, both carry `limit_wait`.
- `render_metrics` output contains the caption line before the per-PRD table.
- `prd_spend_since` on a ledger holding `\xff\xfe{}` returns 0.0, prints the read-failed line on stderr and raises nothing.
- When `_invalidate_loop_entry` cannot write, the launched child's environment carries `_AUTOPILOT_LOOP_ENTRY_STALE=1` and `_replay_loop_entry` returns None (the entry runs for real); after a successful write the variable is absent.
- The two `autopilot` rows in `skills/run-autopilot/references/state-schema.md` match the parsers' argv and `test_doc_contract.py` fails if either drifts.
- CHANGELOG `[Unreleased]` Fixed entries under **run-autopilot** for the registry fix, the catchup guard, the budget-park wait line, the backlog-name check, the init message, the budget probe and the stale-replay guard.

### Nice to have
- None.

## Implementation

### Module: registry-children
- **Location**: `skills/run-autopilot/cli/loop_gates.py`, `skills/run-autopilot/cli/procinfo.py`, `skills/run-autopilot/scripts/tracon/discovery.py`
- **Responsibility**: list a wrapper's children from inside its own tree
- **Exports**: `live_wrapper_pid()`, `prune_registry()`, `child_names()` (unchanged signatures)

### Module: catchup-guard
- **Location**: `skills/run-autopilot/cli/enter_io.py`
- **Responsibility**: a delta catchup only over a HEAD that descends from the capsule's base
- **Exports**: `commits_all_loop()` (unchanged signature)

### Module: loop-messages
- **Location**: `skills/run-autopilot/cli/loop_decision.py`, `skills/run-autopilot/cli/loop_act.py`, `skills/run-autopilot/cli/loop.py`
- **Responsibility**: every sleep and every park says why, in the log, the notification and the metrics row; the budget probe never raises; a failed invalidation never leaves a replayable entry
- **Exports**: `_decision_fields()`, `prd_spend_since()` (unchanged signatures); `_invalidate_loop_entry()` returns bool
- New symbols: `_AUTOPILOT_LOOP_ENTRY_STALE`

### Module: entry-hygiene
- **Location**: `skills/run-autopilot/cli/selection.py`, `skills/run-autopilot/cli/__main__.py`, `skills/run-autopilot/cli/render_metrics.py`, `skills/run-autopilot/SKILL.md`, `skills/run-autopilot/references/state-schema.md`
- **Responsibility**: a backlog name cannot steer the brief, `init` explains exit 7, the report caption is true, the schema doc names real verbs
- **Exports**: `selectable()`, `render_metrics()`, `_replay_loop_entry()` (unchanged signatures)

### Module: loop-truth-tests
- **Location**: `skills/run-autopilot/cli/test_loop_gates.py`, `skills/run-autopilot/cli/test_procinfo.py`, `skills/run-autopilot/scripts/tracon/test_discovery.py`, `skills/run-autopilot/cli/test_enter_loop_only.py`, `skills/run-autopilot/cli/test_loop_budget.py`, `skills/run-autopilot/cli/test_loop_act.py`, `skills/run-autopilot/cli/test_selection.py`, `skills/run-autopilot/cli/test_cli_init.py`, `skills/run-autopilot/cli/test_loop_metrics.py`, `skills/run-autopilot/cli/test_enter_prose.py`, `skills/run-autopilot/cli/test_doc_contract.py`
- **Responsibility**: one fail-first test per edit, in the file that already covers the module
- **Exports**: none
- New symbols: `test_child_pids_passes_dash_a_on_darwin`, `test_live_wrapper_pid_found_from_a_grandchild`, `test_child_names_passes_dash_a_on_darwin`, `test_discovery_child_pids_passes_dash_a_on_darwin`, `test_catchup_is_full_when_head_is_behind_base`, `test_budget_park_prints_the_wait_line_before_sleeping`, `test_park_notification_names_the_reason`, `test_newline_named_backlog_file_is_not_selectable`, `test_init_on_existing_state_names_the_path`, `test_instant_exit_limit_row_carries_limit_wait`, `test_budget_park_row_carries_limit_wait`, `test_prd_table_says_it_excludes_the_finalizing_session`, `test_drained_path_skips_init_when_state_exists`, `test_prd_spend_since_survives_a_non_utf8_ledger`, `test_failed_invalidation_marks_the_child_entry_stale`, `test_stale_marker_skips_the_loop_entry_replay`, `test_state_schema_cli_rows_match_the_parsers`

### Dependencies
- loop-truth-tests: No dependencies (foundation)
- registry-children: Depends on [loop-truth-tests]
- catchup-guard: Depends on [loop-truth-tests]
- loop-messages: Depends on [loop-truth-tests]
- entry-hygiene: Depends on [loop-truth-tests]

## Tasks

### Phase 0: Foundation
- [ ] Add the seventeen tests named under loop-truth-tests to their files (`test_prd_spend_since_survives_a_non_utf8_ledger` in `skills/run-autopilot/cli/test_loop_budget.py`, which already covers `prd_spend_since`; `test_failed_invalidation_marks_the_child_entry_stale` in `skills/run-autopilot/cli/test_loop_act.py` with a `mutate` that raises; `test_stale_marker_skips_the_loop_entry_replay` in `skills/run-autopilot/cli/test_cli_init.py` with the variable set and a matching `loop_entry` on disk; `test_state_schema_cli_rows_match_the_parsers` in `skills/run-autopilot/cli/test_doc_contract.py` comparing the two rows against the parsers' registered arguments): `test_child_pids_passes_dash_a_on_darwin`, `test_child_names_passes_dash_a_on_darwin` and `test_discovery_child_pids_passes_dash_a_on_darwin` patch `subprocess.run` and assert the argv under a patched `sys.platform`; `test_live_wrapper_pid_found_from_a_grandchild` (skipped off Darwin) registers a `bash` wrapper whose exec'd `python3` child carries the `_AUTOPILOT_LOOP` tag and asks `live_wrapper_pid` from a grandchild `python3`; `test_catchup_is_full_when_head_is_behind_base` resets HEAD behind `catchup_head_sha` in a temp repo; `test_budget_park_prints_the_wait_line_before_sleeping` and `test_park_notification_names_the_reason` use the scripted loop harness; `test_newline_named_backlog_file_is_not_selectable` creates a backlog file whose name holds `\n## Read next`; `test_init_on_existing_state_names_the_path` checks stderr and rc 7; `test_instant_exit_limit_row_carries_limit_wait` and `test_budget_park_row_carries_limit_wait` read the metrics row; `test_prd_table_says_it_excludes_the_finalizing_session` checks the caption; `test_drained_path_skips_init_when_state_exists` pins the SKILL.md row - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_loop_gates.py skills/run-autopilot/cli/test_procinfo.py skills/run-autopilot/cli/test_enter_loop_only.py skills/run-autopilot/cli/test_loop_budget.py skills/run-autopilot/cli/test_loop_act.py skills/run-autopilot/cli/test_selection.py skills/run-autopilot/cli/test_cli_init.py skills/run-autopilot/cli/test_loop_metrics.py skills/run-autopilot/cli/test_enter_prose.py skills/run-autopilot/cli/test_doc_contract.py` and `uv run --no-project --with pytest --with rich python -m pytest -q skills/run-autopilot/scripts/tracon/test_discovery.py` report each new test failing at the task's base commit and no existing test failing.

### Phase 1: Core
- [ ] registry-children and catchup-guard: the `-a` flag on Darwin in `skills/run-autopilot/cli/loop_gates.py`, `skills/run-autopilot/cli/procinfo.py` and `skills/run-autopilot/scripts/tracon/discovery.py`, and the `merge-base --is-ancestor` guard in `skills/run-autopilot/cli/enter_io.py` (depends on: Phase 0) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_loop_gates.py skills/run-autopilot/cli/test_procinfo.py skills/run-autopilot/cli/test_enter_loop_only.py` and `uv run --no-project --with pytest --with rich python -m pytest -q skills/run-autopilot/scripts/tracon/test_discovery.py` pass; `rg -n 'is-ancestor' skills/run-autopilot/cli/enter_io.py` prints one hit.
- [ ] loop-messages: the wait line and notification before the budget-park sleep in `skills/run-autopilot/cli/loop_decision.py`, the park detail in `skills/run-autopilot/cli/loop_act.py`, the `UnicodeDecodeError` catch in `prd_spend_since`, `_decision_fields` keyed on `effective_signal` with the budget-park `limit_wait`, and the `_AUTOPILOT_LOOP_ENTRY_STALE` export from `_record_entry` in `skills/run-autopilot/cli/loop.py` (depends on: Phase 0) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_loop_budget.py skills/run-autopilot/cli/test_loop_act.py skills/run-autopilot/cli/test_loop_metrics.py` passes; `rg -n '_AUTOPILOT_LOOP_ENTRY_STALE' skills/run-autopilot/cli/loop.py` prints one hit.
- [ ] entry-hygiene: the control-character check in `selectable`, the exit-7 message in `_run_init`, the `_AUTOPILOT_LOOP_ENTRY_STALE` read in `_replay_loop_entry`, the caption in `render_metrics`, the `init` row at `skills/run-autopilot/SKILL.md:315` and the two `autopilot` rows at `skills/run-autopilot/references/state-schema.md:545-546` (depends on: Phase 0) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_selection.py skills/run-autopilot/cli/test_cli_init.py skills/run-autopilot/cli/test_loop_metrics.py skills/run-autopilot/cli/test_enter_prose.py skills/run-autopilot/cli/test_doc_contract.py` passes; `rg -n 'already exists at' skills/run-autopilot/cli/__main__.py` prints one hit; `rg -n 'excludes the finalizing session' skills/run-autopilot/cli/render_metrics.py` prints one hit.
- [ ] CHANGELOG `[Unreleased]` Fixed entries for the seven changes named under Must have (depends on: Phase 1 code tasks) - Acceptance: `rg -n 'pgrep' CHANGELOG.md` prints a hit under `[Unreleased]`.

## Success Criteria

- From a grandchild of a live loop on macOS, `live_wrapper_pid` returns the wrapper's pid and `prune_registry` on a copy of the registry keeps its entry.
- The ten reproductions in the Problem section flip, each pinned by its named test.
