"""CLI pins for the fast-track planner (fast_track_plan.py).

The four pure functions are the deterministic decisions the driver must not
make from memory, and the CLI is how SKILL.md runs them; the calls themselves
are pinned in test_fast_track_wiring.py. The CLI runs here as a subprocess from
the repo root, against the fixture ledgers beside this file and small JSON
files written into tmp_path. Split out to keep both files under the size limit.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import uuid
from pathlib import Path
from types import ModuleType

import pytest


def _sibling(name: str) -> ModuleType:
    """A helper module read from beside this file, never from an install path."""
    spec = importlib.util.spec_from_file_location(
        name,
        Path(__file__).with_name(f"{name}.py"),
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_testutil = _sibling("fast_track_prose_testutil")

_PLANNER = Path(__file__).with_name("fast_track_plan.py")
_FIXTURES = Path(__file__).with_name("fixtures")
_REPO_ROOT = _testutil.SKILL_MD.parents[2]
_FINDING_KEYS = ("severity", "title", "file", "lane")
_ROSTER = {"blake": 1, "bob": 1, "carl": 1, "eve": 1, "fanout": 1, "ivan": 1}


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(_PLANNER), *args]
    return subprocess.run(command, cwd=_REPO_ROOT, capture_output=True, text=True)


def _row(severity: str, lane: str, title: str = "a finding") -> dict[str, str]:
    return {"severity": severity, "title": title, "file": "src/x.py", "lane": lane}


def _findings(tmp_path: Path, body: object) -> Path:
    path = tmp_path / "findings.json"
    path.write_text(body if isinstance(body, str) else json.dumps(body), "utf-8")
    return path


def _opened(kind: str, item: str, at: int, id_: str) -> dict[str, object]:
    return {"id": id_, "kind": kind, "task": item, "queued_at": at, "prompt_bytes": 9}


def _ledger(tmp_path: Path, source: str | list[dict[str, object]] | None) -> Path:
    # A fixture by name, rows written under a name no CLI can predict, or a path
    # nothing wrote.
    if isinstance(source, str):
        return _FIXTURES / source
    path = tmp_path / f"{uuid.uuid4().hex}.jsonl"
    if source is not None:
        path.write_text("".join(json.dumps(row) + "\n" for row in source), "utf-8")
    return path


# Blocking rows from five lanes, so a CLI whitelisting blake and bob instead of
# excluding the workflow lane has four rows to miss.
_RAISED = [
    _row("CRITICAL", "fast-track:blake", "first"),
    _row("HIGH", "fast-track:fanout", "the workflow's own verifier tested it"),
    _row("MEDIUM", "fast-track:eve", "neither reworks nor blocks"),
    _row("HIGH", "fast-track:eve", "doubt"),
    _row("HIGH", "fast-track:bob", "codex"),
    _row("LOW", "fast-track:carl", "never"),
    _row("CRITICAL", "fast-track:alice", "last, from the legacy consensus lane"),
]
_BLOCKERS = [_RAISED[i] for i in (0, 3, 4, 6)]
_FULL = ["tess", "ivan", "fanout", "blake", "eve", "bob", "carl"]
# The three flags vary independently: each one alone changes the plan.
_LANE_PLANS = [
    (("0", "1", "1"), _FULL),
    (("1", "0", "0"), ["ivan", "alice", "blake", "eve", "bob"]),
    (("0", "1", "0"), _FULL[:6]),
    (("1", "1", "1"), _FULL[1:]),
]
_VERIFY = [(_RAISED, _BLOCKERS), (_RAISED[1:3], []), ([], [])]
_EXITS = [
    ([], "commit"),
    ([_RAISED[2], _RAISED[5]], "commit"),
    (_RAISED[4:6], "branch"),
    ([_RAISED[1]], "branch"),
    ([_RAISED[6]], "branch"),
]
_STAGED = "staged-item"
_STAGED_ROWS = [
    _opened("fast-track:victor", _STAGED, 1, "a1"),
    {"id": "a1", "ended_at": 2, "elapsed_s": 1, "outcome": "ok", "detail": None},
    _opened("fast-track:tess", "another-item", 3, "b2"),
    _opened("fast-track:victor", _STAGED, 4, "c3"),
    {"id": "c3", "kind": "fast-track:victor", "task": _STAGED, "ended_at": 5},
    {"kind": "handoff", "site": "build", "edge": "leave", "at": 6, "prd": "none"},
    _opened("fast-track:delta", _STAGED, 7, "d4"),
]
_HIGH_COUNTS = {**_ROSTER, "delta": 1, "ivan": 2, "victor": 1}
_COUNTS = [
    ("ledger_clean_item.jsonl", "clean-item", _ROSTER),
    (
        "ledger_clean_item.jsonl",
        "noisy-neighbour",
        {"delta": 1, "ivan": 1, "victor": 1},
    ),
    ("ledger_one_confirmed_high.jsonl", "confirmed-high-item", _HIGH_COUNTS),
    (_STAGED_ROWS, _STAGED, {"delta": 1, "victor": 2}),
    (None, "clean-item", {}),
]
_COUNT_IDS = ["clean", "clean-neighbour", "confirmed", "staged", "absent"]
# Each of the four keys missing in turn, behind a well-formed row, so a CLI
# checking one key or one row still accepts three of them.
_MALFORMED = {
    "object": "{}",
    "int": "[1]",
    "text": "no",
    **{
        f"no-{key}": json.dumps(
            [
                _row("CRITICAL", "fast-track:blake"),
                {k: v for k, v in _row("HIGH", "fast-track:bob").items() if k != key},
            ],
        )
        for key in _FINDING_KEYS
    },
}


@pytest.mark.parametrize(
    ("flags", "kinds"),
    _LANE_PLANS,
    ids=["no-tests", "tests-alice", "no-carl", "tests-carl"],
)
def test_lanes_prints_one_kind_per_line_in_dispatch_order(flags, kinds) -> None:
    names = ("--tests-present", "--workflow-available", "--carl-available")
    result = _run("lanes", *(arg for pair in zip(names, flags) for arg in pair))
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [f"fast-track:{kind}" for kind in kinds]


@pytest.mark.parametrize(("rows", "targets"), _VERIFY, ids=["mixed", "none", "empty"])
def test_verify_targets_prints_the_blocking_rows_raised_outside_the_workflow(
    tmp_path,
    rows,
    targets,
) -> None:
    result = _run("verify-targets", str(_findings(tmp_path, rows)))
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == targets


@pytest.mark.parametrize(
    ("rows", "word"),
    _EXITS,
    ids=["empty", "low", "high", "wf", "critical"],
)
def test_exit_action_prints_branch_on_a_surviving_blocker_and_commit_otherwise(
    tmp_path,
    rows,
    word,
) -> None:
    result = _run("exit-action", str(_findings(tmp_path, rows)))
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == word


@pytest.mark.parametrize(("source", "item", "counts"), _COUNTS, ids=_COUNT_IDS)
def test_count_prints_the_items_dispatches_by_kind_sorted_and_ignores_the_rest(
    tmp_path,
    source,
    item,
    counts,
) -> None:
    # Neighbour rows, end rows repeating a kind without `queued_at`, handoff rows,
    # a second item in the same file, a ledger written here, an absent ledger.
    result = _run("count", str(_ledger(tmp_path, source)), item)
    assert result.returncode == 0, result.stderr
    expected = [f"fast-track:{k} {n}" for k, n in sorted(counts.items())]
    assert result.stdout.splitlines() == expected


def test_a_malformed_ledger_line_exits_2_with_one_stderr_line_naming_the_file(
    tmp_path,
) -> None:
    # A bad row is not an absent ledger: silence here would report a free item.
    path = _ledger(tmp_path, _STAGED_ROWS[:1])
    path.write_text(path.read_text("utf-8") + "{not json\n", "utf-8")
    result = _run("count", str(path), _STAGED)
    assert result.returncode == 2, (result.returncode, result.stdout, result.stderr)
    lines = result.stderr.strip().splitlines()
    assert len(lines) == 1 and path.name in lines[0], result.stderr


@pytest.mark.parametrize("verb", ["verify-targets", "exit-action"])
@pytest.mark.parametrize("body", list(_MALFORMED.values()), ids=list(_MALFORMED))
def test_a_malformed_findings_file_exits_2_with_one_stderr_line_naming_it(
    tmp_path,
    verb,
    body,
) -> None:
    path = _findings(tmp_path, body)
    result = _run(verb, str(path))
    assert result.returncode == 2, (result.returncode, result.stdout, result.stderr)
    lines = result.stderr.strip().splitlines()
    assert len(lines) == 1 and path.name in lines[0], result.stderr


@pytest.mark.parametrize("verb", ["verify-targets", "exit-action"])
def test_an_absent_findings_file_is_refused_like_a_malformed_one_never_a_traceback(
    tmp_path,
    verb,
) -> None:
    # The driver's Write step skipped or mistimed: still one line, still exit 2.
    path = tmp_path / "findings.json"
    result = _run(verb, str(path))
    assert result.returncode == 2, (result.returncode, result.stdout, result.stderr)
    lines = result.stderr.strip().splitlines()
    assert len(lines) == 1 and path.name in lines[0], result.stderr
