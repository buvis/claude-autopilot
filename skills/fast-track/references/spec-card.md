# Spec Card Format

> **Paths in this pack.** This pack's root is `${CLAUDE_PLUGIN_ROOT}`. That line
> is substituted when the skill loads and never inside a reference like this
> one, so swap the real directory in by hand when you meet the placeholder
> here. Never hand the literal placeholder to a shell: it expands to the empty
> string and the path silently becomes `/...`.

One card is the whole input to `/autopilot:fast-track`. `card.py` is the only
thing that reads it, and every rule below is one that parser enforces.

Parse the card before anything else runs.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/fast-track/scripts/card.py <card.md>
```

Exit 0 prints the parsed card as JSON. Exit 2 prints
`card.py: <field>: <message>` on stderr and stops the lane there: fix that
field and parse again.

## Frontmatter

The card opens with a `---` line and closes the block before the first section.
Each line inside splits on its first colon, so a value may carry colons of its
own.

| Key | Required | Value |
|-----|----------|-------|
| `item` | yes | The slug every ledger row, temp file and parked branch carries. `[a-z0-9-]+` and nothing else: no capitals, no spaces, no underscores. |
| `model` | yes | `sonnet` or `opus`, the tier the implementor runs on. |
| `suite` | yes | `batch` or `per-item`. `per-item` points the test gate at this card's own test files; `batch` runs the repo suite once, at the last gate. |
| `changelog` | no | Free text, the entry this change earns. Leave it empty when it earns none. |
| `framework` | when `## Tests` is empty | The framework a fresh test author writes in, such as `pytest`. |
| `sample_test` | when `## Tests` is empty | One existing test file, the shape those new tests copy. |

## Sections

Seven `## ` sections, all required. The parser reports the first missing one in
this order, and a heading it knows nothing about is dropped with the lines
under it.

| Section | Shape | What it holds |
|---------|-------|---------------|
| `## Goal` | prose, up to 40 lines | The change, in the words the implementor reads. A longer goal earns `card too large for the lane; write a PRD`. |
| `## Tests` | one test path or node id per line | The tests that pin the change. Named here, the lane reads those files and implements against them. Left empty, one test author dispatch writes them from the card alone. |
| `## Files` | one path per line, up to 12 | The implementor's whole allowlist. A thirteenth file earns the same too-large refusal. |
| `## Constraints` | prose | What the implementor may not do: the dependencies, the exit codes, the shapes that stay. |
| `## Docs` | prose | The documentation this change owes, or `none`. |
| `## Gates` | one command per line | Each line runs on its own Bash call, in card order. |
| `## Transport impact` | prose | What the change moves across a process or network boundary, or `none`. |

A gate line that chains commands is refused: keep the shell operators `&&`,
`;` and the pipe out of every line, and give each command a line of its own.

## A worked card

```markdown
---
item: record-item-future-started
model: sonnet
suite: per-item
changelog: fix(fast-track): refuse an item row started in the future
---

## Goal

Refuse a `--started` timestamp that lies in the future, so a mistyped epoch
cannot record a fast-track item that finished before it began. Every other
input records as it does today; only the future timestamp stops the call, and
the offending value goes to stderr with the field name.

## Tests

skills/fast-track/scripts/test_record_item.py::test_future_started_exits_two

## Files

skills/fast-track/scripts/record_item.py
skills/fast-track/scripts/test_record_item.py

## Constraints

Standard library only, no new dependencies. Keep the exit codes as they are:
0 on a recorded row, 2 on a refusal.

## Docs

none

## Gates

uv run --no-project --with pytest python -m pytest -q skills/fast-track/scripts

## Transport impact

none
```

## An empty `## Tests` section

Leave `## Tests` empty when the tests do not exist yet. The card then carries
`framework` and `sample_test` in its frontmatter, and the lane opens with one
test author dispatch that writes the tests from the goal, the constraints and
that sample. The author reads the card and nothing else, so the goal has to say
what passing looks like.

## Refusals

Every refusal names the field on stderr, in the order below.

| Field | Message | The fix |
|-------|---------|---------|
| `frontmatter` | `card must open with a closed --- block` | Open the card with `---` and close the block above the first section. |
| `goal`, `tests`, `files`, `constraints`, `docs`, `gates`, `transport_impact` | `card is missing this ## section` | Add that section. `## Transport impact` reports under `transport_impact`. |
| `framework` | `an empty ## Tests section needs a framework` | Name the tests in `## Tests`, or add `framework:`. |
| `sample_test` | `an empty ## Tests section needs a sample` | Add `sample_test:` pointing at one existing test file. |
| `gates` | `gate line chains commands: <the line>` | Split the line into one command per line. |
| `files` | `13 files past 12: card too large for the lane; write a PRD` | Cut the allowlist to 12 paths, or write a PRD and run the loop. |
| `goal` | `goal past 40 lines: card too large for the lane; write a PRD` | Cut the goal to 40 lines, or write a PRD and run the loop. |
| `item` | `item 'Fast Track' is not a slug matching [a-z0-9-]+` | Lowercase it and join the words with hyphens. |
| `model` | `unknown model 'gpt-4-turbo'; use one of ('sonnet', 'opus')` | Pick `sonnet` or `opus`. |
| `suite` | `unknown suite 'banana'; use one of ('batch', 'per-item')` | Pick `batch` or `per-item`. |
| `card` | the operating system's error | Point the argument at a card the shell can read. |
