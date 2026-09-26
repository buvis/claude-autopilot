"""The wave: cut the backlog into parallel lanes and keep `wave.json` (PRD 00214).

`wave.json` (dev/local/autopilot/wave.json) is a one-shot planning record for
the wave launcher, not PRD-lifecycle state: only `wave` and `wave_launch` read
or write it.
"""

from __future__ import annotations

import contextlib
import dataclasses
import fcntl
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from cli import lane

WAVE_APPEND_ONLY: tuple[str, ...] = ("CHANGELOG.md", "dev/bin/release-checks")
WAVE_FORCE_SHARED: tuple[str, ...] = (
    "skills/run-autopilot/SKILL.md",
    "skills/run-autopilot/references/state-schema.md",
    "skills/run-autopilot/cli/records.py",
)
_CORE_DIRS = ("skills/run-autopilot/cli/", "skills/run-autopilot/references/")
LANE_STATUSES = ("planned", "running", "aborted", "abort_failed")
WAVE_STATUSES = (*LANE_STATUSES, "done")


@dataclasses.dataclass(frozen=True)
class Lane:
    name: str
    order: int
    branch: str
    worktree: str
    prds: tuple[str, ...]
    paths: tuple[str, ...]
    status: str = "planned"
    pid: int | None = None  # also the process-group id (start_new_session)
    started_at: str | None = None
    worktree_created: bool = False
    abort_error: str | None = None

    def as_dict(self) -> dict:
        data = dataclasses.asdict(self)
        return {**data, "prds": list(self.prds), "paths": list(self.paths)}


class WaveCorruptError(Exception):
    """wave.json exists but is unreadable or not valid JSON."""

    def __str__(self) -> str:
        path, cause = self.args
        return f"{path}: {cause}"


def prd_paths(text: str) -> frozenset[str]:
    """The paths a PRD names, minus the append-only files every PRD touches."""
    return frozenset(lane.named_paths(text)) - frozenset(WAVE_APPEND_ONLY)


def shares(a: frozenset[str], b: frozenset[str]) -> bool:
    """True when path sets `a` and `b` must run in one lane."""
    if a & b:
        return True
    if any(y.startswith(x + "/") or x.startswith(y + "/") for x in a for y in b):
        return True
    forced = frozenset(WAVE_FORCE_SHARED)
    return bool(a & forced) and bool(b & forced)


def cut(prds: dict[str, str], max_lanes: int = 3) -> tuple[list[Lane], list[dict]]:
    """Pack PRDs (basename -> text, in sequence order) into unstamped lanes."""
    path_sets = {name: prd_paths(text) for name, text in prds.items()}
    held_back = [
        {"prd": name, "reason": "no named paths"}
        for name, paths in path_sets.items()
        if not paths
    ]
    names = [name for name, paths in path_sets.items() if paths]
    rank = {name: index for index, name in enumerate(names)}
    parent = {name: name for name in names}

    def find_root(name: str) -> str:
        while parent[name] != name:
            name = parent[name]
        return name

    for index, a in enumerate(names):
        for b in names[index + 1 :]:
            if shares(path_sets[a], path_sets[b]):
                parent[find_root(b)] = find_root(a)
    components: dict[str, list[str]] = {}
    for name in names:
        components.setdefault(find_root(name), []).append(name)
    bins: list[list[str]] = []
    for component in sorted(components.values(), key=lambda c: (-len(c), rank[c[0]])):
        if len(bins) < max_lanes:
            bins.append(list(component))
        else:
            min(bins, key=len).extend(component)
    lanes = [
        Lane(
            name="",
            order=0,
            branch="",
            worktree="",
            prds=tuple(sorted(members, key=rank.__getitem__)),
            paths=tuple(sorted(frozenset().union(*(path_sets[m] for m in members)))),
        )
        for members in bins
    ]
    return lanes, held_back


def _format_branch(wave_id: str, order: int) -> str:
    return f"wave/{wave_id}/l{order}"


def _format_worktree(repo: Path, order: int) -> str:
    return f"{repo.parent}/{repo.name}-l{order}"


def _count_core_paths(each: Lane) -> int:
    return sum(
        1 for path in each.paths if path in WAVE_FORCE_SHARED or path.startswith(_CORE_DIRS)
    )


def _order_lanes(lanes: list[Lane], wave_id: str, repo: Path) -> list[Lane]:
    """Number the lanes (core-touching lanes first) and stamp their names."""
    core = sorted(
        (each for each in lanes if _count_core_paths(each)),
        key=lambda each: (-_count_core_paths(each), min(each.prds)),
    )
    rest = [each for each in lanes if not _count_core_paths(each)]
    return [
        dataclasses.replace(
            each,
            order=order,
            name=f"l{order}",
            branch=_format_branch(wave_id, order),
            worktree=_format_worktree(repo, order),
        )
        for order, each in enumerate(core + rest, 1)
    ]


def load(path: Path) -> dict | None:
    """wave.json's content; None only when it does not exist."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as err:
        raise WaveCorruptError(path, err) from err


def save(path: Path, wave: dict) -> None:
    """Write wave.json atomically (tmp file, then replace). Caller holds the lock."""
    tmp = path.with_suffix(f".json.tmp.{os.getpid()}")
    try:
        tmp.write_text(json.dumps(wave, indent=2) + "\n", encoding="utf-8")
        tmp.replace(path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


@contextlib.contextmanager
def locked(wave_path: Path):
    """Hold an exclusive flock on the sibling `<wave_path>.lock` for the body."""
    with open(f"{wave_path}.lock", "a") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        yield


def plan(repo: Path, wave_path: Path, max_lanes: int = 3) -> int:
    """Cut the backlog into lanes and save them as a planned wave."""
    with locked(wave_path):
        try:
            existing = load(wave_path)
        except WaveCorruptError as err:
            print(
                f"autopilot: wave.json is corrupt ({err}); fix or remove it by hand"
                " before planning",
                file=sys.stderr,
            )
            return 1
        if existing is not None:
            errors = _structural_errors(repo, existing)
            for error in errors:
                print(f"autopilot: {error}", file=sys.stderr)
            if errors:
                print(
                    "autopilot: wave.json is structurally invalid; fix or remove it"
                    " by hand before planning",
                    file=sys.stderr,
                )
                return 1
            if existing["status"] not in ("done", "aborted"):
                print(
                    f"autopilot: wave {existing['id']} is still {existing['status']};"
                    " abort it before planning a new one",
                    file=sys.stderr,
                )
                return 1
        if max_lanes < 1:
            print(f"autopilot: max lanes must be at least 1, got {max_lanes}", file=sys.stderr)
            return 1
        backlog = sorted((repo / "dev/local/prds/backlog").glob("*.md"))
        lanes, held_back = cut({p.name: p.read_text(encoding="utf-8") for p in backlog}, max_lanes)
        if not lanes:
            print("autopilot: no lanes to plan - every PRD is held back", file=sys.stderr)
            return 1
        now = datetime.now(timezone.utc)
        wave_id = now.strftime("%Y%m%d%H%M")
        lanes = _order_lanes(lanes, wave_id, repo)
        for each in lanes:
            print(f"{each.name}  {each.branch}")
            print(f"    prds:  {', '.join(each.prds)}")
            print(f"    paths: {', '.join(each.paths)}")
        print("held back:" if held_back else "held back: none")
        for entry in held_back:
            print(f"    {entry['prd']}: {entry['reason']}")
        save(
            wave_path,
            {
                "id": wave_id,
                "status": "planned",
                "repo": str(repo),
                "base_branch": None,
                "base_sha": None,
                "review_slots": 3,
                "created_at": now.isoformat(),
                "lanes": [each.as_dict() for each in lanes],
                "held_back": held_back,
            },
        )
        return 0


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_basename(value: object) -> bool:
    return isinstance(value, str) and "/" not in value and value not in ("", ".", "..")


_TOP_CHECKS = {
    "id": lambda v: isinstance(v, str),
    "repo": lambda v: isinstance(v, str),
    "status": lambda v: v in WAVE_STATUSES,
    "lanes": lambda v: isinstance(v, list) and bool(v),
    "review_slots": lambda v: _is_int(v) and v > 0,
}
_LANE_CHECKS = {
    "name": lambda v: isinstance(v, str),
    "order": lambda v: _is_int(v) and v > 0,
    "branch": lambda v: isinstance(v, str),
    "worktree": lambda v: isinstance(v, str),
    "prds": lambda v: isinstance(v, list) and bool(v) and all(map(_is_basename, v)),
    "paths": lambda v: True,
    "status": lambda v: v in LANE_STATUSES,
    "pid": lambda v: v is None or _is_int(v),
    "started_at": lambda v: True,
    "worktree_created": lambda v: isinstance(v, bool),
    "abort_error": lambda v: True,
}


def _structural_errors(repo: Path, wave: dict) -> list[str]:
    """One violation string per structural problem in `wave`; [] when sound."""
    if not isinstance(wave, dict):
        return ["wave.json: top level is not an object"]
    errors = [
        f"wave.json: malformed top-level field {field}"
        for field, ok in _TOP_CHECKS.items()
        if field not in wave or not ok(wave[field])
    ]
    if errors:
        return errors
    if wave["repo"] != str(repo):
        return ["wave.json was planned for a different repo"]
    lanes = wave["lanes"]
    for index, each in enumerate(lanes):
        if not isinstance(each, dict):
            errors.append(f"lane {index}: not an object")
            continue
        name = each.get("name")
        label = name if isinstance(name, str) and name else index
        errors += [
            f"lane {label}: malformed field {field}"
            for field, ok in _LANE_CHECKS.items()
            if field not in each or not ok(each[field])
        ]
    if errors:
        return errors
    for field in ("order", "name", "branch", "worktree"):
        first: dict = {}
        for each in lanes:
            value = each[field]
            if value in first:
                errors.append(
                    f"lane {first[value]} and lane {each['name']} both use {field} {value}"
                )
            else:
                first[value] = each["name"]
    owner: dict[str, int] = {}
    for index, each in enumerate(lanes):
        for prd in each["prds"]:
            if owner.get(prd) == index:
                errors.append(f"lane {each['name']} lists {prd} twice")
            elif prd in owner:
                errors.append(f"{prd} is listed in more than one lane")
            else:
                owner[prd] = index
    for each in lanes:
        order = each["order"]
        if each["worktree"] != _format_worktree(repo, order):
            errors.append(
                f"lane {each['name']}: worktree does not match the canonical path"
                f" for order {order}"
            )
        if each["branch"] != _format_branch(wave["id"], order):
            errors.append(
                f"lane {each['name']}: branch does not match the canonical name"
                f" for order {order}"
            )
    return errors
