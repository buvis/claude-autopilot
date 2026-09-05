"""Snapshot Qwen's clean write slice, then check it before staging or testing.

Exit 0: ready/proceed; 1: rejected capability attempt; 2: indeterminate, stop.
Restoration is opt-in after the caller establishes exclusive test ownership.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from work_routing import qwen_attempt_outcome, test_only_diff


def git(snapshot: dict, *args: str, index_file: Path | None = None) -> str:
    command = ["git", "--literal-pathspecs"]
    if snapshot.get("git_dir"):
        command += [
            f"--git-dir={snapshot['git_dir']}",
            f"--work-tree={snapshot['root']}",
        ]
    return subprocess.run(
        [*command, *args],
        cwd=snapshot["root"],
        env=os.environ | {"GIT_INDEX_FILE": str(index_file)} if index_file else None,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def paths_from_file(source: Path, root: Path) -> list[str]:
    paths = []
    for line in source.read_text().splitlines():
        if not line.strip():
            continue
        path = Path(line)
        path = path if path.is_absolute() else root / path
        # A symlink would let the helper write outside the owned Git path.
        if path.is_symlink() or path.absolute() != path.resolve():
            raise ValueError(f"non-canonical path: {line}")
        relative = str(path.relative_to(root))
        if path.is_dir() or relative == ".":
            raise ValueError(f"expected a file: {line}")
        paths.append(relative)
    return list(dict.fromkeys(paths))


def worktree_changed(snapshot: dict, base: str, relative: str) -> bool:
    """Read disk and committed blobs directly; Git's index can hide dirty files."""
    path = Path(snapshot["root"]) / relative
    entry = git(snapshot, "ls-tree", "-z", base, "--", relative)
    if not entry:
        return path.exists() or path.is_symlink()
    mode, kind, oid = entry.split("\t", 1)[0].split()
    if path.is_symlink() or path.resolve() != path or not path.is_file():
        return True
    if kind != "blob" or mode != (
        "100755" if path.stat().st_mode & 0o111 else "100644"
    ):
        return True
    return git(snapshot, "hash-object", "--no-filters", "--", relative).strip() != oid


def changed(snapshot: dict, base: str, paths: list[str]) -> bool:
    if not paths:
        return False
    return any(worktree_changed(snapshot, base, path) for path in paths) or bool(
        git(snapshot, "diff", "--cached", "--name-only", base, "--", *paths)
    )


def committable_edit(snapshot: dict) -> bool:
    """Probe actual staging in a private index, preserving the live index."""
    root = Path(snapshot["root"])
    current_index = root / git(snapshot, "rev-parse", "--git-path", "index").strip()
    with tempfile.TemporaryDirectory(prefix="qwen-index-") as scratch:
        index = Path(scratch) / "index"
        shutil.copyfile(current_index, index)
        path = root / snapshot["files"][0]
        if path.exists() or path.is_symlink():
            git(snapshot, "add", "--", *snapshot["files"], index_file=index)
        else:
            git(
                snapshot,
                "update-index",
                "--force-remove",
                "--",
                *snapshot["files"],
                index_file=index,
            )
        return bool(
            git(
                snapshot,
                "diff",
                "--cached",
                "--name-only",
                snapshot["head"],
                "--",
                *snapshot["files"],
                index_file=index,
            )
        )


def before(args: argparse.Namespace) -> dict:
    root = args.repo_root.resolve()
    snapshot = {
        "root": str(root),
        "git_dir": str(args.git_dir.resolve()) if args.git_dir else None,
        "files": paths_from_file(args.files_file, root),
        "tests": paths_from_file(args.tests_file, root),
    }
    if len(snapshot["files"]) != 1 or test_only_diff(snapshot["files"]):
        raise ValueError("Qwen requires exactly one implementation file")
    if set(snapshot["files"]) & set(snapshot["tests"]):
        raise ValueError("implementation and Tess paths overlap")
    snapshot["head"] = git(snapshot, "rev-parse", "HEAD").strip()
    snapshot["test_commit"] = git(
        snapshot,
        "rev-parse",
        "--verify",
        f"{args.test_commit}^{{commit}}",
    ).strip()
    for path in snapshot["tests"]:
        git(snapshot, "cat-file", "-e", f"{snapshot['test_commit']}:{path}")
    if changed(snapshot, snapshot["head"], snapshot["files"]):
        raise ValueError(
            "implementation slice is already dirty; cannot attribute Qwen edits"
        )
    if changed(snapshot, snapshot["test_commit"], snapshot["tests"]):
        raise ValueError(
            "Tess tests differ from the canonical test commit before dispatch"
        )
    args.snapshot.write_text(json.dumps(snapshot) + "\n")
    return {"next": "dispatch"}


def after(args: argparse.Namespace) -> dict:
    snapshot = json.loads(args.snapshot.read_text())
    tests_changed = changed(snapshot, snapshot["test_commit"], snapshot["tests"])
    verdict = qwen_attempt_outcome(
        tests_changed or args.tests_only or committable_edit(snapshot),
        tests_changed,
    )
    if args.tests_only and not tests_changed:
        verdict["next"] = "handle_failure"
    if tests_changed:
        verdict["tests_restored"] = False
        if args.restore_tests:
            if git(snapshot, "rev-parse", "HEAD").strip() != snapshot["head"]:
                raise ValueError("HEAD moved; do not restore tests in the live tree")
            git(
                snapshot,
                "restore",
                f"--source={snapshot['test_commit']}",
                "--staged",
                "--worktree",
                "--ignore-skip-worktree-bits",
                "--",
                *snapshot["tests"],
            )
            if changed(snapshot, snapshot["test_commit"], snapshot["tests"]):
                raise ValueError("canonical tests could not be restored")
            verdict["tests_restored"] = True
    return verdict


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    prepare = commands.add_parser("before")
    prepare.add_argument("--snapshot", type=Path, required=True)
    prepare.add_argument("--repo-root", type=Path, required=True)
    prepare.add_argument("--git-dir", type=Path)
    prepare.add_argument("--files-file", type=Path, required=True)
    prepare.add_argument("--tests-file", type=Path, required=True)
    prepare.add_argument("--test-commit", required=True)
    check = commands.add_parser("after")
    check.add_argument("--snapshot", type=Path, required=True)
    check.add_argument("--restore-tests", action="store_true")
    check.add_argument("--tests-only", action="store_true")
    args = parser.parse_args()
    try:
        verdict = before(args) if args.action == "before" else after(args)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print(f"Qwen guard indeterminate: {error}", file=sys.stderr)
        return 2
    print(json.dumps(verdict))
    return 1 if verdict.get("arm") == "capability" else 0


if __name__ == "__main__":
    sys.exit(main())
