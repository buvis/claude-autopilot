"""Interpreter-independent pins for the parse-error branches of
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
from pathlib import Path
from typing import Any

import pytest
from test_codex_hook_doctor import codex_hook_doctor

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
