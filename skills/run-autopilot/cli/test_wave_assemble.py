#!/usr/bin/env python3
"""Tests for cli/wave_assemble.py - keep_both, summary and the assemble merge pass.

`keep_both` strips git's three-way conflict marker lines while keeping both
sides of every hunk; `summary` renders a wave's markdown report from
already-computed, already-loaded in-memory data (a wave dict, this wave's
migrated loop-metrics rows, and this wave's assembly_conflict records).
Both are pure - no disk, no git - so every wave/rows/records value here is
an in-memory literal.

`assemble` runs against a throwaway `git init` repo under `tmp_path` whose
wave was planned and launched for real (a recording spawn, no loop started):
each lane commits into its own worktree, then its pid is swapped for a dead
one and its state.json says drained or unfinished. Only `release-checks` is
faked, through the `run_checks` seam.

What `assemble` does after the merge - `migrate_lane`, a merged lane's
worktree removal and the written report - is proved in the sibling
cli/test_wave_assemble_migrate.py, which reuses the fixtures below: run both
files.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

from cli import wave, wave_assemble, wave_launch
from cli.loop_testutil import _spawn_tagged_incumbent
from cli.test_wave_docs import _claims, _sentences
from cli.test_wave_launch import (
    THREE_LANES,
    _autopilot,
    _dead_pid,
    _FakeSpawn,
    _git,
    _repo,
)


def _lane(name: str, prds: list[str], **extra: object) -> dict:
    base = {"name": name, "prds": list(prds), "status": "assembled", "files": []}
    base.update(extra)
    return base


def _wave(
    *,
    wave_id: str = "202609261200",
    lanes: list[dict] | None = None,
    prds: list[dict] | None = None,
) -> dict:
    return {
        "id": wave_id,
        "status": "assembled",
        "lanes": list(lanes) if lanes is not None else [],
        "assembly": {},
        "prds": list(prds) if prds is not None else [],
    }


# ── keep_both ─────────────────────────────────────────────────────────────


def test_keep_both_keeps_both_sides_in_file_order() -> None:
    ours_marker = "<" * 7 + " HEAD"
    sep_marker = "=" * 7
    theirs_marker = ">" * 7 + " feature-branch"
    text = (
        "before\n"
        f"{ours_marker}\n"
        "our line one\n"
        "our line two\n"
        f"{sep_marker}\n"
        "their line one\n"
        "their line two\n"
        f"{theirs_marker}\n"
        "after\n"
    )
    expected = (
        "before\nour line one\nour line two\ntheir line one\ntheir line two\nafter\n"
    )
    assert wave_assemble.keep_both(text) == expected


def test_keep_both_leaves_a_clean_file_alone() -> None:
    # Ordinary lines that start the way a marker does: a markdown underline, a
    # comparison, a doctest prompt, an HTML tag, and a run one character longer
    # than git's own 7-character marker. None of them is a conflict marker.
    text = (
        "one fish\n"
        "======\n"
        "if a >= b:\n"
        "    pass\n"
        ">>> foo()\n"
        "<div>x</div>\n"
        f"{'<' * 8}\n"
        "two fish\n"
    )
    assert wave_assemble.keep_both(text) == text


# ── summary: per-PRD lines ───────────────────────────────────────────────


def test_summary_names_every_prd_with_its_lane_and_outcome() -> None:
    wave = _wave(
        lanes=[
            _lane("l1", ["00215-foo-v1.md"]),
            _lane("l2", ["00216-bar-v1.md", "00217-baz-v1.md", "00218-qux-v1.md"]),
        ],
        prds=[
            {"prd": "00215-foo-v1.md", "lane": "l1", "label": "done"},
            {"prd": "00216-bar-v1.md", "lane": "l2", "label": "parked"},
            {"prd": "00217-baz-v1.md", "lane": "l2", "label": "unassembled"},
            {"prd": "00218-qux-v1.md", "lane": "l2", "label": "backlog"},
        ],
    )
    text = wave_assemble.summary(wave, [], [])
    assert "- 00215-foo-v1.md: Wave 202609261200, lane l1, done" in text
    assert "- 00216-bar-v1.md: Wave 202609261200, lane l2, parked" in text
    assert "- 00217-baz-v1.md: Wave 202609261200, lane l2, unassembled" in text
    assert "- 00218-qux-v1.md: Wave 202609261200, lane l2, backlog" in text


# ── summary: conflict records ────────────────────────────────────────────


def test_summary_lists_conflict_records_verbatim() -> None:
    wave = _wave(lanes=[_lane("l1", ["00215-foo-v1.md"])])
    records = [
        {
            "prd": "00220-example-v1.md",
            "lane": "l2",
            "reason": "conflict marker in cli/foo.py",
        },
        {"prd": "00221-other-v1.md", "lane": "l3", "reason": "binary file diverged"},
    ]
    text = wave_assemble.summary(wave, [], records)
    assert "00220-example-v1.md" in text
    assert "conflict marker in cli/foo.py" in text
    assert "00221-other-v1.md" in text
    assert "binary file diverged" in text


# ── summary: integrator notes ────────────────────────────────────────────


def test_summary_lists_integrator_trailers() -> None:
    wave = _wave(
        lanes=[
            _lane(
                "l1",
                ["00215-foo-v1.md"],
                integrator_notes=[
                    {"sha": "abc1234", "text": "Resolved import order in foo.py"},
                    {"sha": "def5678", "text": "Kept both docstring edits"},
                ],
            ),
            _lane(
                "l2",
                ["00216-bar-v1.md"],
                integrator_notes=[
                    {"sha": "aaa9999", "text": "Dropped a duplicate test case"},
                ],
            ),
        ],
    )
    text = wave_assemble.summary(wave, [], [])
    heading_index = text.index("## Integrator notes")
    for lane, sha, note_text in (
        ("l1", "abc1234", "Resolved import order in foo.py"),
        ("l1", "def5678", "Kept both docstring edits"),
        ("l2", "aaa9999", "Dropped a duplicate test case"),
    ):
        line = f"- {lane} {sha}: {note_text}"
        assert line in text, text
        assert text.index(line) > heading_index
    # Would fail if the lane names were swapped between notes.
    assert "- l2 abc1234: Resolved import order in foo.py" not in text
    assert "- l1 aaa9999: Dropped a duplicate test case" not in text


def test_summary_shows_none_when_no_integrator_notes() -> None:
    wave = _wave(
        lanes=[
            _lane("l1", ["00215-foo-v1.md"]),  # integrator_notes key omitted
            _lane("l2", ["00216-bar-v1.md"], integrator_notes=None),
        ],
    )
    text = wave_assemble.summary(wave, [], [])
    heading_index = text.index("## Integrator notes")
    assert "(none)" in text[heading_index:]


# ── summary: the report header ───────────────────────────────────────────


_HEADERS = (
    {
        "id": "202609261200",
        "base_branch": "wip/waves",
        "base_sha": "abcdef0",
        "branch": "wave/202609261200/assembly",
        "head_sha": "fedcba9",
    },
    {
        "id": "202610021545",
        "base_branch": "release/2.1",
        "base_sha": "1234567",
        "branch": "wave/202610021545/assembly",
        "head_sha": "7654321",
    },
)


@pytest.mark.parametrize(
    ("spec", "other"),
    [(_HEADERS[0], _HEADERS[1]), (_HEADERS[1], _HEADERS[0])],
    ids=["first-wave", "second-wave"],
)
def test_summary_opens_with_the_base_and_the_assembled_head(
    spec: dict,
    other: dict,
) -> None:
    wave = {
        **_wave(wave_id=spec["id"], lanes=[_lane("l1", ["00215-foo-v1.md"])]),
        "base_branch": spec["base_branch"],
        "base_sha": spec["base_sha"],
        "assembly": {
            "worktree": f"/tmp/proj-wave-{spec['id']}",
            "branch": spec["branch"],
            "head_sha": spec["head_sha"],
            "merged": ["l1"],
            "kept": [],
        },
    }
    text = wave_assemble.summary(wave, [], [])
    header = text[: text.index("## PRDs")]
    # Each value pinned to its own labelled line, not just present somewhere in
    # the header: a summary() that swapped base_sha and head_sha between the
    # "base" and "assembled head" lines would fail these two assertions even
    # though both values still appear in the header.
    assert f"# Wave {spec['id']} summary" in header, header
    assert f"- base: {spec['base_branch']} @ {spec['base_sha']}" in header, header
    assert f"- assembled head: {spec['branch']} @ {spec['head_sha']}" in header, header
    # None of the other wave's values either: a header rendered from constants
    # cannot serve both waves.
    for key in ("id", "base_branch", "base_sha", "branch", "head_sha"):
        assert other[key] not in header, header


# ── summary: the lane table ──────────────────────────────────────────────


def _cells(line: str) -> list[str]:
    """A table line's cells, outer pipes and padding dropped."""
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _cell(text: str, line: str, column: str) -> str:
    """`line`'s cell under the lane table's `column` header."""
    for each in text.splitlines():
        headers = [cell.lower() for cell in _cells(each)]
        if {"paths", "files"} <= set(headers):
            return _cells(line)[headers.index(column)]
    raise AssertionError(f"no lane table header naming paths and files:\n{text}")


def test_summary_tables_each_lane_with_its_branch_status_and_batch() -> None:
    # Neither branch name carries its own lane's name, so a missing lane-name
    # column cannot pass on the branch column's coat-tails; each lane's `prds`,
    # `paths` and `files` are disjoint, so neither column can be rendered from
    # another lane's or another column's. l1 carries two of each, pinning the
    # ", ".join(...) separator and element order; a join dropped for the first
    # element alone, or one that reordered the list, would fail l1's asserts.
    wave = _wave(
        lanes=[
            _lane(
                "l1",
                ["00215-foo-v1.md", "00219-quux-v1.md"],
                branch="wave/202609261200/alpha",
                paths=["cli/foo.py", "cli/qux.py"],
                files=["cli/renamed.py", "cli/renamed2.py"],
                batch_id="202609260900",
            ),
            _lane(
                "l2",
                ["00216-bar-v1.md"],
                status="conflict",
                branch="wave/202609261200/beta",
                paths=["cli/bar.py"],
                files=["cli/moved.py"],
                batch_id="202609261000",
            ),
        ],
    )
    text = wave_assemble.summary(wave, [], [])

    def row(branch: str) -> str:
        """The single table line that is this lane's row."""
        matching = [line for line in text.splitlines() if branch in line]
        assert len(matching) == 1, matching
        return matching[0]

    first = row("wave/202609261200/alpha")
    second = row("wave/202609261200/beta")
    for token in ("l1", "assembled", "202609260900"):
        assert token in first, first
    for token in ("l2", "conflict", "202609261000"):
        assert token in second, second
    # Exact cell contents: the join separator and element order are pinned,
    # not just each element's presence somewhere in the row.
    assert _cell(text, first, "prds") == "00215-foo-v1.md, 00219-quux-v1.md", first
    assert _cell(text, first, "paths") == "cli/foo.py, cli/qux.py", first
    assert _cell(text, first, "files") == "cli/renamed.py, cli/renamed2.py", first
    assert _cell(text, second, "prds") == "00216-bar-v1.md", second
    assert _cell(text, second, "paths") == "cli/bar.py", second
    assert _cell(text, second, "files") == "cli/moved.py", second


# ── summary: the totals ──────────────────────────────────────────────────


# Four sessions, 8100 wall seconds (2.25 hours), one captured cost (1.25): a row
# may carry no cost at all, and a row may carry no wall time either.
_FOUR_SESSIONS = [
    {"prd": "00215-foo-v1.md", "wall_secs": 5400, "cost_usd": 1.25},
    {"prd": "00215-foo-v1.md", "wall_secs": 2700, "cost_usd": None},
    {"prd": "00215-foo-v1.md", "wall_secs": 0},
    {"prd": "00215-foo-v1.md"},
]
# Three sessions, 4500 wall seconds (1.25 hours), two captured costs (7.75).
_THREE_SESSIONS = [
    {"prd": "00215-foo-v1.md", "wall_secs": 3600, "cost_usd": 7.0},
    {"prd": "00215-foo-v1.md", "wall_secs": 900, "cost_usd": 0.75},
    {"prd": "00215-foo-v1.md", "wall_secs": 0, "cost_usd": None},
]
# Five sessions, 3500 wall seconds: not a multiple of 900, so the hours total
# (0.9722... -> "0.97") pins actual rounding, not a round quarter-hour that a
# lookup-table formula could special-case. Three captured costs (6.66).
_FIVE_SESSIONS = [
    {"prd": "00215-foo-v1.md", "wall_secs": 1000, "cost_usd": 1.11},
    {"prd": "00215-foo-v1.md", "wall_secs": 2000, "cost_usd": 2.22},
    {"prd": "00215-foo-v1.md", "wall_secs": 500, "cost_usd": 3.33},
    {"prd": "00215-foo-v1.md", "wall_secs": 0, "cost_usd": None},
    {"prd": "00215-foo-v1.md"},
]


@pytest.mark.parametrize(
    ("rows", "totals", "absent"),
    [
        (
            _FOUR_SESSIONS,
            "totals: 4 sessions, 2.25 wall hours, $1.25 captured cost",
            ("3 sessions", "1.25 wall", "$7.75"),
        ),
        (
            _THREE_SESSIONS,
            "totals: 3 sessions, 1.25 wall hours, $7.75 captured cost",
            ("4 sessions", "2.25 wall", "$1.25"),
        ),
        (
            _FIVE_SESSIONS,
            "totals: 5 sessions, 0.97 wall hours, $6.66 captured cost",
            ("4 sessions", "2.25 wall", "$1.25"),
        ),
    ],
    ids=["four-sessions", "three-sessions", "five-sessions"],
)
def test_summary_totals_the_sessions_wall_hours_and_captured_cost(
    rows: list[dict],
    totals: str,
    absent: tuple[str, ...],
) -> None:
    wave = _wave(lanes=[_lane("l1", ["00215-foo-v1.md"])])
    text = wave_assemble.summary(wave, rows, [])
    # The two row sets share no total, so one constant cannot render both, and
    # neither set's numbers may leak into the other's report.
    assert totals in text, text
    for token in absent:
        assert token not in text, text


# ── assemble: fixtures ───────────────────────────────────────────────────


def _write(root: Path, files: dict[str, str]) -> None:
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")


def _launched(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    count: int,
    seed: dict[str, str] | None = None,
) -> tuple[Path, Path]:
    """A wave of `count` lanes, planned and launched with no loop started, over
    a repo whose base commit also carries `seed`: (repo, wave.json path)."""
    repo, wave_path = _repo(tmp_path, dict(list(THREE_LANES.items())[:count]))
    if seed:
        _write(repo, seed)
        _git(repo, "add", *seed)
        _git(repo, "commit", "-qm", "seed files")
    monkeypatch.chdir(tmp_path)
    assert wave.plan(repo, wave_path, max_lanes=count) == 0
    assert wave_launch.launch(repo, wave_path, spawn_fn=_FakeSpawn()) == 0
    return repo, wave_path


def _set_pid(wave_path: Path, name: str, pid: int) -> Path:
    """Point lane `name` at `pid` in wave.json; the lane's worktree."""
    saved = wave.load(wave_path)
    lanes = [
        {**each, "pid": pid} if each["name"] == name else each
        for each in saved["lanes"]
    ]
    wave.save(wave_path, {**saved, "lanes": lanes})
    return Path(next(each["worktree"] for each in lanes if each["name"] == name))


def _finish(wave_path: Path, name: str, next_phase: str) -> Path:
    """Lane `name`'s loop has exited; its state.json says `next_phase`
    ("" is drained, anything else unfinished). The lane's worktree."""
    worktree = _set_pid(wave_path, name, _dead_pid())
    _autopilot(worktree).mkdir(parents=True, exist_ok=True)
    (_autopilot(worktree) / "state.json").write_text(
        json.dumps({"next_phase": next_phase}),
        encoding="utf-8",
    )
    return worktree


def _commit(
    worktree: Path,
    files: dict[str, str],
    subject: str,
    body: str = "",
) -> str:
    """Commit `files` on the lane branch checked out at `worktree`; its sha."""
    _write(worktree, files)
    _git(worktree, "add", *files)
    _git(worktree, "commit", "-q", "-m", subject, *(["-m", body] if body else []))
    return _git(worktree, "rev-parse", "HEAD").stdout.strip()


def _checks_pass(cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(["bash", "dev/bin/release-checks"], 0, "", "")


def _saved(repo: Path, wave_path: Path) -> tuple[dict, dict[str, dict]]:
    """wave.json as assemble left it - still structurally sound under the new
    statuses and optional fields - and its lanes by name."""
    saved = wave.load(wave_path)
    assert wave._structural_errors(repo, saved) == []
    return saved, {each["name"]: each for each in saved["lanes"]}


def _tree(repo: Path, ref: str) -> list[str]:
    return _git(repo, "ls-tree", "-r", "--name-only", ref).stdout.splitlines()


def _show(repo: Path, ref: str, rel: str) -> str:
    return _git(repo, "show", f"{ref}:{rel}").stdout


def _deferred(wave_path: Path, wave_id: str) -> Path:
    return wave_path.parent / "deferred" / f"{wave_id}-deferred.json"


def _deferred_items(wave_path: Path, wave_id: str) -> list[dict]:
    """This wave's deferred records; the file is batched on the bare wave id."""
    content = json.loads(_deferred(wave_path, wave_id).read_text(encoding="utf-8"))
    assert content["batch_id"] == wave_id
    return content["items"]


def _clashing_edits(name: str) -> dict[str, str]:
    """Lane `name`'s edit of the same lines of one append-only file and of two
    ordinary files, so any two lanes committing these conflict on all three."""
    return {
        "CHANGELOG.md": f"# Changelog\n- {name} entry\n",
        "src/zeta.py": f"zeta = '{name}'\n",
        "src/alpha.py": f"alpha = '{name}'\n",
    }


# ── assemble: the per-lane merge pass ────────────────────────────────────


def test_assemble_merges_drained_lanes_in_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path = _launched(tmp_path, monkeypatch, 3)
    for name, rel in (("l1", "x/a.py"), ("l2", "y/b.py"), ("l3", "z/c.py")):
        _commit(_finish(wave_path, name, ""), {rel: f"# {name}\n"}, f"{name} change")
    # Stored out of order: the merge follows each lane's `order`, not the list.
    stored = wave.load(wave_path)
    by_name = {each["name"]: each for each in stored["lanes"]}
    shuffled = [by_name[name] for name in ("l2", "l3", "l1")]
    wave.save(wave_path, {**stored, "lanes": shuffled})
    assert [each["order"] for each in wave.load(wave_path)["lanes"]] == [2, 3, 1]
    checked: list[tuple[Path, str]] = []

    def run_checks(cwd: Path) -> subprocess.CompletedProcess:
        head = _git(Path(cwd), "log", "-1", "--format=%s").stdout.strip()
        checked.append((Path(cwd).resolve(), head))
        return _checks_pass(cwd)

    wave_assemble.assemble(repo, wave_path, run_checks=run_checks)
    saved, lanes = _saved(repo, wave_path)
    wave_id = saved["id"]
    # Checks run in the wave-scoped assembly worktree, once after each merge.
    assembly = (tmp_path / f"proj-wave-{wave_id}").resolve()
    assert checked == [
        (assembly, "l1 change"),
        (assembly, "l2 change"),
        (assembly, "l3 change"),
    ]
    ref = f"wave/{wave_id}/assembly"
    log = _git(repo, "log", "--reverse", "--format=%s", f"{saved['base_sha']}..{ref}")
    assert log.stdout.splitlines() == ["l1 change", "l2 change", "l3 change"]
    assert {"x/a.py", "y/b.py", "z/c.py"} <= set(_tree(repo, ref))
    for name in ("l1", "l2", "l3"):
        assert lanes[name]["status"] == "assembled", lanes[name]
        assert lanes[name].get("conflict_detail") is None, lanes[name]
        assert lanes[name].get("conflict_paths") is None, lanes[name]
    assert not _deferred(wave_path, wave_id).exists()


def test_append_only_conflicts_keep_both_sides_in_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed = {
        "CHANGELOG.md": "# Changelog\n",
        "dev/bin/release-checks": "#!/usr/bin/env bash\n",
    }
    repo, wave_path = _launched(tmp_path, monkeypatch, 2, seed)
    # Both lanes append at the same spot of both append-only files.
    for name, rel in (("l1", "x/a.py"), ("l2", "y/b.py")):
        files = {
            rel: f"# {name}\n",
            "CHANGELOG.md": f"# Changelog\n- {name} entry\n",
            "dev/bin/release-checks": f"#!/usr/bin/env bash\ncheck-{name}\n",
        }
        _commit(_finish(wave_path, name, ""), files, f"{name} change")
    wave_assemble.assemble(repo, wave_path, run_checks=_checks_pass)
    saved, lanes = _saved(repo, wave_path)
    assert (lanes["l1"]["status"], lanes["l2"]["status"]) == ("assembled", "assembled")
    ref = f"wave/{saved['id']}/assembly"
    assert _show(repo, ref, "CHANGELOG.md") == "# Changelog\n- l1 entry\n- l2 entry\n"
    assert _show(repo, ref, "dev/bin/release-checks") == (
        "#!/usr/bin/env bash\ncheck-l1\ncheck-l2\n"
    )
    assert _show(repo, ref, "y/b.py") == "# l2\n"
    assert not _deferred(wave_path, saved["id"]).exists()


def test_other_conflict_keeps_the_lane_and_records_assembly_conflict(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed = {
        "CHANGELOG.md": "# Changelog\n",
        "src/alpha.py": "alpha = 0\n",
        "src/zeta.py": "zeta = 0\n",
    }
    repo, wave_path = _launched(tmp_path, monkeypatch, 2, seed)
    _commit(_finish(wave_path, "l1", ""), _clashing_edits("l1"), "l1 change")
    l2_files = {**_clashing_edits("l2"), "docs/l2.md": "l2 notes\n"}
    tip = _commit(_finish(wave_path, "l2", ""), l2_files, "l2 change")
    wave_assemble.assemble(repo, wave_path, run_checks=_checks_pass)
    saved, lanes = _saved(repo, wave_path)
    wave_id, kept = saved["id"], lanes["l2"]
    assert (lanes["l1"]["status"], kept["status"]) == ("assembled", "conflict")
    # Sorted, and only the paths outside the append-only set.
    assert kept["conflict_paths"] == ["src/alpha.py", "src/zeta.py"]
    # The lane's whole pre-rebase diff is a different, wider list.
    assert kept["files"] == sorted(l2_files)
    detail = kept["conflict_detail"]
    assert detail.startswith("2 conflicted path(s) outside the append-only set: ")
    assert "src/alpha.py" in detail, detail
    assert "src/zeta.py" in detail, detail
    assert "CHANGELOG.md" not in detail, detail
    # The rebase was aborted: the lane branch and worktree are as the lane left them.
    assert _git(repo, "rev-parse", kept["branch"]).stdout.strip() == tip
    assert _git(Path(kept["worktree"]), "status", "--porcelain").stdout == ""
    ref = f"wave/{wave_id}/assembly"
    assert _show(repo, ref, "src/alpha.py") == "alpha = 'l1'\n"
    assert "docs/l2.md" not in _tree(repo, ref)
    assert _deferred_items(wave_path, wave_id) == [
        {
            "type": "stall",
            "site": "assembly_conflict",
            "lane": "l2",
            "files": ["src/alpha.py", "src/zeta.py"],
            "detail": detail,
            "op_id": f"wave-{wave_id}-l2",
            "prd": kept["prds"][0],
        },
    ]


def test_checks_failure_undoes_the_lane_merge_and_keeps_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path = _launched(tmp_path, monkeypatch, 2)
    for name, rel in (("l1", "x/a.py"), ("l2", "y/b.py")):
        _commit(_finish(wave_path, name, ""), {rel: f"# {name}\n"}, f"{name} change")

    def run_checks(cwd: Path) -> subprocess.CompletedProcess:
        # Only l2's file breaks the checks, whenever they run.
        if not (Path(cwd) / "y/b.py").exists():
            return _checks_pass(cwd)
        stderr = "lint: starting\nlint: y/b.py is broken\n"
        return subprocess.CompletedProcess(["bash", "release-checks"], 3, "", stderr)

    wave_assemble.assemble(repo, wave_path, run_checks=run_checks)
    saved, lanes = _saved(repo, wave_path)
    wave_id, kept = saved["id"], lanes["l2"]
    assert (lanes["l1"]["status"], kept["status"]) == ("assembled", "checks_failed")
    detail = kept["conflict_detail"]
    assert detail.startswith("release-checks exit 3 after merging "), detail
    assert detail.endswith(": lint: y/b.py is broken"), detail
    assert "l2" in detail, detail
    assert kept.get("conflict_paths") is None
    # The assembly branch is back at l1's merge; l2's branch still holds its work.
    ref = f"wave/{wave_id}/assembly"
    assert _git(repo, "log", "-1", "--format=%s", ref).stdout.strip() == "l1 change"
    assert "y/b.py" not in _tree(repo, ref)
    kept_log = _git(repo, "log", "--format=%s", kept["branch"]).stdout.splitlines()
    assert "l2 change" in kept_log
    # No path list applies to a checks failure: the "files" key is left out.
    assert _deferred_items(wave_path, wave_id) == [
        {
            "type": "stall",
            "site": "assembly_conflict",
            "lane": "l2",
            "detail": detail,
            "op_id": f"wave-{wave_id}-l2",
            "prd": kept["prds"][0],
        },
    ]


@pytest.mark.parametrize("next_phase", ["work", "review"])
def test_unfinished_lane_is_skipped_not_merged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    next_phase: str,
) -> None:
    repo, wave_path = _launched(tmp_path, monkeypatch, 2)
    # The unfinished lane comes first, so skipping it must not end the pass.
    # Any phase still pending makes a lane unfinished, not one phase name.
    unfinished = _finish(wave_path, "l1", next_phase)
    tip = _commit(unfinished, {"x/a.py": "# l1\n"}, "l1 change")
    _commit(_finish(wave_path, "l2", ""), {"y/b.py": "# l2\n"}, "l2 change")
    # A lane left behind is a kept lane: the wave is partial, not green.
    assert wave_assemble.assemble(repo, wave_path, run_checks=_checks_pass) == 3
    saved, lanes = _saved(repo, wave_path)
    assert saved["status"] == "assembled_partial", saved["status"]
    assert (lanes["l1"]["status"], lanes["l2"]["status"]) == ("unfinished", "assembled")
    tree = _tree(repo, f"wave/{saved['id']}/assembly")
    assert "y/b.py" in tree
    assert "x/a.py" not in tree
    assert _git(repo, "rev-parse", lanes["l1"]["branch"]).stdout.strip() == tip


@pytest.mark.parametrize("live_name", ["l1", "l2", "l3"])
def test_live_lane_refuses_assembly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    live_name: str,
) -> None:
    repo, wave_path = _launched(tmp_path, monkeypatch, 3)
    for name, rel in (("l1", "x/a.py"), ("l2", "y/b.py"), ("l3", "z/c.py")):
        if name == live_name:
            continue
        _commit(_finish(wave_path, name, ""), {rel: f"# {name}\n"}, f"{name} change")
    live = _spawn_tagged_incumbent()
    try:
        # Every lane is checked - first, middle or last - and the refusal names it.
        _set_pid(wave_path, live_name, live.pid)
        before = wave_path.read_text(encoding="utf-8")
        assert wave_assemble.assemble(repo, wave_path, run_checks=_checks_pass) == 1
    finally:
        live.kill()
        live.wait(10)
    err = capsys.readouterr().err
    assert f"lane {live_name} is still running - wait or abort" in err
    assert wave_path.read_text(encoding="utf-8") == before
    wave_id = wave.load(wave_path)["id"]
    assert _git(repo, "branch", "--list", f"wave/{wave_id}/assembly").stdout == ""
    assert not (tmp_path / f"proj-wave-{wave_id}").exists()


def test_assemble_records_each_lanes_files_and_integrator_trailers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, wave_path = _launched(tmp_path, monkeypatch, 3, {"src/shared.py": "v = 0\n"})
    _commit(_finish(wave_path, "l1", ""), {"x/a.py": "# l1\n"}, "l1 change")
    worktree = _finish(wave_path, "l2", "")
    first = {"y/b.py": "# l2\n", "docs/l2.md": "l2\n"}
    _commit(worktree, first, "l2 first", "mentions Integrator: inline, not a trailer")
    noted = _commit(
        worktree,
        {"src/shared.py": "v = 2\n"},
        "l2 second",
        "Integrator: kept l2's value over the seed",
    )
    # The trailer sits mid-range: l2's tip commit after it carries none.
    _commit(worktree, {"y/b.py": "# l2 tip\n"}, "l2 third")
    # l3 edits the line l2 already changed: it conflicts and is kept.
    kept_files = {"src/shared.py": "v = 3\n", "z/c.py": "# l3\n"}
    kept = _commit(
        _finish(wave_path, "l3", ""),
        kept_files,
        "l3 change",
        "Integrator: l3 wanted value 3",
    )
    wave_assemble.assemble(repo, wave_path, run_checks=_checks_pass)
    saved, lanes = _saved(repo, wave_path)
    assert [lanes[name]["status"] for name in ("l1", "l2", "l3")] == [
        "assembled",
        "assembled",
        "conflict",
    ]
    assert lanes["l2"]["files"] == ["docs/l2.md", "src/shared.py", "y/b.py"]
    assert lanes["l2"]["integrator_notes"] == [
        {"sha": noted[:7], "text": "kept l2's value over the seed"},
    ]
    # The rebase onto l1 rewrote l2's commits; the note names the one l2 wrote.
    ref = f"wave/{saved['id']}/assembly"
    assert _git(repo, "log", "-1", "--format=%s", ref).stdout.strip() == "l2 third"
    grep = ["log", "--format=%H", "--grep=^l2 second$", ref]
    rewritten = _git(repo, *grep).stdout.split()
    assert len(rewritten) == 1
    assert rewritten[0] != noted
    assert lanes["l3"]["files"] == ["src/shared.py", "z/c.py"]
    assert lanes["l3"]["integrator_notes"] == [
        {"sha": kept[:7], "text": "l3 wanted value 3"},
    ]


# ── docs: the assembly_conflict slug and the wave summary report ────────


_SKILL_ROOT = Path(__file__).resolve().parent.parent
_RECOVERY = _SKILL_ROOT / "references" / "recovery.md"
_BATCH_REPORT_FORMAT = _SKILL_ROOT / "references" / "batch-report-format.md"
_SKILL_MD = _SKILL_ROOT / "SKILL.md"
_WAVE_REPORT = "reports/<wave id>-wave.md"


def _section(text: str, heading: str) -> str:
    """`text` from `heading` (on its own line) to the next `#`-heading line."""
    marker = f"\n{heading}\n"
    assert marker in text, f"no {heading!r} section"
    body = text[text.index(marker) + len(marker) :]
    end = re.search(r"\n#{1,6} ", body)
    return body if end is None else body[: end.start()]


def _bullet(section: str, marker: str) -> str:
    """The top-level bullet in `section` starting with `marker`, up to the next
    top-level bullet or the section end."""
    assert marker in section, f"no {marker!r} bullet"
    body = section[section.index(marker) :]
    end = re.search(r"\n- ", body[1:])
    return body if end is None else body[: end.start() + 1]


def test_docs_name_the_site_and_the_summary() -> None:
    slugs = _section(_RECOVERY.read_text(encoding="utf-8"), "### Stall `site` slugs")
    bullet = _bullet(slugs, "- `assembly_conflict`").lower()
    sentences = _sentences(bullet)
    assert _claims(sentences, "assemble", "itself", "verb", "directly", "command"), (
        f"{_RECOVERY}: `assembly_conflict` bullet does not credit the assemble "
        "verb itself with writing this stall site"
    )
    assert _claims(sentences, "session", "no ", "not ", "without ", "never "), (
        f"{_RECOVERY}: `assembly_conflict` bullet does not say no session backs it"
    )
    assert _claims(sentences, "state.json", "no ", "not ", "without ", "never "), (
        f"{_RECOVERY}: `assembly_conflict` bullet does not say no state.json backs it"
    )

    batch_text = _BATCH_REPORT_FORMAT.read_text(encoding="utf-8")
    headings = re.findall(r"\n(## [^\n]*)\n", batch_text)
    heading = next(
        (h for h in headings if "wave" in h.lower() and "summar" in h.lower()),
        None,
    )
    assert heading is not None, (
        f"{_BATCH_REPORT_FORMAT}: no `## `-level heading names the wave summary"
    )
    wave_section = _section(batch_text, heading).lower()
    assert _claims(_sentences(wave_section), _WAVE_REPORT, "summar"), (
        f"{_BATCH_REPORT_FORMAT}: {heading!r} does not document {_WAVE_REPORT} as "
        "a report type alongside the per-batch report"
    )

    retention = _section(_SKILL_MD.read_text(encoding="utf-8"), "### Retention")
    assert _WAVE_REPORT in _bullet(retention, "- **Durable**"), (
        f"{_SKILL_MD}: § Retention Durable bullet does not list {_WAVE_REPORT}"
    )
    for other in ("- **Not durable", "- **Disposable**"):
        assert _WAVE_REPORT not in _bullet(retention, other), (
            f"{_SKILL_MD}: § Retention lists {_WAVE_REPORT} outside the Durable bullet"
        )
