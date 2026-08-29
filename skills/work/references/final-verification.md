# Final Verification (step 7)

Moved verbatim out of `SKILL.md` step 7 (PRD 00119-v2; situational: read once
per work phase, after the last task completes). SKILL.md keeps the run-it-once
mandate, the stop condition and the phase-report line. The style-limit gate
that used to sit here as step 7.0 now runs per task at step 5.65
(`references/style-gate.md`).

## What to run

(Project-dependent — use the commands documented in `AGENTS.md` / `CLAUDE.md` / project README.)

- Full workspace tests — Rust: `cargo nextest run --workspace` when nextest is installed (probe once with `cargo nextest --version`; on any nextest infra error fall back to `cargo test --workspace` — doc-tests are NOT run by nextest, so add `cargo test --workspace --doc` when the project has doc-tests); otherwise `cargo test --workspace`. Other stacks: `pytest`, `npm test`
- Lint (e.g., `cargo clippy --workspace`, `ruff check`, `eslint .`)
- Smoke tests if the project defines them (e.g., `./tests/smoke.sh`)
- Integration / e2e tests if the project defines them (e.g., `./tests/integration.sh`, `cargo test -p <crate>-e2e`)
- Any project-specific "definition of done" checks

**When the repo documents no verification commands** (no test/lint/build commands in `AGENTS.md`/`CLAUDE.md`/README): do NOT silently skip verification. Detect the stack from its manifest and improvise the standard suite — `Cargo.toml` → `cargo test --workspace` (+ `cargo clippy --workspace`); `pyproject.toml`/`setup.py` → `pytest` (+ `ruff check` if configured); `package.json` → `npm test` (only if a `test` script exists). Run the improvised set, and **state the exact improvised command set in the phase report** (fail loud — an improvised suite must not read as the project's own documented one). If no stack manifest is detectable and nothing runs, record `verification: none (no suite found)` in the phase report and surface it as a gap for the review phase — never report the phase green on an unverified tree.

Run each as a separate Bash call. Do not chain with `&&`.

## Handling failures at this step

1. Identify which task(s) introduced the regression. The failing test output usually points at a specific module; cross-reference against the task commits.
2. Re-open the offending task via `task-start <task-id>`.
3. Dispatch Ivan with the failure output to fix it: re-render `ivan.md` using the **full** retry command shape in `references/gate-failure.md` § Retry render (every placeholder filled, explicit `--out`), with `FAILING_TESTS` filled from the step-7 failure output and `--set RETRY_INSTRUCTION="Fix only the regression identified below. Do not touch unrelated files or refactor adjacent code."`. The code-quality rules block is already permanent in `ivan.md`. Do NOT relax the failing test.
4. After the fix commits, re-run **only** the previously failing commands from step 7 (not the whole suite again) to confirm the fix.
5. Mark the task completed and re-sync.
6. Repeat until the full suite is green.

Max 3 fix cycles at this step before escalating to the user — regressions clustering here usually indicate a design issue that needs human input.
