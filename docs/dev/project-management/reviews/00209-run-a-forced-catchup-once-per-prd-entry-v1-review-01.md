---
prd: dev/local/prds/wip/00209-run-a-forced-catchup-once-per-prd-entry-v1.md
review: 1
date: 2026-09-21
head_sha: 1c51b2d3e5258cd7410b15cf86f94da6af0521b7
codex_thread_id: 01a0c2bd-974f-7fa2-b349-821cabb2556f
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
  eve: disabled
---

# Review: 00209-run-a-forced-catchup-once-per-prd-entry-v1

Diff range: `b78bc11..1c51b2d3e5258cd7410b15cf86f94da6af0521b7` (merge-base with origin/master; local `master` has advanced with 00208/00211 and is not the base)

codex_rung_guard: not fired

Run mode: standalone (`dev/local/autopilot/state.json` absent; worktree `claude-autopilot-r2`, branch `review/00209`). No task store, no verification-check queue, no `task-add`: findings are reported here, not written as tasks.
Consensus engine: legacy (no `consensus_engine` in PRD frontmatter). Doubt reviewer: codex (default; Eve not dispatched).
Pack: failed (`engram pack` exits 1: worktree not registered in gita; retry blocked by the same cause). Prompts carried `(no pack available this cycle)`.
Ledger: none (cycle 1). Filesystem notes for the blind lens: not triggered (`dev/local` is a real directory, root basename has no leading dot).
Consolidation: `consolidate_findings.py`, four agent pairs. Mechanical checks: 0 tautological shapes in 15 tests; fail-first replay 1 ran, 1 failed against base, 0 passed. No `[MECH]` lines absorbed.
Reviewed: 1 task (T1, commit 1c51b2d) reconstructed from the branch; three files, 30 insertions, 2 deletions (prose rule, prose pin, CHANGELOG).

## Agent Status

- Alice: ✅ Available (Task subagent)
- Blake: ✅ Available (Task subagent, PRD-only)
- Bob: ✅ Available (codex, exit 0, thread id captured; one codex tool call denied by the fact-forcing gate hook, review completed regardless)
- Carl: ✅ Available (gemini-run backend=copilot model=gemini-3.8-flash, exit 0)
- Eve: ⏸️ Disabled (doubt_reviewer resolves to codex; codex guard not fired)

## Consolidated Findings

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [2/4] | 🟡 | `catchup_mode` enum description still says `force` (PRD frontmatter forces full catchup ignoring batch cache) with no mention of the new "spent once tasks are present" nuance PRD 00209 introduces; a reader who consults the schema table instead of `phase-build.md` gets the pre-00209 semantics | skills/run-autopilot/references/state-schema.md:169 | T1 | ALICE, BOB |
| [1/4] | 🟠 | A non-list `state.tasks` reaches `resume_target`, which iterates it and calls `task.get`, raising before the required safe full-catchup fallback | skills/run-autopilot/cli/resume.py:94 | T1 | BOB |
| [1/4] | 🟠 | The canonical resume contract routes any non-empty `state.tasks` directly to `/work`; since `SKILL.md:96` says that encoding wins, a forced resume can bypass the new banner and cache conditions 2–3 | skills/run-autopilot/cli/resume.py:94 | T1 | BOB |
| [1/4] | 🟡 | The prose test checks loose tokens but not the `OR` relationship, exact printed banner, non-list fallback, or canonical resume integration; materially incorrect wording can remain green | skills/run-autopilot/cli/test_custody_prose.py:373 | T1 | BOB |
| [1/4] | 🟡 | Condition 1 mixes the predicate, resume action, malformed-state rule, rationale, and measurement in one dense item; split the predicate and forced-resume behavior into sub-bullets and move the measurement to rationale | skills/run-autopilot/references/phase-build.md:181 | T1 | BOB |
| [1/4] | ⚪ | Cannot statically verify: required pytest suites and `dev/bin/release-checks` pass | N/A | T1 | BOB |
| [1/4] | ⚪ | Cannot statically verify: a forced same-PRD resume logs delta/skipped and starts its first task below 150K usage | N/A | T1 | BOB |

### Orchestrator grounding (facts checked after consolidation, not new findings)

- 🟠 non-list `state.tasks`: confirmed reachable. `cli/state.py::load` runs only `version_status`, not `schema.validate`, so `autopilot resume-target` on a hand-edited `tasks: "x"` raises `AttributeError` at `resume.py:28` (`task.get` on a `str`). Every `statectl` write validates `_LIST_FIELDS` (`schema.py:63`), so the shape can only come from a hand edit. Pre-existing, outside the PRD's structural scope; the PRD's "error case" line describes the prose rule, which this CLI path never reaches.
- 🟠 resume contract bypasses the cache check: confirmed that `resume.py:95` returns `/work continues at ...` for any non-empty `tasks`, and SKILL.md:96 says the encoding wins on disagreement. The PRD's measured problem (a forced full catchup on a same-PRD resume) shows the prose path does run Phase 1 on resume today, so the tension between encoding and prose predates 00209; the new condition narrows what the prose does on that path, it does not create the drift.
- 🟡 [2/4] state-schema row: confirmed. `state-schema.md:169` still reads `force` = "PRD frontmatter forces full catchup ignoring batch cache". Outside the PRD's named structural scope (`phase-build.md`, `test_custody_prose.py`), but a second definition of the same field now disagrees with the authoritative one.
- 🟡 test under-pins: the tokens the test pins are exactly the PRD's acceptance criterion (`force already spent`, `state.tasks`, `same-PRD resume`, absence of `re-runs full catchup regardless of recency`). The finding asks for more than the PRD specified; a stricter pin is a spec change, not a defect against this PRD.
- ⚪ suites/release-checks: resolved this cycle. Full suite 3629 passed / 0 failed / 1 skipped (orchestrator); Blake and Carl each ran `bash dev/bin/release-checks` green; Alice ran the new pin: 1 passed.
- ⚪ post-release metric: not verifiable before release by construction (the PRD names it a post-release signal).

## Alice

[ALICE] 🟡 `catchup_mode` enum description still says `force` (PRD frontmatter forces full catchup ignoring batch cache) with no mention of the new "spent once tasks are present" nuance PRD 00209 introduces; a reader who consults the schema table instead of `phase-build.md` gets the pre-00209 semantics | File: skills/run-autopilot/references/state-schema.md:169 | Task: T1

R1: pass, R2: pass, R3: pass, R4: pass, R6: pass, R7: pass, R8: pass, R9: pass, R10: pass, R11: pass, R12: pass, R13: pass

Notes: diff is exactly the PRD's three named files; condition 1 at `phase-build.md:181` matches the PRD Behavior paragraph verbatim; frontmatter row at `:143` no longer carries the retired phrase; `rg catchup` sweep across `skills/run-autopilot/` and `skills/work/` found only the state-schema line above; new pin run directly: 1 passed; replay block confirms fail-first.

## Blake

[BLAKE] ✅ No issues found

B1-B19: all pass (B3, B4, B9, B11, B13 vacuous: the PRD specifies none of those surfaces). Located `phase-build.md:181` and `:143`, `test_custody_prose.py:364`, `CHANGELOG.md:10-12`; ran the PRD's named target (19 passed) and `bash dev/bin/release-checks` (green); `frontmatter.py`'s `catchup` allowed-value list already carried `force`, untouched.

## Bob

[BOB] 🟠 A non-list `state.tasks` reaches `resume_target`, which iterates it and calls `task.get`, raising before the required safe full-catchup fallback | File: skills/run-autopilot/cli/resume.py:94 | Task: T1
[BOB] 🟠 The canonical resume contract routes any non-empty `state.tasks` directly to `/work`; since `SKILL.md:96` says that encoding wins, a forced resume can bypass the new banner and cache conditions 2–3 | File: skills/run-autopilot/cli/resume.py:94 | Task: T1
[BOB] 🟡 State-schema prose still defines `force` as always ignoring the cache, while its cache description omits the new `state.tasks` condition | File: skills/run-autopilot/references/state-schema.md:169 | Task: T1
[BOB] 🟡 The prose test checks loose tokens but not the `OR` relationship, exact printed banner, non-list fallback, or canonical resume integration; materially incorrect wording can remain green | File: skills/run-autopilot/cli/test_custody_prose.py:373 | Task: T1
[BOB] 🟡 Condition 1 mixes the predicate, resume action, malformed-state rule, rationale, and measurement in one dense item; split the predicate and forced-resume behavior into sub-bullets and move the measurement to rationale | File: skills/run-autopilot/references/phase-build.md:181 | Task: T1
[BOB] ⚪ Cannot statically verify: required pytest suites and `dev/bin/release-checks` pass | File: N/A | Task: T1
[BOB] ⚪ Cannot statically verify: a forced same-PRD resume logs delta/skipped and starts its first task below 150K usage | File: N/A | Task: T1

FIX: 5 items (the two 🟠 and three 🟡 above). VERIFY: 2 items (the suite/release-checks run; the post-release resume metric). KNOWN: (none).

R1: fail
R2: pass
R3: pass
R4: fail
R6: pass
R7: fail
R8: pass
R9: fail
R10: fail
R11: pass
R12: pass
R13: pass

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

Dispatch: single run, no retry, thread id captured for cycle 2 resume.

## Carl

[CARL] ✅ No issues found

R1-R13 (R5 absent from the rubric): all pass. Backend copilot / gemini-3.8-flash. Read the context and diff, swept `catchup` and `catchup_mode` across `skills/`, read `state-schema.md` and `design-rationale.md`, ran the PRD's named pytest target and `bash dev/bin/release-checks` (re-run with the nested-dispatch env vars unset after the first attempt hit the dispatch guard). No frontend surface; reviewed as a generalist.

## Follow-up Tasks Created

None: standalone run, no `state.json`, so no `task-add`. The seven findings above are reported for the operator's decision (packets below).

## Decision packets (unattended: written, not asked)

Agenda: 7 findings; 0 CRITICAL, 2 HIGH (single reviewer), 3 MEDIUM (one at 2/4), 2 LOW (both resolved by evidence this cycle).

**1 of 4, 🟠 HIGH, resume-target crashes on a non-list `state.tasks`.** What: `autopilot resume-target` loads state without schema validation and `resume_target` iterates `tasks`; a non-list value raises instead of reading as "absent". Found by Bob (doubt lens). Evidence: `state.py:119-122` calls `version_status` only; `resume.py:28` calls `task.get`. Confirmed reachable; only a hand-edited state can hold that shape since every `statectl` write validates `tasks` as a list. If unchanged: a hand-corrupted state fails loud at Phase 0 with a traceback instead of the prose's safe full catchup; rare, stable, does not compound. Options: (a) Recommended: accept or defer as pre-existing and out of 00209's scope, file under a follow-up PRD for `resume_target` input hardening (S; strongest reason against: leaves the PRD's stated "error case" true only on the prose path). (b) Patch: `isinstance(tasks, list)` guard in `resume.py:94` plus a regression test (S; widens the diff beyond the PRD's scope). (c) Root: have `state.load` run `schema.validate` so every reader fails on the same message (M; may break readers that tolerate legacy states today).

**2 of 4, 🟠 HIGH, the encoded resume contract skips the cache check.** What: `resume.py:95` routes any non-empty `tasks` straight to `/work`, and SKILL.md:96 says the encoding wins over prose; the new banner and conditions 2-3 live on the prose path. Found by Bob. Evidence: `resume.py:93-99`; the PRD's own measurement shows the prose path does run catchup on resume today. Confirmed as a pre-existing prose/encoding tension, not introduced here. If unchanged: no new breakage; the drift stays where it was. Options: (a) Recommended: accept as pre-existing; note it in `design-rationale.md` or a follow-up PRD that reconciles `resume_target` with Phase 1's cache check (S; reason against: the drift stays undocumented in the encoding's tests). (b) Extend `resume_target` to return a target that names the cache decision on forced resumes, update callers and `test_resume.py` (M; touches the canonical contract for a prose-only PRD). (c) Drop the prose-vs-encoding sentence at SKILL.md:96 for the build gate (S; weakens the drift detector).

**3 of 4, 🟡 MEDIUM [2/4], `state-schema.md:169` still defines `force` the old way.** Found by Alice and Bob. Evidence: line reads "PRD frontmatter forces full catchup ignoring batch cache". Confirmed. If unchanged: two definitions of one field disagree; a reader of the schema table applies pre-00209 semantics. Options: (a) Recommended: one-line edit to the `catchup_mode` row mirroring the `phase-build.md:143` wording, plus a `_assert_absent` pin in the new test (S; reason against: the file is outside the PRD's named scope, so it widens the diff by one line). (b) Point the schema row at `phase-build.md` § Batch cache check instead of restating semantics (S; a reader has to follow a link). (c) Accept or defer (the authoritative rule is right; the summary lags).

**4 of 4, 🟡 MEDIUM bundle (single reviewer, Bob).** (i) Test pins tokens, not the `OR` predicate or banner text: the tokens are the PRD's acceptance criterion verbatim; a stricter pin is a spec change. Recommended: accept as specified, or add the banner string to the `_assert_present` tuple (S). (ii) Condition 1 is dense: style; the PRD dictates the content. Recommended: accept, or move the "Measured 2026-09-20" sentence to the frontmatter-semantics row (S). Both ⚪ LOW items are resolved by this cycle's evidence (suite 3629 passed; release-checks green twice; post-release metric is post-release by definition).

Verdict: 7 findings
Tests: 3629 passed, 0 failed, 1 skipped (suite run this cycle)
