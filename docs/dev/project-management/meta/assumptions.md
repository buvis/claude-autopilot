# Assumptions ledger — PRD 00308-reviewer-lane-resilience-v1

## 1: Replay kills its process group

- Using `files=["test_calc.py"]` with the sibling fixture (`_repo`, `HEAD_IMPL`, `HEAD_TESTS` from `test_replay_tests_against_base.py`) is a valid real worktree setup.
- A 3s grace poll is enough for the killed processes to be cleaned up before checking their pids.
- `/bin/sh` as the runner shell is fine for macOS and Linux.
- `git checkout --` counts as overwriting a file with its original content for Devon's cleanup obligation (no `rm` used).
- The current test failure before the implementation is the expected red state, since the test-only commit precedes it.
- 2.0s of slack above the timeout is enough on a loaded machine (later flagged by review as possibly too tight; left as a non-blocking LOW).
- The exact wording of the timeout skip reason is free, as long as it starts with "runner did not complete:" — the test only checks that a reason is returned.
