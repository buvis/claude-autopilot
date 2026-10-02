# PRD 00093 — cap-out findings, awaiting your decisions

PRD: `00093-cut-build-phase-clerical-overhead-v1`
Stalled at: review cycle 2 of cap 2, `site: cap_critical`
Batch: `202607202320`
Review file: `dev/local/reviews/00093-cut-build-phase-clerical-overhead-v1-review-2.md`
Diff reviewed: `a5af4081..e39296e6` (18 rework commits, the 10 `[D1]` tasks)

The batch kept draining; this PRD is parked in `dev/local/prds/hold/`. To resume:
`mv dev/local/prds/hold/00093-cut-build-phase-clerical-overhead-v1.md dev/local/prds/backlog/`

**Why it stalled rather than finished.** Two CRITICAL findings from cycle 1 are
still open. Both were correctly deferred (neither is fixable inside this PRD),
but a CRITICAL is never treated as a settled deferral at the cap gate — the rule
exists so a PRD cannot reach `done/` with an open CRITICAL. Eight HIGH findings
also remain, and the rework cap is spent, so no further automatic cycle is
authorized.

**Agenda: 10 findings needing your call — 2 CRITICAL, 8 HIGH.** Plus 20 Medium
and 10 Low recorded in the review file, not itemised here.

---

## 1 of 10 — CRITICAL — The 500-line Success Metric is missed, and this PRD made it worse

**What.** The PRD sets a binding Success Metric: "`work/SKILL.md` body lands at
or under 500 lines", and calls that metric "the mechanism [that] makes the
slimming binding rather than incidental". The file is now **813 lines**. It was
737 when this PRD started and 772 at the end of cycle 1, so the PRD's own work
grew it by 76 lines. Found by Blake (blind lens) and confirmed by direct `wc -l`.

**Evidence.** Confirmed, measured: 813 lines. The metric is missed by 63%. This
also newly breaches a second, separate rule — the 800-line file maximum in
`rules/coding-style.md` (rubric R13) — which the file was still under at cycle 1.

**If unchanged.** Every `/work` invocation loads the file, so the cost is paid
~141 times per 30 days at roughly 15.6K tokens. The overrun compounds: this PRD
added prose to fix review findings, and the next PRD to touch the file starts
from a worse baseline than 00119 was scoped against.

**Options.**
1. **(Recommended) Accept the deferral, and re-scope PRD 00119 to the new
   starting point.** 00119 already owns this reduction and documents why it
   cannot be a side-task: `test_fablectl.py` contract-tests the live SKILL.md
   with ~25 exact-text assertions anchored on step-5.5 and step-2.85 prose.
   *Benefit:* keeps the risky 300-line refactor in a PRD built for it, with its
   test-anchor work planned. *Drawback:* 00093 closes with its own headline
   metric unmet, so the metric never gated anything. *Effort:* S (edit 00119).
   *Risk:* none directly; defers the real work again.
2. **Fix it inside 00093 now** — relocate the added prose into references and
   retarget the `test_fablectl.py` anchors. *Benefit:* the metric is actually
   met and the 800-line breach closes. *Drawback:* a 300-line refactor of the
   orchestrator's own procedure file, with ~25 test anchors to retarget; a
   mistake breaks the autopilot safety net that guards every future build.
   *Effort:* L. *Risk:* high, and unattended rework is the worst place for it.
3. **Drop the metric from the PRD** and record that file size is governed by
   00119 alone. *Benefit:* honest — stops a metric nobody intends to enforce
   here from failing every review. *Drawback:* loses the pressure that made the
   slimming binding at all. *Effort:* S. *Risk:* the file keeps growing.
4. **Accept and defer with no further action.** *Benefit:* zero effort.
   *Drawback:* the 800-line breach is left unrecorded anywhere that will act on
   it. *Effort:* none.

**Strongest reason against the recommendation:** it is the third consecutive
deferral of the same finding, and the file grew during each one.

---

## 2 of 10 — CRITICAL — The Phase 2 acceptance number is unreachable as written

**What.** Phase 2's acceptance criterion says `check_build_overhead.py`, run
against the named baseline transcript, must report ">= 7" statectl calls per
completed task. It reports **2.80**. The shipped golden test was written to
assert 2.80 and document the deviation, rather than to satisfy the criterion.
Found by Blake and Alice, and reproduced independently by the orchestrator in
both cycles.

**Evidence.** Confirmed. Against the PRD's own named transcript the script
reports: TaskCreate turns 10, statectl calls 14, completed tasks 5, ratio 2.80.
The TaskCreate figure (10) matches the PRD exactly, which is what shows the
counting logic is honest. The `>= 7` figure came from a batch-wide measurement
(68 statectl calls / 9 tasks across 6 sessions) while the criterion names a
single session. The two numbers measure different scopes.

**If unchanged.** Phase 2's exit criterion ("reproduces the documented baseline
numbers") stays failed, so the measurement script cannot gate the next batch —
which was the entire point of building it. The 7.5-per-task figure in Success
Metrics also cannot be compared against future runs.

**Options.**
1. **(Recommended) Re-baseline the PRD to the per-session number.** Change the
   acceptance criterion to 2.80 for a single session, and restate the "at most
   2 per task" target against the same scope. *Benefit:* the script starts
   gating immediately, against a number that was actually measured. *Drawback:*
   only you can do this — it is a spec change, and it lowers the apparent
   improvement (2.80 → 2 is a much smaller win than 7.5 → 2). *Effort:* S.
2. **Make the script aggregate across a whole batch** so it reproduces the 7.5
   figure as written. *Benefit:* keeps the PRD's headline number intact and
   measures what the problem statement actually described. *Drawback:* new
   feature work on a script that already shipped; needs a batch-of-transcripts
   input mode and its own tests. *Effort:* M. *Risk:* re-opens a closed task.
3. **Keep both scopes** — report per-session and per-batch side by side.
   *Benefit:* no information lost, both criteria satisfiable. *Drawback:* two
   numbers to explain every time; the acceptance criterion still needs an edit
   to say which one gates. *Effort:* M.
4. **Accept and defer.** *Benefit:* zero effort. *Drawback:* the script stays
   un-gating and the Phase 2 exit criterion stays failed indefinitely.

**Strongest reason against the recommendation:** re-baselining to a number the
implementation already produces is uncomfortably close to moving the goalposts
to wherever the ball landed. The mitigation is that 2.80 was independently
reproduced and the TaskCreate control number matched exactly.

---

## 3 of 10 — HIGH — The Tess retry template tells her to preserve tests she cannot see

**What.** `work/references/tess-retry-prompt.md`, created by rework task 12,
says "Keep every test that is already sound" and "Read only the files listed
above. If a file or symbol you need is not listed, stop and report it as a
blocker." The template lists no files. It carries only `{QUALITY_FEEDBACK}`,
`{TASK_DESCRIPTION}` and `{TASK_ACCEPTANCE_CRITERIA}`, and step 2.8's documented
render call passes exactly those three. Found by Bob (High), Alice and Blake.

**Evidence.** Confirmed by reading both templates. The guard sentence was copied
verbatim from `tess-prompt.md:40`, where it has referents — that file supplies
`{SAMPLE_TEST_FILE}` and `{PUBLIC_INTERFACES}`. The retry template kept the
sentence and dropped the referents. The prompt it replaced had neither the
sentence nor the preserve-existing-tests instruction, so this is a regression
introduced by the rework, not a pre-existing gap.

**If unchanged.** Every step-2.8 quality-gate retry hits it — up to 2 per task,
inside a 5-dispatch Tess budget. A literal-minded Tess blocks on the very test
files she is meant to fix; a lenient one rewrites from scratch, which is exactly
what "this is a targeted fix, not a rewrite" was added to prevent.

**Options.**
1. **(Recommended) Add a test-files placeholder and pass it at step 2.8** —
   register `{EXISTING_TESTS}` in `agent-registry.md`, render it with
   `--set-file`, and update the step-2.8 call. *Benefit:* fixes the cause; the
   retry finally has the artifacts its instructions assume. *Drawback:* touches
   the registry, the template and SKILL.md together. *Effort:* S.
2. **Delete the two orphaned instructions** from the retry template.
   *Benefit:* smallest possible change; removes the contradiction.
   *Drawback:* Tess still cannot see the tests, so she still rewrites from
   scratch — the symptom goes quiet, the defect stays. *Effort:* S.
3. **Drop the separate retry template** and re-dispatch the full initial
   template with the feedback appended. *Benefit:* one template, all guards and
   referents present by construction. *Drawback:* undoes task 12's extraction
   and re-sends a larger prompt each retry. *Effort:* M.

**Strongest reason against the recommendation:** it adds a fourth placeholder to
a step whose whole purpose was reducing per-dispatch assembly work.

---

## 4 of 10 — HIGH — The abort-line fix for Tess opened the identical hole for Devon

**What.** Rework task 10 updated `references/subagent-dispatch.md` step 4 to say
the mandatory 100K abort-instruction line is "baked into the persona files, so
there is nothing to prepend", naming `ivan.md` and `tess-prompt.md`. But Devon
(step 2.85) is an Agent-tool dispatch assembled inline from
`adversarial-test-prompt.md`, which carries no abort line — and `SKILL.md:75`
still mandates the line for every Agent dispatch. Found by Alice.

**Evidence.** Confirmed by `rg`: only `ivan.md`, `tess-prompt.md` and
`tess-retry-prompt.md` contain the line. This is the same defect class as the
cycle-1 Tess finding the rework was fixing, displaced one file over.

**If unchanged.** Devon dispatches lose the context-overrun guard silently.
Devon runs on the `opus` and `fable` tiers — the deepest, most expensive
pipeline, and the one most likely to overrun.

**Options.**
1. **(Recommended) Add the abort line to `adversarial-test-prompt.md`** and
   correct step 4's claim to name every persona that carries it. *Benefit:*
   closes the hole and makes the reference true. *Drawback:* the invariant is
   still enforced by hand across N files. *Effort:* S.
2. **Add a test that every dispatch template carries the abort line.**
   *Benefit:* closes this hole and the whole class, permanently. *Drawback:*
   needs an agreed list of what counts as a dispatch template. *Effort:* M.
3. **Revert step 4 to "always prepend"** and stop baking the line into
   personas. *Benefit:* one rule, no per-file drift. *Drawback:* undoes part of
   the PRD's zero-inline-assembly goal. *Effort:* S.

**Strongest reason against the recommendation:** option 1 fixes this instance
while leaving the next persona to make the same mistake — option 2 is what
actually prevents a third occurrence.

---

## 5 of 10 — HIGH — The qwen cache-invalidation test cannot fail

**What.** `test_work_routing.py:885`,
`test_qwen_probe_needed_again_after_a_health_signal_clears_the_cache`, builds
its "after a health signal" state by deleting the cache key **inside the test**,
then asserts `needs_qwen_probe` returns True. It never exercises the watchdog or
infra-failure signal that is supposed to cause the deletion. Found by Bob.

**Evidence.** Confirmed by reading the test; its own comment says the signal is
"modeled here by starting from a matching cached state and deleting the key".
The assertion is identical to what
`test_qwen_probe_needed_when_no_verdict_is_cached` already covers. This test was
added by task 17 specifically to close cycle 1's "no tests bind the qwen
cache/invalidation flow" finding.

**If unchanged.** The invalidation path — the PRD's own stated mitigation for "a
cached qwen preflight masks a backend that died mid-batch" — has no binding
test, while appearing to have one. `rules/testing.md`: a test that cannot fail
when the logic changes is wrong.

**Options.**
1. **(Recommended) Model the signal→action step as a function and test it** —
   e.g. `qwen_cache_action(signal) -> "delete" | "keep"`, with the watchdog and
   infra verdicts asserting `delete` and an ordinary gate failure asserting
   `keep`. *Benefit:* binds the actual decision, and the existing negative case
   becomes meaningful. *Drawback:* adds a sixth public function to
   `work_routing.py`, whose docstring already understates its size. *Effort:* M.
2. **Assert it in prose instead**, extending `test_dispatch_prose.py` to pin
   SKILL.md's two invalidation triggers. *Benefit:* no production code added;
   matches how the rest of the step-3 prose is bound. *Drawback:* prose
   assertions are weak, as finding 6 below shows. *Effort:* S.
3. **Delete the test and record the gap honestly.** *Benefit:* removes a test
   that provides false assurance. *Drawback:* leaves cycle 1's finding open with
   nothing tracking it. *Effort:* S.

**Strongest reason against the recommendation:** it grows a module Alice already
flags as having outgrown its stated scope.

---

## 6 of 10 — HIGH — The new prose tests do not bind what they claim

**What.** `test_dispatch_prose.py` was added by task 17 to stop a prose revert
from silently reintroducing inline prompt authoring. Alice **mutation-tested
it**: she reverted step 3's Ivan render block to "assemble inline" on a copy of
the skill, and all 5 tests still passed. The needle
`render_prompt.py ~/.claude/agents/ivan.md` also occurs in step 5.5's retry
block, so whole-file substring presence stays satisfied. Found by Alice, with
Bob raising the same weakness independently.

**Evidence.** Confirmed by mutation test — the strongest evidence in this cycle.
Two occurrences of the needle; removing one leaves the assertion green.

**If unchanged.** The regression guard the PRD's own test strategy asked for
does not guard. A future edit can undo the migration with every suite green.

**Options.**
1. **(Recommended) Assert per-section, or on occurrence counts.** *Benefit:*
   directly closes the hole the mutation test found; small, local change.
   *Drawback:* section-scoped assertions are brittle against heading renames.
   *Effort:* S.
2. **Render the real personas in a test** and assert the fixed sections — the
   Phase 0 exit criterion the PRD actually named, which nothing currently
   guards (Alice and Blake both flag this separately). *Benefit:* binds
   placeholders to flag sets, catching a whole class the substring tests miss.
   *Drawback:* larger; needs representative fixture values. *Effort:* M.
3. **Both.** *Benefit:* covers prose reverts and placeholder drift.
   *Drawback:* most work. *Effort:* M-L.

**Strongest reason against the recommendation:** option 1 alone still leaves the
Phase 0 exit criterion ("rendering each of Pat, Tess and Ivan reproduces today's
fixed sections") with no automated guard at all.

---

## 7 of 10 — HIGH — The zero-inline-prompt metric is unmet on the qwen, gemini and codex lanes

**What.** The PRD's Success Metric is "zero inline prompt bodies for the
test-writer, implementor and per-task reviewer dispatches". The migration
covered the Claude lanes only. `qwen-integration.md:91` and
`gemini-integration.md:51` both still carry a hand-written "TDD Implementation
Mode (Ivan)" block, and both use dotted lowercase `{task.subject}`-style
placeholders that `render_prompt.py` cannot fill. The codex dispatch checklist
names `-f <prompt file>` without saying it is rendered from `ivan.md`. Found by
Blake.

**Evidence.** Confirmed by `rg`: both files carry the block and the dotted
placeholders; `render_prompt.py`'s regex is `{[A-Z_][A-Z0-9_]*}`, which cannot
match them. Those inline blocks also omit the abort line, the code-quality
rules, the dispatch prologue and the ASSUMPTIONS/FILES_TOUCHED footers that
SKILL.md mandates for every Ivan dispatch "regardless of mechanism".

**If unchanged.** Whenever routing picks qwen, gemini or codex as implementor,
Ivan runs with a weaker prompt missing four mandated guards — and the PRD's
metric reads as met when it is met on one lane out of four.

**Options.**
1. **(Recommended) Point all three lanes at `ivan.md` via `render_prompt.py`.**
   *Benefit:* one implementor prompt for every backend; the metric becomes
   true; the four missing guards arrive automatically. *Drawback:* each lane
   has its own dispatch mechanics, so this is three separate edits plus
   re-verification. *Effort:* M.
2. **Narrow the metric to the Claude lanes** and record the others as known
   gaps. *Benefit:* honest about what shipped; no new work. *Drawback:* leaves
   three lanes dispatching Ivan without mandated guards. *Effort:* S.
3. **Fix only the missing guards** in the inline blocks, leaving them inline.
   *Benefit:* closes the safety gap cheaply. *Drawback:* four more copies of
   text that must stay in sync by hand — the duplication this PRD existed to
   remove. *Effort:* S.

**Strongest reason against the recommendation:** the qwen and gemini lanes are
rarely selected, so this may be real effort spent on paths that seldom run.

---

## 8 of 10 — HIGH — `set-contract-card` does not round-trip the file's contents

**What.** `statectl.py`'s `do_set_contract_card` applies `text.rstrip("\n")`.
The PRD specifies the output as "`state.contract_card` set to the file's
contents" and names an edge case: a card containing quotes, `$(` and a newline
"round-trips through `set-contract-card` unchanged". It does not, byte-for-byte.
Raised by Blake at Low in cycle 1, unaddressed, and re-raised by Bob at High
this cycle.

**Evidence.** Confirmed by reading the code and by Blake's reproduction (file
ends `line2\n\n`, stored value ends `line2`). The code carries a comment
defending the strip: the card is re-injected as `additionalContext` by the
SessionStart hook, which supplies its own framing, so a trailing blank line is
noise.

**If unchanged.** A trailing newline is lost on every contract-card write. The
practical impact is very small — the consumer reframes the text anyway — but the
PRD's stated edge case is not satisfied and the two reviewers disagree about
whether the deviation is acceptable.

**Options.**
1. **(Recommended) Keep the strip; correct the PRD's edge case to say so.**
   *Benefit:* preserves a deliberate, documented, harmless behaviour and stops
   it being re-raised every cycle. *Drawback:* the spec is edited to match the
   code, which is the wrong direction when done carelessly. *Effort:* S.
2. **Store the bytes unchanged** and let the hook trim. *Benefit:* satisfies
   the spec exactly; round-trip becomes literally true. *Drawback:* moves the
   trimming to a consumer that may not do it; churn for no user-visible gain.
   *Effort:* S.
3. **Accept the deferral and ledger it** so it stops recurring without either
   file changing. *Benefit:* zero code churn. *Drawback:* leaves a spec and an
   implementation disagreeing on the record. *Effort:* S.

**Strongest reason against the recommendation:** severity is genuinely disputed
here — Bob calls it High, Blake called it Low, and I read it as Low-to-Medium.
Treat the High rating with suspicion.

---

## 9 of 10 — HIGH — `statectl` gained a fourth verb against the PRD's explicit bound

**What.** The PRD says to "keep the verbs deliberately narrow — two transitions
and one field setter, no schema layer", and its own task text says the abort and
escalate-away paths "keep the generic `append`". Rework task 15 added a fourth
verb, `append-attempt`. Found by Blake.

**Evidence.** Confirmed — `do_append_attempt` exists in `cli/statectl.py:224`.
The context matters: task 15 added it to fix a different cycle-1 finding (the
abort path used inline JSON on the shell plus an array-index path that targets
the wrong task once `[D{cycle}]` follow-ups are appended). So the verb resolves
a real defect while breaking a stated scope bound.

**If unchanged.** A scope bound the PRD set for itself was crossed without the
PRD being updated, and PRD 00089 — which is meant to absorb this surface — now
has one more verb to absorb than it was told about.

**Options.**
1. **(Recommended) Keep the verb; update the PRD's bound and note it for
   00089.** *Benefit:* keeps the better fix (id resolution, no shell quoting)
   and leaves an accurate record for the PRD that inherits it. *Drawback:*
   scope bounds that get edited whenever they bind are not bounds. *Effort:* S.
2. **Revert to the generic `append`** and fix the wrong-task risk another way.
   *Benefit:* honours the stated bound. *Drawback:* reintroduces the exact
   inline-JSON and array-index defects cycle 1 raised. *Effort:* M.
3. **Fold `append-attempt` and `task-done` together** behind one verb with a
   flag. *Benefit:* three verbs again, bound satisfied. *Drawback:* a flag that
   changes which fields move is harder to read than two named verbs; also
   Carl's finding notes the two already share duplicated code. *Effort:* M.

**Strongest reason against the recommendation:** it sets the precedent that any
rework may widen a PRD's scope bound as long as it fixes something.

---

## 10 of 10 — HIGH — `--set-cmd` runs a model-composed string through a shell

**What.** `render_prompt.py`'s `--set-cmd` calls
`subprocess.run(cmd, shell=True)`. The only defence against task-supplied text
reaching that nested shell is prose in SKILL.md telling the orchestrator to
quote paths. Blake argues `shlex.split` satisfies the spec ("a command whose
stdout fills it") without a shell, and that `shell=True` also hides command
execution behind a `python3 ...` argv where the Bash gate cannot inspect it.

**Evidence.** Confirmed present. This was raised in cycle 1 by Blake and Carl at
Medium, and task 14 deliberately preserved it as design-doc-accepted (same trust
domain, caller and callee are the same process). It was **never written to the
settled-decisions ledger**, which is why it returned — this cycle at High, with
a new argument (the Bash-gate blindness) the earlier decision did not consider.

**If unchanged.** The behaviour is unchanged from a design decision you already
approved; the risk is that the decision keeps costing a reviewer slot every
cycle because it was never recorded as settled.

**Options.**
1. **(Recommended) Record the decision in the ledger, and separately weigh the
   new Bash-gate argument.** *Benefit:* stops the recurrence; keeps the one
   genuinely new point visible instead of dismissing it with the old one.
   *Drawback:* two actions rather than one. *Effort:* S.
2. **Switch to `shlex.split` with `shell=False`.** *Benefit:* removes the shell
   entirely; the documented `cat file1 file2` use still works. *Drawback:*
   breaks any `--set-cmd` relying on shell features (pipes, `$( )`,
   redirection); needs a sweep of every call site. *Effort:* M.
3. **Keep `shell=True` and ledger it, no further analysis.** *Benefit:*
   cheapest. *Drawback:* dismisses a new argument on the strength of an old
   decision that did not address it. *Effort:* S.

**Strongest reason against the recommendation:** if the Bash-gate argument holds,
option 2 is the right answer and option 1 delays it another cycle.

---

## Recorded, not itemised

20 Medium and 10 Low findings are in the review file's consolidated table. The
ones most likely to matter:

- `attempt-logging.md` contradicts itself four lines apart (table mandates
  `append-attempt <task-id>`; prose says keep the generic `append` with an index
  path) — a rework regression, cheap to fix.
- `self-deslop-prompt.md` still instructs the `attempts[-1]` indexed write that
  task 15 removed from SKILL.md step 5.6 for failing on every first attempt.
- Step 2.95's `red_check` write has that same first-attempt failure, with no
  carry-into-step-6 workaround.
- `test_work_routing.py` is 971 lines, past the 800 max, and the repo already
  splits this suite elsewhere.
- Stale TDD comments at lines 804 and 912 assert the shipped code "does not
  exist yet".
- `check_build_overhead.py` dies with an uncaught `UnicodeDecodeError` on
  invalid UTF-8, and reads with the locale encoding rather than UTF-8.
- SKILL.md step 3 tells the orchestrator to read a "key not found" signal from
  `statectl del` that the tool never emits.

## Not a finding

33 files carried uncommitted working-tree modifications during this review
(`settings.json`, `warden.yaml`, `.codex/config.toml`, `audit-qwen/`, `tracon/`,
`cli/loop.py`, `consolidate_findings.py`, others). That is your own in-flight
work. It was left untouched and is outside this PRD's scope. One overlaps a
reviewed file — `work/scripts/work_routing.py` carries a black-reflow-only
change on top of HEAD.
