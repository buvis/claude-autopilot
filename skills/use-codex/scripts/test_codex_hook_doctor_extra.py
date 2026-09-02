"""Tests for codex_hook_doctor.py — check() edge cases and doc-sync pins.

Split out of test_codex_hook_doctor.py to keep both files under the
project's file-length limit. Shares `_fake_roots`, `_write_config`,
`_run_cli`, `_snapshot`, and the already-loaded `codex_hook_doctor` module
with that file — see its docstring for the shared fixture/config
conventions these tests also rely on.
"""

from __future__ import annotations

import json
from pathlib import Path

from test_codex_hook_doctor import (
    _fake_roots,
    _run_cli,
    _snapshot,
    _write_config,
    codex_hook_doctor,
)

# ---------------------------------------------------------------------------
# check() — the five newly-added KNOWN_HOOKS entries
# ---------------------------------------------------------------------------


def test_check_resolves_new_aegis_rooted_known_hooks_against_aegis_root(
    tmp_path: Path,
) -> None:
    # protect_config.py, block_devlocal_redirects.py,
    # block-suppression-markers.py, and gateguard-fact-force.py are all
    # KNOWN_HOOKS entries that resolve against aegis_root — a
    # byte-identical canonical source under aegis_root/hooks/ must verdict
    # "ok" for each. The last two also prove the basename-with-hyphens ->
    # canonical-file-with-underscores mapping.
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    aegis_root, autopilot_root = _fake_roots(tmp_path)
    aegis_hooks_dir = aegis_root / "hooks"
    aegis_hooks_dir.mkdir()

    canonical_names = {
        "protect_config.py": "protect_config.py",
        "block_devlocal_redirects.py": "block_devlocal_redirects.py",
        "block-suppression-markers.py": "block_suppression_markers.py",
        "gateguard-fact-force.py": "gateguard_fact_force.py",
    }
    commands = []
    for target_name, canonical_name in canonical_names.items():
        content = f"# {target_name}\n"
        (hooks_dir / target_name).write_text(content, encoding="utf-8")
        (aegis_hooks_dir / canonical_name).write_text(content, encoding="utf-8")
        commands.append(f"python3 hooks/{target_name}")

    config_path = tmp_path / "hooks.json"
    _write_config(config_path, {"PreToolUse": commands})

    result = codex_hook_doctor.check(
        config=config_path,
        aegis_root=aegis_root,
        autopilot_root=autopilot_root,
    )

    seen = {(verdict, target) for verdict, target, _detail in result}
    assert seen == {("ok", str(hooks_dir / name)) for name in canonical_names}


def test_check_resolves_enforce_prd_location_against_autopilot_root_not_aegis_root(
    tmp_path: Path,
) -> None:
    # enforce_prd_location.py is the one KNOWN_HOOKS entry that resolves
    # against autopilot_root rather than aegis_root — a byte-identical
    # canonical source under autopilot_root/hooks/ must verdict "ok" even
    # when aegis_root has a *different* file of the same name, proving the
    # aegis copy is never consulted for this entry.
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    (hooks_dir / "enforce_prd_location.py").write_text("X = 1\n", encoding="utf-8")
    config_path = tmp_path / "hooks.json"
    _write_config(
        config_path,
        {"PreToolUse": ["python3 hooks/enforce_prd_location.py"]},
    )
    aegis_root, autopilot_root = _fake_roots(tmp_path)
    (aegis_root / "hooks").mkdir()
    (aegis_root / "hooks" / "enforce_prd_location.py").write_text(
        "different bytes that would verdict stale if consulted\n",
        encoding="utf-8",
    )
    (autopilot_root / "hooks").mkdir()
    (autopilot_root / "hooks" / "enforce_prd_location.py").write_text(
        "X = 1\n",
        encoding="utf-8",
    )

    result = codex_hook_doctor.check(
        config=config_path,
        aegis_root=aegis_root,
        autopilot_root=autopilot_root,
    )

    verdict, target, _detail = result[0]
    assert verdict == "ok"
    assert target == str(hooks_dir / "enforce_prd_location.py")


# ---------------------------------------------------------------------------
# check() — read-only guarantee, verdict ordering, single-line detail
# ---------------------------------------------------------------------------


def test_check_leaves_the_config_directory_byte_identical(tmp_path: Path) -> None:
    # "Read-only: never writes anything" is the check() contract. A batch
    # runs this against the operator's real ~/.codex, which is promised
    # never to be written to — so compiling a target to detect syntax
    # errors must not leave __pycache__/*.pyc (or anything else) behind.
    config_root = tmp_path / "codex_home"
    hooks_dir = config_root / "hooks"
    hooks_dir.mkdir(parents=True)
    (hooks_dir / "good.py").write_text("X = 1\n", encoding="utf-8")
    config_path = config_root / "hooks.json"
    _write_config(config_path, {"SessionStart": ["python3 hooks/good.py"]})
    aegis_root, autopilot_root = _fake_roots(tmp_path)

    before = _snapshot(config_root)
    codex_hook_doctor.check(
        config=config_path,
        aegis_root=aegis_root,
        autopilot_root=autopilot_root,
    )
    after = _snapshot(config_root)

    assert after == before


def test_check_returns_syntax_error_for_a_drifted_hook_broken_only_at_grammar_level(
    tmp_path: Path,
) -> None:
    # The bracket-level check is not enough. This source tokenizes cleanly
    # (every bracket is balanced) and is still not valid Python, so a check
    # that only looks for unclosed brackets reports "stale" and exits 3,
    # leaving codex enabled against a hook that fails on every tool call.
    # Only a full parse catches it.
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    (hooks_dir / "validate_commit_msg.py").write_text(
        "def f(a b):\n    return a\n",
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

    verdict, _target, detail = result[0]
    assert verdict == "syntax_error"
    assert "\n" not in detail


def test_check_returns_syntax_error_not_stale_when_a_known_hook_is_both_drifted_and_broken(
    tmp_path: Path,
) -> None:
    # A target gets ONE verdict. validate_commit_msg.py here differs from
    # its canonical source (which alone would be "stale") AND fails to
    # compile (which alone would be "syntax_error") — the non-compiling
    # state must win: a hook that cannot compile fails on every tool call,
    # so reporting "stale" would hide the harmful state behind the
    # harmless one.
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    (hooks_dir / "validate_commit_msg.py").write_text(
        "def f(:\n    pass\n",
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
    assert verdict == "syntax_error"
    assert target == str(hooks_dir / "validate_commit_msg.py")


def test_check_syntax_error_detail_has_no_embedded_newline(tmp_path: Path) -> None:
    # py_compile's own message for this exact snippet is multi-line (a
    # "File ..., line N" header, the source excerpt, a caret, then
    # "SyntaxError: ..." on its own line) — the detail column must collapse
    # that to one line, since the batch probe parses "the first broken TSV
    # line" and an embedded newline would split one record into several.
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

    verdict, _target, detail = result[0]
    assert verdict == "syntax_error"
    assert "\n" not in detail
    assert "\r" not in detail


# ---------------------------------------------------------------------------
# CLI — syntax-error-outranks-stale exit code and single-line stdout
# ---------------------------------------------------------------------------


def test_cli_a_syntax_error_on_a_known_drifted_hook_exits_1_not_3(
    tmp_path: Path,
) -> None:
    # stale exits 3 ("hooks fine, keep using codex" to the batch probe);
    # syntax_error exits 1 (gates codex off). A known hook that is both
    # drifted and non-compiling must take the gating exit code.
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    (hooks_dir / "validate_commit_msg.py").write_text(
        "def f(:\n    pass\n",
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

    assert result.returncode == 1
    lines = [line for line in result.stdout.splitlines() if line]
    assert lines[-1] == "summary\t0 ok, 0 stale, 1 broken"
    assert any(
        line.startswith(f"syntax_error\t{hooks_dir / 'validate_commit_msg.py'}\t")
        for line in lines[:-1]
    )


def test_cli_stdout_line_count_is_target_count_plus_one_summary_line_for_a_multiline_syntax_error(
    tmp_path: Path,
) -> None:
    # A record is "<verdict>\t<target>\t<detail>" as ONE TSV line per
    # target. py_compile's message for this snippet spans several physical
    # lines; if that were embedded verbatim, stdout would carry more lines
    # than (targets + 1 summary line) and the batch probe's "first broken
    # TSV line" parsing would see a truncated record.
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    (hooks_dir / "good.py").write_text("X = 1\n", encoding="utf-8")
    (hooks_dir / "broken.py").write_text("def f(:\n    pass\n", encoding="utf-8")
    config_path = tmp_path / "hooks.json"
    _write_config(
        config_path,
        {"SessionStart": ["python3 hooks/good.py", "python3 hooks/broken.py"]},
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
    assert len(lines) == 3
    assert lines[-1] == "summary\t1 ok, 0 stale, 1 broken"


# ---------------------------------------------------------------------------
# CLI — malformed config shapes that must exit 2, not raise
# ---------------------------------------------------------------------------


def test_cli_command_with_an_unbalanced_quote_exits_2_without_a_traceback(
    tmp_path: Path,
) -> None:
    # A command string that cannot be tokenized (unbalanced quote) is one
    # of the shapes the spec's exit-2 contract must cover — the CLI must
    # report it as its own "error: ..." line, not crash with a raw
    # shlex.ValueError traceback.
    config_path = tmp_path / "hooks.json"
    _write_config(config_path, {"SessionStart": ["python3 'hooks/unterminated.py"]})
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
    assert "error:" in result.stderr
    assert "Traceback" not in result.stderr


def test_cli_hooks_event_entry_as_a_bare_string_exits_2_without_a_traceback(
    tmp_path: Path,
) -> None:
    # A structurally wrong `hooks` object — here an event whose list holds
    # a bare string instead of the expected {"hooks": [...]} mapping — is
    # the other shape the spec's exit-2 contract must cover, distinct from
    # unparseable JSON or a missing "hooks" key.
    config_path = tmp_path / "hooks.json"
    config_path.write_text(
        json.dumps({"hooks": {"SessionStart": ["not-a-mapping"]}}),
        encoding="utf-8",
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

    assert result.returncode == 2
    assert "error:" in result.stderr
    assert "Traceback" not in result.stderr


# ---------------------------------------------------------------------------
# check() — implicit target policy (every *.py directly in hooks/)
# ---------------------------------------------------------------------------


def test_check_includes_an_unregistered_non_common_file_as_an_implicit_target(
    tmp_path: Path,
) -> None:
    # check's target set is not limited to basenames a command names, and
    # not limited to _common.py: every *.py sitting directly in the hooks
    # directory is a target. A stray, unregistered, non-_common.py file
    # must still show up in check's results with some verdict, not be
    # silently skipped because nothing names it.
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    (hooks_dir / "good.py").write_text("X = 1\n", encoding="utf-8")
    stray = hooks_dir / "unregistered_stray.py"
    stray.write_text("Y = 1\n", encoding="utf-8")
    config_path = tmp_path / "hooks.json"
    _write_config(config_path, {"SessionStart": ["python3 hooks/good.py"]})
    aegis_root, autopilot_root = _fake_roots(tmp_path)

    result = codex_hook_doctor.check(
        config=config_path,
        aegis_root=aegis_root,
        autopilot_root=autopilot_root,
    )

    assert any(target == str(stray) for _verdict, target, _detail in result)


# ---------------------------------------------------------------------------
# Prose pins — the doctor-first batch probe docs stay in sync with the tool
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]


def test_codex_implementor_doc_names_doctor_before_first_codex_run_dispatch() -> None:
    # The doctor-first paragraph must precede the codex-run.sh -a live-probe
    # dispatch block, not just appear somewhere in the file.
    doc = (
        _REPO_ROOT / "skills" / "work" / "references" / "codex-implementor.md"
    ).read_text(encoding="utf-8")

    doctor_pos = doc.find("codex_hook_doctor.py")
    dispatch_pos = doc.find("codex-run.sh -a")

    assert doctor_pos != -1
    assert dispatch_pos != -1
    assert doctor_pos < dispatch_pos


def test_state_schema_doc_names_hook_doctor() -> None:
    # Strengthened: bind to the codex_probe row that actually documents the
    # hook_doctor sub-field and its detail shape (the "ok" / "stale:
    # <basenames>" verdicts and the exit-1/exit-2 detail strings), not
    # merely to the bare word "hook_doctor" appearing anywhere in the file.
    doc = (
        _REPO_ROOT / "skills" / "run-autopilot" / "references" / "state-schema.md"
    ).read_text(encoding="utf-8")

    codex_probe_row = next(
        (line for line in doc.splitlines() if line.startswith("| `codex_probe` |")),
        None,
    )

    assert codex_probe_row is not None
    assert '"hook_doctor?": "ok"' in codex_probe_row
    assert '"stale: <basenames>"' in codex_probe_row
    assert "hook_doctor: <the first broken TSV line>" in codex_probe_row
    assert "config unreadable: <config path>" in codex_probe_row


def test_use_codex_skill_doc_names_repair() -> None:
    # Strengthened: bind to the operator-only repair rule and the
    # documented 0/1/2/3 exit codes inside the "## Hook doctor" section,
    # not merely to the bare word "repair" appearing anywhere in the file
    # (the section also names the repair subcommand's own CLI flags).
    doc = (_REPO_ROOT / "skills" / "use-codex" / "SKILL.md").read_text(
        encoding="utf-8",
    )

    section_start = doc.find("## Hook doctor")
    assert section_start != -1
    next_heading = doc.find("\n## ", section_start + 1)
    section = doc[section_start : next_heading if next_heading != -1 else len(doc)]

    assert "`repair` is operator-only" in section
    assert "never run it from a batch" in section
    assert "`0` — every target verdicts `ok`." in section
    assert (
        "`1` — one or more targets verdict `missing`/`empty`/`syntax_error`"
        in section
    )
    assert "`2` — the doctor itself could not run" in section
    assert (
        "`3` — nothing broken, but one or more targets verdict `stale`/`no_canonical`"
        in section
    )


def test_use_codex_skill_doc_documents_the_implicit_target_policy() -> None:
    # check's target set is not limited to command-named basenames or to
    # _common.py -- every *.py sitting directly in the hooks directory is a
    # target (see test_check_includes_an_unregistered_non_common_file_as_
    # an_implicit_target above). Pins that the "## Hook doctor" section
    # documents that policy explicitly.
    doc = (_REPO_ROOT / "skills" / "use-codex" / "SKILL.md").read_text(
        encoding="utf-8",
    )

    section_start = doc.find("## Hook doctor")
    assert section_start != -1
    next_heading = doc.find("\n## ", section_start + 1)
    section = doc[section_start : next_heading if next_heading != -1 else len(doc)]

    assert "*.py" in section
    assert "directly in the hooks directory" in section


def test_codex_implementor_doc_names_exit_2_detail_distinctly_from_exit_1() -> None:
    # Exit 2 (config unreadable/not JSON/no hooks object) leaves the doctor
    # with no targets, so it emits neither a per-target TSV line nor a
    # summary line on that path -- only a single stderr `error: <reason>`
    # line. The doc must map exit 2 to fields the doctor can actually
    # produce there, distinct from the exit-1 TSV-line mapping.
    doc = (
        _REPO_ROOT / "skills" / "work" / "references" / "codex-implementor.md"
    ).read_text(encoding="utf-8")

    exit_1_pos = doc.find("Exit 1")
    exit_2_pos = doc.find("Exit 2")
    assert exit_1_pos != -1
    assert exit_2_pos != -1
    assert exit_1_pos < exit_2_pos

    exit_1_section = doc[exit_1_pos:exit_2_pos]
    exit_2_section = doc[exit_2_pos : exit_2_pos + 600]

    assert "first broken TSV line" in exit_1_section
    assert "doctor's own summary" in exit_1_section

    assert "stderr error line" in exit_2_section
    assert 'hook_doctor: "config unreadable:' in exit_2_section
    assert "first broken TSV line" not in exit_2_section
