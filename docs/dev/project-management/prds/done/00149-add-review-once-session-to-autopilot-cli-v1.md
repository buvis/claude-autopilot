---
catchup: skip
design: skip
---

# Add a one-shot review session to the autopilot CLI

Source: `~/.claude/dev/local/discovery/00148-autopilot-fast-track-learnings.md` § 7, plus one launch bug found while reading the loop for it. Numbers and paths come from the PRD 00136 and 00140 runs; nothing is a guess unless marked `(guess)`. Companion: `~/.claude` PRD 00150 repoints the buvis shell front-end (`autopilot`, `autoclaude`, `tracon` functions) at the installed plugin; without it no `autopilot <verb>` resolves from a shell, this one included.

## Problem

The hybrid fast track (decided 2026-08-25) drives builds in the operator's session and mandates a fresh headless session for every review and finalize hand-off. That hop has no first-class command. Both times it was needed (PRD 00136, PRD 00140) it was a throwaway driver in `dev/local/tmp/00136-run-review.py` / `00140-run-review.py`: 85 lines that re-implement the loop's routing and spawn call by hand, hardcode `AP_DIR`, the plugin cache path and a write-scope export, and skip the loop's registry (a concurrent `autoclaude` cannot see the session, and the one-shot cannot see a live loop), plugin-drift and schema gates, and the per-session metrics row. `dev/local/tmp` is GC'd at 7 days, so the driver has to be recreated from a memory note each time. The body it needs already exists as one iteration of `Loop._run_loop` (`cli/loop.py:1079-1164`) minus the acting branches.

Second, the loop launches every session with `runner.DEFAULT_PROMPT = "/run-autopilot"` (`cli/runner.py:51`). Since the plugin extraction of 2026-08-25 the skill is plugin-namespaced: `~/.claude/skills/run-autopilot` no longer exists and the only `run-autopilot` is `~/.claude/plugins/cache/buvis-plugins/autopilot/<version>/skills/run-autopilot`, invoked as `/autopilot:run-autopilot`. The 00140 driver had to override the prompt for that reason. A loop session launched with the bare name has no skill to run; the loop's operator runbook lines (`claude → /run-autopilot`) and SKILL.md § Session Loop repeat the stale name.

## Solution

One new verb, `autopilot review-once`, implemented as `Loop.run_once()`: the loop's own preflights, one routed spawn for `state.next_phase`, the decision read and the metrics row, then exit. No relaunch, no park, no purge/agoge, no notification. It refuses any phase other than `review` or `done` before spawning, so the operator cannot start a build with it by accident. And the launch prompt becomes `/autopilot:run-autopilot` everywhere the CLI owns it.

## Requirements

### Must have

- `cli/loop.py`: `Loop.run_once() -> int`. Order: `_memory_gate`, `_resolve_ap_dir`, `_register`, `_plugin_gate`, `_schema_gate` (same code and order as `_run_loop`; any non-None code tears down and returns it). The pause marker is left untouched: no `consume_pause`, no `clear_paused`, no `stamp_paused`. Then the phase guard: load `state.json`; when the file is missing or unreadable, or `next_phase` is not `"review"` or `"done"`, print `autopilot review-once: next_phase is '<value>' (<state path>); this verb runs review and finalize sessions only. Drive the build in your session, or run autoclaude.` to `self.err`, tear down, return 1 with no spawn (`<value>` is `missing` when the file cannot be read). Otherwise: `routing.route(next_phase, ap_dir, env=self.env)`, the same `━━ <stamp> · phase … ━━` banner as the loop, `self._spawn(...)` with the loop's exact keyword set (so `ScriptedSpawn` and the real `runner.spawn` both fit), `_cleanup_orphans`, `_decide`, `_append_metrics` with `phase_launched = next_phase`; NOT `_fingerprint_bound` (it parks). Then print `autopilot review-once: signal <signal> · next phase '<next>' · <detail>` to `self.out`, tear down, and return 0 when `decision["state_touched"]` is true and the signal is not `state_write_failed`, else 1. `run()`'s SIGTERM/SIGHUP handler block and the `KeyboardInterrupt -> 130` path are shared with `run_once()` through one private wrapper (extract, do not duplicate). `_AUTOPILOT_LOOP` needs no new code: `Loop.__init__` already stamps it with the driver's own pid and the child inherits it.
- `cli/__main__.py`: `"review-once": (_add_review_once, _run_review_once)` in `_SUBCOMMANDS`, no flags (same rationale as `loop`: it anchors on cwd and the `_AUTOPILOT_*` env), lazy `from cli import loop`, returns `loop.Loop().run_once()`. The module docstring's subcommand list gains a `review-once` entry stating the phase guard and the exit rule.
- `skills/run-autopilot/SKILL.md` § Session Loop (the paragraph at line 153): one added sentence naming the literal `autopilot review-once` (the doc-contract test requires the invocation form in SKILL.md or `references/*.md`): it runs one review or finalize session for `state.next_phase` and exits, never relaunches or parks, and the operator exports `_AUTOPILOT_WRITE_SCOPE_EXTRA` first when the project needs it (`~/.claude/AGENTS.md` § Toolchain).
- Prompt rename. Premise: `~/.claude/skills/run-autopilot` does not exist and `~/.claude/plugins/cache/buvis-plugins/autopilot/*/skills/run-autopilot/SKILL.md` does, so the bare skill name is unresolvable and the namespaced one is live. Re-check both paths at execution time; if `~/.claude/skills/run-autopilot` exists again, skip this item and report it. Change: `cli/runner.py` `DEFAULT_PROMPT = "/autopilot:run-autopilot"` and the docstring launch line (line 7); every `/run-autopilot` literal in `cli/loop.py` operator messages (the pause runbook `claude → /run-autopilot, then autoclaude` and any sibling) becomes `/autopilot:run-autopilot`; SKILL.md lines 153 and 222 (`claude -p "/run-autopilot"`) likewise. `cli/test_runner.py:62` and `cli/test_loop.py:442` are updated to the new literal (they pin the old one). References under `references/*.md` that mention `/run-autopilot` as a human-typed command are out of scope here (dozens of sites; a docs chore, see Nice to have).
- Tests, fail-first per `rules/testing.md`, in `cli/test_loop.py` using the existing `make_loop` / `ScriptedSpawn` / `write_state` fixtures:
  - `test_review_once_spawns_the_review_route_once_and_exits_zero`: state `next_phase: "review"`; the step rewrites state with `next_phase: "build"` and a result log; `run_once() == 0`, exactly one launch with `OPUS`/`xhigh`/cap 10800, `out` contains `signal continue` and `next phase 'build'`.
  - `test_review_once_finalize_routes_sonnet_medium`: `next_phase: "done"` launches `SONNET`/`medium`.
  - `test_review_once_refuses_a_build_phase_without_spawning`: `next_phase: "build"` returns 1, zero launches, `err` names `review-once` and `build`.
  - `test_review_once_refuses_without_state_json`: no state file, returns 1, zero launches.
  - `test_review_once_dead_session_exits_one_without_retry_or_park`: `noop_step` returns 1 after one launch, the PRD file is still in `wip/`, the notifier recorded no calls.
  - `test_review_once_exits_zero_when_the_session_pauses`: the step writes `pause_reason` (the rework-cap shape from `test_review_cap_pause_summarizes_and_lists_findings`) and returns 0 with `signal paused` in `out`, no notification.
  - `test_review_once_writes_one_metrics_line`: exactly one row in `loop-metrics.jsonl` with `phase == "review"`.
  - `test_review_once_leaves_the_pause_marker_in_place`: a pause marker present before the call is still present after it, and the session still ran.
  - `test_review_once_refuses_when_a_loop_is_live`: the `_spawn_tagged_incumbent` pattern from `test_duplicate_loop_guard_refuses_a_second_loop`; returns 1, zero launches.
  - `cli/test_runner.py`: `build_argv` with the default prompt ends in `/autopilot:run-autopilot`.
  - `cli/test_doc_contract.py` and `cli/test_cli.py` need no new cases: the registry loop covers `review-once` once it is registered, and the doc test fails until SKILL.md names it.
- `CHANGELOG.md` `[Unreleased]`: one `**run-autopilot**` line under Added (`autopilot review-once`) and one under Fixed (sessions launch `/autopilot:run-autopilot`, the namespaced skill), per `rules/changelog.md`.

### Nice to have

- A docs sweep replacing human-typed `/run-autopilot` with `/autopilot:run-autopilot` under `skills/*/references/` and `README.md` (dozens of sites, matched together with `skills/run-autopilot/...` path fragments, so it needs a hand pass). Separate chore, not this PRD.

## Implementation

### Module: run-once
- **Location**: `skills/run-autopilot/cli/loop.py`, `skills/run-autopilot/cli/test_loop.py`
- **Responsibility**: `Loop.run_once()` and the shared signal wrapper; one session, no acting branches.
- **Exports**: `Loop.run_once()`

### Module: cli-verb
- **Location**: `skills/run-autopilot/cli/__main__.py`, `skills/run-autopilot/SKILL.md` (§ Session Loop, one sentence)
- **Responsibility**: register and document `autopilot review-once`.
- **Exports**: `_SUBCOMMANDS["review-once"]`

### Module: launch-prompt
- **Location**: `skills/run-autopilot/cli/runner.py`, `cli/loop.py` (operator messages), `cli/test_runner.py`, `cli/test_loop.py`, `SKILL.md` lines 153 and 222
- **Responsibility**: the namespaced skill name in the launch argv and the runbook text.
- **Exports**: `runner.DEFAULT_PROMPT`

### Dependencies
- launch-prompt: No dependencies (foundation)
- run-once: Depends on [launch-prompt] (the one-shot must spawn a prompt that resolves)
- cli-verb: Depends on [run-once]

## Tasks

### Phase 0: Foundation
- [ ] Rename the launch prompt (premise re-check first: `test -e ~/.claude/skills/run-autopilot` must fail and `ls ~/.claude/plugins/cache/buvis-plugins/autopilot/*/skills/run-autopilot/SKILL.md` must succeed; otherwise skip and report) - `rg -n '/run-autopilot' skills/run-autopilot/cli/runner.py skills/run-autopilot/cli/loop.py` prints only `/autopilot:run-autopilot` lines; `rg -n 'claude -p "/run-autopilot"' skills/run-autopilot/SKILL.md` prints nothing; `test_runner.py` and `test_loop.py` pass with the new literal.

### Phase 1: Core
- [ ] Implement `Loop.run_once()` with the shared signal wrapper and the nine `test_review_once_*` tests written first (depends on: Phase 0) - the nine tests fail on the old code (no `run_once` attribute) and pass after; the full `cli/` suite stays green (`uv run --with pytest --with rich --with textual pytest skills/run-autopilot`).
- [ ] Register `review-once` in `cli/__main__.py`, document it in the module docstring and SKILL.md § Session Loop, add the two CHANGELOG lines (depends on: Phase 1 task 1) - `python3 skills/run-autopilot/cli/__main__.py review-once` run from a directory with no `dev/local/autopilot` ancestor exits 1 with the `next_phase is 'missing'` message and launches nothing; `test_doc_contract.py` passes; `rg -n 'autopilot review-once' skills/run-autopilot/SKILL.md` prints one line.

## Success Criteria

- `pytest skills/run-autopilot` green with the nine new loop tests and the runner prompt test; zero skips added.
- From the ~/.claude checkout with `state.next_phase == "build"`, `python3 <plugin>/skills/run-autopilot/cli/__main__.py review-once` exits 1 without a `claude` process appearing; with `next_phase == "review"` it spawns exactly one `claude -p … /autopilot:run-autopilot` and exits after that process ends.
- Takes effect only after a plugin release and cache install (memory: plugin PRDs are inert until installed); until then `dev/local/tmp/00140-run-review.py` stays the fallback and the ~/.claude PRD 00150 shell repoint is what makes `autopilot review-once` typeable.
