"""Tests binding the custody prose in `references/state-schema.md` (the
`critical-on-master` marker row, the `## Custody journal` section, the
`batch.critical_on_master` mirror and `git_dir` field rows, the captured
`stall_op` retry keys, and the deferred-log `stall` / `custody` records) and
`SKILL.md` (the push-denial sentence in the Error Handling table, the row-1
parenthetical, and the Retention durable entry for the custody journal).

Same pattern as `test_custody_prose.py`; the shared paths, anchors and
assertion helpers live in `custody_prose_testutil.py`.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cli.custody_prose_testutil import (
    _ATTEMPT_LEDGER_HEADING,
    _CAPTURE_KEYS,
    _CAPTURE_TWICE,
    _CHOICE_PATTERNS,
    _CUSTODY_JOURNAL_PATH,
    _JOURNAL_HEADING,
    _MARKER_ROW_LEAD,
    _PUSH_DENIAL_SENTENCE,
    _SCHEMA_TEXT,
    _SKILL,
    _SKILL_TEXT,
    _STALL_OP_LEAD,
    _STALL_OP_SHAPE,
    _STATE_SCHEMA,
    _assert_absent,
    _assert_bound,
    _assert_carries_commit_range,
    _assert_h2_beside,
    _assert_in_order,
    _assert_matches,
    _assert_no_match,
    _assert_no_negation,
    _assert_present,
    _bullet,
    _cells,
    _deferred_log_section,
    _error_handling,
    _h2_section,
    _marker_files_section,
    _paragraph,
    _prose,
    _section,
    _single_row,
    _typed_row,
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
    # The resolve instruction belongs to the Interactive cell (the one that
    # pushes); the Loop-mode cell defers the denial to the attended Phase 0
    # and never instructs a headless resolve.
    cells = _cells(row)
    interactive, loop = cells[1], cells[2]
    assert _PUSH_DENIAL_SENTENCE in interactive, (
        f"{_SKILL}: expected the push-denial sentence in the Interactive cell of "
        f"{where} — found it elsewhere or not at all."
    )
    assert _PUSH_DENIAL_SENTENCE not in loop, (
        f"{_SKILL}: the Loop-mode cell of {where} carries the push-denial sentence "
        "— an unattended session must not be told to run custody resolve."
    )
    _assert_present(
        loop, _SKILL, f"the Loop-mode cell of {where}", ("Handle pending custody",)
    )
    assert "custody resolve" not in loop, (
        f"{_SKILL}: the Loop-mode cell of {where} names `custody resolve` — loop "
        "mode leaves resolution to the attended Phase 0."
    )
    # No countermand after the sentence in its own cell, no strike-through,
    # and no hook bypass anywhere in the row once the sentence is stripped.
    cell = interactive
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
