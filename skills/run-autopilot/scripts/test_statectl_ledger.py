"""Tests for the attempt ledger complete-prd writes (PRD 00143).

Binds the contract that `statectl.py <state> complete-prd <prd>` appends one
JSONL row per `tasks[].attempts[]` entry to `<state-dir>/ledger/attempts.jsonl`
inside the same transaction, before the per-PRD reset, and that a failed ledger
write aborts the close with `state.json` byte-untouched. Same stdlib-only
unittest, subprocess pattern as test_statectl_complete_prd.py.
"""

import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

STATECTL = Path(__file__).parent / "statectl.py"
PRD = "00143-example.md"
_ISO_UTC_SECONDS = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def _state_with_attempts() -> dict:
    return {
        "phase": "review",
        "prd": PRD,
        "cycle": 1,
        "tasks_completed": 2,
        "tasks_total": 2,
        "batch": {"id": "202608260001", "parks_consecutive": 1},
        "tasks": [
            {
                "id": "task-1",
                "name": "First",
                "model": "sonnet",
                "qwen_eligible": True,
                "attempts": [
                    {"attempt": 1, "model": "sonnet", "outcome": "aborted"},
                    {
                        "attempt": 2,
                        "model": "opus",
                        "outcome": "completed",
                        "escalation_reason": "gate_failure",
                        "escalated_from": "sonnet",
                    },
                ],
            },
            {
                "id": "task-2",
                "name": "Second",
                "attempts": [
                    {"attempt": 1, "model": "haiku", "outcome": "completed"},
                    {"attempt": 2, "model": "haiku", "outcome": "completed"},
                ],
            },
        ],
    }


class StatectlLedgerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.state = Path(self.tmp.name) / "state.json"
        self.ledger = Path(self.tmp.name) / "ledger" / "attempts.jsonl"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write_state(self, obj: object) -> None:
        self.state.write_text(json.dumps(obj))

    def load_state(self) -> dict:
        return json.loads(self.state.read_text(encoding="utf-8"))

    def run_cli(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["python3", str(STATECTL), str(self.state), *args],
            capture_output=True,
            text=True,
        )

    def ledger_rows(self) -> list[dict]:
        lines = self.ledger.read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines if line]

    def test_complete_prd_appends_one_row_per_attempt_across_tasks(self) -> None:
        self.write_state(_state_with_attempts())
        result = self.run_cli("complete-prd", PRD)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.ledger_rows()), 4)
        # The close itself still lands in the same write.
        state = self.load_state()
        self.assertEqual(state["batch"]["completed_prds"][-1]["filename"], PRD)
        self.assertEqual(state["batch"]["parks_consecutive"], 0)

    def test_row_carries_the_documented_fields_and_the_attempt_verbatim(
        self,
    ) -> None:
        fixture = _state_with_attempts()
        self.write_state(fixture)
        self.assertEqual(self.run_cli("complete-prd", PRD).returncode, 0)
        rows = self.ledger_rows()
        self.assertEqual(
            set(rows[0]),
            {
                "batch_id",
                "prd",
                "task_id",
                "task_name",
                "task_model",
                "qwen_eligible",
                "recorded_at",
                "attempt",
            },
        )
        second = rows[1]
        self.assertEqual(second["batch_id"], "202608260001")
        self.assertEqual(second["prd"], PRD)
        self.assertEqual(second["task_id"], "task-1")
        self.assertEqual(second["task_name"], "First")
        self.assertEqual(second["task_model"], "sonnet")
        self.assertIs(second["qwen_eligible"], True)
        self.assertRegex(second["recorded_at"], _ISO_UTC_SECONDS)
        self.assertEqual(second["attempt"], fixture["tasks"][0]["attempts"][1])
        # A task without model/qwen_eligible records null, never a guess.
        self.assertIsNone(rows[2]["task_model"])
        self.assertIsNone(rows[2]["qwen_eligible"])
        self.assertEqual(rows[3]["attempt"], fixture["tasks"][1]["attempts"][1])

    def test_append_keeps_an_existing_row_that_lacks_a_trailing_newline(
        self,
    ) -> None:
        self.ledger.parent.mkdir(parents=True)
        old_row = {"batch_id": "old", "prd": "00001-old.md", "attempt": {"n": 1}}
        self.ledger.write_text(json.dumps(old_row), encoding="utf-8")
        self.write_state(_state_with_attempts())
        self.assertEqual(self.run_cli("complete-prd", PRD).returncode, 0)
        rows = self.ledger_rows()
        self.assertEqual(rows[0], old_row)
        self.assertEqual(len(rows), 5)
        self.assertTrue(self.ledger.read_text(encoding="utf-8").endswith("\n"))

    def test_a_failed_ledger_write_aborts_the_close_with_state_untouched(
        self,
    ) -> None:
        # A directory where the ledger file should be makes every open() fail.
        self.ledger.mkdir(parents=True)
        self.write_state(_state_with_attempts())
        before = self.state.read_bytes()
        bak = Path(f"{self.state}.bak")
        bak.write_bytes(b"{}")
        result = self.run_cli("complete-prd", PRD)
        self.assertEqual(result.returncode, 1)
        self.assertIn("rejected: ledger write failed", result.stderr)
        self.assertEqual(self.state.read_bytes(), before)
        self.assertEqual(bak.read_bytes(), b"{}")
        self.assertNotIn("completed_prds", self.load_state()["batch"])

    def test_a_non_array_attempts_field_rejects_the_close_loudly(self) -> None:
        fixture = _state_with_attempts()
        fixture["tasks"][1]["attempts"] = {"attempt": 1}
        self.write_state(fixture)
        before = self.state.read_bytes()
        result = self.run_cli("complete-prd", PRD)
        self.assertEqual(result.returncode, 1)
        self.assertIn("rejected: task 'task-2' attempts is not an array", result.stderr)
        self.assertEqual(self.state.read_bytes(), before)
        self.assertFalse(self.ledger.exists())

    def test_a_state_without_attempts_writes_no_rows_and_still_completes(
        self,
    ) -> None:
        fixture = _state_with_attempts()
        fixture["tasks"] = [{"id": "task-1", "name": "First", "attempts": []}]
        self.write_state(fixture)
        result = self.run_cli("complete-prd", PRD)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.ledger.exists())
        self.assertEqual(
            self.load_state()["batch"]["completed_prds"][-1]["filename"], PRD
        )


if __name__ == "__main__":
    unittest.main()
