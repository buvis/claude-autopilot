"""Tests for codex_hook_doctor.py — the `repair` subcommand.

Split out of test_codex_hook_doctor.py to keep both files under the
project's file-length limit. Shares `_write_config`, `_fake_roots`, and the
already-loaded `codex_hook_doctor` module with that file — see its
docstring for the shared fixture/config conventions these tests also rely
on.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from test_codex_hook_doctor import _fake_roots, _write_config, codex_hook_doctor

_MODULE_PATH = Path(__file__).with_name("codex_hook_doctor.py")


def _run_repair_cli(
    args: list[str], timeout: int = 10
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_MODULE_PATH), "repair", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


# ---------------------------------------------------------------------------
# repair() — return-value contract
# ---------------------------------------------------------------------------


def test_repair_rewrites_a_stale_known_target_to_canonical_bytes_and_reports_repaired(
    tmp_path: Path,
) -> None:
    # A known target whose bytes differ from canonical ("stale", per check())
    # must be overwritten with the canonical bytes, and the emitted tuple
    # must name both the target and the canonical source it was rewritten
    # from.
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    (hooks_dir / "validate_commit_msg.py").write_text(
        "local = 1\n", encoding="utf-8"
    )
    config_path = tmp_path / "hooks.json"
    _write_config(config_path, {"PreToolUse": ["python3 hooks/validate_commit_msg.py"]})
    aegis_root, autopilot_root = _fake_roots(tmp_path)
    (aegis_root / "hooks").mkdir()
    canonical = aegis_root / "hooks" / "validate_commit_msg.py"
    canonical.write_text("canonical = 2\n", encoding="utf-8")

    result = codex_hook_doctor.repair(
        config=config_path,
        aegis_root=aegis_root,
        autopilot_root=autopilot_root,
    )

    target = str(hooks_dir / "validate_commit_msg.py")
    assert ("repaired", target, str(canonical)) in result
    assert (hooks_dir / "validate_commit_msg.py").read_bytes() == canonical.read_bytes()


def test_repair_rewrites_an_empty_known_target_to_canonical_bytes_and_reports_repaired(
    tmp_path: Path,
) -> None:
    # A zero-byte known target ("empty", per check()) is repairable the same
    # way a stale one is — there is a canonical source, so it is rewritten
    # rather than left broken or deleted.
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    (hooks_dir / "validate_commit_msg.py").write_text("", encoding="utf-8")
    config_path = tmp_path / "hooks.json"
    _write_config(config_path, {"PreToolUse": ["python3 hooks/validate_commit_msg.py"]})
    aegis_root, autopilot_root = _fake_roots(tmp_path)
    (aegis_root / "hooks").mkdir()
    canonical = aegis_root / "hooks" / "validate_commit_msg.py"
    canonical.write_text("canonical = 2\n", encoding="utf-8")

    result = codex_hook_doctor.repair(
        config=config_path,
        aegis_root=aegis_root,
        autopilot_root=autopilot_root,
    )

    target = str(hooks_dir / "validate_commit_msg.py")
    assert ("repaired", target, str(canonical)) in result
    assert (hooks_dir / "validate_commit_msg.py").read_bytes() == canonical.read_bytes()


def test_repair_removes_an_unregistered_zero_byte_stray_file_and_reports_removed(
    tmp_path: Path,
) -> None:
    # stray.py sits directly in hooks/ but is named by no command in the
    # config — a zero-byte placeholder like this is deleted, not repaired
    # (there is nothing registered to repair it as).
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    (hooks_dir / "good.py").write_text("X = 1\n", encoding="utf-8")
    stray = hooks_dir / "stray.py"
    stray.write_text("", encoding="utf-8")
    config_path = tmp_path / "hooks.json"
    _write_config(config_path, {"SessionStart": ["python3 hooks/good.py"]})
    aegis_root, autopilot_root = _fake_roots(tmp_path)

    result = codex_hook_doctor.repair(
        config=config_path,
        aegis_root=aegis_root,
        autopilot_root=autopilot_root,
    )

    assert any(
        verdict == "removed" and path == str(stray) for verdict, path, _ in result
    )
    assert not stray.exists()


def test_repair_skips_a_symlinked_known_target_and_leaves_its_link_target_untouched(
    tmp_path: Path,
) -> None:
    # validate_commit_msg.py is a symlink to a file whose bytes are stale
    # relative to canonical — repair must never write through the symlink,
    # so it reports "skipped\t<target>\tsymlink" and leaves the underlying
    # file exactly as it was.
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    real_file = tmp_path / "real_validate_commit_msg.py"
    real_file.write_text("local = 1\n", encoding="utf-8")
    symlink_path = hooks_dir / "validate_commit_msg.py"
    symlink_path.symlink_to(real_file)
    config_path = tmp_path / "hooks.json"
    _write_config(config_path, {"PreToolUse": ["python3 hooks/validate_commit_msg.py"]})
    aegis_root, autopilot_root = _fake_roots(tmp_path)
    (aegis_root / "hooks").mkdir()
    (aegis_root / "hooks" / "validate_commit_msg.py").write_text(
        "canonical = 2\n", encoding="utf-8"
    )

    result = codex_hook_doctor.repair(
        config=config_path,
        aegis_root=aegis_root,
        autopilot_root=autopilot_root,
    )

    assert ("skipped", str(symlink_path), "symlink") in result
    assert real_file.read_bytes() == b"local = 1\n"
    assert symlink_path.is_symlink()


def test_repair_refuses_common_py_when_a_sibling_imports_a_name_canonical_lacks(
    tmp_path: Path,
) -> None:
    # user_hook.py imports `undefined_name` from _common, but the canonical
    # _common.py (the one repair would rewrite hooks/_common.py to) defines
    # no top-level `def undefined_name` — rewriting would silently break
    # user_hook.py, so repair must refuse and name the missing import.
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    (hooks_dir / "_common.py").write_text("OLD = 1\n", encoding="utf-8")
    (hooks_dir / "user_hook.py").write_text(
        "from _common import undefined_name\n", encoding="utf-8"
    )
    config_path = tmp_path / "hooks.json"
    _write_config(config_path, {"SessionStart": ["python3 hooks/user_hook.py"]})
    aegis_root, autopilot_root = _fake_roots(tmp_path)
    (aegis_root / "hooks").mkdir()
    (aegis_root / "hooks" / "_common.py").write_text(
        "def other_helper():\n    pass\n", encoding="utf-8"
    )

    result = codex_hook_doctor.repair(
        config=config_path,
        aegis_root=aegis_root,
        autopilot_root=autopilot_root,
    )

    common_target = str(hooks_dir / "_common.py")
    verdict, _target, why = next(r for r in result if r[1] == common_target)
    assert verdict == "unrepairable"
    assert "undefined_name" in why
    assert (hooks_dir / "_common.py").read_bytes() == b"OLD = 1\n"


def test_repair_rewrites_common_py_when_every_sibling_import_name_exists_in_canonical(
    tmp_path: Path,
) -> None:
    # Same shape as the refusal case, but this time the canonical _common.py
    # does define `helper_fn` — every sibling import name resolves, so the
    # rewrite proceeds normally and is reported "repaired" like any other
    # known target.
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    (hooks_dir / "_common.py").write_text("OLD = 1\n", encoding="utf-8")
    (hooks_dir / "user_hook.py").write_text(
        "from _common import helper_fn\n", encoding="utf-8"
    )
    config_path = tmp_path / "hooks.json"
    _write_config(config_path, {"SessionStart": ["python3 hooks/user_hook.py"]})
    aegis_root, autopilot_root = _fake_roots(tmp_path)
    (aegis_root / "hooks").mkdir()
    canonical_common = aegis_root / "hooks" / "_common.py"
    canonical_common.write_text("def helper_fn():\n    pass\n", encoding="utf-8")

    result = codex_hook_doctor.repair(
        config=config_path,
        aegis_root=aegis_root,
        autopilot_root=autopilot_root,
    )

    common_target = str(hooks_dir / "_common.py")
    verdict, _target, source = next(r for r in result if r[1] == common_target)
    assert verdict == "repaired"
    assert source == str(canonical_common)
    assert (hooks_dir / "_common.py").read_bytes() == canonical_common.read_bytes()


def test_repair_leaves_hooks_json_byte_identical_after_a_run(tmp_path: Path) -> None:
    # The doctor must never edit hooks.json itself, even while it is
    # rewriting and deleting files in hooks/ during the same run.
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    (hooks_dir / "validate_commit_msg.py").write_text(
        "local = 1\n", encoding="utf-8"
    )
    (hooks_dir / "stray.py").write_text("", encoding="utf-8")
    config_path = tmp_path / "hooks.json"
    _write_config(config_path, {"PreToolUse": ["python3 hooks/validate_commit_msg.py"]})
    aegis_root, autopilot_root = _fake_roots(tmp_path)
    (aegis_root / "hooks").mkdir()
    (aegis_root / "hooks" / "validate_commit_msg.py").write_text(
        "canonical = 2\n", encoding="utf-8"
    )
    before = config_path.read_bytes()

    codex_hook_doctor.repair(
        config=config_path,
        aegis_root=aegis_root,
        autopilot_root=autopilot_root,
    )

    assert config_path.read_bytes() == before


def test_repair_never_touches_files_inside_hooks_tests_subdirectory(
    tmp_path: Path,
) -> None:
    # hooks/tests/ holds test copies (e.g. test_autopilot_stop_hook.py) that
    # are explicitly out of scope for the doctor. Even a file there whose
    # basename matches a KNOWN_HOOKS entry, and that is referenced by a
    # command, must never be rewritten — repair must never enter that
    # subdirectory.
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    tests_subdir = hooks_dir / "tests"
    tests_subdir.mkdir()
    (tests_subdir / "validate_commit_msg.py").write_text(
        "local = 1\n", encoding="utf-8"
    )
    config_path = tmp_path / "hooks.json"
    _write_config(
        config_path,
        {"PreToolUse": ["python3 hooks/tests/validate_commit_msg.py"]},
    )
    aegis_root, autopilot_root = _fake_roots(tmp_path)
    (aegis_root / "hooks").mkdir()
    (aegis_root / "hooks" / "validate_commit_msg.py").write_text(
        "canonical = 2\n", encoding="utf-8"
    )

    codex_hook_doctor.repair(
        config=config_path,
        aegis_root=aegis_root,
        autopilot_root=autopilot_root,
    )

    assert (tests_subdir / "validate_commit_msg.py").exists()
    assert (tests_subdir / "validate_commit_msg.py").read_bytes() == b"local = 1\n"


def test_repair_dry_run_emits_would_verbs_and_changes_no_file_on_disk(
    tmp_path: Path,
) -> None:
    # dry_run=True must still report what it would do (would-repair,
    # would-remove) but must not touch the filesystem at all.
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    target = hooks_dir / "validate_commit_msg.py"
    target.write_text("local = 1\n", encoding="utf-8")
    stray = hooks_dir / "stray.py"
    stray.write_text("", encoding="utf-8")
    config_path = tmp_path / "hooks.json"
    _write_config(config_path, {"PreToolUse": ["python3 hooks/validate_commit_msg.py"]})
    aegis_root, autopilot_root = _fake_roots(tmp_path)
    (aegis_root / "hooks").mkdir()
    canonical = aegis_root / "hooks" / "validate_commit_msg.py"
    canonical.write_text("canonical = 2\n", encoding="utf-8")
    target_before = target.read_bytes()

    result = codex_hook_doctor.repair(
        config=config_path,
        aegis_root=aegis_root,
        autopilot_root=autopilot_root,
        dry_run=True,
    )

    assert ("would-repair", str(target), str(canonical)) in result
    assert any(
        verdict == "would-remove" and path == str(stray) for verdict, path, _ in result
    )
    assert target.read_bytes() == target_before == b"local = 1\n"
    assert stray.exists()
    assert stray.read_bytes() == b""


# ---------------------------------------------------------------------------
# CLI repair — dry-run and exit-code recomputation
# ---------------------------------------------------------------------------


def test_cli_repair_reports_unrepairable_and_exits_1_for_a_registered_unknown_zero_byte_target(
    tmp_path: Path,
) -> None:
    # custom_unknown.py is zero-byte and referenced by a command, but its
    # basename is not a KNOWN_HOOKS entry — there is no canonical source to
    # repair it from, so it must be kept on disk (never deleted, since it is
    # registered) and reported unrepairable. The exit code must still count
    # it as broken (matching check()'s "empty" -> broken classification).
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    custom = hooks_dir / "custom_unknown.py"
    custom.write_text("", encoding="utf-8")
    config_path = tmp_path / "hooks.json"
    _write_config(config_path, {"SessionStart": ["python3 hooks/custom_unknown.py"]})
    aegis_root, autopilot_root = _fake_roots(tmp_path)

    result = _run_repair_cli(
        [
            "--config",
            str(config_path),
            "--aegis-root",
            str(aegis_root),
            "--autopilot-root",
            str(autopilot_root),
        ],
    )

    assert result.returncode == 1
    lines = [line for line in result.stdout.splitlines() if line]
    assert any(line.startswith(f"unrepairable\t{custom}\t") for line in lines)
    assert custom.exists()
    assert custom.stat().st_size == 0


def test_repair_cli_recomputes_exit_code_after_fixing_all_broken_targets(
    tmp_path: Path,
) -> None:
    # One target starts "missing" (protect_config.py, never created) and one
    # starts "stale" (validate_commit_msg.py, differing bytes). After a
    # non-dry-run repair fixes both, the CLI's exit code must reflect the
    # post-repair state (everything ok -> 0), not the pre-repair state.
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    (hooks_dir / "validate_commit_msg.py").write_text(
        "local = 1\n", encoding="utf-8"
    )
    config_path = tmp_path / "hooks.json"
    _write_config(
        config_path,
        {
            "PreToolUse": [
                "python3 hooks/validate_commit_msg.py",
                "python3 hooks/protect_config.py",
            ]
        },
    )
    aegis_root, autopilot_root = _fake_roots(tmp_path)
    (aegis_root / "hooks").mkdir()
    (aegis_root / "hooks" / "validate_commit_msg.py").write_text(
        "X = 1\n", encoding="utf-8"
    )
    (aegis_root / "hooks" / "protect_config.py").write_text(
        "Y = 1\n", encoding="utf-8"
    )

    result = _run_repair_cli(
        [
            "--config",
            str(config_path),
            "--aegis-root",
            str(aegis_root),
            "--autopilot-root",
            str(autopilot_root),
        ],
    )

    assert result.returncode == 0

    post_repair = codex_hook_doctor.check(
        config=config_path,
        aegis_root=aegis_root,
        autopilot_root=autopilot_root,
    )
    assert all(verdict == "ok" for verdict, _, _ in post_repair)


def test_cli_repair_dry_run_exits_matching_check_and_leaves_fixture_unchanged(
    tmp_path: Path,
) -> None:
    # A fixture with a "missing" known target is broken (check() would exit
    # 1). Running repair --dry-run against it must report that same exit
    # code without changing anything: the config bytes and the still-missing
    # target file must be exactly as they were before the call.
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    config_path = tmp_path / "hooks.json"
    _write_config(config_path, {"PreToolUse": ["python3 hooks/validate_commit_msg.py"]})
    aegis_root, autopilot_root = _fake_roots(tmp_path)
    (aegis_root / "hooks").mkdir()
    (aegis_root / "hooks" / "validate_commit_msg.py").write_text(
        "canonical = 2\n", encoding="utf-8"
    )
    before_config = config_path.read_bytes()

    pre_check = codex_hook_doctor.check(
        config=config_path,
        aegis_root=aegis_root,
        autopilot_root=autopilot_root,
    )
    pre_broken = sum(
        1
        for verdict, _, _ in pre_check
        if verdict in ("missing", "empty", "syntax_error")
    )
    assert pre_broken > 0  # sanity: the fixture is indeed broken

    result = _run_repair_cli(
        [
            "--dry-run",
            "--config",
            str(config_path),
            "--aegis-root",
            str(aegis_root),
            "--autopilot-root",
            str(autopilot_root),
        ],
    )

    assert result.returncode == 1
    assert config_path.read_bytes() == before_config
    assert not (hooks_dir / "validate_commit_msg.py").exists()


# ---------------------------------------------------------------------------
# repair() — degrades gracefully instead of crashing
# ---------------------------------------------------------------------------


def test_repair_reports_unrepairable_for_a_missing_canonical_source_and_continues_repairing_other_targets(
    tmp_path: Path,
) -> None:
    # validate_commit_msg.py is a KNOWN hook that is "missing" on disk, and
    # its canonical source is itself absent — there is nothing to rewrite it
    # from, so the target must be reported unrepairable rather than crashing
    # the whole run. protect_config.py, a second KNOWN hook in the same run,
    # is "stale" with its canonical source present and must still be
    # repaired.
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    (hooks_dir / "protect_config.py").write_text("local = 1\n", encoding="utf-8")
    config_path = tmp_path / "hooks.json"
    _write_config(
        config_path,
        {
            "PreToolUse": [
                "python3 hooks/validate_commit_msg.py",
                "python3 hooks/protect_config.py",
            ]
        },
    )
    aegis_root, autopilot_root = _fake_roots(tmp_path)
    (aegis_root / "hooks").mkdir()
    canonical_protect = aegis_root / "hooks" / "protect_config.py"
    canonical_protect.write_text("canonical = 2\n", encoding="utf-8")

    result = _run_repair_cli(
        [
            "--config",
            str(config_path),
            "--aegis-root",
            str(aegis_root),
            "--autopilot-root",
            str(autopilot_root),
        ],
    )

    missing_target = str(hooks_dir / "validate_commit_msg.py")
    repaired_target = str(hooks_dir / "protect_config.py")
    lines = [line for line in result.stdout.splitlines() if line]
    assert any(line.startswith(f"unrepairable\t{missing_target}\t") for line in lines)
    assert any(line.startswith(f"repaired\t{repaired_target}\t") for line in lines)
    assert (
        hooks_dir / "protect_config.py"
    ).read_bytes() == canonical_protect.read_bytes()
    assert result.returncode == 1
    assert "Traceback" not in result.stderr


def test_repair_tolerates_a_non_utf8_sibling_py_file_while_scanning_common_py_imports(
    tmp_path: Path,
) -> None:
    # bad_sibling.py sits in the hooks directory next to a _common.py that
    # needs repair (its bytes are stale relative to canonical). Before
    # rewriting _common.py, repair scans every sibling *.py for
    # "from _common import" names — bad_sibling's bytes are not valid
    # UTF-8, so that scan must not blow up the whole run with an uncaught
    # UnicodeDecodeError.
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    (hooks_dir / "_common.py").write_text("OLD = 1\n", encoding="utf-8")
    (hooks_dir / "user_hook.py").write_text("X = 1\n", encoding="utf-8")
    (hooks_dir / "bad_sibling.py").write_bytes(b"\xff\xfe\x00bad\n")
    config_path = tmp_path / "hooks.json"
    _write_config(config_path, {"SessionStart": ["python3 hooks/user_hook.py"]})
    aegis_root, autopilot_root = _fake_roots(tmp_path)
    (aegis_root / "hooks").mkdir()
    (aegis_root / "hooks" / "_common.py").write_text(
        "canonical = 2\n", encoding="utf-8"
    )

    result = _run_repair_cli(
        [
            "--config",
            str(config_path),
            "--aegis-root",
            str(aegis_root),
            "--autopilot-root",
            str(autopilot_root),
        ],
    )

    lines = [line for line in result.stdout.splitlines() if line]
    assert any(line.startswith("summary\t") for line in lines)
    assert "Traceback" not in result.stderr
    assert result.returncode in (0, 1, 3)
    assert (hooks_dir / "bad_sibling.py").read_bytes() == b"\xff\xfe\x00bad\n"
