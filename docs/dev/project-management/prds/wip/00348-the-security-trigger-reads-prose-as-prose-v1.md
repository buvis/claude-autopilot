---
design: skip
default_model: sonnet
model_tier_rationale: one header-tracking variable and one condition with their exact text inside an existing loop, two additive tests, no existing test changes
---

# The security trigger reads prose as prose

Source: batch 202610161547, PRD 00330 (`hand-the-tail-sweep-to-a-task-tier-session-v1`, two prose-pin tasks, classified `solo` with reason `no_production_code`), 2026-10-17. The solo lane built it in 9 min for $2.33, then `lane-check` escalated the review to the full gate with signal `security_diff` (state `lane_escalated: {"from": "solo", "signal": "security_diff"}`), which bought an opus roster review of 16 min and $10.40 for two single-voice rows, one sonnet rework task and a second cycle. The diff changed `skills/run-autopilot/references/phase-review.md`, a test file and the CHANGELOG; its prose says "session" six times.

## Problem

`SECURITY_RE` (`skills/run-autopilot/cli/lane.py:51-55`) lists `session` beside `token`, `password` and `auth`, and `security_triggered` (`skills/run-autopilot/cli/lane.py:224-243`) tests every added or removed line of the diff with `securityish`, whatever file the line belongs to; only an adjacent `---`/`+++` header pair is skipped. `lane_check.py` returns `security_diff` whenever it fires (`skills/run-autopilot/cli/lane_check.py:81-82`). A doc path never fires by itself (`skills/run-autopilot/cli/test_lane.py:326-328`), but a sentence inside the doc does, so in this repository, whose prose is about sessions, tokens, permissions and hand-offs, the solo lane's one-pass review is unreachable for the docs-and-tests PRDs it exists for. `_DOC_SUFFIXES` (`skills/run-autopilot/cli/lane.py:58`) already names what a doc is.

## Solution

`security_triggered` tracks the file each hunk belongs to and skips the word test for lines under a doc. Inside the loop over `lines`, before the header-pair check, a `+++ ` header sets `current` to its path with a leading `b/` removed (`current = line[4:].strip()` then strip `b/`); `current` starts as `None`. The added-or-removed line test becomes: `if (line.startswith("+") or line.startswith("-")) and (current is None or not current.lower().endswith(_DOC_SUFFIXES)) and securityish(line): return True`. A diff with no header (the existing lone-line tests) keeps `current` at `None` and is tested as today; a `.md`, `.txt` or `.rst` hunk is never tested line by line; the path-level trigger is unchanged, so a file named `auth.md` still fires. The function docstring gains one sentence: `Lines under a doc file (_DOC_SUFFIXES) are prose and never fire; only their path can.`

## Requirements

### Must have
- The header tracking and the doc-aware condition in `security_triggered`, exactly as above; `securityish`, `SECURITY_RE`, the path-level check and the header-pair skip unchanged.
- Fail-first tests in `skills/run-autopilot/cli/test_lane.py` (registered under `[checks] effort lanes`, `dev/bin/release-checks:261`), beside the existing `security_triggered` tests (`skills/run-autopilot/cli/test_lane.py:323-347`), which all keep passing unchanged: `test_security_triggered_ignores_a_securityish_word_under_a_doc_header` (`"--- a/skills/run-autopilot/references/phase-review.md\n+++ b/skills/run-autopilot/references/phase-review.md\n@@ -1 +1 @@\n-the review session runs the sweep\n+the review session hands off\n"` with that `.md` path in `changed_files` is False) and `test_security_triggered_still_fires_on_a_code_hunk_after_a_doc_hunk` (the same doc hunk followed by `"--- a/cli/x.py\n+++ b/cli/x.py\n@@ -1 +1 @@\n+token = read()\n"` with both paths is True).
- A CHANGELOG `[Unreleased]` Fixed entry under **run-autopilot**: the lane's security trigger no longer escalates a solo PRD because its prose mentions a session or a token; only code lines and security-ish paths escalate.

### Nice to have
- None.

## Implementation

### Module: security-trigger
- **Location**: `skills/run-autopilot/cli/lane.py` (`security_triggered`)
- **Responsibility**: the diff-level trigger tests code lines, not prose
- **Exports**: `security_triggered()`, `securityish()` (unchanged signatures)

### Module: security-trigger-tests
- **Location**: `skills/run-autopilot/cli/test_lane.py`
- **Responsibility**: pin the doc skip and the code hunk that still fires
- **Exports**: none
- New symbols: `test_security_triggered_ignores_a_securityish_word_under_a_doc_header`, `test_security_triggered_still_fires_on_a_code_hunk_after_a_doc_hunk`

### Dependencies
- security-trigger: No dependencies (foundation)
- security-trigger-tests: Depends on [security-trigger]

## Tasks

### Phase 0: Foundation
- [ ] Add the two tests to `skills/run-autopilot/cli/test_lane.py`. Premise: `rg -c "current is None" skills/run-autopilot/cli/lane.py` prints 0 before the edit; a different count means the trigger already changed and the task stops and reports. - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_lane.py -k "doc_header or doc_hunk"` fails `test_security_triggered_ignores_a_securityish_word_under_a_doc_header` against the current trigger and passes `test_security_triggered_still_fires_on_a_code_hunk_after_a_doc_hunk`.

### Phase 1: Core
- [ ] Add the header tracking, the condition and the docstring sentence to `security_triggered`, and the CHANGELOG entry (depends on: Phase 0) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_lane.py skills/run-autopilot/cli/test_lane_check.py skills/run-autopilot/cli/test_lane_cli.py` passes; `rg -c "current is None" skills/run-autopilot/cli/lane.py` prints 1; `rg -n "run-autopilot.*security trigger" CHANGELOG.md` prints one line under `[Unreleased]`.

## Success Criteria

- Both new tests pass and the four existing `security_triggered` tests pass unchanged.
- Post-release signal: a solo-lane PRD whose diff is docs and tests finishes with `lane_escalated: null` in its `completed_prds` record unless a code line or a security-ish path is in the diff.
