---
catchup: skip
design: skip
default_model: sonnet
model_tier_rationale: exact marker list and scrub site given; additive tests; no judgment
---

# Scrub inherited host markers at loop spawn

## Overview

### Problem Statement
On 2026-09-05 the 00171 review session carried `CODEX_SESSION_ID`, `CODEX_THREAD_ID` and `CODEX_CI=1`, inherited from the shell that launched `autoclaude`. `skills/use-codex/scripts/codex-run.sh:17` and `skills/use-gemini/scripts/gemini-run.sh:23` read `CODEX_SESSION_ID` or `COPILOT_CLI` as "already inside a CLI agent" and exit 3, so Bob ran on the Claude fallback, Carl was skipped, Blake's subagent hit the same refusal, and the build phase had to run `env -u CODEX_SESSION_ID -u COPILOT_CLI -u AUTOPILOT_DISPATCH_DEPTH bash dev/bin/release-checks` (recorded in `dev/local/autopilot/last-verification.json`; narrative in `dev/local/reviews/00171-route-sonnet-prompt-through-stdin-v1-review-1.md` § Reviewer availability). `cli/runner.py:185` builds the child environment as `{**env, **LAUNCH_ENV}` and passes every inherited variable through, and `cli/loop.py:379` does the same for the agoge session. A loop session is depth 0 by construction; the vendor markers are noise that trips the runners' nesting guards, and nothing records that the lanes were lost.

### Target Users
The operator, who launches `autoclaude` from whatever terminal is at hand, including one spawned by a codex or copilot session; the review phase, which needs its codex and gemini lanes.

### Success Metrics
- `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_runner.py -k "child_env or scrub"` passes with the five new tests named below.
- `rg -n 'LAUNCH_ENV' skills/run-autopilot/cli --glob '!test_*'` lists only `runner.py`.

## Functional Decomposition

### Capability: Host-marker hygiene at spawn
Every headless session the loop spawns starts without the vendor markers that mean "inside a CLI agent".

#### Feature: Scrub list
- **Description**: A frozen tuple `HOST_MARKERS` in `cli/runner.py`, declared next to `LAUNCH_ENV`.
- **Inputs**: none (constant).
- **Outputs**: `("CODEX_CI", "CODEX_SANDBOX", "CODEX_SANDBOX_NETWORK_DISABLED", "CODEX_SESSION_ID", "CODEX_THREAD_ID", "COPILOT_AGENT_SESSION_ID", "COPILOT_CLI", "COPILOT_CLI_BINARY_VERSION")`, the exact names `skills/use-codex/references/host-markers.md` lists.
- **Behavior**: `AUTOPILOT_DISPATCH_DEPTH` is deliberately NOT in the list. It is the runners' real backstop (host-markers.md line 8); a launcher that carries it is a genuine nesting and must stay visible to the guards.

#### Feature: child_env builder
- **Description**: `child_env(env: dict) -> tuple[dict, list[str]]` in `cli/runner.py`.
- **Inputs**: the parent environment dict.
- **Outputs**: `{**env, **LAUNCH_ENV}` with every `HOST_MARKERS` key removed, plus the sorted list of the names that were present.
- **Behavior**: pure, no I/O. `spawn()` and `loop.run_agoge()` call it instead of building the dict inline.

#### Feature: Scrub notice
- **Description**: one stderr line per spawn when the returned list is non-empty.
- **Inputs**: the scrubbed-name list.
- **Outputs**: `autopilot: scrubbed inherited host markers: CODEX_CI, CODEX_SESSION_ID, CODEX_THREAD_ID` (sorted, comma plus space) written to `sys.stderr` before `Popen`.
- **Behavior**: nothing is written when the list is empty. The runner's stderr is what the wrapper surfaces on exit (`_autoclaude_tracon_surface` in `~/.config/bash/plugins/development.plugin.bash`), so the notice lands in the operator's wrapper output without a new channel.

## Structural Decomposition

### Repository Structure

```
skills/run-autopilot/cli/
├── runner.py                 # Maps to: Host-marker hygiene at spawn (HOST_MARKERS, child_env, notice)
├── loop.py                   # Maps to: child_env call site in run_agoge
└── test_runner.py            # Maps to: scrub tests
skills/use-codex/references/
└── host-markers.md           # Maps to: source of the name list (doc note)
CHANGELOG.md
```

### Module: runner
- **Maps to capability**: Host-marker hygiene at spawn
- **Responsibility**: build the child environment for every headless session in one place
- **Exports**:
  - `HOST_MARKERS` - the frozen name tuple
  - `child_env(env)` - the scrubbed environment and the scrubbed names
  - `spawn(...)` - unchanged signature, now calls `child_env`

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **runner (constant + builder)**: `HOST_MARKERS`, `child_env`.

### Core Layer (Phase 1)
- **runner.spawn, loop.run_agoge**: Depends on [runner.child_env].

### Integration Layer (Phase 2)
- **docs**: Depends on [runner.spawn] (host-markers.md note, CHANGELOG entry).

## Implementation Phases

### Phase 0: Foundation
**Goal**: the scrub is a pure function with its own tests.

**Tasks**:
- [ ] Add `HOST_MARKERS` and `child_env(env)` to `cli/runner.py` (no deps) - Acceptance: `test_child_env_drops_every_host_marker` (parent env carrying all eight names plus `PATH`; the child lacks the eight, keeps `PATH`, carries every `LAUNCH_ENV` key; the returned list equals the eight names sorted) and `test_child_env_keeps_dispatch_depth` (`AUTOPILOT_DISPATCH_DEPTH=1` survives, list empty) pass in `cli/test_runner.py`.

**Exit Criteria**: `python -m pytest -q skills/run-autopilot/cli/test_runner.py -k child_env` passes.

### Phase 1: Core
**Goal**: every spawn goes through `child_env`.

**Tasks**:
- [ ] Replace `child_env = {**env, **LAUNCH_ENV}` at `runner.py:185` with the call and write the notice line when the list is non-empty (depends on: Phase 0) - Acceptance: `test_spawn_scrubs_host_markers` (a fake `runner_bin` script that dumps its environment to a file; the parent env sets `CODEX_SESSION_ID=x`; the dump lacks it; captured stderr contains exactly one line starting `autopilot: scrubbed inherited host markers:` naming `CODEX_SESSION_ID`) and `test_spawn_silent_without_markers` (no such line) pass.
- [ ] Route `loop.run_agoge` (`cli/loop.py:379`, the `{**env, **runner.LAUNCH_ENV}` spawn) through `runner.child_env` (depends on: Phase 0) - Acceptance: `rg -n 'runner.LAUNCH_ENV' skills/run-autopilot/cli/loop.py` returns nothing; `rg -n 'child_env' skills/run-autopilot/cli/loop.py` returns exactly one hit; `test_run_agoge_scrubs_host_markers` passes.

**Exit Criteria**: `rg -n 'LAUNCH_ENV' skills/run-autopilot/cli --glob '!test_*'` lists only `runner.py`.

### Phase 2: Integration
**Goal**: the behavior is documented where the markers are catalogued.

**Tasks**:
- [ ] Add a "Scrubbed at loop spawn" paragraph to `skills/use-codex/references/host-markers.md` naming `runner.HOST_MARKERS` and the depth exception, and a `### Fixed` CHANGELOG entry under `[Unreleased]` (depends on: Phase 1) - Acceptance: `rg -n 'HOST_MARKERS' skills/use-codex/references/host-markers.md CHANGELOG.md` returns one hit in each file.

**Exit Criteria**: `bash dev/bin/release-checks` passes.

## Test Strategy

### Critical Scenarios
- **Happy path**: parent shell carries `CODEX_SESSION_ID` → the child session lacks it; `codex-run.sh` no longer exits 3 for nesting; one notice line.
- **Edge case**: parent carries `AUTOPILOT_DISPATCH_DEPTH=1` → it survives and the runners' real guard still refuses.
- **Error case**: parent carries no marker → the child equals `{**env, **LAUNCH_ENV}` exactly and stderr stays silent.

## Risks
- **A launcher that legitimately nests** (autoclaude started from inside a dispatch) loses only the vendor markers and keeps `AUTOPILOT_DISPATCH_DEPTH`, so the runners still refuse. The backstop is preserved by design.
- **Wrapper noise**: at most one line per spawn, and only when markers were present.

## Post-completion notes (2026-09-07)

Converged (batch 202609061630); one deferred row walked 2026-09-07 in the config-audit closure walkthrough
(`~/.claude/dev/local/audit-results/2026-09-05.md`).

- `cli/loop.py` (1355 lines) and `cli/test_loop.py` (1404) exceed the 800-line cap, a violation that
  predates this PRD (1343 and 1378 at base f1489df) and fails rubric R13 on every loop PRD: PRD 00192 splits
  both by responsibility with a design doc first.
