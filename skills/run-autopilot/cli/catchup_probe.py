"""Batch-scoped gh/engram probe for catch-up.

`probe()` checks once per `batch.id` whether `gh` is authenticated and whether
`engram` sees a registered repo, records the verdicts in state as
`catchup_probe`, and reuses that record for the rest of the batch. It returns
the catch-up sections to skip.
"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from cli import custody, state, statectl

_NO_BATCH = "no-batch"
_TIMEOUT = 15
_UNREGISTERED_MARKER = "not inside a registered repo"


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run_probe(
    argv: list[str], *, run: Callable, which: Callable, cwd: Path
) -> subprocess.CompletedProcess | None:
    """Return the CompletedProcess, or None when the binary is absent,
    times out, or cannot be executed."""
    if which(argv[0]) is None:
        return None
    try:
        return run(argv, capture_output=True, text=True, timeout=_TIMEOUT, cwd=cwd)
    except (subprocess.TimeoutExpired, OSError):
        return None


def _skips(record: dict) -> list[str]:
    skip = []
    if record["gh"] != "ok":
        skip.append("github-state")
    if record["engram"] != "ok":
        skip.append("engram")
    return skip


def probe(
    state_path: Path,
    *,
    run: Callable = subprocess.run,
    which: Callable = shutil.which,
    now: Callable[[], str] = _utc_now,
) -> dict:
    """Probe `gh` and `engram` once per `batch.id`, write the verdict to
    `state.catchup_probe`, and return `{"skip": [...]}` naming which
    catch-up sections to omit this batch. Reuses the stored record when its
    `batch_id` matches and it has the expected shape; a malformed stored
    record (not a dict, or missing `gh`/`engram`) is treated as absent and
    re-probed rather than raised."""
    data, _version = state.load(state_path)
    batch_id = (data.get("batch") or {}).get("id") or _NO_BATCH
    recorded = data.get("catchup_probe")
    if (
        isinstance(recorded, dict)
        and recorded.get("batch_id") == batch_id
        and "gh" in recorded
        and "engram" in recorded
    ):
        return {"skip": _skips(recorded)}

    cwd = custody.project_root(state_path.parent)
    gh = _run_probe(["gh", "auth", "status"], run=run, which=which, cwd=cwd)
    engram = _run_probe(
        ["engram", "status", "--scope", "repo"], run=run, which=which, cwd=cwd
    )
    record = {
        "batch_id": batch_id,
        "gh": "absent" if gh is None else ("ok" if gh.returncode == 0 else "unauthenticated"),
        "engram": "absent"
        if engram is None
        else ("unregistered" if _UNREGISTERED_MARKER in engram.stderr else "ok"),
        "checked_at": now(),
    }
    statectl.mutate(state_path, lambda d: d.update(catchup_probe=record))
    return {"skip": _skips(record)}
