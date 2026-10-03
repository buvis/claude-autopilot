# Assumptions ledger — PRD 00240 (ignore nested store lock files)

## Task 2: Prove the recursive lock pattern against real git

Ivan (implementation):
- Used the same `_GIT_ENV` pattern (`GIT_CONFIG_GLOBAL=os.devnull`, `GIT_CONFIG_NOSYSTEM=1`) seen in `custody_testutil.py`'s real-git tests, to isolate the test from the user's global git config; inlined a minimal copy in the test module since it is test-local and not in the allowlist.
- `git init -q` without setting `user.name`/`user.email` is sufficient since the test never commits, only runs `status`.
- Content written to the synthetic `.lock`/`.json` files is arbitrary placeholder text (not specified by the contract).

## Task 4: [D1] Tail sweep — SKILL.md Retention parenthetical and test-assert precision

Ivan (implementation):
- The expected `git status` line for the `.json` record is `?? <path relative to tmp_path>`, because `tmp_path` is the repo root and no `core.quotePath` quoting applies to these ASCII names. The test passes, which confirms this.
- The `rg` check for other uses of `os` in the file ran after the `_GIT_ENV` deletion, so the orphan finding covered only the lines left at that point. It was the sole remaining `os` use.
- `tmp_path` is taken as the git work-tree root, as in the existing test, so `relative_to(tmp_path)` matches git's porcelain paths.

Orchestrator note: this task resolved the duplication that Task 2's first assumption above
announced ("inlined a minimal copy in the test module since it is test-local and not in the
allowlist"). The assumption named the shortcut; the cycle-1 review caught it as a Low finding; the
sweep imported the canonical `_GIT_ENV` from `cli.custody_testutil` instead. The ledger predicted
the finding one task ahead of the reviewers.
