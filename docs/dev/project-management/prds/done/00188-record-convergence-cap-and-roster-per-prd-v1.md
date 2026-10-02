---
catchup: skip
design: skip
default_model: opus
model_tier_rationale: two invented predicates (outcome from cap-overflow deferrals, severity counts from review tables) plus an equivalence obligation on a row three readers already parse
---

# Record convergence cap and roster per PRD

## Problem

The convergence metric is written by prose, and prose skips. `references/phase-review.md:166-184` tells the review session to `printf` a `review_converged` row into `loop-metrics.jsonl`; in ddb batch 202607161128 (ddb paths below are read-only evidence under `/Users/bob/git/src/github.com/doogat/ddb/dev/local/`) that row exists for 3 of 9 PRDs (`autopilot/loop-metrics.jsonl` lines 67, 94, 100) and the deferred ledger records the gap itself: "NONE of 00163, 00200, 00164, 00165, 00166, 00167, 00168 or 00169 ever wrote one" (`autopilot/deferred/202607161128-deferred.json:241`). Even the rows that exist say only `cycles_to_converge` and `outcome`. The ddb assessment (`/Users/bob/git/src/github.com/doogat/ddb/dev/local/audit-results/refactor-assessment-2026-09-06.md`, F2 lines 63-65, F1 line 55) shows why that is not enough: July converged 4 of 5 PRDs under `rework_cap` 3 (`autopilot/reports/202607161128-report.md:233`), August converged 0 of 4 under cap 2 (`autopilot/state.json:10`), and between the two runs the builder model moved from `claude-opus-4-8` (first build row, loop-metrics line 2) to `claude-sonnet-5[1m]` (first such build row, line 45) with 00169 built on `claude-opus-5[1m]` (lines 83-89), and plan task counts grew from 5-11 to 15-21 (00167 declared 4 tasks and ran 21); nothing in any ledger records which cap, roster or model a PRD ran under, so the drop cannot be attributed. The report also prints `Tasks: 0/0` for 00169 and 00170 (report lines 335, 382) because `statectl` defaults absent task counts to 0 at close (`cli/statectl.py:358-361`). Neighbours already cover the rest: PRD 00185 adds `effort` to every session row (do not repeat it here; join on `prd`+`batch`); PRD 00183 fixes decision rows, the implementor mix and the `Cycles:` fallback; done PRD 00168 records per-dispatch timing. This PRD adds only the mechanical convergence row with its run conditions and one report line built from it. No review lens changes: every lens still runs every cycle (`dev/local/discovery/00177-cut-review-and-test-loop-overhead.md:51,58`).

## Solution

The wrapper writes the row, not the model. `loop._append_metrics` (`cli/loop.py:880-919`) already writes one session row per spawn at both call sites (`:1188`, `:1254`) and reads `phase_end` from `state.next_phase` (`:730`); when `phase_launched == "review"` and `phase_end == "done"` it appends one `review_converged` row to the same two files (ddb row 5 is that transition for 00163). The row keeps the four fields readers parse today (`scripts/tracon/model.py:170-186`, `cli/render_metrics.py:19-24`, `cli/test_render.py:93-101` all key on `event`) and adds `rework_cap`, per-cycle reviewer rosters and severity counts read from the review files, the builder models, and planned versus PRD task counts. `autopilot render report` reads the row back and prints one `- Run conditions:` line per PRD section. The prose step in `phase-review.md` becomes a description of what the wrapper records, and contract tests pin both the emission and the field set.

## Requirements

### Must have
- A review session whose state exits to `done` produces exactly one `review_converged` row in `loop-metrics.jsonl` and its `ledger/` mirror, written by `cli/loop.py`, with no skill prose involved; exits to `review`, `build` or `paused` write none.
- Row shape (additive on `phase-review.md:171`): `{"event":"review_converged","prd","batch","cycles_to_converge":<state.cycle>,"outcome":"converged"|"cap_deferred","ts":<epoch>,"rework_cap":<state.rework_cap|null>,"build_models":[...],"attempt_tiers":[...],"tasks_planned":<int|null>,"tasks_completed":<int|null>,"tasks_in_prd":<int|null>,"cycles":[{"cycle":1,"reviewers":[...]|null,"verdict":"converged"|<int>|null,"findings":{"critical","high","medium","low"}|null}, ...]}`.
- `outcome` is `cap_deferred` when any `state.deferred_decisions` dict carries `type == "cap-overflow"` (the cap-out path's only sink, `phase-review.md:55`; 10 such records in the ddb deferred JSON), else `converged`.
- Per cycle `n` in `1..state.cycle`, the review file is `dev/local/reviews/<prd stem>-review-<n>.md` (`phase-review.md:18`) or its zero-padded twin `-review-<nn>.md` (what ddb actually wrote: `reviews/00169-poison-file-reindex-resilience-v1-review-02.md`). `reviewers` is the frontmatter `reviewers:` list (`review-work-completion/references/review-coverage-format.md:13-14`; gate.py:47-49 reads the same line). `verdict` is parsed with `gate.VERDICT_RE` (`cli/gate.py:64`). `findings` counts table rows matching `^\| \[\d+/\d+\] \|` by the first of 🔴 🟠 🟡 ⚪ in the row (`review-work-completion/references/output-formats.md:24,90-94`; ddb `reviews/00169-poison-file-reindex-resilience-v1-review-02.md:72-82` is the live shape, with a `Task` column and a bare emoji in the severity cell). A missing or unparseable file yields `null`, never zeros: absence must not read as clean.
- `build_models` is the distinct `model` of this PRD's session rows with `phase_launched == "build"` in the same batch, first-appearance order; `attempt_tiers` is the distinct `tasks[].attempts[].model`; `tasks_planned`/`tasks_completed` read `state.tasks_total`/`tasks_completed` and fall back to `len(state.tasks)` and its `status == "completed"` count (the tasks array is still present at review exit; `cli/records.py:67-68` drops it and `:111-112` zeroes the counts only in the Phase 9 per-PRD reset); `tasks_in_prd` counts lines matching `^- \[[ x]\] ` in `dev/local/prds/wip/<prd>`.
- The row never blocks the loop: it lives inside the existing `try` of `_append_metrics` (`cli/loop.py:892-919`), and an unreadable state writes nothing.
- `render_report.prd_section` prints `- Run conditions: ...` after `- Tasks:` (`cli/render_report.py:441-442`) from the matching event row, or `- Run conditions: no review_converged row` when none exists, so a future emission gap is loud in the report. `- Tasks:` renders the row's counts when the completed-PRD record is absent or reads `0/0`.
- Stalled PRDs do not emit this review-to-done event and remain in the stalled report; post-release comparisons use completed PRDs only.
- `references/phase-review.md` no longer instructs the append; `state-schema.md` documents the row; contract tests pin all of the above.

### Nice to have
- A `jq` recipe in `state-schema.md` § Convergence rows that groups rows by `rework_cap` and `build_models` and prints the converged share, the July-versus-August question as one command.

## Implementation

### Module: convergence
- **Location**: `skills/run-autopilot/cli/convergence.py` (new, stdlib only, no state writes)
- **Responsibility**: read the review files and state for one PRD and build the row; the one definition of the field set
- **Exports**: `read_cycle(reviews_dir, prd, n) -> dict`, `outcome(state) -> str`, `build_row(ap_dir, state, session_rows, ts) -> dict`, `SEVERITY_MARKS`

### Module: render_metrics
- **Location**: `skills/run-autopilot/cli/render_metrics.py`
- **Responsibility**: the event-row loader beside `load_rows` (`:36-58`), which drops event rows and says "whatever wants those rows reads them itself" (`:24`)
- **Exports**: `load_event_rows(path) -> list[dict]` (rows carrying `event`; malformed lines skip loud as `load_rows` does)

### Module: loop
- **Location**: `skills/run-autopilot/cli/loop.py`
- **Responsibility**: the emission site, one branch in `_append_metrics`
- **Exports**: `_append_metrics(...)` unchanged signature; it re-reads `state.json` only on the review-to-done branch

### Module: render_report
- **Location**: `skills/run-autopilot/cli/render_report.py`, wired in `cli/__main__.py:756-782`
- **Responsibility**: the `Run conditions` line and the `Tasks:` fallback
- **Exports**: `prd_section(state, metrics_rows, completed, json_items=None, attempts_ledger=None, *, convergence=None)`, `run_conditions_line(row) -> str`

### Module: gate
- **Location**: `skills/run-autopilot/cli/gate.py` (existing, read-only)
- **Responsibility**: owns the verdict parser reused by convergence
- **Exports**: `VERDICT_RE`

### Module: verification and documentation
- **Location**: `skills/run-autopilot/cli/test_convergence.py` (new), `cli/test_loop.py`, `cli/test_render.py`, `cli/golden/metrics-render.jsonl`, `cli/golden/expected/report-section.md` (the `cli/` paths are relative to `skills/run-autopilot/`); `skills/run-autopilot/scripts/test_review_prompt_contracts.py`; `skills/run-autopilot/references/phase-review.md`, `state-schema.md`, `batch-report-format.md` (the last two beside phase-review); `CHANGELOG.md`
- **Responsibility**: pin emission/report compatibility and describe the mechanical row
- **Exports**: tests and documented event contract

### Dependencies
- convergence: depends on [gate] (`VERDICT_RE`) only
- render_metrics: no dependencies (foundation)
- loop: depends on [convergence, render_metrics]
- render_report: depends on [render_metrics, convergence]
- gate: no dependencies (existing foundation)
- verification and documentation: depend on [loop, render_report]

## Tasks

### Phase 0: Foundation
- [ ] Write `cli/convergence.py` and `render_metrics.load_event_rows`, with `cli/test_convergence.py` (no deps) - Acceptance: Premise: `load_rows` still drops rows carrying `event` (`cli/render_metrics.py:56`; re-check with `rg -n '"event" not in row' skills/run-autopilot/cli/render_metrics.py` returning one hit; skip and report otherwise). `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli/test_convergence.py` passes with `test_cap_overflow_deferral_reads_as_cap_deferred`, `test_no_cap_overflow_reads_as_converged`, `test_missing_review_file_reads_null_not_zero`, `test_severity_counts_come_from_table_rows_only` (a 🔴 in prose is not counted), `test_reviewers_come_from_the_frontmatter_line`, `test_padded_and_unpadded_review_names_both_resolve`, `test_tasks_in_prd_counts_checkbox_lines`, `test_build_models_are_this_prds_build_sessions_only` and `test_load_event_rows_returns_only_event_rows` (against `cli/golden/metrics-render.jsonl`, which holds exactly one event row at line 7).
- [ ] Emit the row from `_append_metrics` on the review-to-done branch, in both files, in the same `try` (depends on: task 1) - Acceptance: Premise: `_append_metrics` writes primary and mirror inside one `try` (`cli/loop.py:892-919`) and has exactly two call sites (`:1188`, `:1254`); re-check with `rg -n '_append_metrics\(' skills/run-autopilot/cli/loop.py` returning 3 hits (the def plus two calls); skip and report otherwise. In `cli/test_loop.py`, `test_review_exit_to_done_writes_the_convergence_row` (a review step writes `next_phase: "done"`, `cycle: 2`, `rework_cap: 2` and a cap-overflow deferral, plus a fixture review file; primary and mirror each hold the session row followed by one event row whose `outcome` is `cap_deferred`, `rework_cap` is 2 and `cycles[1].findings.high` matches the fixture), `test_review_exit_to_review_writes_no_convergence_row` and `test_build_exit_writes_no_convergence_row` pass; `test_metrics_line_lands_in_primary_and_ledger_mirror` (`:647`) and `test_one_metrics_line_per_session` (`:671`) still pass unchanged.

### Phase 1: Core
- [ ] Render the `Run conditions` line and the `Tasks:` fallback; wire `load_event_rows` into `cli/__main__.py` beside `load_rows` (`:756`) and pass the event matching both PRD and batch as keyword `convergence=...` to `prd_section`, preserving all five existing positional arguments including the attempts ledger (depends on: Phase 0) - Acceptance: Premise: `cli/golden/metrics-render.jsonl` line 7 is the only event row and `cli/golden/expected/report-section.md:5` reads `- Tasks: 3/3` (re-check with `rg -c '"event"' skills/run-autopilot/cli/golden/metrics-render.jsonl` returning 1 and `rg -n '^- Tasks:' skills/run-autopilot/cli/golden/expected/report-section.md` returning `5:- Tasks: 3/3`; skip and report otherwise). Extend the fixture row with the new fields, add the `- Run conditions:` line to `report-section.md` line 6, and `test_report_section_matches_golden` (`cli/test_render.py:60`), `test_run_conditions_line_renders_from_the_event_row`, `test_missing_event_row_renders_loud` and `test_tasks_line_falls_back_to_the_event_row_when_record_reads_zero` pass; `test_event_rows_are_not_counted_as_sessions` (`:93`) still passes; `test_report_keeps_ledger_only_attempts_with_convergence` renders a ledger-only attempt and a convergence row together through the checkout CLI and asserts both the implementor mix and Run conditions, while a legacy five-positional-argument call still works.
- [ ] Rewrite `references/phase-review.md` § Convergence metric (`:166-184`) as a description of the wrapper's row and replace the two "Append the `review_converged` line" instructions (`:55`, `:164`) with "the wrapper records the convergence row at review-phase exit; write nothing"; pin it (depends on: task 2) - Acceptance: Premise: `rg -n 'printf.*loop-metrics' skills/run-autopilot/references/phase-review.md` returns 2 hits (lines 177 and 179) before the edit; skip and report otherwise. After: that search returns 0 hits, `rg -c 'cli/loop.py' skills/run-autopilot/references/phase-review.md` is at least 1, and `test_phase_review_never_instructs_the_convergence_append` in `scripts/test_review_prompt_contracts.py` passes.
- [ ] Document the row in `references/state-schema.md` as § Convergence rows after § Attempt ledger (`:249`), add the `Run conditions` bullet to `references/batch-report-format.md` § What a completed-PRD section carries (`:39-42`), and add a `### Added` CHANGELOG entry under `[Unreleased]` with scope `**run-autopilot**` (depends on: tasks 3 and 4) - Acceptance: Premise: `rg -n '^## Attempt ledger' skills/run-autopilot/references/state-schema.md` returns one hit (line 249) and `rg -n '^## What a completed-PRD section carries' skills/run-autopilot/references/batch-report-format.md` returns one hit (line 39); skip and report otherwise. After: `rg -n '## Convergence rows' skills/run-autopilot/references/state-schema.md` returns one hit; `rg -n 'Run conditions' skills/run-autopilot/references/batch-report-format.md CHANGELOG.md` returns one hit in each; `bash dev/bin/release-checks` passes.

## Success Criteria

- `uv run --no-project --with pytest python -m pytest -q skills/run-autopilot/cli skills/run-autopilot/scripts/test_review_prompt_contracts.py` passes with every test named above present.
- `rg -n 'printf.*loop-metrics|Append the .review_converged. line' skills/run-autopilot/references/phase-review.md` returns nothing.
- Checkout subprocess fixtures cover completed PRDs with and without event rows, cross-batch rows, ledger-only attempts and zeroed task counters; matching sections contain Run conditions and use available event counts instead of `Tasks: 0/0`. All CLI proofs invoke this checkout's `skills/run-autopilot/cli/__main__.py` with the test interpreter and temporary state.

## Post-release signals (non-gating)

These observations require a release/cache refresh and a later installed-plugin batch; they are not completion gates for checkout work.

- On a later batch, parse the ledger JSONL, filter by that batch ID and its completed PRD IDs, and compare the matching event count with the completed PRD count, and every row carries `rework_cap`, a non-empty `build_models`, and one `cycles[]` entry per review cycle whose `reviewers` is non-null.
- Every completed-PRD section of that batch's report carries a `- Run conditions:` line naming the cap, the per-cycle roster and counts, the build models and both task counts (line wording as rendered by `run_conditions_line` example: `cap 2 · 2 cycles, cap_deferred · c1 alice,blake,bob 1/4/3/0 · c2 alice,blake,bob 0/1/8/2 (crit/high/med/low) · build claude-sonnet-5[1m] · tiers sonnet · tasks 21 planned, 4 in PRD`), and no section reads `Tasks: 0/0` while the row holds counts.
