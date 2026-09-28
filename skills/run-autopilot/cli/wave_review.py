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
from collections.abc import Callable
from pathlib import Path

from cli import wave_assemble
from cli.wave import WAVE_APPEND_ONLY, load, locked, save
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
        "Inputs/Outputs/Behavior:",
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
    installed = json.loads(plugins_json.read_text(encoding="utf-8"))
    return {
        "id": wave["id"],
        "mode": "autopilot",
        "completed_prds": [],
        "plugin_versions": {
            name: installed["plugins"][name][0]["version"] for name in _PINNED_PLUGINS
        },
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


def seed_state(
    state_path: Path,
    wave: dict,
    plugins_json: Path,
    run_cli: Callable[[list[str]], subprocess.CompletedProcess] = _run_cli,
) -> None:
    """Seed `state_path` as a build whose tasks are done (next phase: review)
    for the assembly stub PRD, written into prds/wip/. Raises RuntimeError on
    a failed step; a retry skips init once state.json exists."""
    pm = state_path.parent.parent
    state_path.parent.mkdir(parents=True, exist_ok=True)
    stub = _seed_prd(pm, wave)
    batch = _seed_batch(plugins_json, wave)
    for argv in _seed_steps(state_path, wave, stub, batch):
        result = run_cli(argv)
        if result.returncode != 0:
            raise RuntimeError(
                f"seed step `{' '.join(argv[2:])}` exited {result.returncode}:"
                f" {result.stderr.strip()}",
            )


def _check_reviewable(repo: Path, wave: dict) -> Path:
    """The assembly worktree; ValueError when the wave is not assembled, the
    worktree is gone, or `repo` has any uncommitted change."""
    if "assembly" not in wave:
        raise ValueError("wave has no assembly - run `wave assemble` first")
    if wave.get("status") not in ("assembled", "assembled_partial"):
        raise ValueError(f"wave status {wave.get('status')!r} is not reviewable")
    worktree = Path(wave["assembly"]["worktree"])
    if not worktree.is_dir():
        raise ValueError(f"assembly worktree {worktree} is gone")
    dirty = subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    if dirty:
        raise ValueError(f"{repo} has uncommitted changes:\n{dirty}")
    return worktree


def review(
    repo: Path,
    wave: dict,
    spawn_fn: Callable[..., subprocess.Popen] = subprocess.Popen,
) -> str:
    """Review the assembly: seed its worktree at review, run one loop there to
    exit, and record the outcome in wave.json - converged when the stub PRD
    ends in done/, review_failed when it ends in hold/ or stays in wip/."""
    worktree = _check_reviewable(repo, wave)
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
    meta = repo / "docs/dev/project-management/meta"
    if meta.exists():
        shutil.copytree(meta, pm / "meta", dirs_exist_ok=True)

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


def land(
    repo: Path,
    wave: dict,
    *,
    run_git: Callable[..., subprocess.CompletedProcess] = _default_run_git,
) -> int:
    """Land a converged assembly: migrate its worktree's records into `repo`
    as lane "assembly", fast-forward `repo`'s checked-out branch to the
    assembly branch's tip, then drop the worktree and branch. Returns 4 when
    the wave failed review (nothing to land) and 5 when `repo` has moved past
    `wave["base_sha"]` since assembly (refuses rather than merge over new
    history); raises ValueError when the wave was never reviewed."""
    wave_path = repo / "docs/dev/project-management/autopilot/wave.json"
    with locked(wave_path):
        wave = load(wave_path)

    status = wave.get("status")
    if status == "review_failed":
        return 4
    if status != "converged":
        raise ValueError(f"wave status {status!r} is not landable")

    worktree = Path(wave["assembly"]["worktree"])
    repo_head = run_git(["-C", str(repo), "rev-parse", "HEAD"]).stdout.strip()
    resolved_assembly_tip = (
        run_git(["-C", str(worktree), "rev-parse", "HEAD"]).stdout.strip()
        if worktree.is_dir()
        else repo_head
    )
    if repo_head not in (wave["base_sha"], resolved_assembly_tip):
        return 5

    _land_merge(repo, resolved_assembly_tip, run_git)
    _land_migrate(repo, wave_path, wave)

    run_git(["-C", str(repo), "worktree", "remove", "--force", str(worktree)])
    run_git(["-C", str(repo), "branch", "-d", f"wave/{wave['id']}/assembly"])

    with locked(wave_path):
        current = load(wave_path)
        current["assembly"]["head_sha"] = resolved_assembly_tip
        current["status"] = "done"
        save(wave_path, current)

    reports_dir = repo / "docs/dev/project-management/autopilot/reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    save(reports_dir / f"{wave['id']}-wave.json", current)

    return 0
