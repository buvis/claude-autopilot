#!/usr/bin/env python3
"""Tests for which autonomous_decisions entries a write is judged on: every
entry it adds, duplicates included, and none it merely carries over -- plus
the refusal as an operator meets it, driven through the statectl CLI.

Split out of test_schema.py to keep every file under the 800-line limit
(rules/coding-style.md). The entry contract these writes are judged against,
with the shared helpers and constants, lives in
test_schema_decision_entries.py; `valid_state()` stays in test_schema.py.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cli import schema
from cli.test_schema import valid_state
from cli.test_schema_decision_entries import MISSING_KEY_MESSAGE, _valid_decision

_SKILL_DIR = Path(__file__).resolve().parent.parent
# The runnable CLI is the scripts/ shim: cli/statectl.py imports its siblings
# relatively and carries no __main__ guard, so only this path is a process.
STATECTL = _SKILL_DIR / "scripts" / "statectl.py"


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


def _decisions_write(before_entries: list, after_entries: list) -> tuple[dict, dict]:
    """(before, after) for a write whose only change is the decisions list."""
    before = valid_state()
    before["autonomous_decisions"] = before_entries
    after = valid_state()
    after["autonomous_decisions"] = after_entries
    return before, after


# Values Python calls equal to the int 1 without being it: `True == 1` and
# `1.0 == 1` both hold, so a carry-over match by `==` alone cannot tell an
# entry carrying one of these from an entry carrying the int.
INT_LOOKALIKES = (True, 1.0)


def _int_lookalike_stubs() -> list:
    """Entries an older batch wrote whose cycles are `==`-equal to each other
    without sharing a type: every pairing of True, 1.0 and 1 compares equal.
    None of them meets the contract, so judging any one of them raises."""
    return [{"cycle": value, "issue": "i"} for value in (*INT_LOOKALIKES, 1)]


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

    def test_an_int_lookalike_cycle_does_not_claim_an_existing_int_entry(self) -> None:
        # The carry-over match compares values with `==`, and `True == 1` and
        # `1.0 == 1` are both true in Python. So an appended entry carrying one
        # of them reads as equal to the well-formed entry already in the list,
        # claims its occurrence and is never judged -- while the entry contract
        # refuses a boolean or float cycle outright. The two have to agree:
        # this value was never in `before`, so the write added it and it is
        # judged like any other addition. Driven from both slots, because only
        # one of the two entries can claim the single occurrence.
        for lookalike in INT_LOOKALIKES:
            entry = _valid_decision()
            entry["cycle"] = lookalike
            for position, added in (
                ("first", [entry, _valid_decision()]),
                ("last", [_valid_decision(), entry]),
            ):
                with self.subTest(cycle=repr(lookalike), position=position):
                    with self.assertRaises(schema.SchemaError) as ctx:
                        schema.validate_changed(
                            *_decisions_write([_valid_decision()], added),
                        )
                    self.assertEqual(
                        str(ctx.exception),
                        "autonomous_decisions entry missing cycle",
                    )

    def test_an_int_lookalike_in_any_field_makes_the_entry_a_new_one(self) -> None:
        # `cycle` is not the only key an int can sit in, so a matcher that
        # compares the cycle by type and everything else with `==` still lets
        # this write through. The collision is in an extra key the contract
        # says nothing about; the entry it stands in for is one an older loop
        # wrote, carrying a severity the report cannot print. The list is the
        # same length afterwards, so only judging the changed value refuses it.
        for lookalike in INT_LOOKALIKES:
            with self.subTest(value=repr(lookalike)):
                existing = _valid_decision()
                existing["severity"] = "urgent"
                existing["consensus"] = 1
                self.assertNotIn(existing["severity"], schema.DECISION_SEVERITIES)
                added = dict(existing)
                added["consensus"] = lookalike
                with self.assertRaises(schema.SchemaError) as ctx:
                    schema.validate_changed(*_decisions_write([existing], [added]))
                self.assertEqual(
                    str(ctx.exception),
                    "autonomous_decisions entry missing severity",
                )

    def test_carrying_over_int_lookalike_entries_judges_nothing(self) -> None:
        # The mirror of the two cases above, and the one a fix that simply
        # refuses every entry holding a bool or a float gets wrong. All three
        # stubs fail the contract and each compares `==`-equal to the other
        # two, so a matcher that now weighs types has to pair each one with its
        # OWN type -- otherwise it judges an entry the write never added, and
        # the state an older loop wrote stops loading whether that write left
        # the list alone, reordered it, or dropped an entry from it.
        for label, remaining in (
            ("unchanged", _int_lookalike_stubs()),
            ("reordered", list(reversed(_int_lookalike_stubs()))),
            ("one removed", _int_lookalike_stubs()[1:]),
        ):
            with self.subTest(write=label):
                before, after = _decisions_write(_int_lookalike_stubs(), remaining)
                after["phase"] = "review"
                self.assertIsNone(schema.validate_changed(before, after))


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
