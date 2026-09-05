"""Target I/O regressions (PRD 00176) and interpreter-independent pins for
`_missing_common_import_names` (PRD 00173, added by review cycle 1).

The CLI-level null-byte test in test_codex_hook_doctor_extra.py discriminates
only on Python 3.10: from 3.11 a null byte raises SyntaxError, which the
pre-existing branch already caught, so that test stays green with or without
the `(ValueError, OSError)` widening this PRD added. Measured on this host —
`ast.parse("\\x00")` and `compile(b"\\x00", ...)` both raise ValueError on
3.10.20 and SyntaxError on 3.11.15, 3.12.13 and 3.13.13.

Faking the raise removes the interpreter from the equation: revert the widening
to `(UnicodeDecodeError, OSError)` and the bare ValueError escapes
`_missing_common_import_names`, failing this test on every Python.

`codex_hook_doctor` does a plain `import ast`, so `codex_hook_doctor.ast` is
the one shared module object — patching its `parse` wholesale would also break
pytest's own traceback rendering, which parses source to place carets. The
stub therefore raises only for this module's poison source and delegates every
other call to the real parser.

Lives in its own module because test_codex_hook_doctor_extra.py sits at 782 of
the project's 800-line file limit.
"""

from __future__ import annotations

import ast
import errno
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from test_codex_hook_doctor import (
    _fake_roots,
    _run_cli,
    _write_config,
    codex_hook_doctor,
)
from test_codex_hook_doctor_repair import _run_repair_cli

_UNREADABLE = "unreadable (cannot verify _common imports)"
# Stands in for bytes the interpreter refuses; the stub keys off this exact text.
_POISON = "# parse of this source raises ValueError\n"


def test_bare_value_error_from_parse_marks_sibling_and_canonical_unreadable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    (hooks_dir / "bad_sibling.py").write_text(_POISON, encoding="utf-8")
    canonical = tmp_path / "_common.py"
    canonical.write_text(_POISON, encoding="utf-8")

    real_parse = ast.parse

    def fake_parse(source: Any, *args: Any, **kwargs: Any) -> ast.AST:
        if source == _POISON:
            raise ValueError("source code string cannot contain null bytes")
        return real_parse(source, *args, **kwargs)

    monkeypatch.setattr(codex_hook_doctor.ast, "parse", fake_parse)

    assert codex_hook_doctor._missing_common_import_names(hooks_dir, canonical) == [
        f"bad_sibling.py: {_UNREADABLE}",
        f"_common.py: {_UNREADABLE}",
    ]


def test_check_directory_target_reports_error_and_remaining_rows(
    tmp_path: Path,
) -> None:
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    bad = hooks_dir / "a_directory.py"
    bad.mkdir()
    good = hooks_dir / "z_good.py"
    good.write_text("X = 1\n", encoding="utf-8")
    config = tmp_path / "hooks.json"
    _write_config(config, {})  # Both targets must be discovered by glob.
    aegis_root, autopilot_root = _fake_roots(tmp_path)

    proc = _run_cli(
        [
            "--config",
            str(config),
            "--aegis-root",
            str(aegis_root),
            "--autopilot-root",
            str(autopilot_root),
        ]
    )

    assert proc.returncode == 1, proc.stderr
    rows = [line.split("\t") for line in proc.stdout.splitlines()]
    assert rows[0][:2] == ["syntax_error", str(bad)]
    assert "Is a directory" in rows[0][2]
    assert rows[1] == ["ok", str(good), ""]
    assert rows[2] == ["summary", "1 ok, 0 stale, 1 broken"]
    assert len(rows) == 3
    assert proc.stderr == ""


def test_target_deleted_between_exists_and_stat_is_verdicted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "gone.py"
    target.write_text("X = 1\n", encoding="utf-8")
    aegis_root, autopilot_root = _fake_roots(tmp_path)
    real_exists = Path.exists

    def disappearing_exists(path: Path) -> bool:
        exists = real_exists(path)
        if path == target and exists:
            path.unlink()
        return exists

    monkeypatch.setattr(Path, "exists", disappearing_exists)
    verdict, detail = codex_hook_doctor._verdict_for(target, aegis_root, autopilot_root)

    assert verdict == "syntax_error"
    assert "No such file or directory" in detail
    assert str(target) in detail


def test_staleness_uses_the_target_bytes_that_compiled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "protect_config.py"
    target.write_bytes(b"X = 1\n")
    aegis_root, autopilot_root = _fake_roots(tmp_path)
    (aegis_root / "hooks").mkdir()
    canonical = aegis_root / "hooks" / target.name
    canonical.write_bytes(b"X = 1\n")
    real_read = Path.read_bytes

    def disappearing_read(path: Path) -> bytes:
        data = real_read(path)
        if path == target:
            path.unlink()
        return data

    monkeypatch.setattr(Path, "read_bytes", disappearing_read)

    assert codex_hook_doctor._verdict_for(target, aegis_root, autopilot_root) == (
        "ok",
        "",
    )


@pytest.fixture
def unreadable_target(tmp_path: Path) -> Iterator[Path]:
    if os.geteuid() == 0:
        pytest.skip("root bypasses file permission bits")
    target = tmp_path / "unreadable.py"
    target.write_text("X = 1\n", encoding="utf-8")
    mode = target.stat().st_mode
    target.chmod(0)
    try:
        yield target
    finally:
        target.chmod(mode)


def test_unreadable_target_is_verdicted(unreadable_target: Path) -> None:
    verdict, detail = codex_hook_doctor._verdict_for(
        unreadable_target,
        unreadable_target.parent,
        unreadable_target.parent,
    )

    assert verdict == "syntax_error"
    assert "Permission denied" in detail
    assert str(unreadable_target) in detail


@pytest.fixture
def repair_targets(tmp_path: Path) -> tuple[Path, list[str]]:
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    aegis_root, autopilot_root = _fake_roots(tmp_path)
    (aegis_root / "hooks").mkdir()
    names = ["protect_config.py", "validate_commit_msg.py"]
    for name in names:
        (hooks_dir / name).write_bytes(b"X = 1\n")
        (aegis_root / "hooks" / name).write_bytes(b"X = 2\n")
    config = tmp_path / "hooks.json"
    _write_config(config, {"PreToolUse": [f"python3 hooks/{name}" for name in names]})
    return hooks_dir, [
        "--config",
        str(config),
        "--aegis-root",
        str(aegis_root),
        "--autopilot-root",
        str(autopilot_root),
    ]


@pytest.fixture
def readonly_hooks(
    repair_targets: tuple[Path, list[str]],
) -> Iterator[tuple[Path, list[str]]]:
    if os.geteuid() == 0:
        pytest.skip("root bypasses directory permission bits")
    hooks_dir, _ = repair_targets
    mode = hooks_dir.stat().st_mode
    hooks_dir.chmod(0o555)
    try:
        yield repair_targets
    finally:
        hooks_dir.chmod(mode)


def test_readonly_repair_reports_all_targets_without_tmp_litter(
    readonly_hooks: tuple[Path, list[str]],
) -> None:
    hooks_dir, args = readonly_hooks

    proc = _run_repair_cli(args)

    assert proc.returncode == 3, proc.stderr
    rows = [line.split("\t") for line in proc.stdout.splitlines()]
    assert rows[0][:2] == ["unrepairable", str(hooks_dir / "protect_config.py")]
    assert "Permission denied" in rows[0][2]
    assert rows[1][:2] == ["unrepairable", str(hooks_dir / "validate_commit_msg.py")]
    assert "Permission denied" in rows[1][2]
    assert rows[2] == ["summary", "0 ok, 2 stale, 0 broken"]
    assert len(rows) == 3
    assert list(hooks_dir.glob("*.tmp")) == []
    assert (hooks_dir / "protect_config.py").read_bytes() == b"X = 1\n"
    assert (hooks_dir / "validate_commit_msg.py").read_bytes() == b"X = 1\n"
    assert proc.stderr == ""


@pytest.mark.parametrize("failure", ["partial_write", "replace"])
def test_failed_repair_cleans_tmp_and_repairs_next_target(
    repair_targets: tuple[Path, list[str]],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    failure: str,
) -> None:
    hooks_dir, args = repair_targets
    target = hooks_dir / "protect_config.py"
    temp = target.with_name(target.name + ".tmp")
    real_write = Path.write_bytes
    real_replace = os.replace
    error = OSError(errno.ENOSPC, "No space left on device", str(temp))

    def partial_write(path: Path, data: bytes) -> int:
        if path == temp:
            real_write(path, data[:1])
            raise error
        return real_write(path, data)

    def failed_replace(src: Path, dst: Path) -> None:
        if dst == target:
            raise error
        real_replace(src, dst)

    if failure == "partial_write":
        monkeypatch.setattr(Path, "write_bytes", partial_write)
    else:
        monkeypatch.setattr(codex_hook_doctor.os, "replace", failed_replace)

    assert codex_hook_doctor.main(["repair", *args]) == 3
    output = capsys.readouterr()
    rows = [line.split("\t") for line in output.out.splitlines()]
    assert rows[0] == ["unrepairable", str(target), str(error)]
    assert rows[1][:2] == ["repaired", str(hooks_dir / "validate_commit_msg.py")]
    assert rows[2] == ["summary", "1 ok, 1 stale, 0 broken"]
    assert len(rows) == 3
    assert list(hooks_dir.glob("*.tmp")) == []
    assert target.read_bytes() == b"X = 1\n"
    assert (hooks_dir / "validate_commit_msg.py").read_bytes() == b"X = 2\n"
    assert output.err == ""


def test_cleanup_failure_is_reported_without_losing_remaining_rows(
    repair_targets: tuple[Path, list[str]],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    hooks_dir, args = repair_targets
    target = hooks_dir / "protect_config.py"
    temp = target.with_name(target.name + ".tmp")
    real_replace = os.replace
    real_unlink = Path.unlink

    def failed_replace(src: Path, dst: Path) -> None:
        if dst == target:
            raise PermissionError(errno.EACCES, "replace denied", str(target))
        real_replace(src, dst)

    def failed_unlink(path: Path, missing_ok: bool = False) -> None:
        if path == temp:
            raise PermissionError(errno.EACCES, "cleanup denied", str(temp))
        real_unlink(path, missing_ok=missing_ok)

    monkeypatch.setattr(codex_hook_doctor.os, "replace", failed_replace)
    monkeypatch.setattr(Path, "unlink", failed_unlink)

    assert codex_hook_doctor.main(["repair", *args]) == 3
    output = capsys.readouterr()
    rows = [line.split("\t") for line in output.out.splitlines()]
    assert rows[0][:2] == ["unrepairable", str(target)]
    assert "replace denied" in rows[0][2]
    assert "temp cleanup failed:" in rows[0][2]
    assert "cleanup denied" in rows[0][2]
    assert rows[1][:2] == ["repaired", str(hooks_dir / "validate_commit_msg.py")]
    assert rows[2] == ["summary", "1 ok, 1 stale, 0 broken"]
    assert len(rows) == 3
    assert target.read_bytes() == b"X = 1\n"
    assert (hooks_dir / "validate_commit_msg.py").read_bytes() == b"X = 2\n"
    assert temp.read_bytes() == b"X = 2\n"
    assert output.err == ""
