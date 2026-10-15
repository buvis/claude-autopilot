---
catchup: run
design: run
default_model: opus
lane: full
model_tier_rationale: a write boundary with seven refusal cases and one race-sensitive open; the fast-track attempt on v1 left a CRITICAL standing after its one rework
---

# Refuse every unsafe verify --log sink before opening it (v2)

Source: hold PRD 00306 v1 (parked 2026-10-15 02:46 by the fast-track lane, `fast_track_blocked`; its attempt sits on the git branch named fast-track/00306-refuse-tracked-verify-log-v1-c1, head 1eb1fa95, 4 commits); `docs/dev/project-management/audit-results/agoge-2026-10-15.md` packet 1 and § Already routed; `docs/dev/project-management/audit-results/agoge-2026-10-14.md` packets 7, 8, 18.

## Problem

`autopilot verify --log <path>` opens its sink for writing before the gate runs: `_run_locked_gate` (`skills/run-autopilot/cli/verification.py:398-438`) opens the path in write mode as its first act. The only refusal in front of it is `_refuse_verify_log` (`skills/run-autopilot/cli/__main__.py:1028-1040`), a string `is_relative_to` check against the store. v1 tried to close this on the fast-track lane: its solo review confirmed a CRITICAL (a symlink planted at the default log path still wrote through) and a HIGH (the git-directory identity check missed a subdirectory cwd) after the one rework the lane allows, so the lane branched the attempt and reset master. At HEAD 807ed12b nothing of it is live: `--log` naming a committed file on a clean tree still replaces the file with gate output (exit 3, `dirty: true`); the case-variant store path, `.git/config`, `.git/hooks/pre-push.sample` and a FIFO sink are still live (agoge-2026-10-15 § Already routed); a `--log` into another repository's store overwrote that repository's tracked state file; and a hard link under `docs/dev/tmp` to a tracked store file passes every check v1 planned, since the link path is untracked, regular, non-executable and outside the store (agoge-2026-10-15 packet 1, HIGH, trudy):

```
fixture: a committed store state file (autopilot/state.json under the store) = MARKER-trudy-store-bytes
os.link(<that state file>, docs/dev/tmp/gate-hl.log)
verify --gate-command "bash gate.sh" --log docs/dev/tmp/gate-hl.log
-> exit 0, "recorded": true, "dirty": false
state.json now reads: PASS 3 FAIL 0 SKIP 0 EXIT 0
git status: M <the store state file>
```

## Solution

Refuse by identity before any open, at both entry points, and never write through an existing inode. `_refuse_verify_log` grows into the full set, each case one stderr line `autopilot: verify: --log <path> <reason>` and one JSON line `{"error": "<the same text>", "exit": 2, "log": null}`, exit 2: (1) an existing ancestor of the resolved path is the store directory or the git directory by the standard library samefile test, against the store and against what `git rev-parse --absolute-git-dir` and `git rev-parse --git-common-dir` print when run from the repo root (never from cwd): `resolves inside the store`, `resolves inside the git directory`; (2) tracked at HEAD (`git ls-files --error-unmatch` from the toplevel): `is tracked`; (3) the unresolved path or any ancestor below the toplevel is a symlink (an lstat walk): `is a symlink`; (4) the resolved path is outside `git rev-parse --show-toplevel` of the repo root: `resolves outside the repository` (this also covers another repository's store); (5) an existing target that is not a regular file (FIFO, device, directory) or carries any `0o111` bit: `is not a regular file`, `is executable`; (6) an existing target whose lstat link count exceeds one: `has more than one hard link`. The default sink `docs/dev/tmp/gate-<sha7>.log` goes through the same checks, so a symlink or hard link planted there is refused too. In `verification.py`, a new `_open_log_sink` opens the log inside the lock with the create, exclusive, write-only and no-follow flags of the os module after unlinking a pre-existing regular single-link file at that path, so every run writes a fresh inode; `_lock_and_check` (`skills/run-autopilot/cli/verification.py:379-395`) returns `_dirty_result([rel])` for a tracked or symlinked `log_path` before `_run_locked_gate` runs, so a library caller cannot bypass the CLI. The gate itself does not change.

## Requirements

### Must have
- `_refuse_verify_log` refuses, exit 2, each of the seven cases with the stated reason text and the JSON line; every refusal runs before `run_gate` is called, so no lock is taken, no file is created or changed, and `git status --short` is unchanged.
- The default sink is checked the same way: a symlink or a hard link planted at `docs/dev/tmp/gate-<sha7>.log` is refused with exit 2.
- The git-directory identity check holds when `verify` runs with a subdirectory as cwd and `--repo-root` pointing at the toplevel.
- `_run_locked_gate` opens the sink only through `_open_log_sink` (exclusive create, no follow, inside the lock); `_lock_and_check` returns `_dirty_result([rel])` with `recorded: false` for a tracked or symlinked `log_path`, and the sink's bytes are unchanged afterwards.
- Fail-first tests red at the task's base commit. The nine tests of the parked branch's `test_verify_log_refusal.py` are carried over by name (the implementer may read them from that branch with `git show`), plus five new ones named under Implementation.
- A CHANGELOG `[Unreleased]` Fixed entry under **run-autopilot**.

### Nice to have
- None.

## Implementation

### Module: verify-log-refusal
- **Location**: `skills/run-autopilot/cli/__main__.py` (`_refuse_verify_log`, `_run_verify`), `skills/run-autopilot/cli/verification.py` (`_lock_and_check`, `_run_locked_gate`, `_dirty_result`)
- **Responsibility**: no `verify` run writes into a tracked, linked, store, git-directory, out-of-repo, non-regular or executable path
- **Exports**: `_refuse_verify_log()` (extended), `run_gate()` (unchanged signature)
- New symbols: `_open_log_sink`

### Module: verify-log-tests
- **Location**: `skills/run-autopilot/cli/test_verify_log_refusal.py`
- **Responsibility**: pin every refusal case and the untracked-sink happy path against a fixture repo
- **Exports**: none
- New symbols: `test_verify_log_refusal.py`, `test_cli_refuses_tracked_log_and_leaves_bytes_intact`, `test_cli_refuses_symlinked_log`, `test_cli_refuses_log_outside_toplevel`, `test_cli_refuses_case_variant_store_path`, `test_cli_refuses_git_dir_log`, `test_cli_refuses_fifo_log`, `test_cli_refuses_executable_target`, `test_run_gate_refuses_tracked_log_without_opening`, `test_untracked_tmp_log_still_records`, `test_cli_refuses_hardlinked_log`, `test_default_sink_symlink_is_refused`, `test_default_sink_hardlink_is_refused`, `test_git_dir_identity_holds_from_a_subdirectory_cwd`, `test_log_into_another_repos_store_is_refused`

### Dependencies
- verify-log-tests: No dependencies (foundation)
- verify-log-refusal: Depends on [verify-log-tests]

## Tasks

### Phase 0: Foundation
- [ ] Write `skills/run-autopilot/cli/test_verify_log_refusal.py` against a fixture repo (one committed source file, a committed ignore rule for docs/dev/tmp/, a committed state file under the store's autopilot directory holding a marker string) with the fourteen tests named under Implementation: the nine carried over from the parked branch keep their assertions (exit 2, the reason text on stderr, bytes intact, `git status --short` unchanged, the FIFO case returning within 2 seconds, the case-variant test skipped with a reason on a case-sensitive volume), `test_cli_refuses_hardlinked_log` replays the fenced reproduction above and asserts exit 2 and the marker string intact, `test_default_sink_symlink_is_refused` and `test_default_sink_hardlink_is_refused` plant the link at `docs/dev/tmp/gate-<sha7>.log` and run `verify` without `--log`, `test_git_dir_identity_holds_from_a_subdirectory_cwd` runs `verify --repo-root <top> --log .git/config` with cwd set to a subdirectory, `test_log_into_another_repos_store_is_refused` points `--log` at a second fixture repository's store file and asserts its bytes intact. Register the file in a `[checks]` block of `dev/bin/release-checks` - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_verify_log_refusal.py` reports thirteen tests failing (or skipped, for the case-variant test) and `test_untracked_tmp_log_still_records` passing at the task's base commit; `rg -c 'test_verify_log_refusal.py' dev/bin/release-checks` prints 1.

### Phase 1: Core
- [ ] Extend `_refuse_verify_log` in `skills/run-autopilot/cli/__main__.py` with the six case groups (identity via samefile over the existing ancestors against the store and the two git directories resolved from the repo root; tracked via `git ls-files --error-unmatch`; symlink via an lstat walk of the unresolved path; outside via the toplevel; target via lstat, the regular-file mode test, the `0o111` bits and the link count), apply it to the default sink, and add `_open_log_sink` to `skills/run-autopilot/cli/verification.py`, called from `_run_locked_gate`, with `_lock_and_check` returning `_dirty_result([rel])` for a tracked or symlinked `log_path` (depends on: Phase 0) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_verify_log_refusal.py skills/run-autopilot/cli/test_verification_dirty.py skills/run-autopilot/cli/test_verify_truth.py` passes with every new test green; `rg -c '^def test_' skills/run-autopilot/cli/test_verification_dirty.py` prints the same count as at the task's base commit.
- [ ] Add the CHANGELOG `[Unreleased]` Fixed entry `**run-autopilot**: \`autopilot verify --log\` refuses a tracked, symlinked, hard-linked, out-of-repo, store, git-directory, non-regular or executable sink before opening it, and opens the sink exclusively, so a gate run can no longer overwrite committed source, git internals, a hook or the loop's own state` (depends on: Phase 1 refusal) - Acceptance: `rg -n 'verify --log` refuses a tracked' CHANGELOG.md` prints one hit under `[Unreleased]`.

## Success Criteria

- The probe from the Problem section (clean tree, `--log` naming a committed file) exits 2, prints `is tracked` on stderr, and leaves the file byte-identical with `git status --short` empty.
- The fenced hard-link reproduction exits 2 and the store file keeps its marker string.
- `--log .git/config`, the case-variant store path and a FIFO each exit 2 and create or change no file; the FIFO case returns within 2 seconds.
- `test_verify_log_refusal.py` is green and listed in `dev/bin/release-checks`.
