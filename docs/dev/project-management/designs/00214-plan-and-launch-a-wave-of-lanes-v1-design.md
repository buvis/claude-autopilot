# Design: Plan and launch a wave of lanes

PRD: `dev/local/prds/wip/00214-plan-and-launch-a-wave-of-lanes-v1.md`

## Architecture fit

This is new Foundation/Core work inside the existing `skills/run-autopilot/cli/`
package (the sole `state.json`/lifecycle-mutator surface per the project
capsule's Component Boundaries). It adds a **second stateful JSON file**
(`dev/local/autopilot/wave.json`) alongside `state.json`, but `wave.json` is
NOT PRD-lifecycle state — it is a one-shot planning artifact for the *loop
launcher*, read and written only by the new `wave`/`wave_launch` modules and
never by `statectl`, the schema validator, or any gate file. It sits beside
`cli/loop_gates.py` (which it calls for the live-loop registry) and beside
`cli/lane.py` (whose `named_paths` it reuses unmodified) without changing
either. No existing module's public contract changes; this PRD only adds
three new `cli/` modules plus their argparse wiring and docs.

## Module placement

New files (all under `skills/run-autopilot/cli/` unless noted):

- `cli/wave.py` — pure cut (`shares`, `cut`) + the `wave.json` I/O (`load`,
  `save`) + `plan()`. No subprocess, no git.
- `cli/wave_launch.py` — `validate`, `launch`, `status`, `abort`,
  `lane_status`. All git/process/filesystem side effects live here, and every
  one is reachable through an injected callable so tests never touch a real
  process or the real `~/.claude/autopilot-loops/`.
- `cli/wave_cli.py` — argparse wiring only (`add`, `run`); no business logic.
- `cli/test_wave.py`, `cli/test_wave_launch.py` — new test files.
- `references/waves.md` — new operator runbook.

Edits to existing files:

- `cli/__main__.py` — one new line in `_SUBCOMMANDS`:
  `"wave": (wave_cli.add, _run_wave)` (see § `__main__.py` registration
  below for `_run_wave`, and why `wave_cli.run` cannot be registered
  directly), plus the matching import. No other line changes; the registry
  pattern (`_add_custody`/`_run_custody` at `cli/__main__.py:1110-1146`) is
  copied exactly, including the `--state` convention every existing verb
  parser already takes.
- `SKILL.md` (core) — one new row in § Retention's "Disposable" list
  (`wave.json`, `wave-slots/`) and one new bullet in § Reference Files and one
  in § Operator runbook, pointing at `references/waves.md`.
- `references/state-schema.md` — one new row in § Marker files for
  `wave.json` (it is not a marker file in the strict single-purpose sense of
  that table, but the table is where every non-`state.json` durable JSON
  artifact under `dev/local/autopilot/` is already documented, e.g.
  `critical-on-master`; a footnote line makes the distinction explicit rather
  than growing a second table).
- `dev/bin/release-checks` — one new `echo "[checks] waves"` block appended
  at the end, running `cli/test_wave.py` and `cli/test_wave_launch.py`.
- `CHANGELOG.md` — one `### Added` entry under `**run-autopilot**`.

## Interfaces & contracts

### `cli/wave.py`

```python
WAVE_APPEND_ONLY: tuple[str, ...] = ("CHANGELOG.md", "dev/bin/release-checks")
WAVE_FORCE_SHARED: tuple[str, ...] = (
    "skills/run-autopilot/SKILL.md",
    "skills/run-autopilot/references/state-schema.md",
    "skills/run-autopilot/cli/records.py",
)

def prd_paths(text: str) -> frozenset[str]:
    """lane.named_paths(text) minus WAVE_APPEND_ONLY, as a set (order doesn't
    matter past this point - shares() and the connected-components pass are
    both order-independent)."""

def shares(a: frozenset[str], b: frozenset[str]) -> bool:
    """True when path-set a and path-set b must join one lane:
    - a & b is non-empty (a literal shared path), OR
    - some x in a, y in b satisfy y == x + "/" + <anything> or the reverse
      (directory-prefix, either direction; `named_paths` never returns a
      trailing slash, so the prefix check is `y.startswith(x + "/")`), OR
    - a contains ANY WAVE_FORCE_SHARED path AND b contains ANY
      WAVE_FORCE_SHARED path (not necessarily the SAME one - two PRDs each
      naming a different force-shared file still join, per the PRD's "every
      PRD naming one of them joins one lane")."""

@dataclass(frozen=True)
class Lane:
    name: str            # "l<order>"
    order: int           # 1..n, assignment order (see _order_lanes)
    branch: str           # "wave/<wave_id>/l<order>"
    worktree: str         # "<repo_parent>/<repo_basename>-l<order>"
    prds: tuple[str, ...] # basenames, PRD sequence order preserved
    paths: tuple[str, ...]
    status: str = "planned"  # "planned" | "running" | "aborted" | "abort_failed"
    pid: int | None = None    # ALSO the process-group id (start_new_session
                               # makes pid == pgid at spawn time; nothing else
                               # is stored for group liveness - see abort())
    started_at: str | None = None
    worktree_created: bool = False  # set True right after `worktree add`
                                     # succeeds for this lane (dispatch 3's
                                     # blocker: path+branch matching alone,
                                     # at wave.json's minute-resolution id,
                                     # cannot prove THIS launch created the
                                     # worktree - abort() requires this flag
                                     # AND the git-registry match, below)
    abort_error: str | None = None  # set by abort() on a failed cleanup step
                                     # (including "still alive after SIGKILL")

    def as_dict(self) -> dict: ...   # dataclasses.asdict(self), tuples -> lists

def cut(
    prds: dict[str, str], max_lanes: int = 3
) -> tuple[list[Lane], list[dict]]:
    """Pure - no disk, no git, no wave id (the caller stamps name/branch/
    worktree/order after packing; `Lane` here is returned with `name="",
    branch="", worktree="", order=0` and the caller's `_stamp` fills them -
    see `plan()`). `prds` maps PRD basename -> full PRD text, insertion order
    = ascending 00XXX- sequence number (the caller's job, `cut` trusts it for
    "ties by lowest PRD number").

    Steps: for every prd, path_sets[prd] = prd_paths(text); a prd with an
    empty path_sets[prd] is held back (`{"prd": name, "reason": "no named
    paths"}`) and excluded from the cut entirely. Union-Find over the
    remaining PRDs using `shares` pairwise -> connected components, each
    component a list of basenames in ascending sequence order. Greedy pack:
    sort components by size descending (ties: lowest PRD number first);
    walk components in that order, assigning each to the lane (of up to
    `max_lanes` open lanes) with the fewest PRDs so far, opening a new lane
    only while fewer than `max_lanes` are open. Returns
    `(unstamped_lanes, held_back)` - `unstamped_lanes` in packing order, not
    yet given `order`/`name`/`branch`/`worktree`."""

def _order_lanes(lanes: list[Lane], wave_id: str, repo: Path) -> list[Lane]:
    """Stamps `order` (1..n): lanes owning >=1 WAVE_FORCE_SHARED path, or a
    path under `skills/run-autopilot/cli/` or
    `skills/run-autopilot/references/`, sort first, by descending count of
    such paths, ties by lowest PRD number in the lane; remaining lanes keep
    packing order. Then stamps `name="l<order>"`,
    `branch="wave/<wave_id>/l<order>"`,
    `worktree="<repo.parent>/<repo.name>-l<order>"`."""

class WaveCorruptError(Exception):
    """path exists but is unreadable or not valid JSON - distinct from
    "no wave.json yet" so a caller never treats a corrupt file as "no plan"
    and silently overwrites the only control record for lanes that may still
    be running (dispatch 2's blocker: load()'s original None-for-everything
    contract could not tell the two apart)."""

def load(path: Path) -> dict | None:
    """None ONLY when `path` does not exist (genuinely "no plan yet").
    Raises WaveCorruptError(path, cause) when `path` EXISTS but
    `json.loads` fails or the read raises OSError - a real, distinct
    failure mode now that hand-editing `wave.json` between `plan` and
    `launch` is a supported workflow and a syntax error is a realistic way
    into this state. (loop_gates._load_json's None-on-any-failure contract
    is deliberately NOT copied here for that reason - a stale registry
    entry is safe to treat as absent; a wave with live lane pids is not.)"""

def save(path: Path, wave: dict) -> None:
    """Atomic write: tmp = path.with_suffix(".json.tmp.<pid>"); write; replace
    - the same tmp+rename shape as loop_gates._write_registry_entry. Callers
    (`plan`/`launch`/`abort`) hold the lock below for their entire
    load-mutate-save body; `save` itself takes no lock (it always runs
    already-locked)."""

@contextlib.contextmanager
def locked(wave_path: Path):
    """`fcntl.flock` on `<wave_path>.lock`, held for the whole body - the
    EXACT pattern `cli/state.py`'s `transaction()` already uses for
    state.json (`fcntl.flock(lock.fileno(), fcntl.LOCK_EX)` on a sibling
    `.lock` file, span the read too). Reused rather than re-invented:
    dispatch 2's blocker was that `save`'s old "one writer by construction"
    claim was just an assumption with nothing enforcing it - two operator
    shells running `wave launch` and `wave abort` at once could otherwise
    interleave a spawn with a kill. `plan`, `launch`, and `abort` each wrap
    their ENTIRE `load()`-through-`save()` body in `with locked(wave_path):`;
    `status` (read-only, no mutation) takes no lock, matching `state.py`'s
    own lock-free `load()` for read-only callers."""

def plan(repo: Path, wave_path: Path, max_lanes: int = 3) -> int:
    """with locked(wave_path):
    1. try: existing = load(wave_path) except WaveCorruptError as err: print
    "autopilot: wave.json is corrupt (<err>); fix or remove it by hand
    before planning", return 1 - NEVER overwrite a corrupt file, since a
    corrupt-but-hand-edited wave.json may still describe live lane pids.
    if existing is not None: errors = _structural_errors(repo, existing); if
    errors: print every violation, "wave.json is structurally invalid; fix
    or remove it by hand before planning", return 1 - a shape problem
    (e.g. a missing "status" key) must refuse the same as a JSON-syntax
    problem, never be indexed into blindly. Else if existing["status"] not
    in ("done", "aborted"): print the refusal (naming existing["status"])
    on stderr, return 1.
    2. prds = {p.name: p.read_text() for p in sorted((repo /
    "dev/local/prds/backlog").glob("*.md"))} - sorted() gives ascending
    00XXX- order for free (the sequence number is a fixed-width string
    prefix).
    3. lanes, held_back = cut(prds, max_lanes); lanes = _order_lanes(lanes,
    wave_id, repo) where wave_id = utcnow "%Y%m%d%H%M".
    4. Print the lane table (lane name, branch, PRDs in order, owned paths)
    then the held-back list, to stdout.
    5. wave = {"id": wave_id, "status": "planned", "repo": str(repo),
    "base_branch": None, "base_sha": None, "review_slots": 3, "created_at":
    <utcnow iso>, "lanes": [l.as_dict() for l in lanes], "held_back":
    held_back}; save(wave_path, wave); return 0."""
```

`--max-lanes` (both the CLI arg and `cut`'s own parameter) requires
`max_lanes >= 1`; `plan()` refuses with a named message and return 1 before
calling `cut` at all when it is not (dispatch 2 non-blocker: `cut`'s packing
loop has no lane to open at `max_lanes <= 0` and its behavior was otherwise
undefined).

### `cli/wave_launch.py`

```python
def _structural_errors(repo: Path, wave: dict) -> list[str]:
    """Pure. The control-field validator BOTH `validate()` (launch's
    precondition) and `abort()` run - the part with no dependency on
    current backlog PRD text, so `abort()` (which has no `prds` dict to
    give `validate()` and previously ran NO validation at all before
    trusting every hand-editable field for destructive git/filesystem
    action - dispatch 3's blocker) can call it directly on its own
    locked-and-reloaded `wave`. Returns one violation string per problem,
    empty list = structurally sound; checked in this order:
    - top level: `wave` is a dict with string `id`/`repo`/`status`
      (`status` in `("planned", "running", "aborted", "abort_failed")`),
      `wave["lanes"]` a non-empty list, `wave["review_slots"]` a positive
      int -> else "wave.json: malformed top-level field <field>".
    - `wave["repo"]` != str(repo) -> "wave.json was planned for a different
      repo".
    - per lane: every required key present; `order`/`pid` int-or-None,
      `worktree_created` bool, `name`/`branch`/`worktree`/`status` str,
      `status` in the same 4-value set as above, `order` a POSITIVE int
      (never None/0/negative - closing dispatch 3's "order=None slips
      through" gap), `prds` a non-empty list of unique str basenames ->
      else "lane <name or index>: malformed field <field>".
    - `order` not unique across lanes, or `name`/`branch`/`worktree` value
      repeated across two lanes -> "lane <a> and lane <b> both use <field>
      <value>".
    - a PRD basename repeated across two lanes, or twice within one lane's
      `prds` list -> "<prd> is listed in more than one lane" / "lane <name>
      lists <prd> twice".
    - `worktree` not equal to the canonical `_order_lanes`-derived path for
      that `repo`/`order` (guards a hand-edit pointing `abort` at an
      arbitrary filesystem path) -> "lane <name>: worktree does not match
      the canonical path for order <order>". Same check for `branch`
      against `wave/<wave["id"]>/l<order>` (guards a hand-edit that could
      otherwise defeat `abort`'s git-registry ownership comparison by
      pointing two lanes' `worktree`/`branch` at the SAME real worktree)."""

def validate(repo: Path, wave: dict, prds: dict[str, str]) -> list[str]:
    """Pure. `wave.json` is a supported hand-edit surface between `plan` and
    `launch` - so this is the one gate standing between a typo and
    destructive action. `repo` was MISSING from this signature in an
    earlier draft even though the checks below always needed it (dispatch
    3's blocker - `validate(wave, prds)` alone cannot compare `wave["repo"]`
    or derive a canonical worktree path). Returns one violation string per
    problem, empty list = valid; runs `_structural_errors(repo, wave)`
    FIRST (cheap, and a shape problem must be reported before the pricier
    path re-derivation below even attempts to index into `wave`), then:
    - `review_slots` not a positive int -> already covered by
      `_structural_errors`; not repeated here.
    - a PRD named in any lane but absent from `prds` (the backlog dict
      passed in): "lane <name>: <prd> is no longer in backlog/".
    - a PRD named in any lane whose CURRENT text has an empty path set
      (`prd_paths` returns nothing) -> "lane <name>: <prd> now names no
      paths - move it to held_back by hand before launching" (a hand-edit
      could otherwise assign a pathless PRD to a lane, which `cut` itself
      would never do).
    - two lanes whose re-derived path sets `shares()`:
      "lane <a> and lane <b> share <path>" (first shared path found; when
      the hit is `WAVE_FORCE_SHARED` rather than a literal common path,
      "lane <a> and lane <b> both touch force-shared files (<path_a> in
      <a>, <path_b> in <b>)" - the two paths need not be the same one)."""

def launch(
    repo: Path,
    wave_path: Path,
    *,
    spawn_fn=_default_spawn,
    run_git=_default_run_git,
) -> int:
    """No `wave` parameter (dispatch 3's blocker: an earlier draft took a
    caller-supplied `wave` dict without ever reloading it under the lock,
    so a concurrent `abort` finishing first left `launch` free to resurrect
    a stale snapshot and overwrite a live lane's persisted pid with the
    stale one - or null). `with locked(wave_path):` for the WHOLE body,
    starting with `wave = load(wave_path)` (the fresh, authoritative copy -
    `wave_cli.run`'s own load, before ever calling `launch`, is only the
    friendly early "no wave.json yet" message; this reload is the one that
    actually governs the mutation).

    Preconditions, each a named exit-1 refusal on stderr, checked before
    anything is created:
    - `_structural_errors(repo, wave)` non-empty -> print every violation,
      "refusing to launch" (the same structural gate `abort` now also runs -
      see `_structural_errors` above).
    - run_git(["status", "--porcelain"]) non-empty -> "dirty tree"
    - loop_gates.live_wrapper_pid(repo, DEFAULT_LOOPS_DIR) is not None ->
      "a loop is already running on the main root"
    - wave["status"] != "planned" -> "wave is not in planned state"
    - validate(repo, wave, current backlog PRD texts) non-empty -> print
      every violation, "refusing to launch"

    On success, base_sha = run_git(["rev-parse", "HEAD"]).stdout.strip();
    base_branch = run_git(["rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip();
    wave["base_branch"] = base_branch; wave["base_sha"] = base_sha;
    wave["status"] = "running"; save(wave_path, wave) - written BEFORE the
    per-lane loop starts, not after, so a lane 2+ failure never leaves
    base_sha/status stale relative to a lane 1 that is actually running (see
    Risks & edge cases: partial-launch behavior - the blocker this closes).
    For each lane in wave["lanes"] sorted by `order`:
      1. run_git(["worktree", "add", lane["worktree"], "-b", lane["branch"],
         base_sha]); a non-zero result stops the loop over lanes (see Risks
         & edge cases: partial-launch behavior) and returns 1 - lanes already
         launched (their `wave.json` entry already shows `status: "running"`
         with a real pid, per step 7's per-lane save below) are left running,
         not torn down. On success: lane["worktree_created"] = True;
         save(wave_path, wave) - persisted IMMEDIATELY, before steps 2-7 run,
         so a later step's failure (e.g. `spawn_fn` raising `OSError`) still
         leaves an accurate record that THIS lane's worktree really was
         created by this launch (dispatch 3's blocker - `abort` now checks
         this flag, not just a directory's existence, before treating a
         worktree as its own to clean up).
      2. mkdir -p <worktree>/dev/local/prds/{backlog,wip,done,hold} and
         <worktree>/dev/local/autopilot.
      3. For each prd in lane["prds"]: move
         `<repo>/dev/local/prds/backlog/<prd>` to
         `<worktree>/dev/local/prds/backlog/<prd>` (shutil.move; the PRD
         text used for validation must equal the file being moved, or
         validate() would have already caught the drift).
      4. If `<repo>/dev/local/meta` exists, shutil.copytree it to
         `<worktree>/dev/local/meta` (dirs_exist_ok=True).
      5. env = {k: v for k, v in os.environ.items() if k !=
         "_AUTOPILOT_LOOP"}; env["_AUTOPILOT_REVIEW_SLOTS_DIR"] = str(repo /
         "dev/local/autopilot/wave-slots"); env["_AUTOPILOT_REVIEW_SLOTS"] =
         str(wave["review_slots"]); env["_AUTOPILOT_TRACON_CHILD"] = "1".
      6. handle = spawn_fn(
           ["bash", "-c",
            "export _AUTOPILOT_LOOP=$$; exec python3 \"$0\" loop",
            str(CLI_MAIN_PATH)],
           cwd=lane["worktree"], env=env,
           stdout=<append to worktree/dev/local/autopilot/wrapper.log>,
           stderr=STDOUT, stdin=DEVNULL, start_new_session=True,
         ) -> object exposing `.pid`.
      7. lane["pid"] = handle.pid; lane["started_at"] = utcnow iso;
         lane["status"] = "running"; save(wave_path, wave) - persisted
         immediately after EVERY successful lane (not batched to the end of
         the loop), so `wave.json` on disk always names every lane actually
         spawned so far, and `abort`/`status` reading it mid-launch (or after
         a later lane's failure) never see a `pid: null` for a loop that is
         in fact running.
    return 0 (all lanes launched) - the trailing `wave["status"] = "running"`
    write above already covers the whole-wave status; nothing further to
    write here."""

def lane_status(lane: dict) -> str:
    """`lane["pid"]` is None -> lane["status"] verbatim ("planned", or
    "aborted"/"abort_failed" post-abort - a lane whose OWN cleanup step
    failed but whose process group WAS confirmed dead still reaches
    "abort_failed" this way; see abort()'s note on the one case that does
    NOT reach here - a lane whose kill itself failed keeps its PRE-abort
    pid and status, e.g. "running", precisely because it wasn't cleaned up
    at all, and falls through to the next branch below instead). Else
    loop_gates._pid_alive(lane["pid"]) -> "running". Else (pid dead): read
    `<lane["worktree"]>/dev/local/autopilot/state.json`
    (loop_gates._load_json); its `next_phase == ""` -> "drained"; anything
    else, including an unreadable/missing state.json -> "unfinished"."""

def status(repo: Path, wave: dict) -> str:
    """Renders one table row per lane: lane name, pid (or "-"), the lane's
    own state.prd, phase/next_phase, PRD counts per lifecycle dir (glob
    each `<worktree>/dev/local/prds/{backlog,wip,done,hold}/*.md`), the last
    row of `<worktree>/dev/local/autopilot/ledger/loop-metrics.jsonl`'s
    `phase_end`/`signal` fields (loop_gates._load_json line-by-line, last
    parseable line), and lane_status(lane). A lane whose worktree is gone
    (post-abort, no commits) prints '-' for the fields that require reading
    the worktree (state.prd/phase/PRD-counts/loop-metrics - there is nothing
    left on disk to read once the worktree is removed) with status
    "aborted". `lane["abort_error"]` (set only by a failed abort cleanup
    step), when present, prints as one extra column so an incomplete
    cleanup is visible rather than silently reported as clean. Returns the
    rendered string; the caller prints it."""

def _pgid_alive(pgid: int) -> bool:
    """`os.killpg(pgid, 0)` - signal 0 probes existence without sending
    anything, and it tests the PROCESS GROUP, not one pid, so it stays
    correct even after the original leader has exited and a child remains
    (dispatch 3's blocker: the earlier `os.getpgid(lane["pid"])` /
    `_child_pids` combination COULD NOT detect this case - `getpgid` on a
    dead leader raises `ProcessLookupError` before any group is even
    identified, and `_child_pids(leader_pid)` greps `pgrep -P <leader_pid>`,
    which stops finding anything the moment the leader itself is gone,
    since reparented children no longer have it as their parent). Mirrors
    `loop_gates._pid_alive`'s own convention: `ProcessLookupError` -> False,
    `PermissionError` -> True (a group that exists but this process can't
    signal is not "gone")."""

def abort(
    repo: Path,
    wave_path: Path,
    *,
    kill_fn=os.killpg,
    run_git=_default_run_git,
) -> int:
    """No `wave` parameter, matching `launch`'s corrected contract - `with
    locked(wave_path):` for the WHOLE body, starting with
    `wave = load(wave_path)` (the caller only used `load`/`WaveCorruptError`
    for its own friendly early messages; this reload is authoritative).

    `_structural_errors(repo, wave)` runs FIRST, before any signal or
    filesystem action (dispatch 3's blocker: an earlier draft ran NO
    validation before abort - it trusted a hand-edited `pid`, `worktree`,
    `branch`, or `base_sha` directly for destructive git calls and process
    signals, so editing two lanes' `worktree`/`branch` to the same real
    value could point a kill or a forced removal at the wrong target).
    Non-empty -> print every violation, "refusing to touch this wave.json -
    fix the listed fields by hand first", return 1, no signal sent, nothing
    moved, `wave.json` untouched. Only a structurally sound `wave` reaches
    Step 1.

    A single `failed = False` flag, set by any per-lane failure below, TAG
    replaces the earlier plain "mark every lane aborted regardless"
    contract - the actual reason this exists: `plan()`'s refusal check
    already treats anything other than `("done", "aborted")` as "still
    live, refuse to overwrite", so introducing a THIRD terminal wave/lane
    status - `"abort_failed"` - and writing it instead of `"aborted"`
    whenever `failed` ends up `True` is what makes `plan()` correctly
    refuse to replace a wave whose cleanup didn't actually finish (dispatch
    3's blocker: the earlier contract wrote plain `"aborted"` unconditionally,
    which `plan()` would then happily overwrite even though a process might
    still be alive or a worktree might still hold un-restored PRDs).

    Step 1 - kill every live lane. For every lane whose `lane["pid"]` is not
    None: pgid = lane["pid"] (ALWAYS the process-group id too -
    `start_new_session=True` at spawn time made the leader its own group
    leader, so `pid == pgid` from creation, permanently, independent of
    whether that leader later exits - no separate lookup is needed or
    correct here). If `_pgid_alive(pgid)`: kill_fn(pgid, SIGTERM); poll
    `_pgid_alive(pgid)` for up to 60s (1s interval); still alive ->
    kill_fn(pgid, SIGKILL); poll `_pgid_alive(pgid)` AGAIN for up to 10s. If
    the group is STILL alive after that (an immovable process, e.g.
    uninterruptible D-state I/O): `failed = True`;
    lane["abort_error"] = "process group <pgid> survived SIGKILL"; leave
    `lane["pid"]` AS IS (do not clear it - a live group's lane must not
    look inert) and move to the NEXT lane, skipping Step 2 for THIS lane
    entirely (killing failed, so touching its worktree/files is unsafe).

    Step 2 - for every lane that reached this step (any wave/lane status,
    so abort on a never-launched "planned" wave is a no-op that still needs
    to run - see the exit-criteria test), determine whether THIS wave
    actually created the worktree using TWO signals together, not one:
    `lane["worktree_created"]` (persisted by `launch` right after its
    `worktree add` succeeded - dispatch 3's blocker: `wave["id"]` has only
    minute resolution, so path+branch matching alone in the git registry
    cannot rule out an unrelated earlier wave whose id happened to collide;
    the flag is this launch's own first-hand record) AND a git-registry
    match: `porcelain = run_git(["worktree", "list", "--porcelain"]).stdout`
    from `repo`, parsed into blank-line-separated blocks, each block's
    `worktree <path>` line paired with its `branch refs/heads/<name>` line
    when present (a detached-HEAD block has no `branch` line - treat as no
    match); `known = lane["worktree_created"] and
    parsed.get(lane["worktree"]) == f"refs/heads/{lane['branch']}"`
    (dispatch 3's blocker: `--porcelain` reports full refs, `refs/heads/
    <name>`, never the bare branch name - comparing against the bare
    `lane["branch"]` string, as an earlier draft did, can never match):
      - not known (never created, a stale/colliding directory, or a
        worktree whose branch doesn't match): nothing to remove or keep;
        skip straight to the `lane["pid"] = None` line below, WITHOUT
        touching the directory on disk at all.
      - known (this wave's own worktree, confirmed by both signals):
        dirty = run_git(["status", "--porcelain"], cwd=lane["worktree"]).stdout
        != "" (tracked or untracked changes, not just commits - a loop
        killed mid-task can have real uncommitted work with zero commits
        past base). commits_past_base =
        run_git(["rev-list", "--count", f"{wave['base_sha']}..{lane['branch']}"]).
        stdout.strip().
        - commits_past_base == "0" AND NOT dirty: nothing to lose - move its
          done/*, hold/*, wip/*, backlog/* into the matching repo-root
          lifecycle dir (mkdir -p destinations first; shutil.move per file,
          skip if source dir is empty/absent), then
          run_git(["worktree", "remove", "--force", lane["worktree"]]) and
          run_git(["branch", "-D", lane["branch"]]).
        - otherwise (has commits, OR has uncommitted changes with zero
          commits): keep the worktree AND its `dev/local/prds/` files
          exactly where they are - do NOT move anything back to the main
          checkout (an in-progress PRD's only complete record is that
          worktree's own branch/working tree; the main checkout's
          `state.json` has no matching task record for it). Print the
          worktree's `git worktree list` line and, when dirty, one added
          note: "<n> uncommitted change(s), inspect before reusing this
          worktree".
      - EVERY git/filesystem call in this step (`worktree remove`,
        `branch -D`, a move that raises OSError) is wrapped in try/except:
        on failure, print a warning naming the lane and the failed step,
        set `failed = True` and lane["abort_error"] = "<step>: <error>", and
        continue to the NEXT lane rather than aborting the whole call.
      - lane["pid"] = None; lane["status"] = "aborted" if no `abort_error`
        was set for this lane in Step 2, else "abort_failed" (a lane whose
        Step 1 kill itself failed never reaches this line at all - it
        was left mid-loop with its PRE-abort `pid`/`status` untouched
        (typically still "running") plus its own `abort_error`, which
        `lane_status()`/`status()` surface directly; this line only ever
        runs for lanes that were successfully killed or never needed
        killing).

    shutil.rmtree(repo / "dev/local/autopilot/wave-slots") wrapped in
    try/except OSError: on failure, print a warning and set `failed = True`
    (dispatch 3's blocker: `ignore_errors=True` on the ORIGINAL contract
    silently swallowed this - a stuck `wave-slots/` directory is exactly
    the kind of incomplete cleanup this whole rewrite exists to surface).
    wave["status"] = "abort_failed" if (`failed` or any lane ended
    "abort_failed") else "aborted"; save(wave_path, wave); return 1 if
    `failed` else 0 - the exit CODE now reflects cleanup completeness, not
    just "abort ran" (dispatch 3's blocker: the original contract returned
    0 unconditionally). `plan()`'s existing refusal
    (`status not in ("done", "aborted")`) already refuses an
    `"abort_failed"` wave with NO further change needed there - introducing
    the third status value is what makes that refusal correct here.
    Idempotent ON THE CLEAN PATH: a second `abort` call over an `"aborted"`
    wave sees every lane already inert (pid None, no live process group,
    every worktree already gone or already excluded by the ownership
    check), so the loop body is a sequence of no-ops and it still returns
    0. Re-running `abort` over an `"abort_failed"` wave is exactly how the
    operator retries a partial cleanup - each lane's still-live process or
    still-present worktree is re-attempted from its actual current state,
    never blocked by the wave's OWN prior failed status (only `plan()`
    refuses to `plan` a *new* wave over an unresolved one; `abort` always
    re-attempts)."""
```

**`run_git`/`spawn_fn` failure contract** (dispatch 2's blocker: only
`worktree add`'s exit code had defined handling; every other git/filesystem
call in the design was silently assumed to succeed). Every `run_git(...)`
call above that does NOT pass an explicit `cwd=` runs with `cwd=repo`
(never the ambient process cwd, which need not even be inside `repo`) -
`launch`'s preconditions, its `rev-parse` calls, and `abort`'s
`worktree list` all read/mutate the MAIN checkout and must anchor there
regardless of where `autopilot wave ...` was invoked from; only the two
calls explicitly marked `cwd=lane["worktree"]` (a lane's own `git status`/
`rev-list`) run inside a worktree instead. `_default_run_git`
wraps `subprocess.run(args, cwd=cwd, capture_output=True, text=True,
check=True)` - `check=True` means a non-zero exit raises
`subprocess.CalledProcessError`, which propagates as a hard failure
EVERYWHERE except inside `abort`'s per-lane cleanup pass (documented above),
which is the one place a failure must not stop the whole operation.
`_default_run_git(args, cwd=None)` is exactly
`subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
check=True)` - every call site above passes only the git SUBCOMMAND
(`["status", "--porcelain"]`, `["worktree", "add", ...]`); `"git"` itself is
prepended by `_default_run_git`, never by a call site (dispatch 3's blocker:
the original contract left `"git"` out of `_default_run_git` entirely, which
would have tried to exec a program literally named `status` or `worktree`).
`launch`'s per-lane loop (step 1, `worktree add`) and its `rev-parse` calls
before the loop are NOT wrapped - a raised `CalledProcessError` there
propagates out of `launch` uncaught, which `wave_cli.run` catches at the top
level, prints `str(err)`, and returns 1 (the same "stops the loop over
lanes" behavior as before, now with the actual git stderr in the message
instead of an unspecified "non-zero result"). `spawn_fn`'s contract:
raises `OSError` on a failed exec, which `launch` similarly lets propagate
uncaught (the per-lane save from the PRIOR successful lane already
happened, so nothing already-spawned is lost).

### `cli/wave_cli.py`

```python
def add(subparsers) -> None:
    """p = subparsers.add_parser("wave"); verbs = p.add_subparsers(
    dest="verb", required=True). Exactly the `custody` shape
    (cli/__main__.py:1110-1122): every verb parser also takes `--state`
    (optional, resolved the same way every other subcommand resolves it).
    `plan` additionally takes `--max-lanes` (type=int, default=3)."""

def run(args, repo: Path, wave_path: Path) -> int:
    """Takes the ALREADY-RESOLVED `repo`/`wave_path` as explicit parameters -
    it never resolves a state path itself and never imports anything from
    `cli.__main__` (no circular import; see the corrected registration note
    below, which fixes two dispatch-1-missed defects: an off-by-one in the
    repo-root arithmetic, and a resolver-injection contract that had no
    actual mechanism behind it).
    dispatch: "plan" -> wave.plan(repo, wave_path, args.max_lanes);
    "launch"/"status"/"abort" -> wave.load(wave_path) raising WaveCorrupt ->
    print the parse error, "refusing to touch a corrupt wave.json - fix or
    remove it by hand", return 1 (never silently treated as "no plan");
    `None` (genuinely absent) -> print "autopilot: no wave.json at <path>;
    run `autopilot wave plan` first", return 1; else (a wave.json exists and
    parses) dispatch to "launch" -> wave_launch.launch(repo, wave_path) /
    "abort" -> wave_launch.abort(repo, wave_path) - NEITHER takes the `w`
    this preliminary load produced; both take only `wave_path` and reload
    it themselves under their own lock (see their corrected contracts) -
    this preliminary load exists ONLY to print the two friendly early
    messages above. "status" -> wave_launch.status(repo, w) (status alone
    is read-only, so the preliminary `w` IS what it renders; no reload, no
    lock) - prints and returns 0."""
```

### `__main__.py` registration (corrected)

`_SUBCOMMANDS` calls every registered `run_fn` as `run_fn(args)` exactly
(`main()`, `cli/__main__.py:1226-1229`) - there is no hook in that registry
for injecting an extra callable, so `wave_cli.run` cannot be registered
directly (dispatch 1's "inject a `resolve_state_path` callable at
registration" note named no real mechanism and doesn't work). The actual
fix mirrors `_run_custody` exactly: `custody.py`'s functions take an
already-resolved `state_path`/`autopilot_dir` (`_run_custody` resolves
`state_path = _resolve_state_path(args.state)` itself, in `__main__.py`,
before ever calling into `custody.py`). `wave` gets the same shape - one
new private function defined IN `__main__.py`, not in `wave_cli.py`:

```python
def _run_wave(args: argparse.Namespace) -> int:
    state_path = _resolve_state_path(args.state)
    # dev/local/autopilot/state.json -> repo is FOUR parents up, not three:
    # .parent (dev/local/autopilot) -> .parent (dev/local) -> .parent (dev)
    # -> .parent (repo). Three parents lands on `<repo>/dev` (dispatch 2's
    # blocker) - asserting the suffix here catches drift if this walk ever
    # changes without this line changing with it.
    assert state_path.parts[-4:-1] == ("dev", "local", "autopilot"), state_path
    repo = state_path.parents[3]
    wave_path = state_path.parent / "wave.json"
    return wave_cli.run(args, repo, wave_path)
```

`_add_wave = wave_cli.add`; `_SUBCOMMANDS["wave"] = (wave_cli.add, _run_wave)`
- `wave_cli.py` itself never imports `cli.__main__` or resolves a state
path; `_run_wave` is the one seam that does, exactly where every other
subcommand already does it.

### `wave.json` shape (canonical, written by `save`, read by `load`)

```json
{
  "id": "202609261200",
  "status": "planned",
  "repo": "/abs/path/to/repo",
  "base_branch": null,
  "base_sha": null,
  "review_slots": 3,
  "created_at": "2026-09-26T12:00:00Z",
  "lanes": [
    {"name": "l1", "order": 1, "branch": "wave/202609261200/l1",
     "worktree": "/abs/path/to/repo-l1", "prds": ["00214-...md"],
     "paths": ["skills/run-autopilot/cli/wave.py"], "status": "planned",
     "pid": null, "started_at": null, "worktree_created": false,
     "abort_error": null}
  ],
  "held_back": [{"prd": "00220-....md", "reason": "no named paths"}]
}
```

`status` is one of `"planned" | "running" | "aborted" | "abort_failed"` at
the WAVE level (the fourth value closes dispatch 3's blocker: a wave whose
`abort` cleanup didn't fully complete is never written as plain `"aborted"`,
so `plan()`'s existing refusal - anything other than `("done", "aborted")` -
correctly still refuses it). Distinct from `lane_status`'s per-lane derived
string, which is never persisted — only `lane["status"]`
(`"planned" | "running" | "aborted" | "abort_failed"`, the launch/abort-set
values) is stored; `"drained"`/`"unfinished"` are always *derived*, never
written, so `status()`'s rendering can never go stale relative to a lane's
actual live pid).

## Data flow

1. **Plan**: operator (or a script) runs `autopilot wave plan`. `wave.plan`
   reads every `backlog/*.md` PRD's raw text, calls `lane.named_paths` (via
   `wave.prd_paths`) per PRD, runs the pure `cut`, stamps lane identity
   fields, writes `wave.json`. No PRD file moves yet, no worktrees, no
   processes. The operator edits `wave.json` by hand (move a PRD between
   `lanes[i].prds`, merge two lanes, reorder) — a plain-text edit outside
   any code path this PRD adds.
2. **Launch**: `autopilot wave launch` reads the (possibly hand-edited)
   `wave.json`, re-derives path sets from the CURRENT PRD text (`validate`)
   so a hand-edit that broke disjointness is caught before anything is
   created, then for each lane: creates a worktree at the frozen `base_sha`,
   physically moves that lane's PRD files out of the main `backlog/` into the
   worktree's own `backlog/`, copies the capsule, and spawns one detached
   `autopilot loop` process rooted at the worktree. From that point each
   lane is an ordinary, unmodified autopilot loop reading and writing its
   OWN `dev/local/autopilot/state.json` — this PRD adds nothing to the
   per-PRD build/review/done cycle.
3. **Status**: `autopilot wave status` is read-only: it re-derives each
   lane's liveness from the OS (`_pid_alive`) and each lane's progress from
   its own `state.json` and `loop-metrics.jsonl` — `wave.json` itself is
   never the source of live progress, only of identity (which worktree, which
   branch, which PRDs).
4. **Abort**: `autopilot wave abort` reverses step 2's process/worktree
   effects (kill, move PRDs back, remove or keep the worktree by commit
   history) and marks the wave closed, which step 1's refusal check reads
   before it will plan a new wave.

## Reuse inventory

- `cli/lane.py:170 named_paths(text)` — reused unmodified as the path-set
  source; `wave.prd_paths` is a thin wrapper (`named_paths(text)` minus
  `WAVE_APPEND_ONLY`). Greps tried: `named_paths`, `path.?set`, `owned.?path`
  — only `lane.py` defines path-set extraction from PRD text.
- `cli/loop_gates.py:26 _pid_alive`, `:105 live_wrapper_pid`,
  `DEFAULT_LOOPS_DIR` — reused as-is for `launch`'s "no live loop on the main
  root" precondition and for `lane_status`'s liveness check. Greps tried:
  `_pid_alive`, `pid.*alive`, `is.?alive` — one definition, in
  `loop_gates.py`.
- `cli/routing.py:115 _load_json` — same read-tolerant-of-corruption contract
  `wave.load` copies (return `None` on `OSError`/`ValueError` rather than
  raising); `wave_launch.status`/`lane_status` call the `loop_gates` copy of
  the same helper (it re-exports/duplicates `routing._load_json` already —
  no third copy is added).
- `cli/loop_gates.py:221 _write_registry_entry`'s tmp-file-then-`replace`
  pattern — reused as the shape of `wave.save` (atomic write, no partial
  `wave.json` ever observable).
- `cli/state.py`'s `transaction()` `fcntl.flock` pattern (`fcntl.flock(lock
  .fileno(), fcntl.LOCK_EX)` on a sibling `<path>.lock`, held for the whole
  read-modify-write body) — reused unmodified as `wave.locked()`'s
  implementation, closing dispatch 2's mutual-exclusion blocker with the
  exact mechanism this repo already trusts for `state.json`, rather than a
  new locking scheme. Greps tried: `flock`, `fcntl`, `advisory.*lock` — one
  definition, in `cli/state.py`.
- `cli/loop_gates.py:26 _pid_alive`'s exact exception-handling CONVENTION
  (`ProcessLookupError` -> False, any other `OSError`/`PermissionError` ->
  True) — reused for the new `_pgid_alive`, applied to `os.killpg(pgid, 0)`
  instead of `os.kill(pid, 0)`. Not the function itself (a process group and
  a single pid are checked with the same syscall shape but different
  targets), but the same interpretation of what each failure mode means -
  keeping one convention for "is this thing alive" across the file.
- `cli/custody.py` + `cli/__main__.py:1110-1146 _add_custody`/`_run_custody`
  — the verb-subparser-under-one-subcommand shape (`custody list|resolve`)
  is copied exactly for `wave plan|launch|status|abort`, including the
  per-verb optional `--state`. Greps tried: `add_subparsers`,
  `dest="verb"` — `custody` is the only existing multi-verb subcommand.
  `dev/local/autopilot/deferred/` style "list JSON entries" precedent was
  also checked (`custody.pending`) and is the same shape `status` follows
  for rendering, though `status` renders a table, not JSON lines (a human
  operator reads it directly, unlike `custody list`'s machine-consumed
  JSON-per-line).
- `cli/runner.py:44 _run_agoge_process`'s `subprocess.Popen(stdin=DEVNULL,
  stdout=<log file>, stderr=STDOUT)` shape — reused for `_default_spawn`'s
  Popen call, adding only `start_new_session=True` (agoge's spawn blocks on
  `.wait()`; `launch`'s must not, since the lane loop outlives `launch`
  itself — the one real difference, called out in Alternatives). Greps
  tried: `Popen`, `start_new_session`, `DEVNULL` — `loop_act.py` and
  `runner.py` are the only two Popen call sites in `cli/`; neither uses
  `start_new_session` today (both are supervised, not detached), so this
  PRD introduces the repo's first detached-spawn call.
- `cli/test_notify_out.py:25` stub-script-recording-`sys.argv` pattern —
  reused for `test_wave_launch.py`'s "stub `python3` target recording its
  argv and environment" (the PRD's own Acceptance wording); the stub writes
  `repr(sys.argv[1:])` (and, new here, `repr(dict(os.environ))` filtered to
  the `_AUTOPILOT_*` keys) to a file `spawn_fn`'s test double points at.
  Greps tried: `stub.*python`, `record.*argv`, `sys\.argv` in `cli/test_*.py`
  — one existing precedent, reused rather than re-invented.
- **Nothing found** for: a Python worktree helper (`git worktree add/remove`
  wrapped anywhere in this repo) — greps tried `worktree`, `git.*worktree`,
  `add.*-b.*branch` in `cli/*.py` and `scripts/*.py`, all empty. `launch` and
  `abort` are the first callers; both take `run_git` as an injected callable
  specifically so tests never shell out to real git in a way this repo
  doesn't already do elsewhere (`test_wave_launch.py`'s real-`git init`
  `tmp_path` fixtures are the one place real git runs, matching the PRD's own
  Acceptance wording).

## Alternatives considered

1. **`Lane` as a plain `dict` throughout, no dataclass.** Smaller diff — `cut`
   would return `list[dict]` directly and every field access is a dict
   lookup, matching how `state.json`/`wave.json` are otherwise handled in
   this codebase (plain dicts, no dataclass wrapper). Rejected: `cut` is
   documented as pure and side-effect-free, and every existing pure-value
   type in `cli/` (`lane.CardPlan`, `lane.Verdict`, `policy.Verdict`,
   `runner.SpawnResult`) is a frozen dataclass, not a dict — matching that
   convention costs one `as_dict()` method and buys field-typo safety in the
   packing/ordering logic, which is the fiddliest part of this PRD. `wave.json`
   itself, once loaded, stays a plain dict (round-tripped through
   `dataclasses.asdict`), so `wave_launch.py` — which only ever reads an
   already-loaded `wave.json` — never imports the dataclass at all.
2. **Blocking `launch` (wait for each lane's loop to finish its first
   session) instead of detached spawn.** Smallest-diff version of "start N
   loops" — reuse `runner._run_agoge_process`'s `Popen(...).wait()` shape
   unchanged, one lane at a time. Rejected outright: it would serialize the
   lanes (defeating the entire point of running them concurrently) and block
   the calling session for the combined wall-clock of every lane's first
   session. This is the one place this design must diverge from every
   existing Popen call in the repo (see Reuse inventory) — `start_new_session
   =True` plus no `.wait()` is not optional, it's the feature.
3. **A single JSON list (no `wave.json` object wrapper) for lanes**, keyed by
   a separate `held_back` file. Rejected: `status`/`abort` need the wave-level
   fields (`base_sha`, `review_slots`, `status`) alongside the lanes to do
   their job in one read; splitting into two files adds a second load/save
   pair and a second place `plan`'s refusal check has to look, for a
   negligible file-size saving. The PRD's own `wave.json` shape (given in
   its Feature description) already settles this — this alternative is
   listed to record why it wasn't reopened.

## Risks & edge cases

- **Partial launch failure** (a `worktree add` fails on lane 2 of 3): the
  contract above stops the loop and returns 1, leaving lane 1's loop already
  running and lane 1's PRDs already moved. This is a deliberate choice, not
  an oversight: killing an already-started lane on a later lane's failure
  would waste the spend already committed to lane 1's session, and `status`/
  `abort` both work correctly against a `wave.json` with a mix of `"running"`
  and `"planned"` lanes (abort's per-lane loop already handles every lane
  status). The operator's next move is `wave status` to see which lane
  failed, fix the cause (usually a stale worktree path or a dirty base
  branch), and re-run `wave launch` — which will refuse (`status !=
  "planned"`) until the operator either hand-edits `wave.json` back to
  `"planned"` for the un-launched lanes or runs `wave abort` first. This
  gap (there is no "resume a partial launch" verb) is accepted for v1 and
  is exactly the kind of manual step 00216's `wave run` one-shot command
  (a later PRD) is positioned to close.
- **Two future PRDs share this PRD's contracts closely.** 00215 (assemble a
  drained wave) will read `wave.json`'s `lanes[].branch`/`worktree` fields to
  merge each lane's commits onto one integration branch — this design keeps
  those two fields stable and worktree-addressable (never renamed once
  written) for exactly that reason. 00217 (review-slot semaphore) will read
  `wave["review_slots"]` and consume the `_AUTOPILOT_REVIEW_SLOTS_DIR`/
  `_AUTOPILOT_REVIEW_SLOTS` env vars this PRD already sets on every launched
  lane but that nothing reads yet (dead env vars until 00217 lands, called
  out explicitly in the PRD text). A third likely follow-on: `wave plan`
  re-run after a partial `held_back` list changes (a PRD gains a `Location`
  line) — nothing in this design prevents re-running `plan` once the prior
  wave is `"done"`/`"aborted"`, so no extra hook is needed for it.
- **`abort` racing a lane's own in-flight session.** SIGTERM/SIGKILL target
  the process GROUP by pgid directly (`os.killpg`, verified alive via
  `_pgid_alive` — not the leader pid alone, and not assumed to have
  succeeded without a confirming poll — see `abort`'s corrected contract),
  so a lane's `claude -p` child dies alongside its `autopilot loop` parent;
  a session mid-write to its own `state.json` could leave that file
  transiently inconsistent. This is accepted: the lane's worktree is either
  kept (has commits OR uncommitted changes — a human inspects it, and its
  own `dev/local/prds/`/`state.json` stay inside it rather than being split
  across two locations) or discarded entirely (clean at both the commit and
  working-tree level — nothing to lose), so a torn `state.json` in a kept
  worktree is a known, visible cost of a hard abort, not a silent one.
- **A partial `abort` (a lane's process group survives SIGKILL, or a
  filesystem/git step fails mid-cleanup) leaves the wave `"abort_failed"`,
  not `"aborted"`.** This is intentional, not a dead end: `plan()`'s
  existing refusal (anything other than `("done", "aborted")`) already
  refuses to start a NEW wave over it, and re-running `wave abort` is the
  documented retry — each lane's cleanup re-attempts from wherever it
  actually is (a still-live group gets signalled again; an already-cleaned
  lane is a no-op), so there is no separate "resume a failed abort" verb to
  build. The one thing this state cannot self-heal is an immovable process
  (D-state I/O, a wedged container) — that needs a human at the OS level,
  which is outside any CLI tool's reach.
- **`WAVE_FORCE_SHARED` is this-repo-specific** (three paths that only exist
  in `claude-autopilot`). The design doc for 00214 states this plainly (per
  the PRD's own note) rather than trying to generalize it — a no-op constant
  in any other repo is the correct behavior, not a bug to fix.
- **A lane's worktree basename collision** (`<repo>-l1` already exists from a
  prior aborted-but-not-cleaned wave, or from something unrelated entirely).
  `launch`'s `git worktree add` will fail on this and surface as the
  partial-launch case above. `abort`'s corrected contract now protects
  against the OTHER direction of this collision too: because it verifies
  each lane's worktree via `git worktree list --porcelain` (path mapped to
  the expected branch) rather than trusting `Path.is_dir()`, a stray
  directory that merely happens to share the name is never mistaken for
  this wave's own worktree and is left untouched, not force-removed.

## Test strategy outline

`test_wave.py` (pure, no disk beyond `tmp_path` for `load`/`save`/`plan`):
covers `shares` (literal overlap, directory-prefix either direction,
append-only exclusion, force-shared pulling two PRDs naming *different*
force-shared files into one lane), `cut` (component packing into
`max_lanes`, held-back PRDs with no named paths, lane-order priority for
core-owning lanes, `max_lanes <= 0` refused), `plan`'s refusal on a
non-closed existing `wave.json` AND its refusal (not overwrite) on a
CORRUPT `wave.json` (`load` raising `WaveCorruptError`), and a `wave.json`
round-trip (`save` then `load` reproduces the same dict). Plus (new,
closing dispatch 2's and dispatch 3's findings): `locked()` actually
excludes a second concurrent `with locked(...)` block in the same test
process (two threads, one blocks until the first releases);
`_structural_errors()`'s checks (each violation kind above gets one test,
including the two duplicate-field cases, `order` non-positive/None, and a
non-list/empty `prds`), called both through `validate()` and directly (as
`abort()` calls it) so one fixture covers both callers; `validate()`'s
remaining path/backlog-membership checks, now against its corrected
`(repo, wave, prds)` signature, including the pathless-assigned-PRD case.
Exactly the PRD's own Acceptance list (nine tests) plus the round-trip test
it already names, plus the above.

`test_wave_launch.py` (real `git init` repos under `tmp_path`, a stub
`python3` target recording argv/env — see Reuse inventory): covers one
worktree per lane at the frozen `base_sha`, PRDs physically leaving the
main `backlog/`, the capsule being copied when present, `launch` refusing
overlapping lanes (a hand-edited `wave.json` that no longer matches current
PRD text) and a dirty main tree, the spawned driver's own `_AUTOPILOT_LOOP`
tag equalling its own pid (via the stub), the slot-dir/count env vars
reaching the child, and lane roots being distinct registry roots (`<repo>`
vs `<repo>-l1` never alias in `live_wrapper_pid`). Then `status` deriving
`"drained"` from a dead pid plus an empty `next_phase`, `abort` returning
PRDs and removing clean worktrees, `abort` keeping a worktree with commits,
and `abort` on a never-launched `"planned"` wave being a byte-for-byte
no-op on the backlog. Exactly the PRD's own Acceptance list for both tasks,
plus (new, closing dispatch 2's and dispatch 3's findings): `abort` KEEPS a
worktree that has zero commits but a dirty working tree (no data loss on an
in-flight kill); `abort` never touches a same-named directory that
`git worktree list` doesn't map to BOTH `lane["worktree_created"]` AND the
expected `refs/heads/<branch>` (a worktree/branch pair from an unrelated
wave, and a same-path/same-branch pair with `worktree_created` left False,
each get their own test); `abort` continues past one lane's raised
git/OSError, records `abort_error` on that lane, ends the wave
`"abort_failed"` rather than `"aborted"`, and still finishes every other
lane; `plan` refuses to overwrite an `"abort_failed"` wave the same as a
`"planned"`/`"running"` one; a second `abort` call over an `"abort_failed"`
wave retries only the lanes that still need it and clears to `"aborted"`
once every lane is clean; `abort`'s kill step reaps a lane whose leader
already exited but left a child alive in the group (a fake child process
the stub spawns and outlives the "loop" stub, verified via the SAME
`os.killpg(pgid, 0)` probe `_pgid_alive` uses, not by inspecting the
leader pid); `launch` and `abort` each reload `wave.json` fresh under their
own lock rather than trusting a caller-supplied dict (a test that mutates
the on-disk file between a stale in-memory copy and the call proves the
stale copy is never what gets acted on).

`test_docs_name_the_wave_files` (new, Phase 2): pins `wave.json` and
`wave-slots/` into core `SKILL.md`'s Retention "Disposable" list and
`references/waves.md` into its Reference Files list — a prose-pinning test
in the same family as `test_loop_prose.py`/`test_custody_prose*.py`
(explicitly named in the PRD's Phase 2 Acceptance as suites that must stay
green, i.e. this new test must not duplicate or conflict with their
existing section-anchor assertions).

## Review log

- non-blocker: `lane_status()` checks only `_pid_alive`, not the
  recycled-pid `_pid_tagged` guard `loop_gates.live_wrapper_pid` already
  combines with it for exactly this reason — over a multi-hour wave a
  recycled pid could misreport a dead lane as running. Not fixed now.
- non-blocker: "lane" collides with two existing unrelated uses of the same
  word in this codebase (`cli/lane.py`'s effort-lane classifier;
  `hooks/guard_stop_on_live_lanes.py`'s CLI-reviewer-subprocess lanes from
  PRD 00213). Worth a disambiguating name in docs/error text; not fixed now.
- non-blocker: Reuse inventory misattributed `_run_agoge_process`'s Popen
  shape to `cli/runner.py:44` — it is `cli/loop_act.py:44`. The underlying
  reuse claim is correct, only the citation is wrong. Not fixed now.
- question: `validate()`'s violation message ("lane A and lane B share
  <path>") assumes one common path, but the force-shared rule can fire when
  two lanes each name a *different* force-shared file with nothing literally
  in common — the message shape for that case is unspecified.
- question: `CLI_MAIN_PATH` is referenced in `launch()`'s spawn argv but
  never defined; since the spawned process's cwd is the lane's worktree
  (not this repo), an implementor resolving it relative to cwd rather than
  `__file__` would break the spawn silently.
- question: `status()` says a lane whose worktree is gone "prints its
  last-known fields", but nothing in the `wave.json` Lane schema caches
  those fields (state.prd/phase/PRD-counts/loop-metrics) before the
  worktree is deleted — unclear what "last-known" renders as in practice.
- question: the documented wave-level `status` enum (`planned | running |
  aborted`) omits `"done"`, which `plan()`'s own refusal check tests for
  (`not in ("done", "aborted")`) — worth noting `"done"` is a
  forward-compatible value reserved for 00216's future `land` verb, never
  written by this PRD's own modules.
- dispatch 1 (claude): cardinal-sin 0, blocker 1, non-blocker 3, question 4
- non-blocker (dispatch 2): the documented partial-launch retry ("hand-edit
  `wave.json` back to `planned`, re-run `wave launch`") can't actually
  resume just the failed lane — `launch` iterates every lane including
  already-running ones and would re-attempt (and fail on) an existing
  worktree before reaching the un-launched one. Not fixed now; the Risks
  section already accepts "no resume-a-partial-launch verb" for v1 and
  00216's `wave run` is positioned to close the underlying gap — this
  sharpens why the manual retry path specifically doesn't work either,
  which the operator should know before trying it.
- non-blocker (dispatch 2): `lanes[].paths` (each lane's owned-paths list,
  frozen at `plan` time) goes stale after a supported hand-edit — moving a
  PRD between lanes or editing its `Location:` lines leaves the stored
  `paths` inconsistent with the current derivation, even though `launch`'s
  `validate()` re-derives and checks disjointness correctly against the
  CURRENT text. Not fixed now: `wave.json`'s `paths` field is informational
  (the operator table / `status` display), never re-consulted by `validate`
  or `launch` for a correctness decision, so a stale value there is a
  display nit, not a safety gap.
- question (dispatch 2): the main-root loop-exclusion check in `launch`
  (`live_wrapper_pid(repo, ...) is not None`) is a point-in-time check with
  no reservation — a main-root loop could start immediately after it passes
  and race to claim a PRD `launch` is about to move into a lane's worktree.
  Whether a main-root loop is meant to be forbidden for a wave's whole
  lifetime (and if so, by what mechanism) is left to the operator's own
  discipline for v1 — worth an explicit statement in `references/waves.md`
  rather than a code change, since enforcing it would need the main loop
  itself to check for a live wave, which is out of this PRD's scope.
- dispatch 2 (codex): cardinal-sin 0, blocker 9, non-blocker 2, question 1
- dispatch 3 (codex): cardinal-sin 0, blocker 7, non-blocker 0, question 0
