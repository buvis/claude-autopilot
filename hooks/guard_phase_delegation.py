#!/usr/bin/env python3
"""PreToolUse hook (Agent): deny an Agent call that hands a whole phase skill
to a subagent.

PRD 00248. The 2026-10-03 00242 build session dispatched Agent calls that told
a subagent to run /autopilot:work, /autopilot:plan-tasks or
/autopilot:design-solution instead of running the phase skill itself with the
Skill tool. Phase skills must stay in the session; Agent calls are for
per-task subagents (Ivan, Tess, Devon, reviewers) only.

Denies (exit 2, reason on stderr) iff `_AUTOPILOT_LOOP` is set, the tool is
`Agent`, and `is_phase_delegation` matches the prompt or description. Any
unparseable payload fails open.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import allow, block, read_input

# Widened to the -ing form of each verb: recovered transcripts say "You are
# executing the `autopilot:design-solution` skill" (autonomous decision,
# PRD 00248 task 1).
_IMPERATIVE = r"(run(?:ning)?|execut(?:e|ing)|invok(?:e|ing)|follow(?:ing)?|continu(?:e|ing)|resum(?:e|ing))"
_PHASE_JARGON = r"(work phase|plan(?:ning)? phase|design phase)"
# (?P=bt) requires the SAME backtick-or-nothing to close immediately after
# the skill name - "`/autopilot:plan-tasks`" (tight close) matches; "invoke
# `/autopilot:design-solution dev/local/prds/wip/..." (an opening backtick
# whose matching close is many words later, around an args list) does not,
# because nothing closes immediately. No trailing \b: a literal backtick is
# a non-word char, and \b between two non-word chars (backtick, space)
# never matches.
_BARE_SKILL = r"(?P<bt>`?)(?:/)?(autopilot:work|autopilot:plan-tasks|autopilot:design-solution|plan-tasks|design-solution)(?P=bt)"
_SKILL_READ = (
    r"read\s+(?:skills/)?(work|plan-tasks|design-solution)/SKILL\.md"
    r".{0,60}\b(run|follow|execute|continue)\b.{0,20}\b(every|all)\s+tasks?\b"
)
_NEGATION = r"\b(not|never|n't|does\s+not|doesn't|don't|won't)\b"
_NEGATION_RE = re.compile(_NEGATION, re.IGNORECASE)

_DELEGATION_PATTERNS = (
    re.compile(rf"\b{_IMPERATIVE}\b.{{0,40}}\b{_PHASE_JARGON}\b", re.IGNORECASE),
    re.compile(rf"\b{_PHASE_JARGON}\b.{{0,40}}\b{_IMPERATIVE}\b", re.IGNORECASE),
    re.compile(rf"\b{_IMPERATIVE}\s+(?:the\s+)?{_BARE_SKILL}", re.IGNORECASE),
    re.compile(_SKILL_READ, re.IGNORECASE | re.DOTALL),
)


def _negated_before(text: str, start: int, window: int = 20) -> bool:
    """True iff a negation word sits in the `window` chars immediately
    before `start` - the match is `run plan-tasks` inside `does not run
    plan-tasks`, and that is a prohibition, not a delegation."""
    return bool(_NEGATION_RE.search(text[max(0, start - window):start]))


def is_phase_delegation(tool_input: dict) -> bool:
    """True iff this Agent dispatch instructs the subagent to run a phase
    skill (/autopilot:work, /autopilot:plan-tasks, /autopilot:design-solution,
    or the Skill tool generally) rather than a single per-task job.

    Looks at tool_input["prompt"] and tool_input["description"] (both
    optional, default ""). A payload where tool_input is not a dict, or has
    neither key present as a non-empty string, returns False (fail open).
    """
    if not isinstance(tool_input, dict):
        return False
    prompt = tool_input.get("prompt") or ""
    description = tool_input.get("description") or ""
    text = f"{prompt}\n{description}"
    return any(
        not _negated_before(text, match.start())
        for pattern in _DELEGATION_PATTERNS
        for match in pattern.finditer(text)
    )


def main() -> None:
    if not os.environ.get("_AUTOPILOT_LOOP"):
        allow()
    payload = read_input()
    if not payload:
        print("guard_phase_delegation: empty/unparseable payload, allowing", file=sys.stderr)
        allow()
    if payload.get("tool_name") != "Agent":
        allow()
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        print("guard_phase_delegation: unparseable tool_input, allowing", file=sys.stderr)
        allow()
    try:
        delegates = is_phase_delegation(tool_input)
    except Exception:
        print("guard_phase_delegation: predicate raised, allowing", file=sys.stderr)
        allow()  # fail open, defensive - predicate is pure regex, should not raise
    if not delegates:
        allow()
    block(
        "autopilot: run the phase skill (plan-tasks / design-solution / work) "
        "with the Skill tool in THIS session; dispatch Agent calls only for "
        "per-task subagents (Ivan, Tess, Devon, reviewers). "
        "hooks/guard_phase_delegation.py denied this Agent call."
    )


if __name__ == "__main__":
    main()
