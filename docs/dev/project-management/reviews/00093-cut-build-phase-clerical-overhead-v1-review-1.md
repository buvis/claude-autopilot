---
prd: dev/local/prds/wip/00093-cut-build-phase-clerical-overhead-v1.md
review: 1
date: 2026-08-15
head_sha: a5af408158daa57846cb628271bab03900bb2406
codex_thread_id: 01a005d3-23bf-7b70-9866-305e0021a41f
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00093-cut-build-phase-clerical-overhead-v1

Diff range: `2aaeeb5a900d79071ffc3afd06704b35a2b43605..a5af408158daa57846cb628271bab03900bb2406`

codex_rung_guard: not fired

## Review Summary

Reviewed: 7 completed tasks
PRDs checked: 00093-cut-build-phase-clerical-overhead-v1

### Agent Status

- Alice (Claude, consensus lens): ✅ Available
- Blake (Claude, blind/PRD-only lens): ✅ Available
- Bob (codex, doubt + de-slop lens): ✅ Available
- Carl (Gemini via copilot, UI/generalist lens): ✅ Available

Consensus engine: `legacy` (single Alice subagent). Doubt reviewer: `codex`;
the codex doubt-roster guard did not fire (all 8 recorded task attempts were
implemented by `claude`, none by codex), so Eve was not added as a fifth lens.

### Degradations, recorded

- **No engram context pack this cycle.** `engram pack` resolves the repo root
  via `git rev-parse --show-toplevel`, which does not work in this `~/.buvis`
  bare-repo home, and `gather-context.sh` does not run here either. Every prompt
  that takes the pack-file or pack-findings placeholder received the documented
  sentinel `(no pack available this cycle)`. Reviewer inputs (context, diff, PRD, design
  doc, task list) were built by hand and staged under `/tmp` instead.
- **Carl mislabelled his own output lines `[BOB]`.** He copied the agent tag
  from the output-format example block. No retry was spent: the bracketed name
  is deliberately not captured by `consolidate_findings.py` — the `NAME:FILE`
  pair the caller passes is authoritative — so his findings are correctly
  attributed to CARL in the table below.

## Consolidated Findings

57 findings: 3 🔴 Critical, 15 🟠 High, 24 🟡 Medium, 15 ⚪ Low.

**Consensus counts understate agreement.** `consolidate_findings.py` merges by
file plus a Jaccard threshold on the description, so the same defect described
in different words lands in separate rows. The 500-line-metric defect appears
three times (Alice, Blake, Bob) and the zero-inline-prompt defect appears four
times (Alice, Blake, Bob, Carl) rather than merging. The decision gate treats
these as the higher-consensus findings they are.

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [3/4] | 🔴 | Task 7's acceptance criterion is not met: against the named baseline transcript the script reports 2.80 statectl calls per completed task, not ">= 7". Independently confirmed (14 statectl Bash calls, 5 distinct completed TaskUpdate ids, no duplicates). The golden test was rewritten to assert 2.80, so the PRD's Success Metric baseline ("7.5 per task", target "at most 2") needs operator re-baselining before it can gate anything | /Users/bob/.claude/skills/work/scripts/test_check_build_overhead.py:1087 | 7 | ALICE, BLAKE, BOB |
| [2/4] | 🔴 | PRD Success Metric "work/SKILL.md body lands at or under 500 lines" is unmet: the file is 772 lines and this diff grew it (+65/-56). No task in the plan targets the slimming the PRD called binding | /Users/bob/.claude/skills/work/SKILL.md | general | ALICE, BLAKE |
| [2/4] | 🟠 | references/subagent-dispatch.md § Subagent Dispatch Budget still mandates the replaced procedure — assemble the prompt string, write it to /tmp, measure with `wc -c`, prepend the abort line — while all three rewritten sites point readers at that same file for the trim rule | /Users/bob/.claude/skills/work/references/subagent-dispatch.md:15-53 | 4 | ALICE, BLAKE |
| [2/4] | 🟠 | Tess loses the mandatory 100K abort-instruction line: tess-prompt.md does not contain it (ivan.md does), and step 2.7 now states "nothing further needs adding to the prompt by hand", dropping subagent-dispatch.md step 4 for an Agent-tool dispatch | /Users/bob/.claude/skills/work/references/tess-prompt.md | 3 | ALICE, BLAKE |
| [2/4] | 🟠 | The reference the new probe prose points at still contradicts it: qwen-integration.md:26 "The preflight runs once per task attempt", and codex-implementor.md:11 "Same placement as the qwen preflight, but scoped per batch, not per task". Neither was updated, so the cited authority instructs per-task probing | /Users/bob/.claude/skills/work/references/qwen-integration.md:26 | 5 | ALICE, BLAKE |
| [2/4] | 🟠 | The "zero inline prompt bodies" migration is incomplete and now self-contradictory: step 5.7's CRITICAL/HIGH retry still assembles Ivan's prompt inline "with the code-quality rules block from references/code-quality-principles.md", and that file's own header still claims steps 3, 5.5, 5.7 and 7 copy the snippet verbatim | /Users/bob/.claude/skills/work/SKILL.md:679 | 4 | ALICE, BLAKE |
| [2/4] | 🟡 | The new red_check value "n/a:new_module" is undocumented: attempt-logging.md still specifies `"red_check": "skipped:<cause>" | null` as the entry schema, and it is the authority every attempt-log consumer reads | /Users/bob/.claude/skills/work/references/attempt-logging.md:25,56 | 6 | ALICE, BLAKE |
| [2/4] | 🟡 | Step 5.5's retry sentence names both --set-cmd FAILING_TESTS="cat ..." and --set-file FAILING_TESTS=<scratch file> for the same key, leaving the orchestrator to guess which flag to emit | /Users/bob/.claude/skills/work/SKILL.md:480 | 4 | ALICE, BOB |
| [1/4] | 🔴 | Dynamic task/PRD text is interpolated into double-quoted Bash arguments, allowing quotes, backticks, or `$()` to break parsing or execute commands | .claude/skills/work/SKILL.md:231 | 4 | BOB |
| [1/4] | 🟠 | Step 5.7's Pat render passes a skill-relative --set-file path; reproduced from cwd=/Users/bob/.claude: "render_prompt: --set-file path not found for {SIMPLIFICATION_MANDATE}: references/simplification-mandate.md", exit 4 — every per-task review render fails. Needs ~/.claude/skills/work/references/simplification-mandate.md | /Users/bob/.claude/skills/work/SKILL.md:669 | 4 | ALICE |
| [1/4] | 🟠 | The new qwen prose omits statectl's mandatory <state.json> positional; reproduced: `statectl.py set qwen_preflight '{...}'` → "unsupported verb: 'qwen_preflight'", exit 1, and `statectl del qwen_preflight` hits the len(argv)<3 usage exit. Every other statectl call in this file carries <state.json> | /Users/bob/.claude/skills/work/SKILL.md:406,409 | 5 | ALICE |
| [1/4] | 🟠 | Steps 5.5 and 7 tell the orchestrator to re-render ivan.md with only RETRY_INSTRUCTION and FAILING_TESTS, and give no --out; ivan.md also carries {ARCHITECTURE_CONTEXT} and {FILE_PATHS}, so the documented call exits 1 ("missing placeholder: {ARCHITECTURE_CONTEXT}", reproduced) | /Users/bob/.claude/skills/work/SKILL.md:480,746 | 4 | ALICE |
| [1/4] | 🟠 | Task prose is interpolated raw into double-quoted bash words (--set TASK_SUBJECT/TASK_DESCRIPTION/TASK_ACCEPTANCE_CRITERIA/FILE_PATHS); task text in this repo routinely contains backticks and $( ), which bash executes and strips — silent prompt corruption plus arbitrary execution. The quoting instruction covers only paths inside --set-cmd. This is the same quoting failure the PRD's contract-card metric exists to eliminate | /Users/bob/.claude/skills/work/SKILL.md:231,233,665-667 | 4 | ALICE |
| [1/4] | 🟠 | code-quality-principles.md still declares "/work steps 3, 5.5, 5.7, and 7 copy the Prompt Snippet verbatim into every Ivan dispatch" - now false for 3/5.5/7; an orchestrator obeying it double-inlines the block ivan.md already bakes in | /Users/bob/.claude/skills/work/references/code-quality-principles.md:7-11 | Phase 1 | BLAKE |
| [1/4] | 🟠 | Pat rendering uses a repo-relative simplification-mandate path, so ordinary project-root execution cannot find the skill-owned file | .claude/skills/work/SKILL.md:669 | 4 | BOB |
| [1/4] | 🟠 | The zero-inline-prompt requirement remains unmet: Tess quality retries and review-triggered Ivan repairs still assemble instructions inline | .claude/skills/work/SKILL.md:258 | 4 | BOB |
| [1/4] | 🟠 | The binding 500-line limit is unmet; the changed work skill extends beyond line 746 | .claude/skills/work/SKILL.md:746 | 4 | BOB |
| [1/4] | 🟠 | No tests bind the new qwen cache/invalidation flow, red-check branching, or Pat/Tess/Ivan render integrations required by the design test strategy | .claude/skills/work/SKILL.md:310 | general | BOB |
| [1/4] | 🟠 | Subprocess TimeoutExpired logic in --set-cmd is entirely untested | .claude/skills/work/scripts/test_render_prompt.py | 1 | CARL |
| [1/4] | 🟠 | completed_tasks double-counts if TaskUpdate status=completed is emitted twice for the same task_id | .claude/skills/work/scripts/check_build_overhead.py | 7 | CARL |
| [1/4] | 🟡 | completed_tasks counts TaskUpdate calls rather than distinct task ids, so a task re-completed by step 7's regression path (re-open → in_progress → "Mark the task completed") or by a rework cycle double-counts and deflates the headline ratio — the exact metric the PRD gates on | /Users/bob/.claude/skills/work/scripts/check_build_overhead.py:463-465 | 7 | ALICE |
| [1/4] | 🟡 | render_prompt.py exits 2 (persona unreadable) and 3 (unterminated frontmatter) with nothing on stderr, unlike exits 1/4/5 which all print a named cause; an unattended Bash call then sees a bare non-zero code, and no SKILL step documents any exit-code handling for steps 2.7 or 3 | /Users/bob/.claude/skills/work/scripts/render_prompt.py:553,557 | 1 | ALICE |
| [1/4] | 🟡 | Both new main() functions exceed the 50-line rule (render_prompt.main 74 lines, check_build_overhead.main 66 lines per the mechanical-facts block); extracting the --set*/assignment resolution loop and the per-block tool-use classifier are behavior-preserving splits | /Users/bob/.claude/skills/work/scripts/render_prompt.py:56 | 1 | ALICE |
| [1/4] | 🟡 | The four prose-only tasks (steps 2.7/3/5.5/5.7/7 rewrite, qwen batch-scope, red-check skip) ship with no binding test, though the design's own test-strategy names three suites for them and the repo has prose-assertion precedent (test_fablectl.py asserts on work/SKILL.md, test_work_routing.py models step-3 routing) | N/A | general | ALICE |
| [1/4] | 🟡 | Spec'd re-probe trigger narrowed: PRD says re-probe "after any qwen dispatch that fails its step-5.5 gate or times out"; implementation explicitly excludes step-5.5 gate failures | /Users/bob/.claude/skills/work/SKILL.md:409 | Phase 1 | BLAKE |
| [1/4] | 🟡 | The documented re-probe recovery `statectl del qwen_preflight` exits 1 when the field is already absent (do_del raises UsageError on KeyError) - a second infra failure in one batch errors in an unattended loop | /Users/bob/.claude/skills/run-autopilot/cli/statectl.py:171-177 | Phase 1 | BLAKE |
| [1/4] | 🟡 | Abort/escalate-away path still writes `statectl append tasks[i].attempts '<entry-json>'` - inline JSON on the shell (the exact quoting hazard this PRD removed) and an array-INDEX path the PRD itself says stops matching id once rework appends `[D{cycle}]` follow-ups; wrong-task append risk | /Users/bob/.claude/skills/work/references/attempt-logging.md:75-79 | general | BLAKE |
| [1/4] | 🟡 | "At most 2 statectl invocations per completed task" is not structurally guaranteed: step 5.6 still directs a separate `self_deslop` write on every task (including the skip path), plus escalation's `tasks[i].model` mirror and the qwen breaker counter writes | /Users/bob/.claude/skills/work/SKILL.md:634-642 | general | BLAKE |
| [1/4] | 🟡 | Step 5.6 writes `tasks[i].attempts[-1].self_deslop` but the attempt entry is only appended at step 6 by `task-done`; on a first attempt `attempts` is empty so the indexed write fails with "json-path index out of range: [-1]" - the prose even admits the entry is "written by step 6" | /Users/bob/.claude/skills/work/SKILL.md:634 | general | BLAKE |
| [1/4] | 🟡 | render_prompt.py exits 2 (persona unreadable) and 3 (frontmatter never closes) with NO stderr message, yet step 5.7 tells the orchestrator to classify those as runner failures - the cause never reaches the log in a headless run | /Users/bob/.claude/skills/work/scripts/render_prompt.py:59-66 | Phase 0 | BLAKE |
| [1/4] | 🟡 | `--set-cmd` runs arbitrary strings via `subprocess.run(shell=True)`; the only injection guard is skill prose telling the model to shlex.quote task-supplied Contract paths | /Users/bob/.claude/skills/work/scripts/render_prompt.py:82-90 | Phase 0 | BLAKE |
| [1/4] | 🟡 | A successful `--set-cmd` with empty stdout silently fills a required placeholder with empty text, contradicting the design contract | .claude/skills/work/scripts/render_prompt.py:106 | 1 | BOB |
| [1/4] | 🟡 | Completed tasks are counted as transition calls rather than distinct task IDs, so duplicate completion updates deflate the ratio | .claude/skills/work/scripts/check_build_overhead.py:88 | 7 | BOB |
| [1/4] | 🟡 | The new-module pre-check skips when any Contract path is absent, even if that path is not imported by the tests, weakening fail-first verification | .claude/skills/work/SKILL.md:313 | 6 | BOB |
| [1/4] | 🟡 | The only recorded-baseline acceptance test is skipped whenever a machine-local transcript is absent, masking the integration requirement | .claude/skills/work/scripts/test_check_build_overhead.py:433 | 7 | BOB |
| [1/4] | 🟡 | The 74-line `main` mixes assignment resolution, subprocess handling, substitution, and output; extract assignment resolution into a focused helper | .claude/skills/work/scripts/render_prompt.py:56 | 1 | BOB |
| [1/4] | 🟡 | The 66-line `main` mixes transcript parsing, metric classification, and reporting; extract a streaming counter function | .claude/skills/work/scripts/check_build_overhead.py:39 | 7 | BOB |
| [1/4] | 🟡 | Missing stderr message when persona file fails to load (OSError just returns exit code 2) | .claude/skills/work/scripts/render_prompt.py | 1 | CARL |
| [1/4] | 🟡 | Arbitrary command execution via shell=True in --set-cmd poses command injection risk if inputs are untrusted | .claude/skills/work/scripts/render_prompt.py | 1 | CARL |
| [1/4] | 🟡 | Simplification: render_prompt.py:26. Current: `assignments = getattr(namespace, "assignments", None); if assignments is None: ...`. Simpler: `if not hasattr(namespace, "assignments"): namespace.assignments = []` | .claude/skills/work/scripts/render_prompt.py | 1 | CARL |
| [1/4] | 🟡 | Simplification: render_prompt.py:65. Current: 30-line `for kind, raw in ...` loop inside `main`. Simpler: Extract to `_resolve_assignments()` to bring `main` under 50 lines | .claude/skills/work/scripts/render_prompt.py | 1 | CARL |
| [1/4] | 🟡 | Simplification: check_build_overhead.py:55. Current: 34-line `with handle as f:` loop inside `main`. Simpler: Extract to `_count_metrics()` to bring `main` under 50 lines | .claude/skills/work/scripts/check_build_overhead.py | 7 | CARL |
| [1/4] | ⚪ | A --set/--set-file/--set-cmd argument missing its "=" silently yields an empty value (partition returns val=""), producing a prompt with an invisibly empty section — worse than the literal {SLOT} the script exists to prevent | /Users/bob/.claude/skills/work/scripts/render_prompt.py:561 | 1 | ALICE |
| [1/4] | ⚪ | The skill's own reference index still lists only references/test-author-prompt.md; the new tess-prompt.md (now the single source of truth) is absent from it | /Users/bob/.claude/skills/work/SKILL.md:759 | 3 | ALICE |
| [1/4] | ⚪ | check_build_overhead catches only FileNotFoundError/PermissionError around transcript_path.open(); passing a directory raises IsADirectoryError and escapes as a traceback instead of the documented one-line error | /Users/bob/.claude/skills/work/scripts/check_build_overhead.py:420-427 | 7 | ALICE |
| [1/4] | ⚪ | Red-check resolution keys entirely off the task's `Contract` section with no fallback when a legacy task has none; the PRD's stated input is "the test file's import target" | /Users/bob/.claude/skills/work/SKILL.md:311-315 | Phase 1 | BLAKE |
| [1/4] | ⚪ | `set-contract-card` is positional-only; the PRD Feature section specifies `set-contract-card --file <path>`, so a caller following that text passes `--file` as the path and fails | /Users/bob/.claude/skills/run-autopilot/cli/statectl.py:304-310 | general | BLAKE |
| [1/4] | ⚪ | do_set_contract_card applies `text.rstrip("\n")`, so a card file's trailing newline does not round-trip; spec says the field is "the file's contents" | /Users/bob/.claude/skills/run-autopilot/cli/statectl.py:224-227 | general | BLAKE |
| [1/4] | ⚪ | check_build_overhead.py crashes with AttributeError when `message.content` is a string or holds non-dict blocks (reproduced: traceback, exit 1); it also swallows unparseable lines silently | /Users/bob/.claude/skills/work/scripts/check_build_overhead.py:71-74 | Phase 2 | BLAKE |
| [1/4] | ⚪ | `render_prompt.py --set NAME` with no `=` silently assigns an empty value instead of erroring | /Users/bob/.claude/skills/work/scripts/render_prompt.py:70 | Phase 0 | BLAKE |
| [1/4] | ⚪ | ivan.md registers a native agent type carrying `tools: Read, Edit, Write, Bash` in the shared reviewer registry dir; the roster and tool-set tables were not extended, so it is governed only by the loose foreign-file contract | /Users/bob/.claude/agents/ivan.md | Phase 0 | BLAKE |
| [1/4] | ⚪ | No test binds work/SKILL.md's dispatch steps to render_prompt.py; a prose revert reintroduces inline prompt authoring with every suite still green | N/A | Phase 1 | BLAKE |
| [1/4] | ⚪ | A directory supplied as the transcript raises uncaught `IsADirectoryError` instead of the documented unreadable-input exit code 1 | .claude/skills/work/scripts/check_build_overhead.py:44 | 7 | BOB |
| [1/4] | ⚪ | Cannot statically verify: reviewed test suites and golden-contract checks pass | N/A | general | BOB |
| [1/4] | ⚪ | Cannot statically verify: next-batch overhead and median wall-clock success metrics are achieved | N/A | general | BOB |
| [1/4] | ⚪ | IsADirectoryError is uncaught when opening transcript_path | .claude/skills/work/scripts/check_build_overhead.py | 7 | CARL |
| [1/4] | ⚪ | Residual stale inline reference to code-quality-principles.md in step 5.7 retry dispatch | .claude/skills/work/SKILL.md | 4 | CARL |


## Alice

Consensus lens, implementation-aware. Reproduced three of her High findings by
running the documented commands verbatim.

[ALICE] 🟠 Step 5.7's Pat render passes a skill-relative --set-file path; reproduced from cwd=/Users/bob/.claude: "render_prompt: --set-file path not found for {SIMPLIFICATION_MANDATE}: references/simplification-mandate.md", exit 4 — every per-task review render fails. Needs ~/.claude/skills/work/references/simplification-mandate.md | File: /Users/bob/.claude/skills/work/SKILL.md:669 | Task: 4
[ALICE] 🟠 The new qwen prose omits statectl's mandatory <state.json> positional; reproduced: `statectl.py set qwen_preflight '{...}'` → "unsupported verb: 'qwen_preflight'", exit 1, and `statectl del qwen_preflight` hits the len(argv)<3 usage exit. Every other statectl call in this file carries <state.json> | File: /Users/bob/.claude/skills/work/SKILL.md:406,409 | Task: 5
[ALICE] 🟠 Steps 5.5 and 7 tell the orchestrator to re-render ivan.md with only RETRY_INSTRUCTION and FAILING_TESTS, and give no --out; ivan.md also carries {ARCHITECTURE_CONTEXT} and {FILE_PATHS}, so the documented call exits 1 ("missing placeholder: {ARCHITECTURE_CONTEXT}", reproduced) | File: /Users/bob/.claude/skills/work/SKILL.md:480,746 | Task: 4
[ALICE] 🟠 Task prose is interpolated raw into double-quoted bash words (--set TASK_SUBJECT/TASK_DESCRIPTION/TASK_ACCEPTANCE_CRITERIA/FILE_PATHS); task text in this repo routinely contains backticks and $( ), which bash executes and strips — silent prompt corruption plus arbitrary execution. The quoting instruction covers only paths inside --set-cmd. This is the same quoting failure the PRD's contract-card metric exists to eliminate | File: /Users/bob/.claude/skills/work/SKILL.md:231,233,665-667 | Task: 4
[ALICE] 🟠 PRD Success Metric "work/SKILL.md body lands at or under 500 lines" is unmet: the file is 772 lines and this diff grew it (+65/-56). No task in the plan targets the slimming the PRD called binding | File: /Users/bob/.claude/skills/work/SKILL.md | Task: general
[ALICE] 🟠 Task 7's acceptance criterion is not met: against the named baseline transcript the script reports 2.80 statectl calls per completed task, not ">= 7". Independently confirmed (14 statectl Bash calls, 5 distinct completed TaskUpdate ids, no duplicates). The golden test was rewritten to assert 2.80, so the PRD's Success Metric baseline ("7.5 per task", target "at most 2") needs operator re-baselining before it can gate anything | File: /Users/bob/.claude/skills/work/scripts/test_check_build_overhead.py:1087 | Task: 7
[ALICE] 🟡 references/subagent-dispatch.md § Subagent Dispatch Budget still mandates the replaced procedure — assemble the prompt string, write it to /tmp, measure with `wc -c`, prepend the abort line — while all three rewritten sites point readers at that same file for the trim rule | File: /Users/bob/.claude/skills/work/references/subagent-dispatch.md:15-53 | Task: 4
[ALICE] 🟡 Tess loses the mandatory 100K abort-instruction line: tess-prompt.md does not contain it (ivan.md does), and step 2.7 now states "nothing further needs adding to the prompt by hand", dropping subagent-dispatch.md step 4 for an Agent-tool dispatch | File: /Users/bob/.claude/skills/work/references/tess-prompt.md | Task: 3
[ALICE] 🟡 The reference the new probe prose points at still contradicts it: qwen-integration.md:26 "The preflight runs once per task attempt", and codex-implementor.md:11 "Same placement as the qwen preflight, but scoped per batch, not per task". Neither was updated, so the cited authority instructs per-task probing | File: /Users/bob/.claude/skills/work/references/qwen-integration.md:26 | Task: 5
[ALICE] 🟡 The "zero inline prompt bodies" migration is incomplete and now self-contradictory: step 5.7's CRITICAL/HIGH retry still assembles Ivan's prompt inline "with the code-quality rules block from references/code-quality-principles.md", and that file's own header still claims steps 3, 5.5, 5.7 and 7 copy the snippet verbatim | File: /Users/bob/.claude/skills/work/SKILL.md:679 | Task: 4
[ALICE] 🟡 completed_tasks counts TaskUpdate calls rather than distinct task ids, so a task re-completed by step 7's regression path (re-open → in_progress → "Mark the task completed") or by a rework cycle double-counts and deflates the headline ratio — the exact metric the PRD gates on | File: /Users/bob/.claude/skills/work/scripts/check_build_overhead.py:463-465 | Task: 7
[ALICE] 🟡 render_prompt.py exits 2 (persona unreadable) and 3 (unterminated frontmatter) with nothing on stderr, unlike exits 1/4/5 which all print a named cause; an unattended Bash call then sees a bare non-zero code, and no SKILL step documents any exit-code handling for steps 2.7 or 3 | File: /Users/bob/.claude/skills/work/scripts/render_prompt.py:553,557 | Task: 1
[ALICE] 🟡 Both new main() functions exceed the 50-line rule (render_prompt.main 74 lines, check_build_overhead.main 66 lines per the mechanical-facts block); extracting the --set*/assignment resolution loop and the per-block tool-use classifier are behavior-preserving splits | File: /Users/bob/.claude/skills/work/scripts/render_prompt.py:56 | Task: 1
[ALICE] 🟡 The new red_check value "n/a:new_module" is undocumented: attempt-logging.md still specifies `"red_check": "skipped:<cause>" | null` as the entry schema, and it is the authority every attempt-log consumer reads | File: /Users/bob/.claude/skills/work/references/attempt-logging.md:25,56 | Task: 6
[ALICE] 🟡 The four prose-only tasks (steps 2.7/3/5.5/5.7/7 rewrite, qwen batch-scope, red-check skip) ship with no binding test, though the design's own test-strategy names three suites for them and the repo has prose-assertion precedent (test_fablectl.py asserts on work/SKILL.md, test_work_routing.py models step-3 routing) | File: N/A | Task: general
[ALICE] ⚪ A --set/--set-file/--set-cmd argument missing its "=" silently yields an empty value (partition returns val=""), producing a prompt with an invisibly empty section — worse than the literal {SLOT} the script exists to prevent | File: /Users/bob/.claude/skills/work/scripts/render_prompt.py:561 | Task: 1
[ALICE] ⚪ Step 5.5's retry sentence names both --set-cmd FAILING_TESTS="cat ..." and --set-file FAILING_TESTS=<scratch file> for the same key, leaving the orchestrator to guess which flag to emit | File: /Users/bob/.claude/skills/work/SKILL.md:480 | Task: 4
[ALICE] ⚪ The skill's own reference index still lists only references/test-author-prompt.md; the new tess-prompt.md (now the single source of truth) is absent from it | File: /Users/bob/.claude/skills/work/SKILL.md:759 | Task: 3
[ALICE] ⚪ check_build_overhead catches only FileNotFoundError/PermissionError around transcript_path.open(); passing a directory raises IsADirectoryError and escapes as a traceback instead of the documented one-line error | File: /Users/bob/.claude/skills/work/scripts/check_build_overhead.py:420-427 | Task: 7

R1: fail
R2: pass
R3: pass
R4: fail
R6: pass
R7: fail
R8: fail
R9: fail
R10: fail
R11: pass
R12: fail
R13: pass

Verification run read-only, no git writes: `test_render_prompt.py` + `test_check_build_overhead.py` 46 passed / 0 skipped; `/Users/bob/.claude/skills/work/scripts/` + `test_fablectl.py` 275 passed; `run-autopilot/cli/` 534 passed + 117 subtests; `test_agent_registry.py` 109 passed; `test_golden_contracts.py` clean. The three High prose defects were reproduced by running the documented commands verbatim.


## Blake

Blind lens — prompt carried the PRD and the blind rubric only, no diff, no file
list, no implementation summary. He located the code himself.

[BLAKE] 🔴 Success metric "work/SKILL.md body at or under 500 lines" not met - file GREW from 737 to 772 lines (86KB) across this PRD's commits; no trimming commit exists | File: /Users/bob/.claude/skills/work/SKILL.md | Task: general
[BLAKE] 🔴 Phase 2 acceptance not met: script reports 2.80 statectl calls per task against the named baseline transcript, not the required ">= 7"; the test asserts 2.80 and documents the deviation instead of satisfying the criterion | File: /Users/bob/.claude/skills/work/scripts/test_check_build_overhead.py:437-457 | Task: Phase 2
[BLAKE] 🟠 subagent-dispatch.md (the authoritative Budget procedure, "read it before your first Agent dispatch") still mandates assembling the prompt inline, writing it to /tmp and measuring with `wc -c`, and prepending the abort line - never updated, contradicts every new render call site | File: /Users/bob/.claude/skills/work/references/subagent-dispatch.md:15-53 | Task: Phase 1
[BLAKE] 🟠 qwen-integration.md still states "The preflight runs once per task attempt" - the reference SKILL.md points at for the probe now contradicts the batch-scoped cache | File: /Users/bob/.claude/skills/work/references/qwen-integration.md:26 | Task: Phase 1
[BLAKE] 🟠 tess-prompt.md omits the mandatory abort-instruction line while step 2.7 asserts "nothing further needs adding to the prompt by hand" - every Tess dispatch silently loses the 100K context-overrun guard SKILL.md line 75 requires | File: /Users/bob/.claude/skills/work/references/tess-prompt.md | Task: Phase 1
[BLAKE] 🟠 "Zero inline prompt bodies" not met: step 5.7's review-fix Ivan re-dispatch still orders inline assembly (code-quality block + verbatim instruction line), and step 2.8/2.85 Tess retries still hand-author from an un-renderable `{task.description}` template | File: /Users/bob/.claude/skills/work/SKILL.md:679 | Task: Phase 1
[BLAKE] 🟠 code-quality-principles.md still declares "/work steps 3, 5.5, 5.7, and 7 copy the Prompt Snippet verbatim into every Ivan dispatch" - now false for 3/5.5/7; an orchestrator obeying it double-inlines the block ivan.md already bakes in | File: /Users/bob/.claude/skills/work/references/code-quality-principles.md:7-11 | Task: Phase 1
[BLAKE] 🟡 Spec'd re-probe trigger narrowed: PRD says re-probe "after any qwen dispatch that fails its step-5.5 gate or times out"; implementation explicitly excludes step-5.5 gate failures | File: /Users/bob/.claude/skills/work/SKILL.md:409 | Task: Phase 1
[BLAKE] 🟡 The documented re-probe recovery `statectl del qwen_preflight` exits 1 when the field is already absent (do_del raises UsageError on KeyError) - a second infra failure in one batch errors in an unattended loop | File: /Users/bob/.claude/skills/run-autopilot/cli/statectl.py:171-177 | Task: Phase 1
[BLAKE] 🟡 Abort/escalate-away path still writes `statectl append tasks[i].attempts '<entry-json>'` - inline JSON on the shell (the exact quoting hazard this PRD removed) and an array-INDEX path the PRD itself says stops matching id once rework appends `[D{cycle}]` follow-ups; wrong-task append risk | File: /Users/bob/.claude/skills/work/references/attempt-logging.md:75-79 | Task: general
[BLAKE] 🟡 New `red_check: "n/a:new_module"` value is absent from the attempt entry schema, which still documents only `"skipped:<cause>" | null` | File: /Users/bob/.claude/skills/work/references/attempt-logging.md:25,56 | Task: Phase 1
[BLAKE] 🟡 "At most 2 statectl invocations per completed task" is not structurally guaranteed: step 5.6 still directs a separate `self_deslop` write on every task (including the skip path), plus escalation's `tasks[i].model` mirror and the qwen breaker counter writes | File: /Users/bob/.claude/skills/work/SKILL.md:634-642 | Task: general
[BLAKE] 🟡 Step 5.6 writes `tasks[i].attempts[-1].self_deslop` but the attempt entry is only appended at step 6 by `task-done`; on a first attempt `attempts` is empty so the indexed write fails with "json-path index out of range: [-1]" - the prose even admits the entry is "written by step 6" | File: /Users/bob/.claude/skills/work/SKILL.md:634 | Task: general
[BLAKE] 🟡 render_prompt.py exits 2 (persona unreadable) and 3 (frontmatter never closes) with NO stderr message, yet step 5.7 tells the orchestrator to classify those as runner failures - the cause never reaches the log in a headless run | File: /Users/bob/.claude/skills/work/scripts/render_prompt.py:59-66 | Task: Phase 0
[BLAKE] 🟡 `--set-cmd` runs arbitrary strings via `subprocess.run(shell=True)`; the only injection guard is skill prose telling the model to shlex.quote task-supplied Contract paths | File: /Users/bob/.claude/skills/work/scripts/render_prompt.py:82-90 | Task: Phase 0
[BLAKE] ⚪ Red-check resolution keys entirely off the task's `Contract` section with no fallback when a legacy task has none; the PRD's stated input is "the test file's import target" | File: /Users/bob/.claude/skills/work/SKILL.md:311-315 | Task: Phase 1
[BLAKE] ⚪ `set-contract-card` is positional-only; the PRD Feature section specifies `set-contract-card --file <path>`, so a caller following that text passes `--file` as the path and fails | File: /Users/bob/.claude/skills/run-autopilot/cli/statectl.py:304-310 | Task: general
[BLAKE] ⚪ do_set_contract_card applies `text.rstrip("\n")`, so a card file's trailing newline does not round-trip; spec says the field is "the file's contents" | File: /Users/bob/.claude/skills/run-autopilot/cli/statectl.py:224-227 | Task: general
[BLAKE] ⚪ check_build_overhead.py crashes with AttributeError when `message.content` is a string or holds non-dict blocks (reproduced: traceback, exit 1); it also swallows unparseable lines silently | File: /Users/bob/.claude/skills/work/scripts/check_build_overhead.py:71-74 | Task: Phase 2
[BLAKE] ⚪ `render_prompt.py --set NAME` with no `=` silently assigns an empty value instead of erroring | File: /Users/bob/.claude/skills/work/scripts/render_prompt.py:70 | Task: Phase 0
[BLAKE] ⚪ ivan.md registers a native agent type carrying `tools: Read, Edit, Write, Bash` in the shared reviewer registry dir; the roster and tool-set tables were not extended, so it is governed only by the loose foreign-file contract | File: /Users/bob/.claude/agents/ivan.md | Task: Phase 0
[BLAKE] ⚪ No test binds work/SKILL.md's dispatch steps to render_prompt.py; a prose revert reintroduces inline prompt authoring with every suite still green | File: N/A | Task: Phase 1

B1: fail
B2: pass
B3: fail
B4: fail
B5: pass
B6: pass
B7: pass
B8: pass
B9: pass
B10: pass
B11: pass
B12: fail
B13: pass
B14: fail
B15: fail
B16: fail
B17: pass
B18: pass
B19: pass


## Bob

Doubt + de-slop lens (codex, static-only sandbox). His `D{n}` rubric verdicts
and his FIX/VERIFY/KNOWN buckets are preserved verbatim below.

[BOB] 🔴 Dynamic task/PRD text is interpolated into double-quoted Bash arguments, allowing quotes, backticks, or `$()` to break parsing or execute commands | File: .claude/skills/work/SKILL.md:231 | Task: 4
[BOB] 🟠 Pat rendering uses a repo-relative simplification-mandate path, so ordinary project-root execution cannot find the skill-owned file | File: .claude/skills/work/SKILL.md:669 | Task: 4
[BOB] 🟠 The zero-inline-prompt requirement remains unmet: Tess quality retries and review-triggered Ivan repairs still assemble instructions inline | File: .claude/skills/work/SKILL.md:258 | Task: 4
[BOB] 🟠 The binding 500-line limit is unmet; the changed work skill extends beyond line 746 | File: .claude/skills/work/SKILL.md:746 | Task: 4
[BOB] 🟠 The golden acceptance test deliberately asserts 2.80 although the PRD requires at least 7 statectl calls per task | File: .claude/skills/work/scripts/test_check_build_overhead.py:447 | Task: 7
[BOB] 🟡 A successful `--set-cmd` with empty stdout silently fills a required placeholder with empty text, contradicting the design contract | File: .claude/skills/work/scripts/render_prompt.py:106 | Task: 1
[BOB] 🟡 Completed tasks are counted as transition calls rather than distinct task IDs, so duplicate completion updates deflate the ratio | File: .claude/skills/work/scripts/check_build_overhead.py:88 | Task: 7
[BOB] ⚪ A directory supplied as the transcript raises uncaught `IsADirectoryError` instead of the documented unreadable-input exit code 1 | File: .claude/skills/work/scripts/check_build_overhead.py:44 | Task: 7
[BOB] 🟡 The new-module pre-check skips when any Contract path is absent, even if that path is not imported by the tests, weakening fail-first verification | File: .claude/skills/work/SKILL.md:313 | Task: 6
[BOB] 🟠 No tests bind the new qwen cache/invalidation flow, red-check branching, or Pat/Tess/Ivan render integrations required by the design test strategy | File: .claude/skills/work/SKILL.md:310 | Task: general
[BOB] 🟡 The only recorded-baseline acceptance test is skipped whenever a machine-local transcript is absent, masking the integration requirement | File: .claude/skills/work/scripts/test_check_build_overhead.py:433 | Task: 7
[BOB] 🟡 The 74-line `main` mixes assignment resolution, subprocess handling, substitution, and output; extract assignment resolution into a focused helper | File: .claude/skills/work/scripts/render_prompt.py:56 | Task: 1
[BOB] 🟡 The 66-line `main` mixes transcript parsing, metric classification, and reporting; extract a streaming counter function | File: .claude/skills/work/scripts/check_build_overhead.py:39 | Task: 7
[BOB] 🟡 Retry prose specifies both `--set-cmd` and `--set-file` for `FAILING_TESTS`; use only the prepared scratch file and `--set-file` | File: .claude/skills/work/SKILL.md:480 | Task: 4
[BOB] ⚪ Cannot statically verify: reviewed test suites and golden-contract checks pass | File: N/A | Task: general
[BOB] ⚪ Cannot statically verify: next-batch overhead and median wall-clock success metrics are achieved | File: N/A | Task: general
R1: fail
R2: fail
R3: fail
R4: fail
R6: pass
R7: fail
R8: fail
R9: fail
R10: fail
R11: pass
R12: fail
R13: pass
D1: pass
D2: pass
D3: pass
D4: pass
D5: pass
FIX:
- Dynamic task prose crosses a Bash boundary without safe quoting — .claude/skills/work/SKILL.md:231 — use `--set-file` for prose or `shlex.quote()` every complete dynamic argument
- Pat’s simplification mandate resolves relative to the target repository — .claude/skills/work/SKILL.md:669 — pass the resolved absolute skill-owned path
- Retry dispatches still author prompt content inline — .claude/skills/work/SKILL.md:258 — render Tess retries and review-triggered Ivan repairs from templates
- `work/SKILL.md` remains over 500 lines — .claude/skills/work/SKILL.md:746 — move detailed procedures into references while preserving every mandatory gate
- Empty successful command output is accepted — .claude/skills/work/scripts/render_prompt.py:106 — reject empty stdout with exit 4 and add a regression test
- Completion calls are not deduplicated by task ID — .claude/skills/work/scripts/check_build_overhead.py:88 — track completed IDs in a set and test duplicate updates
- Directory transcript errors escape — .claude/skills/work/scripts/check_build_overhead.py:44 — handle `IsADirectoryError`/`OSError` as unreadable input and test it
- New-module detection considers non-imported Contract paths — .claude/skills/work/SKILL.md:313 — skip only when an imported target is absent and add mixed-path coverage
- Workflow integration behaviors lack tests — .claude/skills/work/SKILL.md:310 — add the design-specified qwen, red-check, and persona-render integration tests
- Golden coverage is machine-local and skipped — .claude/skills/work/scripts/test_check_build_overhead.py:433 — ship a redacted deterministic fixture and remove the skip
- `render_prompt.main` exceeds 50 lines — .claude/skills/work/scripts/render_prompt.py:56 — extract assignment-source resolution
- `check_build_overhead.main` exceeds 50 lines — .claude/skills/work/scripts/check_build_overhead.py:39 — extract streaming metric collection
- Retry instructions redundantly name two value sources — .claude/skills/work/SKILL.md:480 — prepare one scratch file and pass only `--set-file`
VERIFY:
- Test status is runtime-only — run `pytest skills/work/scripts/test_render_prompt.py skills/work/scripts/test_check_build_overhead.py skills/run-autopilot/cli/test_records.py` and `python3 skills/run-autopilot/scripts/test_golden_contracts.py`, requiring zero failures
- Operational success metrics require a real subsequent batch — run `check_build_overhead.py` over each next-batch build transcript and verify TaskCreate turns ≤2, statectl/task ≤2, prompt Writes 0, qwen probe frequency within contract, and median wall-clock/task <21 minutes
KNOWN:
- The historical transcript produces 14 statectl calls over 5 distinct completed tasks, or 2.80, while the PRD says ≥7 — reconciling that stale baseline requires operator PRD re-baselining rather than changing the counter to manufacture the requested value

## Carl

Gemini via the copilot backend. No frontend surface in this diff, so he
reviewed as a generalist and concentrated on the two new Python scripts.

● Read review-context-00093-c1.md
  │ /tmp/review-context-00093-c1.md
  └ 191 lines read

● Read review-tasks-00093-c1.md
  │ /tmp/review-tasks-00093-c1.md
  └ 142 lines read

● Read review-diff-00093-c1.diff
  │ /tmp/review-diff-00093-c1.diff
  └ 1 line read

● Read review-diff-00093-c1.diff
  │ /tmp/review-diff-00093-c1.diff
  └ 1503 lines read

[BOB] 🟠 Subprocess TimeoutExpired logic in --set-cmd is entirely untested | File: .claude/skills/work/scripts/test_render_prompt.py | Task: 1
[BOB] 🟠 completed_tasks double-counts if TaskUpdate status=completed is emitted twice for the same task_id | File: .claude/skills/work/scripts/check_build_overhead.py | Task: 7
[BOB] 🟡 Missing stderr message when persona file fails to load (OSError just returns exit code 2) | File: .claude/skills/work/scripts/render_prompt.py | Task: 1
[BOB] 🟡 Arbitrary command execution via shell=True in --set-cmd poses command injection risk if inputs are untrusted | File: .claude/skills/work/scripts/render_prompt.py | Task: 1
[BOB] 🟡 Simplification: render_prompt.py:26. Current: `assignments = getattr(namespace, "assignments", None); if assignments is None: ...`. Simpler: `if not hasattr(namespace, "assignments"): namespace.assignments = []` | File: .claude/skills/work/scripts/render_prompt.py | Task: 1
[BOB] 🟡 Simplification: render_prompt.py:65. Current: 30-line `for kind, raw in ...` loop inside `main`. Simpler: Extract to `_resolve_assignments()` to bring `main` under 50 lines | File: .claude/skills/work/scripts/render_prompt.py | Task: 1
[BOB] 🟡 Simplification: render_prompt.py:98. Current: `if stdout.endswith("\n"): stdout = stdout[:-1]`. Simpler: `stdout = stdout.removesuffix("\n")` | File: .claude/skills/work/scripts/render_prompt.py | Task: 1
[BOB] 🟡 Simplification: check_build_overhead.py:55. Current: 34-line `with handle as f:` loop inside `main`. Simpler: Extract to `_count_metrics()` to bring `main` under 50 lines | File: .claude/skills/work/scripts/check_build_overhead.py | Task: 7
[BOB] ⚪ IsADirectoryError is uncaught when opening transcript_path | File: .claude/skills/work/scripts/check_build_overhead.py | Task: 7
[BOB] ⚪ Residual stale inline reference to code-quality-principles.md in step 5.7 retry dispatch | File: .claude/skills/work/SKILL.md | Task: 4

R1: fail
R2: pass
R3: pass
R4: pass
R6: pass
R7: pass
R8: fail
R9: fail
R10: fail
R11: pass
R12: fail
R13: pass



Changes    +0 -0
AI Credits 20.8 (1m 57s)
Tokens     ↑ 184.4k (94.5k cached) • ↓ 805 (10.0k reasoning)
Resume     copilot --resume=7365ba49-ec57-431b-83ec-28e972788f10


## Verification run by the orchestrator

Read-only, no git writes. Foreground, once for this cycle:

```
work/scripts (test_render_prompt.py + test_check_build_overhead.py)  46 passed
run-autopilot/cli/                                534 passed, 117 subtests
run-autopilot/scripts/                            691 passed, 31 skipped, 126 subtests
```

All 31 skips are `tracon/test_screens.py` acceptance tests that require
`textual`; they are pre-existing environment skips, unrelated to this PRD.

Independent check of the disputed Phase 2 acceptance number, run against the
PRD's own named baseline transcript:

```
TaskCreate turns: 10
statectl calls: 14
statectl calls per completed task: 2.80
prompt-authoring Write calls: 2
completed tasks: 5
```

`TaskCreate turns: 10` matches the PRD exactly. The `2.80` figure does not match
the PRD's `>= 7`, and the reason is visible in the same output: the script
reports **5** completed tasks for that single session, whereas the PRD's "68
across 9 tasks = 7.5 per task" was measured across the whole 6-session batch.
The two numbers are measuring different scopes.

Verdict: 57 findings
Tests: 1271 passed, 0 failed, 31 skipped
