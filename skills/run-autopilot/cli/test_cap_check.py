"""cap-check classifier: which cap-time HIGH/CRITICAL findings did the last
rework introduce?

Fixture repo: a base commit (a.py, c.py, gone.py), a first rework commit that
rewrites a.py line 3 and deletes gone.py, and a second rework commit that adds
b.py, inserts a new line 4 into a.py and adds café.py (renaming nothing; PRD
00321). Two commits in the rework range is deliberate: a fixture with exactly
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
    # git's default; pinned so a global `core.quotePath false` cannot hide the
    # quoted non-ASCII name a newline-split `git diff --name-only` returns.
    _git(root, "config", "core.quotePath", "true")
    (root / "a.py").write_text("one = 1\ntwo = 2\nthree = 3\nfour = 4\nfive = 5\n")
    (root / "c.py").write_text("untouched = True\n")
    (root / "gone.py").write_text("x = 1\ny = 2\n")
    base = _commit(root, "base")
    (root / "a.py").write_text("one = 1\ntwo = 2\nthree = 33\nfour = 4\nfive = 5\n")
    (root / "gone.py").unlink()
    line_fix = _commit(root, "rework: fix a.py and delete gone.py")
    (root / "b.py").write_text("added = True\n")
    (root / "a.py").write_text(
        "one = 1\ntwo = 2\nthree = 33\nadded_four = 44\nfour = 4\nfive = 5\n"
    )
    (root / "café.py").write_text("accent = True\n", encoding="utf-8")
    rework = _commit(root, "rework: add b.py, a.py line 4 and café.py")
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


# --- PRD 00321: every File cell shape, the range proof, cwd independence ---


def _verdicts(rows: list[dict]) -> list[tuple]:
    return [(r["ref"], r["regression"], r["commit"]) for r in rows]


def test_multi_path_cell_is_regression_when_any_path_is(repo):
    """a.py line 4 was added by the rework; c.py was not touched. A cell
    naming both, in either order or split by ';', is a regression."""
    rows = _classify(
        repo,
        [
            ("R1", "HIGH", "a.py:4, c.py"),
            ("R2", "HIGH", "c.py, a.py:4"),
            ("R3", "HIGH", "c.py; a.py:4"),
        ],
    )

    assert _verdicts(rows) == [
        ("R1", True, repo["rework_short"]),
        ("R2", True, repo["rework_short"]),
        ("R3", True, repo["rework_short"]),
    ]


def test_range_cell_blames_every_line(repo):
    """`a.py:2-3`: line 2 is base, line 3 was rewritten by the first rework
    commit - blaming only the range's first line misses it."""
    rows = _classify(
        repo,
        [
            ("R1", "HIGH", "a.py:2-3"),
            ("R2", "HIGH", "a.py:1-4"),
            ("R3", "HIGH", "a.py:1-2"),
        ],
    )

    assert [(r["ref"], r["regression"]) for r in rows] == [
        ("R1", True),
        ("R2", True),
        ("R3", False),
    ]
    assert rows[0]["commit"] == repo["line_fix_short"]


def test_backtick_hash_l_and_colon_l_shapes_parse(repo):
    rows = _classify(
        repo,
        [
            ("R1", "HIGH", "`a.py:4`"),
            ("R2", "HIGH", "a.py#L4"),
            ("R3", "HIGH", "a.py:L4"),
            ("R4", "HIGH", "a.py: 4"),
            ("R5", "HIGH", "`b.py`"),
        ],
    )

    assert _verdicts(rows) == [
        ("R1", True, repo["rework_short"]),
        ("R2", True, repo["rework_short"]),
        ("R3", True, repo["rework_short"]),
        ("R4", True, repo["rework_short"]),
        ("R5", True, repo["rework_short"]),
    ]


def test_annotated_cell_is_parsed_without_its_note(repo):
    rows = _classify(
        repo,
        [
            ("R1", "HIGH", "a.py:4 (the new helper line)"),
            ("R2", "CRITICAL", "b.py (added file)"),
        ],
    )

    assert _verdicts(rows) == [
        ("R1", True, repo["rework_short"]),
        ("R2", True, repo["rework_short"]),
    ]


def test_absolute_in_repo_path_is_normalised(repo):
    """An absolute path under the toplevel classifies like its repo-relative
    form; the plain and dot-slash controls still classify correctly."""
    root = repo["root"]
    rows = _classify(
        repo,
        [
            ("R1", "HIGH", str(root / "b.py")),
            ("R2", "HIGH", f"{root / 'a.py'}:4"),
            ("R3", "HIGH", "a.py:3"),
            ("R4", "HIGH", "./a.py:3"),
        ],
    )

    assert _verdicts(rows) == [
        ("R1", True, repo["rework_short"]),
        ("R2", True, repo["rework_short"]),
        ("R3", True, repo["line_fix_short"]),
        ("R4", True, repo["line_fix_short"]),
    ]


def test_case_variant_path_matches_its_one_changed_file(repo):
    rows = _classify(repo, [("R1", "HIGH", "A.py:4"), ("R2", "HIGH", "B.PY")])

    assert _verdicts(rows) == [
        ("R1", True, repo["rework_short"]),
        ("R2", True, repo["rework_short"]),
    ]


def test_unresolved_path_counts_as_a_stall(repo):
    """A path git cannot resolve at head is never read as "not a regression":
    the row is null with a reason, and the verb exits 1 - for a line-ranged
    cell as well as a lineless one. Null wins over a resolvable regression in
    the same cell."""
    rows = _classify(
        repo,
        [
            ("R1", "HIGH", "missing.py:2-3"),
            ("R2", "HIGH", "missing.py"),
            ("R3", "HIGH", "a.py:3, missing.py"),
        ],
    )

    assert [(r["ref"], r["regression"], r.get("reason")) for r in rows] == [
        ("R1", None, "unresolved path missing.py"),
        ("R2", None, "unresolved path missing.py"),
        ("R3", None, "unresolved path missing.py"),
    ]

    previous = _review(repo["reviews"] / "review-1.md", repo["base"], [])
    for name, cell in (("ranged", "missing.py:2-3"), ("lineless", "missing.py")):
        current = _review(repo["reviews"] / f"{name}.md", repo["rework"], [("R1", "HIGH", cell)])
        result = _run_cap_check_cli(repo, current, previous)
        assert result.returncode == 1, (cell, result.stdout, result.stderr)
        assert '"regression": null' in result.stdout


def test_non_ascii_changed_file_matches(repo):
    rows = _classify(repo, [("R1", "HIGH", "café.py")])

    assert _verdicts(rows) == [("R1", True, repo["rework_short"])]


def test_subdirectory_cwd_classifies_the_same_rows(repo):
    """cap-check run from a subdirectory with no --repo-root (the cap-out
    prose's call shape) reports exactly what it reports from the toplevel."""
    import sys

    previous = _review(repo["reviews"] / "review-1.md", repo["base"], [])
    current = _review(
        repo["reviews"] / "review-2.md",
        repo["rework"],
        [("R1", "HIGH", "a.py:3"), ("R2", "HIGH", "b.py"), ("R3", "HIGH", "c.py")],
    )
    sub = repo["root"] / "sub"
    sub.mkdir()
    argv = [
        sys.executable, _MAIN, "cap-check",
        "--review-file", str(current), "--previous", str(previous),
    ]

    top = subprocess.run(argv, capture_output=True, text=True, timeout=30, cwd=repo["root"])
    nested = subprocess.run(argv, capture_output=True, text=True, timeout=30, cwd=sub)

    assert top.returncode == 1, top.stderr
    assert (nested.returncode, nested.stdout) == (top.returncode, top.stdout), nested.stderr


def _assert_exit_2_naming(result: subprocess.CompletedProcess, *words: str) -> None:
    assert result.returncode == 2, (result.stdout, result.stderr)
    assert "autopilot: cap-check:" in result.stderr
    assert any(word.lower() in result.stderr.lower() for word in words), (words, result.stderr)


def test_equal_or_reversed_head_shas_exit_2(repo):
    """The range is proven, never trusted: equal, reversed, non-descending
    and not-reachable-from-HEAD pairs exit 2 naming the failing condition."""
    root = repo["root"]
    reviews = repo["reviews"]
    rows = [("R1", "HIGH", "a.py:3"), ("R2", "HIGH", "a.py:1")]

    same_prev = _review(reviews / "same-1.md", repo["rework"], [])
    same_cur = _review(reviews / "same-2.md", repo["rework"], rows)
    _assert_exit_2_naming(
        _run_cap_check_cli(repo, same_cur, same_prev), "equal", "same", "identical", "differ",
    )

    rev_prev = _review(reviews / "rev-1.md", repo["rework"], [])
    rev_cur = _review(reviews / "rev-2.md", repo["base"], rows)
    _assert_exit_2_naming(_run_cap_check_cli(repo, rev_cur, rev_prev), "ancestor")

    _git(root, "checkout", "-q", "-b", "side", repo["base"])
    (root / "side.py").write_text("side = True\n")
    side = _commit(root, "side branch commit")
    _git(root, "checkout", "-q", "-")

    off_prev = _review(reviews / "off-1.md", repo["base"], [])
    off_cur = _review(reviews / "off-2.md", side, rows)
    _assert_exit_2_naming(_run_cap_check_cli(repo, off_cur, off_prev), "ancestor", "reachable")

    sib_prev = _review(reviews / "sib-1.md", side, [])
    sib_cur = _review(reviews / "sib-2.md", repo["rework"], rows)
    _assert_exit_2_naming(_run_cap_check_cli(repo, sib_cur, sib_prev), "ancestor")


def test_ref_name_head_sha_exits_2(repo):
    """A branch named beef (hex-looking, later pointed at base) and an
    abbreviated sha are not full 40-hex shas: exit 2, never a deferral."""
    root = repo["root"]
    reviews = repo["reviews"]
    rows = [("R1", "HIGH", "a.py:3")]
    _git(root, "branch", "beef", repo["base"])
    short = _git(root, "rev-parse", "--short", repo["rework"])

    previous = _review(reviews / "review-1.md", repo["base"], [])
    branch_cur = _review(reviews / "branch-cur.md", "beef", rows)
    _assert_exit_2_naming(_run_cap_check_cli(repo, branch_cur, previous), "beef")

    branch_prev = _review(reviews / "branch-prev.md", "beef", [])
    current = _review(reviews / "review-2.md", repo["rework"], rows)
    _assert_exit_2_naming(_run_cap_check_cli(repo, current, branch_prev), "beef")

    short_cur = _review(reviews / "short.md", short, rows)
    _assert_exit_2_naming(_run_cap_check_cli(repo, short_cur, previous), short, "40")


def test_blame_failure_propagates_from_file_exists_at(repo, monkeypatch):
    """Only a missing path reads as "does not exist at head": a corrupt
    object (or any other git failure) propagates from _file_exists_at and
    from _introducing_commit, even when the command text itself happens to
    contain "does not exist"."""
    from cli import cap_check

    real_git = cap_check._git

    def _cat_file_fails_oddly(repo_root, *args):
        if args[:1] == ("cat-file",):
            raise cap_check.CapCheckError("git cat-file failed: fatal: object is corrupt")
        return real_git(repo_root, *args)

    monkeypatch.setattr(cap_check, "_git", _cat_file_fails_oddly)

    with pytest.raises(cap_check.CapCheckError):
        cap_check._file_exists_at(repo["root"], repo["rework"], "b.py")
    with pytest.raises(cap_check.CapCheckError):
        _classify(repo, [("R1", "HIGH", "b.py")])

    def _always_fails(repo_root, *args):
        err = cap_check.CapCheckError(
            "git blame -- does not exist.py failed: fatal: object is corrupt",
        )
        err.stderr = "fatal: object is corrupt"
        raise err

    monkeypatch.setattr(cap_check, "_git", _always_fails)

    with pytest.raises(cap_check.CapCheckError):
        cap_check._file_exists_at(repo["root"], repo["rework"], "does not exist.py")
    with pytest.raises(cap_check.CapCheckError):
        cap_check._introducing_commit(repo["root"], repo["rework"], "does not exist.py", 1)


def test_missing_path_detection_reads_stderr_only(repo):
    from cli.cap_check import CapCheckError, _git, _missing_path_error

    assert CapCheckError("plain").stderr == ""

    decoy = CapCheckError(
        "git cat-file -e abc:does not exist.py failed: fatal: bad object abc",
        stderr="fatal: bad object abc",
    )
    assert not _missing_path_error(decoy)

    assert _missing_path_error(
        CapCheckError("git blame failed", stderr="fatal: no such path 'x.py' in abc"),
    )
    assert _missing_path_error(
        CapCheckError("git cat-file failed", stderr="fatal: path 'x.py' Does Not Exist in 'abc'"),
    )

    with pytest.raises(CapCheckError) as real:
        _git(repo["root"], "cat-file", "-e", f"{repo['rework']}:nothere.py")
    assert "nothere.py" in real.value.stderr
    assert _missing_path_error(real.value)
