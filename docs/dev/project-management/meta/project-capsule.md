# Project Capsule: claude-autopilot

Generated: 2026-09-14

## Key Invariants

- This repo IS the `autopilot@buvis-plugins` skill pack's source. An autopilot
  batch drained *in this repo* executes the **marketplace-cached** install
  (`~/.claude/plugins/cache/buvis-plugins/autopilot/<version>`), not the
  checkout — nothing a PRD changes here is live until `dev/bin/release` +
  `/plugin update`. See memory `project-batch-runs-installed-cache`.
- Bob (codex reviewer) needs his prompt fully inlined (header + context + diff
  + PRD text in one file) — path references are unreadable in his sandbox. See
  memory `project-bob-codex-needs-inlined-prompt`.
- `enforce_prd_location.py` keeps `dev/local/prds/` lifecycle dirs canonical;
  a repo-root `backlog/`/`wip/`/`hold/`/`done/` reference is blocked.

## Architecture Decisions

- Ten skills drive a PRD lifecycle: catchup → design → plan-tasks → work →
  review-rework loop (consensus/blind/doubt lenses every cycle) → done.
- Fourteen agents: one implementor (`ivan`), thirteen reviewers across four
  lenses (consensus: alice/bob/carl; blind: blake; doubt: eve; dimensions:
  rita/cora/grace/toby/mallory/trent/victor/pat).
  bob (codex) and carl (gemini) dispatch to external CLIs; both refuse to
  recurse when already inside a CLI agent (`AUTOPILOT_DISPATCH_DEPTH` /
  host markers) — see README "Recursion guard".
- PRD 00164 (this batch's selection) added VERIFY-finding routing: a
  doubt-lens finding with an exact named check gets queued to
  `dev/local/reviews/{prd-stem}-checks-{cycle}.json` instead of becoming a
  task; `work` step 7 runs the queue inside its one mandatory verification
  pass and writes `dev/local/autopilot/last-verification.json`; the review's
  `Tests:` line reuses that record when its `sha` matches the reviewed HEAD.
  This collapses the "full suite runs up to 3x per cycle" duplication.

## Component Boundaries

- `skills/run-autopilot/cli/` is the sole `state.json` mutator surface
  (`statectl.py` + the `autopilot` subcommand CLI); skills invoke it rather
  than hand-editing state.
- `skills/work/references/final-verification.md` owns the verification
  procedure (suite run, queued checks, the recorded-result write); the
  review skill only *reads* `last-verification.json`, never writes it.

## Active Work

### Batch 202610031511
- [x] 00240-ignore-nested-store-lock-files-v1 (1 cycle)
- [x] 00241-bound-rework-batches-by-file-v1 (2 cycles)
- [x] 00242-harden-the-wave-verbs-v1 (2 cycles)
- [x] 00243-make-the-headroom-wall-scan-match-its-contract-v1 (1 cycle)
- [x] 00244-tidy-the-enter-verb-and-the-review-diff-plumbing-v1 (1 cycle)
- [ ] 00248-keep-phase-skills-in-the-session-v1
- [ ] 00249-stage-and-close-reviews-in-code-v1
- [ ] 00250-finish-the-rework-grouping-fixes-v1

Observations: 00240 was a clean single-PRD cycle, no deferred decisions or
doubts, full suite green at merge (2150 passed). 00241 cap-out at cycle 2
(rework_cap 2) with 2 unresolved HIGH, 0 CRITICAL: 20 findings (4 cycle-1
review-deferrals plus 16 cycle-2 cap-overflow records) migrated to the batch
deferred JSON. `mint-stubs` minted three hold stubs for the unowned severe
rows, `00245`/`00246`/`00247`: the store `.gitignore` recursive-lock-pattern
revert (release-gated on this cache catching up to PRD 00240), the Tail sweep
step-2/Split-rule contradiction left partially unresolved, and the
`_LINE_SUFFIX` citation-shape gap left partially unresolved. Bob (codex)
failed exit 1 twice in both cycles (`turn.failed`, no sidecar); the doubt
lens ran on the Claude fallback both times, all five D1-D5 rubric rules
passing. `engram pack` unavailable (repo not gita-registered) - every review
prompt carried the documented sentinel. 00242 converged at cycle 2 with 13
consolidated findings, all medium/low, zero CRITICAL/HIGH across Alice,
Blake, Bob and Carl; the medium/low tail was swept in one `[D2]` task
(Tess/Ivan/Pat) rather than per-finding tasks. `bash dev/bin/release-checks`
green at cb9be6b (2267 passed, 0 failed, 0 skipped). One deferral recorded
(`_hold_backlog`'s non-injectable `run_git`, an operator call on test
testability vs. scope) plus three cycle-1 deferrals carried from the design
phase; `mint-stubs` minted nothing (all 28 open ledger rows medium/low). 00243 ran
the fast-track lane (card-sized, single task): tests + fix via Tess/Ivan, a
5-lane review (Alice fallback after a rejected Workflow scriptPath, Blake,
Eve, Bob/codex, Carl/Gemini) found only MEDIUM/LOW, converged cycle 1,
`exit-action=commit`. No deferrals, no doubts. 00244 converged at cycle 1
(9/9 tasks) with 15 autonomous decisions, all swept via one tail-sweep task
[D1] rather than per-finding tasks; a concurrent unrelated session committed
mid-run (1fda3dc) introducing one pre-existing release-checks failure
(`test_agent_registry.py::test_registry_holds_no_malformed_agents`, confirmed
unrelated to this PRD's own diff, out of scope here). Two settled deferrals
(`__main__.py` over the 800-line ceiling, pre-existing per PRDs 00223/00236/
00241) migrated to the batch deferred JSON; `mint-stubs` minted one new hold
stub, `00251-triage-the-store-gitignore-recursive-lock-patte-v1`, for an
unowned severe row elsewhere in the batch ledger (29 other rows skipped as
already owned or medium/low).

### Batch 202610021244
- [x] 00236-track-the-store-without-tripping-the-loop-v1 (2 cycles)

Observations: 00236 cap-out at cycle 2 (rework_cap 2) with 2 unresolved HIGH,
0 CRITICAL: 12 cap-overflow findings (2 HIGH, 7 MEDIUM, 3 LOW) migrated to
the batch deferred JSON. `mint-stubs` minted two hold stubs for the unowned
HIGHs, `00238`/`00239`: (1) `lane_check.diff_signal` excludes the
un-prefixed `STORE_EXCLUDE_PATHSPECS`, so a bare-repo-backed store (store at
a nested dot-directory under the work-tree root, e.g. the `~/.claude`
dotfiles layout) still reads as production and escalates every solo-lane
PRD; (2) `Loop._record_review_once_store` has no `in_wave_lane` guard unlike
its sibling call sites, so `autopilot review-once` inside a wave lane
worktree would commit store files onto the lane branch. Task 13 was marked
completed with three quoted findings undelivered (`test_wave_assemble.py`/
`test_wave_launch_refusals.py` untouched this cycle, `wave_review` and
intake replay survivors persist) - also deferred, not reworked. This
checkout has `/docs/` in `.git/info/exclude` (design site 10, deferred to
the operator), so store writes never appear in `git status` - expected,
not a bug. `engram pack` unavailable (repo not gita-registered).

### Batch 202609252154
- [x] 00213-hold-the-loop-session-open-while-cli-reviewer-lanes-run-v1 (1 cycle)
- [x] 00214-plan-and-launch-a-wave-of-lanes-v1 (2 cycles)
- [x] 00215-assemble-a-drained-wave-onto-one-branch-v1 (2 cycles)
- [x] 00216-review-the-assembled-wave-and-run-a-wave-end-to-end-v1 (2 cycles)
- [x] 00217-bound-concurrent-review-sessions-with-a-slot-semaphore-v1 (2 cycles)
- [x] 00218-leave-sessions-at-task-boundaries-and-run-one-devon-round-v1 (2 cycles)
- [x] 00223-enter-the-build-gate-in-one-cli-call-v1 (2 cycles)
- [x] 00231-route-rework-fixes-on-their-own-tier-v1 (2 cycles)
- [x] 00232-keep-subagent-test-runs-narrow-v1 (2 cycles)
- [x] 00233-run-the-test-suites-in-parallel-v1 (2 cycles)

Observations: 00213 converged at cycle 1 (16 findings, no CRITICAL/HIGH); a
tail sweep of 3 [D1] tasks closed the Medium/Low findings (counter-write
guard, loud internal-failure handler, no-output-lane awaiter message, cwd
cast, a tautological registration test dropped, a stub `:?` guard and a
fast-track sentence ordering fix), plus an end-to-end lane-chain test. 6
settled deferrals ledgered (two pre-existing assertionless-test rows, the
three-stub duplication, the gemini marker ordering, the EXIT-only trap, and
the `str()` cwd cast). Bob's codex lane failed twice (exit 1, turn.failed)
and ran as the Claude fallback; engram pack unavailable (repo not
gita-registered).
00214 converged at cycle 2 (rework_cap 2, beat the cap) with 21 autonomous
decisions across both cycles: 6 internal contract contradictions found and
resolved during task work (a status enum gap, an all-held-back lockout, an
unreachable duplicate check, a locked() self-brick trap, an rmtree-under-a-
live-lane hazard, two exception-type gaps in abort's git/OSError handling),
plus 4 items reworked from cycle-1 review (the CRITICAL `pid` positivity
bound now `1 < v < 2**31`, abort's wip/-return target corrected to main
`backlog/`, a ProcessLookupError race, and `base_sha` added to the structural
validator). Cycle 2's own HIGH (missing `[checks] waves` files) was verified
Medium and swept in the Tail task rather than shipped open. The cycle-1
CRITICAL `pid` finding was migrated into the batch deferred JSON per Phase 9
step 6 even though already fixed via rework (the skill's decision-logging
contract always records a Critical to the deferred sink for audit
visibility) — `mint-stubs` then minted two near-duplicate hold triage stubs
for it, `00219`/`00220`; both should be closed at the next backlog review
since the underlying `wave.py:289` bound is already shipped. `engram pack`
unavailable both cycles (repo not gita-registered).
00215 cap-out at cycle 2 (rework_cap 2) with 7 unresolved findings (2 HIGH,
4 MEDIUM, 1 LOW), 0 CRITICAL: all 7 migrated to the batch deferred JSON as
`cap-overflow`. `mint-stubs` minted two hold stubs for the unowned HIGHs,
`00221`/`00222`: (1) `test_wave_assemble_summary.py` is absent from both
`release-checks`' `[checks] waves` block and `test_wave_docs.py`'s
`_WAVE_TEST_FILES` whitelist, so 12 tests never run in CI while the gate
reads green; (2) `wave_assemble.py`'s teardown loses `held_prds`/`status`/
`batch_id`/`worktree_removed` on a pre-save crash because the only `save()`
runs after the worktree removal. `engram pack` unavailable both cycles
(repo not gita-registered).
00216 cap-out at cycle 2 (rework_cap 2) with 21 unresolved findings (0
CRITICAL, 1 HIGH, 13 MEDIUM, 7 LOW): cycle 1's CRITICAL (`autopilot wave run`
crashing on every invocation, `wave_cli.py:29` missing `--state` arg) was
fixed and verified through `main()` in cycle 2's rework; the surviving HIGH
(`land` cannot land after a hand review, `wave_review.py:522`) was not
closed. All 21 cycle-2 findings plus cycle 1's 3 deferred_decisions (the
CRITICAL migration, a requirements-ambiguity over whether waves support a
git-tracked `docs/dev/project-management`, and an out-of-scope test-quality
note) migrated to the batch deferred JSON. `mint-stubs` minted three hold
stubs for the unowned rows, `00224`/`00225`/`00226`: the fixed-but-still-
recorded CRITICAL, the tracked-store ambiguity, and the surviving HIGH.
`engram pack` unavailable both cycles (repo not gita-registered).
00217 cap-out at cycle 2 (rework_cap 2) with 11 unresolved findings (1 HIGH,
8 MEDIUM, 2 LOW), 0 CRITICAL: all 11 migrated to the batch deferred JSON as
`cap-overflow`. `mint-stubs` minted one hold stub for the unowned HIGH, `00227`:
a three-party put-back race in `wave_slots.py`'s `_discard` can still hand one
slot to two holders — closing it fully needs per-slot `fcntl.flock` rather than
the pid-file/rename primitive this PRD specifies. Cycle 1 fixed the original
non-atomic-claim race (4/4 consensus) via a stage-then-rename primitive;
cycle 2's review found this narrower residual left by that fix. `engram pack`
unavailable both cycles (repo not gita-registered).
00218 cap-out at cycle 2 (rework_cap 2). Cycle 1's CRITICAL (time term never
wired into the context-cap hook) was fixed via cycle-2 rework task 4, but per
the same always-record contract it stayed in the deferred sink and
`mint-stubs` minted `00228` for it (should close at backlog review, already
shipped). 8 further cap-overflow findings (2 HIGH, 4 MEDIUM, 2 LOW) went
unresolved at the cap: `mint-stubs` minted `00229`/`00230` for the two HIGHs
(`_cap_headroom.py`'s `trusted_last_wall` lacks a scan-back/dict/bool guard
and substitutes for the PRD's `last_task_wall`, so task 11's widening is dead
code; `test_autopilot_cap_headroom.py` at 923 lines fails the repo's own
800-line style gate). `engram pack` unavailable both cycles (repo not
gita-registered).
00223 cap-out at cycle 2 (rework_cap 2) with 2 unresolved HIGH, 0 CRITICAL:
both migrated to the batch deferred JSON as `cap-overflow`. `mint-stubs`
minted two hold stubs for the unowned HIGHs, `00234`/`00235`: (1) `enter.py`
is 414 lines against the PRD's own "under 400 lines" Phase 0 exit criterion;
(2) the `fs_error`/`park_halt` stop-table rows each name one owning cause
while the code now raises them from several. A cycle-1 known-limitation
(pre-existing `cli/__main__.py` 1289-line, 800-line-cap overflow, task
explicitly refused to touch it) also deferred to batch end. Bob's
`--emit-thread-id` sidecar came back empty both cycles, so no
`codex_thread_id` was stamped and every cycle re-reviewed from zero — worth
its own PRD. `engram pack` unavailable both cycles (repo not
gita-registered).
00231 converged at cycle 2 (rework_cap 2). Cycle 1 auto-fixed a HIGH
(`test_changelog_unreleased_has_one_changed_heading` required exactly one
`### Changed` heading under `[Unreleased]`, but the v0.6.0 release commit
emptied that section, redding `release-checks`; loosened to `<= 1` while
still failing on duplicates) and a Medium (new prose-pin test file's windows
sliced to end-of-file instead of to the pinned bullet/list). Cycle 2's review
found the fix still text-marker-bound rather than structure-bound; swept in
one [D2] task rather than reworked (all Medium/Low). 2 low-severity
deferrals migrated to batch end: `tier_reason` observability may not be a
reachable Success Metric, and `release-checks`' recursion guard fails when
run from inside a nested CLI reviewer dispatch (passes in a normal shell;
pre-existing, out of scope). `engram pack` unavailable both cycles (repo not
gita-registered).
00232 converged at cycle 2 (rework_cap 2, beat the cap). Cycle 1's 3/4 HIGH
(Tess's quality-gate retry and strengthen prompts omitted the narrow-run
sentence, making the new SKILL.md:71 claim false as shipped) was reworked:
NARROW added to `tess-retry-prompt.md` and inside the "Feedback to Tess"
fenced template, plus a prose test rewritten to pin the full literal with
section-anchored adjacency instead of a prefix-only, cross-file-only check.
Cycle 2 converged with 0 CRITICAL/HIGH; a 3-task tail sweep closed the
surviving Medium/Low (the Feedback-to-Tess pin bound to the fence slice
rather than file-wide, a redundant `.rstrip()` after `_norm()` removed, two
unpinned task-4 prose changes given assertions). 4 low/medium deferrals
migrated to batch end, all requirements-ambiguity or pre-existing-text
questions against the PRD text rather than implementation defects (NARROW's
hard-coded pytest flags, `fast-track/SKILL.md`'s pre-existing "keep the
suite green" pull, the Devon-wording inconsistency with SKILL.md:71's
blanket claim, and the four extra NARROW insertion points beyond the PRD's
named file list). `engram pack` unavailable both cycles (repo not
gita-registered).

### Batch 202609061630
- [x] 00178-fix-bob-first-run-and-specify-his-retry-v1 (2 cycles)
- [x] 00179-cap-the-adversarial-test-loop-at-one-round-v1 (1 cycle)
- [x] 00180-route-codex-prompt-through-stdin-v1 (2 cycles)
- [x] 00181-scrub-inherited-host-markers-at-loop-spawn-v1 (1 cycle)
- [x] 00182-close-open-dispatch-rows-at-session-handoffs-v1 (2 cycles)
- [x] 00183-make-batch-report-decisions-and-implementor-mix-render-v1 (2 cycles)
- [x] 00184-carry-tool-discipline-into-every-bash-bearing-loop-prompt-v1 (1 cycle)
- [x] 00185-route-review-reruns-to-high-effort-v1 (1 cycle)
- [x] 00186-add-item-grained-fast-track-lane-v1 (2 cycles)
- [x] 00187-keep-cap-out-criticals-off-master-and-home-deferred-highs-v1 (2 cycles)
- [x] 00188-record-convergence-cap-and-roster-per-prd-v1 (2 cycles)
- [x] 00189-stall-to-split-on-plan-expansion-v1 (2 cycles)
- [x] 00190-bind-the-codex-run-tests-and-dedupe-their-split-v1 (2 cycles)
- [x] 00191-clear-the-handoff-marker-at-phase-edges-v1 (1 cycle)
- [x] 00192-split-loop-py-and-its-tests-under-the-cap-v1 (1 cycle)
- [ ] 00194-design-critical-rework-before-task-dispatch-v1 (backlog)
- [ ] 00195-mint-hold-stubs-for-unowned-deferred-findings-v1 (backlog)
- [ ] 00196-guard-review-phase-rework-sessions-v1 (backlog)
- [ ] 00197-carry-style-limits-into-the-tess-prompt-and-gate-the-test-commit-v1 (backlog)
- [ ] 00198-normalize-reviewer-file-citations-before-consensus-matching-v1 (backlog)
- [ ] 00199-add-loop-guard-rails-for-sleep-limits-and-stand-downs-v1 (backlog)
- [ ] 00200-hand-off-on-usage-headroom-and-decouple-the-session-model-v1 (backlog)
- [ ] 00201-write-a-session-brief-at-every-gate-transition-v1 (backlog)
- [ ] 00202-commit-subagent-output-before-a-rotation-can-lose-it-v1 (backlog)
- [ ] 00204-classify-prds-into-effort-lanes-v1 (backlog)
- [ ] 00205-run-solo-lane-prds-in-one-session-v1 (backlog)
- [ ] 00206-render-fast-track-cards-from-a-prd-and-run-the-lane-in-the-loop-v1 (backlog)

Observations: PRD numbering here continues independently of the `~/.claude`
repo's sequence (same numbers across the two repos are not a collision). The
qwen dispatch path on this host is latched unhealthy for batch 202609061630
(endpoint_unreachable) — see the batch report's deferred item; qwen-eligible
tasks route to Claude Sonnet until that infra bug gets its own PRD.
00180 hit the rework cap at cycle 2 with 9 unresolved findings (highest
severity: one HIGH — the acceptance-gate rg -c count is unmet because 24 test
cases moved into an unrequested new file `test_codex_run_resume.sh`); all 9
went to the batch deferred JSON as `cap-overflow` for `review-batch` triage.
00181 converged at cycle 1 with no unresolved CRITICAL/HIGH; one low-severity
out-of-scope finding (pre-existing loop.py/test_loop.py 800-line cap
violation, not created by this PRD) deferred to batch end.
00182 converged at cycle 2 with 9 findings, none above Medium; 4 discarded
(replay rows verified as behavior-preserving test relocation, plus two
housekeeping nits), 5 swept into one tail-sweep task that landed clean.
00183 converged at cycle 2 with 12 autonomous decisions and one cycle-1
assumed-ambiguity (CHANGELOG grep case-sensitivity, read as case-insensitive
since the required entry already exists); Phase 9's missing-from-report
guard tripped on that assumed-ambiguity record because it carries
question/assumption, not issue text — marked `resolved` in the deferred JSON
since it renders under Assumptions Made, not the Deferred table. Worth its
own fix upstream: `cli/render_report.py`'s `missing_from_report` should
exclude `type == "assumed-ambiguity"` the same way `is_autonomous_row` does.
00184 converged at cycle 1 with 4 findings (0 critical/high, 2 medium swept
into one tail-sweep task that landed clean, 2 low discarded with verified
reasons); 3 autonomous decisions (empty-diff base fix, missing engram pack
substitution, two sandbox-limitation Lows discarded).
00185 converged at cycle 1 with 11 findings (0 critical/high, 7 medium/low
swept into one tail-sweep task that landed clean, 2 pre-existing loop.py
size findings deferred to PRD 00192, 2 "cannot statically verify" findings
discarded with verified reasons).
00186 cap-out at cycle 2 (rework_cap 2) with 8 HIGH still unresolved, 0
CRITICAL: 24 cap-overflow records (8 High, 10 Medium, 6 Low) deferred to the
batch JSON for `review-batch` triage. 4 cycle-1 assumed-ambiguity records hit
the same Phase 9 missing-from-report guard bug already logged under 00183
(question/assumption text, not issue text) — marked `resolved` again as the
same workaround; the upstream fix in `cli/render_report.py`'s
`missing_from_report` (exclude `type == "assumed-ambiguity"`) is now confirmed
twice and worth doing.
00187 converged at cycle 2 with no unresolved CRITICAL/HIGH (cycle-2 tail
findings swept via one task); 1 medium pre-existing `__main__.py` 800-line
cap overflow deferred to batch end for its own PRD.
00188 cap-out at cycle 2 (rework_cap 2) with one unresolved High (Bob:
read_cycle still reads a metadata-only or table-less review file as zero
findings instead of null) and one Low (Alice: `batch` naming in
`_append_convergence`); both deferred to the batch JSON for `review-batch`
triage. Eight of nine cycle-1 findings verified resolved in the cycle-2
rework, no regressions.
00189 cap-out at cycle 2 (rework_cap 2) with one unresolved High (Bob F2
residue: a `//tmp/src/` tree entry still hangs `_ancestors`, since the
cycle-1 fix only bounded the walk at a single leading slash); 5
cap-overflow/out-of-scope findings deferred to the batch JSON for
`review-batch` triage, 3 settled deferrals (rejected-by-design x2,
requirements-ambiguity resolved at build time as an assumed-ambiguity and
reconfirmed by Blake). 2 assumed-ambiguity records tripped the Phase 9
missing-from-report guard bug already logged under 00183 and 00186
(question/assumption text, not issue text) — marked `resolved` again as the
same workaround; now confirmed a third time across three different PRDs,
strongly worth the upstream fix in `cli/render_report.py`'s
`missing_from_report` (exclude `type == "assumed-ambiguity"`).
00190 converged at cycle 2 with 0 findings (1 Low from Blake discarded at the
gate); cycle 1 had 5 findings (1 High, 3 Medium, 1 Low) all fixed in one
rework task; 2 settled deferrals (redundant `rm -f` before use, unchecked
negative array index in bash 3.2) deferred to the batch JSON.
00191 converged at cycle 1 (tail sweep task 5, suite 1197 passed); 1 Low
out-of-scope (inherited size violations) deferred to batch end.
00192 baseline at selection (HEAD 54b7706): `cli/loop.py` 1420 lines
(module helpers lines 97-445 + one `Loop` class lines 447-1418 + `main`),
`cli/test_loop.py` 1714 lines (109 tests, one autouse fixture, fake
clock/ScriptedSpawn harness). Consumers of `cli.loop` outside its own test:
`__main__.py` (`loop.Loop().run()` / `.run_once()`), `test_loop_review_once.py`
and `test_routing.py` (`from cli.loop import Loop`). `cli/golden/` holds 5
files + `expected/`. The loop driver here is the 0.5.1 cache (pid 96616),
not this checkout, so the split cannot self-harm the running batch.
00233 converged at cycle 2 (rework_cap 2, beat the cap): cycle 1 root-caused
intermittent wave-test failures under pytest-xdist to the host's global
`commit.gpgsign=true` leaking into throwaway repos and contending on the
shared gpg-agent, fixed with one `commit.gpgsign false` line in `_repo()`
plus a `test_parallel_safety.py` regression guard, then flipped 5
`release-checks` blocks to `-n auto`/`-n 4`. 3 sonnet-tier [D1] rework tasks
closed cycle-1's HIGH/Medium findings; a tail-sweep [D2] task closed 6 more
Medium/Low findings at cycle 2. 6 items deferred to the batch JSON (an
out-of-scope file pairing, a `consolidate_findings.py` over-merge defect, a
`gather-context.sh` empty-diff trap in master-only repos, a
requirements-ambiguity on `-n auto` vs `-n 4`, a prevent-the-class gap on
future `_repo()` regressions, and a residual sweep item); the
`gather-context.sh` empty-diff defect minted hold stub 00237.

## Related context

- gems `dev/local/prds/wip/00055-bim-cli-modularization-v1.md:1-2` (0.016) -
  another "split the CLI god module" PRD; same shape, different repo.
- `~/.local/tmp/claude-dev/reviews/00127-loop-registry-lies-about-liveness-v1-review-2.md:126`
  (0.016) - earlier loop.py review; registry/liveness seam history.
- `~/.local/tmp/claude-dev/reviews/00129-autoclaude-suite-stubs-do-not-intercept-v1-review-1.md:113-118`
  (0.016) - "unrelated live foreign WIP in cli/loop.py" incident; the
  two-writers-one-checkout risk this repo carries.
- `~/.local/tmp/claude-dev/reviews/00029-...-review-1.md:43` (0.015) - scope
  note naming loop.py among hook/settings surfaces.

Topic queried: "Split cli/loop.py and test_loop.py under the file cap"
(portfolio scope only - this repo is not engram-registered, so `engram index`
and `engram harvest` both refuse with `no_repo`; every review file harvest
returned 0). Staleness (`engram status --scope portfolio`, exit 1): memory
192 (23 stale, 1 dead), prd 5203 (8 stale, 61 dead), code 42722 (42 stale,
97 dead), transcripts 17713 (17604 dead).

## GitHub State

- 0 open issues, 0 open PRs.
- Only `origin`/`origin/master` active (pushed 2026-09-13, no stale branches).
- No tagged GitHub releases; CHANGELOG.md tracks versions instead (latest
  released: 0.5.2; the installed cache runs 0.5.2 for new sessions while the
  live loop pid 96616 is still the 0.5.1 driver).
- No workflow runs found (no CI configured, or none has run).

## Project Health

CI: none configured/observed. Batch 202609061630 has drained 14 PRDs; 12
remain in backlog (00194-00206), 00110 parked in hold. Working tree clean on
`master` at 54b7706. Standing debt: `cli/__main__.py` (1099) and
`test_state.py` (814) also exceed the 800-line cap; 00192 deliberately
excludes them.

## Project Memories

- `project-batch-runs-installed-cache`: batches here run the installed cache,
  need a release to take effect, must not write to `~/.claude`.
- `project-bob-codex-needs-inlined-prompt`: Bob's codex sandbox needs an
  inlined prompt, not path references.
