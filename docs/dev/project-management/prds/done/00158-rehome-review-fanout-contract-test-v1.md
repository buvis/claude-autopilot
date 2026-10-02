---
catchup: skip
design: skip
---

# Rehome the orphaned review-fanout contract test

Source: the pre-existing suite failures surfaced while draining PRD 00156 (2026-08-27). Every count below was measured that day; nothing is a guess unless marked `(guess)`.

## Problem

`skills/review-work-completion/scripts/test_review_fanout_contract.py` pins a file this pack does not own. It resolves `CLAUDE_DIR = Path(__file__).resolve().parents[3]` and reads `<CLAUDE_DIR>/workflows/review-fanout.workflow.js` and `<CLAUDE_DIR>/workflows/_harness.mjs`. Before the plugin extraction (commit `3f4ef75`, 2026-08-25) `parents[3]` was `~/.claude` and both files were there; now it is this repo's root, which has no `workflows/` directory at all. The workflow, its node behavioral suite (`_harness.mjs`, six `*.test.mjs`, `fixtures/`) and the fixtures stayed on the host, where host PRD 00104 created them.

Running `pytest skills/review-work-completion/scripts` therefore reports 18 failures (15 `ReviewFanoutContractTests` errors at setup, 3 `RenderedReviewFilePassesTheRealCoverageGateTests` failures), all one cause: `FileNotFoundError` / `ERR_MODULE_NOT_FOUND` on the two missing host files. The suite has been red since the extraction and nothing depends on it being green, so the failures read as background noise and mask any real regression that lands in the other 204 tests.

Skipping when the workflow is absent would not fix the ownership error either. `skills/review-work-completion/SKILL.md:271` states the design deliberately: the workflow "is **not shipped with this pack**: it is a host-local workflow file, conventionally `~/.claude/workflows/review-fanout.workflow.js`", and when it is absent the `workflow` and `shadow` consensus engines are simply unavailable and the skill falls back to `legacy`. A test that hard-fails on a file the pack documents as optional is wrong for every operator who installs the plugin without it, and a test that skips instead would have no teeth in the only place it ever runs.

## Solution

Move the file to the host, beside the workflow it pins, and give it a resolver for the one thing it still needs from this pack. `~/.claude/hooks/tests/` is the host's pytest home in practice (it already holds `test_settings_wiring.py`, `test_survey.py` and `test_development_plugin_skill_root.py`, none of them hook tests), so the moved file joins the suite the operator already runs. Its 15 source-text cases then sit next to the `.js` they pin. Its 3 coverage-gate cases render markdown through `_harness.mjs` and feed the result to this pack's `check_review_file.py`, so they resolve that script from the installed plugin cache the way `~/.config/bash/plugins/development.plugin.bash`'s `_autopilot_skill_root` does: an env override, then the highest installed version under `~/.claude/plugins/cache/buvis-plugins/autopilot/`, then a clear failure. Both installed versions (0.1.2, 0.2.0) ship `check_review_file.py`, so the resolver has something to find today. The pack's copy is then deleted.

The work spans two repos: the new file lands in `~/.claude` (tracked in the buvis bare repo), the deletion lands here. Under an unattended drain the autopilot write fence denies writes outside the session repo, so a batch running this PRD from this repo needs `_AUTOPILOT_WRITE_SCOPE_EXTRA="$HOME/.claude"` exported, or the move done by hand.

## Requirements

### Must have

- The 18 cases live at `~/.claude/hooks/tests/test_review_fanout_contract.py` and pass there. `WORKFLOW_JS` and `HARNESS_MJS` resolve to `~/.claude/workflows/`, derived from the file's own location, not from a `parents[N]` count that silently re-points when the file moves.
- The three coverage-gate cases locate `check_review_file.py` through a resolver with the `_autopilot_skill_root` shape: `_AUTOPILOT_SKILL_ROOT` (or an equivalent named override) first, then the highest installed version under `~/.claude/plugins/cache/buvis-plugins/autopilot/`, then a failure naming what is missing and how to point at a dev checkout. Never a pinned version - the cache has rolled under a running PRD before.
- `pytest skills/review-work-completion/scripts` in this repo runs clean with no `--ignore`, no new skips, and 204 tests passing.
- `uv run --with pytest --with tree-sitter-language-pack pytest hooks/tests` in `~/.claude` passes with the 18 moved cases included and zero failures.
- The moved test still bites: with a scratch copy of the workflow whose pure-region start marker is deleted, and again with one whose `decideVerdict(...)` call site is replaced by a literal verdict, the corresponding case fails. Prove each once against the mutated copy, never against the shipped file.
- **Premise (re-check at execution):** `skills/review-work-completion/scripts/test_review_fanout_contract.py` exists in this repo and `~/.claude/hooks/tests/test_review_fanout_contract.py` does not. If either is already false the move has happened or diverged - skip the delete and report, never force it.
- No CHANGELOG entry: moving a test is `test`/`chore` per `rules/changelog.md`, with no user-visible change.

### Nice to have

- A one-line pointer in `skills/review-work-completion/SKILL.md` near line 271, next to the sentence that already declares the workflow host-local, naming where its contract test now lives `(guess: worth it only if a reader of that paragraph would otherwise go looking in this repo)`.

## Implementation

### Module: hosted-contract-test
- **Location**: `~/.claude/hooks/tests/test_review_fanout_contract.py` (buvis-tracked; stage with `git --git-dir=~/.buvis --work-tree=~ add ':(top).claude/hooks/tests/test_review_fanout_contract.py'`)
- **Responsibility**: the 18 cases, with both path resolvers repointed.
- **Exports**: none (test)

### Module: pack-cleanup
- **Location**: `skills/review-work-completion/scripts/test_review_fanout_contract.py` (deleted), `skills/review-work-completion/SKILL.md` (optional pointer)
- **Responsibility**: remove the orphan so this repo's suite is green.
- **Exports**: none

### Dependencies
- hosted-contract-test: No dependencies (foundation)
- pack-cleanup: Depends on [hosted-contract-test] - the copy is deleted only after the moved one passes on the host

## Tasks

### Phase 0: Foundation
- [ ] Move the file to `~/.claude/hooks/tests/`, repoint `WORKFLOW_JS`/`HARNESS_MJS` at `~/.claude/workflows/` from the file's own location, and add the plugin-cache resolver for `check_review_file.py` - `uv run --with pytest --with tree-sitter-language-pack pytest hooks/tests` in `~/.claude` passes with the 18 new cases and zero failures; with `_AUTOPILOT_SKILL_ROOT` pointed at a directory holding no `check_review_file.py`, the three coverage-gate cases fail with a message naming the missing script rather than a bare `FileNotFoundError`.
- [ ] Prove the moved test still bites (depends on: previous task) - against a scratch copy of `review-fanout.workflow.js` with the pure-region start marker deleted, the marker case fails; against a copy whose `decideVerdict(...)` call site is replaced by `verdict: "APPROVE"`, the call-site case fails. Both mutations on copies under the session scratch dir; the shipped workflow is never edited.

### Phase 1: Core
- [ ] Delete the pack's copy after re-checking the premise above (depends on: Phase 0) - `pytest skills/review-work-completion/scripts` reports 204 passed, no ignores, no new skips, and `rg --files -g 'test_review_fanout_contract.py' <repo>` returns nothing.

## Success Criteria

- `uv run --with pytest pytest skills/review-work-completion/scripts -q` exits 0 with 204 passed and no `--ignore` flag.
- `uv run --with pytest --with tree-sitter-language-pack pytest hooks/tests -q` in `~/.claude` exits 0 and reports 18 more tests than it did before this PRD.
- Deleting a pure-region marker from a scratch copy of the workflow fails a named case, so the contract the extraction silently disarmed has teeth again.
