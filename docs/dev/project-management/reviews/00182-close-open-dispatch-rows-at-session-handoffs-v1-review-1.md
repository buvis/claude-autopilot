---
prd: dev/local/prds/wip/00182-close-open-dispatch-rows-at-session-handoffs-v1.md
review: 1
date: 2026-09-07
head_sha: 095431eaaca3fc826949f03b1c3ab455b8d264a8
codex_thread_id: 01a07946-8ed8-7371-826b-b9cfd1605f35
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00182-close-open-dispatch-rows-at-session-handoffs-v1

Diff range: `9d3e3a12044ef039f5a484959271d5f8a37bf8cb..095431eaaca3fc826949f03b1c3ab455b8d264a8`

codex_rung_guard: not fired

pack: unavailable (`engram pack` exited 1 — repo not registered in `/Users/bob/.config/gita/repos.csv`; not retried, the lookup is deterministic). The review is degraded on retrieval context, not invalid. Blake never receives a pack by design.

## Review Summary

Reviewed: 4 completed tasks
PRDs checked: 00182-close-open-dispatch-rows-at-session-handoffs-v1

### Agent Status

- Alice: ✅ Available (consensus lens)
- Blake: ✅ Available (blind lens, PRD-only)
- Bob: ✅ Available (doubt + de-slop lens, codex — **succeeded on retry**, see below)
- Carl: ✅ Available (backend `copilot`, model `gemini-3.8-flash`)

### Cycle notes (fail-loud)

Four things about this cycle that a reader should not have to infer:

1. **Bob's first dispatch failed and was retried once.** The codex sandbox refused to open the context and diff by path; his first output was a single "artifacts were inaccessible" line plus all twelve `R` rules marked `fail`. Per `references/retry-policy.md` this spent his one retry: `[RETRY] bob attempt 1/1`, re-dispatched with an 81 KB prompt carrying the context and full diff **inlined verbatim**. The retry produced a complete review (7 findings, all 12 `R` and all 5 `D` lines). The retry output at `dev/local/tmp/bob-output-00182-1-retry.txt` is what was consolidated; the failed first output remains at `bob-output-00182-1.txt`.
2. **`gather-context.sh` first produced an EMPTY diff.** Its branch-base detection picked `master`, which is the branch this PRD's work was committed onto, so `git diff master` was empty. Re-run with `--since <work_start_sha>` — the base the skill mandates for a full review under autopilot — giving the correct 1328-line diff. The script then labelled the scope "incremental"; that label was corrected in the context file to "full review". Tooling gap in the script, surfaced for the batch report, not fixed inside this PRD.
3. **Consolidation was corrected by hand at the decision gate.** `consolidate_findings.py` ran successfully and emitted 13 rows, but its same-file merge rule was defeated by the line-number suffix Bob appends to `File:` values (`record_dispatch.py` vs `record_dispatch.py:151`). Three defects were each reported by two reviewers in different words and stayed split. They are merged below, taking the higher severity — which raised two of them to **[2/4] 🟠 High**. The merges are named explicitly in the table so nothing is silent.
4. **No verification-check queue was written this cycle.** Eve did not run (the codex doubt-roster guard did not fire), and `references/output-formats.md` reserves `source: "bob"` — the Bob persona defines no VERIFY bucket. Bob's two `⚪ VERIFY` items were therefore classified as ordinary findings, and both are answered by the recorded verification at this exact HEAD (see Discarded, below).

## Consolidated Findings

13 raw rows → **9 findings** after merging paraphrases.

| Consensus | Severity | Issue | File | Found By |
|-----------|----------|-------|------|----------|
| [2/4] | 🟠 High | The PRD's named acceptance tests were relocated out of `test_record_dispatch.py` by the style gate, so the PRD's own literal verification commands collect none of them. `pytest -q skills/work/scripts/test_record_dispatch.py -k open_ids` exits 5 ("10 deselected"). The Success Metrics command passes but never runs three of the five tests the PRD names. | skills/work/scripts/test_record_dispatch.py | Blake, Bob |
| [2/4] | 🟠 High | `open_ids()` and `_spans_handoff()` catch only `FileNotFoundError`, unlike `_queued_at()` in the same module which also catches `OSError` and degrades gracefully. An unreadable or non-UTF-8 ledger propagates an unhandled exception out of the `handoff` verb — invoked at every session leave/resume — breaking the module's documented "a telemetry failure is never a dispatch failure". Not covered by any test. | skills/work/scripts/record_dispatch.py | Blake, Bob |
| [2/4] | 🟡 Medium | `_spans_handoff` duplicates `_queued_at`'s read/parse/skip-count loop verbatim; both re-read the same working file, so one `end` call prints the "skipped N unparseable line(s)" warning twice. Extract one shared line-reader used by all three scan functions. | skills/work/scripts/record_dispatch.py | Alice, Bob |
| [1/4] | 🟡 Medium | The `resume` edge is exercised only with an already-closed row; a regression closing open rows on `leave` alone would still pass. Add an open-row `resume` case asserting the lost row precedes the handoff row. | skills/work/scripts/test_record_dispatch_handoff.py | Bob |
| [1/4] | 🟡 Medium | The row-catalogue table still says `elapsed_s` is null only when no start row exists, while the new prose adds another case, and it omits that the handoff timestamp must fall strictly between the endpoints. | skills/work/references/subagent-dispatch.md | Bob |
| [1/4] | ⚪ Low | Commit `1f045ca` also reflows two unrelated spots (the `open_ids` boolean condition, the `--prompt-file` argparse call). **Discarded** — see below. | skills/work/scripts/record_dispatch.py | Alice |
| [1/4] | ⚪ Low | `dev/bin/release-checks` never invokes `test_record_dispatch*.py`, so the PRD's Phase 2 exit criterion is a vacuous gate. **Deferred** — see below. | dev/bin/release-checks | Blake |
| [1/4] | ⚪ Low | VERIFY — cannot statically verify the full test suite. **Discarded** — see below. | N/A | Bob |
| [1/4] | ⚪ Low | VERIFY — cannot statically verify the release gate. **Discarded** — see below. | N/A | Bob |

### Merges applied by hand

- Row 1 absorbs three raw rows: Blake's 🟠 "Phase 0's literal Exit Criteria command fails", Bob's 🟠 "Task 1 and Task 2 acceptance tests were moved out", and Blake's 🟡 "Success Metrics claim is false as literally written". One defect, two commands, one root cause.
- Row 2 absorbs Blake's 🟡 `FileNotFoundError` finding and Bob's 🟠 `open_ids` finding. Severity taken as the higher of the two (🟠).
- Row 3 absorbs Alice's 🟡 duplicate-loop finding and Bob's 🟡 double-warning finding.

### Independently confirmed at the decision gate

Both High findings were verified directly rather than taken on the reviewers' word:

```
$ uv run --no-project --with pytest python -m pytest -q skills/work/scripts/test_record_dispatch.py -k open_ids
10 deselected in 0.01s
EXIT=5
```

```
$ rg -n "FileNotFoundError|OSError" skills/work/scripts/record_dispatch.py
89:    except FileNotFoundError:      # _queued_at
91:    except OSError as err:         # _queued_at — present
126:    except FileNotFoundError:     # _spans_handoff — no OSError branch
157:    except FileNotFoundError:     # open_ids — no OSError branch
```

### Discarded (with reason)

- **Formatter churn in `1f045ca`** (Alice, ⚪): contradicts the attempt record. Those wraps are the repo's own style gate's output — task 2's attempt carries `style_gate: fixed:0647aa4`, task 1's carries `fixed:bc49cf9`. Reverting them would re-trip the gate.
- **Bob's two ⚪ VERIFY items**: already answered at this exact HEAD. `dev/local/autopilot/last-verification.json` at sha `095431e` records 895 passed / 0 failed / 0 skipped and `bash dev/bin/release-checks` exit 0; Alice, Blake and Carl each ran suites green independently this cycle (Blake: 594 passed, 1 skipped across all of `skills/work/scripts/`). Bob's sandbox blocks execution by design, so these are sandbox limits, not defects.

### Deferred to batch end

- **`release-checks` is a vacuous gate for this PRD** (Blake, ⚪): Blake states himself it is pre-existing and not introduced here. Changing what the repo's release gate runs is a repo-wide decision outside PRD 00182's Structural Decomposition, which names only `record_dispatch.py`, its tests, `subagent-dispatch.md` and `CHANGELOG.md`. Recorded in `deferred/202609061630-deferred.json`.

## Follow-up Tasks Created

1. `[D1] Guard the ledger reads against OSError and read the file once per end call` (M) — 🟠 [2/4] + 🟡 [2/4] — addresses rows 2 and 3
2. `[D1] Restore the PRD-named acceptance tests to test_record_dispatch.py and pin the resume edge` (M) — 🟠 [2/4] + 🟡 — addresses rows 1 and 4
3. `[D1] Correct the row-catalogue null-elapsed definition in subagent-dispatch.md` (S) — 🟡 — addresses row 5

All three are decision-gate follow-ups (first-pass work, not retries), tier `sonnet` after the PRD's `default_model: sonnet` floor.

## Alice

Implementation-aware consensus lens. Read the context and diff, inspected `record_dispatch.py`, ran the touched test files (29 passed) and `bash dev/bin/release-checks` (green), verified both of task 4's acceptance `rg` greps return exactly one hit, and reproduced the duplicate-stderr behavior by hand.

```
[ALICE] 🟡 `_spans_handoff` duplicates `_queued_at`'s file-read/parse/skip-count loop verbatim instead of sharing it; both independently re-read the same working file, so an unparseable line's "skipped 1 unparseable line(s)" warning is printed twice in one `end` call. Extract one shared line-reader used by `_queued_at`, `_spans_handoff`, and `open_ids`. | File: skills/work/scripts/record_dispatch.py | Task: 3
[ALICE] ⚪ Commit 1f045ca (task 2) also reflows two unrelated spots with no functional link to the task: the `open_ids` boolean condition and the `--prompt-file` argparse call. Incidental formatter churn, not requested by the task. | File: skills/work/scripts/record_dispatch.py | Task: 2
```

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

## Blake

Blind lens — PRD only, no diff, no file list, no review history. Located the code himself. Ran the full `skills/work/scripts/` suite (594 passed, 1 skipped) and `dev/bin/release-checks` (exit 0), and confirmed both acceptance greps return one hit each. Judged the core behavior (`open_ids`, the `handoff` close, the `end` boundary rule) correct and matching the documented row shapes.

```
[BLAKE] 🟠 Phase 0's literal Exit Criteria command fails as written: `python -m pytest -q skills/work/scripts/test_record_dispatch.py -k open_ids` exits 5 ("10 deselected", no tests collected) because `test_open_ids_lists_only_unclosed_starts` lives in `test_record_dispatch_open_ids.py`, not `test_record_dispatch.py`. Verified by running the command verbatim. | File: skills/work/scripts/test_record_dispatch_open_ids.py | Task: general
[BLAKE] 🟡 Success Metrics claim is false as literally written: the PRD's own command passes (10 passed) but does not execute three of its five named tests, because they live in sibling files. | File: skills/work/scripts/test_record_dispatch.py | Task: general
[BLAKE] 🟡 `open_ids()` and `_spans_handoff()` catch only `FileNotFoundError`, unlike `_queued_at()` which also catches `OSError`. A permission error or non-UTF-8 byte would propagate out of the `handoff` verb instead of the documented best-effort behavior. Not covered by any test. | File: skills/work/scripts/record_dispatch.py | Task: general
[BLAKE] ⚪ `dev/bin/release-checks` never invokes `test_record_dispatch*.py`, so "release-checks passes" is a vacuous gate for this PRD's changes. Pre-existing gap. | File: dev/bin/release-checks | Task: general
```

B1: fail
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
B14: fail
B15: pass
B16: pass
B17: pass
B18: pass
B19: pass

## Bob

Doubt + de-slop lens (codex, static-only sandbox). First dispatch failed on path access; this is the retry, run against a fully inlined prompt. Thread id `01a07946-8ed8-7371-826b-b9cfd1605f35`.

```
[BOB] 🟠 FIX — `open_ids` catches only `FileNotFoundError`; an unreadable or directory-valued metrics path now aborts `handoff` before its best-effort append path. Catch `OSError`, report it, return an empty list, and test this handoff error path. | File: skills/work/scripts/record_dispatch.py:151 | Task: general
[BOB] 🟠 FIX — Task 1 and Task 2 acceptance tests were moved out of `test_record_dispatch.py`, so their mandated `pytest ... test_record_dispatch.py -k ...` verification commands collect no tests and fail. Keep the named acceptance tests in that module and move older tests instead. | File: skills/work/scripts/test_record_dispatch.py:13 | Task: general
[BOB] 🟡 FIX — The resume edge is exercised only with an already-closed row; a regression that closes open rows only on `leave` would pass. Add an open-row `resume` case asserting the lost row precedes the handoff row. | File: skills/work/scripts/test_record_dispatch_handoff.py:109 | Task: 2
[BOB] 🟡 FIX — Every successful `end` lookup rereads and reparses the ledger in `_spans_handoff`; malformed lines consequently emit the same skipped-line warning twice. Parse once for both calculations, or give one scan sole ownership of the warning. | File: skills/work/scripts/record_dispatch.py:119 | Task: 3
[BOB] 🟡 FIX — The row-catalogue table still says `elapsed_s` is null only when no start exists, while the new prose adds another case and omits that the handoff timestamp must be strictly between the endpoints. Update the table definition and make the boundary explicit. | File: skills/work/references/subagent-dispatch.md:185 | Task: 4
[BOB] ⚪ VERIFY — Cannot statically verify the full test suite; run `uv run --no-project --with pytest python -m pytest`. | File: N/A | Task: general
[BOB] ⚪ VERIFY — Cannot statically verify the release gate; run `bash dev/bin/release-checks`. | File: N/A | Task: general
```

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

## Carl

Backend `copilot`, model `gemini-3.8-flash`. Read the context and the full diff, ran `uv run --no-project --with pytest python -m pytest skills/work/scripts` and `bash dev/bin/release-checks` (both green), read `record_dispatch.py` in full, inspected commit `0437bb8`, checked both acceptance greps, traced `record_dispatch` call sites across the pack, and grepped the diff for TODO/FIXME/debug prints.

```
[CARL] ✅ No issues found
```

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

## Mechanical checks (computed)

- **Tautological test shapes**: none found across 24 test functions in 5 test files.
- **Fail-first replay**: 0 touched tests ran; all 5 changed test files could not even be collected against base `9d3e3a12044e` (they fail there). No test passes against the pre-change code, so nothing is unpinned by this measure.
- **Mechanical facts**: every function in the diff is within the 50-line limit — largest are `test_handoff_leaves_closed_rows_alone` (45), `test_handoff_closes_open_rows_as_lost` (43) and `test_end_after_handoff_reports_null_elapsed` (42). No finding contradicted this block.

Verdict: 9 findings
Tests: 895 passed, 0 failed, 0 skipped (reused from last-verification.json at 095431eaaca3fc826949f03b1c3ab455b8d264a8)
