"""Assembly-review PRD stub: `stub_text` renders the body and `review_paths`
computes the diff-scope path list, both from an already-assembled wave dict
(`wave.json` after `wave_assemble.assemble` has populated `wave["assembly"]`).
`seed_state` seeds the assembly worktree's state.json at review, and `review`
runs one loop there and records its outcome in wave.json.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from cli import wave_assemble
from cli.wave import WAVE_APPEND_ONLY, _is_basename, load, locked, save
from cli.wave_assemble import _default_run_git
from cli.wave_launch import _SPAWN_CMD, CLI_MAIN_PATH

_STATECTL = Path(__file__).resolve().parent.parent / "scripts" / "statectl.py"
_PINNED_PLUGINS = ("aegis@buvis-plugins", "warden@buvis-plugins")


def review_paths(wave: dict) -> list[str]:
    """Paths worth a human diff pass: those a lane's `files` names in more
    than one lane, plus the append-only files every PRD touches."""
    counts: dict[str, int] = {}
    for lane in wave["lanes"]:
        for path in set(lane.get("files") or []):
            counts[path] = counts.get(path, 0) + 1
    multi = {path for path, n in counts.items() if n > 1}
    return sorted(multi | set(WAVE_APPEND_ONLY))


def _label(lane: dict) -> str:
    return f"{lane['name']} ({', '.join(lane['prds'])})"


def _keep_both(lane: dict) -> str:
    notes = lane.get("integrator_notes") or []
    if not notes:
        return "no keep-both resolutions recorded"
    return ", ".join(note["text"] for note in notes)


def _stub_frontmatter() -> list[str]:
    return [
        "---",
        "catchup: skip",
        "design: skip",
        "rework_cap: 2",
        "default_model: sonnet",
        "model_tier_rationale: fixes to conflict resolutions and lane"
        " interactions found by the assembly review",
        "---",
        "",
    ]


def _stub_overview(wave: dict, assembly: dict, merged: list[dict]) -> list[str]:
    return [
        f"# Wave {wave['id']} assembly",
        "",
        "## Overview",
        "",
        *[f"- {_label(each)}" for each in merged],
        "",
        f"Diff range: {wave['base_sha']}..{assembly['head_sha']}",
        "",
        "Diff scope:",
        *[f"- {path}" for path in review_paths(wave)],
        "",
    ]


def _stub_functional_decomposition(merged: list[dict]) -> list[str]:
    return [
        "## Functional Decomposition",
        "",
        "### Capability: Assembly",
        "",
        "#### Feature: Lane merges",
        "",
        "Description:",
        *[f"- {each['name']}: {', '.join(each['prds'])}" for each in merged],
        "",
        "Inputs:",
        *[f"- {each['name']}: {', '.join(each['prds'])}" for each in merged],
        "",
        "Outputs:",
        *[
            f"- {each['name']}: {', '.join(each.get('files') or [])}"
            for each in merged
        ],
        "",
        "Behavior:",
        *[f"- {each['name']}: {_keep_both(each)}" for each in merged],
        "",
    ]


def _stub_implementation_phases(merged: list[dict]) -> list[str]:
    return [
        "## Implementation Phases",
        "",
        "### Phase 0: Assembly",
        "",
        *[
            f"- [x] Merge lane {_label(each)} - Acceptance: release-checks green"
            for each in merged
        ],
        "",
    ]


def _stub_test_strategy(merged: list[dict]) -> list[str]:
    return [
        "## Test Strategy",
        "",
        "- bash dev/bin/release-checks",
        *[
            f"- See {prd}'s own Test Strategy"
            for each in merged
            for prd in each["prds"]
        ],
        "",
    ]


def stub_text(wave: dict) -> str:
    """The assembly-review PRD body for `wave`, naming every merged lane."""
    if "assembly" not in wave:
        raise ValueError("wave has no assembly - run `wave assemble` first")
    assembly = wave["assembly"]
    lanes_by_name = {lane["name"]: lane for lane in wave["lanes"]}
    merged = [lanes_by_name[name] for name in assembly["merged"]]

    lines = [
        *_stub_frontmatter(),
        *_stub_overview(wave, assembly, merged),
        *_stub_functional_decomposition(merged),
        *_stub_implementation_phases(merged),
        *_stub_test_strategy(merged),
    ]
    return "\n".join(lines)


def _stub_name(wave: dict) -> str:
    return f"{wave['id']}-wave-assembly-v1.md"


def _run_cli(argv: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(argv, capture_output=True, text=True, check=False)


def _seed_prd(pm: Path, wave: dict) -> str:
    """Create the prds/{backlog,wip,done,hold} folders and write the assembly
    stub PRD into wip/, returning its filename."""
    for folder in ("backlog", "wip", "done", "hold"):
        (pm / "prds" / folder).mkdir(parents=True, exist_ok=True)
    stub = _stub_name(wave)
    (pm / "prds" / "wip" / stub).write_text(stub_text(wave), encoding="utf-8")
    return stub


def _seed_batch(plugins_json: Path, wave: dict) -> dict:
    """The `batch` state value: wave id, empty completed_prds, and the pinned
    plugin versions read from `plugins_json`."""
    try:
        installed = json.loads(plugins_json.read_text(encoding="utf-8"))
    except FileNotFoundError as err:
        raise RuntimeError(f"{plugins_json}: no such file") from err
    plugins = installed.get("plugins", {})
    for name in _PINNED_PLUGINS:
        if name not in plugins:
            raise RuntimeError(f"{plugins_json}: missing pinned plugin {name}")
    versions = {}
    for name in _PINNED_PLUGINS:
        try:
            versions[name] = plugins[name][0]["version"]
        except (KeyError, IndexError, TypeError) as err:
            raise RuntimeError(
                f"{plugins_json}: malformed entry for {name}",
            ) from err
    return {
        "id": wave["id"],
        "mode": "autopilot",
        "completed_prds": [],
        "plugin_versions": versions,
    }


def _seed_steps(
    state_path: Path,
    wave: dict,
    stub: str,
    batch: dict,
) -> list[list[str]]:
    """The CLI invocations that seed `state_path`: `init` (skipped on retry
    once state.json exists), one `statectl set` per key, then `phase-done`."""
    state = str(state_path)
    steps = (
        []
        if state_path.exists()
        else [
            ["python3", str(CLI_MAIN_PATH), "init", "--state", state, "--prd", stub],
        ]
    )
    steps += [
        ["python3", str(_STATECTL), state, "set", key, json.dumps(value)]
        for key, value in (
            ("work_start_sha", wave["base_sha"]),
            ("cycle", 1),
            ("rework_cap", 2),
            ("batch", batch),
        )
    ]
    steps.append(
        [
            "python3",
            str(CLI_MAIN_PATH),
            "phase-done",
            "--state",
            state,
            "--outcome",
            "tasks_done",
        ],
    )
    return steps


def _repo_from_worktree(worktree: Path) -> Path:
    """The main checkout `git worktree add` created `worktree` from, read
    from the worktree's own `.git` file (`gitdir: <repo>/.git/worktrees/<name>`)."""
    line = (worktree / ".git").read_text(encoding="utf-8").strip()
    gitdir = Path(line.removeprefix("gitdir:").strip())
    return gitdir.parents[2]


def seed_state(
    state_path: Path,
    wave: dict,
    plugins_json: Path,
    *,
    run_cli: Callable[[list[str]], subprocess.CompletedProcess] = _run_cli,
) -> None:
    """Seed `state_path` as a build whose tasks are done (next phase: review)
    for the assembly stub PRD, written into prds/wip/. Raises RuntimeError on
    a failed step; a retry skips init once state.json exists."""
    pm = state_path.parent.parent
    state_path.parent.mkdir(parents=True, exist_ok=True)
    stub = _seed_prd(pm, wave)
    repo = _repo_from_worktree(state_path.parents[4])
    meta = repo / "docs/dev/project-management/meta"
    if meta.exists():
        shutil.copytree(meta, pm / "meta", dirs_exist_ok=True)
    batch = _seed_batch(plugins_json, wave)
    for argv in _seed_steps(state_path, wave, stub, batch):
        result = run_cli(argv)
        if result.returncode != 0:
            raise RuntimeError(
                f"seed step `{' '.join(argv[2:])}` exited {result.returncode}:"
                f" {result.stderr.strip()}",
            )


def _check_reviewable(
    repo: Path,
    wave: dict,
    run_git: Callable[..., subprocess.CompletedProcess] = _default_run_git,
) -> Path:
    """The assembly worktree; ValueError when the wave is not assembled, the
    worktree is gone, or `repo` has any uncommitted change."""
    if not _is_basename(wave.get("id")):
        raise ValueError("wave.json: malformed top-level field id")
    if "assembly" not in wave:
        raise ValueError("wave has no assembly - run `wave assemble` first")
    if wave.get("status") not in ("assembled", "assembled_partial"):
        raise ValueError(f"wave status {wave.get('status')!r} is not reviewable")
    worktree = Path(wave["assembly"]["worktree"])
    if not worktree.is_dir():
        raise ValueError(f"assembly worktree {worktree} is gone")
    dirty = run_git(["-C", str(repo), "status", "--porcelain"]).stdout
    if dirty:
        raise ValueError(f"{repo} has uncommitted changes:\n{dirty}")
    return worktree


def review(
    repo: Path,
    wave: dict,
    *,
    spawn_fn: Callable[..., subprocess.Popen] = subprocess.Popen,
    run_git: Callable[..., subprocess.CompletedProcess] = _default_run_git,
) -> str:
    """Review the assembly: seed its worktree at review, run one loop there to
    exit, and record the outcome in wave.json - converged when the stub PRD
    ends in done/, review_failed when it ends in hold/ or stays in wip/."""
    worktree = _check_reviewable(repo, wave, run_git=run_git)
    pm = worktree / "docs/dev/project-management"
    seed_state(
        pm / "autopilot/state.json",
        wave,
        Path.home() / ".claude/plugins/installed_plugins.json",
    )
    (pm / "autopilot/review-paths").write_text(
        "".join(f"{path}\n" for path in review_paths(wave)),
        encoding="utf-8",
    )

    skip = ("_AUTOPILOT_LOOP", "_AUTOPILOT_REVIEW_SLOTS_DIR", "_AUTOPILOT_REVIEW_SLOTS")
    env = {k: v for k, v in os.environ.items() if k not in skip}
    env["_AUTOPILOT_TRACON_CHILD"] = "1"
    with open(pm / "autopilot/wrapper.log", "a") as log:
        loop = spawn_fn(
            ["bash", "-c", _SPAWN_CMD, str(CLI_MAIN_PATH)],
            cwd=str(worktree),
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    loop.wait()

    done = (pm / "prds/done" / _stub_name(wave)).exists()
    outcome = "converged" if done else "review_failed"
    wave_path = repo / "docs/dev/project-management/autopilot/wave.json"
    with locked(wave_path):
        current = load(wave_path)
        current["status"] = outcome
        save(wave_path, current)
    return outcome


def _land_migrate(repo: Path, wave_path: Path, wave: dict) -> None:
    """Migrate the assembly lane's records into `repo`, recording progress in
    wave.json even when migration raises so a retry can resume. Raises when
    the stub PRD did not land in the main checkout's prds/done/."""
    wave["assembly"]["name"] = "assembly"
    wave["assembly"]["status"] = "assembled"
    try:
        wave_assemble.migrate_lane(repo, wave["id"], wave["assembly"])
        stub = repo / "docs/dev/project-management/prds/done" / _stub_name(wave)
        if not stub.exists():
            raise RuntimeError(f"assembly stub {stub} did not land in prds/done/")
    finally:
        with locked(wave_path):
            current = load(wave_path)
            current["assembly"] = wave["assembly"]
            save(wave_path, current)


def _land_merge(
    repo: Path,
    tip: str,
    run_git: Callable[..., subprocess.CompletedProcess],
) -> None:
    """Fast-forward `repo` to the assembly branch's tip `tip`."""
    run_git(["-C", str(repo), "merge", "--ff-only", tip])


def _cycle_count(worktree: Path) -> int:
    """The review loop's cycle count, from the assembly worktree's state.json."""
    state = worktree / "docs/dev/project-management/autopilot/state.json"
    return json.loads(state.read_text(encoding="utf-8"))["cycle"]


def _append_summary_line(repo: Path, wave_id: str, line: str) -> None:
    """Append `line` to the wave's report and ledger markdown files, creating
    each (and its parent folder) on first use. Skips a file where `line`
    already appears verbatim, so a retry does not duplicate it."""
    for folder in ("reports", "ledger"):
        path = (
            repo
            / "docs/dev/project-management/autopilot"
            / folder
            / f"{wave_id}-wave.md"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        if line in existing.splitlines():
            continue
        path.write_text(existing + line + "\n", encoding="utf-8")


def _land_cleanup(
    repo: Path,
    wave_path: Path,
    wave: dict,
    run_git: Callable[..., subprocess.CompletedProcess],
) -> None:
    """The destructive tail of `land`, safe to retry once status is already
    "done": drop the assembly worktree (refusing over uncommitted changes)
    and its branch, remove wave-slots, and archive wave.json into reports/."""
    worktree = Path(wave["assembly"]["worktree"])
    if worktree.is_dir():
        migrated_stub = f"docs/dev/project-management/prds/done/{_stub_name(wave)}"
        dirty = run_git(
            [
                "-C",
                str(worktree),
                "status",
                "--porcelain",
                "--",
                f":(exclude){migrated_stub}",
            ],
        ).stdout
        if dirty.strip():
            raise ValueError(f"{worktree} has uncommitted changes:\n{dirty}")
        run_git(["-C", str(repo), "worktree", "remove", "--force", str(worktree)])

    branch = f"wave/{wave['id']}/assembly"
    if run_git(["-C", str(repo), "branch", "--list", branch]).stdout.strip():
        run_git(["-C", str(repo), "branch", "-d", branch])

    slots = repo / "docs/dev/project-management/autopilot/wave-slots"
    if slots.exists():
        shutil.rmtree(slots)

    reports_dir = repo / "docs/dev/project-management/autopilot/reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    save(reports_dir / f"{wave['id']}-wave.json", wave)
    wave_path.unlink()


def _land_converged(
    repo: Path,
    wave_path: Path,
    wave: dict,
    run_git: Callable[..., subprocess.CompletedProcess],
) -> dict | None:
    """Fast-forward and migrate a converged assembly, returning the refreshed
    wave dict with status "done" - or None when `repo` has moved past
    `wave["base_sha"]` since assembly (refuses rather than merge over new
    history)."""
    branch = f"wave/{wave['id']}/assembly"
    repo_head = run_git(["-C", str(repo), "rev-parse", "HEAD"]).stdout.strip()
    assembly_tip = run_git(["-C", str(repo), "rev-parse", branch]).stdout.strip()
    if repo_head not in (wave["base_sha"], assembly_tip):
        return None

    _land_merge(repo, assembly_tip, run_git)
    _land_migrate(repo, wave_path, wave)

    cycles = _cycle_count(Path(wave["assembly"]["worktree"]))
    _append_summary_line(
        repo,
        wave["id"],
        f"## Assembly review: converged ({cycles} cycle(s)), landed {assembly_tip}",
    )

    with locked(wave_path):
        wave = load(wave_path)
        wave["assembly"]["head_sha"] = assembly_tip
        wave["status"] = "done"
        save(wave_path, wave)
    return wave


def _review_file(worktree: Path, wave: dict) -> Path | None:
    """The stub's own `<stub-stem>-review-<n>.md` file in the assembly
    worktree's reviews/ folder: the highest-numbered one, or the most
    recently modified when numbering can't be compared numerically; None
    when no review file exists."""
    stem = _stub_name(wave).removesuffix(".md")
    prefix = f"{stem}-review-"
    matches = list(
        (worktree / "docs/dev/project-management/reviews").glob(f"{prefix}*.md"),
    )
    if not matches:
        return None
    suffixes = [path.name[len(prefix) : -len(".md")] for path in matches]
    if all(suffix.isdigit() for suffix in suffixes):
        return max(matches, key=lambda path: int(path.name[len(prefix) : -len(".md")]))
    return max(matches, key=lambda path: path.stat().st_mtime)


def _land_review_failed(repo: Path, wave: dict) -> int:
    """Record a review_failed wave's outcome (summary line + operator
    message) and return the "nothing to land" exit code, 4."""
    review_file = _review_file(Path(wave["assembly"]["worktree"]), wave)
    line = (
        f"## Assembly review: review_failed, see {review_file}"
        if review_file is not None
        else "## Assembly review: review_failed, see no review file written"
    )
    _append_summary_line(repo, wave["id"], line)
    print(f"autopilot: {line}", file=sys.stderr)
    return 4


def land(
    repo: Path,
    wave: dict,
    *,
    run_git: Callable[..., subprocess.CompletedProcess] = _default_run_git,
) -> int:
    """Land a converged assembly: migrate its worktree's records into `repo`
    as lane "assembly", fast-forward `repo`'s checked-out branch to the
    assembly branch's tip, append the outcome to the wave's report and
    ledger, save status "done" and the refreshed head_sha, then drop the
    worktree, branch and wave-slots and archive wave.json into reports/. A
    wave already at "done" (a retry after a crash between that save and the
    destructive cleanup) resumes at the cleanup step only. Returns 4 when the
    wave failed review (nothing to land, but the outcome is still recorded)
    and 5 when `repo` has moved past `wave["base_sha"]` since assembly
    (refuses rather than merge over new history); raises ValueError when the
    wave was never reviewed, or when the assembly worktree holds uncommitted
    changes at removal time."""
    wave_path = repo / "docs/dev/project-management/autopilot/wave.json"
    with locked(wave_path):
        wave = load(wave_path)

    if not _is_basename(wave.get("id")):
        raise ValueError("wave.json: malformed top-level field id")

    status = wave.get("status")
    if status == "review_failed":
        return _land_review_failed(repo, wave)
    if status not in ("converged", "done"):
        raise ValueError(f"wave status {status!r} is not landable")

    if status == "converged":
        updated = _land_converged(repo, wave_path, wave, run_git)
        if updated is None:
            print(
                f"autopilot: repo has moved past base_sha {wave['base_sha']!r}"
                " since assembly; nothing landed",
                file=sys.stderr,
            )
            return 5
        wave = updated

    _land_cleanup(repo, wave_path, wave, run_git)
    return 0
