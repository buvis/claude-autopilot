#!/usr/bin/env python3
"""Tests for cli/schema.py's autonomous_decisions entry contract: the keys an
appended entry must carry, the vocabularies it may speak, and the severity set
it is judged against.

Split out of test_schema.py to keep every file under the 800-line limit
(rules/coding-style.md). `valid_state()` stays in test_schema.py, the one
authoritative copy; the decision helpers and constants live here, and
test_schema_decision_scope.py imports the ones it shares.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cli import schema
from cli.test_schema import valid_state


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


if __name__ == "__main__":
    unittest.main()
