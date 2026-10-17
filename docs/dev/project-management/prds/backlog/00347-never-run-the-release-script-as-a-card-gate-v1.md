---
design: skip
default_model: sonnet
model_tier_rationale: one tuple constant and one drop branch with their exact text, one prose sentence, additive tests beside the existing chained-command test
---

# Never run the release script as a card gate

Source: batch 202610161547, PRD 00327 (`release-gate-and-notes-say-what-ships-v2`, classified fast-track `card_sized`), 2026-10-17 13:30-13:44 CEST, session 70 turns, $3.78. The card's `## Gates` section read `uv run ... test_release_checks_counts.py`, `bash dev/bin/release-checks`, `bash dev/bin/release`. Gates 1 and 2 passed; at gate 3 warden refused the release script ("blocked release: needs review"), the session took the loop-mode stall path (`fast_track_blocked`), and the PRD was parked in `hold/` with one of its six gaps landed.

## Problem

`_gates` (`skills/fast-track/scripts/cards_from_prd.py:170-192`) collects every backticked command from the task lines, the `**Exit Criteria**` lines and the `## Success Criteria` section, keeps the ones that start with a prefix in `_GATE_PREFIXES` (`skills/fast-track/scripts/cards_from_prd.py:27`: `uv run `, `python -m pytest`, `pytest`, `bash `), and drops only chained commands. 00327's success criterion "With a `severity: critical` stub in `prds/hold`, `bash dev/bin/release` exits 1 and names it before any other output" therefore became a line under the card's Gates heading, which the lane runs unconditionally, and `dev/bin/release` is a publish action: it tags, bumps the marketplace and pushes. A gate that exits non-zero stops the item (`stopped`, `skills/fast-track/SKILL.md:235-236`), and a gate warden refuses stalls it. A PRD about the release script will always mention it in a criterion, and the lane must never be the thing that runs it.

## Solution

The parser drops a release command the way it drops a chained one. `cards_from_prd.py` gains `_RELEASE_SCRIPTS = ("dev/bin/release",)` beside `_CHAIN_TOKENS`, and `_gates` drops a command whose first path token (the command with an optional leading `bash ` removed, split on whitespace, first element) is in `_RELEASE_SCRIPTS`, printing `cards_from_prd.py: gates: dropped release command: <command>` on stderr; `bash dev/bin/release-checks` is not equal to `dev/bin/release` and stays a gate. The `## Gates` prose in `skills/fast-track/SKILL.md` gains one sentence after "The parser already refused a chained gate line, so each one runs on its own.": `It also drops a command that runs the release script (`dev/bin/release`), which is a publish action no lane runs unattended; a success criterion that names it stays a criterion for the human release step.`

## Requirements

### Must have
- `_RELEASE_SCRIPTS = ("dev/bin/release",)` in `skills/fast-track/scripts/cards_from_prd.py` and the drop branch in `_gates` with the stderr text above.
- Fail-first tests in `skills/fast-track/scripts/test_cards_from_prd.py` (registered under `[checks] fast-track lane`, `dev/bin/release-checks:186-187`), beside `test_gates_drop_chained_commands_loud` (`skills/fast-track/scripts/test_cards_from_prd.py:151-157`): `test_gates_drop_the_release_script_loud` (items naming `bash dev/bin/release` and `uv run --no-project pytest -q y` give `["uv run --no-project pytest -q y"]` and stderr contains `dropped release command: bash dev/bin/release`; a success-criteria list containing `` `dev/bin/release` exits 1 `` contributes no gate), `test_release_checks_is_still_a_gate` (`bash dev/bin/release-checks` survives), and `test_only_the_release_script_raises_no_gates` (items naming only `bash dev/bin/release` raise `RenderError` with `field == "gates"`).
- The one `SKILL.md` sentence above, verbatim.
- A CHANGELOG `[Unreleased]` Fixed entry under **fast-track**: a card never runs `dev/bin/release` as a gate; a criterion that names the release script is dropped loud and left to the human release step.

### Nice to have
- None.

## Implementation

### Module: card-gates
- **Location**: `skills/fast-track/scripts/cards_from_prd.py` (`_gates`, `_GATE_PREFIXES`)
- **Responsibility**: a release command never becomes a card gate
- **Exports**: `render_cards()`, `_gates()` (unchanged signatures)
- New symbols: `_RELEASE_SCRIPTS`

### Module: card-gate-tests
- **Location**: `skills/fast-track/scripts/test_cards_from_prd.py`
- **Responsibility**: pin the drop, the survival of the gate script, and the no-gates error
- **Exports**: none
- New symbols: `test_gates_drop_the_release_script_loud`, `test_release_checks_is_still_a_gate`, `test_only_the_release_script_raises_no_gates`

### Module: lane-prose
- **Location**: `skills/fast-track/SKILL.md` (`## Gates`)
- **Responsibility**: say what the parser drops and why
- **Exports**: none

### Dependencies
- card-gates: No dependencies (foundation)
- card-gate-tests: Depends on [card-gates]
- lane-prose: Depends on [card-gates]

## Tasks

### Phase 0: Foundation
- [ ] Add the three tests to `skills/fast-track/scripts/test_cards_from_prd.py`. Premise: `rg -c "_RELEASE_SCRIPTS" skills/fast-track/scripts/cards_from_prd.py` prints 0 before the edit; a different count means the parser already changed and the task stops and reports. - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/fast-track/scripts/test_cards_from_prd.py -k "release"` fails `test_gates_drop_the_release_script_loud` and `test_only_the_release_script_raises_no_gates` against the current parser and passes `test_release_checks_is_still_a_gate`.

### Phase 1: Core
- [ ] Add `_RELEASE_SCRIPTS` and the drop branch to `_gates`, the `SKILL.md` sentence and the CHANGELOG entry (depends on: Phase 0) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/fast-track/scripts/test_cards_from_prd.py` passes; `rg -c "dropped release command" skills/fast-track/scripts/cards_from_prd.py` prints 1; `rg -c "drops a command that runs the release script" skills/fast-track/SKILL.md` prints 1; `rg -n "fast-track.*release script" CHANGELOG.md` prints one line under `[Unreleased]`.

## Success Criteria

- The three tests pass and `test_gates_drop_chained_commands_loud` still passes.
- Post-release signal: no fast-track item stops with `stopped: gate <n>` or stalls `fast_track_blocked` on a `dev/bin/release` gate; `rg -l "bash dev/bin/release$" docs/dev/tmp/fast-track-*-card.md` finds no card written after the release.
