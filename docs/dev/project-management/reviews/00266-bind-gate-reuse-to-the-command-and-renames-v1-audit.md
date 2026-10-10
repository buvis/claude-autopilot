# Decision Audit Log: 00266-bind-gate-reuse-to-the-command-and-renames-v1

PRD: `00266-bind-gate-reuse-to-the-command-and-renames-v1.md`
Started: 2026-10-07T20:15:13Z
Completed: 2026-10-07T20:15:13Z
Autonomous: 1  |  Deferred: 0  |  Doubts: 0

## Decisions

### 1. Change-list paths kept toplevel-relative, logged late (source: autonomous)

Logged 2026-10-10 by PRD 00270 task 10.

- **Shipped code:** the change list keeps toplevel-relative paths via
  `git status --porcelain --show-prefix`.
- **00266's task wording:** `--relative -- .` plus `-uall`.
- **What happened:** the 00266 review chose the toplevel-relative form and
  never logged the deviation; `-uall` was simply omitted. Without it a repo
  with `status.showUntrackedFiles=no` reuses a gate record over an untracked
  product file (false pass), an untracked store directory collapses to
  `?? docs/`, and a non-ASCII filename comes back quoted (false stale).
- **Resolution:** the toplevel-relative `--show-prefix` form stands. PRD 00270
  added `--untracked-files=all` and `-z` to close the untracked and quoting
  holes.
