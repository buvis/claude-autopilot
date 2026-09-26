"""Wave assembly (PRD 00214): merge the drained lanes into one assembly branch.

`keep_both` strips git's three-way conflict marker lines while keeping both
sides of every hunk. `summary` renders a wave's markdown report from
already-computed, already-loaded in-memory data: a wave dict, this wave's
migrated loop-metrics rows, and this wave's assembly_conflict records. Both
are pure - no disk, no git. `assemble` is the merge pass itself.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from cli.wave import WAVE_APPEND_ONLY, _structural_errors, load, locked, save
from cli.wave_launch import lane_status

WAVE_ASSEMBLY_BRANCH_FMT = "wave/{wave_id}/assembly"
WAVE_ASSEMBLY_WORKTREE_FMT = "{repo_parent}/{repo_name}-wave-{wave_id}"
_CONFLICT_MARKERS = re.compile(r"^(<{7}(?: .*)?|={7}|>{7}(?: .*)?)$", re.MULTILINE)


def keep_both(text: str) -> str:
    """Strip git's conflict marker lines, keeping both sides of every hunk."""
    return "".join(
        line
        for line in text.splitlines(keepends=True)
        if not _CONFLICT_MARKERS.match(line.rstrip("\n"))
    )


def summary(wave: dict, rows: list[dict], records: list[dict]) -> str:
    """Render a wave's markdown report from already-loaded in-memory data."""
    lines = [f"# Wave {wave['id']} summary", "", "## PRDs"]
    for entry in wave["prds"]:
        lines.append(
            f"- {entry['prd']}: Wave {wave['id']}, lane {entry['lane']}, "
            f"{entry['label']}"
        )
    lines += ["", "## Assembly conflicts"]
    if records:
        for record in records:
            lines.append(
                f"- {record['prd']} (lane {record['lane']}): {record['reason']}"
            )
    else:
        lines.append("(none)")
    lines += ["", "## Integrator notes"]
    notes = [
        (note["sha"], note["text"])
        for each_lane in wave["lanes"]
        for note in (each_lane.get("integrator_notes") or [])
    ]
    if notes:
        lines += [f"- {sha}: {text}" for sha, text in notes]
    else:
        lines.append("(none)")
    return "\n".join(lines) + "\n"


# ── assemble ─────────────────────────────────────────────────────────────────


def _git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    """`git <args>` in `cwd`. GIT_EDITOR=true lets `rebase --continue` commit
    unattended, and the plain two-way conflict style is the only one
    `keep_both` understands."""
    return subprocess.run(
        ["git", "-c", "merge.conflictStyle=merge", *args],
        cwd=cwd,
        env={**os.environ, "GIT_EDITOR": "true"},
        capture_output=True,
        text=True,
        check=check,
    )


def _run_release_checks(cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", "dev/bin/release-checks"],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def _integrator_notes(repo: Path, base: str, branch: str) -> list[dict]:
    """Every `Integrator:` trailer on the lane's commits, oldest first, named by
    the sha the lane wrote: read before the rebase rewrites it."""
    out = _git(
        repo,
        "log",
        "--reverse",
        "--format=%H%n%(trailers:key=Integrator,valueonly,unfold)%x1e",
        f"{base}..{branch}",
    ).stdout
    notes: list[dict] = []
    for record in out.split("\x1e"):
        lines = record.strip("\n").splitlines()
        notes += [{"sha": lines[0][:7], "text": text} for text in lines[1:]]
    return notes


def _rebase(worktree: Path, onto: str) -> list[str]:
    """Rebase the branch checked out at `worktree` onto `onto`, keeping both
    sides of every append-only conflict. [] once it lands; the sorted conflicted
    paths outside the append-only set when it cannot, with the rebase aborted."""
    step = _git(worktree, "rebase", onto, check=False)
    while step.returncode != 0:
        diff = ["diff", "--name-only", "--diff-filter=U"]
        conflicted = _git(worktree, *diff).stdout.splitlines()
        if not conflicted:
            _git(worktree, "rebase", "--abort", check=False)
            step.check_returncode()
        others = sorted(set(conflicted) - set(WAVE_APPEND_ONLY))
        if others:
            _git(worktree, "rebase", "--abort")
            return others
        for rel in conflicted:
            path = worktree / rel
            text = path.read_text(encoding="utf-8")
            path.write_text(keep_both(text), encoding="utf-8")
        _git(worktree, "add", "--", *conflicted)
        step = _git(worktree, "rebase", "--continue", check=False)
    return []


def _merge_lane(
    repo: Path,
    wave: dict,
    lane: dict,
    assembly: Path,
    run_checks: Callable[[Path], subprocess.CompletedProcess],
) -> dict | None:
    """Rebase one drained lane onto the assembly branch, fast-forward it and run
    the checks there. None once the lane is assembled; its assembly_conflict
    record when it is kept out."""
    base, branch = wave["base_sha"], lane["branch"]
    changed = _git(repo, "diff", "--name-only", base, branch).stdout
    lane["files"] = sorted(changed.splitlines())
    lane["integrator_notes"] = _integrator_notes(repo, base, branch)
    record = {
        "type": "stall",
        "site": "assembly_conflict",
        "lane": lane["name"],
        "op_id": f"wave-{wave['id']}-{lane['name']}",
        "prd": lane["prds"][0],
    }
    onto = WAVE_ASSEMBLY_BRANCH_FMT.format(wave_id=wave["id"])
    others = _rebase(Path(lane["worktree"]), onto)
    if others:
        lane["status"] = "conflict"
        lane["conflict_paths"] = others
        lane["conflict_detail"] = (
            f"{len(others)} conflicted path(s) outside the append-only set:"
            f" {', '.join(others)}"
        )
        return {**record, "files": others, "detail": lane["conflict_detail"]}
    before = _git(assembly, "rev-parse", "HEAD").stdout.strip()
    _git(assembly, "merge", "--ff-only", branch)
    checks = run_checks(assembly)
    if checks.returncode != 0:
        _git(assembly, "reset", "--hard", before)
        tail = (checks.stderr or checks.stdout or "").strip().splitlines()
        lane["status"] = "checks_failed"
        lane["conflict_detail"] = (
            f"release-checks exit {checks.returncode} after merging {branch}:"
            f" {tail[-1] if tail else ''}"
        )
        return {**record, "detail": lane["conflict_detail"]}
    lane["status"] = "assembled"
    return None


def _refusals(repo: Path, wave: dict) -> list[str]:
    """Why this wave must not be assembled now; [] when it may. Every check runs
    before anything is created."""
    shape = _structural_errors(repo, wave)
    if shape:
        return shape
    if wave["status"] != "running":
        return [f"wave is not in running state (it is {wave['status']})"]
    return [
        f"lane {lane['name']} is still running - wait or abort"
        for lane in sorted(wave["lanes"], key=lambda each: each["order"])
        if lane_status(lane) == "running"
    ]


def assemble(
    repo: Path,
    wave_path: Path,
    *,
    run_checks: Callable[[Path], subprocess.CompletedProcess] = _run_release_checks,
) -> int:
    """Merge every drained lane, in order, into the wave's assembly branch; an
    unfinished lane is skipped, a conflicting or check-breaking one is kept out
    and recorded as deferred. The lock is held for the whole body."""
    with locked(wave_path):
        wave = load(wave_path)
        refusals = _refusals(repo, wave)
        if refusals:
            for refusal in refusals:
                print(f"autopilot: {refusal}", file=sys.stderr)
            return 1
        assembly = Path(
            WAVE_ASSEMBLY_WORKTREE_FMT.format(
                repo_parent=repo.parent,
                repo_name=repo.name,
                wave_id=wave["id"],
            ),
        )
        branch = WAVE_ASSEMBLY_BRANCH_FMT.format(wave_id=wave["id"])
        _git(repo, "worktree", "add", str(assembly), "-b", branch, wave["base_sha"])
        records: list[dict] = []
        for lane in sorted(wave["lanes"], key=lambda each: each["order"]):
            if lane_status(lane) == "drained":
                record = _merge_lane(repo, wave, lane, assembly, run_checks)
                records += [record] if record else []
            else:
                lane["status"] = "unfinished"
            save(wave_path, wave)
        if records:
            deferred = wave_path.parent / "deferred" / f"{wave['id']}-deferred.json"
            deferred.parent.mkdir(parents=True, exist_ok=True)
            content = {"batch_id": wave["id"], "items": records}
            deferred.write_text(json.dumps(content, indent=2) + "\n", encoding="utf-8")
        wave["status"] = "assembled"
        save(wave_path, wave)
        return 0
