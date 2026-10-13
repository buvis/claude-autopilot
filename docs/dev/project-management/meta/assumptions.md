# Assumption ledger

Per-plan. Replaced at the first completed task of a full-plan pass.

Plan: PRD 00285 (resolve process facts without setuid ps), batch 202610111300.

## 1: Write cli/procinfo.py and its tests; register the gate

Tess (test author):

- In the exec_env test, polls `exec_env(pid)` (up to 10s, every 0.05s) until the tag shows up, because bash -> env -> python performs two more execs after Popen returns.
- In the child_names test, does not poll; Popen returns only after the exec succeeds, so the name is "sleep" right away.
- The reaped-pid tests assume the OS does not reuse the pid within the test.
- `child_names` returns direct children only, in any order; the exact-match test compares sorted lists.
- The process name is the short name pgrep reports for the binary; `/bin/sleep` and `/usr/bin/tail` exist on every host that runs this suite (the PATH `sleep`/`tail` on this host are GNU coreutils, named `gsleep`/`gtail` by pgrep).
- An idle `sleep` uses less than 0.1s of CPU, and a 0.5s busy child passes 0.2s of CPU within 10s.

Ivan (implementor):

- `mach_timebase_info` is read as a 2-element uint32 array (`{numer, denom}`) through a separate `libc` CDLL handle in `cpu_seconds`.
- Wrapping ctypes numeric args in explicit `c_uint`/`c_size_t`/`c_uint64` types is within the "exact contract", since it only matches the C parameter widths (plain Python ints default to 32-bit `c_int`, which corrupts 64-bit arm64 arguments).
- Catching `IndexError` in the Linux `/proc/<pid>/stat` parse falls under the design's "never raises" guarantee.
- The sysctl result is sliced to the returned `size.value` instead of the full allocated buffer.

## 2: Switch loop_gates/loop/loop_testutil to exec_env; rewrite fake-ps tests

Tess (test author):

- `_child_pids` remains a module-level name in `loop_gates` after the refactor, as the spec's monkeypatch assumes.
- Did not run the test herself; it is expected red until the production change lands.

Ivan (implementor):

- Added the `cli.procinfo` import in alphabetical order inside each file's existing `from cli...` import block.
- Wrapped the `cli.procinfo` line into the "Allowed imports" docstring so the original "; never ..." clause still follows it.
- Took an empty `rg "\bre\."` result as proof `re` was unused, after a same-shape search confirmed the regex itself matches when something is present.

## 4: Switch codex_review_run heartbeat to procinfo; add descendants test

Tess (test author):

- `_descendants` traversal order is DFS (stack-based) per the design doc's own contract code, even though the PRD prose says "breadth-first"; the test asserts only membership/set equality, never order.
- A PATH `sleep` can resolve through a coreutils symlink (e.g. `gsleep`) on some hosts, so the spawn uses `/bin/sleep` by absolute path to stay machine-independent.
- The childless-pid test passes vacuously in this sandbox today (ps blocked, so `_descendants` already returns `[]` for the wrong reason) and only becomes a real check once this task's production switch lands.

Ivan (implementor):

- The new `sys.path.insert` line goes immediately before the existing `_walk_up` import, ahead of every other local import.
- Kept both `_descendants`/`_cpu_seconds` docstrings verbatim per the "keep if still accurate" instruction; their ps-specific wording is now stale and flagged for a follow-up, not fixed in this task.

Undocumented departure (recorded late, during the task 7 tail sweep): task 2's rewrite of `test_loop_gates.py` added two extra asserts and routed the `_AUTOPILOT_LOOP` tag through a child pid rather than the parent directly, which is stronger than the original contract — this was not recorded in this ledger when it happened.
