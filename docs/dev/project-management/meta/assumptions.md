# Assumption ledger

## PRD 00320-refuse-every-unsafe-verify-log-sink-v2

### Task 2 (implement the six-case refusal and exclusive sink open)

- `_open_log_sink` is handed the repo root as `root` (default `/`) so the
  strict `O_NOFOLLOW` descent starts at the trust boundary. The repo's OWN
  path is trusted: a checkout reached through a symlinked ancestor (a repo
  under macOS `/tmp`) is normal and must not be refused, while everything
  below the root is walked strictly. The design doc's contract gave
  `_open_log_sink(log_path)` only and told it to walk "from the toplevel
  downward", which the one-argument signature cannot do; the added parameter
  is what makes the documented walk possible, and `_run_locked_gate` passes
  `cwd`.
- The sink is created with mode `0o666` (builtin `open`'s mode), not
  `os.open`'s `0o777` default -- an executable sink would make the next run
  refuse its own log.
- Case 1 refuses a literal `docs/dev/project-management/` prefix match in
  addition to the inode walk, so a store path whose directory does not exist
  yet is still refused (it has no inode to compare).
- A failing `git rev-parse --show-toplevel` from `repo_root` fails closed as
  `resolves outside the repository`.
- Case 3's component walk can report a path outside the repo as
  `is a symlink` rather than `resolves outside the repository`; no test pins
  the reason text for that path, only exit 2.
- `repo_root` reaching `refuse()` is always absolute (as `__main__` and
  `run_gate`'s `cwd` provide it), so the walk's stop test matches by path
  equality; a relative `repo_root` would not stop the walk.
- A root/log spelling mismatch in `_pinned_parent_fd` raises `OSError`
  rather than `ValueError`, so a caller's existing handling of a refused
  sink covers it.
- The symlinked-root regression test asserts on `log_sink_refusal.refuse`
  directly rather than through a CLI `verify` run, to keep the two findings
  it separates from conflating.
