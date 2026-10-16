#!/usr/bin/env python3
"""Tests for cli/review_stage._gate_result_line's lock-timeout message
(split from test_review_stage.py, which is already past the 800-line
limit).

The lock-timeout branch reports how long the LOCK wait was, so it must
interpolate verification.GATE_LOCK_TIMEOUT_S (the lock-wait budget), not
verification.GATE_TIMEOUT_S (the gate's own run-timeout) — the two
constants have different values.
"""

from __future__ import annotations

import sys

import pytest

from cli import review_stage, verification


def test_gate_result_line_lock_timeout_reports_lock_timeout_constant() -> None:
    result = {"lock_timeout": True}

    line = review_stage._gate_result_line(result)

    assert str(verification.GATE_LOCK_TIMEOUT_S) in line
    assert str(verification.GATE_TIMEOUT_S) not in line


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
