#!/usr/bin/env python3
"""selection.py - which PRD the autopilot picks next.

The decision is PURE: `sequence`, `selectable` and `select` take directory
LISTINGS, so it is testable without a filesystem and the caller owns the I/O.

    sequence(name)            -> the `00XXX-` prefix as an int, or None
    selectable(names)         -> the selectable subset, lowest sequence first
    select(wip, backlog)      -> (basename, source)

The one exception is `select_eligible(prds_dir)`, which takes a path, lists the
directories, reads each backlog pick's PRD and shells out to run its
`eligibility:` check (PRD 00137) from the project root that path derives - the
I/O-owning core shared by `autopilot select` and `autopilot enter`.

`hold/` is absent from the signature ON PURPOSE - that IS the parked/deferred
exclusion. A function that cannot see `hold/` cannot pick from it, which is a
stronger guarantee than a rule saying it must not.

Two kinds of name are skipped rather than ordered last:

- Anything not ending `.md`.
- Anything without a `00XXX-` prefix. `docs/dev/project-management/prds/FASTTRACK-PLAN-v5.md` is
  unnumbered precisely so "no PRD picker ever selects it"; honoring that is the
  documented contract, not an accident.

A six-digit prefix does not match either, so it is skipped rather than
silently truncated to five and mis-ordered.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

from cli import eligibility

_SEQUENCE_RE = re.compile(r"^(\d{5})-")


def sequence(name: str) -> int | None:
    """Return the `00XXX-` prefix of `name` as an int, or None if it has none."""
    match = _SEQUENCE_RE.match(name)
    return int(match.group(1)) if match else None


def selectable(names: Iterable[str]) -> list[str]:
    """Return the selectable entries of `names`, lowest sequence number first.

    Ties on sequence (two PRDs sharing a number) break on the full name, so
    the order is total and two calls on the same directory agree.
    """
    picks = [n for n in names if n.endswith(".md") and sequence(n) is not None]
    return sorted(picks, key=lambda n: (sequence(n) or 0, n))


def select(wip: Iterable[str], backlog: Iterable[str]) -> tuple[str | None, str]:
    """Return (basename, source) for the next PRD.

    `source` is "wip" (resume in place), "backlog" (needs the verified move to
    `wip/`), or "drained" with a None basename when neither holds a selectable
    PRD. wip wins whole, not per-number: an in-progress PRD is finished before
    a lower-numbered backlog one is started.
    """
    in_wip = selectable(wip)
    if in_wip:
        return in_wip[0], "wip"
    in_backlog = selectable(backlog)
    if in_backlog:
        return in_backlog[0], "backlog"
    return None, "drained"


def _listdir(path: Path) -> list[str]:
    """Basenames in `path`, or [] when it does not exist."""
    try:
        return [entry.name for entry in path.iterdir()]
    except (FileNotFoundError, NotADirectoryError):
        return []


def select_eligible(prds_dir: Path) -> tuple[str | None, str, list[dict]]:
    """Return (basename, source, skips): `select` over `prds_dir`, with each
    backlog pick's `eligibility:` command run from the project root `prds_dir`
    derives until one passes. Each unmet candidate becomes one skip entry (prd,
    command, its real exit code, note) and drops out of THIS pick only - it
    stays in backlog/. wip candidates are never gated. Prints nothing.

    That root is derived HERE, not taken from the caller: two callers derived it
    two different ways, so the same PRD's check could run from two different
    directories under one `--prds`. Resolved first, because `--prds prds` is
    legal and chopping components off a relative string leaves nothing; the
    fallback keeps a too-shallow `--prds` costing a failed check rather than a
    traceback out of a verb that never crashed before."""
    resolved = prds_dir.resolve()
    project_root = resolved.parents[3] if len(resolved.parents) > 3 else resolved
    in_wip = _listdir(prds_dir / "wip")
    in_backlog = _listdir(prds_dir / "backlog")
    skips: list[dict] = []
    while True:
        prd, source = select(in_wip, in_backlog)
        if source != "backlog":
            return prd, source, skips
        try:
            text = (prds_dir / "backlog" / prd).read_text(encoding="utf-8")
        except OSError:
            # Unreadable declares no check: pick it, and let the session
            # that opens it report the real problem.
            text = ""
        command = eligibility.command_for(text)
        if command is None:
            return prd, source, skips
        exit_code, note = eligibility.evaluate(command, project_root)
        if exit_code == 0:
            return prd, source, skips
        skips.append(
            {"prd": prd, "command": command, "exit_code": exit_code, "note": note}
        )
        in_backlog = [name for name in in_backlog if name != prd]
