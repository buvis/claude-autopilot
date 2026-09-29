"""Tests for the HEADROOM_MARGIN and time term on `_headroom_exhausted`
(PRD 00218 follow-up).

Split out of test_autopilot_cap_headroom.py to keep that file under the
800-line limit; shares `_load_hook_module` with that module.
"""

from __future__ import annotations

import unittest

from test_autopilot_context_cap_hook import _load_hook_module


class HeadroomMarginTests(unittest.TestCase):
    def test_margin_hands_off_when_left_is_under_five_quarters_of_the_last_task(
        self,
    ) -> None:
        """173K left of USAGE_CAP (total=327_000) against a last task that
        cost 164K: HEADROOM_MARGIN's five-quarters threshold is 205K, and
        173K < 205K, so the rule fires even though 173K > 164K plainly."""
        module = _load_hook_module()
        self.assertTrue(module._headroom_exhausted(327_000, None, 164_000, 200))

    def test_time_term_hands_off_when_the_deadline_is_near(self) -> None:
        """1000s left against a last task whose wall time was 900s: the
        margined threshold is 900 * 1.25 = 1125, and 1000 < 1125, so the
        time term alone fires the rule."""
        module = _load_hook_module()
        self.assertTrue(
            module._headroom_exhausted(
                None, None, 150_000, 200, secs_left=1000, last_wall=900
            )
        )

    def test_time_term_is_inert_without_a_deadline(self) -> None:
        """With no secs_left, the time term contributes nothing: a case
        that is False on the usage/calls terms alone stays False no matter
        how tight last_wall is."""
        module = _load_hook_module()
        self.assertFalse(
            module._headroom_exhausted(
                300_000, 120, 150_000, 200, secs_left=None, last_wall=900
            )
        )

    def test_time_term_is_inert_without_a_completed_task(self) -> None:
        """With no last_wall (no completed task's wall time recorded), the
        time term contributes nothing: a case that is False on the
        usage/calls terms alone stays False no matter how tight secs_left
        is."""
        module = _load_hook_module()
        self.assertFalse(
            module._headroom_exhausted(
                300_000, 120, 150_000, 200, secs_left=1000, last_wall=None
            )
        )

    def test_malformed_deadline_drops_the_time_term(self) -> None:
        """secs_left=None (what a malformed _AUTOPILOT_SESSION_DEADLINE
        resolves to upstream) makes the time term never fire, regardless of
        last_wall's value."""
        module = _load_hook_module()
        with_no_last_wall = module._headroom_exhausted(
            300_000, 120, 150_000, 200, secs_left=None, last_wall=None
        )
        with_a_tiny_last_wall = module._headroom_exhausted(
            300_000, 120, 150_000, 200, secs_left=None, last_wall=1
        )
        self.assertEqual(with_no_last_wall, with_a_tiny_last_wall)
        self.assertFalse(with_no_last_wall)


if __name__ == "__main__":
    unittest.main()
