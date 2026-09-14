"""Contract tests for the post-00016 review prompt/file shapes.

Replaces test_doubt_review_prompt_contract.py and
test_blind_review_coverage_contract.py, which pinned the retired
`---review-coverage---` block format. The surviving contract is small:
doubt/blind reviewers emit findings plus per-rule `R{n}:` verdict lines, and
the saved review files are validated by check_review_file.py. Stdlib-only.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

_SKILLS = Path(__file__).resolve().parents[2]
# PRD 00109 moved the doubt lens out of run-autopilot/prompts/doubt-review.md
# and into the agent registry. eve.md is now the single source: the native
# doubt persona's system prompt, and the base the codex/Claude-fallback lanes
# assemble from.
_DOUBT_PROMPT = _SKILLS.parent / "agents" / "eve.md"
_DOUBT_RUBRIC = (
    Path(__file__).resolve().parent.parent / "references" / "doubt-review-rubric.md"
)
_BLIND_SKILL = _SKILLS / "review-blindly" / "SKILL.md"
_PHASE_REVIEW = (
    Path(__file__).resolve().parent.parent / "references" / "phase-review.md"
)
_AGENTS = _SKILLS.parent / "agents"
_RUN_AUTOPILOT_SKILL = _SKILLS / "run-autopilot" / "SKILL.md"
_SHELL_RULES_HEADING = "## Shell Command Rules"

# The Bash tool-discipline paragraph every Bash-bearing persona must carry
# verbatim, and the orchestrator skill must lead its Shell Command Rules with.
# Read-only personas never touch Bash, so they must not carry it.
TOOL_DISCIPLINE = (
    "Never call bash `head`, `tail`, `cat`, `grep`, or `find` - a hook blocks "
    "them. Use the Read tool (offset/limit), `rg`, or `rg --files` instead. "
    "Never pipe between heterogeneous commands and never combine an inspection "
    "(read, list, search, diff) with a test, lint or build invocation in one "
    "Bash call - run them as separate calls. Pass an explicit `timeout` on "
    "every Bash call: 60000 ms for an inspection, 300000 ms for a lint run or "
    "a narrow test run, 600000 ms for a full suite or a full build."
)

_BASH_BEARING_PERSONAS = ("alice.md", "blake.md", "eve.md", "victor.md")
_READ_ONLY_PERSONAS = (
    "pat.md",
    "rita.md",
    "cora.md",
    "grace.md",
    "toby.md",
    "mallory.md",
    "trent.md",
)

# The entry shape both `autonomous_decisions` append instructions must show
# verbatim. The state schema also accepts `question` for `issue`, `disposition`
# for `action` and `resolution` for `reason`, but the instruction shows the
# PRIMARY key of each pair only — so this literal deliberately does not accept
# an alias in a primary key's place.
_DECISION_ENTRY_SHAPE = (
    '{"cycle": <state.cycle>, "issue": "...", "severity": "...", '
    '"action": "...", "reason": "..."}'
)

# A short, stable slice of each append instruction's own text. These anchors are
# part of the contract: they locate the two sites, and requiring them means an
# instruction cannot be DELETED to satisfy the shape check. A whole-file count
# would accept two copies anywhere — including a trailing HTML comment no reader
# of the instruction ever sees.
_APPEND_SITE_ANCHORS = (
    "Record it in `autonomous_decisions` as `routed to verification`",
    "Log every decision in the state file",
)

# How far after an anchor the shape still counts as belonging to that site.
# Roughly a paragraph; far short of the thousands of characters separating the
# two sites, so neither window can be satisfied by the other site's copy.
_SHAPE_WINDOW = 600


def _rubric_rule_ids(text: str) -> set[str]:
    # Prefix-agnostic since PRD 00108 split the shared R namespace into
    # consensus R, blind B and doubt D. Hardcoding `R` here would silently
    # return an empty set from BOTH sides of the doubt comparison below, and
    # `rubric_ids <= prompt_ids` would then pass vacuously.
    return set(re.findall(r"^([RDB]\d+):", text, re.MULTILINE))


class DoubtPromptContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.prompt = _DOUBT_PROMPT.read_text()

    def test_prompt_requires_fix_verify_known_buckets(self) -> None:
        for bucket in ("FIX", "VERIFY", "KNOWN"):
            self.assertIn(bucket, self.prompt)

    def test_prompt_rubric_matches_rubric_reference(self) -> None:
        rubric_ids = _rubric_rule_ids(_DOUBT_RUBRIC.read_text())
        self.assertEqual(rubric_ids, {"D1", "D2", "D3", "D4", "D5"})
        prompt_ids = _rubric_rule_ids(self.prompt)
        self.assertTrue(
            rubric_ids <= prompt_ids,
            f"prompt must require every rubric rule; missing {rubric_ids - prompt_ids}",
        )

    def test_doubt_prompt_carries_no_stale_r_prefixed_ids(self) -> None:
        # The rename is prefix-only, so a surviving R-id here means a rule was
        # half-migrated — the emit-verbatim block and the rule list must agree.
        stale = sorted(re.findall(r"^(R\d+):", self.prompt, re.MULTILINE))
        self.assertEqual(stale, [], f"doubt persona still emits {stale}")

    def test_prompt_has_no_retired_coverage_block(self) -> None:
        self.assertNotIn(
            "---review-coverage---",
            self.prompt,
            "PRD 00016 retired the coverage block; reviewers emit findings + R lines only",
        )


class BlindSkillContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.skill = _BLIND_SKILL.read_text()

    def test_blind_skill_gates_with_check_review_file(self) -> None:
        self.assertIn("check_review_file.py", self.skill)
        self.assertNotIn("review_coverage.py", self.skill)

    def test_blind_skill_requires_rubric_verdict_lines(self) -> None:
        self.assertIn("PER-RULE VERDICTS ARE MANDATORY", self.skill)

    def test_blind_skill_has_no_retired_coverage_block(self) -> None:
        self.assertNotIn("---review-coverage---", self.skill)

    def test_blind_skill_writes_verdict_and_tests_lines(self) -> None:
        self.assertIn("Verdict:", self.skill)
        self.assertIn("Tests:", self.skill)


class PhaseReviewDecisionShapeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.phase_review = _PHASE_REVIEW.read_text()

    def test_phase_review_append_names_the_decision_keys(self) -> None:
        # "Record it in autonomous_decisions" without naming the keys is how
        # cycle-only entries got written. Both append sites — the routed-to-
        # verification row and the log-every-decision paragraph — must carry the
        # shape where the reader of that instruction meets it, so each site is
        # located by its own anchor and searched only in the window after it.
        for anchor in _APPEND_SITE_ANCHORS:
            # `find` returns the FIRST match, so a second copy of an anchor
            # would shadow the real site: a decoy paragraph repeating the
            # anchor and the shape would satisfy the window while the genuine
            # instruction stayed shapeless.
            self.assertEqual(
                self.phase_review.count(anchor),
                1,
                f"the append instruction {anchor!r} must appear exactly once, "
                "so the window below searches the site a reader actually meets",
            )
            # The count above already proves the anchor is present, so `find`
            # cannot answer -1 here.
            start = self.phase_review.find(anchor)
            window = self.phase_review[start : start + len(anchor) + _SHAPE_WINDOW]
            self.assertIn(
                _DECISION_ENTRY_SHAPE,
                window,
                f"the append instruction {anchor!r} must show the entry shape "
                "verbatim in its own paragraph, not elsewhere in the file",
            )

    def test_phase_review_never_instructs_the_convergence_append(self) -> None:
        # The loop driver (`cli/loop.py`, `Loop._append_metrics`) writes the
        # `review_converged` row itself when a review session exits to done.
        # Prose that still tells the model to printf the row would write it
        # twice, so the section may only DESCRIBE the wrapper's row, and both
        # exit sites must say so where the reader meets them.
        text = self.phase_review
        self.assertIsNone(
            re.search(r"printf.*loop-metrics", text),
            "phase-review.md must not instruct a printf append to loop-metrics",
        )
        self.assertNotIn(
            "Append the `review_converged` line",
            text,
            "phase-review.md must not instruct appending the review_converged row",
        )
        self.assertIn(
            "cli/loop.py",
            text,
            "phase-review.md must name the loop driver as the row's writer",
        )
        self.assertGreaterEqual(
            text.count("the wrapper records the convergence row at review-phase exit"),
            2,
            "both exit sites (converged and cap-out) must say the wrapper "
            "records the row",
        )


class ToolDisciplineContractTests(unittest.TestCase):
    def test_bash_bearing_personas_carry_tool_discipline(self) -> None:
        for name in _BASH_BEARING_PERSONAS:
            text = (_AGENTS / name).read_text()
            self.assertEqual(
                text.count(TOOL_DISCIPLINE),
                1,
                f"agents/{name} must carry TOOL_DISCIPLINE exactly once",
            )
        for name in _READ_ONLY_PERSONAS:
            text = (_AGENTS / name).read_text()
            self.assertNotIn(
                TOOL_DISCIPLINE,
                text,
                f"agents/{name} is read-only and must not carry TOOL_DISCIPLINE",
            )

    def test_orchestrator_skill_carries_tool_discipline(self) -> None:
        skill = _RUN_AUTOPILOT_SKILL.read_text()
        self.assertEqual(
            skill.count(TOOL_DISCIPLINE),
            1,
            "run-autopilot/SKILL.md must carry TOOL_DISCIPLINE exactly once",
        )
        lines = skill.splitlines()
        self.assertIn(_SHELL_RULES_HEADING, lines)
        after = lines[lines.index(_SHELL_RULES_HEADING) + 1 :]
        first_line = next(line for line in after if line.strip())
        self.assertEqual(
            first_line,
            f"- {TOOL_DISCIPLINE}",
            f"TOOL_DISCIPLINE must be the first bullet under {_SHELL_RULES_HEADING}",
        )


if __name__ == "__main__":
    unittest.main()
