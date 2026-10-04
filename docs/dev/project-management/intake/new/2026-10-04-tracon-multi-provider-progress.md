# Shared progress reporting for autopilot runners

Date: 2026-10-04
Status: intake
Destination: claude-autopilot/docs/dev/project-management/intake/new/

## Problem

Autocodex repeats `codex running; raw output: <path>` every 60 seconds without showing actual activity or reviewer progress. Autoclaude launches tracon by default in an interactive terminal, with a plain stream renderer as fallback. Autocodex bypasses that presentation layer.

Tracon lives in `buvis/claude-autopilot`, under `skills/run-autopilot/scripts/tracon/`, with entry point `skills/run-autopilot/scripts/tracon.py`.

## Requirement

Make tracon and plain terminal reporting support autoclaude and autocodex through a shared reporting contract, with an adapter boundary ready for future autokiro and autocopilot runners.

- Show live phase, PRD/task, provider/model, session elapsed time, messages, tool/command activity, reviewer or worker activity where exposed, and failures.
- During quiet periods, show time since last substantive activity and last known activity. Expose running, waiting, memory-pressure suspension, and failure using available evidence.
- Print the native log path once per session instead of repeating it as the heartbeat.
- Translate provider-native events into a shared reporting stream consumed by both tracon and the plain renderer. Preserve native logs for diagnosis.
- Publish events incrementally, before session completion.
- Preserve attach/detach, pause-at-boundary, stop/cleanup, duplicate-loop protection, and fresh-session boundaries. Reporting must not introduce another lifecycle/state writer.
- Display unavailable usage, cost, or worker telemetry explicitly rather than inventing values.
- Keep provider-specific parsing out of dashboard panels. Future providers should require an adapter, not another dashboard.

## Current implementation evidence

Inspected locally on the intake date:

- `~/.config/bash/plugins/development.plugin.bash`: autoclaude has the tracon front end; autocodex directly invokes its Python driver.
- `~/.config/autocodex/driver.py`, `collect()`: reads structured events live but prints only the repeated 60-second heartbeat.
- `~/.config/autocodex/adapter.py`: copies the native log into `last-session.log` only after the session returns.
- `skills/run-autopilot/scripts/tracon/screens.py`: follows `last-session.log`.
- `skills/run-autopilot/scripts/tracon/stream.py`: rendering, usage, and agent tracking consume Claude-specific events.
- Autocodex already inherits shared loop machinery and sets `_AUTOPILOT_LOOP` for registry identification.

## Acceptance criteria

1. Running Codex sessions show messages and tool starts/completions before exit in both TUI and plain modes.
2. Claude retains existing activity, usage, and worker visibility.
3. Quiet sessions show elapsed/idle time and last known activity without repeated log paths.
4. Session transitions and memory-pressure waits are visible; prior-session activity cannot masquerade as current activity.
5. Lifecycle checks cover attach/detach, pause, Ctrl-C cleanup, and duplicate-loop rejection for both runners.
6. Adapter fixture checks cover Claude/Codex events, unknown/malformed events, failures, and unavailable telemetry.
7. The contract documents future Kiro/Copilot integration. Implementing those runners is outside this requirement.

## Open questions

- Where should the shared contract and adapters live, given tracon's repository and the current personal Codex configuration?
- Should useful plain Codex reporting ship first, or together with tracon integration?
