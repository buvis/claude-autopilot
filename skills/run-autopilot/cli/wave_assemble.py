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
import shutil
import subprocess
import sys
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from cli import records
from cli.wave import (
    WAVE_APPEND_ONLY,
    _structural_errors,
    load,
    locked,
    missing_message,
    save,
)
from cli.wave_launch import lane_status

WAVE_ASSEMBLY_BRANCH_FMT = "wave/{wave_id}/assembly"
WAVE_ASSEMBLY_WORKTREE_FMT = "{repo_parent}/{repo_name}-wave-{wave_id}"
_CONFLICT_MARKERS = re.compile(r"^(<{7}(?: .*)?|={7}|>{7}(?: .*)?)$", re.MULTILINE)
_AUTOPILOT = "docs/dev/project-management/autopilot"
_PRDS = "docs/dev/project-management/prds"
_REVIEWS = "docs/dev/project-management/reviews"
# `wave_launch._RETURN_TO`'s mapping: where each of a lane's lifecycle folders
# comes home to. A merged lane drains all four, a kept one all but done/ - its
# done/ is unassembled work, and stays where the lane left it.
_PRD_HOME = {"backlog": "backlog", "wip": "backlog", "done": "done", "hold": "hold"}
_PRD_LABELS = (("done", "done"), ("hold", "parked"), ("backlog", "backlog"))
_LANE_COLUMNS = ("lane", "branch", "status", "batch", "prds", "paths", "files")


def keep_both(text: str) -> str:
    """Strip git's conflict marker lines, keeping both sides of every hunk."""
    return "".join(
        line
        for line in text.splitlines(keepends=True)
        if not _CONFLICT_MARKERS.match(line.rstrip("\n"))
    )


def _totals(rows: list[dict]) -> str:
    """One `loop-metrics.jsonl` row is one session; a row may carry no wall time
    and may carry no cost, and an uncaptured cost is not a zero one."""
    hours = sum(row.get("wall_secs", 0) for row in rows) / 3600
    cost = sum(row["cost_usd"] for row in rows if row.get("cost_usd") is not None)
    return (
        f"totals: {len(rows)} sessions, {hours:.2f} wall hours,"
        f" ${cost:.2f} captured cost"
    )


def _lane_table(lanes: list[dict]) -> list[str]:
    """One markdown row per lane; every element of its list fields, not the first."""
    rows = [
        [
            each.get("name", ""),
            each.get("branch", ""),
            each.get("status", ""),
            each.get("batch_id") or "",
            ", ".join(each.get("prds") or []),
            ", ".join(each.get("paths") or []),
            ", ".join(each.get("files") or []),
        ]
        for each in lanes
    ]
    return [
        "| " + " | ".join(_LANE_COLUMNS) + " |",
        "|" + "|".join(["---"] * len(_LANE_COLUMNS)) + "|",
        *("| " + " | ".join(row) + " |" for row in rows),
    ]


def summary(wave: dict, rows: list[dict], records: list[dict]) -> str:
    """Render a wave's markdown report from already-loaded in-memory data."""
    assembly = wave.get("assembly") or {}
    lines = [
        f"# Wave {wave['id']} summary",
        "",
        f"- base: {wave.get('base_branch')} @ {wave.get('base_sha')}",
        f"- assembled head: {assembly.get('branch')} @ {assembly.get('head_sha')}",
        f"- {_totals(rows)}",
        "",
        "## Lanes",
        *_lane_table(wave["lanes"]),
        "",
        "## PRDs",
    ]
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


# ── migrate_lane ─────────────────────────────────────────────────────────────


def _batch_id(lane_ap: Path) -> str | None:
    """The batch this lane's loop ran: its own state.json, else - when that file
    is missing or unreadable - its newest final-state report. None when neither
    names one; the records still migrate, only untagged by batch."""
    candidates = [
        lane_ap / "state.json",
        *sorted(lane_ap.glob("reports/*-state-final.json"), reverse=True),
    ]
    for path in candidates:
        try:
            content = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        return (content.get("batch") or {}).get("id")
    return None


def _migrate_jsonl(lane_ap: Path, main_ap: Path, tags: dict) -> None:
    """Append every jsonl record the lane logged to the same-named file under the
    main checkout, each line re-serialized with the lane's tags merged in."""
    sources = [
        lane_ap / "loop-metrics.jsonl",
        lane_ap / "dispatch-metrics.jsonl",
        *sorted(lane_ap.glob("ledger/*.jsonl")),
    ]
    for source in sources:
        if not source.exists():
            continue
        target = main_ap / source.relative_to(lane_ap)
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "a", encoding="utf-8") as out:
            out.writelines(
                json.dumps({**json.loads(line), **tags}) + "\n"
                for line in source.read_text(encoding="utf-8").splitlines()
            )


def _migrate_deferred(lane_ap: Path, main_ap: Path, batch_id: str) -> None:
    """Every item the lane deferred, through `record_defer` - whose own op_id
    dedup is what makes a second pass a no-op. Each item keeps the PRD it names."""
    path = lane_ap / "deferred" / f"{batch_id}-deferred.json"
    if not path.exists():
        return
    content = json.loads(path.read_text(encoding="utf-8"))
    for item in content["items"]:
        records.record_defer(main_ap, item["prd"], batch_id, item)


def _copy_new(source: Path, target: Path) -> None:
    """Every file under `source` the main checkout does not already hold by that
    name; skipping the existing ones is what makes a second pass a no-op."""
    for path in sorted(source.glob("*")):
        if path.is_file() and not (target / path.name).exists():
            target.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target / path.name)


def _route_prds(main: Path, worktree: Path, merged: bool) -> None:
    """Move the PRDs the lane holds RIGHT NOW into their `_PRD_HOME` folder. A
    kept lane's done/ stays put; the re-scan is what makes a second pass a no-op,
    and is what drains that done/ once a later pass finds the lane assembled."""
    for folder, home in _PRD_HOME.items():
        if folder == "done" and not merged:
            continue
        target = main / _PRDS / home
        for prd in sorted((worktree / _PRDS / folder).glob("*.md")):
            target.mkdir(parents=True, exist_ok=True)
            shutil.move(str(prd), str(target / prd.name))


def migrate_lane(main: Path, wave_id: str, lane: dict) -> None:
    """Drain one lane's own records and PRDs into the main checkout.

    The jsonl append is guarded by `lane["migrated_at"]` - it would duplicate,
    not no-op, on a second pass. Everything after it is re-evaluated on every
    call: each step is idempotent on its own terms, and the PRD re-scan is how a
    kept lane's done/ reaches main done/ once a later call finds it assembled.
    Called only while the lane's worktree is still there."""
    worktree = Path(lane["worktree"])
    lane_ap, main_ap = worktree / _AUTOPILOT, main / _AUTOPILOT
    batch_id = _batch_id(lane_ap)
    lane["batch_id"] = batch_id
    if not lane.get("migrated_at"):
        tags = {"lane": lane["name"], "wave": wave_id}
        if batch_id is not None:
            tags["batch"] = batch_id
        _migrate_jsonl(lane_ap, main_ap, tags)
        lane["migrated_at"] = datetime.now(timezone.utc).isoformat()
    if batch_id is not None:
        _migrate_deferred(lane_ap, main_ap, batch_id)
    _copy_new(lane_ap / "reports", main_ap / "reports")
    _copy_new(worktree / _REVIEWS, main / _REVIEWS)
    _route_prds(main, worktree, lane["status"] == "assembled")


# ── the wave's report ────────────────────────────────────────────────────────


def _lane_prd_names(worktree: Path) -> set[str]:
    """Every PRD the lane still holds, including ones no lane ever listed."""
    return {
        path.name
        for folder in _PRD_HOME
        for path in (worktree / _PRDS / folder).glob("*.md")
    }


def _prd_label(main: Path, worktree: Path, prd: str) -> str | None:
    """The folder this PRD actually reached, in `summary`'s words; None when it
    reached none of them."""
    for folder, label in _PRD_LABELS:
        if (main / _PRDS / folder / prd).exists():
            return label
    if (worktree / _PRDS / "done" / prd).exists():
        return "unassembled"
    return None


def _wave_rows(main: Path, wave_id: str) -> list[dict]:
    """THIS wave's migrated loop-metrics rows - the file also holds every earlier
    batch's, and those are not this wave's totals."""
    path = main / _AUTOPILOT / "loop-metrics.jsonl"
    if not path.exists():
        return []
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    return [row for row in rows if row.get("wave") == wave_id]


def _conflict_records(main: Path, wave_id: str) -> list[dict]:
    """This wave's assembly_conflict deferred items, in the shape `summary`
    renders: the record's `detail` is the reason the lane was kept out."""
    path = main / _AUTOPILOT / "deferred" / f"{wave_id}-deferred.json"
    if not path.exists():
        return []
    items = json.loads(path.read_text(encoding="utf-8"))["items"]
    return [
        {"prd": item["prd"], "lane": item["lane"], "reason": item["detail"]}
        for item in items
        if item.get("site") == "assembly_conflict"
    ]


def _write_report(
    repo: Path,
    wave: dict,
    lanes: list[dict],
    prd_names: dict[str, set[str]],
) -> None:
    """Rewrite the wave's durable report whole, and mirror it into `ledger/` -
    the copy `purge-devlocal` never trims. `prds` is built here and nowhere
    else: `summary` is pure, so it cannot see which folder each PRD reached."""
    entries = [
        {"prd": prd, "lane": lane["name"], "label": label}
        for lane in lanes
        for prd in sorted(prd_names[lane["name"]])
        if (label := _prd_label(repo, Path(lane["worktree"]), prd))
    ]
    text = summary(
        {**wave, "prds": entries},
        _wave_rows(repo, wave["id"]),
        _conflict_records(repo, wave["id"]),
    )
    for folder in ("reports", "ledger"):
        target = repo / _AUTOPILOT / folder / f"{wave['id']}-wave.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")


def _drain_lane(
    repo: Path,
    wave: dict,
    lane: dict,
    *,
    run_git: Callable[..., subprocess.CompletedProcess],
) -> set[str]:
    """Migrate one lane, then drop a merged lane's worktree and branch; the PRDs
    it held when the migration started. A lane whose worktree a previous call
    already removed has nothing left to scan, so it is skipped - what it held is
    read back from `lane["held_prds"]`, the only record left of PRDs no lane
    listed in its own `prds`. The removal flag is set WITH the removal: a crash
    between the two still reads as not removed."""
    names = set(lane.get("held_prds") or [])
    if lane.get("worktree_removed"):
        return names
    names |= _lane_prd_names(Path(lane["worktree"]))
    lane["held_prds"] = sorted(names)
    migrate_lane(repo, wave["id"], lane)
    if lane["status"] == "assembled":
        run_git(["worktree", "remove", "--force", lane["worktree"]], cwd=repo)
        run_git(["branch", "-D", lane["branch"]], cwd=repo)
        lane["worktree_removed"] = True
    return names


def _open_assembly(
    repo: Path,
    wave: dict,
    *,
    run_git: Callable[..., subprocess.CompletedProcess],
) -> tuple[Path, str]:
    """The wave's assembly worktree and branch: created on the first call, and
    reused by a rerun that still finds both the recorded assembly and the
    worktree itself on disk."""
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
    return assembly, branch


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
        if wave is None:
            print(f"autopilot: {missing_message(wave_path)}", file=sys.stderr)
            return 1
        refusals = _refusals(repo, wave, run_git=run_git)
        if refusals:
            for refusal in refusals:
                print(f"autopilot: {refusal}", file=sys.stderr)
            return 1
        assembly, branch = _open_assembly(repo, wave, run_git=run_git)
        ordered = sorted(wave["lanes"], key=lambda each: each["order"])
        prd_names: dict[str, set[str]] = {}
        for lane in ordered:
            _assemble_lane(
                wave_path,
                wave,
                lane,
                assembly,
                run_git=run_git,
                run_checks=run_checks,
            )
            held = _drain_lane(repo, wave, lane, run_git=run_git)
            prd_names[lane["name"]] = set(lane["prds"]) | held
            save(wave_path, wave)
        kept = [each["name"] for each in ordered if each["status"] != "assembled"]
        wave["assembly"] = {
            "worktree": str(assembly),
            "branch": branch,
            "head_sha": run_git(["rev-parse", "HEAD"], cwd=assembly).stdout.strip(),
            "merged": [
                each["name"] for each in ordered if each["status"] == "assembled"
            ],
            "kept": kept,
        }
        wave["status"] = "assembled_partial" if kept else "assembled"
        _write_report(repo, wave, ordered, prd_names)
        save(wave_path, wave)
        return 3 if kept else 0
