# Decision Audit Log: 00285-resolve-process-facts-without-ps-v1

PRD: `00285-resolve-process-facts-without-ps-v1.md`
Started: 2026-10-13T00:49:58Z
Completed: 2026-10-13T00:49:58Z
Autonomous: 14  |  Deferred: 0  |  Doubts: 0

### [autonomous] 2026-10-13T00:49:58Z

**Decision**: procinfo.py design (ctypes sysctl/proc_pidinfo on Darwin, /proc on Linux) to replace every ps call site

**Choice**: wrote design doc, ran 3 reviewer dispatches (claude, codex, codex-verify); fixed the descendants-test exec-vs-fork blocker via bash -c "sleep 60 & wait", a UnicodeDecodeError gap in child_names, and clarified kernel-header verification wording

**Rationale**: codex (dispatch 2) found the blocker a Claude-only review missed; remaining non-blockers (pgrep name truncation, per-node pgrep spawns, Linux pgrep -f arg loss) accepted as out-of-scope cosmetic/perf tradeoffs on this Darwin-only host

### [autonomous] 2026-10-13T00:49:58Z

**Decision**: Task 2's premise said `test_loop_gates.py` held two fake-`ps` tests and that its `def test_` count must drop by exactly one. The diff shows one test removed and one added, so the net change is zero, and the stop-and-report condition was not recorded in `assumptions.md`. The rewrite also adds two extra asserts (321 and 43210) and routes the tag through a child pid (1000). That is stronger than the contract, so no code change is needed; only the departure from the contract went unreported.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T00:49:58Z

**Decision**: `test_descendants_lists_a_spawned_child` asserts `sorted(names) == ["bash", "sleep"]` immediately after `Popen` returns, with no polling. The nested bash and `/bin/sleep` are forked after `Popen` returns, so the grandchild may not exist when `_descendants` walks the tree, and the test can fail intermittently. `test_child_names_lists_exactly_the_target_pids_children_by_real_name` in the same PRD already polls up to 10 seconds. Poll `_descendants` until it equals the expected list, or until a deadline.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T00:49:58Z

**Decision**: Docstrings and comments still describe `ps` after the switch. `Loop._cleanup_orphans` says "One ps over all candidates (the bash loop ran ps per pid...)" although it now does one `exec_env` per pid; the design review log asked the implementor to rewrite it. `_cpu_seconds` still says "Parses ps TIME format `[[dd-]hh:]mm:ss[.ss]`" and `_descendants` says "any `ps` failure"; both are now false. The "ps reports the EXEC-time environment" wording in the `_pid_tagged` docstrings is stale too. Rewrite them to say `exec_env` / `cpu_seconds` / `child_names`.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T00:49:58Z

**Decision**: `test_descendants_of_a_childless_pid_is_empty` passes against the pre-change code (fail-first replay). In the sandbox the old `ps` call was blocked, so `_descendants` returned `[]` for the wrong reason. It pins no new behavior and the PRD did not ask for it. Either make it fail at base (for example, assert the empty result comes from a successful `child_names` call via a monkeypatched `pgrep` that returns nothing) or drop it.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T00:49:58Z

**Decision**: `_descendants` walks depth-first (`stack.pop()` takes the last pushed pid), but the spec says "breadth-first over `child_names`, each pid visited once". Only the order of the returned names differs, but it is a literal deviation. A `deque` with `popleft()` fixes it.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T00:49:58Z

**Decision**: New failure-handling branches lack tests: all procinfo tests exercise real processes, leaving syscall failures, missing pgrep and subprocess timeout behavior unpinned — add targeted failure-injection tests asserting None or [].

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T00:49:58Z

**Decision**: The shell stubs use `pgrep -alf .` rather than the contract's `pgrep -lf .`. The `-a` flag keeps ancestor processes in the match list, so it is probably needed for the lane-marker pid. The deviation is not noted anywhere, so add a one-line comment or a note in `assumptions.md`.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T00:49:58Z

**Decision**: The two new `sys.path.insert(...)  # <long comment>` lines run well past 100 columns. Shorten the trailing comments.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T00:49:58Z

**Decision**: The shell stubs use `pgrep -alf .` where the spec prescribes `pgrep -lf .`. On macOS `-a` means "include ancestors", so it widens the match. The filter on the pid field still yields the right line and both suites pass, but the text differs from the spec.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T00:49:58Z

**Decision**: The same `pgrep -alf .` deviation appears in both gemini stubs.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T00:49:58Z

**Decision**: The spec says the `mach_timebase_info` struct is "read once through libc". `_darwin_cpu_seconds` re-loads libc and calls `mach_timebase_info` on every `cpu_seconds` call. The result is correct, only wasteful, and it fires at heartbeat cadence.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T00:49:58Z

**Decision**: Docstrings still describe the old `ps` behaviour. `_pid_tagged` says "ps env ... ps reports the EXEC-time environment", `_cleanup_orphans` says "One ps over all candidates", and `_cpu_seconds`/`_descendants` say "ps failure" and "Parses ps TIME format". The code no longer parses ps output, so this is misleading and not harmless.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-13T00:49:58Z

**Decision**: Heartbeat docstrings still describe ps failures and parsing ps TIME after both implementations were replaced — describe the procinfo delegation and its failure results.

**Choice**: auto-fixed

**Rationale**: fixed by review-close
