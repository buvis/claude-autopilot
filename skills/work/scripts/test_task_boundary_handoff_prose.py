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


# --- Task-boundary handoff (step 6.5): honour the marker's own phase --------
#
# Both files currently treat ANY present `.handoff-requested` marker as an
# unconditional build-phase handoff: task-boundary-handoff.md step 3d always
# writes `--phase build` and always sets `next_phase: "build"`, so a
# review-phase soft-cap request gets misrouted into a build handoff. The fix
# makes the marker carry its own phase (a typed JSON contract, with a legacy
# plain-task-id form kept for back-compat) and makes both files route on
# whether that phase matches the session's current one.


def test_task_boundary_handoff_names_the_four_typed_json_fields() -> None:
    # The new marker format is JSON with four required fields. Pinned as
    # backtick-wrapped identifiers, matching how every other identifier in
    # this file (`.handoff-requested`, `state.tasks`, `next_phase`, ...) is
    # already rendered — a bare "phase" would collide with this file's own
    # "Phase 3" prose (run-autopilot's phase, not the marker's JSON field).
    text = (_SKILL_MD.parent / "references" / "task-boundary-handoff.md").read_text()

    for field in ("`phase`", "`session`", "`at`", "`task_id`"):
        assert field in text, (
            f"references/task-boundary-handoff.md never names the JSON "
            f"marker field {field} — the typed four-field contract (phase, "
            "session, at, task_id) is unstated, so nothing tells a reader "
            "what shape a valid marker has."
        )


def test_task_boundary_handoff_treats_a_nonempty_legacy_marker_as_a_build_request() -> (
    None
):
    # A plain (non-JSON) marker holding a task id is the pre-fix format. It
    # keeps meaning "hand off to build" — only the empty-marker and
    # JSON-marker cases gain phase awareness.
    text = (_SKILL_MD.parent / "references" / "task-boundary-handoff.md").read_text()
    gap = r"(?:(?!\b(?:not|never|neither|nor)\b)[^.])"

    nonempty_legacy_is_build = (
        re.compile(rf"non-empty{gap}{{0,120}}?legacy{gap}{{0,80}}?build", re.IGNORECASE),
        re.compile(rf"legacy{gap}{{0,120}}?non-empty{gap}{{0,80}}?build", re.IGNORECASE),
    )

    assert any(p.search(text) for p in nonempty_legacy_is_build), (
        "references/task-boundary-handoff.md never states that a non-empty "
        "legacy (plain, non-JSON) task-ID marker is treated as a build "
        "request."
    )


def test_task_boundary_handoff_treats_an_empty_legacy_marker_as_the_current_phase() -> (
    None
):
    # An empty legacy marker (the format the context-cap hook wrote before
    # this fix) must read as "the session's current phase", not a hardcoded
    # build — this is what lets a review-phase soft-cap request hand off
    # inside review instead of always landing in build.
    text = (_SKILL_MD.parent / "references" / "task-boundary-handoff.md").read_text()
    gap = r"(?:(?!\b(?:not|never|neither|nor)\b)[^.])"

    # (?<!non-) keeps this off the "non-empty" clause above — "non-empty"
    # contains "empty" as a substring, and that clause is about the OPPOSITE
    # case (always build, not the current phase).
    empty_legacy_is_current_phase = (
        re.compile(
            rf"(?<!non-)empty{gap}{{0,120}}?legacy{gap}{{0,80}}?current phase",
            re.IGNORECASE,
        ),
        re.compile(
            rf"legacy{gap}{{0,120}}?(?<!non-)empty{gap}{{0,80}}?current phase",
            re.IGNORECASE,
        ),
    )

    assert any(p.search(text) for p in empty_legacy_is_current_phase), (
        "references/task-boundary-handoff.md never states that an empty "
        "legacy marker is treated as the current phase — a bare 'empty "
        "marker' rule that does not say CURRENT PHASE still reads as "
        "hardcoded to build."
    )


def test_task_boundary_handoff_no_longer_assumes_every_handoff_is_mid_build() -> None:
    # The current step 3d justifies its unconditional `next_phase: "build"`
    # with "it already is during the build gate, since this is a mid-build
    # task-boundary handoff" — stated as a universal truth. Post-fix that is
    # false whenever the marker (or the session) is in review, so this exact
    # justification cannot survive the fix.
    text = (_SKILL_MD.parent / "references" / "task-boundary-handoff.md").read_text()
    phrase = "since this is a mid-build task-boundary handoff"

    assert phrase not in text, (
        f"references/task-boundary-handoff.md still contains {phrase!r} — "
        "this sentence asserts every task-boundary handoff is mid-build, "
        "which is exactly the bug: a review-phase handoff is not mid-build."
    )


def test_task_boundary_handoff_states_the_stale_marker_stderr_note() -> None:
    # Exact fixed prefix pinned by the task: a phase mismatch prints this
    # note (with the marker's own phase filled in) before removing both
    # markers and continuing as if none were present.
    text = (_SKILL_MD.parent / "references" / "task-boundary-handoff.md").read_text()
    needle = "autopilot: stale handoff marker from phase"

    assert needle in text, (
        f"references/task-boundary-handoff.md never contains the fixed "
        f"stderr prefix {needle!r} for a phase-mismatched marker."
    )


def test_task_boundary_handoff_gives_malformed_json_its_own_distinct_note() -> None:
    # JSON-looking but invalid marker text (bad shape, missing field, empty
    # task_id) is a different failure than a clean phase mismatch, and gets
    # its own wording so a reader can tell the two apart in a log.
    text = (_SKILL_MD.parent / "references" / "task-boundary-handoff.md").read_text()

    assert "malformed" in text.lower(), (
        "references/task-boundary-handoff.md never mentions a 'malformed' "
        "marker note. JSON-looking but invalid marker text (bad field "
        "shapes, an empty task_id) needs its own note, distinct from the "
        "phase-mismatch note."
    )


def test_task_boundary_handoff_removes_both_markers_and_continues_as_absent_on_mismatch() -> (
    None
):
    # A phase mismatch (or a malformed marker) must clean up BOTH marker
    # files and then behave exactly as if no marker had been present — not
    # partially clean up, and not still hand off on the stale phase.
    text = (_SKILL_MD.parent / "references" / "task-boundary-handoff.md").read_text()
    anchor = text.find("autopilot: stale handoff marker from phase")

    assert anchor != -1, (
        "references/task-boundary-handoff.md never states the stale-marker "
        "stderr note — see test_task_boundary_handoff_states_the_stale_"
        "marker_stderr_note; nothing to anchor the removal check to."
    )

    window = text[max(0, anchor - 200) : anchor + 600]

    for marker_file in (".handoff-requested", ".cap-fired"):
        assert marker_file in window, (
            f"references/task-boundary-handoff.md's phase-mismatch handling "
            f"never names {marker_file!r} — both markers must be removed, "
            "not just one."
        )

    assert re.search(r"as if|no marker|absent|return to step 1", window, re.IGNORECASE), (
        "references/task-boundary-handoff.md's phase-mismatch handling "
        "never says to continue exactly as if no marker had been present."
    )


def test_task_boundary_handoff_never_hands_off_on_an_unreadable_state_json() -> None:
    # An unreadable state.json leaves nothing to compare the marker's phase
    # against: no handoff, no invented phase, AND the markers stay in place
    # (this is not a mismatch — there is simply no state to judge them by).
    text = (_SKILL_MD.parent / "references" / "task-boundary-handoff.md").read_text()
    gap = r"(?:(?!\b(?:not|never|neither|nor)\b)[^.])"

    anchor = re.search(
        rf"state\.json{gap}{{0,60}}?(?:unreadable|cannot be read|can.t be read)"
        rf"|(?:unreadable|cannot be read|can.t be read){gap}{{0,60}}?state\.json",
        text,
        re.IGNORECASE,
    )
    assert anchor, (
        "references/task-boundary-handoff.md never describes what happens "
        "when `state.json` cannot be read — there is nothing to compare "
        "the marker's own phase against in that case."
    )

    window = text[max(0, anchor.start() - 60) : anchor.end() + 300]

    assert re.search(r"not\b[^.]{0,50}hand.?off|no\s+handoff", window, re.IGNORECASE), (
        "references/task-boundary-handoff.md's unreadable-state.json case "
        "never says NOT to hand off."
    )
    assert re.search(
        r"not\b[^.]{0,50}(?:invent|assume|guess)[^.]{0,20}phase",
        window,
        re.IGNORECASE,
    ), (
        "references/task-boundary-handoff.md's unreadable-state.json case "
        "never says NOT to invent or assume a phase."
    )
    assert re.search(r"not\b[^.]{0,60}remove", window, re.IGNORECASE), (
        "references/task-boundary-handoff.md's unreadable-state.json case "
        "never says the markers must NOT be removed."
    )


def test_task_boundary_handoff_keeps_review_as_the_target_for_a_valid_empty_marker_in_review() -> (
    None
):
    # The worked case the fix exists for: a valid legacy EMPTY marker seen
    # while the session is in review hands off to review, not build.
    text = (_SKILL_MD.parent / "references" / "task-boundary-handoff.md").read_text()
    gap = r"(?:(?!\b(?:not|never|neither|nor)\b)[^.])"

    review_stays_review = (
        re.compile(
            rf"review{gap}{{0,150}}?(?<!non-)empty{gap}{{0,100}}?legacy", re.IGNORECASE
        ),
        re.compile(
            rf"(?<!non-)empty{gap}{{0,150}}?legacy{gap}{{0,100}}?review", re.IGNORECASE
        ),
        re.compile(
            rf"legacy{gap}{{0,150}}?(?<!non-)empty{gap}{{0,100}}?review", re.IGNORECASE
        ),
    )

    assert any(p.search(text) for p in review_stays_review), (
        "references/task-boundary-handoff.md never states (or shows an "
        "example) that a valid legacy EMPTY marker seen during the review "
        "phase preserves review as the handoff target — this is the case "
        "the fix exists for."
    )


def test_step_6_5_trigger_summary_no_longer_names_an_unconditional_build_next_phase() -> (
    None
):
    # SKILL.md's step 6.5 trigger summary currently spells out
    # `next_phase: "build"` as part of the "Present" branch, unconditionally
    # — the same bug the reference procedure carries. A present marker now
    # routes on whether its own phase matches the session's, so this literal
    # cannot stay as an unconditional list item.
    text = _SKILL_MD.read_text()
    start = text.index("### 6.5.")
    end = text.index("### 7.", start)
    section = text[start:end]
    phrase = 'next_phase: "build"'

    assert phrase not in section, (
        f"{_SKILL_MD}: step 6.5's trigger summary still contains {phrase!r} "
        "unconditionally — a present marker must route on whether its own "
        "phase matches the current session's phase, not always land on "
        "build."
    )
