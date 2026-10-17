---
head_sha: a630774c60b1c1f3b7847e581aea78ce3fcd53a2
reviewers: alice, blake, eve, bob, carl
---

## Alice

**00334-keep-the-test-only-skip-when-a-test-registers-itself-v1-c1**
🟠 Putting the release-checks exact match inside the shared `is_test_path` (skills/work/scripts/work_routing.py:249) also changes lane routing — `lane.is_production_path` now returns False for `dev/bin/release-checks`, breaking `skills/run-autopilot/cli/test_lane.py:127`. CONFIRMED and fixed in rework (scoped the exemption to `test_only_diff` via a new `_TEST_INFRA_PATHS` set; `is_test_path` restored to strict).
🟠 `lane.classify` now routes a release-checks-only PRD to the solo lane (`no_production_code`). Same root cause as above — CONFIRMED and fixed by the same rework.
🟡 PRD named `_TEST_INFRA_PATHS` as the new symbol; cycle-1 code inlined the literal instead. Resolved by the rework (the constant now exists and is what `test_only_diff` filters on).
⚪ Docstring/doc-wrap/sibling-doc/qwen-output/800-line-file nits — recorded, not blocking (surviving set).

## Blake

**00334-keep-the-test-only-skip-when-a-test-registers-itself-v1-c1**
🟠 `test_lane.py::test_production_path_excludes_tests_docs_and_packaging` fails at HEAD (cycle 1) — `1 failed, 51 passed`. CONFIRMED and fixed in rework — rerun after rework: `52 passed`.
🟠 Fail-open beyond the PRD's scope (lane.py, classify_tier.py, style-gate all share `is_test_path`). Same root cause, same fix.
🟡 Not built as the PRD said (`_TEST_INFRA_PATHS` missing in cycle 1). Resolved by the rework.
🟡 Doc sentence overstated the rule (registration-only vs whole-file). Resolved by the rework's rewritten sentence.
⚪ PRD-wording / gates-coverage nits — recorded, not blocking.

## Eve

**00334-keep-the-test-only-skip-when-a-test-registers-itself-v1-c1 (round 1)**
Verdict: NOT clean. Confirmed the same `is_test_path` leak into `lane.py`/`classify_tier.py` with a direct test run (`test_lane.py` 1 failed, 122 passed). FIX items addressed in rework: scoped `_TEST_INFRA_PATHS` exemption, retargeted/added tests, rewritten doc sentence. D1-D5: pass/pass/pass/pass/pass.

**00334-keep-the-test-only-skip-when-a-test-registers-itself-v1-c1 (delta, rework scope)**
Verdict: all three prior findings RESOLVED, verified by rerunning `test_lane.py` (52 passed) and the card's two gates (191 passed) plus dependent suites (223+ passed, no failures). Raised 6 new FIX items (one — a stray formatter reflow of `route()`'s signature — reverted directly in this session as tool noise; the other 5 are LOW and carried into the surviving set), 1 VERIFY (a runtime check for the next batch task), 3 KNOWN (accepted out of scope). D1-D5: pass/pass/pass/pass/pass.

## Bob

**00334-keep-the-test-only-skip-when-a-test-registers-itself-v1-c1**
Missing — the codex CLI lane failed on both its initial dispatch and its one retry: a sandbox/hook fault ("Fact-Forcing Gate" PreToolUse block) prevented every file read before any review content was produced. No findings; recorded as a missing lane, not a pass.

## Carl

**00334-keep-the-test-only-skip-when-a-test-registers-itself-v1-c1**
🟡 `_TEST_INFRA_PATHS` constant omitted, literal inlined instead (cycle 1). Resolved by the rework.
⚪ `test_work_routing.py` over the 800-line file limit (pre-existing, PRD's own placement choice). Recorded, not blocking.
R9: fail (PRD-vs-code mismatch at cycle 1) — resolved by the rework; R13: fail (file-size limit, pre-existing) — recorded, not blocking.

Verdict: 4 findings

All 4 are LOW severity, surviving after rework; see docs/dev/tmp/00334-keep-the-test-only-skip-when-a-test-registers-itself-v1-c1-fast-track-review.md for the full consolidated table, the Verify/Rework/Delta/Exit narrative, and the surviving-set detail.
Tests: 7170 passed, 0 failed, 3 skipped (fast-track batch suite)
codex_rung_guard: not fired
