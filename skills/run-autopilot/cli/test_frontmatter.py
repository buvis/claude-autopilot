#!/usr/bin/env python3
"""Tests for cli/frontmatter.py - the Phase-0 PRD frontmatter parse.

The three dispositions are the contract, so each gets its own assertions:
an invalid value falls back AND warns, an absent field falls back SILENTLY,
and a malformed or missing block takes every default with exactly ONE warning.
The golden fixture is parsed here too, so the fixture and the parser fail
together if either drifts.

The last section covers `apply`, the module's one I/O-owning function: the
reset lines it computes from the pre-write state, and the `on_warning`
callback that lets a caller print a warning it would otherwise lose when the
write fails.
"""

from __future__ import annotations

import inspect
import json
import unittest
from pathlib import Path

from cli import frontmatter

GOLDEN = Path(__file__).resolve().parent.parent / "scripts" / "golden"


def _block(*lines: str) -> str:
    return "---\n" + "\n".join(lines) + "\n---\n\n# A PRD\n"


class DefaultsTests(unittest.TestCase):
    def test_bare_block_takes_every_default_silently(self) -> None:
        fields, warnings = frontmatter.parse(_block("title: nothing recognized"))
        self.assertEqual(warnings, [], "an unset field is the normal case")
        self.assertEqual(
            fields,
            {
                "catchup_mode": "run",
                "design_mode": "run",
                "doubt_reviewer": "codex",
                "consensus_engine": "legacy",
                "session_model": "sonnet",
                "rework_cap": 2,
            },
        )

    def test_optional_markers_stay_absent_rather_than_false(self) -> None:
        # Written as null/False they would survive into state.json and read as
        # "declared off" instead of "not declared".
        fields, _warnings = frontmatter.parse(_block("catchup: skip"))
        self.assertNotIn("design_gate", fields)
        self.assertNotIn("pause_on_ambiguity", fields)
        self.assertNotIn("plan_expansion_override", fields)


class RecognizedValueTests(unittest.TestCase):
    def test_every_enum_field_parses_its_allowed_values(self) -> None:
        for line, key, value in [
            ("catchup: skip", "catchup_mode", "skip"),
            ("catchup: force", "catchup_mode", "force"),
            ("design: skip", "design_mode", "skip"),
            ("doubt_reviewer: fable", "doubt_reviewer", "fable"),
            ("consensus_engine: workflow", "consensus_engine", "workflow"),
            ("consensus_engine: shadow", "consensus_engine", "shadow"),
        ]:
            with self.subTest(line=line):
                fields, warnings = frontmatter.parse(_block(line))
                self.assertEqual(fields[key], value)
                self.assertEqual(warnings, [])

    def test_rework_cap_parses_as_an_int_not_a_string(self) -> None:
        fields, warnings = frontmatter.parse(_block("rework_cap: 5"))
        self.assertEqual(fields["rework_cap"], 5)
        self.assertIsInstance(fields["rework_cap"], int)
        self.assertEqual(warnings, [])

    def test_design_gate_recognized_only_at_its_exact_value(self) -> None:
        fields, warnings = frontmatter.parse(_block("design_gate: user"))
        self.assertEqual(fields["design_gate"], "user")
        self.assertEqual(warnings, [])

        other, no_warnings = frontmatter.parse(_block("design_gate: auto"))
        self.assertNotIn("design_gate", other)
        self.assertEqual(no_warnings, [], "an unrecognized opt-in is not a warning")

    def test_pause_on_ambiguity_recognized_only_at_true(self) -> None:
        fields, _w = frontmatter.parse(_block("pause_on_ambiguity: true"))
        self.assertIs(fields["pause_on_ambiguity"], True)
        for value in ("false", "True", "yes"):
            with self.subTest(value=value):
                other, _ = frontmatter.parse(_block(f"pause_on_ambiguity: {value}"))
                self.assertNotIn("pause_on_ambiguity", other)

    def test_plan_expansion_recognized_only_at_allow(self) -> None:
        fields, warnings = frontmatter.parse(_block("plan_expansion: allow"))
        self.assertIs(fields["plan_expansion_override"], True)
        self.assertEqual(
            fields,
            {**frontmatter.defaults(), "plan_expansion_override": True},
            "the opt-in adds exactly one state key and nothing else",
        )
        self.assertEqual(warnings, [])
        # The negatives cover a substring match (disallow, allowed, allow now),
        # a case-folded match (ALLOW, Allow) and a bare `plan_expansion:` line.
        for value in (
            "true",
            "yes",
            "no",
            "ALLOW",
            "Allow",
            "false",
            "disallow",
            "allowed",
            "allow now",
            "",
        ):
            with self.subTest(value=value):
                other, no_warnings = frontmatter.parse(
                    _block(f"plan_expansion: {value}"),
                )
                self.assertNotIn("plan_expansion_override", other)
                self.assertEqual(
                    no_warnings,
                    [],
                    "an unrecognized opt-in is not a warning",
                )

    def test_plan_expansion_only_counts_inside_a_well_formed_block(self) -> None:
        fields, warnings = frontmatter.parse("---\nplan_expansion: allow\n\n# A PRD\n")
        self.assertEqual(
            fields,
            frontmatter.defaults(),
            "an opt-in inside an unterminated block must not be half-applied",
        )
        self.assertEqual(warnings, [frontmatter.MALFORMED_WARNING])

        other, no_warnings = frontmatter.parse(
            _block("title: x") + "\nadd plan_expansion: allow to the frontmatter\n",
        )
        self.assertNotIn("plan_expansion_override", other)
        self.assertEqual(no_warnings, [])

    def test_session_model_defaults_to_sonnet(self) -> None:
        # PRD 00200: the session model is its own key, defaulting silently to
        # sonnet - `default_model: opus` alone must not pick the orchestrator.
        fields, warnings = frontmatter.parse(_block("default_model: opus"))
        self.assertEqual(fields["session_model"], "sonnet")
        self.assertEqual(warnings, [])

    def test_session_model_opus_is_accepted(self) -> None:
        fields, warnings = frontmatter.parse(_block("session_model: opus"))
        self.assertEqual(fields["session_model"], "opus")
        self.assertEqual(warnings, [])

    def test_session_model_bad_value_warns_and_defaults(self) -> None:
        fields, warnings = frontmatter.parse(_block("session_model: haiku"))
        self.assertEqual(fields["session_model"], "sonnet")
        self.assertEqual(len(warnings), 1)
        self.assertIn("session_model", warnings[0])

    def test_unknown_keys_are_ignored_without_warning(self) -> None:
        # default_model belongs to /plan-tasks and is re-read at Phase 6;
        # Phase 0 must not claim it.
        fields, warnings = frontmatter.parse(
            _block("prd: 00118", "title: A: colonated title", "default_model: opus"),
        )
        self.assertEqual(warnings, [])
        self.assertNotIn("default_model", fields)
        self.assertEqual(fields["catchup_mode"], "run")


class InvalidValueTests(unittest.TestCase):
    def test_each_invalid_enum_falls_back_and_warns_naming_the_field(self) -> None:
        for line, key, default in [
            ("catchup: sometimes", "catchup_mode", "run"),
            ("design: maybe", "design_mode", "run"),
            ("doubt_reviewer: gemini", "doubt_reviewer", "codex"),
            ("consensus_engine: turbo", "consensus_engine", "legacy"),
        ]:
            with self.subTest(line=line):
                fields, warnings = frontmatter.parse(_block(line))
                self.assertEqual(fields[key], default)
                self.assertEqual(len(warnings), 1)
                self.assertIn(line.split(":")[0], warnings[0])

    def test_non_positive_or_unparseable_rework_cap_falls_back_and_warns(self) -> None:
        for raw in ("0", "-3", "abc", "2.5", ""):
            with self.subTest(raw=raw):
                fields, warnings = frontmatter.parse(_block(f"rework_cap: {raw}"))
                self.assertEqual(fields["rework_cap"], 2)
                self.assertEqual(len(warnings), 1)
                self.assertIn("rework_cap", warnings[0])

    def test_every_field_invalid_takes_every_default_and_does_not_crash(self) -> None:
        fields, warnings = frontmatter.parse(
            _block(
                "catchup: nope",
                "rework_cap: nope",
                "design: nope",
                "doubt_reviewer: nope",
                "consensus_engine: nope",
            ),
        )
        self.assertEqual(fields, frontmatter.defaults())
        self.assertEqual(len(warnings), 5, "one warning per invalid field")


class MalformedBlockTests(unittest.TestCase):
    def test_missing_frontmatter_takes_defaults_with_one_warning(self) -> None:
        fields, warnings = frontmatter.parse("# A PRD\n\nNo frontmatter here.\n")
        self.assertEqual(fields, frontmatter.defaults())
        self.assertEqual(warnings, [frontmatter.MALFORMED_WARNING])

    def test_unterminated_block_is_malformed(self) -> None:
        fields, warnings = frontmatter.parse("---\ncatchup: skip\n\n# A PRD\n")
        self.assertEqual(fields, frontmatter.defaults())
        self.assertEqual(warnings, [frontmatter.MALFORMED_WARNING])
        self.assertEqual(
            fields["catchup_mode"],
            "run",
            "a value inside an unterminated block must not be half-applied",
        )

    def test_block_closing_past_the_head_bound_is_malformed(self) -> None:
        # Only the first 20 lines are read, so a `---` rule deep in the body
        # can never be mistaken for the closing delimiter.
        text = "---\n" + "\n".join(f"pad{i}: x" for i in range(25)) + "\n---\n"
        _fields, warnings = frontmatter.parse(text)
        self.assertEqual(warnings, [frontmatter.MALFORMED_WARNING])

    def test_empty_text_is_malformed_rather_than_a_crash(self) -> None:
        fields, warnings = frontmatter.parse("")
        self.assertEqual(fields, frontmatter.defaults())
        self.assertEqual(warnings, [frontmatter.MALFORMED_WARNING])

    def test_malformed_warning_names_every_default_it_applied(self) -> None:
        for token in (
            "catchup_mode=run",
            "rework_cap=2",
            "design_mode=run",
            "doubt_reviewer=codex",
            "consensus_engine=legacy",
            "session_model=sonnet",
        ):
            self.assertIn(token, frontmatter.MALFORMED_WARNING)


class GoldenFixtureTests(unittest.TestCase):
    def test_golden_prd_frontmatter_parses_clean(self) -> None:
        text = (GOLDEN / "prd-frontmatter.md").read_text(encoding="utf-8")
        fields, warnings = frontmatter.parse(text)
        self.assertEqual(warnings, [], "the known-good fixture must not warn")
        self.assertEqual(
            fields,
            {
                "catchup_mode": "run",
                "design_mode": "run",
                "doubt_reviewer": "codex",
                "consensus_engine": "legacy",
                "session_model": "sonnet",
                "rework_cap": 3,
                "design_gate": "user",
                "pause_on_ambiguity": True,
            },
        )


# -- apply: the non-printing core of the `frontmatter` verb --------------------
#
# pytest functions rather than TestCase methods: these need `tmp_path`, which
# cannot be injected into a unittest method.


def _state_file(tmp_path: Path, **fields: object) -> Path:
    path = tmp_path / "state.json"
    path.write_text(
        json.dumps({"phase": "build", "next_phase": "build", **fields}),
        encoding="utf-8",
    )
    return path


def _prd_file(tmp_path: Path, *lines: str) -> Path:
    path = tmp_path / "00090-example-v1.md"
    path.write_text(_block(*lines), encoding="utf-8")
    return path


def test_apply_returns_the_reset_lines_beside_the_fields_and_warnings(
    tmp_path: Path,
) -> None:
    # The reset diagnostics are a THIRD return value, not extra warnings: a
    # caller that prints warnings before the write and resets after it needs
    # the two lists apart.
    state_path = _state_file(tmp_path, rework_cap=5)
    prd = _prd_file(tmp_path, "rework_cap: 2")

    fields, warnings, resets = frontmatter.apply(prd, state_path)

    assert fields["rework_cap"] == 2
    assert resets == ["autopilot: PRD frontmatter reset rework_cap 5 -> 2"]
    assert warnings == [], "a reset is not a parse warning"


def test_apply_reports_no_resets_when_the_state_already_held_the_value(
    tmp_path: Path,
) -> None:
    state_path = _state_file(tmp_path, rework_cap=2)
    prd = _prd_file(tmp_path, "rework_cap: 2")

    _fields, _warnings, resets = frontmatter.apply(prd, state_path)

    assert resets == [], "writing the same value back is not a reset"


def test_apply_hands_every_warning_line_to_on_warning(tmp_path: Path) -> None:
    state_path = _state_file(tmp_path)
    prd = _prd_file(tmp_path, "catchup: sometimes", "doubt_reviewer: gemini")
    seen: list[str] = []

    _fields, warnings, _resets = frontmatter.apply(
        prd, state_path, on_warning=seen.append,
    )

    assert len(warnings) == 2, warnings
    assert seen == warnings, "every returned line reaches the callback, in order"


def test_apply_calls_on_warning_before_it_writes_state(tmp_path: Path) -> None:
    # This ordering is the whole point of the callback: the verb has to have
    # printed the warnings by the time a failing write aborts the call.
    state_path = _state_file(tmp_path, catchup_mode="skip")
    prd = _prd_file(tmp_path, "catchup: force", "doubt_reviewer: gemini")
    snapshots: list[str] = []

    frontmatter.apply(
        prd,
        state_path,
        on_warning=lambda _line: snapshots.append(
            state_path.read_text(encoding="utf-8"),
        ),
    )

    assert snapshots, "an invalid doubt_reviewer must produce a warning"
    for snapshot in snapshots:
        assert "force" not in snapshot, "the warning arrived after the write"
    assert "force" in state_path.read_text(encoding="utf-8")


def test_apply_keeps_two_positional_arguments_and_a_keyword_only_callback() -> None:
    # `enter()` calls apply(prd_path, state_path) with no callback, so the new
    # parameter has to be optional and must not take a positional slot.
    parameters = inspect.signature(frontmatter.apply).parameters
    assert list(parameters) == ["prd_path", "state_path", "on_warning"]
    assert parameters["on_warning"].default is None
    assert parameters["on_warning"].kind is inspect.Parameter.KEYWORD_ONLY


if __name__ == "__main__":
    unittest.main()
