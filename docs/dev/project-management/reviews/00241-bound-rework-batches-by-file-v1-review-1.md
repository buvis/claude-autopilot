---
prd: docs/dev/project-management/prds/wip/00241-bound-rework-batches-by-file-v1.md
review: 1
date: 2026-10-03
head_sha: 1068a962a60ecdc77760e9ea9a1278ac988ca4ea
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00241-bound-rework-batches-by-file-v1

Diff range: `bf07e177401aa1c4e6a9bca377a8cc500d737ca3..1068a962a60ecdc77760e9ea9a1278ac988ca4ea`

codex_rung_guard: not fired

pack: failed (`engram pack` exit 1: "not inside a registered repo; register it in /Users/bob/.config/gita/repos.csv"). Deterministic, so no retry was burned. Alice, Bob and Carl received the `(no pack available this cycle)` sentinel for `{PACK_FILE}` and `{PACK_FINDINGS}`; Blake never receives a pack by design. The review is degraded, not invalid.

bob: codex unavailable (exit 1 twice — `codex-event: error`, `turn.failed`, no `-o` file, and `codex-run.sh` writes no sidecar to salvage). The doubt lens did not drop: a Claude Task subagent ran Bob's exact assembled prompt and its output is Bob's for this cycle. Both CLI dispatch rows are closed as `error` (`exit 1`, then `retry: exit 1`).

bob prompt deviation, flagged: Bob's assembled prompt gained the FIX/VERIFY/KNOWN bucket instruction, which the skill's Bob assembly table does not list (it names only `eve.md`'s "Two lenses" and "Rubric verdicts" sections). Bob is the doubt lane this cycle and was mandated to answer D1-D5, every one of which is a statement about those buckets, so without them all five would have to be failed. Recorded rather than left implicit.

diff scope, flagged: `gather-context.sh` with no `--since` produced an 18-line, 2-file diff, because its `master` base resolves to HEAD on a repo whose PRD work is committed directly to master. It was re-run with `--since bf07e177401a` (`state.work_start_sha`), giving the real 19-file, 897-line range. A review of the first diff would have converged over the whole PRD.

## Review Summary

Reviewed: 3 completed tasks
PRDs checked: 00241-bound-rework-batches-by-file-v1

### Agent Status

- Alice: ✅ Available (Claude subagent, `consensus_engine: legacy`)
- Blake: ✅ Available (Claude subagent, PRD-only blind lens; no Filesystem-notes block — `docs/dev/project-management` is not a symlink and the root basename does not start with `.`)
- Bob: ✅ Available via Claude fallback (codex down; doubt + de-slop lens, `D1`-`D5` below)
- Carl: ✅ Available (gemini CLI, exit 0)

## Consolidated Findings

27 consolidated rows: 0 🔴 Critical, 5 🟠 High, 14 🟡 Medium, 8 ⚪ Low.

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [3/4] | 🟠 | Committed state record c0cd38a reverted PRD 00240's fix: `.gitignore` line 3 went from `autopilot/**/*.lock` back to `autopilot/*.lock`, and four `deferred/*.json.lock` files are now tracked. The installed older autopilot's ensure-store most likely rewrote it. Source `store_tree.py:33` still has the recursive pattern, but the tracked store file now disagrees with it. Restore line 3 and `git rm --cached` the four lock files. Expect a repeat until the 00240 release reaches the installed cache. | docs/dev/project-management/.gitignore:3 | general | ALICE, BOB, CARL |
| [3/4] | 🟠 | `_run_group_rework` validates only "is a list". Elements that are not dicts, or lack `severity`/`file`, raise a raw traceback with exit 1 instead of exit 2 with one stderr line. Reproduced: `[{"severity":"x","text":"t"}]` gives KeyError, `["a"]` gives TypeError, `"file": 3` gives TypeError. The PRD says "exit 2 with one stderr line on unreadable or malformed input", and the orchestrator hand-writes this JSON. | skills/run-autopilot/cli/__main__.py:788 | 2 | ALICE, BLAKE, BOB |
| [3/4] | 🟠 | The Tail sweep prose contradicts itself and breaks Phase 4's resume rule. Step 2 says "Build ONE `[D{cycle}]` task named `[D{cycle}] Tail sweep: <theme>`", and the resume rule keys on that prefix. The new unconditional Split rule creates one task per group, with no naming rule, so group tasks named from `name_hint` lose the prefix. It also removes the old "only above 10 findings" gate, so a 3-finding sweep across 3 files becomes 3 tasks instead of 1 — the per-task pipeline cost the PRD targets. | skills/run-autopilot/references/phase-review.md:197 | 3 | ALICE, BLAKE, BOB |
| [3/4] | ⚪ | The "merge `prose` into the last remaining group" branch is unreachable at `NON_CRITICAL_CAP = 4` and untested; the `and targets` guard is also unreachable, and `code[0]` would raise `IndexError` if it ever ran with no code group. | skills/run-autopilot/cli/rework_groups.py:66 | 1 | ALICE, BLAKE, BOB |
| [2/4] | 🟠 | `N/A` is treated as a path key. The PRD input lists only `<path>[:line]` or `general`, but the consolidated table and the reviewer output format emit `N/A` for cross-cutting findings. On the real 00223 set this produces a one-finding task named `N/A`. `N/A` also skips the "general merges first" rule and takes part in prefix merges as directory `N`. | skills/run-autopilot/cli/rework_groups.py:84 | 1 | ALICE, BOB |
| [2/4] | 🟡 | The `except (OSError, ValueError)` branch has no test. Commit 9b26091 widened it from `JSONDecodeError` to `ValueError` to catch non-UTF-8 files, but `test_cli_malformed_input_exits_two` covers only missing file, directory-as-file and non-array JSON. Narrowing the clause to `OSError` would leave every test green. | skills/run-autopilot/cli/test_rework_groups.py:350 | 2 | ALICE, BOB |
| [2/4] | 🟡 | Plain `json.dumps` escapes non-ASCII. Phase 6 tells the orchestrator to copy each group's findings into `### Findings (verbatim)` with no paraphrase, so it must decode the escapes by hand. `ensure_ascii=False` parses to the same value, so the existing round-trip test still passes. (Confirmed live this cycle: the real run printed `🟠` for 🟠.) | skills/run-autopilot/cli/__main__.py:788 | 2 | ALICE, BLAKE |
| [2/4] | 🟡 | Critical groups come out in input order, but PRD rule 6 read literally orders them by key. `test_critical_findings_stay_separate_and_uncapped` pins input order, and the assumptions ledger never records the choice. | skills/run-autopilot/cli/rework_groups.py:84 | 1 | ALICE, BLAKE |
| [2/4] | 🟡 | `dev/bin/release-checks` wires only `test_rework_groups_prose.py`. It does not run `cli/test_rework_groups.py`, so a regression in the grouping rule itself would not block a release. Spec-literal, not a defect against the PRD. | dev/bin/release-checks:108 | 2 | BLAKE, BOB |
| [2/4] | ⚪ | Naming: `_UNMERGED_FIRST` actually means "keys that are not a general-merge target". It lists `general` itself, which cannot be in `targets` anyway. | skills/run-autopilot/cli/rework_groups.py:24 | 1 | ALICE, BOB |
| [1/4] | 🟠 | `file_key` strips only `:<n>[-<m>]`, a weaker re-implementation of the canonical `consolidate_findings.strip_citation_suffixes`, which also strips ` (lines 3-4)` and `#L12` and unwraps Bob's `N/A (path:77)` shape; those forms reach the table verbatim, so each lands in its own bogus group and burns a cap slot. | skills/run-autopilot/cli/rework_groups.py:23 | 1 | BOB |
| [1/4] | 🟡 | `release-checks` runs only the prose test; `cli/test_rework_groups.py` (372 lines) is in no block and the repo has no CI, so "release-checks green" does not exercise the feature's behavior. The PRD names only the prose test, but its success metrics list both files. | dev/bin/release-checks:108 | 3 | ALICE |
| [1/4] | 🟡 | Simplification: `_merge_pair` returns the whole sort-key tuple; the caller unpacks `(neg_shared, _, _), i, j` and slices `[: -neg_shared]`, a double negative. Return `(shared, i, j)` and slice `[:shared]`. Behavior unchanged. | skills/run-autopilot/cli/rework_groups.py:71 | 1 | ALICE |
| [1/4] | 🟡 | The real consolidated table marks "no file" as `N/A`, not `general`, and nothing maps it. Confirmed: with a/x.py, b/y.py, c/z.py, d/w.py, N/A and general, `general` merged into the lexically smallest group, `N/A`, when it should have been the smallest real file group. The Phase 6 bullet does not tell the orchestrator to normalise it. | skills/run-autopilot/cli/rework_groups.py:88 | general | BLAKE |
| [1/4] | 🟡 | `test_cli_prints_one_json_array` uses the implementation as its own oracle (`printed == rework_groups.group(findings)`) — the pattern 00223 cycle 1 flagged at `test_enter.py:700`. | skills/run-autopilot/cli/test_rework_groups.py:343 | 2 | BOB |
| [1/4] | 🟡 | Three of the four cap tests cannot detect a cap breach: `_by_key` silently collapses groups sharing a `name_hint` and they assert only `set(by_key)`, so five groups with a duplicate key pass. Duplicate keys are reachable, and would create two identically-named `[D]` tasks. | skills/run-autopilot/cli/test_rework_groups.py:188 | 1 | BOB |
| [1/4] | 🟡 | The PRD Test Strategy's happy path requires "one of them `prose`"; the 00223 fixture test asserts only `1 < len(groups) <= 4` and never checks the prose rule survived on real data. | skills/run-autopilot/cli/test_rework_groups.py:307 | 1 | BOB |
| [1/4] | 🟡 | The f2d82e3 regression fix added a redundant assertion instead of replacing the broken one: the `critical_scope` check is strictly implied by the bullet-scoped `_assert_in_order` 17 lines below, and the comment above it still describes the unscoped check the fix abandoned. | skills/run-autopilot/cli/test_design_rework_prose.py:383 | 3 | BOB, mech-check |
| [1/4] | 🟡 | `_RANK` re-declares `consolidate_findings.SEVERITY_ORDER` with different numbers and an implicit unknown rank; one severity table, two copies free to drift. | skills/run-autopilot/cli/rework_groups.py:22 | 1 | BOB |
| [1/4] | 🟡 | skills/run-autopilot/cli/test_rework_groups.py not wired into release-checks | dev/bin/release-checks:108 | 3 | CARL |
| [1/4] | ⚪ | The footer `unittest.main()` is misleading: the module mixes `unittest.TestCase` classes with pytest-fixture functions, so `python test_rework_groups.py` silently skips the four CLI tests. | skills/run-autopilot/cli/test_rework_groups.py:372 | 2 | ALICE |
| [1/4] | ⚪ | Stale comment: it says the CRITICAL sub-bullet "must be the first one in source 2", but the new "Group first" bullet now precedes it, which is why `critical_scope` was added. | skills/run-autopilot/cli/test_design_rework_prose.py:379 | 3 | ALICE |
| [1/4] | ⚪ | `__main__.py` is 1315 lines, over the 800-line limit, and this diff adds 23 more. Pre-existing, deferred in the 00223 review; the task prescribed putting the subparser there. | skills/run-autopilot/cli/__main__.py:771 | 2 | ALICE |
| [1/4] | ⚪ | `_DISPATCH.index(_CRITICAL_BULLET_LEAD)` raises a bare `ValueError: substring not found` when that bullet drifts — the exact failure the suite's own `_section` helper exists to avoid. | skills/run-autopilot/cli/test_design_rework_prose.py:383 | 3 | BOB |
| [1/4] | ⚪ | The exported `group()` is the only function in the module without a docstring, and its `id()`-keyed order restoration carries no comment saying why input order must be rebuilt after a merge concatenates two buckets. | skills/run-autopilot/cli/rework_groups.py:84 | 1 | BOB |
| [1/4] | ⚪ | "cannot read {path}" is printed for a JSON-decode or non-UTF-8 failure too, where the read succeeded and only the content was bad. | skills/run-autopilot/cli/__main__.py:780 | 2 | BOB |
| [1/4] | ⚪ | The assumptions-ledger replacement dropped the plan identity from the title, so a file the new header calls a "per-plan ledger" no longer names its plan. | docs/dev/project-management/meta/assumptions.md:1 | general | BOB |

### Mechanical blocks

- **Tautological test shapes:** 29 test functions checked across 3 test files, **no tautological shapes found**.
- **Fail-first replay:** 3 touched tests ran against `bf07e177401a`; 2 failed against base, **1 passed** — `test_critical_d_task_carries_design_then_contract_then_findings` (`skills/run-autopilot/cli/test_design_rework_prose.py`). 1 test file could not be collected at base. Per step 6's first branch the `[MECH]` line is absorbed into the consolidated row that already names that file and that test's assertion (row 18 above, `mech-check` appended to its finders) rather than becoming a 28th row. Alice judged the flag expected: the base lacks the new "Group first" bullet the f2d82e3 fix scoped around, so the test change is behavior-preserving by construction.
- **Mechanical facts:** `rework_groups.py` is 109 lines with 5 functions, longest `group()` at 26 lines — under the PRD's 200-line exit criterion and the 50-line function limit. The `__main__.py` functions this PRD added are `_add_group_rework` (3 lines) and `_run_group_rework` (14 lines).

### Auto-dismissed (ledger)

None — cycle 1 created the ledger, so `consolidate_findings.py` ran without `--ledger`.

## Alice

Alice ran the implementation-aware consensus lens and raised 1 🟠, 6 🟡 and 7 ⚪ (listed above). She reproduced the malformed-input tracebacks herself, traced the `.gitignore` revert to commit c0cd38a, and ran `test_rework_groups.py`, `test_rework_groups_prose.py` and `test_design_rework_prose.py` (31 passed), `test_store_tree_gitignore.py` (14 passed) and a scoped `cli` selection (2155 passed, 1 skipped, pre-existing and not in the new tests). She did not run the full `release-checks`.

R1: fail
R2: pass
R3: pass
R4: fail
R6: pass
R7: fail
R8: pass
R9: fail
R10: pass
R11: pass
R12: pass
R13: fail

## Blake

Blake ran PRD-only, located the code himself, and raised 3 🟡 and 5 ⚪. He reproduced the three malformed-element cases through `main(['group-rework', ...])`, confirmed the `general`-merges-into-`N/A` misbehaviour on a synthetic set, confirmed critical groups emit in input order, and verified the `json.dumps` escaping. He confirmed both prose inserts are byte-verbatim from the PRD, the CHANGELOG line exists, the 00223 fixture matches its source table, and only the `--findings` flag was added with no new dependencies. He ran the success-metric commands: 18 passed for the two named files, 144 passed across every existing `test_cli*.py` and `test_*prose*.py` under `skills/run-autopilot/`, and `release-checks` through all blocks (he did not capture its exit code).

B1: fail
B2: pass
B3: pass
B4: pass
B5: fail
B6: pass
B7: pass
B8: pass
B9: pass
B10: fail
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

Ran as the native Claude fallback (codex unavailable, exit 1 twice). Static analysis only; no tests, linters or builds run. Raised 5 🟠, 8 🟡 and 8 ⚪, including the three HIGHs no other lens reached at that severity (`N/A` as a junk key, `file_key`'s narrower suffix stripping, and the Tail sweep task-count floor).

Verified clean, for the record: the 40-row 00223 fixture is a faithful transcription of the review file's consolidated table (the "35 findings" heading is the source file's own stale count, and the test comment says so); both prose inserts match the PRD byte-for-byte; keeping "The existing max-2-parallel rework rule applies unchanged" beside the rewritten Split-rule sentence was right; all six behavior rules trace correctly through `_cap`/`_merge_pair`, including the `[: -neg_shared]` slice and the `/`-terminated merged keys; `rework_groups` is imported and registered correctly and `main()` returns the subcommand's code; `test_grouping_leaves_the_input_findings_unchanged` genuinely pins input immutability.

R1: fail
R2: fail
R3: pass
R4: fail
R6: pass
R7: fail
R8: pass
R9: pass
R10: fail
R11: pass
R12: pass
R13: fail

### Doubt buckets

21 findings in = 18 FIX + 1 VERIFY + 2 KNOWN.

**FIX** (18): the `.gitignore` regression; `N/A` normalization; widening `file_key`'s suffix stripping; malformed-element exit 2; the Tail sweep small-sweep floor; the Tail sweep naming rule; hoisting the "Group first." bullet out of the per-task loop; wiring the grouping suite into `release-checks`; testing the `ValueError` catch arm; replacing the CLI test's self-oracle; making the cap tests see a breach; asserting `prose` on the real fixture; dropping the redundant assertion and its stale comment; guarding the bare `ValueError`; renaming `_UNMERGED_FIRST`; guarding the unreachable prose-fold branch; a `group()` docstring; the misleading "cannot read" wording; the ledger title.

**VERIFY** (1): the PRD's success metrics. Split into the cycle-1 queue as two entries (the two pytest/`release-checks` commands). `git check-ignore -q docs/dev/project-management/autopilot/deferred/x.json.lock` was **not queued: command shape** (the queue admits tests, lints, builds, type-checks and project-defined checks; a git query is none) and was run here instead — **exit 1**, confirming nested store lock files are not ignored.

**KNOWN** (2): the duplicated severity table (de-duplicating crosses a skill boundary the PRD never sanctioned); and the cap allocating slots by key count rather than load, which the PRD's Risks section accepts, together with `__main__.py`'s pre-existing 800-line breach.

D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

Ran on the gemini CLI (backend: copilot), exit 0. Raised 1 🟠 and 1 🟡, both corroborating other lenses. His first `release-checks` run reported 20 failures in the runner-recursion-guard block; those were caused by his own nested-dispatch environment (`AUTOPILOT_DISPATCH_DEPTH`, `CODEX_SESSION_ID`, `COPILOT_CLI`, `_AUTOPILOT_LOOP`), and his re-run with `env -u` passed. Not a real failure — the orchestrator's own foreground `release-checks` run exited 0.

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

## Decision gate (cycle 1)

Cap: `cycle 1 < rework_cap 2` → rework allowed. **Not converged**: 5 unresolved 🟠 HIGH, none a settled deferral (cycle 1 created the ledger).

Safety checks: no reviewer count above 10 follow-up tasks after grouping; no prior cycle to compare; no repeat findings; **one transient reviewer failure logged** (Bob/codex exit 1 twice) and the cycle continued with the doubt lens rescued by the Claude fallback.

Deferred to batch end (4, all in `state.deferred_decisions` and the batch deferred JSON, all in the ledger): the `.gitignore` recurrence until a release carries 00240; the duplicated severity table; the stale neighbouring Phase 5/6 prose; `__main__.py`'s 800-line breach.

Resolved by evidence, no task: Bob's "Cannot statically verify" row — both success-metric commands were run this cycle (18 passed; `release-checks` exit 0).

## Follow-up Tasks Created

25 auto-fix findings were bounded with **this PRD's own `autopilot group-rework`** (the repo build — the installed cache v0.7.0 has no such subcommand, which is the release gap) into exactly 4 `[D1]` tasks, rather than hand-split, which would have tripped the >10 scope alarm:

1. `[D1] Harden group-rework input handling, file_key normalization and the cap tests` (L) — opus — group `skills/run-autopilot/cli/`, 19 findings — addresses the malformed-input HIGH, the `N/A` HIGH, the `file_key` HIGH and 16 Medium/Low rows
2. `[D1] Wire test_rework_groups.py into release-checks` (S) — sonnet — group `dev/bin/release-checks`, 3 findings
3. `[D1] Reconcile the Tail sweep split rule with step 2 and restore the ledger title` (M) — sonnet — group `prose`, 2 findings — addresses the Tail sweep HIGH
4. `[D1] Restore the store gitignore lock pattern and untrack the four lock files` (S) — sonnet — group `docs/dev/project-management/.gitignore`, 1 finding — addresses the `.gitignore` HIGH

Observed while doing it: the cap allocates slots by key count, not by load, so one task carries 19 findings beside three carrying 1-3. The PRD's Risks section accepts this explicitly and leaves splitting to `/autopilot:work`'s own task-splitting and prompt-budget rules.

Verdict: 27 findings
Tests: 2036 passed, 0 failed, 0 skipped (suite run this cycle: `bash dev/bin/release-checks`, exit 0; plus 116 shell-harness checks in its four `SUMMARY:` blocks. `last-verification.json` was not reused — its `sha` is f2d82e3 against this cycle's HEAD 1068a962, and its three counts are null.)
