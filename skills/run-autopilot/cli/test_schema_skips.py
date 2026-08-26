#!/usr/bin/env python3
"""Tests for schema.validate's handling of `batch.skips[]` (PRD 00137).

A sibling of `cli/test_schema.py` rather than more of it: that file sits at 752
lines against this project's 800-line ceiling. `cli/test_schema_completed_prds.py`
and `cli/test_schema_task_entries.py` are the same split for their fields, and
this file follows their shape - self-contained, importing only `cli.schema`,
building each state inline.

Scope: the skip records `autopilot select` appends when a PRD's `eligibility:`
check fails. Same doctrine as every other field here - optional, but checked
when present, and the message names the exact element path.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cli import schema


def _well_formed_skip() -> dict:
    return {
        "prd": "00110-flip-v1.md",
        "command": "test -f evidence.md",
        "exit_code": 1,
        "note": "",
        "at": "2026-08-26T18:04:11Z",
    }


class ValidateBatchSkipsTest(unittest.TestCase):
    def test_absent_skips_passes(self) -> None:
        self.assertIsNone(schema.validate({"batch": {"id": "202608261200"}}))

    def test_well_formed_entry_passes(self) -> None:
        self.assertIsNone(schema.validate({"batch": {"skips": [_well_formed_skip()]}}))

    def test_empty_list_passes(self) -> None:
        self.assertIsNone(schema.validate({"batch": {"skips": []}}))

    def test_entry_carrying_only_some_fields_passes(self) -> None:
        self.assertIsNone(
            schema.validate({"batch": {"skips": [{"prd": "00110-x.md"}]}})
        )

    def test_rejects_non_list_skips(self) -> None:
        with self.assertRaises(schema.SchemaError) as ctx:
            schema.validate({"batch": {"skips": "00110-flip-v1.md"}})
        self.assertIn("batch.skips", str(ctx.exception))

    def test_rejects_non_dict_entry(self) -> None:
        with self.assertRaises(schema.SchemaError) as ctx:
            schema.validate({"batch": {"skips": ["00110-flip-v1.md"]}})
        self.assertIn("batch.skips[0]", str(ctx.exception))

    def test_rejects_wrong_typed_field_naming_the_element_path(self) -> None:
        for field, bad_value, type_name in (
            ("prd", 123, "str"),
            ("command", ["false"], "str"),
            ("exit_code", "1", "int"),
            ("exit_code", True, "int"),
        ):
            with self.subTest(field=field, value=bad_value):
                entry = _well_formed_skip()
                entry[field] = bad_value
                with self.assertRaises(schema.SchemaError) as ctx:
                    schema.validate({"batch": {"skips": [entry]}})
                msg = str(ctx.exception)
                self.assertIn(f"batch.skips[0].{field}", msg)
                self.assertIn(f"expected {type_name}", msg)

    def test_bad_field_on_second_element_names_index_one(self) -> None:
        # The index must come from the loop, not a hardcoded 0.
        bad = _well_formed_skip()
        bad["exit_code"] = "1"
        with self.assertRaises(schema.SchemaError) as ctx:
            schema.validate({"batch": {"skips": [_well_formed_skip(), bad]}})
        self.assertIn("batch.skips[1].exit_code", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
