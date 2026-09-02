"""Tests for codex_hook_doctor.py — the `repair` subcommand's full
operator cycle (check -> repair -> check).

Split out of test_codex_hook_doctor_repair.py to keep both files under the
project's file-length limit. Shares `_fake_roots`, `_run_cli`, and
`_write_config` from test_codex_hook_doctor, and `_run_repair_cli` from
test_codex_hook_doctor_repair — see their docstrings for the shared
fixture/config conventions these tests also rely on.
"""

from __future__ import annotations

from pathlib import Path

from test_codex_hook_doctor import _fake_roots, _run_cli, _write_config
from test_codex_hook_doctor_repair import _run_repair_cli


def _build_full_cycle_fixture(
    tmp_path: Path,
) -> tuple[Path, list[str], dict[str, str], dict[str, Path]]:
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    stale = {
        "validate_commit_msg.py": "local_validate = 1\n",
        "_common.py": "local_common = 1\n",
        "protect_config.py": "local_protect = 1\n",
        "block_devlocal_redirects.py": "local_block_devlocal = 1\n",
        "block-suppression-markers.py": "local_block_suppression = 1\n",
        "gateguard-fact-force.py": "local_gateguard = 1\n",
        "enforce_prd_location.py": "local_enforce = 1\n",
    }
    for name, content in stale.items():
        (hooks_dir / name).write_text(content, encoding="utf-8")

    config_path = tmp_path / "hooks.json"
    _write_config(
        config_path,
        {
            "PreToolUse": [
                "python3 hooks/validate_commit_msg.py",
                "python3 hooks/protect_config.py",
                "python3 hooks/block_devlocal_redirects.py",
                "python3 hooks/block-suppression-markers.py",
                "python3 hooks/gateguard-fact-force.py",
                "python3 hooks/enforce_prd_location.py",
            ]
        },
    )

    aegis_root, autopilot_root = _fake_roots(tmp_path)
    aegis_hooks_dir = aegis_root / "hooks"
    aegis_hooks_dir.mkdir()
    autopilot_hooks_dir = autopilot_root / "hooks"
    autopilot_hooks_dir.mkdir()

    canonical_paths = {
        "validate_commit_msg.py": aegis_hooks_dir / "validate_commit_msg.py",
        "_common.py": aegis_hooks_dir / "_common.py",
        "protect_config.py": aegis_hooks_dir / "protect_config.py",
        "block_devlocal_redirects.py": aegis_hooks_dir / "block_devlocal_redirects.py",
        "block-suppression-markers.py": aegis_hooks_dir
        / "block_suppression_markers.py",
        "gateguard-fact-force.py": aegis_hooks_dir / "gateguard_fact_force.py",
        "enforce_prd_location.py": autopilot_hooks_dir / "enforce_prd_location.py",
    }
    canonical_content = {
        "validate_commit_msg.py": "canonical_validate = 2\n",
        "_common.py": "canonical_common = 2\n",
        "protect_config.py": "canonical_protect = 2\n",
        "block_devlocal_redirects.py": "canonical_block_devlocal = 2\n",
        "block-suppression-markers.py": "canonical_block_suppression = 2\n",
        "gateguard-fact-force.py": "canonical_gateguard = 2\n",
        "enforce_prd_location.py": "canonical_enforce = 2\n",
    }
    for name, canonical_path in canonical_paths.items():
        canonical_path.write_text(canonical_content[name], encoding="utf-8")

    cli_args = [
        "--config",
        str(config_path),
        "--aegis-root",
        str(aegis_root),
        "--autopilot-root",
        str(autopilot_root),
    ]

    return hooks_dir, cli_args, stale, canonical_paths


def test_repair_full_cycle_recovers_all_seven_known_hooks_from_a_stale_host_state(
    tmp_path: Path,
) -> None:
    # The PRD's own worst-case host state: all seven KNOWN hooks stale at
    # once. check must exit 3 (stale, nothing broken); repair must rewrite
    # every one of them to canonical bytes and report each "repaired"; a
    # second check must then exit 0. None of the seven files import from
    # _common, so repairing _common.py's sibling-import scan never has
    # cause to refuse it.
    hooks_dir, cli_args, stale, canonical_paths = _build_full_cycle_fixture(tmp_path)

    pre_check = _run_cli(cli_args)
    assert pre_check.returncode == 3

    repair_result = _run_repair_cli(cli_args)
    repair_lines = [line for line in repair_result.stdout.splitlines() if line]
    for name in stale:
        target_path = hooks_dir / name
        canonical_path = canonical_paths[name]
        assert any(
            line.startswith(f"repaired\t{target_path}\t") for line in repair_lines
        )
        assert target_path.read_bytes() == canonical_path.read_bytes()

    post_check = _run_cli(cli_args)
    assert post_check.returncode == 0
