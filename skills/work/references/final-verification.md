# Final Verification (step 7)

Moved verbatim out of `SKILL.md` step 7 (PRD 00119-v2; situational: read once
per work phase, after the last task completes). SKILL.md keeps the run-it-once
mandate, the stop condition and the phase-report line. The style-limit gate
that used to sit here as step 7.0 now runs per task at step 5.65
(`references/style-gate.md`).

## What to run

(Project-dependent — use the commands documented in `AGENTS.md` / `CLAUDE.md` / project README.)

Each bullet names its `timeout` class from `references/subagent-dispatch.md` §
Foreground command budgets — pass the value on the Bash call.

- Full workspace tests (**full suite**, 600000 ms in the foreground; backgrounded, the existing 20 min `Monitor` wait instead) — Rust: `cargo nextest run --workspace` when nextest is installed (probe once with `cargo nextest --version`; on any nextest infra error fall back to `cargo test --workspace` — doc-tests are NOT run by nextest, so add `cargo test --workspace --doc` when the project has doc-tests); otherwise `cargo test --workspace`. Other stacks: `pytest`, `npm test`
- Lint (**lint and narrow tests**, 300000 ms) (e.g., `cargo clippy --workspace`, `ruff check`, `eslint .`)
- Smoke tests if the project defines them (**lint and narrow tests**, 300000 ms) (e.g., `./tests/smoke.sh`)
- Integration / e2e tests if the project defines them (**full suite**, 600000 ms) (e.g., `./tests/integration.sh`, `cargo test -p <crate>-e2e`)
- Any project-specific "definition of done" checks (**lint and narrow tests**, 300000 ms)

**When the repo documents no verification commands** (no test/lint/build commands in `AGENTS.md`/`CLAUDE.md`/README): do NOT silently skip verification. Detect the stack from its manifest and improvise the standard suite — `Cargo.toml` → `cargo test --workspace` (+ `cargo clippy --workspace`); `pyproject.toml`/`setup.py` → `pytest` (+ `ruff check` if configured); `package.json` → `npm test` (only if a `test` script exists). Run the improvised set, and **state the exact improvised command set in the phase report** (fail loud — an improvised suite must not read as the project's own documented one). If no stack manifest is detectable and nothing runs, record `verification: none (no suite found)` in the phase report and surface it as a gap for the review phase — never report the phase green on an unverified tree.

Run each as a separate Bash call. Do not chain with `&&`, and never combine one
with an inspection — a read, list, search or diff — in the same call
(`references/subagent-dispatch.md` § Never combine inspection with
verification): the combined command has two ways to hang and one exit code.

## Timed-out commands

A command that hits its budget was attempted and returned no verdict. It is
neither passed nor skipped — `skipped:` is reserved for a check that was never
attempted at all.

1. Re-run it once at the next larger budget when its class has one: a lint,
   smoke or definition-of-done command re-runs at 600000 ms. A foreground full
   suite is already at the tool maximum, so it has no larger budget and gets no
   re-run — its **first** timeout is terminal and is recorded at once.
2. Record it in the phase report: name the command and the budget it blew,
   beside the `verification: none (no suite found)` line this step already uses
   for an unverified tree. The phase report is a step-7 timeout's **whole**
   record — every task's attempt entry was appended at its own exit (step 6's
   `task-done`), before this step runs, so there is no live entry to stamp.
   Step 5.5's narrow tests, which run while their task is still in flight,
   stamp `verification: "timeout:<command>"` on that task's attempt instead
   (`references/attempt-logging.md` § Best-effort gate stamps).
3. The phase proceeds from there — the record is a fail-loud marker, not a
   block. Never report a timed-out command as a green one, and never silently
   retry it a third time.

## Handling failures at this step

1. Identify which task(s) introduced the regression. The failing test output usually points at a specific module; cross-reference against the task commits.
2. Re-open the offending task via `task-start <task-id>`.
3. Dispatch Ivan with the failure output to fix it: re-render `ivan.md` using the **full** retry command shape in `references/gate-failure.md` § Retry render (every placeholder filled, explicit `--out`), with `FAILING_TESTS` filled from the step-7 failure output and `--set RETRY_INSTRUCTION="Fix only the regression identified below. Do not touch unrelated files or refactor adjacent code."`. The code-quality rules block is already permanent in `ivan.md`. Do NOT relax the failing test.
4. After the fix commits, re-run **only** the previously failing commands from step 7 (not the whole suite again) to confirm the fix.
5. Mark the task completed and re-sync.
6. Repeat until the full suite is green.

Max 3 fix cycles at this step before escalating to the user — regressions clustering here usually indicate a design issue that needs human input.
