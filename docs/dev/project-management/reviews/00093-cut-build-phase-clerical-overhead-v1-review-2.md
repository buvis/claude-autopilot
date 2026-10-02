---
prd: dev/local/prds/wip/00093-cut-build-phase-clerical-overhead-v1.md
review: 2
date: 2026-08-15
head_sha: e39296e60249c49baa624ba5261622f812f34646
codex_thread_id: 01a005d3-23bf-7b70-9866-305e0021a41f
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00093-cut-build-phase-clerical-overhead-v1

Diff range: `a5af408158daa57846cb628271bab03900bb2406..e39296e60249c49baa624ba5261622f812f34646`

codex_rung_guard: not fired

## Review Summary

Reviewed: 17 completed tasks (7 original-plan + 10 `[D1]` rework)
PRDs checked: 00093-cut-build-phase-clerical-overhead-v1

**Incremental cycle.** The diff is scoped to the 18 rework commits since cycle
1's `head_sha`; cycle 1 reviewed the full implementation. Bob resumed his
cycle-1 codex thread (`--resume-thread`), so his verification runs against his
own prior critique rather than from zero.

### Agent Status

- Alice (Claude, consensus lens): OK Available
- Blake (Claude, blind/PRD-only lens): OK Available
- Bob (codex, doubt + de-slop lens): OK Available
- Carl (Gemini via copilot, UI/generalist lens): OK Available

Consensus engine: `legacy` (single Alice subagent). Doubt reviewer: `codex`;
the codex doubt-roster guard did not fire (all 17 recorded task attempts were
implemented by `claude`, none by codex), so Eve was not added as a fifth lens.

### Degradations, recorded

- **No engram context pack this cycle**, same cause as cycle 1: `engram pack`
  resolves the repo root via `git rev-parse --show-toplevel`, which does not
  work in this `~/.buvis` bare-repo home, and `gather-context.sh` does not run
  here either. Every prompt taking the pack placeholders received the
  documented sentinel `(no pack available this cycle)`. Reviewer inputs were
  built by hand and staged under `/tmp`.

### Foreign working-tree state at review time

33 files carry uncommitted modifications unrelated to this PRD (`settings.json`,
`warden.yaml`, `.codex/config.toml`, `audit-qwen/`, `tracon/`, `cli/loop.py`,
`cli/records.py`, `consolidate_findings.py` and others). They are the operator's
own in-flight work, were left untouched, and are **not** findings against this
PRD. One overlaps a reviewed file: `work/scripts/work_routing.py` carries a
black-reflow-only change on top of HEAD (Alice verified it functionally
identical). The review scope is the committed range in the header.

## Consolidated Findings

38 findings: 0 Critical, 8 High, 20 Medium, 10 Low.

**Consensus counts understate agreement**, same mechanism as cycle 1:
`consolidate_findings.py` merges on file plus a Jaccard threshold, and Bob
reports repo-relative paths with line numbers (`.claude/skills/...:15`) while
Alice and Blake report absolute paths. So two pairs of rows below are one
defect each and carry higher real consensus than the table shows:

- the **tess-retry-prompt.md missing-test-files** defect appears twice (the
  `[2/4]` Medium row from Alice+Blake, and Bob's `[1/4]` High row) - real
  consensus 3/4, and the decision gate treats it at Bob's High severity;
- the **test_work_routing.py over 800 lines** defect appears twice (Alice
  `[1/4]`, Bob `[1/4]`) - real consensus 2/4.

Three Blake findings were auto-dismissed against the settled-decisions ledger
and are listed under the table; the dismissal is correct in all three cases.

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [2/4] | 🟠 | set-contract-card strips trailing newlines, so the PRD edge case "a contract card containing ', \", $( and a newline round-trips through set-contract-card unchanged" does not hold byte-for-byte (verified: file ends "line2\n\n", stored value ends "line2"). | /Users/bob/.claude/skills/run-autopilot/cli/statectl.py | general | BLAKE, BOB |
| [2/4] | 🟡 | New tess-retry-prompt.md carries "Read only the files listed above. If a file or symbol you need is not listed, stop and report it as a blocker" but the template lists no files at all (only QUALITY_FEEDBACK / TASK_DESCRIPTION / TASK_ACCEPTANCE_CRITERIA). A literal-minded Tess retry is told to block on the very test files it must edit; the guard was not in the retry prompt it replaced | /Users/bob/.claude/skills/work/references/tess-retry-prompt.md | 12 | ALICE, BLAKE |
| [2/4] | ⚪ | Shipped test file carries stale TDD comments asserting the code under test is absent: "needs_qwen_probe(state, batch_id) -> bool does not exist yet - every test below is expected to fail (AttributeError)" and the same for red_check_disposition. | /Users/bob/.claude/skills/work/scripts/test_work_routing.py | general | BLAKE, BOB |
| [1/4] | 🟠 | subagent-dispatch.md step 4 now says the 100K abort line is "baked into the persona files, so there is nothing to prepend" and names only ivan.md + tess-prompt.md — but Devon (step 2.85) is an Agent-tool dispatch assembled inline from adversarial-test-prompt.md, which carries no abort line (rg: only ivan.md, tess-prompt.md, tess-retry-prompt.md have it). The guard is silently dropped for that lane, and SKILL.md:75 still mandates "with the abort-instruction line prepended". Same regression class as the cycle-1 Tess finding, one file over | /Users/bob/.claude/skills/work/references/subagent-dispatch.md | 10 | ALICE |
| [1/4] | 🟠 | Success metric "zero inline prompt bodies for the implementor dispatch" not met on the gemini and qwen implementor lanes: both still carry a hand-written "TDD Implementation Mode (Ivan)" template with {lowercase} placeholders render_prompt.py cannot fill, and it omits the abort line, code-quality rules, dispatch prologue and ASSUMPTIONS/FILES_TOUCHED footers that SKILL.md mandates for every Ivan dispatch "regardless of mechanism". | /Users/bob/.claude/skills/work/references/qwen-integration.md | general | BLAKE |
| [1/4] | 🟠 | Same inline-prompt hole on the gemini lane; and the codex dispatch checklist names "-f <prompt file>" without saying it is rendered from ivan.md, leaving the codex implementor prompt hand-assembled. | /Users/bob/.claude/skills/work/references/gemini-integration.md | general | BLAKE |
| [1/4] | 🟠 | render_prompt.py --set-cmd runs a model-composed string through subprocess.run(shell=True); the only defence against task-supplied paths reaching that nested shell is prose in SKILL.md. shlex.split satisfies the spec ("a command whose stdout fills it") without a shell, and shell=True also hides command execution behind a `python3 ...` argv where the Bash gate cannot analyse it. | /Users/bob/.claude/skills/work/scripts/render_prompt.py | general | BLAKE |
| [1/4] | 🟠 | Scope creep: statectl gained a FOURTH verb, `append-attempt`, during this PRD, against the PRD's explicit bound ("keep the verbs deliberately narrow - two transitions and one field setter") and against its own instruction that the abort/escalate paths "keep the generic append". | /Users/bob/.claude/skills/run-autopilot/cli/statectl.py | general | BLAKE |
| [1/4] | 🟠 | The Tess retry template asks a fresh dispatch to preserve and modify existing tests but supplies neither those test files nor their contents | .claude/skills/work/references/tess-retry-prompt.md:15 | 12 | BOB |
| [1/4] | 🟠 | The qwen invalidation test deletes the cache itself, so it does not verify that either watchdog or infra-failure signal actually triggers deletion | .claude/skills/work/scripts/test_work_routing.py:885 | 17 | BOB |
| [1/4] | 🟡 | test_dispatch_prose.py does not bind what its docstring claims: I reverted step 3's Ivan render block to "assemble inline" on a copy of the skill and all 5 tests still passed, because the needle "render_prompt.py ~/.claude/agents/ivan.md" also occurs in step 5.5's retry block (2 occurrences). Assert per-section (or occurrence counts), not whole-file substring presence | /Users/bob/.claude/skills/work/scripts/test_dispatch_prose.py | 17 | ALICE |
| [1/4] | 🟡 | self-deslop-prompt.md still instructs the step-5.6 caller to write `state.tasks[i].attempts[-1].self_deslop` — the exact indexed write task 15 removed from SKILL.md step 5.6 because it exits 1 ("json-path index out of range: [-1]") on every first attempt. Two live instructions now contradict each other | /Users/bob/.claude/skills/work/references/self-deslop-prompt.md | 15 | ALICE |
| [1/4] | 🟡 | test_work_routing.py grew 784 -> 971 lines in this cycle, past the 800-line max in rules/coding-style.md, while the repo already splits this suite (test_work_routing_ladder_fence.py, test_work_routing_attempt_outcome.py). The two new suites (needs_qwen_probe, red_check_disposition) are separate concerns and belong in their own files | /Users/bob/.claude/skills/work/scripts/test_work_routing.py | 17 | ALICE |
| [1/4] | 🟡 | No test renders a real persona, so nothing binds the persona placeholders to the flag sets SKILL.md passes: adding a placeholder to ivan.md or dropping a flag from a render call is caught only at dispatch time with exit 1. The design's own test strategy named this ("Ivan/Tess/Pat rendering ... rendered with representative values"); task 17 shipped substring needles instead. tess-retry-prompt.md and its step-2.8 render site ship with no test at all | /Users/bob/.claude/skills/work/scripts/test_dispatch_prose.py | 17 | ALICE |
| [1/4] | 🟡 | attempt-logging.md contradicts itself four lines apart: the table mandates `append-attempt <task-id>`, then the prose says the abort paths "keep the generic `append` form" and "`i` is this task's index in `state.tasks`" - the index path the PRD set out to eliminate. | /Users/bob/.claude/skills/work/references/attempt-logging.md | general | BLAKE |
| [1/4] | 🟡 | Step 2.95 says to "write red_check = \"n/a:new_module\" to the attempt entry" before step 3, but on a first attempt tasks[i].attempts is empty - the exact `json-path index out of range: [-1]` failure step 5.6 documents and works around with a carry-into-step-6 instruction. Step 2.95 has no such instruction, and the extra write would also breach the "<= 2 statectl per task" metric. | /Users/bob/.claude/skills/work/SKILL.md | general | BLAKE |
| [1/4] | 🟡 | check_build_overhead.py dies with an uncaught UnicodeDecodeError traceback on a transcript containing invalid UTF-8 (reproduced), and opens with the locale encoding rather than encoding="utf-8" - despite explicitly handling missing-file, directory, permission and malformed-JSON cases. Transcripts are machine-written and routinely truncated by headless kills. | /Users/bob/.claude/skills/work/scripts/check_build_overhead.py | general | BLAKE |
| [1/4] | 🟡 | No test renders the real personas. Phase 0's exit criterion ("rendering each of Pat, Tess and Ivan produces prompts whose fixed sections match today's") and the Test-Strategy happy path ("reviewer template with a --set-cmd diff produces a prompt containing both the diff and the verbatim simplification mandate") have no automated guard; a placeholder added to a persona fails only at live dispatch, mid-task, with exit 1. | /Users/bob/.claude/skills/work/scripts/test_render_prompt.py | general | BLAKE |
| [1/4] | 🟡 | ivan.md is invisible to the registry's own placeholder guard: test_placeholders_are_declared_in_the_conventions iterates ROSTER, which excludes ivan, so the acceptance criterion "every placeholder it uses appears in the registry table" holds by hand today with no regression test. | /Users/bob/.claude/skills/review-work-completion/scripts/test_agent_registry.py | general | BLAKE |
| [1/4] | 🟡 | The code-quality rules block is duplicated verbatim between code-quality-principles.md (declared source of truth, "edit the snippet here, then propagate it to ivan.md") and ivan.md, by hand, with no test binding them. Byte-identical today (I checked); nothing keeps it that way. | /Users/bob/.claude/agents/ivan.md | general | BLAKE |
| [1/4] | 🟡 | render_prompt.py's final write is an unguarded out_path.write_text with no try/except: a read-only directory, a full disk, or an --out naming a directory produces a Python traceback instead of one of the script's six named exit codes. | /Users/bob/.claude/skills/work/scripts/render_prompt.py | general | BLAKE |
| [1/4] | 🟡 | Dispatch integration tests only search for one command substring; incomplete retry commands or broken placeholder mappings can still pass | .claude/skills/work/scripts/test_dispatch_prose.py:22 | 17 | BOB |
| [1/4] | 🟡 | The actual named-baseline test remains conditional on a machine-local transcript; the synthetic fixture tests generic counting but cannot replace that integration check | .claude/skills/work/scripts/test_check_build_overhead.py:516 | 13 | BOB |
| [1/4] | 🟡 | `append-attempt` accepts any parseable JSON value, allowing a scalar or array to corrupt the object-valued attempt-log schema | .claude/skills/run-autopilot/cli/statectl.py:224 | 15 | BOB |
| [1/4] | 🟡 | The synthetic-baseline test is 64 lines; extract its transcript fixture construction so the test remains under the 50-line limit | .claude/skills/work/scripts/test_check_build_overhead.py:672 | 13 | BOB |
| [1/4] | 🟡 | Incremental prose additions pushed `work/SKILL.md` beyond the separate 800-line file limit; move the new render-value detail into its reference and retain a concise binding rule | .claude/skills/work/SKILL.md:801 | general | BOB |
| [1/4] | 🟡 | Adding qwen and red-check sections pushed `test_work_routing.py` beyond 800 lines; split the new independent sections into focused test modules | .claude/skills/work/scripts/test_work_routing.py:808 | 17 | BOB |
| [1/4] | 🟡 | `do_task_done` duplicates attempt appending logic; replace lines 216-219 with `do_append_attempt(data, task_id, attempt)` | run-autopilot/cli/statectl.py:216 | 15 | CARL |
| [1/4] | ⚪ | check_build_overhead.py's malformed-shape hardening stops one level short: a tool_use whose `input` is not an object still raises an uncaught AttributeError. Reproduced with {"type":"assistant","message":{"content":[{"type":"tool_use","name":"Bash","input":"ls -la"}]}} — traceback plus exit 1, off the documented 0/1/2 contract. Same for a non-dict `entry` or `message` | /Users/bob/.claude/skills/work/scripts/check_build_overhead.py | 13 | ALICE |
| [1/4] | ⚪ | SKILL.md step 3 tells the orchestrator to treat a "key not found" exit from `statectl del qwen_preflight` as success, but statectl never prints that: it prints `cannot delete 'qwen_preflight': 'qwen_preflight'` and exits 1 — the same exit as every other del failure (reproduced). Either the note names a signal that does not exist, or applying it makes all del failures read as success | /Users/bob/.claude/skills/work/SKILL.md | 15 | ALICE |
| [1/4] | ⚪ | work_routing.py's module docstring still says "Pure decision core: three functions over plain dicts" after this diff added needs_qwen_probe and red_check_disposition (five public functions now); red_check_disposition is also step-2.95 red-check logic living in a module scoped to "Implementor routing for /work step 3" | /Users/bob/.claude/skills/work/scripts/work_routing.py | 17 | ALICE |
| [1/4] | ⚪ | Step 5.5's retry block hardcodes `--set-file ARCHITECTURE_CONTEXT=<the same source step 3 used>`, but step 3 documents `--set-cmd ARCHITECTURE_CONTEXT="cat $(printf '%q ' ...)"` when context spans several files. On those tasks the retry command as written has no single path to pass | /Users/bob/.claude/skills/work/SKILL.md | 12 | ALICE |
| [1/4] | ⚪ | Residual inline test-writer prompt: step 2.85's "Feedback to Tess (when Devon succeeds)" block is still a hand-authored Tess dispatch body, so the PRD's "zero inline prompt bodies for the test-writer" metric holds only outside the opus/fable tier. Task 12 migrated 2.8 but left this sibling Tess re-dispatch | /Users/bob/.claude/skills/work/references/adversarial-test-prompt.md | 12 | ALICE |
| [1/4] | ⚪ | state-schema.md's contract_card row still documents the retired mechanism: "via statectl set, in the same write that advances phase/next_phase". | /Users/bob/.claude/skills/run-autopilot/references/state-schema.md | general | BLAKE |
| [1/4] | ⚪ | --set-cmd treats empty stdout as a hard exit-4 failure, an unspecified extra constraint that blocks a whole dispatch when a legitimately empty source fills a slot. | /Users/bob/.claude/skills/work/scripts/render_prompt.py | general | BLAKE |
| [1/4] | ⚪ | The PRD error case "a batch id absent from state.batch degrades to \"no-batch\" and re-probes rather than raising" exists only as jq-shaped prose; needs_qwen_probe takes the id as a caller-supplied parameter and no test binds the fallback. | /Users/bob/.claude/skills/work/scripts/work_routing.py | general | BLAKE |
| [1/4] | ⚪ | Cannot statically verify: reviewed Python and prose-contract test suites pass | N/A | general | BOB |
| [1/4] | ⚪ | Cannot statically verify: next-batch overhead and median build-time success metrics are achieved | N/A | general | BOB |

### Auto-dismissed (ledger)

- [BLAKE] 🔴 Success metric "work/SKILL.md body lands at or under 500 lines" missed by 63%: the file is 813 lines and GREW from 737 at the start of this PRD's work (PRD cites an 806-line audit baseline). The PRD calls this metric the mechanism that "makes the slimming binding rather than incidental". | File: /Users/bob/.claude/skills/work/SKILL.md — Real and confirmed (772 lines measured at HEAD), but owned by a different, already-queued PRD: 00119-shrink-work-skill-body-v1 in the backlog covers exactly this reduction and documents why it cannot be done as a side-task - test_fablectl.py contract-tests the live SKILL.md with ~25 exact-text assertions anchored on step-5.5 and step-2.85 prose, so relocating prose without retargeting anchors breaks the autopilot safety net. Attempting a 272-line refactor of the orchestrator's own procedure file inside an unattended rework cycle is the higher risk. Deferred to 00119, with a note that 00093 raised its starting point from 737 to 772.
- [BLAKE] 🔴 Phase 2 acceptance criterion unmet: run against the named baseline session the script reports "statectl calls per completed task: 2.80", not the required ">= 7"; the Phase 2 exit criterion "reproduces the documented baseline numbers" therefore fails. The test suite was written to assert 2.80 instead. | File: /Users/bob/.claude/skills/work/scripts/test_check_build_overhead.py — Spec defect in the PRD, not an implementation defect. The orchestrator re-ran the script against the PRD's own named baseline transcript and reproduced 2.80 with 5 completed tasks and 10 TaskCreate turns; the TaskCreate figure matches the PRD exactly, so the counting logic is honest. The >= 7 figure was measured batch-wide (68 statectl calls / 9 tasks across 6 sessions) while the acceptance criterion names one single session. Only the operator can re-baseline a Success Metric. Recorded in the batch deferred JSON.
- [BLAKE] 🟡 The PRD's re-probe trigger was narrowed away: PRD says re-probe "after any qwen dispatch that fails its step-5.5 gate or times out"; step 3 item 5 explicitly excludes step-5.5 gate failures. That is the PRD's own stated mitigation for "a cached qwen preflight masks a backend that died mid-batch". | File: /Users/bob/.claude/skills/work/SKILL.md — Deliberate, documented deviation approved at the design gate, not drift. The design doc's Data flow item 4 narrows the trigger to backend-health signals only, with the rationale stated inline: qwen is the weakest routing tier, so ordinary task-difficulty gate failures on a healthy backend are expected and already handled by the one-shot-to-Sonnet escalation, and treating each as a health signal would degrade the cache back toward probe-before-every-task - the exact overhead the feature removes. The PRD itself marked that mitigation "(guess)". Blake could not see this: his lens is PRD-only by design.


## Alice

Consensus lens, implementation-aware. Ran every documented render command
verbatim (Tess 2.7, Tess retry 2.8, Ivan 3, Ivan retry 5.5, Pat 5.7 - all exit
0), ran the documented `statectl set/del qwen_preflight` and `append-attempt`
against a scratch state, and **mutation-tested the new prose suite on a copy of
the skill**, which is what produced her strongest finding.

[ALICE] 🟠 subagent-dispatch.md step 4 now says the 100K abort line is "baked into the persona files, so there is nothing to prepend" and names only ivan.md + tess-prompt.md — but Devon (step 2.85) is an Agent-tool dispatch assembled inline from adversarial-test-prompt.md, which carries no abort line (rg: only ivan.md, tess-prompt.md, tess-retry-prompt.md have it). The guard is silently dropped for that lane, and SKILL.md:75 still mandates "with the abort-instruction line prepended". Same regression class as the cycle-1 Tess finding, one file over | File: /Users/bob/.claude/skills/work/references/subagent-dispatch.md | Task: 10
[ALICE] 🟡 test_dispatch_prose.py does not bind what its docstring claims: I reverted step 3's Ivan render block to "assemble inline" on a copy of the skill and all 5 tests still passed, because the needle "render_prompt.py ~/.claude/agents/ivan.md" also occurs in step 5.5's retry block (2 occurrences). Assert per-section (or occurrence counts), not whole-file substring presence | File: /Users/bob/.claude/skills/work/scripts/test_dispatch_prose.py | Task: 17
[ALICE] 🟡 self-deslop-prompt.md still instructs the step-5.6 caller to write `state.tasks[i].attempts[-1].self_deslop` — the exact indexed write task 15 removed from SKILL.md step 5.6 because it exits 1 ("json-path index out of range: [-1]") on every first attempt. Two live instructions now contradict each other | File: /Users/bob/.claude/skills/work/references/self-deslop-prompt.md | Task: 15
[ALICE] 🟡 New tess-retry-prompt.md carries "Read only the files listed above. If a file or symbol you need is not listed, stop and report it as a blocker" but the template lists no files at all (only QUALITY_FEEDBACK / TASK_DESCRIPTION / TASK_ACCEPTANCE_CRITERIA). A literal-minded Tess retry is told to block on the very test files it must edit; the guard was not in the retry prompt it replaced | File: /Users/bob/.claude/skills/work/references/tess-retry-prompt.md | Task: 12
[ALICE] 🟡 test_work_routing.py grew 784 -> 971 lines in this cycle, past the 800-line max in rules/coding-style.md, while the repo already splits this suite (test_work_routing_ladder_fence.py, test_work_routing_attempt_outcome.py). The two new suites (needs_qwen_probe, red_check_disposition) are separate concerns and belong in their own files | File: /Users/bob/.claude/skills/work/scripts/test_work_routing.py | Task: 17
[ALICE] 🟡 No test renders a real persona, so nothing binds the persona placeholders to the flag sets SKILL.md passes: adding a placeholder to ivan.md or dropping a flag from a render call is caught only at dispatch time with exit 1. The design's own test strategy named this ("Ivan/Tess/Pat rendering ... rendered with representative values"); task 17 shipped substring needles instead. tess-retry-prompt.md and its step-2.8 render site ship with no test at all | File: /Users/bob/.claude/skills/work/scripts/test_dispatch_prose.py | Task: 17
[ALICE] ⚪ check_build_overhead.py's malformed-shape hardening stops one level short: a tool_use whose `input` is not an object still raises an uncaught AttributeError. Reproduced with {"type":"assistant","message":{"content":[{"type":"tool_use","name":"Bash","input":"ls -la"}]}} — traceback plus exit 1, off the documented 0/1/2 contract. Same for a non-dict `entry` or `message` | File: /Users/bob/.claude/skills/work/scripts/check_build_overhead.py | Task: 13
[ALICE] ⚪ SKILL.md step 3 tells the orchestrator to treat a "key not found" exit from `statectl del qwen_preflight` as success, but statectl never prints that: it prints `cannot delete 'qwen_preflight': 'qwen_preflight'` and exits 1 — the same exit as every other del failure (reproduced). Either the note names a signal that does not exist, or applying it makes all del failures read as success | File: /Users/bob/.claude/skills/work/SKILL.md | Task: 15
[ALICE] ⚪ work_routing.py's module docstring still says "Pure decision core: three functions over plain dicts" after this diff added needs_qwen_probe and red_check_disposition (five public functions now); red_check_disposition is also step-2.95 red-check logic living in a module scoped to "Implementor routing for /work step 3" | File: /Users/bob/.claude/skills/work/scripts/work_routing.py | Task: 17
[ALICE] ⚪ Step 5.5's retry block hardcodes `--set-file ARCHITECTURE_CONTEXT=<the same source step 3 used>`, but step 3 documents `--set-cmd ARCHITECTURE_CONTEXT="cat $(printf '%q ' ...)"` when context spans several files. On those tasks the retry command as written has no single path to pass | File: /Users/bob/.claude/skills/work/SKILL.md | Task: 12
[ALICE] ⚪ Residual inline test-writer prompt: step 2.85's "Feedback to Tess (when Devon succeeds)" block is still a hand-authored Tess dispatch body, so the PRD's "zero inline prompt bodies for the test-writer" metric holds only outside the opus/fable tier. Task 12 migrated 2.8 but left this sibling Tess re-dispatch | File: /Users/bob/.claude/skills/work/references/adversarial-test-prompt.md | Task: 12

R1: fail
R2: fail
R3: pass
R4: fail
R6: pass
R7: pass
R8: pass
R9: fail
R10: pass
R11: pass
R12: pass
R13: fail


### Verified-resolved from cycle 1 (checked in code, not from task notes)

The bash-interpolation critical; the Pat skill-relative mandate path; the
missing `<state.json>` positional; the Ivan re-render placeholders and `--out`;
`qwen-integration.md` and `codex-implementor.md` batch-scope wording;
`code-quality-principles.md`'s "copy the Prompt Snippet" claim;
`completed_tasks` dedupe; `IsADirectoryError`; render_prompt exits 2/3/4/6
naming their cause; the `--set-cmd` timeout test via monkeypatched
`SET_CMD_TIMEOUT_SECONDS`; both `main()` under 50 lines with every helper <= 48;
the abort path's new `append-attempt` verb; `n/a:new_module` documented in
`attempt-logging.md`; the reference index.

The four deliberate deviations hold, with one qualification: the
`del`-stays-strict deviation leans on a caller-side note whose stated signal the
tool does not emit (her Low on SKILL.md step 3).

## Blake

Blind lens - his prompt carried the PRD and the blind rubric only: no diff, no
file list, no implementation summary, no review history, and **no ledger** (a
blind lens fed the review's own history is no longer blind). He located the code
himself and ran the suites. His re-raises of settled calls are absorbed
mechanically by `--ledger-dismiss BLAKE`, listed under the table above.

[BLAKE] 🔴 Success metric "work/SKILL.md body lands at or under 500 lines" missed by 63%: the file is 813 lines and GREW from 737 at the start of this PRD's work (PRD cites an 806-line audit baseline). The PRD calls this metric the mechanism that "makes the slimming binding rather than incidental". | File: /Users/bob/.claude/skills/work/SKILL.md | Task: general
[BLAKE] 🔴 Phase 2 acceptance criterion unmet: run against the named baseline session the script reports "statectl calls per completed task: 2.80", not the required ">= 7"; the Phase 2 exit criterion "reproduces the documented baseline numbers" therefore fails. The test suite was written to assert 2.80 instead. | File: /Users/bob/.claude/skills/work/scripts/test_check_build_overhead.py | Task: general
[BLAKE] 🟠 Success metric "zero inline prompt bodies for the implementor dispatch" not met on the gemini and qwen implementor lanes: both still carry a hand-written "TDD Implementation Mode (Ivan)" template with {lowercase} placeholders render_prompt.py cannot fill, and it omits the abort line, code-quality rules, dispatch prologue and ASSUMPTIONS/FILES_TOUCHED footers that SKILL.md mandates for every Ivan dispatch "regardless of mechanism". | File: /Users/bob/.claude/skills/work/references/qwen-integration.md | Task: general
[BLAKE] 🟠 Same inline-prompt hole on the gemini lane; and the codex dispatch checklist names "-f <prompt file>" without saying it is rendered from ivan.md, leaving the codex implementor prompt hand-assembled. | File: /Users/bob/.claude/skills/work/references/gemini-integration.md | Task: general
[BLAKE] 🟠 render_prompt.py --set-cmd runs a model-composed string through subprocess.run(shell=True); the only defence against task-supplied paths reaching that nested shell is prose in SKILL.md. shlex.split satisfies the spec ("a command whose stdout fills it") without a shell, and shell=True also hides command execution behind a `python3 ...` argv where the Bash gate cannot analyse it. | File: /Users/bob/.claude/skills/work/scripts/render_prompt.py | Task: general
[BLAKE] 🟠 Scope creep: statectl gained a FOURTH verb, `append-attempt`, during this PRD, against the PRD's explicit bound ("keep the verbs deliberately narrow - two transitions and one field setter") and against its own instruction that the abort/escalate paths "keep the generic append". | File: /Users/bob/.claude/skills/run-autopilot/cli/statectl.py | Task: general
[BLAKE] 🟡 attempt-logging.md contradicts itself four lines apart: the table mandates `append-attempt <task-id>`, then the prose says the abort paths "keep the generic `append` form" and "`i` is this task's index in `state.tasks`" - the index path the PRD set out to eliminate. | File: /Users/bob/.claude/skills/work/references/attempt-logging.md | Task: general
[BLAKE] 🟡 The PRD's re-probe trigger was narrowed away: PRD says re-probe "after any qwen dispatch that fails its step-5.5 gate or times out"; step 3 item 5 explicitly excludes step-5.5 gate failures. That is the PRD's own stated mitigation for "a cached qwen preflight masks a backend that died mid-batch". | File: /Users/bob/.claude/skills/work/SKILL.md | Task: general
[BLAKE] 🟡 Step 2.95 says to "write red_check = \"n/a:new_module\" to the attempt entry" before step 3, but on a first attempt tasks[i].attempts is empty - the exact `json-path index out of range: [-1]` failure step 5.6 documents and works around with a carry-into-step-6 instruction. Step 2.95 has no such instruction, and the extra write would also breach the "<= 2 statectl per task" metric. | File: /Users/bob/.claude/skills/work/SKILL.md | Task: general
[BLAKE] 🟡 check_build_overhead.py dies with an uncaught UnicodeDecodeError traceback on a transcript containing invalid UTF-8 (reproduced), and opens with the locale encoding rather than encoding="utf-8" - despite explicitly handling missing-file, directory, permission and malformed-JSON cases. Transcripts are machine-written and routinely truncated by headless kills. | File: /Users/bob/.claude/skills/work/scripts/check_build_overhead.py | Task: general
[BLAKE] 🟡 No test renders the real personas. Phase 0's exit criterion ("rendering each of Pat, Tess and Ivan produces prompts whose fixed sections match today's") and the Test-Strategy happy path ("reviewer template with a --set-cmd diff produces a prompt containing both the diff and the verbatim simplification mandate") have no automated guard; a placeholder added to a persona fails only at live dispatch, mid-task, with exit 1. | File: /Users/bob/.claude/skills/work/scripts/test_render_prompt.py | Task: general
[BLAKE] 🟡 ivan.md is invisible to the registry's own placeholder guard: test_placeholders_are_declared_in_the_conventions iterates ROSTER, which excludes ivan, so the acceptance criterion "every placeholder it uses appears in the registry table" holds by hand today with no regression test. | File: /Users/bob/.claude/skills/review-work-completion/scripts/test_agent_registry.py | Task: general
[BLAKE] 🟡 The code-quality rules block is duplicated verbatim between code-quality-principles.md (declared source of truth, "edit the snippet here, then propagate it to ivan.md") and ivan.md, by hand, with no test binding them. Byte-identical today (I checked); nothing keeps it that way. | File: /Users/bob/.claude/agents/ivan.md | Task: general
[BLAKE] 🟡 render_prompt.py's final write is an unguarded out_path.write_text with no try/except: a read-only directory, a full disk, or an --out naming a directory produces a Python traceback instead of one of the script's six named exit codes. | File: /Users/bob/.claude/skills/work/scripts/render_prompt.py | Task: general
[BLAKE] ⚪ set-contract-card strips trailing newlines, so the PRD edge case "a contract card containing ', \", $( and a newline round-trips through set-contract-card unchanged" does not hold byte-for-byte (verified: file ends "line2\n\n", stored value ends "line2"). | File: /Users/bob/.claude/skills/run-autopilot/cli/statectl.py | Task: general
[BLAKE] ⚪ state-schema.md's contract_card row still documents the retired mechanism: "via statectl set, in the same write that advances phase/next_phase". | File: /Users/bob/.claude/skills/run-autopilot/references/state-schema.md | Task: general
[BLAKE] ⚪ Shipped test file carries stale TDD comments asserting the code under test is absent: "needs_qwen_probe(state, batch_id) -> bool does not exist yet - every test below is expected to fail (AttributeError)" and the same for red_check_disposition. | File: /Users/bob/.claude/skills/work/scripts/test_work_routing.py | Task: general
[BLAKE] ⚪ tess-retry-prompt.md instructs "Read only the files listed above" but the retry template lists no files (it carries only QUALITY_FEEDBACK, TASK_DESCRIPTION, TASK_ACCEPTANCE_CRITERIA). | File: /Users/bob/.claude/skills/work/references/tess-retry-prompt.md | Task: general
[BLAKE] ⚪ --set-cmd treats empty stdout as a hard exit-4 failure, an unspecified extra constraint that blocks a whole dispatch when a legitimately empty source fills a slot. | File: /Users/bob/.claude/skills/work/scripts/render_prompt.py | Task: general
[BLAKE] ⚪ The PRD error case "a batch id absent from state.batch degrades to \"no-batch\" and re-probes rather than raising" exists only as jq-shaped prose; needs_qwen_probe takes the id as a caller-supplied parameter and no test binds the fallback. | File: /Users/bob/.claude/skills/work/scripts/work_routing.py | Task: general

B1: fail
B2: fail
B3: pass
B4: fail
B5: fail
B6: fail
B7: fail
B8: pass
B9: pass
B10: pass
B11: pass
B12: pass
B13: pass
B14: fail
B15: fail
B16: fail
B17: pass
B18: fail
B19: pass


## Bob

Doubt + de-slop lens (codex, static-only sandbox), resumed from his cycle-1
thread. His `D{n}` rubric verdicts and his FIX/VERIFY/KNOWN buckets are
preserved verbatim.

[BOB] 🟠 `set-contract-card` now strips trailing newlines, violating the PRD requirement to preserve the file contents unchanged | File: .claude/skills/run-autopilot/cli/statectl.py:247 | Task: 15
[BOB] 🟠 The Tess retry template asks a fresh dispatch to preserve and modify existing tests but supplies neither those test files nor their contents | File: .claude/skills/work/references/tess-retry-prompt.md:15 | Task: 12
[BOB] 🟠 The qwen invalidation test deletes the cache itself, so it does not verify that either watchdog or infra-failure signal actually triggers deletion | File: .claude/skills/work/scripts/test_work_routing.py:885 | Task: 17
[BOB] 🟡 Dispatch integration tests only search for one command substring; incomplete retry commands or broken placeholder mappings can still pass | File: .claude/skills/work/scripts/test_dispatch_prose.py:22 | Task: 17
[BOB] 🟡 The actual named-baseline test remains conditional on a machine-local transcript; the synthetic fixture tests generic counting but cannot replace that integration check | File: .claude/skills/work/scripts/test_check_build_overhead.py:516 | Task: 13
[BOB] 🟡 `append-attempt` accepts any parseable JSON value, allowing a scalar or array to corrupt the object-valued attempt-log schema | File: .claude/skills/run-autopilot/cli/statectl.py:224 | Task: 15
[BOB] 🟡 The synthetic-baseline test is 64 lines; extract its transcript fixture construction so the test remains under the 50-line limit | File: .claude/skills/work/scripts/test_check_build_overhead.py:672 | Task: 13
[BOB] 🟡 Incremental prose additions pushed `work/SKILL.md` beyond the separate 800-line file limit; move the new render-value detail into its reference and retain a concise binding rule | File: .claude/skills/work/SKILL.md:801 | Task: general
[BOB] 🟡 Adding qwen and red-check sections pushed `test_work_routing.py` beyond 800 lines; split the new independent sections into focused test modules | File: .claude/skills/work/scripts/test_work_routing.py:808 | Task: 17
[BOB] ⚪ TDD comments still claim `needs_qwen_probe` and `red_check_disposition` do not exist and their tests are expected to fail | File: .claude/skills/work/scripts/test_work_routing.py:803 | Task: 17
[BOB] ⚪ Cannot statically verify: reviewed Python and prose-contract test suites pass | File: N/A | Task: general
[BOB] ⚪ Cannot statically verify: next-batch overhead and median build-time success metrics are achieved | File: N/A | Task: general
R1: fail
R2: fail
R3: fail
R4: fail
R6: pass
R7: fail
R8: pass
R9: fail
R10: fail
R11: fail
R12: fail
R13: fail
D1: pass
D2: pass
D3: pass
D4: pass
D5: pass
FIX:
- Contract-card trailing newlines are discarded — .claude/skills/run-autopilot/cli/statectl.py:247 — assign `text` unchanged and add a trailing-newline round-trip regression test
- Tess retries lack the current test artifacts — .claude/skills/work/references/tess-retry-prompt.md:15 — add a registered test-files placeholder and pass the generated tests through `--set-file`, or explicitly resume the original Tess context
- Qwen invalidation causes are not tested — .claude/skills/work/scripts/test_work_routing.py:885 — model each watchdog and infra-failure signal and assert it produces the cache-deletion action, with gate failure as the negative case
- Render integration tests assert mere command presence — .claude/skills/work/scripts/test_dispatch_prose.py:22 — validate every dispatch/retry block’s template, output, and complete placeholder mapping, and render representative fixtures
- The named baseline remains skipped off the operator machine — .claude/skills/work/scripts/test_check_build_overhead.py:516 — make the recorded-baseline check an explicit required verification or provide a faithful redacted fixture rather than treating a generic synthetic transcript as equivalent
- `append-attempt` accepts non-object JSON — .claude/skills/run-autopilot/cli/statectl.py:224 — reject non-dict attempt payloads before mutation and test byte-identical state on failure
- Synthetic-baseline test exceeds 50 lines — .claude/skills/work/scripts/test_check_build_overhead.py:672 — extract the transcript-event fixture into a helper
- Rework pushed `work/SKILL.md` beyond 800 lines — .claude/skills/work/SKILL.md:801 — relocate only the newly added explanatory detail and retain concise procedural pointers
- `test_work_routing.py` exceeds 800 lines — .claude/skills/work/scripts/test_work_routing.py:808 — move the new qwen-preflight and red-check suites into dedicated test files
- Stale TDD comments describe implemented functions as absent — .claude/skills/work/scripts/test_work_routing.py:803 — replace them with current contract descriptions
VERIFY:
- Test status is runtime-only — run the statectl, render-prompt, overhead, dispatch-prose, work-routing, golden-contract, and fablectl suites and require zero failures
- Operational metrics need a completed subsequent batch — run `check_build_overhead.py` over its build transcripts and verify TaskCreate turns ≤2, statectl calls/task ≤2, prompt-authoring writes 0, permitted qwen probe frequency, and median task time below 21 minutes
KNOWN:
- (none)

## Carl

Gemini via the copilot backend. No frontend surface in this diff, so he reviewed
as a generalist and concentrated on the changed Python. He returned one finding
and passed every R rule - including R13, which is **wrong**: `work/SKILL.md` is
813 lines and `test_work_routing.py` is 971, both past the 800-line limit, as
Alice and Bob both caught. His one finding is accurate and was confirmed by
reading the code.

[CARL] 🟡 `do_task_done` duplicates attempt appending logic; replace lines 216-219 with `do_append_attempt(data, task_id, attempt)` | File: run-autopilot/cli/statectl.py:216 | Task: 15

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



Changes    +0 -0
AI Credits 17.9 (1m 41s)
Tokens     ↑ 88.5k • ↓ 132 (12.1k reasoning)
Resume     copilot --resume=f90496cf-9fe5-4fce-a8d4-89228749cd60


## Verification run by the orchestrator

Read-only, no git writes. Foreground, once for this cycle:

```
work/scripts/                                     268 passed
run-autopilot/cli/                                534 passed, 117 subtests
run-autopilot/scripts/                            696 passed, 31 skipped, 126 subtests
review-work-completion/scripts/                   215 passed
test_golden_contracts.py                          clean (exit 0)
```

The 31 skips are the pre-existing `tracon/test_screens.py` acceptance tests that
require `textual`; they are environment skips unrelated to this PRD. Note the
`run-autopilot/scripts/` suite needs `rich` on the path (`uv run --with rich`)
or three tracon modules fail collection.

Findings independently confirmed by the orchestrator before the decision gate:

- `work/SKILL.md` is **813** lines (`wc -l`), up from 772 at cycle 1 and 737
  before this PRD. Past the 800-line max in `rules/coding-style.md`.
- `test_work_routing.py` is **971** lines. Same limit breached.
- `tess-retry-prompt.md:27` carries "Read only the files listed above" copied
  from `tess-prompt.md:40`, but without that file's `{SAMPLE_TEST_FILE}` /
  `{PUBLIC_INTERFACES}` placeholders the sentence has no referent, and step
  2.8's documented render call passes only the three content placeholders.
- `test_work_routing.py:885` builds its "after a health signal" state by
  deleting the key inside the test, then asserts the same thing
  `test_qwen_probe_needed_when_no_verdict_is_cached` already asserts.
- Stale TDD comments appear at **two** sites (lines 804 and 912), not the one
  Bob named.
- `attempt-logging.md` line 75's table mandates `append-attempt <task-id>`
  while line 79 says the abort paths "keep the generic `append` form" and
  "`i` is this task's index" - a direct self-contradiction four lines apart.
- `gemini-integration.md:51` and `qwen-integration.md:91` both still carry a
  hand-written "TDD Implementation Mode (Ivan)" block using dotted lowercase
  `{task.subject}`-style placeholders that `render_prompt.py`'s
  `{[A-Z_][A-Z0-9_]*}` regex cannot fill.
- `do_task_done:216-218` and `do_append_attempt:234-236` are identical
  four-line blocks (Carl's finding).

Verdict: 38 findings
Tests: 1713 passed, 0 failed, 31 skipped
