#!/usr/bin/env python3
"""Contract test for the design-review hardening (PRD 00039).

Pins the load-bearing lines in design-solution/SKILL.md and run-autopilot/SKILL.md
so the cross-model codex dispatch and the Phase 1.5 empty-review-log gate cannot
silently drift, and binds the dispatch-summary format to the gate regex (they MUST
agree). Modeled on test_doubt_review_prompt_contract.py. Stdlib only; pytest
collects the unittest.TestCase with no config.

RED-first: deleting any pinned line, or drifting the summary format and the gate
regex out of agreement, makes a specific assertion fail.
"""

import re
import unittest
from pathlib import Path

_SKILLS = Path(__file__).resolve().parents[2]
_DESIGN_SKILL = _SKILLS / "design-solution" / "SKILL.md"
_AUTOPILOT_SKILL = _SKILLS / "run-autopilot" / "SKILL.md"

# The exact awk gate regex body pinned in run-autopilot Phase 1.5. This same
# literal is both asserted-present in the SKILL.md (so a regex-body drift there
# fails `test_gate_regex_body_present`) and compiled for the format<->gate
# correspondence check (so a format drift fails `test_format_matches_gate_regex`).
_GATE_REGEX = (
    r"dispatch [0-9]+ \((claude|codex|claude-fallback)\): "
    r"cardinal-sin [0-9]+, blocker [0-9]+, non-blocker [0-9]+, question [0-9]+"
)


def _section(text: str, heading: str) -> str:
    """Return the body of the H2 section whose heading line is exactly `heading`.

    The slice runs from that line to the next line starting with `## `. Inline
    mentions such as "`## Architecture fit` opens with" do not start a line, so
    they do not end it. A pinned phrase found outside its section (an appended
    tail, an HTML comment) must not satisfy the pin, hence the slice.
    """
    start = re.search(rf"^{re.escape(heading)}$", text, re.MULTILINE)
    if start is None:
        raise AssertionError(f"no H2 heading line {heading!r} in the skill file")
    rest = text[start.end() :]
    end = re.search(r"^## ", rest, re.MULTILINE)
    return rest if end is None else rest[: end.start()]


class DesignReviewContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.design = _DESIGN_SKILL.read_text()
        self.autopilot = _AUTOPILOT_SKILL.read_text()

    # --- design-solution: cross-model codex dispatch + pinned summary format ---

    def test_design_solution_pins_summary_line_format(self) -> None:
        self.assertIn(
            "dispatch <n> (<claude|codex|claude-fallback>): "
            "cardinal-sin <c>, blocker <b>, non-blocker <nb>, question <q>",
            self.design,
        )

    def test_design_solution_dispatches_codex(self) -> None:
        self.assertIn("codex-run.sh", self.design)

    def test_design_solution_codex_never_agent_wrapped(self) -> None:
        # The most-regressed failure mode in this codebase: a subagent that shells
        # out to a CLI hangs. Pin that codex runs as a direct background Bash
        # command, never Agent-wrapped — dropping the invariant must fail here.
        self.assertIn("never a Task subagent", self.design)

    def test_design_solution_codex_always_runs_on_clean_dispatch_1(self) -> None:
        self.assertIn("even when dispatch 1 found zero blockers", self.design)

    def test_design_solution_pins_three_dispatch_ceiling(self) -> None:
        # PRD feature "Verification dispatch (ceiling raised to 3)": reverting the
        # ceiling to 2 (deleting the conditional codex verification dispatch 3)
        # must fail here, not slip through green.
        self.assertIn("3-dispatch ceiling", self.design)

    def test_design_solution_has_claude_fallback(self) -> None:
        self.assertIn("claude-fallback", self.design)

    # --- design-solution: rework mode (PRD 00194) ---
    # Every literal is pinned inside its own H2 section, never file-wide: a
    # phrase in an appended tail or an HTML comment must not satisfy the pin.

    def test_rework_mode_takes_a_review_file(self) -> None:
        rework = _section(self.design, "## Rework mode")
        self.assertIn("--rework <review-file>", rework)
        # The frontmatter is where a model learns the argument exists.
        hint = 'argument-hint: "<prd-path> [--rework <review-file>]"'
        self.assertRegex(
            self.design, re.compile("^" + re.escape(hint) + "$", re.MULTILINE)
        )

    def test_rework_output_is_cycle_scoped(self) -> None:
        # One design doc per review cycle, never overwriting the first-pass doc.
        rework_path = "dev/local/designs/<prd-stem>-rework-<cycle>-design.md"
        self.assertIn(rework_path, _section(self.design, "## Rework mode"))
        output = _section(self.design, "## Output")
        self.assertIn(rework_path, output)
        self.assertIn("dev/local/designs/<prd-stem>-design.md", output)

    def test_rework_keeps_the_nine_sections(self) -> None:
        self.assertIn(
            "same nine sections, same headings, same order as step 3",
            _section(self.design, "## Rework mode"),
        )

    def test_rework_architecture_fit_explains_the_prior_fix(self) -> None:
        rework = _section(self.design, "## Rework mode")
        self.assertIn("what the prior fix changed and why it regressed", rework)
        # Cycle 1 has no prior fix; the paragraph still exists with a fixed text.
        self.assertIn("Prior fix: none - there was no prior rework fix.", rework)

    def test_rework_keeps_the_three_dispatch_procedure(self) -> None:
        # Rework mode must not thin the review: same procedure, same ceiling.
        # Section-scoped, or `3-dispatch ceiling` is green from the first-pass text.
        rework = _section(self.design, "## Rework mode")
        self.assertIn("the same 3-dispatch", rework)
        self.assertIn("3-dispatch ceiling", rework)

    def test_rework_summary_line_is_cycle_specific(self) -> None:
        summary = "design-solution: <prd-stem> (rework cycle <n>)"
        self.assertIn(summary, _section(self.design, "## Rework mode"))
        self.assertIn(
            f"In rework mode the first line reads `{summary}`.",
            _section(self.design, "## Exit report (always printed)"),
        )

    def test_rework_contract_is_the_sole_source(self) -> None:
        self.assertIn(
            "is the sole contract source",
            _section(self.design, "## Rework mode"),
        )

    def test_rework_derives_the_work_base_from_the_cycle_1_review(self) -> None:
        # The work base comes from the cycle-1 review's Diff range, not guessed.
        rework = _section(self.design, "## Rework mode")
        self.assertIn("<prd-stem>-review-1.md", rework)
        self.assertIn("Diff range:", rework)

    def test_rework_review_log_ends_with_the_result_line(self) -> None:
        # Section-scoped, or `result: ok` is green from the Exit report block.
        rework = _section(self.design, "## Rework mode")
        self.assertIn("result: ok", rework)
        self.assertIn("result: failed (open cardinal sins/blockers)", rework)
        self.assertIn("last line of `## Review log`", rework)

    def test_rework_doc_names_its_source_review(self) -> None:
        self.assertIn(
            "Source review: <review-file> (head_sha <head_sha>)",
            _section(self.design, "## Rework mode"),
        )

    # --- run-autopilot Phase 1.5: empty-review-log gate ---

    def test_gate_pause_detail(self) -> None:
        self.assertIn(
            "design doc has empty ## Review log (review never ran)", self.autopilot
        )

    def test_gate_bypass_is_net_new_phrase(self) -> None:
        # Pin a phrase unique to THIS gate, not the bare `design_mode == "skip"`
        # (which already appears elsewhere in Phase 1.5) — so the assertion is
        # genuinely RED-first for the new gate's bypass, not vacuously green.
        self.assertIn("bypasses the empty-review-log gate", self.autopilot)

    def test_gate_is_section_scoped(self) -> None:
        self.assertIn("awk '/^## Review log/", self.autopilot)

    def test_gate_regex_body_present(self) -> None:
        # Locks the gate's match pattern body, not just the awk prefix, so a
        # regex-body drift in the SKILL.md fails here.
        self.assertIn(_GATE_REGEX, self.autopilot)

    def test_gate_runs_on_both_continue_paths(self) -> None:
        self.assertIn("on this success path", self.autopilot)
        self.assertIn("on this artifact-reuse path", self.autopilot)

    # --- correspondence: the emitted summary format and the gate regex agree ---

    def test_format_matches_gate_regex(self) -> None:
        pattern = re.compile(_GATE_REGEX)
        self.assertRegex(
            "dispatch 2 (codex): cardinal-sin 0, blocker 0, non-blocker 1, question 0",
            pattern,
        )
        self.assertRegex(
            "dispatch 3 (claude-fallback): "
            "cardinal-sin 1, blocker 0, non-blocker 0, question 0",
            pattern,
        )
        # A bare heading (an empty Review log) must NOT satisfy the gate regex.
        self.assertNotRegex("## Review log", pattern)


if __name__ == "__main__":
    unittest.main()
