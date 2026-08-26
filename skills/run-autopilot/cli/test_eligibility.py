#!/usr/bin/env python3
"""Tests for cli/eligibility.py - the PRD `eligibility:` gate (PRD 00137).

Two halves: `command_for` reads the key out of PRD frontmatter (absent =
eligible, so None is the common answer), and `evaluate` runs the command and
reports its exit code. Everything that is not a clean exit 0 - non-zero,
unknown binary, timeout, OSError - is an unmet check, because the gate fails
toward not-running the PRD.

The last class is the one real fixture: the command stamped on the live
`hold/00110` PRD, proven unmet against an empty reviews tree and met against
three synthetic ones. That PRD lives under dev/local (gitignored), so the
command string is pinned HERE and the hold file mirrors it.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cli import eligibility

# Mirrors the `eligibility:` line stamped on dev/local/prds/hold/00110-*.md,
# which is gitignored and so cannot be read by a test on a fresh clone.
HOLD_00110_COMMAND = (
    "test $(grep -l 'no verdict divergence' "
    "$(grep -l '^consensus_run_id:' dev/local/reviews/*.md 2>/dev/null "
    "| grep -v /00110-) /dev/null 2>/dev/null | wc -l) -ge 3"
)


def _prd(*frontmatter_lines: str) -> str:
    block = "\n".join(frontmatter_lines)
    return f"---\n{block}\n---\n\n# PRD\n\nBody.\n"


class CommandForTests(unittest.TestCase):
    def test_absent_key_is_none_so_the_prd_stays_eligible(self) -> None:
        self.assertIsNone(eligibility.command_for(_prd("catchup: skip")))

    def test_no_frontmatter_at_all_is_none(self) -> None:
        self.assertIsNone(eligibility.command_for("# PRD\n\nBody.\n"))

    def test_unquoted_value_is_returned_verbatim(self) -> None:
        self.assertEqual(
            eligibility.command_for(_prd("eligibility: test -f README.md")),
            "test -f README.md",
        )

    def test_strips_one_layer_of_matching_double_quotes(self) -> None:
        self.assertEqual(
            eligibility.command_for(_prd('eligibility: "test -f README.md"')),
            "test -f README.md",
        )

    def test_strips_one_layer_of_matching_single_quotes(self) -> None:
        self.assertEqual(
            eligibility.command_for(_prd("eligibility: 'test -f README.md'")),
            "test -f README.md",
        )

    def test_keeps_inner_quotes_the_shell_still_needs(self) -> None:
        self.assertEqual(
            eligibility.command_for(
                _prd("eligibility: \"test $(ls 'a b' | wc -l) -ge 1\""),
            ),
            "test $(ls 'a b' | wc -l) -ge 1",
        )

    def test_unmatched_leading_quote_is_left_alone(self) -> None:
        self.assertEqual(eligibility.command_for(_prd('eligibility: "oops')), '"oops')

    def test_blank_value_is_none_rather_than_an_empty_shell_command(self) -> None:
        self.assertIsNone(eligibility.command_for(_prd("eligibility:")))

    def test_value_keeps_a_colon_after_the_first_one(self) -> None:
        self.assertEqual(
            eligibility.command_for(_prd("eligibility: grep -q 'key: value' f")),
            "grep -q 'key: value' f",
        )


class EvaluateTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.cwd = Path(tmp.name)

    def test_true_is_exit_zero_with_no_note(self) -> None:
        self.assertEqual(eligibility.evaluate("true", self.cwd), (0, ""))

    def test_false_is_non_zero(self) -> None:
        code, note = eligibility.evaluate("false", self.cwd)
        self.assertNotEqual(code, 0)
        self.assertEqual(note, "")

    def test_unknown_binary_is_non_zero_not_a_crash(self) -> None:
        code, _note = eligibility.evaluate("no-such-binary-xyzzy", self.cwd)
        self.assertNotEqual(code, 0)

    def test_timeout_is_minus_one_and_says_so(self) -> None:
        self.assertEqual(
            eligibility.evaluate("sleep 2", self.cwd, timeout=0.2),
            (-1, "timeout"),
        )

    def test_runs_in_the_given_cwd_not_the_callers(self) -> None:
        (self.cwd / "marker.txt").write_text("x", encoding="utf-8")
        self.assertEqual(eligibility.evaluate("test -f marker.txt", self.cwd)[0], 0)

    def test_unusable_cwd_is_an_error_note_not_an_exception(self) -> None:
        code, note = eligibility.evaluate("true", self.cwd / "does-not-exist")
        self.assertEqual(code, -1)
        self.assertTrue(note.startswith("error: "), note)

    def test_a_chatty_command_still_reports_only_its_exit_code(self) -> None:
        # Whether the output was really captured is proven where it matters, at
        # the CLI: test_lifecycle_cli.py's
        # SelectEligibilityTests::test_a_chatty_check_does_not_corrupt_the_pick_json.
        code, note = eligibility.evaluate("echo loud; exit 3", self.cwd)
        self.assertEqual((code, note), (3, ""))


class Hold00110FixtureTests(unittest.TestCase):
    """The live fixture, both directions."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.reviews = self.root / "dev" / "local" / "reviews"
        self.reviews.mkdir(parents=True)

    def _review(self, name: str, *, stamped: bool, converged: bool) -> None:
        head = "---\nconsensus_run_id: abc123\n---\n" if stamped else "---\n---\n"
        body = "Alice: no verdict divergence\n" if converged else "Alice: diverged\n"
        (self.reviews / name).write_text(head + body, encoding="utf-8")

    def test_00110_check_is_unmet_on_an_empty_reviews_dir_and_met_with_three_synthetic_reviews(
        self,
    ) -> None:
        unmet, _note = eligibility.evaluate(HOLD_00110_COMMAND, self.root)
        self.assertNotEqual(unmet, 0, "an empty reviews dir must not satisfy the check")

        for index in range(3):
            self._review(f"0020{index}-x-review.md", stamped=True, converged=True)
        met, note = eligibility.evaluate(HOLD_00110_COMMAND, self.root)
        self.assertEqual((met, note), (0, ""))

    def test_00110_check_ignores_its_own_satellites(self) -> None:
        for index in range(2):
            self._review(f"0020{index}-x-review.md", stamped=True, converged=True)
        self._review("00110-flip-review.md", stamped=True, converged=True)
        code, _note = eligibility.evaluate(HOLD_00110_COMMAND, self.root)
        self.assertNotEqual(
            code, 0, "00110's own review must not count toward its unpark"
        )

    def test_00110_check_ignores_unstamped_and_diverged_reviews(self) -> None:
        self._review("00201-a-review.md", stamped=True, converged=True)
        self._review("00202-b-review.md", stamped=False, converged=True)
        self._review("00203-c-review.md", stamped=True, converged=False)
        code, _note = eligibility.evaluate(HOLD_00110_COMMAND, self.root)
        self.assertNotEqual(code, 0)

    def test_00110_check_is_unmet_when_the_reviews_dir_does_not_exist(self) -> None:
        bare = self.root / "bare"
        bare.mkdir()
        code, _note = eligibility.evaluate(HOLD_00110_COMMAND, bare)
        self.assertNotEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
