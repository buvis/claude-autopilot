"""Assembly-review PRD stub: `stub_text` renders the body and `review_paths`
computes the diff-scope path list, both from an already-assembled wave dict
(`wave.json` after `wave_assemble.assemble` has populated `wave["assembly"]`).
"""

from __future__ import annotations

from cli.wave import WAVE_APPEND_ONLY


def review_paths(wave: dict) -> list[str]:
    """Paths worth a human diff pass: those a lane's `files` names in more
    than one lane, plus the append-only files every PRD touches."""
    counts: dict[str, int] = {}
    for lane in wave["lanes"]:
        for path in set(lane.get("files") or []):
            counts[path] = counts.get(path, 0) + 1
    multi = {path for path, n in counts.items() if n > 1}
    return sorted(multi | set(WAVE_APPEND_ONLY))


def stub_text(wave: dict) -> str:
    """The assembly-review PRD body for `wave`, naming every merged lane."""
    if "assembly" not in wave:
        raise ValueError("wave has no assembly - run `wave assemble` first")
    assembly = wave["assembly"]
    lanes_by_name = {lane["name"]: lane for lane in wave["lanes"]}
    merged = [lanes_by_name[name] for name in assembly["merged"]]

    def label(lane: dict) -> str:
        return f"{lane['name']} ({', '.join(lane['prds'])})"

    def keep_both(lane: dict) -> str:
        notes = lane.get("integrator_notes") or []
        if not notes:
            return "no keep-both resolutions recorded"
        return ", ".join(note["text"] for note in notes)

    lines = [
        "---",
        "catchup: skip",
        "design: skip",
        "rework_cap: 2",
        "default_model: sonnet",
        "model_tier_rationale: fixes to conflict resolutions and lane"
        " interactions found by the assembly review",
        "---",
        "",
        f"# Wave {wave['id']} assembly",
        "",
        "## Overview",
        "",
        *[f"- {label(each)}" for each in merged],
        "",
        f"Diff range: {wave['base_sha']}..{assembly['head_sha']}",
        "",
        "Diff scope:",
        *[f"- {path}" for path in review_paths(wave)],
        "",
        "## Functional Decomposition",
        "",
        "### Capability: Assembly",
        "",
        "#### Feature: Lane merges",
        "",
        "Description:",
        *[f"- {each['name']}: {', '.join(each['prds'])}" for each in merged],
        "",
        "Inputs/Outputs/Behavior:",
        *[f"- {each['name']}: {keep_both(each)}" for each in merged],
        "",
        "## Implementation Phases",
        "",
        "### Phase 0: Assembly",
        "",
        *[
            f"- [x] Merge lane {label(each)} - Acceptance: release-checks green"
            for each in merged
        ],
        "",
        "## Test Strategy",
        "",
        "- bash dev/bin/release-checks",
        *[
            f"- See {prd}'s own Test Strategy"
            for each in merged
            for prd in each["prds"]
        ],
        "",
    ]
    return "\n".join(lines)
