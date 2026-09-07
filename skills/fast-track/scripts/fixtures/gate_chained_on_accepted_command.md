---
item: spec-card-parser
model: sonnet
suite: batch
changelog: none
---

## Goal

Same card as valid.md with the chain welded onto the very command the lane
expects to see, so only the chain character marks it as refused.

## Tests

skills/fast-track/scripts/test_card.py::test_chained_gate_line_is_refused

## Files

skills/fast-track/scripts/card.py
skills/fast-track/scripts/test_card.py

## Constraints

Standard library only.

## Docs

No user-facing docs beyond the fast-track skill reference.

## Gates

uv run --no-project --with pytest python -m pytest -q skills/fast-track/scripts && echo ok

## Transport impact

none
