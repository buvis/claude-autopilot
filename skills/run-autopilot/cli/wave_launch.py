"""cli/wave_launch.py - validate a planned wave and launch its lanes (PRD 00214).

`launch` is the wave's one destructive step: it cuts a worktree per lane, moves
each lane's PRDs into it and spawns a loop there. `wave.json` is a supported
hand-edit surface between `wave plan` and `wave launch`, so `validate` re-derives
every lane's paths from the backlog as it stands NOW, before anything is created.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from cli.loop_gates import DEFAULT_LOOPS_DIR, _load_json, _pid_alive, live_wrapper_pid
from cli.wave import (
    WAVE_FORCE_SHARED,
    _structural_errors,
    load,
    locked,
    prd_paths,
    save,
    shares,
)

CLI_MAIN_PATH = Path(__file__).resolve().parent / "__main__.py"
# `$$` is the lane shell's own pid, and `exec` keeps it: the loop registers as
# its own incumbent, keyed on the lane worktree root.
_SPAWN_CMD = 'export _AUTOPILOT_LOOP=$$; exec python3 "$0" loop'


def _default_run_git(
    args: list[str],
    cwd: Path | None = None,
) -> subprocess.CompletedProcess:
    """`git <args>`: "git" is prepended here, never by a call site."""
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )


# ── validate ─────────────────────────────────────────────────────────────────


def _rederive(lane: dict, prds: dict[str, str]) -> tuple[frozenset[str], list[str]]:
    """A lane's path set as the backlog names it now, plus its drift violations."""
    paths: set[str] = set()
    violations: list[str] = []
    for prd in lane["prds"]:
        if prd not in prds:
            violations.append(f"lane {lane['name']}: {prd} is no longer in backlog/")
            continue
        named = prd_paths(prds[prd])
        if not named:
            violations.append(
                f"lane {lane['name']}: {prd} now names no paths - move it to"
                " held_back by hand before launching",
            )
            continue
        paths |= named
    return frozenset(paths), violations


def _share_violation(
    a: dict,
    b: dict,
    pa: frozenset[str],
    pb: frozenset[str],
) -> str:
    """The message for a pair `shares()` rejected: a literal or directory-prefix
    overlap names the path, a force-shared hit names one file per lane."""
    common = sorted(pa & pb) or sorted(
        x for x in pa for y in pb if x.startswith(y + "/") or y.startswith(x + "/")
    )
    if common:
        return f"lane {a['name']} and lane {b['name']} share {common[0]}"
    forced = frozenset(WAVE_FORCE_SHARED)
    return (
        f"lane {a['name']} and lane {b['name']} both touch force-shared files"
        f" ({sorted(pa & forced)[0]} in {a['name']},"
        f" {sorted(pb & forced)[0]} in {b['name']})"
    )


def validate(repo: Path, wave: dict, prds: dict[str, str]) -> list[str]:
    """One violation string per problem in `wave` against the backlog `prds`; []
    when it is safe to launch. Shape first: a malformed wave is reported before
    any lane is indexed into."""
    shape = _structural_errors(repo, wave)
    if shape:
        return shape
    violations: list[str] = []
    derived: list[tuple[dict, frozenset[str]]] = []
    for lane in wave["lanes"]:
        paths, drift = _rederive(lane, prds)
        violations += drift
        derived.append((lane, paths))
    for index, (a, pa) in enumerate(derived):
        for b, pb in derived[index + 1 :]:
            if shares(pa, pb):
                violations.append(_share_violation(a, b, pa, pb))
    return violations


# ── launch ───────────────────────────────────────────────────────────────────


def _refuse(violations: list[str]) -> int:
    for violation in violations:
        print(f"autopilot: {violation}", file=sys.stderr)
    print("autopilot: refusing to launch", file=sys.stderr)
    return 1


def _backlog_texts(repo: Path) -> dict[str, str]:
    """The main checkout's backlog as it stands now: basename -> text."""
    backlog = repo / "dev/local/prds/backlog"
    return {
        path.name: path.read_text(encoding="utf-8")
        for path in sorted(backlog.glob("*.md"))
    }


def _refusal(repo: Path, wave: dict, run_git: Callable[..., object]) -> int | None:
    """An exit code when this wave must not launch, None when it may. Every
    check runs before anything is created."""
    shape = _structural_errors(repo, wave)
    if shape:
        return _refuse(shape)
    if run_git(["status", "--porcelain"], cwd=repo).stdout.strip():
        print(
            "autopilot: dirty tree; commit or stash the main checkout before"
            " launching a wave",
            file=sys.stderr,
        )
        return 1
    incumbent = live_wrapper_pid(repo, DEFAULT_LOOPS_DIR)
    if incumbent is not None:
        print(
            f"autopilot: a loop is already running on the main root (pid {incumbent})",
            file=sys.stderr,
        )
        return 1
    if wave["status"] != "planned":
        print(
            f"autopilot: wave is not in planned state (it is {wave['status']})",
            file=sys.stderr,
        )
        return 1
    violations = validate(repo, wave, _backlog_texts(repo))
    return _refuse(violations) if violations else None


def _seed_lane_worktree(repo: Path, worktree: Path, prds: list[str]) -> None:
    """The lane's own dev/local: PRD folders, its PRDs moved in, meta copied."""
    for folder in ("backlog", "wip", "done", "hold"):
        (worktree / "dev/local/prds" / folder).mkdir(parents=True, exist_ok=True)
    (worktree / "dev/local/autopilot").mkdir(parents=True, exist_ok=True)
    for prd in prds:
        shutil.move(
            str(repo / "dev/local/prds/backlog" / prd),
            str(worktree / "dev/local/prds/backlog" / prd),
        )
    meta = repo / "dev/local/meta"
    if meta.exists():
        shutil.copytree(meta, worktree / "dev/local/meta", dirs_exist_ok=True)


def _spawn_lane(
    repo: Path,
    worktree: Path,
    review_slots: int,
    spawn_fn: Callable[..., object],
) -> object:
    env = {k: v for k, v in os.environ.items() if k != "_AUTOPILOT_LOOP"}
    env["_AUTOPILOT_REVIEW_SLOTS_DIR"] = str(repo / "dev/local/autopilot/wave-slots")
    env["_AUTOPILOT_REVIEW_SLOTS"] = str(review_slots)
    env["_AUTOPILOT_TRACON_CHILD"] = "1"
    with open(worktree / "dev/local/autopilot/wrapper.log", "a") as log:
        return spawn_fn(
            ["bash", "-c", _SPAWN_CMD, str(CLI_MAIN_PATH)],
            cwd=str(worktree),
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )


def _launch_lane(
    repo: Path,
    wave_path: Path,
    wave: dict,
    lane: dict,
    spawn_fn: Callable[..., object],
    run_git: Callable[..., object],
) -> None:
    """Cut one lane's worktree at the base sha, seed it, spawn its loop. Saved
    twice: once the worktree exists, once the lane is running, so a later lane's
    failure still leaves an accurate record of this one."""
    run_git(
        ["worktree", "add", lane["worktree"], "-b", lane["branch"], wave["base_sha"]],
        cwd=repo,
    )
    lane["worktree_created"] = True
    save(wave_path, wave)
    worktree = Path(lane["worktree"])
    _seed_lane_worktree(repo, worktree, lane["prds"])
    handle = _spawn_lane(repo, worktree, wave["review_slots"], spawn_fn)
    lane["pid"] = handle.pid
    lane["started_at"] = datetime.now(timezone.utc).isoformat()
    lane["status"] = "running"
    save(wave_path, wave)


def launch(
    repo: Path,
    wave_path: Path,
    *,
    spawn_fn: Callable[..., object] = subprocess.Popen,
    run_git: Callable[..., object] = _default_run_git,
) -> int:
    """Launch every lane of the planned wave; 0 when all of them started. The
    lock is held for the whole body, and the wave is reloaded under it."""
    with locked(wave_path):
        wave = load(wave_path)
        refusal = _refusal(repo, wave, run_git)
        if refusal is not None:
            return refusal
        wave["base_sha"] = run_git(["rev-parse", "HEAD"], cwd=repo).stdout.strip()
        wave["base_branch"] = run_git(
            ["rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo,
        ).stdout.strip()
        wave["status"] = "running"
        save(wave_path, wave)
        for lane in sorted(wave["lanes"], key=lambda each: each["order"]):
            _launch_lane(repo, wave_path, wave, lane, spawn_fn, run_git)
        return 0


# ── lane_status ──────────────────────────────────────────────────────────────


def lane_status(lane: dict) -> str:
    """A lane's live status: liveness beats the stored one, and a dead lane is
    told apart by its own state.json."""
    if lane["pid"] is None:
        return lane["status"]
    if _pid_alive(lane["pid"]):
        return "running"
    state = _load_json(Path(lane["worktree"]) / "dev/local/autopilot/state.json")
    if isinstance(state, dict) and state.get("next_phase") == "":
        return "drained"
    return "unfinished"


# ── status ───────────────────────────────────────────────────────────────────

_STATUS_HEADERS = (
    "lane",
    "pid",
    "prd",
    "phase",
    "next_phase",
    "backlog",
    "wip",
    "done",
    "hold",
    "phase_end",
    "signal",
    "status",
    "abort_error",
)
_LIFECYCLE = ("backlog", "wip", "done", "hold")


def _dashed(value: object) -> str:
    """A cell that always prints something: an empty one collapses when a reader
    splits the row on whitespace, and then no column can be told from the next."""
    text = "" if value is None else str(value)
    return text or "-"


def _last_metrics(worktree: Path) -> dict:
    """The last PARSEABLE line of the lane's metrics ledger. A half-written final
    line is skipped, never fatal: the loop appends to this file while we read it."""
    ledger = worktree / "dev/local/autopilot/ledger/loop-metrics.jsonl"
    if not ledger.exists():
        return {}
    last: dict = {}
    for line in ledger.read_text(encoding="utf-8").splitlines():
        try:
            parsed = json.loads(line)
        except ValueError:
            continue
        if isinstance(parsed, dict):
            last = parsed
    return last


def _lane_row(lane: dict) -> list[str]:
    """One lane's cells in `_STATUS_HEADERS` order. The pid, the status and the
    abort_error come from wave.json, so they survive a worktree that is gone -
    dashing the pid there would leave an operator nothing to kill."""
    worktree = Path(lane["worktree"])
    on_disk = worktree.exists()
    state = _load_json(worktree / "dev/local/autopilot/state.json") if on_disk else None
    state = state if isinstance(state, dict) else {}
    metrics = _last_metrics(worktree) if on_disk else {}
    counts = (
        [
            str(len(list((worktree / "dev/local/prds" / folder).glob("*.md"))))
            for folder in _LIFECYCLE
        ]
        if on_disk
        else ["-"] * len(_LIFECYCLE)
    )
    return [
        lane["name"],
        _dashed(lane["pid"]),
        _dashed(state.get("prd")),
        _dashed(state.get("phase")),
        _dashed(state.get("next_phase")),
        *counts,
        _dashed(metrics.get("phase_end")),
        _dashed(metrics.get("signal")),
        lane_status(lane) if on_disk else lane["status"],
        _dashed(lane["abort_error"]),
    ]


def status(repo: Path, wave: dict) -> str:
    """The wave as a table: a header row, then one row per lane. Read-only - no
    lock is taken, and neither the dict nor wave.json is touched."""
    rows = [list(_STATUS_HEADERS), *(_lane_row(lane) for lane in wave["lanes"])]
    widths = [max(len(row[index]) for row in rows) for index in range(len(rows[0]))]
    return "\n".join(
        "  ".join(
            cell.ljust(width) for cell, width in zip(row, widths, strict=True)
        ).rstrip()
        for row in rows
    )


# ── abort ────────────────────────────────────────────────────────────────────


def _pgid_alive(pgid: int) -> bool:
    """`_pid_alive`'s convention for a process GROUP: only `ProcessLookupError`
    means gone, any other `OSError` (EPERM) means it is there but unsignalable. A
    group outlives its reaped leader, which a single-pid probe cannot see."""
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True
    return True


def _wait_for_exit(pgid: int, timeout: float) -> bool:
    """True once the group is gone, polled once a second. POLLED, not slept out:
    the wave lock is held here, so a dead group must not cost the full window."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _pgid_alive(pgid):
            return True
        time.sleep(1)
    return not _pgid_alive(pgid)


def _kill_lane(lane: dict, kill_fn: Callable[[int, int], object]) -> str | None:
    """SIGTERM the lane's group, then SIGKILL it if it outlives the 60s grace.
    None once the group is gone; the failure to record when it is still there.
    `lane["pid"]` IS the pgid: the loop was spawned as its own session leader."""
    pgid = lane["pid"]
    if pgid is None or not _pgid_alive(pgid):
        return None
    kill_fn(pgid, signal.SIGTERM)
    if _wait_for_exit(pgid, 60):
        return None
    kill_fn(pgid, signal.SIGKILL)
    if _wait_for_exit(pgid, 10):
        return None
    return f"process group {pgid} survived SIGKILL"


def _worktree_branches(repo: Path, run_git: Callable[..., object]) -> dict[str, str]:
    """git's own worktree registry: path -> full branch ref. A detached block has
    no `branch` line, so it lands nowhere and can never match a lane."""
    listing = run_git(["worktree", "list", "--porcelain"], cwd=repo).stdout
    registry: dict[str, str] = {}
    for block in listing.split("\n\n"):
        fields = dict(line.split(" ", 1) for line in block.splitlines() if " " in line)
        if "worktree" in fields and "branch" in fields:
            registry[fields["worktree"]] = fields["branch"]
    return registry


def _keep_reason(
    repo: Path,
    wave: dict,
    lane: dict,
    registry: dict[str, str],
    run_git: Callable[..., object],
) -> str | None:
    """Why this lane's worktree must stay, None when it is this wave's to remove.
    Ownership takes TWO signals - the lane's own flag and git's registry - and a
    worktree holding commits or uncommitted work is never removed."""
    if not lane["worktree_created"]:
        return "this wave never recorded creating it"
    if registry.get(lane["worktree"]) != f"refs/heads/{lane['branch']}":
        return f"git no longer has it checked out on {lane['branch']}"
    spec = f"{wave['base_sha']}..{lane['branch']}"
    commits = run_git(["rev-list", "--count", spec], cwd=repo).stdout.strip()
    if commits != "0":
        return f"{commits} commit(s) on {lane['branch']}, not merged anywhere"
    dirty = run_git(["status", "--porcelain"], cwd=Path(lane["worktree"])).stdout
    if dirty.strip():
        return (
            f"{len(dirty.splitlines())} uncommitted change(s), inspect before"
            " reusing this worktree"
        )
    return None


def _return_prds(repo: Path, worktree: Path) -> None:
    """Every PRD the lane still holds, back into the main checkout's own lifecycle
    folder. A wave is aborted mid-PRD, so wip/ is walked like the rest."""
    for folder in _LIFECYCLE:
        target = repo / "dev/local/prds" / folder
        for prd in sorted((worktree / "dev/local/prds" / folder).glob("*.md")):
            target.mkdir(parents=True, exist_ok=True)
            shutil.move(str(prd), str(target / prd.name))


def _clean_up_lane(
    repo: Path,
    wave: dict,
    lane: dict,
    registry: dict[str, str],
    run_git: Callable[..., object],
) -> None:
    """Return the lane's PRDs and drop the worktree and branch this wave cut. A
    worktree that is not ours, or that holds work, keeps its PRDs too: they are
    the only record of what that lane was doing."""
    reason = _keep_reason(repo, wave, lane, registry, run_git)
    if reason is not None:
        worktree = Path(lane["worktree"])
        if worktree.exists():
            print(f"autopilot: keeping {worktree}: {reason}")
        return
    _return_prds(repo, Path(lane["worktree"]))
    run_git(["worktree", "remove", "--force", lane["worktree"]], cwd=repo)
    run_git(["branch", "-D", lane["branch"]], cwd=repo)


def _abort_lane(
    repo: Path,
    wave: dict,
    lane: dict,
    registry: dict[str, str],
    run_git: Callable[..., object],
    kill_fn: Callable[[int, int], object],
) -> bool:
    """One lane's whole abort; True when it did not finish. A lane whose group
    survived keeps its pid and status - it is still running - and its files are
    left alone. Every other failure is per-lane, so the next lane still runs."""
    survived = _kill_lane(lane, kill_fn)
    if survived is not None:
        lane["abort_error"] = survived
        print(f"autopilot: lane {lane['name']}: {survived}", file=sys.stderr)
        return True
    lane["pid"] = None
    try:
        _clean_up_lane(repo, wave, lane, registry, run_git)
    except (OSError, subprocess.CalledProcessError) as err:
        lane["status"] = "abort_failed"
        lane["abort_error"] = f"worktree cleanup failed: {err}"
        print(
            f"autopilot: lane {lane['name']}: worktree cleanup failed: {err}",
            file=sys.stderr,
        )
        return True
    lane["status"] = "aborted"
    lane["abort_error"] = None
    return False


def abort(
    repo: Path,
    wave_path: Path,
    *,
    run_git: Callable[..., object] = _default_run_git,
    kill_fn: Callable[[int, int], object] = os.killpg,
) -> int:
    """Kill every lane's loop, return its PRDs and remove the worktrees this wave
    cut; 0 when every lane finished. The lock is held for the whole body, and the
    wave is reloaded under it."""
    with locked(wave_path):
        wave = load(wave_path)
        violations = _structural_errors(repo, wave)
        if violations:
            for violation in violations:
                print(f"autopilot: {violation}", file=sys.stderr)
            print("autopilot: refusing to touch this wave.json", file=sys.stderr)
            return 1
        registry = _worktree_branches(repo, run_git)
        failed = False
        for lane in sorted(wave["lanes"], key=lambda each: each["order"]):
            failed = _abort_lane(repo, wave, lane, registry, run_git, kill_fn) or failed
            save(wave_path, wave)
        # A lane that survived its kill still reads this directory, so it goes
        # only once every lane has finished - and only if a loop ever made it.
        slots = repo / "dev/local/autopilot/wave-slots"
        if not failed and slots.exists():
            try:
                shutil.rmtree(slots)
            except OSError as err:
                print(f"autopilot: could not remove {slots}: {err}", file=sys.stderr)
                failed = True
        wave["status"] = "abort_failed" if failed else "aborted"
        save(wave_path, wave)
        return 1 if failed else 0
