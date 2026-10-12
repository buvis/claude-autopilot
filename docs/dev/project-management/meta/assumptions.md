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
