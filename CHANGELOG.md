# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **run-autopilot**: a PRD may declare `eligibility: <shell command>`; when it
  exits non-zero, errors or times out the drain skips the PRD (it stays in
  `backlog/`, no session, no park) and records the skip in the batch summary.
  The check's own output never reaches `select`'s stdout, and a failure to
  record the skip exits 2 after printing the pick rather than losing it.
- **work**: the always-read SKILL.md body now sits under the 500-line ceiling
  (situational mechanics moved to references/ with read-at-trigger pointers) and
  a contract test fails when it grows past it.
- **review-work-completion**: when the project's dev/local is a symlink or the
  root is a dot-directory, Blake's run inputs carry a Filesystem notes block
  with the realpath, so the blind lens stops reporting existing files as
  missing.
- **work**: test-only, docs-only and config-only tasks now dispatch Ivan with
  the task's own checks as FAILING_TESTS; Ivan may edit test files his
  allowlist names; Tess receives <dir>/tests/HARNESS_CONTRACT.md whenever a
  touched file's directory carries one.
- **run-autopilot**: complete-prd appends one row per task attempt to
  dev/local/autopilot/ledger/attempts.jsonl before the per-PRD reset, so
  attempt history outlives the batch; a failed write aborts the close with
  state untouched.

### Fixed

- **work**: step 5.6 treats an empty-string task `description` as absent and
  falls back to the task name, so a self-deslop dispatch no longer carries an
  empty description body.
- **work**: check_build_overhead.py counts completed tasks from statectl
  task-done/task-set-status calls instead of the retired TaskUpdate tool, prints
  an explicit zero-tasks line instead of a 0.00 ratio, and reports Agent
  dispatches.
- **work**: the style-limit gate never reports a clean phase for a file it could
  not inspect. An unreadable changed file, or one skipped for an ambiguous
  diff-path tie, now exits 2 ("the gate could not run") instead of 0, which step
  7.0 records as `style_gate: clean`. Reproduced before the fix: the same file
  and diff reported a 61-line function and exit 1 when readable, and exited 0
  with only a note on stderr when unreadable — so the phase report certified a
  file the gate never opened.
- **work**: the style-limit gate no longer flags a long function that a
  deletion-only hunk merely surrounds. `git diff` emits three lines of context
  around a deletion, which the gate counted as "touched", so removing code above
  a pre-existing over-limit function reported that function as a new violation —
  the opposite of the introduced-only rule the gate exists to enforce.
- **work**: the style-limit gate fails loud instead of masquerading as a clean
  run. An unreadable changed file is now skipped with a note on stderr rather
  than silently, and a diff file that cannot be read exits 2 ("the gate could not
  run") instead of crashing to exit 1, which the caller reads as "violations
  found" and which made it dispatch a fix agent with an empty findings list.
- **work**: step 7 no longer contradicts itself about when a work phase may end.
  "Only stop the work phase once step 7 is fully green" sat above a sub-step that
  records a style-gate failure and proceeds, so a literal reader could stall the
  phase or loop on it. The stop condition is now scoped to the test suite, and a
  recorded `style_gate: failed:` is named as a sanctioned way to complete.
- **work**: the style-limit gate resolves each changed file to exactly one diff
  path instead of pooling every same-basename match. A diff touching both
  `conftest.py` and `tests/conftest.py` used to give one of them the other's hunk
  ranges and line counts, which could report a function as touched when its own
  hunk never touched it, and could invent or suppress a file-length violation
  through the pooled pre-image arithmetic. The deepest matching path now wins,
  and a genuine tie is skipped with both candidates named on stderr rather than
  silently picked.
- **work**: step 7.0's bare-repo `--git-dir`/`--work-tree` rule now governs both
  of its `git diff` invocations. It trailed only the first, so in a bare-repo
  home the second could be run without the flags and fail with "fatal: not a git
  repository". Step 7.0 also gained the missing branch for the gate's new exit
  code 2, which records the failure without dispatching a fix agent that would
  have nothing to fix.

## [0.1.2] - 2026-08-25

### Fixed

- Reviewer personas are dispatched as `autopilot:<name>`, not by bare name. The
  harness registers a plugin's agents under its namespace only, so every native
  lane that named a persona bare (Alice, Blake, Eve, and the two Claude
  fallbacks) failed its dispatch with `Agent type 'alice' not found` and was
  marked a failed reviewer — degrading the cycle quietly rather than loudly.

### Added

- **design-solution**: the pack now ships the design phase it drives. Every PRD
  that does not set `design_mode: skip` invokes `/design-solution`, and a missing
  sub-skill pauses the run — so an installed pack broke on its own default path.
  Its severity taxonomy ships with it as `references/cardinal-sins.md`.

### Changed

- The plugin registers all four of its hooks itself. `autopilot_context_cap_hook`
  (PostToolUse), `validate_state_json_hook` (PostToolUse) and
  `review_coverage_hook` (Stop) join `enforce_prd_location` in
  `hooks/hooks.json`. They were reached through a personal `~/.claude` dispatcher
  that globbed the installed plugin cache to find them, which worked but broke
  silently whenever the cache layout changed.

### Documentation

- The "What intentionally stays out" list now names `review-fanout.workflow.js`
  and `rules-library/rationalizations.md`, the two host-local files the pack
  reads but does not ship. Both degrade gracefully; neither was documented.

## [0.1.1] - 2026-08-25

### Fixed

- The `enforce_prd_location` hook now actually runs. It shipped in 0.1.0 as a
  bare `.py` file with no `hooks/hooks.json`, so Claude Code registered zero
  hooks and the file was inert. It is now wired to `PreToolUse` on
  `Edit|Write|MultiEdit` and on `Bash`, and `hooks/_common.py` ships alongside
  it — without that sibling the hook raised `ImportError` on every invocation.

## [0.1.0] - 2026-08-25

### Added

- First release as a plugin. Nine skills (`run-autopilot`, `plan-tasks`, `work`,
  `review-work-completion`, `review-blindly`, `review-plan`, `use-codex`,
  `use-gemini`, `use-sonnet`), fourteen agents, and the
  `enforce_prd_location.py` hook, extracted from personal configuration into an
  installable pack.
- **use-codex, use-gemini**: recursion guard. Both runners exit 3 rather than
  dispatch a CLI agent from inside a CLI agent, detected by the
  `AUTOPILOT_DISPATCH_DEPTH` counter each runner exports and by the host marker
  the CLI sets in its own children (`CODEX_SESSION_ID`, `COPILOT_CLI`).
  `review-work-completion` already degrades on a non-zero runner exit, so a
  refusal costs one reviewer rather than the cycle.
- **use-codex**: `references/host-markers.md` records the probed markers per
  vendor, including that the native Gemini CLI could not be probed.

### Changed

- Skills, agents and scripts locate pack files through `${CLAUDE_PLUGIN_ROOT}`
  (skill bodies), `$0`/`__file__` (scripts), or an explicit note naming the
  resolved root (reference files), instead of the `~/.agents/skills/` and
  `~/.claude/agents/` paths that only existed on the author's machine.
