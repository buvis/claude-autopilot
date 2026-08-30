#!/usr/bin/env python3
"""check_split_hygiene.py - report dead or shadowed bindings in test files.

PRD 00166. The de-slop pass is forbidden to touch tests, and rightly so: an
agent deciding by judgment which test bindings are dead is the path to a
silently weakened test. This is the mechanical answer to the mechanical half
of that question - "is this binding read anywhere in this file" - answered
with `ast`, never judgment. It reports bindings only: never an assertion, a
test function, a fixture or a parametrization, so the fix is deletion-only.

    check_split_hygiene.py FILE [FILE ...]

Exit 0 clean, 1 violations on stdout, 2 could not run - the same three-way
contract check_style_limits.py uses, so the caller's outcome ladder is the
same shape.
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_ESCAPE_CALLS = frozenset({"exec", "eval", "locals"})
# Module-level names pytest resolves by introspection, never by a same-file
# load - the same reason `conftest.py` is excluded wholesale. A missing load
# proves nothing here, and deleting one silently changes which tests run.
_PYTEST_MAGIC_NAMES = frozenset({"pytestmark", "pytest_plugins"})
# Nodes that bind a name as a plain `str` attribute rather than a Name node:
# `except ... as e`, `import x as y`, `case [x, *rest]`, a nested `def`.
_STR_BINDING_ATTRS = ("name", "asname", "rest")


def _loaded_names(tree: ast.AST) -> set[str]:
    """Every identifier this module could read.

    Load-context names, attribute identifiers, argument identifiers (a
    fixture reached only as a test-function parameter is a read), and
    identifier-shaped tokens inside string literals - a `getattr` target, a
    `parametrize` id, a `monkeypatch` path. The string sweep also covers
    `__all__`, whose entries are either those strings or bare Load names.
    """
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            if isinstance(node.ctx, ast.Load):
                names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            names.update(_IDENT_RE.findall(node.value))
    return names


def _is_import_guard(stmt: ast.stmt) -> bool:
    """True for `np = pytest.importorskip("numpy")`. The binding is often
    unread, but the call IS the skip guard: delete it and the module runs
    wherever the dependency happens to be installed, so the suite backstop
    stays green while the guard is gone."""
    for node in ast.walk(stmt):
        if isinstance(node, ast.Attribute) and node.attr == "importorskip":
            return True
        if isinstance(node, ast.Name) and node.id == "importorskip":
            return True
    return False


def _module_bindings(tree: ast.Module) -> list[tuple[str, int]]:
    """Plain-Name assignment targets and imported names bound at module
    level, in source order. A name bound inside a function or class body is
    not module level and never appears here."""
    out: list[tuple[str, int]] = []
    for stmt in tree.body:
        if isinstance(stmt, (ast.Assign, ast.AnnAssign)) and _is_import_guard(stmt):
            continue
        if isinstance(stmt, ast.Assign):
            out.extend(
                (t.id, t.lineno) for t in stmt.targets if isinstance(t, ast.Name)
            )
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            out.append((stmt.target.id, stmt.target.lineno))
        elif isinstance(stmt, ast.ImportFrom) and stmt.module == "__future__":
            # A compiler directive, not a binding. `annotations` is never
            # loaded by anything, so the plain rule flags it in every file
            # that has one - and the deletion-only fix that follows would
            # silently un-lazy every annotation in the module.
            continue
        elif isinstance(stmt, (ast.Import, ast.ImportFrom)):
            # `from x import *` binds no name of its own - ast spells the
            # alias `*`, and deleting the statement takes every name the
            # star supplied with it.
            out.extend(
                (alias.asname or alias.name.split(".")[0], stmt.lineno)
                for alias in stmt.names
                if alias.name != "*"
            )
    return out


def unused_bindings(tree: ast.Module, path: Path) -> list[str]:
    """UNUSED lines for module-level names nothing in the file loads.

    `conftest.py` is excluded wholesale: pytest resolves fixtures by name
    across files, so a missing same-file load proves nothing there.
    """
    if path.name == "conftest.py":
        return []
    loads = _loaded_names(tree)
    return [
        f"UNUSED | {path}:{lineno} | {name} | "
        "module-level binding never read in this file"
        for name, lineno in _module_bindings(tree)
        if not name.startswith("_")
        and name not in loads
        and name not in _PYTEST_MAGIC_NAMES
    ]


def _escapes(fn: ast.AST) -> bool:
    """True when a function's local bindings cannot be tracked from its own
    source - `global`, `nonlocal`, `del`, or an `exec`/`eval`/`locals`
    reference. Such a function is skipped whole rather than guessed at."""
    for node in ast.walk(fn):
        if isinstance(node, (ast.Global, ast.Nonlocal, ast.Delete)):
            return True
        if isinstance(node, ast.Name) and node.id in _ESCAPE_CALLS:
            return True
    return False


def _simple_target(stmt: ast.stmt) -> ast.Name | None:
    """The single plain Name a statement rebinds outright, or None.

    `x = y = 1`, `x += 1`, a bare `x: int` annotation, and every binding a
    compound statement makes (`with ... as`, `for`, `except ... as`, a
    comprehension) fall through to None - their rebinding is the construct's
    own semantics, not a shadow.
    """
    if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
        target = stmt.targets[0]
        return target if isinstance(target, ast.Name) else None
    if isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
        return stmt.target if isinstance(stmt.target, ast.Name) else None
    return None


def _clear(pending: dict[str, int], node: ast.AST) -> None:
    """Drop every name the subtree mentions. A read clears the tracked
    assignment because the value was used; a store clears it because the
    rebinding happened somewhere this scan does not model - inside an `if`,
    a loop, a nested function - and a conditional rebinding is not a shadow.
    """
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name):
            pending.pop(sub.id, None)
            continue
        if isinstance(sub, ast.arg):
            pending.pop(sub.arg, None)
            continue
        # `except ValueError as e`, `import x as y`, `case [a, *rest]` and a
        # nested `def` all bind a name ast.walk never yields as a Name node -
        # it lives in a plain `str` attribute. Clearing by attribute is what
        # keeps those rebindings out of the SHADOWED rule, exactly as the
        # `for`/`with` targets above are kept out.
        for attr in _STR_BINDING_ATTRS:
            bound = getattr(sub, attr, None)
            if isinstance(bound, str):
                pending.pop(bound, None)


def _scan_body(body: list[ast.stmt], path: Path, out: list[str]) -> None:
    """Walk one function's own statements in source order, tracking the line
    of each name's last unread assignment. Reassigning such a name reports
    the PREVIOUS line - that is the value nothing ever read."""
    pending: dict[str, int] = {}
    for stmt in body:
        target = _simple_target(stmt)
        if target is None:
            _clear(pending, stmt)
            continue
        _clear(pending, stmt.value)
        previous = pending.get(target.id)
        if previous is not None:
            out.append(
                f"SHADOWED | {path}:{previous} | {target.id} | "
                "reassigned before the previous value is read",
            )
        pending[target.id] = target.lineno


def shadowed_assignments(tree: ast.Module, path: Path) -> list[str]:
    """SHADOWED lines for a local reassigned before its value is read."""
    out: list[str] = []
    for node in ast.walk(tree):
        is_func = isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        if is_func and not _escapes(node):
            _scan_body(node.body, path, out)
    return out


def check_file(path: Path, skipped: list[str]) -> list[str]:
    """Both rules for one file. A file that cannot be parsed is recorded in
    `skipped` and contributes no lines - never a silent pass."""
    if path.suffix != ".py":
        print(f"check_split_hygiene: not a Python file: {path}", file=sys.stderr)
        skipped.append(str(path))
        return []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, UnicodeDecodeError, SyntaxError, ValueError) as exc:
        print(f"check_split_hygiene: cannot inspect {path}: {exc}", file=sys.stderr)
        skipped.append(str(path))
        return []
    return unused_bindings(tree, path) + shadowed_assignments(tree, path)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Report dead or shadowed bindings in test files.",
    )
    parser.add_argument("files", nargs="+", type=Path)
    args = parser.parse_args(argv)
    skipped: list[str] = []
    found: list[str] = []
    for path in args.files:
        found.extend(check_file(path, skipped))
    for line in found:
        print(line)
    if skipped:
        # A skip is never a pass. Exit 2 is the caller's "could not run"
        # branch: it records `split_hygiene: failed:<stderr>` and dispatches
        # no fixer. It outranks exit 1 - violations found are still printed,
        # but an incomplete check never reads as a clean one.
        print(
            "check_split_hygiene: check incomplete, "
            f"{len(skipped)} file(s) not inspected: {skipped}",
            file=sys.stderr,
        )
        return 2
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
