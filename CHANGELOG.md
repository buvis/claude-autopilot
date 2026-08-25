# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
