---
item: spec-card-parser-bootstrap
model: opus
suite: per-item
changelog: none
sample_test: skills/plan-tasks/scripts/test_classify_tier_cli.py
---

## Goal

Same card as empty_tests_valid.md with the framework key deleted.

## Tests

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
