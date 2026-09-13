---
item: spec-card-parser
model: sonnet
suite: batch
changelog: none
---

## Goal



## Tests

skills/fast-track/scripts/test_card.py::test_missing_section_names_the_field
skills/fast-track/scripts/test_card.py::test_unknown_model_exits_two

## Files

skills/fast-track/scripts/card.py
skills/fast-track/scripts/test_card.py
skills/fast-track/scripts/fixtures/valid.md
skills/fast-track/scripts/fixtures/missing_docs.md
skills/fast-track/scripts/fixtures/missing_transport_impact.md
skills/fast-track/scripts/fixtures/unknown_model.md
skills/fast-track/scripts/fixtures/gate_chained_and.md
skills/fast-track/scripts/fixtures/gate_chained_semicolon.md
skills/fast-track/scripts/fixtures/gate_chained_pipe.md
skills/fast-track/scripts/fixtures/empty_tests_valid.md
skills/fast-track/scripts/fixtures/thirteen_files.md
skills/fast-track/scripts/fixtures/goal_too_long.md

## Constraints

Standard library only. No new dependencies, no network access.

## Docs

No user-facing docs beyond the fast-track skill reference.

## Gates

uv run --no-project --with pytest python -m pytest -q skills/fast-track/scripts
python3 skills/fast-track/scripts/card.py skills/fast-track/scripts/fixtures/valid.md

## Transport impact

none
