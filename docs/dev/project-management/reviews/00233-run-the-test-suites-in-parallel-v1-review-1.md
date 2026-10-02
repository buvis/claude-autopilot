---
prd: docs/dev/project-management/prds/wip/00233-run-the-test-suites-in-parallel-v1.md
review: 1
date: 2026-10-01
head_sha: c502c2f139ccb8fd569d7fcadd4eefe1b3366871
codex_thread_id: 01a0f52f-510c-72d1-a079-73e9848465ec
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00233-run-the-test-suites-in-parallel-v1

Diff range: `a9c1ae26130683dd9b976ecbe44d76450bea069c..c502c2f139ccb8fd569d7fcadd4eefe1b3366871`

codex_rung_guard: not fired

## Top matter

- **Cycle 1, full review.** No prior review file for this PRD; the diff covers
  the PRD's whole work range (3 commits, one per task).
- **Diff base passed explicitly.** `gather-context.sh`'s full-review path
  resolves its base to the detected branch (`master`), and this repo works
  directly on `master`, so `git diff master` at a clean HEAD is **empty**. The
  base was therefore passed as `--since <work_start_sha>`, which produces
  exactly `state.work_start_sha..HEAD`, the range this gate is specified to
  review. The context file's scope line was corrected to say "full review" so
  no reviewer was told this was a rework slice. Recorded because the tooling's
  own full-review path cannot produce a correct diff in a master-only repo.
- **pack: failed (engram: "not inside a registered repo; register it in
  /Users/bob/.config/gita/repos.csv").** Retried once, same error. Every prompt
  that takes `{PACK_FILE}`/`{PACK_FINDINGS}` received the sentinel
  `(no pack available this cycle)`. Degraded, not invalid; Blake never receives
  a pack by design.
- **Consolidation ran via `consolidate_findings.py`** (not model-side). It
  emitted four over-merge warnings, discussed under "Consolidation caveat"
  below.
- **No settled-decisions ledger** (cycle 1), so the `--ledger` flags were
  omitted and no Blake re-raise was auto-dismissed.
- **No verification-check queue written.** The queue is fed from a doubt lens's
  VERIFY bucket. Eve was not active this cycle (the Codex doubt-roster guard did
  not fire), and Bob's assembled prompt carries the registry's doubt appendix
  without the FIX/VERIFY/KNOWN bucket section, so no lens emitted a bucket.
  `source: "bob"` is reserved by `references/output-formats.md` and buckets he
  did not emit were not invented. Bob's two ⚪ lines that name checks stay
  ordinary findings and are classified normally.

## Reviewer status

- Alice: ✅ Available (Claude subagent, consensus lens, `legacy` engine)
- Blake: ✅ Available (Claude subagent, blind lens, PRD-only; fenced out of
  `docs/dev/tmp/` and `docs/dev/project-management/` so the lens stayed blind)
- Bob: ✅ Available (codex, doubt + de-slop lens, exit 0, first run, no retry;
  thread id captured for cycle 2 resume)
- Carl: ✅ Available (gemini via `backend=copilot model=gemini-3.8-flash`,
  exit 0, non-empty reviewer text)

All four reviewers produced format-compliant issue lines and complete per-rule
verdicts on the first run. No retry was spent, and no reviewer failed.

## Consolidated findings

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [3/4] | 🟠 High | `test_the_wave_pair_passes_under_two_workers` hard-requires pytest-xdist in the interpreter, so every serial run of the cli directory using this repo's own convention (`uv run --no-project --with pytest python -m pytest skills/run-autopilot/cli`) now ends red with "unrecognized arguments: -n". PRD Phase 1 requires "the serial run of the same directory green", and task 2's attempt record patched its own verify command with `--with pytest-xdist` instead of fixing the test. The same red hits the work step-7 full run, the review test line and any contributor run. | skills/run-autopilot/cli/test_parallel_safety.py:35 | 1 | ALICE, BLAKE, BOB |
| [3/4] | 🟠 High | Deviation 1 (`-n 4` for `-n auto`): the stated reason holds but the resolution is incomplete. PRD Phase 2's acceptance (`rg -c "\-n auto" dev/bin/release-checks` at least 1) now returns 0, and the success metric "cli block passes `-n auto`" is unmet. No comment in the script says why 4 was chosen, so the next editor will "fix" it back to `-n auto`. `-n auto --maxprocesses 4` keeps the cap and passes the literal check. | dev/bin/release-checks:46 | 3 | ALICE, BLAKE, BOB |
| [1/4] | 🟠 High | The new `final-verification.md` text tells every project to add `-n auto` and claims this repo's `release-checks` "already proves which suites qualify". The gate runs `-n 4`, and `-n auto` is red on its own waves block. The spec wording was "its release gate already passes it", which is not true of this code. | skills/work/references/final-verification.md:16 | 3 | BLAKE |
| [2/4] | 🟡 Medium | Same bug class left in one place: test_lane_cli.py commits through `_git` with no signing override and no `GIT_CONFIG_GLOBAL` (helper at lines 163-170, commits at 177 and 311, `_solo_repo` at 185, 18 call sites). It is part of the whole-directory `-n auto` run the PRD's headline metric recommends. One-line fix: add `"-c", "commit.gpgsign=false"` to `_GIT_IDENTITY` at line 160. The design doc's claim that "no existing helper disables gpg signing" is wrong: test_enter_decisions.py:510 and custody_testutil.py:28 already do. | skills/run-autopilot/cli/test_lane_cli.py:160 | general | ALICE, BLAKE |
| [1/4] | 🟡 Medium | test_hammer_a / test_hammer_b have no assertion: they only prove the code does not raise. | skills/run-autopilot/cli/test_parallel_safety.py:27 | general | CARL, mech-check |
| [1/4] | 🟡 Medium | Fail-first replay: 3 touched tests pass against the pre-change code (test_hammer_a, test_hammer_b, test_the_wave_pair_passes_under_two_workers). **Verified tool artifact for this diff shape** — see "Mechanical blocks" below. | skills/run-autopilot/cli/test_parallel_safety.py | general | mech-check |
| [1/4] | ⚪ Low | Cannot statically verify: the shipped blocks finish under half their serial time (VERIFY). Compare identical custody core, l3, reporting and waves workloads serially versus four workers; recorded whole-directory timings and waves-only 78.29s are not comparable evidence. | N/A | 3 | BOB |
| [1/4] | ⚪ Low | Cannot statically verify: tests pass (VERIFY). The exact runtime check, `bash dev/bin/release-checks`, is already recorded exit 0 at c502c2f; no full-suite rerun requested. | N/A | general | BOB |

### Consolidation caveat (read before building rework tasks)

`consolidate_findings.py` warned on four rows that it "merged citations that
matched only after suffix stripping". Those merges folded **distinct** defects
that happen to share a file:

- `test_parallel_safety.py:35 ~ :27 ~ :22 ~ :31` — the xdist HIGH, Alice's
  probabilistic-guard Medium, Blake's synthetic-pair Medium and Bob's two
  no-assertion items became one row.
- `dev/bin/release-checks:46 ~ :157 ~ :134 ~ :138` — the `-n auto` HIGH,
  Alice's unpinned-new-block Medium, the missing serial comments and Blake's
  uncovered-test-files Low became one row.
- `test_lane_cli.py:160 ~ :163` — the same finding from two reviewers (a
  correct merge).

The table above was re-expanded by hand where the merge hid a severity or a
separate defect, but it is still lossy. **Every reviewer's findings are kept
verbatim in their own section below, and the rework tasks must be transcribed
from those sections, not from this table.** The over-merge is a defect in this
repo's own consolidator (file-level paraphrase matching collapses unrelated
findings); it is outside PRD 00233's diff and is recorded for batch end.

## Mechanical blocks (computed, not reviewer judgement)

- **Mechanical facts** (per-function line counts from `ast`): no finding
  contradicted them. Largest changed function is
  `test_the_wave_pair_passes_under_two_workers` at 21 lines, well inside the
  50-line limit, so R12 and R13 pass on computed evidence.
- **Tautological shapes**: 2 `[MECH]` lines, both absorbed into the table —
  `test_hammer_a` (line 27) and `test_hammer_b` (line 31) have no assertion.
  Carl raised the same two independently. They are no-assert *by design*: the
  failure mode they pin is `_repo()` raising `CalledProcessError`. Alice judged
  that acceptable as workload for the meta-test while noting they also run as
  plain no-assert tests in every suite run.
- **Fail-first replay**: reported 3 touched tests passing against base. This is
  a **tool artifact for this diff**, verified by reading the script, not a
  reviewer disagreement: `replay_tests_against_base.py:155` overlays every
  changed *test* file from HEAD onto the base worktree, and this PRD's entire
  production fix is one line inside
  `skills/run-autopilot/cli/test_wave_launch.py`, which is itself a test file.
  The overlay therefore restored the fix and the replay compared HEAD against
  HEAD. It could not have reported a failure. The real fail-first evidence is
  the build's recorded run (5 of 6 red at base) plus Blake's independent
  scratch-tree check (hammer pair and meta-test all red with the line removed).
  Kept in the table rather than dropped, with this reason attached.

## Alice (consensus lens)

Measured in-session, cited in preference to the build's numbers:

- Waves block serial: 350 passed in 165.89s. Same block at `-n 4`: 350 passed
  in 79.14s = **47.7% of serial** — meets the PRD's "under half" metric, with
  about 4s of margin.
- `[checks] enter` serial: 180 passed in 1.85s (the build's "about 2s" holds).
- Custody core at `-n auto` (18 workers): failed both runs with `[Errno 35]
  Resource temporarily unavailable`, `[Errno 12] Cannot allocate memory` and
  SIGKILLed git children (second run: 34 failed in 2.69s). **Not gpg** —
  `custody_testutil.py:28` already sets `GIT_CONFIG_GLOBAL=/dev/null`. The
  build's stated reason for `-n 4` is real on this host.
- Custody core at `-n 4`: 123 passed in 4.44s. At `-n auto --maxprocesses 4`:
  123 passed in 5.24s (so the proposed fix is green).
- `test_parallel_safety.py` without xdist: `1 failed, 2 passed`,
  `pytest.main(): error: unrecognized arguments: -n`.
- Git probe: with global `commit.gpgsign=true` and `gpg.program=/usr/bin/false`,
  the pre-fix `_repo()` sequence exits 128; with the local `commit.gpgsign
  false` line it exits 0.

Findings:

```
[ALICE] 🟠 `test_the_wave_pair_passes_under_two_workers` hard-requires pytest-xdist in the interpreter, so every serial run of the cli directory using this repo's own convention (`uv run --no-project --with pytest python -m pytest skills/run-autopilot/cli`) now ends red with "unrecognized arguments: -n". PRD Phase 1 requires "the serial run of the same directory green", and task 2's attempt record patched its own verify command with `--with pytest-xdist` instead of fixing the test. The same red hits the work step-7 full run, the review test line and any contributor run. Fix: `pytest.importorskip("xdist", reason="gated by [checks] parallel safety, which installs pytest-xdist")` as the first line of the test, since the gate block always has xdist, or fail with an explicit "install pytest-xdist" message | File: skills/run-autopilot/cli/test_parallel_safety.py:35 | Task: 1
[ALICE] 🟡 The reproducing guard is probabilistic and host-dependent, so it can pass against the pre-change code. The design doc concedes a host whose global git config lacks `commit.gpgsign=true` (CI, most contributors) never sees the bug. On this host the build recorded 5 of 6 red runs at base, so about 1 in 6 reverts come back green. The replay `[MECH]` line is the overlay artifact the orchestrator note describes, not this finding. Add a deterministic test: monkeypatch `GIT_CONFIG_GLOBAL` to a tmp file holding `[commit] gpgsign = true` and `[gpg] program = /usr/bin/false`, then assert `_repo(tmp_path, {})` returns. At the base commit it fails with CalledProcessError 128 on any host; I verified that mechanism. Keep the `-n 2` pair as the contention proof. `test_hammer_a` and `test_hammer_b` have no assert by design, which is acceptable as workload for the meta-test, but they also run as plain no-assert tests in every suite run | File: skills/run-autopilot/cli/test_parallel_safety.py:27 | Task: 1
[ALICE] 🟡 Deviation 1 (`-n 4` for `-n auto`): the stated reason holds (reproduced above) but the resolution is incomplete. PRD Phase 2's acceptance (`rg -c "\-n auto" dev/bin/release-checks` at least 1) now returns 0, and the success metric "cli block passes `-n auto`" is unmet. No comment in the script says why 4 was chosen, so the next editor will "fix" it back to `-n auto`. Use `-n auto --maxprocesses 4` on lines 46, 74, 85 and 139. That keeps the 4-worker cap, shrinks on hosts with fewer than 4 cores and passes the PRD's literal check; I ran it on custody core and it was green. Add a one-line comment above the first converted block naming the 18-worker exhaustion. Also skills/work/references/final-verification.md:16 says release-checks "already proves which suites qualify" for `-n auto`, but the gate encodes `-n 4` | File: dev/bin/release-checks:46 | Task: 3
[ALICE] 🟡 Deviation 3 (own `[checks] parallel safety` block) is acceptable. The stated reason holds: skills/run-autopilot/cli/test_wave_docs.py:107 asserts the waves block's file set EQUALS a closed set, and the new block does run in the gate (release-checks:134-136). The consequence nobody claimed: the guard now sits in a block no pin covers. test_wave_docs.py, test_enter_prose.py:357 and test_custody_prose.py:317 pin their blocks, but deleting or de-xdisting this one leaves every test green. That is exactly the "never wired into release-checks" blocker the design review found. Add a small pin that reads dev/bin/release-checks and asserts the `[checks] parallel safety` block runs test_parallel_safety.py with `--with pytest-xdist` | File: dev/bin/release-checks:134 | Task: 3
[ALICE] ⚪ Deviation 2 (`[checks] enter` left serial) is acceptable. test_enter_prose.py:382 requires the literal `uv run --no-project --with pytest python -m pytest -q` inside that block, and the block runs 1.85s serial. But the PRD says suites left serial are named by a comment, and neither `[checks] enter` nor `[checks] parallel safety` has one. Add `# serial: ...` lines (enter: invocation text pinned by test_enter_prose.py, about 2s; parallel safety: spawns its own `-n 2` run). A comment above `echo "[checks] enter"` is safe, because test_wave_docs.py drops comment lines and the enter pin cuts its block at "\necho " | File: dev/bin/release-checks:157 | Task: 3
[ALICE] ⚪ Same bug class left in one place: test_lane_cli.py commits through `_git` with no signing override and no `GIT_CONFIG_GLOBAL` (helper at lines 163-170, commits at 177 and 311, `_solo_repo` at 185, 18 call sites). It sits in the serial `effort lanes` block today, but it is part of the whole-directory `-n auto` run that the PRD's headline metric and final-verification.md recommend. It passed 3 consecutive whole-directory runs, so this is not proven flaky. One-line fix: add `"-c", "commit.gpgsign=false"` to `_GIT_IDENTITY` at line 160. Note the design doc's claim that "no existing helper disables gpg signing" is wrong: test_enter_decisions.py:510 and custody_testutil.py:28 already do | File: skills/run-autopilot/cli/test_lane_cli.py:160 | Task: general
```

Alice's judgement on the three deviations: all three stated reasons check out
against the code. Deviation 1 is accepted on the merits but fixable to meet the
PRD literally. Deviations 2 and 3 are accepted, each with a small follow-up.
`-n 4` satisfies "under half" on the dominant waves block (47.7%); the CHANGELOG
line "roughly in half" is fair but the margin is thin.

Per-rule verdicts:

```
R1: fail
R2: fail
R3: pass
R4: fail
R6: pass
R7: pass
R8: pass
R9: fail
R10: pass
R11: pass
R12: pass
R13: pass
```

## Blake (blind lens, PRD-only)

Blake received the PRD, the blind rubric and the output format, and nothing
else — no diff, no changed-file list, no design doc, no review history. He
located the code himself and ran it. He notes he could not check the design
doc's `## Root cause` section or its before/after timing, which is correct for
this lens.

What he ran: `-n auto` over `skills/run-autopilot/cli` three times (1949 passed
each, ~77s); `bash dev/bin/release-checks` green once; the waves file list under
`-n auto` twice (red both times); `test_parallel_safety.py` without xdist (1
failed); and a scratch copy of the tree with the `commit.gpgsign` line removed,
where `test_hammer_a`, `test_hammer_b` and the meta-test all fail.

Findings:

```
[BLAKE] 🟠 `release-checks` uses `-n 4` everywhere and never `-n auto`, contradicting the spec. `rg -c "\-n auto" dev/bin/release-checks` prints nothing, so the Phase 2 acceptance fails. The "run-autopilot cli block passes -n auto" metric is also unmet. No comment in the script explains the choice; the reason (fork exhaustion at 18 workers) is only in the commit message. I reproduced that exhaustion: the waves block under `-n auto` fails with `git worktree add` exit 255, `git` killed by SIGKILL, and `BlockingIOError [Errno 35]` at fork. So the deviation is empirically sound. It also means the spec's premise, that the wave family is proven worker-safe at `-n auto`, is false, and the process-table exhaustion is a second shared resource that is not isolated. | File: dev/bin/release-checks:46 | Task: 3
[BLAKE] 🟠 The new `final-verification.md` text tells every project to add `-n auto` and claims this repo's `release-checks` "already proves which suites qualify". The gate runs `-n 4`, and `-n auto` is red on its own waves block. The spec wording was "its release gate already passes it", which is not true of this code. | File: skills/work/references/final-verification.md:16 | Task: 3
[BLAKE] 🟠 `test_the_wave_pair_passes_under_two_workers` hard-fails when pytest-xdist is not installed: the subprocess errors with `unrecognized arguments: -n`. There is no `pytest.importorskip("xdist")`. A plain `--with pytest` run of the `cli` directory, the pre-change serial form, now ends with a red test. Phase 1 requires "the serial run of the same directory green". | File: skills/run-autopilot/cli/test_parallel_safety.py:35 | Task: 1
[BLAKE] 🟡 The "reproducing pair" is synthetic. `test_hammer_a` and `test_hammer_b` each start 12 threads that call `_repo`. Both fail alone at base, so they do not match the spec's "two tests that fail together under -n 2 and pass alone". `-n 2` is incidental to the failure, and the test does not prove cross-worker sharing. On a host without a global `commit.gpgsign=true` (CI, most dev machines) it passes without the fix, so it is a host-dependent guard. A direct assertion that the `_repo` repo has `commit.gpgsign` false would work on any host. | File: skills/run-autopilot/cli/test_parallel_safety.py:22 | Task: 1
[BLAKE] 🟡 Isolation was applied to one fixture only; the same global-config exposure remains elsewhere. `test_lane_cli.py` commits with the real global config (`_git` at line 163, commits at lines 177 and 311). Production `custody.py:454` runs `git revert` through `_git` with the process environment, and custody tests isolate only their own helper. There is no `conftest.py` in `cli/`, and a single autouse isolation would remove the whole class. This is partly outside the spec's "wave family" scope. | File: skills/run-autopilot/cli/test_lane_cli.py:163 | Task: 2
[BLAKE] ⚪ The `enter` block is proven worker-safe but left serial with no comment naming it. The spec requires "a comment names them". The reason, the pin in `test_enter_prose.py:357-383` that fixes the invocation text, is only in the commit message. | File: dev/bin/release-checks:157 | Task: 3
[BLAKE] ⚪ `test_wave_cli_refusals.py` and `test_wave_assemble_summary.py` are in no `release-checks` block. The first is one of the spec's named failing wave files. This predates the PRD, but the gate never exercises them in parallel. | File: dev/bin/release-checks:138 | Task: 3
[BLAKE] ⚪ `test_hammer_a` and `test_hammer_b` run as ordinary tests in every full run. Each starts 12 concurrent git chains, which adds load near the process-limit hazard in the first finding. | File: skills/run-autopilot/cli/test_parallel_safety.py:27 | Task: 1
```

Per-rule verdicts:

```
B1: fail
B2: pass
B3: pass
B4: pass
B5: pass
B6: pass
B7: pass
B8: pass
B9: pass
B10: pass
B11: pass
B12: pass
B13: pass
B14: pass
B15: fail
B16: fail
B17: pass
B18: pass
B19: pass
```

## Bob (doubt + de-slop lens, codex)

Ran on the first dispatch, exit 0, no retry. Thread id
`01a0f52f-510c-72d1-a079-73e9848465ec` captured for cycle 2's
`--resume-thread`.

Findings:

```
[BOB] 🟡 FIX: Four `-n 4` invocations leave Phase 2's explicit `-n auto` acceptance check unsatisfied. Use `-n auto --maxprocesses=4` to retain the resource cap and meet the requirement. | File: dev/bin/release-checks:46 | Task: 3
[BOB] 🟡 FIX: Mechanical shapes flag test_hammer_a's missing assertion. Successful commits do not establish signing isolation when host signing is already disabled; assert each created repo's local commit.gpgsign is false while retaining concurrency. | File: skills/run-autopilot/cli/test_parallel_safety.py:27 | Task: 1
[BOB] 🟡 FIX: Mechanical shapes flag test_hammer_b's missing assertion. Assert each created repo's local commit.gpgsign is false so this test pins the fixture change independently of host signing settings. | File: skills/run-autopilot/cli/test_parallel_safety.py:31 | Task: 1
[BOB] ⚪ Cannot statically verify: the shipped blocks finish under half their serial time (VERIFY). Compare identical custody core, l3, reporting and waves workloads serially versus four workers; recorded whole-directory timings and waves-only 78.29s are not comparable evidence. | File: N/A | Task: 3
[BOB] ⚪ Cannot statically verify: tests pass (VERIFY). The exact runtime check, `bash dev/bin/release-checks`, is already recorded exit 0 at c502c2f; no full-suite rerun requested. | File: N/A | Task: general
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

## Carl (gemini, frontend & design specialist, generalist here)

`backend=copilot model=gemini-3.8-flash`, exit 0, non-empty output. No frontend
surface in this diff, so he reviewed as a generalist, as his persona directs.
He verified the three deviations against the pins and judged all three sound:
`-n 4` prevents host fork exhaustion while still beating half the wall clock;
the serial `enter` block respects `test_enter_prose.py`'s pin for ~2s of
runtime; and the separate block respects `test_wave_docs.py`'s closed set while
still running in the gate.

Findings:

```
[CARL] 🟡 test_hammer_a has no assertion: it only proves the code does not raise | File: skills/run-autopilot/cli/test_parallel_safety.py:27 | Task: general
[CARL] 🟡 test_hammer_b has no assertion: it only proves the code does not raise | File: skills/run-autopilot/cli/test_parallel_safety.py:31 | Task: general
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

Run in this session, not taken on trust:

- **Serial `test_parallel_safety.py`, the exact failing shape:**
  `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_parallel_safety.py`
  → **1 failed, 2 passed**, with
  `pytest.main(): error: unrecognized arguments: -n`. This independently
  reproduces the 3/4-consensus HIGH; it is confirmed, not suspected.
- **Full suite, foreground:**
  `uv run --no-project --with pytest python -m pytest -q --continue-on-collection-errors hooks skills`
  → **1 failed, 4199 passed, 1 skipped, 3 errors**, 1049 subtests passed,
  259.99s. The single failure is
  `test_parallel_safety.py::test_the_wave_pair_passes_under_two_workers`. The 3
  errors are the settled `ModuleNotFoundError: No module named 'rich'`
  collection failures in `tracon/test_panels.py`, `test_screens.py` and
  `test_stream.py`, identical to the prior PRD's cycles.
- **Why the suite ran at all:**
  `docs/dev/project-management/autopilot/last-verification.json` carries the
  right `sha` (`c502c2f…`) but **null `passed`/`failed`/`skipped`**, so the
  reuse precondition fails and a fresh run was mandatory. The build's recorded
  green is `bash dev/bin/release-checks` exit 0, which is true and not in
  conflict: the gate's new `[checks] parallel safety` block installs
  pytest-xdist, so the gate never exercises the broken serial path.
- **The replay artifact** was confirmed by reading
  `replay_tests_against_base.py:155`, not inferred.
- Working tree clean before and after this review; no reviewer modified the
  repo.

## Assessment

The root-cause diagnosis and the one-line fixture fix are sound and were
independently re-derived by two reviewers. The PRD's headline metric holds:
`-n auto` over `skills/run-autopilot/cli` is green 3/3 at ~77s against ~245s
serial, and the dominant waves block is 47.7% of serial at `-n 4`.

What blocks this cycle is narrower and concrete: the new regression guard made
the project's own serial suite red, and the Phase 2 acceptance check plus the
prose it shipped now describe a `-n auto` the gate does not use. Both are small
fixes with named shapes.

Verdict: 8 findings
Tests: 4199 passed, 1 failed, 1 skipped (suite run this cycle)
