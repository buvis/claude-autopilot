---
item: spec-card-parser
model: sonnet
suite: batch
changelog: none
framework: pytest
sample_test: skills/plan-tasks/scripts/test_classify_tier_cli.py
---

## Goal

Same card as valid.md with the section listing the test ids deleted. The
framework and sample keys are present, so the only rule this card breaks is
the missing heading.

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
