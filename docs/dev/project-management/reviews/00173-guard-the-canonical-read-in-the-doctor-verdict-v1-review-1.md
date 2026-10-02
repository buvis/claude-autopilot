---
prd: dev/local/prds/wip/00173-guard-the-canonical-read-in-the-doctor-verdict-v1.md
review: 1
date: 2026-09-05
head_sha: 57ed616f4022e5ab623a173924202b6ba8fb16fd
codex_thread_id: 01a07089-ac37-7070-b5ff-0e5a5c30ca18
reviewers: alice,blake,bob,eve
agents:
  alice: available
  blake: available
  bob: available
  carl: unavailable
  eve: available
---

# Review: 00173-guard-the-canonical-read-in-the-doctor-verdict-v1

Diff range: `57ed616f4022e5ab623a173924202b6ba8fb16fd..working tree (UNCOMMITTED)`

codex_rung_guard: fired (1 codex-implemented task(s))

## Run mode and caveats

**Standalone review, not an autopilot cycle.** `dev/local/autopilot/state.json`
exists but names PRD **00171** (already converged, in `done/`, batch paused by
`paused-by-operator`). Nothing in `dev/local/autopilot/` was read as this PRD's
state and nothing there was written. Consequences, all deliberate:

- No `task-add`: follow-up findings are reported here and to the operator, not
  written as autopilot tasks (SKILL.md step 7, standalone branch).
- No verification-check queue: there is no `state.cycle` and no work phase to
  run the checks (SKILL.md step 6, standalone branch).
- No `state.review_lenses` / `state.doubts_rubric_verdicts` stamping.
- **The contract card was deliberately not written.** `dev/local/autopilot/contract-card.md`
  currently describes PRD 00171's finalize hand-off. Overwriting it would destroy
  a paused batch's re-anchor point, which is exactly the state this run promised
  not to touch. Recorded here instead. Fail loud: this is a skipped step, not a
  completed one.

**The PRD was moved `backlog/` -> `wip/` for this review.** The build session
left it in `backlog/` (its hand-off report says so explicitly); the review
skill reads its target from `wip/`.

**`engram pack` failed** — `not inside a registered repo; register it in
/Users/bob/.config/gita/repos.csv`, exit 1. A deterministic config precondition,
so no retry could change it and none was spent. Every prompt that takes
`{PACK_FILE}` / `{PACK_FINDINGS}` received the literal
`(no pack available this cycle)` sentinel. This review is degraded on retrieval
context, not invalid. `pack: failed (engram: repo not gita-registered)`

**Codex doubt-roster guard — how it was resolved.** The mechanical predicate
(`any(state.tasks[].attempts[].implementor == "codex")`) could not fire: the
state file present belongs to another PRD and carries no `tasks` array at all.
This is the documented gap — "a PRD that never ran under autopilot ... leaves
the guard with no attempts record to consult". The build session's own hand-off
report (`dev/local/reviews/00173-review.md`) records that it ran under codex
(release-checks had to be invoked with `env -u CODEX_SESSION_ID` to clear that
session's recursion marker). Codex would therefore have been reviewing its own
work as the sole doubt lens. **Eve was armed on that evidence**, she produced
usable output, and the guard is recorded in its plain fired form. The count `1`
is the PRD's single Phase 0 task. Bob/codex still ran; the guard added a voice
rather than removing one.

**Scope fence.** Three further files are dirty in the same working tree and
belong to a different, already-completed PRD (00170). Alice, Bob and Eve were
told explicitly not to review them. Blake was not (a blind lens gets the PRD
only) and found the mixed tree himself, which is the ⚪ hygiene finding below.

```
skills/run-autopilot/scripts/tune_routing.py          <- out of scope (PRD 00170)
skills/run-autopilot/scripts/test_tune_routing.py     <- out of scope (PRD 00170)
skills/run-autopilot/scripts/test_statectl_ledger.py  <- out of scope (PRD 00170)
```

In scope: `skills/use-codex/scripts/codex_hook_doctor.py`,
`skills/use-codex/scripts/test_codex_hook_doctor_extra.py`, `CHANGELOG.md`.

## Review Summary

Reviewed: 1 completed task (Phase 0, uncommitted)
PRDs checked: 00173-guard-the-canonical-read-in-the-doctor-verdict-v1

### Agent Status

- Alice: ✅ Available
- Blake: ✅ Available
- Bob: ✅ Available
- Carl: ⚠️ Unavailable: both gemini backends failed after one retry. copilot —
  `Model "gemini-3.1-pro-preview" from --model flag is not available`. Native
  gemini — `IneligibleTierError: This client is no longer supported for Gemini
  Code Assist for individuals` (free tier; migrate to Antigravity). This is a
  standing breakage of the `use-gemini` lane, not a transient quota trip, and
  `dev/bin/release-checks` still asserts the now-unavailable model pin
  (`PASS: plain -f argv is exactly: --model gemini-3.1-pro-preview ...`).
- Eve: ✅ Available (armed by the codex doubt-roster guard, see above)

## Consolidated Findings

Produced by `consolidate_findings.py` over four reviewer outputs. No `--ledger`
flags: cycle 1, no settled-decisions ledger exists.

| Consensus | Severity | Issue | File | Task | Found By |
|-----------|----------|-------|------|------|----------|
| [1/4] | ⚪ | `_repair_known`'s canonical-only-detail check distinguishes "the canonical's own marker" from a sibling's marker by string-prefix matching (`missing[0].startswith(f"{canonical.name}: ")`) rather than a structured signal from `_missing_common_import_names`. Functionally safe today (Python identifiers can't contain `:` or `.`, so no real import name can collide with the marker shape), but fragile if the marker format ever changes. | skills/use-codex/scripts/codex_hook_doctor.py | general | BLAKE |
| [1/4] | ⚪ | Residual unguarded file operations remain elsewhere in the same function pair, unchanged by this PRD and explicitly out of its stated scope: `_repair_known`'s write path (`tmp_path.write_bytes(canonical_bytes)` / `os.replace(...)`) and `_verdict_for`'s re-read of the target (`target.read_bytes()` in the staleness comparison) can still raise `OSError` uncaught, exiting 2. Consistent with this repo's practice of pinning one PRD per fix, so not a regression, but worth a future PRD if these paths are ever hit in the wild. | skills/use-codex/scripts/codex_hook_doctor.py | general | BLAKE |
| [1/4] | ⚪ | Working tree has unrelated uncommitted changes (`skills/run-autopilot/scripts/tune_routing.py`, `test_tune_routing.py`, `test_statectl_ledger.py`) sitting alongside this PRD's change, outside PRD 00173's Structural Decomposition. Not a defect in this PRD's implementation, but a commit-hygiene risk if staged together. | skills/run-autopilot/scripts/tune_routing.py | general | BLAKE |
| [1/4] | ⚪ | Cannot statically verify: acceptance tests pass. VERIFY: run `uv run --no-project --with pytest python -m pytest -q skills/use-codex/scripts`. | N/A | 1 | BOB |
| [1/4] | ⚪ | Cannot statically verify: release checks pass. VERIFY: run `env -u CODEX_SESSION_ID -u COPILOT_CLI -u AUTOPILOT_DISPATCH_DEPTH mise exec -- bash dev/bin/release-checks`. | N/A | 1 | BOB |

Bob's two ⚪ rows are **answered** by this cycle's own runs (see `Tests:` below):
the acceptance suite returned 74 passed and release-checks returned 203 passed,
0 failed, both exit 0. They are kept in the table because they are what the
sandboxed reviewer actually emitted; they need no follow-up.

### Findings NOT in the table — the doubt lens's FIX bucket

**Read this section: it carries the cycle's only substantive findings.**
`consolidate_findings.py` parses only `[AGENT] {emoji} … | File: … | Task: …`
issue lines. The doubt lens emits FIX/VERIFY/KNOWN buckets instead, so **none of
Eve's findings can reach the consolidated table** (documented in
`references/output-formats.md`). Normally the verification-check queue catches
her VERIFY items, but a standalone run writes no queue. They are therefore
listed here in full, and they are the findings that need an operator decision.

1. 🟠 **The null-byte regression test cannot fail on the interpreter the suite
   actually runs on.** `ast.parse('\x00')` raises `SyntaxError` on 3.11.15,
   3.13.13 and 3.14, and a bare `ValueError` only on 3.10.20. So the test's
   `unreadable OR SyntaxError` assertion is already satisfied by the
   pre-existing `except SyntaxError` branch, and Eve confirmed by replay that
   reverting `(ValueError, OSError)` back to `(UnicodeDecodeError, OSError)`
   leaves the suite green on 3.13 and 3.11. The change is only pinned when the
   suite is run under 3.10. File:
   `skills/use-codex/scripts/test_codex_hook_doctor_extra.py:604-632`.
   Proposed fix: add an interpreter-independent unit test that calls
   `_missing_common_import_names` with `monkeypatch.setattr(codex_hook_doctor.ast,
   "parse", <raiser of ValueError>)` and asserts exactly
   `[f"{name}: unreadable (cannot verify _common imports)"]` for a sibling and
   for the canonical; keep the CLI test as the end-to-end proof.
   *Cross-check: Alice and Blake both observed the interpreter dependency and
   both judged it a sandbox limitation. Eve is the only lens that ran 3.10.20
   and measured the consequence. Her reading is the better-evidenced one.*

2. 🟡 **The kept branch of the new conditional is unpinned.** Blanking the
   prefix line (`codex_hook_doctor.py:205` -> `pass`) leaves all 69 non-doc
   tests green: every sibling-caused assertion matches the marker with `in`, and
   the prefix string appears in no test, before or after this change. So
   Feature 3 pins the branch it drops but not the branch it keeps. File:
   `skills/use-codex/scripts/test_codex_hook_doctor_extra.py:627-630`.
   Proposed fix: in the `sibling` param also assert
   `row.split("\t")[2].startswith("sibling imports names not defined in canonical _common.py: ")`.

3. 🟡 **Test hygiene in the null-byte parametrization.** It hard-codes
   `"fake_aegis_root/hooks/_common.py"`, duplicating `_fake_roots` internals from
   `test_codex_hook_doctor.py:53`, while `_canonical_case` already returns
   `canonical`; and the canonical case writes `canonical = 2\n` only to
   overwrite it one line later (a dead write). File:
   `skills/use-codex/scripts/test_codex_hook_doctor_extra.py:604-617`.
   Proposed fix: parametrize with a selector over the returned paths and write
   the readable canonical only in the sibling case.

Severities above are this consolidation's, not Eve's — her buckets carry no
severity field.

**Eve's VERIFY item is answered.** She could only run 3 of release-checks' 5
legs (the script needs repo-root cwd) and asked for a full
`bash dev/bin/release-checks`. That was run this cycle from the repo root:
203 passed, 0 failed, exit 0. Her side-observation stands and is worth noting:
release-checks never runs the `skills/use-codex` pytest suite, so it cannot
catch a regression in this PRD's own code.

**Eve's four KNOWN items** are recorded in her section below with their
out-of-scope justifications. One deserves the operator's eye even though it is
correctly out of scope: the PRD's Feature 2 premise (and a pre-existing code
comment at `codex_hook_doctor.py:65-66`) claims a null byte raises bare
`ValueError` on **3.10 and 3.11**; Eve probed 3.11.15 and it raises
`SyntaxError`. The widened tuple is still a correct superset, so the code is
right and the documentation is wrong.

## Follow-up Tasks Created

None. This is a standalone review with no autopilot state to write to; findings
are reported here and walked through with the operator instead.

## Alice

Consensus lens (Claude subagent, implementation-aware). Verdict: **no defects
found**.

`[ALICE] ✅ No issues found`

Alice read the full working-tree `codex_hook_doctor.py` (433 lines) and
`test_codex_hook_doctor_extra.py` (771 lines) plus the shared fixtures, traced
all three PRD features against the new tests including the TSV row and
exit-code arithmetic in `_report`, and ran both the acceptance suite (74 passed)
and release-checks (green). She reproduced fail-first independently by copying
the new test file alongside the pre-diff (`57ed616`) doctor: 4 of 6 parametrized
cases fail on old code. She flagged, correctly, that the null-byte cases pass
against old code on this host because only 3.12-3.14 are installed, and judged
it a sandbox limitation rather than a defect. She confirmed every touched
function against the mechanical-facts block (largest 45 lines, both files under
800) and found no TODO/FIXME/skip/xfail/debug markers.

```
R1: pass
R2: pass
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: pass
R10: pass
R11: pass
R12: pass
R13: pass
```

## Blake

Blind lens (Claude subagent, PRD-only: no diff, no changed-file list, no review
history, no scope fence). He located the code himself and ran both suites, plus
a differential run of the new tests against `git show HEAD:...` to confirm they
are genuinely fail-first. He independently reached the same null-byte
conclusion as Alice, and verified `_report` and `skills/use-codex/SKILL.md` are
byte-for-byte unchanged. Three ⚪ Low findings, all in the consolidated table
above.

```
[BLAKE] ⚪ `_repair_known`'s canonical-only-detail check distinguishes "the canonical's own marker" from a sibling's marker by string-prefix matching (`missing[0].startswith(f"{canonical.name}: ")`) rather than a structured signal from `_missing_common_import_names`. Functionally safe today (Python identifiers can't contain `:` or `.`, so no real import name can collide with the marker shape), but fragile if the marker format ever changes. | File: skills/use-codex/scripts/codex_hook_doctor.py | Task: general
[BLAKE] ⚪ Residual unguarded file operations remain elsewhere in the same function pair, unchanged by this PRD and explicitly out of its stated scope: `_repair_known`'s write path and `_verdict_for`'s re-read of the target can still raise `OSError` uncaught, exiting 2. Not a regression, but worth a future PRD. | File: skills/use-codex/scripts/codex_hook_doctor.py | Task: general
[BLAKE] ⚪ Working tree has unrelated uncommitted changes (`skills/run-autopilot/scripts/tune_routing.py`, `test_tune_routing.py`, `test_statectl_ledger.py`) sitting alongside this PRD's change, outside PRD 00173's Structural Decomposition. Not a defect in this PRD's implementation, but a commit-hygiene risk if staged together. | File: skills/run-autopilot/scripts/tune_routing.py | Task: general
```

```
B1: pass
B2: pass
B3: pass
B4: pass
B5: pass
B6: pass
B7: pass
B8: pass
B9: pass
B10: pass
B11: pass
B12: pass
B13: pass
B14: pass
B15: pass
B16: fail
B17: fail
B18: pass
B19: pass
```

B16 and B17 name acceptance criteria for Phase 2 and Phase 3 tasks. This PRD has
only a Phase 0, so those rules are unevaluable, and the rubric's standing rule
is that an unevaluable rule counts as `fail`. They are not defects.

## Bob

Consensus lens on codex (static-only sandbox), carrying the doubt appendix.
Codex thread `01a07089-ac37-7070-b5ff-0e5a5c30ca18` (stamped in frontmatter for
the next cycle's `--resume-thread`). He raised no static defects; both of his
lines are the sandbox's mandated "cannot statically verify" form, and both were
answered by real runs this cycle.

```
[BOB] ⚪ Cannot statically verify: acceptance tests pass. VERIFY: run `uv run --no-project --with pytest python -m pytest -q skills/use-codex/scripts`. | File: N/A | Task: 1
[BOB] ⚪ Cannot statically verify: release checks pass. VERIFY: run `env -u CODEX_SESSION_ID -u COPILOT_CLI -u AUTOPILOT_DISPATCH_DEPTH mise exec -- bash dev/bin/release-checks`. | File: N/A | Task: 1
```

```
R1: pass
R2: pass
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: pass
R10: pass
R11: pass
R12: pass
R13: pass
```

```
D1: pass
D2: pass
D3: pass
D4: pass
D5: pass
```

Bob is the codex lane, and codex implemented this work. His clean verdict is
recorded but carries less independent weight than Eve's for exactly that reason;
that is why the guard armed her.

## Carl

⚠️ **Unavailable — did not run.** Retry budget spent (one retry, per
`references/retry-policy.md`).

- Attempt 1, copilot backend (the wrapper's preferred):
  `Error: Model "gemini-3.1-pro-preview" from --model flag is not available.` exit 1
- Attempt 2 (`[RETRY] carl attempt 1/1`), native gemini backend via
  `GEMINI_BACKEND=gemini`:
  `IneligibleTierError: This client is no longer supported for Gemini Code
  Assist for individuals. To continue using Gemini, please migrate to the
  Antigravity suite of products` — tier `free-tier`, reason
  `UNSUPPORTED_CLIENT`. exit 1

Both backends are structurally unavailable, so this is not a transient quota
skip: the `use-gemini` lane is dead until either the copilot model pin is
changed or the gemini client is migrated. `dev/bin/release-checks` still passes
while asserting the dead pin (`PASS: plain -f argv is exactly: --model
gemini-3.1-pro-preview --allow-all-tools --deny-tool=write -p <PROMPT>`), so the
suite cannot detect this. Worth its own PRD; out of scope here.

## Eve

Doubt lens on Fable, armed by the codex doubt-roster guard. She ran the suite
under both 3.13.13 and 3.10.20, replayed the new tests against the base doctor
on 3.13/3.11/3.10, probed `ast.parse('\x00')` per interpreter, and ran a
mutation test on the prefix line. Three FIX, one VERIFY, four KNOWN — full text:

```
FIX:
- The null-byte regression test cannot fail on the host: `ast.parse` raises SyntaxError on 3.11.15/3.13/3.14 (only 3.10 raises bare ValueError), so the `unreadable OR SyntaxError` assertion is satisfied by the pre-existing except branch and reverting `(ValueError, OSError)` to `(UnicodeDecodeError, OSError)` keeps the suite green under uv's 3.13 and mise's 3.14 (replay confirmed: passes against base doctor on 3.13 and 3.11) — skills/use-codex/scripts/test_codex_hook_doctor_extra.py:604-632 — add an interpreter-independent unit test that calls `codex_hook_doctor._missing_common_import_names(hooks_dir, canonical)` with `monkeypatch.setattr(codex_hook_doctor.ast, "parse", <raiser of ValueError("source code string cannot contain null bytes")>)` and asserts exactly `[f"{name}: unreadable (cannot verify _common imports)"]` for a sibling and for the canonical (two params); keep the CLI test as the end-to-end proof
- The prefix branch of the new conditional is unpinned: removing line 205 outright leaves all 69 non-doc tests green because every sibling-caused assertion uses `in` on the marker or name and no test contains the prefix text — skills/use-codex/scripts/test_codex_hook_doctor_extra.py:627-630 — in the `sibling` param assert `row.split("\t")[2].startswith("sibling imports names not defined in canonical _common.py: ")` in addition to the existing marker `or`, so the branch the conditional keeps is pinned alongside the branch it drops
- Null-byte parametrization hard-codes `"fake_aegis_root/hooks/_common.py"` (duplicating `_fake_roots` internals from test_codex_hook_doctor.py:53) while `_canonical_case` already returns `canonical`, and the canonical case writes `canonical = 2\n` only to overwrite it one line later — skills/use-codex/scripts/test_codex_hook_doctor_extra.py:604-617 — parametrize with a selector over the returned paths (`lambda common, canonical: common.with_name("bad_sibling.py")` / `lambda common, canonical: canonical`) and write the readable canonical only in the sibling case
VERIFY:
- PRD exit criterion `bash dev/bin/release-checks` green not confirmed end to end: the script hard-codes relative paths (needs repo-root cwd), I ran 3 of its 5 legs by absolute path (two pytest legs 117 passed, `test_codex_run.sh` 41 passed) and the gemini/sonnet runner legs are unrun; note it never runs the use-codex pytest suite, so it cannot catch a regression in this PRD's code either way — from the repo root run `bash dev/bin/release-checks`
KNOWN:
- A hook target that is itself a directory (or unreadable) still aborts the run with exit 2: `_verdict_for` reads the target unguarded at codex_hook_doctor.py:68 and `hooks_dir.glob("*.py")` matches directories; confirmed live (`error: [Errno 21] Is a directory: .../hooks/x.py`, exit 2) — out of scope: the PRD enumerates exactly three canonical-side paths and pins Phase 0 to them; target-side reads predate this PRD
- The Feature 2 premise overstates 3.11: `ast.parse('\x00')` raises SyntaxError on 3.11.15 (probed), bare ValueError on 3.10.20 only, and the pre-existing comment at codex_hook_doctor.py:65-66 ("ValueError covers a null byte on 3.10/3.11") repeats the claim; the widened tuple is still a correct superset that fixes 3.10 — out of scope: the comment lies outside the diff hunks and predates the PRD (surgical-change rule), and the PRD document is not a reviewed file
- When the canonical is unparseable and siblings import names, the detail still says `sibling imports names not defined in canonical _common.py: <every imported name>, _common.py: SyntaxError ...` although those names are unverified, not known-missing (`sorted(imported) + unparseable` at codex_hook_doctor.py:153,158) — out of scope: PRD Feature 3 limits the prefix drop to the single-entry canonical-only case
- `_repair_known` still reads the canonical twice for `_common.py`: bytes in the new guard (codex_hook_doctor.py:196) and text again inside `_missing_common_import_names` (line 148), so "read the canonical once" holds only for the guard and a canonical rewritten between the two reads is checked and written inconsistently — out of scope: the PRD pins `_missing_common_import_names`'s signature (no bytes parameter) and the window is a same-host race
```

```
D1: pass
D2: pass
D3: pass
D4: pass
D5: pass
```

## PRD acceptance

Every PRD success metric was checked against the working tree:

- *A known target that compiles, whose canonical is a directory or unreadable,
  gets one row and the run exits 1 or 3, never 2* — met.
  `test_directory_canonical_reports_one_target_without_aborting` covers it and
  fails against the base doctor (Alice, Blake and Eve each replayed this).
- *A null byte in a sibling or the canonical `_common.py` yields the unreadable
  marker on every supported Python, never exit 2* — **met in code, weakly
  pinned in tests.** The `(ValueError, OSError)` widening is a correct superset
  (`UnicodeDecodeError` subclasses `ValueError`) and Eve confirmed the old code
  fails under 3.10.20. But the regression test only discriminates under 3.10;
  see FIX item 1.
- *The detail for a canonical-only failure names the canonical failure without
  the sibling-imports prefix* — **met in code, half-pinned in tests.** The
  dropped branch is asserted; the kept branch is not. See FIX item 2.

## Minutes

Walked through with the operator after the panel reported. The two PRD-acceptance
notes above describe the state **at review time**; items 1-3 below resolved them.

| # | Sev | Finding | Decision | Status |
|---|-----|---------|----------|--------|
| 1 | 🟠 | Null-byte regression test cannot fail above Python 3.10 | Add an interpreter-independent monkeypatched unit test | **applied** — new module `skills/use-codex/scripts/test_codex_hook_doctor_parse_errors.py`; fail-first proven against `57ed616` on 3.13 (bare `ValueError` escapes the base module's line 130) |
| 2 | 🟡 | The branch the canonical-only conditional *keeps* has no test | Targeted `startswith` assert on the sibling param | **applied** — `_SIBLING_PREFIX` + an `expect_prefix` param now pin both arms in one test |
| 3 | 🟡 | Test hygiene: hard-coded `_fake_roots` path, dead write | Derive paths from the fixture's returns, drop the dead write | **applied** — parametrize now uses `bad_is_canonical` over `_canonical_case`'s returned paths |
| 4 | 🟡 | `use-gemini` reviewer lane dead on both backends | File a backlog PRD | **queued** — `dev/local/prds/backlog/00175-restore-the-gemini-reviewer-lane-v1.md` |
| 5 | ⚪ | Prefix match couples two functions through message text | Keep the match, add a comment saying why it is safe | **applied** — comment at `codex_hook_doctor.py:206-208` |
| 6 | ⚪ | Residual unguarded target-side reads and the repair write | Fold into a follow-up PRD | **queued** — `dev/local/prds/backlog/00176-guard-the-target-reads-in-the-doctor-v1.md` |
| 7 | ⚪ | PRD and code comment overstate 3.11 | Correct the comment | **applied** — now "3.10 (SyntaxError from 3.11)", measured on 3.10.20 / 3.11.15 / 3.12.13 / 3.13.13 for both `ast.parse` and `compile`. The PRD's own Problem Statement still carries the wrong claim; it is a historical document and was not edited |
| 8 | ⚪ | Mixed uncommitted tree (00170's files beside 00173's) | Stage selectively | **applied** — only the three 00173 files plus the new test module were committed; PRD 00170's three files were left dirty and untouched |
| — | ⚪ | Bob's two "cannot statically verify" rows | Answer with real runs | **resolved, no action** — both commands run this cycle, both green |

### Deviations recorded

- **Two PRDs, not one.** The disposition question named "one new backlog PRD" for
  findings 4 and 6. They are unrelated (a reviewer CLI versus the hook doctor), so
  they were filed separately as 00175 and 00176 rather than merged.
- **The new test lives in its own module.** PRD 00173's Repository Structure names
  `test_codex_hook_doctor_extra.py` as the home for its tests, but that file is at
  789 of the project's 800-line limit, and the sibling modules are at 772 and 795.
  `test_codex_hook_doctor_parse_errors.py` follows the repo's own established
  split-to-stay-under-the-limit pattern.
- **Loupe reflowed both edited Python files** and this was committed. Its formatter
  ran at turn end and restyled six spots this PRD never touched (`_repair_unknown`,
  `_repair_target`, `_remove_orphaned_empty`, `_run_subcommand` and `_report`
  signatures, plus trailing commas in four `unparseable.append` calls), inflating
  the doctor's diff from 23 to ~59 lines. Reverting was not possible within a turn:
  loupe re-applies on every edit, so a revert would need the project formatter
  toggled off. The reflow is semantically inert — 75 passed and release-checks 203
  passed after it. Recorded rather than silently absorbed, against the standing
  note "never commit loupe's reflow".

Verdict: 5 findings
Tests: 203 passed, 0 failed, 0 skipped (suite run this cycle)

Post-rework re-run at the same working tree: release-checks 203 passed, 0 failed,
exit 0; the `skills/use-codex` acceptance suite 74 → **75 passed** with the new
interpreter-independent test. `check_style_limits.py --diff` exit 0 over all three
changed Python files, none skipped.

### Concurrency — the base moved under this review

Measured 2026-09-05T11:10+02:00, after the commit. **A second session committed
into this same checkout while the panel was running.** At session start (09:37)
`git log` showed `57ed616` at the tip and `pgrep` found only an unrelated
`autopilot loop` running in the *agent-skills* repo, so the checkout looked
quiet. It was not. Three commits landed afterwards:

| sha | time | what |
|-----|------|------|
| `0f31c3b` | 10:35 | feat(review-work-completion): detect tautological tests with shape and replay checks |
| `ae3f404` | 10:41 | feat(work): run the tautological-shape check inside the step-2.8 test quality gate |
| `c17d5b2` | 10:59 | test(review-work-completion): resolve gather-context.sh from the contract's own directory |

Consequences, all checked rather than assumed:

- **`head_sha: 57ed616` in this file is still correct** as the base this review
  diffed against — it was the tip when `gather-context.sh` ran at ~09:44, and the
  reviewed content was exactly the working tree against it. But the resulting
  commit `fb8d53e` has **`c17d5b2` as its parent**, not `57ed616`. The three
  commits above were never part of this review's scope.
- **No CHANGELOG clobber.** `ae3f404` and `0f31c3b` both touched `CHANGELOG.md`,
  which this review also committed. `git show fb8d53e -- CHANGELOG.md` is a pure
  4-line addition (index `8e55109` → `96fe932`) with their entries intact below it.
- **The review was not affected by their edits to this very skill.** `0f31c3b`
  modified `skills/review-work-completion/SKILL.md`, `agents/eve.md`,
  `references/rubric.md`, `references/review-dimensions.md` and
  `references/agent-invocation.md` — the contract this cycle was executing. This
  cycle ran the **installed plugin cache** at
  `~/.claude/plugins/cache/buvis-plugins/autopilot/0.4.1/`, not the repo working
  copy, so it used the released 0.4.1 contract start to finish. The repo now
  carries a newer, unreleased contract (including a changed `rubric.md`); the
  `R1`-`R13` verdicts above are the 0.4.1 set.
- **Verification re-run after the merge.** At `fb8d53e`: acceptance suite
  **75 passed**, release-checks **203 passed, 0 failed**, both exit 0.

The lesson for the next manual session: a single `pgrep` at session start does not
prove a checkout is quiet, because a session can be started in it afterwards.
Re-measure git state immediately before committing.
