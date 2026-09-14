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

The same module pins `references/state-schema.md` (the `critical-on-master`
marker row, the `## Custody journal` section, the `batch.critical_on_master`
mirror and `git_dir` field rows, the captured `stall_op` retry keys, and the
deferred-log `stall` / `custody` records) and `SKILL.md` (the push-denial
sentence in the Error Handling table, the row-1 parenthetical, and the
Retention durable entry for the custody journal).
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

_STATE_SCHEMA = _REFERENCES / "state-schema.md"
_SCHEMA_TEXT = _STATE_SCHEMA.read_text()

_SKILL = _SKILL_DIR / "SKILL.md"
_SKILL_TEXT = _SKILL.read_text()

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

_MARKER_ROW_LEAD = "| `critical-on-master` |"
_JOURNAL_HEADING = "## Custody journal"
_STALL_OP_LEAD = "`stall_op` (PRD 00051 task 10)"
_STALL_OP_SHAPE = "{op_id, prd, site, detail}"
_CAPTURE_KEYS = ("commit_range", "commits", "branch", "repo_root", "git_dir")
_CUSTODY_JOURNAL_PATH = "dev/local/autopilot/ledger/custody.jsonl"
_PUSH_DENIAL_SENTENCE = (
    "A push denied by hooks/guard_push_on_critical.py names a pending "
    "cap_critical custody: resolve it with autopilot custody resolve, never "
    "bypass the hook."
)
_CAPTURE_TWICE = "(including a cap_critical custody capture that fails twice)"
_ATTEMPT_LEDGER_HEADING = "## Attempt ledger"

# Shared negation sweep for every custody slice: a paraphrase that keeps the
# tokens but tells the reader the opposite trips one of these words.
_NEGATION = (
    r"(?i)\b(?:does not|do not|never|nothing|no one|nobody|unused|reserved|"
    r"not implemented|ignores?|dropped|struck|nominal|placeholder)\b"
)

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


def _h2_section(text: str, path: Path, heading: str) -> str:
    """Slice the `## heading` block up to the next `## ` heading (or EOF).

    Matches the heading as a whole line, so a `### heading` sub-heading or
    an inline mention neither anchors the slice nor counts as the heading.
    """
    pattern = rf"(?m)^{re.escape(heading)}[ \t]*$"
    matches = list(re.finditer(pattern, text))
    assert len(matches) == 1, (
        f"{path}: expected exactly one {heading!r} heading — found {len(matches)}."
    )
    start = matches[0].start()
    end = text.find("\n## ", matches[0].end())
    return text[start:] if end == -1 else text[start:end]


def _paragraph(text: str, path: Path, lead: str) -> str:
    """Slice the paragraph that starts with `lead`, up to the next blank line."""
    assert lead in text, f"{path}: expected a paragraph starting {lead!r} — not found."
    start = text.index(lead)
    end = text.find("\n\n", start)
    return text[start:] if end == -1 else text[start:end]


def _single_row(scope: str, path: Path, where: str, lead: str) -> str:
    rows = _rows_starting_with(scope, lead)
    assert len(rows) == 1, (
        f"{path}: expected exactly one row starting {lead!r} in {where} — "
        f"found {len(rows)}."
    )
    return rows[0]


def _cells(row: str) -> list[str]:
    """Split a one-line markdown table row into cells (an escaped `\\|` stays inside)."""
    return [cell.strip() for cell in re.split(r"(?<!\\)\|", row.strip())[1:-1]]


def _marker_files_section() -> str:
    return _section(_SCHEMA_TEXT, _STATE_SCHEMA, "## Marker files", "## Attempt ledger")


def _field_table() -> str:
    return _section(
        _SCHEMA_TEXT,
        _STATE_SCHEMA,
        "## Field Descriptions",
        "## Marker files",
    )


def _deferred_log_section() -> str:
    return _section(
        _SCHEMA_TEXT,
        _STATE_SCHEMA,
        "## Batch Deferred Log",
        "## Build-Session Model Promotion Signals",
    )


def _error_handling(end_anchor: str) -> str:
    return _section(_SKILL_TEXT, _SKILL, "## Error Handling", end_anchor)


def _assert_matches(
    scope: str, path: Path, where: str, pattern: str, what: str
) -> None:
    assert re.search(pattern, scope), f"{path}: expected {where} to {what} — not found."


def _assert_no_match(
    scope: str, path: Path, where: str, pattern: str, what: str
) -> None:
    match = re.search(pattern, scope)
    assert match is None, f"{path}: {where} says {match.group(0)!r} — {what}."


def _assert_bound(
    scope: str,
    path: Path,
    where: str,
    noun: str,
    verbs: str,
    window: int = 80,
) -> None:
    """`noun` within `window` chars of one of `verbs`, either order, inside one
    cell and one line, so a bare token cannot satisfy the pin."""
    gap = rf"[^|\n]{{0,{window}}}"
    pattern = rf"(?i){noun}{gap}\b(?:{verbs})\b|\b(?:{verbs})\b{gap}{noun}"
    _assert_matches(scope, path, where, pattern, f"bind {noun!r} to one of {verbs!r}")


def _assert_no_negation(
    scope: str,
    path: Path,
    where: str,
    banned: str = "",
    allow: tuple[str, ...] = (),
) -> None:
    """Neither `_NEGATION`'s words nor the `banned` alternation (case-insensitive
    substrings) may appear in `scope`. `allow` lists the exact phrases the contract
    itself uses (`never delete`); each is blanked first so its word cannot trip."""
    blanked = scope
    for phrase in allow:
        blanked = blanked.replace(phrase, " ")
    pattern = f"{_NEGATION}|{banned}" if banned else _NEGATION
    what = "a negation that inverts the contract while keeping its tokens"
    _assert_no_match(blanked, path, where, pattern, what)


def _assert_carries_commit_range(
    scope: str, where: str, verbs: str, window: int
) -> None:
    """`cap_critical` and `commit_range` joined by one of `verbs`, either order."""
    verbs, gap = rf"\b(?:{verbs})\b", r"[^\n]{0,120}"
    pattern = (
        rf"cap_critical[^\n]{{0,{window}}}{verbs}[^\n]{{0,80}}commit_range"
        rf"|{verbs}{gap}(?:cap_critical{gap}commit_range|commit_range{gap}cap_critical)"
    )
    what = (
        "say a cap_critical record carries `commit_range` (keys in a positive clause)"
    )
    _assert_matches(scope, _STATE_SCHEMA, where, pattern, what)


def _typed_row(where: str, lead: str, type_name: str) -> str:
    """The single Field-table row starting `lead`, whose Type cell says `type_name`."""
    row = _single_row(
        _field_table(), _STATE_SCHEMA, "the Field Descriptions table", lead
    )
    cells = _cells(row)
    assert len(cells) >= 3 and type_name in cells[1], (
        f"{_STATE_SCHEMA}: expected the Type cell of {where} to say {type_name!r} — got {cells!r}."
    )
    return row


def _prose(section: str) -> str:
    """Drop fenced code blocks so a token dump inside a fence satisfies no pin."""
    return re.sub(r"(?s)```.*?(?:```|\Z)", " ", section)


def _assert_h2_beside(text: str, path: Path, heading: str, neighbour: str) -> None:
    """`heading` must be the H2 immediately before or after `neighbour`."""
    headings = [m.group(0).rstrip() for m in re.finditer(r"(?m)^## .*$", text)]
    at = headings.index(heading)
    beside = headings[max(at - 1, 0) : at + 2]
    assert neighbour in beside, (
        f"{path}: expected {heading!r} next to {neighbour!r} — its H2 neighbours are {beside!r}."
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


def test_marker_table_names_critical_on_master_writer_consumer_and_restore() -> None:
    table = _marker_files_section()
    row = _single_row(table, _STATE_SCHEMA, "the Marker files table", _MARKER_ROW_LEAD)
    where = "the `critical-on-master` marker row"
    cells = _cells(row)
    assert len(cells) >= 4, (
        f"{_STATE_SCHEMA}: expected four cells in {where} — got {row!r}."
    )
    writer, consumer, content = cells[1], cells[2], cells[3]
    writer_where, consumer_where = (
        f"the Writer cell of {where}",
        f"the Consumer cell of {where}",
    )
    _assert_matches(
        writer,
        _STATE_SCHEMA,
        writer_where,
        r"do_stall[^|]{0,40}step 4b",
        "name step 4b",
    )
    writing = r"writ\w*|append\w*|upsert\w*|record\w*"
    _assert_bound(writer, _STATE_SCHEMA, writer_where, "do_stall", writing)
    reading = r"reads|read by|checks|checked by|consults|consulted by|denies"
    _assert_bound(
        consumer, _STATE_SCHEMA, consumer_where, r"guard_push_on_critical\.py", reading
    )
    handling = r"reads|read by|handles|handled by|runs|lists|resolves"
    _assert_bound(consumer, _STATE_SCHEMA, consumer_where, "Phase 0", handling)
    _assert_present(
        content, _STATE_SCHEMA, f"the Content cell of {where}", ('{"entries"',)
    )
    restore = (
        r"restor\w+[^|]{0,60}\b(?:from|via|by)\b[^|]{0,30}journal"
        r"|journal[^|]{0,60}\b(?:is|as) the restore source"
    )
    what = "name the journal as the restore source (restored from/via/by it, or it is/as the source)"
    _assert_matches(row, _STATE_SCHEMA, where, restore, what)
    what = "warn that purge-devlocal's 14-day rule may trash the marker"
    _assert_matches(row, _STATE_SCHEMA, where, r"purge-devlocal|\b14\b", what)
    _assert_no_negation(
        row,
        _STATE_SCHEMA,
        where,
        r"no consumer|never written|not restored|no restore|does not (?:touch|read|write)"
        r"|ignores|nothing restores|may trash it at will|none [—-]",
    )


def test_custody_journal_section_lists_events_compaction_gc_exemption_and_locator() -> (
    None
):
    journal = _h2_section(_SCHEMA_TEXT, _STATE_SCHEMA, _JOURNAL_HEADING)
    _assert_h2_beside(
        _SCHEMA_TEXT, _STATE_SCHEMA, _JOURNAL_HEADING, _ATTEMPT_LEDGER_HEADING
    )
    where = f"the {_JOURNAL_HEADING!r} section"
    # Fenced blocks are dropped first: a token dump inside a fence is not prose.
    prose, prose_where = _prose(journal), f"the prose of {where}"
    _assert_present(
        journal, _STATE_SCHEMA, where, ("ledger/custody.jsonl", "head_before")
    )
    events = ('"recorded"', '"resolving"', '"resolved"')
    _assert_in_order(prose, _STATE_SCHEMA, prose_where, events)
    recorded = (
        r'(?i)\bevents?\b[^\n]{0,120}"recorded"'
        r'|"recorded"[^\n]{0,80}(?:appended|written|at step 4b)'
    )
    what = 'bind "recorded" to an event sentence (appended/written/at step 4b)'
    _assert_matches(prose, _STATE_SCHEMA, prose_where, recorded, what)
    # One sentence = no `. ` in between (`custody.jsonl` stays inside one).
    within = r"(?:(?!\. )[^\n]){0,200}"
    gc_exempt = rf"(?:GC-exempt|purge-devlocal){within}ledger/|ledger/{within}(?:GC-exempt|purge-devlocal)"
    what = "state the GC exemption in the same sentence as `ledger/`"
    _assert_matches(prose, _STATE_SCHEMA, prose_where, gc_exempt, what)
    what = "say the journal is compacted to the still-pending rows"
    _assert_matches(
        prose, _STATE_SCHEMA, prose_where, r"(?i)compact\w*[^\n]{0,120}pending", what
    )
    _assert_bound(
        prose,
        _STATE_SCHEMA,
        prose_where,
        r"autopilot\.custodyMarker",
        "git config --local",
    )
    _assert_bound(prose, _STATE_SCHEMA, prose_where, "unset", r"resolve\w*")
    _assert_no_negation(
        journal,
        _STATE_SCHEMA,
        where,
        r"never compacted|is trashed|no locator|never unset|tokens kept|prose pin",
        allow=("never truncates",),
    )


def test_field_table_batch_critical_on_master_row_mirrors_marker_entries() -> None:
    where = "the `batch.critical_on_master` field row"
    row = _typed_row(where, "| `batch.critical_on_master` |", "object[]")
    mirror = r"(?i)(?<!\bno )(?<!\bnot a )mirrors?\b[^|]{0,80}\b(entries|marker)"
    what = "say it mirrors the marker entries (not 'no mirror')"
    _assert_matches(row, _STATE_SCHEMA, where, mirror, what)
    _assert_bound(row, _STATE_SCHEMA, where, "do_stall", r"upsert\w*|writ\w*|append\w*")
    obj, actor = r"\b(?:entry|it|element)\b", "autopilot custody resolve"
    removed = (
        rf"{obj}[^|]{{0,40}}remov\w*[^|]{{0,80}}{actor}"
        rf"|remov\w*[^|]{{0,40}}{obj}[^|]{{0,80}}{actor}"
        rf"|{actor}[^|]{{0,80}}remov\w*[^|]{{0,40}}{obj}"
    )
    what = f"say the entry is removed by `{actor}` (the verb bound to object and actor)"
    _assert_matches(row, _STATE_SCHEMA, where, removed, what)
    _assert_no_negation(
        row,
        _STATE_SCHEMA,
        where,
        r"not a mirror|never removed|never written|no mirror|removes nothing"
        r"|nothing ever populates|skips it",
    )


def test_field_table_git_dir_row_is_captured_at_phase_3_and_reset_per_prd() -> None:
    where = "the `git_dir` field row"
    row = _typed_row(where, "| `git_dir` |", "string?")
    _assert_present(row, _STATE_SCHEMA, where, ("--git-dir",))
    _assert_bound(row, _STATE_SCHEMA, where, "Phase 3", r"captur\w*")
    _assert_bound(row, _STATE_SCHEMA, where, "repo_root", "alongside|with", 30)
    reset = (
        r"(?i)\b(?:cleared|reset)\b[^|]{0,80}Phase 9 step 10"
        r"|Phase 9 step 10[^|]{0,80}\b(?:clears|resets|cleared|reset)\b"
        r"|\b(?:cleared|reset)\b[^|]{0,30}\bper[- ]PRD\b"
    )
    what = "say the field is cleared/reset per PRD (the verb bound to Phase 9 step 10)"
    _assert_matches(row, _STATE_SCHEMA, where, reset, what)
    _assert_no_negation(
        row,
        _STATE_SCHEMA,
        where,
        r"never reset|nothing reads it|never captured|does not set|not captured"
        r"|not passed|leaves it untouched|no consumer|always absent",
    )


def test_stall_op_paragraph_carries_the_cap_critical_capture_keys() -> None:
    para = _paragraph(_marker_files_section(), _STATE_SCHEMA, _STALL_OP_LEAD)
    where = "the `stall_op` paragraph of `## Marker files`"
    _assert_present(para, _STATE_SCHEMA, where, (_STALL_OP_SHAPE, "cap_critical"))
    after = para[para.index(_STALL_OP_SHAPE) + len(_STALL_OP_SHAPE) :]
    for key in _CAPTURE_KEYS:
        what = f"name the capture key {key!r} after the {_STALL_OP_SHAPE!r} shape"
        _assert_matches(after, _STATE_SCHEMA, where, rf"\b{key}\b", what)
    _assert_carries_commit_range(
        para, where, "carries|adds|records|stamps|persists", 240
    )
    _assert_no_negation(
        para,
        _STATE_SCHEMA,
        where,
        r"no extra keys|carries nothing else|only these four|not stored|no others"
        r"|recomputes|exactly those four",
        allow=("never runs git again",),
    )


def test_deferred_log_stall_bullet_lists_cap_critical_with_its_capture_keys() -> None:
    bullet = _bullet(_deferred_log_section(), _STATE_SCHEMA, "stall")
    where = "the deferred-log `stall` bullet"
    _assert_present(bullet, _STATE_SCHEMA, where, ("cap_critical",))
    for key in ("commit_range", "commits", "branch"):
        what = f"name the cap_critical capture key {key!r}"
        _assert_matches(bullet, _STATE_SCHEMA, where, rf"\b{key}\b", what)
    _assert_carries_commit_range(
        bullet, where, "carries|records|adds|stamps|gains", 200
    )
    _assert_no_negation(
        bullet,
        _STATE_SCHEMA,
        where,
        r"not recorded|never written|same bare shape|rather than stored",
    )


def test_deferred_log_custody_bullet_documents_the_resolution_record() -> None:
    section = _deferred_log_section()
    lead = "- `custody`"
    assert section.count(lead) == 1, (
        f"{_STATE_SCHEMA}: expected exactly one {lead!r} bullet — found {section.count(lead)}."
    )
    bullet = _bullet(section, _STATE_SCHEMA, "custody")
    where = "the deferred-log `custody` bullet"
    what = 'show the `"type": "custody"` record shape'
    _assert_matches(bullet, _STATE_SCHEMA, where, r'"type":\s*"custody"', what)
    _assert_present(bullet, _STATE_SCHEMA, where, ("choice", "commit_range"))
    missing = [p for p in _CHOICE_PATTERNS if not re.search(p, bullet)]
    assert not missing, (
        f"{_STATE_SCHEMA}: expected {where} to name all three `choice` values "
        f"(revert, branch-and-revert, accept) — unmatched patterns {missing}."
    )
    writing = "writes|written|appends|appended|records|recorded"
    _assert_bound(
        bullet, _STATE_SCHEMA, where, "autopilot custody resolve", writing, 120
    )
    suffix = r'<op_id>-resolve|op_id[^\n]{0,30}["`]-resolve["`]'
    what = "pin `-resolve` as the op_id suffix (`<op_id>-resolve`)"
    _assert_matches(bullet, _STATE_SCHEMA, where, suffix, what)
    _assert_no_negation(
        bullet,
        _STATE_SCHEMA,
        where,
        r"not recorded|never written|never emitted|no such record|instead|would carry",
    )


def test_git_push_row_routes_a_guard_denial_to_custody_resolve() -> None:
    table = _error_handling("**Loop mode never halts the whole batch")
    row = _single_row(
        table, _SKILL, "the `## Error Handling` table", "| Git push fails"
    )
    where = "the `Git push fails` row"
    _assert_present(row, _SKILL, where, (_PUSH_DENIAL_SENTENCE,))
    # No countermand after the sentence in its own cell, no strike-through,
    # and no hook bypass anywhere in the row once the sentence is stripped.
    cell = next(c for c in _cells(row) if _PUSH_DENIAL_SENTENCE in c)
    tail = cell[cell.index(_PUSH_DENIAL_SENTENCE) + len(_PUSH_DENIAL_SENTENCE) :]
    _assert_absent(
        tail,
        _SKILL,
        f"the text after the push-denial sentence in {where}",
        ("CONTINUE",),
    )
    what = "a strike-through or a countermand of the push-denial sentence"
    _assert_no_match(
        row, _SKILL, where, r"(?i)~~|hooksPath|no-verify|skip-hook|re-run|struck", what
    )
    what = "'bypass' outside the pinned sentence (its only sanctioned use is 'never bypass the hook')"
    _assert_no_match(
        row.replace(_PUSH_DENIAL_SENTENCE, " "), _SKILL, where, r"(?i)bypass", what
    )
    _assert_no_negation(row, _SKILL, where, allow=("never bypass the hook",))


def test_error_handling_row_1_names_the_twice_failed_custody_capture() -> None:
    section = _error_handling("**Turn-ending PAUSE rows")
    where = "the `## Error Handling` section"
    lines = [
        line for line in section.splitlines() if "Security-critical finding" in line
    ]
    assert lines, (
        f"{_SKILL}: expected {where} to mention 'Security-critical finding' — not found."
    )
    carrying = [line for line in lines if _CAPTURE_TWICE in line]
    assert carrying, (
        f"{_SKILL}: expected a 'Security-critical finding' line in {where} to "
        f"carry {_CAPTURE_TWICE!r} — none of {len(lines)} does."
    )
    assert section.count(_CAPTURE_TWICE) == 1, (
        f"{_SKILL}: expected {_CAPTURE_TWICE!r} once in {where} — found {section.count(_CAPTURE_TWICE)}."
    )
    bound = rf"vulnerability being shipped[^\n]{{0,20}}{re.escape(_CAPTURE_TWICE)}"
    what = "carry the parenthetical right after 'vulnerability being shipped' (bound to the trigger)"
    for line in carrying:
        line_where = f"the row-1 line {line!r}"
        _assert_matches(line, _SKILL, line_where, bound, what)
        _assert_no_negation(
            line,
            _SKILL,
            line_where,
            r"fails once|fails three times|excluded|not security|bookkeeping|CONTINUE|log it",
        )


def test_retention_durable_list_names_the_custody_journal() -> None:
    retention = _section(_SKILL_TEXT, _SKILL, "### Retention", "### Resuming")
    where = "the `- **Durable**` retention line"
    durable = _single_row(
        retention, _SKILL, "the `### Retention` list", "- **Durable**"
    )
    _assert_present(durable, _SKILL, where, (_CUSTODY_JOURNAL_PATH,))
    tail = durable[durable.index(_CUSTODY_JOURNAL_PATH) + len(_CUSTODY_JOURNAL_PATH) :]
    assert re.match(r"`?\s*\(", tail), (
        f"{_SKILL}: expected a parenthetical right after {_CUSTODY_JOURNAL_PATH!r} in "
        f"{where}, like the attempt-ledger entry — got {tail[:40]!r}."
    )
    next_path = tail.find("`dev/local")
    blurb = tail if next_path == -1 else tail[:next_path]
    blurb_where = f"the parenthetical after {_CUSTODY_JOURNAL_PATH!r} in {where}"
    _assert_present(blurb, _SKILL, blurb_where, ("custody journal",))
    source = r"(?i)(?<!\bnot )\b(?:the|its|a)\b(?:\s+[\w'’-]+){0,2}\s+restore source"
    what = "call the journal the/its/a restore source (not 'NOT a restore source')"
    _assert_matches(blurb, _SKILL, blurb_where, source, what)
    _assert_no_negation(
        blurb,
        _SKILL,
        blurb_where,
        r"not a restore source|prose linter|goes out with|delete freely",
    )
    _assert_no_negation(durable, _SKILL, where, allow=("never delete",))
    disposable = _single_row(
        retention, _SKILL, "the `### Retention` list", "- **Disposable**"
    )
    what = "the custody journal (any name for it, or its `ledger/` dir) is durable, never disposable"
    _assert_no_match(
        disposable,
        _SKILL,
        "the `- **Disposable**` retention line",
        r"(?i)custody|ledger/",
        what,
    )
