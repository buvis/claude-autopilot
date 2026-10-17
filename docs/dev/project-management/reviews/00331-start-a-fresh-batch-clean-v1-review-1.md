---
head_sha: 7c4c12e189d9e14fc064b2afbd54df4c6d49e11b
reviewers: alice, blake, eve, bob, carl
---

## Alice

**00331-start-a-fresh-batch-clean-v1-c1**
🟠 PRD Must-have not met. The PRD says the `batch_init` stop detail must read exactly `batch <absent|closed>; mint state.batch with statectl (phase-build.md Phase 0 step 3), then run enter again; never autopilot init`. The diff only rewrote the `absent` branch; a closed batch still got the old `batch closed; initialize a batch first` text. File: skills/run-autopilot/cli/enter.py. **CONFIRMED by Victor, fixed in rework.**
🟡 The new detail test only checked the absent case. File: skills/run-autopilot/cli/test_enter.py. Resolved as a side effect of the rework's parametrize.

## Blake

**00331-start-a-fresh-batch-clean-v1-c1**
🟠 The closed-batch case of `_batch_report` still said "initialize a batch first" instead of the statectl-route text. File: skills/run-autopilot/cli/enter.py. **Same finding as Alice's, confirmed, fixed in rework.**
🟡 No test checked the closed-case detail. File: skills/run-autopilot/cli/test_enter.py. Resolved by the rework's parametrize.
⚪ Cleanup can fail halfway (an unlink OSError after state.init leaves a stale brief/card undetected on the next enter) — unlikely, conforms to spec. File: skills/run-autopilot/cli/enter.py. Deferred (KNOWN, out of scope for this card).

## Eve

**00331-start-a-fresh-batch-clean-v1-c1 (round 1)**
FIX: the closed-batch detail gap (same as Alice/Blake). Confirmed, fixed in rework.
VERIFY: (none)
KNOWN: `references/phase-build.md`'s brief-read prose line still names a stale brief before `enter()` runs, out of this card's `## Files` scope; `autopilot init` also mints state without clearing brief/card, out of scope; a closed batch with `state.json` present correctly keeps its brief.
D1: pass, D2: pass, D3: pass, D4: pass, D5: pass

**00331-start-a-fresh-batch-clean-v1-c1 (delta, rework range a2c7cf9a..7c4c12e1)**
FIX: (none)
VERIFY: (none)
KNOWN: the CHANGELOG entry's wording ("the batch-absent stop names the statectl route") doesn't call out the closed case explicitly, though the fix now covers both — out of scope to reword a PRD-given CHANGELOG string; the parametrized test duplicates two of three arrangements already covered by `test_absent_and_closed_batch_stop_batch_init` — costs only test duplication, not worth touching.
D1: pass, D2: pass, D3: pass, D4: pass, D5: pass
Verdict: prior HIGH resolved, no regression.

## Bob

**00331-start-a-fresh-batch-clean-v1-c1**
⚪ Cannot statically verify: codex's own local Fact-Forcing Gate PreToolUse hook blocked every `cat` command before it could read the review context or diff, on both the initial dispatch and its one retry. No real findings produced. Counted as a failed lane after the one-retry budget.

## Carl

**00331-start-a-fresh-batch-clean-v1-c1**
🟡 `_batch_report` branches on absent and retains the stale "initialize a batch first" detail for closed batches instead of inlining the PRD's statectl route. File: skills/run-autopilot/cli/enter.py. Same finding as Alice/Blake, confirmed, fixed in rework.
🟡 `skills/run-autopilot/cli/test_enter.py` grew to 832 lines, exceeding the repo's 800-line limit. File: skills/run-autopilot/cli/test_enter.py. Deferred (MEDIUM, out of scope for this one-finding card; file is 843 lines post-rework, still over the limit — worth a follow-up PRD).

Verdict: converged
Tests: 7148 passed, 0 failed, 3 skipped (fast-track batch suite, `dev/bin/release-checks`)
codex_rung_guard: not fired
