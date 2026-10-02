---
prd: docs/dev/project-management/prds/wip/00233-run-the-test-suites-in-parallel-v1.md
review: 2
date: 2026-10-01
head_sha: f0cb7c1c325e29f5abdf011dec01f6efec7655cf
codex_thread_id: 01a0f52f-510c-72d1-a079-73e9848465ec
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00233-run-the-test-suites-in-parallel-v1

Diff range: `c502c2f139ccb8fd569d7fcadd4eefe1b3366871..f0cb7c1c325e29f5abdf011dec01f6efec7655cf`

codex_rung_guard: not fired

## Top matter

- **Cycle 2, incremental review.** The diff is scoped with
  `--since c502c2f` (cycle 1's `head_sha`), so it covers exactly the three
  rework commits: `6707854` (task 4), `8ea6f3a` (task 5), `f0cb7c1` (task 6).
  5 files, 86 insertions, 11 deletions.
- **Bob resumed his cycle-1 codex thread** (`--resume-thread
  01a0f52f-510c-72d1-a079-73e9848465ec`), so he verified fixes against his own
  prior critique rather than re-reviewing from zero.
- **pack: failed (engram: "not inside a registered repo; register it in
  /Users/bob/.config/gita/repos.csv").** Retried once, same error — identical to
  cycle 1. Every prompt taking `{PACK_FILE}`/`{PACK_FINDINGS}` received the
  sentinel `(no pack available this cycle)`. Degraded, not invalid.
- **Consolidation ran via `consolidate_findings.py`** (not model-side), with
  `--ledger` and `--ledger-dismiss BLAKE`. **No Blake finding was
  auto-dismissed** — none of his cycle-2 lines matched a settled entry, so the
  script emitted no `### Auto-dismissed (ledger)` section. Every one of his
  findings was judged on its merits below.
- **The consolidator under-merged once, in the opposite direction to cycle 1.**
  Carl's `test_repo_disables_signing_regardless_of_host_gpg_config has no
  assertion` stayed a separate `[1/4]` row from the identical Alice/Bob row,
  so one defect appeared twice at a lower consensus than it holds. The table
  below merges them by hand to `[3/4]`. Cycle 1 recorded the inverse failure
  (over-merging distinct defects that share a file); both are the same
  file-level paraphrase matcher, and it is deferred to batch end for its own
  PRD.
- **No verification-check queue written** (no `-checks-2.json`), same as cycle 1
  and for the same structural reason. The queue is fed from a doubt lens's
  FIX/VERIFY/KNOWN buckets. Eve was not active (the Codex doubt-roster guard did
  not fire — no task has a `codex` implementor), and Bob's assembled prompt
  carries `agents/eve.md`'s "Two lenses" and "Rubric verdicts" sections but not
  its "Categorize every residual finding" bucket section, so no lens emitted a
  bucket. `source: "bob"` is reserved by `references/output-formats.md` and
  buckets he did not emit were not invented. His one `(VERIFY)`-worded ⚪ line is
  an ordinary issue line, and it was **resolved by running the check it names**
  (see "Orchestrator's own verification").

## Reviewer status

- Alice: ✅ Available (Claude subagent, consensus lens, `legacy` engine)
- Blake: ✅ Available (Claude subagent, blind lens, PRD-only; no filesystem-notes
  block — `docs/dev/project-management` is not a symlink and the project root's
  basename does not start with `.`, so neither trigger held)
- Bob: ✅ Available (codex, doubt + de-slop lens, exit 0, first run, no retry;
  cycle-1 thread resumed and re-emitted for cycle 3)
- Carl: ✅ Available (gemini via `backend=copilot model=gemini-3.8-flash`,
  exit 0, non-empty reviewer text)

All four produced format-compliant issue lines and complete per-rule verdicts on
the first run. No retry was spent and no reviewer failed.

**One Carl artifact, recorded so it is not mistaken for a product failure.**
Carl's first `bash dev/bin/release-checks` run reported `SUMMARY: 6 passed, 20
failed` in the `[checks] runner recursion guard` block. That is the copilot CLI's
own environment leaking into the gate: `AUTOPILOT_DISPATCH_DEPTH`, `COPILOT_CLI`
and `CODEX_SESSION_ID` were set in his shell, so `codex-run.sh` correctly
refused nested dispatch (`refusing nested dispatch (depth=1)`, exit 3) and every
assertion about its argv saw nothing. Carl diagnosed this himself, re-ran with
`env -u AUTOPILOT_DISPATCH_DEPTH -u COPILOT_CLI -u _AUTOPILOT_LOOP -u
CODEX_SESSION_ID -u COPILOT_AGENT_SESSION_ID bash dev/bin/release-checks`, and
raised no finding from it. Alice and the orchestrator each ran the same gate
green in a clean environment.

## Consolidated findings

Dispositions are the decision gate's, recorded inline so no row's fate is
implicit. The two 🟠 rows are the only ones that could have blocked convergence.

| Consensus | Severity | Issue | File | Task | Found By | Disposition |
|-----------|----------|-------|------|------|----------|-------------|
| [3/4] + mech | 🟡 Medium | `test_repo_disables_signing_regardless_of_host_gpg_config` has no explicit assertion: it only proves `_repo()` does not raise. Alice verified it is not a true tautology (it fails deterministically with the `_repo()` fix removed), but it binds to intent only through an implicit raise. Fix: capture the returned repo and call `_assert_gpgsign_disabled(repo)`, so it reads like the hammer tests. | skills/run-autopilot/cli/test_parallel_safety.py:78 | 4 | ALICE, BOB, CARL, mech-check | **swept** |
| [1/4] | 🟠 High | The PRD's literal success metric (`-n auto` over `skills/run-autopilot/cli` green three times in a row) is not reliably met on this host: 1 of 2 runs had ~15 wave-family failures with a `git worktree add` / fork-exhaustion traceback. | dev/bin/release-checks | general | BLAKE | **discarded — refuted by measurement** |
| [1/4] | 🟠 High | Phase 1 acceptance requires three consecutive green `-n auto` runs; the design doc carries no three-run record for the shipped *capped* invocation, and its 3x-green numbers come from a simulated uncapped run. | designs/00233-…-design.md | general | BLAKE | **discarded — gap closed by running it** |
| [1/4] | 🟡 Medium | `--maxprocesses 4` is a new option the PRD does not specify, and the cap wording now sits in `final-verification.md` in place of the PRD's own sentence. Defensible, but spec drift. | skills/work/references/final-verification.md | general | BLAKE | **deferred to batch end** |
| [1/4] | 🟡 Medium | The design doc contradicts the shipped gate: it says five blocks go parallel including `enter`, and that `test_parallel_safety.py` joins the `waves` file list. In the code `enter` stays serial and `parallel safety` has its own serial block. The doc has no after-implementation timing and never mentions the worker cap, though the PRD asked for before and after to be measured there. | designs/00233-…-design.md | general | BLAKE | **swept** |
| [1/4] | 🟡 Medium | FIX: the new pin runs only inside the block it protects. Deleting `[checks] parallel safety` also removes the pin from the release gate. Move the pin into an independent existing block. | dev/bin/release-checks:141 | 5 | BOB | **swept** |
| [1/4] | 🟡 Medium | FIX: both prose pins accept the strings in comments or echo text without proving pytest executes the file with xdist installed. Parse the continued runner invocation and require the full test path and the dependency in that command, following the existing wave-pin pattern. | skills/run-autopilot/cli/test_release_checks_parallel_prose.py:22 | 5 | BOB | **swept** |
| [1/4] | 🟡 Medium | FIX: `_assert_gpgsign_disabled` duplicates the existing `test_wave_launch._git` subprocess wrapper. Reuse `_git(repo, "config", "--local", "commit.gpgsign")` and retain the stdout assertion. | skills/run-autopilot/cli/test_parallel_safety.py:24 | 4 | BOB | **swept** |
| [1/4] | 🟡 Medium | FIX: the lane signing override has no regression test; existing lane tests also pass without it on hosts with signing disabled. Add a test that forces global signing with a failing signer and verifies `_solo_repo` still creates its commit. | skills/run-autopilot/cli/test_lane_cli.py:160 | 6 | BOB | **swept** |
| [1/4] | 🟡 Medium | [MECH] 3 touched tests pass against the pre-change code: test_hammer_a, test_hammer_b, test_repo_disables_signing_regardless_of_host_gpg_config. | skills/run-autopilot/cli/test_parallel_safety.py | general | mech-check | **discarded — wrong baseline** |
| [1/4] | 🟡 Medium | [MECH] 2 touched tests pass against the pre-change code: test_parallel_safety_block_runs_test_parallel_safety, test_parallel_safety_block_uses_pytest_xdist. | skills/run-autopilot/cli/test_release_checks_parallel_prose.py | general | mech-check | **discarded — wrong baseline** |
| [1/4] | ⚪ Low | The pin file does its `RELEASE_CHECKS.index(...)` slicing at module import, so a deleted or relocated block surfaces as a collection `ValueError` rather than a named test failure. Still red, so a readability nit only. | skills/run-autopilot/cli/test_release_checks_parallel_prose.py:17 | 5 | ALICE | **swept** |
| [1/4] | ⚪ Low | The root cause is host-specific, and `test_the_wave_pair_passes_under_two_workers` is probabilistic, so it only guards the regression on hosts with global signing. The same exposure is patched per-fixture in three places and nothing prevents a future fixture reintroducing it. | skills/run-autopilot/cli/test_parallel_safety.py | general | BLAKE | **deferred to batch end** |
| [1/4] | ⚪ Low | Extra artifacts beyond the PRD's file list: the pin file, the deterministic test, the `test_lane_cli.py` fix. All test-only and justified by the root cause. | skills/run-autopilot/cli/test_release_checks_parallel_prose.py | general | BLAKE | **discarded — not a defect** |
| [1/4] | ⚪ Low | Cannot statically verify: task 6's parallel acceptance. Check records for three consecutive runs of the parallel `cli` command and its serial counterpart; the verification record holds neither. | N/A | 6 | BOB | **discarded — ran the check** |

### The two 🟠 rows, in full

Both are Blake's, both concern the same fact, and both were decided by running
the thing rather than by argument. Neither was in the ledger, so neither was
auto-dismissed and neither could be waved past as "already settled".

**🟠 "bare `-n auto` is not reliably green."** Blake's red run is real, and its
cause is identifiable: it carried a resource-exhaustion signature
(`BlockingIOError [Errno 35]` at fork, `git` killed by SIGKILL, `git worktree
add` exit 255) and it happened inside the review window, while Alice was running
`bash dev/bin/release-checks` end to end plus a 221s serial whole-directory run
plus scratch-copy suites, and Carl was running `release-checks` twice plus
`--continue-on-collection-errors skills/run-autopilot/cli`. Three reviewers
driving full suites on one 18-core host is itself fork pressure. After every
reviewer had finished, with the host otherwise idle, bare `-n auto` over that
directory ran **three consecutive times green: 1952 passed, 0 failed, 77.86s /
77.83s / 78.04s**. Success Metric 1 as literally written is met, 3/3. **Discarded
with that reason, not dismissed**: the residual fact that 18 workers sits near
this host's fork limit under concurrent load is exactly the margin
`--maxprocesses 4` buys, and it survives as the ⚪ above plus the deferred
spec-drift record.

**🟠 "no three-run record for the shipped capped form."** This gap was real.
It is now closed, in this cycle, by running it: the shipped form
(`-n auto --maxprocesses 4`) ran **three consecutive times green: 1952 passed, 0
failed, 153.96s / 91.18s / 92.28s** (run 1 is cold-cache; runs 2 and 3 settle at
~92s). Against Alice's measured 221s serial that is **41.6% of serial**, so the
PRD's under-half metric holds on the whole directory, not only on the dominant
waves block cycle 1 measured at 47.7%. The part of Blake's finding that is about
the **design doc** not carrying these numbers is *not* discarded — it survives as
its own 🟡 and is swept.

## Mechanical blocks (computed, not reviewer judgement)

- **Mechanical facts** (per-function line counts from `ast`): no finding
  contradicted them. The largest changed function is
  `test_the_wave_pair_passes_under_two_workers` at 24 lines, well inside the
  50-line limit; the largest file touched is `test_lane_cli.py` at 331 lines,
  well inside 800. R12 and R13 pass on computed evidence.
- **Tautological shapes**: 1 `[MECH]` line (down from 2 in cycle 1), absorbed
  into the table above and swept. The cycle-1 pair on `test_hammer_a`/`_b` is
  **gone**: both now assert each created repo's local `commit.gpgsign` is
  `false`, so 22 test functions were checked and only the new deterministic test
  still has the implicit-raise shape.
- **Fail-first replay**: 2 `[MECH]` lines, both discarded as computed against the
  wrong baseline for the question asked. This is an incremental review based at
  `c502c2f`; the fixture fix those tests pin landed at `d9868f8`, before that
  base, and `test_wave_launch.py` is not in this cycle's changed-file list, so
  the base worktree already carries the fix. The prose pins likewise pin a block
  that existed at the base by design — their job is to stop a future deletion.
  The real fail-first property was verified by hand instead: Alice deleted the
  `_repo()` line in a scratch copy and both the new deterministic test and
  `test_hammer_a` failed with `CalledProcessError`; she removed
  `--with pytest-xdist` from the block and the pin failed as an ordinary
  assertion failure.

## Alice (consensus lens)

Alice reports all six of her cycle-1 findings resolved and found no regressions.
Her verifications, cited in preference to the build's numbers:

- `test_the_wave_pair_passes_under_two_workers` now opens with
  `pytest.importorskip("xdist", ...)` (`test_parallel_safety.py:55`). Serial run
  of that file plus the new pin file: `5 passed, 1 skipped`, the skip being the
  meta-test. With `--with pytest-xdist`: `6 passed`, so the guard actually runs
  where the gate puts it.
- Serial run of the whole `skills/run-autopilot/cli` directory:
  **1951 passed, 1 skipped, 664 subtests passed in 221s, 0 failed.** This is the
  PRD Phase 1 criterion "the serial run of the same directory green", which was
  red in cycle 1.
- Deleting the `commit.gpgsign` line from `_repo()` in a scratch copy reddened
  both the new deterministic test and `test_hammer_a` with `CalledProcessError`.
  Thread count, worker count, timeout and subprocess shape are unchanged, as the
  task required.
- All four converted blocks use `-n auto --maxprocesses 4`
  (`release-checks:49, 77, 88, 144`); the comment naming the 18-worker
  exhaustion is at `release-checks:45`; `# serial:` comments now sit above
  `[checks] parallel safety` (137) and `[checks] enter` (162).
- Removing `--with pytest-xdist` from the block reddened
  `test_parallel_safety_block_uses_pytest_xdist` as an ordinary assertion
  failure; deleting the block entirely raises `ValueError` at import, which is
  still red.
- `_GIT_IDENTITY` at `test_lane_cli.py:160` carries `-c commit.gpgsign=false`,
  and `_git` at 165 is that file's only git caller. `cli/custody.py` untouched.
- `bash dev/bin/release-checks` ran once end to end, every block green; the
  waves block gave `350 passed in 80.06s`.

Findings:

```
[ALICE] ⚪ The `[MECH]` no-assertion flag on `test_repo_disables_signing_regardless_of_host_gpg_config` is not a real tautology: I verified it fails deterministically when the `_repo()` fix is removed. It does bind to intent only through an implicit raise, though. Optional hardening: call `_assert_gpgsign_disabled(repo)` on the returned repo so it reads like the hammer tests. | File: skills/run-autopilot/cli/test_parallel_safety.py:78 | Task: 4
[ALICE] ⚪ The pin file does its `RELEASE_CHECKS.index(...)` slicing at module import, so a deleted or relocated block shows up as a collection `ValueError` rather than a named test failure. It is still red, so this is a readability nit only. | File: skills/run-autopilot/cli/test_release_checks_parallel_prose.py:17 | Task: 5
```

Per-rule verdicts:

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

## Blake (blind lens, PRD-only)

Blake received the PRD, the blind rubric and the output format, and nothing else
— no diff, no changed-file list, no design-doc content, no review history. He
located the code himself and ran it in a scratch copy at `/tmp/blake-copy-00233`
(which he left in place), and he modified nothing in the repository.

He verified clean, without raising a finding: `bash dev/bin/release-checks` green
end to end (one run, not the two Phase 2 asks for); `rg -c "\-n auto"` at least
1 across four blocks; serial blocks carrying explanatory comments and
mixed-directory suites staying serial; the CHANGELOG `### Changed`
`**run-autopilot**` line; the `final-verification.md` sentence; the `## Root
cause` section naming the shared resource; no new dependency beyond
pytest-xdist; the wave fixture's name and signature unchanged.

Findings:

```
[BLAKE] 🟠 The PRD's literal success metric (`pytest -q -n auto skills/run-autopilot/cli` green three times in a row) is not reliably met on this host. I ran it twice on a scratch copy. Run 1 had about 15 failures, all wave-family (`test_wave_launch_abort_keep`, `test_wave_assemble_migrate` and others). The traceback was inside `subprocess.Popen` on `git worktree add`, which looks like the fork/process-table exhaustion the implementer's own commit message describes (18 workers). Run 2 was green: 1952 passed in 78 s. The implementer worked around it with `--maxprocesses 4`, which the PRD never specifies, and did not amend the PRD or record the three-green evidence for the capped form. | File: dev/bin/release-checks | Task: general
[BLAKE] 🟠 Phase 1 acceptance requires `-n auto` over `cli/` green on three consecutive runs. Bare `-n auto` went red on one of my two runs (see the finding above). The capped form `-n auto --maxprocesses 4` passed once for me (1952 passed in 91 s, against about 245 s serial per the design doc). The design doc contains no three-run record for the shipped, capped invocation. The 3x-green evidence in it (76-77 s) comes from a simulated `GIT_CONFIG_GLOBAL=/dev/null` run with uncapped workers. | File: docs/dev/project-management/designs/00233-run-the-test-suites-in-parallel-v1-design.md | Task: general
[BLAKE] 🟡 `--maxprocesses 4` is a new option the PRD does not specify. The PRD asks only for `--with pytest-xdist` and `-n auto`. The cap is also written into `skills/work/references/final-verification.md`, replacing the PRD's wording "(its release gate already passes it)". The change is defensible, but it is spec drift. | File: skills/work/references/final-verification.md | Task: general
[BLAKE] 🟡 The design doc contradicts the shipped gate. It says five blocks go parallel, including `enter`, and that `test_parallel_safety.py` joins the `waves` file list. In the code, `enter` stays serial and `parallel safety` has its own serial block. The doc has no after-implementation timing and does not mention the worker cap. The PRD asked for before and after to be measured in the design doc. The CHANGELOG claim of "roughly in half" is supported only by my own measurements and by uncapped or simulated numbers in the doc. | File: docs/dev/project-management/designs/00233-run-the-test-suites-in-parallel-v1-design.md | Task: general
[BLAKE] ⚪ The root cause is host-specific: the global `commit.gpgsign=true` plus a shared gpg-agent. The fix is a single `git config commit.gpgsign false` line in `_repo()` (skills/run-autopilot/cli/test_wave_launch.py:76). That is the "isolate it" route the PRD prefers, it is documented under `## Root cause`, and the `test_parallel_safety.py` pair is made deterministic by `test_repo_disables_signing_regardless_of_host_gpg_config`. However, `test_the_wave_pair_passes_under_two_workers` is probabilistic and passes on hosts without global signing, so it only guards the regression on hosts like this one. The same latent exposure was patched separately in `test_lane_cli.py` (via `-c commit.gpgsign=false`) and `test_enter_decisions.py:510`, and nothing prevents a future fixture from reintroducing it. | File: skills/run-autopilot/cli/test_parallel_safety.py | Task: general
[BLAKE] ⚪ Extra artifacts beyond the PRD's file list: `test_release_checks_parallel_prose.py`, the `test_repo_disables_signing_...` test, and the `test_lane_cli.py` fix. All are test-only and justified by the root cause. The `parallel safety` block in release-checks runs `test_parallel_safety.py` without `-n auto`, with a comment explaining why. | File: skills/run-autopilot/cli/test_release_checks_parallel_prose.py | Task: general
```

Per-rule verdicts:

```
B1: fail
B2: pass
B3: pass
B4: fail
B5: pass
B6: pass
B7: fail
B8: pass
B9: pass
B10: pass
B11: pass
B12: pass
B13: pass
B14: pass
B15: fail
B16: pass
B17: pass
B18: pass
B19: pass
```

Blake's four `fail` verdicts (B1, B4, B7, B15) all trace to the two 🟠 rows and
the `--maxprocesses` drift. B1/B4/B15 are answered by the six green runs
recorded below; B7 (no additional options beyond the PRD's) stands and is the
deferred spec-drift record.

## Bob (doubt + de-slop lens, codex)

Ran on the first dispatch, exit 0, no retry, resuming thread
`01a0f52f-510c-72d1-a079-73e9848465ec` from cycle 1. Bob's three cycle-1 FIX
items are all resolved; every line below is new, and four of the five are
de-slop/hardening rather than correctness.

Findings:

```
[BOB] 🟡 FIX: The new pin runs only inside the block it protects. Deleting `[checks] parallel safety` also removes the pin from the release gate. Move the pin into an independent existing block. | File: dev/bin/release-checks:141 | Task: 5
[BOB] 🟡 FIX: Both prose pins accept strings in comments or echo text without proving pytest executes the file with xdist installed. Parse the continued runner invocation and require the full test path and dependency in that command, following the existing wave-pin pattern. | File: skills/run-autopilot/cli/test_release_checks_parallel_prose.py:22 | Task: 5
[BOB] 🟡 FIX: Computed shapes flag the deterministic guard's missing assertion. Capture the returned repo and call `_assert_gpgsign_disabled` to explicitly assert the isolation invariant. | File: skills/run-autopilot/cli/test_parallel_safety.py:78 | Task: 4
[BOB] 🟡 FIX: `_assert_gpgsign_disabled` duplicates the existing `test_wave_launch._git` subprocess wrapper. Reuse `_git(repo, "config", "--local", "commit.gpgsign")` and retain the stdout assertion. | File: skills/run-autopilot/cli/test_parallel_safety.py:24 | Task: 4
[BOB] 🟡 FIX: The lane signing override has no regression test; existing lane tests also pass without it on hosts with signing disabled. Add a test in this file that forces global signing with a failing signer and verifies `_solo_repo` successfully creates its commit. | File: skills/run-autopilot/cli/test_lane_cli.py:160 | Task: 6
[BOB] ⚪ Cannot statically verify: task 6's final-revision parallel acceptance (VERIFY). Check records for three consecutive runs of `uv run --no-project --with pytest --with pytest-xdist python -m pytest -q -n auto skills/run-autopilot/cli` and its serial counterpart; the current verification record contains neither parallel run evidence nor counts for that directory. | File: N/A | Task: 6
```

Per-rule verdicts:

```
R1: fail
R2: fail
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: fail
R10: pass
R11: pass
R12: pass
R13: pass
```

Doubt-rubric verdicts:

```
D1: pass
D2: pass
D3: pass
D4: pass
D5: pass
```

Bob's R1/R2 `fail` rest on the un-pinned lane override and the implicit-raise
guard, both swept below. His R9 `fail` is the same `-n auto` versus
`-n auto --maxprocesses 4` drift Blake raised.

## Carl (gemini, frontend & design specialist, generalist here)

`backend=copilot model=gemini-3.8-flash`, exit 0, non-empty output. No frontend
surface in this diff, so he reviewed as a generalist, as his persona directs. He
ran the pin file, `test_parallel_safety.py` both with and without xdist,
`test_lane_cli.py`, the `-n auto` count, `release-checks` (twice — see the
environment artifact under Reviewer status) and the whole `cli` directory, and
read the consolidator source. He raised one line, matching Alice's and Bob's.

Findings:

```
[CARL] 🟡 test_repo_disables_signing_regardless_of_host_gpg_config has no assertion: it only proves the code does not raise | File: skills/run-autopilot/cli/test_parallel_safety.py:78 | Task: 4
```

Per-rule verdicts:

```
R1: pass
R2: fail
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

## Orchestrator's own verification

Run in this session with the host otherwise idle (every reviewer had finished),
not taken on trust. This is the evidence that decided both 🟠 rows.

**The shipped capped form** —
`uv run --no-project --with pytest --with pytest-xdist python -m pytest -q -n auto --maxprocesses 4 skills/run-autopilot/cli`,
three consecutive runs:

| run | result | wall clock |
|-----|--------|-----------|
| 1 | 1952 passed, 0 failed, 664 subtests passed | 153.96s (cold cache) |
| 2 | 1952 passed, 0 failed, 664 subtests passed | 91.18s |
| 3 | 1952 passed, 0 failed, 664 subtests passed | 92.28s |

**Bare `-n auto`** (18 workers on this host) —
`uv run --no-project --with pytest --with pytest-xdist python -m pytest -q -n auto skills/run-autopilot/cli`,
three consecutive runs:

| run | result | wall clock |
|-----|--------|-----------|
| 1 | 1952 passed, 0 failed, 664 subtests passed | 77.86s |
| 2 | 1952 passed, 0 failed, 664 subtests passed | 77.83s |
| 3 | 1952 passed, 0 failed, 664 subtests passed | 78.04s |

**Serial baseline**: Alice measured the same directory at 1951 passed, 1 skipped,
0 failed in **221s** this cycle. The extra pass in the parallel runs is the
xdist-gated meta-test, which skips without xdist and runs with it — the intended
behaviour of task 4's `importorskip`, visible in the counts.

Against that baseline: the shipped capped form is **41.6% of serial** (92s/221s)
and bare `-n auto` is **35.2%** (78s/221s). PRD Success Metric 3 ("under half its
serial time") therefore holds on the **whole directory**, not only on the
dominant waves block cycle 1 measured at 47.7%.

**PRD Phase 2's literal acceptance check**: `rg -c -- '-n auto'
dev/bin/release-checks` prints **5** (four converted invocations plus the
explanatory comment). Required: at least 1. Met.

**Why the suite itself was not re-run**: `last-verification.json` carries
`sha: f0cb7c1…`, which equals this cycle's reviewed HEAD, with non-null counts
(4202/0/2), so the reuse precondition in step 6 holds and the `Tests:` line below
is composed from that record. **Stated loudly, because the record is not a plain
green**: its second command,
`uv run --no-project --with pytest python -m pytest -q --continue-on-collection-errors hooks skills`,
is recorded at **exit 1** with **0 failed**. Those are consistent — the non-zero
exit comes from the 3 long-settled `ModuleNotFoundError: No module named 'rich'`
collection errors in `tracon/test_panels.py`, `test_screens.py` and
`test_stream.py`, which the record's counts do not carry and which are identical
to the prior PRD's cycles. The arithmetic against cycle 1 also corroborates the
fix: cycle 1 measured 4199 passed / 1 failed / 1 skipped; cycle 2 is
4202 passed / 0 failed / 2 skipped, i.e. +3 passed for the three new tests, and
the one cycle-1 failure (the meta-test) moved into `skipped` exactly as task 4's
`importorskip` intends.

- Working tree clean before and after this review (`git status --porcelain`
  empty); no reviewer modified the repo. Blake's `/tmp/blake-copy-00233` and
  Alice's `/tmp/alice-scratch` are outside it.

## Assessment

Every cycle-1 blocker is closed and independently re-verified. The PRD's serial
criterion, which cycle 1 made red, is green; the Phase 2 `-n auto` acceptance
check passes; and the under-half metric now has like-for-like evidence on the
whole directory rather than on one block. Both of this cycle's 🟠 rows were
evidence questions, and running the evidence answered both.

What remains is a tail of seven Medium/Low hardening items, none of which can
make the gate wrong today: the deterministic guard asserts by implicit raise
rather than explicitly, the two prose pins are substring checks that live inside
the block they protect, `_assert_gpgsign_disabled` reimplements an existing
helper, the lane signing override has no test of its own, and the design doc was
never updated to match what shipped. They are swept into one task rather than
dropped. Two items are deferred to batch end as genuinely out of this PRD's
scope: the `--maxprocesses` spec drift against a shipped PRD's text, and the
directory-wide conftest that would prevent the whole gpg-signing class.

Verdict: 15 findings
Tests: 4202 passed, 0 failed, 2 skipped (reused from last-verification.json at f0cb7c1c325e29f5abdf011dec01f6efec7655cf)
