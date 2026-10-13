#!/usr/bin/env python3
"""Tests for cli/catchup_probe.py's probe(): batch-scoped gh/engram verdicts.

Written from the design contract only. Every subprocess and PATH lookup goes
through injected fakes - no real gh or engram binary ever runs.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cli import catchup_probe

FIRST_NOW = "2026-10-13T08:00:00Z"
LATER_NOW = "2026-10-13T09:30:00Z"
GH_ARGV = ["gh", "auth", "status"]
ENGRAM_ARGV = ["engram", "status", "--scope", "repo"]
UNREGISTERED = "engram: error: not inside a registered repo (cwd /x)\n"


class FakeRun:
    """Stands in for subprocess.run. `outcomes` maps the binary name to a
    (returncode, stderr) pair or to an exception instance to raise."""

    def __init__(self, outcomes: dict) -> None:
        self.outcomes = outcomes
        self.calls: list[tuple[list[str], dict]] = []

    def __call__(self, argv, **kwargs) -> subprocess.CompletedProcess:
        self.calls.append((list(argv), kwargs))
        outcome = self.outcomes[argv[0]]
        if isinstance(outcome, BaseException):
            raise outcome
        returncode, stderr = outcome
        return subprocess.CompletedProcess(argv, returncode, "", stderr)

    def binaries(self) -> list[str]:
        return [argv[0] for argv, _ in self.calls]


def _which_all(name: str) -> str | None:
    return f"/usr/bin/{name}"


def _which_without(missing: str):
    return lambda name: None if name == missing else f"/usr/bin/{name}"


class ProbeTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "repo"
        autopilot_dir = self.root / "docs" / "dev" / "project-management" / "autopilot"
        autopilot_dir.mkdir(parents=True)
        self.state_path = autopilot_dir / "state.json"

    def _write_state(self, state: dict) -> None:
        self.state_path.write_text(json.dumps(state), encoding="utf-8")

    def _read_state(self) -> dict:
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def _probe(self, run: FakeRun, *, which=_which_all, now: str = FIRST_NOW) -> dict:
        return catchup_probe.probe(
            self.state_path,
            run=run,
            which=which,
            now=lambda: now,
        )


class GhVerdictTests(ProbeTestCase):
    def test_probe_records_unauthenticated_then_reuses_within_batch(self) -> None:
        self._write_state({"batch": {"id": "B1"}})
        first_run = FakeRun({"gh": (1, "not logged in"), "engram": (0, "")})

        first = self._probe(first_run)

        self.assertEqual(first, {"skip": ["github-state"]})
        self.assertEqual(sorted(first_run.binaries()), ["engram", "gh"])
        recorded = {
            "batch_id": "B1",
            "gh": "unauthenticated",
            "engram": "ok",
            "checked_at": FIRST_NOW,
        }
        self.assertEqual(self._read_state()["catchup_probe"], recorded)

        # Fresh probes would now say "ok" - only reuse keeps github-state skipped.
        second_run = FakeRun({"gh": (0, ""), "engram": (0, "")})
        second = self._probe(second_run, now=LATER_NOW)

        self.assertEqual(second, {"skip": ["github-state"]})
        self.assertEqual(
            second_run.calls,
            [],
            "the same batch.id must not re-run gh or engram",
        )
        self.assertEqual(
            self._read_state()["catchup_probe"],
            recorded,
            "a covering probe is not rewritten, so checked_at keeps the first time",
        )

    def test_new_batch_reprobes(self) -> None:
        self._write_state(
            {
                "batch": {"id": "B2"},
                "catchup_probe": {
                    "batch_id": "B1",
                    "gh": "unauthenticated",
                    "engram": "ok",
                    "checked_at": FIRST_NOW,
                },
            },
        )
        run = FakeRun({"gh": (0, ""), "engram": (0, "")})

        out = self._probe(run, now=LATER_NOW)

        self.assertEqual(out, {"skip": []})
        self.assertEqual(sorted(run.binaries()), ["engram", "gh"])
        self.assertEqual(
            self._read_state()["catchup_probe"],
            {"batch_id": "B2", "gh": "ok", "engram": "ok", "checked_at": LATER_NOW},
        )

    def test_both_ok_skips_nothing_and_runs_each_probe_with_a_15s_timeout_in_the_repo_root(
        self,
    ) -> None:
        self._write_state({"batch": {"id": "B1"}, "phase": "build"})
        run = FakeRun({"gh": (0, ""), "engram": (0, "")})

        out = self._probe(run)

        self.assertEqual(out, {"skip": []})
        state = self._read_state()
        self.assertEqual(
            state["catchup_probe"],
            {"batch_id": "B1", "gh": "ok", "engram": "ok", "checked_at": FIRST_NOW},
        )
        self.assertEqual(state["batch"], {"id": "B1"})
        self.assertEqual(state["phase"], "build")
        self.assertEqual(sorted(argv for argv, _ in run.calls), [ENGRAM_ARGV, GH_ARGV])
        for argv, kwargs in run.calls:
            with self.subTest(argv[0]):
                self.assertIs(kwargs.get("capture_output"), True)
                self.assertIs(kwargs.get("text"), True)
                self.assertEqual(kwargs.get("timeout"), 15)
                self.assertEqual(Path(kwargs["cwd"]).resolve(), self.root.resolve())

    def test_a_batch_id_that_only_shares_a_prefix_is_a_new_batch(self) -> None:
        for recorded_id, current_id in (("B1", "B10"), ("B", "B1")):
            with self.subTest(f"{recorded_id} -> {current_id}"):
                self._write_state(
                    {
                        "batch": {"id": current_id},
                        "catchup_probe": {
                            "batch_id": recorded_id,
                            "gh": "unauthenticated",
                            "engram": "unregistered",
                            "checked_at": FIRST_NOW,
                        },
                    },
                )
                run = FakeRun({"gh": (0, ""), "engram": (0, "")})

                out = self._probe(run, now=LATER_NOW)

                self.assertEqual(out, {"skip": []})
                self.assertEqual(sorted(run.binaries()), ["engram", "gh"])
                self.assertEqual(
                    self._read_state()["catchup_probe"],
                    {
                        "batch_id": current_id,
                        "gh": "ok",
                        "engram": "ok",
                        "checked_at": LATER_NOW,
                    },
                )

    def test_recorded_gh_absent_is_reused_within_batch(self) -> None:
        recorded = {
            "batch_id": "B1",
            "gh": "absent",
            "engram": "ok",
            "checked_at": FIRST_NOW,
        }
        self._write_state({"batch": {"id": "B1"}, "catchup_probe": recorded})
        run = FakeRun({"gh": (0, ""), "engram": (0, "")})

        out = self._probe(run, now=LATER_NOW)

        self.assertEqual(out, {"skip": ["github-state"]})
        self.assertEqual(run.calls, [])
        self.assertEqual(self._read_state()["catchup_probe"], recorded)

    def test_probes_run_in_the_parent_of_a_non_standard_autopilot_dir(self) -> None:
        autopilot_dir = self.root / "autopilot"
        autopilot_dir.mkdir()
        self.state_path = autopilot_dir / "state.json"
        self._write_state({"batch": {"id": "B1"}})
        run = FakeRun({"gh": (0, ""), "engram": (0, "")})

        self._probe(run)

        self.assertEqual(sorted(run.binaries()), ["engram", "gh"])
        for argv, kwargs in run.calls:
            with self.subTest(argv[0]):
                self.assertEqual(Path(kwargs["cwd"]).resolve(), self.root.resolve())

    def test_gh_is_absent_without_running_it_when_which_finds_no_gh(self) -> None:
        self._write_state({"batch": {"id": "B1"}})
        run = FakeRun({"gh": (0, ""), "engram": (0, "")})

        out = self._probe(run, which=_which_without("gh"))

        self.assertEqual(out, {"skip": ["github-state"]})
        self.assertEqual(run.binaries(), ["engram"])
        recorded = self._read_state()["catchup_probe"]
        self.assertEqual((recorded["gh"], recorded["engram"]), ("absent", "ok"))

    def test_gh_timeout_or_oserror_is_absent_not_unauthenticated(self) -> None:
        for label, failure in (
            ("timeout", subprocess.TimeoutExpired(GH_ARGV, 15)),
            ("vanished binary", FileNotFoundError(2, "No such file", "gh")),
            ("not executable", PermissionError(13, "Permission denied", "gh")),
        ):
            with self.subTest(label):
                self._write_state({"batch": {"id": f"B-{label}"}})
                run = FakeRun({"gh": failure, "engram": (0, "")})

                out = self._probe(run)

                self.assertEqual(out, {"skip": ["github-state"]})
                self.assertEqual(self._read_state()["catchup_probe"]["gh"], "absent")


class EngramVerdictTests(ProbeTestCase):
    def test_engram_unregistered_from_stderr(self) -> None:
        self._write_state({"batch": {"id": "B1"}})
        run = FakeRun({"gh": (0, ""), "engram": (1, UNREGISTERED)})

        out = self._probe(run)

        self.assertEqual(out, {"skip": ["engram"]})
        self.assertEqual(
            self._read_state()["catchup_probe"],
            {
                "batch_id": "B1",
                "gh": "ok",
                "engram": "unregistered",
                "checked_at": FIRST_NOW,
            },
        )

    def test_engram_unregistered_reuses_within_batch(self) -> None:
        self._write_state({"batch": {"id": "B1"}})
        self._probe(FakeRun({"gh": (0, ""), "engram": (1, UNREGISTERED)}))
        recorded = self._read_state()["catchup_probe"]

        second_run = FakeRun({"gh": (0, ""), "engram": (0, "")})
        out = self._probe(second_run, now=LATER_NOW)

        self.assertEqual(out, {"skip": ["engram"]})
        self.assertEqual(second_run.calls, [])
        self.assertEqual(self._read_state()["catchup_probe"], recorded)

    def test_recorded_engram_absent_is_reused_within_batch(self) -> None:
        recorded = {
            "batch_id": "B1",
            "gh": "ok",
            "engram": "absent",
            "checked_at": FIRST_NOW,
        }
        self._write_state({"batch": {"id": "B1"}, "catchup_probe": recorded})
        run = FakeRun({"gh": (0, ""), "engram": (0, "")})

        out = self._probe(run, now=LATER_NOW)

        self.assertEqual(out, {"skip": ["engram"]})
        self.assertEqual(run.calls, [])
        self.assertEqual(self._read_state()["catchup_probe"], recorded)

    def test_engram_new_batch_reprobes(self) -> None:
        self._write_state(
            {
                "batch": {"id": "B2"},
                "catchup_probe": {
                    "batch_id": "B1",
                    "gh": "ok",
                    "engram": "unregistered",
                    "checked_at": FIRST_NOW,
                },
            },
        )
        run = FakeRun({"gh": (0, ""), "engram": (0, "")})

        out = self._probe(run, now=LATER_NOW)

        self.assertEqual(out, {"skip": []})
        self.assertIn("engram", run.binaries())
        self.assertEqual(
            self._read_state()["catchup_probe"],
            {"batch_id": "B2", "gh": "ok", "engram": "ok", "checked_at": LATER_NOW},
        )

    def test_engram_nonzero_exit_without_the_unregistered_marker_is_ok(self) -> None:
        self._write_state({"batch": {"id": "B1"}})
        run = FakeRun({"gh": (0, ""), "engram": (3, "2 stale rows\n")})

        out = self._probe(run)

        self.assertEqual(out, {"skip": []})
        self.assertEqual(self._read_state()["catchup_probe"]["engram"], "ok")

    def test_engram_verdict_reads_the_stderr_marker_not_the_exit_code(self) -> None:
        for label, outcome, verdict, skip in (
            ("exit 1 without the marker", (1, "2 stale rows\n"), "ok", []),
            ("marker on exit 2", (2, UNREGISTERED), "unregistered", ["engram"]),
        ):
            with self.subTest(label):
                self._write_state({"batch": {"id": f"B-{label}"}})
                run = FakeRun({"gh": (0, ""), "engram": outcome})

                out = self._probe(run)

                self.assertEqual(out, {"skip": skip})
                self.assertEqual(self._read_state()["catchup_probe"]["engram"], verdict)

    def test_engram_is_absent_without_running_it_when_which_finds_no_engram(
        self,
    ) -> None:
        self._write_state({"batch": {"id": "B1"}})
        run = FakeRun({"gh": (0, ""), "engram": (0, "")})

        out = self._probe(run, which=_which_without("engram"))

        self.assertEqual(out, {"skip": ["engram"]})
        self.assertEqual(run.binaries(), ["gh"])
        self.assertEqual(self._read_state()["catchup_probe"]["engram"], "absent")

    def test_engram_timeout_or_oserror_is_absent(self) -> None:
        for label, failure in (
            ("timeout", subprocess.TimeoutExpired(ENGRAM_ARGV, 15)),
            ("vanished binary", FileNotFoundError(2, "No such file", "engram")),
            ("not executable", PermissionError(13, "Permission denied", "engram")),
        ):
            with self.subTest(label):
                self._write_state({"batch": {"id": f"B-{label}"}})
                run = FakeRun({"gh": (0, ""), "engram": failure})

                out = self._probe(run)

                self.assertEqual(out, {"skip": ["engram"]})
                self.assertEqual(
                    self._read_state()["catchup_probe"]["engram"],
                    "absent",
                )


class BatchScopeTests(ProbeTestCase):
    def test_both_failing_skips_github_state_then_engram(self) -> None:
        self._write_state({"batch": {"id": "B1"}})
        run = FakeRun({"gh": (1, ""), "engram": (1, UNREGISTERED)})

        self.assertEqual(self._probe(run), {"skip": ["github-state", "engram"]})

    def test_a_state_without_a_batch_id_probes_under_no_batch_and_reuses_it(
        self,
    ) -> None:
        for label, state in (("no batch", {}), ("batch without id", {"batch": {}})):
            with self.subTest(label):
                self._write_state(state)
                self._probe(FakeRun({"gh": (1, ""), "engram": (0, "")}))
                self.assertEqual(
                    self._read_state()["catchup_probe"],
                    {
                        "batch_id": "no-batch",
                        "gh": "unauthenticated",
                        "engram": "ok",
                        "checked_at": FIRST_NOW,
                    },
                )

                again = FakeRun({"gh": (0, ""), "engram": (0, "")})
                self.assertEqual(self._probe(again), {"skip": ["github-state"]})
                self.assertEqual(again.calls, [])

    def test_a_state_without_a_batch_id_does_not_reuse_a_real_batch_record(
        self,
    ) -> None:
        self._write_state(
            {
                "catchup_probe": {
                    "batch_id": "B1",
                    "gh": "unauthenticated",
                    "engram": "unregistered",
                    "checked_at": FIRST_NOW,
                },
            },
        )
        run = FakeRun({"gh": (0, ""), "engram": (0, "")})

        out = self._probe(run, now=LATER_NOW)

        self.assertEqual(out, {"skip": []})
        self.assertEqual(sorted(run.binaries()), ["engram", "gh"])
        self.assertEqual(
            self._read_state()["catchup_probe"],
            {
                "batch_id": "no-batch",
                "gh": "ok",
                "engram": "ok",
                "checked_at": LATER_NOW,
            },
        )


if __name__ == "__main__":
    unittest.main()
