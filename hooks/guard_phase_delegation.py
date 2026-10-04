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
# No "n't" alternative: \b never matches before the "n" inside a
# contraction, so that alternative was dead. Contractions are spelled out.
_NEGATION = (
    r"\b(not|never|does\s+not|doesn't|don't|won't|can't|cannot|isn't|"
    r"shouldn't|wasn't|weren't)\b"
)
_NEGATION_RE = re.compile(_NEGATION, re.IGNORECASE)
_SENTENCE_BOUNDARY_RE = re.compile(r"[.;,\n]")

# Read-only reviewer personas: none of their persona files grant the Skill
# tool (test_every_exempt_reviewer_lacks_the_skill_tool), so exempting them
# from the delegation check cannot be exploited to delegate a phase skill.
_READ_ONLY_REVIEWERS = frozenset(
    {
        "autopilot:alice", "autopilot:blake", "autopilot:bob", "autopilot:carl",
        "autopilot:cora", "autopilot:eve", "autopilot:grace", "autopilot:mallory",
        "autopilot:pat", "autopilot:rita", "autopilot:toby", "autopilot:trent",
        "autopilot:victor",
    }
)

# Tight (immediate-adjacency) phase-jargon pattern, forward direction only:
# "run the work phase" / "run work phase" matches; "run by the work phase"
# and "run at this exact HEAD by the work phase" do not, because nothing
# sits between the verb and its object. The looser bidirectional {0,40}-gap
# form this replaced matched ordinary reviewer prose ("run by the work
# phase"), denying 21 of 231 real review-roster prompts (verified by
# docs/dev/tmp/probe-blake-high-00248.py). No reverse-direction ("work phase
# ... run") pattern: none of the four observed denial fixtures needs it, and
# it is pure false-positive surface.
_PHASE_JARGON_TIGHT = rf"\b{_IMPERATIVE}\s+(?:the\s+|this\s+)?{_PHASE_JARGON}\b"

_DELEGATION_PATTERNS = (
    re.compile(_PHASE_JARGON_TIGHT, re.IGNORECASE),
    # Reverse direction ("<phase> phase ...: <imperative>"), gated on a
    # colon between jargon and verb - "Planning phase for PRD 00300:
    # continue it from task 4." matches; descriptive prose like "the work
    # phase's own run at this HEAD" does not, because nothing introduces
    # the verb as an instruction.
    re.compile(rf"\b{_PHASE_JARGON}\b[^.;\n:]{{0,25}}:\s*(?:it\s+)?\b{_IMPERATIVE}\b", re.IGNORECASE),
    re.compile(rf"\b{_IMPERATIVE}\s+(?:the\s+)?{_BARE_SKILL}", re.IGNORECASE),
    re.compile(_SKILL_READ, re.IGNORECASE | re.DOTALL),
)


def _negated_before(text: str, start: int, window: int = 20) -> bool:
    """True iff a negation word sits in the `window` chars immediately
    before `start`, without crossing a sentence boundary (`.`, `;`, `,`, or a
    newline) - the match is `run plan-tasks` inside `does not run
    plan-tasks`, and that is a prohibition, not a delegation. A negation in
    an earlier sentence ("Do not wait for me. Run the work phase...") must
    not suppress a real delegation in a later one, so only the LAST boundary
    in the window is honored."""
    window_start = max(0, start - window)
    preceding = text[window_start:start]
    preceding = _SENTENCE_BOUNDARY_RE.split(preceding)[-1]
    return bool(_NEGATION_RE.search(preceding))


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
    subagent_type = tool_input.get("subagent_type")
    if isinstance(subagent_type, str) and subagent_type in _READ_ONLY_REVIEWERS:
        return False
    prompt = tool_input.get("prompt")
    description = tool_input.get("description")
    prompt = prompt if isinstance(prompt, str) else ""
    description = description if isinstance(description, str) else ""
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
