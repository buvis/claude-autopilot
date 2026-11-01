---
default_model: opus
model_tier_rationale: invented hold-file contract shared by the loop, the push guard and the docs; a git snapshot whose missed change degrades silently; fail-closed paths across three modules
---

# Hold pushes until an agoge run has left the repo as it found it

Source: the 2026-10-25 agoge incident (claude-agoge intake 00003, processed
into claude-agoge PRDs 00003 and 00005) and the design discussion of
2026-11-01.

## Overview

### Problem Statement

After a batch drains, `run_agoge` in `skills/run-autopilot/cli/loop_act.py`
runs one agoge pass over the repo, and agoge's lanes hold Bash in the
product's checkout. On 2026-10-25 a lane committed into the product's
`master`, tagged that commit `v1.0.0` (the product publishes on tag pushes)
and moved `refs/remotes/origin/master`, which hid 13 unpushed commits behind
a clean `git status`. The agoge session exited 0, the loop printed
"packets written", and nothing held the next push.

`run_agoge` looks only at the exit code. claude-agoge PRDs 00003 and 00005
make lanes stay out of the target and make agoge report a change in its
sidecar's `target_integrity`, but agoge cannot stop a push: its session ends
with the run, and a run killed at the cap (twice in October) reports nothing.
The loop owns the run, and this plugin owns the push guard
(`hooks/guard_push_on_critical.py`), so the loop must check the repo itself
and hold pushes until it has.

### Target Users

Operators who drain batches unattended and push afterwards, from their own
terminal or through an agent session's Bash tool.

### Success Metrics

- While the agoge run is in progress, the push guard denies a Bash
  `git push` into the repo.
- After the run, a repo whose HEAD, refs, index, tracked status, local git
  config and worktree list match the pre-run snapshot, and whose new sidecar
  does not report `changed` or `unknown`, releases the hold. Anything else
  keeps it, lists the changes in the hold file and notifies the operator. A
  comparison that cannot run keeps it too.
- agoge's own outputs never hold: its profile, new report files, and
  branches under `refs/heads/agoge/`.
- The tests in Phase 0 to 2 pass, and `dev/bin/release-checks` passes.

## Functional Decomposition

### Capability: Push hold around the agoge run
The loop arms a hold before the run and settles it after.

#### Feature: Snapshot and comparison
- **Description**: `snapshot(run_git)` records the repo's git state, and
  `compare(before, after)` lists what changed.
- **Inputs**: `run_git`, the callable `custody.store_git` returns.
- **Outputs**: A snapshot dict (A1) and a list of change dicts (A2).
- **Behavior**: Every call is `run_git(["--no-optional-locks", ...])`,
  because a plain `git status` rewrites the index. Anything else `run_git`
  raises, a non-zero exit other than the two allowed in A1, a timeout or an
  undecodable path included, becomes `HoldError`, never an exception that
  escapes into the loop.

#### Feature: Arm and settle
- **Description**: `arm` writes a `running` hold entry before the run;
  `settle` releases it or keeps it after the run.
- **Inputs**: The autopilot dir, `run_git`, the batch id, the log path.
- **Outputs**: The hold file `<autopilot dir>/agoge-hold` (A3).
- **Behavior**: `arm` returns `None` when `rev-parse --show-toplevel`
  fails, since a directory outside git has nothing a push can publish; it
  raises `HoldError` when the hold cannot be written. `settle` runs whatever
  the agoge exit code was, and returns `released`, `changed` or `unverified`
  (A4).

#### Feature: Loop wiring
- **Description**: `run_agoge` arms, runs and settles; `_act_done` passes
  `run_git` and notifies.
- **Inputs**: `store_run_git` from `_act_done`.
- **Outputs**: The status lines and the notification in A5.
- **Behavior**: A hold that cannot be armed skips the run, because no lane
  runs unguarded. A settle that fails leaves the `running` entry, which
  still holds.

### Capability: Push guard
#### Feature: Hold entries deny a push
- **Description**: `hooks/guard_push_on_critical.py` reads `agoge-hold`
  beside `critical-on-master`, through all three of its lookups.
- **Inputs**: The hold file.
- **Outputs**: The denial text in A6.
- **Behavior**: An unreadable hold file denies with the degraded line, as
  an unreadable marker does. The cap_critical text is unchanged when no hold
  entry is present.

### Capability: Store and docs
#### Feature: The hold file is machine state
- **Description**: The hold is ignored by git, documented, and recorded in
  the changelog.
- **Inputs**: None.
- **Outputs**: A7 to A11.
- **Behavior**: An ignored hold file stays out of the drained store commit,
  which `_act_done` makes right after `run_agoge`.

## Structural Decomposition

### Repository Structure

```
skills/run-autopilot/cli/agoge_hold.py          # Snapshot, compare, arm, settle (new)
skills/run-autopilot/cli/test_agoge_hold.py     # Their tests (new)
skills/run-autopilot/cli/loop_act.py            # run_agoge and _act_done wiring
skills/run-autopilot/cli/test_loop_act.py       # Wiring tests; the drained-branch stub
skills/run-autopilot/cli/loop_testutil.py       # The autouse run_agoge stub
skills/run-autopilot/cli/store_tree.py          # STORE_GITIGNORE
hooks/guard_push_on_critical.py                 # Reads and renders hold entries
hooks/test_guard_push_on_critical.py            # Hold denial tests
docs/dev/project-management/.gitignore          # This repo's copy of STORE_GITIGNORE
skills/run-autopilot/SKILL.md                   # Product QA bullet, Retention, push row
skills/run-autopilot/references/state-schema.md # Marker files row
dev/bin/release-checks                          # Runs the new test file
CHANGELOG.md                                    # Unreleased entry
```

### Module: agoge_hold
- **Maps to capability**: Push hold around the agoge run
- **Responsibility**: Record the repo's git state and hold pushes until a
  run has left it unchanged.
- **Exports**:
  - `snapshot(run_git) -> dict`
  - `compare(before, after) -> list[dict]`
  - `arm(ap_dir, run_git, batch, log_path) -> Armed | None`
  - `settle(ap_dir, run_git, armed) -> str`
  - `HoldError`, `Armed` (a NamedTuple of `entry`, `before`, `started`),
    `HOLD_NAME`
- New symbols: `agoge_hold`, `cli.agoge_hold`, `target_integrity`, `target_integrity.status`, `HoldError`, `Armed`, `HOLD_NAME`, `arm`, `settle`, `snapshot`, `compare`, `started`, `run_git`, `store_run_git`, `unverified`, `unarmed`, `released`, `worktrees`, `tracked`, `sidecar`, `refs`, `head`, `settled`, `changes`

### Module: loop wiring
- **Maps to capability**: Push hold around the agoge run (Loop wiring)
- **Responsibility**: Arm, run, settle, report and notify.
- **Exports**:
  - `run_agoge(..., run_git=None)`, now returning the hold status

### Module: push guard
- **Maps to capability**: Push guard
- **Responsibility**: Deny a Bash push while any hold entry exists.
- **Exports**:
  - `_HOLD_NAME`, `_HOLD_HEADER`, and hold blocks in `_format_block`
- New symbols: `_HOLD_NAME`, `_HOLD_HEADER`

### Module: store and docs
- **Maps to capability**: Store and docs
- **Responsibility**: Keep the hold out of git and documented.
- **Exports**:
  - The `autopilot/agoge-hold` ignore pattern and its prose

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **agoge_hold**: The snapshot, comparison and hold file.

### Core Layer (Phase 1)
- **loop wiring**: Depends on [agoge_hold]
- **push guard**: Depends on [agoge_hold] (the file shape in A3)

### Integration Layer (Phase 2)
- **store and docs**: Depends on [loop wiring, push guard]

## Implementation Phases

Premise for every edit that quotes old text: the old text occurs exactly once
in the named file (`rg -F -c '<old text>' <file>` prints 1). The working
tree may carry unrelated edits; leave them alone. If a premise fails, skip
that edit, report it, and never force a match.

Run a test file as
`uv run --no-project --with pytest python -m pytest -q <file> [-k <filter>]`.
Test repositories run with `GIT_CONFIG_GLOBAL=/dev/null`,
`GIT_CONFIG_NOSYSTEM=1`, `HOME` set to the test's tmp dir, and an author and
committer identity set through git's environment variables.

### Phase 0: Foundation
**Goal**: A snapshot that catches each kind of change, and a hold file that
arms and settles.

**Tasks**:
- [ ] Write `skills/run-autopilot/cli/test_agoge_hold.py` against real
  repositories, with `run_git` from `custody.store_git` on a fake autopilot
  dir inside each (no deps). One test per case: an untouched repo compares
  equal; snapshot and settle write nothing in the repo while a stat-dirty
  tracked file is present (`.git/index` bytes and the `.git` file list with
  mtimes unchanged); a branch switch, a new commit, a new tag, a moved
  remote-tracking ref, a staged change, a modified tracked file, a local
  config change and an added worktree are each a change; a new branch under
  `refs/heads/agoge/`, a modified or created profile at either A1 path, and
  a new untracked report file are not; arm writes one `running` entry and
  settle on an unchanged repo deletes the file; settle keeps a `changed`
  entry with its changes, and keeps another batch's entry untouched; a
  sidecar newer than the run with `target_integrity.status` `changed` keeps
  the hold, while an older sidecar or one without that key does not; a git
  call that fails during settle keeps an `unverified` entry; arm in a
  directory outside git returns `None`; arm into an autopilot dir that
  cannot be written raises `HoldError` - Acceptance: the file collects these
  tests, and they fail because `agoge_hold.py` does not exist.
- [ ] Write `skills/run-autopilot/cli/agoge_hold.py` to A1 to A4, importing
  only the stdlib, `cli.custody` and `cli.state` (depends on: the test task)
  - Acceptance: `pytest -q skills/run-autopilot/cli/test_agoge_hold.py`
  passes.

**Exit Criteria**: The hold arms, settles and catches every change in A2.

### Phase 1: Core
**Goal**: The loop holds pushes around every agoge run, and the push guard
enforces the hold.

**Tasks**:
- [ ] Apply A5 to `skills/run-autopilot/cli/loop_act.py`, add
  `cli.agoge_hold` to its module docstring's allowed imports, and add
  `run_git=None` to the `run_agoge` stub lambdas in
  `skills/run-autopilot/cli/loop_testutil.py` and in the drained-branch
  test of `skills/run-autopilot/cli/test_loop_act.py` (depends on: Phase 0).
  Add to `test_loop_act.py`: with `run_git` on a real repo, a fake claude
  that does nothing returns `released` and prints the release line; one that
  runs `git tag v1.0.0` in the repo returns `changed`, leaves a hold entry
  with a `ref` change and prints the held line; an arm that raises
  `HoldError` returns `unarmed` and never launches the fake claude;
  `_act_done` passes `run_git` and notifies when `run_agoge` returns
  `changed` - Acceptance:
  `pytest -q skills/run-autopilot/cli/test_loop_act.py` passes.
- [ ] Apply A6 to `hooks/guard_push_on_critical.py`, and add to
  `hooks/test_guard_push_on_critical.py`: a hold entry denies a push with
  `_HOLD_HEADER`, the batch line and the delete line; an empty
  `{"entries": []}` hold allows; a corrupt hold denies with the degraded
  line; a hold plus pending custody prints both blocks (depends on: Phase 0)
  - Acceptance: `pytest -q hooks/test_guard_push_on_critical.py` passes,
  its existing custody tests included.

**Exit Criteria**: A hold denies pushes, and an unchanged run releases it.

### Phase 2: Integration
**Goal**: The hold file is ignored, documented, tested in the release gate,
and recorded.

**Tasks**:
- [ ] Apply A7 to `skills/run-autopilot/cli/store_tree.py` and to
  `docs/dev/project-management/.gitignore`, and A8 to
  `skills/run-autopilot/SKILL.md` (depends on: Phase 1) - Acceptance:
  `pytest -q skills/run-autopilot/scripts/test_store_tree_prose.py -k disposable`
  and `pytest -q skills/run-autopilot/cli/test_store_tree_gitignore.py` pass.
- [ ] Apply A9 to `skills/run-autopilot/SKILL.md` and A10 to
  `skills/run-autopilot/references/state-schema.md` (depends on: Phase 1) -
  Acceptance: `rg -F -c 'agoge-hold' skills/run-autopilot/SKILL.md` prints 3,
  and `rg -F -c 'agoge-hold' skills/run-autopilot/references/state-schema.md`
  prints 1.
- [ ] Add `skills/run-autopilot/cli/test_agoge_hold.py` to the
  `dev/bin/release-checks` block that lists
  `skills/run-autopilot/cli/test_loop_act.py`, on the line after it, and add
  A11 to `CHANGELOG.md` (depends on: Phase 1) - Acceptance:
  `rg -F -c 'test_agoge_hold.py' dev/bin/release-checks` prints 1, and
  `rg -F -c 'agoge-hold' CHANGELOG.md` prints 1.

**Exit Criteria**: `dev/bin/release-checks` passes.

## Test Strategy

### Critical Scenarios
- **Happy path**: a run that writes only its profile, its reports and an
  `agoge/` test branch → Expected: `released`, no hold file, pushes allowed.
- **Edge case**: the loop is killed during the run → Expected: the
  `running` entry stays and keeps denying pushes until the operator deletes
  the file.
- **Edge case**: a lane runs `git push` during the run → Expected: the push
  guard denies it, because the entry is `running`.
- **Error case**: git fails during settle → Expected: an `unverified` entry,
  and pushes stay held.
- **Regression**: a fake agoge run tags the repo → Expected: `changed`, a
  `ref` change in the hold file, a notification, a denied push.

## Risks

- **Pushes from the operator's own terminal**: no Claude hook sees them.
  Mitigation: the notification and the loop's held line say pushes are held;
  only a git `pre-push` hook could enforce it there, and that is out of scope.
- **The operator works in the repo during the run**: their commit or edit is
  reported as a change. Mitigation: the hold lists every change, and deleting
  the file after a look is one command.
- **The next batch builds on a changed tree**: a hold does not stop the loop
  from starting a new batch. Mitigation: the operator is notified at once,
  every push stays held, and refusing to start a batch is a follow-up.
- **Coarser than agoge's own check**: the loop compares status letters, not
  file contents, and ignores untracked files. Mitigation: a sidecar from
  claude-agoge PRD 00005, which hashes contents, also keeps the hold.
- **`git clean -X` deletes the ignored hold file**: that releases it.
  Mitigation: only an explicit operator act does that; the loop's held line
  and the notification still record the run.

## Appendix: exact behaviour and texts

### A1. Snapshot

| Key | Source, each through `run_git(["--no-optional-locks", ...])` |
|---|---|
| `head` | `{"ref": <symbolic-ref -q HEAD, or null when it exits 1>, "commit": <rev-parse --verify -q HEAD^{commit}, or null when it exits 1>}` |
| `refs` | `for-each-ref --format=%(refname)%00%(objectname)`, as `{refname: oid}`, without refnames that start with `refs/heads/agoge/` |
| `config` | sha256 hex of `config --local --list -z` |
| `worktrees` | the paths on the `worktree ` lines of `worktree list --porcelain` |
| `index` | sha256 hex of `ls-files --stage -z` |
| `tracked` | the sorted `"<XY> <path>"` entries of `status --porcelain=v1 -z --untracked-files=no`; when X or Y is `R` or `C`, the next NUL-separated field is the old path and is consumed; entries whose path is `docs/dev/project-management/meta/agoge-profile.md` or `docs/dev/project-management/agoge-profile.md` are left out |

### A2. Changes

`compare` returns, in this order: `{"kind": "head", "before", "after"}` when
`head.ref` differs, or both are null and `head.commit` differs; one
`{"kind": "ref", "ref", "before", "after"}` per created, deleted or moved
ref (oid or null), sorted by refname; `{"kind": "config"}` with no values,
because remote URLs can hold credentials; `{"kind": "worktrees", "before",
"after"}`; `{"kind": "index"}`; and
`{"kind": "tracked", "added": [...], "removed": [...]}` with the entries that
appeared and went. `settle` may add `{"kind": "sidecar", "status", "path"}`
and `{"kind": "error", "detail"}`.

### A3. The hold file

`<autopilot dir>/agoge-hold` holds `{"entries": [...]}`, written with
`state.atomic_write` and deleted when the last entry goes, every
read-modify-write under `custody.marker_lock(<autopilot dir>/agoge-hold)`.
An entry:

```json
{"op_id": "agoge-<batch>", "kind": "agoge", "repo_root": "<rev-parse --show-toplevel>",
 "batch": "<batch>", "status": "running", "since": "<UTC %Y-%m-%dT%H:%M:%SZ>",
 "log": "<the agoge log path>", "hold": "<absolute path of the hold file>"}
```

`arm` upserts this entry by `op_id`. A kept entry gains `status` `changed`
or `unverified`, `settled` (the same time format) and `changes` (A2).

### A4. Settle

Take a new snapshot. On `HoldError`, keep the entry as `unverified` with one
`error` change. Otherwise compare. Then find the newest
`<autopilot dir>/../audit-results/agoge-*.json` modified at or after
`armed.started`; if it parses and its `target_integrity.status` is
`changed` or `unknown`, add a `sidecar` change. No changes: remove the entry
and return `released`. Changes: keep the entry as `changed`. A missing entry
(the operator deleted the file during the run) is written back when the
result is not `released`.

### A5. Loop wiring

In `run_agoge`, add the keyword-only parameter `run_git=None`. With `None`,
nothing changes and it returns `None`. Otherwise, after `cap` is set and
before `_run_agoge_process`:

- `arm` raises `HoldError`: print to stderr
  `agoge: could not arm the push hold ({err}); QA skipped.` and return
  `unarmed` without launching claude.
- `arm` returns `None`: print to `out`
  `agoge: not a git work tree; no push hold.`, run as today, return `None`.

After the exit-code lines, `settle`. `released` prints to `out`
`agoge: the repo is as the run found it; push hold released.` Any other
status prints to stderr
`agoge: the run left the repo {status}; pushes stay held. Read {log_path}, then delete {hold path}.`
A `HoldError` from `settle` prints
`agoge: could not settle the push hold ({err}); it stays armed.` and returns
`unverified`. Return the status.

In `_act_done`, pass `run_git=store_run_git`, and when the result is neither
`None` nor `released`, call
`self._notify(f"autopilot 🔒 {self._repo_name()}", f"agoge push hold {status}: pushes stay held until you delete docs/dev/project-management/autopilot/agoge-hold.")`.

### A6. Push guard

Add `_HOLD_NAME = "agoge-hold"` and
`_HOLD_HEADER = "BLOCKED: git push targets a repository with a pending agoge push hold."`.
`_read_pending` merges `_marker_entries` of the hold file with the marker's
entries before the journal rows. `_format_block` splits entries on
`kind == "agoge"`: the cap_critical lines exactly as today for the others,
then, when hold entries exist, `_HOLD_HEADER`, one line per entry,
`  batch <batch>: <status> since <since>: <changes>, log <log>`, where
`<changes>` joins `ref <ref>` for a ref change and the `kind` of any other,
or reads `run not settled` when there are none, and last
`Check those changes, then delete <hold> to release the hold.`. The module
docstring gains one sentence naming the hold.

### A7. Ignore pattern

Add the line `autopilot/agoge-hold` after `autopilot/last-verification.json`
in `STORE_GITIGNORE`, and the same line at the same place in
`docs/dev/project-management/.gitignore`.

### A8. Retention

In `### Retention`, replace
``and `docs/dev/project-management/autopilot/.lane-guard-blocks`.`` with
`` `docs/dev/project-management/autopilot/.lane-guard-blocks`, and `docs/dev/project-management/autopilot/agoge-hold` (the agoge push hold, released by the loop or deleted by the operator).``

### A9. SKILL.md

Append to the `**Product QA (agoge)**` bullet:

~~~markdown
 Before the run the loop arms a push hold, `docs/dev/project-management/autopilot/agoge-hold`, so `hooks/guard_push_on_critical.py` denies every Bash `git push` into the repo while agoge runs. After it, the loop compares the repo's HEAD, refs, index, tracked status, local git config and worktrees with its pre-run snapshot, and reads the run's sidecar. An unchanged repo releases the hold; a change keeps it, lists the changes in the file and notifies. agoge's own outputs never hold: its profile, new report files, and branches under `refs/heads/agoge/`.
~~~

In the Error Handling row that starts `| Git push fails`, insert after
`never bypass the hook.`:
` A denial that names an agoge push hold means the last agoge run changed the repo or did not settle: read the changes it lists, then delete docs/dev/project-management/autopilot/agoge-hold.`

### A10. Marker files row

Insert after the `critical-on-master` row of the `## Marker files` table:

~~~markdown
| `agoge-hold` | `run_agoge`: `cli/agoge_hold.arm` before the agoge run and `cli/agoge_hold.settle` after it, under `custody.marker_lock` | `hooks/guard_push_on_critical.py`, which denies a Bash `git push` into the repo while any entry exists; the operator deletes the file after checking the changes | `{"entries": [...]}`, one entry per run: `op_id` `agoge-<batch>`, `kind` `agoge`, `repo_root`, `batch`, `status` `running`, `changed` or `unverified`, `since`, `log`, `hold`, and on a kept entry `settled` and `changes`; the loop removes an entry whose run left the repo unchanged |
~~~

### A11. CHANGELOG entry

Under `## [Unreleased]`, in its `### Added` list (create the heading if it
is absent):

~~~markdown
- **run-autopilot**: the drain's agoge run holds pushes. The loop arms `docs/dev/project-management/autopilot/agoge-hold` before the run, so the push guard denies a Bash `git push` into the repo while agoge runs, and releases it only when the repo's HEAD, refs, index, tracked status, local git config and worktrees match its pre-run snapshot and the run's sidecar reports no change. Otherwise the hold stays, lists the changes and notifies; delete the file after checking. On 2026-10-25 an agoge lane committed, tagged and moved a remote-tracking ref in the product, and the run still exited 0.
~~~
