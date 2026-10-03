---
prd: docs/dev/project-management/prds/wip/00241-bound-rework-batches-by-file-v1.md
review: 2
date: 2026-10-03
head_sha: 0a23f752325253c1f56ac6cee68db03868d2dd40
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00241-bound-rework-batches-by-file-v1

Diff range: `1068a962a60ecdc77760e9ea9a1278ac988ca4ea..0a23f752325253c1f56ac6cee68db03868d2dd40`

codex_rung_guard: not fired

pack: failed (`engram pack` exit 1: "not inside a registered repo; register it in /Users/bob/.config/gita/repos.csv"). The same deterministic failure as cycle 1, so no retry was burned. Alice, Bob and Carl received the `(no pack available this cycle)` sentinel for `{PACK_FILE}` and `{PACK_FINDINGS}`; Blake never receives a pack by design. The review is degraded, not invalid.

bob: codex unavailable (exit 1 twice — `codex-event: error`, `turn.failed`, no `-o` file, and `codex-run.sh` writes no sidecar to salvage). Identical to cycle 1's failure. The doubt lens did not drop: a Claude Task subagent ran Bob's exact assembled prompt and its output is Bob's for this cycle. Both CLI dispatch rows are closed as `error` (`exit 1`, then `retry: exit 1`). `--emit-thread-id` did capture a `thread.started` uuid (`01a102ba-32a5-7b31-abf0-e60e92e7bab2`), but the turn that owns it failed and Bob's output came from the fallback, so `codex_thread_id` is deliberately NOT stamped — resuming a failed turn would be worse than a fresh run.

bob prompt deviation, flagged (same as cycle 1): Bob's assembled prompt gained `eve.md`'s FIX/VERIFY/KNOWN bucket section, which the skill's Bob assembly table does not list (it names only the "Two lenses" and "Rubric verdicts" sections). Bob is the doubt lane this cycle and is mandated to answer D1-D5, every one of which is a statement about those buckets, so without them all five would have to be failed. Recorded rather than left implicit. The cycle-2 queue file consequently carries `source: "bob"`, which `references/output-formats.md` reserves — the same deviation, same reason, consistent with cycle 1.

## Review Summary

Reviewed: 7 completed tasks (3 original-plan, 4 `[D1]` rework)
PRDs checked: 00241-bound-rework-batches-by-file-v1

### Agent Status

- Alice: ✅ Available (Claude subagent, `consensus_engine: legacy`)
- Blake: ✅ Available (Claude subagent, PRD-only blind lens; no Filesystem-notes block — `docs/dev/project-management` is not a symlink and the root basename does not start with `.`)
- Bob: ✅ Available via Claude fallback (codex down, exit 1 twice; doubt + de-slop lens, `D1`-`D5` below)
- Carl: ✅ Available (gemini CLI, `backend=copilot model=gemini-3.8-flash`, exit 0)

## Consolidated Findings

19 consolidated rows: 0 🔴 Critical, 2 🟠 High, 8 🟡 Medium, 9 ⚪ Low.

Cycle 1 raised 27 rows. 24 are verified resolved by at least two lenses reading
the code. Two are **partially** resolved and come back as this cycle's two
HIGHs; one (the `.gitignore` revert) is resolved and stays a settled deferral
because the installed cache can revert it again.

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [3/4] | 🟠 | The Tail sweep HIGH is only partly resolved. The `Tail sweep:` prefix and the resume-rule pin are fixed. Step 2 still reads "Build ONE `[D{cycle}]` task", and the intro still reads "one normal `/autopilot:work` task". Both contradict the Split rule's "one task per group". The old ">10 findings" gate stays gone, so a 3-finding sweep over 3 files still yields 3 tasks, which is the per-task cost the PRD targets. Suggested fix: reword step 2 and the intro to "one task per `group-rework` group". Decide explicitly whether small sweeps still collapse to one task. (Bob's merged row adds: the added clause "the floor is one task, for a single group, never zero" is a no-op, since one group always yields one task.) | skills/run-autopilot/references/phase-review.md:195 | 6 | ALICE, BLAKE, BOB |
| [1/4] | 🟠 | `_LINE_SUFFIX` still misses three citation shapes the canonical `consolidate_findings._TRAILING_LINENO_RE` strips and its comment says the personas emit — `(line 3)`, `(lines 18-22, 423)`, `#L12-L20` — so each still becomes its own junk key and burns a cap slot, the unresolved remainder of cycle 1's `file_key` HIGH | skills/run-autopilot/cli/rework_groups.py:26 | 7 | BOB |
| [2/4] | 🟡 | `file_key` discards the cited file for `N/A (path:77)`. Cycle 1 pointed at `consolidate_findings.strip_citation_suffixes`, which unwraps that shape (`_NA_PARENS_RE`) and keeps the first path as the citation. `file_key` maps it to `general`, and `test_not_applicable_wrapping_a_path_is_the_general_key` pins that. A finding that names a real file therefore merges into the smallest group instead of its own file's group. The ledger records "accepted with any parenthesized tail" as an assumption, and no finding or PRD text authorized it. Either unwrap to the path or record the decision as a ruling. | skills/run-autopilot/cli/rework_groups.py:28 | 7 | ALICE, BOB |
| [1/4] | 🟡 | `file_key` goes beyond the spec's key rule (strip trailing `:<digits>` and `:<digits>-<digits>`, `general` stays `general`). It also strips ` (lines a-b)` and `#Ln` suffixes, and maps `N/A` and `N/A (...)` to `general`. The spec lists only `general` and `<path>[:<line>]` as inputs, so this is unrequested behavior, though it is a harmless superset. | skills/run-autopilot/cli/rework_groups.py:26 | 1 | BLAKE |
| [1/4] | 🟡 | The Tail sweep "Split rule" is not the exact sentence the spec gave. The spec says it "becomes" a single sentence. The implementation appends five sentences: the findings JSON path, the task naming rule, a one-task floor, and max-2-parallel. They are sensible but unrequested. | skills/run-autopilot/references/phase-review.md:197 | 3 | BLAKE |
| [1/4] | 🟡 | The CHANGELOG entry adds three clauses beyond the spec's single "caps at 4 non-CRITICAL tasks, grouped by file" line. They cover suffix shapes, `N/A` handling and the exit-2 message. | CHANGELOG.md:12 | 3 | BLAKE |
| [1/4] | 🟡 | `assert "floor" in paragraph` pins a literal word, not the rule, so any sentence containing "floor" satisfies it — and the clause it guards is itself vacuous | skills/run-autopilot/scripts/test_rework_groups_prose.py:89 | 6 | BOB |
| [1/4] | 🟡 | Task 5's `release-checks` wiring ships with no regression test, though the sibling suite pins its own wiring the same way (`test_design_rework_prose.py:546 test_release_checks_runs_both_design_contract_suites`); deleting the new line leaves everything green | dev/bin/release-checks:76 | 5 | BOB |
| [1/4] | 🟡 | The new prose test copies ~15 lines of landmark lookup and paragraph bounding verbatim from `test_tail_sweep_split_rule_uses_the_command` (lines 43-62); the duplicated block should be one `_split_rule_paragraph()` helper | skills/run-autopilot/scripts/test_rework_groups_prose.py:65 | 6 | BOB |
| [1/4] | 🟡 | 1 touched test passes against the pre-change code: `test_critical_d_task_carries_design_then_contract_then_findings` | skills/run-autopilot/cli/test_design_rework_prose.py | general | mech-check |
| [2/4] | ⚪ | The `if not code: break` guard added in `_cap` is unreachable and untested. The ledger calls it "deliberately untested". `test_prose_only_findings_under_a_cap_of_one_keep_every_finding` never enters the loop, because one group is not greater than a cap of one, so it passes at base and does not reach the guard. A cap of 0 with prose-only input would drive it. The guard also exits with the group count still above the cap. Either test it at cap 0 or drop the guard. | skills/run-autopilot/cli/rework_groups.py:82 | 7 | ALICE, BOB |
| [1/4] | ⚪ | Two weaker pieces remain. `_LINE_SUFFIX` is still narrower than the canonical regex: it misses `(line 3)`, `(lines 3, 5)` and `#L12-L14`, so those shapes can still form bogus groups. The ledger acknowledges the `#L12-L14` case. Separately, the comment in `test_design_rework_prose.py:379` still says the `### Findings (verbatim)` mention "lands first", but the assertion below it now orders only the two bullet leads. | skills/run-autopilot/cli/rework_groups.py:26 | 7 | ALICE |
| [1/4] | ⚪ | The spec names `test_the_00223_cycle_one_set_yields_at_most_four_non_critical_tasks`. The implemented test is `test_the_00223_cycle_one_set_yields_four_non_critical_tasks`. The name differs and the assertion is stricter (exactly 4). | skills/run-autopilot/cli/test_rework_groups.py:481 | 1 | BLAKE |
| [1/4] | ⚪ | Beyond the spec's `test_cli_malformed_input_exits_two`, the CLI also rejects arrays whose elements lack a string `severity` or `file`, and adds `test_cli_malformed_element_exits_two`. This is reasonable validation, but the spec only required exit 2 on unreadable or malformed input. | skills/run-autopilot/cli/__main__.py:776 | 2 | BLAKE |
| [1/4] | ⚪ | The spec's last rule 5 clause (merge `prose` into the single remaining group) is unreachable at cap 4. The code documents this and keeps a guarded branch. | skills/run-autopilot/cli/rework_groups.py:76 | 1 | BLAKE |
| [1/4] | ⚪ | Neither `_is_finding` nor `file_key` rejects an empty `file`, so `{"severity": "🟡", "file": ""}` yields a group — and a `[D]` task — named `""` | skills/run-autopilot/cli/__main__.py:776 | 7 | BOB |
| [1/4] | ⚪ | The new `cannot read` / `cannot parse` split has no test that pins either wording: every malformed-input case asserts only exit 2, empty stdout and one stderr line, so collapsing the two clauses back into one stays green | skills/run-autopilot/cli/test_rework_groups.py:671 | 7 | BOB |
| [1/4] | ⚪ | The second `[MECH]` fail-first line is internally inconsistent: `test_bare_not_applicable_is_the_general_key` cannot pass against the base `file_key`, yet 16 sibling tests did fail at base, so a whole-module overlay leak cannot explain it either | skills/run-autopilot/cli/test_rework_groups.py:139 | general | BOB, mech-check |
| [1/4] | ⚪ | Cannot statically verify: success metrics 1-2 (both pytest suites and `bash dev/bin/release-checks` green) at this HEAD — the recorded exit 0 in `...-checks-1.json` is from cycle 1's HEAD, before tasks 4-7 | N/A | general | BOB |

Consolidation note: `consolidate_findings.py` reported `row 1 merged citations that
matched only after suffix stripping: phase-review.md:195 ~ phase-review.md:197`,
folding Bob's 🟡 small-sweep-floor row into Alice's 🟠 step-2-contradiction row.
The merged row keeps Alice's first-seen wording, so Bob's distinct claim (the new
floor clause is vacuous) is appended to that row's text verbatim rather than lost.

### Mechanical blocks

- **Tautological test shapes:** 47 test functions checked across 3 test files, **no tautological shapes found**.
- **Fail-first replay:** 40 touched tests ran against `1068a962a60e`; 16 failed against base, **24 passed**, 0 test files uncollectable. Two `[MECH]` lines resulted. The first (`test_design_rework_prose.py`, 1 test) is absorbed as its own 🟡 row above — it is the same line cycle 1 absorbed, and cycle 1's judgment still holds (the base lacks the new "Group first" bullet the f2d82e3 fix scoped around, so the test change is behavior-preserving by construction); it is discarded in the gate below and ledgered so it stops recurring. The second (`test_rework_groups.py`, 23 tests) is absorbed into the row that already names that file and `test_bare_not_applicable_is_the_general_key`, with `mech-check` appended to its finders.
- **The second `[MECH]` line resolved, three lenses independently agreeing:** it is a **replay-parser artifact, not unpinned behavior**. Alice re-ran the overlay by hand and found the failing `subTest` cases reported as `SUBFAILED[N/A]`, `SUBFAILED[n/a]`, `SUBFAILED[N/a]` (`'N/A' != 'general'`) while the *parent* test id still reported `PASSED`, which is what the replay keys on. Carl reproduced the base `file_key` in isolation and got `AssertionError` / `Base file_key("N/A"): N/A`. Bob showed the assertion is unsatisfiable against the base regex `r":\d+(-\d+)?$"`, and that a whole-module overlay leak cannot explain it either, since 16 sibling tests did fail at base. Task 7's `N/A` behavior **is** pinned, by four tests each unsatisfiable at base: `test_not_applicable_wrapping_a_path_is_the_general_key`, `test_line_range_and_anchor_citations_share_the_plain_file_key`, `test_every_citation_shape_of_one_file_lands_in_one_group`, `test_not_applicable_merges_with_general_into_the_smallest_file`. `test_widened_stripping_leaves_the_colon_suffix_rule_intact` genuinely passes at base **by design** — it is a preservation guard for the old colon rule, not a pin on new behavior. The remaining passing-at-base tests cover pre-existing cap/order/prose/critical behavior, where passing is expected. The underlying defect is in `replay_tests_against_base.py`'s per-test attribution (it reads `subTest` parents as passes), and it is deferred below.
- **Mechanical facts:** `rework_groups.py` is 136 lines with 5 functions, longest `group()` at 36 lines — under the PRD's 200-line exit criterion and the 50-line function limit. The `__main__.py` functions this PRD added are `_add_group_rework` (3 lines), `_is_finding` (6 lines) and `_run_group_rework` (32 lines).

### Auto-dismissed (ledger)

None — `consolidate_findings.py` ran with `--ledger` and `--ledger-dismiss BLAKE`, and Blake re-raised no settled entry. The four cycle-1 deferrals stayed out of the table on their own.

## Alice

Alice ran the implementation-aware consensus lens and verified 26 of cycle 1's 27 findings resolved in the code, flagging the Tail sweep HIGH as only partly resolved. She raised 2 🟡 and 2 ⚪ (listed above).

Commands she ran: `uv run --no-project --with pytest python -m pytest -q` over `test_rework_groups.py`, `test_rework_groups_prose.py`, `test_design_rework_prose.py` and `test_review_resume_prose.py` (64 passed, 5 subtests passed); `bash dev/bin/release-checks` (all blocks ran with no failure output — she did not capture the numeric exit code); `git check-ignore -v` on `deferred/x.json.lock`, which matches `.gitignore:3 autopilot/**/*.lock`, and `git ls-files`, which shows no `.lock` files under `deferred/`. She also reproduced the fail-first replay by hand (`git archive` of `1068a96` into `/tmp/alice-base`, HEAD's test file overlaid: 18 failed, 30 passed, 2 subtests passed).

**Left behind:** `/tmp/alice-base`, because `rm` is warden-gated inside a subagent. Harmless, outside the repo, noted for cleanup.

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
R13: fail

R13 is a factual fail on `__main__.py` (over 800 lines), a settled deferral she did not re-raise as a finding. R1 fails only on the untested `if not code: break` guard.

## Blake

Blake ran PRD-only, located the code himself, and raised 3 🟡 and 4 ⚪ — every one a scope-creep observation, none a missing requirement. He found no Critical and no High.

He confirmed the module exports (`NON_CRITICAL_CAP`, `group`, `file_key`), the 137-line module under the 200-line limit, the Phase 6 bullet verbatim from the spec and correctly placed before the "CRITICAL D-tasks" bullet, and the `release-checks` wiring at `dev/bin/release-checks:76` and `:109`. He exercised the CLI by hand: a 10-finding input (1 🔴, 8 non-critical, `general`, two `.md`) exited 0 and printed one JSON array matching the result he derived from the spec rules independently — critical group first, then `src/` (🟠, 4), `lib/e.py` (🟠, 2), `prose` (🟡), `tools/z.sh` (⚪), every input finding appearing exactly once. Four error shapes (missing file, JSON object, malformed JSON, finding with no `file`) each exited 2 with one stderr line and empty stdout.

Commands: the two success-metric pytest files (48 passed, 5 subtests, exit 0); `bash dev/bin/release-checks` (**`EXIT=0`**, last suite "180 passed", gather-context checks all PASS); all of `skills/run-autopilot/cli` excluding the new test file (2139 passed, 1 skipped, 668 subtests passed), which covers the existing `test_cli*.py`. He did **not** run the whole `skills/run-autopilot` tree: a broad `-k "prose or test_cli" -x` run stopped at a collection error because `scripts/tracon/test_panels.py` imports `rich`, absent from the `--no-project` environment. That is a pre-existing environment gap unrelated to this PRD; every `*prose*` test `release-checks` runs passed.

B1: pass
B2: pass
B3: pass
B4: pass
B5: pass
B6: fail
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

B6 fails on the four scope-creep rows above (the widened `file_key`, the five-sentence Split rule, the three-clause CHANGELOG line, the extra element validation) — a superset of the spec, not a deviation from it.

## Bob

Ran as the native Claude fallback (codex unavailable, exit 1 twice). Static analysis only; no tests, linters or builds run. Raised 2 🟠, 5 🟡 and 5 ⚪, including the two HIGHs that keep this cycle from converging.

Verified clean, for the record, by reading: `_UNMERGED_FIRST` → `_NOT_A_MERGE_TARGET` with `general` **correctly** retained in the tuple (dropping it would let `general` merge into itself); `_merge_pair`'s double negative removed with behavior preserved — he traced the `shared == 0` case and confirmed `[:-0] == [:0]`; `_CRITICAL_BULLET_LEAD` still live at lines 141 and 387, so removing the bare `.index` orphaned nothing; and the 00223 fixture's full 9→4 merge sequence re-derived by hand, confirming the test is a genuine oracle rather than a restatement of the implementation.

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
R13: fail

R13 fails only on `__main__.py` (~1333 lines), a settled deferral, not re-raised. `rework_groups.py` at 136 lines and `test_rework_groups.py` at 693 are both inside limits.

### Doubt buckets

12 findings in = 9 FIX + 2 VERIFY + 1 KNOWN.

**FIX** (9): Tail sweep step 2's "Build ONE task"; `_LINE_SUFFIX`'s three missing citation shapes; `N/A (path)` discarding the cited path; the absent small-sweep floor; the word-level `"floor"` prose pin; the untested `release-checks` wiring; the duplicated paragraph-bounding block; the accepted empty `file`; the unpinned `cannot read`/`cannot parse` wording.

**VERIFY** (2):
- The second `[MECH]` line's per-test attribution. **Not queued: command shape** — his named check is a `git worktree add` plus a `cd` plus a pytest run, which is three chained commands and a repo state change, none of which the queue admits. It was answered in this cycle instead, by hand, by three lenses (see Mechanical blocks above): the attribution is a replay-parser artifact.
- The PRD's success metrics at this HEAD. Queued as the two entries in `00241-bound-rework-batches-by-file-v1-checks-2.json`. **Also answered here**: `bash dev/bin/release-checks` run in the foreground at this HEAD exited 0 with 2082 pytest passes and 116 shell-harness checks across four `SUMMARY:` blocks, 0 failed; Blake independently got `EXIT=0`, and Blake and Alice ran the pytest selection (48 and 64 passed).

**KNOWN** (1): the `if not code: break` branch is dead at every cap the public API can reach. Cycle 1 demanded a guard for the `code[0]` IndexError on exactly this branch; the branch is PRD rule 5's last clause, which the PRD itself calls unreachable at cap 4; the ledger records it as deliberately untested. Removing it re-opens the cycle-1 finding, so keeping it is the lesser evil and out of scope to re-litigate.

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

Ran on the gemini CLI (`backend=copilot model=gemini-3.8-flash`), exit 0. **`[CARL] ✅ No issues found`**, all twelve R-rules pass.

He independently hand-checked the fail-first replay question and reached the same conclusion as Alice and Bob: `test_bare_not_applicable_is_the_general_key` genuinely fails against base (`AssertionError`, `Base file_key("N/A"): N/A`), and the `SUBFAILED`-alongside-`PASSED` reporting is a replay-parser artifact. He read `replay_tests_against_base.py` itself and re-ran it to inspect the per-test attribution.

As in cycle 1, his first `release-checks` run reported 20 failures in the runner-recursion-guard block (`SUMMARY: 6 passed, 20 failed`), caused by his own nested-dispatch environment (`AUTOPILOT_DISPATCH_DEPTH`, `CODEX_SESSION_ID`, `COPILOT_CLI`, `_AUTOPILOT_LOOP` all set, so `codex-run.sh` refuses with exit 3 where the harness expects 1). His re-run with `env -u` on those four passed. Not a real failure — the orchestrator's own foreground run, also with `env -u`, exited 0, and Blake's plain run reported `EXIT=0`.

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

## Decision gate (cycle 2)

**Cap check: `state.cycle 2 >= state.rework_cap 2`.** Rework is NOT allowed.

**Not converged.** Two unresolved 🟠 HIGH remain, and neither is a settled
deferral — cycle 1 routed both into rework tasks (6 and 7) rather than
deferring them, and both fixes landed only partially:

1. `[3/4]` Tail sweep step 2 still mandates ONE task while the Split rule two
   lines below mandates one per group, and the small-sweep gate is still gone.
   Task 6 was titled to reconcile exactly this and never touched step 2.
2. `[1/4]` `_LINE_SUFFIX` still misses `(line 3)`, `(lines 18-22, 423)` and
   `#L12-L20`. Task 7 widened the regex but not to the canonical set, so junk
   keys can still burn cap slots.

Neither severity was adjusted to manufacture convergence. Blake rated the
`file_key` area 🟡 and Alice ⚪ while Bob rated it 🟠; the consolidated row keeps
the highest severity any lens assigned, which is the rule.

**No 🔴 CRITICAL in the table**, so the `cap_critical` custody stall does not
apply and no rework design is launched.

**Loop mode (`$_AUTOPILOT_LOOP` set): cap-out defers, it does not pause.** All
unresolved findings are ≤ high, so each is appended to `state.deferred_decisions`
as a `cap-overflow` record and the PRD proceeds to the finalize hand-off as
converged-with-deferrals. Stop polishing, not the batch.

**Safety checks:** no reviewer produced more than 10 follow-up tasks (none were
created — see below); issue count fell 27 → 19 against cycle 1, so the trend is
decreasing; the two HIGHs are recurrences of cycle-1 findings, which is the
Protocol B "same issue reappearing" row — the research verdict is *escalate*,
since both remainders are judgment calls about how far to widen a regex and how
to reword a contract the PRD did not specify, and both now land as deferrals;
**one transient reviewer failure logged** (Bob/codex exit 1 twice) with the
cycle continuing on the Claude-rescued doubt lens.

**Resolved by evidence, no task and no deferral** (1): Bob's `⚪ Cannot
statically verify: success metrics 1-2 at this HEAD`. Both commands were run at
this HEAD this cycle — `bash dev/bin/release-checks` exit 0 (2082 pytest passes,
116 shell checks, 0 failed), and the named pytest selection green for Blake (48)
and Alice (64).

**Discarded** (1): the first `[MECH]` fail-first row
(`test_critical_d_task_carries_design_then_contract_then_findings` passes at
base). Reason: behavior-preserving by construction — the base lacks the "Group
first" bullet the f2d82e3 fix scoped its assertion around, so the test cannot
fail there and that is correct. Cycle 1 made the same call; it is now ledgered
so a third cycle would auto-dismiss it.

**Deferred to batch end** (17, all as `cap-overflow` in `state.deferred_decisions`
and all ledgered): the 2 HIGHs above, 8 Mediums and 7 Lows. Notable among them:
the `replay_tests_against_base.py` per-test attribution bug (it reads a
`subTest` parent as a pass, which is a real defect in the review tooling rather
than in this PRD), and the four Blake scope-creep rows (the implementation is a
superset of the spec, which is defensible but was never authorized).

## Follow-up Tasks Created

**None.** The cap check above fired before task creation: at `cycle 2 >=
rework_cap 2` the loop-mode cap-out branch is the only disposition available, and
it routes every unresolved finding to `state.deferred_decisions` rather than to
a task. Creating `[D2]` tasks here would leave orphaned `pending` tasks that
block the finalize this same gate is handing off to. `autopilot group-rework` was
therefore not invoked this cycle.

For the record, had rework been allowed, the 17 deferred findings would have
grouped into at most 4 `[D2]` tasks by this PRD's own command — the bound it
exists to enforce, and the reason cycle 1's 25 findings became 4 tasks instead of
ten.

Verdict: 19 findings
Tests: 2082 passed, 0 failed, 0 skipped (suite run this cycle: `env -u AUTOPILOT_DISPATCH_DEPTH -u CODEX_SESSION_ID -u COPILOT_CLI -u _AUTOPILOT_LOOP bash dev/bin/release-checks` at HEAD 0a23f75, exit 0; plus 116 shell-harness checks across its four `SUMMARY:` blocks, 0 failed. `last-verification.json` was NOT reused — its `sha` is 3722180 against this cycle's HEAD 0a23f752, and its three counts are null. The four env vars are unset because this session's own nested-dispatch markers make `codex-run.sh` refuse with exit 3 where the runner-recursion-guard harness expects 1 — the same 20 spurious failures Carl hit in cycle 1 and again here.)
