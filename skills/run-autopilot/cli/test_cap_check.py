"""cap-check classifier: which cap-time HIGH/CRITICAL findings did the last
rework introduce?

Fixture repo: a base commit (a.py, c.py, gone.py) and a rework commit that
rewrites a.py line 3, adds b.py and deletes gone.py. The previous review file
names the base commit via `head_sha`, the current one names the rework commit.
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
    (root / "b.py").write_text("added = True\n")
    (root / "gone.py").unlink()
    rework = _commit(root, "rework")
    return {
        "root": root,
        "base": base,
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


def test_line_blamed_to_rework_commit_is_regression(repo):
    rows = _classify(repo, [("R1", "HIGH", "a.py:3")])

    assert rows == [
        {
            "ref": "R1",
            "severity": "high",
            "file": "a.py",
            "line": 3,
            "regression": True,
            "commit": repo["rework_short"],
        }
    ]


def test_file_changed_in_rework_without_line_is_regression(repo):
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


def test_missing_previous_review_yields_no_rows(repo):
    from cli.cap_check import classify_findings

    current = _review(repo["reviews"] / "review-2.md", repo["rework"], [("R1", "HIGH", "a.py:3")])

    assert classify_findings(repo["root"], current, None) == []
    assert classify_findings(repo["root"], current, repo["reviews"] / "absent.md") == []


def test_unreadable_head_sha_raises_cap_check_error(repo):
    from cli.cap_check import CapCheckError, classify_findings

    assert issubclass(CapCheckError, RuntimeError)
    previous = _review(repo["reviews"] / "review-1.md", repo["base"], [])
    no_sha = _review(repo["reviews"] / "no-sha.md", None, [("R1", "HIGH", "a.py:3")])
    unknown = _review(repo["reviews"] / "unknown.md", "f" * 40, [("R1", "HIGH", "a.py:3")])

    with pytest.raises(CapCheckError):
        classify_findings(repo["root"], no_sha, previous)
    with pytest.raises(CapCheckError):
        classify_findings(repo["root"], unknown, previous)


def test_rework_range_returns_endpoints_unchanged():
    from cli.cap_check import rework_range

    assert rework_range("abc1234", "def5678") == ("abc1234", "def5678")


_MAIN = str(Path(__file__).resolve().parent / "__main__.py")


def _run_cap_check_cli(repo: dict, review_file: Path, previous: Path) -> subprocess.CompletedProcess:
    import sys

    return subprocess.run(
        [
            sys.executable,
            _MAIN,
            "cap-check",
            "--review-file",
            str(review_file),
            "--previous",
            str(previous),
            "--repo-root",
            str(repo["root"]),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_exit_1_on_any_regression_and_0_otherwise(repo):
    previous = _review(repo["reviews"] / "review-1.md", repo["base"], [])
    regressed = _review(repo["reviews"] / "review-2.md", repo["rework"], [("R1", "HIGH", "a.py:3")])
    clean = _review(repo["reviews"] / "review-3.md", repo["rework"], [("R1", "HIGH", "a.py:1")])

    assert _run_cap_check_cli(repo, regressed, previous).returncode == 1
    assert _run_cap_check_cli(repo, clean, previous).returncode == 0


def test_unreadable_head_sha_exits_2(repo):
    previous = _review(repo["reviews"] / "review-1.md", repo["base"], [])
    no_sha = _review(repo["reviews"] / "no-sha.md", None, [("R1", "HIGH", "a.py:3")])

    assert _run_cap_check_cli(repo, no_sha, previous).returncode == 2
