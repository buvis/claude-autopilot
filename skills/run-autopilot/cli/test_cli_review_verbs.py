#!/usr/bin/env python3
"""Tests for the `review-stage` and `review-close` CLI verbs (PRD 00249 task 5).

Both handlers are thin wrappers: stage() and close() have their own suites
(test_review_stage.py, test_review_close.py), so these tests swap them for
recorders and prove only the CLI side - registration, how the inputs are
built (autopilot mode reads state.json, standalone mode reads flags), the
one-line JSON print, and the exit codes.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from cli import review_close, review_stage, verification
from cli.__main__ import _SUBCOMMANDS, main

PRD = "00249-x-v1.md"
DESIGN_REL = "docs/dev/project-management/designs/00249-x-v1-design.md"
GATE = "make test"
TASKS = [{"id": "1", "name": "first", "status": "completed"}]


def _state(tmp_path: Path, **extra: object) -> Path:
    autopilot = tmp_path / "docs/dev/project-management/autopilot"
    autopilot.mkdir(parents=True)
    path = autopilot / "state.json"
    data = {"prd": PRD, "phase": "review", "tasks": TASKS, **extra}
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@pytest.fixture
def staged(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Swap stage() for a recorder; `result` is what it returns."""
    seen: dict = {"result": {"ok": True, "mode": "autopilot"}}

    def fake_stage(*args, **kwargs) -> dict:
        seen["args"], seen["kwargs"] = args, kwargs
        return seen["result"]

    monkeypatch.setattr(review_stage, "stage", fake_stage)
    return seen


@pytest.fixture
def closed(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Swap close() for a recorder; `result` is what it returns."""
    seen: dict = {"result": {"applied": True, "tasks_created": ["2"]}}

    def fake_close(*args, **kwargs) -> dict:
        seen["args"], seen["kwargs"] = args, kwargs
        return seen["result"]

    monkeypatch.setattr(review_close, "close", fake_close)
    return seen


def _stage_argv(tmp_path: Path, *extra: str) -> list[str]:
    return [
        "review-stage",
        "--cycle-id",
        "00249-c1",
        "--gate-command",
        GATE,
        "--repo-root",
        str(tmp_path),
        *extra,
    ]


@pytest.mark.parametrize("verb", ["review-stage", "review-close"])
def test_cli_registers_review_stage_and_close(
    verb: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert verb in _SUBCOMMANDS
    with pytest.raises(SystemExit) as exc:
        main([verb, "--help"])
    assert exc.value.code == 0
    assert verb in capsys.readouterr().out


def test_review_stage_builds_autopilot_inputs_from_state(
    tmp_path: Path, staged: dict, capsys: pytest.CaptureFixture[str]
) -> None:
    state_path = _state(
        tmp_path,
        design_doc=DESIGN_REL,
        review_lenses={"consensus": "done", "blind": "done", "doubt": "done"},
        doubt_reviewer="codex",
    )

    code = main(_stage_argv(tmp_path, "--state", str(state_path), "--since", "abc"))

    assert code == 0
    kwargs = staged["kwargs"]
    assert kwargs["cycle_id"] == "00249-c1"
    assert kwargs["tasks"] == TASKS
    assert kwargs["prd_path"] == state_path.parents[1] / "prds" / "wip" / PRD
    assert kwargs["design_doc"] == tmp_path / DESIGN_REL
    assert kwargs["roster"] == ["alice", "bob", "carl", "blake"]
    assert kwargs["repo_root"] == tmp_path
    assert kwargs["gate_command"] == GATE
    assert kwargs["replay_cmd"] is None
    assert kwargs["since"] == "abc"
    assert kwargs["state_path"] == state_path
    assert json.loads(capsys.readouterr().out) == staged["result"]


def test_review_stage_fable_doubt_reviewer_puts_eve_on_the_roster(
    tmp_path: Path, staged: dict
) -> None:
    # No review_lenses yet (first cycle): the standard lenses, plus Eve.
    state_path = _state(tmp_path, doubt_reviewer="fable")

    assert main(_stage_argv(tmp_path, "--state", str(state_path))) == 0

    assert staged["kwargs"]["roster"] == ["alice", "bob", "carl", "blake", "eve"]


def test_review_stage_codex_implemented_task_forces_eve_onto_the_roster(
    tmp_path: Path, staged: dict
) -> None:
    # review-work-completion's codex doubt-roster guard: the doubt leg must
    # not be codex alone, whatever state.doubt_reviewer says.
    tasks = [{"id": "1", "attempts": [{"implementor": "codex"}]}]
    state_path = _state(tmp_path, tasks=tasks, doubt_reviewer="codex")

    assert main(_stage_argv(tmp_path, "--state", str(state_path))) == 0

    assert staged["kwargs"]["roster"] == ["alice", "bob", "carl", "blake", "eve"]


def test_review_stage_roster_flag_overrides_the_state_roster(
    tmp_path: Path, staged: dict
) -> None:
    state_path = _state(tmp_path)

    code = main(_stage_argv(tmp_path, "--state", str(state_path), "--roster", "blake"))

    assert code == 0
    assert staged["kwargs"]["roster"] == ["blake"]


@pytest.mark.parametrize("flag", ["--tasks-json", "--prd", "--design-doc"])
def test_review_stage_refuses_standalone_inputs_beside_state(
    tmp_path: Path, staged: dict, flag: str, capsys: pytest.CaptureFixture[str]
) -> None:
    state_path = _state(tmp_path)

    code = main(_stage_argv(tmp_path, "--state", str(state_path), flag, "x"))

    assert code == 1
    assert "args" not in staged
    assert flag in capsys.readouterr().err


def test_review_stage_standalone_reads_flags_and_skips_state(
    tmp_path: Path, staged: dict
) -> None:
    tasks_json = tmp_path / "tasks.json"
    tasks_json.write_text(json.dumps(TASKS), encoding="utf-8")
    prd = tmp_path / PRD

    code = main(
        _stage_argv(
            tmp_path,
            "--tasks-json",
            str(tasks_json),
            "--prd",
            str(prd),
            "--roster",
            "alice, blake,alice",
            "--replay-cmd",
            "pytest",
        )
    )

    assert code == 0
    kwargs = staged["kwargs"]
    assert kwargs["tasks"] == TASKS
    assert kwargs["prd_path"] == prd
    assert kwargs["design_doc"] is None
    assert kwargs["roster"] == ["alice", "blake"]
    assert kwargs["replay_cmd"] == "pytest"
    assert kwargs["state_path"] is None


@pytest.mark.parametrize("missing", ["--tasks-json", "--prd", "--roster"])
def test_review_stage_standalone_refuses_without_its_inputs(
    tmp_path: Path,
    staged: dict,
    missing: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    tasks_json = tmp_path / "tasks.json"
    tasks_json.write_text("[]", encoding="utf-8")
    flags = {"--tasks-json": str(tasks_json), "--prd": "p.md", "--roster": "alice"}
    del flags[missing]

    code = main(_stage_argv(tmp_path, *[x for kv in flags.items() for x in kv]))

    assert code == 1
    assert "args" not in staged
    assert missing in capsys.readouterr().err


def test_review_stage_propagates_a_gather_refusal_exit(
    tmp_path: Path, staged: dict, capsys: pytest.CaptureFixture[str]
) -> None:
    staged["result"] = {"ok": False, "error": "empty diff", "exit": 3}

    code = main(_stage_argv(tmp_path, "--state", str(_state(tmp_path))))

    assert code == 3
    captured = capsys.readouterr()
    assert json.loads(captured.out) == staged["result"]
    assert "empty diff" in captured.err


def _findings(tmp_path: Path, payload: object) -> Path:
    path = tmp_path / "findings.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _close_argv(tmp_path: Path, findings: Path, *extra: str) -> list[str]:
    return [
        "review-close",
        "--review-file",
        str(tmp_path / "review.md"),
        "--state",
        str(tmp_path / "state.json"),
        "--batch-id",
        "decision-gate",
        "--findings",
        str(findings),
        *extra,
    ]


def test_review_close_passes_findings_through_and_exits_zero_when_applied(
    tmp_path: Path, closed: dict, capsys: pytest.CaptureFixture[str]
) -> None:
    chosen = [
        {
            "severity": "\U0001f534",
            "file": "a.py",
            "issue": "i",
            "classification": "fix",
            "found_by": ["alice"],
        }
    ]
    findings = _findings(tmp_path, chosen)

    code = main(_close_argv(tmp_path, findings, "--default-tier", "opus"))

    assert code == 0
    assert closed["args"] == (
        tmp_path / "review.md",
        tmp_path / "state.json",
        "decision-gate",
        chosen,
        "opus",
    )
    assert json.loads(capsys.readouterr().out) == closed["result"]


def test_review_close_exits_nonzero_with_the_reason_when_not_applied(
    tmp_path: Path, closed: dict, capsys: pytest.CaptureFixture[str]
) -> None:
    closed["result"] = {"applied": False, "reason": "already applied"}

    code = main(_close_argv(tmp_path, _findings(tmp_path, [])))

    assert code != 0
    captured = capsys.readouterr()
    assert json.loads(captured.out) == closed["result"]
    assert "already applied" in captured.err


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({"classification": "fix"}, id="not_a_list"),
        pytest.param(["fix"], id="element_not_a_dict"),
        pytest.param([{"file": "a.py"}], id="no_classification"),
    ],
)
def test_review_close_refuses_a_malformed_findings_file_before_close(
    tmp_path: Path, closed: dict, payload: object
) -> None:
    code = main(_close_argv(tmp_path, _findings(tmp_path, payload)))

    assert code == 2
    assert "args" not in closed


def test_review_close_rejects_an_unknown_batch_id(tmp_path: Path) -> None:
    argv = _close_argv(tmp_path, _findings(tmp_path, []))
    argv[argv.index("decision-gate")] = "cycle-3"

    with pytest.raises(SystemExit) as exc:
        main(argv)
    assert exc.value.code == 1


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@example.com",
            "-c",
            "commit.gpgsign=false",
            *args,
        ],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print(1)\n")
    (tmp_path / ".gitignore").write_text("docs/dev/tmp/\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "--no-verify", "-q", "-m", "init")
    return tmp_path


def test_verify_runs_the_gate_once_and_writes_the_record_and_log(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(
        [
            "verify",
            "--gate-command",
            "echo 'out'; echo 'PASS 1 FAIL 0 SKIP 0 EXIT 0'",
            "--repo-root",
            str(repo),
            "--cycle",
            "3",
        ]
    )

    assert code == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["passed"] == 1
    assert printed["recorded"] is True
    assert printed["dirty"] is False
    log_path = Path(printed["log"])
    assert log_path.exists()
    assert b"out" in log_path.read_bytes()
    record_path = repo / "docs/dev/project-management/autopilot/last-verification.json"
    assert record_path.exists()


def test_verify_exits_1_on_a_red_gate(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(
        [
            "verify",
            "--gate-command",
            "echo 'PASS 1 FAIL 1 SKIP 0 EXIT 1'; exit 1",
            "--repo-root",
            str(repo),
        ]
    )

    assert code == 1
    printed = json.loads(capsys.readouterr().out)
    assert printed["exit"] == 1


def test_verify_writes_no_record_on_a_dirty_tree(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (repo / "src" / "app.py").write_text("print('dirty')\n")

    code = main(
        [
            "verify",
            "--gate-command",
            "echo 'PASS 1 FAIL 0 SKIP 0 EXIT 0'",
            "--repo-root",
            str(repo),
        ]
    )

    assert code == 1
    printed = json.loads(capsys.readouterr().out)
    assert printed["dirty"] is True
    assert printed["recorded"] is False
    record_path = repo / "docs/dev/project-management/autopilot/last-verification.json"
    assert not record_path.exists()


def test_verify_dirtied_during_the_run_still_reports_the_process_exit(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Dirtying the tree mid-run suppresses the record and must also change
    # the verb's exit code: exit 0 now means "green and recorded", and a
    # dirty, unrecorded run is never that, whatever the gate command itself
    # exited with. It still ran and the gate itself exited 0 with no
    # timeout, so this is the same "green but unrecorded" case as any other
    # unrecorded run: exit 3, not the generic process-failure exit 1.
    command = "echo dirty > src/dirty.py; echo 'PASS 1 FAIL 0 SKIP 0 EXIT 0'"

    code = main(
        [
            "verify",
            "--gate-command",
            command,
            "--repo-root",
            str(repo),
        ]
    )

    assert code == 3
    printed = json.loads(capsys.readouterr().out)
    assert printed["recorded"] is False
    assert printed["dirty"] is True
    record_path = repo / "docs/dev/project-management/autopilot/last-verification.json"
    assert not record_path.exists()


def test_verify_exits_2_outside_a_git_repo(tmp_path: Path) -> None:
    code = main(
        [
            "verify",
            "--gate-command",
            "echo 'PASS 1 FAIL 0 SKIP 0 EXIT 0'",
            "--repo-root",
            str(tmp_path),
        ]
    )

    assert code == 2


def test_verify_exits_2_when_head_resolution_raises_oserror(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A missing git binary (or any other OSError the HEAD-resolution
    # subprocess.run call can raise) must exit 2 like every other verify
    # failure, not crash with a bare traceback.
    import subprocess as subprocess_module

    real_run = subprocess_module.run

    def _boom(args, **kwargs):
        if args[:2] == ["git", "rev-parse"]:
            raise FileNotFoundError("git: command not found")
        return real_run(args, **kwargs)

    monkeypatch.setattr(subprocess_module, "run", _boom)

    code = main(
        [
            "verify",
            "--gate-command",
            "echo 'PASS 1 FAIL 0 SKIP 0 EXIT 0'",
            "--repo-root",
            str(tmp_path),
        ]
    )

    assert code == 2


GREEN = "echo 'out'; echo 'PASS 1 FAIL 0 SKIP 0 EXIT 0'"
RECORD_REL = "docs/dev/project-management/autopilot/last-verification.json"


def _verify_argv(repo: Path, *extra: str) -> list[str]:
    return ["verify", "--gate-command", GREEN, "--repo-root", str(repo), *extra]


def test_rejects_log_path_resolving_to_record(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(_verify_argv(repo)) == 0
    record = repo / RECORD_REL
    before = record.read_bytes()
    capsys.readouterr()

    code = main(_verify_argv(repo, "--log", str(record)))

    assert code == 2
    captured = capsys.readouterr()
    assert f"--log {record} resolves inside the store" in captured.err
    assert captured.out == ""
    assert record.read_bytes() == before


def test_verify_rejects_a_relative_log_that_resolves_inside_the_store(
    repo: Path,
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # `..` climbs out of the gitignored tmp dir into the store; the check
    # must judge where the path lands, joined to --repo-root, not its text.
    scratch = tmp_path_factory.mktemp("elsewhere")
    monkeypatch.chdir(scratch)
    arg = "docs/dev/tmp/../project-management/somewhere.log"

    code = main(_verify_argv(repo, "--log", arg))

    assert code == 2
    assert f"--log {arg} resolves inside the store" in capsys.readouterr().err
    assert not (repo / "docs/dev/project-management/somewhere.log").exists()
    assert not (scratch / "docs/dev/project-management/somewhere.log").exists()
    assert not (repo / RECORD_REL).exists()


def test_verify_rejects_a_store_resolving_log_even_when_also_tracked(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # The store check is the only CLI-level refusal: a log that resolves
    # inside the store is rejected whether or not it happens to be tracked.
    notes = repo / "docs/dev/project-management/notes.md"
    notes.parent.mkdir(parents=True)
    notes.write_text("keep me\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "--no-verify", "-q", "-m", "notes")

    code = main(_verify_argv(repo, "--log", str(notes)))

    assert code == 2
    assert "resolves inside the store" in capsys.readouterr().err
    assert notes.read_text() == "keep me\n"


def test_verify_a_tracked_log_outside_the_store_is_not_refused_but_cannot_record(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # A tracked destination outside the store is not refused up front (that
    # extra guard was scope creep beyond the spec's store-only check) -- the
    # gate runs, but writing through a tracked file is itself an edit, so
    # the post-run dirty check still blocks the record: exit 3, same as any
    # other green-but-unrecorded run.
    tracked = repo / "src" / "app.py"
    before = tracked.read_bytes()

    code = main(_verify_argv(repo, "--log", str(tracked)))

    assert code == 3
    printed = json.loads(capsys.readouterr().out)
    assert printed["recorded"] is False
    assert printed["dirty"] is True
    assert tracked.read_bytes() != before
    assert not (repo / RECORD_REL).exists()


def test_verify_accepts_an_untracked_log_outside_docs_dev_tmp(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # "Tracked" means git tracks it, not "outside docs/dev/tmp": a never
    # git-added file under src/ is a valid log target.
    log = repo / "src" / "new.log"

    code = main(_verify_argv(repo, "--log", str(log)))

    assert code == 0
    printed = json.loads(capsys.readouterr().out)
    assert Path(printed["log"]).resolve() == log.resolve()
    assert b"out" in log.read_bytes()


def test_verify_a_force_added_tracked_log_under_docs_dev_tmp_still_records(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # docs/dev/tmp is gitignored, but a force-added file there is tracked.
    # It is also one of the store prefixes (scratch is never dirt, tracked
    # or not), and outside docs/dev/project-management, so neither the CLI
    # store check nor the dirty check touches it: the gate records.
    forced = repo / "docs/dev/tmp/forced.log"
    forced.parent.mkdir(parents=True)
    forced.write_text("keep me\n")
    _git(repo, "add", "-f", "docs/dev/tmp/forced.log")
    _git(repo, "commit", "--no-verify", "-q", "-m", "forced")

    code = main(_verify_argv(repo, "--log", str(forced)))

    assert code == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["recorded"] is True
    assert printed["dirty"] is False
    assert forced.read_text() != "keep me\n"


def test_verify_rejects_a_symlinked_log_that_points_at_the_record(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # The store check must resolve symlinks: the link's own path sits in
    # the gitignored tmp dir, but writing through it would clobber the record.
    assert main(_verify_argv(repo)) == 0
    record = repo / RECORD_REL
    before = record.read_bytes()
    capsys.readouterr()
    link = repo / "docs/dev/tmp/link.log"
    link.symlink_to(record)

    code = main(_verify_argv(repo, "--log", str(link)))

    assert code == 2
    captured = capsys.readouterr()
    assert "resolves inside the store" in captured.err
    assert captured.out == ""
    assert record.read_bytes() == before


def test_verify_accepts_a_store_like_path_outside_the_repo(
    repo: Path,
    tmp_path_factory: pytest.TempPathFactory,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # The store is <repo>/docs/dev/project-management, not any directory
    # that happens to share its name elsewhere on disk.
    scratch = tmp_path_factory.mktemp("outside")
    log = scratch / "docs/dev/project-management" / "x.log"
    assert not log.resolve().is_relative_to(repo.resolve())

    code = main(_verify_argv(repo, "--log", str(log)))

    assert code == 0
    printed = json.loads(capsys.readouterr().out)
    assert Path(printed["log"]).resolve() == log.resolve()
    assert b"out" in log.read_bytes()


def test_verify_writes_an_absolute_out_of_repo_log_where_asked(
    repo: Path,
    tmp_path_factory: pytest.TempPathFactory,
    capsys: pytest.CaptureFixture[str],
) -> None:
    scratch = tmp_path_factory.mktemp("abslog")
    log = scratch / "gate.log"

    code = main(_verify_argv(repo, "--log", str(log)))

    assert code == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["recorded"] is True
    assert Path(printed["log"]).resolve() == log.resolve()
    assert b"out" in log.read_bytes()
    assert list(repo.rglob("*.log")) == []


def test_relative_log_resolves_against_repo_root(
    repo: Path,
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    scratch = tmp_path_factory.mktemp("elsewhere")
    monkeypatch.chdir(scratch)
    rel = "docs/dev/tmp/custom/out.log"

    code = main(_verify_argv(repo, "--log", rel))

    assert code == 0
    printed = json.loads(capsys.readouterr().out)
    assert Path(printed["log"]).resolve() == (repo / rel).resolve()
    assert b"out" in (repo / rel).read_bytes()
    assert not (scratch / rel).exists()


def test_verify_untracked_log_outside_the_store_still_works(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    log = repo / "docs/dev/tmp/custom.log"

    code = main(_verify_argv(repo, "--log", str(log)))

    assert code == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["recorded"] is True
    assert Path(printed["log"]).resolve() == log.resolve()
    assert b"out" in log.read_bytes()
    assert (repo / RECORD_REL).exists()


def test_verify_exits_2_when_the_log_cannot_be_opened(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # The log's parent is a plain file, so opening the log raises OSError:
    # the verb prints {sha, log, error} and exits 2, writing no record.
    blocker = repo / "docs/dev/tmp/blocker"
    blocker.parent.mkdir(parents=True)
    blocker.write_text("not a dir\n")
    log = blocker / "gate.log"

    code = main(_verify_argv(repo, "--log", str(log)))

    assert code == 2
    printed = json.loads(capsys.readouterr().out)
    assert set(printed) == {"sha", "log", "error"}
    assert Path(printed["log"]).resolve() == log.resolve()
    assert printed["error"]
    assert not (repo / RECORD_REL).exists()


def _green_result(**overrides: object) -> dict:
    """A run_gate result shaped exactly like a real green, clean, recorded
    run, with `overrides` applied."""
    return {
        "passed": 1,
        "failed": 0,
        "skipped": 0,
        "exit": 0,
        "raw_line": "PASS 1 FAIL 0 SKIP 0 EXIT 0",
        "timed_out": False,
        "recorded": True,
        "dirty": False,
        "dirty_paths": [],
        **overrides,
    }


def test_verify_exits_3_when_green_but_unrecorded(
    repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # No black-box trigger for a green, clean, unrecorded run is known
    # without reading run_gate, so the result is hand-built (the task
    # brief allows this for this one test).
    result = _green_result(recorded=False)
    monkeypatch.setattr(verification, "run_gate", lambda *a, **kw: dict(result))

    code = main(_verify_argv(repo))

    assert code == 3
    printed = json.loads(capsys.readouterr().out)
    assert printed["recorded"] is False
    assert printed["exit"] == 0
    assert printed["dirty_paths"] == []


def test_verify_exits_0_when_the_same_green_result_is_recorded(
    repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Mirror of the exit-3 test: only `recorded` differs, so exit 3 must
    # hinge on that field, not on any key's presence.
    result = _green_result()
    monkeypatch.setattr(verification, "run_gate", lambda *a, **kw: dict(result))

    code = main(_verify_argv(repo))

    assert code == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["recorded"] is True


def test_verify_exits_1_when_the_gate_timed_out_with_exit_0(
    repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = _green_result(timed_out=True, recorded=False)
    monkeypatch.setattr(verification, "run_gate", lambda *a, **kw: dict(result))

    code = main(_verify_argv(repo))

    assert code == 1
    printed = json.loads(capsys.readouterr().out)
    assert printed["timed_out"] is True


def test_verify_prints_the_dirty_paths(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (repo / "src" / "other.py").write_text("print('dirty')\n")

    code = main(_verify_argv(repo))

    assert code == 1
    printed = json.loads(capsys.readouterr().out)
    assert printed["dirty_paths"] == ["src/other.py"]
