"""The context-cap hook's state-write boundary: the `state-write-failed`
halt marker, the guarded `cli.state` import, and the one locked transaction
every state mutation of the hook goes through.

Split out of `autopilot_context_cap_hook.py` to keep that file under the
800-line limit; imported as a sibling module, like `_walk_up`. The halt
guarantee lives here: ANY failure on the way to a state write - cli/
unimportable for any reason, or the transaction raising - writes the marker
the loop wrapper halts on, warns on stderr, and returns False. Nothing here
raises into the harness.

Stdlib only (the cli package is imported lazily, inside the guard).
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any


def write_state_write_failed_marker(autopilot_dir: Path, detail: str) -> None:
    """Write the state-write-failed halt marker: one line of JSON, no cli
    import, no lock, no schema validation — the recovery path must not
    depend on the state boundary that just failed. Best-effort: a failure
    writing the marker itself only warns on stderr, since this hook must
    never raise into the harness.
    """
    marker_path = autopilot_dir / "state-write-failed"
    line = json.dumps({"site": "statectl_fail", "detail": detail}) + "\n"
    try:
        autopilot_dir.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=str(autopilot_dir), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(line)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_name, marker_path)
        except OSError:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise
    except OSError as exc:
        print(
            f"autopilot_context_cap_hook: failed to write state-write-failed marker ({exc})",
            file=sys.stderr,
        )


def import_cli_state(caller: str, autopilot_dir: Path) -> Any | None:
    """Import cli.state, inserting the skill root onto sys.path first.

    The hook lives in scripts/, one level below the skill root that owns the
    cli/ package (mirrors cli/__main__.py's own bootstrap). Returns the
    module, or None if cli/ cannot be imported at all (broken package) — the
    hook must never raise into the harness on that path, only warn and fail
    the write.
    """
    try:
        skill_root = Path(__file__).resolve().parent.parent
        if str(skill_root) not in sys.path:
            sys.path.insert(0, str(skill_root))
        from cli import state as cli_state
    except Exception as exc:
        detail = (
            f"autopilot_context_cap_hook: cli package unavailable ({exc}); "
            f"skipping {caller} to avoid a handoff with no record"
        )
        print(detail, file=sys.stderr)
        write_state_write_failed_marker(autopilot_dir, detail)
        return None
    return cli_state


def write_via_transaction(
    autopilot_dir: Path,
    caller: str,
    mutate: Callable[[dict[str, Any]], dict[str, Any]],
    validate: Callable[[dict[str, Any]], None],
    op_desc: str | None = None,
) -> bool:
    """Import the cli boundary and run one locked cli.state.transaction,
    upholding the hook's halt guarantee: ANY failure — cli/ unimportable, or
    the transaction itself raising — writes the state-write-failed marker and
    a stderr warning naming `op_desc`, then returns False. Never raises into
    the harness. `op_desc` defaults to `caller` when not given. Shared by
    `_append_rotation_to_state` and `_set_oversized_stall`, whose only
    differences are `caller` (passed to `_import_cli_state`), `op_desc`, and
    the mutate/validate closures.
    """
    op_desc = op_desc if op_desc is not None else caller
    cli_state = import_cli_state(caller, autopilot_dir)
    if cli_state is None:
        return False

    state_path = autopilot_dir / "state.json"
    try:
        cli_state.transaction(state_path, mutate, validator=validate)
    except Exception as exc:
        detail = (
            f"autopilot_context_cap_hook: state.json write failed ({exc}); "
            f"skipping {op_desc} to avoid a handoff with no record"
        )
        print(detail, file=sys.stderr)
        write_state_write_failed_marker(autopilot_dir, detail)
        return False
    return True
