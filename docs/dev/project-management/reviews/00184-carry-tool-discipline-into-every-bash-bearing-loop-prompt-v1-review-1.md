---
prd: dev/local/prds/wip/00184-carry-tool-discipline-into-every-bash-bearing-loop-prompt-v1.md
review: 1
date: 2026-09-07
head_sha: 1bb37251c1bd302bcf6afffa34c375fa0cd9d433
codex_thread_id: 01a07bac-d6c5-7081-b4b3-cbc3a2b0319c
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00184-carry-tool-discipline-into-every-bash-bearing-loop-prompt-v1

Diff range: `fdb421ef6eaddb7ab9e5d8dbdc402f126f04b695..1bb37251c1bd302bcf6afffa34c375fa0cd9d433`

codex_rung_guard: not fired

## Cycle notes (fail-loud)

- **Diff scope, corrected once.** `gather-context.sh` with no `--since` computed
  its base as `merge-base HEAD master`. This PRD's work landed directly on
  `master`, so that base equals HEAD and the first run produced an **empty
  diff** (0 lines, 0 changed files). Re-ran with
  `--since fdb421ef6eaddb7ab9e5d8dbdc402f126f04b695` (`state.work_start_sha`),
  which is the range `run-autopilot` mandates for a full review under autopilot.
  The context file therefore labels the scope "incremental review" — that label
  is the script's wording for an explicit base, not a claim that a prior cycle
  exists. This is cycle 1 and the range covers the PRD's whole work.
- **engram pack: unavailable this cycle.** `engram pack` exited 1 with
  `not inside a registered repo; register it in /Users/bob/.config/gita/repos.csv`.
  Deterministic configuration failure, so the one permitted retry was not spent.
  `{PACK_FILE}` and `{PACK_FINDINGS}` were substituted with
  `(no pack available this cycle)` in every prompt that takes them. The review
  is degraded on retrieval context, not invalid.
- **Consolidation ran through `consolidate_findings.py`** (not model-side). No
  ledger flags: cycle 1, no `-ledger.json` exists yet.
- **Verification-check queue: not written.** Eve did not run this cycle (the
  codex doubt-roster guard did not fire, and `doubt_reviewer` is `codex`), so no
  lens whose VERIFY bucket may source the queue produced one. Bob emitted
  FIX/VERIFY/KNOWN buckets because the assembled prompt carried Eve's bucket
  instructions alongside her "Two lenses" and "Rubric verdicts" sections; that
  is one section more than the assembly table specifies, and it is recorded here
  rather than hidden. `source: "bob"` is reserved by
  `references/output-formats.md`, so his two VERIFY items were **not** queued and
  are classified as ordinary ⚪ Low findings instead. Neither is queueable on
  shape in any case: V1 names two commands, and V2's `wc -l` is not a project
  verification command.
- **No follow-up tasks were created in step 7.** This cycle converges (no
  unresolved CRITICAL/HIGH), so the Medium/Low tail is the decision gate's Tail
  sweep, which creates exactly ONE `[D1]` task carrying every finding verbatim.
  Creating step-7 tasks as well would duplicate that task's work.

## Review Summary

Reviewed: 4 completed tasks
PRDs checked: 00184-carry-tool-discipline-into-every-bash-bearing-loop-prompt-v1

### Agent Status

- Alice: ✅ Available (Claude subagent, consensus lens)
- Blake: ✅ Available (Claude subagent, blind/PRD-only lens)
- Bob: ✅ Available (codex, doubt + de-slop lens; thread `01a07bac-d6c5-7081-b4b3-cbc3a2b0319c`)
- Carl: ✅ Available (gemini-run backend=copilot model=gemini-3.8-flash)

## Consolidated Findings

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [2/4] | 🟡 | Orchestrator block was specified twice as "as its first bullet"/"as a bullet" but was inserted as a plain paragraph, not a markdown list item, in the Shell Command Rules section (existing bullets below it start with `- `, this line does not) | skills/run-autopilot/SKILL.md | general | BLAKE, BOB |
| [1/4] | 🟡 | F2: The orchestrator test checks presence anywhere, allowing incorrect placement, missing bullet formatting, and duplicate paragraphs to pass. | skills/run-autopilot/scripts/test_review_prompt_contracts.py:190 | 1 | BOB |
| [1/4] | ⚪ | Cannot statically verify: V1: HEAD contract tests, existing SKILL.md prose pins, and release checks pass. | N/A | general | BOB |
| [1/4] | ⚪ | Cannot statically verify: V2: all changed files satisfy the 800-line limit; complete file contents or counts were not supplied. | N/A | general | BOB |

No 🔴 Critical and no 🟠 High findings. Both ⚪ Low entries are sandbox
limitations rather than defects: Bob cannot execute commands, and both facts he
could not check are already established — the suite result is recorded at this
exact HEAD (see `Tests:` below), and the largest changed file is well under 800
lines.

## Alice

[ALICE] ✅ No issues found

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

Blind, PRD-only. Located the code himself and ran the suites.

Verified satisfied: the four Bash-bearing personas each carry the paragraph
exactly once, after the tools line and before the first `##` heading; the seven
Read-only personas do not carry it; `TOOL_DISCIPLINE` matches the PRD's literal
text and both new tests pass (2 passed, 9 deselected); the full
`skills/run-autopilot/scripts` suite is green (809 passed, 31 pre-existing
skips); `bash dev/bin/release-checks` passes; `CHANGELOG.md` has exactly one
`tool discipline` hit under `[Unreleased]` → `### Changed` naming the five
files; the `rg -c` success metric returns 1 for each of the five files; the diff
touches no unrelated file and adds no parameter or dependency.

One confirmed deviation: the PRD states twice that the orchestrator block is
"as its first bullet" / "as a bullet". Commit `f5b1ca4` inserted it as a plain
paragraph with no leading `- `, directly above the existing bulleted list. The
contract test only checks substring presence, so the pin did not catch it.

[BLAKE] 🟡 Orchestrator block was specified twice as "as its first bullet"/"as a bullet" but was inserted as a plain paragraph, not a markdown list item, in the Shell Command Rules section (existing bullets below it start with `- `, this line does not) | File: skills/run-autopilot/SKILL.md | Task: general

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
B15: pass
B16: pass
B17: pass
B18: pass
B19: pass

## Bob

Doubt + de-slop lens (codex, static-only sandbox).

[BOB] 🟡 F1: Tool discipline is a plain paragraph; Task 3 requires the first bullet under Shell Command Rules. | File: skills/run-autopilot/SKILL.md:277 | Task: 3
[BOB] 🟡 F2: The orchestrator test checks presence anywhere, allowing incorrect placement, missing bullet formatting, and duplicate paragraphs to pass. | File: skills/run-autopilot/scripts/test_review_prompt_contracts.py:190 | Task: 1
[BOB] ⚪ Cannot statically verify: V1: HEAD contract tests, existing SKILL.md prose pins, and release checks pass. | File: N/A | Task: general
[BOB] ⚪ Cannot statically verify: V2: all changed files satisfy the 800-line limit; complete file contents or counts were not supplied. | File: N/A | Task: general

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
R13: fail

FIX:

- F1 — skills/run-autopilot/SKILL.md:277 — Prefix the paragraph with `- `, preserving the existing bullets.
- F2 — skills/run-autopilot/scripts/test_review_prompt_contracts.py:190 — Assert the exact paragraph occurs once and forms the first bullet under `## Shell Command Rules`.

VERIFY:

- V1 — Run `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/scripts`, then separately run `bash dev/bin/release-checks`; require both to pass. (not queued: command shape — two commands in one item; already answered by the recorded verification at this HEAD)
- V2 — Run `wc -l CHANGELOG.md agents/{alice,blake,eve,victor}.md skills/run-autopilot/SKILL.md skills/run-autopilot/scripts/test_review_prompt_contracts.py`; verify each file is at most 800 lines. (not queued: command shape — `wc -l` is not a project verification command)

KNOWN:

- (none)

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

Gemini via copilot backend (`model=gemini-3.8-flash`). Read the diff and
context, ran the targeted contract tests, the full `run-autopilot/scripts`
suite and `dev/bin/release-checks`, checked the `rg -c` success metric across
all five files and the absence across the seven Read-only personas, then swept
`tools:.*Bash` across `agents/`. No frontend surface in this change, so he
reviewed as a generalist.

[CARL] ✅ No issues found

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

## Mechanical checks (computed)

- **Tautological test shapes:** checked 11 test functions in 1 test file; none
  found.
- **Fail-first replay** against `fdb421ef6ead`: 2 touched tests ran, **2 failed
  against base**, 0 passed; 0 test files failed to collect. Both new tests
  genuinely pin the change.
- No `[MECH]` findings were produced, so none were absorbed into the table.

Verdict: 4 findings
Tests: 1056 passed, 0 failed, 31 skipped (reused from last-verification.json at 1bb37251c1bd302bcf6afffa34c375fa0cd9d433)
