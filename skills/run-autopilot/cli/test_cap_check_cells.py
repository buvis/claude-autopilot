"""cap-check classifier: File cells that are unreadable, wrapped in backticks,
directories, annotated with nested parentheses, comma-named or malformed.

Sibling of test_cap_check.py (which sits near the file size limit); the
`repo` fixture and the review helpers are reused from there.
"""

import pytest

from cli.test_cap_check import _classify, _commit, _git, _review, _verdicts, repo


def _classify_range(repo: dict, previous_head: str, head: str, rows: list) -> list[dict]:
    from cli.cap_check import classify_findings

    previous = _review(repo["reviews"] / "range-1.md", previous_head, [])
    current = _review(repo["reviews"] / "range-2.md", head, rows)
    return classify_findings(repo["root"], current, previous)


@pytest.mark.parametrize("cell", ["../x.py", "a.py:9999", "a.py:0"])
def test_unreadable_cell_is_unresolved_and_does_not_abort_other_rows(repo, cell):
    rows = _classify(
        repo,
        [("R1", "HIGH", "a.py:3"), ("R2", "HIGH", cell), ("R3", "CRITICAL", "b.py")],
    )

    assert [r["ref"] for r in rows] == ["R1", "R2", "R3"]
    assert (rows[0]["regression"], rows[0]["commit"]) == (True, repo["line_fix_short"])
    assert rows[1]["regression"] is None
    assert rows[1]["commit"] is None
    assert rows[1]["reason"]
    assert (rows[2]["regression"], rows[2]["commit"]) == (True, repo["rework_short"])


@pytest.mark.parametrize(
    "cell",
    ["`a.py`:4", "a.py:4 `b.py`", "a.py:4 (note (nested))"],
)
def test_wrapped_or_nested_annotated_cell_classifies_like_bare_a_py_4(repo, cell):
    bare, wrapped = _classify(repo, [("R1", "HIGH", "a.py:4"), ("R2", "HIGH", cell)])

    assert bare["regression"] is True
    assert wrapped["regression"] is True
    assert wrapped["commit"] == repo["rework_short"] == bare["commit"]


def test_nested_parenthesis_annotation_is_not_read_as_part_of_the_path(repo):
    rows = _classify(repo, [("R1", "HIGH", "a.py:1 (note (nested))")])

    assert _verdicts(rows) == [("R1", False, None)]
    assert (rows[0]["file"], rows[0]["line"]) == ("a.py", 1)


def test_filename_with_comma_is_one_path_and_comma_space_still_splits(repo):
    root = repo["root"]
    (root / "a,b.py").write_text("comma = True\n")
    comma_commit = _commit(root, "add a,b.py")
    short = _git(root, "log", "--format=%h", "-1", comma_commit)

    rows = _classify_range(
        repo,
        repo["rework"],
        comma_commit,
        [("R1", "HIGH", "a,b.py"), ("R2", "HIGH", "c.py, a,b.py")],
    )

    assert _verdicts(rows) == [("R1", True, short), ("R2", True, short)]
    assert rows[0]["file"] == "a,b.py"

    split = _classify(repo, [("R3", "HIGH", "b.py, a.py:4")])
    assert _verdicts(split) == [("R3", True, repo["rework_short"])]


def test_directory_cell_is_regression_only_when_rework_touched_its_subtree(repo):
    root = repo["root"]
    (root / "untouched").mkdir()
    (root / "untouched" / "u.py").write_text("u = 1\n")
    before = _commit(root, "add untouched/u.py")
    (root / "sub").mkdir()
    (root / "sub" / "x.py").write_text("x = 1\n")
    touch = _commit(root, "add sub/x.py")
    short = _git(root, "log", "--format=%h", "-1", touch)

    rows = _classify_range(
        repo,
        before,
        touch,
        [
            ("R1", "HIGH", "sub/"),
            ("R2", "HIGH", "sub"),
            ("R3", "HIGH", "untouched/"),
            ("R4", "HIGH", "untouched"),
        ],
    )

    assert _verdicts(rows) == [
        ("R1", True, short),
        ("R2", True, short),
        ("R3", False, None),
        ("R4", False, None),
    ]


def test_malformed_numeric_suffix_raises_cap_check_error_naming_the_spec(repo):
    from cli.cap_check import CapCheckError

    with pytest.raises(CapCheckError, match="1-2-3"):
        _classify(repo, [("R1", "HIGH", "a.py:1-2-3")])


def test_missing_path_stays_unresolved_under_a_non_english_git_locale(repo, monkeypatch):
    for name in ("LANG", "LC_ALL", "LC_MESSAGES", "LANGUAGE"):
        monkeypatch.setenv(name, "cs_CZ.UTF-8")

    rows = _classify(repo, [("R1", "HIGH", "missing.py:2"), ("R2", "HIGH", "missing.py")])

    assert [(r["ref"], r["regression"], bool(r["reason"])) for r in rows] == [
        ("R1", None, True),
        ("R2", None, True),
    ]
