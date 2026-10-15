#!/usr/bin/env python3
"""Doc-contract test (finding 26): every subcommand registered in
cli.__main__._SUBCOMMANDS must be named by its literal "autopilot <verb>"
invocation form in at least one operator-facing reference doc
(references/*.md or SKILL.md).

The hazard: a subcommand can be fully wired into the registry - and even
documented in cli/__main__.py's own module docstring, which lists names
without the "autopilot " prefix (e.g. just "defer     --state --prd --batch
--json") - without ever being given its actual invocation form anywhere a
human or an autopilot session reads operator-facing docs. "autopilot defer"
was the known instance of this gap when this test was written: the
subcommand existed and worked, but the string "autopilot defer" appeared
nowhere under references/ or in SKILL.md. The same PRD that surfaced the gap
went on to add "autopilot defer" to three reference files, so this test now
guards against that regression recurring rather than describing a live gap.
"""

from __future__ import annotations

import argparse
import sys
import unittest
from pathlib import Path

_CLI_DIR = Path(__file__).resolve().parent
_SKILL_ROOT = _CLI_DIR.parent
_REFERENCES_DIR = _SKILL_ROOT / "references"
_SKILL_MD = _SKILL_ROOT / "SKILL.md"

sys.path.insert(0, str(_SKILL_ROOT))

from cli.__main__ import _SUBCOMMANDS


def _doc_files() -> list[Path]:
    """Every *.md file directly under references/, plus SKILL.md.

    Deliberately excludes cli/__main__.py's own module docstring: that
    docstring already lists every subcommand name in prose without the
    "autopilot " prefix, so including it here would let every key pass
    trivially regardless of whether the live operator-facing reference docs
    actually name the "autopilot <verb>" invocation.
    """
    files = sorted(_REFERENCES_DIR.glob("*.md"))
    files.append(_SKILL_MD)
    return files


class DocContractTests(unittest.TestCase):
    def test_every_registered_subcommand_has_an_autopilot_invocation_in_the_docs(
        self,
    ) -> None:
        contents = [doc.read_text(encoding="utf-8") for doc in _doc_files()]
        undocumented = [
            key
            for key in _SUBCOMMANDS
            if not any(f"autopilot {key}" in text for text in contents)
        ]
        self.assertEqual(
            undocumented,
            [],
            "subcommand(s) missing an 'autopilot <verb>' invocation in "
            f"references/*.md or SKILL.md: {undocumented}",
        )

    def test_state_schema_cli_rows_match_the_parsers(self) -> None:
        # Stub 00301 (PRD 00278 cycle 2): state-schema.md's rows spelled
        # `group-rework <state.json>` and `review-stage <state.json>
        # <review-file>`, while the real parsers take `--findings <path>`
        # and `--cycle-id`/`--gate-command`. The doc must name the real
        # argv.
        from cli import __main__ as cli_main

        text = (_REFERENCES_DIR / "state-schema.md").read_text(encoding="utf-8")
        group_rework_line = next(
            line for line in text.splitlines()
            if line.startswith("- `autopilot group-rework")
        )
        review_stage_line = next(
            line for line in text.splitlines()
            if line.startswith("- `autopilot review-stage")
        )

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="cmd")
        cli_main._add_group_rework(subparsers)
        cli_main._add_review_stage(subparsers)
        group_rework_required = {
            opt
            for action in subparsers.choices["group-rework"]._actions
            for opt in action.option_strings
            if action.required
        }
        review_stage_required = {
            opt
            for action in subparsers.choices["review-stage"]._actions
            for opt in action.option_strings
            if action.required
        }

        self.assertEqual(group_rework_required, {"--findings"})
        self.assertIn("--findings", group_rework_line)
        self.assertEqual(review_stage_required, {"--cycle-id", "--gate-command"})
        self.assertIn("--cycle-id", review_stage_line)
        self.assertIn("--gate-command", review_stage_line)


if __name__ == "__main__":
    unittest.main()
