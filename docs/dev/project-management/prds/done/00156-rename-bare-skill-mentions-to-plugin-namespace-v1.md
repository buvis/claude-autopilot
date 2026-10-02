---
catchup: skip
design: skip
---

# Rename bare skill mentions to the plugin namespace

Source: the Nice-to-have left out of PRD 00149 (which owns the launch prompt in `cli/runner.py`, the `cli/loop.py` runbook lines, `SKILL.md` lines 153/222 and the two test literals). Counts measured 2026-08-26 with the finder below; nothing is a guess unless marked `(guess)`.

## Problem

Since the 2026-08-25 extraction the ten skills of this pack resolve only under the plugin namespace (`/autopilot:run-autopilot`, `/autopilot:work`, ...); `~/.claude/skills/<name>` is gone and `braid.ignore` keeps plugin-owned names out of it. The docs still tell operators and sessions to type the bare names: `rg -nP '(?<!skills)/(run-autopilot|work|plan-tasks|review-work-completion|review-blindly|design-solution|review-plan|use-codex|use-gemini|use-sonnet)\b' skills agents README.md --type md` matches 168 lines in 27 markdown files (run-autopilot alone: 72 lines in 29 files, code included). A session that follows `run /review-work-completion` or `/run-autopilot status` from a reference gets "unknown skill"; the recovery runbooks (`references/recovery.md`, 9 lines; `phase-build.md`, 18; `phase-review.md`, 23) are the worst place for that. A blind `sed` cannot do it: the same string is a path fragment (`skills/run-autopilot/...`, excluded by the lookbehind) and, in prose, sometimes a directory or a phase name rather than a skill invocation.

## Solution

One hand pass over the matched markdown lines: every mention that means "invoke the skill" becomes `/autopilot:<name>`; mentions that are paths, phase names, or directory names stay. Code and tests are touched only where they pin a renamed doc string (the doc-contract and prose-pin tests). No behavior change.

## Requirements

### Must have

- Every finder hit in `skills/**/*.md`, `agents/*.md` and `README.md` is judged and either renamed to `/autopilot:<name>` or left as a non-invocation. After the pass the finder prints zero lines for the invocation sense; any deliberately kept hit is a path or a name, never a slash-command the reader is told to run.
- The `${CLAUDE_PLUGIN_ROOT}` banner idiom (rules/claude-tooling.md, decided 2026-08-25) is untouched: this PRD renames skill invocations, not path placeholders.
- Tests that pin renamed strings are updated in the same commit (`skills/work/scripts/test_dispatch_prose.py`, `skills/run-autopilot/cli/test_doc_contract.py`, and any `test_*` that asserts a `/<name>` literal, found with the same finder over `*.py`/`*.sh`); the full suites stay green (`uv run --with pytest --with rich --with textual pytest skills/run-autopilot`, `pytest skills/work/scripts`, `pytest skills/review-work-completion/scripts`).
- `CHANGELOG.md` `[Unreleased]` gains one `**docs**` line under Fixed (references name the namespaced skills), per `rules/changelog.md`.

### Nice to have

- A `test_doc_contract.py` case that runs the finder over `references/*.md` and `SKILL.md` and fails on a bare invocation, so the class cannot regress `(guess)`: needs the invocation/path distinction encoded (for example, only lines where the match is preceded by a backtick or "run "), which may be more rule than it is worth.

## Implementation

### Module: docs-rename
- **Location**: `skills/*/SKILL.md`, `skills/*/references/*.md`, `skills/run-autopilot/scripts/README.md`, `agents/*.md`, `README.md`
- **Responsibility**: the hand pass.
- **Exports**: none (docs)

### Module: pinned-strings
- **Location**: `skills/work/scripts/test_dispatch_prose.py`, `skills/run-autopilot/cli/test_doc_contract.py`, other `test_*` files the finder names
- **Responsibility**: keep the prose pins in step with the renamed strings.
- **Exports**: none (tests)

### Dependencies
- docs-rename: No dependencies (foundation); PRD 00149 should land first so its four owned sites are not renamed twice
- pinned-strings: Depends on [docs-rename]

## Tasks

### Phase 0: Foundation
- [ ] Run the finder over markdown, judge each of the 168 lines, rename the invocations - the finder over `--type md` prints only lines that name a path, directory or phase (list them in the commit body).

### Phase 1: Core
- [ ] Update the pinned test strings and the CHANGELOG line (depends on: Phase 0) - the three suites above are green with zero new skips.

## Success Criteria

- `rg -nP '(?<!skills)/(run-autopilot|work|plan-tasks|review-work-completion|review-blindly|design-solution|review-plan|use-codex|use-gemini|use-sonnet)\b' skills agents README.md --type md` prints no line in which the reader is told to run the match.
- A fresh session reading `references/recovery.md` sees `/autopilot:run-autopilot status`, which resolves.
