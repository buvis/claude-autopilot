"""Tests binding the custody prose in run-autopilot's reference files — the
Phase 0 pending-custody handler and the Phase 3 `state.git_dir` capture in
`references/phase-build.md`, the loop-mode cap-out range sentence in
`references/phase-review.md`, and the `cap_critical` slug plus the
custody-aware exit rows in `references/recovery.md`. It also pins the
`[checks] custody push guard` and `[checks] custody core` blocks in
`dev/bin/release-checks` and the two custody entries under an `### Added`
heading in `CHANGELOG.md` (wherever the release moved them).

Mirrors test_dispatch_prose.py's pattern for pinning a skill file's prose:
resolve each target file's path relative to this file, read it once, and
assert on short, reword-resistant substrings, each with a failure message
naming what drifted. Presence assertions are scoped to the section that is
supposed to carry them, via `_section` in `custody_prose_testutil.py`, so
the pin still catches text that has moved out of its section. Each presence
pin binds a verb or an order to its noun (run X, writes Y, PAUSE before Z),
and each section also sweeps for the negations that would invert it
(`Do NOT run`, `never`, `is retired`), so prose that keeps every token but
tells the operator to do the opposite still fails. Absence assertions sweep
every `.md` under `skills/run-autopilot`.

`test_custody_prose_schema.py` pins `references/state-schema.md` and
`SKILL.md` the same way; the shared paths, anchors and assertion helpers
live in `custody_prose_testutil.py`.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cli.custody_prose_testutil import (
    _ABORT_CLOSING,
    _ABORT_HEADING,
    _ABSENT_NEEDLES,
    _BUILD_TEXT,
    _CAPTURE_FAILED_PREFIX,
    _CHOICE_PATTERNS,
    _CUSTODY_HEADING,
    _CUSTODY_WHERE,
    _OLD_BARE_2_ROW,
    _PHASE_BUILD,
    _PHASE_REVIEW,
    _RECOVERY,
    _RECOVERY_TEXT,
    _REVIEW_TEXT,
    _ROSTER_SENTENCE,
    _SELECTION_HEADING,
    _SKILL_DIR,
    _assert_absent,
    _assert_in_order,
    _assert_present,
    _bullet,
    _custody_section,
    _exit_code,
    _added_bullets,
    _rows_starting_with,
    _section,
)

_REPO_ROOT = _SKILL_DIR.parent.parent
_RELEASE_CHECKS = _REPO_ROOT / "dev" / "bin" / "release-checks"
_RELEASE_CHECKS_TEXT = _RELEASE_CHECKS.read_text()
_CHANGELOG = _REPO_ROOT / "CHANGELOG.md"
_CHANGELOG_TEXT = _CHANGELOG.read_text()

_CUSTODY_GUARD_BLOCK = (
    'echo "[checks] custody push guard"\n'
    "uv run --no-project --with pytest python -m pytest -q "
    "hooks/test_guard_push_on_critical.py\n"
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
    at = _exit_code(custody, _PHASE_BUILD, _CUSTODY_WHERE, 9)
    # Sliced after the exit-9 offset, like the exit-5/STOP sibling: a PAUSE
    # bound to some other exit row must not satisfy this pin.
    _assert_present(
        custody[at:],
        _PHASE_BUILD,
        f"{_CUSTODY_WHERE} after exit 9",
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
    # `cli/golden/lanes/` holds frozen PRD texts (the lane classifier's
    # fixture, PRD 00204), which are data, not the skill's prose.
    md_files = sorted(p for p in _SKILL_DIR.rglob("*.md") if "golden" not in p.parts)
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


def test_release_checks_runs_the_custody_push_guard_after_hook_registration() -> None:
    # The exact two-line block (one-line pytest, like the fast-track block),
    # placed after hook registration so the hook checks sit together.
    _assert_in_order(
        _RELEASE_CHECKS_TEXT,
        _RELEASE_CHECKS,
        "the release gate",
        ('echo "[checks] hook registration"', _CUSTODY_GUARD_BLOCK),
    )


def test_release_checks_runs_the_custody_core_suites_after_the_push_guard() -> None:
    core = 'echo "[checks] custody core"'
    recursion = 'echo "[checks] runner recursion guard"'
    _assert_in_order(
        _RELEASE_CHECKS_TEXT,
        _RELEASE_CHECKS,
        "the release gate",
        (_CUSTODY_GUARD_BLOCK, core, recursion),
    )
    block = _section(_RELEASE_CHECKS_TEXT, _RELEASE_CHECKS, core, recursion)
    suites = (
        "custody",
        "custody_stall",
        "custody_resolve",
        "custody_loud",
        "custody_entry",
        "custody_prose",
        "custody_prose_schema",
        "render_custody",
    )
    _assert_present(
        block,
        _RELEASE_CHECKS,
        "the `[checks] custody core` block",
        tuple(f"skills/run-autopilot/cli/test_{suite}.py" for suite in suites),
    )


def test_changelog_added_carries_both_custody_entries() -> None:
    # The whole file's Added blocks, not [Unreleased]: a release moves the
    # entry under its version heading.
    added = _added_bullets(_CHANGELOG_TEXT, _CHANGELOG)

    # Located by subject, never by count: other entries share these scopes.
    pins = (
        ("- **run-autopilot**:", "autopilot custody resolve"),
        ("- **hooks**:", "pending cap_critical custody"),
    )
    for lead, needle in pins:
        bullets = _rows_starting_with(added, lead)
        assert any(needle in bullet for bullet in bullets), (
            f"{_CHANGELOG}: expected a {lead!r} bullet under a "
            f"### Added heading mentioning {needle!r} — found {len(bullets)} {lead!r} "
            "bullet(s), none of which does."
        )


def test_forced_catchup_is_spent_once_the_prd_has_tasks() -> None:
    # PRD 00209: `catchup: force` defeats the batch cache at PRD entry only;
    # a same-PRD resume (tasks already planned) treats it as `run`.
    cache = _section(
        _BUILD_TEXT,
        _PHASE_BUILD,
        "### Batch cache check",
        "## Phase 1.5: Design",
    )
    _assert_present(
        cache,
        _PHASE_BUILD,
        "the Batch cache check",
        ("force already spent", "`state.tasks` is a non-empty list", "same-PRD resume"),
    )
    _assert_absent(
        _BUILD_TEXT,
        _PHASE_BUILD,
        "the frontmatter semantics",
        ("re-runs full catchup regardless of recency",),
    )


def test_phase_0_clears_inherited_markers_before_the_abort_handlers() -> None:
    # PRD 00210: the clear is the session's first Bash call after the
    # lifecycle mkdir and before any abort handler reads state.json.
    prologue = _section(
        _BUILD_TEXT,
        _PHASE_BUILD,
        "### Ensure lifecycle directories exist",
        "### Handle park request",
    )
    _assert_in_order(
        prologue,
        _PHASE_BUILD,
        "the Phase 0 prologue",
        (
            "lifecycle `mkdir -p` block",
            "### Clear inherited hand-off markers",
            "_walk_up.py --clear-markers",
            "never this session's to act on",
        ),
    )
    assert "--clear-cap" not in _BUILD_TEXT, (
        f"{_PHASE_BUILD}: still calls --clear-cap; the Phase 0 clear covers both markers"
    )

