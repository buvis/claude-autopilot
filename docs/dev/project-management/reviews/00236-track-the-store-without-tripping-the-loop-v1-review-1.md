---
prd: docs/dev/project-management/prds/wip/00236-track-the-store-without-tripping-the-loop-v1.md
review: 1
date: 2026-10-02
head_sha: 5ab1a1fdca6dc9cf7c885ae6fe2f69b2350cb8b3
codex_thread_id: 01a0fce2-df57-7220-8f24-ad3af1e88258
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00236-track-the-store-without-tripping-the-loop-v1

Diff range: `23bf974..5ab1a1fdca6dc9cf7c885ae6fe2f69b2350cb8b3`

codex_rung_guard: not fired

pack: failed (`engram pack` exits 1: "not inside a registered repo; register it in
/Users/bob/.config/gita/repos.csv"). Deterministic configuration refusal, so no retry;
every implementation-aware prompt carried the documented `(no pack available this cycle)`
sentinel instead. Blake never receives a pack by design.

carl: ran on backend=copilot model=gemini-3.8-flash.

## Scope of this review

**Cycle 1, a full review.** No prior cycle, no prior findings to verify, no settled
decisions ledger on entry.

**The diff range is wider than `state.work_start_sha` on purpose.** `work_start_sha` is
`4f336ff`, which sits two commits *into* this PRD's own work: `29f4d5a`
("add tests for store_tree dirty-tree predicate") and `4f336ff` ("strengthen store_tree
tests against Devon exploits") are both PRD 00236 commits. Reviewing from
`work_start_sha` would have shown `foreign_dirty`/`record_store`'s implementation with its
fail-first tests cut out of the diff, inviting a false "this has no tests" finding.
`23bf974` is the last commit before PRD 00236 started, so `23bf974..5ab1a1f` is this
PRD's true whole work range. 27 commits, 27 files, +1932/-28.

**The range holds two plans' commits.** The PRD was replanned on 2026-10-02 after a
`tooling_conflict` stall (the original plan told the session to write the store
`.gitignore` with the Write tool, which `hooks/enforce_prd_location.py` correctly
refuses). Commits `18c6cea`…`c8bbe2b` carry the pre-replan numbering; `89f8cf9`…`5ab1a1f`
carry the eight tasks in `state.tasks`. Both are in scope.

**Settled before review, not raised as gaps:** design site 10 (`.git/info/exclude`),
deferred to the operator and already recorded in the batch deferred JSON; and the PRD's
2026-10-02 Writer bullet superseding design site 4 (the `.gitignore` is written by code
and rewritten on content drift, not written-once with the Write tool).

## Consolidation corrections (read before the table)

`consolidate_findings.py` warned on five suffix-stripped citation merges. Three were
legitimate paraphrase merges. **Three folded genuinely different defects onto one
wording**, and the review gate split them back out — without that, one HIGH and two
MEDIUMs would have been lost behind another finding's text:

1. Bob's `cli/loop.py:487` finding (the `review-once` path records nothing) was merged
   onto Alice's `cli/loop.py:592` wave-lane finding. Different defects; split.
2. Alice's and Bob's `__main__.py:1227` finding (a swallowed `.gitignore` write failure)
   was merged onto Alice's `__main__.py:1195` finding (`dirty` fails open). Different
   defects; split.
3. Bob's `test_store_tree_prose.py:84` finding (the rotation and task-boundary
   instructions are unpinned) was merged onto the record-store *placement* finding at the
   same file:line. Different defects; split.

Two merges the script *missed* were applied by hand instead: Blake's
`store_tree.py:62` bare-repo finding joins Alice's and Bob's (one row at [3/4] rather
than [2/4] plus [1/4]), and Carl's inverted-test-name finding joins the placement row.

Net: 30 consolidated rows, not the script's 30-with-different-grouping. Consolidation was
**script-run, gate-corrected** — not hand-rolled.

## Consolidated findings

Issue text here is a label; each reviewer's own words are in their section below, and
every rework task carries its source findings verbatim.

| Consensus | Severity | Issue | File | Found By | Disposition |
|-----------|----------|-------|------|----------|-------------|
| [3/4] | 🟠 High | Store boundary assumes a top-level `docs/`, and `--untracked-files=all` is forced: both wrong for a bare-repo-backed root like `~/.claude` | skills/run-autopilot/cli/store_tree.py:62 | ALICE, BLAKE, BOB | rework task 9 |
| [1/4] | 🟠 High | Solo-lane escalation breaks: store commits in the range read as production paths, so every solo PRD escalates | skills/run-autopilot/cli/lane_check.py:51 | ALICE | rework task 10 |
| [1/4] | 🟠 High | Wave lanes commit store files onto the lane branch; assembly conflicts on ledger appends and double-migrates rows | skills/run-autopilot/cli/loop.py:592 | ALICE | rework task 10 |
| [1/4] | 🟠 High | `review-once` appends tracked ledger metrics after the session exits and records nothing | skills/run-autopilot/cli/loop.py:487 | BOB | rework task 11 |
| [3/4] | 🟡 Medium | Duplicated git-runner closure between `__main__.py` and `loop_act.py` | skills/run-autopilot/cli/__main__.py:1167 | ALICE, BOB, CARL | rework task 15 |
| [3/4] | 🟡 Medium | `record-store` placement contradicts the PRD sentence, and the PRD-mandated test name reads backwards from what it asserts | skills/run-autopilot/scripts/test_store_tree_prose.py:84 | ALICE, BLAKE, CARL | deferred to batch end |
| [2/4] | 🟡 Medium | `autopilot dirty` fails open: a crashed or timed-out `git status` exits 1 with empty stdout, which every gate reads as clean | skills/run-autopilot/cli/__main__.py:1195 | ALICE, BLAKE | rework task 12 |
| [2/4] | 🟡 Medium | A failed store `.gitignore` write is swallowed by `contextlib.suppress(OSError)`, after which `record_store` stages volatile control files | skills/run-autopilot/cli/__main__.py:1227 | ALICE, BOB | rework task 12 |
| [2/4] | 🟡 Medium | The cap-rotation and task-boundary `record-store` instructions have no test; deleting the sentence passes the suite | skills/run-autopilot/scripts/autopilot_context_cap_hook.py:137 | ALICE, BOB | rework task 14 |
| [1/4] | 🟡 Medium | The loop driver records after every session, including died, paused and stood-down ones | skills/run-autopilot/cli/loop.py:592 | BLAKE | rework task 10 |
| [1/4] | 🟡 Medium | `STORE_GITIGNORE` ships 23 patterns where the PRD lists 18 | skills/run-autopilot/cli/store_tree.py:19 | BLAKE | deferred to batch end |
| [1/4] | 🟡 Medium | Four porcelain gates stay unrewritten; the prose test passes via a 10-entry allowlist and scans `.md` only | skills/work/references/gate-failure.md:53 | BLAKE | deferred to batch end |
| [1/4] | 🟡 Medium | The store is still untracked here, and `git add` on an excluded path exits 1 rather than skipping silently | .git/info/exclude | BLAKE | settled deferral + rework task 12 |
| [1/4] | 🟡 Medium | The writer test's `unreadable` case asserts nothing (either-or `except` hedge); the contract bullet it covers is not met | skills/run-autopilot/cli/test_store_gitignore.py:47 | ALICE | rework task 13 |
| [1/4] | 🟡 Medium | The same writer test accepts failure for the missing-directory and invalid-UTF8 cases, where rewriting is required | skills/run-autopilot/cli/test_store_gitignore.py:49 | BOB | rework task 13 |
| [1/4] | 🟡 Medium | Recorder tests inspect fake git argv without proving a real commit's contents or that a foreign staged file survives | skills/run-autopilot/cli/test_store_tree.py:280 | BOB | rework task 13 |
| [1/4] | 🟡 Medium | `STORE_GITIGNORE` builds a fixed payload through a tuple plus `join` where a literal would read directly | skills/run-autopilot/cli/store_tree.py:19 | BOB | rework task 16 |
| [1/4] | 🟡 Medium | Replay: all 3 new intake layout tests pass against the pre-change code | hooks/test_enforce_prd_location.py:24 | BOB, mech-check | rework task 13 |
| [1/4] | 🟡 Medium | Replay: 7 new assembly refusal cases pass against the pre-change code | skills/run-autopilot/cli/test_wave_assemble.py:473 | BOB, mech-check | rework task 13 |
| [1/4] | 🟡 Medium | Replay: the launch runner assertion accepts the old status invocation | skills/run-autopilot/cli/test_wave_launch.py:516 | BOB, mech-check | rework task 13 |
| [1/4] | 🟡 Medium | Replay: all 6 new launch refusal cases pass against the pre-change code | skills/run-autopilot/cli/test_wave_launch_refusals.py:158 | BOB, mech-check | rework task 13 |
| [1/4] | 🟡 Medium | Replay: all 5 new review refusal cases pass against the pre-change code | skills/run-autopilot/cli/test_wave_review.py:697 | BOB, mech-check | rework task 13 |
| [2/4] | ⚪ Low | `__main__.py` is 1278 lines against the 800-line limit; this diff added 80 | skills/run-autopilot/cli/__main__.py | ALICE, BOB | deferred to batch end |
| [1/4] | ⚪ Low | `record_store`'s scoping guarantee is proven only against `FakeGit`; add one real-git test | skills/run-autopilot/cli/test_store_tree.py:280 | ALICE | rework task 13 |
| [1/4] | ⚪ Low | With the store ignored, `record_store` prints a failure line at every handoff | skills/run-autopilot/cli/store_tree.py:102 | ALICE | rework task 12 |
| [1/4] | ⚪ Low | Dead `RuntimeError` arm in `record_store`'s `except`; stale `_check_reviewable` docstring | skills/run-autopilot/cli/wave_review.py:276 | ALICE | rework task 16 |
| [1/4] | ⚪ Low | Out-of-PRD intake-tree change inside the review range | hooks/enforce_prd_location.py:45 | ALICE | deferred to batch end |
| [1/4] | ⚪ Low | `work/SKILL.md` step 5's foreign-dirt rule was never reworded, so task reports will list store paths | skills/work/SKILL.md:364 | BLAKE | rework task 16 |
| [1/4] | ⚪ Low | PRD says normalized repo-relative comparison; code uses a raw `startswith`. `--state` is not in the PRD | skills/run-autopilot/cli/store_tree.py:72 | BLAKE | deferred to batch end |
| [1/4] | ⚪ Low | Cannot statically verify the post-release tracked-store metric | N/A | BOB | deferred (VERIFY not queued: command shape) |

## Gate verification of the two load-bearing HIGHs

Neither was taken on the reviewer's word, because both drive rework:

- `rg -n 'record_store|_append_metrics' skills/run-autopilot/cli/loop.py` → `_append_metrics`
  at 305 (def), **487**, 583; `record_store` at **593** only. The `_run_once`
  (`review-once`) path records nothing. **Confirmed.**
- `lane.is_production_path('docs/dev/project-management/autopilot/ledger/dispatch-metrics.jsonl')`
  → `True`; `...('docs/dev/project-management/.gitignore')` → `True`;
  `...('docs/dev/project-management/prds/wip/x.md')` → `False`. Store commits inside
  `work_start_sha..HEAD` are production-path evidence to the solo lane. **Confirmed.**
- `wc -l skills/run-autopilot/cli/__main__.py` → 1278, so the size claim is accurate and
  not a contradiction of the mechanical-facts block (which computes per-function counts,
  not file length). No finding was discarded for contradicting computed facts this cycle.

## Alice

Consensus lens, implementation-aware. 2 High, 6 Medium, 6 Low. Full text in her findings
block below; every line is carried verbatim into the rework task that owns it.

- 🟠 Solo-lane escalation breaks once the store is tracked: `lane_check.diff_signal` reads `work_start_sha..HEAD` and returns `unnamed_path` for any changed path that `lane.is_production_path` accepts, and that predicate treats every non-doc, non-test path as production. Once `record-store` commits land in that range, store files such as `docs/dev/project-management/autopilot/ledger/dispatch-metrics.jsonl`, `.../deferred/*-deferred.json` and the store `.gitignore` all count as production. I ran `is_production_path` on them and it returned True for each, so every solo-lane PRD would escalate to the full lane. The design never touches `lane_check` or the `lane.py` path predicates. The review-diff builders also have no store exclusion, so reviewers would see store churn (not checked end to end). Fix: filter `STORE_PREFIXES` out of the `changed` list and the diff in `diff_signal` (or add an `:(exclude)` pathspec), and add a test. | File: skills/run-autopilot/cli/lane_check.py:51 | Task: general
- 🟠 Wave lanes were not accounted for once the store is tracked (suspected from code reading; no test exercises a tracked store in a wave). Lane loops run the same `Loop._run_loop`, so the `record_store` call at loop.py:592 commits store files onto the lane branch with no lane gate. The lane worktree is cut at `base_sha` (wave_launch.py:215), so it inherits every tracked backlog PRD and `_seed_lane_worktree` assumes an empty store. At assembly, `_rebase` only tolerates conflicts in `WAVE_APPEND_ONLY`, which is just CHANGELOG and release-checks (wave.py:21), so two lanes that both append `ledger/*.jsonl` or `dispatch-metrics.jsonl` report `conflict` (wave_assemble.py:207). A lane that does merge also has its ledger rows appended a second time by `_migrate_jsonl` (wave_assemble.py:345). The design doc claims lanes are "covered for free", which holds for `foreign_dirty` but not for committing or merging. Needs an operator decision: skip store recording inside wave lanes (both the wrapper sites and the handoff verb), or define how lane store commits merge. | File: skills/run-autopilot/cli/loop.py:592 | Task: general
- 🟡 `foreign_dirty` is wrong for the bare-repo-backed configuration that the `git_dir` plumbing deliberately supports. It forces `--untracked-files=all`, which overrides `status.showUntrackedFiles=no`, the documented dotfiles-repo setting. `STORE_PREFIXES` also assumes the work-tree top is the project root. I reproduced this with a bare repo whose work-tree holds the store under `.claude/` and `showUntrackedFiles=no`. Plain `git status --porcelain` listed one tracked change. `foreign_dirty` returned the store file (prefix mismatch) plus every untracked file. Over `$HOME` that would also hit the 30 s timeout, which `foreign_dirty` does not catch. The wrapper and handoff `record_store` pathspec `:(top)docs/dev/project-management` resolves to the wrong directory in that layout as well. Fix: derive the store prefix from the store's position under the work-tree, and do not force `all` when the config says otherwise (or bound the walk). Add a bare-repo test with a nested store. | File: skills/run-autopilot/cli/store_tree.py:62 | Task: general
- 🟡 `autopilot dirty` fails open and its contract is undocumented. `foreign_dirty` and `_run_dirty` let a failed or timed-out `git status` (CalledProcessError, TimeoutExpired) escape as a traceback with exit 1 and an empty stdout. Exit 1 already means "usage error / --state unresolved" in the module's exit table and now also means "paths found". The stand-down and task-boundary gates read "prints at least one path / comes back empty", so a crashed check reads as clean. The module docstring lists `record-store` and `ensure-store` but omits `dirty` and the new meaning of exit 1. Fix: catch git failures in `_run_dirty`, print one stderr line and return a distinct code (the table's 2 or 5), then document `dirty` and its codes in the docstring and exit table. | File: skills/run-autopilot/cli/__main__.py:1195 | Task: general
- 🟡 A failed store `.gitignore` write is swallowed with no output. `contextlib.suppress(OSError)` in the `ensure-store` verb and in `enter._prepare_tree` prints nothing, so a missing or unwritable `.gitignore` is invisible. `record_store` then runs `git add` over the store and stages `state.json`, `.turn-counts.json`, lock files and `wrapper.log` into public history, which is exactly what the PRD exists to prevent. Keep exit 0 and keep Phase 0 running, but emit one stderr line naming the path and the error (the `record_store` precedent), and pin it in the existing survives-a-failing-write tests. | File: skills/run-autopilot/cli/__main__.py:1227 | Task: 2
- 🟡 The `unreadable` case of `test_ensure_store_gitignore_never_reports_a_match_it_cannot_read` asserts nothing, because `except (OSError, UnicodeDecodeError): return` is an either-or hedge. I ran the writer on a mode-0 `.gitignore`: it raises PermissionError, because `write_text` cannot open a mode-0 file, so the contract bullet "an unreadable existing file counts as differing: write it" is not met and the test hides that. Make the test assert the contract (`wrote is True` and the body is rewritten), and make the writer unlink then rewrite if that is the intended behavior. Otherwise state in the contract and test that raising is the expected outcome and assert it. | File: skills/run-autopilot/cli/test_store_gitignore.py:47 | Task: 1
- 🟡 The new rotation instruction has no test. No test asserts that `_rotation_instructions` contains `record-store`, or `--site build` versus `--site review`. Deleting the sentence passes every test, and the design flagged this interpolation as a bug hazard. Only the older `assertNotIn("build", ...review...)` at test_autopilot_cap_breach.py:224 guards half of it. The task-boundary step h ordering (record-store after the `leave` row) is also unpinned, since `test_handoff_procedure_records_the_store_before_the_leave_row` covers only the core SKILL.md. The sentence is also not runnable as written: it says bare `autopilot record-store` where the script path is known from `__file__`. | File: skills/run-autopilot/scripts/autopilot_context_cap_hook.py:137 | Task: 5
- 🟡 Duplicated git-runner closure. `_store_repo.run_git` in `__main__.py` and `store_git.run_git` in `loop_act.py` are line-for-line the same: prefix from `custody.git_argv`, `cwd` passthrough, `check=True`, the 30 s timeout. Replace `_store_repo` with a call to the shared function (import `store_git` from `cli.loop_act`, or move it next to `git_argv` in `custody.py`) so there is one copy of the bare-repo `cwd` rule. | File: skills/run-autopilot/cli/__main__.py:1167 | Task: 4
- ⚪ `__main__.py` is 1278 lines against the 800-line limit. It was already over (pre-existing debt), but this diff adds 80 lines to it, against the design's estimate of about 25. Put the three store verbs in a sibling module registered like `wave_cli.add` instead of growing the file. | File: skills/run-autopilot/cli/__main__.py:1167 | Task: general
- ⚪ PRD wording and the implementation disagree on the record-store placement, and the test name is inverted. The PRD Behavior bullet puts the step "between the brief and the leave row". The code, SKILL.md step 2 and task-boundary step h put it after the row (the design's correction, which does satisfy the PRD's own "porcelain empty after the leave row" metric). `test_handoff_procedure_records_the_store_before_the_leave_row` asserts after, and its name is PRD-mandated. Amend the PRD text, or rename the test. Three gate sites also deliberately keep raw porcelain (the wave_launch.py abort check, `_land_cleanup`, the gate-failure.md ESCALATE guard) although the PRD says every gate is rewritten. | File: skills/run-autopilot/scripts/test_store_tree_prose.py:84 | Task: 7
- ⚪ `record_store`'s scoping guarantee ("another writer's staged file stays staged") is asserted only as argv shape against `FakeGit`. I checked it against real git by hand and it holds (an outside `b.txt` stayed `A `, and the store commit and a rename commit were clean). Add one real-git test so a refactor that keeps the argv but changes the outcome is caught. | File: skills/run-autopilot/cli/test_store_tree.py:280 | Task: 1
- ⚪ Consequence of site 10 still being deferred (noted, not a defect of this diff): with `/docs/` in `.git/info/exclude`, `git add -- :(top)docs/dev/project-management` is not a silent skip as the design claims. I reproduced exit 1 with "paths are ignored by one of your .gitignore files". Every loop iteration, the drained exit and every handoff will print `autopilot: store record failed: ...` until the exclude line is removed. Release this only together with the operator step, or have `record_store` treat an ignored store as "nothing to record". | File: skills/run-autopilot/cli/store_tree.py:102 | Task: general
- ⚪ Small cleanups. The `except` tuple in `record_store` includes `RuntimeError`, which nothing in production raises; it exists so one test can inject it, and the test could raise `CalledProcessError` instead. `_check_reviewable`'s docstring still says "any uncommitted change" although store churn is now exempt. | File: skills/run-autopilot/cli/wave_review.py:276 | Task: 3
- ⚪ Out-of-PRD change in range: the `intake` entry in `KNOWN_DIRS`, its test file, the CHANGELOG "Fixed" bullet and the release-checks line are unrelated to PRD 00236, which says the hook's refusal "stays as is". They are a deliberate stall fix and harmless, but they belong in their own PRD or commit. | File: hooks/enforce_prd_location.py:45 | Task: general

```
R1: fail
R2: fail
R3: pass
R4: fail
R6: pass
R7: pass
R8: pass
R9: fail
R10: fail
R11: pass
R12: pass
R13: fail
```

## Blake

Blind lens: PRD and rubric only, no diff, no file list, no review history. He located the
code himself and ran his own evidence (the PRD's pytest command gave 56 passed;
`autopilot dirty` printed nothing here; `git add --dry-run -- ":(top)docs/dev/project-management"`
exits 1 because `/docs/` is still in `.git/info/exclude`). No filesystem-notes block was
needed: `docs/dev/project-management` is not a symlink here and the project root does not
start with a dot. 1 High, 5 Medium, 3 Low.

- 🟠 `foreign_dirty` hard-codes `--untracked-files=all`. That overrides the `status.showUntrackedFiles=no` the operator sets on bare-repo-backed work-trees such as the `$HOME` dotfiles repo. `custody.git_argv` and `state.git_dir` support that shape. There, every untracked file in the work-tree counts as foreign dirt, and `autopilot dirty` always exits 1. The stand-down `dirty_tree` test would then fire on every session in that repo. The status call can also hit the 30 s timeout, and `dirty` does not catch that. The flag exists to stop a collapsed `?? docs/` entry reading as foreign. Handle that case without overriding the repo config for bare-backed repos. | File: skills/run-autopilot/cli/store_tree.py:62 | Task: general
- 🟡 Placement contradicts the PRD. The PRD says the record-store step goes "between the brief and the leave row". SKILL.md and the task-boundary handoff put it after the leave row, as the last write before STOP. The PRD's own metric (porcelain empty after every leave row) can only be met after the row, because the row appends to the tracked dispatch-metrics.jsonl, so the PRD is internally inconsistent. The design doc records this choice. The PRD-named acceptance test `test_handoff_procedure_records_the_store_before_the_leave_row` asserts the opposite of its name: its docstring says "after its leave row", and the body checks the record-store index is greater than the `record_dispatch.py handoff` index. The test passes without proving the property its name states. | File: skills/run-autopilot/scripts/test_store_tree_prose.py:84 | Task: general
- 🟡 Unrequested behavior. The loop driver calls `record_store(..., "loop", ...)` after every session, before `_act_branch`. That includes sessions that died, paused or stood down. The PRD names only the session handoff, the task-boundary handoff, the cap rotation and the drained exit. It adds at least one `chore(autopilot)` commit per session beyond the "about 15 per PRD" the PRD's Risks section budgets. The drained-exit call at loop_act.py:238 is in scope. | File: skills/run-autopilot/cli/loop.py:592 | Task: general
- 🟡 `STORE_GITIGNORE` has 23 patterns, but the PRD lists 18 and says "the pattern list above, in order". The extras are `.review-gate-blocks`, `.review-gate-failed`, `.lane-guard-blocks`, `wave.json` and `review-paths`. They came from the existing Disposable bullet, which already named them at f550a2e. The parity test forces the superset, so the PRD contradicts itself. The shipped file and the pinned test list (test_store_tree.py:683) both carry the superset, so `test_ensure_store_gitignore_writes_the_pattern_list` pins a list different from the spec's. | File: skills/run-autopilot/cli/store_tree.py:19 | Task: general
- 🟡 The PRD says every prose site that runs `git status --porcelain` for a gate is rewritten, and its acceptance test says no file under `skills/` outside `cli/store_tree.py` and tests "contains `status --porcelain` as a gate instruction". Several gates are still on raw porcelain: gate-failure.md:53 (the "uncommitted:" reset guard), rework-mode.md:20, wave_launch.py:441, wave_review.py:406. The design doc defends the destructive-step ones, but the test goes green only through a 10-entry allowlist (test_store_tree_prose.py:34) and scans `.md` files only. Once the store is tracked, the gate-failure.md guard will read "uncommitted" whenever store churn is present. That fails safe but takes the slow path. | File: skills/work/references/gate-failure.md:53 | Task: general
- 🟡 The store is still untracked in this checkout, because `/docs/` is still in `.git/info/exclude`. With that line present, `git add -- :(top)docs/dev/project-management` exits 1 ("paths are ignored"). So `record_store` prints a failure line at every handoff and commits nothing. The design doc says git "silently skips" an excluded path, which is wrong. The PRD's post-release metric cannot be exercised until the operator removes the line here and in claude-plugins. The PRD does not task this explicitly; the design does. | File: .git/info/exclude | Task: general
- ⚪ `autopilot dirty` exits 1 for "foreign paths found". An unresolved `--state` (`_walk_up_or_exit`) and any git failure (uncaught `CalledProcessError`/`TimeoutExpired`/`FileNotFoundError` traceback) also exit 1, with nothing on stdout. Prose gates read "comes back empty" (task-boundary-handoff.md:32). A failure that leaves stdout empty could be misread as clean. Catch git errors and use a distinct exit code. | File: skills/run-autopilot/cli/__main__.py:1195 | Task: general
- ⚪ With the store tracked, work/SKILL.md step 5's "any other dirty path is foreign ... name it in the phase report" rule will list store paths in every task report. It was not reworded to `autopilot dirty`. The PRD counted about 16 sites; the design accounts for fewer. | File: skills/work/SKILL.md:364 | Task: general
- ⚪ The PRD says paths are "compared on the repo-relative, normalized path". The code does a raw `startswith` on git's own output and never normalizes. It is correct for porcelain `-z`, but it is not the stated contract. The three new verbs also take an optional `--state` flag the PRD does not list. `pause.py` has no change; it has no git call, which the design explains. | File: skills/run-autopilot/cli/store_tree.py:72 | Task: general

```
B1: fail
B2: fail
B3: pass
B4: pass
B5: pass
B6: fail
B7: pass
B8: pass
B9: pass
B10: pass
B11: pass
B12: pass
B13: pass
B14: pass
B15: pass
B16: fail
B17: pass
B18: pass
B19: pass
```

## Bob

Doubt + de-slop lens, codex in its read-only sandbox. Ran first time, no retry, no
fallback. 2 High, 11 Medium, 2 Low, plus the FIX/VERIFY/KNOWN buckets and the D-rubric
verdicts.

- 🟠 Bare-backed projects set repo_root to $HOME, but fixed prefixes/pathspec target $HOME/docs rather than ~/.claude/docs; store dirt remains foreign and recording misses the actual store | File: skills/run-autopilot/cli/store_tree.py:15 | Task: general
- 🟠 review-once appends tracked ledger metrics after the session exits without recording them, leaving this session's final store writes uncommitted | File: skills/run-autopilot/cli/loop.py:487 | Task: general
- 🟡 Both lifecycle callers silently suppress .gitignore write failures; retain exit 0 but report the path and error on stderr | File: skills/run-autopilot/cli/__main__.py:1227 | Task: 2
- 🟡 The writer test returns successfully on OSError or UnicodeDecodeError even for missing-directory and invalid-UTF8 cases, accepting failure where rewriting is required | File: skills/run-autopilot/cli/test_store_gitignore.py:49 | Task: 2
- 🟡 Recorder tests inspect fake Git arguments without proving that real commits include additions/deletions and preserve another staged file | File: skills/run-autopilot/cli/test_store_tree.py:280 | Task: general
- 🟡 New task-boundary and cap-rotation record-store instructions lack tests pinning leave-row ordering and the interpolated build/review site | File: skills/run-autopilot/scripts/test_store_tree_prose.py:84 | Task: 5
- 🟡 _store_repo duplicates loop_act.store_git's resolver and subprocess closure; share one runner factory while preserving cwd, timeout and bare-repo behavior | File: skills/run-autopilot/cli/__main__.py:1167 | Task: general
- 🟡 STORE_GITIGNORE generates a fixed payload through a tuple and join; an equivalent multiline string makes the ordered file contents directly readable | File: skills/run-autopilot/cli/store_tree.py:19 | Task: 1
- 🟡 Supplied replay reports all three new layout tests passing against pre-change code; they do not pin the intake change | File: hooks/test_enforce_prd_location.py:24 | Task: general
- 🟡 Supplied replay reports seven new assembly refusal cases passing against pre-change code; strengthen them to distinguish store churn from foreign dirt | File: skills/run-autopilot/cli/test_wave_assemble.py:473 | Task: general
- 🟡 The changed launch runner assertion accepts the old status invocation; supplied replay confirms it passes before the change | File: skills/run-autopilot/cli/test_wave_launch.py:516 | Task: general
- 🟡 Supplied replay reports all six new launch refusal cases passing against pre-change code; add store-only positive controls to pin the new distinction | File: skills/run-autopilot/cli/test_wave_launch_refusals.py:158 | Task: general
- 🟡 Supplied replay reports all five new review refusal cases passing against pre-change code; assert that refusal diagnostics exclude store paths | File: skills/run-autopilot/cli/test_wave_review.py:697 | Task: general
- ⚪ __main__.py remains 1,278 lines, exceeding the 800-line limit; the context identifies this as pre-existing debt | File: skills/run-autopilot/cli/__main__.py:1 | Task: general
- ⚪ Cannot statically verify: a tracked-store batch produces no store-caused dirty_tree stand-downs and finishes each handoff with clean Git status | File: N/A | Task: general

```
R1: fail
R2: fail
R3: pass
R4: fail
R6: pass
R7: pass
R8: pass
R9: fail
R10: fail
R11: pass
R12: pass
R13: fail
```

FIX:

- Bare-backed store paths — skills/run-autopilot/cli/store_tree.py:15 — Derive the project's store location from the state directory, express it relative to Git's work-tree root, and test a nested `.claude` project.
- Unrecorded review-once metrics — skills/run-autopilot/cli/loop.py:487 — Record the store after `_append_metrics` in `_run_once`; test ordering and continuation on recording failure.
- Silent ignore-file failures — skills/run-autopilot/cli/__main__.py:1227 — Emit one stderr diagnostic from both lifecycle callers while preserving successful exit behavior.
- Writer-test exception hedge — skills/run-autopilot/cli/test_store_gitignore.py:49 — Require successful rewriting for missing-directory and invalid-UTF8 cases; isolate unreadable-input handling with deterministic fault injection.
- Recorder integration coverage — skills/run-autopilot/cli/test_store_tree.py:280 — Add temporary-repository tests asserting committed additions/deletions and preservation of a staged foreign file.
- Handoff instruction coverage — skills/run-autopilot/scripts/test_store_tree_prose.py:84 — Pin task-boundary row-before-record ordering and cap-rotation record-store instructions for both build and review.
- Duplicate runner construction — skills/run-autopilot/cli/__main__.py:1167 — Share the existing resolver-and-runner construction between CLI and wrapper callers.
- Generated constant payload — skills/run-autopilot/cli/store_tree.py:19 — Replace the tuple/join with an identical multiline string.
- Layout replay survivors — hooks/test_enforce_prd_location.py:24 — Strengthen coverage through the actual editor-hook boundary so the intake acceptance case distinguishes the pre-change implementation.
- Assembly replay survivors — skills/run-autopilot/cli/test_wave_assemble.py:473 — Pair foreign-refusal cases with store-only acceptance controls.
- Launch runner replay survivor — skills/run-autopilot/cli/test_wave_launch.py:516 — Require the NUL-delimited status invocation with `--untracked-files=all`.
- Launch refusal replay survivors — skills/run-autopilot/cli/test_wave_launch_refusals.py:158 — Add store-only acceptance controls within the parametrized scenarios.
- Review refusal replay survivors — skills/run-autopilot/cli/test_wave_review.py:697 — Assert foreign paths appear and dirty store paths do not appear in refusal diagnostics.

VERIFY:

- Post-release batch behavior — After the operator completes the deferred tracking configuration, run a batch with the store tracked; check telemetry for store-caused `dirty_tree` stand-downs and capture Git status after session and wrapper recording. **Not queued: command shape** — it names a post-release batch observation, not one runnable command, and it is gated on the deferred operator step. Recorded as a deferral instead, so it stays visible at batch end.

KNOWN:

- Existing file-size debt — skills/run-autopilot/cli/__main__.py:1 — The context explicitly identifies the pre-existing oversized dispatcher; splitting the whole CLI exceeds this PRD's store-tracking scope.

```
D1: pass
D2: pass
D3: pass
D4: pass
D5: pass
```

## Carl

Gemini lens on backend=copilot, model=gemini-3.8-flash. Reviewed as a generalist (no
frontend surface in this diff) and ran the store suites himself. 2 Medium, and he passed
every rubric rule — the panel's most lenient read this cycle.

- 🟡 Redundant git runner closure duplicated between CLI store subparser and loop_act | File: skills/run-autopilot/cli/__main__.py:1181 | Task: 2
- 🟡 Test function name contradicts its assertion order | File: skills/run-autopilot/scripts/test_store_tree_prose.py:84 | Task: 7

```
R1: pass
R2: pass
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: pass
R10: pass
R11: pass
R12: pass
R13: pass
```

## Mechanical blocks (computed, absorbed into the table)

Tautological-shape check: 126 test functions across 10 test files, **no `[MECH]` lines** —
no constant, self-comparing or hedged assert shapes found by the scanner. (The either-or
hedge Alice and Bob both found by reading is in an `except` arm, which this scanner does
not model; that is why the human lenses still matter.)

Fail-first replay against `23bf974`: 26 touched tests ran, 4 failed at base, **22 passed**;
4 test files could not be collected at base. Five `[MECH]` lines, all absorbed onto rows
the doubt lens had already raised, with `mech-check` appended as a finder. All five are
queued in rework task 13.

## Follow-up tasks created

Eight `[D1]` rework tasks, ids 9–16. No 🔴 CRITICAL row, so no rework design doc was
required and the `default_model: opus` floor does not apply; tiers are the classifier's
call.

1. id 9 (L, opus) — Derive the store boundary from the work-tree instead of assuming a top-level `docs/` — 🟠 3/4
2. id 10 (L, opus) — Keep store commits out of lane routing and out of wave lane branches — 🟠 ×2 + 🟡
3. id 11 (S, sonnet) — Record the store on the `review-once` exit path — 🟠
4. id 12 (M, sonnet) — Make store failures legible: `dirty`'s exit codes, gitignore write errors, ignored-store recording — 🟡 ×3 + ⚪ ×2
5. id 13 (L, sonnet) — Make the new store tests able to fail: replay survivors, real-git recording, writer hedges — 🟡 ×8 + ⚪
6. id 14 (S, sonnet) — Pin the cap-rotation and task-boundary record-store instructions — 🟡 ×2
7. id 15 (S, sonnet) — Collapse the duplicated store git-runner closure into one — 🟡 3/4
8. id 16 (S, sonnet) — Store-tracking cleanups: dead `except` arm, stale docstring, missed `work/SKILL.md` dirt site, gitignore literal — 🟡 + ⚪ ×2

One decision was taken on the gate's own authority rather than escalated: Alice asked for
an operator choice between skipping store recording inside wave lanes and defining how
lane store commits merge. The gate chose **skip** — additive, non-destructive, no new
merge semantics, and it cannot lose work because a lane's store writes stay in its
worktree exactly as today. Recorded in `autonomous_decisions` and in task 10 as settled.

Seven findings were deferred to batch end (all requirements ambiguities or pre-existing
debt already adjudicated in the design doc) and are recorded in both the batch deferred
JSON and the settled-decisions ledger, so no later cycle re-argues them.

Verdict: 30 findings
Tests: 2064 passed, 0 failed, 0 skipped (reused from last-verification.json at 5ab1a1fdca6dc9cf7c885ae6fe2f69b2350cb8b3)
