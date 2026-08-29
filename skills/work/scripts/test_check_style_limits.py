"""Behavioural contract for check_style_limits.py (PRD 00140).

The script reports only the coding-style limit violations a diff itself
introduces: functions over 50 lines whose line span a diff's new-side hunk
range touches, and files the diff pushed over 800 lines. Pre-existing debt
(an untouched over-limit function, a file already over 800 before the
diff) is deliberately not reported here - that is scope for the review
lens, not this regression check.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

_MODULE_PATH = Path(__file__).with_name("check_style_limits.py")
_SPEC = importlib.util.spec_from_file_location("check_style_limits", _MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
csl = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(csl)


def _write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_MODULE_PATH), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def _long_function(name: str, n_lines: int) -> str:
    """A `def name():` line followed by (n_lines - 1) body lines, so the
    function's total line count is exactly n_lines."""
    body = "\n".join("    x = 1" for _ in range(n_lines - 1))
    return f"def {name}():\n{body}\n"


def _write_over_limit_diff(tmp_path: Path) -> tuple[Path, str]:
    """A 2-line stub expanded by the diff into a 51-line function - the
    whole function is on the diff's new side, so it is fully "touched"."""
    func_text = _long_function("over_limit", 51)
    py_file = _write(tmp_path, "mod.py", func_text)
    diff_text = (
        "diff --git a/mod.py b/mod.py\n"
        "--- a/mod.py\n"
        "+++ b/mod.py\n"
        "@@ -1,2 +1,51 @@\n"
        "-def over_limit():\n"
        "-    pass\n" + "".join(f"+{line}\n" for line in func_text.splitlines())
    )
    return py_file, diff_text


def _write_clean_diff(tmp_path: Path) -> tuple[Path, str]:
    py_file = _write(tmp_path, "mod.py", "def small():\n    return 1\n")
    diff_text = (
        "diff --git a/mod.py b/mod.py\n"
        "--- a/mod.py\n"
        "+++ b/mod.py\n"
        "@@ -1,2 +1,2 @@\n"
        "-def small():\n"
        "-    return 0\n"
        "+def small():\n"
        "+    return 1\n"
    )
    return py_file, diff_text


# --- touched_ranges ---------------------------------------------------------


def test_touched_ranges_strips_the_b_prefix_from_the_diff_path() -> None:
    diff_text = (
        "diff --git a/pkg/mod.py b/pkg/mod.py\n"
        "--- a/pkg/mod.py\n"
        "+++ b/pkg/mod.py\n"
        "@@ -10,3 +10,5 @@ def something():\n"
        " context line\n"
        "+added line\n"
        "+added line\n"
        " context line\n"
        " context line\n"
    )
    ranges = csl.touched_ranges(diff_text)
    assert list(ranges.keys()) == ["pkg/mod.py"]
    assert ranges["pkg/mod.py"] == [(10, 14)]


def test_touched_ranges_header_without_a_count_is_a_single_line() -> None:
    diff_text = (
        "diff --git a/mod.py b/mod.py\n"
        "--- a/mod.py\n"
        "+++ b/mod.py\n"
        "@@ -1,1 +1 @@\n"
        "-old line\n"
        "+new line\n"
    )
    assert csl.touched_ranges(diff_text)["mod.py"] == [(1, 1)]


def test_touched_ranges_pure_deletion_hunk_contributes_no_range() -> None:
    diff_text = (
        "diff --git a/mod.py b/mod.py\n"
        "--- a/mod.py\n"
        "+++ b/mod.py\n"
        "@@ -10,2 +9,0 @@\n"
        "-removed line one\n"
        "-removed line two\n"
    )
    # Key presence for a file whose only hunk is a pure deletion isn't
    # pinned by the contract - only that it contributes no range. `.get`
    # keeps this assertion agnostic to that unstated detail.
    assert csl.touched_ranges(diff_text).get("mod.py", []) == []


# --- function violations -----------------------------------------------------


def test_touched_function_over_fifty_lines_is_reported(tmp_path: Path) -> None:
    py_file, diff_text = _write_over_limit_diff(tmp_path)
    assert csl.violations(diff_text, [py_file]) == [
        f"FUNCTION | {py_file}:1 | over_limit | 51 lines",
    ]


def test_untouched_function_over_fifty_lines_in_same_file_is_not_reported(
    tmp_path: Path,
) -> None:
    edited = ["def edited():", "    x = 1", "    x = 2"]
    gap = [""] * 12
    text = "\n".join(edited + gap) + "\n" + _long_function("never_touched", 51)
    py_file = _write(tmp_path, "mod.py", text)
    diff_text = (
        "diff --git a/mod.py b/mod.py\n"
        "--- a/mod.py\n"
        "+++ b/mod.py\n"
        "@@ -1,3 +1,3 @@\n"
        "-def edited():\n"
        "-    x = 1\n"
        "-    x = 0\n"
        "+def edited():\n"
        "+    x = 1\n"
        "+    x = 2\n"
    )
    assert csl.violations(diff_text, [py_file]) == []


def test_all_deletions_diff_never_reports_a_function_line(tmp_path: Path) -> None:
    py_file = _write(tmp_path, "mod.py", _long_function("survivor", 51))
    diff_text = (
        "diff --git a/mod.py b/mod.py\n"
        "--- a/mod.py\n"
        "+++ b/mod.py\n"
        "@@ -1,5 +1,0 @@\n"
        "-def old_helper():\n"
        "-    x = 1\n"
        "-    x = 2\n"
        "-    x = 3\n"
        "-    x = 4\n"
    )
    assert csl.violations(diff_text, [py_file]) == []


def test_deletion_hunk_with_trailing_context_does_not_report_the_function_it_surrounds(
    tmp_path: Path,
) -> None:
    py_file = _write(tmp_path, "mod.py", _long_function("survivor", 51))
    diff_text = (
        "diff --git a/mod.py b/mod.py\n"
        "--- a/mod.py\n"
        "+++ b/mod.py\n"
        "@@ -1,8 +1,3 @@\n"
        "-def old_helper():\n"
        "-    x = 1\n"
        "-    x = 2\n"
        "-    x = 3\n"
        "-    x = 4\n"
        " def survivor():\n"
        "     x = 1\n"
        "     x = 1\n"
    )
    assert csl.violations(diff_text, [py_file]) == []


def test_hunk_with_an_addition_still_contributes_its_range_and_reports_the_function(
    tmp_path: Path,
) -> None:
    text = "# note\n" + _long_function("survivor", 51)
    py_file = _write(tmp_path, "mod.py", text)
    diff_text = (
        "diff --git a/mod.py b/mod.py\n"
        "--- a/mod.py\n"
        "+++ b/mod.py\n"
        "@@ -1,8 +1,4 @@\n"
        "-def old_helper():\n"
        "-    x = 1\n"
        "-    x = 2\n"
        "-    x = 3\n"
        "-    x = 4\n"
        "+# note\n"
        " def survivor():\n"
        "     x = 1\n"
        "     x = 1\n"
    )
    assert csl.touched_ranges(diff_text)["mod.py"] == [(1, 4)]
    assert csl.violations(diff_text, [py_file]) == [
        f"FUNCTION | {py_file}:2 | survivor | 51 lines",
    ]


# --- file violations ----------------------------------------------------------


def test_file_crossing_eight_hundred_lines_is_reported(tmp_path: Path) -> None:
    text = "x = 1\n" * 810
    py_file = _write(tmp_path, "mod.py", text)
    added = "".join("+x = 1\n" for _ in range(15))
    diff_text = (
        "diff --git a/mod.py b/mod.py\n"
        "--- a/mod.py\n"
        "+++ b/mod.py\n"
        "@@ -0,0 +1,15 @@\n" + added
    )
    assert csl.violations(diff_text, [py_file]) == [f"FILE | {py_file} | 810 lines"]


def test_file_already_over_eight_hundred_lines_before_the_diff_is_not_reported(
    tmp_path: Path,
) -> None:
    text = "x = 1\n" * 810
    py_file = _write(tmp_path, "mod.py", text)
    diff_text = (
        "diff --git a/mod.py b/mod.py\n"
        "--- a/mod.py\n"
        "+++ b/mod.py\n"
        "@@ -5,2 +5,2 @@\n"
        "-x = 1\n"
        "-x = 1\n"
        "+x = 2\n"
        "+x = 2\n"
    )
    assert csl.violations(diff_text, [py_file]) == []


# --- multi-file diffs / unparseable files --------------------------------------


def test_deleted_file_hunks_do_not_count_against_the_previous_file(
    tmp_path: Path,
) -> None:
    py_file = _write(tmp_path, "mod.py", "x = 1\n" * 805)
    added = "".join("+x = 2\n" for _ in range(10))
    removed = "".join("-old line\n" for _ in range(20))
    diff_text = (
        "diff --git a/mod.py b/mod.py\n"
        "--- a/mod.py\n"
        "+++ b/mod.py\n"
        "@@ -1,0 +1,10 @@\n" + added + "diff --git a/gone.py b/gone.py\n"
        "--- a/gone.py\n"
        "+++ /dev/null\n"
        "@@ -1,20 +0,0 @@\n" + removed
    )
    assert csl.violations(diff_text, [py_file]) == [f"FILE | {py_file} | 805 lines"]


def test_unparseable_file_still_reports_a_file_crossing(tmp_path: Path) -> None:
    text = "def broken(:\n" + "x = 1\n" * 804
    py_file = _write(tmp_path, "broken.py", text)
    added = "".join("+x = 1\n" for _ in range(10))
    diff_text = (
        "diff --git a/broken.py b/broken.py\n"
        "--- a/broken.py\n"
        "+++ b/broken.py\n"
        "@@ -0,0 +1,10 @@\n" + added
    )
    assert csl.violations(diff_text, [py_file]) == [f"FILE | {py_file} | 805 lines"]


# --- diff-path resolution (same-basename collisions) --------------------------


def test_pooled_ranges_do_not_leak_a_root_files_hunk_onto_a_same_named_nested_file(
    tmp_path: Path,
) -> None:
    (tmp_path / "tests").mkdir()
    edited = ["def edited():", "    x = 1", "    x = 2"]
    gap = [""] * 12
    text = "\n".join(edited + gap) + "\n" + _long_function("never_touched", 51)
    py_file = _write(tmp_path, "tests/conftest.py", text)
    diff_text = (
        "diff --git a/conftest.py b/conftest.py\n"
        "--- a/conftest.py\n"
        "+++ b/conftest.py\n"
        "@@ -16,51 +16,51 @@\n"
        "-old line\n"
        "+new line\n"
        "diff --git a/tests/conftest.py b/tests/conftest.py\n"
        "--- a/tests/conftest.py\n"
        "+++ b/tests/conftest.py\n"
        "@@ -1,3 +1,3 @@\n"
        "-def edited():\n"
        "-    x = 1\n"
        "-    x = 1\n"
        "+def edited():\n"
        "+    x = 1\n"
        "+    x = 2\n"
    )
    assert csl.violations(diff_text, [py_file]) == []


def test_equal_depth_ambiguous_matches_are_skipped_with_the_rest_still_reported(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    _write(tmp_path, "c.py", "def small():\n    return 1\n")
    ambiguous_path = Path("c.py")
    other_file, over_limit_diff = _write_over_limit_diff(tmp_path)
    diff_text = (
        "diff --git a/a/c.py b/a/c.py\n"
        "--- a/a/c.py\n"
        "+++ b/a/c.py\n"
        "@@ -1,2 +1,2 @@\n"
        "-def small():\n"
        "-    return 0\n"
        "+def small():\n"
        "+    return 1\n"
        "diff --git a/b/c.py b/b/c.py\n"
        "--- a/b/c.py\n"
        "+++ b/b/c.py\n"
        "@@ -1,2 +1,2 @@\n"
        "-def small():\n"
        "-    return 0\n"
        "+def small():\n"
        "+    return 1\n"
    ) + over_limit_diff
    result = csl.violations(diff_text, [ambiguous_path, other_file])
    captured = capsys.readouterr()
    assert result == [f"FUNCTION | {other_file}:1 | over_limit | 51 lines"]
    assert str(ambiguous_path) in captured.err


def test_file_arithmetic_uses_only_the_matched_files_own_counts(
    tmp_path: Path,
) -> None:
    (tmp_path / "pkg").mkdir()
    text = "x = 1\n" * 805
    py_file = _write(tmp_path, "pkg/cfg.py", text)
    root_deletions = "".join("-old line\n" for _ in range(20))
    own_deletions = "".join("-x = 1\n" for _ in range(5))
    own_additions = "".join("+x = 1\n" for _ in range(10))
    diff_text = (
        "diff --git a/cfg.py b/cfg.py\n"
        "--- a/cfg.py\n"
        "+++ b/cfg.py\n"
        "@@ -1,20 +1,0 @@\n" + root_deletions + "diff --git a/pkg/cfg.py b/pkg/cfg.py\n"
        "--- a/pkg/cfg.py\n"
        "+++ b/pkg/cfg.py\n"
        "@@ -1,5 +1,10 @@\n" + own_deletions + own_additions
    )
    assert csl.violations(diff_text, [py_file]) == [f"FILE | {py_file} | 805 lines"]


def test_match_normalises_dot_slash_and_double_slash_diff_paths(
    tmp_path: Path,
) -> None:
    (tmp_path / "a").mkdir()
    func_text = _long_function("over_limit", 51)
    py_file = _write(tmp_path, "a/b.py", func_text)
    diff_text = (
        "diff --git a/a/b.py b/a/b.py\n"
        "--- a/a/b.py\n"
        "+++ b/./a/b.py\n"
        "@@ -1,2 +1,51 @@\n"
        "-def over_limit():\n"
        "-    pass\n" + "".join(f"+{line}\n" for line in func_text.splitlines())
    )
    assert csl.violations(diff_text, [py_file]) == [
        f"FUNCTION | {py_file}:1 | over_limit | 51 lines",
    ]


# --- non-Python skip -----------------------------------------------------------


def test_non_python_changed_file_is_skipped_silently(tmp_path: Path) -> None:
    md_file = _write(tmp_path, "notes.md", "# notes\n" + "line\n" * 900)
    diff_text = (
        "diff --git a/notes.md b/notes.md\n"
        "--- a/notes.md\n"
        "+++ b/notes.md\n"
        "@@ -0,0 +1,900 @@\n" + "".join("+line\n" for _ in range(900))
    )
    assert csl.violations(diff_text, [md_file]) == []


# --- unreadable / missing files ------------------------------------------------


def test_violations_skips_a_missing_path_and_still_reports_the_surviving_path(
    tmp_path: Path,
) -> None:
    py_file, over_limit_diff = _write_over_limit_diff(tmp_path)
    missing_path = tmp_path / "missing.py"
    diff_text = (
        "diff --git a/missing.py b/missing.py\n"
        "--- a/missing.py\n"
        "+++ b/missing.py\n"
        "@@ -1,1 +1,1 @@\n"
        "-old line\n"
        "+new line\n"
    ) + over_limit_diff
    assert csl.violations(diff_text, [missing_path, py_file]) == [
        f"FUNCTION | {py_file}:1 | over_limit | 51 lines",
    ]


def test_violations_notes_a_skipped_unreadable_path_on_stderr(
    tmp_path: Path,
    capsys,
) -> None:
    py_file, over_limit_diff = _write_over_limit_diff(tmp_path)
    missing_path = tmp_path / "missing.py"
    diff_text = (
        "diff --git a/missing.py b/missing.py\n"
        "--- a/missing.py\n"
        "+++ b/missing.py\n"
        "@@ -1,1 +1,1 @@\n"
        "-old line\n"
        "+new line\n"
    ) + over_limit_diff
    result = csl.violations(diff_text, [missing_path, py_file])
    captured = capsys.readouterr()
    assert result == [f"FUNCTION | {py_file}:1 | over_limit | 51 lines"]
    assert str(missing_path) in captured.err


def test_violations_skips_a_file_with_invalid_utf8_bytes(tmp_path: Path) -> None:
    py_file = tmp_path / "mod.py"
    py_file.write_bytes(b"\xff\xfe\x00\x01binary garbage")
    diff_text = (
        "diff --git a/mod.py b/mod.py\n"
        "--- a/mod.py\n"
        "+++ b/mod.py\n"
        "@@ -1,1 +1,1 @@\n"
        "-old line\n"
        "+new line\n"
    )
    assert csl.violations(diff_text, [py_file]) == []


# --- main / CLI ------------------------------------------------------------


def test_clean_diff_via_main_exits_zero_with_empty_output(
    tmp_path: Path,
    capsys,
) -> None:
    py_file, diff_text = _write_clean_diff(tmp_path)
    diff_file = _write(tmp_path, "changes.diff", diff_text)
    exit_code = csl.main(["--diff", str(diff_file), str(py_file)])
    assert exit_code == 0
    assert capsys.readouterr().out == ""


def test_violating_diff_via_main_exits_one_and_prints_the_lines(
    tmp_path: Path,
    capsys,
) -> None:
    py_file, diff_text = _write_over_limit_diff(tmp_path)
    diff_file = _write(tmp_path, "changes.diff", diff_text)
    exit_code = csl.main(["--diff", str(diff_file), str(py_file)])
    out = capsys.readouterr().out
    assert exit_code == 1
    assert out == f"FUNCTION | {py_file}:1 | over_limit | 51 lines\n"


def test_main_exits_two_when_a_changed_file_could_not_be_read(
    tmp_path: Path,
    capsys,
) -> None:
    """The gate must never certify a file it could not open. Reproduced at
    PRD 00140 review cycle 2: the same file and diff exit 1 when readable
    and exited 0 when unreadable, and the gate records exit 0 as
    `style_gate: clean` - so the report certified a file the gate
    never inspected. An uninspected file is exit 2, not a pass."""
    py_file, diff_text = _write_over_limit_diff(tmp_path)
    diff_file = _write(tmp_path, "changes.diff", diff_text)
    py_file.chmod(0o000)
    try:
        exit_code = csl.main(["--diff", str(diff_file), str(py_file)])
    finally:
        py_file.chmod(0o644)
    captured = capsys.readouterr()
    assert exit_code == 2, "an unreadable changed file must not exit 0 (clean)"
    assert str(py_file) in captured.err
    assert "gate incomplete" in captured.err


def test_main_exits_two_when_a_changed_file_is_an_ambiguous_diff_path_tie(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    """The other fail-open route into the same exit: an equal-depth tie is
    skipped, so that file went uninspected too. The tie needs a RELATIVE
    single-segment argument (as in the sibling ambiguity test) - step 5.65
    passes absolute paths, which is why this path is far harder to reach
    in real use than the unreadable-file one above."""
    monkeypatch.chdir(tmp_path)
    _write(tmp_path, "c.py", "def small():\n    return 1\n")
    diff_text = (
        "diff --git a/a/c.py b/a/c.py\n"
        "--- a/a/c.py\n"
        "+++ b/a/c.py\n"
        "@@ -1,2 +1,2 @@\n"
        "+def small():\n"
        "+    return 1\n"
        "diff --git a/b/c.py b/b/c.py\n"
        "--- a/b/c.py\n"
        "+++ b/b/c.py\n"
        "@@ -1,2 +1,2 @@\n"
        "+def small():\n"
        "+    return 1\n"
    )
    diff_file = _write(tmp_path, "changes.diff", diff_text)
    exit_code = csl.main(["--diff", str(diff_file), "c.py"])
    captured = capsys.readouterr()
    assert exit_code == 2, "an ambiguous tie must not exit 0 (clean)"
    assert "ambiguous diff-path match" in captured.err
    assert "gate incomplete" in captured.err


def test_violations_records_an_unreadable_path_in_the_skipped_list(
    tmp_path: Path,
) -> None:
    """`skipped` is what lets main() tell 'found nothing' from 'did not
    look'. Since PRD 00162 a path the diff does not name is a skip too:
    the caller derived it from that diff, so the gate cannot claim the
    file is simply unchanged."""
    py_file, diff_text = _write_over_limit_diff(tmp_path)
    absent = _write(tmp_path, "not_in_diff.py", "def tiny():\n    return 1\n")
    skipped: list[str] = []
    py_file.chmod(0o000)
    try:
        csl.violations(diff_text, [py_file, absent], skipped=skipped)
    finally:
        py_file.chmod(0o644)
    assert skipped == [str(py_file), str(absent)]


def test_main_exits_two_and_names_the_path_when_the_diff_file_is_missing(
    tmp_path: Path,
    capsys,
) -> None:
    missing_diff = tmp_path / "absent.diff"
    py_file = _write(tmp_path, "mod.py", "def small():\n    return 1\n")
    exit_code = csl.main(["--diff", str(missing_diff), str(py_file)])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert str(missing_diff) in captured.err
    assert captured.out == ""


def test_main_exits_two_and_names_the_path_for_invalid_utf8_diff_bytes(
    tmp_path: Path,
    capsys,
) -> None:
    bad_diff = tmp_path / "bad.diff"
    bad_diff.write_bytes(b"\xff\xfe\x00\x01binary garbage")
    py_file = _write(tmp_path, "mod.py", "def small():\n    return 1\n")
    exit_code = csl.main(["--diff", str(bad_diff), str(py_file)])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert str(bad_diff) in captured.err
    assert captured.out == ""


def test_cli_subprocess_exits_one_and_prints_violation_lines(tmp_path: Path) -> None:
    py_file, diff_text = _write_over_limit_diff(tmp_path)
    diff_file = _write(tmp_path, "changes.diff", diff_text)
    result = _run("--diff", str(diff_file), str(py_file))
    assert result.returncode == 1
    assert result.stdout == f"FUNCTION | {py_file}:1 | over_limit | 51 lines\n"


def test_cli_subprocess_exits_zero_and_prints_nothing_for_a_clean_diff(
    tmp_path: Path,
) -> None:
    py_file, diff_text = _write_clean_diff(tmp_path)
    diff_file = _write(tmp_path, "changes.diff", diff_text)
    result = _run("--diff", str(diff_file), str(py_file))
    assert result.returncode == 0
    assert result.stdout == ""


# --- uninspected candidates and untracked full-add blocks (PRD 00162) ---------


def test_main_exits_two_when_a_candidate_is_absent_from_the_diff(
    tmp_path: Path,
    capsys,
) -> None:
    """PRD 00162: every caller derives its candidate list from the diff, so
    a candidate with no `+++ b/` match is a caller/gate disagreement, not an
    ordinary answer. Passing it over silently is how eight oversized
    functions in uncommitted modules earned a `style_gate: clean`."""
    py_file, diff_text = _write_clean_diff(tmp_path)
    absent = _write(tmp_path, "untracked.py", _long_function("over_limit", 60))
    diff_file = _write(tmp_path, "changes.diff", diff_text)
    exit_code = csl.main(["--diff", str(diff_file), str(py_file), str(absent)])
    captured = capsys.readouterr()
    assert exit_code == 2, "a candidate the gate never located must not exit 0"
    assert str(absent) in captured.err
    assert "gate incomplete" in captured.err


def _no_index_full_add(path: Path, text: str) -> str:
    """The block `git diff --no-index -- /dev/null <path>` emits for an
    untracked file: one `+++ b/` header (git drops the leading slash of an
    absolute path) and a single whole-file hunk. Verified against git in
    this repo's environment, 2026-08-28."""
    lines = text.splitlines()
    rel = str(path).lstrip("/")
    return (
        f"diff --git a/{rel} b/{rel}\n"
        "new file mode 100644\n"
        "--- /dev/null\n"
        f"+++ b/{rel}\n"
        f"@@ -0,0 +1,{len(lines)} @@\n"
    ) + "".join(f"+{line}\n" for line in lines)


def test_untracked_full_add_block_reports_the_file_crossing(
    tmp_path: Path,
    capsys,
) -> None:
    """A whole-file add makes the file-limit arithmetic `n - ins + dels`
    reduce to 0, so any untracked file over 800 lines is the diff's own
    doing and is reported."""
    text = "x = 1\n" * 900
    py_file = _write(tmp_path, "big.py", text)
    diff_file = _write(tmp_path, "changes.diff", _no_index_full_add(py_file, text))
    exit_code = csl.main(["--diff", str(diff_file), str(py_file)])
    assert exit_code == 1
    assert capsys.readouterr().out == f"FILE | {py_file} | 900 lines\n"


def test_untracked_full_add_block_reports_an_over_limit_function(
    tmp_path: Path,
    capsys,
) -> None:
    """Every function in a whole-file add intersects the single hunk, so
    the 60-line function in a new module can no longer hide from the
    gate."""
    text = _long_function("over_limit", 60)
    py_file = _write(tmp_path, "test_big.py", text)
    diff_file = _write(tmp_path, "changes.diff", _no_index_full_add(py_file, text))
    exit_code = csl.main(["--diff", str(diff_file), str(py_file)])
    assert exit_code == 1
    assert capsys.readouterr().out == (
        f"FUNCTION | {py_file}:1 | over_limit | 60 lines\n"
    )


def test_pure_deletion_hunk_on_a_present_file_still_exits_zero(
    tmp_path: Path,
    capsys,
) -> None:
    """The new skip must not turn ordinary deletions into a gate failure:
    the file is named by the diff, so it was inspected and found clean."""
    func_text = _long_function("over_limit", 60)
    py_file = _write(tmp_path, "mod.py", func_text)
    diff_text = (
        "diff --git a/mod.py b/mod.py\n"
        "--- a/mod.py\n"
        "+++ b/mod.py\n"
        "@@ -70,3 +69,0 @@\n"
        "-def gone():\n"
        "-    return 1\n"
        "-\n"
    )
    diff_file = _write(tmp_path, "changes.diff", diff_text)
    exit_code = csl.main(["--diff", str(diff_file), str(py_file)])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == ""
    assert captured.err == ""


def _hunkless_block(body: str) -> str:
    """A block that changes no content carries a `diff --git` header and no
    `+++ b/` line at all. Shapes confirmed against git, 2026-08-28."""
    return "diff --git a/mod.py b/mod.py\n" + body


HUNKLESS_BLOCKS = {
    "empty new file": _hunkless_block("new file mode 100644\nindex 0000000..e69de29\n"),
    "mode-only change": _hunkless_block("old mode 100644\nnew mode 100755\n"),
    "pure rename": (
        "diff --git a/old.py b/mod.py\n"
        "similarity index 100%\n"
        "rename from old.py\n"
        "rename to mod.py\n"
    ),
}


def test_two_spellings_of_one_path_are_one_key(tmp_path: Path) -> None:
    """The `diff --git` header and the `+++ b/` line can spell the same file
    differently. Left unnormalised they are two keys of equal match depth,
    which reads as an ambiguous tie and skips a file the diff plainly
    names."""
    py_file = _write(tmp_path, "b.py", _long_function("over_limit", 51))
    diff_text = (
        "diff --git a/b.py b/b.py\n"
        "--- a/b.py\n"
        "+++ b/./b.py\n"
        "@@ -1,2 +1,51 @@\n"
        "+def over_limit():\n"
        "+    x = 1\n"
    )
    assert list(csl.touched_ranges(diff_text)) == ["b.py"]
    skipped: list[str] = []
    csl.violations(diff_text, [py_file], skipped=skipped)
    assert skipped == []


def test_a_content_free_block_is_inspected_not_skipped(
    tmp_path: Path,
    capsys,
) -> None:
    """A rename, a chmod and an empty new file change no line, so the gate
    has nothing to flag and must exit 0. Recording them as uninspected
    would put `style_gate: failed` on a healthy phase - adding an empty
    `__init__.py` is enough to trigger it."""
    py_file = _write(tmp_path, "mod.py", "def small():\n    return 1\n")
    for name, block in HUNKLESS_BLOCKS.items():
        diff_file = _write(tmp_path, f"{name}.diff", block)
        exit_code = csl.main(["--diff", str(diff_file), str(py_file)])
        captured = capsys.readouterr()
        assert exit_code == 0, f"{name} exited {exit_code}: {captured.err}"
        assert captured.err == "", f"{name}: {captured.err}"
