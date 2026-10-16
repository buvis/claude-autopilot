#!/usr/bin/env python3
"""Tests for the `verify` CLI verb: the gate run, the record and log it
writes, the --log store refusal, and the exit codes. Split out of
test_cli_review_verbs.py to keep each file under the style limit.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from cli import verification
from cli.__main__ import main


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
    lines = captured.out.splitlines()
    assert len(lines) == 1
    printed = json.loads(lines[0])
    assert "resolves inside the store" in printed["error"]
    assert printed["exit"] == 2
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


def test_verify_refuses_a_tracked_log_outside_the_store(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # PRD 00320 refuses a tracked --log destination anywhere in the repo,
    # not only one inside the store: the gate never runs and the tracked
    # file keeps its bytes.
    tracked = repo / "src" / "app.py"
    before = tracked.read_bytes()

    code = main(_verify_argv(repo, "--log", str(tracked)))

    assert code == 2
    captured = capsys.readouterr()
    assert captured.err.strip().endswith("is tracked")
    printed = json.loads(captured.out)
    assert printed["error"].endswith("is tracked")
    assert printed["exit"] == 2
    assert tracked.read_bytes() == before
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


def test_verify_refuses_a_force_added_tracked_log_under_docs_dev_tmp(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # docs/dev/tmp is gitignored, but a force-added file there is tracked,
    # and PRD 00320 refuses a tracked sink wherever it sits -- the scratch
    # prefix does not excuse it.
    forced = repo / "docs/dev/tmp/forced.log"
    forced.parent.mkdir(parents=True)
    forced.write_text("keep me\n")
    _git(repo, "add", "-f", "docs/dev/tmp/forced.log")
    _git(repo, "commit", "--no-verify", "-q", "-m", "forced")

    code = main(_verify_argv(repo, "--log", str(forced)))

    assert code == 2
    captured = capsys.readouterr()
    assert captured.err.strip().endswith("is tracked")
    printed = json.loads(captured.out)
    assert printed["error"].endswith("is tracked")
    assert printed["exit"] == 2
    assert forced.read_text() == "keep me\n"


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
    lines = captured.out.splitlines()
    assert len(lines) == 1
    printed = json.loads(lines[0])
    assert "resolves inside the store" in printed["error"]
    assert printed["exit"] == 2
    assert record.read_bytes() == before


def test_verify_refuses_a_store_like_path_outside_the_repo(
    repo: Path,
    tmp_path_factory: pytest.TempPathFactory,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # PRD 00320 refuses any sink that resolves outside this repository, so a
    # directory elsewhere on disk that merely shares the store's name is
    # refused for being outside, not for looking like the store.
    scratch = tmp_path_factory.mktemp("outside")
    log = scratch / "docs/dev/project-management" / "x.log"
    assert not log.resolve().is_relative_to(repo.resolve())

    code = main(_verify_argv(repo, "--log", str(log)))

    assert code == 2
    captured = capsys.readouterr()
    assert captured.err.strip().endswith("resolves outside the repository")
    printed = json.loads(captured.out)
    assert printed["error"].endswith("resolves outside the repository")
    assert printed["exit"] == 2
    assert not log.exists()


def test_verify_refuses_an_absolute_out_of_repo_log(
    repo: Path,
    tmp_path_factory: pytest.TempPathFactory,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # PRD 00320: an absolute sink outside the repository is refused, and
    # nothing is written at the path it asked for.
    scratch = tmp_path_factory.mktemp("abslog")
    log = scratch / "gate.log"

    code = main(_verify_argv(repo, "--log", str(log)))

    assert code == 2
    captured = capsys.readouterr()
    assert captured.err.strip().endswith("resolves outside the repository")
    printed = json.loads(captured.out)
    assert printed["error"].endswith("resolves outside the repository")
    assert printed["exit"] == 2
    assert not log.exists()
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
        "lock_timeout": False,
        "head_moved": False,
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


def test_verify_exits_1_on_a_nonzero_process_exit_with_no_summary_line(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # No summary line at all, but the process itself failed: is_red must
    # follow the process exit, not just the (absent) parsed summary.
    code = main(_verify_argv(repo, "--gate-command", "echo build failed; exit 2"))

    assert code == 1
    printed = json.loads(capsys.readouterr().out)
    assert printed["exit"] == 2
    assert printed["raw_line"] is None


def test_verify_exits_1_on_a_nonzero_process_exit_despite_a_green_summary(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # A green summary line can't paper over a nonzero process exit: the
    # gate command itself failed after printing the summary.
    command = "echo 'PASS 1 FAIL 0 SKIP 0 EXIT 0'; exit 5"

    code = main(_verify_argv(repo, "--gate-command", command))

    assert code == 1
    printed = json.loads(capsys.readouterr().out)
    assert printed["exit"] == 5


def test_verify_prints_the_dirty_paths(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (repo / "src" / "other.py").write_text("print('dirty')\n")

    code = main(_verify_argv(repo))

    assert code == 1
    printed = json.loads(capsys.readouterr().out)
    assert printed["dirty_paths"] == ["src/other.py"]
