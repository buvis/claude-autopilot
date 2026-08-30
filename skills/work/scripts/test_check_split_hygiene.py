"""Behavioural contract for check_split_hygiene.py (PRD 00166).

The checker answers one mechanical question about a test file - "is this
binding read anywhere in this file" - so the de-slop pass never has to judge
it. Every case below pins a rule about BINDINGS. None of them is about an
assertion, a test function, a fixture or a parametrization, and that is the
point: the checker must never give a fix agent a reason to touch one.
"""

from __future__ import annotations

import ast
import importlib.util
import subprocess
import sys
from pathlib import Path

_MODULE_PATH = Path(__file__).with_name("check_split_hygiene.py")
_SPEC = importlib.util.spec_from_file_location("check_split_hygiene", _MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
csh = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(csh)


def _write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def _unused(tmp_path: Path, text: str, name: str = "test_mod.py") -> list[str]:
    # Both rules take a parsed tree; the path is only a label and the
    # conftest.py check. Nothing reads the file, so nothing writes one.
    return csh.unused_bindings(ast.parse(text), tmp_path / name)


def _shadowed(tmp_path: Path, text: str) -> list[str]:
    return csh.shadowed_assignments(ast.parse(text), tmp_path / "test_mod.py")


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_MODULE_PATH), *args],
        capture_output=True,
        text=True,
        check=False,
    )


# --- Unused module-level binding rule ---------------------------------------


def test_reports_module_constant_no_test_reads(tmp_path: Path) -> None:
    lines = _unused(tmp_path, "EXPECTED = 3\n\n\ndef test_thing():\n    assert 1\n")
    assert len(lines) == 1
    assert lines[0].startswith("UNUSED | ")
    assert ":1 | EXPECTED | " in lines[0]


def test_accepts_module_constant_read_in_an_assertion(tmp_path: Path) -> None:
    text = "EXPECTED = 3\n\n\ndef test_thing():\n    assert EXPECTED == 3\n"
    assert _unused(tmp_path, text) == []


def test_never_reports_an_underscore_prefixed_binding(tmp_path: Path) -> None:
    assert _unused(tmp_path, "_HELPER = 3\n\n\ndef test_thing():\n    assert 1\n") == []


def test_never_reports_a_name_used_only_in_a_parametrize_string(
    tmp_path: Path,
) -> None:
    text = (
        "import pytest\n"
        "\n"
        "WIDGET = 3\n"
        "\n"
        '@pytest.mark.parametrize("case", ["WIDGET"])\n'
        "def test_thing(case):\n"
        "    assert case\n"
    )
    assert _unused(tmp_path, text) == []


def test_never_reports_a_conftest_binding(tmp_path: Path) -> None:
    assert _unused(tmp_path, "EXPECTED = 3\n", name="conftest.py") == []


def test_never_reports_a_future_import(tmp_path: Path) -> None:
    # `from __future__ import annotations` binds a name nothing ever loads, so
    # the plain unused-binding rule flags it in every file in this repo - and
    # the fix that follows is deletion-only. Removing it silently un-lazies
    # every annotation in the module. A compiler directive is not a binding.
    text = (
        "from __future__ import annotations\n"
        "\n"
        "\n"
        "def test_thing() -> None:\n"
        "    assert 1\n"
    )
    assert _unused(tmp_path, text) == []


def test_never_reports_a_pytest_magic_module_name(tmp_path: Path) -> None:
    # pytest reads `pytestmark` and `pytest_plugins` by introspection, not by
    # a same-file load - the same reason conftest.py is excluded. Deleting a
    # non-strict xfail mark yields a silent XPASS: no failure, no gate, a
    # weakened test. Exactly the harm this whole check exists to prevent.
    text = (
        "import pytest\n"
        "\n"
        "pytestmark = pytest.mark.xfail\n"
        "pytest_plugins = ['tests.fixtures']\n"
        "\n"
        "\n"
        "def test_thing():\n"
        "    assert 1\n"
    )
    assert _unused(tmp_path, text) == []


def test_never_reports_a_star_import(tmp_path: Path) -> None:
    # `from helpers import *` binds no name of its own; ast spells the alias
    # `*`, so the plain rule reported a binding literally named `*` whose
    # deletion takes every name the star supplied.
    text = "from fnmatch import *\n\n\ndef test_thing():\n    assert 1\n"
    assert _unused(tmp_path, text) == []


def test_never_reports_an_importorskip_guard(tmp_path: Path) -> None:
    # The binding is unread on purpose; the CALL is the guard. Delete it and
    # the module runs wherever the dependency is installed, so the suite
    # backstop stays green while the skip is gone.
    text = (
        "import pytest\n"
        "\n"
        'np = pytest.importorskip("numpy")\n'
        "\n"
        "\n"
        "def test_thing():\n"
        "    assert 1\n"
    )
    assert _unused(tmp_path, text) == []


def test_reports_an_import_that_is_bound_and_never_used(tmp_path: Path) -> None:
    lines = _unused(tmp_path, "import fnmatch\n\n\ndef test_thing():\n    assert 1\n")
    assert len(lines) == 1
    assert ":1 | fnmatch | " in lines[0]


def test_never_reports_a_name_listed_in_dunder_all(tmp_path: Path) -> None:
    text = 'WIDGET = 3\n__all__ = ["WIDGET"]\n\n\ndef test_thing():\n    assert 1\n'
    assert _unused(tmp_path, text) == []


def test_never_reports_a_fixture_used_only_as_a_test_argument(tmp_path: Path) -> None:
    # The PRD's own edge case: arg identifiers are collected as loads, so a
    # fixture reached only through a test-function parameter is a read.
    text = (
        "import pytest\n"
        "\n"
        "\n"
        "@pytest.fixture\n"
        "def widget():\n"
        "    return 3\n"
        "\n"
        "\n"
        "def test_thing(widget):\n"
        "    assert widget\n"
    )
    assert _unused(tmp_path, text) == []


# --- Shadowed assignment rule -----------------------------------------------


def test_reports_a_reassignment_with_no_read_between_naming_the_first_line(
    tmp_path: Path,
) -> None:
    text = "def test_thing():\n    x = 1\n    x = 2\n    assert x\n"
    lines = _shadowed(tmp_path, text)
    assert len(lines) == 1
    assert lines[0].startswith("SHADOWED | ")
    assert ":2 | x | reassigned before the previous value is read" in lines[0]


def test_accepts_a_reassignment_whose_previous_value_was_read(tmp_path: Path) -> None:
    text = "def test_thing():\n    x = 1\n    assert x\n    x = 2\n    assert x\n"
    assert _shadowed(tmp_path, text) == []


def test_counts_augmented_assignment_as_a_read(tmp_path: Path) -> None:
    text = "def test_thing():\n    x = 1\n    x += 1\n    x = 2\n    assert x\n"
    assert _shadowed(tmp_path, text) == []


def test_never_reports_a_loop_target_rebinding(tmp_path: Path) -> None:
    text = (
        "def test_thing():\n"
        "    x = 1\n"
        "    for x in (2, 3):\n"
        "        pass\n"
        "    x = 4\n"
        "    assert x\n"
    )
    assert _shadowed(tmp_path, text) == []


def test_never_reports_an_except_as_target(tmp_path: Path) -> None:
    # `except ValueError as caught` binds via ExceptHandler.name, a plain
    # str - ast.walk never yields it as a Name node, so the generic clear
    # missed it and the earlier default was reported as dead. The PRD lists
    # `except ... as` beside `for` and `with` as never reported.
    text = (
        "def test_thing():\n"
        "    caught = None\n"
        "    try:\n"
        "        risky()\n"
        "    except ValueError as caught:\n"
        "        pass\n"
        "    caught = other()\n"
        "    assert caught\n"
    )
    assert _shadowed(tmp_path, text) == []


def test_never_reports_a_with_target_rebinding(tmp_path: Path) -> None:
    text = (
        "def test_thing():\n"
        "    handle = None\n"
        "    with open('f') as handle:\n"
        "        pass\n"
        "    handle = other()\n"
        "    assert handle\n"
    )
    assert _shadowed(tmp_path, text) == []


def test_never_reports_a_comprehension_target_rebinding(tmp_path: Path) -> None:
    text = (
        "def test_thing():\n"
        "    item = None\n"
        "    rows = [item for item in (1, 2)]\n"
        "    item = last(rows)\n"
        "    assert item\n"
    )
    assert _shadowed(tmp_path, text) == []


def test_never_reports_a_match_capture_rebinding(tmp_path: Path) -> None:
    # `case ... as got` binds through MatchAs.name, a plain str like
    # ExceptHandler.name. Pinned so narrowing the sweep to node types keeps
    # every capture construct the PRD names excluded.
    text = (
        "def test_thing(value):\n"
        "    got = None\n"
        "    match value:\n"
        "        case [got, *rest]:\n"
        "            pass\n"
        "    got = final()\n"
        "    assert got\n"
    )
    assert _shadowed(tmp_path, text) == []


def test_reports_a_shadow_a_nested_def_would_otherwise_hide(tmp_path: Path) -> None:
    # A nested `def` rebinds outright - it is not one of the PRD's capture
    # constructs. Clearing on it (which an attribute-name sweep over `.name`
    # did) silently swallowed a genuine dead value, exactly the leftover this
    # whole check exists to find.
    text = (
        "def test_thing():\n"
        "    handler = 1\n"
        "    def handler():\n"
        "        return 2\n"
        "    handler = 3\n"
        "    assert handler == 3\n"
    )
    lines = _shadowed(tmp_path, text)
    assert len(lines) == 1
    assert ":2 | handler | reassigned before the previous value is read" in lines[0]


def test_skips_a_function_that_calls_locals(tmp_path: Path) -> None:
    # The other arm of _escapes: a name lookup rather than a statement node.
    text = "def test_thing():\n    x = 1\n    print(locals())\n    x = 2\n"
    assert _shadowed(tmp_path, text) == []


def test_skips_a_function_that_declares_a_global(tmp_path: Path) -> None:
    text = "def test_thing():\n    global x\n    x = 1\n    x = 2\n"
    assert _shadowed(tmp_path, text) == []


# --- Exit contract ----------------------------------------------------------


def test_unparseable_file_exits_2_and_names_the_file_on_stderr(
    tmp_path: Path,
) -> None:
    broken = _write(tmp_path, "test_broken.py", "def test_thing(:\n")
    result = _run(str(broken))
    assert result.returncode == 2
    assert str(broken) in result.stderr
    assert "not inspected" in result.stderr


def test_one_uninspectable_path_forces_exit_2_beside_clean_files(
    tmp_path: Path,
) -> None:
    # Exit 2 outranks both 0 and 1: a batch that could not inspect every file
    # must never read as a clean check, or the gate certifies a file it never
    # opened.
    clean = _write(tmp_path, "test_clean.py", "def test_thing():\n    assert 1\n")
    notes = _write(tmp_path, "notes.md", "not python\n")
    result = _run(str(clean), str(notes))
    assert result.returncode == 2
    assert str(notes) in result.stderr


def test_clean_file_exits_0_and_a_violating_file_exits_1(tmp_path: Path) -> None:
    clean = _write(tmp_path, "test_clean.py", "def test_thing():\n    assert 1\n")
    assert _run(str(clean)).returncode == 0
    dirty = _write(tmp_path, "test_dirty.py", "EXPECTED = 3\n")
    dirty_result = _run(str(dirty))
    assert dirty_result.returncode == 1
    assert "UNUSED | " in dirty_result.stdout
