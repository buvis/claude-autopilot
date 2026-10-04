---
head_sha: 8a983f5545b1c9f7675a50f06c1a8fd17dbde5c9
reviewers: alice, blake, eve, bob, carl
---

# Review: 00250-finish-the-rework-grouping-fixes-v1

Diff range: `cc452692714bb5fcc2c262c944c953f30417a82b..8a983f5545b1c9f7675a50f06c1a8fd17dbde5c9`

codex_rung_guard: not fired

## Alice

**00250-finish-the-rework-grouping-fixes-v1-c1**
Round 1: 🟠 `_LINE_SUFFIX` not replaced with the exact mandated canonical pattern — shapes `a/b.py#L12-20`, `a/b.py (lines 18 - 22)` stayed unstripped. 🟡 `file_key` docstring not updated. ⚪ stale "Split rule" wording in a test comment. ⚪ an uncommitted loupe reflow caught and reverted before commit (not shipped).
Verified CONFIRMED by `autopilot:victor`. Reworked: regex replaced with the canonical pattern verbatim; docstring updated.
Delta (round 2, post-rework): resolved. No regression. Two new MEDIUM/LOW test-coverage gaps noted (no regression test pinning the two shapes; no parity test between the two regex copies) — neither CRITICAL nor HIGH, left for the normal tail sweep.
R1-R8,R10-R13: pass both rounds. R9: fail round 1, not re-asked round 2 (delta lens uses D-rubric only).

## Blake

**00250-finish-the-rework-grouping-fixes-v1-c1**
Round 1: 🟠 same regex-parity gap, confirmed independently with 4 concrete failing inputs. 🟡 docstring gap. ⚪ Tail sweep wording deviation judged defensible. ⚪ no parity test.
B1: fail. B2-B19: pass.

## Eve

**00250-finish-the-rework-grouping-fixes-v1-c1**
Round 1 (doubt): FIX — regex not the mandated pattern; no parity test; docstring gap; stale PRD-number citation in the new prose test; the "never says one task" test only bans two exact strings. VERIFY: none. KNOWN: card's premise partly stale; hold-stub deletion carries no V7 re-mint risk.
D1-D5: pass.
Delta (round 2): prior finding resolved (regex now byte-identical to the canonical pattern; both cited shapes strip correctly); no regression. Raised two new FIX items (test-coverage gaps on the fix, both MEDIUM/LOW, not re-verified).
D1-D5: pass (round 2).

## Bob

**00250-finish-the-rework-grouping-fixes-v1-c1**
Round 1: 🟠 regex misses canonical citation shapes `a/b.py#L12-20` and `a/b.py (lines  3-4)`. ⚪ docstring gap. ⚪ cannot statically verify test/release-checks results (sandboxed).
R1-R8,R10-R13: pass. R9: fail.
(Output also echoed the Output Format spec's own worked examples as literal findings — discarded as prompt-echo artifacts, not real issues about this diff.)

## Carl

**00250-finish-the-rework-grouping-fixes-v1-c1**
Round 1: 🟠 `_LINE_SUFFIX` diverged from canonical `_TRAILING_LINENO_RE`, misses `#L12-20`. 🟡 docstring gap.
R1-R8,R10-R13: pass. R9: fail.

Verdict: converged
Tests: 25 passed, 0 failed, 0 skipped (fast-track batch suite, `bash dev/bin/release-checks`)
codex_rung_guard: not fired
