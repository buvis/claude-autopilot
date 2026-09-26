"""cli/wave_launch.py - validate a planned wave and launch its lanes (PRD 00214).

`launch` is the wave's one destructive step: it cuts a worktree per lane, moves
each lane's PRDs into it and spawns a loop there. `wave.json` is a supported
hand-edit surface between `wave plan` and `wave launch`, so `validate` re-derives
every lane's paths from the backlog as it stands NOW, before anything is created.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
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
