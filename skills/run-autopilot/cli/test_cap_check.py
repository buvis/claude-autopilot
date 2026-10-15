"""cap-check classifier: which cap-time HIGH/CRITICAL findings did the last
rework introduce?

Fixture repo: a base commit (a.py, c.py, gone.py), a first rework commit that
rewrites a.py line 3 and deletes gone.py, and a second rework commit that adds
b.py. Two commits in the rework range is deliberate: a fixture with exactly
one commit cannot distinguish "the commit that introduced the row" from "the
rework range's head commit" - the two always coincide. The previous review
file names the base commit via `head_sha`, the current one names the second
rework commit.
Imports sit inside each test so the module's absence fails every test, not
collection.
"""

import subprocess
from pathlib import Path

import pytest


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        [
            "git",
            "-c", "user.name=t",
            "-c", "user.email=t@example.com",
            "-c", "commit.gpgsign=false",
            "-c", "core.hooksPath=/dev/null",
            *args,
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _commit(root: Path, message: str) -> str:
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", message)
    return _git(root, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path: Path) -> dict:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    (root / "a.py").write_text("one = 1\ntwo = 2\nthree = 3\nfour = 4\nfive = 5\n")
    (root / "c.py").write_text("untouched = True\n")
    (root / "gone.py").write_text("x = 1\ny = 2\n")
    base = _commit(root, "base")
    (root / "a.py").write_text("one = 1\ntwo = 2\nthree = 33\nfour = 4\nfive = 5\n")
    (root / "gone.py").unlink()
    line_fix = _commit(root, "rework: fix a.py and delete gone.py")
    (root / "b.py").write_text("added = True\n")
    rework = _commit(root, "rework: add b.py")
    return {
        "root": root,
        "base": base,
        "line_fix": line_fix,
        "line_fix_short": _git(root, "log", "--format=%h", "-1", line_fix),
        "rework": rework,
        "rework_short": _git(root, "log", "--format=%h", "-1", rework),
        "reviews": tmp_path,
    }


def _review(path: Path, head_sha: str | None, rows: list[tuple[str, str, str]]) -> Path:
    front = f"---\nhead_sha: {head_sha}\n---\n\n" if head_sha else "---\nreviewer: t\n---\n\n"
    table = "| Ref | Severity | File | Issue |\n|-----|----------|------|-------|\n"
    table += "".join(f"| {ref} | {sev} | {file} | issue {ref} |\n" for ref, sev, file in rows)
    path.write_text(f"{front}# Review\n\n## Consolidated Findings\n\n{table}")
    return path


def _classify(repo: dict, rows: list[tuple[str, str, str]]) -> list[dict]:
    from cli.cap_check import classify_findings

    previous = _review(repo["reviews"] / "review-1.md", repo["base"], [])
    current = _review(repo["reviews"] / "review-2.md", repo["rework"], rows)
    return classify_findings(repo["root"], current, previous)


def test_line_blamed_to_its_introducing_rework_commit_is_regression(repo):
    """a.py:3 was rewritten by the FIRST rework commit, not the range's head -
    this is what the two-commit fixture exists to prove."""
    rows = _classify(repo, [("R1", "HIGH", "a.py:3")])

    assert rows == [
        {
            "ref": "R1",
            "severity": "high",
            "file": "a.py",
            "line": 3,
            "regression": True,
            "commit": repo["line_fix_short"],
        }
    ]


def test_file_only_row_is_attributed_to_the_commit_that_added_it(repo):
    """b.py was added by the SECOND rework commit, not the first - a file-only
    row must name the commit that actually touched the file, not the range's
    last commit unconditionally."""
    rows = _classify(repo, [("R2", "CRITICAL", "b.py")])

    assert rows == [
        {
            "ref": "R2",
            "severity": "critical",
            "file": "b.py",
            "line": None,
            "regression": True,
            "commit": repo["rework_short"],
        }
    ]


def test_rows_outside_rework_range_are_not_regressions(repo):
    rows = _classify(
        repo,
        [
            ("R1", "HIGH", "a.py:1"),
            ("R2", "HIGH", "c.py"),
            ("R3", "CRITICAL", "gone.py:2"),
            ("R4", "HIGH", "missing.py:2"),
        ],
    )

    assert [(r["ref"], r["file"], r["line"], r["regression"], r["commit"]) for r in rows] == [
        ("R1", "a.py", 1, False, None),
        ("R2", "c.py", None, False, None),
        ("R3", "gone.py", 2, False, None),
        ("R4", "missing.py", 2, False, None),
    ]


def test_deleted_file_only_row_is_not_a_regression(repo):
    """gone.py is still in `git diff --name-only` for the rework range (it was
    deleted there), but it no longer exists at head - a file-only row naming it
    must not be classified a regression just because the path appears in the
    diff."""
    rows = _classify(repo, [("R1", "CRITICAL", "gone.py")])

    assert rows == [
        {
            "ref": "R1",
            "severity": "critical",
            "file": "gone.py",
            "line": None,
            "regression": False,
            "commit": None,
        }
    ]


def test_line_range_and_comma_cells_are_parsed_to_their_first_line(repo):
    """A File cell holding a line range (`a.py:3-4`) or a comma list
    (`a.py:3,9`) must still split the file from the line - the rest of the
    cell content never feeds back into the parsed file name."""
    rows = _classify(repo, [("R1", "HIGH", "a.py:3-4"), ("R2", "HIGH", "a.py:3,9")])

    assert [(r["file"], r["line"], r["regression"]) for r in rows] == [
        ("a.py", 3, True),
        ("a.py", 3, True),
    ]


def test_row_without_file_is_not_regression(repo):
    rows = _classify(repo, [("R1", "HIGH", "")])

    assert rows == [
        {
            "ref": "R1",
            "severity": "high",
            "file": "",
            "line": None,
            "regression": False,
            "commit": None,
        }
    ]


def test_medium_and_low_rows_are_never_classified(repo):
    rows = _classify(
        repo,
        [
            ("R1", "MEDIUM", "a.py:3"),
            ("R2", "CRITICAL", "c.py:1"),
            ("R3", "LOW", "b.py"),
            ("R4", "HIGH", "a.py:3"),
        ],
    )

    assert [(r["ref"], r["severity"], r["regression"]) for r in rows] == [
        ("R2", "critical", False),
        ("R4", "high", True),
    ]


def test_medium_and_low_only_rows_never_invoke_git(repo, monkeypatch):
    """Severity filtering must happen before either git call - a review file
    with no HIGH/CRITICAL row takes no git path at all."""
    from cli import cap_check

    def _fail(*args, **kwargs):
        raise AssertionError("git must not be called when no high/critical row survives")

    monkeypatch.setattr(cap_check, "_git", _fail)
    rows = _classify(repo, [("R1", "MEDIUM", "a.py:3"), ("R2", "LOW", "b.py")])

    assert rows == []


def test_missing_previous_review_yields_no_rows(repo):
    from cli.cap_check import classify_findings

    current = _review(repo["reviews"] / "review-2.md", repo["rework"], [("R1", "HIGH", "a.py:3")])

    assert classify_findings(repo["root"], current, None) == []
    assert classify_findings(repo["root"], current, repo["reviews"] / "absent.md") == []
    assert classify_findings(repo["root"], current, "") == []


def test_unreadable_head_sha_raises_cap_check_error(repo):
    from cli.cap_check import CapCheckError, classify_findings

    assert issubclass(CapCheckError, RuntimeError)
    previous = _review(repo["reviews"] / "review-1.md", repo["base"], [])
    no_sha = _review(repo["reviews"] / "no-sha.md", None, [("R1", "HIGH", "a.py:3")])
    unknown = _review(repo["reviews"] / "unknown.md", "f" * 40, [("R1", "HIGH", "a.py:3")])
    bad_sha = _review(repo["reviews"] / "bad-sha.md", "-rf", [("R1", "HIGH", "a.py:3")])

    with pytest.raises(CapCheckError):
        classify_findings(repo["root"], no_sha, previous)
    with pytest.raises(CapCheckError):
        classify_findings(repo["root"], unknown, previous)
    with pytest.raises(CapCheckError):
        classify_findings(repo["root"], bad_sha, previous)


def test_invalid_utf8_in_review_file_raises_cap_check_error(repo):
    from cli.cap_check import CapCheckError, classify_findings

    previous = _review(repo["reviews"] / "review-1.md", repo["base"], [])
    broken = repo["reviews"] / "broken.md"
    broken.write_bytes(b"---\nhead_sha: " + repo["rework"].encode() + b"\n---\n\xff\xfe")

    with pytest.raises(CapCheckError):
        classify_findings(repo["root"], broken, previous)


def test_git_blame_failure_other_than_missing_path_raises_cap_check_error(repo, monkeypatch):
    """Only a missing-path blame failure reads as "not a regression" - any
    other git failure (a corrupt object, an out-of-range line) must propagate
    as CapCheckError rather than silently clearing the row."""
    from cli import cap_check

    real_git = cap_check._git

    def _blame_fails_oddly(repo_root, *args):
        if args[:1] == ("blame",):
            raise cap_check.CapCheckError("git blame failed: object is corrupt")
        return real_git(repo_root, *args)

    monkeypatch.setattr(cap_check, "_git", _blame_fails_oddly)

    with pytest.raises(cap_check.CapCheckError):
        _classify(repo, [("R1", "HIGH", "a.py:3")])


def test_rework_range_returns_endpoints_unchanged():
    from cli.cap_check import rework_range

    assert rework_range("abc1234", "def5678") == ("abc1234", "def5678")


_MAIN = str(Path(__file__).resolve().parent / "__main__.py")


def _run_cap_check_cli(
    repo: dict,
    review_file: Path,
    previous: Path | None,
) -> subprocess.CompletedProcess:
    import sys

    argv = [
        sys.executable,
        _MAIN,
        "cap-check",
        "--review-file",
        str(review_file),
        "--repo-root",
        str(repo["root"]),
    ]
    if previous is not None:
        argv += ["--previous", str(previous)]
    return subprocess.run(argv, capture_output=True, text=True, timeout=30)


def test_exit_1_on_any_regression_and_0_otherwise(repo):
    previous = _review(repo["reviews"] / "review-1.md", repo["base"], [])
    regressed = _review(repo["reviews"] / "review-2.md", repo["rework"], [("R1", "HIGH", "a.py:3")])
    clean = _review(repo["reviews"] / "review-3.md", repo["rework"], [("R1", "HIGH", "a.py:1")])

    regressed_run = _run_cap_check_cli(repo, regressed, previous)
    assert regressed_run.returncode == 1
    assert '"regression": true' in regressed_run.stdout
    assert f'"commit": "{repo["line_fix_short"]}"' in regressed_run.stdout

    assert _run_cap_check_cli(repo, clean, previous).returncode == 0


def test_omitted_previous_exits_0_with_no_output(repo):
    current = _review(repo["reviews"] / "review-2.md", repo["rework"], [("R1", "HIGH", "a.py:3")])

    result = _run_cap_check_cli(repo, current, None)

    assert result.returncode == 0
    assert result.stdout == ""


def test_unreadable_head_sha_exits_2(repo):
    previous = _review(repo["reviews"] / "review-1.md", repo["base"], [])
    no_sha = _review(repo["reviews"] / "no-sha.md", None, [("R1", "HIGH", "a.py:3")])

    result = _run_cap_check_cli(repo, no_sha, previous)

    assert result.returncode == 2
    assert "autopilot: cap-check:" in result.stderr
