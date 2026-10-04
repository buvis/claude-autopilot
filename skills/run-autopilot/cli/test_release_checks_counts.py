"""Tests for dev/bin/release-checks' count-accumulation helpers (PRD 00256).

Runs the real `run_pytest`/`run_harness`/`run_gather_harness` functions
sourced out of the live script against synthetic commands, so a block's
real reported counts -- not a count of its own `echo "[checks]"` header
lines -- are what the final summary line carries, and a failing block no
longer aborts the whole run.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

_RELEASE_CHECKS = Path(__file__).resolve().parents[3] / "dev" / "bin" / "release-checks"


def _run_helpers(body: str) -> str:
    """Sources only the helper-function definitions out of the live script
    (everything from `set -uo pipefail` up to the first `echo "[checks]"`
    call), then runs `body` against them. Returns combined stdout+stderr."""
    text = _RELEASE_CHECKS.read_text()
    marker = '\necho "[checks] '
    helpers = text[: text.index(marker)]
    script = f"{helpers}\n{body}\n"
    proc = subprocess.run(
        ["bash", "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.stdout + proc.stderr


def test_summary_counts_tests_not_check_blocks() -> None:
    out = _run_helpers(
        """
        run_pytest bash -c 'echo "3 passed, 1 skipped in 0.01s"; exit 0'
        run_pytest bash -c 'echo "5 passed in 0.02s"; exit 0'
        echo "PASS $TOTAL_PASS FAIL $TOTAL_FAIL SKIP $TOTAL_SKIP EXIT 0"
        """
    )
    # Real test totals (3+5 passed, 1 skipped), never the two-call count of
    # the script's own echo "[checks]" header lines.
    assert "PASS 8 FAIL 0 SKIP 1 EXIT 0" in out


def test_summary_line_printed_on_failure() -> None:
    out = _run_helpers(
        """
        run_pytest bash -c 'echo "2 failed, 1 passed in 0.01s"; exit 1'
        EXIT_CODE=0
        if [[ "$TOTAL_FAIL" -ne 0 || "$INFRA_FAIL" -ne 0 ]]; then EXIT_CODE=1; fi
        echo "PASS $TOTAL_PASS FAIL $TOTAL_FAIL SKIP $TOTAL_SKIP EXIT $EXIT_CODE"
        """
    )
    assert "PASS 1 FAIL 2 SKIP 0 EXIT 1" in out


def test_infrastructure_failure_is_not_counted_as_a_test_failure() -> None:
    out = _run_helpers(
        """
        run_gather_harness bash -c 'echo "PASS: a"; exit 1'
        EXIT_CODE=0
        if [[ "$TOTAL_FAIL" -ne 0 || "$INFRA_FAIL" -ne 0 ]]; then EXIT_CODE=1; fi
        echo "PASS $TOTAL_PASS FAIL $TOTAL_FAIL SKIP $TOTAL_SKIP EXIT $EXIT_CODE"
        """
    )
    # One real PASS: line counted, zero invented failures, but EXIT still
    # non-zero because the harness itself exited non-zero after reporting.
    assert "PASS 1 FAIL 0 SKIP 0 EXIT 1" in out


def test_gather_context_harness_counts_pass_lines() -> None:
    out = _run_helpers(
        """
        run_gather_harness bash -c 'echo "PASS: one"; echo "PASS: two"; exit 0'
        echo "PASS $TOTAL_PASS FAIL $TOTAL_FAIL SKIP $TOTAL_SKIP EXIT 0"
        """
    )
    assert "PASS 2 FAIL 0 SKIP 0 EXIT 0" in out
