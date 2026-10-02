---
prd: dev/local/prds/wip/00179-cap-the-adversarial-test-loop-at-one-round-v1.md
review: 1
date: 2026-09-06
head_sha: 3de0c061edc7c71265cc2e5196679fafac09ccbe
codex_thread_id: 01a0781c-d4d6-7631-a8c8-6ab289655677
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00179-cap-the-adversarial-test-loop-at-one-round-v1

Diff range: `f2488270e82e63b8468f853a3985d6e4868f96b5..3de0c061edc7c71265cc2e5196679fafac09ccbe`

codex_rung_guard: not fired

pack: failed (`engram pack` exited 1: "not inside a registered repo; register it in /Users/bob/.config/gita/repos.csv"). Not retried — the failure is a deterministic registration precondition, not a transient error. `{PACK_FILE}` and `{PACK_FINDINGS}` were substituted with `(no pack available this cycle)` in every prompt that takes them. The review is degraded on retrieval context, not invalid.

diff-scope note: `gather-context.sh`'s own base detection resolves to `master`, and this repo commits directly to `master`, so its bare run would produce a **0-line diff**. The gather was run with `--since f2488270e82e63b8468f853a3985d6e4868f96b5` (`state.work_start_sha`) to produce the PRD's real 137-line, 5-file work-range diff. Despite the flag's name this is a **full** cycle-1 review, not an incremental one.

## Reviewer status

- Alice: ✅ Available (Claude subagent, consensus lens; exit 0, no retry needed)
- Blake: ✅ Available (Claude subagent, blind/PRD-only lens; exit 0, no retry needed). Filesystem-notes block not added — neither trigger holds (`dev/local` is a real directory, project root basename is `claude-autopilot`).
- Bob: ✅ Available (codex CLI, doubt + de-slop lens; exit 0, first dispatch, no retry needed). Notable: `state.codex_probe.verdict` is `unhealthy` for this batch, and the gateguard PreToolUse hook blocked his first two `sed` reads; he recovered within the same run and produced a full review with all `R{n}` and `D{n}` verdict lines.
- Carl: ✅ Available (gemini via `backend=copilot model=gemini-3.8-flash`; exit 0, 4.16 AI credits, 27s)
- Eve: ⏸️ Disabled — the codex doubt-roster guard did not fire (`state.tasks[].attempts[].implementor` is `claude` on both tasks), and `state.doubt_reviewer` is `codex`.

`codex_thread_id` stamped: `01a0781c-d4d6-7631-a8c8-6ab289655677`. A cycle 2 would resume Bob's session with `--resume-thread`.

## Consolidated Findings

3 findings, all raised by Bob alone. Severity split: 0 🔴 Critical, 0 🟠 High, 2 🟡 Medium, 1 ⚪ Low.

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [1/4] | 🟡 | FIX: All three tests search entire files, so they pass if cap text moves outside Outcomes or steps 2.8/2.85; slice each named section before asserting, following `test_dispatch_prose.py` precedent | skills/work/scripts/test_adversarial_cap_prose.py:27 | 2 | BOB |
| [1/4] | 🟡 | FIX: `Path(__file__).resolve().parent.parent` is computed twice; define the work directory once and derive both target paths from it | skills/work/scripts/test_adversarial_cap_prose.py:15 | 2 | BOB |
| [1/4] | ⚪ | Cannot statically verify: run `uv run --no-project --with pytest python -m pytest -q skills/work/scripts/test_dispatch_prose.py`, `uv run --no-project --with pytest python -m pytest -q skills/work/scripts/test_adversarial_cap_prose.py`, and `bash dev/bin/release-checks` to confirm all current-head checks pass and the new suite reports 3 passed | N/A | general | BOB |

Consolidation ran through `consolidate_findings.py` (script path, not model-side). No ledger existed for this PRD (cycle 1), so the two `--ledger` flags were omitted and no Blake finding was auto-dismissed.

Carry-forward: none — this is cycle 1, so there is no `-checks-0.json` queue file to read.

Mechanical test checks absorbed: none. Both computed blocks came back clean — `detect_tautological_tests.py` emitted zero `[MECH]` lines across the 3 test functions in 1 test file, and `replay_tests_against_base.py` reported 3 touched tests ran, **3 failed against base, 0 passed**, so every new test genuinely pins this change. (Bob's `R2: fail` is not supported by that computed replay result.)

Verification-check queue: **not written**. Bob is the only doubt lane that ran, and `agents/bob.md` defines no FIX/VERIFY/KNOWN buckets — his output is `[BOB]` issue lines plus `R{n}`/`D{n}` verdicts. Eve did not run. Per `references/output-formats.md` § Verification-check queue, `source: "bob"` is reserved and no bucket may be invented, so this cycle queues nothing. The ⚪ Low finding above names exact commands, but it arrives as an ordinary issue line, not a VERIFY bucket item, and is classified normally.

## Alice

`[ALICE] ✅ No issues found`

Verified by direct execution: `test_adversarial_cap_prose.py` → 3 passed; `test_dispatch_prose.py` → 32 passed (SKILL.md still 499 lines, under the 500 ceiling); `bash dev/bin/release-checks` → all blocks green. All five PRD `rg` acceptance counts confirmed exactly (`Max 1 Tess/Devon round`→1, `Max 2 Tess/Devon rounds`→0, `max 4 dispatches`→1, `max 5 dispatches`→0, `test_adversarial_cap_prose.py` in `release-checks`→1). Contract text matched byte-for-byte; the § Feedback to Tess block, the first outcome-table row, `test-author-prompt.md` and `red-check.md` confirmed untouched. `git diff --stat` matches the declared 5 files / 76+ / 4- — no scope creep.

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

## Blake

`[BLAKE] ✅ No issues found`

Located the implementation independently from the PRD alone and confirmed: the two outcome-table rows read byte-for-byte as specified; `SKILL.md:242` carries the exact `max 4 dispatches` paragraph and step 2.85 (line 256) gains exactly the specified first sentence; the new test file carries exactly the three named tests with the specified present/absent strings; `release-checks` gained the `[checks] adversarial cap prose` block in the existing pattern and ran fully green; `CHANGELOG.md` carries the exact Changed bullet. Every Phase 0 and Phase 1 acceptance command was executed. Diff footprint touches exactly the 5 files the PRD's Repository Structure lists. Declared-unchanged items (`test-author-prompt.md:80`, `red-check.md`'s accidentally-green row) confirmed untouched.

B1: pass
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
B15: pass
B16: pass
B17: pass
B18: pass
B19: pass

## Bob

[BOB] 🟡 FIX: All three tests search entire files, so they pass if cap text moves outside Outcomes or steps 2.8/2.85; slice each named section before asserting, following `test_dispatch_prose.py` precedent | File: skills/work/scripts/test_adversarial_cap_prose.py:27 | Task: 2
[BOB] 🟡 FIX: `Path(__file__).resolve().parent.parent` is computed twice; define the work directory once and derive both target paths from it | File: skills/work/scripts/test_adversarial_cap_prose.py:15 | Task: 2
[BOB] ⚪ Cannot statically verify: run `uv run --no-project --with pytest python -m pytest -q skills/work/scripts/test_dispatch_prose.py`, `uv run --no-project --with pytest python -m pytest -q skills/work/scripts/test_adversarial_cap_prose.py`, and `bash dev/bin/release-checks` to confirm all current-head checks pass and the new suite reports 3 passed | File: N/A | Task: general

R1: fail
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
D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

Orchestrator note on Bob's precedent claim (checked, not assumed): `test_dispatch_prose.py` does slice sections (`_TEXT.index("### 5.7.")` and friends, 14 such slices) alongside whole-file substring assertions, so his cited precedent is real. The PRD's own verbatim contract, however, specifies only "read once, assert short reword-resistant substrings" and names the exact assert strings — section scoping is an improvement beyond the contract, not a contract breach.

## Carl

`[CARL] ✅ No issues found`

Read the context and diff, then ran `test_adversarial_cap_prose.py`, `test_dispatch_prose.py` and the five PRD `rg` acceptance checks. Backend: `copilot`, model `gemini-3.8-flash`, 4.16 AI credits, 27s.

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

Verdict: 3 findings
Tests: 2634 passed, 0 failed, 1 skipped (suite run this cycle)

Test-run note: `last-verification.json` matched this cycle's HEAD but carries `null` for all three counts (it records only `bash dev/bin/release-checks` → exit 0), so the counts could not be reused and the suite was run this cycle. The run is `uv run --no-project --with pytest --with rich --with textual python -m pytest -q skills`. The two extra `--with` flags are required: without them, `skills/run-autopilot/scripts/tracon/{test_panels,test_screens,test_stream}.py` fail collection with `ModuleNotFoundError: No module named 'rich'` and pytest exits 2 having run nothing. That is a pre-existing environment gap in this repo, unrelated to this diff.
