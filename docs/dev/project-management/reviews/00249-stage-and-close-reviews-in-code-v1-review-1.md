---
prd: docs/dev/project-management/prds/wip/00249-stage-and-close-reviews-in-code-v1.md
review: 1
date: 2026-10-04
head_sha: b2afd0bf0c6fbfb99d046e4a99af3a630c916914
codex_thread_id: 01a107c0-74ec-7b42-8214-20eb3fb3eccf
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00249-stage-and-close-reviews-in-code-v1

Diff range: `4c20da6b4a7d9e4ab01820e16d01074df4174d47..b2afd0bf0c6fbfb99d046e4a99af3a630c916914`

codex_rung_guard: not fired

Consensus engine: legacy. Full review, cycle 1, scoped with
`gather-context.sh --since 4c20da6b4a7d9e4ab01820e16d01074df4174d47`
(`state.work_start_sha`) because the PRD work landed directly on `master`.
Context pack: `docs/dev/tmp/engram-pack-00249c1.md` (2390 tokens).
Reviewer prompts and inputs were staged by hand: the installed pack is 0.8.0,
which predates the `review-stage` verb this PRD adds, so this cycle ran the
0.8.0 prose path.

## Consolidated Findings

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [3/4] | 🟠 | review-close reads two frontmatter blocks that the review-file format does not fully define. (a) `dispatch_rows:` is documented nowhere: not in SKILL.md step 8, not in skills/review-work-completion/references/output-formats.md:245. So close() never ends the dispatch rows in practice, and the "closes the stage-time rows" claim is dead. If a model did stamp it, `--outcome ok` is hardcoded where the design requires "the same outcome table SKILL.md step 6 uses". That could double-end a row that SKILL.md:362 already tells the model to end. (b) The documented `agents:` block lists only alice, bob and carl, with states available/unavailable/disabled. So the `blind` and `fable` lenses are never closed and stay "running". `disabled` maps to "failed" (`"done" if status == "available" else "failed"`), which marks a never-invoked lens as failed | skills/run-autopilot/cli/review_close.py:134 | 4 | ALICE, BLAKE, BOB |
| [3/4] | 🟡 | Function-size limit exceeded (computed): close is 92 lines (review_close.py:101), run_gate is 75 (verification.py:101), stage is 56 (review_stage.py:647). Split close() into parse-inputs and `_apply` helpers, and pull the result-building and timeout branches out of run_gate | skills/run-autopilot/cli/review_close.py:101 | 4 | ALICE, BOB, CARL |
| [2/4] | 🟠 | review-stage never wires the settled-decisions ledger or the prior-cycle findings: stage() always passes prior_findings=None to render_roster, and the `review-stage` CLI has no --settled-ledger or --prior-findings flag. render_roster's ledger and incremental code is therefore unreachable in production, and SKILL.md step 4 tells the model to hand-append both with the Edit tool. That contradicts the PRD (Render the roster prompts: Alice, Bob, Carl and Eve get the settled-decisions section; Critical Scenarios: an incremental cycle's prompts carry the addendum and prior findings, Blake's does not). Two cycles per PRD is the norm, so the second cycle falls back to the hand-editing this PRD removes | skills/run-autopilot/cli/review_stage.py:575 | 2 | ALICE, BLAKE |
| [2/4] | 🟠 | stage() stamps review_lenses without the `ui` key for Carl. LENS_PERSONAS has no `ui`, and test_stage_stamps_roster_and_opens_cli_rows pins {consensus, blind, doubt} with carl on the roster. The PRD says "the same writes step 5 makes today", and SKILL.md:263 (the bare-repo fallback) still says to add `ui` (Carl). review_close._PERSONA_LENS and __main__.py:841 both treat `ui` as the lens key for Carl. Carl's lens never shows "running", then appears as "done" or "failed" from close(), and the test locks in the regression. Fix: add `ui` for carl to the stamped lenses and correct the test | skills/run-autopilot/cli/review_stage.py:80 | 2 | ALICE, BOB |
| [2/4] | 🟠 | run_gate keeps the first 2 MB of output and drops the tail, but the summary line is last. A gate that prints more than the cap loses its PASS/FAIL/SKIP line, so counts come back null and the gate looks stale. test_run_gate_truncates_output_before_parsing pins exactly that outcome. `communicate()` also buffers the full output first, so memory is not actually bounded. Keep the tail (`[-GATE_OUTPUT_CAP:]`) or read incrementally | skills/run-autopilot/cli/verification.py:84 | 1 | ALICE, BOB |
| [2/4] | 🟡 | Tautological and non-pinning test (computed MECH lines at test_rework_groups_prose.py:81 and the fail-first replay). test_tail_sweep_split_rule_states_findings_path_naming_and_floor hedges with `"at most 4, never zero" in section or "caps at 4" in section`, and every other assert in it also passes on the old prose. It passes against the pre-change code, so it pins nothing new. Assert the specific new text without the `or` | skills/run-autopilot/scripts/test_rework_groups_prose.py:112 | 7 | ALICE, BOB |
| [2/4] | 🟡 | F8: CLI staging cannot receive the settled ledger or prior findings; the skill retains manual prompt edits although the renderer already supports both inputs | skills/run-autopilot/cli/__main__.py:898 | general | BOB, CARL |
| [1/4] | 🟠 | `reuse_verdict` adds a clean-working-tree requirement (`git status --porcelain` must be empty) that the spec does not state. The spec says `reused` when every path changed since `sha` is under the store and the counts are non-null. In a live autopilot checkout the store has uncommitted writes (`dispatch-metrics.jsonl` is modified right now, and `state.json` changes during a run). The verdict will therefore be `stale` in most real reviews, and the gate re-runs. That defeats the stated problem of re-running the gate for store-only commits. | skills/run-autopilot/cli/verification.py:75 | Gate reuse | BLAKE |
| [1/4] | 🟠 | "One-line gate summary" is not delivered. `run_gate` only parses a `PASS n FAIL n SKIP n EXIT c` line from the command's own stdout. Nothing makes a gate run print that line, and the pack's own gate `dev/bin/release-checks` never emits it (no match in `dev/`). With this pack's gate command, `run_gate` returns null counts, writes no `last-verification.json`, and the line reads "Tests: counts unavailable". The spec's "no second run is ever needed to read counts" is therefore false for this pack. `test_run_gate_prints_one_summary_line` only feeds a stub command that already prints the line. | skills/run-autopilot/cli/verification.py:160 | Gate summary | BLAKE |
| [1/4] | 🟠 | `review-close` does not match the specified interface. The spec has `--review-file <f>` reading a machine-readable findings block carried in the review file. The code needs `--state`, `--batch-id {decision-gate,tail-sweep}`, `--findings <external json>` and `--default-tier`, and the model must hand-write that JSON with the Write tool. The design doc chose this, but it contradicts the PRD and leaves the "second source of truth" risk with no cross-check against the table. The spec outputs `autonomous_decisions` entries, and `close()` writes none, only `deferred_decisions`. A second call with the same file returns `applied: false` and exits 1, not a clean idempotent success. The prose treats it as non-failure. | skills/run-autopilot/cli/review_close.py:101 | Close the cycle | BLAKE |
| [1/4] | 🟠 | F2: The prescribed release-checks command emits no required PASS/FAIL/SKIP/EXIT summary, so staging records no counts and step 6 reruns the suite; ancestor reuse also falls back to the old exact-SHA check | skills/review-work-completion/SKILL.md:400 | general | BOB |
| [1/4] | 🟠 | F3: Blake and Eve receive the design doc through run["prd"], because staging appends it to the PRD file; this violates their PRD-only input boundary | skills/run-autopilot/cli/review_stage.py:428 | 3 | BOB |
| [1/4] | 🟠 | F4: Adding Eve removes Bob’s doubt appendix, but Eve’s failure fallback explicitly uses Bob’s assembled prompt; that fallback therefore lacks the doubt lenses, buckets and D1–D5 rubric | skills/run-autopilot/cli/review_stage.py:505 | 3 | BOB |
| [1/4] | 🟠 | F6: Unknown classifications such as "fxi" pass validation, create nothing, and still stamp the batch applied; invalid severity strings also bypass CRITICAL grouping | skills/run-autopilot/cli/__main__.py:1017 | 5 | BOB |
| [1/4] | 🟠 | F9: resolve_base() independently computes a merge-base, while gather-context.sh diffs against the branch tip and supports additional remote fallbacks; replay can therefore certify a different range | skills/run-autopilot/cli/review_stage.py:183 | 2 | BOB |
| [1/4] | 🟡 | close() hardcodes `require_codex_guard=False`. The design calls it "caller-decided", but neither close() nor the CLI exposes a flag. A saved review file with a missing codex_rung_guard line is therefore accepted, although SKILL.md:435 gates the same file with --require-codex-guard | skills/run-autopilot/cli/review_close.py:123 | 4 | ALICE |
| [1/4] | 🟡 | Chosen-finding input is only half validated. `_is_chosen_finding` accepts any string classification, so a typo such as "Fix" or "fixx" is silently dropped: no task, no deferral, exit 0. `severity` is never checked against the four emoji, although the design calls a wrong emoji "the one place a finding silently misroutes". Reject unknown classification and severity values with exit 2 | skills/run-autopilot/cli/__main__.py:1016 | 5 | ALICE |
| [1/4] | 🟡 | reuse_verdict requires `git status --porcelain` to be empty, so a dirty store file defeats reuse. The session's initial git status already shows docs/dev/project-management/autopilot/dispatch-metrics.jsonl modified, and autopilot rewrites those files during a run. This is suspected, not reproduced. The design says "empty", but it undercuts the PRD goal of reusing the record when only store commits follow. Consider ignoring dirty paths under docs/dev/project-management/ | skills/run-autopilot/cli/verification.py:75 | 1 | ALICE |
| [1/4] | 🟡 | Tail-sweep close-out does not match the design. The design says doubts_rubric_verdicts, review_lenses and dispatch-row ending are skipped as no-ops on a tail-sweep call. close() re-applies the lens statuses and verdicts and re-ends the rows on every call regardless of batch_id. phase-review.md:197 claims it is a no-op "by design". Gate those steps on `batch_id == "decision-gate"`, or fix the prose | skills/run-autopilot/cli/review_close.py:172 | 7 | ALICE |
| [1/4] | 🟡 | No CHANGELOG entry for the new `autopilot review-stage` and `autopilot review-close` verbs, the gate-reuse behaviour or the SKILL.md rewrite. These are user-visible feat changes, and CHANGELOG.md has an [Unreleased] section. rg for review-stage / review-close in CHANGELOG.md and README.md returned nothing | CHANGELOG.md | general | ALICE |
| [1/4] | 🟡 | Module signatures and flags differ from the spec. The spec has `stage(state_path, cycle_id, since)`, `render_roster(staged, roster)`, `close(review_file, state_path)`, `reuse_verdict(record, repo)` and `run_gate(command)`. The code has `stage()` with 11 parameters, `render_roster` with 7, `close()` with 5, `reuse_verdict(record, repo_root, head_sha)` and `run_gate(command, cwd, sha, cycle, timeout)`. The spec lists `--state (default store path)`, `--cycle-id` and `--since`. The code adds `--gate-command` (required), `--replay-cmd`, `--tasks-json`, `--prd`, `--design-doc`, `--roster` and `--repo-root`. `--state` has no default, and omitting it silently switches to a standalone mode the spec does not describe as a flag-driven mode. | skills/run-autopilot/cli/__main__.py:898 | general | BLAKE |
| [1/4] | 🟡 | The summary lacks items the spec lists. It has no diff-scope field, and no "exact commands" for the reviewer dispatch message. The gate verdict is a `tests_line` string and the counts are not separate fields. The dispatch message is still composed by the model. | skills/run-autopilot/cli/review_stage.py:675 | Arm the roster | BLAKE |
| [1/4] | 🟡 | `review-work-completion/SKILL.md` step 6 does not end with `autopilot review-close`, as the Phase 2 task requires. The skill states "This skill creates no tasks", and the call lives only in `phase-review.md`. The design doc moved it there, but the PRD acceptance text says step 6. | skills/review-work-completion/SKILL.md:410 | Phase 2 | BLAKE |
| [1/4] | 🟡 | F5: close() replaces source-tagged doubt verdicts with untagged matches from the whole review file, losing reviewer attribution required by dual-reviewer reporting | skills/run-autopilot/cli/review_close.py:131 | 4 | BOB |
| [1/4] | 🟡 | F7: Persona preflight uses a permissive flat-string parser rather than validating YAML; null, empty collections and malformed values can pass. Direct render_roster() calls bypass preflight entirely | skills/run-autopilot/cli/review_stage.py:369 | 3 | BOB |
| [1/4] | 🟡 | Function run_gate exceeds 50-line limit (75 lines) | skills/run-autopilot/cli/verification.py:101 | 1 | CARL |
| [1/4] | 🟡 | Function stage exceeds 50-line limit (56 lines) | skills/run-autopilot/cli/review_stage.py:647 | 2 | CARL |
| [1/4] | 🟡 | Trailing empty "(found by: )" suffix rendered when finding has no author | skills/run-autopilot/cli/review_close.py:72 | 4 | CARL |
| [1/4] | ⚪ | resolve_base re-derives the diff-range base in Python (origin/HEAD, master, develop) instead of taking the base gather-context.sh resolved, which the context file's "_Diff scope_" line already carries (_SCOPE_RE parses it). The two can drift | skills/run-autopilot/cli/review_stage.py:183 | 2 | ALICE |
| [1/4] | ⚪ | Passing a non-numeric cycle id such as "00249c1" records `cycle: null` in last-verification.json. In autopilot mode the cycle could come from state.cycle | skills/run-autopilot/cli/review_stage.py:349 | 2 | ALICE |
| [1/4] | ⚪ | The edit to test_no_persona_prompt_text_survives_outside_the_registry grew that test to 56 lines. It passes at base only because it is an exemption list; this is acceptable but over 50 lines | skills/review-work-completion/scripts/test_agent_registry.py:222 | 6 | ALICE |
| [1/4] | ⚪ | The new test files are not listed in `dev/bin/release-checks`, so the Phase 2 exit command does not exercise them. I did not run the whole script. | dev/bin/release-checks:1 | Phase 2 | BLAKE |
| [1/4] | ⚪ | K1: The supplied shapes block flags an unchanged either-or assertion in test_dispatch_references_document_the_fail_closed_contract | skills/review-work-completion/scripts/test_agent_registry.py:213 | general | BOB |
| [1/4] | ⚪ | K2: The supplied replay reports test_no_persona_prompt_text_survives_outside_the_registry passing at base; its change only exempts deliberately frozen golden fixtures | skills/review-work-completion/scripts/test_agent_registry.py:255 | general | BOB |
| [1/4] | ⚪ | K3: __main__.py remains above the 800-line limit at 1580 lines; it already exceeded that limit before this diff | skills/run-autopilot/cli/__main__.py:1 | general | BOB |
| [1/4] | ⚪ | Cannot statically verify: acceptance suites and release-checks pass | N/A | general | BOB |

Mechanical checks absorbed: the two `[MECH]` tautology lines and the two
fail-first replay lines are present as rows above (the
`test_rework_groups_prose.py` pair merged into the `[2/4]` 🟡 row; the two
`test_agent_registry.py` lines merged onto Bob's K1/K2 rows). Add
`mech-check` to those rows' finders.

Carry-forward: none (cycle 1, no prior checks queue).

## Alice

Alice ran as a native Claude subagent against the context, diff and pack.
Her findings are the `ALICE` rows above. She ran the new and changed suites
locally (71 passed, 0 failed, 0 skipped) and did not run `dev/bin/release-checks`.

R1: pass
R2: fail
R3: pass
R4: fail
R6: pass
R7: fail
R8: pass
R9: fail
R10: pass
R11: pass
R12: fail
R13: pass

## Blake

Blake ran blind (PRD + blind rubric only, no diff, no file list, no design
doc). His findings are the `BLAKE` rows above. He ran the new and related test
files (185 passed) and did not run the full `dev/bin/release-checks`.

B1: fail
B2: fail
B3: fail
B4: fail
B5: pass
B6: fail
B7: fail
B8: pass
B9: pass
B10: pass
B11: pass
B12: pass
B13: pass
B14: pass
B15: pass
B16: fail
B17: pass
B18: pass
B19: pass

## Bob

Bob ran on codex in the read-only sandbox and carried the doubt + de-slop lens
this cycle (`eve.md`'s Two lenses, bucket and rubric sections appended to his
persona). His findings are the `BOB` rows above.

Doubt buckets:

FIX: F1 gate output unbounded in memory; F2 the prescribed gate emits no
PASS/FAIL/SKIP/EXIT summary; F3 Blake and Eve receive the design doc through
`run["prd"]`; F4 Eve's fallback loses the doubt appendix; F5 doubt verdicts lose
their source tags; F6 unknown classifications pass validation and still stamp
the batch applied; F7 persona preflight parses frontmatter permissively;
F8 CLI staging cannot receive the ledger or prior findings; F9 `resolve_base()`
is a second diff-base resolver; F10 staging omits Carl's `ui` lens; F11 dispatch
closure assumes undocumented frontmatter and always records `ok`; F12 new
functions exceed the 50-line limit; F13 the tail-sweep floor test accepts
"caps at 4" without the floor.

VERIFY: the acceptance suites and the release gate. Queued in
`00249-stage-and-close-reviews-in-code-v1-checks-1.json` as the four-file pytest
command (one command, already run this cycle, exit 0); the `bash
dev/bin/release-checks` half was not queued ("not queued: command shape" - the
VERIFY text chains two commands) and was run directly this cycle instead.

KNOWN: K1 the flagged either-or assertion is unchanged by this diff; K2 the
registry fixture exemption is behavior-preserving; K3 `__main__.py` already
exceeded the 800-line file limit before this diff.

R1: fail
R2: fail
R3: pass
R4: fail
R6: pass
R7: fail
R8: pass
R9: fail
R10: fail
R11: pass
R12: fail
R13: fail

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

Carl ran on the copilot backend (`gemini-run.sh`, exit 0). His findings are the
`CARL` rows above. His own `bash dev/bin/release-checks` run reported
`SUMMARY: 6 passed, 20 failed` in the `runner recursion guard` group, but that
is an artifact of his own sandbox: `COPILOT_CLI`, `CODEX_SESSION_ID` and
`AUTOPILOT_DISPATCH_DEPTH` were set in his environment, so every codex-wrapper
assertion hit the nested-dispatch refusal (exit 3). He re-ran with
`env -u COPILOT_CLI -u CODEX_SESSION_ID -u AUTOPILOT_DISPATCH_DEPTH`. This
orchestrator's own clean-environment run of the same script passed every group
(counts in the `Tests:` line below), so no gate failure is carried from Carl's
first attempt.

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
R12: fail
R13: pass

Verdict: 36 findings
Tests: 2621 passed, 0 failed, 0 skipped (suite run this cycle)
