"""Pin PRD 00249: steps 3-5 stage the cycle through `autopilot review-stage`.

Hand-writing every reviewer prompt cost 26-73 s of generation each. The CLI
renders them in code, so the staging steps must name it and must no longer
tell the model to write prompt files with the Write tool. Step 8 may still use
the Write tool for its own files, so the ban is scoped to steps 3-5.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SKILL = (ROOT / "skills/review-work-completion/SKILL.md").read_text(encoding="utf-8")

HAND_WRITTEN_PROMPT = re.compile(r"use the \*\*Write tool\*\*.*?to create", re.DOTALL)


def _between(start: str, end: str) -> str:
    return SKILL.split(start, 1)[1].split(end, 1)[0]


def test_skill_stages_via_review_stage() -> None:
    step_4 = _between("\n### 4. ", "\n### ")
    assert "review-stage" in step_4, "step 4 no longer names `review-stage`"

    staging = _between("\n### 3. ", "\n### 6. ")
    hand_written = HAND_WRITTEN_PROMPT.search(staging)
    assert hand_written is None, (
        "steps 3-5 still tell the model to write prompt files by hand: "
        f"{hand_written.group(0)[:120]!r}"
    )
