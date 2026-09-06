"""Contract test for the Bob lack-of-input retry policy prose.

Pins the retry-policy.md / SKILL.md / agent-invocation.md / agents/bob.md text
that lets `review-work-completion` detect Bob's lack-of-input refusal shape and
retry him with an inlined prompt (PRD 00178). Text-pinning only:
stdlib unittest, no import of any module under test. Deleting the refusal
detection rule, the inlined-prompt mechanics, the dispatch-ledger kind flags,
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
        cls.refusal = _section(
            cls.retry_policy, "## Lack-of-input refusal (Bob)"
        )
        cls.inlined_prompt = _section(
            cls.retry_policy, "## Inlined retry prompt (CLI reviewers)"
        )
        cls.bob_invocation = _section(cls.agents, "## Bob (Codex)")

    def test_refusal_shape_checks_no_pass_verdict_lines(self) -> None:
        # The refusal detector's first gate: no `R{n}: pass` line at all.
        self.assertIn("rg -c '^R[0-9]+: pass'", self.refusal)

    def test_refusal_shape_checks_no_issue_lines(self) -> None:
        # The second gate: no emitted issue line of any severity/clean emoji.
        self.assertIn("(🔴|🟠|🟡|✅)", self.refusal)

    def test_refusal_shape_requires_cannot_statically_verify_line(self) -> None:
        # The third gate: at least one explicit "cannot verify" line, which is
        # what distinguishes a genuine refusal from a reviewer that just found
        # nothing to say.
        self.assertIn("⚪ Cannot statically verify", self.refusal)

    def test_inlined_retry_prompt_tells_bob_the_sandbox_supplied_everything(
        self,
    ) -> None:
        # The retry prompt must explain why Bob cannot read files this time -
        # everything is inlined - or he retries the same refusal.
        self.assertIn("INLINED BELOW as text", self.inlined_prompt)

    def test_inlined_retry_prompt_uses_dedicated_retry_filename(self) -> None:
        # The retry prompt is written to its own file, distinct from the first
        # attempt's prompt file, so both are retained for forensics.
        self.assertIn("bob-prompt-{id}-retry.md", self.inlined_prompt)

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

    def test_bob_invocation_cross_references_lack_of_input_refusal(self) -> None:
        # The invocation doc must point at the refusal rule so the retry gets
        # triggered from Bob's own dispatch section, not just documented in
        # isolation in retry-policy.md.
        self.assertIn("Lack-of-input refusal", self.bob_invocation)

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

    def test_bob_invocation_other_exits_and_refusal_share_the_one_cli_retry(
        self,
    ) -> None:
        # Every non-3/4 exit, plus the refusal shape, gets the one CLI retry.
        self.assertIn(
            "The one CLI retry above applies to every other non-zero exit, "
            "and to the refusal shape it names",
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
