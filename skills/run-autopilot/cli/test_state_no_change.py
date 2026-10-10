#!/usr/bin/env python3
"""Tests for state.NO_CHANGE: the no-op sentinel a `transaction` mutator can
return to signal that nothing needs writing.

state.transaction(path, fn, ...): when fn(current) returns NO_CHANGE (by
identity), the validator, the schema-version stamp, the .bak write and the
atomic replace are all skipped, and a fresh json.loads of the pre-transaction
bytes is returned instead of `current`.

statectl.mutate(state_path, apply): apply(current) returning NO_CHANGE makes
mutate's inner fn return NO_CHANGE too, so nothing is written; mutate's own
return value to its caller is whatever `apply` assigned via its closure,
unaffected by the sentinel.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cli import schema, state, statectl


def _bak_path(path: Path) -> Path:
    return Path(f"{path}.bak")


def _write_json(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")


class _TempDirTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.path = self.dir / "state.json"


class NoChangeIdentityTest(_TempDirTestCase):
    def test_no_change_is_an_object_compared_only_by_identity(self) -> None:
        self.assertIsInstance(state.NO_CHANGE, object)
        self.assertIsNot(state.NO_CHANGE, {})
        self.assertIsNot(state.NO_CHANGE, None)


class TransactionNoChangeTest(_TempDirTestCase):
    def test_transaction_writes_neither_backup_nor_state_on_no_change(self) -> None:
        _write_json(self.path, {"phase": "build", "cycle": 1})
        state.transaction(self.path, lambda current: dict(current, cycle=2))
        state_before = self.path.read_bytes()
        state_mtime_before = self.path.stat().st_mtime_ns
        bak_before = _bak_path(self.path).read_bytes()
        bak_mtime_before = _bak_path(self.path).stat().st_mtime_ns

        def no_op(current: dict) -> dict:
            current["phase"] = "mutated-then-abandoned"
            return state.NO_CHANGE

        returned = state.transaction(self.path, no_op)

        self.assertEqual(self.path.read_bytes(), state_before)
        self.assertEqual(self.path.stat().st_mtime_ns, state_mtime_before)
        self.assertEqual(_bak_path(self.path).read_bytes(), bak_before)
        self.assertEqual(_bak_path(self.path).stat().st_mtime_ns, bak_mtime_before)
        # The in-place mutation `no_op` made before giving up must not leak
        # into the returned value either - it is a fresh re-parse of the
        # pre-transaction bytes, not the mutated `current` object.
        self.assertEqual(returned["phase"], "build")
        self.assertEqual(returned["cycle"], 2)

    def test_no_change_skips_the_validator(self) -> None:
        _write_json(self.path, {"phase": "build"})
        calls = []

        def boom_validator(new_state: dict) -> None:
            calls.append(new_state)
            raise AssertionError("validator must not run on NO_CHANGE")

        state.transaction(
            self.path, lambda current: state.NO_CHANGE, validator=boom_validator
        )
        self.assertEqual(calls, [])

    def test_a_changing_transaction_still_refreshes_the_backup(self) -> None:
        _write_json(self.path, {"phase": "build", "cycle": 1})
        state.transaction(self.path, lambda current: dict(current, cycle=2))
        bak_after_first = _bak_path(self.path).read_bytes()

        state.transaction(self.path, lambda current: dict(current, cycle=3))

        bak_after_second = _bak_path(self.path).read_bytes()
        self.assertNotEqual(bak_after_second, bak_after_first)
        committed, _ = state.load(self.path)
        self.assertEqual(committed["cycle"], 3)
        self.assertEqual(json.loads(bak_after_second)["cycle"], 2)


class MutateNoChangeTest(_TempDirTestCase):
    def test_mutate_returns_no_change_and_writes_nothing(self) -> None:
        _write_json(self.path, {"phase": "build", "cycle": 1})
        state_before = self.path.read_bytes()

        def apply(current: dict) -> object:
            current["cycle"] = 99
            return state.NO_CHANGE

        outcome = statectl.mutate(self.path, apply)

        self.assertIs(outcome, state.NO_CHANGE)
        self.assertEqual(self.path.read_bytes(), state_before)
        self.assertFalse(_bak_path(self.path).exists())

    def test_statectl_re_exports_the_same_sentinel(self) -> None:
        self.assertIs(statectl.NO_CHANGE, state.NO_CHANGE)

    def test_mutate_still_writes_and_returns_outcome_when_apply_changes_state(
        self,
    ) -> None:
        _write_json(self.path, {"phase": "build", "cycle": 1})

        def apply(current: dict) -> str:
            current["cycle"] = 2
            return "bumped"

        outcome = statectl.mutate(self.path, apply)

        self.assertEqual(outcome, "bumped")
        committed, _ = state.load(self.path)
        self.assertEqual(committed["cycle"], 2)


if __name__ == "__main__":
    unittest.main()
