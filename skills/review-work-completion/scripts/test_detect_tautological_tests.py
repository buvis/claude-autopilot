"""Contract for detect_tautological_tests.py.

Each flagged shape is one that cannot fail as written; each unflagged one is
a legitimate idiom the calibration run over this pack's own suite found
(snapshot-before/after, a class helper that calls `self.fail`, a module
helper that asserts). A rule that flags an idiom below is a regression even
if it also catches more.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import detect_tautological_tests as d

SCRIPT = Path(__file__).with_name("detect_tautological_tests.py")

SHAPES = '''\
import pytest


def _snapshot(p):
    return sorted(p.iterdir())


def _assert_row(row):
    assert row.startswith("ok")


def _plain_helper(row):
    return row


def test_constant():
    assert True


def test_tuple_constant():
    assert ("a", "b")


def test_self_compare(value):
    assert value == value


def test_hedge(out):
    assert "a" in out or "b" in out


def test_swallows(run):
    try:
        assert run() == 1
    except Exception:
        pass


def test_any_exception(run):
    with pytest.raises(Exception):
        run()


def test_no_assertion(run):
    run()


def test_helper_without_assert(run):
    _plain_helper(run())


def test_snapshot_idiom(tmp_path, run):
    before = _snapshot(tmp_path)
    run()
    assert _snapshot(tmp_path) == before


def test_module_helper_asserts(run):
    _assert_row(run())


def test_raises_specific(run):
    with pytest.raises(ValueError):
        run()


class TestSuite:
    def reject(self, problems):
        if problems:
            self.fail("bad")

    def test_class_helper_reaches_fail(self):
        self.reject([])

    def test_class_no_assertion(self):
        self.setUp()
'''


def _write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def _hits(tmp_path: Path) -> dict[str, list[str]]:
    status, count, hits = d.check_test_file(_write(tmp_path, "test_shapes.py", SHAPES))
    assert status == "ok" and count == 13
    grouped: dict[str, list[str]] = {}
    for severity, name, _line, reason in hits:
        grouped.setdefault(name, []).append(f"{severity} {reason.split(':')[0]}")
    return grouped


def test_each_shape_that_cannot_fail_is_flagged_once_at_its_severity(tmp_path: Path) -> None:
    hits = _hits(tmp_path)
    assert hits["test_constant"] == ["🟠 asserts a constant"]
    assert hits["test_tuple_constant"] == ["🟠 asserts a constant"]
    assert hits["test_self_compare"] == ["🟠 compares an expression with itself"]
    assert hits["test_hedge"] == ["🟡 hedges with `or`"]
    assert hits["test_swallows"] == ["🟠 swallows exceptions"]
    assert hits["test_any_exception"] == ["🟡 accepts any exception via `raises(Exception)`"]
    assert hits["test_no_assertion"] == ["🟡 has no assertion"]
    assert hits["test_helper_without_assert"] == ["🟡 has no assertion"]
    assert hits["test_class_no_assertion"] == ["🟡 has no assertion"]


def test_legitimate_idioms_are_not_flagged(tmp_path: Path) -> None:
    hits = _hits(tmp_path)
    for name in (
        "test_snapshot_idiom",
        "test_module_helper_asserts",
        "test_raises_specific",
        "test_class_helper_reaches_fail",
    ):
        assert name not in hits, f"{name} flagged: {hits.get(name)}"


def test_only_test_files_are_checked(tmp_path: Path) -> None:
    status, _, _ = d.check_test_file(_write(tmp_path, "helpers.py", "def test_x():\n    assert True\n"))
    assert status == "skipped (not a test file)"
    status, _, _ = d.check_test_file(_write(tmp_path, "test_broken.py", "def (:\n"))
    assert status == "skipped (parse error)"


def test_the_cli_prints_issue_lines_and_exits_zero(tmp_path: Path) -> None:
    shapes = _write(tmp_path, "test_shapes.py", SHAPES)
    other = _write(tmp_path, "impl.py", "X = 1\n")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(shapes), str(other)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "## Tautological test shapes (computed, do not re-judge)" in result.stdout
    assert f"[MECH] 🟠 test_constant asserts a constant: it cannot fail | File: {shapes}:17 | Task: general" in result.stdout
    assert "Checked 13 test function(s) in 1 test file(s)." in result.stdout
