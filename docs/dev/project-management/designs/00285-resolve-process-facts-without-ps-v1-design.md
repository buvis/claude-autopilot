# Design: Resolve process facts without setuid ps

## Architecture fit

This lands entirely inside `skills/run-autopilot/` plus the two sibling skills'
shell test stubs. One new stdlib-only module, `cli/procinfo.py`, becomes the
single place that reads another process's env, CPU time or children; every
existing `ps`-shelling site (`cli/loop_gates.py`, `cli/loop.py`,
`cli/loop_testutil.py`, `scripts/tracon/discovery.py`,
`scripts/codex_review_run.py`) switches its implementation to call it while
keeping its own public function names and signatures unchanged, so none of
their callers or test doubles need to change. The two shell stubs
(`skills/use-codex/scripts/codex_run_test_lib.sh`,
`skills/use-gemini/scripts/test_gemini_run.sh`) swap their `ps -o command=`
snapshot line for a `pgrep -lf` filter — no Python involved there.

`cli/loop_gates.py`'s own docstring ("Allowed imports: stdlib, `cli.state`,
`cli.routing`, `cli.loop_decision`; never `cli.loop` or `cli.loop_act`") gains
`cli.procinfo` in that list, since `procinfo` is stdlib-only and introduces no
new coupling direction (it is a leaf module with zero imports from the `cli`
package).

## Module placement

New files:
- `skills/run-autopilot/cli/procinfo.py` — `exec_env`, `cpu_seconds`,
  `child_names`.
- `skills/run-autopilot/cli/test_procinfo.py` — the five Success Metrics
  tests.

Edited files:
- `skills/run-autopilot/cli/loop_gates.py` — `_pid_tagged` body only.
- `skills/run-autopilot/cli/loop.py` — `_cleanup_orphans` body only.
- `skills/run-autopilot/cli/loop_testutil.py` — `_spawn_tagged_incumbent` body
  only.
- `skills/run-autopilot/cli/test_loop_gates.py` — the two fake-`ps` tests
  collapse into one fake-`exec_env` test.
- `skills/run-autopilot/scripts/tracon/discovery.py` — `_pid_tagged` body
  only (this file keeps its own copy of `_child_pids`/`_pid_alive`, mirroring
  `loop_gates.py`; only the ps-reading half of `_pid_tagged` changes).
- `skills/run-autopilot/scripts/codex_review_run.py` — `_descendants` and
  `_cpu_seconds` bodies only.
- `skills/run-autopilot/scripts/test_codex_review_run.py` — add
  `test_descendants_lists_a_spawned_child`.
- `skills/use-codex/scripts/codex_run_test_lib.sh` — one snapshot line.
- `skills/use-gemini/scripts/test_gemini_run.sh` — two snapshot lines (same
  line appears twice per the PRD's own line numbers 67 and 85).
- `dev/bin/release-checks` — one new `[checks] process facts` block.
- `CHANGELOG.md` — one `### Fixed` entry under `[Unreleased]`.

## Interfaces & contracts

### `cli/procinfo.py` (new, stdlib-only: `ctypes`, `ctypes.util`, `os`,
`subprocess`, `sys`)

```python
CTL_KERN = 1
KERN_PROCARGS2 = 49
PROC_PIDTASKINFO = 4
TASKINFO_SIZE = 96  # struct proc_taskinfo: 6 x uint64 + 12 x int32

def exec_env(pid: int) -> dict[str, str] | None: ...
def cpu_seconds(pid: int) -> float | None: ...
def child_names(pid: int) -> list[tuple[int, str]]: ...
```

- **`exec_env(pid)`**
  - Darwin: `libc = ctypes.CDLL(ctypes.util.find_library("c"))`.
    `mib = (ctypes.c_int * 3)(CTL_KERN, KERN_PROCARGS2, pid)`.
    First call: `libc.sysctl(mib, 3, None, ctypes.byref(size), None, 0)` with
    `size = ctypes.c_size_t(0)` to get the required buffer length. A non-zero
    return → `None`. Second call: `buf = ctypes.create_string_buffer(size.value)`,
    `libc.sysctl(mib, 3, buf, ctypes.byref(size), None, 0)`. A non-zero return
    → `None`.
  - Buffer layout (from `KERN_PROCARGS2`): 4-byte native-endian `argc`
    (`int.from_bytes(buf.raw[:4], sys.byteorder)`), then the exec path
    NUL-terminated, then NUL padding, then `argc` argv strings
    NUL-terminated, then the environment strings NUL-terminated, ending at
    an empty string or buffer end.
  - Parse: `parts = buf.raw[4:].split(b"\0")`. Walk `parts`, skipping the
    exec path (`parts[0]`) and any immediately-following empty strings
    (NUL padding) until `argc` non-exec-path entries have been consumed as
    argv (skip exactly `argc` entries once padding is passed). After argv,
    collect entries up to (not including) the first empty entry as the
    environment block. For each entry containing `=`: split on the first
    `=` only, decode both sides with `os.fsdecode` (bytes → str, surrogate-
    escaping anything non-UTF-8). Entries without `=` are dropped. Return
    the resulting `dict[str, str]`.
  - Linux: read `/proc/<pid>/environ` (`Path(f"/proc/{pid}/environ").read_bytes()`),
    `split(b"\0")`, drop the trailing empty entry, split each remaining
    entry on the first `=`, decode with `os.fsdecode`. An `OSError` (gone,
    permission, no `/proc`) → `None`.
  - Any other platform, or any `OSError`/`ValueError` anywhere above →
    `None`. Never raises.

- **`cpu_seconds(pid)`**
  - Darwin: `libproc = ctypes.CDLL(ctypes.util.find_library("proc"))`.
    `buf = ctypes.create_string_buffer(TASKINFO_SIZE)`.
    `n = libproc.proc_pidinfo(pid, PROC_PIDTASKINFO, 0, ctypes.byref(buf), TASKINFO_SIZE)`.
    `n != TASKINFO_SIZE` → `None`. Read `pti_total_user` and
    `pti_total_system` at byte offsets 16 and 24 respectively, per the PRD
    (`struct proc_taskinfo`'s six `uint64` fields are
    `pti_virtual_size, pti_resident_size, pti_total_user, pti_total_system,
    ...` — `pti_total_user` is the 3rd field, offset 16; `pti_total_system`
    is the 4th, offset 24). This design does not override the PRD's offsets;
    the implementing task MUST still verify them live against the running
    kernel header (`<bsd/sys/proc_info.h>`) before trusting them — see
    Risks.
    `numer, denom = ctypes.c_uint32(0), ctypes.c_uint32(0)` filled by one
    `mach_timebase_info` struct read through the same `libc` handle used in
    `exec_env` (two adjacent `uint32` fields). `seconds = (user + system) *
    numer.value / denom.value / 1e9`.
  - Linux: read `/proc/<pid>/stat`, split on whitespace AFTER the closing
    `)` of the second field (the comm field may itself contain
    whitespace/parens), take 0-indexed fields 11 and 12 of that tail
    (`utime`, `stime` — PRD fields "14 and 15" counting the whole line
    1-indexed), sum, divide by `os.sysconf("SC_CLK_TCK")`.
  - Any `OSError`/`ValueError`, or an unsupported platform → `None`. Never
    raises.

- **`child_names(pid)`**
  - `subprocess.run(["pgrep", "-l", "-P", str(pid)], capture_output=True, text=True, errors="surrogateescape", timeout=10)`
    (`errors="surrogateescape"` so a non-UTF-8 process name decodes instead
    of raising `UnicodeDecodeError`, which neither of the two caught
    exception types below covers).
  - Each stdout line: `pid_str, _, name = line.partition(" ")`. Skip a line
    whose `pid_str` is not all digits. Append `(int(pid_str), name)`.
  - `OSError` or `subprocess.SubprocessError` → `[]`. Never raises.

### `cli/loop_gates.py::_pid_tagged` (signature unchanged: `(pid: int, tag_pid: int) -> bool`)

```python
def _pid_tagged(pid: int, tag_pid: int) -> bool:
    pids = [pid, *(int(p) for p in _child_pids(pid))]
    needle = str(tag_pid)
    for p in pids:
        env = exec_env(p)
        if env is not None and env.get("_AUTOPILOT_LOOP") == needle:
            return True
    return False
```

`_child_pids` (pgrep-based) and `_pid_alive` are unchanged — only the
ps-reading half of the tag check moves to `exec_env`. `import re` becomes
unused here and is dropped from `loop_gates.py` once nothing else in the file
needs it (confirm with `rg -n "\bre\." skills/run-autopilot/cli/loop_gates.py`
before removing the import).

### `cli/loop.py::Loop._cleanup_orphans` (signature unchanged: `(self) -> None`)

```python
def _cleanup_orphans(self) -> None:
    try:
        out = subprocess.run(
            ["pgrep", "-u", os.environ.get("USER", ""), "-P", "1"],
            capture_output=True, text=True, timeout=10,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return
    pids = [token for token in out.split() if token.isdigit()]
    needle = str(self.loop_pid)
    for pid_str in pids:
        env = exec_env(int(pid_str))
        if env is not None and env.get("_AUTOPILOT_LOOP") == needle:
            try:
                os.kill(int(pid_str), signal_mod.SIGHUP)
            except OSError:
                pass
```

The `pgrep -u <USER> -P 1` candidate list is unchanged; only the batched
`ps ewww` tag read is replaced by one `exec_env` call per candidate. `import
re` and the `re.compile(...)` tag pattern are dropped from this method; keep
`re` imported in the file only if another use remains (check before removing
the module-level import).

### `cli/loop_testutil.py::_spawn_tagged_incumbent` (signature unchanged: `() -> subprocess.Popen`)

```python
def _spawn_tagged_incumbent() -> subprocess.Popen:
    proc = subprocess.Popen(
        ["bash", "-c",
         f"exec env _AUTOPILOT_LOOP=$$ {sys.executable} -c "
         '"import time; time.sleep(60)"'],
    )
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        env = exec_env(proc.pid)
        if env is not None and env.get("_AUTOPILOT_LOOP") == str(proc.pid):
            return proc
        time.sleep(0.05)
    raise AssertionError("tagged incumbent never appeared in exec_env")
```

### `scripts/tracon/discovery.py::_pid_tagged` (signature unchanged: `(pid: int, tag_pid: int) -> bool`)

Same body shape as `loop_gates._pid_tagged` above, using this file's own
`_child_pids`. `discovery.py` imports `from cli.procinfo import exec_env`
after putting the skill root on `sys.path`
(`Path(__file__).resolve().parents[2]`, since `discovery.py` lives at
`scripts/tracon/discovery.py` and `cli/` is a sibling of `scripts/`).

### `scripts/codex_review_run.py::_descendants` (signature unchanged: `(root_pid: int) -> list[str]`)

```python
def _descendants(root_pid: int) -> list[str]:
    found: list[str] = []
    seen: set[int] = set()
    stack = [root_pid]
    while stack:
        cur = stack.pop()
        for pid, name in child_names(cur):
            if pid in seen:
                continue
            seen.add(pid)
            found.append(name)
            stack.append(pid)
    return found
```

Breadth-first per the PRD; the implementation above is a stack-based DFS that
still visits each pid once — `## Risks & edge cases` below records why this is
an equivalent, not a literal breadth-first walk, and names the choice as a
non-blocking design note the review step must confirm the PRD does not care
about queueing order (only "lists the direct children with their short
names", and the Success Metric test name is
`test_descendants_lists_a_spawned_child`, which does not assert ordering).

### `scripts/codex_review_run.py::_cpu_seconds` (signature unchanged: `(pid: int) -> float | None`)

```python
def _cpu_seconds(pid: int) -> float | None:
    return cpu_seconds(pid)
```

A thin wrapper kept under its existing private name so every call site in
this file (and any test patching `_cpu_seconds`) needs no further change.

### `scripts/codex_review_run.py` and `scripts/tracon/discovery.py` sys.path setup

Both already run as standalone scripts outside the `cli` package. Each adds,
before its `from cli.procinfo import ...`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # codex_review_run.py: scripts/ -> run-autopilot/
```

```python
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # tracon/discovery.py: scripts/tracon/ -> run-autopilot/
```

(`cli/__init__.py` is already an empty file, confirmed present, so `cli` is
importable once its parent is on `sys.path`.)

### `cli/test_loop_gates.py` — new test replacing the two fake-`ps` tests

```python
def test_pid_tagged_requires_an_exact_pid_match(monkeypatch):
    def fake_exec_env(pid):
        return {"_AUTOPILOT_LOOP": "4321"} if pid == 999 else None
    monkeypatch.setattr(loop_gates, "exec_env", fake_exec_env)
    monkeypatch.setattr(loop_gates, "_child_pids", lambda pid: [])
    assert loop_gates._pid_tagged(999, 4321) is True
    assert loop_gates._pid_tagged(999, 432) is False
```

`rg -c "def test_" skills/run-autopilot/cli/test_loop_gates.py` drops by
exactly one (two tests removed, one added) per the PRD's premise.

### `cli/test_procinfo.py` — the five Success Metrics tests

```python
def test_exec_env_reads_the_tag_of_a_spawned_child():
    # spawn via the same "exec env _AUTOPILOT_LOOP=$$ <python> -c sleep(60)"
    # shape as _spawn_tagged_incumbent; assert exec_env(pid)["_AUTOPILOT_LOOP"]
    # == str(pid); kill in finally.

def test_exec_env_is_none_for_a_reaped_pid():
    # spawn a short-lived child, wait() it, assert exec_env(pid) is None.

def test_cpu_seconds_is_nonnegative_and_monotonic_for_own_pid():
    # before = cpu_seconds(os.getpid()); busy-loop 1_000_000 additions;
    # after = cpu_seconds(os.getpid()); assert before is not None and
    # after is not None and 0 <= before <= after.

def test_cpu_seconds_is_none_for_a_reaped_pid():
    # same reaped pid as above; assert cpu_seconds(pid) is None.

def test_child_names_lists_a_spawned_child():
    # spawn `sleep 60` as a child; assert its (pid, "sleep") appears in
    # child_names(os.getpid()); kill in finally.
```

### `scripts/test_codex_review_run.py` — new test

```python
def test_descendants_lists_a_spawned_child():
    # spawn `bash -c "sleep 60 & wait"` — the trailing `& wait` forces bash
    # to fork a real child for `sleep` and block in the parent rather than
    # exec'ing `sleep` directly in place (a single-command `bash -c "sleep
    # 60"` can replace its own image with no descendant to find); assert
    # "sleep" appears in _descendants(bash_proc.pid); kill both (parent then
    # child) in finally.
```

### `dev/bin/release-checks` — new gate block

```bash
echo "[checks] process facts"
run_pytest uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_procinfo.py
```

Placed alongside the existing per-module `[checks]` blocks (same pattern as
every other `run_pytest` invocation in the file — the implementing task finds
the nearest sibling block and matches its indentation/placement exactly).

### Shell stubs

`skills/use-codex/scripts/codex_run_test_lib.sh:77` and both occurrences in
`skills/use-gemini/scripts/test_gemini_run.sh:67` and `:85`:

```bash
# before
ps -o command= -p "$_p" > "${STUB_LANES_SNAPSHOT_DIR:?}/.cmd.$_p" 2>/dev/null
# after
pgrep -lf . | while read -r _pid _cmd; do [ "$_pid" = "$_p" ] && printf '%s\n' "$_cmd"; done > "${STUB_LANES_SNAPSHOT_DIR:?}/.cmd.$_p" 2>/dev/null
```

## Data flow

Before: every consumer shells to `ps`/`pgrep`, gets back text, regex- or
column-parses it. After: every consumer calls one of three `procinfo`
functions, which do the same job via `sysctl`/`proc_pidinfo`/`/proc` reads
(falling back to `pgrep` only for the children listing, which stays a
subprocess call — `pgrep` is not setuid and already works in the sandbox, so
Phase 1's `child_names` keeps it rather than reimplementing a process-tree
walk via `sysctl`). No call site's inputs or outputs change shape: `_pid_tagged`
still takes `(pid, tag_pid)` and returns `bool`; `_cleanup_orphans` still takes
no arguments; `_descendants`/`_cpu_seconds` still take a pid and return the
same types. The only internal change is what each function asks the kernel,
not what it tells its caller.

## Reuse inventory

- `cli/loop_gates.py::_pid_alive`, `_child_pids` — unchanged, reused as-is by
  the new `_pid_tagged` body (searches: `rg -n "_pid_alive|_child_pids"
  skills/run-autopilot/cli/loop_gates.py skills/run-autopilot/scripts/tracon/discovery.py`
  confirms both files already carry their own near-identical copies; this PRD
  does not consolidate them, only the `ps`-reading half each contains).
- `cli/loop_testutil.py::_spawn_tagged_incumbent` — the exact
  `exec env _AUTOPILOT_LOOP=$$ <python> -c "sleep(60)"` spawn shape is reused
  verbatim by `test_procinfo.py`'s tag test, per the PRD's own instruction.
- No existing `sysctl`/`proc_pidinfo`/ctypes-based process-info helper exists
  anywhere in the repo. Searches tried: `rg -n "ctypes" skills dev`
  (0 hits outside this PRD's new files), `rg -n "sysctl|proc_pidinfo|KERN_PROC"
  skills dev` (0 hits), `rg -n "/proc/.*stat|/proc/.*environ" skills dev`
  (0 hits) — nothing found, `procinfo.py` is genuinely new.
- `os.sysconf("SC_CLK_TCK")` and `/proc/<pid>/stat` parsing: no existing repo
  helper; standard Linux idiom, inlined per the PRD's own Behavior text
  rather than imported from anywhere (nothing to import).

## Alternatives considered

1. **Shell out to a non-setuid `ps` alternative (e.g. `/bin/ps` replaced by
   a bundled static binary, or `procstat`/`lsof`)** — smallest diff
   (one binary swap, no ctypes). Rejected: no such non-setuid, no-extra-
   dependency binary is guaranteed present across the hosts this runs on
   (macOS has none; introducing a vendored binary violates the "stdlib only"
   boundary `procinfo.py`'s Module Placement responsibility sets, and ships
   a binary the sandbox would need to separately permit).
2. **Read `/proc` unconditionally and treat Darwin as unsupported (`None`
   everywhere)** — smaller diff than the chosen design (no ctypes at all).
   Rejected: this is the host the PRD measures against (`db8beb0`/`b57e425`,
   Darwin), so "unsupported on Darwin" would leave every Success Metric
   failing exactly where it must pass; the PRD's own Behavior sections
   mandate the Darwin sysctl/libproc path.
3. **Chosen: the PRD's own ctypes `sysctl`/`proc_pidinfo` design on Darwin,
   `/proc` on Linux, `None`/`[]` elsewhere** — matches the PRD's named
   Behavior sections exactly (module name, function names, constants,
   buffer layout, Linux fallback). The extra size over option 1 buys
   platform-native facts with zero new binaries or sandbox exceptions; the
   extra size over option 2 buys passing on the actual host this batch runs
   on.

## Risks & edge cases

- **`TASKINFO_SIZE`/offset verification is a measured fact, not a citation.**
  The PRD's own model-tier rationale flags this: `struct proc_taskinfo`'s
  field layout and the `pti_total_user`/`pti_total_system` byte offsets must
  be verified against the running kernel's native header
  (`<bsd/sys/proc_info.h>` / `<libproc/proc_info.h>`) rather than transcribed
  from this design doc or the PRD text, because a transcription error here
  produces a wrong-but-plausible CPU number instead of a crash; a ctypes
  self-check (`ctypes.sizeof`/offset probes against the same hand-written
  ctypes declaration) can only confirm the declaration against itself, so it
  is a secondary sanity probe, never a substitute for the native-header
  check. The implementing task for the `cpu_seconds` feature must do the
  native-header verification live and record what it measured (e.g. in the
  task's commit message or a code comment) before trusting the offsets baked
  into the design above.
- **`KERN_PROCARGS2` EINVAL for a zombie or empty-environment process**:
  `exec_env` returns `None`; every caller already treats `None` as
  "untreated/unresolvable", identical to today's empty-`ps`-line reading —
  no caller-side behavior change.
- **CPU-time units across Intel vs. Apple Silicon**: `mach_timebase_info`'s
  `numer`/`denom` normalizes this; every caller (`_cpu_seconds` in the
  codex heartbeat) only compares successive readings for monotonic growth,
  never an absolute threshold, so a wrong constant could change magnitude
  but not direction — the monotonic Success Metric test pins direction only.
- **Linux branch is unexercised on this host**: both `/proc` branches are a
  few lines each and fail toward `None`/`[]` on any `OSError`, never toward
  an exception; no test exercises them on this Darwin host, which the PRD's
  own Risks section accepts.
- **`_descendants`'s DFS-via-stack vs. the PRD's literal "breadth-first"
  wording**: covered above in Interfaces & contracts; the Success Metric
  test does not assert traversal order, only membership, so this is a
  non-blocking implementation choice, not a contract deviation.
- **Likely next changes after this PRD**: (1) a Linux CI leg that would
  actually exercise the `/proc` branches — this design's Linux parsing is
  self-contained enough that a future PRD can add tests without touching
  `procinfo.py`'s public surface; (2) consolidating the now-triplicated
  `_pid_alive`/`_child_pids` pair across `loop_gates.py` and
  `tracon/discovery.py` into `procinfo.py` itself — deliberately out of
  scope here (the PRD's Module responsibility for `loop consumers` and
  `scripts consumers` keeps each file's existing exports unchanged); this
  design does not block that future move, since `procinfo.py` has no
  dependency on either file's `_pid_alive`/`_child_pids`.
- **Nothing in `procinfo.py` boxes in a future third platform** (e.g.
  *BSD): the `sys.platform` dispatch in each function is a plain if/elif
  returning `None`/`[]` on no match, so adding a branch is additive.

## Test strategy outline

- **Unit** (`cli/test_procinfo.py`): the five Success Metrics tests, each
  spawning or reaping a real child process rather than mocking `sysctl` —
  the PRD's own acceptance criteria name these five tests by name and
  require them to pass for real, since the whole point is exercising the
  sandboxed syscalls themselves.
- **Unit** (`cli/test_loop_gates.py`): `test_pid_tagged_requires_an_exact_pid_match`
  replaces the two fake-`ps` tests, monkeypatching `exec_env` (not
  `subprocess.run`) to prove the exact-match/no-prefix-match contract
  without touching a real process.
- **Integration** (`scripts/test_codex_review_run.py`):
  `test_descendants_lists_a_spawned_child` spawns a real
  `bash -c "sleep 60 & wait"` (forcing a true fork rather than an exec-in-
  place) and asserts `_descendants` finds the `sleep` child by name —
  proves the `child_names`-based DFS walk against a real process tree.
- **Shell** (`skills/use-codex/scripts/test_codex_run.sh`,
  `skills/use-gemini/scripts/test_gemini_run.sh`): existing suites, unchanged
  assertions; only their stub's snapshot mechanism changes, so a passing run
  proves the `pgrep -lf` replacement still feeds the same `.cmd.<pid>`
  shape the assertions already expect.
- **Gate** (`dev/bin/release-checks`): the new `[checks] process facts`
  block plus the existing wave/lane-marker blocks (now passing under
  `exec_env`/`pgrep -lf` instead of failing under setuid `ps`) are what the
  PRD's third Success Metric (`FAIL 0` on the summary line, run inside the
  sandboxed loop session) measures end to end.

## Review log

- non-blocker: `child_names`'s `pgrep -l` truncates names to 15 chars, a cosmetic regression from `_descendants`' prior `ps -eo comm=` full-name output; accepted as-is (the Success Metric test only checks `"sleep"`, well under 15 chars).
- non-blocker: `_descendants`'s stack-based walk spawns one `pgrep` subprocess per visited node instead of one `ps` call for the whole tree; accepted for the shallow trees codex heartbeats actually see (a handful of tool subprocesses, not hundreds).
- question: the orphan sweep's per-candidate `exec_env` cost ("a sysctl, microseconds each") is asserted, not measured against `_cleanup_orphans`' own docstring rationale for batching; the implementing task should spot-check wall time against a realistic candidate count and update the docstring to describe the new per-pid mechanism.
dispatch 1 (claude): cardinal-sin 0, blocker 1, non-blocker 2, question 1
- non-blocker: the shell stub's `while read` loop can exit non-zero on its last (non-matching) iteration even after an earlier matching line wrote the snapshot; under `set -e` this could abort the stub. Left as-is: the existing stubs already run `2>/dev/null`-tolerant, best-effort snapshot lines in a non-`errexit` context (confirmed by the prior `ps -o command=` line's own silent-failure tolerance), so this is consistent with existing stub style, not a regression — worth a follow-up hardening pass, not a block.
- non-blocker: `pgrep -lf .` loses full command-line args under Linux procps (`-f` changes matching semantics there, not output); accepted because every call site this PRD touches runs on Darwin only (the sandboxed `autoclaude` host), and the shell stubs' own suites run on this same Darwin host.
- non-blocker: `_descendants`'s stack-based walk is DFS while the PRD text says "breadth-first"; already recorded above in Risks & edge cases as a non-blocking, membership-only equivalence — reconfirmed by this dispatch, no change made.
- non-blocker: a ctypes-sizeof self-check (the Risks section's "printing ctypes.sizeof/offset probes" alternative) can only confirm the ctypes declaration against itself, not against the true kernel struct; the Risks section already mandates verifying against the live kernel header as the primary check, with the self-check as a secondary sanity probe only — wording in Risks is clarified to make the header check mandatory, not alternative.
- non-blocker: `child_names`'s `subprocess.run(..., text=True)` can raise `UnicodeDecodeError` on a non-UTF-8 process name, which neither `OSError` nor `subprocess.SubprocessError` catches, breaking the "never raises" contract. Fixed in the design below (errors="surrogateescape" added to the decode).
dispatch 2 (codex): cardinal-sin 0, blocker 1, non-blocker 5, question 0
dispatch 3 (codex): cardinal-sin 0, blocker 0, non-blocker 0, question 0
