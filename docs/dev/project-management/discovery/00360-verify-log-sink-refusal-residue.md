# Discovery: Verify log-sink refusal residue

## Classification
Depth: light | Date: 2026-10-18 | Status: pre-elicitation (triage of batch 202610161547's deferred findings on PRD 00320, no questions asked yet)

## Problem
PRD 00320 (refuse every unsafe `autopilot verify --log` sink) capped out at
cycle 2 with one HIGH and fourteen Medium/Low findings unresolved. Verified
at HEAD e8ca2f7 on 2026-10-18:

- HIGH, hold stub 00328 (ledger key 6da9cfe213cf, consensus 3/4): a `.git`
  file with a relative `gitdir:` pointer is still not refused.
  `_worktree_gitdir_pointer` (`skills/run-autopilot/cli/log_sink_refusal.py:122-137`)
  returns `Path(text.split(":", 1)[1].strip())` unanchored; `os.path.samefile`
  then resolves it against the process cwd, raises, and the `except OSError:
  continue` at line 107 swallows it, so `_open_log_sink` would unlink and
  recreate that `.git` file. Bob's cycle-2 line names the fix: `if not
  pointer.is_absolute(): pointer = resolved.parent / pointer`.
- Medium: the nested-repo refusal is locale-dependent and fails open
  (`_in_nested_repo` matches the English `"work tree"` in git's stderr; a
  translated `LC_ALL` reads as "not nested"); a nested `.git` path whose
  parent does not exist yet (`nested/.git/refs/heads/newdir/ref`) returns
  None because `_git(resolved.parent, ...)` raises `FileNotFoundError`;
  `_worktree_gitdir_pointer` slurps the whole candidate file to test a
  seven-byte prefix, twice per verify run; containment (case 4) runs before
  the symlink walk (case 3), so a symlink resolving outside the toplevel
  reports `resolves outside the repository` instead of `is a symlink`; two
  cycle-2 tests assert only `result is not None`;
  `test_run_gate_refuses_a_symlinked_log_and_leaves_its_target` binds the
  tracked case, not the symlink case its comment claims.
- Low: two tests pin the same containment early return; `_pinned_parent_fd`
  raises a bare `OSError` for an absolute `--log` spelled through a different
  root than `--repo-root` (exit 2 without the stated JSON shape); a leaf
  swapped between the refusal and `os.unlink` is deleted; the `gitdir:` loop
  compares against the store target where it can only yield the wrong reason;
  a stale comment from the cycle-1 R2 fix.

Accepted deviations recorded by review-close and closed in this triage: the
nested-repo refusal and `_open_log_sink`'s `root` parameter are additions
beyond the PRD (a safe superset); every refusal reason folds into a dirty
result; `_descend` creates parent directories after the refusal passes;
three relocated tests pass at base by design; `refuse` runs twice per gate
run on purpose (the TOCTOU the second check closes).

## Requirements (candidate, to be elicited)

### Must have
- F1: anchor a relative `gitdir:` pointer on `resolved.parent` before the
  identity compare, with a regression test on a `worktree.useRelativePaths`
  worktree and on a submodule.
- F2: replace the stderr-sniffing nested-repo probe with `git rev-parse
  --is-inside-git-dir` (not localized), and walk the lexical ancestors for a
  `.git` entry below the toplevel when the sink's parent does not exist.
- F3: read a bounded prefix in `_worktree_gitdir_pointer`.
- F4: the cycle-2 tests assert the exact reason string.

### Nice to have
- The Low items above, swept in one tail task.

### Out of scope
- Re-ordering cases 3 and 4 (refusal and exit code are unchanged; the
  reason text differs).

## Constraints
- The refusal is security-critical (it guards a destructive write on
  master); every change ships with a test that fails on the old code.
- `lane: full` and `default_model: opus` as in 00320 v2.

## Codebase Context
- `skills/run-autopilot/cli/log_sink_refusal.py` (`refuse`,
  `_identity_targets`, `_worktree_gitdir_pointer`, `_in_nested_repo`,
  `_symlinked_component`).
- `skills/run-autopilot/cli/test_verify_log_refusal.py`,
  `skills/run-autopilot/cli/test_verify_truth.py`.
- Review evidence: `reviews/00320-refuse-every-unsafe-verify-log-sink-v2-review-2.md`,
  Bob's cycle-2 output `docs/dev/tmp/bob-output-00320c2.txt` lines 13-16.

## Approach (candidate)
One card-sized PRD for F1-F4 on the fast-track lane; the Low items as its
tail.

## Success Criteria (candidate)
- `autopilot verify --log <worktree>/.git` with a relative pointer exits 2
  naming the git-directory reason, under `LC_ALL=de_DE.UTF-8` as well.

## Risks
- A nested-repo probe by plumbing may behave differently on git versions
  before 2.20; pin the minimum git version in the test.

## Open Questions
- Keep the gitfile pointer check and the nested-repo probe (beyond the v2
  spec) as named requirements, or state the spec as "any git directory,
  linked or nested"?

## Discovery Log

### Inferred (not asked)
- Hold stub 00328 is closed into done/ with a note naming this document;
  the deferred ledger rows carry `disposition: discovery 00360`.
