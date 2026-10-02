---
prd: dev/local/prds/wip/00178-fix-bob-first-run-and-specify-his-retry-v1.md
review: 1
date: 2026-09-06
head_sha: fa95ae09e04e6c6f82cefbad329f74f16924d127
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00178-fix-bob-first-run-and-specify-his-retry-v1

Diff range: `560f061a1bd500b9cf772a13ce86236e3b481bf4..fa95ae09e04e6c6f82cefbad329f74f16924d127`

codex_rung_guard: not fired

pack: failed (`engram pack` exited 1: "not inside a registered repo; register it in /Users/bob/.config/gita/repos.csv"). Not retried — the failure is a deterministic registration precondition, not a transient error. `{PACK_FILE}` and `{PACK_FINDINGS}` were substituted with `(no pack available this cycle)` in every prompt that takes them. The review is degraded on retrieval context, not invalid.

diff-scope note: `gather-context.sh`'s own base detection resolves to `master`, and this repo commits directly to `master`, so its first run produced a **0-line diff**. The gather was re-run with `--since 560f061a1bd500b9cf772a13ce86236e3b481bf4` (`state.work_start_sha`) to produce the PRD's real 271-line, 8-file work-range diff. Despite the flag's name this is a **full** cycle-1 review, not an incremental one; the context file says so at its diff-scope line.

## Reviewer status

- Alice: ✅ Available (Claude subagent, consensus lens)
- Blake: ✅ Available (Claude subagent, blind/PRD-only lens)
- Bob: ✅ Available (codex CLI, doubt + de-slop lens; exit 0, first dispatch, no retry needed). Notable: `state.codex_probe.verdict` was `unhealthy` for this batch and the *installed* `agents/bob.md` still carries the pre-PRD-00178 sandbox wording, yet Bob read his context and diff and produced a full review — no lack-of-input refusal this cycle.
- Carl: ✅ Available (gemini via `backend=copilot model=gemini-3.8-flash`; exit 0, 38.3 AI credits, 4m07s)

`codex_thread_id` omitted: `--emit-thread-id` was passed but `bob-thread-00178-c1.txt` was written empty, so there is no id to stamp. The next cycle runs Bob fresh.

## Consolidated Findings

10 findings. Severity split: 1 🟠 High, 6 🟡 Medium, 3 ⚪ Low. Every row is [1/4] as
consolidated, but see the merge note below the table.

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [1/4] | 🟠 | FIX: Non-zero Bob exits are told to retry the CLI here, but step 5 sends exits 3/4 to the Claude fallback and the PRD requires exit 3 to fall back without a retry; define explicit precedence so the wrong dispatch path cannot run | skills/review-work-completion/references/agent-invocation.md:45 | 2 | BOB |
| [1/4] | 🟡 | FIX: Dispatch closeout is conditioned on reading an output file even though terminal failures may publish none, and a failed retry cannot record both `retry` and `exit <n>` using one `--detail`; close every terminal dispatch and provide a mutually exclusive outcome table | skills/review-work-completion/SKILL.md:366 | 3 | BOB |
| [1/4] | 🟡 | FIX: Bob now mandates `cat`/`sed`/`rg`/`ls`, but his native fallback exposes only `Read` and the registry still says his prompt forbids commands; adapt the fallback instructions and update the stale registry rationale | skills/review-work-completion/references/agent-registry.md:32 | 1 | BOB |
| [1/4] | 🟡 | FIX: The prose tests do not pin ledger closure/outcomes, the ALL-THREE conjunction, exact inlined blocks, output-path reuse, or omission of `--resume-thread`, so several introduced behaviors can regress while all tests pass | skills/review-work-completion/scripts/test_retry_policy_prose.py:53 | 4 | BOB |
| [1/4] | 🟡 | FIX: The unrelated Python-first UUID fallback is not pinned; the existing test checks only that `pat_session_id` exists, so reversing the fallback order would pass | skills/work/SKILL.md:427 | general | BOB |
| [1/4] | 🟡 | FIX: Eleven single-assert methods carry comments that largely repeat their descriptive names and assertions; use table-driven `subTest` cases and retain only comments explaining non-obvious invariants | skills/review-work-completion/scripts/test_retry_policy_prose.py:53 | 4 | BOB |
| [1/4] | 🟡 | FIX: The refusal predicate and retry assembly are dense single paragraphs; replace them with three numbered gates and ordered assembly steps while preserving every required literal | skills/review-work-completion/references/retry-policy.md:23 | 2 | BOB |
| [1/4] | ⚪ | Phase 1 Task 2 says to add "the `after one retry (inlined)` wording for the Bob section" to SKILL.md alongside the ledger sentences; that exact phrase exists only in retry-policy.md (line 54), never in SKILL.md's own step 6/8 review-file/consolidation instructions. Not caught by the Phase 1 acceptance `rg` checks or by test_retry_policy_prose.py. | skills/review-work-completion/SKILL.md | Phase 1 | BLAKE |
| [1/4] | ⚪ | The replacement sentence in agent-invocation.md ("On a non-zero exit or a lack-of-input refusal, retry once per retry-policy.md § Lack-of-input refusal (Bob)") is copied verbatim from the PRD, but retry-policy.md's "Lack-of-input refusal (Bob)" section only defines the specific three-`rg`-check refusal shape, not a generic non-zero-exit trigger — so a driver following this sentence for a non-zero exit that is not exit 3 has no defined procedure. PRD-authored ambiguity carried faithfully into the implementation. | skills/review-work-completion/references/agent-invocation.md | Phase 1 | BLAKE |
| [1/4] | ⚪ | Cannot statically verify: VERIFY — `bash dev/bin/release-checks` passes at the reviewed HEAD; run that exact command | N/A | 4 | BOB |

**Merge note (decision gate).** `consolidate_findings.py` kept Bob's 🟠 row and
Blake's second ⚪ row separate because their wordings share no file *path* string
(Bob cites `agent-invocation.md:45`, Blake cites `agent-invocation.md`). They are
**one defect**: the same replaced sentence, the same contradiction with SKILL.md
step 5. The decision gate merges them at **2/4 consensus, 🟠 High** (higher
severity wins). This is the one finding blocking convergence.

**Verified against the repo, not taken on trust.** `agent-invocation.md:45` does
end with "On a non-zero exit or a lack-of-input refusal, retry once per
retry-policy.md § Lack-of-input refusal (Bob)", while `retry-policy.md` §
Lack-of-input refusal (Bob) defines only the three-`rg`-check shape and names a
non-zero exit merely as one of the *existing* triggers. SKILL.md step 5 routes
exit 3 to the Claude fallback and exit 4 to sidecar salvage. A driver following
line 45 literally would retry the codex CLI on exit 3. Confirmed, not plausible.

**Fix constraint for the rework.** The PRD acceptance criterion
`rg -c 'Lack-of-input refusal' skills/review-work-completion/references/agent-invocation.md`
must print **1**. Any precedence clause added there must NOT repeat that phrase,
or it breaks the PRD's own acceptance check and `test_retry_policy_prose.py`.

## Alice (consensus lens)

`[ALICE] ✅ No issues found`

Alice independently re-ran all twelve PRD acceptance commands, confirmed the
persona/section texts are byte-for-byte the PRD's verbatim contracts, verified
the `record_dispatch.py` flags used in the prose match the script's real
`argparse` definition (`skills/work/scripts/record_dispatch.py:119-140`) and that
`--kind` is free text, and confirmed the `_section` helper bounds each section
correctly against the real file content. She checked the revert/re-land pair
(`7ccaa57`/`3fc1b0c`) nets out identically to `9704638`.

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

## Blake (blind lens, PRD-only)

Two ⚪ Low findings (both in the table above); all nineteen rules pass. Blake ran
the PRD's acceptance `rg` commands live and reports `test_agent_registry.py` (112
tests) and `test_retry_policy_prose.py` (11 tests) green, `bash dev/bin/release-checks`
green, all three CHANGELOG entries present, and no scope creep (no PRD-00180
stdin work, no new flags, no files outside the PRD's declared Repository
Structure).

B1: pass
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
B15: pass
B16: pass
B17: pass
B18: pass
B19: pass

## Bob (doubt + de-slop lens, codex)

Seven `[BOB]` issue lines (1 🟠, 6 🟡) plus one ⚪ VERIFY line — all in the table
above. First dispatch, no retry.

R1: fail
R2: pass
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

**On Bob's four `R` fails.** R1/R4/R9/R10 are his own scoring against findings the
gate has now classified; they are recorded verbatim above and are not
independently re-adjudicated here. Alice and Carl both pass all twelve, and
Blake passes all nineteen, so no rubric rule fails across the panel by
consensus. Bob's R-fails track the same seven findings already in the table
rather than adding new ones.

## Carl (gemini)

`[CARL] ✅ No issues found` — backend `copilot`, model `gemini-3.8-flash`.

Carl read the context and diff, ran `bash dev/bin/release-checks` (twice, once
with the nested-dispatch env vars unset), checked the diff for TODO/FIXME/debug
markers, and rendered `retry-policy.md` lines 25-55 through the GitHub markdown
API to confirm the ```` ```diff ```` fence prose renders correctly.

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

## Mechanical checks (computed, not reviewer opinion)

- **Function line counts** (`compute_mech_facts.py`): one Python file changed,
  `test_retry_policy_prose.py`; largest function 12 lines (`setUpClass`). Every
  function is well under the 50-line limit — R12 pass is a computed fact.
- **Tautological test shapes** (`detect_tautological_tests.py`): 11 test
  functions checked in 1 file, **zero** `[MECH]` lines.
- **Fail-first replay** (`replay_tests_against_base.py`): 11 touched tests ran
  against the pre-change code at `560f061a1bd5`; **11 failed, 0 passed**. Every
  new test genuinely pins this change — R2 pass is a computed fact, not a
  judgement.

No `[MECH]` findings existed to absorb into the table.

## Verification-check queue

**No queue file written this cycle**, deliberately. Bob emitted one ⚪ line
prefixed `VERIFY —`, but the queue is sourced from a doubt lens that emits real
FIX/VERIFY/KNOWN buckets — Eve, or a lane standing in for her
(`references/output-formats.md` § Verification-check queue: `"bob"` is a
*reserved* source, because `agents/bob.md` defines no VERIFY bucket). Eve did not
run: the codex doubt-roster guard did not fire, so she was not on the roster.

Bob's one VERIFY item is answered by the recorded verification rather than
queued: `dev/local/autopilot/last-verification.json` holds
`bash dev/bin/release-checks` → exit 0 at sha `fa95ae09e04e6c6f82cefbad329f74f16924d127`,
which is exactly the reviewed HEAD. The decision gate discards it on that
verified basis.

## Follow-up tasks

Task creation for this cycle is owned by the run-autopilot Phase 6 "Dispatch
rework" contract, not by this skill's step 7: Phase 6 requires the `[C1]`/`[D1]`
prefixes, the `### Findings (verbatim)` block and registration in
`state.rework_task_ids`, none of which step 7's format carries. Creating them
here as well would double-create. They are created once, in Phase 6, and listed
in the decision-gate minutes appended below.

Verdict: 10 findings
Tests: 235 passed, 0 failed, 0 skipped (reused from last-verification.json at fa95ae09e04e6c6f82cefbad329f74f16924d127)
