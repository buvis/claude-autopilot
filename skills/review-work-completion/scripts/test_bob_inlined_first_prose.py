"""Contract test for Bob's inlined prompt as his first-run shape.

Pins the retry-policy.md / SKILL.md text once Bob's first dispatch always
builds the inlined-context prompt: the inlined-prompt section describes
itself as the dispatch-1 shape, not a retry-only fallback, and no
lack-of-input refusal detection or retry survives in either file.
Text-pinning only: stdlib unittest, no import of any module under test.
"""

from __future__ import annotations

import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
SKILL_MD = SKILL_DIR / "SKILL.md"
RETRY_POLICY = SKILL_DIR / "references" / "retry-policy.md"

# Stable anchor inside the inlined prompt's head block; the section heading
# around it is what the rewrite retitles, so the section is found by content.
INLINED_ANCHOR = "INLINED BELOW as text"


def _enclosing_section(text: str, anchor: str) -> str:
    """Return the `## ` section that contains `anchor`."""
    at = text.index(anchor)
    start = text.rfind("\n## ", 0, at) + 1
    ends = [
        e
        for e in (text.find("\n### ", at), text.find("\n## ", at))
        if e != -1
    ]
    end = min(ends) if ends else len(text)
    return text[start:end]


class BobInlinedFirstProseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skill = SKILL_MD.read_text(encoding="utf-8")
        cls.retry_policy = RETRY_POLICY.read_text(encoding="utf-8")

    def test_first_bob_prompt_is_the_inlined_shape(self) -> None:
        # The inlined-prompt mechanics survive the rewrite...
        self.assertIn(INLINED_ANCHOR, self.retry_policy)
        section = _enclosing_section(self.retry_policy, INLINED_ANCHOR)
        heading = section.splitlines()[0]
        self.assertTrue(heading.startswith("## "), heading)
        # ...but no longer as a retry-only fallback: the heading must not
        # frame the shape as a retry prompt.
        self.assertNotIn("retry", heading.lower())
        # The section must say it is built on Bob's first dispatch.
        lowered = section.lower()
        self.assertTrue(
            "dispatch 1" in lowered or "first dispatch" in lowered,
            "inlined-prompt section does not describe itself as the "
            "dispatch-1 (first dispatch) shape",
        )

    def test_no_lack_of_input_retry_remains(self) -> None:
        # With the inlined shape on dispatch 1 there is no non-inlined first
        # run to detect a refusal against, so neither file may keep the rule.
        for name, text in (
            ("SKILL.md", self.skill),
            ("retry-policy.md", self.retry_policy),
        ):
            with self.subTest(file=name):
                self.assertEqual(text.lower().count("lack-of-input"), 0)

    def test_retry_case_uses_the_retry_verb(self) -> None:
        # The ledger's retry case opens its row with the new CLI verb, not a
        # hand-typed second `start --task` call under the same task.
        at = self.skill.index("Ledger each CLI reviewer dispatch.")
        region = self.skill[at : at + 900]
        self.assertIn("record_dispatch.py retry", region)
        self.assertNotIn(
            'second `start` row under the same `--task`'.replace("`", ""),
            region.replace("`", ""),
        )


if __name__ == "__main__":
    unittest.main()
