# Review: PRD 00169, close the hook-doctor rework-cap findings

Hand-run fast-track session S1 (2026-09-02), plan `dev/local/plans/00169-fast-track-sequence.md`.
Base `2244b1d` (v0.4.0). Build commits `89466c2`, `9aa34ed`, `568ffcb`, plus `10a940d`
(a baseline-red changelog pin outside the PRD). Rework commit `189d91e`.

## Cycle 1 panel

| Lens | Reviewer | Result |
|------|----------|--------|
| Consensus (Claude) | Alice | no issues, R1-R13 pass; reproduced fail-first at the baseline in her own worktree |
| Blind, PRD-only | Blake | no issues, B1-B19 pass; mapped all eight 00161 deferred findings to landed fixes |
| Consensus (codex, static) | Bob | 1 MEDIUM, R1 fail |
| Doubt + de-slop (Fable) | Eve | 4 FIX, 0 VERIFY, 5 KNOWN, D1-D5 pass |

No CRITICAL or HIGH raised, so no adversarial verification (Victor) was dispatched.

## Findings

| # | Severity | Finding | Where | Raised by | Decision | Status |
|---|----------|---------|-------|-----------|----------|--------|
| 1 | MEDIUM | The OSError branch of the canonical `_common.py` read has no regression test; only the non-UTF-8 branch is covered | `test_codex_hook_doctor_extra.py` | Bob | Fix: parametrize the unreadable-canonical test over latin-1 bytes and a directory canonical | applied `189d91e`; Bob re-review clean, R1 pass |
| 2 | MEDIUM | Success metric "the rung comes back on after repair" has no automated proof for a syntax-broken known hook; the repair test stops at bytes-equal | `test_codex_hook_doctor_extra.py:428` | Eve (FIX) | Fix: assert the post-repair `check()` returns `[("ok", target, "")]` | applied `189d91e` |
| 3 | LOW | `use-codex/SKILL.md` § Hook doctor still says `repair` restores "missing/empty/stale known hooks" | `SKILL.md:106` | Eve (FIX) | Fix: add "syntax-broken" | applied `189d91e` |
| 4 | LOW | The `codex_probe` shape literal's `hook_doctor?` union omits the exit-2 value the same row's prose defines | `state-schema.md:198` | Eve (FIX) | Fix: append `\|"doctor error: <config path>"` | applied `189d91e` |
| 5 | LOW | `_load_hooks` is annotated `-> dict` but only `check()` guards the type; the `data` temp is dead weight | `codex_hook_doctor.py:85` | Eve (FIX) | Fix: move the `TypeError` guard into `_load_hooks`, return directly, drop the guard from `check()` | applied `189d91e` |
| 6 | LOW (deferred) | `_verdict_for` reads the canonical unguarded (`canonical.read_bytes()`), so an OS-unreadable canonical behind a compiling known target still exits 2 with no rows. Confirmed: `error: [Errno 21] Is a directory`. The PRD pinned its fix to the later read; the verdict for that state is a decision the PRD did not make | `codex_hook_doctor.py:79` | Eve (KNOWN) | Defer | filed as PRD 00173 |
| 7 | LOW (deferred) | The unrepairable detail for a canonical-only failure carries the false prefix `sibling imports names not defined in canonical _common.py:` before the marker; pre-existing wording from PRD 00161 cycle 1 | `codex_hook_doctor.py:199` | Eve (KNOWN) | Defer | filed as PRD 00173 |
| 8 | LOW (deferred) | On Python 3.10/3.11 a null byte makes `ast.parse` raise a bare `ValueError` that neither except tuple in `_missing_common_import_names` catches (exit 2); the operator runtime raises `SyntaxError` there and is caught | `codex_hook_doctor.py:123,139` | Eve (KNOWN) | Defer | filed as PRD 00173 |
| 9 | LOW | Commit `9aa34ed` is `fix(work)` but its changelog text extends the `**use-codex**` bullet | `CHANGELOG.md` | Eve (KNOWN) | Accept: the PRD mandated one `**use-codex**` bullet naming all four fixes | recorded |
| 10 | LOW | `test_the_changelog_names_the_ledger` (commit `10a940d`) passes as long as the string appears anywhere in the changelog; deleting the pin belongs to PRD 00168's owner | `test_dispatch_telemetry_prose.py:259` | Eve (KNOWN) | Accept: the commit unblocked a baseline-red acceptance suite; the pin's owner decides its fate | recorded |

Bob also emitted `⚪ Cannot statically verify: tests, linters, and release checks pass`, which is his sandbox contract, not a finding; the runs are recorded below.

Disagreements: none. Alice and Blake found nothing; Bob's and Eve's items do not contradict them.

## Cycle 2 (re-review of the rework `189d91e`)

Only the reviewers whose findings the rework touched were re-run.

| Reviewer | Result |
|----------|--------|
| Bob (`--resume-thread`) | no findings, R1-R13 pass |
| Eve (resumed context) | 3 FIX, 0 VERIFY, 5 KNOWN (the same five), D1-D5 pass |

| # | Severity | Finding | Where | Raised by | Decision | Status |
|---|----------|---------|-------|-----------|----------|--------|
| 11 | MEDIUM | The cycle-1 rework grew the parametrized test to 54 lines; `check_style_limits.py --diff` exits 1 on the 50-line function limit, which the work skill's step-5.65 gate would trip on the next task touching the file | `test_codex_hook_doctor_extra.py:508` | Eve (FIX) | Fix: trim the comment block to five lines (function now 48 lines) | applied `2ba6b93`; gate exit 0 |
| 12 | LOW | Nothing binds the guard `_load_hooks` now shares: a regression to the raw `AttributeError` would still exit 2 and pass the suite | `codex_hook_doctor.py:87` | Eve (FIX) | Fix: CLI test feeding `{"hooks": []}`, asserting exit 2, `hooks must be an object` on stderr, no traceback | applied `2ba6b93` |
| 13 | LOW | Two backlog PRDs numbered 00172: another session filed `00172-treat-session-stand-down-as-pause-v1.md` six minutes before this session's guard PRD, so rows 6-8 pointed at an ambiguous id | `dev/local/prds/backlog/` | Eve (FIX) | Fix: renumber the guard PRD to 00173 and update rows 6-8 | applied (`mv`, this file) |

## Cycle 3 (confirmation pass on `2ba6b93`)

| Reviewer | Result |
|----------|--------|
| Eve (resumed context) | 0 FIX, 0 VERIFY, 5 KNOWN (unchanged, rows 6-10), D1-D5 pass. Verified the guard test fails on a guard-less doctor copy (message assertion), the style gate exits 0, file lengths 772 / 670 |

**Converged** after two rework cycles: no CRITICAL, HIGH, or MEDIUM open; rows 6-8 deferred to PRD 00173, rows 9-10 accepted.

## Verification

- Gate suite after the rework: `2473 passed, 1 skipped, 4 warnings, 459 subtests passed in 65.92s` (baseline 2465 + 7 new tests + 1 parametrized case; the skip is the known golden-transcript machine-state test).
- Style gate (`check_style_limits.py --diff` over the five changed `.py` files): exit 0, no output, before and after the rework.
- `bash dev/bin/release-checks`: green (112 / 5 / 41 / 18 / 23).
- Live CLI check on scratch fixtures: latin-1 hook with a PEP 263 cookie, `check` exits 0; a syntax-broken `validate_commit_msg.py` with its canonical present, `check` exits 1, `repair` prints a `repaired` row and exits 0.
- Fail-first: 5 of the 7 new tests failed against the old doctor (reproduced independently by Alice and Eve at `2244b1d`).

## Process notes

- The plan's baseline of 2465 predates the release commit `2244b1d`: `test_the_changelog_names_the_ledger_under_unreleased` fails there because the 0.4.0 release moved its entry under the version heading. Verified in a throwaway worktree; fixed in `10a940d` (pin the whole file), disclosed as a deviation and confirmed by Alice and Eve.
- Deviations from the PRD (all in the context file handed to the reviewers): the four repair tests live in `test_codex_hook_doctor_extra.py` because the repair test file was 787 lines; the unreadable-canonical test uses an empty `hooks/_common.py` so the exit is honestly 1 (a stale-but-unrepairable `_common.py` exits 3, which Eve confirmed live); `_load_hooks` serves all three reads; the doctor's own `py_compile` comment was rewritten in Phase 0; the changelog bullet landed per `fix` commit.
- Two rework cycles (`189d91e`, `2ba6b93`), the full budget. Convergence by the plan's definition (no CRITICAL, no HIGH open) held from cycle 1; cycle 2 was reworked because finding 11 is a gate violation, not a wording item. The cycle-3 Eve pass confirms; any further LOW is recorded, not reworked.
- Twice during the review phase the `.py` files edited that turn came back reflowed (trailing commas, exploded signatures, a collapsed `if`) in regions this PRD never touched. Not another session: `loupe`'s end-of-turn format pass (ruff/black on its queue of edited files) does it, and this repo is not black-clean, so the reflow is noise. Reverted with `git checkout` both times, never committed. The plan attributes the same symptom to "the formatter of another session"; that attribution is wrong.
- The `sonnet-run.sh` leading-dash prompt bug reported mid-session by the agent-skills session is filed as PRD 00171 (not part of this review).
