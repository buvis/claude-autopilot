---
item: spec-card-parser
model: sonnet
suite: batch
changelog: none
---

## Goal

Parse one hand-written spec card into a Card so the fast-track lane has a
single validated input and never guesses a missing value.

## Tests

skills/fast-track/scripts/test_card.py::test_missing_section_names_the_field
skills/fast-track/scripts/test_card.py::test_unknown_model_exits_two

## Files

    

## Constraints

Standard library only. No new dependencies, no network access.

## Docs

No user-facing docs beyond the fast-track skill reference.

## Gates

uv run --no-project --with pytest python -m pytest -q skills/fast-track/scripts
python3 skills/fast-track/scripts/card.py skills/fast-track/scripts/fixtures/valid.md

## Transport impact

none
