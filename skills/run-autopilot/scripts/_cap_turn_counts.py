"""Per-session tool-call counter for the context-cap hook (PRD 00073, 00200).

`.turn-counts.json` in the autopilot dir holds `{"counts": {<session id>:
<int>}, "fired": [<session id>, ...], "last": {"session", "count", "usage"}}`.
The hook bumps its own session's count on every fire, fires the turn
tripwire once per session when the count reaches the threshold, and records
the latest fire as `last` for the build gate's gate-edge headroom check.
Split out of `autopilot_context_cap_hook.py` to keep that file under the
800-line limit; imported as a sibling module, like `_walk_up`.

Stdlib only.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

TURN_COUNTS_FILE = ".turn-counts.json"


def load_turn_counts(counts_file: Path) -> dict[str, Any]:
    """Read the counter file, resetting (with one stderr line) when it is
    unreadable or the wrong shape. A missing file is the normal first-call
    state and stays silent (else every session logs on its first call)."""
    data: dict[str, Any] = {"counts": {}, "fired": []}
    if not counts_file.exists():
        return data
    reset_reason: str | None = None
    try:
        loaded: Any = json.loads(counts_file.read_text())
    except (OSError, ValueError):
        loaded = None
        reset_reason = "unreadable"
    if isinstance(loaded, dict) and isinstance(loaded.get("counts"), dict):
        data = {
            "counts": dict(loaded["counts"]),
            "fired": list(loaded.get("fired", [])),
        }
    elif loaded is not None:
        reset_reason = "wrong shape"
    if reset_reason:
        print(
            f"autopilot_context_cap_hook: turn-counts reset ({reset_reason})",
            file=sys.stderr,
        )
    return data


def bump_and_check_tripwire(
    autopilot_dir: Path,
    session_id: str,
    tripwire: int,
    total: int | None = None,
    arm: bool = True,
) -> tuple[int, bool]:
    """Increment this session's tool-call counter and return `(count, fires)`:
    the count after this call, and True exactly once, the call on which it
    reaches `tripwire`. Fires at most once per session (the session id is
    recorded under "fired"). A missing or corrupt counter file resets to zero
    and logs; it never raises. Interactive sessions never reach here — main()'s
    $_AUTOPILOT_LOOP + phase guards run first. The count is also the calls
    half of the task record (PRD 00200), so it is returned even when the
    counter could not be persisted (then `fires` is False).

    The same write records this fire as `last`: `{"session", "count",
    "usage"}` (`usage` is `total`, null when the transcript had no usage line
    yet). The build gate reads it at the design->plan and plan->work edges to
    apply the headroom rule where no task is in progress (PRD 00200). With
    `arm=False` (a fire the `.cap-fired` marker de-duplicates) the count and
    `last` are still recorded but the tripwire never fires or arms: `last`
    must describe THIS session even while a rotation's marker blocks the
    checks, or the gate-edge check reads the dead session's exhausted values
    and hands off again (review 1 of PRD 00200).
    """
    counts_file = autopilot_dir / TURN_COUNTS_FILE
    data = load_turn_counts(counts_file)
    # Coerce this session's prior count defensively: a valid-JSON file with a
    # non-int value (null, "x") must reset that entry, never raise (the hook's
    # never-crash contract; PRD error case).
    try:
        prior = int(data["counts"].get(session_id, 0))
    except (TypeError, ValueError):
        prior = 0
        print(
            "autopilot_context_cap_hook: turn-counts reset (bad count value)",
            file=sys.stderr,
        )
    count = prior + 1
    data["counts"][session_id] = count
    already_fired = session_id in data["fired"]
    fires = arm and count >= tripwire and not already_fired
    if fires:
        data["fired"].append(session_id)
    data["last"] = {"session": session_id, "count": count, "usage": total}
    try:
        tmp = counts_file.with_suffix(".json.tmp")
        # Explicit handle rather than write_text: the counter must be on disk
        # before the rename publishes it, or a power loss resurrects an old
        # count and the tripwire re-fires (or never fires) for that session.
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(data))
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, counts_file)
    except OSError:
        # A counter we cannot persist must not fire (it would re-fire forever).
        return count, False
    return count, fires
