---
prd: docs/dev/project-management/prds/wip/00285-resolve-process-facts-without-ps-v1.md
review: 1
date: 2026-10-13
head_sha: 31abf0322137f96e479dba727b0daafedbb5e0f6
codex_thread_id: 01a1327b-e041-76e3-af38-1fe909b1e51e
reviewers: alice,blake,bob
agents:
  alice: available
  blake: available
  bob: available
  carl: unavailable
dispatch_rows:
  bob: 9a4cd75f, 7c17a48d (retry)
  carl: 4bb619ab, f072eb83 (retry)
---

# Review: 00285-resolve-process-facts-without-ps-v1 (cycle 1)

Diff range: `17a745807352c6a7c879587d1842092f50178332..31abf0322137f96e479dba727b0daafedbb5e0f6` (full — the PRD's whole work range)

codex_rung_guard: not fired

## Review Summary

Reviewed: 6 completed tasks
PRDs checked: 00285-resolve-process-facts-without-ps-v1

### Agent Status

- Alice: ✅ Available (consensus lens, legacy engine)
- Blake: ✅ Available (blind lens, PRD-only)
- Bob: ✅ Available (doubt lens, codex) — after one retry (inlined). His first run refused with the sandbox read failure (`sandbox-exec: sandbox_apply: Operation not permitted`, `cat` could not start) and emitted twelve unevidenced `fail` verdicts; the inlined retry prompt carried the review context and the full diff verbatim, and its output is what is consolidated here.
- Carl: ⚠️ Unavailable: `gemini-run` exit 1 on both the first run and the retry, backend `copilot` model `gemini-3.8-flash`, `Error: Authentication failed` (GitHub Copilot token invalid, expired, or missing the `Copilot Requests` permission). Exit 1 is a runtime failure, not the exit-4 permanent shape, so no `state.batch.unavailable_reviewers` latch was written and the next cycle will try him again.

pack: failed (engram pack exit 1: `sqlite3.OperationalError: attempt to write a readonly database`) — the review ran without the findings-precedent pack, which is degraded, not invalid.

Consolidation note (fail loud): Bob's output emits its finding lines as `- [BOB] …` bullets inside the FIX/VERIFY/KNOWN buckets, and `consolidate_findings.py`'s `_LINE_RE` anchors on `^[`, so the first run of the consolidator silently dropped all five of his findings. The bullet prefix was stripped from his output file and the consolidator re-run; the table below is that second run. The consolidator also reported one suffix-stripped merge: row R2 folded `test_codex_review_run.py:726` (Alice) with `:740` (Bob) — the same racing-descendants test, correctly merged.

Mechanical checks: two `[MECH]` findings, both already raised by a reviewer, so both were absorbed into existing rows rather than added: the `or`-hedge in `test_wrapper_alive_script_requires_root_arg` (row R7, `mech-check` added as a finder) and the fail-first replay result that `test_descendants_of_a_childless_pid_is_empty` passes against the pre-change code (row R4, `mech-check` added as a finder).

## Consolidated Findings

| Ref | Consensus | Severity | Issue | File | Task | Found By |
|-----|-----------|----------|-------|------|------|----------|
| R1 | [3/3] | 🟡 | Task 2's premise said `test_loop_gates.py` held two fake-`ps` tests and that its `def test_` count must drop by exactly one. The diff shows one test removed and one added, so the net change is zero, and the stop-and-report condition was not recorded in `assumptions.md`. The rewrite also adds two extra asserts (321 and 43210) and routes the tag through a child pid (1000). That is stronger than the contract, so no code change is needed; only the departure from the contract went unreported. | skills/run-autopilot/cli/test_loop_gates.py:426 | 2 | ALICE, BLAKE, BOB |
| R2 | [2/3] | 🟡 | `test_descendants_lists_a_spawned_child` asserts `sorted(names) == ["bash", "sleep"]` immediately after `Popen` returns, with no polling. The nested bash and `/bin/sleep` are forked after `Popen` returns, so the grandchild may not exist when `_descendants` walks the tree, and the test can fail intermittently. `test_child_names_lists_exactly_the_target_pids_children_by_real_name` in the same PRD already polls up to 10 seconds. Poll `_descendants` until it equals the expected list, or until a deadline. | skills/run-autopilot/scripts/test_codex_review_run.py:726 | 4 | ALICE, BOB |
| R3 | [1/3] | 🟡 | Docstrings and comments still describe `ps` after the switch. `Loop._cleanup_orphans` says "One ps over all candidates (the bash loop ran ps per pid...)" although it now does one `exec_env` per pid; the design review log asked the implementor to rewrite it. `_cpu_seconds` still says "Parses ps TIME format `[[dd-]hh:]mm:ss[.ss]`" and `_descendants` says "any `ps` failure"; both are now false. The "ps reports the EXEC-time environment" wording in the `_pid_tagged` docstrings is stale too. Rewrite them to say `exec_env` / `cpu_seconds` / `child_names`. | skills/run-autopilot/cli/loop.py:248 (also skills/run-autopilot/scripts/codex_review_run.py:261, skills/run-autopilot/scripts/codex_review_run.py:303, skills/run-autopilot/scripts/codex_review_run.py:399, skills/run-autopilot/cli/loop_gates.py:52, skills/run-autopilot/scripts/tracon/discovery.py:95, skills/run-autopilot/cli/loop_testutil.py:172, skills/run-autopilot/cli/loop_testutil.py:184) | 2 | ALICE |
| R4 | [1/3] | 🟡 | `test_descendants_of_a_childless_pid_is_empty` passes against the pre-change code (fail-first replay). In the sandbox the old `ps` call was blocked, so `_descendants` returned `[]` for the wrong reason. It pins no new behavior and the PRD did not ask for it. Either make it fail at base (for example, assert the empty result comes from a successful `child_names` call via a monkeypatched `pgrep` that returns nothing) or drop it. | skills/run-autopilot/scripts/test_codex_review_run.py:745 | 4 | ALICE, mech-check |
| R5 | [1/3] | 🟡 | `_descendants` walks depth-first (`stack.pop()` takes the last pushed pid), but the spec says "breadth-first over `child_names`, each pid visited once". Only the order of the returned names differs, but it is a literal deviation. A `deque` with `popleft()` fixes it. | skills/run-autopilot/scripts/codex_review_run.py:265 | 3 | BLAKE |
| R6 | [1/3] | 🟡 | New failure-handling branches lack tests: all procinfo tests exercise real processes, leaving syscall failures, missing pgrep and subprocess timeout behavior unpinned — add targeted failure-injection tests asserting None or []. | skills/run-autopilot/cli/test_procinfo.py:1 | 1 | BOB |
| R7 | [1/3] | 🟡 | Mechanical analysis identifies an either-or hedge in test_wrapper_alive_script_requires_root_arg — this existing assertion is outside the changed test hunk; tightening its expected outcome belongs in separate test maintenance. | skills/run-autopilot/scripts/tracon/test_discovery.py:1645 | general | BOB, mech-check |
| R8 | [1/3] | ⚪ | The shell stubs use `pgrep -alf .` rather than the contract's `pgrep -lf .`. The `-a` flag keeps ancestor processes in the match list, so it is probably needed for the lane-marker pid. The deviation is not noted anywhere, so add a one-line comment or a note in `assumptions.md`. | skills/use-codex/scripts/codex_run_test_lib.sh:77 (also skills/use-gemini/scripts/test_gemini_run.sh:67, skills/use-gemini/scripts/test_gemini_run.sh:85) | 5 | ALICE |
| R9 | [1/3] | ⚪ | The Linux branches of `exec_env` and `cpu_seconds` (the `/proc/<pid>/stat` parse after `rindex(")")`) and the `mach_timebase_info` failure path have no test. The PRD accepts the Linux gap. A small monkeypatched `sys.platform` / `Path.read_text` test for the comm-with-parens case would pin the trickiest parse cheaply. | skills/run-autopilot/cli/procinfo.py:1054 | 1 | ALICE |
| R10 | [1/3] | ⚪ | The two new `sys.path.insert(...)  # <long comment>` lines run well past 100 columns. Shorten the trailing comments. | skills/run-autopilot/scripts/codex_review_run.py:50 (also skills/run-autopilot/scripts/tracon/discovery.py:21) | 3 | ALICE |
| R11 | [1/3] | ⚪ | The shell stubs use `pgrep -alf .` where the spec prescribes `pgrep -lf .`. On macOS `-a` means "include ancestors", so it widens the match. The filter on the pid field still yields the right line and both suites pass, but the text differs from the spec. | skills/use-codex/scripts/codex_run_test_lib.sh:77 | 4 | BLAKE |
| R12 | [1/3] | ⚪ | The same `pgrep -alf .` deviation appears in both gemini stubs. | skills/use-gemini/scripts/test_gemini_run.sh:67 | 4 | BLAKE |
| R13 | [1/3] | ⚪ | The spec says the `mach_timebase_info` struct is "read once through libc". `_darwin_cpu_seconds` re-loads libc and calls `mach_timebase_info` on every `cpu_seconds` call. The result is correct, only wasteful, and it fires at heartbeat cadence. | skills/run-autopilot/cli/procinfo.py:85 | 1 | BLAKE |
| R14 | [1/3] | ⚪ | Docstrings still describe the old `ps` behaviour. `_pid_tagged` says "ps env ... ps reports the EXEC-time environment", `_cleanup_orphans` says "One ps over all candidates", and `_cpu_seconds`/`_descendants` say "ps failure" and "Parses ps TIME format". The code no longer parses ps output, so this is misleading and not harmless. | skills/run-autopilot/cli/loop.py:248 (also skills/run-autopilot/cli/loop_gates.py:51, skills/run-autopilot/scripts/tracon/discovery.py:94, skills/run-autopilot/scripts/codex_review_run.py:261 and :303) | general | BLAKE |
| R15 | [1/3] | ⚪ | Four tests beyond the five named in the spec were added to the new file: `test_exec_env_omits_the_tag_of_an_untagged_child`, `test_cpu_seconds_reads_the_target_pid_not_the_caller`, `test_child_names_is_empty_for_a_childless_process` and `test_child_names_lists_exactly_the_target_pids_children_by_real_name`. They are test-only, add coverage, and cause no product scope creep. | skills/run-autopilot/cli/test_procinfo.py:80 | 1 | BLAKE |
| R16 | [1/3] | ⚪ | Heartbeat docstrings still describe ps failures and parsing ps TIME after both implementations were replaced — describe the procinfo delegation and its failure results. | skills/run-autopilot/scripts/codex_review_run.py:298 | 4 | BOB |
| R17 | [1/3] | ⚪ | Existing function and file sizes exceed rubric limits: codex_review_run.main is 154 lines, and test_discovery.py extends past 800 lines — these pre-existing structures are outside this narrowly scoped process-facts replacement. | skills/run-autopilot/scripts/codex_review_run.py:415 | general | BOB |

## Alice

Alice's seven findings are rows R1, R2, R3, R4, R8, R9 and R10 above. No CRITICAL or HIGH finding.

```
R1: pass
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
```

## Blake

Blake's seven findings are rows R1, R5, R11, R12, R13, R14 and R15 above. He confirmed, from the PRD alone: `procinfo.py` exists and is stdlib-only with `exec_env`, `cpu_seconds` and `child_names`; every named consumer is switched (`loop_gates._pid_tagged`, `loop._cleanup_orphans`, `loop_testutil._spawn_tagged_incumbent`, `tracon/discovery._pid_tagged`, the `codex_review_run` heartbeat helpers); the exit-criteria `rg` sweep for `["ps"`, `ps -o `, `ps ewww` and `ps -eo` over `skills`, `hooks` and `dev/bin` returns nothing; `dev/bin/release-checks:330-331` registers `test_procinfo.py`; the CHANGELOG entry is present. He re-ran the PRD's acceptance commands: `test_procinfo.py` 9 passed, the release-checks prose/count tests 14 passed, the seven loop and wave files 152 passed, the filtered `test_codex_review_run.py` 6 passed, `tracon/test_discovery.py` 90 passed, `test_codex_run.sh` 26 passed 0 failed, `test_gemini_run.sh` 38 passed 0 failed, `dev/bin/release-checks` PASS 3504 FAIL 0 SKIP 0 EXIT 0. He notes he could not confirm his own session ran inside a `run-agent` sandbox, and that the Linux branches are untested here (as the PRD's Risks section states). No CRITICAL or HIGH finding.

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
B14: pass
B15: pass
B16: pass
B17: pass
B18: pass
B19: pass
```

## Bob

Doubt lens plus de-slop, codex, after one retry (inlined). FIX: rows R2, R6 and R16. VERIFY: row R1 (compare AST test-function counts at the two shas and record the stop-and-report discrepancy without deleting valid coverage) — it names no exact runnable command, so it is not queued as a verification check and stays an ordinary finding. KNOWN: rows R7 and R17, both pre-existing and outside this PRD's scope. No CRITICAL or HIGH finding.

```
R1: fail
R2: pass
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: fail
R10: pass
R11: pass
R12: fail
R13: fail
D1: pass
D2: pass
D3: pass
D4: pass
D5: pass
```

## Carl

Carl: unavailable (`gemini-run` exit 1, backend `copilot` model `gemini-3.8-flash`, authentication failed) on both the first run and the retry. No UI or design lens this cycle. The PRD touches no frontend surface, so the gap is narrow.

Verdict: 17 findings
Tests: 3504 passed, 0 failed, 0 skipped (reused from last-verification.json at 31abf0322137f96e479dba727b0daafedbb5e0f6)
