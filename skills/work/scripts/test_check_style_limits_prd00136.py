"""Fixture-based regression pin: PRD 00136 cycle-1 diff replayed through
check_style_limits.py (PRD 00140)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_MODULE_PATH = Path(__file__).with_name("check_style_limits.py")
_SPEC = importlib.util.spec_from_file_location("check_style_limits", _MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
csl = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(csl)

_FIXTURE_DIR = Path(__file__).with_name("fixtures") / "prd00136-cycle1"
_DIFF_PATHS = [
    ".claude/hooks/enforce_write_scope.py",
    ".claude/hooks/dispatch.py",
    ".claude/hooks/tests/test_enforce_write_scope.py",
    ".claude/hooks/tests/test_handler_run_parity.py",
]


def _copy_fixtures(tmp_path: Path) -> list[Path]:
    """Mirror each post-image file at its diff path under tmp_path: the module
    matches a given path to a diff path by trailing segments, so a copy must
    carry the same tail as the `+++ b/` path it stands in for."""
    paths = []
    for rel in _DIFF_PATHS:
        text = (_FIXTURE_DIR / f"{Path(rel).name}.txt").read_text(encoding="utf-8")
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        paths.append(path)
    return paths


def _expected_lines(paths: list[Path]) -> list[str]:
    qualified_name = (
        "TestDispatcherRegistration."
        "test_degraded_hook_line_reaches_real_stderr_through_the_dispatcher"
    )
    return [
        f"FUNCTION | {paths[2]}:642 | {qualified_name} | 57 lines",
        f"FILE | {paths[3]} | 817 lines",
    ]


def test_prd00136_cycle1_replay_reports_exactly_the_two_reviewer_findings(
    tmp_path: Path,
) -> None:
    paths = _copy_fixtures(tmp_path)
    diff_text = (_FIXTURE_DIR / "changes.diff").read_text(encoding="utf-8")
    assert csl.violations(diff_text, paths) == _expected_lines(paths)


def test_prd00136_cycle1_replay_exits_one_with_the_two_lines(
    tmp_path: Path, capsys
) -> None:
    paths = _copy_fixtures(tmp_path)
    diff_path = _FIXTURE_DIR / "changes.diff"
    exit_code = csl.main(["--diff", str(diff_path), *[str(p) for p in paths]])
    line1, line2 = _expected_lines(paths)
    assert exit_code == 1
    assert capsys.readouterr().out == line1 + "\n" + line2 + "\n"
