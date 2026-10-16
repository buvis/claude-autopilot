"""cli/cap_check.py - classify a review file's HIGH/CRITICAL findings as
regressions introduced by the rework range between a previous review file's
`head_sha` and the current one's.

Every git call runs at the toplevel of `repo_root`, so the verb classifies the
same rows from any subdirectory. A File cell git cannot resolve at head makes
its row `regression: null` (a stall), never a clean `false` (a deferral).
"""

from __future__ import annotations

import posixpath
import re
import subprocess
from pathlib import Path

from . import frontmatter
from .findings_section import _reviewed_keys

_FILE_LINE_RE = re.compile(r"^(.*):(\d+(?:[-,]\d+)*)$")
_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
_ANNOTATION_RE = re.compile(r"\s*\([^)]*\)\s*$")
# ';' always splits; ',' splits only when the next non-space char is not a
# digit, so `a.py:3,9` stays one segment for _FILE_LINE_RE's comma list.
_SPLIT_RE = re.compile(r";|,(?!\s*\d)")
_HASH_L_RE = re.compile(r"^(.*)#[Ll](\d+)(?:-[Ll]?(\d+))?$")
_COLON_L_RE = re.compile(r"^(.*?):\s*[Ll]\s*(\d+)(?:-[Ll]?(\d+))?$")
# `path:N`, `path: N`, `path:N-M`; the comma list falls through to _FILE_LINE_RE.
_COLON_RANGE_RE = re.compile(r"^(.*?):\s*(\d+)(?:\s*-\s*(\d+))?$")


class CapCheckError(RuntimeError):
    """review_file could not be read, parsed, or diffed against git.
    `.stderr` carries git's raw stderr for a failed git call, else "" -
    `_missing_path_error` inspects only this field, never the formatted
    message (which also carries the command text)."""

    def __init__(self, message: str, stderr: str = ""):
        super().__init__(message)
        self.stderr = stderr


def rework_range(previous_head: str, head: str) -> tuple[str, str]:
    """(previous_head, head) unchanged - a thin named pair, not a lookup, so
    callers have one symbol to import instead of building the tuple inline."""
    return (previous_head, head)


def _head_sha(text: str, review_file: Path) -> str:
    sha = frontmatter.declared(text).get("head_sha", "").strip()
    if not sha:
        raise CapCheckError(f"{review_file} carries no head_sha frontmatter line")
    if not _SHA_RE.match(sha):
        raise CapCheckError(
            f"{review_file} carries a malformed head_sha: {sha!r} (need a full 40-hex sha)",
        )
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
        stderr = err.stderr.strip() if err.stderr else ""
        reason = stderr or str(err)
        raise CapCheckError(f"git {' '.join(args)} failed: {reason}", stderr) from err
    except OSError as err:
        raise CapCheckError(f"git {' '.join(args)} failed: {err}") from err
    return result.stdout.strip()


def _toplevel(repo_root: str | Path) -> Path:
    """The toplevel of the work tree holding `repo_root`; CapCheckError when
    `repo_root` is not inside a git work tree."""
    return Path(_git(repo_root, "rev-parse", "--show-toplevel"))


def _parse_number_list(spec: str) -> list[int]:
    """`spec` is the digits-and-separators suffix `_FILE_LINE_RE` captured
    (e.g. "3-5,9"): every named line, a range expanded in full."""
    lines: list[int] = []
    for token in spec.split(","):
        if "-" in token:
            first_s, last_s = token.split("-", 1)
            first, last = int(first_s), int(last_s)
            lines.extend(range(first, max(first, last) + 1))
        else:
            lines.append(int(token))
    return lines


def _split_file_line(cell: str) -> tuple[str, list[int] | None]:
    matched = _FILE_LINE_RE.match(cell)
    if matched is None:
        return cell, None
    return matched.group(1), _parse_number_list(matched.group(2))


def _clean_segment(segment: str) -> str:
    segment = segment.strip().strip("`").strip()
    return _ANNOTATION_RE.sub("", segment).strip().strip("`").strip()


def _segment_lines(segment: str) -> tuple[str, list[int] | None]:
    for regex in (_HASH_L_RE, _COLON_L_RE, _COLON_RANGE_RE):
        matched = regex.match(segment)
        if matched is not None:
            first = int(matched.group(2))
            last = int(matched.group(3)) if matched.group(3) else first
            return matched.group(1).strip(), list(range(first, max(first, last) + 1))
    path, lines = _split_file_line(segment)
    return path.strip(), lines


def _normalise_path(path: str, toplevel: Path, changed_files: set[str]) -> str:
    if Path(path).is_absolute():
        for candidate, top in ((Path(path), toplevel), (Path(path).resolve(), toplevel.resolve())):
            try:
                path = candidate.relative_to(top).as_posix()
                break
            except ValueError:
                continue
    else:
        path = posixpath.normpath(path)
    if path not in changed_files:
        folded = [f for f in changed_files if f.casefold() == path.casefold()]
        if len(folded) == 1:
            path = folded[0]
    return path


def _parse_file_cell(
    cell: str, toplevel: Path, changed_files: set[str],
) -> list[tuple[str, list[int] | None]]:
    """One File cell's (path, lines) pairs; `lines` is None for a path with no
    line spec, else every line the cell names (a range yields all of them, a
    comma list only its first, as before). An empty segment yields no pair."""
    cell = _ANNOTATION_RE.sub("", cell.strip().strip("`").strip())
    pairs = []
    for segment in _SPLIT_RE.split(cell):
        segment = _clean_segment(segment)
        if not segment:
            continue
        path, lines = _segment_lines(segment)
        if path:
            pairs.append((_normalise_path(path, toplevel, changed_files), lines))
    return pairs


def _verify_range(repo_root: str | Path, previous_head: str, head: str) -> None:
    """Prove the rework range instead of trusting it: CapCheckError naming
    the failing condition unless both shas are full 40-hex commits, differ,
    previous_head is an ancestor of head and head is reachable from HEAD."""
    for sha in (previous_head, head):
        if not _SHA_RE.match(sha):
            raise CapCheckError(f"head_sha {sha!r} is not a full 40-hex sha")
    for sha in (previous_head, head):
        try:
            _git(repo_root, "rev-parse", "--verify", "--quiet", f"{sha}^{{commit}}")
        except CapCheckError as err:
            raise CapCheckError(f"head_sha {sha} does not resolve to a commit", err.stderr) from err
    if previous_head.casefold() == head.casefold():
        raise CapCheckError(
            f"previous and current head_sha are equal ({head}); the rework range is empty",
        )
    checks = (
        (previous_head, head, f"previous head_sha {previous_head} is not an ancestor of head_sha {head}"),
        (head, "HEAD", f"head_sha {head} is not an ancestor of HEAD (not reachable from HEAD)"),
    )
    for ancestor, descendant, message in checks:
        try:
            _git(repo_root, "merge-base", "--is-ancestor", ancestor, descendant)
        except CapCheckError as err:
            raise CapCheckError(message, err.stderr) from err


def _missing_path_error(err: CapCheckError) -> bool:
    """True only when git's own stderr names a missing path. The formatted
    message is never read: it carries the command text, so a path spelled
    "does not exist.py" would otherwise mask a corrupt-object failure."""
    stderr = err.stderr.lower()
    return (
        "no such path" in stderr
        or "does not exist" in stderr
        or "exists on disk, but not in" in stderr
    )


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
    except CapCheckError as err:
        if _missing_path_error(err):
            return False
        raise
    return True


def _pair_commit(
    repo_root: Path,
    previous_head: str,
    head: str,
    path: str,
    lines: list[int] | None,
    rework_commits: set[str],
    changed_files: set[str],
) -> str | None:
    """The abbreviated commit that made an existing pair a regression, else
    None."""
    if lines is None:
        if path in changed_files:
            return _first_commit_touching(repo_root, previous_head, head, path)
        return None
    for line in lines:
        introducing = _introducing_commit(repo_root, head, path, line)
        if introducing is not None and introducing in rework_commits:
            return _git(repo_root, "log", "--format=%h", "-1", introducing)
    return None


def _classify_row(
    repo_root: Path,
    previous_head: str,
    head: str,
    row,
    rework_commits: set[str],
    changed_files: set[str],
) -> dict:
    """Row verdict over every (path, lines) pair of its File cell: null when
    any path is missing at head, else true when any pair is a regression,
    else false. `file`/`line` name the pair that decided the verdict."""
    pairs = _parse_file_cell(row.file, repo_root, changed_files)
    result = {"regression": False, "commit": None}
    decider = pairs[0] if pairs else ("", None)
    missing = [pair for pair in pairs if not _file_exists_at(repo_root, head, pair[0])]
    if missing:
        decider = missing[0]
        result = {
            "regression": None,
            "commit": None,
            "reason": f"unresolved path {decider[0]}",
        }
    else:
        for path, lines in pairs:
            commit = _pair_commit(
                repo_root, previous_head, head, path, lines, rework_commits, changed_files,
            )
            if commit is not None:
                decider = (path, lines)
                result = {"regression": True, "commit": commit}
                break
    return {
        "ref": row.ref,
        "severity": row.severity,
        "file": decider[0],
        "line": decider[1][0] if decider[1] else None,
        **result,
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
    if previous_review_file is None or not str(previous_review_file):
        return []
    previous_review_file = Path(previous_review_file)
    if not previous_review_file.exists():
        raise CapCheckError(f"{previous_review_file}: previous review file does not exist")

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

    toplevel = _toplevel(repo_root)
    _verify_range(toplevel, previous_head, head)

    rework_commits = set(
        _git(toplevel, "rev-list", f"{previous_head}..{head}").splitlines(),
    )
    changed_files = {
        name
        for name in _git(
            toplevel, "diff", "--name-only", "-z", previous_head, head,
        ).split("\0")
        if name
    }

    return [
        _classify_row(toplevel, previous_head, head, row, rework_commits, changed_files)
        for row in rows
    ]
