# Backlog review - claude-autopilot - 2026-09-05

Verdict: GO - `backlog/` holds 00176, 00178, 00179, 00180, all READY after the
apply pass. 00175 left the backlog at 21:03, moved to `done/` by the Codex
session that built it. Preflight done at 21:35: (1) the 00174 + 00175 work is
committed as `9336ab5` (32 files, +1725/-228; `dev/bin/release-checks` re-run
before the commit: 224 passed, 0 failed), and (2) the stale `202609011951`
state is archived to `reports/202609011951-state-final.json` and the
`paused-by-operator` marker removed. Tree clean; `autopilot loop` can start.

Inventory (measured 19:25): `backlog/` holds 00175, 00176, 00178, 00179, 00180;
`wip/` empty; `hold/` holds 00110; `discovery/` holds 00157, 00177. Sequence
numbers unique across all dirs. No loop or wrapper process; a Codex TUI session the user started at 14:35
(`~/.codex/sessions/2026/09/05/rollout-2026-09-05T14-35-14-*.jsonl`,
`originator: codex-tui`, `cwd` this repo, prompt "implement ... 00175 ... by hand
avoiding the usual autopilot ceremony ... fresh context based subagents") is
editing this checkout (see Preflight). An earlier draft of this report blamed a
`claude` process (pid 21171); that one runs in `doogat/ddb` and was a wrong guess.
check_links (backlog/wip only): four hits, all in 00178 lines 65-66, all per-cycle
runtime files (`review-context-{id}.md` from `gather-context.sh:50`,
`review-diff-{id}.diff` from SKILL.md:190, `{agent}-prompt-{id}.md` from SKILL.md
step 4) - not findings. Law read live: `create-prd/SKILL.md` +
`assets/{minimal,standard,example_prd_rpg}.md`. Budget rules read from this repo's
`skills/plan-tasks/SKILL.md` steps 4-4.7 (150K per task, one split attempt, then
`hold/`); the installed cache is 0.5.0, released 11:12 today from this tree.

## Preflight (repo state, not PRD findings)

- **Working tree dirty, two PRDs deep.** 18 files from 00174 (in `done/`, reviewed
  by hand under `dev/local/reviews/00174-manual/`, uncommitted since 13:09) plus
  00175's files, written 19:19-20:56 by the Codex session while this review ran
  (`gemini-run.sh`, `test_gemini_run.sh`, `use-gemini/SKILL.md`,
  `review-work-completion/SKILL.md`, `references/agent-invocation.md`,
  `state-schema.md`, `test_carl_skip_prose.py`, `release-checks`, and by 20:56
  also `run-autopilot/SKILL.md` and `phase-build.md`) and a CHANGELOG entry for
  both. 26 files, +874/-228 at 21:07. The Codex session closed at 21:03
  ("Implemented manually; PRD moved to done ... Changes remain uncommitted");
  `dev/bin/release-checks` re-run here at 21:25: 224 passed, 0 failed
  (118 + 5 + 41 + 33 + 27). A batch must
  start from a committed tree: the first task's `release-checks` and suite runs
  exercise whatever is in the checkout, and the per-task commit sweeps stray edits
  into the wrong PRD's range.
- **Stale batch state.** `dev/local/autopilot/state.json` still carries batch
  `202609011951` (`prd: 00171`, `phase: build`) beside a `paused-by-operator`
  marker from 09:11 today, with plugin pins aegis 0.3.2 / warden 0.14.0. A fresh
  `autopilot loop` resumes that identity and runs the plugin-drift preflight
  against those pins.
- **Both resolved after the walkthrough (21:35):** commit `9336ab5` holds the
  00174 + 00175 work as one `fix(work/use-gemini)` commit (the two PRDs share
  hunks in `state-schema.md` and `CHANGELOG.md`); `state.json` moved to
  `reports/202609011951-state-final.json` beside that batch's report, and the
  pause marker was deleted. `state.json.bak` and the empty lock stay.

## Map

| # | PRD | template | lines | subsystems | depends on | verdict |
|---|-----|----------|-------|------------|------------|---------|
| 00175 | restore-the-gemini-reviewer-lane-v1 | standard | 135 | use-gemini (`gemini-run.sh`, `test_gemini_run.sh`, SKILL.md); review-work-completion (SKILL.md steps 1/5/6, new `test_carl_skip_prose.py`); run-autopilot (`state-schema.md`) | none stated; built by hand in the working tree 19:19-21:03 | DONE - moved to `done/` 21:03 by the Codex session; review record `dev/local/reviews/00175-manual-review.md`; code uncommitted |
| 00176 | guard-the-target-reads-in-the-doctor-v1 | standard | 94 | use-codex (`codex_hook_doctor.py`, `test_codex_hook_doctor_parse_errors.py`) | none (00173 done) | READY (Q1, N2 applied) |
| 00178 | fix-bob-first-run-and-specify-his-retry-v1 | standard | 188 | `agents/bob.md`; review-work-completion (`retry-policy.md`, `agent-invocation.md`, SKILL.md steps 5/6, new `test_retry_policy_prose.py`); `dev/bin/release-checks` | none (cites 00180 for the argv cap; no dependency on this macOS host) | READY (B4, N3, N4 applied) |
| 00179 | cap-the-adversarial-test-loop-at-one-round-v1 | standard | 119 | work (SKILL.md 2.8/2.85, `adversarial-test-prompt.md`, new `test_adversarial_cap_prose.py`); `dev/bin/release-checks` | none | READY |
| 00180 | route-codex-prompt-through-stdin-v1 | standard | 87 | use-codex (`codex-run.sh`, `test_codex_run.sh`, `dispatch-contract.md`) | none (00171 done) | READY (B5 applied) |

Compliance (lens A): all five on the standard template, every heading present and
ordered, every task carries `Acceptance:`, `#### Feature:` headings unique, no
stubs or `(guess)` markers, frontmatter values valid. Custom phase titles in
00175/00176/00180 accepted as in the 2026-09-03 gate.

Grounding verified with `rg` (true at 19:25 against the committed tree unless
noted): `gemini-run.sh:73` pin, exit 3 at l.21/25 (nested-dispatch guard);
`records.py` preserves `batch` (l.13, l.106); review SKILL.md l.72 Carl check,
l.253 `ui` lens key, l.385 `reviewers:`; `state-schema.md` § batch (l.216+), no
`unavailable_reviewers`; `check_review_file.py` and `test_codex_resume_contract.py`
(`_section`, unittest) exist; doctor `exists()` l.54 then `stat()` l.56, unguarded
`read_bytes()` l.68 (except tuple is `SyntaxError, ValueError`) and l.81, `glob`
l.113, write l.219-220; doctor test modules 772/789/795/61 lines; `bob.md` l.7,
l.26-39 exactly as quoted, "Perform STATIC analysis only" pinned at
`test_agent_registry.py:235`, leak check l.185, no other pin on the sandbox
wording; `retry-policy.md:19` "amended prompt file"; `agent-invocation.md:45`
sentence; `record_dispatch.py` `OUTCOMES = ok|timeout|killed|error|lost`,
`--kind`/`--task` free text, no-dir start prints an id and writes nothing;
severity emojis 🔴🟠🟡⚪ and `✅ No issues found` (`output-formats.md:24,30`);
`adversarial-test-prompt.md:18-19` and work SKILL.md:242 verbatim, 2.85 at
l.244-257, `test-author-prompt.md:80`, `red-check.md:25`, 500-line ceiling at
`test_dispatch_prose.py:23`, no test pins the old numbers (control: 8 `Tess` hits
in that file); `codex-run.sh` `"$PROMPT"` at l.145/216/244/304/357, pipefail l.7,
`run_cmd` l.162, resume argv l.328 feeds l.244; `test_codex_run.sh` 39 `PASS "`
lines and every case name 00180 quotes; `dispatch-contract.md:21`;
`sonnet-run.sh:238` printf shape; `codex exec --help` documents `-`.

## Findings

### Blocking

- **B1** [00175] D grounding + E collisions: all three phases are already built,
  uncommitted, in this checkout by the user's 14:35 Codex TUI session and its
  fresh-context sub-rollouts (files dated 19:19-19:28;
  Phase 2 landed at 19:28 while this review ran: `unavailable_reviewers` and its
  `_details` sibling in `state-schema.md`, the step-1 read, the step-5 write, the
  step-6 skip line, `test_carl_skip_prose.py`, and its `release-checks` block).
  Phase 0-1 detail:
  `DEFAULT_COPILOT_MODEL="gemini-3.8-flash"`, a `permanently_unavailable()`
  stderr classifier returning exit 4 with a one-shot native fallback, 15 new
  `test_gemini_run.sh` cases, the probe and exit-code table in
  `use-gemini/SKILL.md`, a "Carl availability" paragraph in review SKILL.md step 5,
  and a rewritten § Carl in `agent-invocation.md` -> fails as: rework thrash (autopilot
  plans and reviews work that is already in the tree, against text whose exit
  code and pin no longer match) and the dirty tree lands in the batch. Fix: decide
  in the walkthrough - rewrite 00175 to Phase 2 once the hand work is committed,
  hand the whole PRD back to autopilot, or hold it.
- **B2** [00175] B executability: Feature "A served model", Behavior: "If copilot
  serves no Gemini model at all, decide and record whether Carl moves to a
  different backend or is retired from the roster" -> fails as: unattended hang (a
  decision deferred to implementation). Answer, from the in-flight work: copilot's
  `/model` picker on 2026-09-05 rejects the Pro Preview pin and offers Gemini
  Flash; Carl stays on Gemini at `gemini-3.8-flash`. Fix: write that in.
- **B3** [00175] B + C: the "reserved exit code" is never numbered; Feature 2 says
  "mirroring `codex-run.sh`'s exit 3", but `gemini-run.sh` already exits 3 for the
  nested-dispatch guard (l.21, l.25) -> fails as: wrong-TDD lock-in (the stub
  cases in task 2 and the step-5 consumer in Phase 2 each pick a number). Fix: pin
  exit 4 (the in-flight value; 3 stays the guard) in Feature 2 Outputs, Phase 0
  task 2, the Phase 2 task and the Test Strategy.
- **B4** [00175, 00178] B executability: observational success lines. 00175
  Success Metric 4, Phase 2 Exit Criteria and Test Strategy edge case 3 ("cycle 2
  and PRD B's cycle 1 ... no `gemini-run.sh` call"); 00178 Success Metric 1 ("A
  cycle with codex available writes exactly one `bob` start row ... at least one
  `R{n}: pass` line"). The batch runs the installed 0.5.0 cache, so nothing these
  PRDs change fires in-session -> fails as: rework thrash (reviewers file
  unmet-criteria findings; the 00093-v1 pattern, D5 in the 2026-08-26 gate). Fix:
  label each "post-release signal, not judged in-session"; the in-session checks
  are the prose tests and `rg` pins already in the tasks.
- **B5** [00180] B + C: Phase 0 acceptance `rg -n '"\$PROMPT"'
  skills/use-codex/scripts/codex-run.sh prints exactly one hit, the copilot line`
  cannot pass: today the pattern hits l.145 (the `Prompt required` guard), l.216 (a
  comment), l.244, l.304 and l.357; after the change the guard, the comment, the
  two new `printf '%s' "$PROMPT" |` lines and the copilot line all still match.
  Also "the three codex invocations" names two edit sites: l.244 and l.304; the
  resume argv at l.328 reaches codex through l.244 -> fails as: rework thrash (an
  implementor cannot satisfy the criterion; a reviewer cannot key it). Fix:
  acceptance becomes `rg -c 'PROMPT" < /dev/null' skills/use-codex/scripts/codex-run.sh`
  prints 1 (the copilot line) and `rg -c "printf '%s' \"\\\$PROMPT\" \|"
  skills/use-codex/scripts/codex-run.sh` prints 2; the task says two lines (244,
  304) and updates the l.216 comment to the new shape.

### Questions

- **Q1** [00176] B executability: Feature "An unreadable target verdicts itself",
  Behavior: "Reuse an existing verdict string ... `syntax_error` already carries a
  detail ... Decide the mapping explicitly in the task"; Risks: "the alternative is
  a new verdict string ... decide once, in task 1". Task 1 says only "mapping
  `OSError` onto an existing verdict". The test author sees the task text alone;
  Blake reads the `syntax_error` lean. Options: pin `syntax_error` (no `_report`
  or SKILL.md exit-list change; `unrepairable` on repair via l.171) / a new
  `unreadable` verdict (cleaner meaning; touches `_report` counting, the use-codex
  SKILL.md exit list and the prose pins) / leave it to the implementor.

### Non-blocking

- **N1** [00175] D grounding: review SKILL.md:72 ("serves `gemini-3.1-pro-preview`")
  and `agent-invocation.md:58` ("exits non-zero ... skip Carl") go stale after the
  pin and exit-code change and are not in the PRD's tree. Already rewritten in the
  in-flight working tree; moot if that lands.
- **N2** [00175, 00176] A compliance: no `default_model` and no
  `model_tier_rationale` (create-prd 5.6 wants the omission recorded as a
  decision). Suggest `sonnet` for 00176 (guards with exact call sites, additive
  tests) and for a Phase-2-only 00175 (prose transcription); `opus` if 00175 keeps
  the stderr classification (invented predicate).
- **N3** [00178] B frontmatter: prose-only PRD without `catchup: skip` /
  `design: skip`, unlike siblings 00179 and 00180.
- **N4** [00178] C coherence: the lack-of-input predicate (`^R[0-9]+: pass` count 0
  AND `^\[BOB\] (🔴|🟠|🟡|✅)` count 0) also matches a first run whose only findings
  are ⚪ Low-severity real findings, since ⚪ is the Low emoji
  (`output-formats.md:24`). Discovery 00177 says "the only finding lines are ⚪
  `Cannot statically verify` lines". Optional third condition:
  `rg -c '^\[BOB\] ⚪ Cannot statically verify' <bob-output>` prints at least 1.
- **N5** [00175] A/C: Dependency Graph labels "Core Layer (Phase 2)" while phases
  run 0/1/2; Phase 1 (docs) maps to no layer. Nit; disappears in a Phase-2 rewrite.
- **N6** [00179] D: `skills/work/SKILL.md` is 499 lines against the 500-line
  ceiling in `test_dispatch_prose.py` (HEAD and the dirty tree agree). This PRD
  adds no line (the sentence joins an existing paragraph); the next PRD to add one
  breaks the pin.
- **N7** [00180] G gaps: `gemini-run.sh` keeps the positional `-p "$PROMPT"`,
  leaving two prompt-delivery shapes across the three runners. Scoped out by the
  PRD and the discovery (Carl's prompt is short, never inlined); noted, no PRD.

## Reshapes

- **Withdrawn**: a Phase-2-only rewrite of 00175 was drafted while Phase 2 looked
  unbuilt; at 19:28 the owning session delivered Phase 2 too, so the PRD is
  complete in the tree and needs no reshape, only its owner's commit and move.
- **Considered, not proposed**: renumbering 00180 below 00178 (00178 cites 00180 as
  the PRD that removes the argv cap). No dependency: 00178 states the 1 MiB macOS
  limit covers the observed 39 KB prompt. Order stays.
- Sizing: all five under 200 lines and one subsystem each except 00175 (three).
  00180 is small (87 lines, one task) but owns its own test surface, the same shape
  00171 shipped in; no merge.

## Gaps

- 00177 must-have 8 (Carl skipped for the rest of the batch) is built in the
  working tree as of 19:28 (see B1); its review and commit belong to the owning
  session, not this batch.
- Every fix-type PRD ships its regression test (00176 fail-first, 00180
  watched-failing, 00175 stub cases, 00178/00179 prose pins).
- No consumer/producer holes: `record_dispatch.py` takes free-text `--kind`
  (00178); `detect_tautological_tests.py` is in 0.5.0 (00179's premise).

## Traceability

Discovery 00177 must-haves: 1 persona read-only shell -> 00178 F1; 2 retry
amendment -> 00178 F3; 3 codex stdin incl. resume -> 00180; 4 one dispatch unless
triggers -> 00178 F2; 5 ledger rows -> 00178 F4; 6 adversarial cap -> 00179 F1-F2;
7 ledger caps pinned -> 00179 F3; 8 Carl batch skip -> 00175 Phase 2. Out of scope
respected: no lens removed, no driver polling, no create-prd hygiene. 00175 and
00176 come from the 00173 review, not a discovery doc.

## End state after this batch

Carl runs on a served Gemini Flash pin, a dead backend exits 4 and stays off for
the batch; Bob reads his inputs through read-only shell, has a written inlined
retry and appears in the dispatch ledger with Carl; the Tess/Devon loop stops
after one strengthen round; the codex prompt travels on stdin so no byte is an
option and no argv cap applies; the hook doctor never exits 2 on a host file.
Nothing is live until the hand-built 00174/00175 work is committed, the batch
drains, and `dev/bin/release` + `/plugin update` ship it. Left over: the
positional prompt in `gemini-run.sh`, work SKILL.md one line under its ceiling,
00110 in hold, and the stale `202609011951` state file.

## Frontmatter tuning

| PRD | suggestion | why |
|-----|------------|-----|
| 00175 | `default_model: sonnet` + rationale (Phase-2 rewrite) or `opus` (whole PRD) | prose transcription vs an invented stderr predicate |
| 00176 | `default_model: sonnet` + rationale | exact call sites, additive fail-first tests |
| 00178 | `catchup: skip`, `design: skip` | prose-only, like 00179/00180 |

## Decisions applied

Walkthrough 20:40-20:53, five packets. Minutes:

1. B1 [00175] - **skipped, deferred to the owning session**: no edit, no move.
   The owner turned out to be the user's own 14:35 Codex TUI session; it ran
   its own fresh-context requirements, blind and doubt reviews, moved the PRD to
   `done/` at 21:03 and left the code uncommitted. B2, B3, N1, N5 and the 00175
   half of B4 lapse with it; exit 4 and `gemini-3.8-flash` are the shipped values.
2. B5 [00180] - **applied (count the shapes)**: acceptance is now
   `rg -c '"\$PROMPT" < /dev/null' ...codex-run.sh` prints 1 (today 4) and
   `rg -c "printf '%s' \"\\\$PROMPT\" \|" ...codex-run.sh` prints 2 (today 0);
   both commands verified against a scratch copy of the post-change lines (1 and
   2). Task, Feature Inputs and Module text say two dispatch lines (244, 304;
   328 feeds 244); the task rewords the line-216 comment without quoting argv.
3. B4 [00178] - **applied (labelled)**: Success Metric 1 carries "Post-release
   signal, not judged in-session: the in-session checks are the prose test and
   the `rg` pins in Phases 0-2."
4. Q1 [00176] - **applied (pin `syntax_error`)**: Feature Outputs/Behavior, task 1
   and the Risks bullet name `syntax_error` with the `OSError` text as detail; the
   "decide in the task" sentence and the new-verdict alternative are gone.
5. LOW batch - **all three applied**: 00176 `default_model: sonnet` +
   `model_tier_rationale`; 00178 `catchup: skip`, `design: skip`; 00178
   lack-of-input trigger is ALL THREE of the two zero counts plus
   `rg -c '^\[BOB\] ⚪ Cannot statically verify' <bob-output>` >= 1, mirrored in
   Phase 1 task 1 ("three `rg -c` commands"), the Phase 2 assert list and the
   Test Strategy edge case.

Report-only, no action: N6 (work SKILL.md at 499/500 lines), N7 (`gemini-run.sh`
positional prompt, scoped out by discovery 00177), the 00178/00180 order
(no dependency). Deferred with a durable home: nothing.

## Post-gate actions (21:35-22:45)

- Commit `9336ab5` (00174 + 00175) pushed; batch `202609011951` state archived;
  pause marker removed.
- 21:40: a second Codex TUI session (pid 65763, `rollout-2026-09-05T21-40-07`)
  started implementing 00176 by hand: 00176 moved to `wip/` at 21:48, branch
  `fix/00176-doctor-target-io` checked out in this checkout, three
  `fix(use-codex)` commits so far. **00176 is no longer part of this batch**;
  the remaining backlog is 00178, 00179, 00180.
- 22:23: `dev/bin/release patch` ran on that branch by mistake (release commit
  `d37dfb5`, tag, marketplace bump all on the unmerged branch). Undone per the
  user's choice: `4f9ca64` reverts the stamp on the branch, tag deleted
  locally and on origin, marketplace bump reverted (`1bad5bd`), re-released
  from a master worktree: `9968aad` = v0.5.1 (00174 + 00175 only), marketplace
  `b7acd49`, worktree removed.
- Plugin cache refreshed to 0.5.1 (see the final chat message for the check).
- 23:56: the Codex session finished 00176 (four cleared-context review
  cycles, 224 release checks, 2,616 tests by its account), merged the release
  metadata into its branch (`560f061`), fast-forwarded `master`, deleted the
  branch, moved 00176 to `done/` and pushed; the doctor fix sits under
  [Unreleased]. `release-checks` re-run on merged master: 224 passed.
- 2026-09-06 00:01: `autopilot loop` launched for this repo on the plain
  renderer from a detached launcher (registry `55019.json`, driver pid 55029,
  first session pid 55042, plugin cache 0.5.1). Backlog at launch: 00178,
  00179, 00180. A first launch attempt died on `set -u` (the profile function
  reads unset variables); the one-line error at the top of `wrapper.log` is
  that attempt. A separate loop (registry `54209.json`) belongs to
  `agent-skills`.

Post-apply lens A on 00176/00178/00180: every template heading present and
ordered, frontmatter fields valid. Post-apply `check_links.py` (backlog/wip):
the same four 00178 runtime-artifact paths (`review-context-{id}.md`,
`review-diff-{id}.diff`, `bob-prompt-{id}.md`, `bob-prompt-{id}-retry.md`), all
defined by review-work-completion step 4 / `gather-context.sh` - not findings.
Gate honesty: no lens skipped; 00175's grounding was measured against a tree
that changed three times during the review (19:19, 19:22, 19:28), so its lines
describe the 19:28 state; no subagents used. Release checks re-run on the
final tree at 21:25: 224 passed, 0 failed.
