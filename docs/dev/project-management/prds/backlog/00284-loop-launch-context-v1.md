---
design: skip
default_model: sonnet
model_tier_rationale: transcription - exact argv, default JSON, message format and fallback expression given; named tests; one live launch check
---

# Loop launch context: MCP allowlist, brief repo root, full validator rejection

## Overview

### Problem Statement
Each headless loop session starts at about 85K tokens of context before any
work. Part of that is every claude.ai connector the account has (seven today:
Docs, Reader, Tidal, Mermaid, Excalidraw, Cloudflare, Context7), and loop
sessions need only Context7. The session brief prints `repo root: none` on
every normal run (`skills/run-autopilot/cli/brief.py:109` reads `state.repo_root`, which only
`records.py` writes). The `autonomous_decisions` validator names one missing
field per rejection, so a watched session needed five rejected calls to add
one entry. Source: discovery
`docs/dev/project-management/discovery/00281-loop-efficiency.md` (F7, F9,
F13).

### Target Users
The operator running `autoclaude`, and every loop session.

### Success Metrics
- `test_build_argv_strict_mcp_default_is_context7` and `test_mcp_config_override_and_inherit` pass.
- `env AUTOPILOT_LIVE=1 uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_launch_mcp_live.py` passes (Context7 only by default; the override changes the list).
- `test_brief_repo_root_falls_back_to_project_root` and `test_validator_names_every_missing_field` pass.
- `bash dev/bin/release-checks` exits 0 with `FAIL 0` on its summary line at the end of the last phase.

## Functional Decomposition

### Capability: Narrow launch environment

#### Feature: MCP allowlist (F7)
- **Description**: Loop sessions load only the Context7 MCP server unless `_AUTOPILOT_MCP_CONFIG` says otherwise.
- **Inputs**: env `_AUTOPILOT_MCP_CONFIG`: unset gives the default; `inherit` gives no MCP flags (today's launch); any other value is passed verbatim to `--mcp-config` (a JSON string or a file path, both accepted by `claude`).
- **Outputs**: `build_argv(..., mcp_config=<value>)` inserts `--strict-mcp-config --mcp-config <value>` before `--output-format`; with `None`, no flags.
- **Behavior**: `DEFAULT_MCP_CONFIG = '{"mcpServers":{"context7":{"type":"http","url":"https://mcp.context7.com/mcp"}}}'`. Checked live on 2026-10-12 with `claude -p --model haiku`. With no flags, `system/init.mcp_servers` listed the seven claude.ai connectors. `--strict-mcp-config --mcp-config '{"mcpServers":{}}'` gave `[]`, so strict also drops claude.ai connectors. The default above gave `[{"name":"context7","status":"connected","source":"dynamic"}]`. The claude.ai Context7 connector is therefore not kept; the local HTTP entry replaces it. `spawn` resolves the value with `mcp_config_for(env)`. Per-repo override: set `_AUTOPILOT_MCP_CONFIG` in that repo's environment.

### Capability: Session brief

#### Feature: Repo root fallback (F9)
- **Description**: The brief's `repo root` falls back to the project root when `state.repo_root` is unset.
- **Inputs**: `state.repo_root`; `project_root` (new keyword on `render_brief`, default `None`).
- **Outputs**: `- repo root: <state.repo_root or project_root or none>`.
- **Behavior**: `statectl.write_brief` passes `str(custody.project_root(state_path.parent))`. Called without the keyword, `render_brief` keeps today's output, so the golden brief and `test_brief.py`'s `repo root: none` case stay valid.

### Capability: State validator

#### Feature: All missing fields in one rejection (F13)
- **Description**: `_validate_decision_entry` collects every missing field and raises once.
- **Inputs**: an appended `autonomous_decisions` entry.
- **Outputs**: `SchemaError("autonomous_decisions entry missing " + ", ".join(missing))`.
- **Behavior**: The order is the rule order: `issue`, `action`, `reason` (each satisfied by its alternative in `_DECISION_PROSE_PAIRS`), then `cycle`, then `severity`. For `assumed-ambiguity` entries it is `question`, `assumption`. A non-dict entry stays `missing issue`. With one field missing the message is byte-identical to today's, so every single-field test stands. A bare `{"cycle": 1}` now reads `autonomous_decisions entry missing issue, action, reason, severity`.

## Structural Decomposition

### Repository Structure

```
skills/run-autopilot/cli/
├── runner.py                 # Maps to: MCP allowlist
├── test_launch_mcp_live.py   # Maps to: MCP allowlist (live, opt-in)
├── brief.py                  # Maps to: Repo root fallback
├── statectl.py               # Maps to: Repo root fallback (passes project_root)
└── schema.py                 # Maps to: All missing fields in one rejection
dev/bin/release-checks        # [checks] l3 gains test_launch_mcp_live.py
```

### Module: runner
- **Maps to capability**: Narrow launch environment
- **Responsibility**: The MCP flags on the launch line.
- **Exports**:
  - `DEFAULT_MCP_CONFIG` - the Context7-only config string.
  - `mcp_config_for(env)` - `None` for `inherit`, the env value when set, else the default.
  - `build_argv(..., mcp_config=None)` - new keyword.
- New symbols: `DEFAULT_MCP_CONFIG`, `mcp_config_for`, `mcp_config`, `test_launch_mcp_live.py`, `_AUTOPILOT_MCP_CONFIG`, `context7`, `mcp_servers`, `test_build_argv_strict_mcp_default_is_context7`, `test_mcp_config_override_and_inherit`

### Module: brief
- **Maps to capability**: Session brief
- **Responsibility**: Render the repo root with a fallback.
- **Exports**: `render_brief(state, now, project_root=None)`.
- New symbols: `project_root`, `test_brief_repo_root_falls_back_to_project_root`

### Module: schema
- **Maps to capability**: State validator
- **Responsibility**: One rejection naming every gap.
- **Exports**: `_validate_decision_entry` (same name, collected message).
- New symbols: `test_validator_names_every_missing_field`, `test_bare_entry_names_every_missing_key_in_rule_order`

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **runner**: argv and env resolution.
- **brief**: fallback.
- **schema**: collected message.

### Core Layer (Phase 1)
- **live launch check**: Depends on [runner]

### Integration Layer (Phase 2)
- **docs**: Depends on [runner]

## Implementation Phases

### Phase 0: Foundation
**Goal**: Three independent code changes.

**Tasks**:
- [ ] `DEFAULT_MCP_CONFIG`, `mcp_config_for`, the `mcp_config` keyword on `build_argv`, and `spawn` passing `mcp_config_for(env)` (no deps) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_runner.py -k "mcp"` passes, including `test_build_argv_strict_mcp_default_is_context7` (the exact flag pair, before `--output-format`) and `test_mcp_config_override_and_inherit`. Existing `build_argv` tests stay green, because `mcp_config=None` keeps today's argv.
- [ ] `render_brief(..., project_root=None)` and `write_brief` passing it (no deps) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_brief.py -k "repo_root"` passes, including `test_brief_repo_root_falls_back_to_project_root` (a state without `repo_root` written through `write_brief` shows the project root, never `none`); the golden test is unchanged.
- [ ] Collected message in `_validate_decision_entry` (no deps) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_schema_decision_entries.py skills/run-autopilot/cli/test_schema_decision_scope.py` passes with `test_validator_names_every_missing_field` added. Premise: only `test_bare_entry_names_issue_before_the_other_missing_keys` asserts a message for an entry missing two or more fields. Re-check by running both files after the change: exactly that one test should fail before it is updated to `missing issue, action, reason, severity` and renamed `test_bare_entry_names_every_missing_key_in_rule_order`. If any other test fails, stop and report rather than editing it.

**Exit Criteria**: the three filters pass.

### Phase 1: Core
**Goal**: Prove the effect on a real launch, not just the flag.

**Tasks**:
- [ ] `cli/test_launch_mcp_live.py`: builds argv with `build_argv("haiku", "low", None, mcp_config=mcp_config_for(env), prompt="reply ok")` plus `--max-turns 1`, runs it with a child env built from `os.environ` without `_AUTOPILOT_LOOP` and with `CLAUDE_NESTED=1` and `_CLAUDE_NOTIFY_QUIET=1` (as `skills/use-sonnet/scripts/sonnet-run.sh` lines 16-33 do, so the nested session can never write the loop's signal file), and parses the `system`/`init` event. It asserts on the `mcp_servers` entries' `name` values only, never on `status`, so an unreachable endpoint cannot red it. The test is skipped unless `AUTOPILOT_LIVE=1`, so the default suite never spends money or needs the network; the file is registered in the `[checks] l3` block of `dev/bin/release-checks` (PRD 00278's pin fails on an unregistered test file; it skips there) (depends on: Phase 0) - Acceptance: `env AUTOPILOT_LIVE=1 uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_launch_mcp_live.py` passes with 2 tests run and 0 skipped. With env unset, `mcp_servers` names are exactly `["context7"]`; with `_AUTOPILOT_MCP_CONFIG='{"mcpServers":{}}'` they are `[]`; `rg -n "test_launch_mcp_live.py" dev/bin/release-checks` hits.

**Exit Criteria**: the live check passes.

### Phase 2: Integration
**Goal**: Docs.

**Tasks**:
- [ ] Document `_AUTOPILOT_MCP_CONFIG` (default, `inherit`, override) beside the other `_AUTOPILOT_*` knobs in the run-autopilot docs and in `runner.py`'s module docstring launch line; add CHANGELOG `[Unreleased]` entries: Changed (loop sessions load only Context7) and Fixed (brief repo root, validator lists all missing fields) (depends on: Phase 1) - Acceptance: `rg -n "_AUTOPILOT_MCP_CONFIG" skills/run-autopilot` hits code and docs; `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_doc_contract.py` passes.

**Exit Criteria**: `bash dev/bin/release-checks` exits 0 with `FAIL 0` on its summary line.

## Test Strategy

### Critical Scenarios
- **Happy path**: env without `_AUTOPILOT_MCP_CONFIG` → Expected: argv holds `--strict-mcp-config --mcp-config <DEFAULT_MCP_CONFIG>`; the live init lists `context7` only.
- **Edge case**: `_AUTOPILOT_MCP_CONFIG=inherit` → Expected: no MCP flags (today's launch).
- **Edge case**: state with `repo_root` set → Expected: brief shows it, not the fallback.
- **Error case**: entry `{"cycle": 1}` → Expected: one `SchemaError` naming `issue, action, reason, severity`.

## Risks

- **Context7 HTTP endpoint down**: the session starts without it, as when the connector is down today; `inherit` restores the old launch. The live test asserts server names, not status, so an outage cannot red it.
- **A repo needs another server**: set `_AUTOPILOT_MCP_CONFIG` for that repo.
- **Boot-context saving not measured per batch**: the nice-to-have metrics field (first-turn context tokens) is deferred, so the effect shows only in session cost. See the discovery doc.
