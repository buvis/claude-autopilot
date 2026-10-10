---
design: run
default_model: opus
model_tier_rationale: invented contracts (a no-change sentinel in the shared state.transaction, a new autopilot verify verb and its exit codes, run_gate's dirty rule) plus an equivalence duty on the reuse check; a wrong turn certifies a red tree as green
---

# Trust only real gate runs

## Overview

### Problem Statement

The second agoge run of 2026-10-07 (`docs/dev/project-management/audit-results/agoge-2026-10-07-2.md`,
packets 4, 5, 6, 7, 9, 10, 11, 12, 20; all confirmed; decisions in its `## Minutes`,
settled with the operator) shows that `last-verification.json` can certify a tree
no gate ever passed, and that the gate still runs far more often than it must:

- **4 (HIGH):** `verification.run_gate` stamps HEAD's sha on a run made over
  uncommitted product edits. Once the edits are dropped, `review-stage` reuses
  the green record for a HEAD that fails.
- **5 (HIGH):** nothing ties the record to a gate run. `skills/work/references/final-verification.md:105`
  tells sessions to hand-write it, so a wrong or forged file skips the gate.
- **6 (MEDIUM):** `_ancestor_and_clean` lists changes with `git log --name-only`,
  which shows nothing for a merge commit's own resolution edits.
- **7 (MEDIUM):** a `review-close` that loses a race sees "already applied" inside
  `state.transaction`, which still rewrites `state.json.bak` and loses the
  pre-apply rollback point (29 of 30 trials).
- **9 (MEDIUM):** batch `202610071409` ran the ~206 s gate 15 times (51.6 min);
  reuse saved one. Causes: a hand-written record (short sha, no counts), Blake
  rerunning the suite after `review-stage` already staged its Tests line, and
  agents rerunning just to redirect output to a file.
- **10 (MEDIUM):** reuse needs the exact command string, so `bash dev/bin/release-checks`
  vs `dev/bin/release-checks` costs a full rerun.
- **11 (LOW):** status runs without `--untracked-files=all` and the path listing
  without `-z`: a repo with `status.showUntrackedFiles=no` reuses over an
  untracked product file (false pass), an untracked store dir collapses to
  `?? docs/`, and a non-ASCII store filename comes back quoted (false stales).
  PRD 00266's task asked for `--relative -- .` and `-uall`; the 00266 review kept
  the toplevel-relative form and never logged that.
- **12 (LOW):** `rework_groups._merge_pair` grows cubically (500 rows 8 s, 1,000 rows 63 s).
- **20 (LOW):** the `test_release_checks_counts.py` comment's file counts drift.

PRD 00266 (`prds/done/00266-bind-gate-reuse-to-the-command-and-renames-v1.md`)
bound reuse to the command, a full sha and both rename ends. This PRD makes
`run_gate` the only writer, makes it refuse to record a dirty tree, and closes
the remaining reuse gaps.

### Target Users

The autopilot loop and its operator: build sessions running the work phase,
review sessions running `review-stage`, and reviewers (Blake) reading the
staged Tests line.

### Success Metrics

- Every test named in the task Acceptance lines passes and fails at base.
- No prose in `skills/` tells a session to write `last-verification.json`.
- A gate run on a tree dirty outside the store never yields a record.

## Functional Decomposition

### Capability: Honest gate record

`last-verification.json` describes a committed tree that a real `run_gate` call checked.

#### Feature: Dirty-tree refusal (packet 4)
- **Description**: `run_gate` writes no record when the tree is dirty outside the store.
- **Inputs**: `cwd`; `git status --porcelain=1 -z --untracked-files=all` before the run and again after it.
- **Outputs**: result dict gains `"recorded": bool` and `"dirty": bool`.
- **Behavior**: a new helper `_dirty_outside_store(repo_root) -> bool` runs `rev-parse --show-prefix` and the status call, and reuses `_iter_porcelain_z_records` and `_dirty_path_is_in_store`. Any git failure (including a cwd outside a git repo) counts as dirty. `run_gate` checks before spawning and after reaping; it writes the record only when both checks are clean and a summary line parsed. **Chosen: no record, not a `dirty: true` stamp.** A stamp adds a field every reader must honor, and the prose reader in `review-work-completion/SKILL.md` step 6 matches the record by sha alone, so it would reuse a stamped record. No record needs no reader change: an absent record is already `stale`. An older record from a clean run stays; it still describes its own committed tree, and `reuse_verdict` re-checks the tree at reuse time.

#### Feature: Sole writer (packets 5, 9a)
- **Description**: only `verification.run_gate` writes the record; sessions call a CLI verb.
- **Inputs**: `autopilot verify --gate-command CMD [--repo-root PATH] [--cycle N] [--log PATH]`.
- **Outputs**: one JSON line: run_gate's result plus `"sha"` (HEAD) and `"log"` (the log path). Exit 0 when the gate exited 0 and did not time out; 1 when it exited non-zero or timed out; 2 when HEAD cannot be resolved or the gate cannot be spawned or the log cannot be written (OSError).
- **Behavior**: resolves HEAD with `git rev-parse HEAD` in the repo root (default cwd), default log path `docs/dev/tmp/gate-<sha[:7]>.log`, calls `run_gate(command, repo_root, sha, cycle, log_path=...)`. `final-verification.md`, `work/SKILL.md` step 7, `lane-solo.md` § 3 and `review-work-completion/SKILL.md` step 6's fallback run the full suite through this verb and never write the file. The record's JSON shape stays documented in `final-verification.md` as what the verb writes.

#### Feature: Gate log (packet 9c)
- **Description**: one gate run leaves its full output in a file, so nobody reruns to read it.
- **Inputs**: `run_gate(..., log_path: Path | None = None)`.
- **Outputs**: the log file holds every byte of stdout and stderr, in read order, as `_drain_bounded` drains them. Memory stays bounded as today; only the parse tail is kept.
- **Behavior**: `review-stage` passes `docs/dev/tmp/gate-<cycle_id>.log` and adds `"log"` to `summary["gate"]`. Prose says: read failures from the log with `rg`; never rerun the gate to capture or re-read output.

#### Feature: Blake gets the staged Tests line (packet 9b)
- **Description**: Blake's prompt carries this cycle's `## Test gate` block and tells him not to rerun the suite.
- **Inputs**: the `## Test gate` section `stage()` appended to `review-context-<id>.md`.
- **Outputs**: `blake-prompt-<id>.md` ends with that section verbatim (before Filesystem notes, when those apply).
- **Behavior**: `_run_inputs` reads the section with `_section(context_text, "Test gate")`; a context with no such section (a direct `render_roster()` call) adds no block. `agents/blake.md` gains one sentence after the Bash rules: "When your run inputs carry a `## Test gate` block, it is this cycle's full-suite result at HEAD: do not rerun the full suite; a narrow run of one test file to check a spec claim is fine." The Tests line names counts only, never the diff, so the lens stays blind.

### Capability: Exact reuse check

`reuse_verdict` sees every change since the record and matches commands by meaning, not spelling.

#### Feature: Command normalizing (packet 10)
- **Description**: one `normalize_command(command: str) -> str` used before compare and before write.
- **Inputs**: a command string.
- **Outputs**: `" ".join(command.split())`, then one leading `bash ` or `sh ` removed, then one leading `./` removed.
- **Behavior**: `_record_shape_ok` compares `normalize_command(c["command"]) == normalize_command(gate_command)`; `_write_record` stores `normalize_command(command)`. So `bash ./dev/bin/release-checks`, `./dev/bin/release-checks` and `dev/bin/release-checks` all match.

#### Feature: Tree-to-tree change list (packets 6, 11)
- **Description**: list changed paths with `git diff --name-only --no-renames -z <sha> <head_sha>`, split on NUL.
- **Inputs**: record sha, HEAD sha.
- **Outputs**: toplevel-relative paths, unquoted.
- **Behavior**: replaces the `git log` call in `_ancestor_and_clean`; a non-zero exit is `stale`. The status call gains `--untracked-files=all`. The toplevel-relative form with `--show-prefix` stays (the 00266 review's choice); the deviation from 00266 task wording (`--relative -- .`, `-uall`) is logged in the 00266 audit.

### Capability: Safe state writes

#### Feature: No-change abort (packet 7)
- **Description**: `state.transaction` writes neither `.bak` nor state when the mutator reports no change.
- **Inputs**: a module-level sentinel `state.NO_CHANGE`, returned by `fn`.
- **Outputs**: `transaction` returns the parsed current state untouched; the validator does not run.
- **Behavior**: `statectl.mutate` passes the sentinel through: when `apply` returns `state.NO_CHANGE`, its inner `fn` returns it and `mutate` returns it. `review_close._close_mutator` returns `state.NO_CHANGE` on the already-applied path (it still sets `outcome["already"] = True`). Every other caller is unchanged, so `.bak` refresh on a real write is unchanged.

### Capability: Recorded limits

#### Feature: Ceiling and count comments (packets 12, 20)
- **Description**: comment-only edits; no behavior.
- **Behavior**: a `# ponytail:` comment above `_merge_pair` says the pair scan is cubic in distinct files, the knee is ~500 rows (1,000 rows take 63 s), and the upgrade path is computing pair ranks once and updating them per merge (roughly quadratic). The `_REVIEW_VERB_TEST_FILES` comment drops both counts ("eleven", "nine") and keeps the meaning: the `cli/` files the two globs reach plus the modules no glob can reach.

## Structural Decomposition

### Repository Structure

```
CHANGELOG.md                                              # [Unreleased] Fixed lines
agents/
└── blake.md                                              # Feature: Blake gets the staged Tests line
dev/bin/
└── release-checks                                        # registers the two new test modules
docs/dev/project-management/reviews/
└── 00266-bind-gate-reuse-to-the-command-and-renames-v1-audit.md   # deviation log (packet 11)
skills/run-autopilot/
├── cli/
│   ├── __main__.py                                       # Feature: Sole writer (verify verb)
│   ├── verification.py                                   # Dirty-tree refusal, Gate log, Command normalizing, Tree-to-tree change list
│   ├── review_stage.py                                   # Gate log, Blake gets the staged Tests line
│   ├── state.py                                          # Feature: No-change abort
│   ├── statectl.py                                       # No-change abort (mutate passthrough)
│   ├── review_close.py                                   # No-change abort (caller)
│   ├── rework_groups.py                                  # Ceiling comment
│   ├── fixtures/
│   │   └── blake-prompt-00244c1.md                       # golden Blake prompt, regenerated
│   ├── test_verification.py                              # tests: verification
│   ├── test_review_stage.py                              # tests: review_stage
│   ├── test_cli_review_verbs.py                          # tests: verify verb
│   ├── test_state_no_change.py                           # NEW tests: no-change abort
│   └── test_release_checks_counts.py                     # count comment, tuple entries
└── references/
    └── lane-solo.md                                      # § 3 Suite calls the verb
skills/work/
├── SKILL.md                                              # step 7 calls the verb
├── references/
│   └── final-verification.md                             # § Recorded verification result calls the verb
└── scripts/
    ├── test_verify_queue_prose.py                        # four assertions rewritten
    └── test_gate_record_writer_prose.py                  # NEW tests: writer and log prose
skills/review-work-completion/
├── SKILL.md                                              # step 3 gate note, step 6 fallback
└── references/
    └── agent-invocation.md                               # § Blake: Test gate
```

### Module: verification
- **Maps to capability**: Honest gate record, Exact reuse check
- **Responsibility**: run the gate once, write the only record, decide reuse
- **Exports**:
  - `run_gate(command, cwd, sha, cycle, timeout=GATE_TIMEOUT_S, log_path=None) -> dict` - adds `recorded`, `dirty`
  - `normalize_command(command) -> str` - new
  - `reuse_verdict(record, repo_root, head_sha, gate_command)` - signature unchanged

### Module: cli verify verb
- **Maps to capability**: Honest gate record
- **Responsibility**: the one CLI path sessions use to run the full suite
- **Exports**: `autopilot verify` (`_add_verify`, `_run_verify` in the `_SUBCOMMANDS` registry; docstring entry beside `review-stage`)

### Module: review_stage
- **Maps to capability**: Honest gate record
- **Responsibility**: pass a log path to `run_gate`; give Blake the Test gate block
- **Exports**: `run_gate_line` result gains `"log"`

### Module: state / statectl / review_close
- **Maps to capability**: Safe state writes
- **Responsibility**: skip every write when a mutator reports no change
- **Exports**: `state.NO_CHANGE`

### Module: prose
- **Maps to capability**: Honest gate record
- **Responsibility**: route every full-suite run through `autopilot verify`; read the log with `rg`
- **Exports**: none

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **verification**: normalize, diff, status flags, dirty refusal, log
- **state**: `NO_CHANGE` sentinel and `statectl.mutate` passthrough
- **comments**: `rework_groups.py`, `test_release_checks_counts.py`

### Core Layer (Phase 1)
- **review_close**: Depends on [state]
- **cli verify verb**: Depends on [verification]
- **review_stage**: Depends on [verification]

### Integration Layer (Phase 2)
- **prose**: Depends on [cli verify verb, review_stage]
- **00266 audit, CHANGELOG**: Depends on [verification, review_close, cli verify verb, review_stage]

## Implementation Phases

### Phase 0: Foundation
**Goal**: the record is written only for a clean tree, and reuse sees every change.

**Tasks**:
- [ ] verification: add `normalize_command` and use it in `_record_shape_ok` and `_write_record` (no deps) - Acceptance: in `skills/run-autopilot/cli/test_verification.py`, `test_reuse_matches_a_command_spelled_with_bash_dot_slash_and_extra_spaces` (record `dev/bin/release-checks`, request `bash  ./dev/bin/release-checks` -> `reused`) and `test_run_gate_writes_the_normalized_command` pass and fail at base; `test_reuse_is_stale_when_the_gate_command_differs` still passes.
- [ ] verification: replace the `git log` call with `git diff --name-only --no-renames -z <sha> <head_sha>` split on NUL, and add `--untracked-files=all` to the status call (no deps) - Acceptance: in `test_verification.py`, `test_merge_resolution_change_outside_the_store_is_stale`, `test_untracked_product_file_is_stale_when_status_hides_untracked` (repo config `status.showUntrackedFiles=no`), `test_an_untracked_store_dir_stays_reused` (the whole `docs/` tree untracked, so base status prints `?? docs/`) and `test_store_only_commit_with_non_ascii_filename_is_reused` pass and fail at base; `test_committed_rename_into_the_store_is_stale` and `test_store_only_change_below_toplevel_is_reused` still pass.
- [ ] verification: add `_dirty_outside_store`, check it before spawn and after reap in `run_gate`, write the record only when both are clean, add `recorded`/`dirty` to the result, add `log_path` and stream both pipes into it from `_drain_bounded`; update the module and `run_gate` docstrings to say `run_gate` is the only writer. Premise: three existing tests assert a record written under a non-git `tmp_path` (`test_run_gate_keeps_tail_so_a_late_summary_line_still_parses`, `test_run_gate_writes_last_verification_json_on_fresh_run`, `test_run_gate_reports_the_process_exit_not_the_printed_one`); re-check with `rg -n "RECORD_REL\).exists\(\)|RECORD_REL\).read_text" skills/run-autopilot/cli/test_verification.py` and move exactly those that assert a write onto the `repo` fixture, changing nothing else in them; if the set differs, move only the ones that assert a write and report the difference (no deps) - Acceptance: in `test_verification.py`, `test_run_gate_on_a_dirty_tree_writes_no_record`, `test_run_gate_dirtied_during_the_run_writes_no_record`, `test_run_gate_outside_a_git_repo_writes_no_record`, `test_run_gate_tolerates_dirty_store_paths` and `test_run_gate_streams_stdout_and_stderr_to_the_log` pass and fail at base; the three moved tests pass.
- [ ] state: add `NO_CHANGE`; `transaction` returns `current` with no validator run, no `.bak` and no state write when `fn` returns it; `statectl.mutate` passes it through; create `skills/run-autopilot/cli/test_state_no_change.py` and register it in `dev/bin/release-checks` (`[checks] review verbs` block) and in `_REVIEW_VERB_TEST_FILES` (no deps) - Acceptance: in `test_state_no_change.py`, `test_transaction_writes_neither_backup_nor_state_on_no_change` (state and `.bak` bytes and mtimes unchanged) and `test_mutate_returns_no_change_and_writes_nothing` pass and fail at base; `test_a_changing_transaction_still_refreshes_the_backup` passes; `test_every_review_verb_test_file_is_listed` passes.
- [ ] comments: add the `# ponytail:` ceiling comment above `rework_groups._merge_pair`; drop "eleven" and "nine" from the `_REVIEW_VERB_TEST_FILES` comment (no deps) - Acceptance: `rg -n "ponytail:.*500" skills/run-autopilot/cli/rework_groups.py` prints one line; `rg -n "eleven|nine" skills/run-autopilot/cli/test_release_checks_counts.py` prints nothing while `rg -n "_REVIEW_VERB_TEST_FILES" skills/run-autopilot/cli/test_release_checks_counts.py` hits (control); comment-only, no behavior to test.

**Exit Criteria**: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_verification.py skills/run-autopilot/cli/test_state_no_change.py` exits 0.

### Phase 1: Core
**Goal**: callers use the new contracts.

**Tasks**:
- [ ] review_close: `_close_mutator`'s already-applied branch returns `state.NO_CHANGE` (depends on: Phase 0) - Acceptance: in `test_state_no_change.py`, `test_an_in_lock_already_applied_close_keeps_the_backup` (apply once, monkeypatch `_prelock_refusal` to return None, close again: `{"applied": False, "reason": "already applied"}` and `.bak` bytes unchanged) passes and fails at base.
- [ ] cli: add the `verify` verb to `__main__.py` (registry entry, docstring entry, exit 0/1/2 as in Feature: Sole writer) (depends on: Phase 0) - Acceptance: in `skills/run-autopilot/cli/test_cli_review_verbs.py`, `test_verify_runs_the_gate_once_and_writes_the_record_and_log`, `test_verify_exits_1_on_a_red_gate`, `test_verify_writes_no_record_on_a_dirty_tree` and `test_verify_exits_2_outside_a_git_repo` pass and fail at base.
- [ ] review_stage: pass `TMP_REL / f"gate-{cycle_id}.log"` to `run_gate` and add `"log"` to `run_gate_line`'s result; add the Test gate block to Blake's appends; add the `agents/blake.md` sentence; regenerate `skills/run-autopilot/cli/fixtures/blake-prompt-00244c1.md`. Premise: `test_stage_writes_every_input_file` (the test holding `assert summary["gate"] == {`) pins the gate dict exactly; re-check with `rg -n 'summary\["gate"\] == \{' skills/run-autopilot/cli/test_review_stage.py` and add only the `"log"` key to that expected dict (depends on: Phase 0) - Acceptance: in `skills/run-autopilot/cli/test_review_stage.py`, `test_blake_prompt_carries_the_staged_tests_line`, `test_blake_prompt_has_no_test_gate_block_without_one_in_the_context` and `test_stage_writes_the_gate_log` pass and the first and third fail at base; `test_render_matches_golden_blake` and `test_blake_prompt_carries_no_diff_or_ledger` pass against the regenerated fixture.

**Exit Criteria**: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_review_stage.py skills/run-autopilot/cli/test_cli_review_verbs.py skills/run-autopilot/cli/test_state_no_change.py` exits 0.

### Phase 2: Integration
**Goal**: prose sends every full-suite run through the verb, and the records say what shipped.

**Tasks**:
- [ ] prose: rewrite `final-verification.md` § Recorded verification result (run the full suite with `autopilot verify --gate-command "<full suite command>" [--cycle <state.cycle>]`; the verb alone writes the record; a timed-out or unparsed run writes no record; a dirty tree writes no record; read failures from the printed log with `rg`, never rerun the gate to capture output; keep the JSON shape as what the verb writes; a record from a pre-fix HEAD is never reused) and point its full-suite bullet at the verb; update `skills/work/SKILL.md` step 7, `skills/run-autopilot/references/lane-solo.md` § 3, `skills/review-work-completion/SKILL.md` step 3's `gate.tests_line` note (it writes the record only on a clean tree) and step 6's fallback run (`autopilot verify` instead of a bare suite run), and add `## Blake: Test gate` to `agent-invocation.md`. Create `skills/work/scripts/test_gate_record_writer_prose.py` and register it in `dev/bin/release-checks` (`[checks] review verbs`) and `_REVIEW_VERB_TEST_FILES`. Premise: `rg -c 'unless the whole suite re-ran clean at the final HEAD|no parseable counts records .null. for all three|empty .commands. array|"exit": "timeout"., never a number' skills/work/scripts/test_verify_queue_prose.py` prints 4; rewrite only those four assertions to the new rules; if the count differs, rewrite the ones found and report the difference (depends on: Phase 1) - Acceptance: in `test_gate_record_writer_prose.py`, `test_no_prose_tells_a_session_to_write_the_record` (no line in the four prose files matches `(?i)\bwrite\b.*last-verification\.json`), `test_final_verification_runs_the_suite_through_autopilot_verify`, `test_gate_output_is_read_from_the_log_not_a_rerun`, `test_review_fallback_runs_through_autopilot_verify` and `test_agent_invocation_documents_blake_test_gate` pass and fail at base; `uv run --no-project --with pytest python -m pytest -q skills/work/scripts/test_verify_queue_prose.py skills/work/scripts/test_command_budget_prose.py` exits 0.
- [ ] 00266 audit: append a decision entry to `docs/dev/project-management/reviews/00266-bind-gate-reuse-to-the-command-and-renames-v1-audit.md`: the shipped code kept toplevel-relative paths with `--show-prefix` instead of the task's `--relative -- .`, omitted `-uall`, and PRD 00270 added `--untracked-files=all` and `-z` (agoge 2026-10-07-2 packet 11) (depends on: Phase 0) - Acceptance: `rg -n "00270" docs/dev/project-management/reviews/00266-bind-gate-reuse-to-the-command-and-renames-v1-audit.md` hits and `rg -n "relative -- \." <same file>` hits.
- [ ] CHANGELOG: add `[Unreleased] ### Fixed` lines: dirty-tree gate runs record nothing; `run_gate` is the only writer and `autopilot verify` is the new way to run the suite (also under `### Added`); merge resolution edits and untracked or non-ASCII paths are seen by reuse; commands match after normalizing; a racing `review-close` keeps `state.json.bak`; Blake no longer reruns the suite (depends on: all above) - Acceptance: `rg -n "autopilot verify" CHANGELOG.md` hits inside `[Unreleased]` (line number below the `## [0.9.0]` heading's).

**Exit Criteria**: `bash dev/bin/release-checks` exits 0 with `FAIL 0` on its summary line.

## Test Strategy

### Critical Scenarios
- **Happy path**: clean tree, `autopilot verify` green -> record at HEAD with the normalized command, log written; the next `review-stage` with `bash dev/bin/release-checks` reuses it.
- **Edge case**: gate runs over an uncommitted product edit, edit is reverted -> no record from that run; `review-stage` reruns.
- **Edge case**: merge commit whose resolution edits `src/` while both parents touch only the store -> `stale`.
- **Edge case**: `status.showUntrackedFiles=no` plus an untracked product file -> `stale`.
- **Error case**: two `review-close` calls race -> one applies, the other returns "already applied", `.bak` keeps the pre-apply bytes.
- **Error case**: `autopilot verify` outside a git repo -> exit 2, no record.

## Risks

- **A determined forger can still write the file**: accepted by the operator (packet 5 option 1 closes the routine path, not a forger). No hook is added.
- **A project that does not ignore `docs/dev/tmp/`**: the log and the staged review inputs count as dirty, so no record is written and reuse never fires. That fails safe (a rerun). This pack's `.gitignore` and the `test_review_stage.py` fixture ignore it.
- **Normalizing joins two commands that differ only in spacing inside quotes**: unlikely for a gate command; accepted for the reruns it saves.
- **`state.NO_CHANGE` blast radius**: only callers that return the sentinel change behavior; every other `transaction`/`mutate` caller is unchanged, guarded by `test_a_changing_transaction_still_refreshes_the_backup`.
- **Blake's independence**: he no longer runs the suite himself. Accepted by the operator (packet 9); he may still run one narrow test file.
- **`test_verify_queue_prose.py` is not in `dev/bin/release-checks`**: its rewritten assertions are checked by the Phase 2 Acceptance command, not by the gate. Adding it to the gate is out of scope.
