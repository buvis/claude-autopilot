---
item: spec-card-parser
model: sonnet
suite: batch
changelog: none
---

## Goal

Same card as valid.md with an allowlist far past the lane's bound, not one
path over it.

## Tests

skills/fast-track/scripts/test_card.py::test_missing_section_names_the_field

## Files

skills/fast-track/scripts/card.py
skills/fast-track/scripts/test_card.py
skills/fast-track/scripts/fixtures/valid.md
skills/fast-track/scripts/fixtures/missing_goal.md
skills/fast-track/scripts/fixtures/missing_tests.md
skills/fast-track/scripts/fixtures/missing_files.md
skills/fast-track/scripts/fixtures/missing_constraints.md
skills/fast-track/scripts/fixtures/missing_docs.md
skills/fast-track/scripts/fixtures/missing_gates.md
skills/fast-track/scripts/fixtures/missing_transport_impact.md
skills/fast-track/scripts/fixtures/unknown_model.md
skills/fast-track/scripts/fixtures/unknown_model_gpt_4_turbo.md
skills/fast-track/scripts/fixtures/unknown_model_empty.md
skills/fast-track/scripts/fixtures/unknown_suite_banana.md
skills/fast-track/scripts/fixtures/unknown_suite_empty.md
skills/fast-track/scripts/fixtures/gate_chained_and.md
skills/fast-track/scripts/fixtures/gate_chained_semicolon.md
skills/fast-track/scripts/fixtures/gate_chained_pipe.md
skills/fast-track/scripts/fixtures/thirteen_files.md
skills/fast-track/scripts/fixtures/goal_too_long.md

## Constraints

Standard library only.

## Docs

No user-facing docs beyond the fast-track skill reference.

## Gates

uv run --no-project --with pytest python -m pytest -q skills/fast-track/scripts

## Transport impact

none
