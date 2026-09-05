#!/usr/bin/env python3
"""detect_tautological_tests.py - test functions whose shape cannot fail.

A tautological test passes whatever the code under test does. Reviewers wave
these through when they read like tests (PRD 00173: an `A or B` assertion
already satisfied by a pre-existing branch). The shapes below are decidable
from `ast`, so they are computed once and handed to every reviewer as facts.

    detect_tautological_tests.py <file>...

Prints a markdown block: one `[MECH] {emoji} ... | File: ... | Task: general`
line per hit, in the reviewer issue-line format so step 6 can absorb it into
the consolidated table unchanged. Non-test, non-Python and unparseable files
are skipped. Exit is always 0 - a facts block is review context, and a
missing fact must never fail the cycle.

Shapes (severity):
  🟠 constant assert        `assert True`, `assert (a, b)`
  🟠 self-compare           `assert x == x`
  🟠 swallowed exception    `try: ... except Exception: pass`
  🟡 either-or hedge        `assert A or B`
  🟡 any-exception          `pytest.raises(Exception)`
  🟡 no assertion           nothing in the body (or a same-file helper) can fail

Not a shape: `before = snap(); act(); assert snap() == before`. Inlining the
name would call that a self-compare; the calibration run over this pack's own
2133 tests found every such hit to be that idiom, so names are never inlined.

ponytail: Python/pytest only via `ast`, one level of helper resolution
(module functions and the enclosing class's methods). Extend when a real
miss shows up.
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

FUNCTION_NODES = (ast.FunctionDef, ast.AsyncFunctionDef)
ALWAYS_TRUE_OPS = (ast.Eq, ast.Is, ast.GtE, ast.LtE)
BROAD_EXCEPTIONS = {"Exception", "BaseException", "AssertionError"}
ASSERTING_NAMES = {"raises", "warns", "fail", "expect"}
HIGH, MEDIUM = "🟠", "🟡"

Hit = tuple[str, int, str]


def is_test_file(path: Path) -> bool:
    name = path.name
    return path.suffix == ".py" and (name.startswith("test_") or name.endswith("_test.py"))


def test_functions(tree: ast.Module) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    """Module-level `test_*` functions and `test_*` methods of any class."""
    return [fn for fn, _ in _tests_with_helpers(tree)]


def _functions(body: list[ast.stmt]) -> dict[str, ast.AST]:
    return {n.name: n for n in body if isinstance(n, FUNCTION_NODES)}


def _tests_with_helpers(tree: ast.Module) -> list[tuple[ast.AST, dict[str, ast.AST]]]:
    """Each test paired with the helpers a call in it may resolve to: the
    module's functions, plus the enclosing class's methods for a method."""
    module_helpers = _functions(tree.body)
    found = []
    for node in tree.body:
        if isinstance(node, FUNCTION_NODES) and node.name.startswith("test_"):
            found.append((node, module_helpers))
        elif isinstance(node, ast.ClassDef):
            helpers = {**module_helpers, **_functions(node.body)}
            for child in node.body:
                if isinstance(child, FUNCTION_NODES) and child.name.startswith("test_"):
                    found.append((child, helpers))
    return found


def _callee_name(call: ast.Call) -> str:
    func = call.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return ""


def _has_assertion(fn: ast.AST, helpers: dict[str, ast.AST], depth: int = 1) -> bool:
    for node in ast.walk(fn):
        if isinstance(node, ast.Assert):
            return True
        if isinstance(node, ast.Call):
            name = _callee_name(node)
            if "assert" in name.lower() or name in ASSERTING_NAMES:
                return True
            if depth and name in helpers and _has_assertion(helpers[name], helpers, 0):
                return True
    return False


def _swallows(handler: ast.ExceptHandler) -> bool:
    broad = handler.type is None or (
        isinstance(handler.type, ast.Name) and handler.type.id in BROAD_EXCEPTIONS
    )
    inert = all(
        isinstance(stmt, (ast.Pass, ast.Continue))
        or (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant))
        for stmt in handler.body
    )
    return broad and inert


def _broad_raises(node: ast.With) -> bool:
    for item in node.items:
        call = item.context_expr
        if (
            isinstance(call, ast.Call)
            and _callee_name(call) == "raises"
            and call.args
            and isinstance(call.args[0], ast.Name)
            and call.args[0].id in {"Exception", "BaseException"}
        ):
            return True
    return False


def _assert_shape(node: ast.Assert) -> Hit | None:
    test = node.test
    if isinstance(test, ast.Constant) or (isinstance(test, ast.Tuple) and test.elts):
        return HIGH, node.lineno, "asserts a constant: it cannot fail"
    if (
        isinstance(test, ast.Compare)
        and len(test.ops) == 1
        and isinstance(test.ops[0], ALWAYS_TRUE_OPS)
        and ast.dump(test.left) == ast.dump(test.comparators[0])
    ):
        return HIGH, node.lineno, "compares an expression with itself: it cannot fail"
    if isinstance(test, ast.BoolOp) and isinstance(test.op, ast.Or):
        return MEDIUM, node.lineno, "hedges with `or`: either outcome satisfies it"
    return None


def check_test_function(fn: ast.AST, helpers: dict[str, ast.AST]) -> list[Hit]:
    """(severity, line, reason) per tautological shape in one test."""
    hits: list[Hit] = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Assert):
            hit = _assert_shape(node)
            if hit:
                hits.append(hit)
        elif isinstance(node, ast.Try) and any(_swallows(h) for h in node.handlers):
            hits.append((HIGH, node.lineno, "swallows exceptions: a failure inside the try cannot surface"))
        elif isinstance(node, ast.With) and _broad_raises(node):
            hits.append((MEDIUM, node.lineno, "accepts any exception via `raises(Exception)`"))
    if not _has_assertion(fn, helpers):
        hits.append((MEDIUM, fn.lineno, "has no assertion: it only proves the code does not raise"))
    return hits


def check_test_file(path: Path) -> tuple[str, int, list[tuple[str, str, int, str]]]:
    """(status, test count, [(severity, test name, line, reason)])."""
    if not is_test_file(path):
        return "skipped (not a test file)", 0, []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, ValueError, UnicodeDecodeError):
        return "skipped (parse error)", 0, []
    tests = _tests_with_helpers(tree)
    hits = [
        (severity, fn.name, line, reason)
        for fn, helpers in tests
        for severity, line, reason in check_test_function(fn, helpers)
    ]
    return "ok", len(tests), hits


def render_block(paths: list[Path]) -> str:
    lines = [
        "## Tautological test shapes (computed, do not re-judge)",
        "",
        "Each `[MECH]` line is a test whose shape cannot fail as written. Raise",
        "it; step 6 adds any line the table lacks. `mech-check` is the finder.",
        "",
    ]
    files = tests = 0
    for path in paths:
        status, count, hits = check_test_file(path)
        if status == "skipped (parse error)":
            lines.append(f"- `{path}` — {status}")
        if status != "ok":
            continue
        files += 1
        tests += count
        for severity, name, line, reason in hits:
            lines.append(f"[MECH] {severity} {name} {reason} | File: {path}:{line} | Task: general")
    lines.append("")
    lines.append(f"Checked {tests} test function(s) in {files} test file(s).")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Print a markdown block of test functions whose shape cannot fail.",
    )
    parser.add_argument("files", nargs="+", type=Path, metavar="FILE")
    args = parser.parse_args(argv)
    print(render_block(args.files))
    return 0


if __name__ == "__main__":
    sys.exit(main())
