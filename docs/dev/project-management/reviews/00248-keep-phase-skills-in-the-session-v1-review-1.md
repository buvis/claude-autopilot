---
prd: docs/dev/project-management/prds/wip/00248-keep-phase-skills-in-the-session-v1.md
review: 1
date: 2026-10-04
head_sha: 9c0150af9b5f8b05ff85fcae56eb6ee78a98d186
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00248-keep-phase-skills-in-the-session-v1

Diff range: `36e236ba7e7b64e40664ca580a32e9dc7d3b5953..9c0150af9b5f8b05ff85fcae56eb6ee78a98d186`

codex_rung_guard: not fired

Cycle 1, full review of the PRD's whole work range (`state.work_start_sha..HEAD`).
All four reviewers ran: Alice (consensus, Claude subagent), Blake (blind,
PRD-only), Bob (doubt + de-slop, codex), Carl (consensus, Gemini on copilot).
Eve did not run: the codex doubt-roster guard did not fire (all four tasks were
implemented by Claude). Consensus engine: `legacy`.

Bob's codex thread-id sidecar was written empty, so no `codex_thread_id` is
stamped and cycle 2 runs him fresh.

Pack: `docs/dev/tmp/engram-pack-00248-c1.md` (9293 tokens).

## Consolidated Findings

21 findings. The `mech-check` finder is appended to the three rows the computed
test-check blocks also name.

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [3/4] | 🟡 | Four tests loop `for fixture in _denied()` with no non-empty assert: the subagent_type, loop-value, non-agent-tool and outside-loop tests. If the fixtures directory is missing or renamed they pass vacuously. The fail-first replay shows several of them passing at base for this reason. Only `test_the_four_observed_delegations_are_denied` guards `len == 4`. Parametrize over `_denied()` with ids, or assert `len(_denied()) == 4` in each. | hooks/test_guard_phase_delegation.py:179 | 1 | ALICE, BOB, CARL, mech-check |
| [2/4] | 🟡 | The predicate is a regex keyword match with only a 20-character negation window, so false positives remain likely. Examples: an Ivan prompt for a task that edits phase-skill prose, such as "run the tests in the work phase", or a negation more than 20 characters before the match. The tests never exercise `subagent_type` or multi-task signals, and the predicate ignores them. That is a legitimate design-doc choice but narrows the safety net. | hooks/guard_phase_delegation.py:47 | 1 | BLAKE, BOB |
| [1/4] | 🟠 | `is_phase_delegation` denies real review-roster prompts, which the PRD requires to be allowed. Run over the real `docs/dev/tmp/*-prompt-*.md` files, `alice-prompt-00188c1.md` and `alice-prompt-00215c1.md` match pattern 1, "imperative within 40 chars of 'work phase'", on "run by the work phase" / "run at this exact HEAD by the work phase". Another 11 Alice, Bob and Carl prompts also match, for example 00187c2, 00188c2, 00189c1/c2 and 202609140442. The Blake prompt for this PRD also matches. If any inline the PRD or review context into an Agent prompt, the guard blocks the reviewer in loop mode. The test corpus is only `dispatch-*.txt`, so no test covers Alice, Blake or Watcher prompts. | hooks/guard_phase_delegation.py:48 | 1 | BLAKE |
| [1/4] | 🟡 | `para.startswith(f"{gate} {anchor}") or para == f"{gate} {anchor}"` is an either-or hedge. The second disjunct implies the first, so it is redundant and weakens the assert's intent. Replace it with the single `startswith` check. | hooks/test_guard_phase_delegation.py:367 | 3 | ALICE, BOB, CARL, mech-check |
| [1/4] | 🟡 | `assert result.stderr in ("", "guard_phase_delegation: predicate raised, allowing\n")` accepts either outcome. Whichever behaviour the code has, the test passes. Pin the real behaviour: the predicate coerces `5` through the f-string and does not raise, so stderr is `""`. | hooks/test_guard_phase_delegation.py:246 | 1 | ALICE |
| [1/4] | 🟡 | Unrelated reflow of `test_spawn_scrub_notice_sorts_multiple_markers_comma_space_joined` (signature collapsed to one line). It is out of scope and traces to no task, even though commits 19ef3c6 and 5353215 were meant to revert reflows. It is also the cause of the fail-first replay line that lists this test as touched. Revert the hunk. | skills/run-autopilot/cli/test_runner.py:323 | 2 | ALICE, mech-check |
| [1/4] | 🟡 | `_negated_before` uses a 20-char window that crosses sentence boundaries, so an earlier "not" in a different sentence suppresses a real delegation. Confirmed: `"Do not wait for me. Run the work phase for PRD 7"` returns False (allowed). Cut the window at the last `.`, `;` or newline before the match. | hooks/guard_phase_delegation.py:55 | 1 | ALICE |
| [1/4] | 🟡 | Each gate sentence is followed immediately by the old sentence, giving "Invoke `/autopilot:plan-tasks` with the Skill tool ...; never delegate planning to an Agent. Invoke `/autopilot:plan-tasks` with the selected PRD." The same happens for `/autopilot:work`. Merge each into one sentence. The gate-prose test pins the duplicated form, so it would change with it. | skills/run-autopilot/references/phase-build.md:344 | 3 | ALICE |
| [1/4] | 🟡 | The allow-corpus test excludes any `docs/dev/tmp/dispatch-*.txt` file that contains "guard_phase_delegation", plus a hard-coded pair (`dispatch-tess-1.txt`, `dispatch-ivan-1.txt`). The PRD says to allow every real prompt. These exclusions are documented in a comment but shrink the gate. Two such files (`dispatch-ivan-3.txt`, `dispatch-tess-3.txt`) are denied by the predicate and are filtered only because they quote the denied phrases. | hooks/test_guard_phase_delegation.py:35 | 1 | BLAKE |
| [1/4] | 🟡 | The Phase 1 acceptance test id `::test_gate_prose_names_the_guard` does not exist. It was split into `test_gate_prose_names_the_guard_in_phase_build` and `test_gate_prose_names_the_guard_in_work_skill`. A literal node-id run of the PRD's named test finds nothing, though `-k` would match. | hooks/test_guard_phase_delegation.py:341 | 3 | BLAKE |
| [1/4] | 🟡 | Non-string fields violate fail-open: `{"prompt": ["run plan-tasks"]}` is stringified and denied despite neither field being a non-empty string | hooks/guard_phase_delegation.py:73 | 1 | BOB |
| [1/4] | 🟡 | Negation filtering and scanning past a negated first match have no committed regression tests; these behaviors lose coverage when the temporary corpus is absent | hooks/test_guard_phase_delegation.py:150 | 1 | BOB |
| [1/4] | ⚪ | `test_hooks_json_registers_the_guard_on_agent` pins `pre[:3] == _EXISTING_PRE` and `len(pre) == 4`, copying three unrelated hook entries verbatim. Any future PreToolUse hook breaks this test. Assert only that exactly one Agent-matcher entry runs the guard. | hooks/test_guard_phase_delegation.py:302 | 3 | ALICE |
| [1/4] | ⚪ | The `n't` alternative in `_NEGATION` is dead: `\b` never matches before `n` inside a word. "can't", "isn't" and "shouldn't" are therefore not recognised as negations (only "doesn't", "don't" and "won't" are, via their own alternatives). Drop `n't` or write the contractions out. | hooks/guard_phase_delegation.py:44 | 1 | ALICE |
| [1/4] | ⚪ | The loose 40-char gap on the work/plan/design-phase patterns false-denies per-task prompts such as "Run the unit tests covering the work phase handoff." Confirmed: returns True. This repo edits phase skills, so the corpus is clean today but the risk is real. The design accepts it. | hooks/guard_phase_delegation.py:48 | 1 | ALICE |
| [1/4] | ⚪ | The `work/SKILL.md` STOP-line addition differs from the PRD's sentence ("In loop mode a hook enforces this (`hooks/guard_phase_delegation.py`)."). It is expanded with a scope disclaimer about what the hook does not enforce. The Phase 3 gate says "never delegate work execution to an Agent" rather than repeating the plan-tasks sentence verbatim for work. Both are harmless wording drift. | skills/work/SKILL.md:51 | 3 | BLAKE |
| [1/4] | ⚪ | The predicate was widened to -ing verbs ("running", "executing") plus a `_NEGATION` heuristic, and the hook has a `try/except` that fails open when the predicate raises. The PRD did not specify these. They are logged in `docs/dev/project-management/meta/assumptions.md` and are low risk, but they go slightly beyond the spec. | hooks/guard_phase_delegation.py:30 | 1 | BLAKE |
| [1/4] | ⚪ | The hook gives one generic reason naming all three phase skills, not the PRD's example string "run /autopilot:work in this session; dispatch only per-task subagents". It still names the rule. | hooks/guard_phase_delegation.py:103 | 1 | BLAKE |
| [1/4] | ⚪ | Cannot statically verify: the hook/runner suites and release-checks pass; last-verification records release-checks exit 0 but provides no test counts | N/A | 4 | BOB |

Two further rows from Alice and Bob duplicate the `:367` hedge and the vacuous
`_denied()` loops above; the consolidator merged them (two merges were reported
as citation-suffix matches: `:179 ~ :53` and `:47 ~ :46`).

## Orchestrator verification of the 🟠 HIGH

The HIGH was not taken on trust. `docs/dev/tmp/probe-blake-high-00248.py`
imported `is_phase_delegation` and ran it over every `docs/dev/tmp/*-prompt-*.md`
file: **21 of 231 real reviewer prompts are denied**, including
`blake-prompt-00248-c1.md`, this very cycle's own blind-lens prompt. The PRD's
allow set explicitly names "the review roster's Alice, Blake and Watcher
prompts", so this is a confirmed violation of a stated acceptance requirement,
not a hypothetical. This cycle only escaped the block because the dispatch
pointed each reviewer at its prompt file instead of inlining the run inputs —
luck, not design.

The same probe confirmed two Medium claims and refuted nothing:

- `"Do not wait for me. Run the work phase for PRD 7."` → `False` (allowed): the
  20-char negation window swallows a real delegation across a sentence boundary.
- `{"prompt": ["run plan-tasks"]}` → `True` (denied): a non-string field is
  stringified rather than failing open.

## Alice

Nine findings (6 🟡, 3 ⚪), no Critical or High. Confirmed the feature is
present end to end — hook, registration, `CLI_SUFFIX`, gate prose,
release-checks wiring, CHANGELOG — and that `_AUTOPILOT_LOOP` is exported by
`skills/run-autopilot/cli/loop.py:216`, so the guard is armed in loop sessions.
No secrets in the fixtures. Her findings are test hedges, an out-of-scope
reflow, a duplicated prose sentence, and two regex edge cases she probed
directly.

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

Seven findings, one 🟠. He ran both PRD gates independently (236 passed;
`release-checks` green) and verified the registration, the loop gate, the
fail-open paths, the fixtures, `CLI_SUFFIX`, both gate sentences, the
release-checks line and the CHANGELOG entry. He could not confirm the denied
fixtures are byte-verbatim from the 2026-10-03 log — the design doc already
records that as unverifiable and instructs the fixtures to be labelled
reconstructions.

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

Six findings (4 🟡, 2 ⚪) plus the doubt buckets. Static-only, as his sandbox
requires; his one ⚪ is the explicit "cannot statically verify" for the runtime
gates, which is why both gate commands are queued as verification checks for
this cycle.

FIX:
- Non-string fail-open violation — hooks/guard_phase_delegation.py:73 — Ignore non-string field values before matching; add list/dict cases containing delegation text.
- Missing durable predicate coverage — hooks/test_guard_phase_delegation.py:150 — Add explicit negated-invocation allow cases and a negated first match followed, beyond the negation window, by a genuine delegation that must be denied.
- Vacuous fixture loops — hooks/test_guard_phase_delegation.py:53 — Assert the four expected fixture names inside `_denied()` so every caller fails when fixtures are missing.
- Redundant assertion branch — hooks/test_guard_phase_delegation.py:367 — Replace the disjunction with `assert para.startswith(f"{gate} {anchor}")`.

VERIFY:
- Runtime acceptance — Run `uv run --no-project --with pytest python -m pytest -q hooks/test_guard_phase_delegation.py skills/run-autopilot/cli/test_runner.py`, then `bash dev/bin/release-checks`; retain exit codes and test counts.

KNOWN:
- Predicate wording limitations — Explicitly accepted in the design's review log and risks; expanding semantic classification exceeds this bounded observed-shape guard.

R1: fail
R2: fail
R3: pass
R4: pass
R6: pass
R7: fail
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

Backend: copilot (`gemini-run.sh`, exit 0), non-empty review. Two 🟡 findings,
both already raised by Alice and the mechanical blocks. He ran the PRD's pytest
command and `release-checks` himself and found both green. No frontend surface
in this diff, so he reviewed as a generalist and invented no frontend findings.

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

## Verification-check queue

Two entries written to
`docs/dev/project-management/reviews/00248-keep-phase-skills-in-the-session-v1-checks-1.json`
(source `bob`, from his VERIFY bucket; both are single project verification
commands). The work phase's step 7 runs them and writes each `result` back.

## Pre-existing suite failures (not this PRD's)

The repo-wide suite is not green, and neither failure was introduced here —
both were reproduced at the PRD base `36e236ba` in a throwaway worktree:

- `skills/work/scripts/test_dispatch_prose.py::test_work_skill_body_stays_under_the_500_line_ceiling` — `work/SKILL.md` is 506 lines at base **and** at HEAD (task 3's edit added no net line), so the ceiling was already blown.
- `skills/work/scripts/test_dispatch_telemetry_prose.py::test_step_6_5_writes_the_leave_row_before_the_stop` — `ValueError: substring not found` at base too.
- Three `skills/run-autopilot/scripts/tracon/test_*.py` collection errors (ImportError), environmental.

Neither failing file is wired into `dev/bin/release-checks`, which is why the
PRD's own gate reads green while the repo-wide suite does not.

Verdict: 21 findings
Tests: 4715 passed, 2 failed, 1 skipped (suite run this cycle; both failures and the 3 tracon collection errors reproduce at base 36e236ba and are not this PRD's)
