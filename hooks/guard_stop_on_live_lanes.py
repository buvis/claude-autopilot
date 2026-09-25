"""Stop hook: hold a loop session open while a CLI reviewer lane still runs (PRD 00213).

Headless claude kills its children when the turn ends, so a live codex or gemini
lane marked under `dev/local/autopilot/lanes/<pid>` refuses the stop (exit 2).
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import NamedTuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "skills" / "run-autopilot" / "scripts")
)

from _common import allow, block, read_input
from _walk_up import find_autopilot_dir

LANE_MAX_AGE_SECS = 3600
BLOCK_CAP = 40
AWAITER = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "review-work-completion"
    / "scripts"
    / "await_reviewer_outputs.py"
)


class Lane(NamedTuple):
    pid: int
    kind: str
    output: str


def live_lanes(autopilot_dir: Path) -> list[Lane]:
    lanes: list[Lane] = []
    for marker in sorted((autopilot_dir / "lanes").iterdir()):
        try:
            pid = int(marker.name)
        except ValueError:
            continue
        try:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                marker.unlink(missing_ok=True)
                continue
            except PermissionError:
                pass
            lines = marker.read_text().splitlines()
            kind = lines[0].strip() if lines else ""
            output = lines[1].strip() if len(lines) > 1 else ""
            # ponytail: a recycled pid holds the session until LANE_MAX_AGE_SECS; the ceiling bounds it
            age = time.time() - marker.stat().st_mtime
            if age > LANE_MAX_AGE_SECS:
                sys.stderr.write(
                    f"autopilot: lane {kind} (pid {pid}) has run {int(age // 60)} min, "
                    f"past the {LANE_MAX_AGE_SECS // 60} min ceiling; "
                    "not holding the session for it\n"
                )
                continue
            lanes.append(Lane(pid, kind, output))
        except OSError:
            continue
    return lanes


def reason(lanes: list[Lane], awaiter: Path) -> str:
    named = "; ".join(
        f"{lane.kind} (pid {lane.pid}) -> {lane.output or '(no -o file)'}"
        for lane in lanes
    )
    outputs = " ".join(lane.output for lane in lanes if lane.output)
    return (
        f"autopilot: {len(lanes)} CLI reviewer lane(s) still running: {named}. "
        "Headless claude kills them when this turn ends. "
        f"Run python3 {awaiter} --budget 100 {outputs} in the foreground; "
        "while its last line is WAITING run it again; on DONE continue the review. "
        "Do not end the turn before then."
    )


def _guard() -> None:
    if not os.environ.get("_AUTOPILOT_LOOP"):
        allow()
    payload = read_input()
    autopilot_dir = find_autopilot_dir(Path(payload.get("cwd") or os.getcwd()))
    if autopilot_dir is None or not (autopilot_dir / "lanes").is_dir():
        allow()
    counter = autopilot_dir / ".lane-guard-blocks"
    lanes = live_lanes(autopilot_dir)
    if not lanes:
        counter.unlink(missing_ok=True)
        allow()
    try:
        count = int(counter.read_text().strip()) + 1
    except (OSError, ValueError):
        count = 1
    if count > BLOCK_CAP:
        sys.stderr.write(
            f"autopilot: lane_guard: failed - giving up after {BLOCK_CAP} "
            "blocked exits to preserve session liveness\n"
        )
        counter.unlink(missing_ok=True)
        allow()
    counter.write_text(f"{count}\n")
    block(reason(lanes, AWAITER))


def main() -> None:
    try:
        _guard()
    except Exception:
        sys.exit(0)


if __name__ == "__main__":
    main()
