#!/usr/bin/env python3
"""triage.py - mint hold stubs for unowned deferred severe findings (PRD 00195).

An open CRITICAL/HIGH row in a batch's deferred JSON, or a `cap_critical` or
`cap_regression` stall row, lives only in that JSON until someone writes a PRD for it. This
module gives each such row a file: `docs/dev/project-management/prds/hold/<NNNNN>-triage-
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
directories plus `docs/dev/project-management/discovery` (discovery reserves numbers but owns no
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
import tempfile
from pathlib import Path

from . import custody, render_report, selection

LIFECYCLE_DIRS = ("backlog", "wip", "hold", "done")
DISCOVERY_DIR = "discovery"
OWNERSHIP_LINES = 20
SEVERE = frozenset({"critical", "high", "\U0001f534", "\U0001f7e0"})
_SLUG_MAX = 40
_TITLE_MAX = 80
_REVISION_RE = re.compile(r"-v\d+\.md$")
# The cap-check regression stall site (PRD 00310/00321): mints a stub like a
# cap_critical stall, but has no custody record.
REGRESSION_SITE = "cap_regression"
FOLD_JACCARD = 0.25
_TOKEN_RE = re.compile(r"[a-z0-9_]+")

TRIAGE_TASK = (
    "- [ ] triage: promote to backlog or close - Acceptance: this file is no "
    "longer under docs/dev/project-management/prds/hold/"
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
{ledger_keys}source_prd: {source_prd}
severity: {severity}
---

# Triage: {title}

## Problem

{problem}
## Solution

Attended triage. A human promotes this finding into a backlog PRD through \
normal PRD authoring and review, or closes it. Autopilot never drains \
`docs/dev/project-management/prds/hold/`, and this stub is never auto-promoted. \
A PRD that absorbs this stub quotes its ledger_key line (every key when there \
are several) in its first 20 lines, or the next finalize mints the finding again.

## Requirements

### Must have
- A triage decision for ledger key `{key}`: a backlog PRD, or closed.

### Nice to have
- None until triage.

## Implementation

### Module: triage
- **Location**: `docs/dev/project-management/prds/hold/`
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

- This file is no longer under `docs/dev/project-management/prds/hold/`.
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
    """An open row at CRITICAL/HIGH (case-insensitive), or a cap_critical or
    cap_regression stall."""
    if not isinstance(row, dict) or not render_report._is_open(row):
        return False
    if row.get("type") == "stall":
        return row.get("site") in (custody.CUSTODY_SITE, REGRESSION_SITE)
    if row.get("type") == "review-critical" and str(
        row.get("action") or ""
    ).startswith("fix in cycle"):
        return False
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
    to a dotted sidecar that is unique to this call (`mkstemp`, so two writers
    racing for the same name never share one), then `os.link` publishes it
    under `path`, which fails with FileExistsError when a rival already holds
    that exact name and never exposes a half-written file (a crash mid-write
    leaves only the sidecar, which no reader treats as a PRD). Module-level
    so a test can interpose a rival claim between this write and the rescan
    that follows."""
    sidecar = _stage(path, content)
    try:
        os.link(sidecar, path)
    finally:
        sidecar.unlink(missing_ok=True)


def _stage(path: Path, content: str) -> Path:
    """Write `content` to a sidecar unique to this call beside `path`."""
    handle, name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    with os.fdopen(handle, "w", encoding="utf-8") as fh:
        fh.write(content)
    return Path(name)


def _relink(path: Path, fresh: Path) -> bool:
    """Move our own stub to `fresh` without ever replacing a rival there:
    True when the new name was taken by us, False when it already existed.
    A crash between the link and the unlink leaves an identical twin under
    both numbers; the retry sees the key owned and skips it, and attended
    triage closes the extra file."""
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
        # Only CUSTODY_SITE and REGRESSION_SITE stalls reach here (qualifies()
        # gates every other stall site out before _severity is ever called).
        # A cap_regression stall fires only when every unresolved finding is
        # high-or-below (an unresolved CRITICAL takes the cap_critical branch
        # instead), so "critical" would overstate it - "high" is this stall's
        # true worst case.
        return "critical" if row.get("site") == custody.CUSTODY_SITE else "high"
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


def _problem(rows: list[dict], batch_id: str, source_prd: str) -> str:
    lines = []
    for row in rows:
        lines += [
            f"Deferred finding with no PRD owner when this stub was minted: "
            f"{_provenance(row, batch_id)}, raised against `{source_prd}`.",
            "",
        ]
        for field in ("issue", "detail"):
            value = row.get(field)
            if isinstance(value, str) and value.strip():
                lines += [f"{field.capitalize()}: {value}", ""]
    return "\n".join(lines)


def render_stub(rows: list[dict], batch_id: str, keys: list[str]) -> str:
    """The hold artifact: the create-prd minimal heading order, filled with
    every member row's ledger provenance and the single triage action. A
    group of two or more rows also lists every key on `ledger_keys:`."""
    row, key = rows[0], keys[0]
    source_prd = str(row.get("prd") or "unknown")
    return _STUB_TEMPLATE.format(
        batch_id=batch_id,
        key=key,
        ledger_keys=f"ledger_keys: {', '.join(keys)}\n" if len(keys) > 1 else "",
        source_prd=source_prd,
        severity=_severity(row),
        title=_title(row, key),
        problem=_problem(rows, batch_id, source_prd),
        task=TRIAGE_TASK,
    )


def fold_key(row: dict) -> tuple:
    """Rows fold into one finding only within one source PRD and severity."""
    return (row.get("prd"), _severity(row))


def similar(a: dict, b: dict) -> bool:
    """Same cited file (line ignored), or a casefolded `[a-z0-9_]+` token-set
    Jaccard of at least FOLD_JACCARD between the two finding texts."""
    file_a, file_b = (str(r.get("file") or "").split(":")[0] for r in (a, b))
    if file_a and file_a == file_b:
        return True
    ta, tb = (set(_TOKEN_RE.findall(finding_text(r).casefold())) for r in (a, b))
    return bool(ta | tb) and len(ta & tb) / len(ta | tb) >= FOLD_JACCARD


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
    groups: list[tuple[list[dict], list[str]]] = []
    skipped = 0
    for row in rows:
        text = finding_text(row) if qualifies(row) else None
        if text is None:
            skipped += 1
            continue
        key = ledger_key(text)
        group = next(
            (
                g
                for g in groups
                if key in g[1]
                or (fold_key(g[0][0]) == fold_key(row) and similar(g[0][0], row))
            ),
            None,
        )
        if group is None:
            groups.append(([row], [key]))
        elif key not in group[1]:
            group[0].append(row)
            group[1].append(key)
    minted: list[str] = []
    for members, keys in groups:
        if any(key in head for key in keys for head in heads):
            continue
        slug = slugify(str(members[0].get("topic") or finding_text(members[0])))
        path = _allocate(prds_dir, slug, render_stub(members, batch_id, keys))
        minted.append(path.name)
    return {"minted": minted, "skipped": len(rows) - len(minted)}
