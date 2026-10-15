---
prd: docs/dev/project-management/prds/wip/00308-reviewer-lane-resilience-v1.md
review: 1
date: 2026-10-15
head_sha: 322e9abbf209125f434af4c4fcbaa0778cd03105
codex_thread_id: 01a13e51-b2be-7642-82a8-72e297a959e3
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
dispatch_rows:
  bob: 60637809
  carl: 076340f7
---

# Review: 00308-reviewer-lane-resilience-v1

Diff range: `06c65adb85bc038edacadb4c36a1737eb466efb1..322e9abbf209125f434af4c4fcbaa0778cd03105`

codex_rung_guard: not fired

## Review Summary

Reviewed: 4 completed tasks
PRDs checked: 00308-reviewer-lane-resilience-v1.md

### Agent Status

- Alice: ✅ Available (consensus lens, engine `legacy`)
- Blake: ✅ Available (blind lens, PRD-only)
- Bob: ✅ Available (doubt lens + de-slop, codex) — **first dispatch refused as lack-of-input; the one inlined retry produced this review** (see Degradations)
- Carl: ✅ Available (UI/design lens, backend `copilot`, model `gemini-3.8-flash`)
- Eve: ⏸️ Disabled (doubt_reviewer is `codex` and no task was codex-implemented, so the codex doubt-roster guard did not fire)

### Degradations this cycle

- **engram context pack: failed** (`engram pack exit 1: sqlite3.OperationalError: attempt to write a readonly database`). Every prompt carried the `(no pack available this cycle)` sentinel; Blake never receives a pack by design. The review is degraded, not invalid.
- **Bob's first dispatch refused** with the documented lack-of-input shape (zero `R{n}: pass`, zero severity issue lines, one `⚪ Cannot statically verify`): the 9 KB staged prompt references file paths the codex sandbox could not open (`sandbox_apply: Operation not permitted`). Per `references/retry-policy.md` § Lack-of-input refusal the one retry was dispatched as the inlined prompt (187 KB, context + full diff inlined), which succeeded. **This is exactly the defect this PRD fixes**; the fix is in the repo source, while this batch runs the installed `0.9.0` pack, so the old behavior is expected here and is not a finding against the work.
- **Bob's findings needed manual normalization before consolidation.** His assembled prompt carries the FIX/VERIFY/KNOWN bucket sections, so he emitted his issue lines as bucket list items (`- [BOB] 🟠 …`). `consolidate_findings.py` matches `^[BOB]` only, so the first consolidation run silently dropped all eight of his findings, including a 🟠 nobody else raised (R7). A normalized copy (`bob-output-20261015-0700-normalized.txt`, leading `- ` stripped, text otherwise byte-identical) was consolidated instead. Consolidation was still the script, not model-side.

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [3/4] | 🟠 | Bob's first dispatch is never wired to the inlined prompt. The only place the new shape appears is retry-policy.md:23 ("dispatch 1 always builds this inlined prompt"). SKILL.md step 5 was not edited for this: the persona table at :245 and "Use the staged prompts" at :258 still send Bob the review-stage prompt. `rg -i inlin` finds nothing relevant in SKILL.md, and agent-invocation.md:37 still dispatches `{bob_prompt_file_absolute_path}`. retry-policy.md:23 also names the first-run file `bob-prompt-{id}-retry.md`, which collides with the staged `bob-prompt-{id}.md` that `review-stage` measured for the ledger row. Task 4 and the PRD require step 5's Bob dispatch to build the inlined shape unconditionally, so the headline success metric (one codex dispatch per cycle) is not delivered by the prose. | skills/review-work-completion/SKILL.md:258 | 4 | ALICE, BLAKE, BOB |
| R2 | [3/4] | 🟠 | Dangling references to the deleted "Lack-of-input refusal (Bob)" section remain. agent-invocation.md:47 still says "On a non-zero exit or a lack-of-input refusal, retry once per retry-policy.md § Lack-of-input refusal (Bob)". agent-invocation.md:49 still says the refusal shape "switches to the inlined retry prompt ... § Inlined retry prompt (CLI reviewers)", a heading that was renamed. The operator is therefore still told to retry on a rule that no longer exists. test_retry_policy_prose.py:82 and :115-123 pin this stale text (`assertIn("Lack-of-input refusal", self.bob_invocation)`, "and to the refusal shape it names"), so the suite protects the contradiction. Fix both docs and drop or rewrite those assertions. | skills/review-work-completion/references/agent-invocation.md:47 | 4 | ALICE, BLAKE, CARL |
| R3 | [3/4] | 🟡 | `test_no_lack_of_input_retry_remains` passes against the pre-change code (fail-first replay [MECH]), so it does not pin the deletion. It loops with `subTest`, and the replay's parent result for it stays PASSED. It also checks only SKILL.md and retry-policy.md, so it misses the two surviving "lack-of-input" hits in agent-invocation.md:47 and :49. Replace the `subTest` loop with plain asserts that carry a message, and add agent-invocation.md to the scanned files. | skills/review-work-completion/scripts/test_bob_inlined_first_prose.py:60 | 4 | ALICE, BOB, CARL, mech-check |
| R4 | [3/4] | 🟡 | The `gave no result within ${FALLBACK_DEADLINE}s; killed.` message does not match the PRD, and no test asserts either deadline message. The PRD and design require `ERROR: gemini fallback produced no output within <n>s.` on timeout, and gemini-run.sh:244 emits different text. The auth message at :248 also differs from the PRD line `ERROR: copilot permanently unavailable (authentication failed).`. The design doc waives the auth wording, so that part is minor. The deadline is a total wall-clock cap, not a no-output cap, so a slow but productive fallback is killed at 900s. The stricter message either needs to be emitted as specified or the deviation documented in the PRD or design. | skills/use-gemini/scripts/gemini-run.sh:244 | 2 | ALICE, BLAKE, BOB |
| R5 | [2/4] | 🟡 | Hedged assert flagged by mech-check. `assert not gemini_argv.exists() or gemini_argv.read_text() == ""` accepts either outcome. The gemini stub always writes a non-empty argv (`printf '%s\n' "$@"`), so the empty-file branch can never mean "not invoked". Simplify to `assert not gemini_argv.exists()`, which also removes the f-string `read_text()` that would raise on a missing file. | skills/use-gemini/scripts/test_gemini_run_unavailable.py:1438 | 2 | ALICE, BOB |
| R6 | [2/4] | 🟡 | `run_cmd` ends with an unconditional `set +m`, whereas the design saved and restored the caller's monitor mode (`mopt`). The script is non-interactive today, so this is harmless. The auth classifier also now lives inline in `run_cmd` (:247) rather than in `permanently_unavailable()` as the PRD says. Behavior is equivalent, but the design's single-classifier shape is lost, and the fallback guard keys on a new global `AUTH_FAILED` flag. Low-risk; note it or align it. | skills/use-gemini/scripts/gemini-run.sh:232 | 2 | ALICE, BOB |
| R7 | [1/4] | 🟠 | The watchdog is cancelled before `wait "$stderr_pid"`. If Gemini exits while a child retains stderr, that wait remains unbounded. Keep the watchdog active through stderr draining and add this regression case. | skills/use-gemini/scripts/gemini-run.sh:239 | 2 | BOB |
| R8 | [1/4] | 🟡 | The Bob prompt file name deviates from the spec. The spec output is `docs/dev/tmp/bob-prompt-{id}.md` built as the inlined shape. retry-policy.md:23 still writes `bob-prompt-{id}-retry.md`, and `test_retry_policy_prose.py:59` pins that "retry" filename. Because review-stage already writes `bob-prompt-{id}.md`, the first-run inlined prompt would sit beside the staged one under a retry name. The first-run prompt is also dispatched "without `--resume-thread`", so incremental cycles lose the codex thread resume that agent-invocation.md:40 documents. The spec does not address this. | skills/review-work-completion/references/retry-policy.md:23 | 8 | BLAKE |
| R9 | [1/4] | 🟡 | The timeout kill depends on successfully creating `timed_out`. If `touch` fails, the `&&` chain skips SIGKILL and leaves the fallback running indefinitely. Attempt the kill independently of marker creation and report timer failures. | skills/use-gemini/scripts/gemini-run.sh:235 | 2 | BOB |
| R10 | [1/4] | 🟡 | The separate auth branch duplicates permanent-rejection handling and introduces unnecessary global state. Follow the specified shared classifier: extend `permanently_unavailable()`, retain its existing diagnostic, and inspect retained stderr when deciding whether to fall back. | skills/use-gemini/scripts/gemini-run.sh:247 | 2 | BOB |
| R11 | [1/4] | 🟡 | test_auth_failure_exits_4_without_fallback hedges with `or`: either outcome satisfies it | skills/use-gemini/scripts/test_gemini_run_unavailable.py:161 | 2 | CARL, mech-check |
| R12 | [1/4] | 🟡 | Fallback deadline message diverges from PRD contract | skills/use-gemini/scripts/gemini-run.sh:243 | 2 | CARL |
| R13 | [1/4] | 🟡 | permanently_unavailable not extended with auth patterns per task contract | skills/use-gemini/scripts/gemini-run.sh:200 | 2 | CARL |
| R14 | [1/4] | ⚪ | `test_retry_case_uses_the_retry_verb` compares `'second `start` row under the same `--task`'.replace("`", "")` against `region.replace("`", "")`. Write the backtick-free literal once and drop both `.replace` calls. The `skill[at:at+900]` window is brittle, since the retry verb sits about 650 characters in. Anchor on the paragraph end instead. | skills/review-work-completion/scripts/test_bob_inlined_first_prose.py:1060 | 4 | ALICE |
| R15 | [1/4] | ⚪ | `GEMINI_FALLBACK_TIMEOUT`, the new auth exit 4 for every `gemini-run.sh` caller, and the 900s default appear only in CHANGELOG and the script. Neither use-gemini/SKILL.md:34 nor :71 mentions them. A one-line doc addition would cover it. | skills/use-gemini/SKILL.md:34 | 2 | ALICE |
| R16 | [1/4] | ⚪ | test_retry_policy_prose.py still carries stale "retry prompt" comments and test names that describe the inlined prompt as a retry-only prompt (:55-67, :70). This is cosmetic, but it contradicts the retitled section. | skills/review-work-completion/scripts/test_retry_policy_prose.py:55 | 4 | ALICE |
| R17 | [1/4] | ⚪ | The spec says `permanently_unavailable` "also matches" auth strings. The implementation adds a separate branch in `run_cmd` (gemini-run.sh:247) gated on `rc -ne 0`, with `AUTH_FAILED` suppressing the fallback. Behavior is equivalent or stricter, and the fallback skip is correct (gemini-run.sh:356). `permanently_unavailable` itself (gemini-run.sh:199-201) is unchanged. | skills/use-gemini/scripts/gemini-run.sh:199 | 2 | BLAKE |
| R18 | [1/4] | ⚪ | Small additions beyond the spec: a non-numeric `GEMINI_FALLBACK_TIMEOUT` silently falls back to 900 (gemini-run.sh:229), and `retry` with no autopilot dir prints a random token and writes nothing (record_dispatch.py:92). Both fail safe and are tested; neither is specified. | skills/work/scripts/record_dispatch.py:92 | 3 | BLAKE |
| R19 | [1/4] | ⚪ | The retry row sets `prompt_bytes: None`, where `start` rows carry an int (record_dispatch.py:109). The spec lists only kind, task and detail. Consumers that sum `prompt_bytes` could trip on null; I did not trace them all. | skills/work/scripts/record_dispatch.py:109 | 3 | BLAKE |
| R20 | [1/4] | 🟡 | 3 touched test(s) pass against the pre-change code: test_ordinary_copilot_failure_stays_exit_1_without_fallback, test_successful_copilot_run_mentioning_auth_keeps_exit_0, test_tier_rejection_still_falls_back | skills/use-gemini/scripts/test_gemini_run_unavailable.py | general | mech-check |

### Mechanical test checks absorbed

Three `[MECH]` lines were produced by `detect_tautological_tests.py` and `replay_tests_against_base.py`:

- the hedged `test_auth_failure_exits_4_without_fallback` assert → folded into **R11** (and overlaps **R5**, which Alice and Bob raised against the same defect in the same file; the gate treats R5 and R11 as one defect).
- `test_no_lack_of_input_retry_remains` passing against base → folded into **R3**.
- three `test_gemini_run_unavailable.py` tests passing against base → **R20**, its own row.

No prior cycle exists, so nothing was carried forward.

## Alice

Nine findings (2 🟠, 4 🟡, 3 ⚪), listed as R1, R2, R3, R4, R5, R6, R14, R15, R16 above. She ran the three new test files herself: 15 passed.

Checked and reported clean by Alice:
- `_run_in_worktree` puts `Popen` inside the `try`, uses `proc.pid` with `killpg`, and guards `ProcessLookupError`. The test checks the leader, the grandchild and a decoy outside the group.
- `retry_row` copies `kind` and `task` from the named start row and passes the no-dir, unknown-id and ended-row cases.
- The process-group kill in `run_cmd` works under `stdin=/dev/null`.

```
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
R13: pass
```

(The consensus rubric has no `R5`; twelve verdict lines is the complete set.)

## Blake

Blind lens, PRD-only. Seven findings (2 🟠, 2 🟡, 3 ⚪), listed as R1, R2, R4, R8, R17, R18, R19 above. He read the code and ran the listed pytest files: 52 passed. He did not run `dev/bin/release-checks`.

Verified correct by Blake: the replay process-group kill, the `retry` verb, the bounded fallback and its four named tests, both CHANGELOG entries, the three new test files' registration in `dev/bin/release-checks`, and `rg 'lack-of-input'` returning 0 in SKILL.md and retry-policy.md.

```
B1: fail
B2: pass
B3: pass
B4: pass
B5: fail
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
B17: fail
B18: pass
B19: pass
```

## Bob

Doubt lens + de-slop, codex. Eight findings (1 🟠, 7 🟡), listed as R1, R3, R4, R5, R6, R7, R9, R10 above. **R7 is his alone** — the only finding no other reviewer raised.

FIX / VERIFY / KNOWN buckets as emitted:

```
FIX:
- 🟠 The watchdog is cancelled before `wait "$stderr_pid"`. If Gemini exits while a child retains stderr, that wait remains unbounded. | skills/use-gemini/scripts/gemini-run.sh:239
- 🟡 The timeout kill depends on successfully creating `timed_out`; if `touch` fails the `&&` chain skips SIGKILL. | skills/use-gemini/scripts/gemini-run.sh:235
- 🟡 Step 5 omits the required unconditional first-dispatch assembly instruction. | skills/review-work-completion/SKILL.md:260
- 🟡 `set +m` unconditionally disables monitor mode instead of preserving the caller's setting. | skills/use-gemini/scripts/gemini-run.sh:237
- 🟡 The timeout diagnostic differs from the required message; the deadline tests never assert it. | skills/use-gemini/scripts/gemini-run.sh:244
- 🟡 The separate auth branch duplicates permanent-rejection handling and adds unnecessary global state. | skills/use-gemini/scripts/gemini-run.sh:247
- 🟡 The mechanically flagged auth assertion accepts either an absent or empty invocation file. | skills/use-gemini/scripts/test_gemini_run_unavailable.py:161

VERIFY:
- 🟡 Fail-first replay reports the refusal-removal test passing against base. Run `test_no_lack_of_input_retry_remains` against `06c65adb85bc` with only Python test files overlaid and both policy Markdown files retained from base; it must fail on the old refusal rule. | skills/review-work-completion/scripts/test_bob_inlined_first_prose.py:60
  (not queued: command shape — the item describes an overlay procedure, not one runnable command line. It stays an ordinary finding, folded into R3.)

KNOWN:
- (none)
```

```
R1: fail
R2: fail
R3: pass
R4: fail
R6: pass
R7: pass
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
```

## Carl

UI/design lens, backend `copilot`, model `gemini-3.8-flash`. Five findings (4 🟡, 1 ⚪), listed as R2, R3, R11, R12, R13 above. He ran the changed test files and probed the `set -m` process-group behavior directly.

```
R1: pass
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
R13: pass
```

## Verification-check queue

No entries this cycle. The single VERIFY item names an overlay procedure rather than one runnable command line, so the queue rule leaves it as an ordinary finding (see Bob's section).

Verdict: 20 findings
Tests: 6845 passed, 0 failed, 34 skipped (suite run this cycle)
