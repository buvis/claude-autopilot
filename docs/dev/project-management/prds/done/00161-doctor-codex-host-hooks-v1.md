---
catchup: skip
design: skip
---

# Doctor the Codex host hooks

Source: `dev/local/discovery/00157-autopilot-efficiency-policies.md`, PRD 3 of 3 (must-haves 14-16, Q9-Q10, the inferred ownership finding). Independent of PRDs 00159 and 00160; sequenced last because host-hook repair has a different ownership and deployment boundary.

## Overview

### Problem Statement

`~/.codex/hooks.json` registers ten command targets under `~/.codex/hooks/`. The config and nine of the ten copies are untracked (the dotfiles bare repo tracks only `.codex/hooks/notify.py`, a symlink); their sources are split across the aegis plugin, this plugin, the legacy `buvis/home` clone and one local-only hook (`design-quality-check.py`). Verified 2026-08-27: every one of the seven copies with a plugin source differs from it (copied in April, sources moved on), `track_cost.py` differs from its host source in `~/.claude/hooks/` too, and two zero-byte leftovers, `analyze-instincts.py` and `observe_tool.py` (2026-08-26), sit beside them after a hook-churn episode in which missing targets were silenced with empty files instead of repaired. Nothing validates a target before a codex dispatch; a missing or empty target fails on every tool call, and a codex run that hits a failing hook retries until it burns out (`work/references/codex-implementor.md` § Hook interaction). Codex's `[hooks.state]` trust table in `~/.codex/config.toml` also still lists entries for registrations that no longer exist (`post_tool_use:1..4`, `stop:2..4`); it is Codex-owned and out of scope here.

### Target Users

The operator, who owns `~/.codex` and runs the repair; the `/autopilot:work` batch probe, which must know before the first codex dispatch whether the host's hooks are usable.

### Success Metrics

- A plugin-owned doctor validates every registered target and repairs the known ones from their canonical plugin sources; its regression tests catch a missing, empty, non-compiling or stale target against fixtures.
- `/autopilot:work`'s batch probe runs the doctor in check mode once per batch before any codex dispatch; a broken result records an `unhealthy` probe whose `detail` names the target, and the rung falls back to Claude for the batch with the reason in the batch report. Nothing in a batch ever writes to `~/.codex`.
- Post-release signal (operator step, outside any batch): `codex_hook_doctor.py check` on this host exits 1 before repair and 0 after `codex_hook_doctor.py repair`, no zero-byte file remains in `~/.codex/hooks/`, and the next batch report's probe line reads `codex probe: healthy (backend: codex)` with no `hooks:` note.

## Functional Decomposition

### Capability: Hook doctor
One stdlib script with two verbs.

#### Feature: Check
- **Description**: `codex_hook_doctor.py check [--config PATH] [--aegis-root PATH] [--autopilot-root PATH]` validates every registered target.
- **Inputs**: the config (default `$CODEX_HOME/hooks.json`, else `~/.codex/hooks.json`); the hooks directory is `<config dir>/hooks`; the aegis root defaults to the `installPath` of the first `aegis@buvis-plugins` entry in `~/.claude/plugins/installed_plugins.json`; the autopilot root defaults to `Path(__file__).resolve().parents[3]`.
- **Outputs**: one TSV line per target, `<verdict>\t<target>\t<detail>`, verdicts `ok`, `stale`, `no_canonical`, `missing`, `empty`, `syntax_error`; a final `summary\t<n> ok, <n> stale, <n> broken`. Exit 0 all ok; 3 no broken target but at least one `stale` or `no_canonical`; 1 any `missing`, `empty` or `syntax_error`; 2 config unreadable, not JSON, or without a `hooks` object.
- **Behavior**: For every `command` under every event block, the target is the last `shlex.split` token, resolved against the config directory when relative. `missing`: no file. `empty`: zero bytes. `syntax_error`: `py_compile` fails (detail carries the message). `stale`: a known hook whose bytes differ from its canonical source. `no_canonical`: a known hook whose canonical root cannot be found. Unknown targets (host-owned) get only the three broken checks. `_common.py` is checked like a target although it is a sibling import, because every known hook imports it. Read-only: never writes anything.

#### Feature: Known-hook table
- **Description**: The map from a target basename to its canonical plugin source.
- **Inputs**: the two roots.
- **Outputs**: the table below, verbatim in the script.
- **Behavior**: `validate_commit_msg.py`, `protect_config.py`, `block_devlocal_redirects.py`, `_common.py` → `<aegis>/hooks/<same name>`; `block-suppression-markers.py` → `<aegis>/hooks/block_suppression_markers.py`; `gateguard-fact-force.py` → `<aegis>/hooks/gateguard_fact_force.py`; `enforce_prd_location.py` → `<autopilot>/hooks/enforce_prd_location.py`. Host-owned, validated but never repaired: `notify.py` (a symlink into `~/.claude/hooks/`), `track_cost.py`, `design-quality-check.py`, and any target not in the table. `_common.py`'s canonical is aegis's: every `from _common import` in `~/.codex/hooks/*.py` names only `allow`, `block` and `read_input` (verified 2026-08-27), all of which aegis's module defines; repair re-checks this (below).

#### Feature: Repair
- **Description**: `codex_hook_doctor.py repair [--dry-run] [same options]` rewrites known targets from canonical sources and removes unregistered zero-byte placeholders.
- **Inputs**: the check verdicts; the hooks directory listing.
- **Outputs**: TSV lines `repaired\t<target>\t<source>`, `removed\t<path>`, `unrepairable\t<target>\t<why>`, `skipped\t<target>\tsymlink`; with `--dry-run` the verbs are `would-repair` and `would-remove` and nothing changes. Exit code: the check exit code re-computed after the changes.
- **Behavior**: A known target that is `missing`, `empty` or `stale` is rewritten with the canonical bytes (temp file in the same directory, then `os.replace`), except a symlinked target, which is never written through. Before rewriting `_common.py` the doctor scans every sibling `*.py` for `from _common import` names and refuses (`unrepairable`, names listed) when the canonical module lacks a top-level `def` for any of them. A broken unknown target is `unrepairable`. Then placeholders: the config is re-read at that moment, and every zero-byte `*.py` directly in the hooks directory that no registered command names is deleted; a registered zero-byte file is `empty`, never deleted. The doctor never edits `hooks.json`, never touches `config.toml`, and never enters `hooks/tests/` (the test copies there, `test_autopilot_stop_hook.py` included, are out of scope). Premise, re-checked by this scan at every run: `analyze-instincts.py` and `observe_tool.py` are zero-byte and unregistered; either one growing content or a registration means it is kept and reported, never removed.

### Capability: Batch integration
Check once per batch, before codex; record, never guess.

#### Feature: Doctor-first batch probe
- **Description**: `work/references/codex-implementor.md` § Codex batch health probe runs the doctor before the live probe.
- **Inputs**: the doctor's exit code and summary line.
- **Outputs**: the `state.codex_probe` slice, with a new optional key `hook_doctor`.
- **Behavior**: Under the existing batch-scope check, the probe first runs `python3 ${CLAUDE_PLUGIN_ROOT}/skills/use-codex/scripts/codex_hook_doctor.py check` (foreground Bash: a local file scan, no dispatch). Exit 1 or 2: write `verdict: "unhealthy"`, `detail: "hook_doctor: <the first broken TSV line>"`, `hook_doctor: "<summary line>"`, `backend` as resolved by `command -v codex`, and skip the live probe (no codex dispatch this batch, infra semantics, no escalation stamp). Exit 0 or 3: run the live probe unchanged and add `hook_doctor: "ok"` or `hook_doctor: "stale: <basenames>"` to the slice. Stale copies do not gate the rung `(guess)` - they have run every batch so far; flip to gating if a drifted copy ever misbehaves. A batch never runs `repair`: the unattended write fence denies `~/.codex`, and repair is the operator's explicit command.

#### Feature: Report line
- **Description**: The batch report's probe line shows the doctor's note.
- **Inputs**: `state.codex_probe.hook_doctor`.
- **Outputs**: `codex probe: healthy (backend: codex); hooks: stale: _common.py` when the key is present and not `"ok"`; today's line otherwise.
- **Behavior**: `cli/render_report.py` appends `; hooks: <value>` to whichever probe line it renders; an absent key or `"ok"` renders exactly today's text, so the golden render stays byte-identical.

## Structural Decomposition

### Repository Structure

```
skills/use-codex/
├── SKILL.md                              # Maps to: Hook doctor (## Hook doctor section)
└── scripts/
    ├── codex_hook_doctor.py              # Maps to: Check, Known-hook table, Repair
    └── test_codex_hook_doctor.py         # Maps to: Hook doctor (tests) + prose pins
skills/work/references/codex-implementor.md            # Maps to: Doctor-first batch probe
skills/run-autopilot/
├── cli/render_report.py                  # Maps to: Report line
├── cli/test_render.py                    # Maps to: Report line (tests)
└── references/
    ├── state-schema.md                   # Maps to: codex_probe.hook_doctor
    └── batch-report-format.md            # Maps to: Report line
CHANGELOG.md
```

### Module: hook-doctor
- **Maps to capability**: Hook doctor
- **Responsibility**: the two verbs, the table, the safety checks; stdlib only; locates the autopilot root from `__file__`, never from an install path.
- **Exports**: CLI `codex_hook_doctor.py check|repair`; `check(config, aegis_root, autopilot_root) -> list[tuple[str, str, str]]`; `repair(...)`; `KNOWN_HOOKS` (the table)

### Module: batch-probe-prose
- **Maps to capability**: Batch integration
- **Responsibility**: the doctor-first paragraph in `codex-implementor.md`; the `## Hook doctor` section in `use-codex/SKILL.md` (both commands, exit codes, the operator-only rule for repair); the `codex_probe` row and the report-format clause.
- **Exports**: none (prose)

### Module: report-render
- **Maps to capability**: Batch integration
- **Responsibility**: the `; hooks:` suffix and its test.
- **Exports**: none new (`render_report.py` internal)

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **hook-doctor (check)**: the verdicts and the table.
- **report-render**: independent of the script.

### Core Layer (Phase 1)
- **hook-doctor (repair)**: Depends on [hook-doctor (check)].

### Integration Layer (Phase 2)
- **batch-probe-prose**: Depends on [hook-doctor (check), hook-doctor (repair), report-render].

## Implementation Phases

### Phase 0: Foundation
**Goal**: Check mode and the report suffix exist and are tested against fixtures.

**Tasks**:
- [ ] Add `skills/use-codex/scripts/codex_hook_doctor.py` with `check`, `KNOWN_HOOKS` and the option defaults, plus `test_codex_hook_doctor.py` (pytest, `tmp_path`: a fake config dir with `hooks.json` and `hooks/`, a fake aegis root and a fake autopilot root passed explicitly, never the real ones): all targets equal to canonical → exit 0 and every line `ok`; a target absent → `missing`, exit 1; a registered zero-byte target → `empty`, exit 1; a target with `def (:` → `syntax_error`, exit 1; a known target whose bytes differ → `stale`, exit 3; an unknown non-empty target → `ok`; a quoted command path (`python3 '<path>'`) resolves; malformed JSON → exit 2; a config without `hooks` → exit 2; `_common.py` present only as a sibling is still checked (no deps) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/use-codex/scripts/test_codex_hook_doctor.py` green; `python3 skills/use-codex/scripts/codex_hook_doctor.py check --config /nonexistent/hooks.json` exits 2.
- [ ] Append `; hooks: <hook_doctor>` to the codex probe line in `skills/run-autopilot/cli/render_report.py` when `codex_probe.hook_doctor` is present and not `"ok"`, with two cases in `cli/test_render.py`: `hook_doctor: "stale: _common.py"` renders the suffix on a healthy line; a slice without the key renders today's exact line (no deps) - Acceptance: `uv run --no-project --with pytest --with rich --with textual python -m pytest -q skills/run-autopilot/cli/test_render.py skills/run-autopilot/scripts/test_golden_contracts.py` green.

**Exit Criteria**: Both suites green; the doctor's default paths are never read by any test.

### Phase 1: Core
**Goal**: Repair mode restores known targets and removes placeholders safely.

**Tasks**:
- [ ] Add `repair` and `--dry-run` to `codex_hook_doctor.py` with tests: a stale known target's bytes equal canonical after repair and the line reads `repaired`; an empty known target likewise; an unregistered zero-byte `stray.py` is `removed`; a registered zero-byte unknown target is kept and `unrepairable`, exit 1; a symlinked known target is `skipped ... symlink` and its link target's bytes are untouched; `_common.py` is refused when a sibling imports a name the canonical module lacks; `hooks.json` bytes are identical before and after; a `tests/` subdirectory is untouched; `--dry-run` prints `would-` lines and changes no file (depends on: Phase 0) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/use-codex/scripts/test_codex_hook_doctor.py` green; `rg -n "hooks.json" skills/use-codex/scripts/codex_hook_doctor.py` shows no write call on the config.

**Exit Criteria**: Repair suite green; `codex_hook_doctor.py repair --dry-run --config <fixture>` on a broken fixture exits 1 and leaves it broken.

### Phase 2: Integration
**Goal**: The batch probe uses the doctor, and every consumer document says so.

**Tasks**:
- [ ] Add the doctor-first paragraph to `skills/work/references/codex-implementor.md` § Codex batch health probe (ahead of the `codex-run.sh -a` block: the command, the exit-code mapping to `verdict`/`detail`/`hook_doctor`, "never `repair` from a batch"); add `## Hook doctor` to `skills/use-codex/SKILL.md` (both commands, exit codes 0/1/2/3, the operator-only repair rule); document `hook_doctor?` and the `detail` shape in the `codex_probe` row of `skills/run-autopilot/references/state-schema.md` and the `; hooks:` suffix in `references/batch-report-format.md`; add prose pins to `test_codex_hook_doctor.py` (`codex-implementor.md` names `codex_hook_doctor.py` before its first `codex-run.sh -a`; `state-schema.md` names `hook_doctor`; `use-codex/SKILL.md` names `repair`); add the CHANGELOG lines (feat commits: `**use-codex**` under Added for the doctor; `**work**` under Changed for the doctor-first probe; `**run-autopilot**` under Added for the `hooks:` note) (depends on: Phase 1) - Acceptance: `rg -n "codex_hook_doctor.py" skills/work/references/codex-implementor.md skills/use-codex/SKILL.md` hits in both; `rg -n "hook_doctor" skills/run-autopilot/references/state-schema.md skills/run-autopilot/references/batch-report-format.md` hits in both; `rg -n "^- \*\*(use-codex|work|run-autopilot)\*\*" CHANGELOG.md` hits under `[Unreleased]`; `uv run --no-project --with pytest --with rich --with textual python -m pytest -q skills/use-codex/scripts skills/work/scripts skills/run-autopilot` green.

**Exit Criteria**: Full suite green; `bash dev/bin/release-checks` green (`test_codex_run.sh` untouched). Operator step after release, outside any batch: `check`, `repair`, `check` exits 0.

## Test Strategy

### Critical Scenarios
- **Happy path**: fixture hooks equal to canonical → `check` exits 0; the probe runs the live codex probe and stamps `hook_doctor: "ok"`; the report line is unchanged.
- **Edge case**: seven stale copies (today's host state, reproduced in a fixture) → `check` exits 3, the rung stays on, the report reads `; hooks: stale: ...`; `repair` rewrites all seven and `check` exits 0.
- **Edge case**: `_common.py` canonical lacks a name a sibling imports → `repair` refuses that one file and repairs the rest.
- **Error case**: a registered target is zero bytes → `check` exits 1; the probe writes `unhealthy` with `detail: "hook_doctor: empty\t..."`, no codex dispatch, the batch continues on Claude, the report says so.
- **Error case**: `hooks.json` is not JSON → exit 2, same fallback, the detail names the config.

## Risks

- **Host-config ownership drift**: the doctor repairs only what a plugin canonically owns and reports the rest; `notify.py`, `track_cost.py` and `design-quality-check.py` stay the operator's, and the PRD records which is which.
- **A repair silently breaks a hook's import**: the `_common.py` import scan refuses the rewrite when a name would go missing; `py_compile` runs on every target after repair.
- **Codex re-prompting for trust after a rewrite**: `[hooks.state]` keys carry a `trusted_hash` per registration, and two entries with the same command share one hash, so the hash keys on the registration rather than the file bytes; the first codex run after repair is the confirming signal, listed above.
- **Repair run inside a batch**: prohibited in prose and denied by the unattended write fence; the batch only ever runs `check`.
