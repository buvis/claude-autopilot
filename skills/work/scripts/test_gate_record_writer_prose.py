"""Prose pins for routing the full-suite run through `autopilot verify`
(PRD 00270).

`autopilot verify` (the CLI verb, PRD 00270 task 7) wraps
`verification.run_gate` and is the only caller that may write
`docs/dev/project-management/autopilot/last-verification.json`. Four prose
files describe or trigger a full-suite run: `work/references/final-verification.md`
(step 7), `work/SKILL.md` (step 7's own text), `run-autopilot/references/lane-solo.md`
(the solo lane's own suite run) and `review-work-completion/SKILL.md` (step 6's
fallback run). None of them may tell a session to write the record by hand -
that is exactly the drift this pin exists to catch.

Same pattern as test_verify_queue_prose.py: read each file once, assert on
short, reword-resistant substrings/regexes, each with a failure message naming
what drifted.
"""

from __future__ import annotations

import re
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
_WORK = _SCRIPTS.parent
_SKILLS = _WORK.parent

_FINAL_VERIFICATION = _WORK / "references" / "final-verification.md"
_WORK_SKILL = _WORK / "SKILL.md"
_LANE_SOLO = _SKILLS / "run-autopilot" / "references" / "lane-solo.md"
_REVIEW_SKILL = _SKILLS / "review-work-completion" / "SKILL.md"
_AGENT_INVOCATION = _SKILLS / "review-work-completion" / "references" / "agent-invocation.md"

_PROSE_FILES = (_FINAL_VERIFICATION, _WORK_SKILL, _LANE_SOLO, _REVIEW_SKILL)

_WRITE_RECORD_RE = re.compile(r"(?i)\bwrite\b.*last-verification\.json")


def test_no_prose_tells_a_session_to_write_the_record() -> None:
    # The verb is the sole writer; a session that hand-writes the record
    # defeats the sha/dirty-tree guarantees `autopilot verify` exists to give.
    for path in _PROSE_FILES:
        text = path.read_text()
        for lineno, line in enumerate(text.splitlines(), start=1):
            assert not _WRITE_RECORD_RE.search(line), (
                f"{path}:{lineno} tells a session to write last-verification.json "
                "by hand instead of routing the run through `autopilot verify`."
            )


def test_final_verification_runs_the_suite_through_autopilot_verify() -> None:
    verification = _FINAL_VERIFICATION.read_text()

    assert "autopilot verify --gate-command" in verification, (
        "references/final-verification.md's Recorded verification result "
        "section no longer runs the full suite through `autopilot verify`."
    )
    assert "sole writer" in verification, (
        "references/final-verification.md no longer names `autopilot verify` "
        "as the sole writer of last-verification.json."
    )


def test_gate_output_is_read_from_the_log_not_a_rerun() -> None:
    verification = _FINAL_VERIFICATION.read_text()

    assert "rg" in verification and "log" in verification, (
        "references/final-verification.md no longer tells a session to read a "
        "failure's output from the printed log with rg."
    )
    assert "never by re-running the gate to capture it" in verification, (
        "references/final-verification.md no longer forbids re-running the "
        "gate to capture output that the log already holds."
    )


def test_review_fallback_runs_through_autopilot_verify() -> None:
    review = _REVIEW_SKILL.read_text()

    assert 'run `autopilot verify --gate-command "<full suite command>" --cycle' in review, (
        "review-work-completion/SKILL.md step 6's fallback no longer runs the "
        "full suite through `autopilot verify`, so it could still write the "
        "record itself or re-run the gate to capture output."
    )


def test_agent_invocation_documents_blake_test_gate() -> None:
    agent_invocation = _AGENT_INVOCATION.read_text()

    assert "## Blake: Test gate" in agent_invocation, (
        "agent-invocation.md has no '## Blake: Test gate' section documenting "
        "the ## Test gate block agents/blake.md's new sentence refers to."
    )
    assert "must not rerun" in agent_invocation, (
        "agent-invocation.md's Blake: Test gate section no longer states that "
        "Blake must not rerun the full suite when he has the staged result."
    )
