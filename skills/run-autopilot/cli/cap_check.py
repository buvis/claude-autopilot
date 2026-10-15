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

_FILE_LINE_RE = re.compile(r"^(.*):(\d+)(?:[-,]\d+)*$")
_SHA_RE = re.compile(r"^[0-9a-fA-F]{4,40}$")


class CapCheckError(RuntimeError):
    """review_file could not be read, parsed, or diffed against git."""


def rework_range(previous_head: str, head: str) -> tuple[str, str]:
    """(previous_head, head) unchanged - a thin named pair, not a lookup, so
    callers have one symbol to import instead of building the tuple inline."""
    return (previous_head, head)


def _head_sha(text: str, review_file: Path) -> str:
    sha = frontmatter.declared(text).get("head_sha", "").strip()
    if not sha:
        raise CapCheckError(f"{review_file} carries no head_sha frontmatter line")
    if not _SHA_RE.match(sha):
        raise CapCheckError(f"{review_file} carries a malformed head_sha: {sha!r}")
    return sha


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as err:
        raise CapCheckError(f"cannot read {path}: {err}") from err


def _git(repo_root: str | Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as err:
        reason = err.stderr.strip() if err.stderr else str(err)
        raise CapCheckError(f"git {' '.join(args)} failed: {reason}") from err
    except OSError as err:
        raise CapCheckError(f"git {' '.join(args)} failed: {err}") from err
    return result.stdout.strip()


def _split_file_line(cell: str) -> tuple[str, int | None]:
    matched = _FILE_LINE_RE.match(cell)
    if matched is None:
        return cell, None
    return matched.group(1), int(matched.group(2))


def _missing_path_error(err: CapCheckError) -> bool:
    """True only for a git failure that names a missing path, never any other
    git error - those must propagate as CapCheckError per the spec, not be
    read as "not a regression"."""
    message = str(err).lower()
    return "no such path" in message or "does not exist" in message


def _introducing_commit(
    repo_root: str | Path,
    head: str,
    file: str,
    line: int,
) -> str | None:
    try:
        blame = _git(
            repo_root, "blame", "-L", f"{line},{line}", "--porcelain", head, "--", file,
        )
    except CapCheckError as err:
        if _missing_path_error(err):
            return None
        raise
    if not blame:
        return None
    return blame.splitlines()[0].split()[0]


def _first_commit_touching(
    repo_root: str | Path,
    previous_head: str,
    head: str,
    file: str,
) -> str | None:
    log = _git(
        repo_root,
        "log",
        "--format=%h",
        "--reverse",
        f"{previous_head}..{head}",
        "--",
        file,
    )
    lines = log.splitlines()
    return lines[0] if lines else None


def _file_exists_at(repo_root: str | Path, head: str, file: str) -> bool:
    try:
        _git(repo_root, "cat-file", "-e", f"{head}:{file}")
    except CapCheckError:
        return False
    return True


def _classify_row(
    repo_root: str | Path,
    previous_head: str,
    head: str,
    row,
    rework_commits: set[str],
    changed_files: set[str],
) -> dict:
    file, line = _split_file_line(row.file)
    regression = False
    commit = None
    if file:
        if line is not None:
            introducing = _introducing_commit(repo_root, head, file, line)
            if introducing is not None and introducing in rework_commits:
                regression = True
                commit = _git(repo_root, "log", "--format=%h", "-1", introducing)
        elif file in changed_files and _file_exists_at(repo_root, head, file):
            commit = _first_commit_touching(repo_root, previous_head, head, file)
            regression = commit is not None
    return {
        "ref": row.ref,
        "severity": row.severity,
        "file": file,
        "line": line,
        "regression": regression,
        "commit": commit,
    }


def classify_findings(
    repo_root: str | Path,
    review_file: str | Path,
    previous_review_file: str | Path | None,
) -> list[dict]:
    """Every high/critical row of `review_file`'s Consolidated Findings
    section, classified against the rework range between
    `previous_review_file`'s head_sha and `review_file`'s head_sha."""
    review_file = Path(review_file)
    if previous_review_file is None or not str(previous_review_file) or not Path(
        previous_review_file,
    ).exists():
        return []
    previous_review_file = Path(previous_review_file)

    text = _read_text(review_file)
    rows, problem = _reviewed_keys(text)
    if problem is not None:
        raise CapCheckError(f"{review_file}: {problem}")

    rows = [row for row in rows if row.severity in ("high", "critical")]
    if not rows:
        return []

    head = _head_sha(text, review_file)
    previous_text = _read_text(previous_review_file)
    previous_head = _head_sha(previous_text, previous_review_file)
    previous_head, head = rework_range(previous_head, head)

    rework_commits = set(
        _git(repo_root, "rev-list", f"{previous_head}..{head}").splitlines(),
    )
    changed_files = set(
        _git(repo_root, "diff", "--name-only", f"{previous_head}..{head}").splitlines(),
    )

    return [
        _classify_row(repo_root, previous_head, head, row, rework_commits, changed_files)
        for row in rows
    ]
