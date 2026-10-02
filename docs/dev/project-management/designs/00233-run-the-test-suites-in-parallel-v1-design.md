# Design: Run the test suites in parallel

## Root cause

The host's global git config has `commit.gpgsign=true` (confirmed:
`git config --global --get commit.gpgsign` → `true`, with a `user.signingkey`
set and no `gpg.program` override). None of the wave-test git fixtures
disable signing or redirect `HOME`, so every throwaway repo they `git init`
inherits that global setting and every `git commit` call tries to GPG-sign
through the host's single shared `gpg-agent`.

Under serial execution only one commit happens at a time, so the agent never
sees concurrent requests and every signature succeeds. Under `pytest-xdist`,
multiple workers call `git commit` in close time proximity, and the shared
agent chokes:

```
error: gpg failed to sign the data:
gpg: lockfile disappeared
[GNUPG:] KEY_CONSIDERED 9C861295C71FF0EBE7FE857ED1BCFE7035C136D1 2
[GNUPG:] BEGIN_SIGNING H8
gpg: signing failed: Cannot allocate memory
[GNUPG:] FAILURE sign 16810070
gpg: signing failed: Cannot allocate memory

fatal: failed to write commit object
```

`git commit` then exits 128, and every downstream git operation in that test
(a rebase, a `worktree add`, a second commit) fails or cascades from it. This
is exactly the "git lock or global config" guess in the PRD's Problem
Statement, confirmed.

**Not the cause**: `tmp_path`/`monkeypatch.chdir` isolation is fine — every
repo path is per-test. `test_wave_review.py`'s `_assembled` fixture already
`monkeypatch.setenv("HOME", str(tmp_path / "home"))` before `git init`
(line 253 before line 314), which makes the global `.gitconfig` invisible to
that one repo — it was never exposed to the bug. The shared point of exposure
is `test_wave_launch.py::_repo`, which neither disables gpgsign nor moves
`HOME`.

### Reproducing pair

Two threaded "hammer" tests, each committing N throwaway repos concurrently
(real OS-thread concurrency inside one process reproduces the race far more
reliably under `-n 2` than two sequential-commit tests — xdist workers
running one commit at a time rarely land close enough in time to contend for
the agent; verified empirically: two tests doing 25-40 *sequential* commits
each under `-n 2` passed every time, while two tests each firing 12
*concurrent* commits via `ThreadPoolExecutor` failed about half the time):

```python
def _one_repo(base: Path, tag: int) -> None:
    repo = base / f"proj-{tag}"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "master")
    _git(repo, "config", "user.email", "wave@example.com")
    _git(repo, "config", "user.name", "Wave Test")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-qm", "seed")  # <- fails under concurrent load
                                          #    when commit.gpgsign is unset


def _hammer(tmp_path: Path) -> None:
    with ThreadPoolExecutor(max_workers=12) as pool:
        list(pool.map(lambda i: _one_repo(tmp_path, i), range(12)))


def test_hammer_a(tmp_path: Path) -> None:
    _hammer(tmp_path)


def test_hammer_b(tmp_path: Path) -> None:
    _hammer(tmp_path)
```

Measured on this host: `pytest -n 2` on just this pair, repo-local config
has no `commit.gpgsign` override → fails about half the time with the exact
`CalledProcessError` above. With `commit.gpgsign` forced off (simulated via
`GIT_CONFIG_GLOBAL=/dev/null` for this measurement, see Test strategy) the
same pair passes every time, in well under a second.

## Architecture fit

Test-only change. No production module gains a new responsibility; `cli/`'s
runtime code (`wave_launch.py`, `wave_assemble.py`, `wave_review.py`, …) is
untouched. The fix lives entirely in the shared test fixture layer
(`test_wave_launch.py::_repo`) and in the release gate script
(`dev/bin/release-checks`) and its prose counterpart
(`skills/work/references/final-verification.md`).

## Module placement

- **Edit** `skills/run-autopilot/cli/test_wave_launch.py` — `_repo()` gains
  one `git config` call disabling commit signing for the throwaway repo.
  Every file that imports `_repo`/`_planned` from here (`test_wave_cli_refusals.py`,
  `test_wave_assemble.py`, `test_wave_review.py`, `test_wave_run.py`,
  `test_wave_launch_refusals.py`, `test_wave_launch_status.py`,
  `test_wave_launch_abort*.py`) and every worktree spawned from that repo
  via `git worktree add` (shares the same local `.git/config`, e.g. the
  commit in `test_wave_assemble.py:144` and `test_wave_review_land.py:72`)
  inherits the fix with no further edit.
- **New file** `skills/run-autopilot/cli/test_parallel_safety.py` — holds
  the reproducing pair above plus the meta-test that proves it fails before
  the fix and passes after, and a deterministic guard that pins the `_repo()`
  fix under a hostile `GIT_CONFIG_GLOBAL`. It has its own
  `[checks] parallel safety` block in `dev/bin/release-checks`, not a slot in
  the `[checks] waves` file list: `test_wave_docs.py` asserts the `waves`
  block's file set EQUALS a closed set, so adding it there would redden that
  pin. The block runs with `--with pytest-xdist` and no `-n` (the meta-test
  spawns its own `-n 2` subprocess), so it runs as a standing regression
  guard every release.
- **New file** `skills/run-autopilot/cli/test_release_checks_parallel_prose.py`
  — pins that block's `uv run ... -m pytest` invocation (the test path and
  `--with pytest-xdist`, read from the continued command, not any substring).
  It runs from the `[checks] effort lanes` block, so deleting the block it
  pins does not delete the pin.
- **Edit** `skills/run-autopilot/cli/test_lane_cli.py` — `_GIT_IDENTITY` gains
  `-c commit.gpgsign=false`, pinned by its own test.
- **Edit** `dev/bin/release-checks` — `--with pytest-xdist` and
  `-n auto --maxprocesses 4` on four proven-safe blocks (see the contract
  section below for which ones qualify and why the cap exists).
- **Edit** `skills/work/references/final-verification.md` — one added
  clause on the Python suite line.
- **Edit** `CHANGELOG.md` — one `### Changed` line.

## Interfaces & contracts

### `test_wave_launch.py::_repo` (edit)

```python
def _repo(tmp_path: Path, prds: dict[str, str]) -> tuple[Path, Path]:
    """A committed git repo with `prds` in backlog: (repo, wave.json path)."""
    repo = tmp_path / "proj"
    _backlog(repo).mkdir(parents=True)
    for name, text in prds.items():
        (_backlog(repo) / name).write_text(text, encoding="utf-8")
    _autopilot(repo).mkdir(parents=True)
    (repo / ".gitignore").write_text("docs/dev/project-management/\n", encoding="utf-8")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    _git(repo, "init", "-q", "-b", "master")
    _git(repo, "config", "user.email", "wave@example.com")
    _git(repo, "config", "user.name", "Wave Test")
    _git(repo, "config", "commit.gpgsign", "false")  # new line: isolates
    # from the host's global signing config (and its shared gpg-agent),
    # which `-n auto` otherwise contends on across workers (PRD 00233).
    _git(repo, "add", ".gitignore", "README.md")
    _git(repo, "commit", "-qm", "seed")
    return repo, _autopilot(repo) / "wave.json"
```

No signature change, no new return value, no new caller-visible behavior —
every existing call site and every imported re-export is unaffected.

### `test_parallel_safety.py` (new)

```python
"""Proves the wave fixtures are safe under pytest-xdist (PRD 00233).

`test_the_wave_pair_passes_under_two_workers` is the fail-first proof: it
runs `test_hammer_a`/`test_hammer_b` under `-n 2` in a subprocess and
asserts both pass. Both hammer tests call the REAL `_repo()` fixture
(not a copy), so this is a standing regression guard: if `_repo()`'s
`commit.gpgsign false` line is ever reverted, this test goes red again.
"""

from __future__ import annotations

import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from cli.test_wave_launch import _repo

_HAMMER_THREADS = 12


def _hammer(tmp_path: Path) -> None:
    with ThreadPoolExecutor(max_workers=_HAMMER_THREADS) as pool:
        list(pool.map(lambda i: _repo(tmp_path / f"case-{i}", {}), range(_HAMMER_THREADS)))


def test_hammer_a(tmp_path: Path) -> None:
    _hammer(tmp_path)


def test_hammer_b(tmp_path: Path) -> None:
    _hammer(tmp_path)


def test_the_wave_pair_passes_under_two_workers() -> None:
    """Fail-first proof (PRD 00233 Phase 0): the hammer pair above, run
    under 2 real pytest-xdist workers in a subprocess, must both pass."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys, pytest; sys.exit(pytest.main(sys.argv[1:]))",
            "-q",
            "-n",
            "2",
            f"{__file__}::test_hammer_a",
            f"{__file__}::test_hammer_b",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, (
        f"wave hammer pair failed under -n 2:\n{result.stdout}\n{result.stderr}"
    )
```

Because `_hammer` calls the real `_repo()` (not a reimplementation), this
test is genuinely fail-first against the actual base commit: `_repo()`
today has no `commit.gpgsign` override, so `test_hammer_a`/`test_hammer_b`
already fail intermittently under `-n 2` (verified this session: 2 of 3
runs red before the fix, 3 of 3 green after — see Test strategy outline).
No monkeypatch or manual demonstration is needed for the fail-first record;
the task's attempt entry cites a real failing run of this exact file.
Phase 0's acceptance criterion is satisfied by the file as committed, run
once at the base commit.

### `dev/bin/release-checks` (edit)

Add `--with pytest-xdist` and `-n auto` to the pytest invocations whose
suite is a pure subset of `skills/run-autopilot/cli/` (no other directory's
files on the same line) — these are exactly the files proven safe by the
whole-directory 3x-green run in Test strategy below, since a subset of an
already-contention-free file set carries no new contention source:

- `[checks] custody core`
- `[checks] l3`
- `[checks] reporting`
- `[checks] waves`

Shipped as four blocks, not five. `[checks] enter` stays serial: its exact
invocation text is pinned by `test_enter_prose.py`, and it runs in about 2s
serial, so it is not worth the pin edit. `test_parallel_safety.py` is not on
the `waves` file list (that set is a closed set pinned by `test_wave_docs.py`);
it has its own `[checks] parallel safety` block, serial by design because the
meta-test spawns its own `-n 2` subprocess.

Every converted block carries `-n auto --maxprocesses 4`. The cap is
load-bearing: bare `-n auto` resolves to 18 workers on this host and goes red
under concurrent load, so the gate caps workers at 4.

Three groups of blocks stay serial, for different reasons, and the
`release-checks` comment on each must say the right one:

- `[checks] plan size gate`, `[checks] design rework prose`, `[checks] l4`,
  `[checks] effort lanes` genuinely **mix** `skills/run-autopilot/cli/`
  files with files from other directories — not covered by the
  whole-cli-directory proof:
  ```bash
  # serial: mixes files outside skills/run-autopilot/cli/, not covered by the
  # whole-cli-directory parallel-safety proof (PRD 00233)
  ```
- `[checks] cap hook` and `[checks] loop blockers prose` contain **no**
  `skills/run-autopilot/cli/` files at all (they're entirely
  `skills/run-autopilot/scripts/` and `skills/work/scripts/`) — simply
  outside this PRD's scope, not "mixed":
  ```bash
  # serial: no skills/run-autopilot/cli/ files here, outside PRD 00233's scope
  ```
- `[checks] enter` and `[checks] parallel safety` — serial for the reasons
  given above (a pinned invocation text, and a meta-test that spawns its own
  xdist subprocess).

Each converted line changes from

```bash
uv run --no-project --with pytest python -m pytest -q \
  skills/run-autopilot/cli/test_custody.py \
  ...
```

to

```bash
uv run --no-project --with pytest --with pytest-xdist python -m pytest -q -n auto --maxprocesses 4 \
  skills/run-autopilot/cli/test_custody.py \
  ...
```

Same file lists, same `echo` labels — a block that fails still names itself
the same way it does today.

### `skills/work/references/final-verification.md` (edit)

The existing Python suite bullet (line 16) names `pytest` as the fallback
command for "other stacks". Append the clause the PRD's Phase 2 Behavior
section asks for:

> Other stacks: `pytest`, `npm test` — add `-n auto` (with `pytest-xdist`
> installed) when the project's tests are worker-safe; this repo's own
> `dev/bin/release-checks` already proves which suites qualify.

## Data flow

No runtime data flow changes. The only "flow" touched is test execution
order: `pytest-xdist` distributes test *items* (not files) across worker
processes by default (`--dist load`), so two wave tests in the same file can
already land on different workers today — nothing about file grouping needs
to change for the fix to apply.

## Reuse inventory

- `test_wave_launch.py::_git`/`_repo` — the one fixture to fix; already the
  single reuse point every other wave test file imports from (confirmed:
  `rg -n "from cli.test_wave_launch import" skills/run-autopilot/cli/test_wave*.py`
  — 11 files import from it).
- No `conftest.py`, `pytest.ini`, or `[tool.pytest.ini_options]` table
  exists under `skills/run-autopilot/cli/` (one unrelated `conftest.py`
  exists at `skills/run-autopilot/scripts/tracon/conftest.py`, scoped to the
  dashboard's own tests and never collected alongside the wave family) —
  there is no cli-local pytest fixture/marker layer to extend or collide
  with; `xdist_group` is unused today.
- No existing helper disables gpg signing anywhere in the codebase
  (`rg -n "gpgsign|GIT_CONFIG_GLOBAL" --type py` — nothing found); this is a
  new, narrowly-scoped pattern, not a duplicate of something already present.

## Alternatives considered

1. **Redirect `HOME` in `_repo()`** (like `test_wave_review.py`'s
   `_assembled` already does), instead of setting `commit.gpgsign false`
   directly. Rejected as the larger diff for the same effect: `_repo()` is
   imported by 11 files and several of them read environment/HOME-adjacent
   state in their own assertions (none currently check `HOME`, but it is a
   wider blast radius to audit); a single `git config` line is the
   smallest-diff fix and is exactly what the PRD's "Isolate it" feature
   recommends ("a per-test id, HOME, git config or path under tmp_path").
2. **`xdist_group` + `--dist loadgroup`** to serialize just the wave family
   onto one worker. Rejected: the PRD's own Risks section calls this "the
   fallback only when the resource is genuinely global" — this resource
   (gpgsign) is a per-repo config value, not inherently global, so isolating
   it is correct over serializing around it. Keeping it as the documented
   fallback if some other, truly-global contention surfaces later.
3. **Chosen: one `git config commit.gpgsign false` line in `_repo()`.**
   Smallest possible diff, fixes the shared root cause at its single point
   of entry, needs no new fixture, no new marker, and no test file touches
   `HOME` or process environment at all.

## Risks & edge cases

- **A flaky parallel gate is worse than a slow one** (PRD's own Risk): no
  suite goes parallel in `release-checks` without the 3x-green proof above;
  every other block stays serial with a comment naming why, so a false
  "proven safe" claim never ships silently.
- **Unrelated xdist tmp-dir warning**: `-n auto`/`-n 2` runs on this host
  also print a `PytestWarning: (rm_rf) error removing .../garbage-*:
  Directory not empty` on every run (pytest's own cross-session `tmp_path`
  garbage collection racing itself across workers). It is a warning, not a
  failure, is unrelated to the gpgsign root cause, and reproduces with or
  without the fix — out of scope for this PRD; worth a one-line mention in
  the PR/commit body so it isn't mistaken for a regression later.
- **A host with `commit.gpgsign` already false** (CI, most contributors)
  never saw this bug and will see no behavior change — the new `git config`
  line is a no-op override there.
- **Likely next changes this design should not box in**: (1) extending
  `-n auto` to the remaining mixed-directory `release-checks` blocks once
  someone proves those directories safe too — the per-block comment pattern
  here is what that future change edits, not a hardcoded allowlist; (2) a
  future wave fixture that spawns its own `git commit` outside `_repo()`
  needs the same `commit.gpgsign false` line — nothing here prevents that,
  but nothing auto-propagates it either, so a reviewer should grep for new
  `"init"` call sites in `test_wave*.py` additions.

## Test strategy outline

1. `test_parallel_safety.py::test_the_wave_pair_passes_under_two_workers` —
   fail-first against the real `_repo()`: measured this session, the hammer
   pair (both calling `_repo()` directly) failed 2 of 3 runs under `-n 2` at
   the current base commit, and passed 3 of 3 once `commit.gpgsign` was
   forced off. Record the base-commit failing run in the task's attempt
   entry; after the fixture fix lands, the meta-test (which wraps this same
   pair in a subprocess) is green.
2. Whole-directory parallel runs over `skills/run-autopilot/cli`, measured
   after the fix shipped with the host idle, three consecutive runs each:
   - shipped capped form, `-n auto --maxprocesses 4`: 1952 passed, 0 failed,
     153.96s (cold cache), 91.18s, 92.28s.
   - bare `-n auto` (18 workers on this host): 1952 passed, 0 failed, 77.86s,
     77.83s, 78.04s.
3. Serial baseline, same directory: 1951 passed, 1 skipped, 0 failed in 221s
   (the skip is the xdist-gated meta-test, which is intended). Capped is
   41.6% of serial and uncapped is 35.2%, both under the "half" success
   metric. These replace the earlier planning figures, which came from a
   simulated `GIT_CONFIG_GLOBAL=/dev/null` run with uncapped workers and are
   not what shipped.
4. `bash dev/bin/release-checks` green twice in a row after the converted
   blocks land.
5. `rg -c -- "-n auto" dev/bin/release-checks` ≥ 1 (4 after this change, one
   per converted block).

## Review log

Non-blockers and questions (recorded, not fixed):

- (non-blocker) The PRD's own Success Metrics phrase "its run-autopilot
  `cli` block passes `-n auto`" (singular) is satisfied by five separate
  `release-checks` blocks (custody core, l3, reporting, waves, enter)
  collectively, not one unified block — `release-checks` has always split
  `cli/` into many named blocks for failure-output granularity, and this
  design does not merge them (that would lose the per-block `echo` labels
  on failure). A reader expecting one block should read "block" as "the
  gate's `cli/`-only coverage."
- (question, dispatch 2 / codex) Whether the fail-first discipline this
  design now relies on (one real failing run of `test_parallel_safety.py`
  at the base commit, recorded in the attempt entry) is an acceptable
  substitute for a committed red state in git history, given the failure is
  probabilistic (2 of 3 runs, not 3 of 3) rather than deterministic. Left to
  the implementor: run it enough times at the base commit to get one clean
  failing capture before applying the fixture fix.

dispatch 1 (claude): cardinal-sin 0, blocker 1, non-blocker 2, question 2
dispatch 2 (codex): cardinal-sin 0, blocker 1, non-blocker 0, question 0
dispatch 3 (codex): cardinal-sin 0, blocker 0, non-blocker 0, question 0
