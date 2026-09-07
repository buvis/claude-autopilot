#!/usr/bin/env python3
"""Tests for cli/schema.py: state shape/type/enum validation + version stamp.

schema.py is stdlib-only. It exposes:
  - SCHEMA_VERSION: int, the current schema stamp.
  - SchemaError: raised by validate(), naming the offending field.
  - validate(state: dict) -> None: whole-state shape/type/enum check of
    KNOWN fields only. Nothing is required; unknown top-level fields are
    tolerated. Raises on the FIRST offending known field.
  - version_status(state: dict) -> str: exhaustive classification of the
    state's "schema_version" key into one of "unstamped" | "current" |
    "old" | "future" | "invalid".

These tests bind only the public contract described in the task brief. No
implementation was read or referenced.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cli import render_report, schema

# Whatever autopilot state this machine happens to carry. Skipped when absent,
# so the suite is green on a machine that has never run a batch.
LIVE_STATE_JSON = Path.home() / ".claude/dev/local/autopilot/state.json"
# Derived from this file, not from an install path: the suite runs the same
# from the plugin cache, a checkout, or a worktree.
_SKILL_DIR = Path(__file__).resolve().parent.parent
GOLDEN_DIR = _SKILL_DIR / "scripts" / "golden"
CLI_GOLDEN_DIR = _SKILL_DIR / "cli" / "golden"
# The runnable CLI is the scripts/ shim: cli/statectl.py imports its siblings
# relatively and carries no __main__ guard, so only this path is a process.
STATECTL = _SKILL_DIR / "scripts" / "statectl.py"


def valid_state() -> dict:
    """A fresh, fully-populated dict where every documented field is valid.

    Fresh dict/list/nested-dict literals every call, so callers may mutate
    the result freely without cross-test contamination.
    """
    return {
        "phase": "build",
        "next_phase": "review",
        "catchup_mode": "run",
        "design_mode": "run",
        "doubt_reviewer": "codex",
        "consensus_engine": "legacy",
        "cycle": 1,
        "rework_cap": 3,
        "tasks_total": 5,
        "tasks_completed": 2,
        "tasks": [{"id": "1", "name": "do the thing", "status": "pending"}],
        "phases_completed": ["build"],
        "autonomous_decisions": [],
        "deferred_decisions": [],
        "review_cycles": [],
        "doubts": [],
        "batch": {"id": "202607290001", "mode": "autopilot"},
    }


class ValidateFullyPopulatedStateTest(unittest.TestCase):
    def test_fully_populated_valid_state_passes(self) -> None:
        self.assertIsNone(schema.validate(valid_state()))


class ValidateEmptyAndMissingFieldsTest(unittest.TestCase):
    def test_empty_dict_passes(self) -> None:
        self.assertIsNone(schema.validate({}))

    def test_state_missing_phase_passes(self) -> None:
        state = valid_state()
        del state["phase"]
        self.assertIsNone(schema.validate(state))

    def test_state_missing_next_phase_passes(self) -> None:
        state = valid_state()
        del state["next_phase"]
        self.assertIsNone(schema.validate(state))


class ValidateEnumFieldsTest(unittest.TestCase):
    """Each documented enum field, tested independently, out-of-set value."""

    def test_rejects_out_of_enum_phase(self) -> None:
        state = valid_state()
        state["phase"] = "blils"
        with self.assertRaises(schema.SchemaError) as ctx:
            schema.validate(state)
        msg = str(ctx.exception)
        self.assertIn("phase", msg)
        self.assertIn("blils", msg)

    def test_rejects_out_of_enum_next_phase(self) -> None:
        state = valid_state()
        state["next_phase"] = "nope"
        with self.assertRaises(schema.SchemaError) as ctx:
            schema.validate(state)
        msg = str(ctx.exception)
        self.assertIn("next_phase", msg)
        self.assertIn("nope", msg)

    def test_rejects_out_of_enum_catchup_mode(self) -> None:
        state = valid_state()
        state["catchup_mode"] = "maybe"
        with self.assertRaises(schema.SchemaError) as ctx:
            schema.validate(state)
        msg = str(ctx.exception)
        self.assertIn("catchup_mode", msg)
        self.assertIn("maybe", msg)

    def test_rejects_out_of_enum_design_mode(self) -> None:
        state = valid_state()
        state["design_mode"] = "maybe"
        with self.assertRaises(schema.SchemaError) as ctx:
            schema.validate(state)
        msg = str(ctx.exception)
        self.assertIn("design_mode", msg)
        self.assertIn("maybe", msg)

    def test_rejects_out_of_enum_doubt_reviewer(self) -> None:
        state = valid_state()
        state["doubt_reviewer"] = "gpt"
        with self.assertRaises(schema.SchemaError) as ctx:
            schema.validate(state)
        msg = str(ctx.exception)
        self.assertIn("doubt_reviewer", msg)
        self.assertIn("gpt", msg)

    def test_rejects_out_of_enum_consensus_engine(self) -> None:
        state = valid_state()
        state["consensus_engine"] = "hybrid"
        with self.assertRaises(schema.SchemaError) as ctx:
            schema.validate(state)
        msg = str(ctx.exception)
        self.assertIn("consensus_engine", msg)
        self.assertIn("hybrid", msg)


class ValidateLegacyPhaseToleranceTest(unittest.TestCase):
    """Regression guard: legacy phase values must never be rejected."""

    def test_tolerates_legacy_blind_phase(self) -> None:
        state = valid_state()
        state["phase"] = "blind"
        self.assertIsNone(schema.validate(state))

    def test_tolerates_legacy_doubt_phase(self) -> None:
        state = valid_state()
        state["phase"] = "doubt"
        self.assertIsNone(schema.validate(state))

    def test_next_phase_empty_string_passes(self) -> None:
        state = valid_state()
        state["next_phase"] = ""
        self.assertIsNone(schema.validate(state))


class ValidateIntFieldsTest(unittest.TestCase):
    """Each documented int field, tested independently, non-int value."""

    def test_rejects_non_int_cycle(self) -> None:
        state = valid_state()
        state["cycle"] = "3"
        with self.assertRaises(schema.SchemaError) as ctx:
            schema.validate(state)
        msg = str(ctx.exception)
        self.assertIn("cycle", msg)
        self.assertIn("3", msg)

    def test_rejects_non_int_rework_cap(self) -> None:
        state = valid_state()
        state["rework_cap"] = "3"
        with self.assertRaises(schema.SchemaError) as ctx:
            schema.validate(state)
        msg = str(ctx.exception)
        self.assertIn("rework_cap", msg)
        self.assertIn("3", msg)

    def test_rejects_non_int_tasks_total(self) -> None:
        state = valid_state()
        state["tasks_total"] = "5"
        with self.assertRaises(schema.SchemaError) as ctx:
            schema.validate(state)
        msg = str(ctx.exception)
        self.assertIn("tasks_total", msg)
        self.assertIn("5", msg)

    def test_rejects_non_int_tasks_completed(self) -> None:
        state = valid_state()
        state["tasks_completed"] = "2"
        with self.assertRaises(schema.SchemaError) as ctx:
            schema.validate(state)
        msg = str(ctx.exception)
        self.assertIn("tasks_completed", msg)
        self.assertIn("2", msg)

    def test_rejects_bool_for_cycle(self) -> None:
        # ASSUMPTION (see report): bool is a subclass of int in Python, but
        # this validator treats bool as NOT a valid int value. A True/False
        # slipping into an int-typed field is always a bug, never a
        # legitimate value, so it is rejected rather than silently coerced.
        state = valid_state()
        state["cycle"] = True
        with self.assertRaises(schema.SchemaError) as ctx:
            schema.validate(state)
        self.assertIn("cycle", str(ctx.exception))


class ValidateListFieldsTest(unittest.TestCase):
    """Each documented list field, tested independently, non-list value."""

    def test_rejects_non_list_tasks(self) -> None:
        state = valid_state()
        state["tasks"] = {"id": "1"}
        with self.assertRaises(schema.SchemaError) as ctx:
            schema.validate(state)
        self.assertIn("tasks", str(ctx.exception))

    def test_rejects_non_list_phases_completed(self) -> None:
        state = valid_state()
        state["phases_completed"] = {"build": True}
        with self.assertRaises(schema.SchemaError) as ctx:
            schema.validate(state)
        self.assertIn("phases_completed", str(ctx.exception))

    def test_rejects_non_list_autonomous_decisions(self) -> None:
        state = valid_state()
        state["autonomous_decisions"] = {"a": 1}
        with self.assertRaises(schema.SchemaError) as ctx:
            schema.validate(state)
        self.assertIn("autonomous_decisions", str(ctx.exception))

    def test_rejects_non_list_deferred_decisions(self) -> None:
        state = valid_state()
        state["deferred_decisions"] = {"a": 1}
        with self.assertRaises(schema.SchemaError) as ctx:
            schema.validate(state)
        self.assertIn("deferred_decisions", str(ctx.exception))

    def test_rejects_non_list_review_cycles(self) -> None:
        state = valid_state()
        state["review_cycles"] = {"a": 1}
        with self.assertRaises(schema.SchemaError) as ctx:
            schema.validate(state)
        self.assertIn("review_cycles", str(ctx.exception))

    def test_rejects_non_list_doubts(self) -> None:
        state = valid_state()
        state["doubts"] = {"a": 1}
        with self.assertRaises(schema.SchemaError) as ctx:
            schema.validate(state)
        self.assertIn("doubts", str(ctx.exception))


class ValidateBatchFieldTest(unittest.TestCase):
    def test_rejects_non_dict_batch(self) -> None:
        state = valid_state()
        state["batch"] = "202607290001"
        with self.assertRaises(schema.SchemaError) as ctx:
            schema.validate(state)
        self.assertIn("batch", str(ctx.exception))

    def test_rejects_batch_id_wrong_type(self) -> None:
        state = valid_state()
        state["batch"] = {"id": 123}
        with self.assertRaises(schema.SchemaError) as ctx:
            schema.validate(state)
        msg = str(ctx.exception)
        self.assertIn("batch", msg)
        self.assertIn("123", msg)

    def test_empty_batch_dict_passes(self) -> None:
        state = valid_state()
        state["batch"] = {}
        self.assertIsNone(schema.validate(state))


COMPLETED_PRD_ELEMENT_FIELD_REJECT_CASES = (
    ("filename", 123, "str"),
    ("cycles", "two", "int"),
    ("autonomous_decisions", "two", "int"),
    ("escalated_decisions", "two", "int"),
    ("tasks_completed", "two", "int"),
    ("tasks_total", "two", "int"),
)


def _well_formed_completed_prd_entry() -> dict:
    return {
        "filename": "00001-x.md",
        "cycles": 1,
        "autonomous_decisions": 0,
        "escalated_decisions": 0,
        "tasks_completed": 1,
        "tasks_total": 1,
    }


class ValidateBatchCompletedPrdsElementShapeTest(unittest.TestCase):
    """Per-element shape of `batch.completed_prds`: legacy bare strings are
    tolerated, dict entries are checked field-by-field (present-if-typed,
    absent-if-optional), and anything else is rejected outright."""

    def test_bare_string_entry_passes_legacy_tolerance(self) -> None:
        state = valid_state()
        state["batch"] = {"completed_prds": ["00001-x.md"]}
        self.assertIsNone(schema.validate(state))

    def test_well_formed_dict_entry_passes(self) -> None:
        state = valid_state()
        state["batch"] = {"completed_prds": [_well_formed_completed_prd_entry()]}
        self.assertIsNone(schema.validate(state))

    def test_dict_entry_missing_all_optional_fields_passes(self) -> None:
        state = valid_state()
        state["batch"] = {"completed_prds": [{}]}
        self.assertIsNone(schema.validate(state))

    def test_dict_entry_with_only_some_fields_present_passes(self) -> None:
        state = valid_state()
        state["batch"] = {"completed_prds": [{"filename": "00003-c.md"}]}
        self.assertIsNone(schema.validate(state))

    def test_rejects_wrong_typed_field_naming_the_element_path(self) -> None:
        for field, bad_value, type_name in COMPLETED_PRD_ELEMENT_FIELD_REJECT_CASES:
            with self.subTest(field=field):
                state = valid_state()
                entry = _well_formed_completed_prd_entry()
                entry[field] = bad_value
                state["batch"] = {"completed_prds": [entry]}
                with self.assertRaises(schema.SchemaError) as ctx:
                    schema.validate(state)
                msg = str(ctx.exception)
                self.assertIn(f"batch.completed_prds[0].{field}", msg)
                self.assertIn(f"expected {type_name}", msg)

    def test_bad_cycles_value_message_names_exact_field_path(self) -> None:
        state = valid_state()
        state["batch"] = {"completed_prds": [{"cycles": "two"}]}
        with self.assertRaises(schema.SchemaError) as ctx:
            schema.validate(state)
        self.assertIn(
            "batch.completed_prds[0].cycles: expected int, got 'two'",
            str(ctx.exception),
        )

    def test_bad_field_on_second_element_names_index_one(self) -> None:
        state = valid_state()
        state["batch"] = {
            "completed_prds": [
                _well_formed_completed_prd_entry(),
                {"filename": "00002-y.md", "cycles": "two"},
            ],
        }
        with self.assertRaises(schema.SchemaError) as ctx:
            schema.validate(state)
        self.assertIn("batch.completed_prds[1].cycles", str(ctx.exception))

    def test_rejects_non_str_non_dict_element(self) -> None:
        for bad in (42, ["nested"], None):
            with self.subTest(value=bad):
                state = valid_state()
                state["batch"] = {"completed_prds": [bad]}
                with self.assertRaises(schema.SchemaError) as ctx:
                    schema.validate(state)
                self.assertIn("completed_prds", str(ctx.exception))


class RenderBatchSummaryCompletedPrdsSumsTest(unittest.TestCase):
    """PRD Phase 1 acceptance: a batch that completes two PRDs renders
    non-zero cycle and decision sums through render_report.batch_summary."""

    def test_two_completed_prds_render_matching_nonzero_sums(self) -> None:
        state = valid_state()
        state["batch"] = {
            "id": "202607290001",
            "completed_prds": [
                {
                    "filename": "00001-a.md",
                    "cycles": 3,
                    "autonomous_decisions": 2,
                    "escalated_decisions": 1,
                    "tasks_completed": 5,
                    "tasks_total": 5,
                },
                {
                    "filename": "00002-b.md",
                    "cycles": 4,
                    "autonomous_decisions": 3,
                    "escalated_decisions": 2,
                    "tasks_completed": 6,
                    "tasks_total": 6,
                },
            ],
        }
        self.assertIsNone(schema.validate(state))
        report = render_report.batch_summary(state, [])
        self.assertIn("Total cycles: 7", report)
        self.assertIn("Autonomous decisions: 5", report)
        self.assertIn("Escalated decisions: 3", report)


class ValidateUnknownFieldsToleratedTest(unittest.TestCase):
    def test_tolerates_unknown_top_level_string_field(self) -> None:
        state = valid_state()
        state["contract_card"] = "anything"
        self.assertIsNone(schema.validate(state))

    def test_tolerates_unknown_top_level_bool_field(self) -> None:
        state = valid_state()
        state["needs_attention"] = False
        self.assertIsNone(schema.validate(state))

    def test_tolerates_multiple_unknown_top_level_fields_together(self) -> None:
        state = valid_state()
        state["contract_card"] = "anything"
        state["needs_attention"] = False
        state["some_future_field"] = {"nested": [1, 2, 3]}
        self.assertIsNone(schema.validate(state))


class ValidateFirstOffendingFieldTest(unittest.TestCase):
    def test_reports_exactly_one_field_when_several_are_wrong(self) -> None:
        # Three independently-invalid known fields, chosen so none of their
        # names is a substring of another (unlike e.g. "phase" / "next_phase").
        state = {
            "cycle": "not-an-int",
            "rework_cap": "also-not-an-int",
            "doubt_reviewer": "gpt",
        }
        with self.assertRaises(schema.SchemaError) as ctx:
            schema.validate(state)
        msg = str(ctx.exception)
        self.assertTrue(msg, "SchemaError must carry a non-empty message")
        named = [f for f in ("cycle", "rework_cap", "doubt_reviewer") if f in msg]
        self.assertEqual(
            len(named),
            1,
            f"expected exactly one offending field named (the first), got {named} in: {msg!r}",
        )


class SchemaVersionConstantTest(unittest.TestCase):
    def test_schema_version_is_int(self) -> None:
        self.assertIsInstance(schema.SCHEMA_VERSION, int)

    def test_schema_version_equals_documented_value(self) -> None:
        self.assertEqual(schema.SCHEMA_VERSION, 1)


class VersionStatusTest(unittest.TestCase):
    def test_unstamped_when_key_absent(self) -> None:
        self.assertEqual(schema.version_status({}), "unstamped")

    def test_unstamped_ignores_other_fields(self) -> None:
        self.assertEqual(schema.version_status({"phase": "build"}), "unstamped")

    def test_current_when_equal_to_schema_version(self) -> None:
        self.assertEqual(
            schema.version_status({"schema_version": schema.SCHEMA_VERSION}),
            "current",
        )

    def test_old_when_zero(self) -> None:
        # At SCHEMA_VERSION == 1, 0 is the ONLY reachable 'old' value. This
        # is the branch that was previously unreachable / mis-specified.
        self.assertEqual(schema.version_status({"schema_version": 0}), "old")

    def test_future_when_greater_than_schema_version(self) -> None:
        self.assertEqual(schema.version_status({"schema_version": 2}), "future")

    def test_invalid_for_string(self) -> None:
        self.assertEqual(schema.version_status({"schema_version": "1"}), "invalid")

    def test_invalid_for_float(self) -> None:
        self.assertEqual(schema.version_status({"schema_version": 1.0}), "invalid")

    def test_invalid_for_none(self) -> None:
        self.assertEqual(schema.version_status({"schema_version": None}), "invalid")

    def test_invalid_for_negative_int(self) -> None:
        self.assertEqual(schema.version_status({"schema_version": -1}), "invalid")

    def test_invalid_for_bool_true(self) -> None:
        # Pinned explicitly by the contract's invalid-family list (bool is
        # named alongside str/float/None/negative), unlike the ambiguous
        # int-field bool question in validate().
        self.assertEqual(schema.version_status({"schema_version": True}), "invalid")

    def test_invalid_for_bool_false(self) -> None:
        self.assertEqual(schema.version_status({"schema_version": False}), "invalid")


class ValidateHostileInputTest(unittest.TestCase):
    """Regressions found by the task-2 per-task review, 2026-07-29.

    All three shipped in the first implementation and all three break the
    boundary contract that `transaction()` depends on: it promises its callers
    either a committed write or a raised `SchemaError`, and callers branch on
    documented exit codes derived from exactly that. Any other exception
    escaping, or any silent acceptance, breaks it.
    """

    def test_rejects_unhashable_value_in_enum_field(self) -> None:
        # `state[field] not in allowed` against a set raises TypeError for an
        # unhashable value. Reachable: `statectl set phase '[]'` writes it,
        # since statectl has no validation -- the gap this module closes.
        for bad in ([], {}):
            with self.subTest(value=bad):
                with self.assertRaises(schema.SchemaError) as ctx:
                    schema.validate({"phase": bad})
                self.assertIn("phase", str(ctx.exception))

    def test_rejects_non_dict_state_root(self) -> None:
        # The severe one: a root that is a list or str silently returned None,
        # i.e. a FULL validation bypass -- `transaction()` would then commit a
        # corrupt root through the very boundary meant to prevent it.
        for bad in ([], "x", None, 42):
            with self.subTest(root=bad):
                with self.assertRaises(schema.SchemaError) as ctx:
                    schema.validate(bad)
                self.assertIn("state", str(ctx.exception))

    def test_version_status_classifies_non_dict_state_as_invalid(self) -> None:
        # `version_status(None)` leaked TypeError; `version_status([])`
        # answered "unstamped", which a caller would treat as a healthy
        # legacy state and stamp as current.
        for bad in (None, [], "x", 42):
            with self.subTest(root=bad):
                self.assertEqual(schema.version_status(bad), "invalid")


class LiveStateFixtureTest(unittest.TestCase):
    """The live autopilot state file must always validate clean."""

    def test_live_autopilot_state_validates_clean(self) -> None:
        if not LIVE_STATE_JSON.exists():
            self.skipTest(f"live state fixture not found: {LIVE_STATE_JSON}")
        state = json.loads(LIVE_STATE_JSON.read_text(encoding="utf-8"))
        try:
            schema.validate(state)
        except schema.SchemaError as exc:
            self.fail(f"{LIVE_STATE_JSON}: {exc}")


class GoldenFixturesTest(unittest.TestCase):
    """Every golden state-*.json fixture must always validate clean.

    Both golden directories are covered. `cli/golden/` was previously missed,
    so `state-render.json`, `state-batch-202608162223.json`, and
    `state-batch-202608162223-reconstructed.json` validated only by luck; a
    fixture that stopped validating would have gone unnoticed.
    """

    def test_all_golden_state_fixtures_validate_clean(self) -> None:
        golden_files = []
        for directory in (GOLDEN_DIR, CLI_GOLDEN_DIR):
            if not directory.exists():
                self.fail(f"golden fixtures dir is tracked but missing: {directory}")
            found = sorted(directory.glob("state-*.json"))
            self.assertTrue(found, f"no golden fixtures found under {directory}")
            golden_files += found
        for path in golden_files:
            with self.subTest(fixture=path.name):
                state = json.loads(path.read_text(encoding="utf-8"))
                try:
                    schema.validate(state)
                except schema.SchemaError as exc:
                    self.fail(f"{path}: {exc}")


WIDENED_SCALAR_REJECT_CASES = (
    ("prd", lambda s: s.__setitem__("prd", 123), "prd"),
    (
        "work_start_sha",
        lambda s: s.__setitem__("work_start_sha", 123),
        "work_start_sha",
    ),
    ("repo_root", lambda s: s.__setitem__("repo_root", 123), "repo_root"),
    ("design_doc", lambda s: s.__setitem__("design_doc", 123), "design_doc"),
    (
        "replan_count_non_int",
        lambda s: s.__setitem__("replan_count", "3"),
        "replan_count",
    ),
    (
        "replan_count_bool",
        lambda s: s.__setitem__("replan_count", True),
        "replan_count",
    ),
    (
        "batch_parks_consecutive_non_int",
        lambda s: s["batch"].__setitem__("parks_consecutive", "3"),
        "batch.parks_consecutive",
    ),
    (
        "batch_parks_consecutive_bool",
        lambda s: s["batch"].__setitem__("parks_consecutive", True),
        "batch.parks_consecutive",
    ),
    (
        "batch_completed_prds_non_list",
        lambda s: s["batch"].__setitem__("completed_prds", "not-a-list"),
        "batch.completed_prds",
    ),
)

WIDENED_SCALAR_ACCEPT_CASES = (
    ("prd", lambda s: s.__setitem__("prd", "00004-feature-x.md")),
    ("work_start_sha", lambda s: s.__setitem__("work_start_sha", "3f2c1a9")),
    (
        "repo_root",
        lambda s: s.__setitem__(
            "repo_root",
            "/Users/dev/git/src/github.com/buvis/run-autopilot",
        ),
    ),
    (
        "design_doc",
        lambda s: s.__setitem__(
            "design_doc",
            "dev/local/prds/wip/00004-feature-x/design.md",
        ),
    ),
    ("replan_count", lambda s: s.__setitem__("replan_count", 0)),
    (
        "batch_parks_consecutive",
        lambda s: s["batch"].__setitem__("parks_consecutive", 0),
    ),
    (
        "batch_completed_prds",
        lambda s: s["batch"].__setitem__("completed_prds", ["00001-x.md"]),
    ),
)


class ValidateWidenedScalarFieldsTest(unittest.TestCase):
    """The scalar fields this task adds: prd/work_start_sha/repo_root/design_doc
    (str), replan_count and batch.parks_consecutive (int, bool rejected),
    batch.completed_prds (list). Each is optional -- only checked if present."""

    def test_rejects_malformed_widened_scalar_fields_naming_the_offending_field(
        self,
    ) -> None:
        for label, mutate, expected_name in WIDENED_SCALAR_REJECT_CASES:
            with self.subTest(label=label):
                state = valid_state()
                mutate(state)
                with self.assertRaises(schema.SchemaError) as ctx:
                    schema.validate(state)
                self.assertIn(expected_name, str(ctx.exception))

    def test_well_formed_widened_scalar_fields_pass(self) -> None:
        for label, mutate in WIDENED_SCALAR_ACCEPT_CASES:
            with self.subTest(label=label):
                state = valid_state()
                mutate(state)
                self.assertIsNone(schema.validate(state))


class SchemaErrorReprBoundedTest(unittest.TestCase):
    def test_error_message_for_giant_field_value_is_bounded_not_interpolated_in_full(
        self,
    ) -> None:
        # A MALFORMED giant value (str where int is required): the rejection
        # message must truncate the value, never interpolate all 100K chars.
        # (A giant-but-valid str field passes validation and raises nothing —
        # the widened `prd: str` rule has no length limit.)
        with self.assertRaises(schema.SchemaError) as ctx:
            schema.validate({"replan_count": "x" * 100_000})
        self.assertLess(len(str(ctx.exception)), 500)
        self.assertIsNone(schema.validate({"prd": "x" * 100_000}))


class ChangedFieldsTest(unittest.TestCase):
    """The scoping primitive behind statectl's shim and `phase-done`: what did
    this write actually touch?"""

    def test_edited_field_is_changed(self) -> None:
        self.assertEqual(
            schema.changed_fields({"phase": "build"}, {"phase": "review"}),
            {"phase"},
        )

    def test_added_field_is_changed(self) -> None:
        self.assertEqual(schema.changed_fields({}, {"cycle": 1}), {"cycle"})

    def test_removed_field_is_changed(self) -> None:
        # `del` is a mutation like any other; a removal that leaves the state
        # invalid must not slip past because the key is gone.
        self.assertEqual(schema.changed_fields({"cycle": 1}, {}), {"cycle"})

    def test_untouched_fields_are_not_changed(self) -> None:
        before = {"phase": "build", "batch": {"id": "b1"}, "tasks": [{"id": "1"}]}
        self.assertEqual(schema.changed_fields(before, dict(before)), set())

    def test_nested_edit_reports_its_top_level_owner(self) -> None:
        self.assertEqual(
            schema.changed_fields({"batch": {"id": "b1"}}, {"batch": {"id": "b2"}}),
            {"batch"},
        )

    def test_a_value_reassigned_to_an_equal_copy_is_not_a_change(self) -> None:
        # Equality, not identity: statectl rebuilds nested containers, and a
        # rebuilt-but-identical list is not a write worth validating.
        self.assertEqual(
            schema.changed_fields({"tasks": [{"id": "1"}]}, {"tasks": [{"id": "1"}]}),
            set(),
        )


class ValidateChangedTest(unittest.TestCase):
    def test_malformed_value_for_the_targeted_field_is_rejected(self) -> None:
        with self.assertRaises(schema.SchemaError) as ctx:
            schema.validate_changed({"phase": "build"}, {"phase": "nonsense"})
        self.assertIn("phase", str(ctx.exception))

    def test_untouched_pre_existing_odd_field_blocks_nothing(self) -> None:
        # A forensic hand-edit left `cycle` malformed. Every later write to an
        # unrelated field must still land, or one bad field wedges the loop.
        before = {"cycle": "not-an-int", "phase": "build"}
        after = {"cycle": "not-an-int", "phase": "review"}
        self.assertIsNone(schema.validate_changed(before, after))

    def test_valid_change_beside_an_odd_field_still_passes(self) -> None:
        before = {"weird": object.__class__.__name__, "next_phase": "build"}
        after = {**before, "next_phase": "review"}
        self.assertIsNone(schema.validate_changed(before, after))

    def test_touching_the_odd_field_itself_is_rejected(self) -> None:
        with self.assertRaises(schema.SchemaError):
            schema.validate_changed(
                {"cycle": "not-an-int"},
                {"cycle": "still-not-an-int-but-different"},
            )

    def test_removing_a_field_is_allowed(self) -> None:
        # statectl's `del` verb removes fields outright and must keep working:
        # every schema rule is "if present, must match", never "must exist".
        self.assertIsNone(schema.validate_changed({"phase": "build"}, {}))

    def test_no_change_validates_nothing(self) -> None:
        state = {"cycle": "not-an-int"}
        self.assertIsNone(schema.validate_changed(state, dict(state)))


# --- autonomous_decisions entries, judged at the append boundary -----------
#
# The batch report draws one row per entry, so an entry it cannot render must
# be refused at the moment it is appended, naming the key it lacks, instead of
# surfacing as a blank row at batch end. Only entries a write ADDS are judged:
# entries already sitting in the state are never re-checked, so a batch
# resumed from an older state still loads.


def _valid_decision() -> dict:
    """The smallest appended entry that satisfies every rule of the contract."""
    return {
        "cycle": 1,
        "issue": "the reviewers split on the retry cap",
        "severity": "high",
        "action": "kept the documented 3-retry default",
        "reason": "no reviewer produced a counter-example",
    }


def _alternative_decision() -> dict:
    """The smallest appended entry written in the alternative vocabulary.

    `question`, `disposition` and `resolution` stand in for `issue`, `action`
    and `reason`. Its `type` is not "assumed-ambiguity", so this is an
    ORDINARY decision and every ordinary rule still applies to it.
    """
    return {
        "cycle": 4,
        "question": "should a parked PRD keep its severity?",
        "severity": "medium",
        "disposition": "left the recorded severity alone",
        "resolution": "no reviewer proposed a different one",
    }


def _appended(entry: object) -> tuple[dict, dict]:
    """(before, after) for a write whose only change is appending `entry`."""
    before = valid_state()
    after = valid_state()
    after["autonomous_decisions"] = [entry]
    return before, after


def _appended_batch(count: int, malformed_at: int) -> tuple[dict, dict]:
    """(before, after) for a write appending `count` entries in one go.

    Every entry is well-formed and distinguishable from its neighbours except
    the one at `malformed_at`, which lacks its `issue`.
    """
    entries = []
    for index in range(count):
        entry = _valid_decision()
        entry["cycle"] = index + 1
        if index == malformed_at:
            del entry["issue"]
        entries.append(entry)
    before = valid_state()
    after = valid_state()
    after["autonomous_decisions"] = entries
    return before, after


def _stub_entries() -> list:
    """Entries an older batch already wrote, none of which meets the contract."""
    return [{"cycle": 1}, {}, {"issue": "", "severity": "urgent"}]


# Severity values that must be refused. Each is proven absent from
# `DECISION_SEVERITIES` before it is used, so the published set has to be what
# does the rejecting: a validator carrying its own list of strings it has seen
# operators mistype fails here on the one that list forgot.
UNPUBLISHED_SEVERITIES = ("urgent", "blocker", "sev0", "banana", "HIGH", "")

# `severity` is an enum of strings, so nothing that is not a string can be in
# it. None is what an absent key reads as, and True is truthy without being a
# severity, so a truthiness check is not enough.
NON_STRING_SEVERITIES = (42, None, True, 3.5)

# The shapes a JSON payload puts in `cycle` when it is not an int: a
# shell-quoted number, an absent key, a float, a malformed list, and True --
# which this module documents as NOT a valid int, so a plain
# isinstance(value, int) check would wrongly accept it.
NON_INT_CYCLES = ("1", None, 3.7, [], True)

# `issue`, `action` and `reason` carry the prose the report prints in the row.
# A number or a list is not text, and True is truthy without being text.
NON_STRING_PROSE = (99, ["nested"], True)

# The one message shape the contract publishes for a refused entry. A non-dict
# entry lacks every key at once, so which key it names is the validator's
# choice -- but it still has to speak this shape and name one.
MISSING_KEY_MESSAGE = r"^autonomous_decisions entry missing \S+$"

# Prose no other test hardcodes. The rule is "one non-empty string", nothing
# narrower, so a terse phrase, a punctuation-heavy one and a long one all
# render the same row. A validator that only recognises the wordings this suite
# happens to use would refuse every real decision the loop writes.
ACCEPTED_PROSE = (
    "kept it",
    "the panel disagreed about the timeout",
    "cap: 3 -> 5 (see PRD 00073); nobody objected -- so it stands",
    "the reviewers wrote it out at length. " * 20,
)

# `cycle` is an int, with no documented floor, ceiling, or roster of known
# cycles. A batch that reworks seventeen times still renders its rows, and a
# decision recorded before the first review cycle is still a decision.
ACCEPTED_CYCLES = (0, 4, 17, 10_000_000)

# The alternative name each prose pair accepts, mapped to the name the refusal
# message must speak. The contract publishes both vocabularies, so both have to
# be judged -- but only the first key of the pair is ever named back.
ALTERNATIVE_PROSE_KEYS = {
    "question": "issue",
    "disposition": "action",
    "resolution": "reason",
}

# A pool wide enough to pin the severity gate to the published set from BOTH
# sides. The roster of refused values above kills a private blocklist; only
# asking which members of a pool survive kills a private allowlist that is a
# superset of DECISION_SEVERITIES. So the pool holds the five published values,
# case and whitespace variants of them, synonyms an operator might reach for,
# and strings nobody would.
SEVERITY_CANDIDATES = (
    "critical",
    "high",
    "medium",
    "low",
    "n/a",
    "Critical",
    "HIGH",
    "Medium",
    " low",
    "n/a ",
    "N/A",
    "trivial",
    "info",
    "nit",
    "sev1",
    "sev0",
    "blocker",
    "urgent",
    "minor",
    "major",
    "none",
    "na",
    "",
    "   ",
    "banana",
    "severity",
)


class DecisionSeveritiesConstantTest(unittest.TestCase):
    """`DECISION_SEVERITIES` is the accepted severity set, published so callers
    and tests read it instead of restating the five strings."""

    def test_severity_set_holds_exactly_the_five_documented_values(self) -> None:
        self.assertEqual(
            set(schema.DECISION_SEVERITIES),
            {"critical", "high", "medium", "low", "n/a"},
        )

    def test_every_published_severity_is_accepted_on_an_appended_entry(self) -> None:
        for severity in schema.DECISION_SEVERITIES:
            with self.subTest(severity=severity):
                entry = _valid_decision()
                entry["severity"] = severity
                self.assertIsNone(schema.validate_changed(*_appended(entry)))

    def test_the_accepted_severities_are_exactly_the_published_set(self) -> None:
        # The roster of refused values elsewhere proves each named value is
        # rejected; it cannot prove nothing ELSE slips through. Here the whole
        # candidate pool is offered and the accepted subset must equal the
        # constant, so a validator carrying a private allowlist wider than
        # DECISION_SEVERITIES -- one that also waves through "trivial" -- fails.
        accepted = set()
        for candidate in SEVERITY_CANDIDATES:
            entry = _valid_decision()
            entry["severity"] = candidate
            try:
                schema.validate_changed(*_appended(entry))
            except schema.SchemaError:
                continue
            accepted.add(candidate)
        self.assertEqual(accepted, set(schema.DECISION_SEVERITIES))


class AppendedDecisionRequiredKeysTest(unittest.TestCase):
    """Each rule the report needs to render a row, enforced on append."""

    def test_appended_decision_missing_issue_is_rejected(self) -> None:
        entry = _valid_decision()
        del entry["issue"]
        with self.assertRaises(schema.SchemaError) as ctx:
            schema.validate_changed(*_appended(entry))
        self.assertEqual(
            str(ctx.exception),
            "autonomous_decisions entry missing issue",
        )

    def test_bare_entry_names_issue_before_the_other_missing_keys(self) -> None:
        # The CLI acceptance case: appending `{"cycle": 1}` lacks issue,
        # severity, action AND reason, and must name `issue` -- the first
        # rule, not whichever check the implementation happens to run first.
        with self.assertRaises(schema.SchemaError) as ctx:
            schema.validate_changed(*_appended({"cycle": 1}))
        self.assertEqual(
            str(ctx.exception),
            "autonomous_decisions entry missing issue",
        )

    def test_empty_issue_string_counts_as_missing(self) -> None:
        # A present-but-blank key renders the same blank row as an absent one.
        entry = _valid_decision()
        entry["issue"] = ""
        with self.assertRaises(schema.SchemaError) as ctx:
            schema.validate_changed(*_appended(entry))
        self.assertEqual(
            str(ctx.exception),
            "autonomous_decisions entry missing issue",
        )

    def test_missing_action_and_disposition_is_rejected_naming_action(self) -> None:
        entry = _valid_decision()
        del entry["action"]
        with self.assertRaises(schema.SchemaError) as ctx:
            schema.validate_changed(*_appended(entry))
        self.assertEqual(
            str(ctx.exception),
            "autonomous_decisions entry missing action",
        )

    def test_missing_reason_and_resolution_is_rejected_naming_reason(self) -> None:
        entry = _valid_decision()
        del entry["reason"]
        with self.assertRaises(schema.SchemaError) as ctx:
            schema.validate_changed(*_appended(entry))
        self.assertEqual(
            str(ctx.exception),
            "autonomous_decisions entry missing reason",
        )

    def test_missing_cycle_is_rejected(self) -> None:
        entry = _valid_decision()
        del entry["cycle"]
        with self.assertRaises(schema.SchemaError) as ctx:
            schema.validate_changed(*_appended(entry))
        self.assertEqual(
            str(ctx.exception),
            "autonomous_decisions entry missing cycle",
        )

    def test_non_int_cycle_is_rejected(self) -> None:
        # The report groups rows by cycle number, so anything that is not an
        # int leaves the row unplaceable. True is in the table on purpose:
        # bools are ints to Python, and this module documents the carve-out
        # that says they are still not valid int values.
        for bad in NON_INT_CYCLES:
            with self.subTest(cycle=bad):
                entry = _valid_decision()
                entry["cycle"] = bad
                with self.assertRaises(schema.SchemaError) as ctx:
                    schema.validate_changed(*_appended(entry))
                self.assertEqual(
                    str(ctx.exception),
                    "autonomous_decisions entry missing cycle",
                )

    def test_severity_outside_the_published_set_is_rejected(self) -> None:
        # Driven from the constant, not from one hand-picked typo: every value
        # is asserted absent from DECISION_SEVERITIES first, so only the
        # published set can be what refuses it.
        for bad in UNPUBLISHED_SEVERITIES:
            with self.subTest(severity=bad):
                self.assertNotIn(bad, schema.DECISION_SEVERITIES)
                entry = _valid_decision()
                entry["severity"] = bad
                with self.assertRaises(schema.SchemaError) as ctx:
                    schema.validate_changed(*_appended(entry))
                self.assertEqual(
                    str(ctx.exception),
                    "autonomous_decisions entry missing severity",
                )

    def test_missing_severity_is_rejected(self) -> None:
        # The report prints a severity per row; an absent one draws the blank
        # cell this whole rule exists to prevent.
        entry = _valid_decision()
        del entry["severity"]
        with self.assertRaises(schema.SchemaError) as ctx:
            schema.validate_changed(*_appended(entry))
        self.assertEqual(
            str(ctx.exception),
            "autonomous_decisions entry missing severity",
        )

    def test_non_string_severity_is_rejected(self) -> None:
        for bad in NON_STRING_SEVERITIES:
            with self.subTest(severity=bad):
                self.assertNotIn(bad, schema.DECISION_SEVERITIES)
                entry = _valid_decision()
                entry["severity"] = bad
                with self.assertRaises(schema.SchemaError) as ctx:
                    schema.validate_changed(*_appended(entry))
                self.assertEqual(
                    str(ctx.exception),
                    "autonomous_decisions entry missing severity",
                )

    def test_non_string_value_for_a_prose_key_is_rejected_naming_that_key(
        self,
    ) -> None:
        # Each pair wants one non-empty STRING. A number satisfies "is set"
        # but is not the prose the row prints, so it fails the same way an
        # absent key does, naming the same key.
        for key in ("issue", "action", "reason"):
            for bad in NON_STRING_PROSE:
                with self.subTest(key=key, value=bad):
                    entry = _valid_decision()
                    entry[key] = bad
                    with self.assertRaises(schema.SchemaError) as ctx:
                        schema.validate_changed(*_appended(entry))
                    self.assertEqual(
                        str(ctx.exception),
                        f"autonomous_decisions entry missing {key}",
                    )

    def test_entry_that_is_not_a_dict_is_rejected(self) -> None:
        # `statectl append` takes raw JSON, so a bare string or list reaches
        # this boundary and would otherwise render as an unreadable row. The
        # refusal still speaks the one published message shape and names a key
        # the entry lacks -- a non-dict lacks all of them, so which key it
        # names is the validator's call.
        for bad in ("just a string", ["nested"], None, 42):
            with self.subTest(entry=bad):
                with self.assertRaises(schema.SchemaError) as ctx:
                    schema.validate_changed(*_appended(bad))
                self.assertRegex(str(ctx.exception), MISSING_KEY_MESSAGE)


class AppendedDecisionAcceptedShapesTest(unittest.TestCase):
    """The vocabularies and extras an entry is allowed to carry."""

    def test_appended_decision_with_disposition_is_accepted(self) -> None:
        entry = {
            "cycle": 2,
            "question": "should a parked PRD keep its number?",
            "severity": "low",
            "disposition": "kept the number",
            "resolution": "renumbering breaks the satellite paths",
        }
        self.assertIsNone(schema.validate_changed(*_appended(entry)))

    def test_alternative_keys_may_be_mixed_across_pairs(self) -> None:
        # Each pair is judged on its own; an entry is not required to speak
        # one vocabulary throughout.
        entry = {
            "cycle": 3,
            "question": "is the 500K cap still right?",
            "severity": "medium",
            "action": "left the cap alone",
            "resolution": "the 1M window it is coupled to has not changed",
        }
        self.assertIsNone(schema.validate_changed(*_appended(entry)))

    def test_extra_keys_do_not_invalidate_an_entry(self) -> None:
        entry = _valid_decision()
        entry["file"] = "cli/schema.py"
        entry["consensus"] = "2 of 3 reviewers agreed"
        entry["research"] = "checked the PRD and the design doc"
        # A `type` other than "assumed-ambiguity" is just another extra key:
        # only that exact value switches the entry to the second rule.
        entry["type"] = "autonomous"
        # And so is `assumption`, for the same reason: an ordinary decision
        # that happens to record what it assumed is still judged by the
        # ordinary rules, and must not be let off cycle/severity/action/reason
        # just because it carries the key the other rule names.
        entry["assumption"] = "assumed the retry cap was deliberate"
        self.assertIsNone(schema.validate_changed(*_appended(entry)))

    def test_prose_the_validator_has_never_seen_is_accepted(self) -> None:
        # The rule is "one non-empty string", so acceptance cannot depend on
        # WHICH string. Each prose key is fed wordings that appear nowhere
        # else in this suite: a validator recognising only a roster of known
        # phrasings passes every rejection test above and still refuses every
        # real decision the loop writes.
        for key in ("issue", "action", "reason"):
            for text in ACCEPTED_PROSE:
                with self.subTest(key=key, value=text[:20]):
                    entry = _valid_decision()
                    entry[key] = text
                    self.assertIsNone(schema.validate_changed(*_appended(entry)))

    def test_a_one_character_issue_is_accepted(self) -> None:
        # "Blank" means the empty string and nothing wider. A minimum length
        # would refuse a terse-but-present value, which renders a perfectly
        # readable row.
        entry = _valid_decision()
        entry["issue"] = "x"
        self.assertIsNone(schema.validate_changed(*_appended(entry)))

    def test_cycles_beyond_the_first_few_are_accepted(self) -> None:
        # `cycle` is an int, full stop. Pinning acceptance to the cycle
        # numbers a short batch happens to reach would reject the fourth
        # rework cycle the moment a real batch got there.
        for cycle in ACCEPTED_CYCLES:
            with self.subTest(cycle=cycle):
                entry = _valid_decision()
                entry["cycle"] = cycle
                self.assertIsNone(schema.validate_changed(*_appended(entry)))


class AlternativeVocabularyEntryTest(unittest.TestCase):
    """An entry written in the alternative vocabulary is judged by the SAME
    ordinary rules, and the refusal still names the first key of the pair.

    Accepting these entries is only half the contract. Without the refusals
    below, a validator that waves through anything carrying a `question` key
    passes every other test here, and `{"question": ""}` alone becomes a
    decision the report has to draw a blank row for.
    """

    def test_blank_alternative_prose_is_rejected_naming_the_primary_key(self) -> None:
        for alternative, primary in ALTERNATIVE_PROSE_KEYS.items():
            with self.subTest(key=alternative):
                entry = _alternative_decision()
                entry[alternative] = ""
                with self.assertRaises(schema.SchemaError) as ctx:
                    schema.validate_changed(*_appended(entry))
                self.assertEqual(
                    str(ctx.exception),
                    f"autonomous_decisions entry missing {primary}",
                )

    def test_non_string_alternative_prose_is_rejected_naming_the_primary_key(
        self,
    ) -> None:
        for alternative, primary in ALTERNATIVE_PROSE_KEYS.items():
            for bad in NON_STRING_PROSE:
                with self.subTest(key=alternative, value=bad):
                    entry = _alternative_decision()
                    entry[alternative] = bad
                    with self.assertRaises(schema.SchemaError) as ctx:
                        schema.validate_changed(*_appended(entry))
                    self.assertEqual(
                        str(ctx.exception),
                        f"autonomous_decisions entry missing {primary}",
                    )

    def test_alternative_vocabulary_entry_still_needs_a_cycle(self) -> None:
        # An entry carrying `question` is still an ordinary decision unless its
        # `type` says otherwise, so it does not get the assumed-ambiguity
        # branch's exemption from cycle.
        entry = _alternative_decision()
        del entry["cycle"]
        with self.assertRaises(schema.SchemaError) as ctx:
            schema.validate_changed(*_appended(entry))
        self.assertEqual(
            str(ctx.exception),
            "autonomous_decisions entry missing cycle",
        )

    def test_alternative_vocabulary_entry_still_needs_a_published_severity(
        self,
    ) -> None:
        for bad in UNPUBLISHED_SEVERITIES:
            with self.subTest(severity=bad):
                self.assertNotIn(bad, schema.DECISION_SEVERITIES)
                entry = _alternative_decision()
                entry["severity"] = bad
                with self.assertRaises(schema.SchemaError) as ctx:
                    schema.validate_changed(*_appended(entry))
                self.assertEqual(
                    str(ctx.exception),
                    "autonomous_decisions entry missing severity",
                )


class AssumedAmbiguityEntryTest(unittest.TestCase):
    """An `assumed-ambiguity` entry is judged by the second rule only."""

    def test_assumed_ambiguity_entry_needs_question_and_assumption(self) -> None:
        complete = {
            "type": "assumed-ambiguity",
            "question": "which severity does a parked PRD get?",
            "assumption": "treated it as medium",
        }
        # Accepted with no cycle, severity, action or reason of any kind.
        self.assertIsNone(schema.validate_changed(*_appended(complete)))

        for missing in ("question", "assumption"):
            with self.subTest(missing=missing):
                entry = dict(complete)
                del entry[missing]
                with self.assertRaises(schema.SchemaError) as ctx:
                    schema.validate_changed(*_appended(entry))
                self.assertEqual(
                    str(ctx.exception),
                    f"autonomous_decisions entry missing {missing}",
                )

        for blank in ("question", "assumption"):
            with self.subTest(blank=blank):
                entry = dict(complete)
                entry[blank] = ""
                with self.assertRaises(schema.SchemaError) as ctx:
                    schema.validate_changed(*_appended(entry))
                self.assertEqual(
                    str(ctx.exception),
                    f"autonomous_decisions entry missing {blank}",
                )


class AddedDecisionScopeTest(unittest.TestCase):
    """Every entry a write adds is judged, not only the one at the end of the
    list: a write that records two decisions at once must not smuggle a blank
    row in ahead of a well-formed one."""

    def test_the_first_of_two_appended_entries_is_judged_too(self) -> None:
        incomplete = _valid_decision()
        del incomplete["issue"]
        before = valid_state()
        after = valid_state()
        after["autonomous_decisions"] = [incomplete, _valid_decision()]
        with self.assertRaises(schema.SchemaError) as ctx:
            schema.validate_changed(before, after)
        self.assertEqual(
            str(ctx.exception),
            "autonomous_decisions entry missing issue",
        )

    def test_the_second_of_two_appended_entries_is_judged_too(self) -> None:
        # The mirror of the case above. Judging only the first added entry
        # fails exactly here, and it fails silently: the blank row lands at the
        # end of the batch report where nothing else looks at it.
        incomplete = _valid_decision()
        del incomplete["issue"]
        before = valid_state()
        after = valid_state()
        after["autonomous_decisions"] = [_valid_decision(), incomplete]
        with self.assertRaises(schema.SchemaError) as ctx:
            schema.validate_changed(before, after)
        self.assertEqual(
            str(ctx.exception),
            "autonomous_decisions entry missing issue",
        )

    def test_the_last_entry_of_a_longer_append_is_judged_too(self) -> None:
        # Three at once, the bad one at the end. Every two-entry case above is
        # satisfied by a check that judges the first two added entries, and
        # that check lets this row through.
        with self.assertRaises(schema.SchemaError) as ctx:
            schema.validate_changed(*_appended_batch(3, 2))
        self.assertEqual(
            str(ctx.exception),
            "autonomous_decisions entry missing issue",
        )

    def test_an_entry_in_the_middle_of_a_longer_append_is_judged_too(self) -> None:
        # Four at once, the bad one neither first nor last: no fixed slot --
        # the head, the tail, or any prefix or suffix of the added entries --
        # covers it. Only judging all of them does.
        with self.assertRaises(schema.SchemaError) as ctx:
            schema.validate_changed(*_appended_batch(4, 1))
        self.assertEqual(
            str(ctx.exception),
            "autonomous_decisions entry missing issue",
        )

    def test_two_well_formed_entries_appended_at_once_are_accepted(self) -> None:
        second = _valid_decision()
        second["cycle"] = 2
        before = valid_state()
        after = valid_state()
        after["autonomous_decisions"] = [_valid_decision(), second]
        self.assertIsNone(schema.validate_changed(before, after))


class ExistingDecisionEntriesTest(unittest.TestCase):
    """Only entries a write ADDS are judged -- this is what keeps a resumed
    batch, whose state already holds stub entries, loadable. "Added" is about
    which values are new, not about the list getting longer."""

    def test_existing_entries_are_not_revalidated_on_load(self) -> None:
        state = valid_state()
        state["autonomous_decisions"] = _stub_entries()
        self.assertIsNone(schema.validate(state))
        after = valid_state()
        after["autonomous_decisions"] = _stub_entries()
        after["phase"] = "review"
        self.assertIsNone(schema.validate_changed(state, after))

    def test_valid_append_beside_pre_existing_stubs_is_accepted(self) -> None:
        before = valid_state()
        before["autonomous_decisions"] = _stub_entries()
        after = valid_state()
        after["autonomous_decisions"] = _stub_entries() + [_valid_decision()]
        self.assertIsNone(schema.validate_changed(before, after))

    def test_bad_append_is_still_rejected_when_the_list_already_holds_stubs(
        self,
    ) -> None:
        # The check must judge the added entry, not give up because the list
        # it lands in already contains entries that would fail.
        entry = _valid_decision()
        del entry["issue"]
        before = valid_state()
        before["autonomous_decisions"] = _stub_entries()
        after = valid_state()
        after["autonomous_decisions"] = _stub_entries() + [entry]
        with self.assertRaises(schema.SchemaError) as ctx:
            schema.validate_changed(before, after)
        self.assertEqual(
            str(ctx.exception),
            "autonomous_decisions entry missing issue",
        )

    def test_an_entry_swapped_in_for_an_existing_one_is_judged(self) -> None:
        # The mirror of the tolerance above, and the case a length comparison
        # misses: the list is the same size afterwards, but the value at the
        # end was never in `before`, so the write added it and the report will
        # draw a row for it.
        incomplete = _valid_decision()
        del incomplete["issue"]
        before = valid_state()
        before["autonomous_decisions"] = _stub_entries()
        after = valid_state()
        after["autonomous_decisions"] = _stub_entries()[:-1] + [incomplete]
        with self.assertRaises(schema.SchemaError) as ctx:
            schema.validate_changed(before, after)
        self.assertEqual(
            str(ctx.exception),
            "autonomous_decisions entry missing issue",
        )

    def test_a_bare_string_swapped_in_for_an_existing_entry_is_judged(self) -> None:
        before = valid_state()
        before["autonomous_decisions"] = _stub_entries()
        after = valid_state()
        after["autonomous_decisions"] = _stub_entries()[:-1] + ["just a string"]
        with self.assertRaises(schema.SchemaError) as ctx:
            schema.validate_changed(before, after)
        self.assertRegex(str(ctx.exception), MISSING_KEY_MESSAGE)


class DuplicateAppendedDecisionEntriesTest(unittest.TestCase):
    """Addition counts occurrences, not membership: a value already sitting in
    the list can still be added again. Every copy a write pushes past the
    number `before` held is judged; the copies that merely carry over are not,
    so a state written by an older loop still loads."""

    def test_a_second_copy_of_an_invalid_entry_is_judged(self) -> None:
        # The value is already in `before`, so asking only whether it appears
        # there calls this write an addition of nothing -- and the blank row
        # the second copy draws lands in the report unchallenged.
        before = valid_state()
        before["autonomous_decisions"] = [{"cycle": 1}]
        after = valid_state()
        after["autonomous_decisions"] = [{"cycle": 1}, {"cycle": 1}]
        with self.assertRaises(schema.SchemaError) as ctx:
            schema.validate_changed(before, after)
        self.assertEqual(
            str(ctx.exception),
            "autonomous_decisions entry missing issue",
        )

    def test_a_second_copy_of_a_valid_entry_is_accepted(self) -> None:
        # The mirror, and the case a "refuse any repeat" fix gets wrong:
        # judging the new copy is the point, not refusing it for being a
        # repeat. Two identical well-formed decisions draw two readable rows.
        before = valid_state()
        before["autonomous_decisions"] = [_valid_decision()]
        after = valid_state()
        after["autonomous_decisions"] = [_valid_decision(), _valid_decision()]
        self.assertIsNone(schema.validate_changed(before, after))

    def test_valid_append_beside_repeated_stubs_is_accepted(self) -> None:
        # Every stub appears twice, so a fix that judges an entry whenever the
        # list holds more than one of it refuses a write that only added a
        # well-formed decision.
        before = valid_state()
        before["autonomous_decisions"] = _stub_entries() + _stub_entries()
        after = valid_state()
        after["autonomous_decisions"] = (
            _stub_entries() + _stub_entries() + [_valid_decision()]
        )
        self.assertIsNone(schema.validate_changed(before, after))

    def test_an_unchanged_list_of_repeated_stubs_is_never_judged(self) -> None:
        # The resume path: the write touches `phase`, the decisions list comes
        # through equal (a fresh copy, not the same object), and not one of its
        # entries -- all invalid, each of them duplicated -- is re-judged.
        before = valid_state()
        before["autonomous_decisions"] = _stub_entries() + _stub_entries()
        after = valid_state()
        after["autonomous_decisions"] = _stub_entries() + _stub_entries()
        after["phase"] = "review"
        self.assertIsNone(schema.validate_changed(before, after))

    def test_a_write_that_only_removes_entries_judges_nothing(self) -> None:
        # A removal can only lower an occurrence count, so nothing was added
        # and nothing is judged -- even though every entry kept, and every
        # entry dropped, fails the contract. Dropping one copy of each value
        # is the case a naive count comparison mixes up.
        remainders = (
            _stub_entries(),
            [{"cycle": 1}, {"cycle": 1}],
            [],
        )
        for remainder in remainders:
            with self.subTest(kept=len(remainder)):
                before = valid_state()
                before["autonomous_decisions"] = _stub_entries() + _stub_entries()
                after = valid_state()
                after["autonomous_decisions"] = remainder
                self.assertIsNone(schema.validate_changed(before, after))

    def test_several_copies_of_an_invalid_entry_appended_at_once_are_rejected(
        self,
    ) -> None:
        # Three copies beside none, two more beside one, three more beside
        # two: whichever of the new copies the validator reaches first, they
        # are the same value and the refusal names the same key.
        #
        # Three different invalid values, each lacking a different key, so the
        # repeated value is never the one literal a check could recognise by
        # sight. The bare stub names `issue`; the other two are well-formed
        # decisions with one prose key removed, so the key named back varies
        # with the value and a single hardcoded refusal cannot cover all three.
        missing_action = _valid_decision()
        del missing_action["action"]
        missing_reason = _valid_decision()
        del missing_reason["reason"]
        invalid_values = (
            ({"cycle": 1}, "issue"),
            (missing_action, "action"),
            (missing_reason, "reason"),
        )
        for value, key in invalid_values:
            for existing, total in ((0, 3), (1, 3), (2, 5)):
                with self.subTest(missing=key, existing=existing, total=total):
                    before = valid_state()
                    before["autonomous_decisions"] = [
                        dict(value) for _ in range(existing)
                    ]
                    after = valid_state()
                    after["autonomous_decisions"] = [dict(value) for _ in range(total)]
                    with self.assertRaises(schema.SchemaError) as ctx:
                        schema.validate_changed(before, after)
                    self.assertEqual(
                        str(ctx.exception),
                        f"autonomous_decisions entry missing {key}",
                    )

    def test_a_duplicate_added_before_the_end_of_the_list_is_judged(self) -> None:
        # The discipline AddedDecisionScopeTest already carries, brought to the
        # duplicate lane. The added copy sits at index 1 of three, so it is not
        # the last entry, its index is below the length `before` had, and its
        # value is not the bare {"cycle": 1} stub the cases above drive. A
        # check that judges only the tail of the list, only the indices past
        # the old length, or only that one literal, accepts this write and lets
        # the blank row the second copy draws into the report.
        incomplete = _valid_decision()
        del incomplete["issue"]
        before = valid_state()
        before["autonomous_decisions"] = [dict(incomplete), _valid_decision()]
        after = valid_state()
        after["autonomous_decisions"] = [
            dict(incomplete),
            dict(incomplete),
            _valid_decision(),
        ]
        with self.assertRaises(schema.SchemaError) as ctx:
            schema.validate_changed(before, after)
        self.assertEqual(
            str(ctx.exception),
            "autonomous_decisions entry missing issue",
        )

    def test_reordering_pre_existing_entries_judges_nothing(self) -> None:
        # A reorder adds no occurrence of anything: the same values come out
        # in the same numbers, so every entry merely carried over and none is
        # re-judged, however invalid they all are. A check that pairs
        # `after[i]` against `before[i]`, or that judges everything from the
        # first slot whose value moved, refuses this write -- and a loop whose
        # state got rewritten in a different order would never load again.
        before = valid_state()
        before["autonomous_decisions"] = _stub_entries()
        after = valid_state()
        after["autonomous_decisions"] = list(reversed(_stub_entries()))
        self.assertIsNone(schema.validate_changed(before, after))

    def test_a_carried_over_entry_matches_on_values_not_on_key_names(self) -> None:
        # The carry-over match compares VALUES. Here the added entry and the
        # pre-existing one share all five key names and differ only in what
        # those keys hold, so a count kept under a lossy key -- the sorted key
        # names, the key count, the `type` -- lets the pre-existing entry pay
        # for the added one and waves an unpublished severity into the report.
        bad = _valid_decision()
        bad["severity"] = "urgent"
        before = valid_state()
        before["autonomous_decisions"] = [_valid_decision()]
        after = valid_state()
        after["autonomous_decisions"] = [bad, _valid_decision()]
        with self.assertRaises(schema.SchemaError) as ctx:
            schema.validate_changed(before, after)
        self.assertEqual(
            str(ctx.exception),
            "autonomous_decisions entry missing severity",
        )


class StatectlRejectionCliTest(unittest.TestCase):
    """The refusal as an operator meets it, driven as a real process: the
    validator raising inside `mutate`'s apply has to reach the shell as exit 1
    plus the `rejected:` line, and the write it refused must never land."""

    def test_appending_a_bare_decision_exits_1_and_leaves_the_file_untouched(
        self,
    ) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "state.json"
            state_path.write_text(json.dumps(valid_state()), encoding="utf-8")
            before = state_path.read_bytes()
            proc = subprocess.run(
                [
                    sys.executable,
                    str(STATECTL),
                    str(state_path),
                    "append",
                    "autonomous_decisions",
                    '{"cycle": 1}',
                ],
                capture_output=True,
                text=True,
            )
            after = state_path.read_bytes()
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertEqual(
            proc.stderr.splitlines(),
            ["rejected: autonomous_decisions entry missing issue"],
        )
        # The raise happens before state.transaction writes, so a rejected
        # append leaves the file byte-identical -- not merely re-serialized.
        self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
