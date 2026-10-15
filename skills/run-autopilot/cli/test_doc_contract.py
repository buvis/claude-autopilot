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
import re
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
            line
            for line in text.splitlines()
            if line.startswith("- `autopilot group-rework")
        )
        review_stage_line = next(
            line
            for line in text.splitlines()
            if line.startswith("- `autopilot review-stage")
        )

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="cmd")
        cli_main._add_group_rework(subparsers)
        cli_main._add_review_stage(subparsers)

        def surface(verb: str) -> tuple[set[str], set[str], list]:
            actions = subparsers.choices[verb]._actions
            required = {
                opt
                for action in actions
                for opt in action.option_strings
                if action.required
            }
            optional = {
                opt
                for action in actions
                for opt in action.option_strings
                if not action.required and opt not in ("-h", "--help")
            }
            positionals = [
                action
                for action in actions
                if not action.option_strings
                and not isinstance(action, argparse._SubParsersAction)
            ]
            return required, optional, positionals

        def check_line(verb: str, invocation: str) -> None:
            required, optional, positionals = surface(verb)
            self.assertEqual(positionals, [], f"{verb} parser grew a positional")
            unbracketed = re.sub(r"\[[^\]]*\]", "", invocation)
            bracketed = {
                o
                for g in re.findall(r"\[[^\]]*\]", invocation)
                for o in re.findall(r"--[\w-]+", g)
            }
            bare = set(re.findall(r"--[\w-]+", unbracketed))
            for opt in sorted(bracketed | bare):
                self.assertIn(opt, required | optional, f"{verb}: unknown {opt}")
            for opt in sorted(bracketed):
                self.assertIn(opt, optional, f"{verb}: {opt} bracketed but required")
            for opt in sorted(bare - required):
                self.fail(f"{verb}: optional {opt} presented as required")
            for opt in sorted(required - bare):
                self.fail(f"{verb}: required {opt} missing or bracketed")
            leftover = re.sub(r"--[\w-]+\s+<[^>]*>", "", unbracketed)
            self.assertNotRegex(
                leftover,
                r"<[^>]*>",
                f"{verb}: bare positional placeholder remains",
            )

        self.assertEqual(surface("group-rework")[0], {"--findings"})
        self.assertEqual(surface("review-stage")[0], {"--cycle-id", "--gate-command"})
        check_line("group-rework", group_rework_line.split("`")[1])
        check_line("review-stage", review_stage_line.split("`")[1])

        base = "autopilot review-stage --cycle-id <id> --gate-command <cmd>"
        for label, bad in {
            "bare positional": f"{base} [--state <state.json>] <review-file>",
            "required missing": "autopilot review-stage --cycle-id <id> [--state <state.json>]",
            "unknown option": f"{base} [--nonexistent <x>]",
            "optional as required": f"{base} --state <state.json>",
        }.items():
            with self.subTest(validator_rejects=label):
                with self.assertRaises(AssertionError):
                    check_line("review-stage", bad)


if __name__ == "__main__":
    unittest.main()
