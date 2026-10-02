# PRD 00173 — manual implementation and review handoff

2026-09-05. Base: `57ed616f4022e5ab623a173924202b6ba8fb16fd`.
Implementation is uncommitted. No autopilot loop was invoked and no live
autopilot state was modified.

## Implementation

- Guard canonical byte reads in `_verdict_for` and `_repair_known` with
  `OSError`; repair reads before its dry-run branch and writes the captured bytes.
- Catch `ValueError` at both AST parse sites, retaining the existing
  `SyntaxError` markers and Unicode decoding coverage.
- Emit a sole canonical failure marker without the sibling-import prefix.
- Add three regression functions (six parameter cases) and the Unreleased /
  Fixed `use-codex` changelog entry. `_report`, public signatures, verdict
  strings, and `skills/use-codex/SKILL.md` are unchanged.

The earlier directory-canonical regression now expects
`no canonical source (<path>)`, because the new byte-read guard runs before
the import scanner. Its undecodable-byte case still expects the scanner's
unreadable marker. Both cases retain proof that another stale target repairs.

## Verification

- Fail-first: before changing production code, directory-canonical and
  canonical-only-detail cases produced four failures on Python 3.11.15.
  Both null-byte cases failed on native Python 3.10.20 with exit 2 and no
  TSV rows. Thus all three features have reproduced baseline failures.
- Acceptance: `mise exec -- uv run --no-project --with pytest python -m
  pytest -q skills/use-codex/scripts` — **74 passed**, Python 3.13.13.
- Native compatibility: the three doctor test modules (`test_codex_hook_doctor.py`,
  `test_codex_hook_doctor_extra.py`, `test_codex_hook_doctor_repair.py`) —
  **73 passed each** using explicit `uv run --python 3.10`, `3.11`, `3.12`,
  `3.13`, and `3.14`. The installed 3.11.15 already raises `SyntaxError` for
  null bytes; 3.10.20 exercises the bare `ValueError` catches.
- Release checks — **112 / 5 / 41 / 18 / 27 passed**, exit 0, via:
  `env -u CODEX_SESSION_ID -u COPILOT_CLI -u AUTOPILOT_DISPATCH_DEPTH mise
  exec -- bash dev/bin/release-checks`.
  An initial run inherited this Codex session's recursion marker and failed
  the runner harness. The successful run removes those markers only from
  the test subprocess. The harness uses local stub binaries and explicitly
  tests recursion refusal; production guards remain intact.
- `check_style_limits.py --diff` on both changed Python files — exit 0,
  neither file skipped. The extra test module is 771 lines, below 800.
- `git diff --check` — exit 0.

## Independent panel

All reviewers were spawned with `fork_turns="none"`; none inherited the
builder conversation. Reviewers could write their reports but were instructed
not to edit code/tests or invoke autopilot. Their bounded probes used temporary
fixtures with explicit config and canonical roots.

| Lens | Report | Result |
| --- | --- | --- |
| Code/diff review | [Consensus](00173-consensus.md) | No findings; 74 tests and independent permission/parser/buffer probes passed. |
| PRD-only review, no diff or builder notes | [Blind](00173-blind.md) | No actionable findings; requirement matrix, 74 tests and eight independent probes passed. |
| Review with doubt, all six questions and five slop checks | [Doubt](00173-doubt.md) | 11 doubts: 0 FIX, 10 verified/dismissed, 1 pre-existing KNOWN boundary. |

The independent probes also verify permission loss between check and repair,
both dry-run and real repair refusal, continued sibling repair, retained
multi-entry detail, and reuse of a single guarded canonical byte buffer.
No review-driven code changes or second doubt pass were needed.

## Scope and handoff

The concrete three-feature acceptance scope is complete. A local target that
is itself a directory can still exit 2 before canonical handling; that
pre-existing target-file failure is outside this canonical-source PRD.
The broad phase-goal sentence should not be read as a guarantee against
every possible host-file error.

Per the user-global fresh-session rule, `/review-work-completion` was not
invoked from this build session. The next phase is that review in a fresh
session; use this report, the PRD, and the three scoped uncommitted files as
the handoff. The task checkbox is complete, but the PRD remains in backlog
pending that handoff. No shared `state.json` was changed to schedule it.

The pre-existing edits in `test_statectl_ledger.py`, `test_tune_routing.py`,
and `tune_routing.py` belong to concurrent work and were left untouched.
No worktrees, branches, or plan files were created for this task.
