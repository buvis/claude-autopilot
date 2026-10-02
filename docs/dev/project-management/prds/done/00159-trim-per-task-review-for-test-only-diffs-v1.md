---
catchup: skip
design: skip
---

# Trim per-task review for test-only diffs

Source: `dev/local/discovery/00157-autopilot-efficiency-policies.md`, PRD 1 of 3 (must-haves 1-8, Q2-Q5, Q11-Q12). PRD 00160 (planner tier routing) reuses the path predicate this PRD adds; PRD 00161 (Codex hook doctor) is independent.

## Overview

### Problem Statement

A recent 12-task PRD paid the full per-task pipeline for every task, including test-only work: a self-deslop dispatch, a Pat review that re-ran tests and read around the repo, and a mandatory Ivan retry for every MEDIUM finding even when the finding was about naming or duplication. `/autopilot:work` step 5.6 skips deslop only below 30 net lines, step 5.7 skips Pat only on `haiku` and for docs/config task classes, Pat's lane (`sonnet-run.sh` with no permission flags) can still call tools, and Pat's contract has no severity semantics, so a maintainability MEDIUM costs one Ivan dispatch and a Pat re-run (PRD 00140). When Pat's reply breaks the `SEVERITY | file:line | issue | fix` shape there is no defined retry at all. The fresh-session PRD review already re-reviews every task's diff through every lens, so this per-task work adds little signal.

### Target Users

The operator draining PRD batches with `/autopilot:run-autopilot`, and the `/autopilot:work` orchestrator session that must apply the policy headlessly, with no one to ask.

### Success Metrics

- Deterministic dispatch counts, pinned by tests: a test-only diff dispatches zero self-deslop subagents and zero Pat reviewers; an invalid Pat reply causes at most one more Pat dispatch (two calls total); a style, DRY or maintainability finding causes zero Ivan retries.
- Pat's dispatch carries `--tools ""`, so a Pat run makes zero tool calls; the test status Pat judges from is the recorded step-5.5 result.
- `skills/work/scripts/test_dispatch_prose.py::test_work_skill_body_stays_under_the_500_line_ceiling` stays green (SKILL.md is 495 lines by that test's count today; 5 lines of headroom).
- Post-release signal (the batch runs the installed plugin cache, not this tree): the first batch after release shows attempts stamped `self_deslop: "skipped:test-only"` and `review: "skipped:test-only"` on its test-only tasks, and no `medium-retry:` stamp whose finding was style, DRY or maintainability.

## Functional Decomposition

### Capability: Test-only gate
Decide from the committed diff alone, at execution time, whether the self-deslop and Pat lanes run.

#### Feature: Test path predicate
- **Description**: One conservative, shared predicate that says whether a repo-relative path is test or fixture code.
- **Inputs**: a path string (repo-relative, forward slashes) or a list of them.
- **Outputs**: `is_test_path(path) -> bool`; `test_only_diff(paths) -> bool`; `test_only_gate(paths, in_rework) -> dict[str, str]`.
- **Behavior**: `is_test_path` is true when any directory segment is one of `test`, `tests`, `__tests__`, `spec`, `specs`, `fixtures`, `__fixtures__`, `__snapshots__`, `testdata`, or the basename is `conftest.py` or matches `test_*.py`, `*_test.py`, `*_test.go`, `*.test.{js,jsx,ts,tsx,mjs,cjs}`, `*.spec.{js,jsx,ts,tsx,mjs,cjs}`, `*_spec.rb`, `*Test.java`, `*Tests.java`, `test_*.sh`, `*_test.sh`. Nothing else qualifies: `src/lib.rs` with an inline `#[cfg(test)]` module, `testing/x.py`, `contest/x.py`, `README.md` and `hooks/x.py` are production. Segment and basename matches are exact and case-sensitive. `test_only_diff` is `bool(paths) and all(is_test_path(p) for p in paths)`; an empty list is never test-only. `test_only_gate` returns `{}` unless `test_only_diff(paths)`; then `{"self_deslop": "skipped:test-only"}`, plus `"review": "skipped:test-only"` only when `in_rework` is false (a rework task keeps Pat: its CLOSURE verdicts are what stop a second review cycle, the same reason the micro lane keeps him).

#### Feature: Task base SHA and committed-path listing
- **Description**: A single diff base every later step reads.
- **Inputs**: step 2's `task-start` call.
- **Outputs**: `<task_base_sha>` held in-session; the path list `git diff --name-only <task_base_sha>..HEAD`.
- **Behavior**: Right after `task-start`, step 2 runs `git rev-parse HEAD` and holds it as `<task_base_sha>`. It equals the parent of the test commit when step 2.9 committed tests, and is also defined for test-only, docs-only, config-only and micro-lane tasks, where no test commit exists and step 5.7's `BASE_SHA` is undefined today. Step 5.6, step 5.7 and `BASE_SHA` all read it; `<test_commit_sha>` keeps its one remaining reader, the step-5.5 ESCALATE reset.

#### Feature: Skip stamps
- **Description**: Every skip is visible in attempt data.
- **Inputs**: the gate's verdict.
- **Outputs**: `self_deslop: "skipped:test-only"`, `review: "skipped:test-only"` on the attempt record; both named in the phase report.
- **Behavior**: Step 5.6 checks the gate before the 30-line/2-file rule and records the stamp without dispatching. Step 5.7 checks it after the tier gate (a `haiku` task still records nothing) and outside rework mode; every tier, `fable` included, takes the skip. Any production or unknown path falls through to today's pipeline unchanged.

### Capability: Diff-only Pat
Pat judges only what the prompt carries.

#### Feature: Tool-less reviewer dispatch
- **Description**: `sonnet-run.sh` gains `-t, --tools LIST`, passed to `claude` as `--tools LIST`; the step-5.7 dispatch passes `-t ""`.
- **Inputs**: the flag and its value (an empty string means no tools, per `claude --help`).
- **Outputs**: the pair `--tools <LIST>` in the child argv, in `--print` mode.
- **Behavior**: Absent `-t`, the argv is byte-identical to today (the T1 exact-argv lock in `test_sonnet_run.sh` stays green). `-t` without a value is a usage error on stderr, exit non-zero, no dispatch.

#### Feature: Recorded verification and severity semantics in the persona
- **Description**: `agents/pat.md` gains a `## Recorded verification` section carrying `{VERIFICATION_RESULT}`, a diff-only instruction, and severity semantics; the simplification mandate maps to LOW.
- **Inputs**: `dev/local/tmp/review-task-<id>-verification.txt`, written by the orchestrator with the Write tool: the exact step-5.5 command(s), each exit code and the runner's own summary line (for example `12 passed in 0.4s`), or the literal attempt value `verification: skipped:<cause>` when step 5.5 could not run.
- **Outputs**: the rendered prompt; findings whose severity encodes the retry rule.
- **Behavior**: The persona says, verbatim in spirit: judge only from this prompt (the diff, the task text, the recorded verification); do not read other files, run commands or re-run tests. Under `## Reporting contract` it states: MEDIUM is reserved for a correctness or security defect this diff introduces that its tests do not catch (a wrong result, an unhandled error path, data loss, injection, secret exposure, a missing authorization check); style, naming, duplication, structure, maintainability and every behavior-preserving simplification are LOW, whatever their size, and a LOW is noted, never retried in this loop. `skills/work/references/simplification-mandate.md` replaces its "Classify ... as **Important**, not Minor" paragraph with: report each concrete behavior-preserving simplification as a LOW finding with file:line, the current shape and the simpler replacement; LOW findings are carried to the PRD-level review, never retried here. The output shape (`SEVERITY | file:line | issue | fix`, `NO FINDINGS`, `CLOSURE` lines) is unchanged, so the SKILL.md MEDIUM-in-task retry row needs no edit: the severity now guarantees a MEDIUM is correctness or security. `tools: Read` stays in the frontmatter (the registry test pins it; the CLI lane never reads it).

### Capability: Output-contract enforcement
An invalid reply costs one correction, never a silent pass.

#### Feature: Review output parser
- **Description**: `skills/work/scripts/parse_review.py <output-file>` (stdlib) validates and parses Pat's reply.
- **Inputs**: the `-o` file of the sonnet run.
- **Outputs**: stdout JSON `{"no_findings": bool, "findings": [{"severity", "file", "issue", "fix"}], "closures": [{"verdict", "finding", "evidence"}]}`; exit 0 valid, exit 1 invalid (stderr `parse_review: <reason>: <offending line>`), exit 2 file missing or empty.
- **Behavior**: Lines are stripped; blank lines ignored. A line whose first ` | ` field is CRITICAL, HIGH, MEDIUM or LOW (matched case-insensitively, emitted uppercase) must split into exactly four fields on ` | ` (maxsplit 3) or the output is invalid; a line whose first field is `CLOSURE` must have four fields with `resolved` or `unresolved` second; the exact line `NO FINDINGS` marks an empty review; every other line is prose and ignored. The output is valid iff it holds at least one finding, closure or `NO FINDINGS` line, no malformed prefixed line, and not both `NO FINDINGS` and a finding.

#### Feature: One correction retry
- **Description**: An invalid reply is retried once with a terse contract correction through the `{CONTRACT_CORRECTION}` placeholder.
- **Inputs**: parser exit 1; the fixed correction text in `references/per-task-review.md`: "Your previous reply did not follow the reporting contract. Reply again with only lines of the form `SEVERITY | file:line | issue | fix` (CRITICAL/HIGH/MEDIUM/LOW), CLOSURE lines where the description carries a findings block, or the single line `NO FINDINGS`. No other text."
- **Outputs**: a second dispatch, or `review: "failed:invalid_output"` on the attempt record and in the phase report.
- **Behavior**: The initial render passes `--set CONTRACT_CORRECTION=""` (the `RETRY_INSTRUCTION` idiom); the retry re-renders `pat.md` with every other flag identical and the correction text set, then dispatches once. A second exit 1 records `review: "failed:invalid_output"` and proceeds to step 6; the mandatory PRD review catches what Pat missed. Exit 2 stays the existing runner-failure row (retry once, then `review: failed:<cause>`). A valid reply feeds the existing ladder (CLOSURE, CRITICAL/HIGH, MEDIUM-in-task, LOW) from the parsed JSON; each re-run inside that ladder is parsed the same way, with the same single correction.

## Structural Decomposition

### Repository Structure

```
skills/work/
├── SKILL.md                              # Maps to: steps 2, 5.6, 5.7 (edits, net <= +4 lines)
├── scripts/
│   ├── work_routing.py                   # Maps to: Test path predicate
│   ├── test_work_routing.py              # Maps to: Test path predicate (tests)
│   ├── parse_review.py                   # Maps to: Review output parser
│   ├── test_parse_review.py              # Maps to: Review output parser (tests)
│   └── test_dispatch_prose.py            # Maps to: prose pins for every edit below
└── references/
    ├── per-task-review.md                # Maps to: Test-only skip, -t "" dispatch, parse + correction retry
    ├── self-deslop-prompt.md             # Maps to: Test-only skip (step 5.6 procedure)
    ├── simplification-mandate.md         # Maps to: severity semantics (LOW)
    ├── gate-failure.md                   # Maps to: Task base SHA (§ Test-commit SHA rewording)
    └── attempt-logging.md                # Maps to: Skip stamps (schema)
skills/use-sonnet/scripts/
├── sonnet-run.sh                         # Maps to: Tool-less reviewer dispatch
└── test_sonnet_run.sh                    # Maps to: Tool-less reviewer dispatch (tests)
agents/pat.md                             # Maps to: Recorded verification and severity semantics
skills/review-work-completion/references/agent-registry.md   # Maps to: placeholder table
skills/run-autopilot/references/state-schema.md              # Maps to: Skip stamps (schema)
CHANGELOG.md
```

### Module: work-routing
- **Maps to capability**: Test-only gate
- **Responsibility**: the pure predicates; `route()` and every existing function stay byte-identical.
- **Exports**: `is_test_path(path)`, `test_only_diff(paths)`, `test_only_gate(paths, in_rework)`

### Module: review-parser
- **Maps to capability**: Output-contract enforcement
- **Responsibility**: validate and parse one Pat reply; no I/O beyond reading the file.
- **Exports**: CLI `parse_review.py <output-file>`; `parse(text) -> dict` raising `ValueError` on invalid input.

### Module: sonnet-runner
- **Maps to capability**: Diff-only Pat
- **Responsibility**: the `-t/--tools` passthrough.
- **Exports**: CLI flag `-t, --tools LIST`

### Module: pat-persona
- **Maps to capability**: Diff-only Pat
- **Responsibility**: `agents/pat.md` placeholders `{VERIFICATION_RESULT}` and `{CONTRACT_CORRECTION}`, the diff-only instruction, severity semantics; the mandate's LOW paragraph; both placeholders added to the registry table.
- **Exports**: none (prose)

### Module: work-prose
- **Maps to capability**: all three
- **Responsibility**: SKILL.md step 2 (`<task_base_sha>`), 5.6 (gate first), 5.7 (gate, `BASE_SHA` = `<task_base_sha>`, two render flags, parse pointer); the reference procedures; the two schema docs; prose pins; CHANGELOG.
- **Exports**: none (prose)

## Dependency Graph

### Foundation Layer (Phase 0)
No dependencies - built first.

- **work-routing**: the predicate and the gate.
- **review-parser**: the validator.
- **sonnet-runner**: the flag.

### Core Layer (Phase 1)
- **pat-persona**: Depends on [] (its placeholders are filled by work-prose; nothing runs from the checkout mid-PRD).

### Integration Layer (Phase 2)
- **work-prose**: Depends on [work-routing, review-parser, sonnet-runner, pat-persona] (it names every symbol, flag and placeholder they define).

## Implementation Phases

### Phase 0: Foundation
**Goal**: The three mechanisms exist and are tested in isolation.

**Tasks**:
- [ ] Add `is_test_path`, `test_only_diff`, `test_only_gate` to `skills/work/scripts/work_routing.py` with tests in `test_work_routing.py`: `tests/foo.py` and `skills/work/scripts/fixtures/x.txt` are test paths; `test_x.py`, `x_test.go`, `x.test.ts`, `x.spec.js`, `conftest.py` are test paths; `src/lib.rs`, `testing/x.py`, `contest/x.py`, `README.md`, `hooks/x.py` are not; a mixed list is not test-only; an empty list is not test-only; the gate skips both lanes outside rework and keeps `review` in rework (no deps) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/work/scripts/test_work_routing.py` green; `git diff --stat HEAD -- skills/work/scripts/work_routing.py` shows only additions (no existing line changed).
- [ ] Add `skills/work/scripts/parse_review.py` and `test_parse_review.py` covering: two findings parse to JSON with uppercase severities; `NO FINDINGS` parses with `no_findings: true`; CLOSURE lines parse; a prose preamble line is ignored; `MEDIUM: file.py:12 - issue` exits 1 naming the line; a reply with no contract line exits 1; `NO FINDINGS` plus a finding exits 1; an empty file exits 2 (no deps) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/work/scripts/test_parse_review.py` green; `python3 skills/work/scripts/parse_review.py /dev/null` exits 2.
- [ ] Add `-t, --tools LIST` to `skills/use-sonnet/scripts/sonnet-run.sh` (prompt mode: `--tools "$LIST"` appended before the prompt) and three cases to `test_sonnet_run.sh`: `-t ""` yields the argv pair `--tools` `""`; `-t Read` yields `--tools` `Read`; `-t` with no value exits non-zero on stderr with no claude invocation (no deps) - Acceptance: `bash skills/use-sonnet/scripts/test_sonnet_run.sh` prints `0 failed`, T1's exact-argv lock included.

**Exit Criteria**: All three suites green; no existing test edited.

### Phase 1: Core
**Goal**: The persona carries the new contract.

**Tasks**:
- [ ] Edit `agents/pat.md` (add `## Recorded verification` with `{VERIFICATION_RESULT}` and the diff-only instruction; add the severity-semantics paragraph under `## Reporting contract`; add `{CONTRACT_CORRECTION}` as the last line of the body; keep `tools: Read`), rewrite the LOW paragraph in `skills/work/references/simplification-mandate.md`, and add both placeholders to the table in `skills/review-work-completion/references/agent-registry.md` (depends on: Phase 0) - Acceptance: `rg -n "VERIFICATION_RESULT|CONTRACT_CORRECTION" agents/pat.md skills/review-work-completion/references/agent-registry.md` hits in both files; `rg -n "Important, not Minor" skills/work/references/simplification-mandate.md` has no hit and `rg -n "LOW" skills/work/references/simplification-mandate.md` hits; `rg -n "maintainability" agents/pat.md` hits on a line that also contains `LOW`; `uv run --no-project --with pytest python -m pytest -q skills/review-work-completion/scripts/test_agent_registry.py` green.

**Exit Criteria**: Registry suite green; the persona renders with `render_prompt.py` once both new placeholders are set.

### Phase 2: Integration
**Goal**: `/autopilot:work` applies the policy and every stamp is documented and pinned.

**Tasks**:
- [ ] Edit `skills/work/SKILL.md`: step 2 item 1 captures `<task_base_sha>`; step 5.6 lists `git diff --name-only <task_base_sha>..HEAD` and applies `test_only_diff` before the 30-line/2-file rule, recording `self_deslop: "skipped:test-only"`; step 5.7 applies `test_only_gate` after the tier table (outside rework mode) recording `review: "skipped:test-only"`, sets `BASE_SHA` = `<task_base_sha>`, adds `--set-file VERIFICATION_RESULT=dev/local/tmp/review-task-<id>-verification.txt` and `--set CONTRACT_CORRECTION=""` to the render block, and points at the parse-and-correct procedure. Write the procedures: `references/per-task-review.md` (§ Test-only diffs; the dispatch line becomes `sonnet-run.sh -t "" -f ... -o ...`; § Result handling opens with `parse_review.py`, the correction text verbatim, the one retry, `review: "failed:invalid_output"`), `references/self-deslop-prompt.md` (§ Test-only diffs), `references/gate-failure.md` § Test-commit SHA (`BASE_SHA` is `<task_base_sha>` from step 2) (depends on: Phase 1) - Acceptance: `uv run --no-project --with pytest python -m pytest -q skills/work/scripts/test_dispatch_prose.py` green, the 500-line ceiling test included; `rg -n "task_base_sha" skills/work/SKILL.md skills/work/references/gate-failure.md` hits in both; `rg -n '\-t ""' skills/work/references/per-task-review.md` hits; `rg -n "parse_review.py|failed:invalid_output" skills/work/references/per-task-review.md` hits both strings.
- [ ] Enumerate the new values in `skills/work/references/attempt-logging.md` (`self_deslop` gains `"skipped:test-only"`; `review` gains `"skipped:test-only"` and `"failed:invalid_output"`, with semantics) and in `skills/run-autopilot/references/state-schema.md` (the `tasks[].attempts[].self_deslop` row and a `review` entry in the `tasks[].attempts` signature); add prose pins to `test_dispatch_prose.py` (step 2 names `task_base_sha`; step 5.6 names `skipped:test-only`; step 5.7 names `skipped:test-only`, `VERIFICATION_RESULT`, `CONTRACT_CORRECTION`; `per-task-review.md` names `parse_review.py`, `failed:invalid_output` and `-t ""`; `attempt-logging.md` lists both new `review` values; `pat.md` names both placeholders; `simplification-mandate.md` lacks `Important, not Minor`); add the CHANGELOG lines (feat commits: `**work**` under Added for the test-only skip, the tool-less recorded-verification Pat with correctness/security MEDIUM, and the invalid-output retry; `**use-sonnet**` under Added for `-t/--tools`) (depends on: Phase 2 task 1) - Acceptance: `rg -n "skipped:test-only|failed:invalid_output" skills/work/references/attempt-logging.md skills/run-autopilot/references/state-schema.md` hits in both files; `uv run --no-project --with pytest python -m pytest -q skills/work/scripts/test_dispatch_prose.py` green; `rg -n "^- \*\*(work|use-sonnet)\*\*" CHANGELOG.md` hits under `[Unreleased]`.

**Exit Criteria**: `uv run --no-project --with pytest --with rich --with textual python -m pytest -q skills/work/scripts skills/review-work-completion/scripts skills/run-autopilot` green; `bash skills/use-sonnet/scripts/test_sonnet_run.sh` green; `bash dev/bin/release-checks` green.

## Test Strategy

### Critical Scenarios
- **Happy path**: a task commits `skills/work/scripts/test_parse_review.py` and `skills/work/scripts/fixtures/pat-reply.txt` only → `test_only_gate` returns both skip stamps; step 5.6 and 5.7 dispatch nothing; the attempt carries `self_deslop: "skipped:test-only"` and `review: "skipped:test-only"`.
- **Edge case**: the same diff plus `skills/work/scripts/parse_review.py` → not test-only; the normal pipeline runs; a rework task with a test-only diff → deslop skipped, Pat dispatched.
- **Edge case**: Pat's reply is `LOW | a.py:3 | duplicated helper | inline it` → parsed valid, noted, zero Ivan retries; `MEDIUM | a.py:3 | swallowed OSError | re-raise` inside the task's files → one retry as today.
- **Error case**: Pat replies in prose → `parse_review.py` exits 1 → one re-dispatch with the correction → still prose → `review: "failed:invalid_output"`, task proceeds, two Pat calls total.
- **Error case**: `sonnet-run.sh -t` with no value → exit non-zero, no child process.

## Risks

- **Misclassifying a mixed diff as test-only**: the predicate is a closed list matched exactly, the diff is re-listed from git at execution time, and any non-matching path falls through to the full pipeline.
- **Severity-label gaming (a real bug filed as LOW to dodge a retry)**: the semantics are in the persona and pinned by tests; the PRD-level review lenses re-review every diff and are untouched by this PRD.
- **A tool-less Pat loses context it used to fetch**: the diff, the task text and the recorded verification are the only inputs by design (discovery Q4); a gap surfaces as a wrong finding the PRD review corrects, not as a silent pass.
- **SKILL.md headroom (5 lines)**: every added line is offset by moving mechanics to the references; the ceiling test is the gate, and the task fails loud rather than raising it.
