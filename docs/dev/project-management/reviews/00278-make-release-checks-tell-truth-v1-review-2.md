---
prd: docs/dev/project-management/prds/wip/00278-make-release-checks-tell-truth-v1.md
review: 2
date: 2026-10-13
head_sha: e0101faa837c7e75a924a2c2056c4590255c69ac
codex_thread_id: 01a134bf-6d96-7e52-9378-fe6491cb5f02
reviewers: alice,blake,bob
agents:
  alice: available
  blake: available
  bob: available
  carl: unavailable
dispatch_rows:
  bob: 58f68457
  carl: db2dc4d5
---

# Review: 00278-make-release-checks-tell-truth-v1 (cycle 2, incremental)

Diff range: `80beb7ade23c288466b6ae9440540e4be10c67fa..e0101faa837c7e75a924a2c2056c4590255c69ac`

codex_rung_guard: not fired

## Review Summary

Reviewed: 13 completed tasks (incremental: the cycle-1 rework commits only)
PRDs checked: 00278-make-release-checks-tell-truth-v1

### Agent Status

- Alice: ✅ Available (consensus lens, legacy engine)
- Blake: ✅ Available (blind lens, PRD-only)
- Bob: ✅ Available (doubt lens + de-slop, codex) — after one retry (inlined). His first run returned a lack-of-input refusal (no file contents read, every `R{n}` marked fail with the stated reason "missing cycle-2 evidence"); the inlined retry supplied the context and diff verbatim and produced a full review.
- Carl: ⚠️ Unavailable: gemini-run backend=copilot model=gemini-3.8-flash exited 1 — "Authentication failed", GitHub Copilot token invalid/expired. Retried once, same failure. Not a permanent (exit 4) unavailability, so no batch latch.
- Eve: ⏸️ Disabled: resolved doubt reviewer is `codex` and the codex doubt-roster guard did not fire (no codex-implemented task in this PRD).

Notes on this cycle's inputs:

- pack: failed (engram pack exit 1: `sqlite3.OperationalError: attempt to write a readonly database`) — degraded, not invalid; Alice's and Bob's prompts carried the `(no pack available this cycle)` sentinel.
- Consolidation ran via `consolidate_findings.py` with `--ledger` and `--ledger-dismiss BLAKE`; two Blake rows were auto-dismissed against settled cycle-1 deferrals (listed below).
- Working-tree note: three touched test files carried a formatter reflow (trailing commas, line wrapping) at session start with no behavior change; it was reverted with `git checkout` before the cycle ran, so the reviewed tree is the committed tree.
- Bob's VERIFY item (R9) is **not queued** as a verification check: it asks for a two-revision wall-time benchmark in isolated checkouts, which has no pass/fail exit to record, so it stays an ordinary ⚪ finding (same call as cycle 1's R15).

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [2/3] | 🟠 | Prior findings R7, R10 and R11 are not resolved. `test_allow_corpus_ignores_scratch_dispatch_files` is now tautological. It writes the scratch file into `tmp_path`, which neither the current `_allow_corpus()` nor the old one ever globs, so the second assert cannot differ from the first. The fail-first replay confirms it passes at base. The isolation fix removed the only thing the test could detect. Fix: write the scratch file to the real `docs/dev/tmp` under a unique name (for example `dispatch-zzz-<uuid>.txt`) in a try/finally and assert `_allow_corpus() == sorted((FIXTURES / "allowed").glob("*.txt"))` before and during. That is the design's sanctioned form, and it fails against the old `real or fixtures` implementation. Alternatively monkeypatch a module-level `CORPUS` that the code under test actually reads. | hooks/test_guard_phase_delegation.py:98 | 12 | ALICE, BLAKE, mech-check |
| R2 | [1/3] | 🟠 | The docs added for red test 1 describe invocations that do not exist. state-schema.md says `autopilot group-rework <state.json>` and `autopilot review-stage <state.json> <review-file>` ("stage a finished review file for the decision gate"). The parsers take `group-rework --findings <path>` (cli/__main__.py:835) and `review-stage --cycle-id --gate-command [--state ...]` (cli/__main__.py:1014-1025). The correct review-stage form already sits at skills/review-work-completion/SKILL.md:153. test_doc_contract goes green on a false doc, so an operator following it gets an argparse error. Use the real argument forms. | skills/run-autopilot/references/state-schema.md:540 | 1 | BLAKE |
| R3 | [1/3] | 🟡 | Prior R1 is only half resolved. The new comment in `dev/bin/release-checks` names `hooks/test_guard_phase_delegation_scratch_replay.py` literally. The pin uses a plain `path not in text` check, so that path passes the pin whether or not `UNGATED` lists it. The `UNGATED` entry is dead again, and removing it would not fail any test. Fix: reword the comment so it does not repeat the path (for example "the scratch-replay hook test is intentionally UNGATED"). Or add a test that every `UNGATED` path is absent from the script text. | dev/bin/release-checks:128 | 10 | ALICE |
| R4 | [1/3] | 🟡 | The gate pin accepts any substring hit in the script text. A test path that appears only in a comment or `echo` counts as gated. `_dir_is_bare_target` also treats a bare directory word in a comment as gating every test under it; the docstring admits this at skills/run-autopilot/cli/test_release_checks_counts.py:325. The spec says "paths literally named in the script". Today this is a theoretical hole: the real script's directories evaluate correctly, and only skills/fast-track/scripts matches. Matching only inside `run_pytest`/`run_harness` argument lines would close it. | skills/run-autopilot/cli/test_release_checks_counts.py:344 | 9 | BLAKE |
| R5 | [1/3] | 🟡 | The scratch file is created under `tmp_path`, but nothing redirects corpus discovery there. Restoring the original scratch-reading implementation can therefore pass in a clean checkout. Monkeypatch its corpus location to the isolated directory, retain the committed-fixture assertions, and verify failure with the original `_allow_corpus` restored. This leaves prior R10/R11 incompletely resolved. | hooks/test_guard_phase_delegation.py:98 | 12 | BOB, mech-check |
| R6 | [1/3] | ⚪ | `test_the_fast_track_lane_whole_directory_target_is_a_gated_target` passes at base. It pins the existing `skills/fast-track/scripts` target in the real script rather than new logic, so this is acceptable as a regression pin. It will go red if someone renames that target, which is the intent. No change needed. | skills/run-autopilot/cli/test_release_checks_counts.py:398 | 13 | ALICE, mech-check |
| R7 | [1/3] | ⚪ | I measured the gate at 5m08s wall (sandboxed host), against the ~220 s baseline. I did not find the new wall time in anything I read, so I could not confirm the task-report requirement. | dev/bin/release-checks | 9 | BLAKE |
| R8 | [1/3] | ⚪ | The CHANGELOG packet-7 bullet is not the "observed split" form (denies X, still allows Y). It says the four phrasings "now correctly deny (PRD 00271)". I confirmed that is true at HEAD: with `_AUTOPILOT_LOOP=1`, the four delegation phrasings exit 2 and "Do the work phase tests pass?" exits 0. The old "stays allowed" text is gone and 00271 is cited inside [Unreleased]. Accurate, so only a form deviation. | CHANGELOG.md:37 | 7 | BLAKE |
| R9 | [1/3] | ⚪ | The required gate wall-time report remains absent from the supplied evidence. Measure `/usr/bin/time -p bash dev/bin/release-checks` in isolated checkouts at original implementation base `a15cbe13bcee0e6b6cb68ae9d44ae9eeda537255` and reviewed revision `e0101faa837c7e75a924a2c2056c4590255c69ac`; record both elapsed times and their delta in the task report. | N/A | 10 | BOB |

Mechanical test checks absorbed into the rows above (context file, step 3):

- `[MECH] 🟡 1 touched test(s) pass against the pre-change code: test_allow_corpus_ignores_scratch_dispatch_files | File: hooks/test_guard_phase_delegation.py` → folded into R1 and R5.
- `[MECH] 🟡 1 touched test(s) pass against the pre-change code: test_the_fast_track_lane_whole_directory_target_is_a_gated_target | File: skills/run-autopilot/cli/test_release_checks_counts.py` → folded into R6.

No tautological-shape test was reported (57 test functions checked across 3 files).

No previous-cycle verification-check queue existed (`-checks-1.json` was never written: cycle 1's single VERIFY item named no runnable command), so nothing was carried forward.

### Auto-dismissed (ledger)

- [BLAKE] 🟠 Phase 1 exit criterion not met. `bash dev/bin/release-checks` exits 1 with `PASS 6300 FAIL 67 SKIP 32 EXIT 1` at HEAD (e0101fa). All 67 failures are in skills/run-autopilot/cli/test_gate_findings_unread_shapes.py. | File: skills/run-autopilot/cli/test_gate_findings_unread_shapes.py:1 — Already deferred for this PRD as a pre-existing-failure record in the batch deferred JSON: all 67 failures are authored by PRD 00277 (parked in hold/ on a blocking escalation) and reproduce identically at the task base. Out of scope for 00278; the gate correctly stays RED until 00277 is finished or its tests are retired.
- [BLAKE] ⚪ `dev/bin/release` uses `grep -rl` with `2>/dev/null || true`, matching non-.md files and subdirectories. | File: dev/bin/release:16 — Transient by design and recorded in the design doc: the self-match ends when this PRD moves to done/ at finalize. The reviewer states no change is needed.

## Alice

Consensus lens, implementation-aware, legacy engine. Her findings are rows R1, R3 and R6 above.

Verified resolved by Alice:
- R3 (cycle 1): the scratch-replay file now imports `_guard_module` and `_tool_input` from `hooks/test_guard_phase_delegation.py`; the duplicate definitions are gone.
- R4 (cycle 1): `state-schema.md` has the CLI-verb heading at the end of the section, after the signals paragraphs, as bullets; `test_doc_contract.py` passes.
- R2/R9 (cycle 1): the `_dir_is_bare_target` docstring now explains the whole-directory `skills/fast-track/scripts` case and the `echo`/comment caveat, and a test names that case.
- Settled deferrals (the `FAIL 0` shortfall, the `dev/bin/release` self-match, the `skills/work/SKILL.md` note) were not re-raised.

She ran the incremental files and the six prose-parsing tests: 272 passed. She did not run the full gate.

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

## Blake

Blind lens, PRD-only. His findings are rows R1 (independently), R2, R4, R7 and R8 above, plus the two ledger-dismissed rows.

Verified satisfied by Blake: all three red tests pass; `skills/work/SKILL.md` is 492 lines and the "then STOP" prose was fixed rather than the test; every tracked `test_*.py` is named in `release-checks` except the scratch replay; the `[checks]` block shape is kept; tracon carries `--with rich`; the scratch-replay split works and uses the committed fixtures; the release shim refuses before `exec` and names the PRD; `SKILL.md:46` reads `python3 (>= 3.11)`; the CHANGELOG Changed bullet is present; the `ponytail:` comment sits above `_backed` at `cli/gate.py:316`. He measured the gate at 5m08s wall on a sandboxed host.

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
B16: pass
B17: pass
B18: pass
B19: pass

## Bob

Doubt lens + de-slop (codex), after one retry (inlined).

FIX:
- 🟡 The scratch file is created under `tmp_path`, but nothing redirects corpus discovery there; restoring the original implementation can pass in a clean checkout (R5).

VERIFY:
- ⚪ The required gate wall-time report remains absent from the supplied evidence (R9). Not queued: it asks for a two-revision benchmark in isolated checkouts, with no pass/fail exit to record, so it stays an ordinary finding.

KNOWN:
- (none)

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

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

Carl: unavailable (gemini-run backend=copilot model=gemini-3.8-flash, exit 1: "Authentication failed … Your GitHub token may be invalid, expired, or lacking the required permissions"). Retried once with the same configuration and the same failure; no output file was consolidated. Not exit 4, so Carl is not latched for the batch.

Verdict: 9 findings
Tests: 6300 passed, 67 failed, 32 skipped (reused from last-verification.json at e0101faa837c7e75a924a2c2056c4590255c69ac)
