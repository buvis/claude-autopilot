---
prd: dev/local/prds/wip/00214-plan-and-launch-a-wave-of-lanes-v1.md
review: 2
date: 2026-09-26
head_sha: 0f476c54b7f8249705f6a81f425a4d9a2875a9c6
codex_thread_id: 01a0dc90-8e96-7e00-ad58-d201618f8a35
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00214-plan-and-launch-a-wave-of-lanes-v1

Diff range: `b8b6b17cb989385cf34baaca4957b282b0690aaf..0f476c54b7f8249705f6a81f425a4d9a2875a9c6`

codex_rung_guard: not fired

pack: failed (engram: "not inside a registered repo; register it in /Users/bob/.config/gita/repos.csv"; retried once, same result — identical to cycle 1). `{PACK_FILE}` and `{PACK_FINDINGS}` were substituted with `(no pack available this cycle)` for every reviewer that takes them. The review is degraded on retrieval context, not invalid.

## Review Summary

Reviewed: 6 completed tasks (4 original + rework tasks 5 and 6)
PRDs checked: 00214-plan-and-launch-a-wave-of-lanes-v1

### Agent Status

- Alice: ✅ Available (Claude subagent, consensus lens; ran the six in-scope wave suites herself — 177 passed, 0 failed)
- Blake: ✅ Available (Claude subagent, blind/PRD-only lens; ran the PRD's named Success-Metric invocation — 137 passed — plus the three CI-orphaned files directly — 14 passed)
- Bob: ✅ Available (codex, read-only sandbox; consensus + doubt/de-slop lens, `D1`-`D5` emitted; resumed his cycle-1 thread `01a0dc90` via `--resume-thread`, first try, no retry)
- Carl: ✅ Available (gemini via copilot backend; ran the wave suites and `release-checks` — twice, once after unsetting the nested-dispatch env vars — and reported no issues)

### Cycle mechanics worth recording

1. **Scope: this was an INCREMENTAL review, not a full one.** The session brief asserted the range was `work_start_sha..HEAD` (`14da0ce8..0f476c5`), but the skill's own rule is explicit — a prior review file with a `head_sha` makes the cycle incremental and scopes the diff with `--since <that sha>`. The skill's rule was followed and the brief's line was not. The resulting diff is 1828 lines over 23 files, non-empty, so cycle 1's empty-diff trap (`gather-context.sh` resolving its full-review base to `master`, the branch this PRD is built on) did not recur — `--since` bypasses that resolution entirely. That latent `gather-context.sh` defect is still unfixed and is still out of this PRD's scope.
2. **Two commits in the incremental range belong to another PRD.** `9bc679c` ("unblock reviewer lanes, hand off before the cap, name the CLI") and `52b470a` ("chore: release v0.5.6") are an out-of-band operator hotfix that landed between cycle 1's review and this PRD's rework, so `b8b6b17c..HEAD` carries them and the ten files they own. Every reviewer prompt named those commits and those files as out of scope, with the in-scope file list beside them. No reviewer raised a finding against them, so no misattribution occurred — but the range itself is wider than this PRD's work, and that is a property of taking the prior cycle's `head_sha` as the base when unrelated commits interleave.
3. **`consolidate_findings.py` over-merged one row again, and said so on stderr.** Its suffix-stripping citation match folded Alice's `_worktree_line` fallback finding (`wave_launch.py:449`) together with Bob's `status`-trusts-`Path.exists()` finding (`wave_launch.py:319`) — two different defects that happen to sit in one file. **The table below splits them back out by hand** and restores Bob's own ⚪ severity, which the merge had promoted to 🟡. Its other merge (row 1, `release-checks:107 ~ :108`) was correct: Alice, Blake and Bob all described the same defect, so the 3/4 consensus there is real. Consolidation was otherwise the script's, unmodified.
4. **No verification-check queue was written this cycle.** Bob's single VERIFY item chains two commands (the seven-file pytest invocation `then bash dev/bin/release-checks`), which the queue forbids — recorded below as `not queued: command shape`, exactly as in cycle 1. No `checks-2.json` exists, and there was no `checks-1.json` to carry forward.
5. **The `Tests:` line is reused, not freshly run.** `dev/local/autopilot/last-verification.json` records `sha: 0f476c54…` — this cycle's reviewed HEAD — with non-null counts, so the skill's reuse path applies and no suite was re-run by the gate. That record covers `release-checks` (exit 0) and the `skills/run-autopilot/cli/` suite (exit 0). Three reviewers independently ran suites this cycle anyway; their counts are in their sections and agree.

## Consolidated Findings

Consensus is over N=4 reviewers. The row marked **(split)** was separated by hand from the over-merged script row (mechanics note 3); its consensus and severity are restated from the source output. Rows marked **(mech-check)** absorbed a computed `[MECH]` line from the context's fail-first replay block.

| Consensus | Severity | Issue | File | Task | Found By | Gate verdict |
|-----------|----------|-------|------|------|----------|--------------|
| [3/4] | 🟡 Medium (regraded from 🟠) | `dev/bin/release-checks`' `[checks] waves` block runs only `test_wave.py`, `test_wave_launch.py`, `test_wave_launch_status.py` and `test_wave_launch_abort.py`. Task 6 split three more test files off the wave suite — `test_wave_launch_abort_keep.py`, `test_wave_launch_abort_kill.py` (the kill-race/`ProcessLookupError` HIGH fix), `test_wave_launch_refusals.py` (live-loop refusal, non-canonical `--state`, failed-worktree-listing) — and wired none of them into the release gate or anything else | dev/bin/release-checks:107 | 6 | ALICE, BLAKE, BOB | **CONFIRMED, regraded to Medium.** Verified directly: `rg` over the repo (excluding `dev/local/`) finds the three basenames nowhere, while the control term `test_wave_launch_status` hits `release-checks` — so the search shape is proven and the absence is real. **Regraded** because Blake and Bob, the two who actually ran `release-checks` and the orphan files, both rated it 🟡; only Alice said 🟠, and `consolidate_findings.py` takes the max. Nothing shipped misbehaves (all 14 orphan tests pass), the PRD's literal Success Metric names only two test files and the block already exceeds it with four, and the exposure is future-regression-only. Cycle 1 rated the identical class of gap 🟡 and fixed it as a one-line extension. **Swept this cycle** — see Tail sweep. |
| [1/4] **(split)** | 🟡 Medium | `_worktree_line`'s fallback silently drops the operator-facing reason: for a kept worktree `git worktree list` does not list, `_clean_up_lane` prints a bare path with no `autopilot:` prefix and no explanation, where the pre-rework `_keep_reason` printed `autopilot: keeping <path>: this wave never recorded creating it`. No test exercises the branch | skills/run-autopilot/cli/wave_launch.py:449 | 6 | ALICE | CONFIRMED — a regression task 6's own output-splitting fix introduced on its fallback path. **Swept this cycle.** |
| [1/4] | 🟡 Medium | `_run_wave` accepts `--state <repo>/dev/local/autopilot/anything.json`: the canonical-path check compares only the three-part directory tail and ignores the `state.json` basename | skills/run-autopilot/cli/__main__.py:1156 | 6 | BOB | CONFIRMED — a residue of task 6's own `assert`-to-refusal fix. Nothing unsafe follows (the repo root still resolves correctly), but a typo'd filename is accepted silently. **Swept this cycle.** |
| [1/4] | ⚪ Low | `references/waves.md` says every kept-worktree reason is printed, but the commit and ownership cases now print only git's listing line | skills/run-autopilot/references/waves.md:100 | 6 | BOB | CONFIRMED — the doc half of task 6's output change, coupled to the `_worktree_line` row above. **Swept this cycle.** |
| [1/4] **(split)** | ⚪ Low | `status` still treats any existing directory as a worktree instead of consulting git's worktree registry | skills/run-autopilot/cli/wave_launch.py:319 | 3 | BOB | **Settled deferral.** Cycle 1 ruled the same finding design-accepted: the design's `status(repo, wave) -> str` signature carries no `run_git` seam, so `status` structurally cannot consult git. Cycle 1 failed to write it to the ledger, which is why it re-raised; it is written there now. |
| [1/4] | 🟡 Medium | `plan`, `validate`, `launch` and `abort` diverge from the PRD's Module Exports signatures (they take `repo`/`wave_path` rather than a loaded `wave` dict) | skills/run-autopilot/cli/wave.py:225 | general | BLAKE | **Settled deferral.** Cycle 1 ruled every one of these design-conformant: the reload-under-lock shape is the design's own concurrency fix. Cycle 1 left them out of the ledger, so `--ledger-dismiss BLAKE` could not suppress them; written to the ledger now. |
| [1/4] | 🟡 Medium | `Lane.as_dict()` carries `worktree_created` and `abort_error`, and the status table an `abort_error` column, none of which appear in the PRD's stated shapes | skills/run-autopilot/cli/wave.py:32 | general | BLAKE | **Discarded — design-mandated.** Both fields are required by the reviewed design doc: `worktree_created` is dispatch 3's own blocker fix (path+branch matching at minute-resolution cannot prove this launch created the worktree) and `abort_error` is in the design's abort contract. Blake, blind by construction, could not see the design. Additive and non-breaking. Ledgered. |
| [2/4] **(mech-check)** | 🟡 Medium | 48 touched `test_wave.py` cases pass against the pre-change implementation, failing the strict fail-first criterion | skills/run-autopilot/cli/test_wave.py:571 | general | BOB, mech-check | **Discarded — computed fact, not a defect here.** The diff appends four `pid` rows and two `base_sha` rows to existing parametrize lists, so the replay marks each whole test *function* touched while its 48 pre-existing cases are untouched sibling and positive-control cases. Forcing them red would require changing unrelated production behavior. The skill's own rule for a replay row: a behavior-preserving addition's neighbours pass by design, and the gate may dismiss with that reason. Ledgered. |
| [2/4] **(mech-check)** | 🟡 Medium | Two touched abort tests pass against the pre-change implementation | skills/run-autopilot/cli/test_wave_launch_abort.py:321 | general | BOB, mech-check | **Discarded — same reason.** `test_abort_runs_every_git_call_in_the_repo_but_the_lane_probes` and `test_abort_kills_a_group_whose_leader_has_already_exited` exist to close coverage gaps **cycle 1 explicitly asked for** on behavior that was already correct. A coverage test for correct behavior cannot fail against the base without breaking production first. Ledgered. |
| [2/4] **(mech-check)** | 🟡 Medium | The new live-main-loop refusal test passes against the pre-change implementation | skills/run-autopilot/cli/test_wave_launch_refusals.py:74 | general | BOB, mech-check | **Discarded — same reason.** This test closes cycle 1's own "no test covers the PRD-required live-loop refusal" finding; the refusal already worked. Ledgered. |
| [1/4] | 🟡 Medium | `wave_cli.run` duplicates identical `CalledProcessError` handling for the launch and abort verbs; one shared dispatch guard would be simpler | skills/run-autopilot/cli/wave_cli.py:48 | 6 | BOB | **Declined, recorded.** A behavior-preserving de-slop suggestion, but collapsing two per-verb `try` blocks into one shared guard widens the guard's scope over verbs that currently do not need it, and the duplication is two lines. Surgical Changes: not refactoring working dispatch code to remove two lines. Ledgered so it is not re-argued. |
| [1/4] | ⚪ Low | A mid-launch `OSError` (`shutil.move`/`copytree` in `_seed_lane_worktree`) is caught nowhere between `_launch_lane` and `wave_cli.run`, which catches only `CalledProcessError`; it would surface as a raw traceback and leave `worktree_created: true` with no process spawned | skills/run-autopilot/cli/wave_launch.py:202 | general | BLAKE | **Settled deferral.** Blake rated it Low himself and named the reason: the PRD describes this failure mode for `abort`, never for `launch`, and `abort` remains a working manual recovery path. Adding launch-side rollback is a behavior decision outside this PRD's contract. Ledgered. |
| [1/4] | ⚪ Low | Cannot statically verify: in-scope test suites and `release-checks` pass | N/A | general | BOB | **Discarded — answered by evidence.** Bob's sandbox blocks execution; three other reviewers ran the code this cycle. Alice: 177 passed, 0 failed across the six in-scope files. Blake: 137 passed on the PRD's named invocation, plus 14 passed on the three orphan files, plus the whole of `release-checks` green. Carl: wave suites and `release-checks` green. Ledgered. |

### Not queued for verification

- `VERIFY-01` (BOB): "run the seven pytest files, then `bash dev/bin/release-checks`" — **not queued: command shape.** Two chained commands, which the queue forbids. Already answered by evidence anyway (see the last row above). No `checks-2.json` was written this cycle.

## Alice

Consensus lens, implementation-aware. Verified all four cycle-1 dispatched findings resolved in the code and pinned by new tests, naming the fix site for each: the `pid` range `1 < v < 2**31` at `wave.py:292`; the `_RETURN_TO` mapping at `wave_launch.py:464` sending both `wip/` and `backlog/` to main `backlog/`; the per-`kill_fn` try/except at `wave_launch.py:398-407`; and `_TOP_CHECKS["base_sha"]` at `wave.py:280`. She also walked the cycle-1 Medium/Low tail and confirmed each item fixed — the `waves.md` 00216→00217 attribution, the abort-folder wording, the new abort git-cwd pinning test, `_run_wave`'s `assert`→refusal, `wave_cli.run`'s `abort` branch catching `CalledProcessError`, and wave-slots retention keying on `alive` rather than `failed` — except the `_worktree_line` fallback edge she raised as a finding.

Ran the six in-scope files: 177 passed, 0 failed (150.78s). Confirmed every changed function under 50 lines and every changed file under 800, against the mechanical-facts block and `wc -l`. Re-raised nothing settled.

Findings: 1 × 🟠 (regraded to 🟡 by the gate), 1 × 🟡.

`R1: fail` `R2: pass` `R3: pass` `R4: fail` `R6: pass` `R7: pass` `R8: pass` `R9: pass` `R10: pass` `R11: pass` `R12: pass` `R13: pass`

Her `R1`/`R4` failures both rest on the release-checks wiring gap — the gate accepts the gap as real and sweeps it, while reading it as a CI-wiring Medium rather than as the diff's new behavior being untested (the tests exist and pass; only the gate does not call them).

## Blake

Blind lens — prompt carried the PRD and the `B` rubric only: no diff, no changed-file list, no implementation summary, no review history, and he was told explicitly not to read `dev/local/reviews/` or `dev/local/designs/`. No filesystem-notes block (the trigger does not hold: `dev/local` is a real directory and the project root does not start with `.`).

Found the code himself and independently confirmed the whole PRD-visible surface correct, in detail: `shares()`' three join rules including the cross-file `WAVE_FORCE_SHARED` case; `cut()` pure and 42 lines against the under-50 exit criterion; largest-component-first packing into the fewest-PRD lane; core-first lane ordering; every `wave.json` naming rule; all four `launch` preconditions running before anything is created; the spawn argv, cwd, env, stdio and `start_new_session=True` verbatim against the spec; and `abort`'s SIGTERM→60s→SIGKILL→10s escalation, process-group semantics, **`wip/`→main `backlog/`** mapping, four-way worktree-keep logic and idempotent rerun. He also verified the deferred items are genuinely absent (`assemble`/`review`/`land`/`run` unregistered, the two slot env vars written and read nowhere) and that the docs and CHANGELOG entry are present and pinned.

Ran the PRD's named Success-Metric invocation: 137 passed. Ran the three CI-orphaned files directly: 14 passed. Ran the whole of `release-checks`: green.

Findings: 3 × 🟡, 1 × ⚪ — the export-signature divergence, the extra `wave.json` fields, the release-gate wiring gap, and the mid-launch `OSError` path.

`B1: pass` `B2: fail` `B3: fail` `B4: pass` `B5: pass` `B6: fail` `B7: pass` `B8: pass` `B9: pass` `B10: pass` `B11: pass` `B12: pass` `B13: pass` `B14: pass` `B15: pass` `B16: pass` `B17: pass` `B18: pass` `B19: pass`

`B2`/`B3` rest on the shape and signature deviations the gate settled as design-conformant; `B6` rests on the extra `wave.json` fields, design-mandated. All three are artifacts of a blind lens judging against the PRD without the design doc that reviewed and approved those deviations — which is the lens working as designed, not a fault.

## Bob

Doubt + de-slop lens on codex, read-only sandbox, plus the consensus `R` rubric. Resumed his cycle-1 codex thread, so he verified his own prior critique rather than re-reviewing from zero. Ran first-try; no retry, no salvage path needed.

He confirmed his four cycle-1 findings fixed (implicitly — none is re-raised) and produced nine new issue lines: two Medium residues of task 6's own fixes (the `--state` basename, the `wave_cli` duplication), one Medium agreeing with the release-gate gap, three Medium fail-first replay observations, one Low doc mismatch, one Low re-raise of `status`'s `Path.exists()` keying, and the sandbox non-verification line. Nothing above 🟡 from any reviewer this cycle — the cycle's whole 🔴/🟠 surface is empty.

Buckets as emitted: `FIX (5)`, `VERIFY (1)`, `KNOWN (7)`. His KNOWN bucket correctly carried forward all four coverage gaps the brief handed him as out-of-scope, and — notably — he pre-emptively justified all three of his own fail-first replay rows in KNOWN, explaining why forcing them red would require changing unrelated production code. The gate agreed with that reasoning and dismissed all three.

`R1: fail` `R2: fail` `R3: pass` `R4: pass` `R6: pass` `R7: fail` `R8: pass` `R9: fail` `R10: pass` `R11: pass` `R12: pass` `R13: pass`

`D1: pass` `D2: pass` `D3: pass` `D4: pass` `D5: pass`

On his `R` failures: `R1`/`R2` rest on the release-gate gap and the replay rows; `R7` on the `--state` basename check; `R9` on the kept-worktree doc/output mismatch. The gate confirmed the gap, the basename and the doc line (all three swept) and dismissed the replay rows with reasons. All five doubt-rubric rules pass.

## Carl

Gemini lens via the copilot backend. Read the context and the scoped diff, then the three new test files in full, and inspected `base_sha` usage, the CHANGELOG, TODO/FIXME/DEBUG markers, and every changed file's function and file length limits with `ast` and `wc -l`.

Ran the wave suites and then `bash dev/bin/release-checks` — twice, the second time with `AUTOPILOT_DISPATCH_DEPTH`, `COPILOT_CLI` and `_AUTOPILOT_LOOP` unset to clear the nested-dispatch guards, exactly as he did in cycle 1 — and reported both green.

Findings: none. `[CARL] ✅ No issues found`.

`R1: pass` `R2: pass` `R3: pass` `R4: pass` `R6: pass` `R7: pass` `R8: pass` `R9: pass` `R10: pass` `R11: pass` `R12: pass` `R13: pass`

Carl having no frontend surface to review, he ran as a generalist and did not invent frontend findings, as his persona directs.

## Follow-up Tasks Created

None at this step: the cycle produced no 🔴 and no unresolved 🟠, so nothing routed to Phase 6 rework. The four actionable Medium/Low findings go to one Tail sweep task instead (Phase 5).

Verdict: 13 findings
Tests: 1506 passed, 0 failed, 0 skipped (reused from last-verification.json at 0f476c54)
