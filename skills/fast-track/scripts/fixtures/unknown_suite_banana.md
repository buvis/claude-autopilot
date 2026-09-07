---
item: spec-card-parser
model: sonnet
suite: banana
changelog: none
---

## Goal

Same card as valid.md naming a suite the lane cannot run.

## Tests

skills/fast-track/scripts/test_card.py::test_unknown_suite_exits_two

## Files

skills/fast-track/scripts/card.py
skills/fast-track/scripts/test_card.py

## Constraints

Standard library only.

## Docs

No user-facing docs beyond the fast-track skill reference.

## Gates

uv run --no-project --with pytest python -m pytest -q skills/fast-track/scripts

## Transport impact

none
