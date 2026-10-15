# Decision Audit Log: 00308-reviewer-lane-resilience-v1

PRD: `00308-reviewer-lane-resilience-v1.md`
Started: 2026-10-15T08:22:22Z
Completed: 2026-10-15T08:22:22Z
Autonomous: 34  |  Deferred: 0  |  Doubts: 0

### [autonomous] 2026-10-15T08:22:22Z

**Decision**: 00308 design: how to bound/kill the gemini fallback process group and the replay-timeout runner without a tty or a new binary dependency

**Choice**: use set -m enabled in the calling shell (not inside a subshell) directly before backgrounding, plus kill -s KILL for the gemini fallback; Popen+communicate+os.killpg(proc.pid, SIGKILL) for the replay runner; extended permanently_unavailable() regex for copilot auth failure; added record_dispatch.py retry verb

**Rationale**: 3 review dispatches found and the design fixed: a SIGTERM-only kill (cardinal-sin), a set -m-inside-subshell that does not isolate the process group, TimeoutExpired has no pid attribute, setsid is absent on macOS (verified empirically, not just by review), and a Popen call outside its try block; all closed, no open findings

### [autonomous] 2026-10-15T08:22:22Z

**Decision**: Bob's first dispatch is never wired to the inlined prompt. The only place the new shape appears is retry-policy.md:23 ("dispatch 1 always builds this inlined prompt"). SKILL.md step 5 was not edited for this: the persona table at :245 and "Use the staged prompts" at :258 still send Bob the review-stage prompt. `rg -i inlin` finds nothing relevant in SKILL.md, and agent-invocation.md:37 still dispatches `{bob_prompt_file_absolute_path}`. retry-policy.md:23 also names the first-run file `bob-prompt-{id}-retry.md`, which collides with the staged `bob-prompt-{id}.md` that `review-stage` measured for the ledger row. Task 4 and the PRD require step 5's Bob dispatch to build the inlined shape unconditionally, so the headline success metric (one codex dispatch per cycle) is not delivered by the prose.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-15T08:22:22Z

**Decision**: Dangling references to the deleted "Lack-of-input refusal (Bob)" section remain. agent-invocation.md:47 still says "On a non-zero exit or a lack-of-input refusal, retry once per retry-policy.md § Lack-of-input refusal (Bob)". agent-invocation.md:49 still says the refusal shape "switches to the inlined retry prompt ... § Inlined retry prompt (CLI reviewers)", a heading that was renamed. The operator is therefore still told to retry on a rule that no longer exists. test_retry_policy_prose.py:82 and :115-123 pin this stale text (`assertIn("Lack-of-input refusal", self.bob_invocation)`, "and to the refusal shape it names"), so the suite protects the contradiction. Fix both docs and drop or rewrite those assertions.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-15T08:22:22Z

**Decision**: The watchdog is cancelled before `wait "$stderr_pid"`. If Gemini exits while a child retains stderr, that wait remains unbounded. Keep the watchdog active through stderr draining and add this regression case.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-15T08:22:22Z

**Decision**: `test_no_lack_of_input_retry_remains` passes against the pre-change code (fail-first replay [MECH]), so it does not pin the deletion. It loops with `subTest`, and the replay's parent result for it stays PASSED. It also checks only SKILL.md and retry-policy.md, so it misses the two surviving "lack-of-input" hits in agent-invocation.md:47 and :49. Replace the `subTest` loop with plain asserts that carry a message, and add agent-invocation.md to the scanned files.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-15T08:22:22Z

**Decision**: The `gave no result within ${FALLBACK_DEADLINE}s; killed.` message does not match the PRD, and no test asserts either deadline message. The PRD and design require `ERROR: gemini fallback produced no output within <n>s.` on timeout, and gemini-run.sh:244 emits different text. The auth message at :248 also differs from the PRD line `ERROR: copilot permanently unavailable (authentication failed).`. The design doc waives the auth wording, so that part is minor. The deadline is a total wall-clock cap, not a no-output cap, so a slow but productive fallback is killed at 900s. The stricter message either needs to be emitted as specified or the deviation documented in the PRD or design.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-15T08:22:22Z

**Decision**: Fallback deadline message diverges from PRD contract

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-15T08:22:22Z

**Decision**: Hedged assert flagged by mech-check. `assert not gemini_argv.exists() or gemini_argv.read_text() == ""` accepts either outcome. The gemini stub always writes a non-empty argv (`printf '%s\n' "$@"`), so the empty-file branch can never mean "not invoked". Simplify to `assert not gemini_argv.exists()`, which also removes the f-string `read_text()` that would raise on a missing file.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-15T08:22:22Z

**Decision**: test_auth_failure_exits_4_without_fallback hedges with `or`: either outcome satisfies it

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-15T08:22:22Z

**Decision**: `run_cmd` ends with an unconditional `set +m`, whereas the design saved and restored the caller's monitor mode (`mopt`). The script is non-interactive today, so this is harmless. The auth classifier also now lives inline in `run_cmd` (:247) rather than in `permanently_unavailable()` as the PRD says. Behavior is equivalent, but the design's single-classifier shape is lost, and the fallback guard keys on a new global `AUTH_FAILED` flag. Low-risk; note it or align it.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-15T08:22:22Z

**Decision**: The separate auth branch duplicates permanent-rejection handling and introduces unnecessary global state. Follow the specified shared classifier: extend `permanently_unavailable()`, retain its existing diagnostic, and inspect retained stderr when deciding whether to fall back.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-15T08:22:22Z

**Decision**: permanently_unavailable not extended with auth patterns per task contract

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-15T08:22:22Z

**Decision**: The timeout kill depends on successfully creating `timed_out`. If `touch` fails, the `&&` chain skips SIGKILL and leaves the fallback running indefinitely. Attempt the kill independently of marker creation and report timer failures.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-15T08:22:22Z

**Decision**: The Bob prompt file name deviates from the spec. The spec output is `docs/dev/tmp/bob-prompt-{id}.md` built as the inlined shape. retry-policy.md:23 still writes `bob-prompt-{id}-retry.md`, and `test_retry_policy_prose.py:59` pins that "retry" filename. Because review-stage already writes `bob-prompt-{id}.md`, the first-run inlined prompt would sit beside the staged one under a retry name. The first-run prompt is also dispatched "without `--resume-thread`", so incremental cycles lose the codex thread resume that agent-invocation.md:40 documents. The spec does not address this.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-15T08:22:22Z

**Decision**: `test_retry_case_uses_the_retry_verb` compares `'second `start` row under the same `--task`'.replace("`", "")` against `region.replace("`", "")`. Write the backtick-free literal once and drop both `.replace` calls. The `skill[at:at+900]` window is brittle, since the retry verb sits about 650 characters in. Anchor on the paragraph end instead.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-15T08:22:22Z

**Decision**: `GEMINI_FALLBACK_TIMEOUT`, the new auth exit 4 for every `gemini-run.sh` caller, and the 900s default appear only in CHANGELOG and the script. Neither use-gemini/SKILL.md:34 nor :71 mentions them. A one-line doc addition would cover it.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-15T08:22:22Z

**Decision**: test_retry_policy_prose.py still carries stale "retry prompt" comments and test names that describe the inlined prompt as a retry-only prompt (:55-67, :70). This is cosmetic, but it contradicts the retitled section.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-15T08:22:22Z

**Decision**: The retry row sets `prompt_bytes: None`, where `start` rows carry an int (record_dispatch.py:109). The spec lists only kind, task and detail. Consumers that sum `prompt_bytes` could trip on null; I did not trace them all.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-15T08:22:22Z

**Decision**: R1/R2 (🟠, 3/4 each) and R7 (🟠, 1/4): Bob's first dispatch is not wired to the inlined shape; dangling references to the deleted lack-of-input section survive in agent-invocation.md and are pinned by a test; the gemini watchdog is cancelled before the stderr wait, leaving that wait unbounded.

**Choice**: auto-fix via rework cycle 1 (tasks 5, 6)

**Rationale**: Cycle 1 of 2, so rework is allowed. Each is a clearly specified, bounded fix against a requirement the PRD states explicitly; none needs a research protocol (no new dependency, no recurrence, no data-model or public-API change) and none blocks another task, so no escalation applies. No 🔴 row exists, so no rework design ran.

### [autonomous] 2026-10-15T08:22:22Z

**Decision**: Eleven 🟡/⚪ findings (R3, R4+R12, R5+R11, R6, R8, R9, R10+R13, R14, R15, R16, R19)

**Choice**: auto-fix via rework cycle 1 (tasks 5, 6, 7, 8)

**Rationale**: Medium and Low never block convergence, but they are swept rather than dropped. Since the cycle did not converge anyway, they ride the same rework pass instead of a tail sweep. R12 folds onto R4 and R13 onto R10 (same defect, same file); R5 and R11 are the same hedged assert raised at two line numbers.

### [autonomous] 2026-10-15T08:22:22Z

**Decision**: R17 and R18 (⚪) and R20 (🟡, mech-check replay)

**Choice**: discarded; recorded in the settled-decisions ledger

**Rationale**: R17 and R18 assert no defect in their own text (behavior equivalent or stricter; both additions fail safe and are tested). R20's three tests are precision guards for the new auth classifier, so passing against the pre-change code is by design, not an unpinned behavior.

### [autonomous] 2026-10-15T08:22:22Z

**Decision**: Bob's first codex dispatch refused as lack-of-input; the engram context pack failed to build

**Choice**: logged, continued with graceful degradation

**Rationale**: Safety-check row: a transient reviewer error logs and continues. The one inlined retry recovered Bob's full review (eight findings, including the only 🟠 nobody else raised). The pack failure left every prompt carrying the documented sentinel. The refusal is the very defect this PRD fixes, and this batch runs the installed 0.9.0 pack rather than the repo source, so it is not a finding against the work.

### [autonomous] 2026-10-15T08:22:22Z

**Decision**: consolidate_findings.py dropped all eight of Bob's findings on the first run

**Choice**: re-consolidated against a normalized copy of Bob's output

**Rationale**: Bob's assembled prompt carries the FIX/VERIFY/KNOWN bucket sections, so he emitted issue lines as list items (`- [BOB] …`), which the consolidator's `^[BOB]` match misses. Stripping the leading `- ` into a separate file recovered them with the text otherwise byte-identical. Consolidation remained the script, not model-side. Worth a follow-up PRD: the bucket-emitting doubt lens and the consolidator disagree about line shape.

### [autonomous] 2026-10-15T08:22:22Z

**Decision**: R2 (🟠, 1/4, Blake blind): the auth-failure stderr line does not match the PRD literal string

**Choice**: discarded as a settled call; recorded in the settled-decisions ledger

**Rationale**: The design doc (00308-...-design.md:71-81) waives the literal string explicitly and reads the success metric as exits-4-and-latches; cycle 1 (R4) already adjudicated it. Blake never sees the design doc, which is why it returned. Exit 4 and the latch hold and are tested.

### [autonomous] 2026-10-15T08:22:22Z

**Decision**: R5, R8 and the three mech-check replay rows R12/R13/R14

**Choice**: discarded; recorded in the settled-decisions ledger

**Rationale**: R5: the PRD use case (-o, Carl) is covered and buffering the streaming path is out of scope. R8 asks to revert cycle 1 R19, whose fix was exactly dropping the null field. R12/R13/R14: this cycle replays against cycle 1 head, so passing against base only states the rework did not change behavior cycle 1 already landed.

### [autonomous] 2026-10-15T08:22:22Z

**Decision**: Eight actionable 🟡/⚪ findings (R1, R3+R9, R4, R6, R7, R10, R11)

**Choice**: auto-fix via the cycle-2 tail sweep

**Rationale**: Cycle 2 converged (no unresolved CRITICAL/HIGH, constraint gate exit 0), so the medium/low tail is swept by normal work tasks before finalize rather than reworked in another review cycle.

### [autonomous] 2026-10-15T08:22:22Z

**Decision**: Bob's dispatch-ledger `prompt_bytes` is measured by `review-stage` from the roughly 9 KB staged prompt. The inlined prompt now overwrites that file afterwards (about 187 KB in cycle 1), so the row understates what codex received. SKILL.md does not tell the operator to re-measure. A note, or re-measuring the file at dispatch, would keep the metric honest.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-15T08:22:22Z

**Decision**: `skills/review-work-completion/SKILL.md:260`, the cycle-1 high-severity fix, has no regression test. `test_bob_inlined_first_prose.py` pins only `retry-policy.md`, the absence of "lack-of-input", and the retry verb. Deleting the step-5 "Bob's prompt is always the inlined shape" paragraph would pass every test. Add an assert that SKILL.md step 5 names the inlined section and the `bob-prompt-{id}.md` overwrite.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-15T08:22:22Z

**Decision**: The rework adds no test assertion for step 5's overwrite-before-dispatch instruction. The existing first-dispatch test already passed when that wiring was missing; the added assertions check other documents. Add a regression assertion that fails when step 5's unconditional inlined assembly is removed.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-15T08:22:22Z

**Decision**: `run_cmd` is now 61 lines (`gemini-run.sh:220` to `:280`) against the 50-line limit. The cycle-1 version was under it; the watchdog and stderr-drain rework pushed it over. Move the watchdog launch and teardown into a helper, for example `start_watchdog` and `stop_watchdog`, without changing behavior.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-15T08:22:22Z

**Decision**: `GEMINI_FALLBACK_TIMEOUT` caps total wall-clock time, not "no output". The message reads "produced no output within Ns" even when the fallback was producing output. `skills/use-gemini/SKILL.md:42` documents the whole-run cap, so this is a known divergence from the PRD wording. A value of `0` arms an immediate kill, because only non-numeric values fall back to 900.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-15T08:22:22Z

**Decision**: Timeout classification still depends on successfully creating `timed_out`. If `touch` fails after Gemini exits successfully but leaves a child holding stderr, the watchdog kills that child, yet the parent can publish output and return 0. Propagate expiry independently of marker creation and add a failed-marker regression test.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-15T08:22:22Z

**Decision**: If `touch` of the `timed_out` marker fails, the watchdog now still kills the group and reports the failure. The run then returns the raw kill status (137) instead of the specified exit 4, and no test covers that branch (`gemini-run.sh:241` to `:244`). It is a rare filesystem failure inside an already-created mktemp dir, but the exit contract is not met there. Consider deriving the timeout verdict from the kill itself, for example a flag file written after the kill, or accept and document it.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-15T08:22:22Z

**Decision**: The exit-code table still describes exit 4 only as "Model unavailable or client tier ineligible". It does not mention the auth failure or the fallback timeout.

**Choice**: auto-fixed

**Rationale**: fixed by review-close
