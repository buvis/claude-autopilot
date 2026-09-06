"""Shared loader and helpers for the record_dispatch.py test files (PRD 00168).

record_dispatch.py's tests outgrew a single 800-line file and were split by
verb (see test_record_dispatch.py's module docstring for the shared testing
approach); every split file loads this module the same way it would have
loaded record_dispatch.py directly, so each keeps its own independent copy
of both modules and no test-file order or caching assumption is introduced.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

MODULE_PATH = Path(__file__).with_name("record_dispatch.py")
_SPEC = importlib.util.spec_from_file_location("record_dispatch", MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
record_dispatch = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(record_dispatch)

HEX_ID = re.compile(r"^[0-9a-f]{8}$")


def project(tmp_path: Path) -> Path:
    """A project tree with an autopilot dir and a nested cwd; returns the dir."""
    autopilot = tmp_path / "proj" / "dev" / "local" / "autopilot"
    autopilot.mkdir(parents=True)
    (tmp_path / "proj" / "src").mkdir()
    return autopilot


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def pin_clock(monkeypatch: pytest.MonkeyPatch, now: float) -> None:
    monkeypatch.setattr(record_dispatch, "time", SimpleNamespace(time=lambda: now))


def run_handoff(site: str, edge: str, phase: str, prd: str) -> int:
    return record_dispatch.main(
        ["handoff", "--site", site, "--edge", edge, "--phase", phase, "--prd", prd],
    )
