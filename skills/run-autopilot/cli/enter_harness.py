#!/usr/bin/env python3
"""Shared scaffolding for the cli/enter.py tests.

Not a test module (the name deliberately avoids the `test_` prefix, so pytest
does not collect it): it holds the constants, the fixture builders and the
`Env` harness that test_enter.py and test_enter_decisions.py both drive
`enter()` through. Every `def test_*` lives in those two modules.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

from cli import enter, records

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
_walk_up = importlib.import_module("_walk_up")

KEYS = {
    "stop",
    "detail",
    "prd",
    "source",
    "parked",
    "custody_pending",
    "lane_effective",
    "catchup",
    "design",
    "resume_target",
    "batch",
}
EXPECTED_STOPS = (
    "fs_error",
    "park_halt",
    "mv_verify",
    "deferred_io",
    "stall_op_conflict",
    "stall_op_malformed",
    "park_precondition_failed",
    "replan",
    "escalation_exhausted",
    "cap_pause",
    "custody",
    "drained",
    "prd_not_found",
    "batch_init",
    "lane",
    "state_write_failed",
    "design_review_log_empty",
)
# Stops that can only happen at or after step 6 (resume_target computed).
LATE_ONLY = {
    "custody",
    "drained",
    "prd_not_found",
    "batch_init",
    "lane",
    "state_write_failed",
    "design_review_log_empty",
}
EARLY = [s for s in EXPECTED_STOPS if s not in LATE_ONLY]

CLI_MAIN = Path(__file__).resolve().parent / "__main__.py"

PRD = "00010-sample-prd.md"
OTHER = "00020-other-prd.md"
BATCH_ID = "202609290000"
NOW = "2026-09-29T12:00:00Z"
HEAD = "c" * 40
# Prose-only body: the lane classifier reads it as `full` (reason unparsed).
FULL_PRD = "---\ndesign: skip\n---\n\n# Prose only\n\nNo paths here.\n"
DISPATCH_LINE = (
    "- dispatch 1 (codex): cardinal-sin 0, blocker 0, non-blocker 2, question 1"
)


def _prd_text(**keys: str) -> str:
    head = ["---", *(f"{k}: {v}" for k, v in {"design": "skip", **keys}.items()), "---"]
    return "\n".join(head) + "\n\n# Prose only\n\nNo paths here.\n"


def _open_state(**overrides) -> dict:
    base = {
        "phase": "build",
        "next_phase": "build",
        "batch": {"id": BATCH_ID, "completed_prds": [], "parks_consecutive": 0},
    }
    base.update(overrides)
    return base


def _cache(**overrides) -> dict:
    batch = {
        "id": BATCH_ID,
        "completed_prds": [],
        "parks_consecutive": 0,
        "catchup_completed_at": "2026-09-29T11:00:00Z",
        "catchup_head_sha": HEAD,
    }
    batch.update(overrides)
    return batch


def _custody_entry() -> dict:
    return {
        "prd": "00004-feature-x.md",
        "batch": BATCH_ID,
        "op_id": "op-c1",
        "commit_range": "a" * 40 + ".." + "b" * 40,
        "commits": 2,
        "detail": "cap tripped.",
        "repo_root": "/abs/path",
        "git_dir": None,
        "branch": "master",
    }


class Env:
    """<root>/docs/dev/project-management/{prds,autopilot} plus fakes."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.pm = root / "docs" / "dev" / "project-management"
        self.prds_dir = self.pm / "prds"
        self.autopilot_dir = self.pm / "autopilot"
        self.state_path = self.autopilot_dir / "state.json"
        self.autopilot_dir.mkdir(parents=True)
        self.rows: list[tuple[str, str]] = []
        self.head_calls: list[Path] = []
        self.head: str | None = HEAD

    def put(self, folder: str, name: str = PRD, text: str = FULL_PRD) -> Path:
        path = self.prds_dir / folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def has(self, folder: str, name: str = PRD) -> bool:
        return (self.prds_dir / folder / name).exists()

    def write_state(self, data: dict) -> None:
        self.state_path.write_text(json.dumps(data), encoding="utf-8")

    def read_state(self) -> dict:
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def marker(self, prd: str = PRD) -> None:
        (self.autopilot_dir / "park-requested").write_text(
            json.dumps({"prd": prd, "reason": "wrapper died mid-session"}),
            encoding="utf-8",
        )

    def git_head(self, repo_root: Path) -> str | None:
        self.head_calls.append(repo_root)
        return self.head

    def record(self, prd: str, site: str) -> None:
        self.rows.append((prd, site))

    def run(
        self,
        *,
        prd_arg: str | None = None,
        in_loop: bool = False,
        default_recorder: bool = False,
        **kw,
    ) -> dict:
        if not default_recorder:
            kw.setdefault("record_resume_row", self.record)
        kw.setdefault("now", lambda: NOW)
        out = enter.enter(
            self.state_path,
            prds_dir=self.prds_dir,
            autopilot_dir=self.autopilot_dir,
            prd_arg=prd_arg,
            in_loop=in_loop,
            git_head=self.git_head,
            **kw,
        )
        assert set(out) == KEYS
        assert out["stop"] is None or out["stop"] in enter.STOPS
        assert json.loads(json.dumps(out, sort_keys=True)) == out
        return out


def _fake_park(monkeypatch: pytest.MonkeyPatch, code: int) -> None:
    monkeypatch.setattr(records, "do_park", lambda *a, **k: code)
