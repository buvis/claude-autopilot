---
prd: dev/local/prds/wip/00178-fix-bob-first-run-and-specify-his-retry-v1.md
review: 2
date: 2026-09-06
head_sha: 0453db981cd51fd68e90dc3a168305311dd1dbd2
codex_thread_id: 01a077e5-3a6d-7eb0-904e-dca99dba18e3
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00178-fix-bob-first-run-and-specify-his-retry-v1 (cycle 2)

Diff range: `fa95ae09e04e6c6f82cefbad329f74f16924d127..0453db981cd51fd68e90dc3a168305311dd1dbd2`
(incremental — the three `[D1]` rework commits only; cycle 1 reviewed the full work range)

codex_rung_guard: not fired

pack: failed (`engram pack` exited 1: "not inside a registered repo; register it in
/Users/bob/.config/gita/repos.csv"). Not retried — same deterministic registration
precondition cycle 1 recorded, not a transient error. `{PACK_FILE}` and `{PACK_FINDINGS}`
were substituted with `(no pack available this cycle)` in every prompt that takes them.
The review is degraded on retrieval context, not invalid.

## Reviewer status

- Alice: ✅ Available (Claude subagent, consensus lens; 2 findings, R1 fail)
- Blake: ✅ Available (Claude subagent, blind/PRD-only lens; clean, B1-B19 all pass)
- Bob: ✅ Available (codex CLI, doubt + de-slop lens; exit 0, **first dispatch, no retry**;
  5 findings, R1/R2/R4/R9/R10 fail, D1-D5 all pass)
- Carl: ✅ Available (gemini via `backend=copilot model=gemini-3.8-flash`; exit 0; clean, R1-R13 all pass)

### Deviation recorded — Bob's prompt was hand-patched, so this run does NOT vindicate the installed persona

The batch runs the **installed** pack (`autopilot/0.5.1`), whose `agents/bob.md` still
carries the pre-PRD-00178 sandbox wording (`Do NOT attempt to run commands`) — this PRD's
fix lives in the working tree and needs a release to take effect. Assembling Bob's prompt
from the installed persona verbatim would have reproduced the exact refusal this PRD exists
to fix.

So the assembled prompt substituted the persona's `Do NOT attempt to run commands` line
with the working tree's own replacement wording (read-only shell reads are permitted; never
report an inability to read a file you were told to read). **Bob then read his context and
diff on the first dispatch and produced a full review.**

Read honestly, that is evidence *for* the PRD's fix, not evidence that the installed
persona works: the fixed wording produced a clean first run. It is not the post-release
signal PRD Success Metric 1 describes, which can only be measured after a release.

### Retry-trigger evaluation (PRD 00178's own new policy, exercised live)

The three `rg -c` checks were run against `bob-output-00178-c2.txt`:

| check | result |
|-------|--------|
| `rg -c '^R[0-9]+: pass'` | **7** (exit 0) |
| `rg -c '^\[BOB\] (🔴\|🟠\|🟡\|✅)'` | **4** (exit 0) |
| `rg -c '^\[BOB\] ⚪ Cannot statically verify'` | **0** (exit 1) |

The ALL-THREE conjunction does not hold, so this is **not** a lack-of-input refusal.
Bob was dispatched exactly once; no retry prompt was assembled.

### Ledger rows (PRD 00178's other new behavior, exercised live)

Both CLI reviewers opened and closed a `record_dispatch.py` row under task `review-00178-c2`:

```
{"id":"28fb15a7","kind":"bob","task":"review-00178-c2","queued_at":1788717787,"prompt_bytes":11829}
{"id":"9eef1594","kind":"carl","task":"review-00178-c2","queued_at":1788717789,"prompt_bytes":9755}
```

Both closed `--outcome ok`. Exactly one `bob` start row, as PRD Success Metric 1 requires.

## Consolidated Findings

7 findings. Severity split: **0 🔴 Critical, 0 🟠 High**, 6 🟡 Medium, 1 ⚪ Low.

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [1/4] | 🟡 | No test pins the new exit-routing precedence text (exit 3/4 own their fallback path, never a CLI retry) that fixes the cycle-1 High finding; a future edit could silently reintroduce the ambiguous dispatch routing with all 235 tests still green. | skills/review-work-completion/references/agent-invocation.md | 5 | ALICE |
| [1/4] | 🟡 | The `bob, pat` tools-table row's new trailing sentence ("Neither is asked to locate code, so `Read` covers the native lane.") restates the same point the new paragraph immediately below already makes ("he is never told to go find code, which is the one thing those lanes need `rg` for"); drop one. | skills/review-work-completion/references/agent-registry.md | 6 | ALICE |
| [1/4] | 🟡 | FIX: Bob's native fallback still receives the exact persona that mandates shell reads, while its only tool is `Read`; the registry merely describes an override that never reaches the agent. Add the Read-tool override to the fallback dispatch or grant it Bash | skills/review-work-completion/references/agent-registry.md:44 | 6 | BOB |
| [1/4] | 🟡 | FIX: The closeout table has no matching state for exit-0 output with malformed issue lines or incomplete verdicts, although both trigger retries; initial and failed-retry dispatch rows can therefore remain open. Add explicit error/detail rows for both states | skills/review-work-completion/SKILL.md:368 | 7 | BOB |
| [1/4] | 🟡 | FIX: The cycle-2 precedence and native-fallback contracts have no fail-first regression coverage—the unchanged suite passes at the pre-rework base. Add assertions for exit-3/4 precedence and the actual native Read override | skills/review-work-completion/scripts/test_retry_policy_prose.py:93 | general | BOB |
| [1/4] | 🟡 | FIX: The new exit-routing rule compresses four branches and prompt-selection behavior into one dense paragraph; replace it with a trigger/routing/retry-prompt table while preserving the pinned cross-reference count | skills/review-work-completion/references/agent-invocation.md:47 | 5 | BOB |
| [1/4] | ⚪ | FIX: The retry annotation is recorded only when the inlined retry produced verdicts, but the PRD requires it whenever that retry ran; key the annotation on dispatch occurrence so failed retries are also visible | skills/review-work-completion/SKILL.md:450 | 7 | BOB |

**Merge note (decision gate).** `consolidate_findings.py` kept Alice's row 1 and Bob's row 5
separate because their `File` strings differ (`agent-invocation.md` vs
`test_retry_policy_prose.py:93`). They are **one defect**: the cycle-2 rework text is not
pinned by any assertion. The decision gate merges them at **2/4 consensus, 🟡 Medium**.

**Cycle-1 findings — all four verified resolved.** Alice checked each against the code and
ran every hard-constraint `rg -c`; Carl independently ran all six and the full suite. The
🟠 High (exit-routing precedence), both 🟡 Mediums (registry rationale, ledger closeout) and
the ⚪ Low (`after one retry (inlined)` wording) are closed. No regression was found in the
rework, and no reviewer re-raised a settled cycle-1 deferral.

**Auto-dismissed (ledger).** None. Blake reported no findings, so the `--ledger-dismiss BLAKE`
filter had nothing to match.

## Alice

Read the context file, the diff, and the referenced sources in full. Verified all four
cycle-1 findings resolved, cross-checked the new `agent-invocation.md` precedence paragraph
against SKILL.md's actual "Bob fallback" prose (consistent), confirmed `agents/bob.md` was
not touched per task 6's constraint, and verified the new closeout `--detail` encoding
against `record_dispatch.py`'s argparse (`--outcome` choices `ok|error`, `--detail` free text).
All hard-constraint `rg -c` counts verified directly and match exactly.
`pytest` on `test_retry_policy_prose.py` + `test_agent_registry.py`: 123 passed.

Two gaps found, both non-blocking prose issues:

```
[ALICE] 🟡 No test pins the new exit-routing precedence text (exit 3/4 own their fallback path, never a CLI retry) that fixes the cycle-1 High finding; a future edit could silently reintroduce the ambiguous dispatch routing with all 235 tests still green. | File: skills/review-work-completion/references/agent-invocation.md | Task: 5
[ALICE] 🟡 The `bob, pat` tools-table row's new trailing sentence ("Neither is asked to locate code, so `Read` covers the native lane.") restates the same point the new paragraph immediately below already makes ("he is never told to go find code, which is the one thing those lanes need `rg` for"); drop one. | File: skills/review-work-completion/references/agent-registry.md | Task: 6
R1: fail
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
```

## Blake

Blind lens, PRD-only. Located the code himself and verified every acceptance criterion in
Phases 0, 1 and 2. Confirmed `--kind` is free text in `record_dispatch.py` (no `choices`
constraint), matching the PRD's claim that no script change is needed. Confirmed the persona
text, both retry-policy sections (including the exact `rg -c` commands and the head/mid
blocks), the SKILL.md ledger sentences in steps 5 and 6 with all three outcome forms, and the
CHANGELOG entries. Ran `bash dev/bin/release-checks` green across all four check blocks
including the new `[checks] retry policy prose` block. No out-of-scope code, no new
dependencies, no script signature changes.

```
[BLAKE] ✅ No issues found

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
```

## Bob

Doubt + de-slop lens (codex, exit 0, first dispatch, no retry). Prompt hand-patched per the
deviation recorded above.

```
[BOB] 🟡 FIX: Bob's native fallback still receives the exact persona that mandates shell reads, while its only tool is `Read`; the registry merely describes an override that never reaches the agent. Add the Read-tool override to the fallback dispatch or grant it Bash | File: skills/review-work-completion/references/agent-registry.md:44 | Task: 6
[BOB] 🟡 FIX: The closeout table has no matching state for exit-0 output with malformed issue lines or incomplete verdicts, although both trigger retries; initial and failed-retry dispatch rows can therefore remain open. Add explicit error/detail rows for both states | File: skills/review-work-completion/SKILL.md:368 | Task: 7
[BOB] 🟡 FIX: The cycle-2 precedence and native-fallback contracts have no fail-first regression coverage—the unchanged suite passes at the pre-rework base. Add assertions for exit-3/4 precedence and the actual native Read override | File: skills/review-work-completion/scripts/test_retry_policy_prose.py:93 | Task: general
[BOB] 🟡 FIX: The new exit-routing rule compresses four branches and prompt-selection behavior into one dense paragraph; replace it with a trigger/routing/retry-prompt table while preserving the pinned cross-reference count | File: skills/review-work-completion/references/agent-invocation.md:47 | Task: 5
[BOB] ⚪ FIX: The retry annotation is recorded only when the inlined retry produced verdicts, but the PRD requires it whenever that retry ran; key the annotation on dispatch occurrence so failed retries are also visible | File: skills/review-work-completion/SKILL.md:450 | Task: 7
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

**On Bob's R-fails.** R1/R2 (test coverage, tautology) are the substantive ones and are
carried into the sweep as the merged unpinned-rework-text finding. R4 (integration),
R9 (matches PRD behavior exactly) and R10 (error handling) are marked fail on the strength
of his own findings 1 and 2 — the inert native-fallback override and the closeout table's
missing states. Blake, reviewing the same PRD blind, passed every equivalent rule after
running the acceptance checks himself, and Alice and Carl both passed R4/R9/R10. Bob's
reading is the strictest of the four; it is recorded, and the two underlying findings are
swept rather than dismissed.

**No verification-check queue written this cycle.** The queue sources only from a doubt lens
that emits real FIX/VERIFY/KNOWN buckets. Bob's persona mandates the `[BOB]` issue-line
format and `R{n}`/`D{n}` verdicts and defines no buckets — his inline `FIX:` prefixes are not
bucket sections — and `output-formats.md` reserves `source: bob` for a persona that later
gains them. Eve did not run because the codex doubt-roster guard did not fire (no task in
this PRD had a `codex` implementor).

## Carl

Generalist review (no frontend surface in this diff). Independently ran all six
hard-constraint `rg -c` checks, read the changed files plus `record_dispatch.py` and both
test files, and ran `bash dev/bin/release-checks` twice — once plainly, and once with
`env -u COPILOT_CLI -u CODEX_SESSION_ID -u AUTOPILOT_DISPATCH_DEPTH` to clear the dispatch
recursion guard — plus `test_agent_registry.py` and `test_retry_policy_prose.py` under both
`unittest` and `pytest`. Also checked line counts on every touched file against the
800-line limit.

```
[CARL] ✅ No issues found

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
```

## Mechanical checks

All three computed blocks were no-ops this cycle — the diff touches only `.md` files:

- Mechanical facts: 4 files, all skipped (non-python).
- Tautological test shapes: checked 0 test functions in 0 test files.
- Fail-first replay: skipped (the diff touches no test function).

No `[MECH]` lines to absorb into the table.

## Carried-forward checks

None. Cycle 1 wrote no `checks-1.json` queue file (same reason as above — no doubt lens
emitted a VERIFY bucket), so there is nothing to carry forward.

## On the `Tests:` line — deviation from the docs-only rule, recorded

The reviewed diff touches only `.md` files, so step 6's literal rule would write
`Tests: none (docs-only)`. That sentinel was **not** used, deliberately: in this pack the
prose *is* the product, and `test_retry_policy_prose.py` / `test_agent_registry.py` assert
directly on the bytes of the four changed files. A `.md`-only diff here can and does break
the suite, so "docs-only" would have reported no evidence for a change the suite actually
gates. `bash dev/bin/release-checks` was run in full this cycle and its real counts are
below. The PRD's own third success metric is that this command is green.

The reused-record path was not eligible either: `dev/local/autopilot/last-verification.json`
holds `fa95ae09e04e...`, the diff base, not this cycle's HEAD.

Verdict: 7 findings
Tests: 235 passed, 0 failed, 0 skipped (suite run this cycle)
