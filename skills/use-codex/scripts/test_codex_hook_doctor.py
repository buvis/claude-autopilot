"""Tests for codex_hook_doctor.py — the `check` subcommand.

Every test builds a throwaway hooks.json plus a sibling `hooks/` directory
under `tmp_path`, and always passes `--config`/`--aegis-root`/`--autopilot-root`
(or the matching `check()` keyword arguments) explicitly. The doctor's
defaults point at the real `~/.codex`, `~/.claude`, and this repo — none of
that may leak into a test run.

`stale` and `no_canonical` verdicts are exercised using the exact
basename-to-canonical-source table given by the spec, e.g.
`validate_commit_msg.py` resolves against
`<aegis_root>/hooks/validate_commit_msg.py`. Only that basename mapping is
relied on here — the internal shape of `KNOWN_HOOKS` itself (dict layout,
lookup helper, etc.) is never asserted on, only the `check()` verdicts it
produces for those basenames.

`_common.py` is itself one of the KNOWN_HOOKS basenames, so any fixture that
registers a bare `_common.py` target must also supply a byte-identical
`<aegis_root>/hooks/_common.py` — otherwise it verdicts `no_canonical`
instead of `ok`.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

_MODULE_PATH = Path(__file__).with_name("codex_hook_doctor.py")
_SPEC = importlib.util.spec_from_file_location("codex_hook_doctor", _MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
codex_hook_doctor = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(codex_hook_doctor)


def _write_config(path: Path, events: dict[str, list[str]]) -> None:
    """A hooks.json with one command per entry in `events[event_name]`."""
    hooks_obj = {
        event: [{"hooks": [{"type": "command", "command": c} for c in commands]}]
        for event, commands in events.items()
    }
    path.write_text(json.dumps({"hooks": hooks_obj}), encoding="utf-8")


def _fake_roots(tmp_path: Path) -> tuple[Path, Path]:
    """Empty aegis/autopilot roots — no KNOWN_HOOKS lookup should need them
    when every target in a test is an unknown (host-owned) hook."""
    aegis_root = tmp_path / "fake_aegis_root"
    autopilot_root = tmp_path / "fake_autopilot_root"
    aegis_root.mkdir()
    autopilot_root.mkdir()
    return aegis_root, autopilot_root


def _run_cli(args: list[str], timeout: int = 10) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_MODULE_PATH), "check", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


# ---------------------------------------------------------------------------
# check() — return-value contract
# ---------------------------------------------------------------------------


def test_check_returns_ok_for_a_healthy_relative_target(tmp_path: Path) -> None:
    # A non-empty, syntactically valid file referenced by a relative token
    # must resolve against the config's directory and report "ok".
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    (hooks_dir / "good.py").write_text("X = 1\n", encoding="utf-8")
    config_path = tmp_path / "hooks.json"
    _write_config(config_path, {"SessionStart": ["python3 hooks/good.py"]})
    aegis_root, autopilot_root = _fake_roots(tmp_path)

    result = codex_hook_doctor.check(
        config=config_path,
        aegis_root=aegis_root,
        autopilot_root=autopilot_root,
    )

    assert len(result) == 1
    verdict, target, _detail = result[0]
    assert verdict == "ok"
    assert target == str(hooks_dir / "good.py")


def test_check_returns_missing_for_a_target_with_no_file_on_disk(
    tmp_path: Path,
) -> None:
    # The command references a hook that was never created — the resolved
    # path must still be reported, just with a "missing" verdict.
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    config_path = tmp_path / "hooks.json"
    _write_config(config_path, {"SessionStart": ["python3 hooks/missing.py"]})
    aegis_root, autopilot_root = _fake_roots(tmp_path)

    result = codex_hook_doctor.check(
        config=config_path,
        aegis_root=aegis_root,
        autopilot_root=autopilot_root,
    )

    assert result == [("missing", str(hooks_dir / "missing.py"), result[0][2])]


def test_check_returns_empty_for_a_zero_byte_target(tmp_path: Path) -> None:
    # Existing but zero-byte is a distinct verdict from both "ok" and
    # "missing" — a hook that got truncated is not the same failure as one
    # that never existed.
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    (hooks_dir / "empty.py").write_text("", encoding="utf-8")
    config_path = tmp_path / "hooks.json"
    _write_config(config_path, {"SessionStart": ["python3 hooks/empty.py"]})
    aegis_root, autopilot_root = _fake_roots(tmp_path)

    result = codex_hook_doctor.check(
        config=config_path,
        aegis_root=aegis_root,
        autopilot_root=autopilot_root,
    )

    verdict, target, _detail = result[0]
    assert verdict == "empty"
    assert target == str(hooks_dir / "empty.py")


def test_check_returns_syntax_error_with_the_compile_message_in_detail(
    tmp_path: Path,
) -> None:
    # Non-empty but broken Python must fail via py_compile, and the detail
    # column is the only place the compile error is surfaced to a reader.
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    (hooks_dir / "broken.py").write_text("def f(:\n    pass\n", encoding="utf-8")
    config_path = tmp_path / "hooks.json"
    _write_config(config_path, {"SessionStart": ["python3 hooks/broken.py"]})
    aegis_root, autopilot_root = _fake_roots(tmp_path)

    result = codex_hook_doctor.check(
        config=config_path,
        aegis_root=aegis_root,
        autopilot_root=autopilot_root,
    )

    verdict, target, detail = result[0]
    assert verdict == "syntax_error"
    assert target == str(hooks_dir / "broken.py")
    assert detail != ""


def test_check_resolves_a_quoted_absolute_path_with_spaces(tmp_path: Path) -> None:
    # `python3 '/path with spaces/hook.py'` must resolve to the path inside
    # the quotes, not the closing quote or the raw quoted token.
    spaced_dir = tmp_path / "path with spaces"
    spaced_dir.mkdir()
    hook_file = spaced_dir / "hook.py"
    hook_file.write_text("X = 1\n", encoding="utf-8")
    config_path = tmp_path / "hooks.json"
    _write_config(config_path, {"SessionStart": [f"python3 '{hook_file}'"]})
    aegis_root, autopilot_root = _fake_roots(tmp_path)

    result = codex_hook_doctor.check(
        config=config_path,
        aegis_root=aegis_root,
        autopilot_root=autopilot_root,
    )

    verdict, target, _detail = result[0]
    assert verdict == "ok"
    assert target == str(hook_file)


def test_check_includes_unreferenced_common_py_as_an_implicit_target(
    tmp_path: Path,
) -> None:
    # _common.py is only ever imported, never invoked by a `command` line,
    # but it still lives in the hooks directory and must still be checked.
    # It is also a KNOWN_HOOKS basename, so it needs a byte-identical
    # canonical source to verdict "ok" rather than "no_canonical".
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    (hooks_dir / "good.py").write_text("X = 1\n", encoding="utf-8")
    (hooks_dir / "_common.py").write_text("Y = 2\n", encoding="utf-8")
    config_path = tmp_path / "hooks.json"
    _write_config(config_path, {"SessionStart": ["python3 hooks/good.py"]})
    aegis_root, autopilot_root = _fake_roots(tmp_path)
    (aegis_root / "hooks").mkdir()
    (aegis_root / "hooks" / "_common.py").write_text("Y = 2\n", encoding="utf-8")

    result = codex_hook_doctor.check(
        config=config_path,
        aegis_root=aegis_root,
        autopilot_root=autopilot_root,
    )

    seen = {(verdict, target) for verdict, target, _detail in result}
    assert seen == {
        ("ok", str(hooks_dir / "good.py")),
        ("ok", str(hooks_dir / "_common.py")),
    }


def test_check_covers_commands_from_every_event_block(tmp_path: Path) -> None:
    # Two distinct event names, each with its own command — a doctor that
    # only walked the first event key would silently miss the second.
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    (hooks_dir / "a.py").write_text("A = 1\n", encoding="utf-8")
    (hooks_dir / "b.py").write_text("B = 1\n", encoding="utf-8")
    config_path = tmp_path / "hooks.json"
    _write_config(
        config_path,
        {"SessionStart": ["python3 hooks/a.py"], "PreToolUse": ["python3 hooks/b.py"]},
    )
    aegis_root, autopilot_root = _fake_roots(tmp_path)

    result = codex_hook_doctor.check(
        config=config_path,
        aegis_root=aegis_root,
        autopilot_root=autopilot_root,
    )

    seen = {(verdict, target) for verdict, target, _detail in result}
    assert seen == {
        ("ok", str(hooks_dir / "a.py")),
        ("ok", str(hooks_dir / "b.py")),
    }


def test_check_returns_stale_for_a_known_hook_whose_bytes_differ_from_canonical(
    tmp_path: Path,
) -> None:
    # validate_commit_msg.py is a KNOWN_HOOKS basename whose canonical
    # source is <aegis_root>/hooks/validate_commit_msg.py — differing bytes
    # must verdict "stale", not "ok".
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    (hooks_dir / "validate_commit_msg.py").write_text(
        "local version\n", encoding="utf-8"
    )
    config_path = tmp_path / "hooks.json"
    _write_config(config_path, {"PreToolUse": ["python3 hooks/validate_commit_msg.py"]})
    aegis_root, autopilot_root = _fake_roots(tmp_path)
    (aegis_root / "hooks").mkdir()
    (aegis_root / "hooks" / "validate_commit_msg.py").write_text(
        "canonical version\n", encoding="utf-8"
    )

    result = codex_hook_doctor.check(
        config=config_path,
        aegis_root=aegis_root,
        autopilot_root=autopilot_root,
    )

    verdict, target, _detail = result[0]
    assert verdict == "stale"
    assert target == str(hooks_dir / "validate_commit_msg.py")


def test_check_returns_no_canonical_for_a_known_hook_missing_its_canonical_source(
    tmp_path: Path,
) -> None:
    # Same known basename, but the given aegis_root has no hooks/ dir at
    # all — the canonical source cannot be located, so this is
    # "no_canonical" rather than "stale" or "ok".
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    (hooks_dir / "validate_commit_msg.py").write_text(
        "local version\n", encoding="utf-8"
    )
    config_path = tmp_path / "hooks.json"
    _write_config(config_path, {"PreToolUse": ["python3 hooks/validate_commit_msg.py"]})
    aegis_root, autopilot_root = _fake_roots(tmp_path)

    result = codex_hook_doctor.check(
        config=config_path,
        aegis_root=aegis_root,
        autopilot_root=autopilot_root,
    )

    verdict, target, _detail = result[0]
    assert verdict == "no_canonical"
    assert target == str(hooks_dir / "validate_commit_msg.py")


# ---------------------------------------------------------------------------
# CLI — exit codes and stdout shape
# ---------------------------------------------------------------------------


def test_cli_a_nonexistent_config_file_exits_2() -> None:
    # Matches the PRD's own acceptance criterion verbatim.
    result = _run_cli(["--config", "/nonexistent/hooks.json"])

    assert result.returncode == 2


def test_cli_invalid_json_config_exits_2(tmp_path: Path) -> None:
    config_path = tmp_path / "hooks.json"
    config_path.write_text("{not valid json", encoding="utf-8")
    aegis_root, autopilot_root = _fake_roots(tmp_path)

    result = _run_cli(
        [
            "--config",
            str(config_path),
            "--aegis-root",
            str(aegis_root),
            "--autopilot-root",
            str(autopilot_root),
        ],
    )

    assert result.returncode == 2


def test_cli_config_without_a_hooks_key_exits_2(tmp_path: Path) -> None:
    config_path = tmp_path / "hooks.json"
    config_path.write_text(json.dumps({"foo": "bar"}), encoding="utf-8")
    aegis_root, autopilot_root = _fake_roots(tmp_path)

    result = _run_cli(
        [
            "--config",
            str(config_path),
            "--aegis-root",
            str(aegis_root),
            "--autopilot-root",
            str(autopilot_root),
        ],
    )

    assert result.returncode == 2


def test_cli_all_ok_exits_0_with_one_tsv_line_and_a_summary(tmp_path: Path) -> None:
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    (hooks_dir / "good.py").write_text("X = 1\n", encoding="utf-8")
    config_path = tmp_path / "hooks.json"
    _write_config(config_path, {"SessionStart": ["python3 hooks/good.py"]})
    aegis_root, autopilot_root = _fake_roots(tmp_path)

    result = _run_cli(
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
    lines = [line for line in result.stdout.splitlines() if line]
    assert len(lines) == 2
    target_line = f"ok\t{hooks_dir / 'good.py'}\t"
    assert any(line.startswith(target_line) for line in lines[:-1])
    assert lines[-1] == "summary\t1 ok, 0 stale, 0 broken"


def test_cli_a_missing_target_exits_1_and_counts_as_broken(tmp_path: Path) -> None:
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    (hooks_dir / "good.py").write_text("X = 1\n", encoding="utf-8")
    config_path = tmp_path / "hooks.json"
    _write_config(
        config_path,
        {"SessionStart": ["python3 hooks/good.py", "python3 hooks/missing.py"]},
    )
    aegis_root, autopilot_root = _fake_roots(tmp_path)

    result = _run_cli(
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
    assert lines[-1] == "summary\t1 ok, 0 stale, 1 broken"
    assert any(line.startswith(f"ok\t{hooks_dir / 'good.py'}\t") for line in lines[:-1])
    assert any(
        line.startswith(f"missing\t{hooks_dir / 'missing.py'}\t") for line in lines[:-1]
    )


def test_cli_a_stale_only_target_exits_3(tmp_path: Path) -> None:
    # Matches the PRD's own required Phase-0 test case: a known target
    # whose bytes differ from canonical, and nothing missing/empty/broken,
    # must exit 3 (not 0 and not 1).
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    (hooks_dir / "validate_commit_msg.py").write_text(
        "local version\n", encoding="utf-8"
    )
    config_path = tmp_path / "hooks.json"
    _write_config(config_path, {"PreToolUse": ["python3 hooks/validate_commit_msg.py"]})
    aegis_root, autopilot_root = _fake_roots(tmp_path)
    (aegis_root / "hooks").mkdir()
    (aegis_root / "hooks" / "validate_commit_msg.py").write_text(
        "canonical version\n", encoding="utf-8"
    )

    result = _run_cli(
        [
            "--config",
            str(config_path),
            "--aegis-root",
            str(aegis_root),
            "--autopilot-root",
            str(autopilot_root),
        ],
    )

    assert result.returncode == 3
    lines = [line for line in result.stdout.splitlines() if line]
    assert lines[-1] == "summary\t0 ok, 1 stale, 0 broken"
    assert any(
        line.startswith(f"stale\t{hooks_dir / 'validate_commit_msg.py'}\t")
        for line in lines[:-1]
    )
