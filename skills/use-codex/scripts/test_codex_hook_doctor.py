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

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

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


def _snapshot(root: Path) -> dict[str, str | int]:
    """Relative path -> sha256 of the bytes (-1 for directories) for every
    entry under `root`, used to prove a run left the tree untouched. A hash,
    not a size: a same-size rewrite must fail the read-only proofs."""
    return {
        str(p.relative_to(root)): (
            hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else -1
        )
        for p in root.rglob("*")
    }


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
    # Non-empty but broken Python must fail compile(), and the detail column
    # (its one-line str(exc)) is the only place the error reaches a reader.
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


def test_check_returns_ok_for_a_latin1_hook_that_declares_its_coding_cookie(
    tmp_path: Path,
) -> None:
    # PEP 263: a coding cookie makes non-UTF-8 source valid Python, and
    # compile() honours it only when handed the raw bytes. Decoding as UTF-8
    # first raised UnicodeDecodeError and verdicted a healthy hook
    # "syntax_error" (exit 1, rung gated off).
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    (hooks_dir / "latin.py").write_bytes(
        '# -*- coding: latin-1 -*-\nX = "\xe9"\n'.encode("latin-1")
    )
    config_path = tmp_path / "hooks.json"
    _write_config(config_path, {"SessionStart": ["python3 hooks/latin.py"]})
    aegis_root, autopilot_root = _fake_roots(tmp_path)

    result = codex_hook_doctor.check(
        config=config_path,
        aegis_root=aegis_root,
        autopilot_root=autopilot_root,
    )

    assert result[0][:2] == ("ok", str(hooks_dir / "latin.py"))


def test_check_returns_syntax_error_for_latin1_bytes_without_a_coding_cookie(
    tmp_path: Path,
) -> None:
    # The same bytes minus the cookie are not valid Python: compile()
    # assumes UTF-8 and rejects them, so the verdict stays "syntax_error".
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    (hooks_dir / "latin.py").write_bytes('X = "\xe9"\n'.encode("latin-1"))
    config_path = tmp_path / "hooks.json"
    _write_config(config_path, {"SessionStart": ["python3 hooks/latin.py"]})
    aegis_root, autopilot_root = _fake_roots(tmp_path)

    result = codex_hook_doctor.check(
        config=config_path,
        aegis_root=aegis_root,
        autopilot_root=autopilot_root,
    )

    assert result[0][:2] == ("syntax_error", str(hooks_dir / "latin.py"))


def test_check_returns_syntax_error_for_a_hook_containing_a_null_byte(
    tmp_path: Path,
) -> None:
    # compile() rejects a null byte with ValueError on 3.10/3.11 and
    # SyntaxError on 3.12+; the verdict is "syntax_error" on every version,
    # never an uncaught exception.
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    (hooks_dir / "nul.py").write_bytes(b"X = 1\x00\n")
    config_path = tmp_path / "hooks.json"
    _write_config(config_path, {"SessionStart": ["python3 hooks/nul.py"]})
    aegis_root, autopilot_root = _fake_roots(tmp_path)

    result = codex_hook_doctor.check(
        config=config_path,
        aegis_root=aegis_root,
        autopilot_root=autopilot_root,
    )

    assert result[0][:2] == ("syntax_error", str(hooks_dir / "nul.py"))


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
        "local = 1\n",
        encoding="utf-8",
    )
    config_path = tmp_path / "hooks.json"
    _write_config(config_path, {"PreToolUse": ["python3 hooks/validate_commit_msg.py"]})
    aegis_root, autopilot_root = _fake_roots(tmp_path)
    (aegis_root / "hooks").mkdir()
    (aegis_root / "hooks" / "validate_commit_msg.py").write_text(
        "canonical = 2\n",
        encoding="utf-8",
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
        "local = 1\n",
        encoding="utf-8",
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


def test_cli_config_whose_hooks_value_is_not_an_object_exits_2(tmp_path: Path) -> None:
    # `hooks` present but a list: the doctor names the shape problem on
    # stderr and exits 2, rather than surfacing a raw AttributeError from
    # iterating it. The guard lives in _load_hooks, so repair() gets it too.
    config_path = tmp_path / "hooks.json"
    config_path.write_text(json.dumps({"hooks": []}), encoding="utf-8")
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
    assert "hooks must be an object" in result.stderr
    assert "Traceback" not in result.stderr


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
        "local = 1\n",
        encoding="utf-8",
    )
    config_path = tmp_path / "hooks.json"
    _write_config(config_path, {"PreToolUse": ["python3 hooks/validate_commit_msg.py"]})
    aegis_root, autopilot_root = _fake_roots(tmp_path)
    (aegis_root / "hooks").mkdir()
    (aegis_root / "hooks" / "validate_commit_msg.py").write_text(
        "canonical = 2\n",
        encoding="utf-8",
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


def test_cli_a_no_canonical_only_target_exits_3(tmp_path: Path) -> None:
    # no_canonical is grouped with stale for the exit-code decision, not
    # with missing/empty/syntax_error: a known target whose canonical
    # source cannot be located, with nothing else missing/empty/broken,
    # must still exit 3 rather than the old (buggy) 1.
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    (hooks_dir / "validate_commit_msg.py").write_text(
        "local = 1\n",
        encoding="utf-8",
    )
    config_path = tmp_path / "hooks.json"
    _write_config(config_path, {"PreToolUse": ["python3 hooks/validate_commit_msg.py"]})
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

    assert result.returncode == 3
    lines = [line for line in result.stdout.splitlines() if line]
    assert lines[-1] == "summary\t0 ok, 1 stale, 0 broken"
    assert any(
        line.startswith(f"no_canonical\t{hooks_dir / 'validate_commit_msg.py'}\t")
        for line in lines[:-1]
    )


# ---------------------------------------------------------------------------
# CLI — defaulted --config/--aegis-root/--autopilot-root flags
# ---------------------------------------------------------------------------


def test_cli_config_flag_defaults_to_codex_home_env_hooks_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # `--config` may be omitted: it must then default to
    # `$CODEX_HOME/hooks.json` when CODEX_HOME is set. HOME is left alone —
    # only CODEX_HOME should matter here.
    codex_home = tmp_path / "codex_home"
    hooks_dir = codex_home / "hooks"
    hooks_dir.mkdir(parents=True)
    (hooks_dir / "good.py").write_text("X = 1\n", encoding="utf-8")
    config_path = codex_home / "hooks.json"
    _write_config(config_path, {"SessionStart": ["python3 hooks/good.py"]})
    aegis_root, autopilot_root = _fake_roots(tmp_path)
    monkeypatch.setenv("CODEX_HOME", str(codex_home))

    result = _run_cli(
        ["--aegis-root", str(aegis_root), "--autopilot-root", str(autopilot_root)],
    )

    assert result.returncode == 0
    lines = [line for line in result.stdout.splitlines() if line]
    assert lines[-1] == "summary\t1 ok, 0 stale, 0 broken"


def test_cli_config_flag_defaults_to_home_dot_codex_hooks_json_without_codex_home(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Without CODEX_HOME set, the default config must fall back to
    # `~/.codex/hooks.json`.
    fake_home = tmp_path / "fake_home"
    dot_codex = fake_home / ".codex"
    hooks_dir = dot_codex / "hooks"
    hooks_dir.mkdir(parents=True)
    (hooks_dir / "good.py").write_text("X = 1\n", encoding="utf-8")
    config_path = dot_codex / "hooks.json"
    _write_config(config_path, {"SessionStart": ["python3 hooks/good.py"]})
    aegis_root, autopilot_root = _fake_roots(tmp_path)
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.setenv("HOME", str(fake_home))

    result = _run_cli(
        ["--aegis-root", str(aegis_root), "--autopilot-root", str(autopilot_root)],
    )

    assert result.returncode == 0
    lines = [line for line in result.stdout.splitlines() if line]
    assert lines[-1] == "summary\t1 ok, 0 stale, 0 broken"


def test_cli_aegis_root_flag_defaults_to_first_matching_installed_plugin_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # `--aegis-root` may be omitted: it must then default to the
    # installPath of the first "aegis@buvis-plugins" entry in
    # ~/.claude/plugins/installed_plugins.json.
    fake_home = tmp_path / "fake_home"
    plugins_dir = fake_home / ".claude" / "plugins"
    plugins_dir.mkdir(parents=True)
    real_aegis_root = tmp_path / "real_aegis_install"
    (real_aegis_root / "hooks").mkdir(parents=True)
    (real_aegis_root / "hooks" / "validate_commit_msg.py").write_text(
        "X = 1\n",
        encoding="utf-8",
    )
    (plugins_dir / "installed_plugins.json").write_text(
        json.dumps(
            {
                "version": 2,
                "plugins": {
                    "other@buvis-plugins": [
                        {"installPath": str(tmp_path / "other")},
                    ],
                    "aegis@buvis-plugins": [
                        {"installPath": str(real_aegis_root)},
                    ],
                },
            },
        ),
        encoding="utf-8",
    )
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    (hooks_dir / "validate_commit_msg.py").write_text("X = 1\n", encoding="utf-8")
    config_path = tmp_path / "hooks.json"
    _write_config(config_path, {"PreToolUse": ["python3 hooks/validate_commit_msg.py"]})
    _, autopilot_root = _fake_roots(tmp_path)
    monkeypatch.setenv("HOME", str(fake_home))

    result = _run_cli(
        ["--config", str(config_path), "--autopilot-root", str(autopilot_root)],
    )

    assert result.returncode == 0
    lines = [line for line in result.stdout.splitlines() if line]
    assert lines[-1] == "summary\t1 ok, 0 stale, 0 broken"


def test_default_aegis_root_reads_the_real_installed_plugins_json_shape(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The real installed_plugins.json is a dict keyed by "plugins", whose
    # value is itself a dict keyed by plugin name, mapping to a *list* of
    # install entries — not a flat list of {"name", "installPath"} objects.
    # _default_aegis_root() must resolve against that real shape.
    fake_home = tmp_path / "fake_home"
    plugins_dir = fake_home / ".claude" / "plugins"
    plugins_dir.mkdir(parents=True)
    real_aegis_root = tmp_path / "real_aegis_install"
    (plugins_dir / "installed_plugins.json").write_text(
        json.dumps(
            {
                "version": 2,
                "plugins": {
                    "aegis@buvis-plugins": [
                        {
                            "scope": "user",
                            "installPath": str(real_aegis_root),
                            "version": "0.3.2",
                        },
                    ],
                },
            },
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("HOME", str(fake_home))

    result = codex_hook_doctor._default_aegis_root()

    assert result == real_aegis_root


def test_cli_exits_2_when_aegis_plugin_entry_list_is_empty(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # An "aegis@buvis-plugins" entry that resolves to an empty list (e.g. an
    # uninstalled-but-present entry) must not crash the doctor with an
    # unhandled IndexError — it must exit 2 like any other resolution
    # failure.
    fake_home = tmp_path / "fake_home"
    plugins_dir = fake_home / ".claude" / "plugins"
    plugins_dir.mkdir(parents=True)
    (plugins_dir / "installed_plugins.json").write_text(
        json.dumps({"version": 2, "plugins": {"aegis@buvis-plugins": []}}),
        encoding="utf-8",
    )
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    (hooks_dir / "good.py").write_text("X = 1\n", encoding="utf-8")
    config_path = tmp_path / "hooks.json"
    _write_config(config_path, {"SessionStart": ["python3 hooks/good.py"]})
    _, autopilot_root = _fake_roots(tmp_path)
    monkeypatch.setenv("HOME", str(fake_home))

    result = _run_cli(
        ["--config", str(config_path), "--autopilot-root", str(autopilot_root)],
    )

    assert result.returncode == 2


def test_cli_autopilot_root_flag_is_no_longer_required(tmp_path: Path) -> None:
    # `--autopilot-root` may be omitted; argparse must not treat it as a
    # hard requirement. Uses only an unknown (non-KNOWN_HOOKS) target, so
    # the resolved default value never needs to be dereferenced.
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    (hooks_dir / "good.py").write_text("X = 1\n", encoding="utf-8")
    config_path = tmp_path / "hooks.json"
    _write_config(config_path, {"SessionStart": ["python3 hooks/good.py"]})
    aegis_root, _ = _fake_roots(tmp_path)

    result = _run_cli(["--config", str(config_path), "--aegis-root", str(aegis_root)])

    assert result.returncode == 0
    lines = [line for line in result.stdout.splitlines() if line]
    assert lines[-1] == "summary\t1 ok, 0 stale, 0 broken"
