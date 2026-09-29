#!/usr/bin/env python3
"""Tests for cli/wave_review.py - stub_text, review_paths, seed_state, review.

`stub_text` and `review_paths` are pure: they render the assembly stub PRD
body and compute its diff-scope path list from an already-assembled wave dict
(`wave.json` after `wave_assemble.assemble` has populated `wave["assembly"]`),
never touching git, disk, or a PRD file.

`seed_state` and `review` run against a throwaway `git init` repo under
`tmp_path` with a real assembly worktree checked out beside it. The seed's
CLI calls run for real; no loop is ever started - a recording `spawn_fn`
stands in for one, and its `wait()` plays the loop's effect on the worktree.
HOME is moved under `tmp_path` so review()'s own installed_plugins.json read
lands on a fixture.

The `test_run_*` tests below exercise `wave_run.run` (cli/wave_run.py, not
yet implemented - they fail with ImportError/AttributeError until it lands,
which is expected). `test_docs_name_the_exit_codes`,
`test_wave_statuses_include_converged_and_review_failed`, and
`test_wave_cli_registers_review_land_run_as_wave_subverbs` pin the doc,
wave.py, and wave_cli.py sides of the same feature.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import shutil
import signal
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from cli import (
    frontmatter,
    loop_decision,
    schema,
    wave,
    wave_assemble,
    wave_cli,
    wave_launch,
    wave_review,
    wave_run,
)
from cli.test_wave_assemble import _launched
from cli.test_wave_launch import _autopilot, _git, _repo


def _lane(name: str, prds: list[str], files: list[str] | None = None) -> dict:
    """A minimal lane entry: `files` omitted entirely when not given, so a
    lane that never recorded it is exercised the way assemble() leaves one."""
    lane = {"name": name, "prds": prds}
    if files is not None:
        lane["files"] = files
    return lane


def _wave(**overrides: object) -> dict:
    """A wave whose assembly merged both lanes l1 and l2, in order."""
    base = {
        "id": "202609281200",
        "base_sha": "1111111",
        "assembly": {"head_sha": "2222222", "merged": ["l1", "l2"]},
        "lanes": [
            _lane("l1", ["00001-a.md"], files=["cli/records.py", "cli/x.py"]),
            _lane("l2", ["00002-b.md", "00003-c.md"], files=["cli/records.py"]),
        ],
    }
    base.update(overrides)
    return base


# ── stub_text ────────────────────────────────────────────────────────────


def test_stub_prd_names_every_merged_lane_and_the_range() -> None:
    text = wave_review.stub_text(_wave())
    lines = text.splitlines()
    assert "- l1 (00001-a.md)" in lines
    assert "- l2 (00002-b.md, 00003-c.md)" in lines
    assert "Diff range: 1111111..2222222" in lines


def test_stub_prd_carries_the_headings_plan_tasks_parses() -> None:
    text = wave_review.stub_text(_wave())
    assert "#### Feature: Lane merges" in text
    assert "### Phase 0: Assembly" in text
    lines = text.splitlines()
    assert (
        "- [x] Merge lane l1 (00001-a.md) - Acceptance: release-checks green" in lines
    )
    assert (
        "- [x] Merge lane l2 (00002-b.md, 00003-c.md) - Acceptance: release-checks green"
        in lines
    )


def test_stub_frontmatter_is_the_five_pairs() -> None:
    text = wave_review.stub_text(_wave())
    assert frontmatter.declared(text) == {
        "catchup": "skip",
        "design": "skip",
        "rework_cap": "2",
        "default_model": "sonnet",
        "model_tier_rationale": (
            "fixes to conflict resolutions and lane interactions found by the"
            " assembly review"
        ),
    }
    _, warnings = frontmatter.parse(text)
    assert warnings == []


def test_stub_prd_lists_the_diff_scope() -> None:
    wave_dict = _wave()
    text = wave_review.stub_text(wave_dict)
    assert "Diff scope:" in text
    lines = text.splitlines()
    for path in wave_review.review_paths(wave_dict):
        # The exact bullet styling is not pinned, only that each path gets
        # its own line rather than being folded into one comma list.
        assert path in lines or f"- {path}" in lines, (path, text)


def test_stub_text_raises_without_an_assembly() -> None:
    wave_dict = _wave()
    del wave_dict["assembly"]
    with pytest.raises(ValueError):
        wave_review.stub_text(wave_dict)


# ── review_paths ─────────────────────────────────────────────────────────


def test_review_paths_are_the_multi_lane_files_plus_append_only() -> None:
    wave_dict = _wave(
        assembly={"head_sha": "2222222", "merged": ["l1"]},
        lanes=[
            _lane("l1", ["00001-a.md"], files=["cli/records.py", "cli/x.py"]),
            # l2 could not merge (conflict/checks_failed) but still counts.
            _lane("l2", ["00002-b.md"], files=["cli/records.py"]),
            # l3 never recorded a files list at all.
            _lane("l3", ["00003-c.md"]),
        ],
    )
    assert wave_review.review_paths(wave_dict) == [
        "CHANGELOG.md",
        "cli/records.py",
        "dev/bin/release-checks",
    ]


# ── seed_state / review: fixtures ────────────────────────────────────────

CLI_MAIN = Path(__file__).resolve().parent / "__main__.py"
STATECTL = Path(__file__).resolve().parent.parent / "scripts" / "statectl.py"
SPAWN_CMD = 'export _AUTOPILOT_LOOP=$$; exec python3 "$0" loop'
WAVE_ID = "202609281200"
STUB = f"{WAVE_ID}-wave-assembly-v1.md"
PINS = {"aegis@buvis-plugins": "0.3.2", "warden@buvis-plugins": "1.4.0"}


def _entry(name: str, version: str) -> list[dict]:
    """One plugin's installed_plugins.json value: a list whose [0] is live."""
    return [
        {
            "scope": "user",
            "installPath": f"/plugins/cache/{name}/{version}",
            "version": version,
            "installedAt": "2026-09-01T00:00:00.000Z",
            "lastUpdated": "2026-09-20T00:00:00.000Z",
            "gitCommitSha": "0123456789abcdef0123456789abcdef01234567",
        },
    ]


INSTALLED = {
    "version": 2,
    "plugins": {
        "aegis@buvis-plugins": _entry("aegis", "0.3.2"),
        "warden@buvis-plugins": _entry("warden", "1.4.0"),
        "loupe@buvis-plugins": _entry("loupe", "2.0.1"),
        "some-other-plugin@some-marketplace": _entry("some-other-plugin", "9.9.9"),
    },
}


def _pm(root: Path) -> Path:
    return root / "docs" / "dev" / "project-management"


def _plugins_json(tmp_path: Path) -> Path:
    return tmp_path / "home" / ".claude" / "plugins" / "installed_plugins.json"


def _full_lane(tmp_path: Path, name: str, prds: list[str], files: list[str]) -> dict:
    """A lane as wave.json holds it after assembly: every key `wave status` reads."""
    return {
        **_lane(name, prds, files=files),
        "pid": None,
        "status": "drained",
        "worktree": str(tmp_path / f"proj-wave-{name}"),
        "abort_error": None,
    }


def _assembled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    status: str = "assembled",
) -> tuple[Path, Path, dict]:
    """A committed repo whose saved wave is `status`, its assembly worktree
    checked out beside it, a meta/ note in the main checkout, HOME moved onto
    an installed_plugins.json fixture, and the process cwd moved off the repo:
    (repo, wave.json path, wave)."""
    repo, wave_path = _repo(tmp_path, {})
    worktree = (tmp_path / f"proj-wave-{WAVE_ID}").resolve()
    _git(repo, "worktree", "add", "-q", str(worktree), "-b", f"wave/{WAVE_ID}/assembly")
    (_pm(repo) / "meta").mkdir(parents=True)
    (_pm(repo) / "meta" / "goals.md").write_text("ship waves\n", encoding="utf-8")
    _plugins_json(tmp_path).parent.mkdir(parents=True)
    _plugins_json(tmp_path).write_text(json.dumps(INSTALLED), encoding="utf-8")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.chdir(tmp_path)
    wave_dict = _wave(
        status=status,
        assembly={
            "worktree": str(worktree),
            "head_sha": "2222222",
            "merged": ["l1", "l2"],
        },
        lanes=[
            _full_lane(tmp_path, "l1", ["00001-a.md"], ["cli/records.py", "cli/x.py"]),
            _full_lane(
                tmp_path,
                "l2",
                ["00002-b.md", "00003-c.md"],
                ["cli/records.py"],
            ),
        ],
    )
    wave.save(wave_path, wave_dict)
    return repo, wave_path, wave_dict


def _recording_cli(
    calls: list[list[str]],
) -> Callable[[list[str]], subprocess.CompletedProcess]:
    """A `run_cli` that records each argv, then runs it for real."""

    def run_cli(argv: list[str]) -> subprocess.CompletedProcess:
        calls.append(list(argv))
        return subprocess.run(argv, capture_output=True, text=True, check=False)

    return run_cli


def _normalized(argv: list[str]) -> list[object]:
    """argv with its script path resolved and, for a statectl call, its JSON
    value decoded: the check pins the value, not json.dumps's spacing."""
    shown: list[object] = [argv[0], Path(argv[1]).resolve(), *argv[2:]]
    if shown[1] == STATECTL:
        shown[-1] = json.loads(argv[-1])
    return shown


def _seed_argv(
    state_path: Path,
    wave_id: str = WAVE_ID,
    base_sha: str = "1111111",
) -> list[list[object]]:
    """The six seed calls, in order, as `_normalized` shows them."""
    state = str(state_path)
    batch = {
        "id": wave_id,
        "mode": "autopilot",
        "completed_prds": [],
        "plugin_versions": PINS,
    }
    return [
        [
            "python3",
            CLI_MAIN,
            "init",
            "--state",
            state,
            "--prd",
            f"{wave_id}-wave-assembly-v1.md",
        ],
        ["python3", STATECTL, state, "set", "work_start_sha", base_sha],
        ["python3", STATECTL, state, "set", "cycle", 1],
        ["python3", STATECTL, state, "set", "rework_cap", 2],
        ["python3", STATECTL, state, "set", "batch", batch],
        [
            "python3",
            CLI_MAIN,
            "phase-done",
            "--state",
            state,
            "--outcome",
            "tasks_done",
        ],
    ]


class _Loop:
    """A spawned loop not yet waited on: wait() plays `effect` (the loop's
    work on the assembly worktree), then reports `exit_code`."""

    def __init__(self, effect: Callable[[], None], exit_code: int) -> None:
        self.pid = 4242
        self.returncode: int | None = None
        self._effect = effect
        self._exit_code = exit_code

    def wait(self, timeout: float | None = None) -> int:
        if self.returncode is None:
            self._effect()
            self.returncode = self._exit_code
        return self.returncode


class _FakeLoop:
    """Stands in for subprocess.Popen: records the spawn, starts nothing."""

    def __init__(
        self,
        effect: Callable[[], None] = lambda: None,
        exit_code: int = 0,
    ) -> None:
        self.calls: list[dict] = []
        self._effect = effect
        self._exit_code = exit_code

    def __call__(self, cmd: list[str], **kwargs: object) -> _Loop:
        self.calls.append({"cmd": list(cmd), **kwargs})
        return _Loop(self._effect, self._exit_code)


def _moving(worktree: Path, dest: str | None) -> Callable[[], None]:
    """The loop's effect: the seeded stub, already in wip/, ends in `dest`
    (None: the loop died with it still in wip/)."""

    def move() -> None:
        wip = _pm(worktree) / "prds" / "wip" / STUB
        assert wip.exists(), "the seed must put the stub in wip/ before the loop runs"
        if dest is not None:
            shutil.move(str(wip), str(_pm(worktree) / "prds" / dest / STUB))

    return move


# ── seed_state ───────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("wave_id", "base_sha"),
    [(WAVE_ID, "1111111"), ("202610051530", "9f8e7d6")],
    ids=["usual-wave", "other-wave"],
)
def test_seeded_state_is_the_tasks_done_shape(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    wave_id: str,
    base_sha: str,
) -> None:
    _, _, wave_dict = _assembled(tmp_path, monkeypatch)
    wave_dict = {**wave_dict, "id": wave_id, "base_sha": base_sha}
    stub_name = f"{wave_id}-wave-assembly-v1.md"
    worktree = Path(wave_dict["assembly"]["worktree"])
    state_path = _autopilot(worktree) / "state.json"
    calls: list[list[str]] = []
    wave_review.seed_state(
        state_path,
        wave_dict,
        _plugins_json(tmp_path),
        run_cli=_recording_cli(calls),
    )
    state = json.loads(state_path.read_text(encoding="utf-8"))
    schema.validate(state)
    assert (state["phase"], state["next_phase"]) == ("review", "review")
    assert state["prd"] == stub_name
    assert state["work_start_sha"] == base_sha
    assert (state["cycle"], state["rework_cap"]) == (1, 2)
    assert state["batch"]["id"] == wave_id
    assert state["batch"]["plugin_versions"] == PINS
    assert not state.get("phases_completed")
    # Every step, in order: the last write is phase-done --outcome tasks_done.
    assert [_normalized(argv) for argv in calls] == _seed_argv(
        state_path,
        wave_id,
        base_sha,
    )
    for folder in ("backlog", "wip", "done", "hold"):
        assert (_pm(worktree) / "prds" / folder).is_dir(), folder
    stub = _pm(worktree) / "prds" / "wip" / stub_name
    assert stub.read_text(encoding="utf-8") == wave_review.stub_text(wave_dict)
    assert [path.name for path in (_pm(worktree) / "prds").rglob("*.md")] == [stub_name]


@pytest.mark.parametrize(
    ("aegis", "warden"),
    [("0.3.2", "1.4.0"), ("5.0.7", "2.11.3")],
    ids=["usual", "bumped"],
)
def test_seed_state_extracts_only_the_two_pinned_plugin_versions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    aegis: str,
    warden: str,
) -> None:
    _, _, wave_dict = _assembled(tmp_path, monkeypatch)
    plugins = {
        **INSTALLED["plugins"],
        "aegis@buvis-plugins": _entry("aegis", aegis),
        "warden@buvis-plugins": _entry("warden", warden),
    }
    _plugins_json(tmp_path).write_text(
        json.dumps({**INSTALLED, "plugins": plugins}),
        encoding="utf-8",
    )
    state_path = _autopilot(Path(wave_dict["assembly"]["worktree"])) / "state.json"
    wave_review.seed_state(state_path, wave_dict, _plugins_json(tmp_path))
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["batch"]["plugin_versions"] == {
        "aegis@buvis-plugins": aegis,
        "warden@buvis-plugins": warden,
    }
    installed = json.loads(_plugins_json(tmp_path).read_text(encoding="utf-8"))
    assert loop_decision.plugin_drift(state, installed) is None


def test_seed_state_raises_on_a_failed_step_and_a_retry_resumes_past_init(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, wave_dict = _assembled(tmp_path, monkeypatch)
    state_path = _autopilot(Path(wave_dict["assembly"]["worktree"])) / "state.json"
    real = _recording_cli([])

    def dies_at_cycle(argv: list[str]) -> subprocess.CompletedProcess:
        if "cycle" in argv:
            return subprocess.CompletedProcess(argv, 1, "", "disk went away")
        return real(argv)

    with pytest.raises(RuntimeError) as raised:
        wave_review.seed_state(
            state_path,
            wave_dict,
            _plugins_json(tmp_path),
            run_cli=dies_at_cycle,
        )
    assert "cycle" in str(raised.value)
    assert "disk went away" in str(raised.value)
    assert state_path.exists()
    retry: list[list[str]] = []
    wave_review.seed_state(
        state_path,
        wave_dict,
        _plugins_json(tmp_path),
        run_cli=_recording_cli(retry),
    )
    # init would exit 7 on the existing state.json: the retry picks up after it.
    assert [_normalized(argv) for argv in retry] == _seed_argv(state_path)[1:]
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert (state["phase"], state["next_phase"], state["cycle"]) == (
        "review",
        "review",
        1,
    )


# ── review ───────────────────────────────────────────────────────────────


def test_review_writes_review_paths_in_the_assembly_worktree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, _, wave_dict = _assembled(tmp_path, monkeypatch)
    worktree = Path(wave_dict["assembly"]["worktree"])
    wave_review.review(repo, wave_dict, spawn_fn=_FakeLoop(_moving(worktree, "done")))
    text = (_autopilot(worktree) / "review-paths").read_text(encoding="utf-8")
    assert text == "".join(f"{path}\n" for path in wave_review.review_paths(wave_dict))
    assert text.splitlines() == [
        "CHANGELOG.md",
        "cli/records.py",
        "dev/bin/release-checks",
    ]
    assert not (_autopilot(repo) / "review-paths").exists()


def test_review_copies_meta_and_spawns_the_loop_in_the_assembly_worktree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, _, wave_dict = _assembled(tmp_path, monkeypatch)
    worktree = Path(wave_dict["assembly"]["worktree"])
    # Set as an outer lane would have them: they must not reach the one
    # assembly-review session, which never contends for the lane semaphore.
    monkeypatch.setenv("_AUTOPILOT_REVIEW_SLOTS_DIR", str(tmp_path / "wave-slots"))
    monkeypatch.setenv("_AUTOPILOT_REVIEW_SLOTS", "3")
    seen: dict[str, str] = {}

    def loop() -> None:
        state = json.loads(
            (_autopilot(worktree) / "state.json").read_text(encoding="utf-8"),
        )
        seen["next_phase"] = state["next_phase"]
        _moving(worktree, "done")()

    spawn = _FakeLoop(loop)
    wave_review.review(repo, wave_dict, spawn_fn=spawn)
    assert (_pm(worktree) / "meta" / "goals.md").read_text(
        encoding="utf-8",
    ) == "ship waves\n"
    assert seen["next_phase"] == "review"  # seeded before the loop started
    [call] = spawn.calls
    assert call["cmd"] == ["bash", "-c", SPAWN_CMD, str(CLI_MAIN)]
    assert Path(call["cwd"]).resolve() == worktree
    assert call["start_new_session"] is True
    assert "_AUTOPILOT_REVIEW_SLOTS_DIR" not in call["env"]
    assert "_AUTOPILOT_REVIEW_SLOTS" not in call["env"]
    assert call["env"]["_AUTOPILOT_TRACON_CHILD"] == "1"
    assert call["env"]["PATH"] == os.environ["PATH"]
    wrapper_log = _autopilot(worktree) / "wrapper.log"
    assert Path(call["stdout"].name).resolve() == wrapper_log.resolve()


@pytest.mark.parametrize(
    ("status", "dest", "exit_code", "outcome"),
    [
        ("assembled", "done", 0, "converged"),
        ("assembled_partial", "hold", 0, "review_failed"),
        ("assembled", None, 1, "review_failed"),
        # The folder decides, not the exit code or the pre-review status.
        ("assembled", "hold", 0, "review_failed"),
        ("assembled_partial", "done", 0, "converged"),
        ("assembled", "done", 1, "converged"),
        ("assembled", None, 0, "review_failed"),
    ],
    ids=[
        "done-converges",
        "hold-fails",
        "died-in-wip-fails",
        "hold-after-full-assembly-fails",
        "done-after-partial-assembly-converges",
        "done-despite-nonzero-exit-converges",
        "clean-exit-still-in-wip-fails",
    ],
)
def test_review_outcome_reads_done_and_hold(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    status: str,
    dest: str | None,
    exit_code: int,
    outcome: str,
) -> None:
    repo, wave_path, wave_dict = _assembled(tmp_path, monkeypatch, status=status)
    worktree = Path(wave_dict["assembly"]["worktree"])
    before = json.loads(wave_path.read_text(encoding="utf-8"))
    spawn = _FakeLoop(_moving(worktree, dest), exit_code)
    assert wave_review.review(repo, wave_dict, spawn_fn=spawn) == outcome
    saved = wave.load(wave_path)
    assert saved["status"] == outcome
    assert {**saved, "status": status} == before


@pytest.mark.parametrize(
    "gap",
    ["not_assembled", "worktree_gone", "repo_dirty", "tracked_file_edited"],
)
def test_review_refuses_before_assembly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    gap: str,
) -> None:
    repo, wave_path, wave_dict = _assembled(tmp_path, monkeypatch)
    worktree = Path(wave_dict["assembly"]["worktree"])
    if gap == "not_assembled":
        # Lanes still running: assemble() has not written `assembly` yet.
        wave_dict = {
            **{key: value for key, value in wave_dict.items() if key != "assembly"},
            "status": "running",
        }
        wave.save(wave_path, wave_dict)
    elif gap == "worktree_gone":
        _git(repo, "worktree", "remove", "--force", str(worktree))
    elif gap == "repo_dirty":
        (repo / "stray.py").write_text("x = 1\n", encoding="utf-8")
    else:
        # No new file: only an uncommitted edit to the tracked README.md.
        with (repo / "README.md").open("a", encoding="utf-8") as readme:
            readme.write("uncommitted line\n")
    before = wave_path.read_text(encoding="utf-8")
    spawn = _FakeLoop()
    with pytest.raises(ValueError):
        wave_review.review(repo, wave_dict, spawn_fn=spawn)
    assert spawn.calls == []
    assert wave_path.read_text(encoding="utf-8") == before
    assert not (_autopilot(worktree) / "state.json").exists()
    assert not (_autopilot(worktree) / "review-paths").exists()


def test_review_releases_the_lock_during_the_wait(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path, wave_dict = _assembled(tmp_path, monkeypatch)
    worktree = Path(wave_dict["assembly"]["worktree"])
    seen: dict[str, str] = {}

    def loop() -> None:
        with open(f"{wave_path}.lock", "a") as lock:
            try:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                pytest.fail("review() held wave.json's lock across the loop's wait")
            seen["status"] = wave_launch.status(repo, wave.load(wave_path))
            # A concurrent writer's change, made under the lock mid-review.
            current = wave.load(wave_path)
            current["lanes"][1]["abort_error"] = "written mid-review"
            wave.save(wave_path, current)
        _moving(worktree, "done")()

    assert wave_review.review(repo, wave_dict, spawn_fn=_FakeLoop(loop)) == "converged"
    assert [row.split()[0] for row in seen["status"].splitlines()] == [
        "lane",
        "l1",
        "l2",
    ]
    saved = wave.load(wave_path)
    assert saved["status"] == "converged"
    # Reloaded fresh under the lock, not saved from the caller's stale copy.
    assert saved["lanes"][1]["abort_error"] == "written mid-review"


# ── land ─────────────────────────────────────────────────────────────────


def _git_out(cwd: Path, *args: str) -> str:
    """`git <args>` run inside `cwd`, stdout stripped - the existing `_git`
    helper never returns anything, so a land() test that needs the real
    output (a rev-parse, a commit count) shells out itself."""
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _branch_exists(repo: Path, branch: str) -> bool:
    return bool(_git_out(repo, "branch", "--list", branch))


def _landable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    status: str = "converged",
) -> tuple[Path, Path, dict]:
    """`_assembled`, plus a real `base_sha` (the repo's actual HEAD, not
    `_wave`'s placeholder "1111111") and one commit on the assembly branch
    that both lands the stub PRD in the worktree's `prds/done/` (what a
    converged review leaves behind) and gives the branch a real, current tip
    ahead of the stale "2222222" `_wave` records in `assembly.head_sha` (the
    rework-since-assemble() commit `land`'s own head-sha refresh must see)."""
    repo, wave_path, wave_dict = _assembled(tmp_path, monkeypatch, status=status)
    worktree = Path(wave_dict["assembly"]["worktree"])
    base_sha = _git_out(repo, "rev-parse", "HEAD")
    stub = _pm(worktree) / "prds" / "done" / STUB
    stub.parent.mkdir(parents=True, exist_ok=True)
    stub.write_text("stub prd\n", encoding="utf-8")
    # `_assembled` already redirected HOME to a fixture dir with no
    # .gitconfig, so a real commit here needs its own identity.
    _git(worktree, "config", "user.email", "wave-test@example.com")
    _git(worktree, "config", "user.name", "Wave Test")
    # docs/dev/tmp/ is gitignored in this fixture repo (see
    # `_check_reviewable`'s dirty-check tests), so the stub needs --force.
    _git(worktree, "add", "--force", str(stub))
    _git(worktree, "commit", "-m", "test: complete assembly review")
    _autopilot(worktree).mkdir(parents=True, exist_ok=True)
    (_autopilot(worktree) / "state.json").write_text(
        json.dumps({"cycle": 1}),
        encoding="utf-8",
    )
    wave_dict = {**wave_dict, "base_sha": base_sha}
    wave.save(wave_path, wave_dict)
    return repo, wave_path, wave_dict


def test_land_fast_forwards_master_and_removes_the_worktree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, _, wave_dict = _landable(tmp_path, monkeypatch)
    worktree = Path(wave_dict["assembly"]["worktree"])
    assembly_tip = _git_out(worktree, "rev-parse", "HEAD")
    assert wave_review.land(repo, wave_dict) == 0
    assert _git_out(repo, "rev-parse", "HEAD") == assembly_tip
    assert not worktree.exists()
    assert not _branch_exists(repo, f"wave/{WAVE_ID}/assembly")


def test_land_migrates_the_assembly_artifacts_as_lane_assembly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, _, wave_dict = _landable(tmp_path, monkeypatch)
    worktree = Path(wave_dict["assembly"]["worktree"])
    (_autopilot(worktree) / "loop-metrics.jsonl").write_text(
        json.dumps({"event": "cycle_done"}) + "\n",
        encoding="utf-8",
    )
    assert wave_review.land(repo, wave_dict) == 0
    lines = (
        (_autopilot(repo) / "loop-metrics.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    [row] = [json.loads(line) for line in lines]
    assert row == {"event": "cycle_done", "lane": "assembly", "wave": WAVE_ID}


def test_land_refuses_when_master_moved(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path, wave_dict = _landable(tmp_path, monkeypatch)
    worktree = Path(wave_dict["assembly"]["worktree"])
    (repo / "unrelated.txt").write_text("x\n", encoding="utf-8")
    _git(repo, "add", "unrelated.txt")
    _git(repo, "commit", "-m", "test: land unrelated work on master meanwhile")
    before = _git_out(repo, "rev-list", "--count", "HEAD")
    assert wave_review.land(repo, wave_dict) == 5
    assert _git_out(repo, "rev-list", "--count", "HEAD") == before
    assert worktree.exists()
    assert wave.load(wave_path)["status"] == "converged"


def test_review_failed_keeps_master_untouched(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path, wave_dict = _landable(
        tmp_path,
        monkeypatch,
        status="review_failed",
    )
    worktree = Path(wave_dict["assembly"]["worktree"])
    before = _git_out(repo, "rev-list", "--count", "HEAD")
    assert wave_review.land(repo, wave_dict) == 4
    assert _git_out(repo, "rev-list", "--count", "HEAD") == before
    assert worktree.exists()
    assert _branch_exists(repo, f"wave/{WAVE_ID}/assembly")
    assert wave.load(wave_path)["status"] == "review_failed"


def test_land_precondition_rejects_assembled_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path, wave_dict = _assembled(tmp_path, monkeypatch, status="assembled")
    with pytest.raises(ValueError):
        wave_review.land(repo, wave_dict)
    assert wave.load(wave_path)["status"] == "assembled"


def test_land_resumes_after_a_migration_crash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path, wave_dict = _landable(tmp_path, monkeypatch)
    worktree = Path(wave_dict["assembly"]["worktree"])
    ledger = _autopilot(repo) / "loop-metrics.jsonl"
    (_autopilot(worktree) / "loop-metrics.jsonl").write_text(
        json.dumps({"event": "cycle_done"}) + "\n",
        encoding="utf-8",
    )
    real_migrate_lane = wave_assemble.migrate_lane
    calls = {"n": 0}

    def crashes_once(main: Path, wave_id: str, lane: dict) -> None:
        real_migrate_lane(main, wave_id, lane)
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("simulated crash after migration")

    monkeypatch.setattr(wave_assemble, "migrate_lane", crashes_once)
    with pytest.raises(RuntimeError, match="simulated crash after migration"):
        wave_review.land(repo, wave_dict)

    saved = wave.load(wave_path)
    assert saved["status"] == "converged"
    assert saved["assembly"].get("migrated_at")
    assert worktree.exists()
    assert ledger.read_text(encoding="utf-8").count("cycle_done") == 1
    assert (_pm(repo) / "prds" / "done" / STUB).exists()

    monkeypatch.setattr(wave_assemble, "migrate_lane", real_migrate_lane)
    assert wave_review.land(repo, wave_dict) == 0
    # A successful land moves wave.json to reports/ rather than leaving it
    # readable at wave_path (task 7: "move, not copy" - see
    # test_land_removes_wave_slots_and_moves_wave_json_to_reports).
    assert not wave_path.exists()
    archived = json.loads(
        (_autopilot(repo) / "reports" / f"{WAVE_ID}-wave.json").read_text(
            encoding="utf-8",
        ),
    )
    assert archived["status"] == "done"
    assert ledger.read_text(encoding="utf-8").count("cycle_done") == 1
    assert not worktree.exists()


def test_land_refreshes_the_archived_head_sha(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, _, wave_dict = _landable(tmp_path, monkeypatch)
    worktree = Path(wave_dict["assembly"]["worktree"])
    actual_tip = _git_out(worktree, "rev-parse", "HEAD")
    assert wave_dict["assembly"]["head_sha"] != actual_tip
    assert wave_review.land(repo, wave_dict) == 0
    archived = json.loads(
        (_autopilot(repo) / "reports" / f"{WAVE_ID}-wave.json").read_text(
            encoding="utf-8",
        ),
    )
    assert archived["assembly"]["head_sha"] == actual_tip


def test_land_appends_the_converged_summary_line(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, _, wave_dict = _landable(tmp_path, monkeypatch)
    worktree = Path(wave_dict["assembly"]["worktree"])
    assembly_tip = _git_out(worktree, "rev-parse", "HEAD")

    assert wave_review.land(repo, wave_dict) == 0

    expected_line = f"## Assembly review: converged (1 cycle(s)), landed {assembly_tip}"
    for folder in ("reports", "ledger"):
        text = (_autopilot(repo) / folder / f"{WAVE_ID}-wave.md").read_text(
            encoding="utf-8",
        )
        assert text.count("## Assembly review:") == 1
        assert expected_line in text.splitlines()


def test_review_failed_appends_the_summary_line_with_no_review_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path, wave_dict = _landable(
        tmp_path,
        monkeypatch,
        status="review_failed",
    )
    worktree = Path(wave_dict["assembly"]["worktree"])
    before = _git_out(repo, "rev-list", "--count", "HEAD")

    assert wave_review.land(repo, wave_dict) == 4

    assert _git_out(repo, "rev-list", "--count", "HEAD") == before
    assert worktree.exists()
    assert _branch_exists(repo, f"wave/{WAVE_ID}/assembly")
    assert wave.load(wave_path)["status"] == "review_failed"
    expected_line = "## Assembly review: review_failed, see no review file written"
    for folder in ("reports", "ledger"):
        text = (_autopilot(repo) / folder / f"{WAVE_ID}-wave.md").read_text(
            encoding="utf-8",
        )
        assert text.count("## Assembly review:") == 1
        assert expected_line in text.splitlines()


def test_land_resumes_after_a_crash_between_save_and_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The design saves status "done" and the refreshed head_sha BEFORE the
    destructive worktree/branch/wave-slots/wave.json cleanup, so a kill in
    between leaves status already "done" while the worktree, branch, and
    wave.json's own location are all still there - the retry must finish the
    leftover cleanup without redoing the merge/migrate/save and without
    duplicating the summary line."""
    repo, wave_path, wave_dict = _landable(tmp_path, monkeypatch)
    worktree = Path(wave_dict["assembly"]["worktree"])
    assembly_tip = _git_out(worktree, "rev-parse", "HEAD")
    real_run_git = wave_assemble._default_run_git

    def crashes_on_worktree_remove(
        argv: list[str],
        **kwargs: object,
    ) -> subprocess.CompletedProcess:
        if "worktree" in argv and "remove" in argv:
            raise RuntimeError("simulated crash before the destructive cleanup")
        return real_run_git(argv, **kwargs)

    with pytest.raises(
        RuntimeError,
        match="simulated crash before the destructive cleanup",
    ):
        wave_review.land(repo, wave_dict, run_git=crashes_on_worktree_remove)

    saved = wave.load(wave_path)
    assert saved["status"] == "done"
    assert saved["assembly"]["head_sha"] == assembly_tip
    assert worktree.exists()
    assert _branch_exists(repo, f"wave/{WAVE_ID}/assembly")
    report = (_autopilot(repo) / "reports" / f"{WAVE_ID}-wave.md").read_text(
        encoding="utf-8",
    )
    assert report.count("## Assembly review:") == 1

    assert wave_review.land(repo, saved) == 0

    assert not worktree.exists()
    assert not _branch_exists(repo, f"wave/{WAVE_ID}/assembly")
    assert not wave_path.exists()
    report_after = (_autopilot(repo) / "reports" / f"{WAVE_ID}-wave.md").read_text(
        encoding="utf-8",
    )
    assert report_after.count("## Assembly review:") == 1


def test_land_removes_wave_slots_and_moves_wave_json_to_reports(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path, wave_dict = _landable(tmp_path, monkeypatch)
    slots = _autopilot(repo) / "wave-slots"
    slots.mkdir(parents=True)
    (slots / "slot-0").write_text("held\n", encoding="utf-8")

    assert wave_review.land(repo, wave_dict) == 0

    assert not slots.exists()
    assert not wave_path.exists()
    assert (_autopilot(repo) / "reports" / f"{WAVE_ID}-wave.json").exists()


def test_land_refuses_when_master_moved_and_worktree_is_gone(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The guard must resolve the assembly branch's tip directly (it stays
    resolvable via the branch ref even once the worktree checkout is
    removed), not fall back to a substitute that makes "master moved" pass
    vacuously."""
    repo, wave_path, wave_dict = _landable(tmp_path, monkeypatch)
    worktree = Path(wave_dict["assembly"]["worktree"])
    assembly_branch = f"wave/{WAVE_ID}/assembly"
    _git(repo, "worktree", "remove", "--force", str(worktree))
    (repo / "unrelated.txt").write_text("x\n", encoding="utf-8")
    _git(repo, "add", "unrelated.txt")
    _git(repo, "commit", "-m", "test: land unrelated work while the worktree is gone")
    before = _git_out(repo, "rev-list", "--count", "HEAD")

    assert wave_review.land(repo, wave_dict) == 5

    assert _git_out(repo, "rev-list", "--count", "HEAD") == before
    assert _branch_exists(repo, assembly_branch)
    assert wave.load(wave_path)["status"] == "converged"


def test_land_refuses_to_discard_uncommitted_changes_in_the_assembly_worktree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The pre-removal dirty-check sits right before `git worktree remove
    --force`, after the merge and migrate have already landed and status has
    already advanced to "done" - it protects only the worktree itself from
    being discarded, not the earlier steps from completing."""
    repo, wave_path, wave_dict = _landable(tmp_path, monkeypatch)
    worktree = Path(wave_dict["assembly"]["worktree"])
    assembly_tip = _git_out(worktree, "rev-parse", "HEAD")
    (worktree / "dirty.txt").write_text("uncommitted rework\n", encoding="utf-8")

    with pytest.raises(ValueError):
        wave_review.land(repo, wave_dict)

    assert _git_out(repo, "rev-parse", "HEAD") == assembly_tip
    assert worktree.exists()
    assert (worktree / "dirty.txt").exists()
    assert _branch_exists(repo, f"wave/{WAVE_ID}/assembly")
    assert wave.load(wave_path)["status"] == "done"


# ── run ──────────────────────────────────────────────────────────────────


def _run_wave(wave_path: Path) -> None:
    """A wave.json valid enough for wave.load to parse. wave_run.run's own
    plan/launch/assemble/review/land calls are all faked in the tests below,
    so only the wait loop's own wave.load(wave_path) reload touches this
    file for real."""
    wave.save(
        wave_path,
        {
            "id": "202609281200",
            "base_sha": "1111111",
            "status": "planned",
            "lanes": [
                {
                    "name": "l1",
                    "prds": ["00001-a.md"],
                    "pid": 111,
                    "status": "running",
                    "worktree": None,
                    "abort_error": None,
                },
                {
                    "name": "l2",
                    "prds": ["00002-b.md"],
                    "pid": 222,
                    "status": "running",
                    "worktree": None,
                    "abort_error": None,
                },
            ],
        },
    )


def _dead_after_one_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    """wave_launch.lane_status reports both lanes "running" through the
    first full pass over the lane list, then "drained" from then on - the
    wait loop's "every lane pid reads dead" condition trips after one poll,
    matching lane_status's own "pid alive" / "dead pid" vocabulary."""
    seen: list[str] = []

    def fake_lane_status(lane: dict) -> str:
        seen.append(lane["name"])
        return "running" if len(seen) <= 2 else "drained"

    monkeypatch.setattr(wave_launch, "lane_status", fake_lane_status)


def _rising_clock() -> Callable[[], float]:
    """Jumps 700s (past the 10-minute print cadence) on every call, so the
    status print/poll fires on the first iteration regardless of exactly
    when and how often run() samples the clock."""
    ticks = {"value": 0.0}

    def clock() -> float:
        ticks["value"] += 700.0
        return ticks["value"]

    return clock


def _bounded_sleep(limit: int = 20) -> Callable[[float], None]:
    """Fails the test fast and legibly instead of hanging the suite if the
    wait loop's termination check never reads a lane as dead."""
    calls = {"n": 0}

    def sleep_fn(_seconds: float) -> None:
        calls["n"] += 1
        if calls["n"] > limit:
            pytest.fail("wave_run.run's wait loop never exited")

    return sleep_fn


def _run_wave_one_lane(wave_path: Path) -> None:
    """A one-lane wave.json: with a single lane, the wait loop's
    `all(lane_status(lane) != "running" for lane in loaded["lanes"])` check
    never short-circuits past a second lane, so a lane_status fake keyed on
    call count maps 1:1 onto wait-loop polls."""
    wave.save(
        wave_path,
        {
            "id": "202609281200",
            "base_sha": "1111111",
            "status": "planned",
            "lanes": [
                {
                    "name": "l1",
                    "prds": ["00001-a.md"],
                    "pid": 111,
                    "status": "running",
                    "worktree": None,
                    "abort_error": None,
                },
            ],
        },
    )


def _dead_after_n_polls(n: int) -> Callable[[dict], str]:
    """wave_launch.lane_status reports "running" for the first n calls, then
    "drained" - paired with _run_wave_one_lane so the wait loop takes exactly
    n non-terminal polls before it exits."""
    calls = {"n": 0}

    def fake_lane_status(lane: dict) -> str:
        calls["n"] += 1
        return "running" if calls["n"] <= n else "drained"

    return fake_lane_status


def _stepped_clock(step: float) -> Callable[[], float]:
    """Advances by a fixed `step` seconds on every call, so a cadence test
    can pin exactly how many polls it takes to cross the 10-minute print
    threshold, unlike `_rising_clock`'s fixed 700s jump."""
    ticks = {"value": 0.0}

    def clock() -> float:
        ticks["value"] += step
        return ticks["value"]

    return clock


def test_run_orders_plan_launch_wait_assemble_review_land(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path = _repo(tmp_path, {})
    _run_wave(wave_path)
    _dead_after_one_pass(monkeypatch)
    calls: list[str] = []
    monkeypatch.setattr(wave, "plan", lambda *a, **k: calls.append("plan") or 0)
    monkeypatch.setattr(
        wave_launch,
        "launch",
        lambda *a, **k: calls.append("launch") or 0,
    )
    monkeypatch.setattr(
        wave_launch,
        "status",
        lambda *a, **k: calls.append("status") or "lane table",
    )
    monkeypatch.setattr(
        wave_assemble,
        "assemble",
        lambda *a, **k: calls.append("assemble") or 0,
    )
    monkeypatch.setattr(
        wave_review,
        "review",
        lambda *a, **k: calls.append("review") or "converged",
    )
    monkeypatch.setattr(wave_review, "land", lambda *a, **k: calls.append("land") or 0)

    exit_code = wave_run.run(
        repo,
        yes=True,
        sleep_fn=_bounded_sleep(),
        clock=_rising_clock(),
    )

    assert exit_code == 0
    assert calls[:2] == ["plan", "launch"]
    assert calls[-3:] == ["assemble", "review", "land"]
    assert "status" in calls[2:-3]


def test_run_status_cadence_skips_the_print_under_ten_minutes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path = _repo(tmp_path, {})
    _run_wave_one_lane(wave_path)
    monkeypatch.setattr(wave_launch, "lane_status", _dead_after_n_polls(3))
    monkeypatch.setattr(wave, "plan", lambda *a, **k: 0)
    monkeypatch.setattr(wave_launch, "launch", lambda *a, **k: 0)
    status_calls: list[str] = []
    monkeypatch.setattr(
        wave_launch,
        "status",
        lambda *a, **k: status_calls.append("status") or "lane table",
    )
    monkeypatch.setattr(wave_assemble, "assemble", lambda *a, **k: 0)
    monkeypatch.setattr(wave_review, "review", lambda *a, **k: "converged")
    monkeypatch.setattr(wave_review, "land", lambda *a, **k: 0)

    exit_code = wave_run.run(
        repo,
        yes=True,
        sleep_fn=_bounded_sleep(),
        clock=_stepped_clock(100.0),
    )

    assert exit_code == 0
    assert status_calls == []


def test_run_status_cadence_prints_once_after_crossing_ten_minutes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path = _repo(tmp_path, {})
    _run_wave_one_lane(wave_path)
    monkeypatch.setattr(wave_launch, "lane_status", _dead_after_n_polls(2))
    monkeypatch.setattr(wave, "plan", lambda *a, **k: 0)
    monkeypatch.setattr(wave_launch, "launch", lambda *a, **k: 0)
    status_calls: list[str] = []
    monkeypatch.setattr(
        wave_launch,
        "status",
        lambda *a, **k: status_calls.append("status") or "lane table",
    )
    monkeypatch.setattr(wave_assemble, "assemble", lambda *a, **k: 0)
    monkeypatch.setattr(wave_review, "review", lambda *a, **k: "converged")
    monkeypatch.setattr(wave_review, "land", lambda *a, **k: 0)

    exit_code = wave_run.run(
        repo,
        yes=True,
        sleep_fn=_bounded_sleep(),
        clock=_stepped_clock(350.0),
    )

    assert exit_code == 0
    assert status_calls == ["status"]


def test_run_without_tty_needs_yes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo, _ = _repo(tmp_path, {})
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    plan_calls: list[str] = []
    monkeypatch.setattr(wave, "plan", lambda *a, **k: plan_calls.append("plan") or 0)

    exit_code = wave_run.run(repo, yes=False)

    assert exit_code == 1
    assert plan_calls == []
    captured = capsys.readouterr()
    assert "--yes" in captured.out + captured.err


def test_run_tty_without_yes_waits_for_confirm_before_launch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path = _repo(tmp_path, {})
    _run_wave(wave_path)
    _dead_after_one_pass(monkeypatch)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    calls: list[str] = []
    monkeypatch.setattr(wave, "plan", lambda *a, **k: calls.append("plan") or 0)
    monkeypatch.setattr(
        wave_launch,
        "launch",
        lambda *a, **k: calls.append("launch") or 0,
    )
    monkeypatch.setattr(wave_launch, "status", lambda *a, **k: "lane table")
    monkeypatch.setattr(wave_assemble, "assemble", lambda *a, **k: 0)
    monkeypatch.setattr(wave_review, "review", lambda *a, **k: "converged")
    monkeypatch.setattr(wave_review, "land", lambda *a, **k: 0)

    def confirm(*args: object, **kwargs: object) -> str:
        calls.append("confirm")
        return ""

    exit_code = wave_run.run(
        repo,
        yes=False,
        confirm_fn=confirm,
        sleep_fn=_bounded_sleep(),
        clock=_rising_clock(),
    )

    assert exit_code == 0
    assert calls[:3] == ["plan", "confirm", "launch"]


def test_run_tty_without_yes_eof_at_confirm_refuses_without_launching(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path = _repo(tmp_path, {})
    _run_wave(wave_path)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(wave, "plan", lambda *a, **k: 0)
    launch_calls: list[str] = []
    monkeypatch.setattr(
        wave_launch,
        "launch",
        lambda *a, **k: launch_calls.append("launch") or 0,
    )

    def confirm(*args: object, **kwargs: object) -> str:
        raise EOFError

    exit_code = wave_run.run(repo, yes=False, confirm_fn=confirm)

    assert exit_code == 1
    assert launch_calls == []


def test_run_yes_on_a_tty_skips_the_confirm_prompt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path = _repo(tmp_path, {})
    _run_wave(wave_path)
    _dead_after_one_pass(monkeypatch)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(wave, "plan", lambda *a, **k: 0)
    monkeypatch.setattr(wave_launch, "launch", lambda *a, **k: 0)
    monkeypatch.setattr(wave_launch, "status", lambda *a, **k: "lane table")
    monkeypatch.setattr(wave_assemble, "assemble", lambda *a, **k: 0)
    monkeypatch.setattr(wave_review, "review", lambda *a, **k: "converged")
    monkeypatch.setattr(wave_review, "land", lambda *a, **k: 0)
    confirm_calls: list[str] = []

    def confirm(*args: object, **kwargs: object) -> str:
        confirm_calls.append("confirm")
        return ""

    exit_code = wave_run.run(
        repo,
        yes=True,
        confirm_fn=confirm,
        sleep_fn=_bounded_sleep(),
        clock=_rising_clock(),
    )

    assert exit_code == 0
    assert confirm_calls == []


@pytest.mark.parametrize("review_slots", [0, -1], ids=["zero", "negative"])
def test_run_rejects_a_non_positive_review_slots_before_any_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    review_slots: int,
) -> None:
    repo, wave_path = _repo(tmp_path, {})
    plan_calls: list[str] = []
    monkeypatch.setattr(wave, "plan", lambda *a, **k: plan_calls.append("plan") or 0)

    exit_code = wave_run.run(repo, review_slots=review_slots, yes=True)

    assert exit_code == 1
    assert plan_calls == []
    assert not wave_path.exists()


def test_run_writes_a_valid_review_slots_value_into_wave_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path = _repo(tmp_path, {})
    _run_wave(wave_path)
    _dead_after_one_pass(monkeypatch)
    monkeypatch.setattr(wave, "plan", lambda *a, **k: 0)
    monkeypatch.setattr(wave_launch, "launch", lambda *a, **k: 0)
    monkeypatch.setattr(wave_launch, "status", lambda *a, **k: "lane table")
    monkeypatch.setattr(wave_assemble, "assemble", lambda *a, **k: 0)
    monkeypatch.setattr(wave_review, "review", lambda *a, **k: "converged")
    monkeypatch.setattr(wave_review, "land", lambda *a, **k: 0)

    exit_code = wave_run.run(
        repo,
        review_slots=5,
        yes=True,
        sleep_fn=_bounded_sleep(),
        clock=_rising_clock(),
    )

    assert exit_code == 0
    assert wave.load(wave_path)["review_slots"] == 5


def test_run_exit_code_follows_the_weakest_step(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """assemble reports a lane held back (3); review still converges and
    land still succeeds - the run's own exit code carries assemble's 3
    forward instead of flattening it to 0."""
    repo, wave_path = _repo(tmp_path, {})
    _run_wave(wave_path)
    _dead_after_one_pass(monkeypatch)
    monkeypatch.setattr(wave, "plan", lambda *a, **k: 0)
    monkeypatch.setattr(wave_launch, "launch", lambda *a, **k: 0)
    monkeypatch.setattr(wave_launch, "status", lambda *a, **k: "lane table")
    monkeypatch.setattr(wave_assemble, "assemble", lambda *a, **k: 3)
    monkeypatch.setattr(wave_review, "review", lambda *a, **k: "converged")
    monkeypatch.setattr(wave_review, "land", lambda *a, **k: 0)

    exit_code = wave_run.run(
        repo,
        yes=True,
        sleep_fn=_bounded_sleep(),
        clock=_rising_clock(),
    )

    assert exit_code == 3


def test_run_exit_code_last_nonzero_step_wins(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pins the combination rule: the LAST non-zero code wins. land's 5
    (master moved between the confirmation gate and land) supersedes
    assemble's earlier 3 - not the reverse, and not a sum or a max."""
    repo, wave_path = _repo(tmp_path, {})
    _run_wave(wave_path)
    _dead_after_one_pass(monkeypatch)
    monkeypatch.setattr(wave, "plan", lambda *a, **k: 0)
    monkeypatch.setattr(wave_launch, "launch", lambda *a, **k: 0)
    monkeypatch.setattr(wave_launch, "status", lambda *a, **k: "lane table")
    monkeypatch.setattr(wave_assemble, "assemble", lambda *a, **k: 3)
    monkeypatch.setattr(wave_review, "review", lambda *a, **k: "converged")
    monkeypatch.setattr(wave_review, "land", lambda *a, **k: 5)

    exit_code = wave_run.run(
        repo,
        yes=True,
        sleep_fn=_bounded_sleep(),
        clock=_rising_clock(),
    )

    assert exit_code == 5


def test_run_returns_1_at_once_when_assemble_refuses(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """assemble's 1 is a refusal (a live lane, or a corrupt/absent
    wave.json), not a kept lane - run must return it immediately instead
    of handing an unmet precondition to review, which would raise
    ValueError."""
    repo, wave_path = _repo(tmp_path, {})
    _run_wave(wave_path)
    _dead_after_one_pass(monkeypatch)
    calls: list[str] = []
    monkeypatch.setattr(wave, "plan", lambda *a, **k: 0)
    monkeypatch.setattr(wave_launch, "launch", lambda *a, **k: 0)
    monkeypatch.setattr(wave_launch, "status", lambda *a, **k: "lane table")
    monkeypatch.setattr(wave_assemble, "assemble", lambda *a, **k: 1)
    monkeypatch.setattr(
        wave_review,
        "review",
        lambda *a, **k: calls.append("review") or "converged",
    )

    exit_code = wave_run.run(
        repo,
        yes=True,
        sleep_fn=_bounded_sleep(),
        clock=_rising_clock(),
    )

    assert exit_code == 1
    assert calls == []


def test_run_calls_land_when_review_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """review_failed must still reach land() - it is the only caller of the
    land() branch that appends the "review_failed" summary line, and the
    run's own exit code carries land's 4 forward."""
    repo, wave_path = _repo(tmp_path, {})
    _run_wave(wave_path)
    _dead_after_one_pass(monkeypatch)
    monkeypatch.setattr(wave, "plan", lambda *a, **k: 0)
    monkeypatch.setattr(wave_launch, "launch", lambda *a, **k: 0)
    monkeypatch.setattr(wave_launch, "status", lambda *a, **k: "lane table")
    monkeypatch.setattr(wave_assemble, "assemble", lambda *a, **k: 0)
    monkeypatch.setattr(wave_review, "review", lambda *a, **k: "review_failed")
    land_calls: list[str] = []
    monkeypatch.setattr(
        wave_review,
        "land",
        lambda *a, **k: land_calls.append("land") or 4,
    )

    exit_code = wave_run.run(
        repo,
        yes=True,
        sleep_fn=_bounded_sleep(),
        clock=_rising_clock(),
    )

    assert land_calls == ["land"]
    assert exit_code == 4


def test_run_interrupt_terminates_lane_groups(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A real SIGINT delivered mid-wait - whether run() installs its own
    signal.signal handler or just lets the default SIGINT -> KeyboardInterrupt
    propagate through a try/except - must call wave_launch's own per-lane
    kill routine for every lane still "running" (the SIGTERM-forwarding
    itself is _kill_lane's own concern, reused rather than reimplemented -
    not re-verified here), mark the wave interrupted, and exit 130.
    _kill_lane itself is faked: its real SIGTERM-then-60s-grace-then-SIGKILL
    escalation needs a genuine process group to observe dying, which these
    made-up lane pids never are."""
    repo, wave_path = _repo(tmp_path, {})
    _run_wave(wave_path)
    monkeypatch.setattr(wave, "plan", lambda *a, **k: 0)
    monkeypatch.setattr(wave_launch, "launch", lambda *a, **k: 0)
    monkeypatch.setattr(wave_launch, "lane_status", lambda lane: "running")
    killed: list[str] = []
    monkeypatch.setattr(
        wave_launch,
        "_kill_lane",
        lambda lane, kill_fn: killed.append(lane["name"]),
    )

    def interrupt(_seconds: float) -> None:
        os.kill(os.getpid(), signal.SIGINT)

    with pytest.raises(SystemExit) as raised:
        wave_run.run(repo, yes=True, sleep_fn=interrupt, clock=lambda: 0.0)

    assert raised.value.code == 130
    assert sorted(killed) == ["l1", "l2"]
    saved_status = wave.load(wave_path)["status"]
    assert saved_status == "interrupted"
    # Not just the literal string: the real per-field validator must accept it too,
    # or `wave assemble`/`plan`/`launch`/`abort` all refuse the saved wave.json.
    assert wave._TOP_CHECKS["status"](saved_status) is True


# ── docs: waves.md names the run() exit codes ───────────────────────────

WAVES_MD = Path(__file__).resolve().parent.parent / "references" / "waves.md"


def test_docs_name_the_exit_codes() -> None:
    text = WAVES_MD.read_text(encoding="utf-8")
    assert "## wave run" in text
    section = text.split("## wave run", 1)[1].split("\n## ", 1)[0]
    for code, phrase in (
        ("0", "landed"),
        ("1", "precondition refused"),
        ("3", "assemble kept a lane"),
        ("4", "review failed"),
        ("5", "master moved"),
    ):
        assert re.search(rf"(?<!\d){code}(?!\d)", section), code
        assert phrase in section, phrase


# ── wave.py: WAVE_STATUSES ───────────────────────────────────────────────


def test_wave_statuses_include_converged_and_review_failed() -> None:
    assert "converged" in wave.WAVE_STATUSES
    assert "review_failed" in wave.WAVE_STATUSES
    assert wave._TOP_CHECKS["status"]("converged") is True
    assert wave._TOP_CHECKS["status"]("review_failed") is True


def test_wave_statuses_include_interrupted() -> None:
    assert "interrupted" in wave.WAVE_STATUSES
    assert wave._TOP_CHECKS["status"]("interrupted") is True


def test_structural_errors_and_assemble_accept_an_interrupted_wave(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The interrupt handler's `status: "interrupted"` must be a value
    `_structural_errors` accepts and `_refusals` does not refuse assembly for
    on status grounds alone - otherwise the documented `wave assemble` resume
    is impossible. The one lane is marked already "assembled" (a
    structurally valid lane status with a real precedent - a rerun that
    finds a lane already merged) so this test isolates the wave-level status
    check from the lane's own liveness and merge machinery."""
    repo, wave_path = _launched(tmp_path, monkeypatch, 1)
    saved = wave.load(wave_path)
    finished = {**saved["lanes"][0], "pid": None, "status": "assembled"}
    interrupted = {**saved, "status": "interrupted", "lanes": [finished]}
    assert wave._structural_errors(repo, interrupted) == []
    wave.save(wave_path, interrupted)
    refusal_code = 1
    assert wave_assemble.assemble(repo, wave_path) != refusal_code


# ── wave_cli.py: review/land/run verbs ───────────────────────────────────


def test_wave_cli_registers_review_land_run_as_wave_subverbs() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()
    wave_cli.add(subparsers)

    review_args = parser.parse_args(["wave", "review", "--state", "x"])
    assert review_args.verb == "review"

    land_args = parser.parse_args(["wave", "land", "--state", "x"])
    assert land_args.verb == "land"

    run_args = parser.parse_args(
        ["wave", "run", "--max-lanes", "2", "--review-slots", "1", "--yes"],
    )
    assert run_args.verb == "run"
    assert run_args.max_lanes == 2
    assert run_args.review_slots == 1
    assert run_args.yes is True
