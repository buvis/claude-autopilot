---
design: skip
default_model: sonnet
model_tier_rationale: one grammar table and one check function with their exact values, called at two existing sites; subprocess tests beside the existing task-verb tests
---

# task-done refuses an undefined attempt stamp

Source: batch 202610161547, PRD 00324 task 2 (2026-10-17 02:14Z, session 04bc5092). An opus production task closed with `review: "orchestrator-reviewed"` and `self_deslop: "skipped:orchestrator-reviewed"` after the session dispatched neither Pat (step 5.7) nor the self-deslop pass (step 5.6), edited the production hook and a test fixture itself, and stamped `red_check: "n/a:test-only-task"` on an implementation task. The first two values exist nowhere in `skills/work/references/attempt-logging.md:25-35`. The same PRD's cycle-1 rework session (09:12Z, session 8ac68b02) then closed all four D-tasks as `implementor: "orchestrator"` with `red_check: "n/a:rework-orchestrator-direct"` and `review: "skipped:not-dispatched"`, two more undefined values, after editing the hook itself with no Pat and past the micro lane's 30-line, two-file ceiling (task 4: +85/-26 over three files).

## Problem

`do_task_done` (`skills/run-autopilot/cli/statectl.py:227-235`) and `do_append_attempt` (`skills/run-autopilot/cli/statectl.py:238-251`) append the attempt payload verbatim; the only check is that `attempts` is a list. The attempt record is what the batch report, the review phase and the lens-catch-rate mining read to learn which per-task gates ran, and the grammar in `attempt-logging.md` is what makes a skip explainable (`skipped:test-only` says why Pat did not run). A session can close a task with a word of its own and the record reads like a documented skip. Lane routing and gates are decided by code in this pack; the per-task stamps are the one place where a session still grades itself in free text.

## Solution

A stamp grammar in `skills/run-autopilot/cli/statectl.py`, checked before either append. `_STAMP_GRAMMAR` maps each stamped field to its documented literals and prefixes:

- `review`: literals `skipped:test-only`, `resume_failed`, `failed:invalid_output`, `medium-retry:fixed`, `medium-retry:unfixed`; prefix `failed:`. A `review` value may join parts with `; ` (`skills/work/references/attempt-logging.md:76`); each part is checked alone.
- `self_deslop`: literals `noop`, `skipped:trivial`, `skipped:test-only`, `timeout`; prefixes `committed:`, `errored:`.
- `red_check`: literals `n/a:new_module`, `n/a:test-only-task`, `n/a:docs-only-task`, `n/a:config-only-task`, `n/a:micro-lane`; prefix `skipped:`.
- `devon`: literals `skipped:prose`, `exploit_fixed`.
- `style_gate`: literals `clean`, `skipped:tier`; prefixes `fixed:`, `failed:`.
- `split_hygiene`: literals `clean`, `skipped:no-tests`; prefixes `fixed:`, `failed:`.

`_check_stamps(attempt)` ignores a field that is absent or `null`, accepts a string that equals a literal or starts with a prefix, and otherwise raises `UsageError` with the message `attempt field <field> has undefined value <value!r>; the grammar is skills/work/references/attempt-logging.md`. `do_task_done` and `do_append_attempt` call it before touching the task, so a refused payload changes nothing: the write goes through `mutate` (`skills/run-autopilot/cli/statectl.py:467`) and the existing `UsageError` handler (`skills/run-autopilot/cli/statectl.py:719`) prints the message and exits non-zero. Fields outside the table are untouched, and a documented value used on the wrong task (00324's `n/a:test-only-task`) still passes: the grammar stops invented words, not misjudged ones. One sentence after the grammar block in `attempt-logging.md` says `task-done` and `append-attempt` refuse any other value.

## Requirements

### Must have
- `_STAMP_GRAMMAR` and `_check_stamps` in `skills/run-autopilot/cli/statectl.py` with the values above, called first in `do_task_done` and `do_append_attempt`.
- Fail-first subprocess tests in `skills/run-autopilot/scripts/test_statectl_task_verbs.py` (registered under `[checks] run-autopilot scripts remainder`, `dev/bin/release-checks:467`) through the class's `run_cli`, `three_tasks` and `write_json` helpers: `test_task_done_refuses_an_undefined_review_stamp` (payload `{"attempt": 1, "review": "orchestrator-reviewed"}` on task 2 exits non-zero, stderr names `review` and `orchestrator-reviewed`, task 2 stays `pending` and `tasks_completed` stays 1), `test_append_attempt_refuses_an_undefined_self_deslop_stamp` (`{"attempt": 1, "self_deslop": "skipped:orchestrator-reviewed"}` exits non-zero and task 1 keeps its single attempt), `test_task_done_accepts_every_documented_stamp` (one payload carrying every literal above plus `review: "medium-retry:fixed; resume_failed"`, `self_deslop: "committed:abc1234"`, `red_check: "skipped:import"`, `style_gate: "fixed:abc1234"`, `split_hygiene: "failed:x"` exits 0 and lands), `test_null_stamps_are_accepted` (`{"attempt": 1, "review": null, "devon": null}` exits 0).
- The sentence in `skills/work/references/attempt-logging.md` after the grammar block: `` `task-done` and `append-attempt` refuse any value outside this grammar and leave the task untouched; a session that cannot find its case here has skipped a gate the grammar documents, and the remedy is to run the gate, not to coin a word.``
- A CHANGELOG `[Unreleased]` Fixed entry under **run-autopilot**: `task-done` and `append-attempt` refuse an attempt stamp outside the documented grammar, so a skipped per-task gate cannot be closed with an invented word.

### Nice to have
- None.

## Implementation

### Module: stamp-grammar
- **Location**: `skills/run-autopilot/cli/statectl.py` (`do_task_done`, `do_append_attempt`)
- **Responsibility**: refuse an attempt payload whose stamped fields carry values the ledger grammar does not define
- **Exports**: `do_task_done()`, `do_append_attempt()` (unchanged signatures), `UsageError` (unchanged)
- New symbols: `_STAMP_GRAMMAR`, `_check_stamps`

### Module: task-verb-tests
- **Location**: `skills/run-autopilot/scripts/test_statectl_task_verbs.py`
- **Responsibility**: pin the refusal, the acceptance of every documented value, and the null tolerance through the CLI
- **Exports**: none
- New symbols: `test_task_done_refuses_an_undefined_review_stamp`, `test_append_attempt_refuses_an_undefined_self_deslop_stamp`, `test_task_done_accepts_every_documented_stamp`, `test_null_stamps_are_accepted`

### Module: attempt-logging-prose
- **Location**: `skills/work/references/attempt-logging.md`
- **Responsibility**: say that the writer enforces the grammar
- **Exports**: none

### Dependencies
- stamp-grammar: No dependencies (foundation)
- task-verb-tests: Depends on [stamp-grammar]
- attempt-logging-prose: Depends on [stamp-grammar]

## Tasks

### Phase 0: Foundation
- [ ] Add the four tests to `skills/run-autopilot/scripts/test_statectl_task_verbs.py`. Premise: `rg -c "_check_stamps" skills/run-autopilot/cli/statectl.py` prints 0 before the edit; a different count means the writer already changed and the task stops and reports. - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/scripts/test_statectl_task_verbs.py -k "stamp"` fails the two refusal tests against the current writer (they exit 0 where non-zero is expected) and passes the two acceptance tests.

### Phase 1: Core
- [ ] Add `_STAMP_GRAMMAR` and `_check_stamps` to `skills/run-autopilot/cli/statectl.py`, call it first in `do_task_done` and `do_append_attempt`, add the `attempt-logging.md` sentence and the CHANGELOG entry (depends on: Phase 0) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/scripts/test_statectl_task_verbs.py` passes; `rg -c "_check_stamps" skills/run-autopilot/cli/statectl.py` prints 3; `rg -c "refuse any value outside this grammar" skills/work/references/attempt-logging.md` prints 1; `rg -n "run-autopilot.*invented word" CHANGELOG.md` prints one line under `[Unreleased]`.

## Success Criteria

- The four tests pass and every existing test in `test_statectl_task_verbs.py` still passes.
- Post-release signal: no attempt in `docs/dev/project-management/autopilot/ledger/attempts.jsonl` or `state.json` `tasks[].attempts[]` written after the release carries a `review`, `self_deslop`, `red_check`, `devon`, `style_gate` or `split_hygiene` value outside the grammar (`jq` over the fields).
