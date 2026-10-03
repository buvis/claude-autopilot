# Assumptions ledger — PRD 00240 (ignore nested store lock files)

## Task 2: Prove the recursive lock pattern against real git

Ivan (implementation):
- Used the same `_GIT_ENV` pattern (`GIT_CONFIG_GLOBAL=os.devnull`, `GIT_CONFIG_NOSYSTEM=1`) seen in `custody_testutil.py`'s real-git tests, to isolate the test from the user's global git config; inlined a minimal copy in the test module since it is test-local and not in the allowlist.
- `git init -q` without setting `user.name`/`user.email` is sufficient since the test never commits, only runs `status`.
- Content written to the synthetic `.lock`/`.json` files is arbitrary placeholder text (not specified by the contract).
