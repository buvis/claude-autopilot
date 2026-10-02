# Review verification — PRD 00176, cycle 2

Reviewed HEAD: `31fe06b59973374da818a116ec4b3606845049d6`.
Incremental base: `ece9ac34053a17e9629e9af50355e7c84dc32fe2`.

## Deterministic checks

- `git diff --check ece9ac34053a17e9629e9af50355e7c84dc32fe2 HEAD`: exit 0.
- `git status --short`: empty. Review coordinator made no tracked edits.
- Mechanical AST facts: `_repair_known` 42 lines; `_write_repair` 17; `_remove_orphaned_empty` 22. Changed Python files contain 466 and 362 lines.
- Tautology scan: 9 test functions checked; no `[MECH]` findings.
- Replay initial attempt: skipped because sandbox denied `.git/worktrees/wt` metadata creation. Exact command forwarded to parent for escalation; no child escalation requested.
- Pack attempt: `engram pack --cycle 00176-02 --prd /Users/bob/git/src/github.com/buvis/claude-autopilot/dev/local/prds/wip/00176-guard-the-target-reads-in-the-doctor-v1.md --capsule dev/local/meta/project-capsule.md` returned exit 1: `not inside a registered repo`. Prompts use `(no pack available this cycle)`.

## Reviewer dispatch

Both real wrappers were invoked unchanged with the staged prompt paths. Each returned exit 3, `refusing nested dispatch (already inside a CLI agent)`, on its initial attempt and one retry. `[RETRY] Bob attempt 1/1`; `[RETRY] Carl attempt 1/1`. No real backend launched and no dispatch guard was bypassed. Carl is unavailable for this cycle, not permanently unavailable. Bob uses a native fresh fallback. Alice, Blake, and Bob each use `fork_turns=none`; all are native Codex subagents in this host adapter, so there is no model diversity. Initial Bob fallback dispatch hit the thread limit; retry after Alice finished succeeded. No task store, state, or verification queue was created.

## Verified residual findings

`/Users/bob/.local/share/mise/installs/python/3.12.13/bin/python -B dev/local/tmp/review-probe-00176-02.py` returned exit 0. It first executes Blake's lstat-boundary injection with two stale known targets, then a real mode-0444 temporary-file reproduction inside `TemporaryDirectory`.

```text
is_symlink OSError:
{'exit_code': 2, 'stdout': '', 'stderr': "error: [Errno 13] Permission denied: '/virtual-review/hooks/protect_config.py'\n"}
before: True b'pre-existing operator data\n'
verdict: unrepairable
detail: [Errno 13] Permission denied: '<temporary-directory>/protect_config.py.tmp'
temp exists after: False
target bytes after: b'X = 1\n'
```

The symlink metadata probe substitutes the external I/O result, not an exception in the repair code. It demonstrates the unguarded `Path.is_symlink()` failure mode present on Python 3.12.13. The temp deletion reproduction uses real filesystem permissions under a writable directory, and proves the existing `.tmp` is deleted even though write failed before creating/truncating it. The symlink guard was already absent before this PRD; Blake raises it as a remaining stated error-handling gap. The cleanup deletion was introduced in the PRD's original guarded-write work and carried through this cycle's extraction.

`/Users/bob/.local/share/mise/installs/python/latest/bin/python -B dev/local/tmp/review-duplicate-probe-00176-02.py` returned exit 0. With a dangling `hooks/a_dangling.py` symlink and a later `hooks/z_empty.py` placeholder, real `repair()` returns:

```text
('unrepairable', '<hooks>/a_dangling.py', 'no canonical source for unknown hook (missing)')
('unrepairable', '<hooks>/a_dangling.py', "[Errno 2] No such file or directory: '<hooks>/a_dangling.py'")
('removed', '<hooks>/z_empty.py', '')
rows for dangling target: 2
later orphan removed: True
```

This duplicate row is introduced by this cycle's orphan cleanup handler. Probe temporary directories clean themselves; only review evidence scripts remain in dev/local/tmp.

## Parent verification

- Full suite: **2610 passed, 0 failed, 1 skipped, 459 subtests passed**, 4 existing warnings, in 76.99s. Counts reused from the matching `last-verification.json` at reviewed HEAD; the parent ran the mandatory foreground suite, so no duplicate suite was launched here. The immutable record copy is `dev/local/tmp/review-verification-record-00176-02.json`.
- Release checks: **224 passed**, exit 0, parent-run at the same HEAD and recorded in the matching verification record. Host markers were removed only for that hermetic stub-test command; real reviewer dispatch retained every recursion guard.
- Doctor scripts suite: **85 passed**, builder-observed at reviewed HEAD.
- Mechanical fail-first replay against `ece9ac34053a17e9629e9af50355e7c84dc32fe2`: **3 touched cases ran, 3 failed against base, 0 passed, 0 collection failures**. Parent executed the exact replay command after the child sandbox denial. Output is `dev/local/tmp/replay-output-00176-02.md`.
- Tautology scan: **9 test functions checked, no findings**. Together with the replay, there are no `[MECH]` findings to absorb.
- `git diff --check ece9ac34053a17e9629e9af50355e7c84dc32fe2 HEAD` passed against reviewed HEAD.

The single skip is the existing golden transcript baseline test, whose local fixture is absent. The four warnings are the existing legacy bare-string completed-PRD schema warnings, unchanged from cycle 1. The final parent verification arrived after the independent reviewers returned; it resolves their pending-runtime notes and does not alter their source findings.

## Fail-first replay (computed, do not re-judge)

Touched tests from HEAD, run against the pre-change code at `ece9ac34053a`
(HEAD's test files overlaid on a base worktree). A test that passes there
does not pin this change. A behavior-preserving refactor's tests pass by
design, so weigh the PRD's intent before raising one. `mech-check` is the finder.

Replay: 3 touched test(s) ran, 3 failed against base, 0 passed; 0 test file(s) could not be collected at base (their tests fail there). Command: uv run --no-project --with pytest python -m pytest
