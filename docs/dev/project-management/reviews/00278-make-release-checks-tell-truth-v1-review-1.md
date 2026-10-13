---
prd: docs/dev/project-management/prds/wip/00278-make-release-checks-tell-truth-v1.md
review: 1
date: 2026-10-13
head_sha: 80beb7ade23c288466b6ae9440540e4be10c67fa
codex_thread_id: 01a134a0-0ea9-7501-80a2-3906200d8348
reviewers: alice,blake,bob
agents:
  alice: available
  blake: available
  bob: available
  carl: unavailable
dispatch_rows:
  bob: 9b4d0e4f
  carl: 9faea90f
---

# Review: 00278-make-release-checks-tell-truth-v1

Diff range: `a15cbe13bcee0e6b6cb68ae9d44ae9eeda537255..80beb7ade23c288466b6ae9440540e4be10c67fa`

codex_rung_guard: not fired

## Review Summary

Reviewed: 9 completed tasks
PRDs checked: 00278-make-release-checks-tell-truth-v1

### Agent Status

- Alice: ✅ Available (consensus lens, legacy engine)
- Blake: ✅ Available (blind lens, PRD-only)
- Bob: ✅ Available (doubt lens + de-slop, codex) — after one retry (inlined). His first run returned a lack-of-input refusal (`sandbox-exec: sandbox_apply: Operation not permitted`, no files read); the retry used the inlined prompt and produced a full review.
- Carl: ⚠️ Unavailable: gemini-run backend=copilot model=gemini-3.8-flash exited 1 — "Authentication failed", GitHub Copilot token invalid/expired. Retried once, same failure. Not a permanent (exit 4) unavailability, so no batch latch.
- Eve: ⏸️ Disabled: resolved doubt reviewer is `codex` and the codex doubt-roster guard did not fire (no codex-implemented task in this PRD).

Notes on this cycle's inputs:

- pack: failed (engram pack exit 1: `sqlite3.OperationalError: attempt to write a readonly database`) — degraded, not invalid; Alice's and Bob's prompts carried the `(no pack available this cycle)` sentinel.
- Format warnings: Alice's `test_release_checks_counts.py:319` row and Blake's `:319-347` row omitted the `| Task:` field; both were normalized with the task id before consolidation so the rows were not dropped.
- Consolidation ran via `consolidate_findings.py` (no ledger — cycle 1, no settled decisions file). Bob's issue lines sit inside his FIX/VERIFY/KNOWN buckets as `- [BOB] …`; the leading list marker was stripped in his saved output so the consolidator parsed them. His raw output is kept at `docs/dev/tmp/bob-output-00278-c1-raw.txt`.

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [3/3] | 🟠 | The scratch-replay file was added to the gated `[checks] hook registration` block, which contradicts PRD 00278 (the file is "not run by `release-checks`" and is the one `UNGATED` entry). The `UNGATED` entry is now dead because the file is named in the script. The gate's counts now depend on whether gitignored scratch files exist: skipped in a clean clone, run in the live checkout. That is the live-vs-clone mismatch packet 12 set out to remove. Remove the line from the block so `UNGATED` is real and the pin stays honest. | dev/bin/release-checks:136 | 9 | ALICE, BLAKE, BOB |
| R2 | [2/3] | 🟡 | `test_a_directory_matching_only_part_of_a_longer_token_is_not_a_gated_target` and `test_the_repo_root_is_never_a_gated_target` pass against base. They exercise only the new `_dir_is_bare_target` helper defined in the same file. They are not tautological as written, but they pin an addition the design did not ask for. The design's pin is a plain `path not in text` substring check. The directory-target branch is needed for the whole-directory `skills/fast-track/scripts` target at release-checks:171, so keep it. Add a one-line comment saying so, and add a test that names the fast-track case. Also note that a bare mention of a directory in an `echo` or comment line would mark every test file under it as gated. | skills/run-autopilot/cli/test_release_checks_counts.py:319 | 9 | ALICE, BOB, mech-check |
| R3 | [2/3] | 🟡 | The replay file redefines `_tool_input` and `_guard_module`, which duplicate the originals in `hooks/test_guard_phase_delegation.py`. It already imports `_agent_payload`, `_description` and `_run` from that module. Import the two helpers too. | hooks/test_guard_phase_delegation_scratch_replay.py:38 | 4 | ALICE, BOB |
| R4 | [1/3] | 🟠 | The new `## Two more CLI verbs` heading was inserted in the middle of the "Build-Session Model Promotion Signals" section. The `**Target resolution.**` and `**The five signals.**` paragraphs that follow now sit under the wrong heading. The two verb lines also have no list markers, so Markdown renders them as one run-on paragraph. Move them into a real CLI-verb listing or the end of an existing section, and use bullets. | skills/run-autopilot/references/state-schema.md:520 | 1 | ALICE |
| R5 | [1/3] | 🟠 | The gate does not reach `FAIL 0`. Phase 1 acceptance and exit criterion, "`bash dev/bin/release-checks` exits 0 with `FAIL 0`", is unmet | skills/run-autopilot/cli/test_gate_findings_unread_shapes.py | Phase 1 | BLAKE |
| R6 | [1/3] | 🟠 | The required FAIL 0 acceptance remains unmet: 67 failures reproduce identically at base and belong to parked PRD 00277. Resolving that PRD's unfinished behavior is outside this change's scope; retain the documented deferral. | skills/run-autopilot/cli/test_gate_findings_unread_shapes.py | 9 | BOB |
| R7 | [1/3] | 🟡 | `test_allow_corpus_ignores_scratch_dispatch_files` passes against the pre-change code. The replay overlays HEAD's test file, so the narrowed `_allow_corpus` already applies. It also compares `_allow_corpus()` to a `before` value taken from the same function, not to the committed fixtures glob. The contract asked for `== sorted((FIXTURES / "allowed").glob("*.txt"))` before and after the scratch file exists. Assert that literal so the test pins the rule. | hooks/test_guard_phase_delegation.py:98 | 4 | ALICE, mech-check |
| R8 | [1/3] | 🟡 | The task 9 acceptance criterion (`bash dev/bin/release-checks` exits 0 with `FAIL 0`) is unmet. The gate shows 67 failures, all in `test_gate_findings_unread_shapes.py`, a PRD 00277 file that was already gated and is parked in hold. The deferred-findings record documents this and it is out of scope here. It still means the PRD's exit criterion is not met, and the gate stays RED for any release until 00277 is finished or its tests are retired. | docs/dev/project-management/autopilot/deferred/202610111300-deferred.json:522 | 9 | ALICE |
| R9 | [1/3] | 🟡 | The pin deviates from the spec. The spec says it compares tracked files with "the paths literally named in the script". `test_every_tracked_test_file_is_gated` also accepts any file whose parent directory appears as a bare token (`_dir_is_bare_target`) | skills/run-autopilot/cli/test_release_checks_counts.py:319-347 | Phase 1 | BLAKE, mech-check |
| R10 | [1/3] | 🟡 | The corpus regression test compares against `_allow_corpus()` itself rather than the committed fixtures; the supplied replay confirms it passes at base. Assert the exact fixture list before and during scratch-file presence, and verify that restoring the old implementation fails. | hooks/test_guard_phase_delegation.py:98 | 4 | BOB, mech-check |
| R11 | [1/3] | 🟡 | The regression test overwrites and deletes a fixed file in the live checkout, risking existing scratch content and concurrent-test interference. Use an isolated temporary corpus with monkeypatching. | hooks/test_guard_phase_delegation.py:102 | 4 | BOB |
| R12 | [1/3] | ⚪ | The new refusal guard in `dev/bin/release` matches the open PRD 00278 itself, because it contains the phrase "release is blocked" and sits in `wip/`. No real release can run until the PRD reaches `done/`. The design doc records this and the test uses an isolated fixture, so no change is needed. Keep it in mind at release time. | dev/bin/release:16 | 6 | ALICE |
| R13 | [1/3] | ⚪ | `skills/work/SKILL.md` is 492 lines and the leave-row test passes, but I could not confirm the moved text landed in a reference file. All of these pass in the combined run: the three red tests, `test_release_refuses_while_a_held_prd_blocks_it`, `test_every_tracked_test_file_is_gated`, and `test_allow_corpus_ignores_scratch_dispatch_files` (197 passed across those five files) | skills/work/SKILL.md | red tests 2 and 3 | BLAKE |
| R14 | [1/3] | ⚪ | The gate time cost is not recorded anywhere I could find. The spec asks the task report to state the new wall time, and I did not run the full gate, so I could not measure it | N/A | Phase 1 | BLAKE |
| R15 | [1/3] | ⚪ | The required before/after gate wall-time report is absent from the supplied evidence. Check the task-9 report against the recorded baseline and revised gate elapsed times; record both and their delta. | N/A | 9 | BOB |

Mechanical test checks absorbed into the rows above (context file, step 3):

- `[MECH] 🟡 1 touched test(s) pass against the pre-change code: test_allow_corpus_ignores_scratch_dispatch_files | File: hooks/test_guard_phase_delegation.py` → folded into R7 and R10.
- `[MECH] 🟡 2 touched test(s) pass against the pre-change code: test_a_directory_matching_only_part_of_a_longer_token_is_not_a_gated_target, test_the_repo_root_is_never_a_gated_target | File: skills/run-autopilot/cli/test_release_checks_counts.py` → folded into R2 and R9.

No tautological-shape test was reported.

## Alice

Consensus lens, implementation-aware, legacy engine. Her seven findings are rows R1, R2, R3, R4, R7, R8 and R12 above. She ran 12 test files covering the new and changed tests, the three red tests and the six `[checks]`-parsing prose tests: 320 passed. She did not run `dev/bin/release-checks` itself.

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
R12: pass
R13: pass

## Blake

Blind lens, PRD-only. His findings are rows R1, R5, R9, R12 (independently), R13 and R14 above. He read the code himself, ran the five red-test and gate-pin files (197 passed across them), and checked git history; he did not run the full gate, so the new wall time is unverified.

Verified satisfied by Blake: the CHANGELOG no longer contains "stays allowed" and `00271` sits inside `[Unreleased]`; CHANGELOG.md states the Python 3.11 floor; `skills/run-autopilot/SKILL.md:46` reads `python3` (>= 3.11); the `# ponytail:` quadratic comment sits above `_backed`; `_allow_corpus` returns the committed fixtures only; `group-rework` and `review-stage` invocations are documented in `state-schema.md`; the tracon block carries `--with rich`; the `[checks]` block shape is preserved.

B1: fail
B2: pass
B3: pass
B4: fail
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
B18: fail
B19: fail

## Bob

Doubt lens + de-slop (codex), after one retry (inlined).

FIX:
- 🟠 Scratch replay is explicitly included in the release gate despite its UNGATED designation (R1).
- 🟡 The corpus regression test compares against `_allow_corpus()` itself rather than the committed fixtures (R10).
- 🟡 The regression test overwrites and deletes a fixed file in the live checkout (R11).
- 🟡 The coverage pin adds an unrequested directory-name exemption (R2).
- 🟡 Scratch replay duplicates `_guard_module` and `_tool_input` while already importing sibling helpers (R3).

VERIFY:
- ⚪ The required before/after gate wall-time report is absent from the supplied evidence (R15). Not queued: his text names no exact runnable command (rubric D3), so it stays an ordinary finding.

KNOWN:
- 🟠 The required FAIL 0 acceptance remains unmet: 67 failures reproduce identically at base and belong to parked PRD 00277 (R6).

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

Verdict: 15 findings
Tests: 6354 passed, 67 failed, 32 skipped (reused from last-verification.json at 80beb7ade23c288466b6ae9440540e4be10c67fa, written by this cycle's own `review-stage` gate run)
