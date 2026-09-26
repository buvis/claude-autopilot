"""Wave assembly (PRD 00214): merge the drained lanes into one assembly branch.

`keep_both` strips git's three-way conflict marker lines while keeping both
sides of every hunk. `summary` renders a wave's markdown report from
already-computed, already-loaded in-memory data: a wave dict, this wave's
migrated loop-metrics rows, and this wave's assembly_conflict records. Both
are pure - no disk, no git. `assemble` is the merge pass itself.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from cli import records
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


def _default_run_git(
    args: list[str],
    cwd: Path | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess:
    """`git <args>`: "git" is prepended here, never by a call site. GIT_EDITOR=true
    lets `rebase --continue` commit unattended, and the plain two-way conflict
    style is the only one `keep_both` understands - both belong here, so an
    injected fake sees the same argument shape."""
    return subprocess.run(
        ["git", "-c", "merge.conflictStyle=merge", *args],
        cwd=cwd,
        env={**os.environ, "GIT_EDITOR": "true"},
        capture_output=True,
        text=True,
        check=check,
    )


def _default_run_checks(cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", "dev/bin/release-checks"],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def lane_files_and_notes(
    lane: dict,
    base_sha: str,
    *,
    run_git: Callable[..., subprocess.CompletedProcess],
) -> tuple[list[str], list[dict]]:
    """One lane's changed paths (sorted) and every `Integrator:` trailer on its
    commits, oldest first, named by the sha the lane wrote: read in the lane's
    own worktree before the rebase rewrites it."""
    worktree, branch = Path(lane["worktree"]), lane["branch"]
    changed = run_git(
        ["diff", "--name-only", base_sha, branch],
        cwd=worktree,
    ).stdout
    out = run_git(
        [
            "log",
            "--reverse",
            "--format=%H%n%(trailers:key=Integrator,valueonly,unfold)%x1e",
            f"{base_sha}..{branch}",
        ],
        cwd=worktree,
    ).stdout
    notes: list[dict] = []
    for record in out.split("\x1e"):
        lines = record.strip("\n").splitlines()
        notes += [{"sha": lines[0][:7], "text": text} for text in lines[1:]]
    return sorted(changed.splitlines()), notes


def _rebase(
    worktree: Path,
    onto: str,
    *,
    run_git: Callable[..., subprocess.CompletedProcess],
) -> list[str]:
    """Rebase the branch checked out at `worktree` onto `onto`, keeping both
    sides of every append-only conflict. [] once it lands; the sorted conflicted
    paths outside the append-only set when it cannot, with the rebase aborted."""
    step = run_git(["rebase", onto], cwd=worktree, check=False)
    while step.returncode != 0:
        diff = ["diff", "--name-only", "--diff-filter=U"]
        conflicted = run_git(diff, cwd=worktree).stdout.splitlines()
        if not conflicted:
            run_git(["rebase", "--abort"], cwd=worktree, check=False)
            step.check_returncode()
        others = sorted(set(conflicted) - set(WAVE_APPEND_ONLY))
        if others:
            run_git(["rebase", "--abort"], cwd=worktree)
            return others
        for rel in conflicted:
            path = worktree / rel
            text = path.read_text(encoding="utf-8")
            path.write_text(keep_both(text), encoding="utf-8")
        run_git(["add", "--", *conflicted], cwd=worktree)
        step = run_git(["rebase", "--continue"], cwd=worktree, check=False)
    return []


def merge_lane(
    assembly: Path,
    lane: dict,
    *,
    run_git: Callable[..., subprocess.CompletedProcess],
    run_checks: Callable[[Path], subprocess.CompletedProcess],
) -> str:
    """Rebase one drained lane onto the assembly branch, fast-forward it and run
    the checks there; the lane's new status - "assembled", "conflict" or
    "checks_failed". Anything but "assembled" also sets `lane["conflict_detail"]`,
    and "conflict" alone sets `lane["conflict_paths"]`."""
    branch = lane["branch"]
    before = run_git(["rev-parse", "HEAD"], cwd=assembly).stdout.strip()
    others = _rebase(Path(lane["worktree"]), before, run_git=run_git)
    if others:
        lane["conflict_paths"] = others
        lane["conflict_detail"] = (
            f"{len(others)} conflicted path(s) outside the append-only set:"
            f" {', '.join(others)}"
        )
        return "conflict"
    run_git(["merge", "--ff-only", branch], cwd=assembly)
    checks = run_checks(assembly)
    if checks.returncode != 0:
        run_git(["reset", "--hard", before], cwd=assembly)
        tail = (checks.stderr or checks.stdout or "").strip().splitlines()
        lane["conflict_detail"] = (
            f"release-checks exit {checks.returncode} after merging {branch}:"
            f" {tail[-1] if tail else ''}"
        )
        return "checks_failed"
    return "assembled"


def _refusals(
    repo: Path,
    wave: dict,
    *,
    run_git: Callable[..., subprocess.CompletedProcess],
) -> list[str]:
    """Why this wave must not be assembled now; [] when it may. Every check runs
    before anything is created."""
    shape = _structural_errors(repo, wave)
    if shape:
        return shape
    live = [
        f"lane {lane['name']} is still running - wait or abort"
        for lane in sorted(wave["lanes"], key=lambda each: each["order"])
        if lane_status(lane) == "running"
    ]
    if live:
        return live
    if run_git(["status", "--porcelain"], cwd=repo).stdout.strip():
        return [f"{repo} has uncommitted changes - commit or stash them first"]
    if wave["status"] not in ("running", "assembled", "assembled_partial"):
        return [f"wave is not in running state (it is {wave['status']})"]
    return []


def _assemble_lane(
    wave_path: Path,
    wave: dict,
    lane: dict,
    assembly: Path,
    *,
    run_git: Callable[..., subprocess.CompletedProcess],
    run_checks: Callable[[Path], subprocess.CompletedProcess],
) -> None:
    """Take one lane through the merge pass: an already-assembled lane is left
    alone, an unfinished one is only marked, and a kept-out one is deferred."""
    if lane["status"] == "assembled":
        return
    if lane_status(lane) == "unfinished":
        lane["status"] = "unfinished"
        return
    lane["files"], lane["integrator_notes"] = lane_files_and_notes(
        lane,
        wave["base_sha"],
        run_git=run_git,
    )
    lane["status"] = merge_lane(
        assembly,
        lane,
        run_git=run_git,
        run_checks=run_checks,
    )
    if lane["status"] == "assembled":
        return
    paths = lane.get("conflict_paths")
    records.record_defer(
        wave_path.parent,
        lane["prds"][0],
        wave["id"],
        {
            "type": "stall",
            "site": "assembly_conflict",
            "lane": lane["name"],
            **({"files": paths} if paths is not None else {}),
            "detail": lane["conflict_detail"],
            "op_id": f"wave-{wave['id']}-{lane['name']}",
        },
    )


def assemble(
    repo: Path,
    wave_path: Path,
    *,
    run_git: Callable[..., subprocess.CompletedProcess] = _default_run_git,
    run_checks: Callable[[Path], subprocess.CompletedProcess] = _default_run_checks,
) -> int:
    """Merge every drained lane, in order, into the wave's assembly branch; an
    unfinished lane is skipped, a conflicting or check-breaking one is kept out
    and recorded as deferred. The lock is held for the whole body."""
    with locked(wave_path):
        wave = load(wave_path)
        refusals = _refusals(repo, wave, run_git=run_git)
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
        if not (wave.get("assembly") and assembly.exists()):
            run_git(
                ["worktree", "add", str(assembly), "-b", branch, wave["base_sha"]],
                cwd=repo,
            )
        for lane in sorted(wave["lanes"], key=lambda each: each["order"]):
            _assemble_lane(
                wave_path,
                wave,
                lane,
                assembly,
                run_git=run_git,
                run_checks=run_checks,
            )
            save(wave_path, wave)
        wave["status"] = "assembled"
        save(wave_path, wave)
        return 0
