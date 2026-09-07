---
item: spec-card-parser
model: sonnet
suite: batch
changelog: none
---

## Goal

Goal line 01 of 40, the longest goal the lane still accepts.
Goal line 02 of 40, one thought per line, no blank lines in between.
Goal line 03 of 40.
Goal line 04 of 40.
Goal line 05 of 40.
Goal line 06 of 40.
Goal line 07 of 40.
Goal line 08 of 40.
Goal line 09 of 40.
Goal line 10 of 40.
Goal line 11 of 40.
Goal line 12 of 40.
Goal line 13 of 40.
Goal line 14 of 40.
Goal line 15 of 40.
Goal line 16 of 40.
Goal line 17 of 40.
Goal line 18 of 40.
Goal line 19 of 40.
Goal line 20 of 40.
Goal line 21 of 40.
Goal line 22 of 40.
Goal line 23 of 40.
Goal line 24 of 40.
Goal line 25 of 40.
Goal line 26 of 40.
Goal line 27 of 40.
Goal line 28 of 40.
Goal line 29 of 40.
Goal line 30 of 40.
Goal line 31 of 40.
Goal line 32 of 40.
Goal line 33 of 40.
Goal line 34 of 40.
Goal line 35 of 40.
Goal line 36 of 40.
Goal line 37 of 40.
Goal line 38 of 40.
Goal line 39 of 40.
Goal line 40 of 40, still inside the limit.

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

## Transport impact

none
