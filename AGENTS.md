# AGENTS.md

## FROZEN since 2026-11-01

This repository is frozen. Autopilot is being ported to
`~/git/src/github.com/buvis/agent-plugins/plugins/autopilot`
(port inventory pinned at `e960ef1c`, `agent-plugins/tools/autopilot/source-pin.json`).

- Do not edit, commit, push, or run an autopilot loop here. Read only.
- A fix or feature for autopilot goes to `agent-plugins`, recorded through the
  port's inventory process there.
- The installed plugin still comes from this repo until the port ships. That
  does not reopen it: report a live bug to the user instead of patching here.
- A local pre-commit hook refuses commits. Only the user lifts the freeze.
