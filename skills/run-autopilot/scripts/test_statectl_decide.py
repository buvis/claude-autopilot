"""Tests for the `decide` verb and `get --default` (PRD 00309 fast-track card c1).

A census of batch 202610111300's loop transcripts counted 11
`autonomous_decisions` appends rejected by `_validate_decision_entry`
(cli/schema.py) for a missing `issue` or `severity` - each a wasted turn
spent re-typing `statectl.py append autonomous_decisions ...` by hand. The
`decide` verb is the same append, pre-validated through the one schema rule
BEFORE the file is touched, so a bad entry costs one call instead of a
retry loop; invalid in, the state file is byte-unchanged.

Separately, 5 `statectl.py get` calls exited 1 with `json-path key not
found` before the key existed at all (a state written before a field was
ever set). `get --default VALUE` lets a reader ask "give me VALUE if this
key is absent" instead of treating "never written yet" as a usage error;
`get` with no `--default` keeps today's exit-1 behavior unchanged.

Stdlib-only unittest, subprocess pattern - matches test_statectl.py exactly,
which these tests sit beside.
"""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

STATECTL = Path(__file__).parent / "statectl.py"


class StatectlDecideTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.state = Path(self.tmp.name) / "state.json"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write_state(self, obj: object) -> None:
        self.state.write_text(json.dumps(obj))

    def load_state(self) -> object:
        return json.loads(self.state.read_text())

    def run_cli(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["python3", str(STATECTL), str(self.state), *args],
            capture_output=True,
            text=True,
        )

    # -- decide: a valid entry lands -------------------------------------

    def test_decide_appends_a_valid_entry(self) -> None:
        self.write_state({"autonomous_decisions": []})
        entry = {
            "issue": "no CHANGELOG entry template matched the fix",
            "severity": "low",
            "cycle": 1,
            "action": "added one under Fixed",
            "reason": "closest documented category",
        }
        result = self.run_cli(
            "decide",
            "--issue",
            entry["issue"],
            "--severity",
            entry["severity"],
            "--cycle",
            str(entry["cycle"]),
            "--action",
            entry["action"],
            "--reason",
            entry["reason"],
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        state = self.load_state()
        self.assertEqual(state["autonomous_decisions"], [entry])

    # -- decide: missing severity is rejected before any write -----------

    def test_decide_missing_severity_exits_1_before_write(self) -> None:
        self.write_state({"autonomous_decisions": []})
        before = self.state.read_bytes()

        result = self.run_cli(
            "decide",
            "--issue",
            "no CHANGELOG entry template matched the fix",
            "--cycle",
            "1",
            "--action",
            "added one under Fixed",
            "--reason",
            "closest documented category",
            # --severity deliberately omitted
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("severity", result.stderr)
        self.assertEqual(
            self.state.read_bytes(),
            before,
            "an entry the schema rejects must never reach disk",
        )

    # -- get --default: fills in a value for a key never written ---------

    def test_get_default_prints_default_on_missing_key(self) -> None:
        self.write_state({"phase": "build"})

        result = self.run_cli("get", "cap_rotations", "--default", json.dumps([]))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), [])

    # -- get without --default: unchanged exit-1 contract ----------------

    def test_get_without_default_still_exits_1(self) -> None:
        self.write_state({"phase": "build"})

        result = self.run_cli("get", "cap_rotations")

        self.assertEqual(result.returncode, 1)
        self.assertTrue(result.stderr.strip())

    # -- get --default: a present key must never be masked by the default --

    def test_get_default_never_masks_a_present_key(self) -> None:
        # _dispatch finds the json-path by hardcoding argv[2], so flag-first
        # order (`get --default VALUE path`) reads "--default" itself as the
        # path. "--default" is absent from the state, so get_value raises
        # UsageError and the present key's real value is silently replaced
        # by the default instead of being returned.
        self.write_state({"cap_rotations": 5})

        result = self.run_cli("get", "--default", "0", "cap_rotations")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), 5)

    def test_get_default_flag_first_order_works(self) -> None:
        self.write_state({"batch": {"id": "xyz"}})

        path_first = self.run_cli("get", "batch.id", "--default", "null")
        flag_first = self.run_cli("get", "--default", "null", "batch.id")

        self.assertEqual(path_first.returncode, 0, path_first.stderr)
        self.assertEqual(flag_first.returncode, 0, flag_first.stderr)
        self.assertEqual(json.loads(path_first.stdout), "xyz")
        self.assertEqual(
            json.loads(path_first.stdout),
            json.loads(flag_first.stdout),
        )

    def test_get_default_malformed_path_is_a_usage_error(self) -> None:
        # _run_get_with_default's try/except wraps both parse_path() and
        # get_value(), so a malformed path (a doubled dot) raises UsageError
        # and is swallowed into the default exactly like a missing key would
        # be - the caller cannot tell "never written" from "you typed the
        # path wrong".
        self.write_state({"batch": {"id": "xyz"}})

        result = self.run_cli("get", "batch..id", "--default", "7")

        self.assertNotEqual(result.returncode, 0)
        self.assertNotEqual(result.stdout.strip(), "7")

    def test_get_trailing_default_is_a_usage_error(self) -> None:
        self.write_state({"batch": {"id": "xyz"}})

        result = self.run_cli("get", "batch.id", "--default")

        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("Traceback", result.stderr)
        self.assertNotIn("IndexError", result.stderr)

    def test_usage_names_decide_and_get_default(self) -> None:
        result = subprocess.run(
            ["python3", str(STATECTL), "--help"],
            capture_output=True,
            text=True,
        )

        output = result.stdout + result.stderr
        self.assertIn("decide", output)
        self.assertIn("--default", output)


if __name__ == "__main__":
    unittest.main()
