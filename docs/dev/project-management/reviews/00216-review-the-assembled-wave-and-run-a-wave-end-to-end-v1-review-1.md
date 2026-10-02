---
prd: dev/local/prds/wip/00216-review-the-assembled-wave-and-run-a-wave-end-to-end-v1.md
review: 1
date: 2026-09-28
head_sha: fc5e559feb59baa9320f17127ed8ed6b8870cfa0
codex_thread_id: 01a0e9e5-9c75-7cb3-9e4f-3e236de8b1e3
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00216-review-the-assembled-wave-and-run-a-wave-end-to-end-v1

Diff range: `5f0acd5ec83bd59227ee3245e4ed648ec3390a39..fc5e559feb59baa9320f17127ed8ed6b8870cfa0`

codex_rung_guard: not fired

## Run conditions

- **Scope label caveat (fail loud).** `gather-context.sh` was invoked with `--since 5f0acd5…` and so labels the context file `incremental review`. This is a **full cycle-1 review**: the repo works directly on `master`, so the script's own branch-base diff (`git diff master`) was empty, and `state.work_start_sha..HEAD` is the PRD's whole work range. Reviewers were told this explicitly in their prompts.
- **Out-of-range commit inside the diff.** `5d9036a` ("finish the tracked-store migration") is in the range but not in PRD 00216's task plan. Reviewers were told to report defects anywhere but not to score 00216 against it.
- **Context pack:** `engram pack` failed (`not inside a registered repo; register it in ~/.config/gita/repos.csv`). Substituted `(no pack available this cycle)`; no retry, the failure is deterministic. Review degraded, not invalid.
- **Bob prompt shape (deviation, recorded).** Bob was dispatched with the **inlined** prompt (review context + full diff inlined verbatim, per `references/retry-policy.md` § Inlined retry prompt) on the FIRST dispatch rather than after a lack-of-input refusal, because this repo has a recorded history of the codex reviewer failing on path references. He returned a complete review with all twelve `R{n}` and all five `D{n}` lines on the first run; no retry was spent.
- **Consolidation:** `consolidate_findings.py`, 4 reviewers, no ledger (cycle 1). It reported citation merges after suffix stripping on rows 1, 2, 3 and 6.

## Alice (consensus lens)

Ran pytest on `test_wave_review.py` and `test_wave_docs.py`: 45 passed. Did not run `release-checks` or `test_gather_context_paths.sh`.

Found the cycle's CRITICAL by direct reproduction, plus 4 High, 10 Medium and 5 Low. Full text: `dev/local/tmp/alice-output-00216c1.txt`.

R1: fail
R2: fail
R3: pass
R4: fail
R6: pass
R7: fail
R8: pass
R9: fail
R10: pass
R11: pass
R12: fail
R13: fail

## Blake (blind lens — PRD only, no diff)

Ran `test_wave_review.py` (41 passed), both gather-context shell tests, and `release-checks` (green, waves block 280 passed).

Independently reproduced the same CRITICAL from the spec alone, without ever seeing the diff, and ran both invocation forms (`wave run` and `wave run --state …`). Full text: `dev/local/tmp/blake-output-00216c1.txt`.

B1: fail
B2: fail
B3: fail
B4: pass
B5: fail
B6: pass
B7: pass
B8: pass
B9: pass
B10: pass
B11: pass
B12: fail
B13: pass
B14: fail
B15: pass
B16: fail
B17: pass
B18: pass
B19: pass

Blake's own verdict notes: B17 holds vacuously (the PRD has no Phase 3); B18/B19 hold because the PRD names no explicit out-of-scope section.

Leftover from Blake's CLI probe: an empty `git init` repo at `/tmp/blake-wave-probe`. Harmless, outside the repo; `rm` is warden-gated so he left it.

## Bob (codex — consensus + doubt/de-slop lens)

Static-only sandbox, inlined prompt. 13 findings. Full text: `dev/local/tmp/bob-output-00216c1.txt`.

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

Doubt buckets: 13 FIX, VERIFY `- (none)`, KNOWN `- (none)`.

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl (gemini — frontend/design specialist, generalist here)

Backend: copilot. Ran `test_wave_review.py`, `test_gather_context_paths.sh` and `release-checks` himself, and ran `check_style_limits.py` over the changed Python files. 10 findings, no frontend surface in this diff. Full text: `dev/local/tmp/carl-output-00216c1.txt`.

R1: pass
R2: fail
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: fail
R10: pass
R11: pass
R12: fail
R13: fail

## Mechanical checks (computed)

Absorbed into the table below as the `mech-check` finder on three existing rows; they added no new row.

- Tautological shapes: `test_stub_prd_lists_the_diff_scope` (`test_wave_review.py:127`) and `test_null_byte_blocks_common_repair_without_aborting` (`test_codex_hook_doctor_extra.py:641`) each hedge with `or`. 88 test functions checked across 6 files.
- Fail-first replay against `5f0acd5ec83b`: 3 touched tests ran, 1 failed at base, 2 passed there — `test_custody_journal_section_lists_events_compaction_durability_and_locator` and `test_check_resolves_new_aegis_rooted_known_hooks_against_aegis_root`, both from commit `5d9036a`. 1 test file could not be collected at base (`test_wave_review.py`, a new module — expected).

## Consolidated Findings

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [2/4] | 🔴 | `autopilot wave run` crashes on every real invocation: `run_p` registers no `--state`, but `__main__._run_wave` reads `args.state` first. Reproduced: `python3 skills/run-autopilot/cli/__main__.py wave run` exits 1 with `AttributeError: 'Namespace' object has no attribute 'state'` before `wave_run.run` is reached; `wave run --state …` is rejected as an unrecognized argument. The PRD's headline verb, the documented `autoclaude wave` alias and the CHANGELOG entry advertising it are all unusable. `test_wave_cli_registers_review_land_run_as_wave_subverbs` only parses argv and every `test_run_*` calls `wave_run.run` directly, so no test goes through `main()` | skills/run-autopilot/cli/wave_cli.py:29 | 5 | ALICE, BLAKE |
| [4/4] | 🟠 | The confirmation gate is a no-op on a TTY. The PRD says "unless `--yes`, wait for Enter on a TTY". `run` only refuses when there is no TTY and no `--yes`, and never calls `input()`. An operator at a terminal who omits `--yes` launches N lane loops immediately (moving PRDs and creating worktrees unconfirmed), so `--yes` does nothing there. The plan table is not shown before the gate either, because the gate sits before `plan`. No test covers the TTY-without-yes branch | skills/run-autopilot/cli/wave_run.py:75 | 5 | ALICE, BLAKE, BOB, CARL |
| [4/4] | 🟠 | `land` never appends the `## Assembly review: …` line to the wave summary, on either outcome. The `review_failed` branch just returns 4; the converged line is absent too. `rg "Assembly review"` finds no writer anywhere under `skills/run-autopilot` (0 matches, 241 files, against a working control). The PRD's Land behavior requires it for both outcomes and its post-release success signal (`reports/<wave id>-wave.md` ends with `## Assembly review: converged`) cannot occur. `run()` also skips `land()` entirely on `review_failed`, so even the failure line has no caller. No test pins either line | skills/run-autopilot/cli/wave_review.py:347 | 4 | ALICE, BLAKE, BOB, CARL |
| [1/4] | 🟠 | The documented interrupt-resume path is broken. The handler writes `status: "interrupted"`, which is not in `WAVE_STATUSES` (verified: `_TOP_CHECKS["status"]("interrupted")` is False). `_structural_errors` then rejects the file, so `wave assemble`, `plan`, `launch` and `abort` all refuse it, and `assemble._refusals` admits only running/assembled/assembled_partial. The PRD, `waves.md` and the CHANGELOG all promise `wave assemble` resumes from there. `test_run_interrupt_terminates_lane_groups` asserts the string but never checks it against the pack's own validator. The handler also saves without `wave.locked` | skills/run-autopilot/cli/wave_run.py:34 | 5 | ALICE, BLAKE |
| [1/4] | 🟠 | `land` is not resumable across its destructive steps. The design requires saving `status: "done"` and the refreshed `head_sha` BEFORE `git worktree remove` and `git branch`; the code removes the worktree and branch first (`wave_review.py:365-366`) and saves afterwards (`:368-372`). A kill between them leaves status `converged` with the worktree gone; the retry then sets `resolved_assembly_tip = repo_head`, merge and migrate pass as no-ops, and `worktree remove --force` on the missing path raises `CalledProcessError`, wedging the wave until hand-edited. `test_land_resumes_after_a_migration_crash` covers only a crash inside migration | skills/run-autopilot/cli/wave_review.py:365 | 4 | ALICE, BOB |
| [1/4] | 🟠 | Cross-cutting premise conflict: the store is tracked, but every dirty-tree check assumes it is ignored. `docs/dev/project-management/` is not gitignored in this repo (verified: `git check-ignore` exits 1, `git status` shows `?? docs/`), while the design's `## Architecture fit` asserts it is "gitignored everywhere" and the test fixture writes that gitignore line (`test_wave_launch.py:71`). `wave.json` and `assemble`'s reports therefore make `git status --porcelain` non-empty, so `_check_reviewable` refuses with `ValueError` in this very repo. `launch`'s existing dirty check trips the same way. Commit `5d9036a` in this range states "the store is tracked and never age-purged" | skills/run-autopilot/cli/wave_review.py:244 | 2 | BLAKE, BOB, ALICE |
| [1/4] | 🟠 | `land` is not usable after a hand review, contradicting the PRD's Edge scenario ("a later `wave land` after a hand review still lands") and its "own verb so an operator who reviewed by hand can still land" line. `review_failed` returns 4 unconditionally; `assembled`/`assembled_partial` raise an uncaught `ValueError`. Only `converged` proceeds, and only the loop's own review sets it | skills/run-autopilot/cli/wave_review.py:346 | 4 | BLAKE |
| [3/4] | 🟡 | `test_wave_review.py` is 1141 lines against the 800-line ceiling. The style gate flagged it at 804 lines (task 4) and 1073 lines (task 5) and it was not split either time. Move the `test_run_*`, docs and cli tests into their own file (e.g. `test_wave_run.py`, which also needs a `release-checks` and `_WAVE_TEST_FILES` entry) | skills/run-autopilot/cli/test_wave_review.py | general | ALICE, BOB, CARL |
| [3/4] | 🟡 | `stub_text` folds the contract's separate `Inputs`, `Outputs` and `Behavior` items into one `Inputs/Outputs/Behavior:` label listing only keep-both text. The PRD asks for Description, Inputs, Outputs and Behavior naming each merged lane and its resolutions. `plan-tasks` still parses it, but it is not the specified shape | skills/run-autopilot/cli/wave_review.py:78 | 1 | ALICE, BLAKE, BOB |
| [2/4] | 🟡 | `land` does not hold `wave.json`'s lock for its body, unlike `assemble`. It loads under lock, releases, does the merge and migrate with separate short lock/save cycles, then saves and archives unlocked. The design requires the whole body locked "exactly like `assemble()`" | skills/run-autopilot/cli/wave_review.py:343 | 4 | ALICE, CARL |
| [2/4] | 🟡 | Precondition and git failures escape `review`, `land` and `wave run` as raw tracebacks: `ValueError` from `_check_reviewable`, `RuntimeError` from `seed_state`, `CalledProcessError` from git, `KeyError`/`FileNotFoundError` from `installed_plugins.json`. `wave_cli` catches none of them for these verbs, though `assemble`/`launch` print `autopilot: …` and return 1. The PRD says `wave run` exits 1 on a precondition refusal, and `waves.md` claims the propagation is "like every other precondition check in this pack", which is false. `land` also returns 4 and 5 with nothing on stderr | skills/run-autopilot/cli/wave_cli.py:73 | 5 | ALICE, BLAKE |
| [2/4] | 🟡 | `wave_cli.run` is 51 lines after this diff, over the 50-line limit (the computed mechanical-facts block agrees: `run` — line 35, 51 lines) | skills/run-autopilot/cli/wave_cli.py:35 | 5 | ALICE, CARL |
| [2/4] | 🟡 | `test_stub_prd_lists_the_diff_scope` hedges with `or` (`path in lines or f"- {path}" in lines`), so either outcome passes. `stub_text` emits exactly `- {path}`; pin that form | skills/run-autopilot/cli/test_wave_review.py:127 | 1 | ALICE, BOB, CARL, mech-check |
| [1/4] | 🟡 | `land` does not delete `wave-slots/`, which the PRD requires. The only code that removes it is `wave abort`, whose own comment warns that leaked slots starve the next wave | skills/run-autopilot/cli/wave_review.py:365 | 4 | BLAKE, CARL |
| [1/4] | 🟡 | `wave.json` is copied to `reports/<id>-wave.json`, not moved. The original stays at `autopilot/wave.json` with status `done`. PRD: "move it to `reports/<wave id>-wave.json`" | skills/run-autopilot/cli/wave_review.py:368 | 4 | BLAKE, ALICE, CARL |
| [1/4] | 🟡 | When the assembly worktree directory is missing, the "master moved" guard is a no-op: `resolved_assembly_tip` falls back to `repo_head`, so `repo_head not in (base_sha, tip)` can never be true. `land` then does a no-op merge and `worktree remove` errors. The design requires resolving the branch tip directly with `rev-parse wave/<id>/assembly`, never the recorded or substituted value | skills/run-autopilot/cli/wave_review.py:354 | 4 | BLAKE, BOB |
| [1/4] | 🟡 | `review` and `land` skip `_structural_errors`, though `assemble` and `abort` run it. `id`, `assembly.worktree` and `base_sha` come straight from `wave.json` and feed the stub filename, the `reports/<id>-wave.json` path and `git worktree remove --force <worktree>`. A hand-edited `id` such as `../x` is not refused on these two verbs, so the CHANGELOG line "every `autopilot wave` verb now refuses a `wave.json` whose `id` is not a plain basename" is untrue | skills/run-autopilot/cli/wave_review.py:234 | general | BLAKE |
| [1/4] | 🟡 | `land` runs `git worktree remove --force` with no check for uncommitted source edits in the assembly worktree. Only the artifact migration happens first, so uncommitted rework is lost after the fast-forward | skills/run-autopilot/cli/wave_review.py:365 | 4 | BLAKE |
| [1/4] | 🟡 | Signal handling covers only the lane wait loop. A SIGINT/SIGTERM during the nested review is not caught; the review loop is a `start_new_session` process and is orphaned, the run stops with a traceback, and the wave stays `assembled` with a half-seeded worktree. The design named this a deliberate, documented gap; it is recorded here so the decision is visible rather than silent | skills/run-autopilot/cli/wave_run.py:40 | 5 | BLAKE |
| [1/4] | 🟡 | `--review-slots` is written into `wave.json` with no validation and no test. Any int is accepted; `0` or a negative value makes `_TOP_CHECKS["review_slots"]` (`> 0`) fail, `launch` refuses, and a later `plan` refuses the "structurally invalid" file, leaving a poisoned `wave.json`. No test exercises the `review_slots != 3` branch | skills/run-autopilot/cli/wave_run.py:83 | 5 | ALICE |
| [1/4] | 🟡 | The 10-minute status cadence is untested. `_rising_clock` jumps 700s on every call, so a `run` that printed the table on every 30s poll would pass. Add a case where the clock advances less than 600s and asserts no `status` call, plus one that crosses 600s | skills/run-autopilot/cli/test_wave_review.py:880 | 5 | ALICE |
| [1/4] | 🟡 | Simplification: `_check_reviewable` re-implements `git status --porcelain` with a raw `subprocess.run` although `_default_run_git` is already imported, bypassing the injectable git seam the pack uses everywhere else. `review()` also re-implements `_spawn_lane`'s env and Popen recipe (11 lines) | skills/run-autopilot/cli/wave_review.py:244 | 2 | ALICE |
| [1/4] | 🟡 | Simplification: `gather-context.sh` duplicates its `git diff` invocation across branches; build a shared path-args array instead | skills/review-work-completion/scripts/gather-context.sh:123 | 3 | CARL |
| [1/4] | 🟡 | Two changed tests pass against the pre-change code, so they do not pin their stated migration claims (out of PRD 00216's scope — both belong to commit `5d9036a`) | skills/run-autopilot/cli/test_custody_prose_schema.py:105 | general | BOB, mech-check |
| [1/4] | 🟡 | An either-or assertion whose outcome cannot fail as written (out of PRD 00216's scope — pre-existing, in commit `5d9036a`'s file) | skills/use-codex/scripts/test_codex_hook_doctor_extra.py:641 | general | BOB, CARL, mech-check |
| [1/4] | ⚪ | Signature drift from the PRD's Exports. `seed_state`'s `run_cli` and `review`'s `spawn_fn` lost the keyword-only `*`. The `meta/` copy the task assigns to `seed_state` lives in `review()` instead, so `seed_state` alone does not copy `meta/`. `review` has no `run_git` seam at all | skills/run-autopilot/cli/wave_review.py:212 | 2 | ALICE |
| [1/4] | ⚪ | Docs and comment drift: `test_wave_review.py`'s module docstring still says `wave_run.py` is "not yet implemented - they fail with ImportError"; `wave_run.py`'s docstring cites "PRD 00214 follow-on" (should be 00216); `state-schema.md`'s wave.json row shows `assembly` as `{"worktree","branch"}` only, though the code reads `head_sha`, `merged` and `kept` | skills/run-autopilot/cli/test_wave_review.py:491 | 5 | ALICE |
| [1/4] | ⚪ | `waves.md` § wave run omits the alias line `caffeinate -is python3 "$_skill/cli/__main__.py" wave run "$@"`, which the PRD lists as required doc content | skills/run-autopilot/references/waves.md:233 | 5 | BLAKE, ALICE |
| [1/4] | ⚪ | The `review-paths` row in `state-schema.md` does not say the file is removed with the assembly worktree, and the bash test is registered under its own `[checks] gather-context paths` block rather than inside the `[checks] waves` block the PRD names | skills/run-autopilot/references/state-schema.md:253 | 5 | BLAKE |
| [1/4] | ⚪ | When every lane is kept (`assemble` returns 3 with `merged: []`), `run` still spawns a full-roster review over an empty assembly and then "lands" a no-op | skills/run-autopilot/cli/wave_run.py:94 | 5 | ALICE |
| [1/4] | ⚪ | `land()` calls `branch -d` instead of the design's `branch -D` (safe after the ff merge, but a deviation) | skills/run-autopilot/cli/wave_review.py:360 | 4 | CARL |
| [1/4] | ⚪ | The PRD's literal paths (`dev/local/…`) are implemented as `docs/dev/project-management/…`. This matches the repo-wide migration and is consistent everywhere, recorded only as a literal-spec deviation (the design doc made this correction deliberately) | skills/review-work-completion/scripts/gather-context.sh:116 | 3 | BLAKE |
| [1/4] | ⚪ | Fail-first replay note (commit `5d9036a`, outside 00216's compliance scope): two of its touched tests pass against the pre-change code because the commit is renames and prose swaps only | skills/use-codex/scripts/test_codex_hook_doctor_extra.py:641 | general | ALICE |

Verdict: 33 findings
Tests: 1795 passed, 0 failed, 0 skipped (suite run this cycle)

`bash dev/bin/release-checks` exit 0, run twice this cycle at `fc5e559`. Composition: 1368 pytest + 303 subtests + 124 shell assertions. `dev/local/autopilot/last-verification.json` matched this HEAD but carried null counts, so its record could not be reused and the suite was run fresh — the counts above are this cycle's own run, not a reused record.
