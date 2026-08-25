#!/usr/bin/env python3
"""check_style_limits.py - report style limit violations introduced by a diff.

PRD 00140. A regression check that flags only the violations a diff itself
introduces: functions over 50 lines whose line span intersects a diff hunk
range, and files the diff pushed over 800 lines. Pre-existing debt is
deliberately not reported -- that is scope for the review lens.

    check_style_limits.py --diff DIFF_FILE FILE [FILE ...]
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path

_MECH = (
    Path(__file__).resolve().parents[2]
    / "review-work-completion"
    / "scripts"
    / "compute_mech_facts.py"
)
_spec = importlib.util.spec_from_file_location("compute_mech_facts", _MECH)
assert _spec is not None and _spec.loader is not None
_compute_mech_facts = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_compute_mech_facts)

facts_for_file = _compute_mech_facts.facts_for_file

_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))?\s+@@")


def touched_ranges(diff_text: str) -> dict[str, list[tuple[int, int]]]:
    """Parse diff text and return per-file new-side line ranges.

    Returns a dict mapping diff path (b/ stripped) to a list of
    (start, end) tuples for each hunk's new-side range. A hunk only
    contributes its range when it adds at least one line; a hunk that is
    pure deletion (with or without trailing context) touches nothing.
    """
    result: dict[str, list[tuple[int, int]]] = {}
    current_path = ""
    pending: tuple[int, int] | None = None
    has_addition = False

    def flush() -> None:
        if pending is not None and has_addition:
            result[current_path].append(pending)

    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            flush()
            current_path = line[6:]
            result.setdefault(current_path, [])
            pending = None
            has_addition = False
        elif line.startswith("+++"):
            flush()
            current_path = ""
            pending = None
            has_addition = False
        elif current_path and line.startswith("@@ "):
            flush()
            m = _HUNK_RE.match(line)
            if m:
                start = int(m.group(1))
                count = int(m.group(2)) if m.group(2) else 1
                pending = (start, start + count - 1) if count > 0 else None
            else:
                pending = None
            has_addition = False
        elif (
            pending is not None and line.startswith("+") and not line.startswith("+++")
        ):
            has_addition = True
    flush()
    return result


def _line_counts(diff_text: str) -> dict[str, tuple[int, int]]:
    """Per diff path (b/ stripped): (insertions, deletions) counted from the
    hunk body lines; the +++/--- header lines are not counted."""
    counts: dict[str, tuple[int, int]] = {}
    cur = ""
    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            cur = line[6:]
            counts.setdefault(cur, (0, 0))
        elif line.startswith("+++"):
            cur = ""
        elif cur and line.startswith("+") and not line.startswith("+++"):
            counts[cur] = (counts[cur][0] + 1, counts[cur][1])
        elif cur and line.startswith("-") and not line.startswith("---"):
            counts[cur] = (counts[cur][0], counts[cur][1] + 1)
    return counts


def _match(path: Path, diff_path: str) -> bool:
    """Same file when the trailing path segments agree for the last
    min(len) segments, so `<tmp>/test_x.py` matches `hooks/tests/test_x.py`."""
    a, d = path.parts, Path(diff_path).parts
    n = min(len(a), len(d))
    return n > 0 and a[-n:] == d[-n:]


def _resolve_diff_path(
    path: Path,
    ranges_by_path: dict[str, list[tuple[int, int]]],
) -> str | None:
    """Resolve path to exactly ONE diff path: the candidate agreeing on
    the most trailing segments wins. An equal-depth tie is ambiguous -
    skip it (print the file and the tied candidates to stderr) rather
    than silently picking one or pooling them."""
    by_depth: dict[int, list[str]] = {}
    for dp in ranges_by_path:
        if _match(path, dp):
            depth = min(len(path.parts), len(Path(dp).parts))
            by_depth.setdefault(depth, []).append(dp)
    if not by_depth:
        return None
    candidates = by_depth[max(by_depth)]
    if len(candidates) > 1:
        print(
            f"check_style_limits: ambiguous diff-path match for {path}: "
            f"{candidates} - skipping",
            file=sys.stderr,
        )
        return None
    return candidates[0]


def violations(
    diff_text: str,
    paths: list[Path],
    function_limit: int = 50,
    file_limit: int = 800,
) -> list[str]:
    """Return violation lines for the given diff and file paths."""
    ranges_by_path = touched_ranges(diff_text)
    counts = _line_counts(diff_text)
    results: list[str] = []
    for path in paths:
        diff_path = _resolve_diff_path(path, ranges_by_path)
        if diff_path is None:
            continue
        status, funcs = facts_for_file(path)
        if status == "skipped (non-python)":
            continue
        ranges = ranges_by_path[diff_path]
        if status == "ok":
            for name, start, length in funcs:
                end = start + length - 1
                if length > function_limit and any(
                    start <= re_ and rs <= end for rs, re_ in ranges
                ):
                    results.append(
                        f"FUNCTION | {path}:{start} | {name} | {length} lines",
                    )
        ins, dels = counts.get(diff_path, (0, 0))
        try:
            n = len(path.read_text(encoding="utf-8").splitlines())
        except (OSError, SyntaxError, ValueError, UnicodeDecodeError) as exc:
            print(
                f"check_style_limits: skipping unreadable file {path}: {exc}",
                file=sys.stderr,
            )
            continue
        if n > file_limit and n - ins + dels <= file_limit:
            results.append(f"FILE | {path} | {n} lines")
    return results


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Check style limit violations introduced by a diff.",
    )
    parser.add_argument("--diff", required=True, type=Path)
    parser.add_argument("files", nargs="+", type=Path)
    args = parser.parse_args(argv)
    try:
        diff_text = args.diff.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(
            f"check_style_limits: cannot read diff file {args.diff}: {exc}",
            file=sys.stderr,
        )
        return 2
    found = violations(diff_text, args.files)
    for line in found:
        print(line)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
