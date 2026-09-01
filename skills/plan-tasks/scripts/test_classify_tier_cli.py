"""Tests for classify_tier.py's CLI entry point (``main()``).

Split out of test_classify_tier.py (which grew past the repo's 800-line file
cap) into this and its sibling test_classify_tier_*.py modules; see
_classify_tier_test_support.py for the shared ``_MODULE_PATH``/``_run_cli``
helpers every one of them calls.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

_SUPPORT_PATH = Path(__file__).with_name("_classify_tier_test_support.py")
_SUPPORT_SPEC = importlib.util.spec_from_file_location(
    "classify_tier_test_support", _SUPPORT_PATH
)
assert _SUPPORT_SPEC is not None and _SUPPORT_SPEC.loader is not None
_support = importlib.util.module_from_spec(_SUPPORT_SPEC)
_SUPPORT_SPEC.loader.exec_module(_support)

_MODULE_PATH = _support._MODULE_PATH
_run_cli = _support._run_cli


def test_the_cli_warns_once_about_an_unknown_default_model_and_still_exits_zero(
    tmp_path: Path,
) -> None:
    # "fable" is a real tier elsewhere but not in this ordering. The warning
    # moved out of the pure core and into the CLI entry point, so the
    # observable behaviour has to be pinned at the process boundary: exactly
    # one line naming the dropped value on stderr, exit 0, and the unchanged
    # tier still on stdout.
    result = _run_cli(
        tmp_path,
        ["cache/store.py", "cache/keys.py", "cli/main.py"],
        "design and migrate the cache layer",
        120,
        "--default-model",
        "fable",
    )

    assert result.returncode == 0
    assert json.loads(result.stdout) == {"model": "sonnet", "tier_reason": "default"}
    stderr_lines = result.stderr.splitlines()
    # The wording is free, but there must be exactly one line and the dropped
    # value has to be in it: a warning that never names what it rejected
    # leaves the operator hunting the batch for a typo the CLI already found.
    assert len(stderr_lines) == 1
    assert "fable" in stderr_lines[0]


@pytest.mark.parametrize(
    ("files", "text", "lines", "extra", "expected"),
    [
        (
            ["tests/test_x.py"],
            "port the concurrency tests",
            10,
            (),
            {"model": "sonnet", "tier_reason": "test_port"},
        ),
        (
            ["cli/schema.py"],
            "widen the result schema",
            30,
            ("--contract-edit",),
            {"model": "opus", "tier_reason": "contract"},
        ),
        (
            ["cli/loop.py"],
            "fix the retry backoff",
            30,
            ("--algorithmic-risk",),
            {"model": "opus", "tier_reason": "algorithmic_risk"},
        ),
        (
            ["src/app.py"],
            "rename foo to bar",
            10,
            ("--default-model", "opus"),
            {"model": "opus", "tier_reason": "floor"},
        ),
        (
            ["src/app.py"],
            "rename foo to bar",
            10,
            (),
            {"model": "haiku", "tier_reason": "mechanical"},
        ),
        (
            ["src/app.py"],
            "rename foo to bar",
            500,
            (),
            {"model": "sonnet", "tier_reason": "default"},
        ),
    ],
)
def test_the_cli_prints_the_classification_as_json_and_exits_zero(
    tmp_path: Path,
    files: list[str],
    text: str,
    lines: int,
    extra: tuple[str, ...],
    expected: dict,
) -> None:
    # The planner shells out to this and parses stdout, so the JSON shape is
    # the contract. The last two rows are the plumbing check: same production
    # file, no flags, so only --text-file can produce "mechanical" and only
    # --lines can take it away again. A CLI that passed an empty text through
    # fails the fifth row; one that hardcoded the line count fails the sixth.
    result = _run_cli(tmp_path, files, text, lines, *extra)

    assert result.returncode == 0
    assert json.loads(result.stdout) == expected


def test_the_cli_rejects_a_negative_lines_value(tmp_path: Path) -> None:
    # A negative line count trivially satisfies "<= 50" and would misroute an
    # arbitrarily large change into the cheap tier, so the CLI has to refuse
    # it rather than classify it.
    result = _run_cli(tmp_path, ["src/app.py"], "rename foo to bar", -1)

    assert result.returncode == 1
    assert result.stderr.strip() != ""
    assert result.stdout == ""


@pytest.mark.parametrize("missing", ["--files-file", "--text-file"])
def test_the_cli_exits_one_when_an_input_file_cannot_be_read(
    tmp_path: Path,
    missing: str,
) -> None:
    # A planner that read "no files" from an unreadable list would classify
    # every task as sonnet/default and never say why, so this arm fails loud
    # with exit 1 and a plain message.
    present = "--text-file" if missing == "--files-file" else "--files-file"
    real = tmp_path / "real.txt"
    real.write_text("src/app.py\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(_MODULE_PATH),
            present,
            str(real),
            missing,
            str(tmp_path / "gone.txt"),
            "--lines",
            "10",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert result.stderr.strip() != ""
    assert "Traceback" not in result.stderr


def test_the_cli_exits_one_when_the_lines_argument_is_absent(
    tmp_path: Path,
) -> None:
    # --lines is a required input, not an optional one defaulting to zero: a
    # silent zero satisfies the mechanical bound, so a caller who forgot the
    # flag would get the cheap tier on an arbitrarily large change.
    files_file = tmp_path / "files.txt"
    files_file.write_text("src/app.py\n", encoding="utf-8")
    text_file = tmp_path / "text.txt"
    text_file.write_text("rename foo to bar\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(_MODULE_PATH),
            "--files-file",
            str(files_file),
            "--text-file",
            str(text_file),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert result.stderr.strip() != ""
    assert "Traceback" not in result.stderr


def test_the_cli_exits_one_when_the_files_file_argument_is_absent(
    tmp_path: Path,
) -> None:
    # Omitting the flag entirely is the same failure as pointing it at nothing.
    text_file = tmp_path / "text.txt"
    text_file.write_text("rename foo to bar\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(_MODULE_PATH),
            "--text-file",
            str(text_file),
            "--lines",
            "10",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert result.stderr.strip() != ""
    assert "Traceback" not in result.stderr
