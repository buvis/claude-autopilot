## Architecture fit

`skills/run-autopilot/cli/` is already the sole owner of git-state decisions
the loop makes about itself (`custody.py`'s `git_argv`/`project_root`,
`records.py`'s `_capture_range` repo_root/git_dir fallback, the wave modules'
own `run_git` injection convention). This PRD adds one more foundation module
in that layer, `cli/store_tree.py`, with zero internal dependencies (pure
over an injected `run_git`, mirroring `wave_launch.py`'s `_default_run_git`
pattern) — Phase 0 of the Dependency Graph. Every other change is a caller
switching from a raw `git status --porcelain` call, or prose that names one,
to this module's predicate: the wave CLI refusals (`wave_launch.py`,
`wave_assemble.py`, `wave_review.py`), the task-boundary handoff
(`skills/work/references/task-boundary-handoff.md`), the stand-down procedure
and Session handoff procedure (`skills/run-autopilot/SKILL.md`), the
cap-rotation hook's instructions (`autopilot_context_cap_hook.py`), and
fast-track's per-item "foreign dirt" report (`skills/fast-track/SKILL.md`).
None of these move layers; they gain one call each.

## Module placement

New files:
- `skills/run-autopilot/cli/store_tree.py` — `STORE_PREFIXES`,
  `foreign_dirty`, `record_store`, each pure over an injected `run_git`.
- `skills/run-autopilot/cli/test_store_tree.py` — unit tests for the module.
- `skills/run-autopilot/scripts/test_store_tree_prose.py` — pins every prose
  site below to the new wording, and runs the `.gitignore`/Retention-list
  parity check.
- `docs/dev/project-management/.gitignore` — created by the Phase 0 `mkdir`
  step, not by a skill edit; see Interfaces.

Edited files:
- `skills/run-autopilot/cli/__main__.py` — two thin subparsers, `dirty` and
  `record-store` (`_add_dirty`/`_run_dirty`, `_add_record_store`/
  `_run_record_store`), registered in the existing `(add_parser_fn, run_fn)`
  dispatch table (~line 1157).
- `skills/run-autopilot/cli/custody.py` — one new function,
  `repo_and_git_dir(autopilot_dir)`, the bare-repo-aware resolver shared by
  `__main__.py`'s two subparsers and `loop.py`'s wrapper-level calls below.
- `skills/run-autopilot/cli/loop.py` (`Loop._run_loop`, after
  `_append_metrics`) and `skills/run-autopilot/cli/loop_act.py`
  (`ActMixin._act_done`, after the state-final.json archive and QA/purge) —
  the wrapper's own `record_store` calls, covering the tracked writes the
  Claude session's own handoff-time `record-store` cannot reach because
  they happen after the session has already exited (dispatch 3/codex).
- `skills/run-autopilot/cli/wave_launch.py:141` (`_refusal`),
  `wave_assemble.py:273` (`_refusals`) and `wave_review.py:286`
  (`_check_reviewable`) — swap the raw
  `run_git(["status", "--porcelain"], ...)` for
  `store_tree.foreign_dirty(repo, run_git=run_git)`. `wave_review.py:402-413`
  (`_land_cleanup`) and `wave_launch.py:440` (`_keep_verdict`) are
  deliberately NOT in this list — see Risks & edge cases.
- `skills/run-autopilot/SKILL.md` — § Session Loop's stand-down procedure
  (the `dirty_tree` evidence test) and § Session handoff procedure step 2
  (new sub-step before the `leave` row) and § Retention (one sentence tying
  the Disposable list to the `.gitignore` file) and the Phase 0 lifecycle
  `mkdir` block (ship the `.gitignore`).
- `skills/run-autopilot/scripts/autopilot_context_cap_hook.py`'s
  `_rotation_instructions` — one added sentence.
- `skills/work/references/task-boundary-handoff.md` step 3e.
- `skills/fast-track/SKILL.md` lines 46-50 and 204.
- `skills/run-autopilot/references/*.md` whichever reference files quote the
  stand-down/handoff prose verbatim (the design doesn't enumerate these by
  line; the prose test (`test_no_gate_parses_porcelain_by_hand`) is what
  planning/work drive to green — see Test Strategy).
- `dev/bin/release-checks` — one new `[checks] store tree` block.
- `CHANGELOG.md` — one `### Changed` / `**run-autopilot**` bullet.
- `.git/info/exclude` (this repo) — delete line 20, `/docs/` (and the
  2026-09-30 comment above it at line 19). This is the actual precondition
  for everything else in this PRD: `.git/info/exclude` is per-checkout, not
  version-controlled, so no commit in this repo's history can flip it for
  another clone — it is a plain file edit, in scope for this PRD's own task
  list because the file lives inside THIS checkout. Until it is removed,
  `record_store`'s `git add -A -- docs/dev/project-management` adds nothing
  (git silently skips an excluded path) and `foreign_dirty` never sees
  anything under `docs/` in porcelain in the first place — every mechanism
  below is inert until this line is gone. See Risks & edge cases for the
  claude-plugins repo, which needs the identical edit but is out of this
  PRD's file scope (a different repo).

## Interfaces & contracts

### `cli/store_tree.py` (new, zero internal deps)

```python
from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

RunGit = Callable[..., "subprocess.CompletedProcess[str]"]

# Trailing slash matters: a sibling like `docs/dev/project-management-notes/`
# must not match.
STORE_PREFIXES = ("docs/dev/project-management/", "docs/dev/tmp/")


def _default_run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """`git <args>` in `cwd`. Raises `subprocess.CalledProcessError` on a
    non-zero exit — callers that must survive a failing git call (commit)
    catch it themselves; `status`/`diff`/`rev-parse` never fail here."""
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    )


def _porcelain_paths(raw: str) -> list[str]:
    """Parse `git status --porcelain -z` output into a flat path list. A
    rename/copy record (`XY` with `X` or `Y` in `RC`) is two consecutive
    NUL-terminated fields — `XY NEW\\0OLD\\0` — and contributes BOTH paths,
    so a rename out of the store is foreign even though the entry's own
    `XY NEW` slot shows the destination (which may be inside the store)."""
    fields = raw.split("\0")
    if fields and fields[-1] == "":
        fields = fields[:-1]
    paths: list[str] = []
    i = 0
    while i < len(fields):
        entry = fields[i]
        xy, path = entry[:2], entry[3:]
        paths.append(path)
        if "R" in xy or "C" in xy:
            i += 1
            paths.append(fields[i])
        i += 1
    return paths


_STORE_PATHSPEC = ":(top)docs/dev/project-management"


def foreign_dirty(
    repo: Path, run_git: RunGit = _default_run_git
) -> list[str]:
    """Porcelain paths in `repo` outside the store, repo-relative and
    normalized. `--untracked-files=all` is mandatory: without it, an
    entirely-untracked `docs/` (a fresh checkout, or a repo where the store
    was never tracked before) collapses to one `?? docs/` entry that fails
    the `STORE_PREFIXES` check and reads as foreign dirt even though every
    file under it is store-owned — `-z` alone does not change git's default
    directory-collapsing. [] means `repo` is clean of anything the store
    doesn't own."""
    result = run_git(
        ["status", "--porcelain", "-z", "--untracked-files=all"], cwd=repo
    )
    return [
        path
        for path in _porcelain_paths(result.stdout)
        if not path.startswith(STORE_PREFIXES)
    ]


def record_store(
    repo: Path,
    site: str,
    prd: str,
    run_git: RunGit = _default_run_git,
) -> str | None:
    """Stage and commit ONLY `docs/dev/project-management`, leaving any
    OTHER already-staged path exactly as staged (never swept into this
    commit, never unstaged). Returns the new commit sha, or None when the
    store itself had nothing to commit. ANY failure in this function —
    `add`, the cached diff, `commit`, or the final `rev-parse` — is caught,
    normalized to one stderr line (embedded newlines collapsed), and
    answered with `None`. It NEVER raises, so a handoff that calls this
    never fails on it, matching the PRD's best-effort contract."""
    try:
        run_git(["add", "-A", "--", _STORE_PATHSPEC], cwd=repo)
        staged = run_git(
            ["diff", "--cached", "--name-only", "--", _STORE_PATHSPEC], cwd=repo
        ).stdout.strip()
        if not staged:
            return None
        subject = (
            f"chore(autopilot): record {site} state for {prd}"
            if prd
            else f"chore(autopilot): record {site} state"
        )
        # `git commit <pathspec>` records the matching slice of the CURRENT
        # WORKING TREE (not literally the staged snapshot — a working-tree
        # edit made after `add` but before this call would be swept in
        # too; `record_store`'s own `add` immediately precedes this call,
        # so the two coincide here), while any OTHER already-staged path
        # outside the pathspec stays staged and untouched — the fix for
        # "record_store can commit another writer's staged files"
        # (dispatch 2, codex): `git diff --cached`/`git commit` with no
        # pathspec inspect and commit the WHOLE index, not just what `add`
        # just staged. Wording corrected per dispatch 3 (codex,
        # verification): "incorrectly described as committing an index
        # slice."
        run_git(["commit", "-m", subject, "--", _STORE_PATHSPEC], cwd=repo)
        return run_git(["rev-parse", "HEAD"], cwd=repo).stdout.strip()
    except (subprocess.CalledProcessError, OSError) as exc:
        detail = getattr(exc, "stderr", None) or str(exc)
        one_line = " ".join(str(detail).split())
        print(f"autopilot: record-store failed: {one_line}", file=sys.stderr)
        return None
```

`foreign_dirty`'s rename rule answers the PRD's `(guess)`: either side outside
the store makes the entry foreign. This also means a rename FULLY inside the
store (e.g. a PRD moving `backlog/` → `wip/`) contributes nothing, which is
the behavior every call site needs.

Every store pathspec in this module is the `:(top)docs/dev/project-management`
magic-pathspec form, never the bare string, per the operator's own standing
note for a bare-repo-backed root (`~/.claude/AGENTS.md`'s dotfiles-repo
section): a pathspec normally resolves
against the process's **current working directory**, not `--work-tree` — a
bare `docs/dev/project-management` run from a subdirectory of the work-tree
silently resolves to `<cwd>/docs/dev/project-management` and finds nothing.
`:(top)` anchors it to the work-tree root regardless of `cwd`. This is also
why `cli/__main__.py`'s `_store_git` (below) must pass a real `cwd` through
to `subprocess.run` rather than relying on `--work-tree` alone — dispatch 2
(codex) caught both the missing `:(top)` and the dropped `cwd` as one defect
("Bare-repo recording resolves the store path against the caller's
directory").

### `cli/custody.py` addition (one small resolver, shared by three callers)

Dispatch 3 (codex, verification) found that `record-store`'s one call site
in the session handoff procedure cannot satisfy the PRD's own success
metric ("`git status --porcelain` empty after every leave row") alone: the
**wrapper** (`cli/loop.py`, a plain Python process, not the Claude session)
keeps writing tracked store files AFTER the session that ran `record-store`
has already exited — `_append_metrics` (loop-metrics.jsonl, called right
after `_decide`) and `loop_act.py`'s `_act_done` (`reports/{batch}-state-
final.json` on drain, plus the agoge QA report). These need their own
`record_store` call, made directly by the wrapper in Python — not by
shelling out to `autopilot record-store`, since `loop.py` already runs in
the same interpreter and can import `cli.store_tree` directly. This is a
THIRD caller needing the same bare-repo-aware repo resolution
`cli/__main__.py`'s `_store_git` already has, so that resolution moves to
`cli/custody.py` (which already owns `git_argv`/`project_root`) as one
small function, instead of a third copy:

```python
def repo_and_git_dir(autopilot_dir: Path) -> tuple[Path, str | None]:
    """(repo_root, git_dir) for the project `autopilot_dir` belongs to:
    `state.repo_root`/`state.git_dir` when set (the bare-repo-backed case),
    else `project_root(autopilot_dir)` with no git_dir. Tolerant of a
    missing or unreadable state.json — returns the project_root fallback,
    never raises. The one resolver `cli/__main__.py`'s `dirty`/
    `record-store` subparsers and `cli/loop.py`'s wrapper-level recording
    calls all share."""
    try:
        data = json.loads((autopilot_dir / "state.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    repo_root = Path(data.get("repo_root") or project_root(autopilot_dir))
    return repo_root, data.get("git_dir")
```

### `cli/__main__.py` additions (thin; this file is pre-existing debt over
the 800-line cap per PRD 00223's batch report — these two subparsers add
~25 lines and do not touch that debt)

```python
def _add_dirty(subparsers) -> None:
    p = subparsers.add_parser("dirty")
    p.add_argument("--state")


def _run_dirty(args: argparse.Namespace) -> int:
    state_path = _resolve_state_path(args.state)
    repo_root, run_git = _store_git(state_path)
    paths = store_tree.foreign_dirty(repo_root, run_git=run_git)
    for path in paths:
        print(path)
    return 1 if paths else 0


def _add_record_store(subparsers) -> None:
    p = subparsers.add_parser("record-store")
    p.add_argument("--state")
    p.add_argument("--site", required=True)
    p.add_argument("--prd", default="")


def _run_record_store(args: argparse.Namespace) -> int:
    state_path = _resolve_state_path(args.state)
    repo_root, run_git = _store_git(state_path)
    sha = store_tree.record_store(repo_root, args.site, args.prd, run_git=run_git)
    if sha:
        print(sha)
    return 0


def _store_git(state_path: Path) -> tuple[Path, Callable]:
    """repo_root + a `(args, cwd) -> CompletedProcess` git runner, from the
    shared `custody.repo_and_git_dir` resolver (also used by `cli/loop.py`'s
    wrapper-level recording calls — see the `cli/custody.py` addition
    above)."""
    autopilot_dir = state_path.parent
    repo_root, git_dir = custody.repo_and_git_dir(autopilot_dir)
    prefix = custody.git_argv(str(repo_root), git_dir)

    def run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
        # `cwd` must reach subprocess.run even in the bare-backed branch:
        # `custody.git_argv`'s bare-repo prefix carries `--git-dir`/
        # `--work-tree` but no `-C`, and `--work-tree` does NOT anchor
        # pathspec resolution — git still resolves a relative pathspec
        # against the process cwd. Dropping this kwarg (an earlier draft
        # did) silently resolved `docs/dev/project-management` beneath
        # whatever directory the CLI happened to be invoked from instead
        # of the work-tree root (dispatch 2, codex).
        return subprocess.run(
            [*prefix, *args], cwd=cwd, capture_output=True, text=True, check=True
        )

    return repo_root, run_git
```

`dirty` and `record-store` must work before `state.json` exists (e.g. the
Phase 0 stand-down check on a from-empty batch) — `custody.repo_and_git_dir`
is tolerant of that by construction (its own `try`/`except` around the
`state.json` read), so both verbs always resolve a repo even with no state
file, falling back to `project_root`'s derivation from the autopilot dir's
own path shape (`.../docs/dev/project-management/autopilot` → four parents
up).

Exit codes: `dirty` → 0 (clean) / 1 (foreign paths printed, one per line).
`record-store` → always 0 (prints the sha on stdout when it committed,
nothing otherwise) — a commit failure is reported on stderr by `store_tree`
itself and must never fail the handoff that called it.

### `cli/loop.py` / `cli/loop_act.py` additions (the wrapper's own recording calls)

`Loop._run_loop` (`cli/loop.py`), after `self._append_metrics(...)` (the
call already there, around line 583) and before `self._act_branch(...)`:

```python
from cli import store_tree

...
self._append_metrics(
    ap_dir, ts_start, ts_end, decision, phase_launched, plan.model, plan.effort,
)
repo_root, git_dir = custody.repo_and_git_dir(ap_dir)
store_tree.record_store(
    repo_root, "loop", decision.get("prd", ""),
    run_git=_wrapper_run_git(git_dir),
)
code = self._act_branch(decision, ap_dir)
```

(`_wrapper_run_git(git_dir)` is a one-line local closure built from
`custody.git_argv`, the same shape `cli/__main__.py`'s `_store_git` builds —
not spelled out twice here, same pattern.) This covers `loop-metrics.jsonl`.

`ActMixin._act_done` (`cli/loop_act.py`), after the `state_path.replace(...
-state-final.json)` archive and after `run_agoge`/`run_purge` (whichever of
those actually wrote something), one more `store_tree.record_store` call
with `site="drained"` — covering the archived state file and the agoge QA
report, the two drained-exit writes dispatch 3 named. This is the FINAL
possible store write in a batch's lifetime; nothing downstream can dirty the
store again once this call returns.

**Stop-hook bookkeeping files need gitignore entries too** (dispatch 3):
`.review-gate-blocks`, `.review-gate-failed` (`review_coverage_hook.py`) and
`.lane-guard-blocks` (`guard_stop_on_live_lanes.py`) are per-session counters
and failure markers, written and removed by hooks outside any session's
control — the same volatile-control-file class as `.handoff-requested`/
`.cap-fired`. Add all three to both the `.gitignore` body and the Retention
Disposable bullet (sites 3-4 above), alongside the other hook markers.

### Wave CLI callers (edits, not new contracts)

`wave_launch.py:141`: replace
`if run_git(["status", "--porcelain"], cwd=repo).stdout.strip():` with
`if store_tree.foreign_dirty(repo, run_git=run_git):` (same `run_git`
injection already in scope; `foreign_dirty` takes the plain two-arg
`(args, cwd)` signature `_default_run_git` already uses here, so no adapter
needed — `wave_launch.py`'s own `_default_run_git` IS already store_tree's
`RunGit` shape).

`wave_assemble.py:273`: same substitution in `_refusals`.

`wave_review.py:286` (`_check_reviewable`): same substitution; keep raising
`ValueError` with the printed path list
(`"\n".join(store_tree.foreign_dirty(repo, run_git=run_git))`).

`wave_review.py:402-413` (`_land_cleanup`): **NOT touched — stays on today's
raw porcelain with its narrow `:(exclude)<migrated_stub>`.** An earlier draft
of this design swapped it to `foreign_dirty` on the reasoning that the manual
exclude becomes redundant once the store itself is the ignore rule; dispatch
2 (codex) and the Claude fallback dispatch both independently flagged this as
a blocker ("Assembly cleanup can destroy uncommitted store artifacts"): this
call sits immediately before `git worktree remove --force`, and
`foreign_dirty` treats EVERY store path as non-foreign, so a crash or a
skipped handoff that left real uncommitted store writes in the assembly
worktree (a stuck review file, a ledger append, a mid-handoff `state.json`)
would read as "clean" and the worktree — and that uncommitted work — would
be force-removed with no error. This is the exact same data-loss shape the
Risks section already calls out for `wave_launch.py:440`'s abort-keep check,
and the reasoning is identical: a destructive step must never be gated on a
predicate that calls real uncommitted work invisible. Leave this call exactly
as it is today.

### `docs/dev/project-management/.gitignore` (new, shipped by the Phase 0
`mkdir` step — a plain file write guarded by "create if absent", not a
skill-authored edit)

```
autopilot/state.json
autopilot/state.json.bak
autopilot/*.lock
autopilot/.turn-counts.json
autopilot/.handoff-requested
autopilot/.cap-fired
autopilot/.session-left
autopilot/.review-gate-blocks
autopilot/.review-gate-failed
autopilot/.lane-guard-blocks
autopilot/lanes/
autopilot/wave-slots/
autopilot/wave.json
autopilot/review-paths
autopilot/last-session.log
autopilot/wrapper.log
autopilot/pause-requested
autopilot/paused-by-operator
autopilot/park-requested
autopilot/session-brief.md
autopilot/contract-card.md
autopilot/replan-context.md
autopilot/last-verification.json
```

One path per line, no trailing blank-line requirement beyond the final
newline; `test_store_gitignore_matches_the_disposable_list` reads both this
file and the core `SKILL.md` Retention "Disposable" bullet and asserts the
same basename set (`autopilot/state.json` form, not `docs/dev/…`-prefixed,
since the file already lives inside the store and the patterns are relative
to it).

**This list is NOT simply the PRD's `Feature: Volatile control files stay
ignored` text copied verbatim.** Checking it against the CURRENT
`SKILL.md` § Retention "Disposable" bullet (dispatch 2/claude-fallback,
Blocking: "Design's own worked `.gitignore` content omits two files the real
SKILL.md Disposable list names, and adds others it doesn't") found the two
lists disagree in both directions: the Disposable bullet already names
`autopilot/wave.json` and `autopilot/review-paths`, which the PRD's text
omits (now added above); and the PRD's text names
`state.json.bak`/`*.lock`/`.turn-counts.json`/`.handoff-requested`/
`.cap-fired`/`contract-card.md`/`park-requested`/`last-verification.json`,
each a genuinely volatile per-session file referenced elsewhere in
`SKILL.md` (the cap hook's markers, the Contract card section, the
Session handoff procedure) but missing from the Disposable bullet's own
prose today. The `.gitignore` body above is the union, and it is correct —
the defect was in the two sources disagreeing, not in either alone.
**Site 3 below (the Retention sentence) is therefore not just "add one
sentence": it also updates the Disposable bullet itself to name the same
items this `.gitignore` names**, so the parity test has two matching lists
to check from day one rather than asserting a fact that's false at
Phase-2 start.

### Prose-site contracts (exact behavior, wording left to the task that
touches each file)

1. **`SKILL.md` § Session Loop, stand-down procedure.** The `dirty_tree`
   condition's test changes from "`git status --porcelain` lists a tracked
   path this session did not edit" to "`autopilot dirty` prints at least one
   path" — same evidence, store writes no longer qualify as that evidence.
2. **`SKILL.md` § Session handoff procedure, step 2.** Insert
   `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-autopilot/cli/__main__.py
   record-store --state <state.json> --site <build|review|done> --prd
   <state.prd>` (best-effort, like the row write — a failure is one stderr
   line, never a reason to skip the row or the STOP) **AFTER the `leave` row,
   as the last write before STOP** — NOT between the brief and the row as
   the PRD's own Feature description guesses. The PRD's placement fails its
   own Success Metric ("`git status --porcelain` is empty after every
   session's leave row", dispatch 2/codex: "The leave row dirties the store
   after its recording commit"): the `leave` row itself is
   `record_dispatch.py`'s append to `dispatch-metrics.jsonl`, a tracked
   store file — committing before that row leaves that one jsonl append
   uncommitted every single handoff. Placing `record-store` last means the
   row's own write is swept into the same commit. Runs at every site in the
   existing table (`build → review`, `review → review`, `review → done`,
   `build → done`, `PRD → PRD`, `batch end`).
3. **`SKILL.md` § Retention.** Two changes: (a) the Disposable bullet itself
   gains the eleven items it is currently missing —
   `autopilot/state.json.bak`, `autopilot/*.lock`,
   `autopilot/.turn-counts.json`, `autopilot/.handoff-requested`,
   `autopilot/.cap-fired`, `autopilot/contract-card.md`,
   `autopilot/park-requested`, `autopilot/last-verification.json`,
   `autopilot/.review-gate-blocks`, `autopilot/.review-gate-failed`,
   `autopilot/.lane-guard-blocks` — so it names the exact same set as the
   `.gitignore` body above (it already named `wave.json`/`review-paths`,
   which the PRD's draft list omitted — those stay). (b) one added sentence
   after the bullet: "The machine form of this list is
   `docs/dev/project-management/.gitignore`, shipped by the Phase 0 `mkdir`
   step; a test keeps the two in step."
4. **Phase 0 lifecycle `mkdir` block** (core `SKILL.md` § "Phase 0
   invariants" and `references/phase-build.md` § "Ensure lifecycle
   directories exist"). After the existing `mkdir -p`, write
   `docs/dev/project-management/.gitignore` with the Write tool **only when
   it does not already exist** — this must stay idempotent and must never
   clobber a hand-edited copy.
5. **`autopilot_context_cap_hook.py`'s `_rotation_instructions`.** One
   sentence added after the `wip - rotated mid-task` commit instruction and
   before "Then STOP": "Also run `autopilot record-store --site <phase>
   --prd <the PRD>` so this session's store writes are committed before the
   rotation hands off." **`--site <phase>` interpolates this function's own
   `phase` parameter (`"build"` or `"review"`), not a literal `"build"`** —
   the function already branches on `phase` to build the `resume` text one
   paragraph earlier; a hardcoded `--site build` would mislabel every
   review-phase rework rotation's commit (dispatch 2/claude-fallback:
   "Review rotations are recorded as build rotations").
6. **`task-boundary-handoff.md` step 3e.** Becomes: confirm `autopilot
   dirty --state <dir>/state.json` is empty (replaces "Confirm the working
   tree is clean (`git status --short` empty)"); same "do not hand off,
   investigate first" rule on a non-empty result. No `record-store` call
   belongs at step e — `autopilot dirty` already excludes the store from
   "dirty" whether or not it is committed, so the check needs nothing
   committed first to pass; conflating the check with the commit at this
   step was an earlier draft's mistake (see step h below for where
   `record-store` actually belongs). This genuinely fixes a false refusal:
   durable store artifacts written mid-phase (ledger `.jsonl` appends,
   review files) are real uncommitted tracked paths once the store is
   tracked, and `git status --short` would see them and block the handoff
   even though nothing is actually wrong — `autopilot dirty` does not.
   **`task-boundary-handoff.md` step 3h** (not 3e) gains the `record-store`
   call, at the same position as site 2 above: AFTER the `leave` row, as the
   last write before STOP, so the row's own `dispatch-metrics.jsonl` append
   is swept into the commit too.
7. **`fast-track/SKILL.md` lines 46-50 and 204.** Both already use the word
   "foreign" for a dirty path outside the card's known files — this PRD
   gives that word a precise meaning. Line 46's "Run `git status --porcelain`
   and account for every dirty path" becomes "Run `autopilot dirty --state
   <path>` and account for every path it prints" (store churn from this very
   session's own prior writes no longer needs accounting for). Line 204's
   "Any other dirty path is foreign: leave it unstaged and name it in the
   report" is unchanged in meaning — "dirty path" there already means
   whatever `autopilot dirty` reports, once line 46 is fixed — but reads
   "Run `autopilot dirty --state <path>`; any path it still prints, beyond
   the staged `FILES_TOUCHED:` set, is foreign: leave it unstaged and name it
   in the report."
8. **`dev/bin/release-checks`.** New block, placed beside `[checks] waves`:
   ```bash
   echo "[checks] store tree"
   uv run --no-project --with pytest python -m pytest -q \
     skills/run-autopilot/cli/test_store_tree.py \
     skills/run-autopilot/scripts/test_store_tree_prose.py
   ```
9. **`CHANGELOG.md`.** One bullet under `## [Unreleased]` → `### Changed` →
   `**run-autopilot**`: "the tracked `docs/dev/project-management` store no
   longer trips clean-tree gates or the stand-down procedure; each session
   commits its own store writes before handing off."
10. **`.git/info/exclude`, this repo.** Replace the `/docs/` line (and its
    preceding comment) with `/docs/dev/tmp/` — this keeps the one tree
    `rules/working-documents.md` says must stay globally gitignored
    gitignored, while un-excluding everything else under `docs/`,
    including `docs/dev/project-management/`. Plain file edit, no test can
    pin a per-checkout file's content across clones, so this is verified by
    hand: `git check-ignore -v docs/dev/project-management/autopilot/state.json`
    exits **0**, naming `docs/dev/project-management/.gitignore` as the
    match (it IS still ignored — by the new per-store file now, not by
    `.git/info/exclude`); `git check-ignore -v
    docs/dev/project-management/prds/done/<any>.md` exits **1** (a durable
    store path, genuinely trackable); `git check-ignore -v
    docs/dev/tmp/anything` still exits 0. (Corrected from an earlier draft
    that expected `state.json` itself to come back unignored — dispatch
    2/claude-fallback: "The rollout verification expects the wrong
    check-ignore result.")
11. **`work/references/gate-failure.md`, the ESCALATE reset guard (around
    "uncommitted:") — considered, deliberately NOT switched to
    `autopilot dirty`; stays on raw porcelain.** An earlier draft of this
    design (wrongly) treated this as a site to fix, reasoning that store
    churn here only costs the safe fix-forward path instead of the fast
    reset. Dispatch 3 (codex, verification) caught the actual shape of the
    bug: this guard gates a `git update-ref` immediately followed by
    `git reset --hard <test_commit_sha>` — a destructive discard of
    anything not yet committed. `autopilot dirty` calling every store path
    invisible would let an uncommitted tracked review edit or ledger append
    pass the guard and then be destroyed by the hard reset — the exact same
    data-loss shape as `_land_cleanup` and `wave_launch.py:440`, which the
    design already protects. This is a third instance of the same pattern:
    **a destructive step's precondition check must never be relaxed to
    ignore the store**, only a non-destructive refusal/friction gate may be.
    Leave this guard exactly as it is today (`work/references/gate-failure.md`
    gets no edit for this site); list it in Risks & edge cases alongside the
    other two.
12. **`work/references/rework-mode.md:20`, the micro-lane eligibility
    check — considered, no change.** This also runs an unscoped
    `git status --porcelain`, but only to confirm that SPECIFIC named files
    (the ones the task is about to touch) are clean — it never treats the
    whole porcelain output as a pass/fail gate, so store churn elsewhere in
    the tree cannot block it today and needs no fix. Named here (like
    `pause.py`, site 13 below) so the PRD's "~16 sites" inventory is
    traceably accounted for rather than silently dropped.
13. **`pause.py` — no code change.** The PRD's Structural Decomposition
    names `pause.py` beside the wave modules as a `foreign_dirty` importer,
    but `pause.py` contains no git call and no porcelain parsing — it only
    reads/writes the `pause-requested` marker JSON, including the
    `condition` field (`dirty_tree` among its values). That field is
    WRITTEN by the stand-down procedure prose (site 1 above), not computed
    in `pause.py`. Site 1's rewrite (`autopilot dirty` replacing the raw
    porcelain read) is what satisfies the PRD's intent for this site;
    `pause.py` itself is correctly left untouched. See Risks & edge cases.

## Data flow

A session's store writes (PRD moves, `state.json` fields via `statectl`,
ledger `.jsonl` appends, review/design files) accumulate as working-tree
changes under `docs/dev/project-management/` throughout the session, exactly
as today. At each hand-off site (§ Session handoff procedure, the
task-boundary handoff, the cap-rotation instructions, the drained exit), the
NEW step calls `record-store`, which `git add -A -- docs/dev/project-management`
+ commits in one local commit (no push — matches every other autopilot
commit). Any gate that needs to know "is anything ELSE dirty" (stand-down,
the wave refusals, fast-track's per-item report, the task-boundary confirm)
calls `dirty`, which reads the live porcelain and filters by prefix — it
does not depend on `record-store` having run first (a session that crashed
before committing still reports its own leftover store dirt as non-foreign,
by design: that dirt is this PRD's problem to swallow, not the gate's job to
flag).

## Reuse inventory

- `cli/custody.py:git_argv(repo_root, git_dir)` (lines 133-138) — the
  `--git-dir`/`--work-tree` vs. `-C` prefix builder for a bare-repo-backed
  root. Reused directly in `__main__.py`'s new `_store_git` helper instead of
  reinventing bare-repo detection.
- `cli/custody.py:project_root(autopilot_dir)` (lines 176-179) — derives the
  repo root purely from the autopilot dir's path shape; reused as the
  no-`state.repo_root`-yet fallback.
- `cli/records.py:_capture_range` (lines 262-279) — the exact
  `repo_root = current.get("repo_root") or str(custody.project_root(...))` /
  `git_dir = current.get("git_dir")` fallback pattern this PRD's `_store_git`
  copies verbatim (same two fields, same precedence).
- `cli/wave_launch.py:_default_run_git` (lines 39-50) and
  `cli/wave_assemble.py:_default_run_git` (lines 132-148, the one
  `wave_review.py` actually imports — `wave_review.py:20` does `from
  cli.wave_assemble import _default_run_git`, it defines no copy of its
  own) — both share the `(args, cwd) -> CompletedProcess` shape
  `store_tree.RunGit` matches, so each module's existing `run_git`
  parameter passes straight into `foreign_dirty` with no adapter.
- Searches tried and empty: `rg -n "def.*porcelain|def.*dirty" skills/`
  (nothing — no existing predicate to extend), `rg -n "gitignore"
  skills/run-autopilot/` (nothing — no prior `.gitignore` machinery to
  reuse), `~/.claude/rules-library/rationalizations.md` (absent on this
  host; reuse sweep ran on verb/noun synonyms chosen by hand: `dirty`/
  `foreign`/`porcelain`/`clean`/`uncommitted`, `store`/`tracked`/`ignore`).

## Alternatives considered

1. **Smallest-diff: keep porcelain parsing at each call site, just add a
   shared prefix filter they each call.** Rejected as the shipped design's
   near-neighbor rather than a real alternative — it duplicates the `-z`
   parsing (including the rename two-field quirk) at 4+ call sites instead
   of once, which is exactly the kind of drift PRD 00236's own problem
   statement is about (today's bug IS duplicated porcelain logic). The
   chosen design centralizes parsing in `store_tree.py` and ships a thin CLI
   wrapper so prose sites get a plain command instead of inline Python.
2. **A `pre-commit`/`post-checkout` git hook that auto-commits the store.**
   Rejected: git hooks are not portable across the operator's multiple
   checkouts of this repo (worktrees, wave lanes, a fresh clone) without a
   separate hook-install step this PRD would then also have to own, and a
   silent auto-commit on arbitrary git operations is a surprise the
   explicit `record-store` call avoids — every commit this PRD adds has a
   named site and a named caller.
3. **Chosen: a pure predicate + a thin recorder, both CLI verbs, swapped in
   at every call site.** Matches the PRD's own `cli/store_tree.py` module
   shape, keeps the store-prefix knowledge in exactly one file (testable in
   isolation per the Phase 0 exit criterion), and lets every prose site stay
   prose (`autopilot dirty`, `autopilot record-store`) rather than inlining
   Python.

## Risks & edge cases

- **Rollback plan (cardinal sin, dispatch 2/codex: "The tracking migration
  has no rollback plan"; dispatch 3/codex verification found the first
  draft of this plan itself still incomplete: "never commits the removal or
  disables the recording rollout... the command is also neither universally
  successful nor idempotent").** Restoring the deleted `.git/info/exclude`
  line alone does NOT roll this back — it only controls what git offers for
  a future `git add`, it has no effect on paths git already tracks. The
  complete, ordered rollback, owned by the operator (the human who runs
  `/plugin update` and pushes releases, per `project-batch-runs-installed-
  cache`):
  1. **Stop every loop first.** `touch
     docs/dev/project-management/autopilot/pause-requested` in each live
     checkout (§ Session Loop) — this is what actually "disables the
     recording rollout": no running session calls `record-store` or
     `autopilot dirty` with the new semantics once every loop is paused.
     Confirm no `autoclaude`/`loop` process remains (`ps`) before step 2 —
     untracking while a session is mid-commit is undefined.
  2. **Untrack, rooted and explicit, then COMMIT the untracking itself** —
     the step the first draft of this plan omitted: `git -C <repo> rm -r
     --cached -- docs/dev/project-management` (rooted with `-C`, not a bare
     `cd`-dependent invocation; `--cached` leaves every file on disk,
     working-tree untouched), then `git -C <repo> commit -m
     "chore(autopilot): untrack the store (rollback PRD 00236)"`. Without
     this commit, HEAD still lists every store path as tracked and a fresh
     clone or `git reset` brings tracking straight back. `git rm --cached`
     is not perfectly idempotent (a second run with nothing left to remove
     exits non-zero, and a path whose index content differs from both HEAD
     and the working tree is refused rather than silently skipped) — run it
     once, over a known-committed tree, not as a retry loop.
  3. **Restore `.git/info/exclude`'s `/docs/` line** (undoing site 10),
     re-establishing the pre-PRD "never offered for `git add`" boundary for
     every future session in this checkout.
  4. **Downgrade the installed plugin**, `/plugin update autopilot@buvis-
     plugins` to the pre-00236 release — the loop runs the installed
     marketplace cache, not this source checkout (`project-batch-runs-
     installed-cache`), so this is the step that actually stops a future
     resumed loop from calling `record_store`/`foreign_dirty` again; editing
     source alone does not.
  5. **Content that must never have been public** (a leaked secret already
     pushed) is a separate, unautomated operator decision — `git
     filter-repo` or a fresh orphan branch, same as any other after-the-fact
     secret-scrub, outside this PRD's code.
  No automated test exercises this runbook (it is an operator-run shell
  sequence against live git state, not CI-reproducible); the Test Strategy
  below says so explicitly rather than implying coverage that doesn't exist.
- **Likely next changes this design should not box in:** (1) a future
  second ignored-but-not-committed path outside today's Disposable list —
  `STORE_PREFIXES` and the `.gitignore` are two lists that must move
  together; the parity test is what keeps a future addition honest. (2) a
  wave lane's own worktree gaining the same tracked-store requirement for
  its `docs/dev/project-management` — already covered for free since
  `foreign_dirty` takes any `repo: Path`, lane worktree included. (3) a
  `record-store` call wanting a custom commit scope narrower than the whole
  store (e.g. "only this PRD's files") — not needed today; `record_store`'s
  signature would need a path-filter parameter, which the current one-arg
  `git add -A -- docs/dev/project-management` can't express, so a future PRD
  adding that is a signature change, not a wrapper.
- **Three sites stay on raw porcelain, by design, NOT missed sites: the
  destructive-step rule.** `wave_launch.py:440`'s abort worktree-keep
  decision, `wave_review.py:402-413`'s `_land_cleanup`, and
  `work/references/gate-failure.md`'s ESCALATE reset guard each gate a
  step that discards or overwrites uncommitted work the instant the guard
  says "clean" (worktree discard on abort; `worktree remove --force` on
  land; `git reset --hard` after a branch-ref CAS). None of the three is a
  refusal gate the PRD's own bullet names ("the `wave_launch`/
  `wave_assemble`/`wave_review` **refusals**" — a refusal just stops an
  action from starting, it doesn't discard anything that already exists).
  `foreign_dirty` calling every store path invisible would let any of the
  three destroy real uncommitted store state that never got a
  `record-store` call (abort before any handoff; a crash or skipped handoff
  in the assembly worktree; a task escalation racing a mid-write ledger
  append). **The rule this PRD applies throughout: a destructive step's
  precondition check is never relaxed to ignore the store — only a
  non-destructive refusal/friction gate may be.** `_land_cleanup` was
  flagged independently by dispatch 2 (codex) and the Claude fallback
  dispatch; the `gate-failure.md` reset guard was caught by dispatch 3
  (codex, verification) after an earlier draft of this design mistakenly
  "fixed" it. Leave all three untouched.
- **`pause.py` needs no edit** (see Interfaces site 13) — it never calls
  git; the PRD's Structural Decomposition bullet naming it is satisfied by
  the stand-down prose rewrite (site 1) instead.
- **claude-plugins carries the identical `.git/info/exclude` `/docs/` line**
  (the PRD's own Problem Statement names both repos). That repo is not this
  checkout, so this PRD cannot edit it directly; the removal there is an
  operator follow-up once this PRD's `store_tree`/`record-store` machinery
  is released and installed, same timing as any other cross-repo rollout in
  this project's history (`project-batch-runs-installed-cache` memory). Flag
  it in the exit report so the operator does not read "done" as "both repos
  done."
- **`docs/dev/tmp/` has no root-level `.gitignore` entry.** `STORE_PREFIXES`
  already excludes it from every autopilot gate, and `record_store` never
  stages it, but once `/docs/` leaves `.git/info/exclude` a plain `git
  status`/`git add -A` run by a human or another tool would see it as
  untracked — `rules/working-documents.md` already says `docs/dev/tmp/`
  must be "globally gitignored," so the same `.git/info/exclude` task (site
  10) should add `/docs/dev/tmp/` as its replacement line rather than
  deleting `/docs/` outright with nothing in its place.
- **A secret committed via a review or design file.** Already named in the
  PRD's own Risks section as an operator task outside this PRD's code; this
  design adds no new exposure (it commits exactly what already gets written
  to the store, just more promptly), but it does make that content land in
  git history sooner and on every session rather than only at an eventual
  manual commit — worth the operator's attention once `/docs/` first leaves
  `.git/info/exclude`.
- **Commit noise** (~15 `chore(autopilot)` commits per PRD) — named and
  accepted in the PRD's own Risks section; `phase-done`'s existing
  "commit history is left as-is" rule already defers squashing to the
  operator.
- **An already-existing hand-edited `.gitignore` short-circuits the parity
  guarantee** (dispatch 2/codex, non-blocking). Site 4's "write only when
  absent" rule means a `docs/dev/project-management/.gitignore` already on
  disk (pre-dating this PRD, or hand-edited later) is never reconciled
  against a Disposable-bullet change — `record_store` would then stage a
  volatile file the bullet says should never be tracked. Accepted for this
  PRD: the idempotent "create if absent" rule is what makes Phase 0 safe to
  re-run every session without clobbering an operator's edit, and this repo
  has no pre-existing `docs/dev/project-management/.gitignore` to collide
  with (confirmed: the directory does not exist yet pre-PRD). A drift
  checker that diffs an existing `.gitignore` against the current Disposable
  bullet is a reasonable follow-up, not this PRD's job.
- **`record-store` racing a concurrent reader of `state.json`.** `git add`
  snapshots the working tree at call time; a `statectl` writer and a
  `record-store` call never run in the same process turn (both are
  synchronous CLI calls from the one active session), so there is no new
  race beyond the one `statectl`'s existing advisory lock already covers.

## Test strategy outline

- `cli/test_store_tree.py` (Phase 0 exit criterion): `foreign_dirty` on a
  store-only dirty tree returns `[]`; on a mix, returns only the non-store
  paths; a rename with either endpoint outside the store is foreign even
  when the other endpoint is inside it; an entirely-untracked `docs/`
  directory (nothing tracked under it yet) still reports only non-store
  paths as foreign, not a collapsed `docs/` entry; `record_store` stages
  AND commits only `docs/dev/project-management` — a file OUTSIDE the store
  that was already staged before the call stays staged and uncommitted
  afterward (the scoped-commit regression dispatch 2/codex found); returns
  `None` with nothing committed when the store itself had nothing staged;
  survives a `run_git` that raises on ANY of `add`/`diff --cached`/`commit`/
  `rev-parse` (prints one normalized single-line stderr message, still
  returns `None`, raises nothing — not just a `commit` failure, the gap
  dispatch 2/codex found in an earlier draft that wrapped only the commit
  call); a `git commit` failure whose stderr spans multiple lines collapses
  to one stderr line.
- `cli/__main__.py`-level: `test_cli_dirty_exits_one_on_foreign_paths`
  (exit 1 + the path on stdout for a non-store dirty file; exit 0 + no
  output for a store-only dirty tree) and
  `test_cli_record_store_commits_with_the_site_and_prd` (the commit subject
  contains both `--site` and `--prd`; a sha is printed; a repeat call with
  nothing new staged prints nothing and still exits 0).
- Every existing `test_wave*.py`/`test_pause*.py` stays green unchanged —
  the refusals still refuse on a genuinely foreign dirty path, they just
  stop refusing on store-only churn (no test currently asserts a store path
  triggers a wave refusal, so this is a pure narrowing with no expected
  regression).
- **`test_no_gate_parses_porcelain_by_hand`'s exact scope** (dispatch
  2/claude-fallback, Blocking: this acceptance test's PRD wording — "no file
  under `skills/` outside `cli/store_tree.py` and tests contains `status
  --porcelain` as a gate instruction" — read literally would also flag
  `wave_launch.py:440` and `wave_review.py`'s `_land_cleanup`, both of which
  this design deliberately leaves on raw porcelain (see Risks & edge cases).
  The test scans only `.md` prose files for a `status --porcelain` (or
  `status --short`) sentence that reads as a clean-tree GATE (an "is the
  tree clean" / "confirm clean" / "refuse if dirty" framing, not a
  file-enumeration or inspection-only use like `work/SKILL.md:353`'s stage
  list or `gate-failure.md:227`'s crash-recovery note) — it does not scan
  `.py` files at all, so `wave_launch.py:440` and `_land_cleanup` can never
  trip it. `cli/store_tree.py` itself is the one `.py` file allowed to
  mention `--porcelain` literally, since it IS the implementation.
- `scripts/test_store_tree_prose.py`
  (`test_no_gate_parses_porcelain_by_hand`,
  `test_stand_down_names_autopilot_dirty`,
  `test_handoff_procedure_records_the_store_before_the_leave_row`,
  `test_store_gitignore_matches_the_disposable_list`) — structural/prose
  pins over the edited `.md`/`.py` files, same genre as the repo's existing
  `test_*_prose.py` suites.
- `bash dev/bin/release-checks` green end to end (Success Metrics).
- **Not covered by any automated test, by design:** the rollback runbook
  (Risks & edge cases) — it is an operator-run sequence against live git
  state (stop every loop, untrack, downgrade the plugin), not something a
  unit or prose test can exercise in CI.

## Review log

dispatch 1 (claude): cardinal-sin 0, blocker 2, non-blocker 1, question 1
dispatch 2 (codex): cardinal-sin 1, blocker 7, non-blocker 3, question 0 — independently cross-checked by one extra Claude dispatch run in parallel while codex's completion was still pending (both runs converged on the `_land_cleanup`/abort-worktree data-loss defect and the `.gitignore`/Disposable-bullet mismatch, reinforcing confidence in both)
dispatch 3 (codex): cardinal-sin 1, blocker 2, non-blocker 1, question 0 — verification pass over the dispatch-2 fixes; caught a third destructive-step/store-dirty-check conflation (the `gate-failure.md` reset guard), the wrapper-level post-session store writes (`loop.py`/`loop_act.py`), and an incomplete rollback plan; all fixed in this doc, no dispatch 4 (3-dispatch ceiling)
