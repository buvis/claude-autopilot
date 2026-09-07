---
item: spec-card-parser
model: sonnet
suite: batch
changelog: none
---

## Goal

Same card as valid.md with the Transport impact section deleted.

## Tests

skills/fast-track/scripts/test_card.py::test_missing_section_names_the_field

## Files

skills/fast-track/scripts/card.py
skills/fast-track/scripts/test_card.py

## Constraints

Standard library only.

## Docs

No user-facing docs beyond the fast-track skill reference.

## Gates

uv run --no-project --with pytest python -m pytest -q skills/fast-track/scripts
