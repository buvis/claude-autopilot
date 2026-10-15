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
            "action": "added one under Fixed",
            "reason": "closest documented category",
            "cycle": 1,
            "severity": "low",
        }
        result = self.run_cli("decide", json.dumps(entry))

        self.assertEqual(result.returncode, 0, result.stderr)
        state = self.load_state()
        self.assertEqual(state["autonomous_decisions"], [entry])

    # -- decide: missing severity is rejected before any write -----------

    def test_decide_missing_severity_exits_1_before_write(self) -> None:
        self.write_state({"autonomous_decisions": []})
        before = self.state.read_bytes()
        entry = {
            "issue": "no CHANGELOG entry template matched the fix",
            "action": "added one under Fixed",
            "reason": "closest documented category",
            "cycle": 1,
            # severity deliberately omitted
        }

        result = self.run_cli("decide", json.dumps(entry))

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


if __name__ == "__main__":
    unittest.main()
