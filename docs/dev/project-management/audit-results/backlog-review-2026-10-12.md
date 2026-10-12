# Backlog review - claude-autopilot - 2026-10-12

Verdict: GO (walkthrough complete 2026-10-12; every Blocking finding resolved by an applied
edit or reshape, every Question decided; lens A re-run green on all seven remaining PRDs;
`ground_prd.py` reports 0 unresolved or missing rows for `backlog/`; the one `check_links` hit
left is the fixture-16 symlink target `docs/dev/project-management/settings.json` in 00276,
which the symlink test itself creates).

Initial verdict before the walkthrough: NO-GO (8 Blocking open).

Grounded at `bcba9e6` (HEAD at review time; tree clean; no live loop, `pgrep -fl "autopilot loop"` empty).
Law: `~/.agents/skills/create-prd` SKILL.md + `assets/standard.md` as of today.
Budget/tier rules: `autopilot:plan-tasks` steps 4.5-4.7 (read from this checkout, the pack's source).
Mechanical checks: `check_links.py` and `ground_prd.py` both ran (exit 1 each); rows filtered to
`prds/backlog/` and `prds/wip/`. Measured facts carry "(measured)"; everything else is read from code.

Context: 00271 is in `wip/` and drains first. Batches in this repo execute the installed plugin
cache, so none of these PRDs can harm the loop that builds them (memory
`project-batch-runs-installed-cache`); nothing lands until `dev/bin/release` + `/plugin update`.

## Map

| # | PRD | template | lines | subsystems | depends on | verdict |
|---|-----|----------|-------|------------|------------|---------|
| 00276 | make-the-gate-record-trustworthy | standard | 190 -> 192 | cli/verification, cli verify verb, work/references, CHANGELOG | none (00270 done) | READY (was FIX) |
| 00277 | catch-critical-rows-in-every-shape | standard | 139 -> 146 | cli/gate, cli refusal line, review-work-completion references | none (00269 done) | READY (was FIX) |
| 00278 | make-release-checks-tell-truth | standard | 152 -> 204 | dev/bin/release, dev/bin/release-checks, hooks tests, work/SKILL.md, run-autopilot SKILL.md, gate.py comment, CHANGELOG | 00271 drained (it is wip, so yes) | READY (was FIX; absorbed 00280) |
| 00279 | run-one-exact-reuse-rule | standard | 121 -> 133 | cli/verification, review-work-completion SKILL, work/references, release-checks, CHANGELOG | 00276 (same module, disjoint functions), 00278 (release-checks shape) | READY (was FIX) |
| 00280 | state-python-floor-and-sweep-ceiling | standard | 92 | run-autopilot SKILL.md, CHANGELOG, one gate.py comment | none | MERGED into 00278; original in `hold/` |
| 00282 | loop-guards | standard | 183 -> 184 | cli loop, loop_decision, loop_act, records, enter, __main__, brief, watchdog, runner; references | none | READY (was FIX) |
| 00283 | loop-catchup | standard | 147 -> 149 | cli loop, enter, enter_io, catchup_probe (new), __main__; references; release-checks | 00278 (test-file pin) | READY (was FIX) |
| 00284 | loop-launch-context | standard | 146 -> 148 | cli runner, brief, statectl, schema; live launch test (new); release-checks | 00278 (test-file pin) | READY (was FIX) |

00278 sits at 204 lines after the merge, four over the ~200 soft split line; it stays one PRD:
one subsystem (the release gate and its prose), two phases, nine tasks each touching a few small
files, so no task approaches the 150K budget.

Hygiene: only `NNNNN-slug-v1.md` files plus `.migration-placeholder` (1 byte, Sep 28) in
`backlog/`; `cli/selection.py` keeps only `.md` names with a `00XXX-` prefix, so the placeholder is
ignored (verified, not a finding). Sequence numbers unique across backlog/wip/done/hold/discovery
(00264 has v1 and v2 in done/, a versioned pair, allowed). Every task line carries `Acceptance:`;
`#### Feature:` headings unique in every PRD; frontmatter fields all recognized and valid (no
comment on any `default_model:` line); no `{...}`, TBD, `(guess)` or human-in-the-loop phrase in
`backlog/` (`rg` sweep, empty, control: the same sweep finds `(guess:` in `wip/00271`).

## Findings

### Blocking

- [00282, 00283, 00284] Executability: every acceptance and exit criterion runs `uv run pytest ...`.
  In this repo a bare `uv run pytest --version` fails with `ModuleNotFoundError: No module named
  '_pytest'` (measured): there is no pyproject, so pytest is only reachable as
  `uv run --no-project --with pytest python -m pytest` (the form `dev/bin/release-checks` uses).
  The final exit criterion `uv run pytest skills/run-autopilot` is green cannot hold either:
  collecting that tree stops with 3 errors, `skills/run-autopilot/scripts/tracon/test_{panels,screens,stream}.py`
  import `rich`, which is not installed (measured at bcba9e6, 3487 collected, 3 errors).
  -> fails as: rework thrash (every criterion red whatever the implementor does), then stall at the
  rework cap. Fix: replace `uv run pytest` with `uv run --no-project --with pytest python -m pytest -q`
  throughout; replace the three final exit criteria and the last success-metric line with
  `bash dev/bin/release-checks` exits 0 with `FAIL 0` on its summary line (create-prd gate rule).
- [00278] Coherence: "Gate every tracked test" says a test fails when `git ls-files '*test_*.py'`
  names a file the script does not run; "Committed fixtures in the gate" says the new
  `hooks/test_guard_phase_delegation_scratch_replay.py` "is not run by release-checks". Both cannot
  hold without an exclusion the PRD never states. Also unstated: `release-checks` is a list of
  explicit `echo "[checks] <name>"` blocks with literal file paths, and six prose tests parse those
  exact lines (`test_release_checks_parallel_prose.py`, `test_wave_docs.py`, `test_triage_prose.py`,
  `test_enter_prose.py`, `test_design_rework_prose.py`, `test_custody_prose.py`; the script's own
  header says so), so a rewrite into a `git ls-files` loop reds them. The counts are stale too:
  254 tracked `test_*.py` today, not 262 (measured), and 262 - 133 is 129, not 113.
  -> fails as: wrong-TDD lock-in (the planner invents the exclusion rule and the script shape).
  Fix: state the contract - keep every existing `[checks]` block and its paths; add the ungated
  files to new or existing blocks; `test_every_tracked_test_file_is_gated` compares
  `git ls-files '*test_*.py'` at run time with the paths literally named in the script, minus an
  `UNGATED` tuple in the test that names the scratch replay file and its reason; the tracon block
  carries `--with rich`; drop the fixed counts.
- [00283, 00284] Collision with 00278: `cli/test_catchup_probe.py` (00283) and
  `cli/test_launch_mcp_live.py` (00284) are new tracked `test_*.py` files. `release-checks` names
  files explicitly (verified), so after 00278 lands, 00278's pin fails until each is registered,
  and neither PRD registers it; 00279 does (`test_tests_line_source_prose.py`).
  -> fails as: rework thrash (`release-checks` red at the PRD's own exit criterion). Fix: 00283
  Phase 0 task 2 adds "register it in the `[checks] enter` block"; 00284 Phase 1 adds "register it
  in the `[checks] l3` block (it skips by default)".
- [00284] Executability: Phase 1's acceptance is `AUTOPILOT_LIVE=1 uv run pytest ...`. The
  user-global tools rule (loaded in loop sessions too) forbids env-var prefixes in Bash calls, and
  warden's `defaultDecision` is `ask`; `env ...` commands are allowed (audit log:
  `env -C /tmp/... python3 ...` -> allow). The test also spawns `claude -p` with the session's env:
  `skills/use-sonnet/scripts/sonnet-run.sh` lines 16-33 unset `_AUTOPILOT_LOOP` ("the autopilot Stop
  hook gates its signal-file write on _AUTOPILOT_LOOP, and a reviewer subprocess must never write
  that signal") and set `CLAUDE_NESTED=1`, `_CLAUDE_NOTIFY_QUIET=1`; a test that forwards the
  inherited env can write the loop's signal file mid-batch. And the assertion depends on the
  Context7 endpoint answering.
  -> fails as: unattended hang (a warden ask) or loop interference. Fix: acceptance runs
  `env AUTOPILOT_LIVE=1 uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_launch_mcp_live.py`;
  the test builds the child env as `sonnet-run.sh` does; it asserts on `mcp_servers` names only,
  never on `status`.
- [00277] Contract: Feature "Severity-content flag" reads two ways - "a severity emoji (🔴🟠🟡⚪) or
  a severity word (...) next to a pipe". The source (agoge packet 4, option 1) is "a severity emoji,
  or a severity word beside a pipe". The bullet-with-no-token shape has no pipe, so the stricter
  reading misses it. And "the 8 shapes of packet 4" are enumerated nowhere the test author sees:
  the packet names seven (bullet with no token, `[2 / 2]`, `［2/2］`, `(2/2)`, blockquote table,
  pipe-less table, HTML `<table>`); the eighth is in neither the PRD nor the report.
  -> fails as: wrong-TDD lock-in. Fix: reword the Description ("an emoji anywhere on the line, or a
  severity word with a pipe on either side"), enumerate the shapes in the task line.
- [00279] Grounding: the premise says `test_reuse_matches_a_command_spelled_with_bash_dot_slash_and_extra_spaces`
  is in `test_verification.py` and re-checks with `rg ... test_verification.py`. It is in
  `test_verification_dirty.py:302`. The re-check finds nothing, a failed premise means skip, the old
  expectation stays, and it fails once `normalize_command` changes.
  -> fails as: rework thrash. Fix: name `test_verification_dirty.py`.
- [00283] Contract: catchup-probe says "A probe timeout of 15 s counts as a failure" but names no
  verdict for it: for `gh` "any other exit gives unauthenticated", for `engram` "any other result
  gives ok", so a hung `engram` reads `ok`, the step runs, and hangs again.
  -> fails as: wrong-TDD lock-in. Fix: a timeout gives `absent` for either binary (one sentence).
- [00276, 00277, 00278, 00279, 00280] Grounding gate: 30 `unresolved` rows, all new test names plus
  `dirty_paths`, because 00278, 00279 and 00280 have no `### Module:` block at all (template
  requires one per module) and 00276/00277's blocks carry no `New symbols:` line. Two `missing`
  citations are short forms: 00277:108 `output-formats.md:101`, 00280:43 `SKILL.md:46` (both
  resolve under their full paths, verified). Eight test names lack the `test_` prefix
  (00276 `rejects_log_path_resolving_to_record`; 00277 `indented_fence_does_not_blank_rows`,
  `critical_row_in_unparsed_shape_is_malformed`, `fenced_findings_table_is_malformed`,
  `fenced_example_rows_without_header_still_pass`, `refusal_line_stays_single_line_with_control_chars`;
  00279 `sh_and_bash_records_do_not_cross_reuse`, `dot_slash_and_bare_records_do_not_cross_reuse`),
  so pytest would not collect them as written.
  -> fails as: stall on a dangling citation / wrong-TDD lock-in. Fix: add Module blocks with
  `New symbols:` lines, full citation paths, `test_` prefixes.

### Non-blocking

- [00278] Grounding drift: "PRD 00271 (held)" - it is in `wip/` (and the shim covers both dirs, so
  the feature still works); the Placement note's "while 00271 sits in hold/" likewise;
  `skills/work/SKILL.md` is 505 lines, not 506 (still over the 500 ceiling); CHANGELOG "stays
  allowed" is line 28, not 25. Phrase-based acceptances are unaffected.
- [00279] CHANGELOG "different whitespace" is line 44, not 41.
- [00276] "hold stub 00274" / "hold stub 00275": both closed into `done/` on 2026-10-10
  (`b57e425`); the Phase 1 task says "ledger key from that stub" - inline `493345e2608e`.
- [00276] Phase 0 task 6 names no file for the symlink test; its sibling reuse tests sit in
  `test_verification_dirty.py` while the tree says `test_verification.py`. Name one.
- [00283] The premise re-check names `test_enter_decisions.py` for the existing force tests; they
  are in `test_enter.py:605-620` (`("force", None, _cache(), HEAD, "full")`). With the real
  `commits_all_loop` default on a non-git fixture that case still gives `full` (git failure ->
  False), so nothing breaks; fix the file name so the premise check reads true.
- [00276, 00277, 00278] Compliance (format only): Phases 1-2 lack `**Goal**:` lines; Feature blocks
  use Description/Behavior instead of the four template fields; Test Strategy holds verbatim
  reproductions instead of Happy/Edge/Error. The headings tooling parses are present and in order.
- [00282] Sizing: the `Loop._pre_enter` task bundles `loop.py` (630 lines), `__main__.py` (1803),
  `brief.py`, `enter.py` and four named tests; by the plan-tasks formula about 100K, under the 150K
  threshold, but the batch's likeliest split. Fine as written; the planner may split by file.
- [00282] Discovery risk "the first PRD A task confirms `total_cost_usd` is cumulative" was dropped;
  the PRD accepts the risk ("parks late, never early"). Noted, not a dropped must-have.
- [00278] Gate time: +2,323 tests on a ~220 s gate that runs every cycle. Accepted in Risks.
- [00276] Verified: `run_gate(command, cwd, ...)` takes `cwd` (the lock path's base); the default
  `verify` log is `docs/dev/tmp/gate-<sha7>.log`, outside the refused `docs/dev/project-management/`
  prefix; `check_links` flags `docs/dev/project-management/settings.json` in the fixture-16 line,
  a symlink target the test creates (forward reference, not a finding).
- [all cli PRDs] `check_style_limits.py` flags only files the diff pushed over 800 lines
  ("Pre-existing debt is" tolerated), so edits to `cli/__main__.py` (1803 lines) do not trip it.

### Questions

- [00277] What is the eighth shape? Packet 4 lists seven; the fixture set trudy used is not in the
  report or its JSON.
- [00282] Discovery F4 says a kill "routes to the existing died/retry path". The PRD routes it
  through today's decision table: `continue` when the killed session touched state, else
  no-progress -> died/retry (`loop_decision.py` has no `killed_by` branch, verified). Ratify the
  deviation, or force the died path?
- [00280] Merge into 00278 or keep (see Reshapes).

## Reshapes

- 00280 -> 00278. Two edits (two doc lines, one comment), no test surface; the `gate.py` comment
  makes the diff "production" for the lane router, so it pays the full roster. 00278 already owns
  the "Release claims are true" capability, the SKILL.md/CHANGELOG surface and the sonnet floor.
  Mechanics: add Feature "Python floor (packet 11)" under 00278's "Release claims are true" and the
  `_backed` ceiling comment as a Phase 0 task; `git mv` 00280 to `hold/` with this reason recorded
  here (never delete). Alternative: keep 00280 with `catchup: skip`.

## Gaps

- 00278's pin becomes a standing obligation: every later PRD that adds a `test_*.py` file must
  register it in `release-checks` or the gate goes red. The pin's failure message should name the
  file and the fix. 00283 and 00284 are the first two (Blocking above).
- 00278's release block reads `hold/` and `wip/`: while 00271 (which says "The next release is
  blocked on this PRD") is in either, `dev/bin/release` refuses. Intended; it clears when 00271
  reaches `done/`.
- Boot-context tokens per batch (discovery nice-to-have) have no PRD; declared deferred in 00284
  Risks and discovery 00281. F8, F10, F11, F12, F14 stay parked in discovery 00281.
- `cli/__main__.py` (1803 lines, over the 800 cap, standing debt) grows again with 00276, 00277,
  00282 and 00283. No PRD splits it; recommend `/assess-evolution` after this batch.
- Loop self-harm: none possible in this repo (installed cache executes the batch). 00282-00284
  change loop behavior only after a release.

## End state after this batch

The gate record is honest in every repo: dirt means outside both store prefixes plus hidden-flag
edits, `run_gate` is the single writer under a lock, a green-but-unrecorded run exits 3, and a
product symlink into the store makes reuse stale. The findings backstop reads rows by content, not
syntax, and refuses a real table hidden in a fence. `release-checks` runs every tracked test file
with a pin against omissions, the release shim refuses while a held or in-flight PRD blocks it, the
`Tests:` line has one rule (code), and the pack states Python 3.11. The loop parks a PRD past its
spend budget, routes 2-7 s sessions as `instant_exit`, kills a silent session from launch while
sparing open tool calls, enters in code before launch, runs delta catchup after loop-only commits,
probes `gh` and `engram` once per batch, launches with Context7 only, and prints a truthful brief
repo root. Still lacking: a release and `/plugin update` before any of it runs; a measurement of
the boot-context saving; the parked discovery leftovers; the `__main__.py` split.

## Frontmatter tuning

| PRD | suggestion | why |
|-----|------------|-----|
| 00280 | `catchup: skip` (if kept) | docs-only, no fresh context needed |
| 00284 | `design: skip` candidate | mechanism decided and checked live on 2026-10-12; contracts exact |
| 00283 | keep `design: run` | new verb and a new injectable |
| 00276, 00277, 00282 | keep `opus` | concurrency (flock, watchdog timing), trust-boundary widening |
| all | `catchup` default `run` | batch cache is warm; `force` not needed |

## Decisions applied

Walkthrough 2026-10-12, ten findings plus one LOW batch; every item applied in place with the
Edit tool (00278 rewritten whole for the merge), then lens A re-run: headings in template order on
all seven, one `Acceptance:` per task line (9/9, 6/6, 9/9, 3/3, 8/8, 4/4, 5/5), feature headings
unique, no retired string left (`uv run pytest`, `hold stub`, `(held)`, `506 to 500`, `line 41`,
`line 25`, `8 shapes` outside the verbatim reproduction block), `ground_prd.py` 0 non-ok rows on
`backlog/`.

| # | PRD | decision | status |
|---|-----|----------|--------|
| 1 | 00282, 00283, 00284 | `uv run pytest` -> `uv run --no-project --with pytest python -m pytest -q` in every criterion; final exit criteria and last success metric -> `bash dev/bin/release-checks` exits 0 with `FAIL 0` | applied |
| 2 | 00278 | gate contract stated: `[checks]` blocks kept (six parsing prose tests named), ungated files added to blocks, pin compares `git ls-files` with named paths minus an `UNGATED` tuple (scratch replay + reason), `--with rich` on tracon, fixed counts dropped | applied |
| 3 | 00283, 00284 | `test_catchup_probe.py` registered in `[checks] enter` and `test_launch_mcp_live.py` in `[checks] l3`, inside the task that creates each file; `rg` acceptance added | applied |
| 4 | 00284 | acceptance `env AUTOPILOT_LIVE=1 uv run ...`; child env scrubbed as `sonnet-run.sh` does (`_AUTOPILOT_LOOP` removed, `CLAUDE_NESTED=1`, `_CLAUDE_NOTIFY_QUIET=1`); assertion on `mcp_servers` names only | applied |
| 5 | 00277 | Description: emoji anywhere on the line, severity word with a `\|` on either side, consensus variants; seven shapes enumerated in the Success Metric and the task line | applied |
| 6 | 00279 | premise, re-check and new tests point at `test_verification_dirty.py`; Exit Criteria runs both verification test files | applied |
| 7 | 00283 | a 15 s probe timeout gives `absent` for either binary | applied |
| 8 | 00276-00279 | Module blocks added (00278 x3, 00279 x2, 00277 +1), `New symbols:` lines on every block, full citation paths, `test_` prefixes on eight names | applied |
| 9 | 00280 -> 00278 | Features "Python floor (packet 11)" and "Ceiling comment (packet 20)" under a new Capability "Stated contracts"; two Phase 0 tasks; reproductions 11 and 20; the 3.10 risk; 00280 `git mv`'d to `hold/` (reason: merged here, 2026-10-12) | applied |
| 10 | 00282 | kill routing deviation from discovery F4 ratified in the Feature text and a Risks bullet | applied |
| L1 | 00278 | 00271 "in `wip/`", 505 lines, CHANGELOG line 28, red tests 2 and 3 named by their exact files | applied |
| L2 | 00276 | closed stubs cited as `prds/done/00274` and `prds/done/00275`, ledger key `493345e2608e` inlined, symlink test placed in `test_verification_dirty.py` | applied |
| L3 | 00279, 00283 | CHANGELOG line 44; force cases cited at `test_enter.py` lines 605-620 | applied |
| L4 | 00284 | `design: skip` | applied |

Left as is: 00277's verbatim reproduction block still quotes the report's "All 8 shapes" (it is
the report's own text); 00278 at 204 lines (see Map).
