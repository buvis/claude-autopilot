# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
