"""Tests binding the custody prose in run-autopilot's reference files — the
Phase 0 pending-custody handler and the Phase 3 `state.git_dir` capture in
`references/phase-build.md`, the loop-mode cap-out range sentence in
`references/phase-review.md`, and the `cap_critical` slug plus the
custody-aware exit rows in `references/recovery.md`.

Mirrors test_dispatch_prose.py's pattern for pinning a skill file's prose:
resolve each target file's path relative to this file, read it once, and
assert on short, reword-resistant substrings, each with a failure message
naming what drifted. Presence assertions are scoped to the section that is
supposed to carry them, via `_section` below, so the pin still catches text
that has moved out of its section. Each presence pin binds a verb or an
order to its noun (run X, writes Y, PAUSE before Z), and each section also
sweeps for the negations that would invert it (`Do NOT run`, `never`,
`is retired`), so prose that keeps every token but tells the operator to do
the opposite still fails. Absence assertions sweep every `.md` under
`skills/run-autopilot`.

Pins for `references/state-schema.md` and `SKILL.md` (the custody record
shape, the marker file, the batch mirror, the captured `stall_op` retry
fields) belong to a later task and land in this same module.
"""

from __future__ import annotations

import re
from pathlib import Path

_SKILL_DIR = Path(__file__).resolve().parent.parent
_REFERENCES = _SKILL_DIR / "references"

_PHASE_BUILD = _REFERENCES / "phase-build.md"
_BUILD_TEXT = _PHASE_BUILD.read_text()

_PHASE_REVIEW = _REFERENCES / "phase-review.md"
_REVIEW_TEXT = _PHASE_REVIEW.read_text()

_RECOVERY = _REFERENCES / "recovery.md"
_RECOVERY_TEXT = _RECOVERY.read_text()

_CUSTODY_HEADING = "### Handle pending custody"
_ABORT_HEADING = "### Handle Work-phase abort"
_ABORT_CLOSING = "Before acting on whichever branch matched"
_SELECTION_HEADING = "### Normal PRD selection"
_CUSTODY_WHERE = f"the {_CUSTODY_HEADING!r} section"

_ROSTER_SENTENCE = (
    "Invoke `/autopilot:review-work-completion` skill. Every cycle runs ALL "
    "lenses (its roster, PRD 00015): Alice (consensus), Blake (blind, "
    "PRD-only), Bob (doubt rubric D1-D5 + de-slop; Claude fallback when codex "
    "is down), Carl (UI, optional), plus Eve as a fifth lens when that "
    "skill's step 1 doubt-reviewer resolution rule activates her."
)

_CAPTURE_FAILED_PREFIX = "autopilot: cap_critical custody capture failed:"
_OLD_BARE_2_ROW = (
    "| 2 | state unreadable | the corrupted-state row of Error Handling applies |"
)

# The three `--choice` values as word-bounded patterns; the first excludes
# the `revert` inside `branch-and-revert` so it cannot count twice.
_CHOICE_PATTERNS = (r"(?<![\w-])revert\b", r"\bbranch-and-revert\b", r"\baccept\b")

# Built by concatenation on purpose: the acceptance criterion sweeps the
# whole `skills/run-autopilot` tree with `rg` for these exact strings and
# must find nothing, so this file may not spell any of them out.
_ABSENT_NEEDLES = (
    "--" + "commit-range",
    "--" + "range",
    "mint" + "-stubs",
    "custody " + "stub",
    "design" + "-rework",
)


def _section(text: str, path: Path, start_anchor: str, end_anchor: str) -> str:
    """Slice `text` from `start_anchor` up to `end_anchor`.

    Asserts both anchors are present first, naming `path` and the missing
    anchor, so a drifted heading fails loudly instead of raising a bare
    `ValueError: substring not found`.
    """
    assert start_anchor in text, (
        f"{path}: expected section anchor {start_anchor!r} — not found."
    )
    start = text.index(start_anchor)
    assert end_anchor in text[start:], (
        f"{path}: expected section anchor {end_anchor!r} after "
        f"{start_anchor!r} — not found."
    )
    end = text.index(end_anchor, start)
    return text[start:end]


def _bullet(text: str, path: Path, slug: str) -> str:
    """Slice the ``- `slug` — ...`` bullet, including its wrapped lines.

    The bullet ends at the next bullet lead-in or the next blank line,
    whichever comes first.
    """
    lead = f"- `{slug}`"
    assert lead in text, f"{path}: expected a {lead!r} bullet — not found."
    start = text.index(lead)
    ends = [
        i for i in (text.find("\n- ", start + 1), text.find("\n\n", start)) if i != -1
    ]
    return text[start : min(ends)] if ends else text[start:]


def _custody_section() -> str:
    return _section(_BUILD_TEXT, _PHASE_BUILD, _CUSTODY_HEADING, _SELECTION_HEADING)


def _rows_starting_with(text: str, lead: str) -> list[str]:
    return [line for line in text.splitlines() if line.strip().startswith(lead)]


def _assert_present(
    scope: str,
    path: Path,
    where: str,
    needles: tuple[str, ...],
) -> None:
    for needle in needles:
        assert needle in scope, (
            f"{path}: expected {where} to say {needle!r} — not found."
        )


def _assert_absent(
    scope: str,
    path: Path,
    where: str,
    needles: tuple[str, ...],
) -> None:
    """Negative sweep: none of `needles` may appear in `scope`.

    Each needle is a negation that keeps the section's tokens but inverts
    its instruction (`Do NOT run ...`, `is retired`, `never retry`).
    """
    for needle in needles:
        assert needle not in scope, (
            f"{path}: {where} says {needle!r} — a negation that inverts the "
            "contract while keeping its tokens."
        )


def _exit_code(scope: str, path: Path, where: str, code: int) -> int:
    """Return the offset of `exit <code>` in `scope` (case-insensitive on `exit`)."""
    match = re.search(rf"(?i)\bexit {code}\b", scope)
    assert match, f"{path}: expected {where} to handle exit {code} — not found."
    return match.start()


def _assert_in_order(
    scope: str,
    path: Path,
    where: str,
    needles: tuple[str, ...],
) -> None:
    _assert_present(scope, path, where, needles)
    offsets = [scope.index(needle) for needle in needles]
    assert offsets == sorted(offsets), (
        f"{path}: expected {where} to name {needles!r} in that order — got "
        f"offsets {offsets}."
    )


def test_pending_custody_handler_sits_between_abort_handler_and_selection() -> None:
    assert _BUILD_TEXT.count(_CUSTODY_HEADING) == 1, (
        f"{_PHASE_BUILD}: expected exactly one {_CUSTODY_HEADING!r} heading — "
        f"found {_BUILD_TEXT.count(_CUSTODY_HEADING)}."
    )
    for anchor in (_ABORT_HEADING, _SELECTION_HEADING):
        assert anchor in _BUILD_TEXT, (
            f"{_PHASE_BUILD}: expected Phase 0 heading {anchor!r} — not found."
        )

    abort = _BUILD_TEXT.index(_ABORT_HEADING)
    custody = _BUILD_TEXT.index(_CUSTODY_HEADING)
    selection = _BUILD_TEXT.index(_SELECTION_HEADING)
    assert abort < custody < selection, (
        f"{_PHASE_BUILD}: {_CUSTODY_HEADING!r} must come after "
        f"{_ABORT_HEADING!r} and before {_SELECTION_HEADING!r} — got offsets "
        f"abort={abort}, custody={custody}, selection={selection}."
    )

    # The offsets alone accept a custody heading wedged inside the abort
    # handler; the abort section must still be whole when custody starts.
    abort_section = _section(
        _BUILD_TEXT,
        _PHASE_BUILD,
        _ABORT_HEADING,
        _CUSTODY_HEADING,
    )
    assert _ABORT_CLOSING in abort_section, (
        f"{_PHASE_BUILD}: the {_ABORT_HEADING!r} section must still carry its "
        f"closing {_ABORT_CLOSING!r} paragraph before {_CUSTODY_HEADING!r} "
        "starts — the custody heading appears to sit inside the abort handler."
    )


def test_pending_custody_handler_lists_then_asks_three_choices_and_resolves() -> None:
    custody = _custody_section()

    assert re.search(r"(?i)\brun\s+`autopilot custody list`", custody), (
        f"{_PHASE_BUILD}: expected {_CUSTODY_WHERE} to instruct "
        "'run `autopilot custody list`' (the verb bound to the call) — not found."
    )
    _assert_present(custody, _PHASE_BUILD, _CUSTODY_WHERE, ("AskUserQuestion",))
    choices = ("`revert`", "`branch-and-revert`", "`accept`")
    _assert_in_order(custody, _PHASE_BUILD, _CUSTODY_WHERE, choices)
    resolve = "autopilot custody resolve --prd <stem> --choice <choice>"
    _assert_present(custody, _PHASE_BUILD, _CUSTODY_WHERE, (resolve,))
    exit_5 = _exit_code(custody, _PHASE_BUILD, _CUSTODY_WHERE, 5)
    assert custody.find("STOP", exit_5) != -1, (
        f"{_PHASE_BUILD}: expected {_CUSTODY_WHERE} to STOP the turn after "
        "exit 5 (an unfinished revert) — no 'STOP' follows 'exit 5'."
    )
    negations = ("Do NOT run `autopilot custody", "Never open", "Nothing to do here")
    _assert_absent(custody, _PHASE_BUILD, _CUSTODY_WHERE, negations)


def test_pending_custody_handler_logs_the_count_and_continues_in_loop_mode() -> None:
    custody = _custody_section()
    line = "custody: <n> entries await an attended resume"
    _assert_present(custody, _PHASE_BUILD, _CUSTODY_WHERE, (line,))

    lower = custody.lower()
    line_at = lower.index(line)
    assert "loop mode" in lower[:line_at], (
        f"{_PHASE_BUILD}: expected {_CUSTODY_WHERE} to introduce loop mode "
        f"before the {line!r} line — the line is not bound to loop mode."
    )
    assert "continue" in lower[line_at:], (
        f"{_PHASE_BUILD}: expected {_CUSTODY_WHERE} to continue after printing "
        f"{line!r} — no 'continue' follows the line. Loop mode must log and "
        "continue rather than ask or resolve."
    )
    _assert_absent(custody, _PHASE_BUILD, _CUSTODY_WHERE, ("is retired",))


def test_pending_custody_handler_pauses_when_custody_state_is_unreadable() -> None:
    custody = _custody_section()
    _exit_code(custody, _PHASE_BUILD, _CUSTODY_WHERE, 9)
    _assert_present(
        custody,
        _PHASE_BUILD,
        _CUSTODY_WHERE,
        ("PAUSE", 'site: "sub_skill_fail"'),
    )
    _assert_absent(custody, _PHASE_BUILD, _CUSTODY_WHERE, ("fine to walk past",))


def test_phase_3_records_git_dir_for_the_bare_repo_case() -> None:
    capture = _section(
        _BUILD_TEXT,
        _PHASE_BUILD,
        "**Capture `repo_root` in the same step.**",
        "Invoke `/autopilot:work` skill.",
    )
    where = "the Phase 3 `repo_root` capture step"

    assert re.search(r"writes? [^.\n]{0,80}`state\.git_dir`", capture), (
        f"{_PHASE_BUILD}: expected {where} to say it writes `state.git_dir` "
        "(the verb bound to the field) — not found."
    )
    _assert_present(capture, _PHASE_BUILD, where, ("--git-dir", "unset when"))
    negations = ("unset in every case", "nothing reads it")
    _assert_absent(capture, _PHASE_BUILD, where, negations)


def test_loop_cap_out_captures_the_range_internally_with_no_range_flag() -> None:
    cap_out = _section(
        _REVIEW_TEXT,
        _PHASE_REVIEW,
        "- **Loop mode (`$_AUTOPILOT_LOOP` set) — cap-out defers, never pauses.**",
        "- **Interactive — perform the Cap-pause behavior**",
    )
    where = "the loop-mode cap-out bullet"

    pins = ('site: "cap_critical"', "there is no range flag to pass")
    _assert_present(cap_out, _PHASE_REVIEW, where, pins)
    assert re.search(r"captures[^\n]{0,60}work_start_sha\.\.HEAD", cap_out), (
        f"{_PHASE_REVIEW}: expected {where} to say the stall captures "
        "`work_start_sha..HEAD` (the verb bound to the range) — not found."
    )
    negations = ("Do not compute", "captures nothing", "by hand")
    _assert_absent(cap_out, _PHASE_REVIEW, where, negations)


def test_review_lens_roster_sentence_is_byte_identical() -> None:
    assert _ROSTER_SENTENCE in _REVIEW_TEXT, (
        f"{_PHASE_REVIEW}: the review-lens roster sentence is no longer "
        "byte-identical — it must read exactly:\n" + _ROSTER_SENTENCE
    )
    assert _REVIEW_TEXT.count(_ROSTER_SENTENCE) == 1, (
        f"{_PHASE_REVIEW}: expected the roster sentence exactly once — found "
        f"{_REVIEW_TEXT.count(_ROSTER_SENTENCE)}."
    )


def test_recovery_names_cap_critical_slug_and_its_custody_surfaces() -> None:
    slugs = _section(
        _RECOVERY_TEXT,
        _RECOVERY,
        "### Stall `site` slugs",
        "### Systemic-park breaker interaction",
    )
    bullet = _bullet(slugs, _RECOVERY, "cap_critical")
    where = "the `cap_critical` slug bullet"

    artefacts = (
        "critical-on-master",
        "ledger/custody.jsonl",
        "autopilot.custodyMarker",
        "batch.critical_on_master",
        "autopilot custody resolve",
    )
    _assert_present(bullet, _RECOVERY, where, artefacts)
    assert "migrated" in bullet, (
        f"{_RECOVERY}: expected {where} to name the migrated pending deferrals "
        "('migrated') — not found."
    )
    named = [p for p in _CHOICE_PATTERNS if re.search(p, bullet)]
    assert len(named) >= 2, (
        f"{_RECOVERY}: expected {where} to name at least two of the three "
        f"`--choice` values (revert, branch-and-revert, accept) — matched {named}."
    )
    negations = ("writes no marker", "not involved", "no journal")
    _assert_absent(bullet, _RECOVERY, where, negations)


def test_every_exit_table_2_row_carries_the_capture_failed_clause() -> None:
    rows = _rows_starting_with(_RECOVERY_TEXT, "| 2 |")
    assert len(rows) >= 3, (
        f"{_RECOVERY}: expected a `| 2 |` row in each of the three stall exit "
        f"tables (loop-mode procedure, oversized task, escalation exhausted) — "
        f"found {len(rows)}."
    )
    pins = (
        _CAPTURE_FAILED_PREFIX,
        "corrupted-state row",
        "wip/",
        "never delete `state.json`",
    )
    for row in rows:
        where = f"each `| 2 |` exit row (here {row!r})"
        _assert_present(row, _RECOVERY, where, pins)
        assert re.search(r"retry[^|]{0,40}ONCE", row), (
            f"{_RECOVERY}: expected {where} to retry the same stall ONCE "
            "(the verb bound to ONCE) — not found."
        )
        _assert_in_order(row, _RECOVERY, where, ("PAUSE", "sub_skill_fail"))
        _assert_absent(row, _RECOVERY, where, ("never retry", "not a site", "cosmetic"))

    # Whole-file on purpose: the old bare wording must not survive in any
    # copy of the table, so scoping this to one table would be weaker.
    assert _OLD_BARE_2_ROW not in _RECOVERY_TEXT, (
        f"{_RECOVERY}: found the bare pre-custody row {_OLD_BARE_2_ROW!r} — "
        "one exit table still lacks the capture-failed clause."
    )


def test_every_exit_table_9_row_covers_the_custody_write_failure() -> None:
    rows = _rows_starting_with(_RECOVERY_TEXT, "| 9 |")
    assert len(rows) >= 3, (
        f"{_RECOVERY}: expected a `| 9 |` row in each of the three stall exit "
        f"tables — found {len(rows)}."
    )
    pins = ("custody write failed", "hold/", "intent retained", "re-run the same stall")
    negations = ("do NOT re-run", "never exit 9", "intent is discarded")
    for row in rows:
        where = f"each `| 9 |` exit row (here {row!r})"
        _assert_present(row, _RECOVERY, where, pins)
        _assert_absent(row, _RECOVERY, where, negations)


def test_no_manual_range_flag_or_later_feature_leaks_into_the_skill_prose() -> None:
    md_files = sorted(_SKILL_DIR.rglob("*.md"))
    assert md_files, f"{_SKILL_DIR}: expected at least one .md file to sweep."

    # Absence checks stay whole-tree: scoping them would let the old flag or
    # a later feature's name reappear in another file and still pass.
    for path in md_files:
        text = path.read_text()
        for needle in _ABSENT_NEEDLES:
            assert needle not in text, (
                f"{path}: found {needle!r} — the custody range is derived "
                "internally (no manual range flag), and the stub-minting / "
                "design rework feature is not part of this task."
            )
