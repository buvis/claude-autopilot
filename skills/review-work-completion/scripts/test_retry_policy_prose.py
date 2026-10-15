"""Contract test for the Bob retry policy prose.

Pins the retry-policy.md / SKILL.md / agent-invocation.md / agents/bob.md text
for Bob's inlined-prompt mechanics and retry handling (PRD 00178). Text-pinning
only: stdlib unittest, no import of any module under test. Deleting the
inlined-prompt mechanics, the dispatch-ledger kind flags,
the Bob-invocation cross-reference, or the sandbox's read-only-command
allowance must fail one of these tests.
"""

from __future__ import annotations

import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
PACK_ROOT = SKILL_DIR.parent.parent
SKILL_MD = SKILL_DIR / "SKILL.md"
RETRY_POLICY = SKILL_DIR / "references" / "retry-policy.md"
AGENT_INVOCATION = SKILL_DIR / "references" / "agent-invocation.md"
AGENT_REGISTRY = SKILL_DIR / "references" / "agent-registry.md"
BOB_MD = PACK_ROOT / "agents" / "bob.md"


def _section(text: str, header: str) -> str:
    """Return the slice from `header` up to the next `## ` or `### ` header."""
    start = text.index(header)
    after = start + len(header)
    ends = [
        e
        for e in (text.find("\n### ", after), text.find("\n## ", after))
        if e != -1
    ]
    end = min(ends) if ends else len(text)
    return text[start:end]


class RetryPolicyProseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skill = SKILL_MD.read_text(encoding="utf-8")
        cls.retry_policy = RETRY_POLICY.read_text(encoding="utf-8")
        cls.agents = AGENT_INVOCATION.read_text(encoding="utf-8")
        cls.registry = AGENT_REGISTRY.read_text(encoding="utf-8")
        cls.bob_persona = BOB_MD.read_text(encoding="utf-8")
        cls.inlined_prompt = _section(
            cls.retry_policy,
            "## Inlined prompt (Bob's first dispatch)",
        )
        cls.bob_invocation = _section(cls.agents, "## Bob (Codex)")

    def test_inlined_retry_prompt_tells_bob_the_sandbox_supplied_everything(
        self,
    ) -> None:
        # The retry prompt must explain why Bob cannot read files this time -
        # everything is inlined - or he retries the same refusal.
        self.assertIn("INLINED BELOW as text", self.inlined_prompt)

    def test_inlined_prompt_overwrites_the_staged_file(self) -> None:
        # The inlined build always runs on dispatch 1, so it writes the same
        # path review-stage staged for Bob rather than a separate name.
        self.assertIn("bob-prompt-{id}.md", self.inlined_prompt)
        self.assertNotIn("bob-prompt-{id}-retry.md", self.inlined_prompt)

    def test_inlined_retry_prompt_restricts_review_to_inlined_text(self) -> None:
        # The persona edit that stops Bob from trying to explore the codebase
        # on the retry, which would just reproduce the refusal.
        self.assertIn("using ONLY the inlined text above", self.inlined_prompt)

    def test_skill_ledgers_bob_dispatch_with_its_kind(self) -> None:
        # Dispatch-ledger rows must tag Bob's kind so a retry's second row is
        # attributable to him.
        self.assertIn("record_dispatch.py start --kind bob", self.skill)

    def test_skill_ledgers_carl_dispatch_with_its_kind(self) -> None:
        # Same ledger call names Carl's kind flag for his own dispatch rows.
        self.assertIn("--kind carl", self.skill)

    def test_bob_invocation_cross_references_the_inlined_prompt_section(self) -> None:
        # The invocation doc must point at the section that actually builds
        # {bob_prompt_file_absolute_path}, not a deleted refusal-retry rule.
        self.assertIn("Inlined prompt (Bob's first dispatch)", self.bob_invocation)
        self.assertNotIn("Lack-of-input refusal", self.bob_invocation)

    def test_bob_persona_permits_read_only_shell_commands(self) -> None:
        # Bob's sandbox appendix must tell him HOW to read files (read-only
        # shell commands), not just that he is barred from writing.
        self.assertIn("read-only shell commands", self.bob_persona)

    def test_bob_persona_does_not_forbid_running_commands_outright(self) -> None:
        # An earlier, stricter phrasing blocked Bob from running any command
        # at all, which also blocks the read-only commands the appendix now
        # grants him. That phrasing must not resurface.
        self.assertNotIn("Do NOT attempt to run commands", self.bob_persona)

    def test_bob_invocation_exit3_takes_the_claude_fallback_with_no_cli_retry(
        self,
    ) -> None:
        # Exit-routing owns exit 3: straight to the fallback, no CLI retry.
        self.assertIn(
            "exit 3 (codex unavailable) dispatches Bob's Claude fallback straight away",
            self.bob_invocation,
        )
        self.assertIn("neither takes a CLI retry", self.bob_invocation)

    def test_bob_invocation_exit4_checks_the_sidecar_before_falling_back(
        self,
    ) -> None:
        # Exit 4 salvages a complete review from the sidecar before ever
        # reaching the Claude fallback.
        self.assertIn(
            "checks the `codex-review-last.jsonl` sidecar for a complete review to salvage",
            self.bob_invocation,
        )

    def test_bob_invocation_other_exits_share_the_one_cli_retry(self) -> None:
        # Every non-3/4 exit gets the one CLI retry, re-dispatching the same
        # inlined prompt file rather than switching shapes mid-retry.
        self.assertIn(
            "The one CLI retry above applies to every other non-zero exit: "
            "it re-dispatches the same inlined prompt file",
            self.bob_invocation,
        )

    def test_agent_registry_documents_bobs_native_fallback_tool(self) -> None:
        # The registry must say what tool Bob's native Claude fallback reads
        # its named files with, in place of the persona's read-only shell
        # commands.
        self.assertIn("Bob's fallback reads through the Read tool", self.registry)
        self.assertIn("with read-only shell commands", self.registry)
        self.assertIn("(`cat`, `sed -n`, `rg`, `ls`)", self.registry)
        self.assertIn(
            "subagent holding `Read` alone, which opens those same named "
            "files with that",
            self.registry,
        )


if __name__ == "__main__":
    unittest.main()
