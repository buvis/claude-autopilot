#!/usr/bin/env python3
"""frontmatter.py - the Phase-0 PRD frontmatter parse and its defaults.

PURE: takes the PRD's TEXT, returns (fields, warnings). No disk, no PyYAML -
the recognized grammar is flat `key: value` lines, which is all any PRD in the
tree has ever used.

    parse(text) -> (fields, warnings)

The one exception is `apply(prd_path, state_path)`, the non-printing core of
`autopilot frontmatter`: it reads the PRD, adds the lane fields, and writes
them all to state.json in one transaction, handing each warning to
`on_warning` before that write and returning the reset lines beside them.

`fields` maps STATE keys (not PRD keys) to effective values, and carries only
what Phase 0 should write: an absent optional field stays absent rather than
being written as a null. `warnings` holds the lines the caller prints.

Three dispositions, and the difference is deliberate:

- Invalid value      -> the default, plus one warning naming the field.
- Absent field       -> the default, silently. Warning on every unset field
                        would fire five times for a bare PRD, contradicting
                        the ONE-line whole-block fallback below.
- Malformed block or
  no frontmatter     -> every default, plus exactly one warning (MALFORMED).

Only the first 22 lines are read (the Phase-0 contract's 20, plus the two
custody keys the hold refresh may add): a block that has not closed by then
is malformed, and a `---` rule further down the body can never be mistaken
for the closing delimiter.

`default_model` is deliberately NOT recognized here. It belongs to
`/plan-tasks` and is re-read from the PRD at Phase 6 rework dispatch; Phase 0
never touches it, so it falls through as an unknown key. The orchestrator
model is the separate `session_model` key (PRD 00200): `default_model` floors
the per-task tier, `session_model` picks the build session's model.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

# 20, plus the two custody keys the hold refresh may add.
_HEAD_LINES = 22

# PRD key -> (state key, allowed values, default). Every one of these takes
# its default and warns when the value is not allowed.
_ENUMS: dict[str, tuple[str, tuple[str, ...], str]] = {
    "catchup": ("catchup_mode", ("run", "skip", "force"), "run"),
    "design": ("design_mode", ("run", "skip"), "run"),
    "doubt_reviewer": ("doubt_reviewer", ("codex", "fable"), "codex"),
    "consensus_engine": (
        "consensus_engine",
        ("legacy", "shadow", "workflow"),
        "legacy",
    ),
    "session_model": ("session_model", ("sonnet", "opus"), "sonnet"),
}

_REWORK_CAP_DEFAULT = 2

# The three opt-in markers: recognized only at their exact value, absent
# otherwise, and never warned about - an unset opt-in is the normal case.
_OPT_INS: dict[str, tuple[str, str, object]] = {
    "design_gate": ("design_gate", "user", "user"),
    "pause_on_ambiguity": ("pause_on_ambiguity", "true", True),
    "plan_expansion": ("plan_expansion_override", "allow", True),
}

MALFORMED_WARNING = (
    "autopilot: PRD frontmatter malformed; defaulting catchup_mode=run, "
    "rework_cap=2, design_mode=run, doubt_reviewer=codex, "
    "consensus_engine=legacy, session_model=sonnet"
)


def defaults() -> dict:
    """The effective fields for a PRD that declares nothing."""
    fields = {state_key: default for state_key, _allowed, default in _ENUMS.values()}
    fields["rework_cap"] = _REWORK_CAP_DEFAULT
    return fields


def _block(text: str) -> list[str] | None:
    """The frontmatter body lines, or None when absent or unterminated."""
    lines = text.splitlines()[:_HEAD_LINES]
    if not lines or lines[0].strip() != "---":
        return None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return lines[1:index]
    return None


def _pairs(body: list[str]) -> dict[str, str]:
    """Flat `key: value` lines as a dict. Splits on the FIRST colon only -
    `title: Harden the gate: part two` keeps its colon in the value."""
    pairs = {}
    for line in body:
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        pairs[key.strip()] = value.strip()
    return pairs


def declared(text: str) -> dict[str, str]:
    """The flat `key: value` pairs of the frontmatter block, read under the
    same `_HEAD_LINES` window `parse` uses; `{}` on a malformed or absent
    block. For callers that read keys `parse` does not recognize (the lane
    classifier's `lane:` and `design:`)."""
    body = _block(text)
    return {} if body is None else _pairs(body)


def _rework_cap(raw: str) -> int | None:
    """`raw` as a positive int, or None when it is not one."""
    try:
        value = int(raw)
    except ValueError:
        return None
    return value if value > 0 else None


def parse(text: str) -> tuple[dict, list[str]]:
    """Parse `text`'s frontmatter into (state fields, warnings)."""
    fields = defaults()
    body = _block(text)
    if body is None:
        return fields, [MALFORMED_WARNING]

    declared = _pairs(body)
    warnings: list[str] = []

    for prd_key, (state_key, allowed, default) in _ENUMS.items():
        if prd_key not in declared:
            continue
        value = declared[prd_key]
        if value in allowed:
            fields[state_key] = value
        else:
            warnings.append(
                f"autopilot: PRD frontmatter {prd_key}={value!r} is not one of "
                f"{'/'.join(allowed)}; defaulting to {default}",
            )

    if "rework_cap" in declared:
        capped = _rework_cap(declared["rework_cap"])
        if capped is None:
            warnings.append(
                f"autopilot: PRD frontmatter rework_cap={declared['rework_cap']!r} "
                f"is not a positive integer; defaulting to {_REWORK_CAP_DEFAULT}",
            )
        else:
            fields["rework_cap"] = capped

    for prd_key, (state_key, marker, value) in _OPT_INS.items():
        if declared.get(prd_key) == marker:
            fields[state_key] = value

    return fields, warnings


def _lane_fields(text: str) -> tuple[dict, list[str]]:
    """The three lane fields `cli/lane.py` decides for this PRD, and the one
    warning an invalid `lane:` value earns (silence when the key is absent).
    `off` in `_AUTOPILOT_LANES` forces full.

    Deferred import for the same by-path reason `apply` documents below."""
    from . import lane

    keys = declared(text)
    verdict = lane.classify(text, keys)
    warnings: list[str] = []
    if "lane" in keys and keys["lane"] not in lane.LANES:
        warnings.append(
            f"autopilot: PRD frontmatter lane={keys['lane']!r} is not one of "
            f"solo/fast-track/full; defaulting to {verdict.lane}",
        )
    fields = {
        "lane": verdict.lane,
        "lane_reason": verdict.reason,
        "lane_effective": lane.effective(
            verdict.lane, os.environ.get("_AUTOPILOT_LANES"),
        ),
    }
    return fields, warnings


def apply(
    prd_path: Path,
    state_path: Path,
    *,
    on_warning: Callable[[str], None] | None = None,
) -> tuple[dict, list[str], list[str]]:
    """Parse `prd_path`, add lane/lane_reason/lane_effective (`off` in
    `_AUTOPILOT_LANES` forces full), write every field to `state_path` in ONE
    transaction, and return (fields, warnings, resets). Prints nothing; raises
    OSError, state.StateError, or schema.SchemaError on a failed read/write.

    `on_warning` is handed each warning line BEFORE the write, so a caller that
    prints them still has them when the write then raises. `resets` names one
    line per field whose value the write actually changed, read from the
    pre-write state inside the transaction, so it stays empty on a failure.

    Imports the package siblings here, not at module level: `parse` and
    `declared` are also loaded BY PATH (no parent package) by
    fast-track/scripts/cards_from_prd.py, where a relative import cannot
    resolve."""
    from . import schema, state

    text = Path(prd_path).read_text(encoding="utf-8")
    fields, warnings = parse(text)
    lane_fields, lane_warnings = _lane_fields(text)
    fields.update(lane_fields)
    warnings += lane_warnings
    if on_warning is not None:
        for line in warnings:
            on_warning(line)

    before: dict = {}

    def commit(current: dict) -> dict:
        before.update(current)
        return {**current, **fields}

    state.transaction(
        state_path,
        commit,
        validator=lambda new_state: schema.validate(
            {key: value for key, value in new_state.items() if key in fields},
        ),
    )
    # Compared, not enumerated: every field `parse` can write earns its own
    # line, so a new key cannot be overwritten in silence.
    resets = [
        f"autopilot: PRD frontmatter reset {key} {before[key]} -> {value}"
        for key, value in fields.items()
        if key in before and before[key] != value
    ]
    return fields, warnings, resets
