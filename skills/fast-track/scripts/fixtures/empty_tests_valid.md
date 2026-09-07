---
item: spec-card-parser-bootstrap
model: opus
suite: per-item
changelog: fast-track parses spec cards before assembling the lane
framework: pytest
sample_test: skills/plan-tasks/scripts/test_classify_tier_cli.py
---

## Goal

Bootstrap a card whose tests do not exist yet, so the implementor writes them
from the named framework and the sample test.

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
