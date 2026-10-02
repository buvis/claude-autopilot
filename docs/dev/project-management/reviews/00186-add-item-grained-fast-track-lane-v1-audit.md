# Decision Audit Log: 00186-add-item-grained-fast-track-lane-v1

PRD: `00186-add-item-grained-fast-track-lane-v1.md`
Started: 2026-09-13T16:49:10Z
Completed: 2026-09-13T16:49:10Z
Autonomous: 18  |  Deferred: 24  |  Doubts: 0

### [autonomous] 2026-09-13T16:49:10Z

### [autonomous] 2026-09-13T16:49:10Z

### [autonomous] 2026-09-13T16:49:10Z

### [autonomous] 2026-09-13T16:49:10Z

### [autonomous] 2026-09-13T16:49:10Z

### [autonomous] 2026-09-13T16:49:10Z

### [autonomous] 2026-09-13T16:49:10Z

### [autonomous] 2026-09-13T16:49:10Z

### [autonomous] 2026-09-13T16:49:10Z

### [autonomous] 2026-09-13T16:49:10Z

### [autonomous] 2026-09-13T16:49:10Z

### [autonomous] 2026-09-13T16:49:10Z

### [autonomous] 2026-09-13T16:49:10Z

**Decision**: Cap check: cycle 2 >= rework_cap 2 with 8 unresolved HIGH findings and no CRITICAL

**Choice**: cap-out: every unresolved finding (8 High, 10 Medium, 6 Low after merging duplicates and adding the 5 cycle-1 carried Medium/Low that never got a sweep) appended to state.deferred_decisions as cap-overflow; review_converged emitted with outcome cap_deferred; PRD finalizes as converged-with-deferrals

**Rationale**: Loop mode (_AUTOPILOT_LOOP set): the cap gate defers, never pauses; a CRITICAL would have stalled the PRD and none was raised. No [D2] tasks were created at review step 7 because the cap gate was evaluated first: creating tasks the cap forbids dispatching would leave pending tasks in state.tasks that the finalize session would never run.

### [autonomous] 2026-09-13T16:49:10Z

**Decision**: Gate verification of the eight HIGH findings before deferring them

**Choice**: verified each directly rather than on the reviewer's word: rg over skills/fast-track/scripts finds no pin for reset-refused/branch-failed/base-sha (Alice); SKILL.md:296-298 appends three Eve inputs while lane-dispatch.md:150-158 and the PRD name six (Alice, Bob, Carl); SKILL.md:352-354 and lane-dispatch.md:113-115 list Workflow arg names only, no prd_text/agent_name values (Blake); SKILL.md:153 commits the tests with no pathspec (Bob); the dirty-path preflight at :31-35 covers only ## Files while :191-195 stages CHANGELOG.md (Bob); render_prompt.py _run_set_cmd exits 4 on empty stdout, so an all-new Files list kills Tess's render (Bob); the end-of-run push at :583-585 is gated only on the batch suite (Bob); fast_track_plan.py _load_findings has no severity enum check and both decisions test membership in (CRITICAL, HIGH) (Bob). All eight hold.

**Rationale**: a HIGH deferred to batch end must be a real defect; the cycle-1 gate set the standard of checking mechanical claims directly

### [autonomous] 2026-09-13T16:49:10Z

**Decision**: Three fail-first replay [MECH] rows: test_count_prints_the_items_dispatches_by_kind_sorted_and_ignores_the_rest (absent-ledger case), test_both_rework_values_are_accepted_and_land_as_integers, test_cost_is_null_unless_passed pass against the pre-change code

**Choice**: absorbed into the consolidated table as mech-check rows, then ledger-dismissed (disposition discarded) as behavior-preserving pins by design: each has a sibling that fails at base and pins the fix, and Alice and Carl both verified the same reading

**Rationale**: the replay block says a behavior-preserving refactor's tests pass by design and the gate may ledger-dismiss with that reason; nothing dropped silently

### [autonomous] 2026-09-13T16:49:10Z

**Decision**: Blake's Medium on dev/bin/release-checks (premise-and-skip not honored; acceptance says one line, rg prints two)

**Choice**: discarded with a verified reason: task 6's description re-measured the premise at plan time (five [checks] blocks) and re-anchored it, so the premise held; the acceptance literal contradicts the very block the PRD asks for (echo + pytest = two lines); implementation matches the PRD description

**Rationale**: a finding refuted by the task record and the PRD's own text is not a code defect

### [autonomous] 2026-09-13T16:49:10Z

**Decision**: Gate-raised Medium: SKILL.md:153 Tests commit message is test(<scope>): add tests for <item> while the PRD specifies test(<item>): add tests for <goal>

**Choice**: recorded as a cap-overflow deferral under found_by gate, since no reviewer raised it and the cap forbids a task

**Rationale**: found while verifying Bob's pathspec finding on the same line; fail-loud rules forbid leaving a verified spec mismatch out of the record

### [autonomous] 2026-09-13T16:49:10Z

**Decision**: Reviewer rosters and degraded inputs this cycle

**Choice**: Alice (sonnet), Blake (sonnet, blind), Bob (codex, resumed thread 01a07da8, exit 0, full R and D verdicts), Carl (copilot gemini-3.8-flash, exit 0) all ran; Eve not activated (doubt_reviewer codex, no codex-implemented task); engram pack failed twice with the deterministic gita-registration error, sentinel substituted; no verification-check queue written (Bob emitted FIX/KNOWN prefixes but no VERIFY item)

**Rationale**: degraded by the missing pack, not invalid

### [deferred] 2026-09-13T16:49:10Z

**Decision**: SKILL.md's Roster section gives Eve only 3 run inputs (card, `<base-sha>..HEAD`, changed-file list) while `lane-dispatch.md` documents 6, and the PRD requires "her five run inputs ... and a sixth, the `{OUTPUT_FORMAT}` block ... so each FIX item is also an `[EVE] {emoji} ... | File: ...` line the consolidator can read." SKILL.md never appends the mechanical-checks block or the OUTPUT_FORMAT block to Eve's render. Without the sixth input Eve's FIX items are not consolidator-readable, so a CRITICAL she raises never reaches victor or the exit rule.

**Choice**: deferred to batch end (cap-overflow)

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-13T16:49:10Z

**Decision**: The Workflow tool call for the consensus lane (review-fanout.workflow.js) never states the values for `prd_text` or `agent_name` in either SKILL.md or lane-dispatch.md; only the bare arg names are listed. The PRD explicitly requires `prd_text` = the card and `agent_name` = `ALICE` and cites `review-work-completion/SKILL.md:315-325` as the arg-to-value table to reuse; fast-track's own args block gives an operator no way to know what to put in `prd_text` or `agent_name`. Only `personas` gets an explanation.

**Choice**: deferred to batch end (cap-overflow)

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-13T16:49:10Z

**Decision**: Task 9's blocked-exit failure transitions (`stopped: branch-failed`, `stopped: reset-refused`, `branch: refused (<paths>)`) and the `<base-sha>`/`<rework-base-sha>` capture steps ship with zero test coverage: `rg -i 'reset-refused|branch-failed|branch: refused|rev-parse|base-sha' skills/fast-track/scripts` prints nothing (gate-verified). Task 9 was the only rework task with no test commit (b67a3fa fix only), so a future SKILL.md edit could silently drop either failure transition and nothing in the suite would catch it (rules/testing.md: every bug fix ships with its regression test).

**Choice**: deferred to batch end (cap-overflow)

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-13T16:49:10Z

**Decision**: FIX: Tess's bare commit still includes unrelated staged changes. Add a test-file pathspec and extend commit-scope coverage to the Tests section. (Gate-verified: SKILL.md:148-154 runs `git add <the test files>` then `git commit -m "test(<scope>): add tests for <item>"` with no `-- <paths>` pathspec, while the Implement and Rework commits from task 11 carry one.)

**Choice**: deferred to batch end (cap-overflow)

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-13T16:49:10Z

**Decision**: FIX: The changelog step commits existing foreign edits when CHANGELOG.md is outside the card's Files list. Include it in the dirty-path preflight whenever changelog is not none. (Gate-verified: the Preconditions dirty-path check at SKILL.md:31-35 covers only `## Files`; the changelog step at :191-195 Edits and stages CHANGELOG.md regardless of a pre-existing foreign edit in it.)

**Choice**: deferred to batch end (cap-overflow)

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-13T16:49:10Z

**Decision**: FIX: Tess's interface command still fails when every Files entry is new: the filtered list is empty, and the renderer rejects failed or empty command output. Provide an explicit empty-interface fallback in both render examples. (Gate-verified: `render_prompt.py:_run_set_cmd` returns exit 4 on empty stdout, so `--set-cmd PUBLIC_INTERFACES="cat $(printf '%q ' <entries that exist today>)"` takes the render down for a card that only creates files.)

**Choice**: deferred to batch end (cap-overflow)

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-13T16:49:10Z

**Decision**: FIX: Branch creation or reset failure leaves blocked commits on the current branch, but the final push checks only the batch suite. Disable pushing or terminate the run on either failure. (Gate-verified: SKILL.md:576-585; an item that ended `stopped: reset-refused` keeps confirmed CRITICAL/HIGH commits on the working branch, and the end-of-run `--push` is gated only on a green batch suite.)

**Choice**: deferred to batch end (cap-overflow)

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-13T16:49:10Z

**Decision**: FIX: The findings loader validates keys but accepts invalid severity values; `"high"` or null silently bypasses verification and produces `commit`. Validate field types and the severity enum before either decision. (Gate-verified: `_load_findings` builds `Finding(r["severity"], ...)` with no enum check; `verify_targets` and `exit_action` test membership in `("CRITICAL", "HIGH")`, so a lowercase or null severity fails open to `commit`.)

**Choice**: deferred to batch end (cap-overflow)

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-13T16:49:10Z

**Decision**: `asserted()`'s negator check only inspects text before a match's start (`text[:match.start()]`), so a negator embedded inside a two-limb pattern span (the shape GREEN_STOP/GATE_STOP from task 7 use) is invisible to it. Alice's live repro: `asserted("When the suite is green, this never causes the item to end stopped: tests-green-before-implementation.", GREEN_STOP)` returns True. Task 8's fix (ced1678) closed it only for the multicard patterns; the stop-rule pins still carry the hole (also raised by Bob at fast_track_stop_testutil.py:82 and Carl at :89).

**Choice**: deferred to batch end (cap-overflow)

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-13T16:49:10Z

**Decision**: The prose-testutil pattern carried from cycle 1 (~692-line bespoke reader model vs. a 374-line precedent) grew substantially this cycle: five new testutil modules (`fast_track_multicard_testutil.py` 740 lines, `fast_track_render_testutil.py` 682, `fast_track_stop_testutil.py` 384, `fast_track_wiring_testutil.py` 182, `fast_track_reference_testutil.py` 164, ~2150 lines total) plus `test_fast_track_commit.py` 625 and `test_fast_track_prose.py` at 798/800 lines. Blake: the scripts dir carries far more files than the PRD's Repository Structure names, all test-only. Behavior-preserving simplification, not urgent.

**Choice**: deferred to batch end (cap-overflow)

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-13T16:49:10Z

**Decision**: FIX: The new count CLI catches only ValueError. A JSON null row, missing kind, or unreadable ledger produces a traceback instead of the documented diagnostic and exit 2. Validate ledger rows and handle those failures. (Gate-verified by reading `count_item_dispatches` and `_main`: a `null` row raises AttributeError on `.get`, a row with `queued_at` and no `kind` raises KeyError, a directory or unreadable path raises OSError; only ValueError is caught.)

**Choice**: deferred to batch end (cap-overflow)

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-13T16:49:10Z

**Decision**: FIX: The CLI matrix never tests workflow unavailable with Carl available; incorrectly enabling the workflow whenever Carl exists passes every case. Add that independent flag combination.

**Choice**: deferred to batch end (cap-overflow)

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-13T16:49:10Z

**Decision**: FIX: Every blocking exit fixture starts with a blocker, so examining only the first finding passes. Add a nonblocking row followed by HIGH and require `branch`.

**Choice**: deferred to batch end (cap-overflow)

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-13T16:49:10Z

**Decision**: FIX: The exit prose pin accepts a sentence such as "`branch` never parks the item" because _bound_case checks only matching words. Validate the action's polarity and add negated cases.

**Choice**: deferred to batch end (cap-overflow)

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-13T16:49:10Z

**Decision**: FIX: The strict frontmatter reader accepts raw NUL characters inside scalar values, allowing invalid YAML to pass the pack-wide check. Reject forbidden raw characters before scalar parsing and add regression coverage. (The rework session's own Devon round reported the same ceiling: control characters, tabs in plain values and duplicate keys pass the stdlib reader.)

**Choice**: deferred to batch end (cap-overflow)

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-13T16:49:10Z

**Decision**: FIX: The new metrics test file copies five fixture/CLI helpers from test_record_item.py. Move their shared implementations into one test utility, preserving the separate test files and assertions.

**Choice**: deferred to batch end (cap-overflow)

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-13T16:49:10Z

**Decision**: The Tests commit message in SKILL.md is `test(<scope>): add tests for <item>` while the PRD's Tests-are-the-spec feature specifies `test(<item>): add tests for <goal>`; the scope and subject are swapped. No reviewer raised it; the gate found it while verifying Bob's pathspec finding on the same line.

**Choice**: deferred to batch end (cap-overflow)

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-13T16:49:10Z

**Decision**: `fast_track_plan.py`'s module docstring still carries em dashes ("Lane planner for /fast-track — the four decisions...", "...decide two things and no more — which ones..."), against the project's no-em-dash convention. Pre-existing, untouched by tasks 7-16, self-reported by the build session as an open item.

**Choice**: deferred to batch end (cap-overflow)

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-13T16:49:10Z

**Decision**: `ARCHITECTURE_CONTEXT`'s three-way fallback (`AGENTS.md` -> `CLAUDE.md` -> `/dev/null`) goes beyond task 10's literal ask ("`## Constraints` + `AGENTS.md`"); it's tested and defensible but is scope not explicitly requested.

**Choice**: deferred to batch end (cap-overflow)

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-13T16:49:10Z

**Decision**: FIX: Three standalone roster tests duplicate cases already fully asserted by the eight-combination matrix. Remove those duplicate wrappers while retaining the matrix and explicitly required acceptance-test names. (Carried from cycle 1, never tasked; no tail sweep runs on a cap-out, so it is deferred here rather than dropped.)

**Choice**: deferred to batch end (cap-overflow)

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-13T16:49:10Z

**Decision**: FIX: `_pasteable`, `_instructive` and `code_fragments` repeat the module's explanation of fenced commands in lengthy docstrings. Keep the central rationale and replace these repetitions with concise function contracts. (Carried from cycle 1, never tasked; no tail sweep runs on a cap-out.)

**Choice**: deferred to batch end (cap-overflow)

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-13T16:49:10Z

**Decision**: Every `render_prompt.py` call in SKILL.md omits the `--dispatch-kind`/`--dispatch-task` flags the PRD names verbatim for Ivan and Tess, issuing a separate `record_dispatch.py start` call instead. Functionally equivalent but departs from the cited reuse pattern without being flagged as deliberate. (Carried from cycle 1.)

**Choice**: deferred to batch end (cap-overflow)

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-13T16:49:10Z

**Decision**: `count_item_dispatches` calls `json.loads(line)` on every line with no try/except; a blank or truncated ledger line raises `json.JSONDecodeError` and crashes the planner rather than skipping the bad row. (Carried from cycle 1; the task-16 CLI now turns the ValueError into exit 2 with one stderr line, so the library function still raises but the CLI no longer tracebacks on that shape. Bob's cycle-2 finding on `:140` covers the shapes it still misses.)

**Choice**: deferred to batch end (cap-overflow)

**Rationale**: rework cap reached with this finding unresolved

### [deferred] 2026-09-13T16:49:10Z

**Decision**: The exit rule and the foreign-WIP dirty-path check are documented only as SKILL.md prose; no automated test runs those git commands end to end, so a watered-down rewording could still pass the string-matching pins. (Carried from cycle 1; overlaps Alice's cycle-2 High on the untested task-9 transitions.)

**Choice**: deferred to batch end (cap-overflow)

**Rationale**: rework cap reached with this finding unresolved
