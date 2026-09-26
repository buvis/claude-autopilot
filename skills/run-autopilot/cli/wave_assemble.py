"""Pure rendering helpers for wave assembly (PRD 00214).

`keep_both` strips git's three-way conflict marker lines while keeping both
sides of every hunk. `summary` renders a wave's markdown report from
already-computed, already-loaded in-memory data: a wave dict, this wave's
migrated loop-metrics rows, and this wave's assembly_conflict records. Both
are pure - no disk, no git.
"""

from __future__ import annotations


def keep_both(text: str) -> str:
    """Strip git's conflict marker lines, keeping both sides of every hunk."""
    return "".join(
        line
        for line in text.splitlines(keepends=True)
        if not (
            line.startswith("<<<<<<<")
            or line.startswith("=======")
            or line.startswith(">>>>>>>")
        )
    )


def summary(wave: dict, rows: list[dict], records: list[dict]) -> str:
    """Render a wave's markdown report from already-loaded in-memory data."""
    lines = [f"# Wave {wave['id']} summary", "", "## PRDs"]
    for entry in wave["prds"]:
        lines.append(
            f"- {entry['prd']}: Wave {wave['id']}, lane {entry['lane']}, "
            f"{entry['label']}"
        )
    lines += ["", "## Assembly conflicts"]
    if records:
        for record in records:
            lines.append(
                f"- {record['prd']} (lane {record['lane']}): {record['reason']}"
            )
    else:
        lines.append("(none)")
    lines += ["", "## Integrator notes"]
    notes = [
        (note["sha"], note["text"])
        for each_lane in wave["lanes"]
        for note in (each_lane.get("integrator_notes") or [])
    ]
    if notes:
        lines += [f"- {sha}: {text}" for sha, text in notes]
    else:
        lines.append("(none)")
    return "\n".join(lines) + "\n"
