"""Scratch replay of real dispatch prompts for guard_phase_delegation.py.

Split out of `test_guard_phase_delegation.py` (packet 12, PRD 00278): the
committed allow corpus is the gate's reproducible contract, so it must not
depend on gitignored `docs/dev/tmp/dispatch-*.txt` scratch files. This file
replays those scratch files, when present, as an on-demand extra check -
never run by `release-checks` (see its `UNGATED` entry).
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

from test_guard_phase_delegation import _agent_payload, _description, _run

HOOKS = Path(__file__).resolve().parent
CORPUS = HOOKS.parent / "docs" / "dev" / "tmp"


def _self_referential(p: Path) -> bool:
    # This PRD's own dispatch prompts (Tess, Devon, Ivan, their retries)
    # quote the denied phrases verbatim ("guard_phase_delegation") to
    # specify the hook's contract - not a real delegation attempt, so they
    # are excluded rather than counted as false positives. Content-only
    # check: every file this ever excluded (dispatch-tess-1[.txt/-strengthen],
    # dispatch-ivan-1, dispatch-tess-3, dispatch-ivan-3) names the module
    # literally, so no hard-coded filename list is needed.
    return "guard_phase_delegation" in p.read_text(encoding="utf-8")


def _scratch_corpus() -> list[Path]:
    return sorted(p for p in CORPUS.glob("dispatch-*.txt") if not _self_referential(p))


def _guard_module():
    sys.path.insert(0, str(HOOKS))
    return importlib.import_module("guard_phase_delegation")


def _tool_input(fixture: Path, subagent_type: str | None = "general-purpose") -> dict:
    description, _, prompt = fixture.read_text(encoding="utf-8").partition("\n")
    tool_input = {"description": description, "prompt": prompt}
    if subagent_type is not None:
        tool_input["subagent_type"] = subagent_type
    return tool_input


@pytest.mark.skipif(not _scratch_corpus(), reason="no scratch dispatch-*.txt files in docs/dev/tmp")
@pytest.mark.parametrize("prompt_file", _scratch_corpus(), ids=lambda p: p.name)
def test_scratch_dispatch_prompt_is_allowed(prompt_file: Path) -> None:
    guard = _guard_module()
    prompt = prompt_file.read_text(encoding="utf-8")
    assert prompt.strip(), prompt_file.name
    assert guard.is_phase_delegation({"prompt": prompt, "description": ""}) is False
    described = {"prompt": prompt, "description": _description(prompt_file)}
    assert guard.is_phase_delegation(described) is False


@pytest.mark.skipif(not _scratch_corpus(), reason="no scratch dispatch-*.txt files in docs/dev/tmp")
def test_scratch_dispatch_prompts_pass_the_hook_in_the_loop() -> None:
    blocked = []
    for sample in _scratch_corpus():
        tool_input = _tool_input(sample)
        result = _run(_agent_payload(tool_input), loop=True)
        if result.returncode != 0 or result.stderr != "":
            blocked.append((sample.name, result.returncode, result.stderr))
    assert blocked == []
