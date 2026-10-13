#!/usr/bin/env python3
"""Tests for cli/verification.py split out of test_verification.py (PRD 00249
task 1 rework, cycle 1): dirty-tree refusal, store/ancestor ("tree-to-tree")
reuse checks, and command-normalization checks. Split because
test_verification.py outgrew the 800-line style cap.

The reuse checks run against real temporary git repos: the point is to bind
real git behavior (ancestry, diff paths, dirty tree), not a mock of it.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from cli import verification

STORE = "docs/dev/project-management"
GATE = "dev/bin/release-checks"
STORE_PREFIX = verification.STORE_PREFIX
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

    assert verification.reuse_verdict(record, repo, head, gate_command=GATE) == (
        "reused",
        record,
    )
    # An empty diff (record at HEAD itself) is vacuously store-only.
    same = _record(head)
    assert verification.reuse_verdict(same, repo, head, gate_command=GATE) == (
        "reused",
        same,
    )


def test_stale_when_code_changed(repo: Path) -> None:
    base = _git(repo, "rev-parse", "HEAD")
    _commit(repo, f"{STORE}/autopilot/state.json", "{}\n")
    head = _commit(repo, "src/app.py", "print(2)\n")

    assert verification.reuse_verdict(_record(base), repo, head, gate_command=GATE) == (
        "stale",
        {},
    )

    # Any path outside the store counts, not only the ones under src/.
    later = _commit(repo, "Makefile", "all:\n\t@true\n")
    assert verification.reuse_verdict(
        _record(head), repo, later, gate_command=GATE
    ) == ("stale", {})


def test_reuse_verdict_fails_closed_on_git_error(repo: Path, tmp_path_factory) -> None:
    head = _git(repo, "rev-parse", "HEAD")
    not_a_repo = tmp_path_factory.mktemp("plain")

    assert verification.reuse_verdict(None, repo, head, gate_command=GATE) == (
        "stale",
        {},
    )
    assert verification.reuse_verdict(_record(""), repo, head, gate_command=GATE) == (
        "stale",
        {},
    )
    no_sha = _record(head)
    del no_sha["sha"]
    assert verification.reuse_verdict(no_sha, repo, head, gate_command=GATE) == (
        "stale",
        {},
    )
    assert verification.reuse_verdict(_record(123), repo, head, gate_command=GATE) == (
        "stale",
        {},
    )
    unknown = _record("0123456789abcdef0123456789abcdef01234567")
    assert verification.reuse_verdict(unknown, repo, head, gate_command=GATE) == (
        "stale",
        {},
    )
    assert verification.reuse_verdict(
        _record("no-such-ref"), repo, head, gate_command=GATE
    ) == (
        "stale",
        {},
    )
    assert verification.reuse_verdict(
        _record(head), not_a_repo, head, gate_command=GATE
    ) == ("stale", {})


def test_reuse_verdict_rejects_non_ancestor_sha(repo: Path) -> None:
    root = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "-b", "side")
    sibling = _commit(repo, f"{STORE}/notes/side.md", "side\n")
    _git(repo, "checkout", "-q", "-")
    head = _commit(repo, f"{STORE}/notes/main.md", "main\n")

    # Sibling commit (survived a reset/rebase): not an ancestor of HEAD.
    assert verification.reuse_verdict(
        _record(sibling), repo, head, gate_command=GATE
    ) == ("stale", {})
    # Descendant: record newer than the HEAD being checked.
    assert verification.reuse_verdict(_record(head), repo, root, gate_command=GATE) == (
        "stale",
        {},
    )


def test_reuse_verdict_rejects_dirty_tree(repo: Path) -> None:
    head = _git(repo, "rev-parse", "HEAD")
    record = _record(head)
    assert verification.reuse_verdict(record, repo, head, gate_command=GATE) == (
        "reused",
        record,
    )

    (repo / "src" / "app.py").write_text("print('dirty')\n")
    assert verification.reuse_verdict(record, repo, head, gate_command=GATE) == (
        "stale",
        {},
    )

    _git(repo, "checkout", "--", "src/app.py")
    (repo / "src" / "new.py").write_text("untracked\n")
    assert verification.reuse_verdict(record, repo, head, gate_command=GATE) == (
        "stale",
        {},
    )


def test_rename_out_of_store_is_not_clean(repo: Path) -> None:
    store_dir = repo / STORE / "notes"
    store_dir.mkdir(parents=True)
    (store_dir / "old.md").write_text("x\n")
    _git(repo, "add", "--", f"{STORE}/notes/old.md")
    _git(repo, "commit", "--no-verify", "-q", "-m", "add store note")
    head = _git(repo, "rev-parse", "HEAD")
    record = _record(head)
    assert verification.reuse_verdict(record, repo, head, gate_command=GATE) == (
        "reused",
        record,
    )

    # Destination at the repo root, outside the store and outside src/.
    _git(repo, "mv", f"{STORE}/notes/old.md", "moved.md")
    assert verification.reuse_verdict(record, repo, head, gate_command=GATE) == (
        "stale",
        {},
    )


def test_rename_into_store_from_production_is_not_clean() -> None:
    # A rename into the store from outside it is judged by both endpoints
    # too: a clean destination alone must not excuse a dirty source.
    assert (
        verification._dirty_path_is_in_store(
            f"{STORE}/moved.md", "production.md", STORE_PREFIX
        )
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
    assert (
        verification._dirty_path_is_in_store(f"{STORE}/dst.md", "src.md", STORE_PREFIX)
        is False
    )


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


def test_reuse_verdict_ignores_dirty_paths_under_the_store(repo: Path) -> None:
    store_dir = repo / STORE / "autopilot"
    store_dir.mkdir(parents=True)
    tracked = store_dir / "state.json"
    tracked.write_text("{}\n")
    _git(repo, "add", "--", f"{STORE}/autopilot/state.json")
    _git(repo, "commit", "--no-verify", "-q", "-m", "add store file")
    head = _git(repo, "rev-parse", "HEAD")
    record = _record(head)
    assert verification.reuse_verdict(record, repo, head, gate_command=GATE) == (
        "reused",
        record,
    )

    # Dirty a tracked store file and add an untracked one: both ignored.
    tracked.write_text('{"dirty": true}\n')
    (store_dir / "dispatch-metrics.jsonl").write_text("{}\n")
    assert verification.reuse_verdict(record, repo, head, gate_command=GATE) == (
        "reused",
        record,
    )

    # A store path that merely contains "src/" in its name is still store.
    nested = store_dir.parent / "notes" / "src"
    nested.mkdir(parents=True)
    (nested / "x.md").write_text("note\n")
    assert verification.reuse_verdict(record, repo, head, gate_command=GATE) == (
        "reused",
        record,
    )

    # A non-store path dirty at the same time still makes the record stale.
    (repo / "src" / "app.py").write_text("print('dirty')\n")
    assert verification.reuse_verdict(record, repo, head, gate_command=GATE) == (
        "stale",
        {},
    )

    # ... and so does one that lives outside src/ entirely.
    _git(repo, "checkout", "--", "src/app.py")
    (repo / "pyproject.toml").write_text("[project]\n")
    assert verification.reuse_verdict(record, repo, head, gate_command=GATE) == (
        "stale",
        {},
    )


def test_committed_rename_into_the_store_is_stale(repo: Path) -> None:
    base = _git(repo, "rev-parse", "HEAD")
    (repo / STORE / "notes").mkdir(parents=True)
    _git(repo, "mv", "src/app.py", f"{STORE}/notes/app.md")
    _git(repo, "commit", "--no-verify", "-q", "-m", "move product file into store")
    head = _git(repo, "rev-parse", "HEAD")

    verdict = verification.reuse_verdict(
        _record(base),
        repo,
        head,
        gate_command="dev/bin/release-checks",
    )

    assert verdict == ("stale", {})


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
        record,
        root,
        code_head,
        gate_command=command,
    ) == ("stale", {})


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("dev/bin/release-checks", "dev/bin/release-checks"),
        ("bash  ./dev/bin/release-checks", "dev/bin/release-checks"),
        ("sh ./dev/bin/release-checks", "dev/bin/release-checks"),
        ("./dev/bin/release-checks", "dev/bin/release-checks"),
        ("  dev/bin/release-checks\t--fast\n", "dev/bin/release-checks --fast"),
        # Whitespace collapses before the prefix strip, so a tab counts.
        ("bash\t./dev/bin/release-checks", "dev/bin/release-checks"),
        # Exactly one shell prefix and exactly one "./" are stripped.
        ("bash bash ./dev/bin/release-checks", "bash ./dev/bin/release-checks"),
        ("sh sh dev/bin/release-checks", "sh dev/bin/release-checks"),
        ("././dev/bin/release-checks", "./dev/bin/release-checks"),
        # Only the first shell prefix goes, even when a different one follows.
        ("bash sh ./x", "sh ./x"),
        # Any whitespace collapses (str.split semantics), an inner newline too.
        ("dev/bin/release-checks\n--fast", "dev/bin/release-checks --fast"),
        # A prefix needs its trailing space: "bashful" is not "bash ".
        ("bashful ./x", "bashful ./x"),
        ("make test", "make test"),
    ],
)
def test_normalize_command_collapses_space_then_strips_one_shell_and_one_dot_slash(
    raw: str,
    expected: str,
) -> None:
    assert verification.normalize_command(raw) == expected


@pytest.mark.parametrize(
    "value",
    [
        None,
        123,
        ["dev/bin/release-checks"],
        b"dev/bin/release-checks",
        {"command": "x"},
    ],
)
def test_normalize_command_maps_non_str_to_empty_string(value: object) -> None:
    assert verification.normalize_command(value) == ""


def test_reuse_matches_a_command_spelled_with_bash_dot_slash_and_extra_spaces(
    repo: Path,
) -> None:
    head = _git(repo, "rev-parse", "HEAD")
    record = _record(head)  # recorded from "dev/bin/release-checks"

    for spelled in (
        "bash  ./dev/bin/release-checks",
        "sh ./dev/bin/release-checks",
        "  ./dev/bin/release-checks ",
    ):
        verdict = verification.reuse_verdict(record, repo, head, gate_command=spelled)
        assert verdict == ("reused", record), spelled

    # The match runs both ways: a record spelled loosely matches a plain gate.
    loose = _record(head)
    loose["commands"] = [{"command": "bash   ./dev/bin/release-checks", "exit": 0}]
    assert verification.reuse_verdict(loose, repo, head, gate_command=GATE) == (
        "reused",
        loose,
    )

    # Normalizing never makes a different command match.
    for other in (
        "bash bash ./dev/bin/release-checks",
        "dev/bin/release-checks --fast",
    ):
        assert verification.reuse_verdict(record, repo, head, gate_command=other) == (
            "stale",
            {},
        ), other


def test_merge_resolution_change_outside_the_store_is_stale(repo: Path) -> None:
    # `git log --name-only` over a merge commit's range is silent for the
    # merge commit's own resolution edits (it only shows them against the
    # first parent's default diff, which can hide a resolution that touched
    # product code). `git diff` between the two endpoints is not: it must
    # catch an outside-the-store edit introduced only by the merge's own
    # resolution.
    base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "-b", "feature")
    _commit(repo, f"{STORE}/notes/feature.md", "feature\n")
    feature_tip = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "-")
    _commit(repo, f"{STORE}/notes/main.md", "main\n")

    _git(repo, "merge", "--no-ff", "-q", "-m", "merge feature", feature_tip)
    # Resolve the merge by touching a file outside the store - this edit is
    # part of the merge commit itself, not a prior commit on either branch.
    (repo / "src" / "app.py").write_text("print('merged')\n")
    _git(repo, "add", "--", "src/app.py")
    _git(repo, "commit", "--no-verify", "-q", "--amend", "--no-edit")
    head = _git(repo, "rev-parse", "HEAD")

    assert verification.reuse_verdict(_record(base), repo, head, gate_command=GATE) == (
        "stale",
        {},
    )


def test_untracked_product_file_is_stale_when_status_hides_untracked(
    repo: Path,
) -> None:
    # With status.showUntrackedFiles=no, a plain `git status --porcelain=1`
    # hides an untracked file entirely; reuse_verdict must still catch it by
    # requesting --untracked-files=all explicitly.
    _git(repo, "config", "status.showUntrackedFiles", "no")
    head = _git(repo, "rev-parse", "HEAD")
    record = _record(head)
    assert verification.reuse_verdict(record, repo, head, gate_command=GATE) == (
        "reused",
        record,
    )

    (repo / "src" / "untracked.py").write_text("print('new')\n")
    assert verification.reuse_verdict(record, repo, head, gate_command=GATE) == (
        "stale",
        {},
    )


def test_an_untracked_store_dir_stays_reused(repo: Path) -> None:
    # The whole docs/ tree untracked: base `git status` prints only
    # "?? docs/" (a directory, not per-file entries) when the directory
    # itself is untracked. That single record must still resolve as
    # store-only, not fall through the store check by looking unfamiliar.
    base = _git(repo, "rev-parse", "HEAD")
    store_dir = repo / STORE / "autopilot"
    store_dir.mkdir(parents=True)
    (store_dir / "state.json").write_text("{}\n")
    assert verification.reuse_verdict(_record(base), repo, base, gate_command=GATE) == (
        "reused",
        _record(base),
    )


def test_store_only_commit_with_non_ascii_filename_is_reused(repo: Path) -> None:
    # git quotes non-ASCII paths in its default status/log output; the NUL
    # separated forms used here must not need that quoting resolved.
    base = _git(repo, "rev-parse", "HEAD")
    head = _commit(repo, f"{STORE}/notes/café.md", "note\n")
    record = _record(base)
    assert verification.reuse_verdict(record, repo, head, gate_command=GATE) == (
        "reused",
        record,
    )


def test_run_gate_on_a_dirty_tree_writes_no_record(repo: Path) -> None:
    (repo / "src" / "app.py").write_text("print('dirty')\n")

    result = verification.run_gate(
        "echo 'PASS 1 FAIL 0 SKIP 0 EXIT 0'",
        repo,
        "abc",
        1,
    )

    assert result == {
        "passed": None,
        "failed": None,
        "skipped": None,
        "exit": None,
        "raw_line": None,
        "timed_out": False,
        "recorded": False,
        "dirty": True,
    }
    assert not (repo / RECORD_REL).exists()


def test_run_gate_dirtied_during_the_run_writes_no_record(repo: Path) -> None:
    # Clean at spawn time; the command itself dirties the tree before it
    # prints its summary line. The post-reap check must still catch it.
    command = "echo dirty > src/dirty.py; echo 'PASS 1 FAIL 0 SKIP 0 EXIT 0'"

    result = verification.run_gate(command, repo, "abc", 1)

    assert result["passed"] == 1
    assert result["recorded"] is False
    assert result["dirty"] is True
    assert not (repo / RECORD_REL).exists()


def test_run_gate_tolerates_dirty_store_paths(repo: Path) -> None:
    store_dir = repo / STORE / "autopilot"
    store_dir.mkdir(parents=True)
    (store_dir / "state.json").write_text("{}\n")

    result = verification.run_gate(
        "echo 'PASS 1 FAIL 0 SKIP 0 EXIT 0'",
        repo,
        "abc",
        1,
    )

    assert result["passed"] == 1
    assert result["recorded"] is True
    assert result["dirty"] is False
    assert (repo / RECORD_REL).exists()


def test_gate_runs_in_a_repo_that_does_not_ignore_docs_dev_tmp(
    repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # No .gitignore anywhere and no user/system git config, so nothing hides
    # docs/dev/tmp/: it is store by definition (STORE_PREFIXES), not dirt.
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    assert not (repo / ".gitignore").exists()
    prompt = repo / "docs" / "dev" / "tmp" / "alice-prompt-1.md"
    prompt.parent.mkdir(parents=True)
    prompt.write_text("prompt\n")
    _git(repo, "add", "--", "docs/dev/tmp/alice-prompt-1.md")
    # Any name and any depth under docs/dev/tmp/, staged or left untracked.
    (repo / "docs" / "dev" / "tmp" / "bob-notes.txt").write_text("notes\n")
    nested = repo / "docs" / "dev" / "tmp" / "sub" / "x"
    nested.parent.mkdir(parents=True)
    nested.write_text("nested\n")
    _git(repo, "add", "--", "docs/dev/tmp/bob-notes.txt", "docs/dev/tmp/sub/x")
    (repo / "docs" / "dev" / "tmp" / "untracked.md").write_text("untracked\n")
    assert "?? docs/dev/tmp/untracked.md" in _git(
        repo, "status", "--porcelain=1", "--untracked-files=all"
    )

    result = verification.run_gate(
        "echo 'PASS 1 FAIL 0 SKIP 0 EXIT 0'",
        repo,
        "abc",
        1,
    )

    assert result["passed"] == 1
    assert result["recorded"] is True
    assert result["dirty"] is False
    assert (repo / RECORD_REL).exists()

    # The prefix is the directory, not a name stem: a staged sibling that
    # merely starts with "docs/dev/tmp" is still foreign dirt.
    (repo / RECORD_REL).unlink()
    (repo / "docs" / "dev" / "tmp-notes.md").write_text("notes\n")
    _git(repo, "add", "--", "docs/dev/tmp-notes.md")
    refused = verification.run_gate(
        "echo 'PASS 1 FAIL 0 SKIP 0 EXIT 0'",
        repo,
        "abc",
        1,
    )
    assert refused["recorded"] is False
    assert refused["dirty"] is True
    assert not (repo / RECORD_REL).exists()


def test_gate_refuses_a_rename_from_product_code_into_docs_dev_tmp(
    repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A rename is judged by both endpoints: a tmp destination does not
    # excuse the product source it was moved out of.
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    (repo / "docs" / "dev" / "tmp").mkdir(parents=True)
    _git(repo, "mv", "src/app.py", "docs/dev/tmp/app.py")

    result = verification.run_gate(
        "echo 'PASS 1 FAIL 0 SKIP 0 EXIT 0'",
        repo,
        "abc",
        1,
    )

    assert result["recorded"] is False
    assert result["dirty"] is True
    assert not (repo / RECORD_REL).exists()


def test_gate_below_the_toplevel_excuses_its_own_docs_dev_tmp(
    repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # cwd is a subdirectory of the git toplevel (like $HOME/.claude under
    # $HOME): git paths are toplevel-relative, the tmp prefix is not.
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    _commit(repo, "sub/src/app.py", "print(1)\n")
    root = repo / "sub"
    tmp = root / "docs" / "dev" / "tmp"
    tmp.mkdir(parents=True)
    (tmp / "alice-prompt-1.md").write_text("prompt\n")
    _git(repo, "add", "--", "sub/docs/dev/tmp/alice-prompt-1.md")
    (tmp / "untracked.md").write_text("untracked\n")

    result = verification.run_gate(
        "echo 'PASS 1 FAIL 0 SKIP 0 EXIT 0'",
        root,
        "abc",
        1,
    )

    assert result["passed"] == 1
    assert result["recorded"] is True
    assert result["dirty"] is False
    assert (root / RECORD_REL).exists()


def test_own_log_outside_tmp_is_not_dirt(
    repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A user-level ignore rule (a global `*.log`) must not be what hides the
    # log, so git config outside the repo is switched off.
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    log_path = repo / "my-own.log"
    assert not log_path.exists()

    result = verification.run_gate(
        "echo 'PASS 1 FAIL 0 SKIP 0 EXIT 0'",
        repo,
        "abc",
        1,
        log_path=log_path,
    )

    assert result["passed"] == 1
    assert result["recorded"] is True
    assert result["dirty"] is False
    assert (repo / RECORD_REL).exists()
    assert "PASS 1 FAIL 0 SKIP 0 EXIT 0" in log_path.read_text()
    assert _git(repo, "ls-files", "--", "my-own.log") == ""

    # Only the gate's own log, by exact path, is excused: another untracked
    # file outside the store with the same basename, written by the same
    # run, still refuses the record. Run 1's log is removed first so the
    # refusal comes from the post-run check (the gate ran: passed == 1),
    # not from leftover pre-spawn dirt.
    (repo / RECORD_REL).unlink()
    log_path.unlink()
    refused = verification.run_gate(
        "mkdir -p sub; echo stray > sub/my-own.log; echo 'PASS 1 FAIL 0 SKIP 0 EXIT 0'",
        repo,
        "abc",
        1,
        log_path=log_path,
    )
    assert refused["passed"] == 1
    assert refused["recorded"] is False
    assert refused["dirty"] is True
    assert not (repo / RECORD_REL).exists()


def test_own_log_exclusion_does_not_excuse_a_sibling_sharing_its_name_as_prefix(
    repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The log is excused by exact path, not as a prefix: an untracked
    # sibling whose name starts with the log's name still refuses the record.
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    log_path = repo / "my-own.log"

    refused = verification.run_gate(
        "echo stray > my-own.log.bak; echo 'PASS 1 FAIL 0 SKIP 0 EXIT 0'",
        repo,
        "abc",
        1,
        log_path=log_path,
    )

    assert refused["passed"] == 1
    assert refused["recorded"] is False
    assert refused["dirty"] is True
    assert not (repo / RECORD_REL).exists()


def test_own_log_does_not_skip_the_pre_spawn_dirty_check(
    repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Passing log_path excuses the log alone: a tree already dirty before
    # the call is still refused before the command spawns.
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    (repo / "stray.txt").write_text("stray\n")

    result = verification.run_gate(
        "echo 'PASS 1 FAIL 0 SKIP 0 EXIT 0'",
        repo,
        "abc",
        1,
        log_path=repo / "my-own.log",
    )

    assert result == {
        "passed": None,
        "failed": None,
        "skipped": None,
        "exit": None,
        "raw_line": None,
        "timed_out": False,
        "recorded": False,
        "dirty": True,
    }
    assert not (repo / RECORD_REL).exists()
