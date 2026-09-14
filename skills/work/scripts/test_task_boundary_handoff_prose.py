"""Tests binding the live text of
${CLAUDE_PLUGIN_ROOT}/skills/work/references/task-boundary-handoff.md, the
task-boundary handoff procedure /work step 6.5 defers to.

Split out of test_dispatch_prose.py (which pins SKILL.md and the first wave of
this reference's phase-aware rules) so that file stays under the 800-line
ceiling; every later prose test for this reference lives here. Same pattern:
resolve the path relative to this file, read it once, and assert on short,
reword-resistant substrings, or on a regex over the window of one lettered
procedure step, each with a failure message naming what drifted and where to
look. The procedure's steps are numbered 1, 2, 3a-3h; a window is cut from a
step's `<letter>. ` line start to the next lettered step.
"""

from __future__ import annotations

import re
from pathlib import Path

_SKILL_MD = Path(__file__).resolve().parent.parent / "SKILL.md"
_REFERENCE_MD = _SKILL_MD.parent / "references" / "task-boundary-handoff.md"
_TEXT = _REFERENCE_MD.read_text()

_FIELDS = ("`phase`", "`session`", "`at`", "`task_id`")
_STALE_NOTE = "`autopilot: stale handoff marker from phase {marker phase} removed`"
# test_dispatch_prose.py's gap idiom, tightened to one sentence: no negation
# word, no ". " sentence end (so `state.next_phase` stays whole), no line break.
_GAP = r"(?:(?!\b(?:not|never|neither|nor)\b)(?!\.\s)[^\n])"


def _affirmed(text: str, first: str, second: str, span: int) -> bool:
    # `first` and `second` (regex fragments, either order) in ONE sentence with
    # no negation from its start through the later of the two. Proximity alone
    # is satisfied by a sentence DENYING the rule ("Never set `next_phase` to
    # the marker phase"); the anchor on the sentence start tells them apart.
    return any(
        re.search(
            rf"(?:^|\.\s){_GAP}*?{a}{_GAP}{{0,{span}}}?{b}",
            text,
            re.IGNORECASE | re.MULTILINE,
        )
        for a, b in ((first, second), (second, first))
    )


def _step_start(letter: str) -> int:
    match = re.search(rf"^[ \t]*{letter}\.\s", _TEXT, re.MULTILINE)
    assert match, (
        f"{_REFERENCE_MD} has no procedure step 3{letter} (a line starting "
        f"with '{letter}. ') — the lettered step layout these tests window on "
        "has been renumbered or flattened."
    )
    return match.start()


def _step_3b() -> str:
    return _TEXT[_step_start("b") : _step_start("c")]


def _step_3c() -> str:
    return _TEXT[_step_start("c") : _step_start("d")]


def _step_3h() -> str:
    # The last lettered step: everything from its line start to the end of
    # the file, so a trailing note under it still counts as its text.
    return _TEXT[_step_start("h") :]


def _malformed_bullet(window: str) -> str:
    # The bullet inside step 3b that names the malformed case: from the start
    # of the line carrying "malformed" to the next bullet or the window's end.
    hit = re.search(r"malformed", window, re.IGNORECASE)
    assert hit, (
        "references/task-boundary-handoff.md step 3b no longer has a bullet "
        "naming the 'malformed' marker case."
    )
    start = window.rfind("\n", 0, hit.start()) + 1
    following = re.search(r"\n[ \t]*- ", window[hit.end() :])
    end = hit.end() + following.start() if following else len(window)
    return window[start:end]


def test_step_3c_prints_the_exact_stale_marker_note_ending_in_removed() -> None:
    # The whole note is the contract, not its prefix: it carries only the
    # marker's phase and ends in "removed". Pinned with its closing backtick
    # and inside the 3c window, so a note that kept the old ", expected
    # {state.phase}" tail cannot pass on the shared prefix.
    window = _step_3c()

    assert _STALE_NOTE in window, (
        f"references/task-boundary-handoff.md step 3c does not print exactly "
        f"{_STALE_NOTE!r} on a phase mismatch. The full literal is the contract; "
        "a longer or reworded note is a different message."
    )


def test_step_3c_removes_both_markers_right_after_the_stale_note() -> None:
    # The note is half the contract: the step then removes BOTH markers,
    # unnegated. A 3c that printed the exact literal "but do NOT remove
    # anything" carries the needle and hands off on a stale marker anyway.
    window = _step_3c()
    assert _STALE_NOTE in window, "pinned by the exact-note test above"
    tail = window[window.index(_STALE_NOTE) + len(_STALE_NOTE) :]

    for marker_file in (".handoff-requested", ".cap-fired"):
        assert _affirmed(tail, r"\bremov", re.escape(marker_file), 120), (
            f"references/task-boundary-handoff.md step 3c does not remove "
            f"{marker_file!r} after printing the stale note (or a not/never sits "
            "between the two) — the stale marker would trip the next boundary."
        )


def test_step_3b_requires_every_marker_field_to_be_a_string() -> None:
    # A JSON marker is valid only when each of the four fields is a string
    # (and `task_id` is non-empty). The typing rule must sit in step 3b next
    # to the field list, and OUTSIDE the malformed bullet — a doc that only
    # mentions strings while describing the failure never states the rule.
    window = _step_3b()
    typing_rule = window.replace(_malformed_bullet(window), "")

    for field in _FIELDS:
        assert field in typing_rule, (
            f"references/task-boundary-handoff.md step 3b's validity rule "
            f"never names {field} — the four-field list is missing from the "
            "step that decides what a valid marker is."
        )
        assert _affirmed(typing_rule, re.escape(field), r"\bstrings?\b", 200), (
            f"references/task-boundary-handoff.md step 3b never says, in one "
            f"unnegated sentence, that {field} must be a STRING — a numeric or "
            "null value would read as a valid marker."
        )
    assert _affirmed(typing_rule, "`task_id`", "non-empty", 60), (
        "references/task-boundary-handoff.md step 3b no longer requires a "
        "non-empty `task_id` for a valid marker (or denies it: 'need not be')."
    )


def test_step_3b_names_a_non_string_field_value_as_malformed() -> None:
    # The malformed bullet is the failure side of the typing rule: a field
    # whose value is not a string is malformed, not a clean mismatch.
    bullet = _malformed_bullet(_step_3b())

    assert _affirmed(
        bullet,
        r"(?:non-string|not\s+(?:a\s+)?string)",
        r"malformed",
        200,
    ), (
        "references/task-boundary-handoff.md step 3b's malformed bullet never "
        "names a field whose value is not a string (non-string / not a "
        "string) as malformed — the reader is left to guess whether a "
        "numeric `task_id` is valid, stale, or malformed."
    )
    assert not re.search(
        r"(?:\b(?:not|never)\b|n't)\s+(?:\w+\s+)?malformed",
        bullet,
        re.IGNORECASE,
    ), (
        "references/task-boundary-handoff.md step 3b's malformed bullet says "
        "something is NOT malformed — the failure side of the typing rule is "
        "denied where it should be stated."
    )


def test_step_3h_sets_next_phase_to_the_marker_phase_never_a_literal_build() -> None:
    # The match path hands off within the marker's own phase: `next_phase`
    # is set to the marker's (matching) phase, in the same unnegated
    # sentence, and no literal build target survives anywhere in the file —
    # neither the old `next_phase: "build"` nor `--site build`.
    window = _step_3h()

    assert _affirmed(
        window,
        r"next_phase",
        r"(?:marker's \(matching\) phase|marker phase|marker's phase)",
        80,
    ), (
        "references/task-boundary-handoff.md step 3h never sets `next_phase` "
        "to the marker's (matching) phase (or a not/never denies it) — a "
        "review-phase handoff would land wherever the text hardcodes."
    )
    for literal in ('next_phase: "build"', "--site build"):
        assert literal not in _TEXT, (
            f"references/task-boundary-handoff.md still contains {literal!r} "
            "— a literal build target outlived the phase-aware handoff."
        )


def test_step_3h_leave_row_carries_the_marker_phase_as_both_phase_and_site() -> None:
    # The `leave` telemetry row is one command: record_dispatch.py handoff
    # with --edge leave, and BOTH --phase and --site taking the marker
    # phase. A row that fixes either flag to a literal misfiles every
    # non-build handoff in the dispatch telemetry.
    window = _step_3h()
    row = re.search(r"`[^`]*record_dispatch\.py handoff[^`]*`", window)

    assert row, (
        "references/task-boundary-handoff.md step 3h no longer shows the "
        "`record_dispatch.py handoff ...` leave row as one backticked command."
    )
    for flag in ("--edge leave", "--phase <marker phase>", "--site <marker phase>"):
        assert flag in row.group(0), (
            f"references/task-boundary-handoff.md step 3h's leave row "
            f"{row.group(0)!r} lacks {flag!r}."
        )


def test_malformed_marker_bullet_removes_both_marker_files() -> None:
    # A malformed marker is cleaned up the same way as a stale one: BOTH
    # `.handoff-requested` and `.cap-fired` go, or the next task boundary
    # trips over the survivor. Anchored on the malformed note the way the
    # mismatch test anchors on the stale note.
    anchor = _TEXT.find("malformed handoff marker")

    assert anchor != -1, (
        "references/task-boundary-handoff.md never prints the "
        "'malformed handoff marker' note — nothing to anchor the removal "
        "check to."
    )

    window = _TEXT[anchor : anchor + 600]

    assert re.search(r"\bremov", window, re.IGNORECASE), (
        "references/task-boundary-handoff.md's malformed-marker handling "
        "never says to remove anything."
    )
    for marker_file in (".handoff-requested", ".cap-fired"):
        assert marker_file in window, (
            f"references/task-boundary-handoff.md's malformed-marker handling "
            f"never names {marker_file!r} for removal — both markers must go, "
            "not just one."
        )
