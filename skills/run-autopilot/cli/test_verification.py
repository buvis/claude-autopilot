#!/usr/bin/env python3
"""Tests for cli/verification.py (PRD 00249 task 1).

The reuse checks run against real temporary git repos: the point is to bind
real git behavior (ancestry, diff paths, dirty tree), not a mock of it.
"""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import time
from pathlib import Path

import pytest

from cli import verification

STORE = "docs/dev/project-management"
RECORD_REL = Path(STORE) / "autopilot" / "last-verification.json"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
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
    ).stdout.strip()


def _commit(repo: Path, rel: str, body: str = "x\n") -> str:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    _git(repo, "add", "--", rel)
    _git(repo, "commit", "--no-verify", "-q", "-m", f"touch {rel}")
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    _commit(tmp_path, "src/app.py", "print(1)\n")
    return tmp_path


def _record(sha: object, passed=5, failed=0, skipped=1) -> dict:
    return {
        "sha": sha,
        "cycle": 1,
        "commands": [{"command": "dev/bin/release-checks", "exit": 0}],
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
    }


def test_reuse_when_only_store_paths_changed(repo: Path) -> None:
    base = _git(repo, "rev-parse", "HEAD")
    _commit(repo, f"{STORE}/autopilot/state.json", "{}\n")
    head = _commit(repo, f"{STORE}/reviews/r1.md", "review\n")
    record = _record(base)

    assert verification.reuse_verdict(record, repo, head) == ("reused", record)
    # An empty diff (record at HEAD itself) is vacuously store-only.
    same = _record(head)
    assert verification.reuse_verdict(same, repo, head) == ("reused", same)


def test_stale_when_code_changed(repo: Path) -> None:
    base = _git(repo, "rev-parse", "HEAD")
    _commit(repo, f"{STORE}/autopilot/state.json", "{}\n")
    head = _commit(repo, "src/app.py", "print(2)\n")

    assert verification.reuse_verdict(_record(base), repo, head) == ("stale", {})

    # Any path outside the store counts, not only the ones under src/.
    later = _commit(repo, "Makefile", "all:\n\t@true\n")
    assert verification.reuse_verdict(_record(head), repo, later) == ("stale", {})


@pytest.mark.parametrize("field", ["passed", "failed", "skipped"])
def test_stale_when_counts_null(repo: Path, field: str) -> None:
    head = _git(repo, "rev-parse", "HEAD")
    nulled = _record(head)
    nulled[field] = None
    missing = _record(head)
    del missing[field]

    assert verification.reuse_verdict(nulled, repo, head) == ("stale", {})
    assert verification.reuse_verdict(missing, repo, head) == ("stale", {})


def test_reuse_verdict_fails_closed_on_git_error(repo: Path, tmp_path_factory) -> None:
    head = _git(repo, "rev-parse", "HEAD")
    not_a_repo = tmp_path_factory.mktemp("plain")

    assert verification.reuse_verdict(None, repo, head) == ("stale", {})
    assert verification.reuse_verdict(_record(""), repo, head) == ("stale", {})
    no_sha = _record(head)
    del no_sha["sha"]
    assert verification.reuse_verdict(no_sha, repo, head) == ("stale", {})
    assert verification.reuse_verdict(_record(123), repo, head) == ("stale", {})
    unknown = _record("0123456789abcdef0123456789abcdef01234567")
    assert verification.reuse_verdict(unknown, repo, head) == ("stale", {})
    assert verification.reuse_verdict(_record("no-such-ref"), repo, head) == (
        "stale",
        {},
    )
    assert verification.reuse_verdict(_record(head), not_a_repo, head) == ("stale", {})


def test_reuse_verdict_rejects_non_ancestor_sha(repo: Path) -> None:
    root = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "-b", "side")
    sibling = _commit(repo, f"{STORE}/notes/side.md", "side\n")
    _git(repo, "checkout", "-q", "-")
    head = _commit(repo, f"{STORE}/notes/main.md", "main\n")

    # Sibling commit (survived a reset/rebase): not an ancestor of HEAD.
    assert verification.reuse_verdict(_record(sibling), repo, head) == ("stale", {})
    # Descendant: record newer than the HEAD being checked.
    assert verification.reuse_verdict(_record(head), repo, root) == ("stale", {})


def test_reuse_verdict_rejects_dirty_tree(repo: Path) -> None:
    head = _git(repo, "rev-parse", "HEAD")
    record = _record(head)
    assert verification.reuse_verdict(record, repo, head) == ("reused", record)

    (repo / "src" / "app.py").write_text("print('dirty')\n")
    assert verification.reuse_verdict(record, repo, head) == ("stale", {})

    _git(repo, "checkout", "--", "src/app.py")
    (repo / "src" / "new.py").write_text("untracked\n")
    assert verification.reuse_verdict(record, repo, head) == ("stale", {})


def test_rename_out_of_store_is_not_clean(repo: Path) -> None:
    store_dir = repo / STORE / "notes"
    store_dir.mkdir(parents=True)
    (store_dir / "old.md").write_text("x\n")
    _git(repo, "add", "--", f"{STORE}/notes/old.md")
    _git(repo, "commit", "--no-verify", "-q", "-m", "add store note")
    head = _git(repo, "rev-parse", "HEAD")
    record = _record(head)
    assert verification.reuse_verdict(record, repo, head) == ("reused", record)

    # Destination at the repo root, outside the store and outside src/.
    _git(repo, "mv", f"{STORE}/notes/old.md", "moved.md")
    assert verification.reuse_verdict(record, repo, head) == ("stale", {})


def test_rename_into_store_from_production_is_not_clean() -> None:
    # A rename into the store from outside it is judged by both endpoints
    # too: a clean destination alone must not excuse a dirty source.
    assert (
        verification._dirty_path_is_in_store(f"{STORE}/moved.md", "production.md")
        is False
    )


def test_copy_record_checks_both_paths() -> None:
    # A copy's status code ("C") can land in either XY column; both of its
    # paths -- the new copy and the source it was copied from -- must be
    # checked, the same as a rename's.
    raw = f"C  {STORE}/dst.md\0src.md\0"
    assert verification._iter_porcelain_z_records(raw) == [
        (f"{STORE}/dst.md", "src.md"),
    ]
    assert verification._dirty_path_is_in_store(f"{STORE}/dst.md", "src.md") is False


def test_blank_status_column_does_not_desync_fields() -> None:
    # A rename/copy code can sit in either XY column: a blank first column
    # (" R") must still be read as a rename and consume the following field
    # as its source path, not misread as an ordinary record and leave the
    # source path to be parsed as its own, separate entry.
    raw = f" R {STORE}/dst.md\0src.md\0 M {STORE}/other.md\0"
    assert verification._iter_porcelain_z_records(raw) == [
        (f"{STORE}/dst.md", "src.md"),
        (f"{STORE}/other.md", None),
    ]


def test_run_gate_drains_stderr_without_deadlock(tmp_path: Path) -> None:
    # Passes against the pre-change code too: `communicate()` already read
    # both pipes concurrently, so this is pre-existing, unchanged behavior,
    # not something the new manual `_drain_bounded` loop had to add -- it
    # only has to not regress it, which this still pins.
    # A child writing far more than one OS pipe buffer's worth to stderr,
    # before it ever prints its stdout summary line: a drain that reads
    # stdout but never stderr would leave the child blocked writing to a
    # full stderr pipe, and run_gate would hang past its deadline.
    command = (
        "head -c 2000000 /dev/zero | tr '\\0' 'e' 1>&2; "
        "echo 'PASS 1 FAIL 0 SKIP 0 EXIT 0'"
    )
    result = verification.run_gate(command, tmp_path, "abc", None, timeout=10)

    assert result["passed"] == 1
    assert result["timed_out"] is False


def test_reuse_verdict_ignores_dirty_paths_under_the_store(repo: Path) -> None:
    store_dir = repo / STORE / "autopilot"
    store_dir.mkdir(parents=True)
    tracked = store_dir / "state.json"
    tracked.write_text("{}\n")
    _git(repo, "add", "--", f"{STORE}/autopilot/state.json")
    _git(repo, "commit", "--no-verify", "-q", "-m", "add store file")
    head = _git(repo, "rev-parse", "HEAD")
    record = _record(head)
    assert verification.reuse_verdict(record, repo, head) == ("reused", record)

    # Dirty a tracked store file and add an untracked one: both ignored.
    tracked.write_text('{"dirty": true}\n')
    (store_dir / "dispatch-metrics.jsonl").write_text("{}\n")
    assert verification.reuse_verdict(record, repo, head) == ("reused", record)

    # A store path that merely contains "src/" in its name is still store.
    nested = store_dir.parent / "notes" / "src"
    nested.mkdir(parents=True)
    (nested / "x.md").write_text("note\n")
    assert verification.reuse_verdict(record, repo, head) == ("reused", record)

    # A non-store path dirty at the same time still makes the record stale.
    (repo / "src" / "app.py").write_text("print('dirty')\n")
    assert verification.reuse_verdict(record, repo, head) == ("stale", {})

    # ... and so does one that lives outside src/ entirely.
    _git(repo, "checkout", "--", "src/app.py")
    (repo / "pyproject.toml").write_text("[project]\n")
    assert verification.reuse_verdict(record, repo, head) == ("stale", {})


def _spy_on_drain(monkeypatch) -> list[dict]:
    """Records every drain call's cap and the tail it handed back, while
    still running the real drain."""
    real = verification._drain_bounded
    calls: list[dict] = []

    def _wrapper(proc, cap, deadline):
        tail, done = real(proc, cap, deadline)
        calls.append({"cap": cap, "tail": tail, "done": done})
        return tail, done

    monkeypatch.setattr(verification, "_drain_bounded", _wrapper)
    return calls


def _popen(command: str) -> subprocess.Popen:
    return subprocess.Popen(
        ["/bin/sh", "-c", command],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )


def test_gate_timeout_default_lets_a_real_suite_finish() -> None:
    # A default deadline of a few seconds would kill every real gate run
    # mid-flight; the suite this gate runs takes minutes.
    assert verification.GATE_TIMEOUT_S >= 600
    assert verification.GATE_OUTPUT_CAP >= 100_000


def test_drain_bounded_keeps_only_the_last_cap_bytes() -> None:
    proc = _popen("printf '%0300d' 0")
    try:
        tail, done = verification._drain_bounded(proc, 64, time.monotonic() + 10)
    finally:
        proc.wait()
        proc.stdout.close()
        proc.stderr.close()

    assert tail == b"0" * 64
    assert done is True


def test_drain_bounded_reports_not_done_for_a_lingering_child() -> None:
    proc = _popen("echo hi; sleep 30")
    try:
        start = time.monotonic()
        tail, done = verification._drain_bounded(proc, 4096, time.monotonic() + 0.5)
        elapsed = time.monotonic() - start
    finally:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait()
        proc.stdout.close()
        proc.stderr.close()

    assert done is False
    assert tail == b"hi\n"
    assert elapsed < 5


def test_run_gate_prints_one_summary_line(tmp_path: Path) -> None:
    command = (
        "printf 'PASS 1 FAIL 1 SKIP 1 EXIT 1\\n"
        "noise PASS x\\n"
        "PASS 12 FAIL 0 SKIP 3 EXIT 0\\n'"
    )
    result = verification.run_gate(command, tmp_path, "abc123", 2)

    assert result == {
        "passed": 12,
        "failed": 0,
        "skipped": 3,
        "exit": 0,
        "raw_line": "PASS 12 FAIL 0 SKIP 3 EXIT 0",
        "timed_out": False,
    }


def test_run_gate_unparseable_output_records_nothing(tmp_path: Path) -> None:
    result = verification.run_gate(
        "echo 'pass 1 fail 0 skip 0 exit 0'; exit 3",
        tmp_path,
        "abc",
        1,
    )

    assert result["passed"] is None
    assert result["failed"] is None
    assert result["skipped"] is None
    assert result["exit"] == 3
    assert result["timed_out"] is False
    assert not (tmp_path / RECORD_REL).exists()

    # A line that merely looks like the summary is not one either.
    near_miss = verification.run_gate(
        "echo 'PASSED 3 of 4 in 5 s 6'",
        tmp_path,
        "abc",
        1,
    )
    assert near_miss["passed"] is None
    assert near_miss["raw_line"] is None
    assert not (tmp_path / RECORD_REL).exists()


def test_run_gate_keeps_tail_so_a_late_summary_line_still_parses(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(verification, "GATE_OUTPUT_CAP", 64)
    calls = _spy_on_drain(monkeypatch)
    # The summary line is always last; a cap that keeps the tail (not the
    # head) of output exceeding GATE_OUTPUT_CAP must still find it, and the
    # bytes beyond the cap really are dropped.
    command = "printf '%0100d\\n' 0; echo 'PASS 1 FAIL 0 SKIP 0 EXIT 0'"
    result = verification.run_gate(command, tmp_path, "abc", None)

    assert result["passed"] == 1
    assert result["failed"] == 0
    assert result["skipped"] == 0
    assert result["raw_line"] == "PASS 1 FAIL 0 SKIP 0 EXIT 0"
    assert (tmp_path / RECORD_REL).exists()
    assert [call["cap"] for call in calls] == [verification.GATE_OUTPUT_CAP]
    assert len(calls[0]["tail"]) <= 64


def test_run_gate_streams_and_keeps_tail(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(verification, "GATE_OUTPUT_CAP", 4096)
    calls = _spy_on_drain(monkeypatch)
    # One unbroken burst, no newlines, far larger than the cap -- proves the
    # drain is byte-bounded as it reads, not only truncated after a full
    # buffered capture: what it hands back never exceeds the cap.
    command = "head -c 2000000 /dev/zero | tr '\\0' 'x'; echo; echo 'PASS 1 FAIL 0 SKIP 0 EXIT 0'"
    result = verification.run_gate(command, tmp_path, "abc", None, timeout=30)

    assert result["passed"] == 1
    assert result["raw_line"] == "PASS 1 FAIL 0 SKIP 0 EXIT 0"
    assert [call["cap"] for call in calls] == [4096]
    assert len(calls[0]["tail"]) <= 4096


# Passes against the pre-change code too: last-match selection over the
# fully captured output is pre-existing, unchanged behavior, not the
# byte-bounded drain this PRD adds (that gap is covered by
# test_run_gate_streams_and_keeps_tail's _drain_bounded spy instead).
def test_run_gate_uses_last_summary_line_not_first(tmp_path: Path) -> None:
    command = "echo 'PASS 1 FAIL 1 SKIP 0 EXIT 1'; echo 'PASS 1 FAIL 0 SKIP 0 EXIT 0'"
    result = verification.run_gate(command, tmp_path, "abc", None)

    assert result["raw_line"] == "PASS 1 FAIL 0 SKIP 0 EXIT 0"
    assert result["failed"] == 0


def test_run_gate_times_out_and_writes_nothing(tmp_path: Path) -> None:
    # `sleep 30; echo` keeps sleep as a child of the shell: killing only the
    # shell would leave sleep holding the pipes open for 30s.
    start = time.monotonic()
    result = verification.run_gate(
        "echo 'PASS 1 FAIL 0 SKIP 0 EXIT 0'; sleep 30; echo done",
        tmp_path,
        "abc",
        1,
        timeout=6,
    )
    elapsed = time.monotonic() - start

    assert result == {
        "passed": None,
        "failed": None,
        "skipped": None,
        "exit": None,
        "raw_line": None,
        "timed_out": True,
    }
    # The deadline tracks the `timeout` argument: waiting out the given 6s
    # (not some constant deadline of its own) and then returning promptly.
    assert 5 < elapsed < 10
    assert not (tmp_path / RECORD_REL).exists()


def test_run_gate_times_out_when_the_child_closes_both_pipes_and_lingers(
    tmp_path: Path,
) -> None:
    # The deadline bounds the process's exit, not just its output: a child
    # that closes stdout AND stderr hits EOF on both pipes immediately, so a
    # drain-only deadline would then wait 30s for the shell to exit.
    start = time.monotonic()
    result = verification.run_gate(
        "exec 1>&-; exec 2>&-; sleep 30",
        tmp_path,
        "abc",
        1,
        timeout=1,
    )
    elapsed = time.monotonic() - start

    assert result == {
        "passed": None,
        "failed": None,
        "skipped": None,
        "exit": None,
        "raw_line": None,
        "timed_out": True,
    }
    # A 1s timeout returns in about 1s: paired with the 6s case above, no
    # single hardcoded deadline can satisfy both bounds.
    assert 0.5 < elapsed < 4
    assert not (tmp_path / RECORD_REL).exists()


def test_reuse_verdict_refuses_a_record_of_a_failed_gate(repo: Path) -> None:
    # Otherwise fully reusable: ancestor sha, only store paths changed since,
    # clean tree. The gate still never certifies HEAD from a red run.
    base = _git(repo, "rev-parse", "HEAD")
    head = _commit(repo, f"{STORE}/autopilot/state.json", "{}\n")
    green = _record(base)
    assert verification.reuse_verdict(green, repo, head) == ("reused", green)

    nonzero_exit = _record(base)
    nonzero_exit["commands"] = [{"command": "dev/bin/release-checks", "exit": 1}]
    assert verification.reuse_verdict(nonzero_exit, repo, head) == ("stale", {})

    some_failed = _record(base, passed=5, failed=2)
    assert verification.reuse_verdict(some_failed, repo, head) == ("stale", {})


def test_reuse_verdict_refuses_a_non_dict_commands_entry(repo: Path) -> None:
    # reuse_verdict fails toward a rerun and never raises, so a record whose
    # commands hold a non-dict entry is stale, not an AttributeError in the
    # caller.
    base = _git(repo, "rev-parse", "HEAD")
    head = _commit(repo, f"{STORE}/autopilot/state.json", "{}\n")

    a_string = _record(base)
    a_string["commands"] = ["x"]
    assert verification.reuse_verdict(a_string, repo, head) == ("stale", {})

    a_null = _record(base)
    a_null["commands"] = [None]
    assert verification.reuse_verdict(a_null, repo, head) == ("stale", {})


def test_reuse_verdict_refuses_an_empty_commands_list(repo: Path) -> None:
    # run_gate always records one entry, so a record with no recorded exit
    # never certifies a green gate -- it is malformed.
    base = _git(repo, "rev-parse", "HEAD")
    head = _commit(repo, f"{STORE}/autopilot/state.json", "{}\n")

    empty = _record(base)
    empty["commands"] = []
    assert verification.reuse_verdict(empty, repo, head) == ("stale", {})


def test_reuse_verdict_docstring_states_the_tolerances_it_applies() -> None:
    doc = (verification.reuse_verdict.__doc__ or "").lower()

    # The empty-porcelain claim is gone: no clause pairs the two any more.
    clauses = re.split(r"[.;\n]", doc)
    assert [c for c in clauses if "porcelain" in c and "empty" in c] == []
    # One clause says dirty paths under the store tree are tolerated.
    assert [c for c in clauses if "docs/dev/project-management/" in c and "dirty" in c]
    # One clause says a rename or copy is judged by both of its endpoints.
    assert [
        c
        for c in clauses
        if ("rename" in c or "copy" in c) and ("both" in c or "endpoint" in c)
    ]


def test_run_gate_closes_the_child_pipes_before_returning(
    tmp_path: Path,
    monkeypatch,
) -> None:
    real_popen = subprocess.Popen
    created: list[subprocess.Popen] = []

    def _spy(*args, **kwargs):
        proc = real_popen(*args, **kwargs)
        created.append(proc)
        return proc

    monkeypatch.setattr(verification.subprocess, "Popen", _spy)
    result = verification.run_gate(
        "echo 'PASS 1 FAIL 0 SKIP 0 EXIT 0'",
        tmp_path,
        "abc",
        1,
    )

    assert result["passed"] == 1
    assert result["timed_out"] is False
    assert len(created) == 1
    proc = created[0]
    assert proc.stdout is not None and proc.stdout.closed
    assert proc.stderr is not None and proc.stderr.closed


def test_run_gate_writes_last_verification_json_on_fresh_run(tmp_path: Path) -> None:
    command = "echo 'PASS 7 FAIL 2 SKIP 1 EXIT 1'; exit 1"
    result = verification.run_gate(command, tmp_path, "deadbeef", 4)

    assert result["exit"] == 1
    written = json.loads((tmp_path / RECORD_REL).read_text())
    assert written == {
        "sha": "deadbeef",
        "cycle": 4,
        "commands": [{"command": command, "exit": 1}],
        "passed": 7,
        "failed": 2,
        "skipped": 1,
    }


def test_run_gate_reports_the_process_exit_not_the_printed_one(
    tmp_path: Path,
) -> None:
    # The command lies about its own status: the gate reports what the
    # process actually exited with.
    command = "echo 'PASS 1 FAIL 0 SKIP 0 EXIT 0'; exit 2"
    result = verification.run_gate(command, tmp_path, "cafe", 1)

    assert result["exit"] == 2
    assert result["passed"] == 1
    written = json.loads((tmp_path / RECORD_REL).read_text())
    assert written["commands"] == [{"command": command, "exit": 2}]


def test_reuse_is_stale_when_the_gate_command_differs(repo: Path) -> None:
    head = _git(repo, "rev-parse", "HEAD")
    record = _record(head)  # recorded from "dev/bin/release-checks"

    same = verification.reuse_verdict(
        record, repo, head, gate_command="dev/bin/release-checks"
    )
    assert same == ("reused", record)
    other = verification.reuse_verdict(record, repo, head, gate_command="make test")
    assert other == ("stale", {})


def test_committed_rename_into_the_store_is_stale(repo: Path) -> None:
    base = _git(repo, "rev-parse", "HEAD")
    (repo / STORE / "notes").mkdir(parents=True)
    _git(repo, "mv", "src/app.py", f"{STORE}/notes/app.md")
    _git(repo, "commit", "--no-verify", "-q", "-m", "move product file into store")
    head = _git(repo, "rev-parse", "HEAD")

    verdict = verification.reuse_verdict(
        _record(base), repo, head, gate_command="dev/bin/release-checks"
    )

    assert verdict == ("stale", {})


def test_symbolic_sha_record_is_stale(repo: Path) -> None:
    head = _git(repo, "rev-parse", "HEAD")

    for symbolic in ("HEAD", "master", head[:12], head.upper()):
        verdict = verification.reuse_verdict(
            _record(symbolic), repo, head, gate_command="dev/bin/release-checks"
        )
        assert verdict == ("stale", {}), symbolic


def test_store_only_change_below_toplevel_is_reused(repo: Path) -> None:
    # repo_root is a subdirectory of the git toplevel (like $HOME/.claude under
    # $HOME): git paths are toplevel-relative, the store prefix is not.
    root = repo / "sub"
    _commit(repo, "sub/src/app.py", "print(1)\n")
    base = _git(repo, "rev-parse", "HEAD")
    _commit(repo, f"sub/{STORE}/autopilot/state.json", "{}\n")
    head = _commit(repo, f"sub/{STORE}/reviews/r1.md", "review\n")
    record = _record(base)
    command = "dev/bin/release-checks"

    assert verification.reuse_verdict(record, root, head, gate_command=command) == (
        "reused",
        record,
    )

    # A dirty tracked store file and an untracked one stay tolerated.
    (root / STORE / "reviews" / "r1.md").write_text("edited\n")
    (root / STORE / "reviews" / "new.md").write_text("new\n")
    assert verification.reuse_verdict(record, root, head, gate_command=command) == (
        "reused",
        record,
    )

    # Product code below the toplevel still makes it stale.
    code_head = _commit(repo, "sub/src/app.py", "print(2)\n")
    assert verification.reuse_verdict(
        record, root, code_head, gate_command=command
    ) == ("stale", {})
