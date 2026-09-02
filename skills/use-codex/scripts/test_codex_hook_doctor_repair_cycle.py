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


# name -> (canonical root key, canonical basename, stale body, canonical body).
# Six known hooks resolve against the aegis root, one against the autopilot
# root, and two of them are spelled differently locally than canonically.
_SEVEN_HOOKS = {
    "validate_commit_msg.py": ("aegis", "validate_commit_msg.py", "validate"),
    "_common.py": ("aegis", "_common.py", "common"),
    "protect_config.py": ("aegis", "protect_config.py", "protect"),
    "block_devlocal_redirects.py": (
        "aegis",
        "block_devlocal_redirects.py",
        "block_devlocal",
    ),
    "block-suppression-markers.py": (
        "aegis",
        "block_suppression_markers.py",
        "block_suppression",
    ),
    "gateguard-fact-force.py": ("aegis", "gateguard_fact_force.py", "gateguard"),
    "enforce_prd_location.py": ("autopilot", "enforce_prd_location.py", "enforce"),
}


def _build_full_cycle_fixture(
    tmp_path: Path,
) -> tuple[Path, list[str], dict[str, str], dict[str, Path]]:
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    aegis_root, autopilot_root = _fake_roots(tmp_path)
    roots = {"aegis": aegis_root / "hooks", "autopilot": autopilot_root / "hooks"}
    for root in roots.values():
        root.mkdir()

    stale: dict[str, str] = {}
    canonical_paths: dict[str, Path] = {}
    for name, (root_key, canonical_name, stem) in _SEVEN_HOOKS.items():
        stale[name] = f"local_{stem} = 1\n"
        (hooks_dir / name).write_text(stale[name], encoding="utf-8")
        canonical_paths[name] = roots[root_key] / canonical_name
        canonical_paths[name].write_text(
            f"canonical_{stem} = 2\n", encoding="utf-8"
        )

    config_path = tmp_path / "hooks.json"
    _write_config(
        config_path,
        {
            "PreToolUse": [
                f"python3 hooks/{name}"
                for name in _SEVEN_HOOKS
                if name != "_common.py"
            ]
        },
    )

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
