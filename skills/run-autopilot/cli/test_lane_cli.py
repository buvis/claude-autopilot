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
    assert echoed["lane_effective"] == "full", "solo is unreleased in shadow"
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
