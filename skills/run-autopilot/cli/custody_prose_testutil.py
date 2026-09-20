"""Shared paths, anchors and assertion helpers for the custody prose pins in
`test_custody_prose.py` (phase-build, phase-review, recovery) and
`test_custody_prose_schema.py` (state-schema, SKILL.md).

Each target file is resolved relative to this file and read once at import;
the helpers slice a section, bullet, paragraph or table row out of that text
and assert on short, reword-resistant substrings, each with a failure message
naming what drifted.
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
# must find nothing, so this file may not spell any of them out. The
# stub-minting verb left this list when PRD 00195 landed it (its call sites
# are pinned by test_triage_prose.py).
_ABSENT_NEEDLES = (
    "--" + "commit-range",
    "--" + "range",
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


def _added_bullets(text: str, path: Path) -> str:
    """Every `### Added` block of the changelog, joined.

    A release stamps `[Unreleased]` into a version heading, so a pin that
    slices `[Unreleased]` alone goes red at the first release after it
    landed; the whole file keeps the entry wherever the release moved it.
    """
    blocks = re.findall(r"(?ms)^### Added[ \t]*$\n(.*?)(?=^##)", text + "\n## ")
    assert blocks, f"{path}: expected at least one '### Added' heading — not found."
    return "\n".join(blocks)


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
