# Assumptions ledger — PRD 00311-verify-reports-what-the-gate-did-v1

## 1: Write test_verify_truth.py pinning the six verify-truth reproductions

- "SIGKILL the verify subprocess at 0.5s": the test waits until gate A's first tick appears (so a gate has spawned), then kills at 0.5s after launch or right away if that has passed. Starting the CLI can take longer than 0.5s.
- The fixture repo is `tmp_path/"repo"`, not `tmp_path`, so gate scripts and tick or pgid files sit outside the repo and are not dirt.
- verify is run as `sys.executable skills/run-autopilot/cli/__main__.py verify --gate-command ... --repo-root ...`.
- The exact `tests_line` strings in the `run_gate_line` test come from the design, because the contract does not spell them out: `Tests: (gate skipped: another gate held the lock for {int(GATE_TIMEOUT_S)}s)` and `Tests: (gate skipped: HEAD moved during the lock wait)`.
- "dirty_paths present" is checked as `out.get("dirty_paths") == fake["dirty_paths"]` (`[]`).
- The exit-2 refusals use `--log docs/dev/project-management/gate.log` for the store log, and a freshly `git init`-ed repo with no commits for the HEAD-resolution refusal.
- The fake lock-timeout result in the `run_gate_line` test uses `timed_out False`, matching the contract.
