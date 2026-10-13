---
default_model: opus
model_tier_rationale: equivalence obligation - sysctl and libproc readings must stand in for `ps` across the loop registry, tracon and the codex heartbeat; the buffer layout and struct offsets are measured facts the implementer must verify live, not transcribe
---

# Resolve process facts without setuid ps

## Overview

### Problem Statement
Since 2026-10-11 the autoclaude shell function launches the loop through run-agent, inside the operator's seatbelt profile. `/bin/ps` is setuid root and the sandbox refuses to exec it (EPERM, bash exit 126), while `/usr/bin/pgrep` is not setuid and works. Every product path that shells out to `ps` swallows the failure and reads an empty string:

- `_pid_tagged` in `skills/run-autopilot/cli/loop_gates.py:49-68` (registry prune and the live-loop refusal)
- `_cleanup_orphans` in `skills/run-autopilot/cli/loop.py:247-281`
- `_pid_tagged` in `skills/run-autopilot/scripts/tracon/discovery.py:92-111`
- `_descendants` and `_cpu_seconds` in `skills/run-autopilot/scripts/codex_review_run.py:252-344` (the Bob hang detector)

`dev/bin/release-checks` reads `PASS 3436 FAIL 9` in every sandboxed session (measured 2026-10-12 at db8beb0 and at base b57e425):

- the seven wave tests that spawn a tagged incumbent through `_spawn_tagged_incumbent` in `skills/run-autopilot/cli/loop_testutil.py:182-203`, which polls `ps ewww`
- the codex and gemini lane-marker shell cases, whose stubs snapshot `ps -o command=` into `STUB_LANES_SNAPSHOT_DIR` at `skills/use-codex/scripts/codex_run_test_lib.sh:77` and `skills/use-gemini/scripts/test_gemini_run.sh:67-85`

A red record is never reused (`reuse_verdict` in `skills/run-autopilot/cli/verification.py:159` needs `failed == 0`), so every review cycle re-runs the suite, and every queued PRD's "`release-checks` exits 0" criterion is unreachable.

### Target Users
The operator running sandboxed `autoclaude` batches, and the loop's own guards: the duplicate-loop refusal, the orphan sweep, tracon discovery and the codex heartbeat.

### Success Metrics
- `test_exec_env_reads_the_tag_of_a_spawned_child`, `test_exec_env_is_none_for_a_reaped_pid`, `test_cpu_seconds_is_nonnegative_and_monotonic_for_own_pid`, `test_cpu_seconds_is_none_for_a_reaped_pid` and `test_child_names_lists_a_spawned_child` pass.
- The seven wave tests and the two lane-marker shell cases named in the Problem Statement pass inside a `run-agent` session.
- `bash dev/bin/release-checks` exits 0 with `FAIL 0` on its summary line at the end of the last phase, run inside the sandboxed loop session.

## Functional Decomposition

### Capability: Process facts
Read a same-user process's exec-time environment, CPU time and children without `ps`.

#### Feature: Exec-time environment
- **Description**: `exec_env(pid)` returns the environment the process was exec'd with.
- **Inputs**: `pid: int`.
- **Outputs**: `dict[str, str] | None` (None means unreadable: dead, zombie, another user's, or an unsupported platform).
- **Behavior**: Darwin: `ctypes.CDLL(ctypes.util.find_library("c")).sysctl` with `mib = (ctypes.c_int * 3)(CTL_KERN, KERN_PROCARGS2, pid)`, module constants `CTL_KERN = 1` and `KERN_PROCARGS2 = 49`; call once with a NULL buffer to get the size, then into `ctypes.create_string_buffer(size)`; a non-zero return is None. Buffer layout: a 4-byte native-endian argc, the exec path NUL-terminated, NUL padding, argc argv strings NUL-terminated, then the environment strings NUL-terminated. Parse: drop the first 4 bytes, split on `\0`, skip the exec path and every empty entry before argv, skip argc argv entries, then take entries up to the first empty entry, keep those containing `=`, split each on the first `=`, decode with `os.fsdecode`. Linux: `/proc/<pid>/environ` split on `\0`, same key split. Any `OSError` or other platform returns None. Never raises.

#### Feature: CPU seconds
- **Description**: `cpu_seconds(pid)` returns user plus system CPU time consumed so far.
- **Inputs**: `pid: int`.
- **Outputs**: `float | None`.
- **Behavior**: Darwin: `ctypes.CDLL(ctypes.util.find_library("proc")).proc_pidinfo(pid, PROC_PIDTASKINFO, 0, ctypes.byref(buf), TASKINFO_SIZE)` with module constants `PROC_PIDTASKINFO = 4` and `TASKINFO_SIZE = 96` (struct proc_taskinfo: six uint64 then twelve int32); a return value other than 96 is None; seconds = (uint64 at offset 16, pti_total_user, + uint64 at offset 24, pti_total_system) × numer / denom from mach_timebase_info (two uint32, read once through libc) / 1e9. Linux: fields 14 and 15 of `/proc/<pid>/stat` counted after the closing `)`, divided by `os.sysconf("SC_CLK_TCK")`. Otherwise None. Never raises.

#### Feature: Children
- **Description**: `child_names(pid)` lists the direct children with their short names.
- **Inputs**: `pid: int`.
- **Outputs**: `list[tuple[int, str]]`, empty on any failure.
- **Behavior**: `subprocess.run(["pgrep", "-l", "-P", str(pid)], capture_output=True, text=True, timeout=10)`; each line is `<pid> <name>` (pgrep truncates the name to 15 characters, the kernel's short command name); lines that do not start with digits are skipped; `OSError` and `subprocess.SubprocessError` give `[]`.

### Capability: Consumers
Every `ps` call site reads the three functions instead.

#### Feature: Registry tag check
- **Description**: `_pid_tagged(pid, tag_pid)` in `loop_gates.py` and in `tracon/discovery.py` decides by `exec_env`.
- **Inputs**: `pid`, `tag_pid`, the existing `_child_pids(pid)` (pgrep, unchanged).
- **Outputs**: `bool`.
- **Behavior**: True iff `exec_env(p)` for `p` in `[pid, *_child_pids(pid)]` holds `_AUTOPILOT_LOOP` equal to `str(tag_pid)`; a None env counts as untagged. The `ps ewww` call and the `_AUTOPILOT_LOOP=<pid>( |$)` regex are removed. Function names stay, so the tracon `stub_tagged` fixture and every monkeypatch keep working.

#### Feature: Orphan sweep
- **Description**: `_cleanup_orphans` HUPs the loop's own orphans by env, not by `ps` output.
- **Inputs**: the existing `pgrep -u <USER> -P 1` pid list.
- **Outputs**: `SIGHUP` to each orphan whose `exec_env` holds `_AUTOPILOT_LOOP == str(self.loop_pid)`.
- **Behavior**: one `exec_env` per orphan pid (a sysctl, microseconds each; the per-pid cost the docstring warns about came from spawning `ps`). `OSError` on `kill` is still ignored.

#### Feature: Codex heartbeat
- **Description**: `_descendants` and `_cpu_seconds` in `codex_review_run.py` read `procinfo`.
- **Inputs**: the codex pid.
- **Outputs**: `_descendants` keeps its `list[str]` of names, breadth-first over `child_names`, each pid visited once; `_cpu_seconds` returns `cpu_seconds(pid)`.
- **Behavior**: the `ps -eo` and `ps -o time=` calls are removed; the heartbeat line format and `_proc_alive` are unchanged.

#### Feature: Test fixtures
- **Description**: the fixtures that proved tags and command lines through `ps` use the new facts.
- **Inputs**: a spawned tagged child; a lane-marker pid inside the codex and gemini stubs.
- **Outputs**: `_spawn_tagged_incumbent` returns once `exec_env(proc.pid)` holds the tag; each stub writes the full command line of pid `_p` to `.cmd.<pid>` from `pgrep -lf .` filtered to the line whose first field equals `_p`.
- **Behavior**: the two tests in `skills/run-autopilot/cli/test_loop_gates.py:426-453` that fake `subprocess.run` with `ps` text become one test that monkeypatches `exec_env` to return `{"_AUTOPILOT_LOOP": "4321"}` for pid 999 and asserts `_pid_tagged(999, 4321)` is True and `_pid_tagged(999, 432)` is False (the exact-match intent survives; the "non-final ps line" case has no counterpart in a dict). Premise: `rg -c "def test_" skills/run-autopilot/cli/test_loop_gates.py` drops by exactly one; any other change to that file's test count is a stop-and-report.

## Structural Decomposition

### Repository Structure

```
skills/run-autopilot/
├── cli/
│   ├── procinfo.py                  # NEW: exec_env, cpu_seconds, child_names  (Process facts)
│   ├── test_procinfo.py             # NEW: the five Success Metrics tests
│   ├── loop_gates.py                # _pid_tagged via exec_env               (Registry tag check)
│   ├── loop.py                      # _cleanup_orphans via exec_env          (Orphan sweep)
│   ├── loop_testutil.py             # _spawn_tagged_incumbent polls exec_env (Test fixtures)
│   └── test_loop_gates.py           # fake-ps tests become a fake-exec_env test
├── scripts/
│   ├── codex_review_run.py          # _descendants, _cpu_seconds via procinfo (Codex heartbeat)
│   └── tracon/
│       └── discovery.py             # _pid_tagged via exec_env               (Registry tag check)
skills/use-codex/scripts/codex_run_test_lib.sh   # stub snapshot via pgrep -lf  (Test fixtures)
skills/use-gemini/scripts/test_gemini_run.sh     # same, both stubs             (Test fixtures)
dev/bin/release-checks                            # registers test_procinfo.py
CHANGELOG.md
```

### Module: procinfo
- **Maps to capability**: Process facts
- **Responsibility**: the only place that reads another process's env, CPU time or children; stdlib only (ctypes, os, subprocess, sys).
- **Exports**:
  - `exec_env(pid)` - exec-time environment or None
  - `cpu_seconds(pid)` - user plus system CPU seconds or None
  - `child_names(pid)` - `[(pid, name), ...]`
- New symbols: `procinfo`, `cli.procinfo`, `exec_env`, `cpu_seconds`, `child_names`, `CTL_KERN`, `KERN_PROCARGS2`, `PROC_PIDTASKINFO`, `TASKINFO_SIZE`, `test_exec_env_reads_the_tag_of_a_spawned_child`, `test_exec_env_is_none_for_a_reaped_pid`, `test_cpu_seconds_is_nonnegative_and_monotonic_for_own_pid`, `test_cpu_seconds_is_none_for_a_reaped_pid`, `test_child_names_lists_a_spawned_child`

### Module: loop consumers
- **Maps to capability**: Consumers (Registry tag check, Orphan sweep, Test fixtures)
- **Responsibility**: `loop_gates.py`, `loop.py`, `loop_testutil.py` and `test_loop_gates.py` import `from cli.procinfo import exec_env`; `loop_gates.py`'s "Allowed imports" docstring line gains `cli.procinfo`.
- **Exports**: unchanged (`_pid_tagged`, `prune_registry`, `live_wrapper_pid`, `_spawn_tagged_incumbent`).
- New symbols: `test_pid_tagged_requires_an_exact_pid_match`

### Module: scripts consumers
- **Maps to capability**: Consumers (Registry tag check, Codex heartbeat)
- **Responsibility**: `codex_review_run.py` and `tracon/discovery.py` put the skill root on `sys.path` (`Path(__file__).resolve().parents[1]` and `parents[2]`) and import `from cli.procinfo import ...`; `tracon/discovery.py` stays stdlib-only in spirit (`cli/__init__.py` is empty, `procinfo` is stdlib).
- **Exports**: unchanged (`_pid_tagged`, `_descendants`, `_cpu_seconds`).
- New symbols: `test_descendants_lists_a_spawned_child`

### Module: shell stubs
- **Maps to capability**: Consumers (Test fixtures)
- **Responsibility**: `skills/use-codex/scripts/codex_run_test_lib.sh:77` and `skills/use-gemini/scripts/test_gemini_run.sh:67-85` (both stubs) replace `ps -o command= -p "$_p"` with `pgrep -lf . | while read -r _pid _cmd; do [ "$_pid" = "$_p" ] && printf '%s\n' "$_cmd"; done`, so the existing `*codex-run.sh*` and `*gemini-run.sh*` assertions keep their input.
- **Exports**: none (shell).

### Module: gate
- **Maps to capability**: Process facts
- **Responsibility**: `dev/bin/release-checks` gains `echo "[checks] process facts"` followed by `run_pytest uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_procinfo.py`; `CHANGELOG.md` gains a `### Fixed` entry under `[Unreleased]`.
- **Exports**: none.

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **procinfo**: the three facts and their tests.

### Core Layer (Phase 1)
- **loop consumers**: Depends on [procinfo]
- **scripts consumers**: Depends on [procinfo]
- **shell stubs**: no code dependency; grouped here because the gate's lane-marker cases only go green with it.

### Integration Layer (Phase 2)
- **gate**: Depends on [procinfo, loop consumers, scripts consumers, shell stubs]

## Implementation Phases

### Phase 0: Foundation
**Goal**: the three facts exist, are tested, and the new test file is gated.

**Tasks**:
- [ ] Write `skills/run-autopilot/cli/procinfo.py` and `skills/run-autopilot/cli/test_procinfo.py`; the tag test spawns `bash -c 'exec env _AUTOPILOT_LOOP=$$ <python> -c "import time; time.sleep(60)"'` like `_spawn_tagged_incumbent` and kills it in `finally`; the monotonic test reads `cpu_seconds(os.getpid())` before and after a busy loop of one million additions; add the `[checks] process facts` block to `dev/bin/release-checks` in the same task (no deps) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_procinfo.py` exits 0 with the five tests passing; `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_release_checks_parallel_prose.py skills/run-autopilot/cli/test_release_checks_counts.py` exits 0.

**Exit Criteria**: `procinfo.py` is the only new product file; it imports nothing outside the stdlib.

### Phase 1: Core
**Goal**: no product or test path spawns `ps`.

**Tasks**:
- [ ] Switch `loop_gates._pid_tagged`, `loop._cleanup_orphans` and `loop_testutil._spawn_tagged_incumbent` to `exec_env`; rewrite the two fake-`ps` tests in `test_loop_gates.py` as `test_pid_tagged_requires_an_exact_pid_match` (depends on: Phase 0) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_loop.py skills/run-autopilot/cli/test_loop_gates.py skills/run-autopilot/cli/test_loop_review_once.py skills/run-autopilot/cli/test_wave_launch.py skills/run-autopilot/cli/test_wave_launch_status.py skills/run-autopilot/cli/test_wave_launch_refusals.py skills/run-autopilot/cli/test_wave_assemble.py` exits 0; `rg -n "\"ps\"" skills/run-autopilot/cli/loop_gates.py skills/run-autopilot/cli/loop.py skills/run-autopilot/cli/loop_testutil.py` exits 1.
- [ ] Switch `tracon/discovery._pid_tagged` to `exec_env` (depends on: Phase 0) - Acceptance: `uv run --no-project --with pytest --with rich python -m pytest -q skills/run-autopilot/scripts/tracon/test_discovery.py` exits 0; `rg -n "\"ps\"" skills/run-autopilot/scripts/tracon/discovery.py` exits 1.
- [ ] Switch `codex_review_run._descendants` and `_cpu_seconds` to `procinfo`; add `test_descendants_lists_a_spawned_child` (a `sleep 60` child of a `bash -c` parent appears by name) to `skills/run-autopilot/scripts/test_codex_review_run.py` (depends on: Phase 0) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/scripts/test_codex_review_run.py -k "CpuSecondsTests or ProcAliveTests or descendants"` exits 0; `rg -n "\"ps\"" skills/run-autopilot/scripts/codex_review_run.py` exits 1.
- [ ] Replace the three `ps -o command=` snapshot lines in the codex and gemini stubs with the `pgrep -lf` filter (no deps) - Acceptance: `bash skills/use-codex/scripts/test_codex_run.sh` and `bash skills/use-gemini/scripts/test_gemini_run.sh` each exit 0 and print `SUMMARY: <n> passed, 0 failed`; `rg -n "ps -o command=" skills/use-codex/scripts skills/use-gemini/scripts` exits 1.

**Exit Criteria**: `rg -n "\[\"ps\"|ps -o |ps ewww|ps -eo" skills hooks dev/bin -g '*.py' -g '*.sh'` matches only the operator advice text in `hooks/guard_stop_on_live_lanes.py`.

### Phase 2: Integration
**Goal**: the gate is green inside the sandbox and the change is recorded.

**Tasks**:
- [ ] Add the `CHANGELOG.md` `### Fixed` entry: `- **run-autopilot**: the loop registry, orphan sweep, tracon discovery and the codex heartbeat read process facts through sysctl, libproc and pgrep instead of setuid ps, so they work inside a seatbelt sandbox and the release gate no longer reads nine failures there` (depends on: Phase 1) - Acceptance: `rg -c "instead of setuid ps" CHANGELOG.md` prints 1.

**Exit Criteria**: `bash dev/bin/release-checks` exits 0 with `FAIL 0` on its summary line, run inside the sandboxed loop session.

## Test Strategy

### Critical Scenarios
- **Happy path**: a child exec'd with `_AUTOPILOT_LOOP=<its pid>` → Expected: `exec_env(pid)["_AUTOPILOT_LOOP"] == str(pid)` and `_pid_tagged(pid, pid)` is True.
- **Edge case**: a tagged grandchild under an untagged shell (the tracon layout, `_spawn_forked_loop_shell`) → Expected: `_pid_tagged(shell_pid, shell_pid)` is True through `_child_pids`.
- **Edge case**: `_pid_tagged(999, 432)` with env `{"_AUTOPILOT_LOOP": "4321"}` → Expected: False (exact match, no prefix match).
- **Error case**: a reaped pid → Expected: `exec_env` None, `cpu_seconds` None, `child_names` `[]`, `_pid_tagged` False, no exception.
- **Error case**: `pgrep` missing from PATH → Expected: `child_names` `[]`, `_descendants` `[]`, heartbeat prints "no tool subprocs" as today.

## Risks

- **`KERN_PROCARGS2` returns EINVAL for a zombie or a process exec'd with an empty environment**: `exec_env` returns None and the pid reads as untagged, which is what an empty `ps` line meant before; the registry entry is swept exactly as today.
- **Task CPU time units differ between Intel and Apple silicon**: the timebase multiplication normalizes them; the heartbeat only compares successive readings, so a wrong constant could not flip a verdict, and the monotonic test pins the direction.
- **Linux branch is unexercised on this host**: the tests exercise the running platform only; the `/proc` reads are a few lines and fail toward None, never toward a crash.
- **Scope exclusions**: the operator advice at `hooks/guard_stop_on_live_lanes.py:88` (it tells a human to run ps on `pids` in their own shell) and the autoclaude function's own `ps -o pgid=` self-guard run in the operator's shell, outside the sandbox, and keep ps.
