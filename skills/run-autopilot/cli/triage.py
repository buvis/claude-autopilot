#!/usr/bin/env python3
"""triage.py - mint hold stubs for unowned deferred severe findings (PRD 00195).

An open CRITICAL/HIGH row in a batch's deferred JSON, or a `cap_critical`
stall row, lives only in that JSON until someone writes a PRD for it. This
module gives each such row a file: `dev/local/prds/hold/<NNNNN>-triage-
<slug>-v1.md`, a HOLD triage artifact whose single task is "promote to
backlog or close". Autopilot never drains `hold/`, so nothing here is ever
executed; the stub only makes the finding visible to the backlog reviewer.

    ledger_key(text)                              -> 12 hex chars
    mint_stubs(autopilot_dir, prds_dir, batch_id) -> {"minted": [...], "skipped": n}

Ownership: a row's `ledger_key` (sha1 over `render_report._normalize` of its
issue, else detail) appearing in the first 20 lines of ANY PRD under
backlog/, wip/, hold/ or done/ means the row has an owner - a minted stub, or
a hand-written PRD that quotes the key. Identical normalized text folds to
one key, so duplicate rows (a cap-overflow record and its migrated
deferred_decision twin) mint one stub, and a rerun mints nothing.

Allocation: the next free five-digit sequence at the tail of the four PRD
directories plus `dev/local/discovery` (discovery reserves numbers but owns no
ledger keys). The candidate is written first, then the directories are
rescanned; when a different work item claimed the same number meanwhile,
this attempt's OWN file is renumbered to a fresh tail number and the rescan
repeats until the number is unique. Another writer's file is never moved.
Two revisions of one work unit (`00042-foo-v1.md`, `00042-foo-v2.md`) share
a number by design and are not a collision.

Errors: `LedgerError` (a ValueError; distinct from fablectl's ledger of the
same name, which is the fable-attempt ledger) for a deferred JSON that
exists but cannot be read, decoded or is not `{"items": [...]}`; an absent
ledger (a batch that deferred nothing never creates one) mints nothing and
is not an error. OSError from any stub write. Publication is exclusive and
atomic (sidecar write, then `os.link`), so a rival holding the exact same
name is never replaced and a crash mid-write publishes nothing. A run that
fails midway leaves the stubs it published, and each of those owns its key,
so a retry mints only the rest.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

from . import custody, render_report, selection

LIFECYCLE_DIRS = ("backlog", "wip", "hold", "done")
DISCOVERY_DIR = "discovery"
OWNERSHIP_LINES = 20
SEVERE = frozenset({"critical", "high"})
_SLUG_MAX = 40
_TITLE_MAX = 80
_REVISION_RE = re.compile(r"-v\d+\.md$")

TRIAGE_TASK = (
    "- [ ] triage: promote to backlog or close - Acceptance: this file is no "
    "longer under dev/local/prds/hold/"
)


# The frozen hold artifact: the create-prd minimal template's heading order
# (H1, Problem, Solution, Requirements, Must have, Nice to have, Implementation,
# Module: triage, Dependencies, Tasks, Phase 0: Foundation, Phase 1: Core,
# Success Criteria), inlined so the plugin never reads an operator's template.
_STUB_TEMPLATE = """\
---
catchup: skip
design: skip
ledger: deferred/{batch_id}-deferred.json
ledger_key: {key}
source_prd: {source_prd}
severity: {severity}
---

# Triage: {title}

## Problem

{problem}
## Solution

Attended triage. A human promotes this finding into a backlog PRD through \
normal PRD authoring and review, or closes it. Autopilot never drains \
`dev/local/prds/hold/`, and this stub is never auto-promoted.

## Requirements

### Must have
- A triage decision for ledger key `{key}`: a backlog PRD, or closed.

### Nice to have
- None until triage.

## Implementation

### Module: triage
- **Location**: `dev/local/prds/hold/`
- **Responsibility**: hold ledger key `{key}` from `{source_prd}` until a human \
triages it
- **Exports**: none

### Dependencies
- triage: No dependencies (foundation)

## Tasks

### Phase 0: Foundation
{task}

### Phase 1: Core
No implementation tasks until attended triage.

## Success Criteria

- This file is no longer under `dev/local/prds/hold/`.
"""


class LedgerError(ValueError):
    """The batch deferred JSON is unreadable or not `{"items": [...]}`."""


def ledger_key(text) -> str:
    """The first 12 hex characters of sha1 over the normalized text."""
    normalized = render_report._normalize(text)
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:12]


def load_ledger(path: Path) -> list | None:
    """The ledger's `items`; None when the file does not exist (a batch that
    deferred nothing never creates it); LedgerError naming what is wrong with
    a file that exists but cannot be read or is not `{"items": [...]}`."""
    if not path.exists():
        return None
    try:
        raw = path.read_bytes()
    except OSError as err:
        raise LedgerError(f"cannot read ledger {path}: {err}") from err
    try:
        content = json.loads(raw)
    except ValueError as err:
        # json.loads decodes the bytes itself, so a UnicodeDecodeError lands
        # here as the ValueError it is, not as a traceback.
        raise LedgerError(f"ledger {path} is not valid JSON: {err}") from err
    if not isinstance(content, dict) or not isinstance(content.get("items"), list):
        raise LedgerError(f'ledger {path} is not {{"items": [...]}}')
    return content["items"]


def qualifies(row) -> bool:
    """An open row at CRITICAL/HIGH (case-insensitive), or a cap_critical stall."""
    if not isinstance(row, dict) or not render_report._is_open(row):
        return False
    if row.get("type") == "stall":
        return row.get("site") == custody.CUSTODY_SITE
    return str(row.get("severity") or "").strip().casefold() in SEVERE


def finding_text(row: dict) -> str | None:
    """The row's issue, else its detail, else None (nothing to key on)."""
    for field in ("issue", "detail"):
        value = row.get(field)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _prd_heads(prds_dir: Path) -> list[str]:
    """The first OWNERSHIP_LINES lines of every PRD in the four lifecycle dirs."""
    heads = []
    for lifecycle in LIFECYCLE_DIRS:
        directory = prds_dir / lifecycle
        if not directory.is_dir():
            continue
        for path in sorted(directory.iterdir()):
            if path.suffix != ".md" or not path.is_file():
                continue
            with path.open(encoding="utf-8", errors="replace") as handle:
                heads.append("".join(handle.readline() for _ in range(OWNERSHIP_LINES)))
    return heads


def _sequence_dirs(prds_dir: Path) -> list[Path]:
    return [prds_dir / d for d in LIFECYCLE_DIRS] + [prds_dir.parent / DISCOVERY_DIR]


def _numbered(prds_dir: Path) -> list[tuple[int, Path]]:
    """Every (sequence, path) across the five sequence directories."""
    found = []
    for directory in _sequence_dirs(prds_dir):
        if not directory.is_dir():
            continue
        for path in directory.iterdir():
            number = selection.sequence(path.name)
            if number is not None:
                found.append((number, path))
    return found


def next_sequence(prds_dir: Path) -> int:
    """One past the highest sequence in the four PRD dirs and discovery."""
    numbers = [number for number, _ in _numbered(prds_dir)]
    return max(numbers, default=0) + 1


def _work_unit(name: str) -> str:
    return _REVISION_RE.sub("", name)


def _claimed_by_other(prds_dir: Path, own: Path) -> bool:
    """A file other than `own` (and not a revision of it) carries own's number."""
    number = selection.sequence(own.name)
    return any(
        n == number and path != own and _work_unit(path.name) != _work_unit(own.name)
        for n, path in _numbered(prds_dir)
    )


def _write_candidate(path: Path, content: str) -> None:
    """Publish a stub at `path` exclusively and atomically: the content goes
    to a dotted sidecar first, then `os.link` publishes it under `path`,
    which fails with FileExistsError when a rival already holds that exact
    name and never exposes a half-written file (a crash mid-write leaves only
    the sidecar, which no reader treats as a PRD). Module-level so a test can
    interpose a rival claim between this write and the rescan that follows."""
    sidecar = path.with_name(f".{path.name}.tmp")
    try:
        sidecar.write_text(content, encoding="utf-8")
        os.link(sidecar, path)
    finally:
        sidecar.unlink(missing_ok=True)


def _relink(path: Path, fresh: Path) -> bool:
    """Move our own stub to `fresh` without ever replacing a rival there:
    True when the new name was taken by us, False when it already existed."""
    try:
        os.link(path, fresh)
    except FileExistsError:
        return False
    path.unlink()
    return True


def _allocate(prds_dir: Path, slug: str, content: str) -> Path:
    hold = prds_dir / "hold"
    hold.mkdir(parents=True, exist_ok=True)
    while True:
        path = hold / f"{next_sequence(prds_dir):05d}-triage-{slug}-v1.md"
        try:
            _write_candidate(path, content)
        except FileExistsError:
            continue
        break
    while _claimed_by_other(prds_dir, path):
        fresh = hold / f"{next_sequence(prds_dir):05d}-triage-{slug}-v1.md"
        if _relink(path, fresh):
            path = fresh
    return path


def slugify(text: str) -> str:
    words = re.sub(r"[^a-z0-9]+", "-", text.casefold()).strip("-")
    return words[:_SLUG_MAX].rstrip("-") or "finding"


def _severity(row: dict) -> str:
    if row.get("type") == "stall":
        return "critical"
    return str(row.get("severity")).strip().casefold()


def _provenance(row: dict, batch_id: str) -> str:
    parts = [f"batch `{batch_id}`", f"ledger `deferred/{batch_id}-deferred.json`"]
    for field in ("type", "site", "topic", "cycle", "consensus", "op_id"):
        if row.get(field) not in (None, ""):
            parts.append(f"{field} `{row[field]}`")
    return ", ".join(parts)


def _title(row: dict, key: str) -> str:
    if row.get("topic"):
        return str(row["topic"])
    text = " ".join(str(finding_text(row) or key).split())
    return text if len(text) <= _TITLE_MAX else text[: _TITLE_MAX - 3].rstrip() + "..."


def _problem(row: dict, batch_id: str, source_prd: str) -> str:
    lines = [
        f"Deferred finding with no PRD owner when this stub was minted: "
        f"{_provenance(row, batch_id)}, raised against `{source_prd}`.",
        "",
    ]
    for field in ("issue", "detail"):
        value = row.get(field)
        if isinstance(value, str) and value.strip():
            lines += [f"{field.capitalize()}: {value}", ""]
    return "\n".join(lines)


def render_stub(row: dict, batch_id: str, key: str) -> str:
    """The hold artifact: the create-prd minimal heading order, filled with
    ledger provenance and the single triage action."""
    source_prd = str(row.get("prd") or "unknown")
    return _STUB_TEMPLATE.format(
        batch_id=batch_id,
        key=key,
        source_prd=source_prd,
        severity=_severity(row),
        title=_title(row, key),
        problem=_problem(row, batch_id, source_prd),
        task=TRIAGE_TASK,
    )


def mint_stubs(autopilot_dir: Path, prds_dir: Path, batch_id: str) -> dict:
    """Mint one hold stub per qualifying, unowned, distinct ledger key of
    `<autopilot_dir>/deferred/<batch_id>-deferred.json`.

    Returns `{"minted": [<basename>, ...], "skipped": n}`, `skipped` counting
    every row that produced no file (not qualifying, no text, owned, or a
    duplicate of an earlier row).
    """
    rows = load_ledger(Path(autopilot_dir) / "deferred" / f"{batch_id}-deferred.json")
    if rows is None:
        print("autopilot: mint-stubs: ledger absent, nothing to mint", file=sys.stderr)
        return {"minted": [], "skipped": 0}
    prds_dir = Path(prds_dir)
    heads = _prd_heads(prds_dir)
    minted: list[str] = []
    seen: set[str] = set()
    skipped = 0
    for row in rows:
        text = finding_text(row) if qualifies(row) else None
        if text is None:
            skipped += 1
            continue
        key = ledger_key(text)
        if key in seen or any(key in head for head in heads):
            skipped += 1
            continue
        seen.add(key)
        slug = slugify(str(row.get("topic") or text))
        path = _allocate(prds_dir, slug, render_stub(row, batch_id, key))
        minted.append(path.name)
    return {"minted": minted, "skipped": skipped}
