# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **use-codex**: `codex_hook_doctor.py check` validates every target registered
  in `~/.codex/hooks.json` against the canonical plugin sources that own it,
  reporting `ok`/`stale`/`no_canonical`/`missing`/`empty`/`syntax_error` per
  target with a summary line and an exit code a batch probe can branch on.
- **use-codex**: `codex_hook_doctor.py repair [--dry-run]` restores
  missing/empty/stale known hooks from their canonical source and removes
  orphaned zero-byte placeholders. Operator-only — the unattended write fence
  denies writes under `~/.codex`, so a batch never runs it.
- **run-autopilot**: the codex probe line in the Implementor Mix batch-report
  section appends `; hooks: <hook_doctor>` whenever the doctor-first batch
  probe recorded a stale hook copy or its own failure summary.
- **work**: a per-dispatch timing ledger at
  `dev/local/autopilot/dispatch-metrics.jsonl`, mirrored into the GC-exempt
  `ledger/` copy the way `loop-metrics.jsonl` is. `record_dispatch.py` writes
  it: `start` opens a row (queued time, prompt bytes, an id), `end` closes it
  with the elapsed seconds and an outcome (`ok`, `timeout`, `killed`, `error`,
  `lost`), and `handoff` stamps one edge of a session handoff. Every write is
  best-effort: an unresolvable autopilot dir, an unwritable file or an id with
  no start row exits 0, so telemetry never blocks a dispatch or a phase
  transition.

### Changed

- **plan-tasks**: opus is assigned per task on a public-contract edit or
  concrete algorithmic risk, PRD-wide keywords, file count and token count no
  longer promote, test ports and packaging pin to Sonnet, and every task
  records `tier_reason`. The classifier CLI rejects a negative `--lines`
  rather than letting it satisfy the cheap tier's size bound, and the
  unknown-`default_model` warning is emitted by the CLI so the classifier
  core stays free of side effects.
- **work**: the codex batch health probe runs the hook doctor first. A broken
  hook (`codex_hook_doctor.py check` exits 1 or 2) marks the probe
  `unhealthy` and skips the live probe for the rest of the batch with no
  escalation stamp; a stale-only result (exit 3) still runs the live probe
  and records `hook_doctor: "stale: <basenames>"` alongside it.

### Fixed

- **use-codex**: `codex_hook_doctor.py check` no longer writes bytecode beside
  the hooks it inspects, so the verb is read-only as documented and a batch
  cannot mutate `~/.codex` just by probing it.
- **use-codex**: a registered hook that has drifted from its canonical source
  *and* stopped compiling now reports `syntax_error` (exit 1, codex gated off)
  instead of `stale` (exit 3, codex left on). A hook that cannot compile fails
  on every tool call, so the harmful state must win the verdict.
- **use-codex**: a `syntax_error` detail is collapsed to a single line, so each
  record stays one TSV line and the batch probe's "first broken line" parsing
  cannot read a truncated record.
- **use-codex**: a `hooks.json` whose command cannot be tokenized, or whose
  event entry is not a mapping, exits 2 with the doctor's own `error:` line
  instead of an unhandled traceback.
- **use-codex**: `codex_hook_doctor.py repair` no longer aborts the whole run
  when a known target's canonical source is itself absent. That one target is
  reported `unrepairable` and the remaining targets are still repaired, with
  the exit code staying the recomputed check code instead of collapsing to 2.
- **use-codex**: a hook file whose bytes are not valid UTF-8 no longer aborts
  `check` or `repair`. It verdicts `syntax_error` like any other file that
  cannot be compiled, and the sibling scan behind `_common.py` repair skips it
  and carries on rather than failing the run.
- **use-codex**: `codex_hook_doctor.py repair` no longer deletes a registered
  hook whose command spells its path indirectly (`hooks/../hooks/custom.py`).
  Target paths are now normalized lexically, so the registered set and the
  placeholder scan agree on the same file.
- **use-codex**: an unregistered zero-byte file whose basename matches a known
  hook is now removed as the placeholder it is, instead of being rewritten from
  the canonical source. The cleanup exemption covers registered targets plus
  `_common.py`, not every known basename.
- **run-autopilot**: the batch report's `; hooks:` note no longer leaks onto a
  probe left over from an earlier batch. A mismatched-batch probe renders
  exactly `codex probe: not run`, so a stale note cannot be read as describing
  the current batch.
- **use-codex**: `codex_hook_doctor.py repair` now reports a known target whose
  canonical source cannot be found as `unrepairable` instead of omitting it
  from the output entirely, so a repair run accounts for every target it
  considered.
- **work**: the doctor-first probe's exit-1 and exit-2 mappings are now stated
  separately. Exit 2 means the config itself is unusable, so the doctor emits no
  TSV or summary line and the probe records the stderr error line with
  `hook_doctor: "config unreadable: <path>"`. The previous merged wording asked
  for a "first broken TSV line" that cannot exist on that path.

## [0.3.0] - 2026-09-01

### Added

- **work**: the final verification step now runs the checks the review queued
  for it. A doubt-lens finding that "needs a specific named check to resolve"
  used to become a rework task whose work pass ran the whole suite again to
  answer it; the check now runs beside the suite that was about to be
  duplicated, and the phase report carries one `verify_check: <command> -> exit
  <n>` line per check. A non-zero exit is evidence, not a phase failure - it
  reaches the next review cycle as an open finding. A queued command is checked
  before it runs (a single test, lint, build or project check; no chaining,
  redirection or state change) and one that fails the check is refused and
  reported rather than executed - the command text is composed by a reviewer
  from the diff and the PRD, so it is untrusted input. With no queue file
  present, which is every first-pass build, nothing runs and nothing is
  reported.
- **work**: the final verification step records what it ran to
  `dev/local/autopilot/last-verification.json` - the HEAD sha, each command and
  its exit code, and the pass/fail/skip counts. A suite whose output carries no
  parseable counts records `null` for all three, and a phase that ran no suite
  writes an empty command list; either way the reader runs the suite itself
  rather than reporting counts nobody measured.
- **work**: explicit timeout budgets for foreground verification commands and a
  rule against combining inspection with verification. Inspection calls get
  60000 ms, lint and narrow tests 300000 ms, a foreground full suite 600000 ms;
  a fired budget buys one re-run at the next larger one (the full suite has
  none, so its first timeout is terminal), then names the command and its budget
  in the phase report. A command that timed out while a task was in flight also
  stamps `verification: "timeout:<command>"` on that task's attempt.
  Backgrounded full suites keep their 20-minute `Monitor` wait.
- **work**: a mechanical split-hygiene check on test files a task touched. It
  parses with `ast` and reports bindings only - a module-level name nothing in
  the file reads, and a local reassigned before its previous value is read -
  never an assertion, test function, fixture or parametrization. The de-slop
  pass still may not modify tests; this answers the mechanical half of that
  question instead of asking an agent to judge it.
- **work**: a style-limit fix may now create the sibling modules a split needs.
  That one dispatch is handed the violating files plus their parent directories
  and told it may add modules there; every other implementor dispatch keeps the
  task's Contract paths unchanged. Before, a fixer asked to split an 800-line
  file could only report a blocker, because the file it had to create was in no
  allowlist.
- **work**: a task whose committed diff touches only test and fixture paths now
  skips both the self-deslop pass and the per-task review, stamping the attempt
  `self_deslop: "skipped:test-only"` and `review: "skipped:test-only"`. A rework
  task keeps its reviewer, and any production path in the diff runs the full
  pipeline unchanged.
- **work**: the per-task reviewer now judges the prompt and nothing else. It is
  dispatched with no tools and reads the step-5.5 test result from the prompt
  instead of re-running the suite, and its severities carry a fixed meaning:
  MEDIUM is a correctness or security defect the diff's own tests miss, while
  style, naming, duplication, structure, maintainability and every
  behavior-preserving simplification are LOW. A LOW is carried to the PRD-level
  review rather than costing an implementor retry.
- **work**: a per-task review reply that breaks the reporting contract now costs
  one correction retry instead of passing as an empty review. A second bad reply
  records `review: "failed:invalid_output"` and the task proceeds; the PRD-level
  review is what catches whatever the reviewer missed.
- **use-sonnet**: `-t, --tools LIST` passes `--tools=LIST` to `claude` in prompt
  mode. `-t ""` grants no tools at all, which is how a reviewer gets pinned to
  the prompt it was given. The value is joined to the flag on purpose: `--tools`
  is variadic, so passing it as a separate argument swallows the prompt and the
  run dies with "Input must be provided". Without the flag the argv is
  unchanged, and a bare `-t` is a usage error rather than a silent grant.
- **use-sonnet**: `-S, --session-id UUID` fixes the id of a headless run and
  `-R, --resume-print ID` resumes that conversation, both in `--print` mode, so
  a second dispatch can carry only what changed instead of the whole diff again.
  The interactive `-r` is untouched and cannot be combined with `-R`; without
  either new flag the argv is unchanged, and a bare `-S` or `-R` is a usage
  error rather than a silently fresh session.

### Changed

- **review-work-completion**: a Medium or Low doubt-lens finding that names an
  exact check to run is now queued for the work phase instead of becoming a
  rework task, and follow-up task creation skips it. The queue is a per-cycle
  JSON file beside the review files. A CRITICAL or HIGH is never routed - it
  keeps its task and still blocks convergence - and a VERIFY item that names no
  exact command is not queued and is classified exactly as before. A queued
  check that comes back non-zero is read from the previous cycle's queue and
  becomes an ordinary finding, so a red check cannot be converged over.
- **review-work-completion**: the review's `Tests:` line is composed from the
  work phase's recorded verification run when that record's sha matches the
  reviewed HEAD and its counts parsed, instead of running the same suite a
  second time. The line says which path produced it - reused record or a suite
  run this cycle - so a reused count can never read as a fresh one. Any
  mismatch, missing record or unparsed count runs the suite in the foreground
  as before.
- **work**: the style-limit gate now runs at the end of each task against that
  task's own diff (step 5.65), instead of once per phase over everything every
  task committed. A file is split while the context that produced it is still in
  session, the per-task reviewer reads an already-conforming diff, and each
  attempt carries its own `style_gate:` value. `haiku` tasks skip it
  (`style_gate: skipped:tier`); the phase-end gate is gone, and the phase report
  lists one value per task.
- **work**: a per-task review re-run now carries only the delta. The first
  dispatch of a task fixes a reviewer session id; every later cycle resumes that
  conversation with the prior findings and `git diff <last reviewed>..HEAD`
  instead of the whole task diff again. A resume that fails falls back to one
  full-diff dispatch and says so in the report (`review: resume_failed`), so the
  review is never skipped.

### Fixed

- **work**: the style-limit gate no longer reports clean over uncommitted or
  unmatched Python files. It appends a whole-file add block for every untracked
  `.py` file to the diff it measures, so a new module's oversized functions
  are flagged before the review sees them, and a candidate the gate cannot find
  in the diff is recorded as not inspected (exit 2, `style_gate:
  failed:<stderr>`) instead of certifying a file it never opened. A block that
  changes no content - a pure rename, a mode-only change, an empty new file -
  reads as inspected and clean rather than forcing that exit 2.
- **docs**: the review pack step no longer tells you to run `engram` out of one
  machine's checkout path. It shows the plain `engram pack` command and says
  `engram` is optional, with the `uv run --project <your engram checkout>` form
  for when it is not on PATH.

## [0.2.2] - 2026-08-27

### Changed

- **hooks**: writing one of the named keepers (`project-capsule.md`,
  `decisions.md`, `troubleshooting.md`, `assumptions.md`, `agoge-profile.md`,
  `ecc-cursor`, `upstream-cursor`) directly at a `dev/local` root is now
  blocked and routed to `dev/local/meta/<name>`. The root is directories-only;
  the compat-symlink allowance it replaced existed only until agoge, git-ferry
  and aegis shipped meta-first paths, which they now have. A non-keeper stray
  at root is unaffected and is still routed to `dev/local/tmp/<name>`.

## [0.2.1] - 2026-08-27

### Fixed

- **docs**: references, skill bodies and the tracon dashboard now name the
  namespaced skills (`/autopilot:run-autopilot`, `/autopilot:work`, …), so an
  operator or session that types what a runbook shows gets a command that
  resolves.

## [0.2.0] - 2026-08-27

### Added

- **run-autopilot**: `autopilot review-once` runs exactly one headless
  review or finalize session for `state.next_phase` (refusing a build phase
  before spawning) and exits, replacing the throwaway `dev/local/tmp` review
  drivers.
- **run-autopilot**: `autopilot render report` exits 12 and names every
  pending deferred item its rendered section does not contain, so a deferral
  that never reaches the report stops the finalize step instead of passing
  silently.
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
- **work**: rework tasks with at most two findings in at most two files (none
  CRITICAL) are edited by the orchestrator instead of dispatching Ivan,
  reverting to the normal lane when the diff overruns; step 5 stamps `reflow:`
  on any staged file whose diff exceeds the hunk threshold so a formatter sweep
  is visible instead of silently re-reviewed.
- **review-work-completion**: step 3 skips `engram pack` when
  `git rev-parse --show-toplevel` fails and records
  `pack: skipped (no git worktree)` instead of a failure line.

### Fixed

- **run-autopilot**: loop sessions launch `/autopilot:run-autopilot`, the
  plugin-namespaced skill, instead of the bare `/run-autopilot` that stopped
  resolving at the plugin extraction; the operator runbook lines say the same.
- **work**: qwen dispatch reaches its helper again. `qwen-integration.md` named
  `~/.agents/skills/use-qwen/`, but `use-qwen` was a Claude-only skill under
  `~/.claude/skills/` that braid never composed into the shared union, so the
  path resolved to nothing and every qwen dispatch quietly fell back to Claude -
  at token cost, for work meant to run locally and free. Fixed by publishing
  `use-qwen` to buvis/agent-skills, which puts it in the union the documented
  path already pointed at; this file is unchanged.
- **run-autopilot**: a PRD that capped out no longer loses its open findings
  from the batch report: the Deferred to Batch End table renders the union of
  `state.deferred_decisions` and the batch deferred JSON, deduplicated, with a
  Reason cell for every cap-overflow row.
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
- The pack no longer ships Serena project metadata. `work/`, `review-blindly/`
  and `review-work-completion/` each carried a `.serena/` directory (505 lines
  of another tool's per-machine config) into the installed plugin.

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
