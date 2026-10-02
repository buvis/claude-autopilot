---
prd: dev/local/prds/wip/00180-route-codex-prompt-through-stdin-v1.md
review: 2
date: 2026-09-06
head_sha: 6ee0acadecf7282ab18e5240e929f043d823844d
codex_thread_id: 01a0784f-d7ff-7162-bcff-b869d4f26fa1
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00180-route-codex-prompt-through-stdin-v1

Diff range: `61bd107b4cf16f26f222bcdf7871aa85cf2679dc..6ee0acadecf7282ab18e5240e929f043d823844d`

codex_rung_guard: not fired

pack: failed (`engram pack` exited 1 — "not inside a registered repo; register it in /Users/bob/.config/gita/repos.csv"). Same deterministic configuration error as cycle 1, so no retry was attempted; `{PACK_FILE}` and `{PACK_FINDINGS}` were substituted with the documented sentinel `(no pack available this cycle)` in every prompt that takes them. The review is degraded by the missing retrieval context, not invalid.

## Scope note

Cycle 2, an **incremental review**. Cycle 1's review file carried `head_sha: 61bd107b4cf1`, so `gather-context.sh --since 61bd107b4cf1` scoped the diff to the three rework commits (`7f87ab2`, `bb08599`, `6ee0aca`) that closed cycle 1's decision-gate task. Alice, Bob and Carl received the incremental addendum plus cycle 1's consolidated findings and were asked to verify each is resolved; Blake received neither (PRD-only every cycle, by design). Bob resumed his cycle-1 codex session via `--resume-thread 01a0784f-d7ff-7162-bcff-b869d4f26fa1`.

## Mechanical checks

The three computed blocks are python/pytest-only and this diff's changed tests are bash harnesses, so all three had nothing to inspect. They are **vacuous, not clean**, and were delivered to the implementation-aware reviewers as a companion file (`dev/local/tmp/review-mech-00180-2.md`) rather than appended to the context file, because aegis blocks shell appends into `dev/local/` and rewriting the 188-line context file by hand risked transcription drift. Same content, same reviewers. This mirrors cycle 1.

- `compute_mech_facts.py` — all 5 changed files skipped (non-python).
- `detect_tautological_tests.py` — checked 0 test functions in 0 test files.
- `replay_tests_against_base.py` — `replay: skipped (the diff touches no test function)`.

**Bash fail-first replay, computed by the orchestrator this cycle** to cover the gap. HEAD's `test_codex_run.sh` and `test_codex_run_resume.sh` were copied over a clean base worktree at `61bd107` (the code as cycle 1 reviewed it) and run there. Result: **45 passed, 1 failed**.

Only one case binds to this cycle's change:

- `-f PROMPTFILE containing only a newline: exit 1, 'Prompt required' on stderr, codex never invoked` — fails against base (exits 0 and dispatches a 49-byte prompt). Correct fail-first; it pins the new `case "$PROMPT" in *[![:space:]]*)` guard.

Three pass against base:

- `[MECH] unreadable prompt file: non-zero exit, error names the file, codex never invoked` — passes against the pre-fix code, so it does **not** pin the new `if ! PROMPT=$(cat "$PROMPT_FILE" && printf 'x')` guard. On base, `cat`'s own stderr already names the file and the old `[ -z "$PROMPT" ]` guard already exited 1, satisfying every clause by accident. Absorbed into the table below.
- `-f PROMPTFILE ending in a newline: ... byte-identical` — legitimate backfill; base already preserved the trailing newline (that was cycle 1's finding).
- `--emit-thread-id: final argv token is the literal '-' stdin marker` — legitimate backfill; base already emitted the `-`, and cycle 1's finding was the *missing assertion*.
- All 24 cases in `test_codex_run_resume.sh` — a pure relocation of cases that already existed and already passed.

## Consolidation note

`consolidate_findings.py` ran successfully with `--ledger` and `--ledger-dismiss BLAKE`, and emitted 10 rows with zero auto-dismissals. Three deliberate, disclosed adjustments:

1. **Blake's `File:` paths were normalised** from absolute (`/Users/bob/git/.../codex-run.sh`) to repo-relative before consolidation, so the script could merge his rows with the other three reviewers, which the identical-file-string rule would otherwise have prevented. Only the path form changed; no finding text was edited.
2. **Alice's and Bob's split-duplication rows are merged** into one `[2/4]` row. They are the same defect, split because Alice filed it as `File: N/A` and Bob as `test_codex_run_resume.sh:13`. Merged on issue-text-plus-file, the matching standard this gate uses.
3. **The `[MECH]` replay line is folded** into the existing tautological-test row (same file, same test) rather than added as its own row, per step 6's absorption rule. `mech-check` is listed among its finders; the `[3/4]` consensus still counts reviewers only, since `mech-check` is not one of the four.

## Consolidated findings

| Consensus | Severity | Issue | File | Found By |
|-----------|----------|-------|------|----------|
| [2/4] | 🟠 High | The PRD's explicit acceptance gate (`rg -c 'PASS "' skills/use-codex/scripts/test_codex_run.sh` must print 40) is not met — it prints 21. The 18 `--resume-thread` cases plus the fresh-path exit-code pin were relocated into a brand-new file `test_codex_run_resume.sh` (24 PASS lines) that the PRD's Structural Decomposition never names. Coverage is preserved in aggregate (21+24=45), but the PRD's literal instruction — "a different count means a case was lost, so stop and report" — was not honored | skills/use-codex/scripts/test_codex_run.sh | Blake, Bob |
| [3/4] | 🟡 Medium | Tautological test: the "unreadable prompt file" case passes against pre-fix code, so it does not pin the new cat-failure guard or its new stderr message | skills/use-codex/scripts/test_codex_run.sh | Alice, Bob, Carl, mech-check |
| [2/4] | 🟡 Medium | The unrequested file split duplicates fixture/helper code verbatim across both test files instead of the requested single shared-helper extraction, and creates two copies of the very stdin helper the cycle-1 task asked to have extracted once | skills/use-codex/scripts/test_codex_run_resume.sh | Alice, Bob |
| [1/4] | 🟡 Medium | Scope creep: `bb08599` bundles two behaviors PRD 00180 never specifies — (a) whitespace-only prompt files rejected as "Prompt required", (b) a failed `cat` read now errors explicitly | skills/use-codex/scripts/codex-run.sh | Blake |
| [1/4] | 🟡 Medium | Whitespace validation also rejects positional whitespace-only prompts, expanding behavior beyond the requested `-f` prompt-file guard | skills/use-codex/scripts/codex-run.sh:154 | Bob |
| [1/4] | 🟡 Medium | Fresh-JSON marker coverage adds a separate invocation although the existing JSON invocation already captured argv; fold the final-token check into case 3 | skills/use-codex/scripts/test_codex_run.sh:454 | Bob |
| [1/4] | 🟡 Medium | Trailing-newline coverage duplicates the leading-dash file case, which already byte-compares a newline-terminated file | skills/use-codex/scripts/test_codex_run.sh:434 | Bob |
| [1/4] | ⚪ Low | The "unreadable prompt file" test silently becomes a no-op `PASS` on any user that can read chmod-000 files (e.g. root in CI) | skills/use-codex/scripts/test_codex_run.sh | Alice |
| [1/4] | ⚪ Low | The PRD's Test Strategy wants the leading-dash case verified "on the plain, JSON and resume paths", but the new test exercises only the plain path | skills/use-codex/scripts/test_codex_run.sh | Blake |
| [1/4] | ⚪ Low | Carried forward: the cycle-1 queued check `bash dev/bin/release-checks` has no `result` recorded in `-checks-1.json`, so it counts as not passed | N/A | verify-check |

**Verdict: 10 findings** (9 consolidated after the merge, plus 1 carried forward).

### Discarded (1)

- ⚪ The carried-forward check (last row above). **Verified resolved this cycle:** the orchestrator ran `bash dev/bin/release-checks` in the foreground at HEAD `6ee0aca` — exit 0, 247 passed / 0 failed / 0 skipped. Alice ran both harnesses (22/22, 24/24) and release-checks green; Blake ran `test_codex_run.sh` green; Carl ran all three green. Recorded in the settled-decisions ledger.

### Orchestrator note — a work-phase recording gap, not a diff defect

`dev/local/autopilot/last-verification.json` is still stamped `sha: 61bd107b4cf1, cycle: 1` even though the D1 rework added three commits on top of it, and `-checks-1.json`'s single queued entry never received a `result`. Both point at the same thing: the work phase's step-7 verification did not run (or did not record) after the cycle-1 rework. That is why this cycle could not reuse the recorded counts and ran the suite itself, and why the carry-forward rule fired above. It is a defect in the autopilot machinery, not in this PRD's diff, so it is recorded here rather than filed as a finding against the change.

### Orchestrator verification of reviewer claims

Every finding was checked directly rather than taken on the reviewer's word:

- **PRD acceptance gate (21 vs 40)** — confirmed. `rg -c 'PASS "' skills/use-codex/scripts/test_codex_run.sh` returns **21**; the new `test_codex_run_resume.sh` returns **24**. The PRD's premise requires 40 in the first file. The other three acceptance criteria pass: `rg -c '"\$PROMPT" < /dev/null' codex-run.sh` is **1** (required 1, was 2 at cycle 1 — cycle 1's 🟠 High is **fixed**), `rg -c "printf '%s' \"\$PROMPT\" \|"` is **2** (required 2), release-checks green.
- **No test case was actually lost** — confirmed. 247 passed / 0 failed at HEAD against 243 at cycle 1, i.e. +4, matching the four new cases. The runtime PASS count (22 + 24 = 46) exceeds the source `PASS "` count (21 + 24 = 45) because the extracted `child_stdin_is_prompt()` helper is called from more than one site. So the PRD's chosen proxy would have broken on the requested helper extraction alone, independently of the file split.
- **Tautological unreadable-file test** — confirmed by the bash fail-first replay above: the case passes against base `61bd107`.
- **Two copies of the helper / duplicated fixtures** — confirmed. `child_stdin_is_prompt()` is defined at `test_codex_run.sh:43` **and** `test_codex_run_resume.sh:45`. `diff` between the two files reports 244 left-only and 285 right-only lines out of 483 and 524, so **239 lines are byte-identical** — more duplication than either reviewer estimated (Alice said ~90, Bob ~148).
- **Whitespace guard reaches positional prompts** — confirmed by reading `codex-run.sh:137-161`: the `case "$PROMPT"` guard sits *outside* the `if [ -n "$PROMPT_FILE" ]` block, while the CHANGELOG entry describes the change as `-f`-only.
- **Self-skipping PASS** — confirmed at `test_codex_run.sh:392-393`, and it is the only skip-shaped `PASS` branch in either harness. It did not fire in this run.
- **All seven cycle-1 findings resolved** — confirmed independently by Alice and by the acceptance-criteria counts above.

## Alice

Verified all seven cycle-1 findings resolved and ran `test_codex_run.sh` (22/22), `test_codex_run_resume.sh` (24/24) and `dev/bin/release-checks` (exit 0) at HEAD `6ee0aca`. Three findings, none blocking: the tautological unreadable-file test (🟡), the unrequested split duplicating stub/helper code instead of extracting one shared helper (🟡), and that same test degrading to a no-op PASS for a user who can read chmod-000 files (⚪).

R1: pass
R2: fail
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

## Blake

Blind lens, PRD-only prompt; located the code himself. Confirmed the core stdin routing is correct on the plain path, the JSON path shared by fresh and resume, and the dispatch-contract exception; confirmed the copilot fallback and `gemini-run.sh` were left untouched, and reproduced two of the PRD's `rg -c` counts. Three findings: the unmet `PASS "` acceptance gate (🟠), scope creep in `bb08599` (🟡), and the leading-dash case pinned only on the plain path (⚪).

Blake is blind to the cycle-1 decision-gate task by design, so he reads its two sanctioned additions as unspecified scope creep. Both were explicitly requested by that task; what survives his objection is that the **PRD** never authorised them.

B1: fail
B2: pass
B3: pass
B4: pass
B5: pass
B6: fail
B7: pass
B8: pass
B9: pass
B10: pass
B11: pass
B12: pass
B13: pass
B14: pass
B15: fail
B16: pass
B17: pass
B18: pass
B19: pass

## Bob

Codex, static-only sandbox, carrying the doubt + de-slop lens. Resumed his cycle-1 session (`--resume-thread 01a0784f-d7ff-7162-bcff-b869d4f26fa1`), so he verified the fixes against his own prior critique; the same thread id was re-captured for a future cycle. Six findings, the sharpest of the panel: the broken PRD source-count contract (🟠), the duplicated fixtures and doubled helper, the non-binding and self-skipping unreadable-file test, the positional-prompt blast radius of the whitespace guard, and two redundant test invocations.

FIX / VERIFY / KNOWN buckets were emitted (Bob carries the doubt lens this cycle; `doubt_reviewer` is `codex` and Eve was not active). All six findings landed in FIX; VERIFY and KNOWN were both `- (none)`, so `-checks-2.json` is an empty array and no verification check was queued this cycle.

R1: fail
R2: fail
R3: fail
R4: pass
R6: pass
R7: pass
R8: pass
R9: fail
R10: pass
R11: pass
R12: pass
R13: pass
D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

Gemini via copilot backend, model `gemini-3.8-flash`. Ran both harnesses and release-checks himself, including a re-run with the dispatch-guard env vars unset. He judged all cycle-1 findings resolved and the split proportionate (it keeps both files under the 800-line cap with no case lost). One finding: the unreadable-file test not binding to the new guard, which he diagnosed independently and correctly as `grep` matching `cat`'s own stderr. No frontend surface in this diff, so he reviewed as a generalist and correctly invented no frontend findings.

R1: pass
R2: fail
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

Verdict: 10 findings
Tests: 247 passed, 0 failed, 0 skipped (suite run this cycle)
