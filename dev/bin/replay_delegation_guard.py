#!/usr/bin/env python3
"""Replay every recorded Agent dispatch through the phase-delegation guard.

Read-only: it scans the session transcripts, runs
hooks/guard_phase_delegation.py once per distinct dispatch payload, and
reports how many dispatches of each kind the guard refuses. Exits 1 when a
per-task, agoge or reviewer dispatch is refused or a pinned known-deny record
is allowed, and 2 when there is nothing to replay.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "hooks"))

from guard_phase_delegation import (
    _AGOGE_PREFIX,
    _READ_ONLY_REVIEWERS,
    _is_per_task_persona,
)

DEFAULT_GUARD = REPO / "hooks" / "guard_phase_delegation.py"
DEFAULT_TRANSCRIPTS = (
    Path.home() / ".claude" / "projects" / str(REPO).replace("/", "-").replace(".", "-")
)

# Tool-use ids of dispatches the guard refused when this replay was pinned.
# Allowing one of them again is a regression, whatever the report says.
PINNED_DENY = (
    "toolu_011eQouP7ZMWxba7b8ijXmiR",
    "toolu_01WwjmFapBm8w3NYCwWddUbk",
    "toolu_01S6V4tZDtrS3ePnXWtD9dT2",
    "toolu_01Ku4TbcQoeik6ZLf5XkkAuD",
)

BUCKET_ORDER = ("per-task", "reviewer", "agoge", "other")

# A description that names one task or one per-task persona, read only when
# `subagent_type` is absent or generic and so cannot answer by itself.
_PER_TASK_DESCRIPTION = re.compile(
    r"\btasks?\s+#?[A-Za-z]?\d+\b|\b(?:ivan|tess|devon)\b",
    re.IGNORECASE,
)


def bucket(tool_input: dict, exempt: frozenset[str]) -> str:
    """Which kind of dispatch this is: agoge, reviewer, per-task or other."""
    subagent_type = tool_input.get("subagent_type")
    if isinstance(subagent_type, str):
        if subagent_type.startswith(_AGOGE_PREFIX):
            return "agoge"
        if subagent_type in exempt:
            return "reviewer"
        if _is_per_task_persona(subagent_type):
            return "per-task"
        if subagent_type != "general-purpose":
            return "other"
    description = tool_input.get("description")
    if isinstance(description, str) and _PER_TASK_DESCRIPTION.search(description):
        return "per-task"
    return "other"


def _dispatches(directory: Path) -> list[tuple[str, dict]]:
    """Every Agent tool_use in every *.jsonl under `directory`, in file order."""
    found: list[tuple[str, dict]] = []
    for path in sorted(directory.rglob("*.jsonl")):
        text = path.read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            try:
                record = json.loads(line)
            except ValueError:
                continue  # a truncated or non-JSON line is not a dispatch
            message = record.get("message") if isinstance(record, dict) else None
            content = message.get("content") if isinstance(message, dict) else None
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") != "tool_use" or block.get("name") != "Agent":
                    continue
                if isinstance(block.get("input"), dict):
                    found.append((block.get("id"), block["input"]))
    return found


def _dedupe(dispatches: list[tuple[str, dict]]) -> list[tuple[dict, list[str]]]:
    """Group identical payloads, keeping every id that carried one."""
    groups: dict[str, tuple[dict, list[str]]] = {}
    for tool_id, tool_input in dispatches:
        key = json.dumps(tool_input, sort_keys=True)
        if key in groups:
            groups[key][1].append(tool_id)
        else:
            groups[key] = (tool_input, [tool_id])
    return list(groups.values())


def _refused(guard: Path, tool_input: dict) -> bool:
    payload = json.dumps(
        {"session_id": "replay", "tool_name": "Agent", "tool_input": tool_input},
    )
    result = subprocess.run(
        [sys.executable, str(guard)],
        input=payload,
        text=True,
        capture_output=True,
        env={**os.environ, "_AUTOPILOT_LOOP": "1"},
        check=False,
    )
    return result.returncode != 0


def _detail(name: str, tool_id: str, tool_input: dict) -> str:
    persona = tool_input.get("subagent_type") or "-"
    description = " ".join(str(tool_input.get("description", "")).split())
    return f"{name} {tool_id} {persona} {description}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="replay the delegation guard")
    parser.add_argument("--transcripts", type=Path, default=DEFAULT_TRANSCRIPTS)
    parser.add_argument("--guard", type=Path, default=DEFAULT_GUARD)
    args = parser.parse_args(argv)

    if not args.guard.is_file():
        print(f"replay: no guard at {args.guard}", file=sys.stderr)
        return 2
    if not args.transcripts.is_dir():
        print(f"replay: no transcripts at {args.transcripts}", file=sys.stderr)
        return 2
    groups = _dedupe(_dispatches(args.transcripts))
    if not groups:
        print(f"replay: no Agent dispatch under {args.transcripts}", file=sys.stderr)
        return 2

    counts = {name: [0, 0] for name in BUCKET_ORDER}
    details: list[str] = []
    failed = False
    for tool_input, ids in groups:
        name = bucket(tool_input, _READ_ONLY_REVIEWERS)
        refused = _refused(args.guard, tool_input)
        counts[name][0] += 1
        if refused:
            counts[name][1] += 1
            details.append(_detail(name, ids[0], tool_input))
            failed = failed or name != "other"
        pinned = [tool_id for tool_id in ids if tool_id in PINNED_DENY]
        if pinned and not refused:
            print(
                f"replay: pinned deny id allowed: {' '.join(pinned)}",
                file=sys.stderr,
            )
            failed = True

    print(f"total {len(groups)}")
    for name in BUCKET_ORDER:
        seen, refused_count = counts[name]
        if seen:
            print(f"{name} {seen} refused {refused_count}")
    for line in details:
        print(line)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
