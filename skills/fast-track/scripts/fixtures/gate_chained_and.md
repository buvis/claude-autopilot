---
item: spec-card-parser
model: sonnet
suite: batch
changelog: none
---

## Goal

Same card as valid.md with two commands chained by && on one gate line.

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

python3 -m compileall -q skills/fast-track/scripts && echo ok

## Transport impact

none
