#!/usr/bin/env python3
"""The subprocess half of the lane tests (PRD 00204): `autopilot frontmatter`
driven as a real process over a temp state, so the three lane fields land in
`state.json` and on stdout the way Phase 0 step 5 sees them.

Every proof runs THIS checkout's `cli/__main__.py` with the test interpreter,
never the installed cache.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from cli import frontmatter

CLI_MAIN = Path(__file__).resolve().parent / "__main__.py"

SOLO_PRD = """---
catchup: skip
design: skip
---

# Docs only

### Problem Statement

Two reference files drift.

### Repository Structure

```
skills/run-autopilot/
└── references/
    ├── phase-build.md
    └── recovery.md
```

## Implementation Phases

### Phase 0: Foundation

- [ ] Rewrite both files - Acceptance: the prose pin is green
"""


def _run(
    args: list[str],
    cwd: Path,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CLI_MAIN), *args],
        capture_output=True,
        text=True,
        cwd=str(cwd),
        env={**os.environ, **(env or {})},
    )


def _project(tmp_path: Path, prd_text: str) -> tuple[Path, Path]:
    """A synthetic <root>/dev/local/{autopilot,prds/wip} tree: (state, prd)."""
    ap_dir = tmp_path / "dev" / "local" / "autopilot"
    ap_dir.mkdir(parents=True)
    state_path = ap_dir / "state.json"
    state_path.write_text(
        json.dumps(
            {
                "prd": "00204-x-v1.md",
                "phase": "build",
                "next_phase": "build",
                "cycle": 1,
                "phases_completed": [],
                "batch": {"id": "202609141200", "completed_prds": []},
            },
        ),
        encoding="utf-8",
    )
    wip = tmp_path / "dev" / "local" / "prds" / "wip"
    wip.mkdir(parents=True)
    prd = wip / "00204-x-v1.md"
    prd.write_text(prd_text, encoding="utf-8")
    return state_path, prd


def _frontmatter(tmp_path: Path, prd_text: str, env=None):
    state_path, prd = _project(tmp_path, prd_text)
    proc = _run(
        ["frontmatter", "--state", str(state_path), "--prd", str(prd)],
        cwd=tmp_path,
        env=env,
    )
    state = json.loads(state_path.read_text(encoding="utf-8"))
    return proc, state


def test_frontmatter_verb_echoes_lane_fields(tmp_path: Path) -> None:
    proc, state = _frontmatter(tmp_path, SOLO_PRD)
    assert proc.returncode == 0, proc.stderr
    echoed = json.loads(proc.stdout)
    assert echoed["lane"] == "solo"
    assert echoed["lane_reason"] == "no_production_code"
    # `solo` is a released lane since PRD 00205, so it runs as itself.
    assert echoed["lane_effective"] == "solo"
    for key in ("lane", "lane_reason", "lane_effective"):
        assert state[key] == echoed[key]


def test_frontmatter_verb_forces_full_under_lanes_off(tmp_path: Path) -> None:
    proc, state = _frontmatter(tmp_path, SOLO_PRD, env={"_AUTOPILOT_LANES": "off"})
    assert proc.returncode == 0, proc.stderr
    assert state["lane"] == "solo"
    assert state["lane_effective"] == "full"


def test_invalid_override_warns_and_classifies(tmp_path: Path) -> None:
    text = SOLO_PRD.replace("design: skip\n", "design: skip\nlane: fast\n")
    proc, state = _frontmatter(tmp_path, text)
    assert proc.returncode == 0, proc.stderr
    assert proc.stderr.strip().splitlines() == [
        "autopilot: PRD frontmatter lane='fast' is not one of solo/fast-track/full; "
        "defaulting to solo",
    ]
    assert state["lane"] == "solo"
    assert "fast" not in json.dumps(state)


def test_absent_lane_key_is_silent(tmp_path: Path) -> None:
    proc, state = _frontmatter(tmp_path, SOLO_PRD)
    assert proc.returncode == 0
    assert proc.stderr == ""
    # Silence is not absence: the classified fields still land.
    assert json.loads(proc.stdout)["lane"] == "solo"
    assert (state["lane"], state["lane_reason"]) == ("solo", "no_production_code")


def test_valid_override_is_written_as_the_lane(tmp_path: Path) -> None:
    text = SOLO_PRD.replace("design: skip\n", "design: skip\nlane: full\n")
    proc, state = _frontmatter(tmp_path, text)
    assert proc.returncode == 0, proc.stderr
    assert proc.stderr == ""
    assert (state["lane"], state["lane_reason"]) == ("full", "override")


def test_malformed_warning_is_byte_identical(tmp_path: Path) -> None:
    proc, state = _frontmatter(tmp_path, "# PRD with no frontmatter\n")
    assert proc.returncode == 0, proc.stderr
    assert proc.stderr.strip().splitlines() == [frontmatter.MALFORMED_WARNING]
    assert (state["lane"], state["lane_reason"]) == ("full", "unparsed")
    assert state["lane_effective"] == "full"


# ── lane-check (PRD 00205) ───────────────────────────────────────────────────

_GIT_IDENTITY = ["-c", "user.name=t", "-c", "user.email=t@example.com"]


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *_GIT_IDENTITY, "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout.strip()


def _commit(repo: Path, name: str, text: str, message: str = "c") -> None:
    (repo / name).parent.mkdir(parents=True, exist_ok=True)
    (repo / name).write_text(text, encoding="utf-8")
    _git(repo, "add", name)
    _git(repo, "commit", "-q", "-m", message)


def _solo_repo(tmp_path: Path) -> tuple[Path, Path]:
    """A temp git repo with one commit and a solo-lane state whose
    work_start_sha is that commit: (repo, state_path)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _commit(repo, "notes.md", "# notes\n", "base")
    ap_dir = repo / "dev" / "local" / "autopilot"
    ap_dir.mkdir(parents=True)
    state_path = ap_dir / "state.json"
    state_path.write_text(
        json.dumps(
            {
                "prd": "00205-x-v1.md",
                "phase": "build",
                "next_phase": "build",
                "lane": "solo",
                "lane_reason": "no_production_code",
                "lane_effective": "solo",
                "work_start_sha": _git(repo, "rev-parse", "HEAD"),
                "repo_root": str(repo),
            },
        ),
        encoding="utf-8",
    )
    return repo, state_path


def _lane_check(state_path: Path, *extra: str) -> tuple[subprocess.CompletedProcess, dict]:
    proc = _run(["lane-check", "--state", str(state_path), *extra], cwd=state_path.parent)
    return proc, json.loads(state_path.read_text(encoding="utf-8"))


def test_lane_check_escalates_on_a_production_path(tmp_path: Path) -> None:
    repo, state_path = _solo_repo(tmp_path)
    _commit(repo, "pkg/mod.py", "x = 1\n")
    proc, state = _lane_check(state_path)
    assert proc.returncode == 3, proc.stderr
    assert proc.stdout.strip() == "lane: escalate unnamed_path"
    assert state["lane_effective"] == "full"
    assert state["lane_escalated"] == {"from": "solo", "signal": "unnamed_path"}


def test_lane_check_escalates_on_a_security_diff(tmp_path: Path) -> None:
    repo, state_path = _solo_repo(tmp_path)
    _commit(repo, "notes.md", "# notes\npassword: hunter2\n")
    proc, state = _lane_check(state_path)
    assert proc.returncode == 3, proc.stderr
    assert proc.stdout.strip() == "lane: escalate security_diff"
    assert state["lane_escalated"]["signal"] == "security_diff"


def test_lane_check_passes_a_docs_only_diff(tmp_path: Path) -> None:
    repo, state_path = _solo_repo(tmp_path)
    before = state_path.read_bytes()
    _commit(repo, "notes.md", "# notes\nA second line.\n")
    _commit(repo, "docs/test_guide.py", "def test_ok():\n    assert True\n")
    proc, _state = _lane_check(state_path)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "lane: ok"
    assert state_path.read_bytes() == before, "a passing check writes nothing"


@pytest.mark.parametrize(
    "signal", ["critical_finding", "high_unresolved", "suite_red", "review_failed"]
)
def test_lane_check_records_an_explicit_signal(tmp_path: Path, signal: str) -> None:
    _repo, state_path = _solo_repo(tmp_path)
    proc, state = _lane_check(state_path, "--signal", signal)
    assert proc.returncode == 3, proc.stderr
    assert proc.stdout.strip() == f"lane: escalate {signal}"
    assert state["lane_effective"] == "full"
    assert state["lane_escalated"] == {"from": "solo", "signal": signal}


def test_lane_check_refuses_an_unreadable_state_path(tmp_path: Path) -> None:
    # A directory (or a permission-denied file) is as unreadable as a
    # missing file: exit 2 with the reason, never a traceback.
    _repo, state_path = _solo_repo(tmp_path)
    proc = _run(["lane-check", "--state", str(state_path.parent)], cwd=tmp_path)
    assert proc.returncode == 2
    assert "lane-check:" in proc.stderr
    assert "Traceback" not in proc.stderr


def test_lane_check_escalates_when_git_fails(tmp_path: Path) -> None:
    _repo, state_path = _solo_repo(tmp_path)
    not_a_repo = tmp_path / "elsewhere"
    not_a_repo.mkdir()
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["repo_root"] = str(not_a_repo)
    state_path.write_text(json.dumps(state), encoding="utf-8")
    proc, state = _lane_check(state_path)
    assert proc.returncode == 3, proc.stderr
    assert proc.stdout.strip() == "lane: escalate check_failed"
    assert state["lane_escalated"]["signal"] == "check_failed"


def test_lane_check_refuses_without_work_start_sha(tmp_path: Path) -> None:
    _repo, state_path = _solo_repo(tmp_path)
    state = json.loads(state_path.read_text(encoding="utf-8"))
    del state["work_start_sha"]
    state_path.write_text(json.dumps(state), encoding="utf-8")
    proc, state = _lane_check(state_path)
    assert proc.returncode == 2
    assert "work_start_sha" in proc.stderr
    assert "lane_escalated" not in state


def test_lane_check_rejects_an_unknown_signal(tmp_path: Path) -> None:
    _repo, state_path = _solo_repo(tmp_path)
    proc, state = _lane_check(state_path, "--signal", "sideways")
    # _ArgumentParser maps every usage error to exit 1; 2 is reserved for
    # state errors (the exit-code table in __main__.py's docstring).
    assert proc.returncode == 1
    assert "--signal" in proc.stderr and "'sideways'" in proc.stderr
    assert "review_failed" in proc.stderr, "the usage line lists the four signals"
    assert "lane_escalated" not in state


def test_lane_check_sees_a_production_file_renamed_into_docs(tmp_path: Path) -> None:
    # With rename detection the diff would list only notes/mod.md and carry
    # no changed lines; --no-renames reads the rename as a delete plus an
    # add, so the vanished production file still escalates.
    repo, state_path = _solo_repo(tmp_path)
    _commit(repo, "pkg/mod.py", "x = 1\n")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["work_start_sha"] = _git(repo, "rev-parse", "HEAD")
    state_path.write_text(json.dumps(state), encoding="utf-8")
    (repo / "notes").mkdir()
    _git(repo, "mv", "pkg/mod.py", "notes/mod.md")
    _git(repo, "commit", "-q", "-m", "rename")
    proc, state = _lane_check(state_path)
    assert proc.returncode == 3, proc.stderr
    assert proc.stdout.strip() == "lane: escalate unnamed_path"


def test_phase_done_lane_reviewed_from_build(tmp_path: Path) -> None:
    _repo, state_path = _solo_repo(tmp_path)
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["phases_completed"] = []
    state_path.write_text(json.dumps(state), encoding="utf-8")
    proc = _run(
        ["phase-done", "--state", str(state_path), "--outcome", "lane_reviewed"],
        cwd=state_path.parent,
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout) == {"phase": "done", "next_phase": "done"}
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["phases_completed"] == ["review"]
    assert state["next_phase"] == "done"
