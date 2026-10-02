# Backlog review - claude-autopilot - 2026-09-21

Verdict: GO (walkthrough complete 2026-09-22; every Blocking finding resolved
by an applied edit, every Question decided, lens A re-run green on all five).

Grounded at `8885300` (0.5.5, HEAD at review time; tree clean; no live loop).
Law: `~/.agents/skills/create-prd` SKILL.md + `assets/standard.md` as of today.
Budget/tier rules: `autopilot:plan-tasks` steps 4.5-4.7 (installed plugin, read).
Citation check: `check_links.py` - every backlog hit is a runtime file the PRD
itself creates (`lanes/`, `wave.json`, `lane.json`, a worktree `state.json`);
no dangling citation.

## Map

| # | PRD | template | lines | subsystems | depends on | verdict |
|---|-----|----------|-------|------------|------------|---------|
| 00213 | hold-the-loop-session-open-while-cli-reviewer-lanes-run | standard | 267 | hooks/, use-codex, use-gemini, review-work-completion, fast-track prose | none (00211 landed) | READY (layer names fixed) |
| 00214 | plan-and-launch-a-wave-of-lanes | standard | 313 | run-autopilot cli (wave, wave_launch, wave_cli), docs | none; consumes cli/lane.named_paths, loop_gates | READY (edits applied) |
| 00215 | assemble-a-drained-wave-onto-one-branch | standard | 264 | run-autopilot cli (wave_assemble), records, docs | 00214 | READY (B3 applied) |
| 00216 | review-the-assembled-wave-and-run-a-wave-end-to-end | standard | 309 | run-autopilot cli (wave_review, wave_run), state seeding, gather-context.sh | 00214, 00215 | READY (B1, B2, Q1 applied) |
| 00217 | bound-concurrent-review-sessions-with-a-slot-semaphore | standard | 176 | run-autopilot cli (wave_slots, loop.py) | 00214 (soft: creates the block/file itself if absent) | READY (edits applied) |

All five: standard template, every heading present in order (00213 names its
layers "Layer 1/Layer 2" instead of "Core/Integration"); every task carries
`Acceptance:`; `#### Feature:` headings unique; frontmatter fields all
recognized and valid (`model_tier_rationale` is ignored by both parsers, as
documented); no `{...}`, TBD, `(guess)`, or human-in-the-loop phrase found
(`rg` sweep); Open Questions of the discovery are all decided in the PRD text.
Sequence numbers unique across backlog/wip/done/hold/discovery (00212 is the
discovery doc; 00213-00217 are the PRDs).

## Findings

### Blocking

- [00216] Grounding/Coherence: the seeded state sets `phases_completed
  ["build"]` and calls it "the state a build session leaves at `tasks_done`".
  It is not: `cli/transitions.py::_to_review` leaves `phases_completed`
  untouched and `autopilot init` writes no such key, so the real shape has no
  `"build"` entry ever. `test_seeded_state_is_the_tasks_done_shape` would pin
  a false shape -> fails as: wrong-TDD lock-in, then rework thrash when a
  reviewer diffs it against `transitions.py`. Fix: seed with `autopilot init`,
  `statectl set` for `work_start_sha`, `cycle`, `rework_cap`, `batch`, then
  `autopilot phase-done --outcome tasks_done` (a pure transition plus
  `handoff.clear_markers`), so the shape is produced by the transition and
  cannot drift; drop `phases_completed` from the seed and the test's field
  list; the Risks bullet becomes moot and is rewritten.
- [00216] Coherence: `test_stub_frontmatter_is_the_six_pairs` names six pairs;
  the Behavior lists five (`catchup`, `design`, `rework_cap`, `default_model`,
  `model_tier_rationale`) -> fails as: wrong-TDD lock-in (Ivan invents a
  sixth key to turn the test green). Fix: rename to `..._five_pairs` and say
  "the five pairs".
- [00215] Goal alignment: discovery must-have 4 asks the assembly to apply
  "every `Integrator:` trailer from lane commits". The trailers exist (e.g.
  `16c451a`: "Integrator: CHANGELOG.md, one bullet appended at the END of
  [Unreleased] ### Added") and are prose instructions to a human integrator,
  which deterministic code cannot apply; 00215 drops them without saying so
  -> a dropped must-have (lens H rule). Fix: the wave summary gains
  `## Integrator notes` listing every `Integrator:` trailer in
  `base_sha..<lane head>` per merged lane (verbatim, with the commit sha), one
  `test_summary_lists_integrator_trailers`; no automatic application, and the
  PRD says why.

### Non-blocking

- [00217] Grounding: the one `self._spawn` call site is `Loop._launch`, not
  `Loop._launch_phase`; `routing.Route` carries no phase, so
  `_announce_and_launch` (which knows `phase`) must pass it down, and the
  `review-once` verb (`_run_once`) shares the site so it takes a slot too.
  Edit the Feature and the task to name `Loop._launch`.
- [00214] Executability: Phase 1 Exit Criteria runs `wave plan` on "this
  repo's own backlog" from inside the batch session, writing `wave.json` into
  the live autopilot dir mid-batch. Edit: assert it on a `tmp_path` repo (the
  tests already do) or drop the criterion.
- [00214] Sizing: the Phase 1 task bundles validate + launch + status + abort
  with 11 named tests; one implementor turn for four verbs is the batch's
  likeliest overrun. Split: task 1 validate + launch + `wave_cli` registration;
  task 2 status + abort.
- [00214] Coherence: "one path is a directory prefix of the other" and the
  edge case "a PRD names `skills/x/`" - `cli/lane.named_paths` never returns a
  directory (a trailing `/` is dropped by `_candidate`), so the prefix rule
  fires only for a `- **Location**:` path written without a trailing slash
  (`skills/x`). Edit the edge case and the Behavior so the test author builds
  the right fixture and Ivan does not "fix" `named_paths` (00204 code).
- [00216] Compliance: `#### Feature: \`autopilot wave run\`` - backticks in a
  feature heading; the coverage gate keys on the heading text. Rename to
  `#### Feature: Run a wave in one command`.
- [00217] Executability: nothing creates `wave-slots/` (00214 only names it in
  the env); `acquire` must `mkdir -p` the dir before `mkdir <dir>/<n>`.
- [00213] Compliance: Dependency Graph layer headings read "Layer 1 (Phase
  1)" / "Layer 2 (Phase 2)"; the template says "Core Layer" / "Integration
  Layer". Wording only.
- [00214] Design: `WAVE_FORCE_SHARED` hardcodes this repo's three files into
  the plugin; a no-op in every other repo. Accept (harmless) or note in
  `waves.md`.
- [00213, 00214] Terminology: "lane" now means an effort lane (`cli/lane.py`),
  a CLI reviewer lane (00213 `dev/local/autopilot/lanes/<pid>`), and a wave
  lane (00214 `dev/local/autopilot/lane.json`, same dir). If Q2 drops
  `lane.json` the same-dir collision disappears; otherwise rename 00213's dir
  to `reviewer-lanes/`.
- [00214] Note: a main-checkout loop started after `wave launch` matches lane
  sessions as peers (`claude-autopilot-` is a prefix of `claude-autopilot-l1-`)
  and pays one SendMessage plus up to 120 s per Phase 0; it never stands down
  wrongly (lanes own different PRDs). Worth one line in `waves.md`.

### Questions

- [00216] Assembly review scope. As written the loop reviews `base_sha..HEAD`
  of the whole wave with the full roster. Measured on the 2026-09-20 wave:
  135 files, 12,367 insertions, 1,289 deletions across 88 commits, of which
  the shared files (CHANGELOG, release-checks, SKILL.md, state-schema.md,
  records.py, schema.py) were 6 files, 112 insertions. Bob's prompt must
  inline the diff; a ~13K-line diff will not fit his context and the review
  degrades to `review_failed`, so the wave fails to land after all the work.
  Options: keep full range and accept; scope the assembly review to files
  touched by two or more lanes plus `WAVE_APPEND_ONLY` (a `--paths` filter on
  `gather-context.sh`, in 00216); size-gate between the two.
- [00215/00214] must-have 6 asks for a `- Wave:` line in the batch report's
  per-PRD section. 00215 ships a wave summary file instead and tags the
  migrated rows; the per-PRD sections are rendered inside each lane before
  migration. `lane.json` (00214) is written and read by nothing. Options:
  accept the substitution and drop `lane.json`; have `render_report` read
  `lane.json` and emit `- Wave: <id>, lane <name>`; defer.
- [00214] must-have 8 second half wants `repo-l2` sessions to count as the
  same repository in the stand-down filter. 00214 argues the opposite is right
  (PRDs are physically partitioned per lane, so lanes are never peers) and
  changes nothing. Options: accept 00214's reading; implement the letter
  (strip `-l<n>`); key on the git common dir.

## Reshapes

None proposed. All four >200-line PRDs are single-subsystem, three phases,
and each task plans well under the 150K budget (new files, small PRD slices).
00214's Phase 1 task split (above) is an in-place edit, not a reshape.

## Gaps

- `Integrator:` trailers (B3 above).
- Post-batch: these PRDs run from the checkout but the batch executes the
  installed 0.5.5 cache; nothing lands until `dev/bin/release` +
  `/plugin update`. The `autoclaude wave` alias is a dotfiles change after
  that release (declared in 00214/00216).
- The Watcher prose stays beside the new Stop hook until a batch proves the
  hook (declared follow-up in 00213).
- Discovery nice-to-have "lane-local `session_model` overrides" has no PRD;
  fine, it is a nice-to-have.

## End state after this batch

The plugin can cut a backlog into path-disjoint lanes, launch one ordinary
loop per lane in its own worktree, bound concurrent review sessions with a
directory semaphore, assemble drained lanes onto one branch with the keep-both
rule and a stall record for every real conflict, migrate ledgers with lane and
wave tags, review the assembled branch through the ordinary loop, and land it
on master by fast-forward, all behind `autopilot wave <verb>` and a one-shot
`wave run`. Loop sessions can no longer end a turn on top of a live codex or
gemini reviewer. Still lacking after the batch: a release, the dotfiles alias,
a real-wave measurement of the per-lane catchup cost (00214 Risks), and the
Watcher prose retirement.

## Frontmatter tuning

| PRD | suggestion | why |
|-----|------------|-----|
| all | keep `catchup: skip`, but run `/git-ferry:catchup` by hand before launching the batch | `dev/local/meta/project-capsule.md` is dated 2026-09-14 and lists 00194-00206 as backlog; with `skip` on every PRD nothing refreshes it |
| 00213, 00217 | `design: skip` as set | contracts are written out; fine |
| 00214-00216 | `design: run` as set | invented predicates and an invented state contract; fine |

## Decisions applied

Walkthrough 2026-09-22, six findings plus two LOW batches; every item applied
in place with the Edit tool, then lens A re-run (headings in template order on
all five, one `Acceptance:` per task line, feature headings unique, no retired
string left: `lane.json`, `six_pairs`, `_launch_phase` gone).

| # | PRD | decision | status |
|---|-----|----------|--------|
| 1 | 00216 | seed through `autopilot init` + data sets + `autopilot phase-done --outcome tasks_done`; `phases_completed` never written; Risks bullet rewritten; test field list adjusted | applied |
| 2 | 00216 | `test_stub_frontmatter_is_the_five_pairs` | applied |
| 3 | 00215 | `wave.json` lanes gain `integrator_notes`; summary renders `## Integrator notes` verbatim, applies none; Problem Statement says why; two tests | applied |
| 4 | 00215 + 00216 | assembly review scoped to the interaction surface: 00215 records per-lane `files`; 00216 adds pure `review_paths(wave)`, writes `dev/local/autopilot/review-paths` in the assembly worktree, the stub lists `Diff scope:`; `gather-context.sh` reads the marker and appends `-- <paths>` to both diffs with a `path-scoped review` label; new task with `test_gather_context_paths.sh`; marker documented in state-schema § Marker files and Retention; new Risks bullet on the accepted blind spot | applied |
| 5 | 00214 | `lane.json` dropped from launch, Retention and state-schema rows; 00215 header no longer names it | applied |
| 6 | 00214 | stand-down filter unchanged; `waves.md` notes the main-loop peer wait | applied (ratified deviation from must-have 8b) |
| L1 | 00217 | `Loop._launch` named as the spawn site; phase passed from `_announce_and_launch`; `review-once` shares the site | applied |
| L2 | 00214 | Phase 1 Exit Criteria restated on `tmp_path`; live-backlog run forbidden | applied |
| L3 | 00214 | Phase 1 split: validate + launch + `wave_cli`, then status + abort (+ `test_abort_on_a_planned_wave_is_a_noop`) | applied |
| L4 | 00214 | prefix rule reworded around `named_paths` (no trailing-slash directories); edge case fixed | applied |
| L5 | 00216 | `#### Feature: Run a wave in one command` | applied |
| L6 | 00217 | `acquire` runs `mkdir -p` on the slots dir; `test_acquire_creates_the_slots_dir` | applied |
| L7 | 00213 | Dependency Graph layers renamed Core / Integration | applied |
| L8 | 00214 | `waves.md` notes `WAVE_FORCE_SHARED` is repo-specific and the peer wait | applied |
| - | 00215 / 00214 | must-have 6 `- Wave:` line: substitution by the wave summary accepted | rejected (by decision) |
| - | all | terminology (three meanings of "lane"): the same-dir clash is gone with `lane.json`; no rename | accepted as-is |

Not changed: `catchup: skip` on all five stays; run `/git-ferry:catchup` by
hand before the batch (the capsule is dated 2026-09-14).
