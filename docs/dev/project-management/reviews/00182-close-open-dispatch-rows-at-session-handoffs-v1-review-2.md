---
prd: dev/local/prds/wip/00182-close-open-dispatch-rows-at-session-handoffs-v1.md
review: 2
date: 2026-09-07
head_sha: a026540ab0bb2efc5a3f439870668a4609936faa
codex_thread_id: 01a07946-8ed8-7371-826b-b9cfd1605f35
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00182-close-open-dispatch-rows-at-session-handoffs-v1

Diff range: `095431eaaca3fc826949f03b1c3ab455b8d264a8..a026540ab0bb2efc5a3f439870668a4609936faa`

codex_rung_guard: not fired

pack: unavailable (`engram pack` exited 1 — repo not registered in `/Users/bob/.config/gita/repos.csv`; retried once at the start of this cycle, same deterministic failure). The review is degraded on retrieval context, not invalid. Blake never receives a pack by design.

## Review Summary

Reviewed: 7 completed tasks (4 original-plan, 3 `[D1]` rework follow-ups)
PRDs checked: 00182-close-open-dispatch-rows-at-session-handoffs-v1

This is an **incremental** cycle: the diff covers only the five rework commits
`5ebd59c`, `6273c54`, `9d6bdef`, `5a5daa8`, `a026540`. Cycle 1 reviewed the full
implementation.

### Agent Status

- Alice: ✅ Available (consensus lens)
- Blake: ✅ Available (blind lens, PRD-only)
- Bob: ✅ Available (doubt + de-slop lens, codex — **resumed cycle-1 thread** `01a07946-8ed8-7371-826b-b9cfd1605f35`, first dispatch succeeded)
- Carl: ✅ Available (backend `copilot`, model `gemini-3.8-flash`)

### Cycle notes (fail-loud)

1. **All five cycle-1 findings are closed.** Alice and Blake each verified this
   independently, by running the PRD's own literal commands rather than reading
   the diff: `pytest -q skills/work/scripts/test_record_dispatch.py -k open_ids`
   now collects and passes (1 passed, 13 deselected — it exited 5 last cycle),
   the whole file runs 14 passed with all five PRD-named acceptance tests in it,
   and `bash dev/bin/release-checks` exits 0.
2. **Bob's prompt was inlined verbatim from the start this cycle.** Cycle 1 spent
   his one retry discovering that the codex sandbox cannot open the context and
   diff by path. This cycle's 69 KB prompt carried both inline, and his first
   dispatch produced a complete review (4 findings, all 12 `R` and all 5 `D`
   lines). No retry spent.
3. **Bob's `File:` values carry no line-number suffix this cycle.** That suffix
   defeated `consolidate_findings.py`'s same-file merge in cycle 1 and forced a
   hand-merge; his prompt was amended to forbid it, and consolidation ran clean.
4. **The fail-first replay flagged six touched tests, and they split two ways.**
   Four are cycle-1 tests that task 6 *relocated* between modules, so they pass
   against this range's base by construction — discarded with reason below. The
   fifth is the same relocation case. The sixth is real signal and is swept.
5. **No verification-check queue was written this cycle.** Eve did not run (the
   codex doubt-roster guard did not fire, 0 codex-implemented tasks), and
   `references/output-formats.md` reserves `source: "bob"`. Bob emitted no VERIFY
   items this cycle in any case — all four of his findings are FIX.

## Consolidated Findings

7 consolidated rows + 2 absorbed `[MECH]` rows → **9 findings**, none above 🟡 Medium.

| Consensus | Severity | Issue | File | Found By |
|-----------|----------|-------|------|----------|
| [2/4] | 🟡 Medium | The new `end` read-failure test uses a directory-valued ledger, so appending is impossible and it cannot assert the end row that the fix must still write. Replace it with a non-UTF-8 ledger case asserting exit 0, one read-failure diagnostic, no "no start row" diagnostic, and an appended null-elapsed end row. | skills/work/scripts/test_record_dispatch_read_failures.py | Bob, mech-check |
| [1/4] | 🟡 Medium | The new CHANGELOG bullet's third clause claims `end` read failures no longer also report "no start row", but that double message never shipped: it was a transient regression introduced by `6273c54` and fixed by `9d6bdef`, both inside this unreleased range. Remove the release-facing claim, keep its regression test. | CHANGELOG.md | Bob |
| [1/4] | 🟡 Medium | `_queued_at` keeps a `found` sentinel and walks every remaining row after the first valid start, even though `_read_rows` has already finished parsing and diagnostics. Return the first valid `queued_at` directly and emit the missing-start warning after the loop. | skills/work/scripts/record_dispatch.py | Bob |
| [1/4] | 🟡 Medium | Comments at lines 69 and 143 describe the pre-fix implementation in the present tense ("Today that read is unguarded", both helpers "walk the same lines"), contradicting the code they now sit above. | skills/work/scripts/test_record_dispatch_read_failures.py | Bob |
| [1/4] | 🟡 Medium | 4 touched tests pass against the pre-change code: `test_open_ids_lists_only_unclosed_starts`, `test_handoff_closes_open_rows_as_lost`, `test_handoff_resume_closes_open_rows_as_lost`, `test_handoff_leaves_closed_rows_alone`. **Discarded** — see below. | skills/work/scripts/test_record_dispatch.py | mech-check |
| [1/4] | 🟡 Medium | 1 touched test passes against the pre-change code: `test_handoff_writes_its_site_edge_stamp_phase_and_prd`. **Discarded** — see below. | skills/work/scripts/test_record_dispatch_handoff.py | mech-check |
| [1/4] | ⚪ Low | `test_record_dispatch.py`'s module docstring says the file holds only the `end` verb's tests and that handoff/open_ids tests live in siblings, but the file now also holds `test_open_ids_lists_only_unclosed_starts` and three handoff tests — correctly, since the PRD's exit-criteria commands require them there. The docstring is stale, not the placement. | skills/work/scripts/test_record_dispatch.py | Blake |
| [1/4] | ⚪ Low | The PRD's Success Metrics says "the four new tests named below" while Phases 0-1 name five. A PRD-text miscount. **Discarded** — see below. | dev/local/prds/wip/00182-close-open-dispatch-rows-at-session-handoffs-v1.md | Blake |
| [1/4] | ⚪ Low | PRD 00182 is still in `dev/local/prds/wip/` with every task checkbox unchecked. **Discarded** — see below. | dev/local/prds/wip/00182-close-open-dispatch-rows-at-session-handoffs-v1.md | Blake |

### Mech-check absorption

The replay block's third `[MECH]` line names
`test_end_over_an_unreadable_working_file_does_not_also_report_no_start_row` in
`test_record_dispatch_read_failures.py` — the same test and file as Bob's first
finding. Absorbed into that row, raising it to **[2/4]**. The other two `[MECH]`
lines matched no consolidated row and were added as rows of their own.

### Independently confirmed at the decision gate

Both of Bob's factual claims were verified directly rather than taken on his word.

`_queued_at` at the range base (`git show 095431e:skills/work/scripts/record_dispatch.py`)
returns from inside its `except OSError` handler:

```python
    except OSError as err:
        print(f"record_dispatch: start row lookup failed: {err}", file=sys.stderr)
        return None
```

It therefore never reached the `no start row` print after a read failure. The
double message Bob names existed only between `6273c54` (which extracted
`_read_rows` and dropped the early return) and `9d6bdef` (which restored it) —
never in a released state. His CHANGELOG finding is correct.

The `found` sentinel at `record_dispatch.py:124-135` has no `break`, so the loop
does walk every remaining row after the first valid start. Confirmed by reading.

The two stale comments are at `test_record_dispatch_read_failures.py:69-70`
("Today that read is unguarded for OSError and crashes before the row is ever
attempted") and `:145-148` (both helpers "walk the same lines ... prints the same
warning twice"). Both describe code this range replaced. Confirmed by reading.

Blake's docstring finding is confirmed at `test_record_dispatch.py:9-14`.

### Discarded (with reason)

- **Four relocated tests pass against base** (mech-check, 🟡): task 6's whole
  contract was to MOVE these tests between modules without changing them
  ("changes NO production code", "move test bodies verbatim"). They pin behavior
  that landed in cycle 1, before this range's base, so passing at the base is
  what a correct relocation looks like. The replay block itself says a
  behavior-preserving change's tests pass by design.
- **`test_handoff_writes_its_site_edge_stamp_phase_and_prd` passes against base**
  (mech-check, 🟡): same cause. It is a cycle-1 test that task 6 relocated out of
  `test_record_dispatch.py` to stay under the 800-line cap.
- **PRD Success Metrics says "four" where the phases name five** (Blake, ⚪):
  the implementation satisfies all five and all five pass. Editing a PRD's
  Success Metrics after the fact to match what was built is the exact move the
  blind lens exists to catch; the miscount is in the spec's prose, not the code,
  and the PRD closes with this cycle.
- **PRD still in `wip/` with unchecked boxes** (Blake, ⚪): the expected
  mid-flight state. Autopilot's Phase 9 performs the verified `wip/` → `done/`
  move after this review converges. Not a defect.

### Swept to one `[D2]` task (tail sweep)

Five actionable findings, all 🟡/⚪, none blocking convergence: rows 1, 2, 3, 4
and 7 above. They are transcribed verbatim into a single `[D2]` sweep task.

## Alice

Implementation-aware consensus lens. Ran the full `skills/work/scripts/` suite
(601 passed, 1 skipped — the one skip is a pre-existing golden-fixture skip in
`test_check_build_overhead.py`), both PRD exit-criteria commands, `release-checks`
(exit 0), `test_dispatch_telemetry_prose.py` (16 passed), and both acceptance
greps (one hit each). Verified `5a5daa8` touches only test files and `a026540`
only `subagent-dispatch.md`, matching each task's stated constraints. Confirmed
no callers of `_queued_at`, `_spans_handoff`, `_read_rows` or `open_ids` exist
outside the module and its tests, so the public surface is unchanged.

She also checked out `6273c54` in a scratch worktree and overlaid HEAD's
`test_record_dispatch_read_failures.py` to test the replay block's third
`[MECH]` line directly:
`test_end_over_an_unreadable_working_file_does_not_also_report_no_start_row`
genuinely FAILS against the commit `9d6bdef` fixes, even though it passes against
the range's outer base. It is a legitimate fail-first regression test at the
atomic-commit level, not a tautology — which is why row 1 is swept for its
missing end-row assertion rather than for being tautological.

```
[ALICE] ✅ No issues found
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

Blind lens — PRD only, no diff, no file list, no review history. Located the code
himself. Ran the full suite (601 passed, 1 skipped), both literal exit-criteria
pytest invocations, `release-checks` (exit 0), and both acceptance greps (one hit
each: `subagent-dispatch.md:188`, `CHANGELOG.md:21`). Confirmed every one of the
five PRD-named acceptance tests exists verbatim in `test_record_dispatch.py` and
that their fixtures match the PRD's literal examples byte for byte — the
`"detail": "spans handoff; "` trailing space with no suffix, the
`"detail": "open at build/leave handoff"` string, and the strict
`queued_at < at < ended_at` window with both boundary cases tested. Judged
`open_ids`'s missing-file, unreadable and non-UTF-8 paths all to match the
"empty ledger, not a failure" contract, and confirmed no historical-row migration
code exists anywhere, honoring the PRD's stated no-migration risk.

```
[BLAKE] ⚪ test_record_dispatch.py's module docstring says it holds only the `end`-verb's tests and that handoff/open_ids tests live in sibling files, but the file itself also contains test_open_ids_lists_only_unclosed_starts and three handoff tests (correctly, per the PRD's own exit-criteria commands) | File: skills/work/scripts/test_record_dispatch.py | Task: general
[BLAKE] ⚪ PRD's Success Metrics says "the four new tests named below" but the Phase 0/1 tasks actually name five (open_ids, handoff_closes_open_rows_as_lost, handoff_leaves_closed_rows_alone, end_after_handoff_reports_null_elapsed, end_without_handoff_keeps_elapsed); a PRD-text miscount, not an implementation gap since all five exist and pass | File: dev/local/prds/wip/00182-close-open-dispatch-rows-at-session-handoffs-v1.md | Task: general
[BLAKE] ⚪ PRD 00182 is still in dev/local/prds/wip/ with every task checkbox unchecked even though the code, tests, docs and release-checks are all in place and passing; a housekeeping gap, not a code defect | File: dev/local/prds/wip/00182-close-open-dispatch-rows-at-session-handoffs-v1.md | Task: general
```

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

## Bob

Doubt + de-slop lens (codex, static-only sandbox). Resumed his cycle-1 thread, so
he verified the rework against his own prior critique. First dispatch succeeded;
no retry spent.

```
[BOB] 🟡 FIX — At line 120, the new end read-failure test uses a directory-valued ledger, passes against the pre-change code, and cannot verify the required end-row write because appending is impossible. Replace it with a non-UTF-8 ledger case asserting exit 0, one read-failure diagnostic, no “no start row” diagnostic, and an appended null-elapsed end row. | File: skills/work/scripts/test_record_dispatch_read_failures.py | Task: 5
[BOB] 🟡 FIX — The new CHANGELOG bullet claims end read failures no longer also report “no start row,” but fail-first replay proves that behavior already existed at the review base; it was only a transient rework regression. Remove that release-facing claim while retaining its regression test. | File: CHANGELOG.md | Task: 5
[BOB] 🟡 FIX — At line 122, `_queued_at` retains a `found` sentinel and scans every row after finding the first valid start, even though `_read_rows` has already completed parsing and diagnostics. Return the first valid `queued_at` directly, then emit the missing-start warning after the loop. | File: skills/work/scripts/record_dispatch.py | Task: 5
[BOB] 🟡 FIX — Comments around lines 69 and 143 describe the pre-fix implementation in the present tense (“Today that read is unguarded” and both helpers “walk the same lines”), contradicting the reviewed code. Replace them with concise invariant-focused explanations. | File: skills/work/scripts/test_record_dispatch_read_failures.py | Task: 5
```

R1: fail
R2: fail
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

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

Backend `copilot`, model `gemini-3.8-flash`. Read the context and the full diff,
ran both PRD exit-criteria commands, the full `skills/work/scripts/` suite,
`test_dispatch_telemetry_prose.py`, and `release-checks`, read
`record_dispatch.py` in full, inspected the range's `git log -p` for that file,
and checked both acceptance greps.

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

- **Tautological test shapes**: none found across 24 test functions in 4 test files.
- **Fail-first replay**: 11 touched tests ran against base `095431eaaca3`; 5 failed
  there (correctly pinning this range) and 6 passed. Of those 6, five are task 6's
  verbatim relocations and are discarded above; the sixth
  (`test_end_over_an_unreadable_working_file_does_not_also_report_no_start_row`)
  was re-tested by Alice against `6273c54` and does fail there.
- **Mechanical facts**: every function in the diff is within the 50-line limit —
  largest are `test_handoff_leaves_closed_rows_alone` (45),
  `test_handoff_closes_open_rows_as_lost` (43) and
  `test_handoff_resume_closes_open_rows_as_lost` (42). `_read_rows` is 35 lines.
  No finding contradicted this block.

Verdict: 9 findings
Tests: 2665 passed, 0 failed, 1 skipped (reused from last-verification.json at a026540ab0bb2efc5a3f439870668a4609936faa)
