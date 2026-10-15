"""cli/cap_check.py - classify a review file's HIGH/CRITICAL findings as
regressions introduced by the rework range between a previous review file's
`head_sha` and the current one's.

Assumes cwd is the project root unless the CLI's `--repo-root` is passed.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from . import frontmatter
from .findings_section import _reviewed_keys

_FILE_LINE_RE = re.compile(r"^(.*):(\d+)$")


class CapCheckError(RuntimeError):
    """review_file could not be read, parsed, or diffed against git."""


def rework_range(previous_head: str, head: str) -> tuple[str, str]:
    """(previous_head, head) unchanged - a thin named pair, not a lookup, so
    callers have one symbol to import instead of building the tuple inline."""
    return (previous_head, head)


def _head_sha(review_file: Path) -> str:
    try:
        text = review_file.read_text(encoding="utf-8")
    except OSError as err:
        raise CapCheckError(f"cannot read {review_file}: {err}") from err
    sha = frontmatter.declared(text).get("head_sha", "").strip()
    if not sha:
        raise CapCheckError(f"{review_file} carries no head_sha frontmatter line")
    return sha


def _git(repo_root: str | Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as err:
        raise CapCheckError(f"git {' '.join(args)} failed: {err}") from err
    return result.stdout.strip()


def _split_file_line(cell: str) -> tuple[str, int | None]:
    matched = _FILE_LINE_RE.match(cell)
    if matched is None:
        return cell, None
    return matched.group(1), int(matched.group(2))


def classify_findings(
    repo_root: str | Path,
    review_file: str | Path,
    previous_review_file: str | Path | None,
) -> list[dict]:
    """Every high/critical row of `review_file`'s Consolidated Findings
    section, classified against the rework range between
    `previous_review_file`'s head_sha and `review_file`'s head_sha."""
    review_file = Path(review_file)
    if previous_review_file is None or not Path(previous_review_file).exists():
        return []
    previous_review_file = Path(previous_review_file)

    try:
        text = review_file.read_text(encoding="utf-8")
    except OSError as err:
        raise CapCheckError(f"cannot read {review_file}: {err}") from err
    rows, problem = _reviewed_keys(text)
    if problem is not None:
        raise CapCheckError(f"{review_file}: {problem}")

    head = _head_sha(review_file)
    previous_head = _head_sha(previous_review_file)
    previous_head, head = rework_range(previous_head, head)

    rework_commits = set(
        _git(repo_root, "rev-list", f"{previous_head}..{head}").splitlines(),
    )
    changed_files = set(
        _git(repo_root, "diff", "--name-only", f"{previous_head}..{head}").splitlines(),
    )

    out: list[dict] = []
    for row in rows:
        if row.severity not in ("high", "critical"):
            continue
        file, line = _split_file_line(row.file)
        regression = False
        commit: str | None = None
        if file:
            if line is not None:
                try:
                    blame = _git(
                        repo_root,
                        "blame",
                        "-L",
                        f"{line},{line}",
                        "--porcelain",
                        head,
                        "--",
                        file,
                    )
                except CapCheckError:
                    blame = ""
                if blame:
                    blamed_commit = blame.splitlines()[0].split()[0]
                    if blamed_commit in rework_commits:
                        regression = True
                        commit = _git(repo_root, "log", "--format=%h", "-1", head)
            else:
                if file in changed_files:
                    regression = True
                    commit = _git(repo_root, "log", "--format=%h", "-1", head)
        out.append(
            {
                "ref": row.ref,
                "severity": row.severity,
                "file": file,
                "line": line,
                "regression": regression,
                "commit": commit,
            },
        )
    return out
