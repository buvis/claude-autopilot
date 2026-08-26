"""Reflow tripwire for ``/work`` step 5 — hunk count per staged file.

A formatter sweep nobody asked for once landed 58 hunks in a file a task had
already edited cleanly (PRD 00148). Step 5 has no way to notice that, so the
sweep rides into the task commit and the next review cycle re-reads it as the
task's work. This counts ``@@`` lines in ``git diff -U0 HEAD -- <path>`` and
names any path at or above the threshold, so the attempt record can stamp
``reflow:`` and the phase report can name the file. It reads only: hunk
scoping stays a manual call.
"""

from __future__ import annotations

import argparse
import subprocess
import sys

DEFAULT_THRESHOLD = 20


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Flag files whose uncommitted diff has too many hunks.",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=DEFAULT_THRESHOLD,
        help=f"Hunk count at which a file is flagged (default: {DEFAULT_THRESHOLD}).",
    )
    parser.add_argument("--git-dir", help="Passed to git as --git-dir (bare-repo home).")
    parser.add_argument("--work-tree", help="Passed to git as --work-tree.")
    parser.add_argument("paths", nargs="+", help="Paths to measure.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    prefix = ["git"]
    if args.git_dir:
        prefix += ["--git-dir", args.git_dir]
    if args.work_tree:
        prefix += ["--work-tree", args.work_tree]

    flagged: list[tuple[str, int]] = []
    for path in args.paths:
        result = subprocess.run(
            [*prefix, "diff", "-U0", "HEAD", "--", path],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            message = " ".join(result.stderr.split()) or "git exited non-zero"
            print(
                f"check_reflow: git diff failed for {path}: {message}",
                file=sys.stderr,
            )
            return 2
        # Under -U0 git emits one `@@` header per changed run of lines, so
        # counting them counts the changes.
        hunks = sum(1 for line in result.stdout.splitlines() if line.startswith("@@"))
        if hunks >= args.threshold:
            flagged.append((path, hunks))

    for path, hunks in flagged:
        print(f"{path}\t{hunks}")
    return 1 if flagged else 0


if __name__ == "__main__":
    sys.exit(main())
