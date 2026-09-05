#!/usr/bin/env python3
"""replay_tests_against_base.py - run the touched tests against the pre-change code.

A regression test must fail against the code it was written to pin
(`rules/testing.md`). Reviews kept finding tests that did not - 00164: a
prose pin whose substring already existed; 00167: `"60000" in "600000"`;
00173: an `A or B` assert satisfied by the old branch - each time because
one reviewer reverted the change by hand and re-ran the test. This computes
that replay once, for every touched test, and hands the result to all of them.

    replay_tests_against_base.py --base <sha> [--cmd "<pytest invocation>"] [--timeout S]

Checks out <base> in a temporary worktree, overlays HEAD's changed test files
and conftests, runs only the test functions the diff touched, and prints one
`[MECH] 🟡 ...` line per test file whose touched tests PASS there. Exit is
always 0: anything that stops the replay (no worktree, no runner, timeout)
prints a `replay: skipped (...)` line instead, and a diff that changes no
non-test file is skipped outright - a coverage backfill pins existing
behavior by design.

ponytail: pytest only, `-rA` summary parsing, touched = any hunk inside the
function's span, names matched without class scope. Test helpers and fixture
data that are not test files stay at base, so a test that needs them fails
there and is (safely) not reported.
"""

from __future__ import annotations

import argparse
import ast
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from detect_tautological_tests import is_test_file, test_functions

HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", re.MULTILINE)
RESULT_RE = re.compile(r"^(PASSED|FAILED|ERROR|XPASS|XFAIL|SKIPPED)\s+(\S+?)::(\S+)", re.MULTILINE)
# A collection error names the file alone: its tests never ran, so they
# neither pass nor count, and the summary line says how many files that was.
COLLECT_ERROR_RE = re.compile(r"^ERROR (\S+\.py)(?:\s|$)", re.MULTILINE)
NAMES_SHOWN = 6


def run_git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=False
    )


def is_overlay_file(path: str) -> bool:
    return is_test_file(Path(path)) or Path(path).name == "conftest.py"


def head_ranges(diff_text: str) -> list[tuple[int, int]]:
    """HEAD-side line ranges of every hunk; a pure deletion maps to the line
    it left behind, so a function that lost lines still counts as touched."""
    ranges = []
    for m in HUNK_RE.finditer(diff_text):
        start = int(m.group(1))
        count = int(m.group(2)) if m.group(2) is not None else 1
        ranges.append((start, start + max(count, 1) - 1))
    return ranges


def touched_tests(root: Path, base: str, path: str) -> set[str] | None:
    """Names of the test functions the diff touched in `path`; None means
    every test (the file is new at HEAD, or its HEAD content will not parse)."""
    if run_git(root, "cat-file", "-e", f"{base}:{path}").returncode != 0:
        return None
    ranges = head_ranges(run_git(root, "diff", "-U0", base, "HEAD", "--", path).stdout)
    try:
        tree = ast.parse(run_git(root, "show", f"HEAD:{path}").stdout)
    except (SyntaxError, ValueError):
        return None
    touched = set()
    for fn in test_functions(tree):
        start = min((d.lineno for d in fn.decorator_list), default=fn.lineno)
        end = fn.end_lineno or fn.lineno
        if any(lo <= end and hi >= start for lo, hi in ranges):
            touched.add(fn.name)
    return touched


def parse_results(stdout: str) -> list[tuple[str, str, str]]:
    """(outcome, file, test name) per `-rA` summary line; the parametrize id
    and any class prefix are dropped so names match `touched_tests`."""
    rows = []
    for outcome, path, rest in RESULT_RE.findall(stdout):
        rows.append((outcome, path, rest.split("::")[-1].split("[")[0]))
    return rows


def _run_in_worktree(
    root: Path, base: str, files: list[str], cmd: str, timeout: float
) -> tuple[str, str | None]:
    """(pytest stdout, skip reason). The worktree lives in a temp dir and is
    removed whatever happens."""
    # resolve(): on macOS mkdtemp answers /var/... for /private/var/..., and
    # pytest keys nodeids off the resolved rootdir, so the paths would not
    # match the touched map without it.
    tmp = Path(tempfile.mkdtemp(prefix="replay-")).resolve()
    worktree = tmp / "wt"
    try:
        added = run_git(root, "worktree", "add", "--detach", str(worktree), base)
        if added.returncode != 0:
            return "", f"worktree add failed: {added.stderr.strip()}"
        head = run_git(root, "rev-parse", "HEAD").stdout.strip()
        overlay = run_git(worktree, "checkout", head, "--", *files)
        if overlay.returncode != 0:
            return "", f"overlay failed: {overlay.stderr.strip()}"
        # A new test file that imports a module born in this diff cannot be
        # collected at base; without --continue-on-collection-errors pytest
        # would abort the whole run over it and every other file would go unreplayed.
        argv = [
            *shlex.split(cmd), "-q", "-rA", "--rootdir", str(worktree),
            "-p", "no:cacheprovider", "--continue-on-collection-errors", *files,
        ]
        try:
            run = subprocess.run(
                argv, cwd=worktree, capture_output=True, text=True, timeout=timeout, check=False
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return "", f"runner did not complete: {exc}"
        if not RESULT_RE.search(run.stdout) and not COLLECT_ERROR_RE.search(run.stdout):
            tail = (run.stderr or run.stdout).strip().splitlines()[-1:] or ["no output"]
            return "", f"runner produced no results (exit {run.returncode}: {tail[0]})"
        return run.stdout, None
    finally:
        run_git(root, "worktree", "remove", "--force", str(worktree))
        shutil.rmtree(tmp, ignore_errors=True)


def replay(root: Path, base: str, cmd: str, timeout: float) -> str:
    """The markdown block for this diff."""
    header = [
        "## Fail-first replay (computed, do not re-judge)",
        "",
        f"Touched tests from HEAD, run against the pre-change code at `{base[:12]}`",
        "(HEAD's test files overlaid on a base worktree). A test that passes there",
        "does not pin this change. A behavior-preserving refactor's tests pass by",
        "design, so weigh the PRD's intent before raising one. `mech-check` is the finder.",
        "",
    ]
    changed = run_git(root, "diff", "--name-only", base, "HEAD").stdout.split()
    if not changed:
        return "\n".join(header + [f"replay: skipped (no change between {base[:12]} and HEAD)"])
    if all(is_overlay_file(p) for p in changed):
        return "\n".join(header + ["replay: skipped (no non-test change; a backfill's tests pass against base by design)"])
    present = run_git(root, "diff", "--name-only", "--diff-filter=d", base, "HEAD").stdout.split()
    files = [p for p in present if is_overlay_file(p)]
    touched = {p: touched_tests(root, base, p) for p in files if is_test_file(Path(p))}
    to_run = [p for p, names in touched.items() if names is None or names]
    if not to_run:
        return "\n".join(header + ["replay: skipped (the diff touches no test function)"])

    stdout, reason = _run_in_worktree(root, base, files, cmd, timeout)
    if reason:
        return "\n".join(header + [f"replay: skipped ({reason})"])

    ran = 0
    passing: dict[str, list[str]] = {}
    for outcome, path, name in parse_results(stdout):
        names = touched.get(path)
        if names is not None and name not in names:
            continue
        ran += 1
        if outcome == "PASSED":
            passing.setdefault(path, []).append(name)
    lines = list(header)
    for path, names in passing.items():
        shown = ", ".join(dict.fromkeys(names[:NAMES_SHOWN]))
        more = f" +{len(names) - NAMES_SHOWN} more" if len(names) > NAMES_SHOWN else ""
        lines.append(
            f"[MECH] 🟡 {len(names)} touched test(s) pass against the pre-change code: "
            f"{shown}{more} | File: {path} | Task: general"
        )
    passed = sum(len(n) for n in passing.values())
    uncollectable = len(set(COLLECT_ERROR_RE.findall(stdout)))
    lines += [
        "",
        f"Replay: {ran} touched test(s) ran, {ran - passed} failed against base, {passed} passed; "
        f"{uncollectable} test file(s) could not be collected at base (their tests fail there). Command: {cmd}",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the diff's touched tests against the pre-change code and report the ones that pass.",
    )
    parser.add_argument("--base", required=True, help="pre-change commit (left side of the review's diff range)")
    parser.add_argument("--cmd", default="python3 -m pytest", help="per-file pytest invocation")
    parser.add_argument("--timeout", type=float, default=600.0, help="seconds for the whole run")
    args = parser.parse_args(argv)
    top = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=False
    )
    if top.returncode != 0:
        print("replay: skipped (no git worktree)")
        return 0
    print(replay(Path(top.stdout.strip()), args.base, args.cmd, args.timeout))
    return 0


if __name__ == "__main__":
    sys.exit(main())
