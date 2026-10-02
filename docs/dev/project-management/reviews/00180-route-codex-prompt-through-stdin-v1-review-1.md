---
prd: dev/local/prds/wip/00180-route-codex-prompt-through-stdin-v1.md
review: 1
date: 2026-09-06
head_sha: 61bd107b4cf16f26f222bcdf7871aa85cf2679dc
codex_thread_id: 01a0784f-d7ff-7162-bcff-b869d4f26fa1
reviewers: alice,blake,bob,carl
agents:
  alice: available
  blake: available
  bob: available
  carl: available
---

# Review: 00180-route-codex-prompt-through-stdin-v1

Diff range: `4acfaa31f48539fd4227712ff839963cc0173611..61bd107b4cf16f26f222bcdf7871aa85cf2679dc`

codex_rung_guard: not fired

pack: failed (`engram pack` exited 1 — "not inside a registered repo; register it in /Users/bob/.config/gita/repos.csv"). Deterministic configuration error, so no retry was attempted; `{PACK_FILE}` and `{PACK_FINDINGS}` were substituted with the documented sentinel `(no pack available this cycle)` in every prompt that takes them. The review is degraded by the missing retrieval context, not invalid.

## Scope note

Cycle 1, a full review. `gather-context.sh` with no `--since` diffed against `master`, and because this PRD's work was committed **on** master the diff came back empty (0 lines). The gather was re-run with `--since 4acfaa31f485` so the diff covers the PRD's whole work range from `state.work_start_sha`, which is the range recorded above. The context file's own scope label therefore reads "incremental review"; that label is wrong and the range is right. No prior review file exists, so no incremental addendum was added to any prompt.

## Mechanical checks

The three computed blocks are python/pytest-only and this diff's only changed test is a bash harness, so all three had nothing to inspect. They are **vacuous, not clean**, and were delivered to the implementation-aware reviewers as a companion file (`dev/local/tmp/review-mech-00180-1.md`) rather than appended to the context file, because aegis blocks shell appends into `dev/local/` and rewriting the 145-line context file by hand risked transcription drift. Same content, same reviewers.

- `compute_mech_facts.py` — all 4 changed files skipped (non-python).
- `detect_tautological_tests.py` — checked 0 test functions in 0 test files.
- `replay_tests_against_base.py` — skipped (the diff touches no python test function).

**Bash fail-first replay, computed by the orchestrator this cycle** to cover the gap: HEAD's `test_codex_run.sh` was copied over a clean base worktree at `4acfaa31f485` (pre-change `codex-run.sh`) and run there. Result: **36 passed, 6 failed**. The six reds are exactly the rewritten and new cases — the three `codex child stdin is exactly the prompt` cases (no-flag, `--emit-thread-id`, `--resume-thread`), the no-flag argv pin, the `--resume-thread` argv pin, and the new leading-dash case. So the rewritten pins genuinely bind to this change and are not tautological, and every other case stayed green across it.

## Consolidation note

`consolidate_findings.py` ran successfully and emitted 13 rows. Three of those rows are the **same** defect — the stale line-217 comment — split because the reviewers wrote the path differently (`codex-run.sh` for Alice/Blake/Carl, `codex-run.sh:217` for Bob), and the script merges only within an identical file string. They are merged here into one 4/4 row on issue-text-plus-file, which is the matching standard this gate uses. Alice's and Bob's duplicated-stdin-check findings are likewise merged (same three blocks, different proposed remedy). The consolidation itself was the script's, not model-side; only this cross-row merge is a judgment call, recorded here so it is visible.

## Consolidated findings

| Consensus | Severity | Issue | File | Found By |
|-----------|----------|-------|------|----------|
| [4/4] | 🟠 High | Comment above `run_codex_json_path` (line 217) was never reworded and still documents the old `"$PROMPT" < /dev/null` argv shape, so the PRD's own acceptance check `rg -c '"\$PROMPT" < /dev/null' codex-run.sh` prints 2, not the required 1 | skills/use-codex/scripts/codex-run.sh | Alice, Blake, Bob, Carl |
| [2/4] | 🟡 Medium | The new `printf 'x'` / `"${PROMPT%x}"` read makes `-f` preserve trailing newlines — undocumented, no CHANGELOG line, and diverging from `test_sonnet_run.sh` T20 which pins the twin script as stripping it | skills/use-codex/scripts/codex-run.sh | Alice, Blake |
| [2/4] | 🟡 Medium | Three near-identical 8-line stdin-check blocks duplicated for the no-flag, `--emit-thread-id` and `--resume-thread` cases; the `! grep` clause is redundant after a byte-exact `diff -q` | skills/use-codex/scripts/test_codex_run.sh | Alice, Bob |
| [1/4] | 🟡 Medium | Prompt-file sentinel masks `cat` failures, potentially dispatching partially read input | skills/use-codex/scripts/codex-run.sh:142 | Bob |
| [1/4] | 🟡 Medium | Fresh JSON test does not assert the required trailing `-`, so the stub passes even if codex is not told to read stdin | skills/use-codex/scripts/test_codex_run.sh:232 | Bob |
| [1/4] | 🟡 Medium | Resume test banner still claims stdin must be `/dev/null`, opposite to the rewritten assertion | skills/use-codex/scripts/test_codex_run.sh:710 | Bob |
| [2/4] | ⚪ Low | The trailing-newline-preserving read means `[ -z "$PROMPT" ]` no longer catches a newline-only prompt file, so the `Prompt required` guard is bypassed and codex is dispatched with a one-newline prompt; untested either way | skills/use-codex/scripts/codex-run.sh | Alice, Blake |
| [1/4] | ⚪ Low | `test_codex_run.sh` grew from 752 to 794 lines, 6 short of the project's 800-line cap | skills/use-codex/scripts/test_codex_run.sh | Alice |

### Discarded (1)

- ⚪ `[BOB] Cannot statically verify: the Bash harness and release checks pass at HEAD` — sandbox artifact, not a defect. Bob is static-only by construction. The checks did run green at this exact HEAD: `last-verification.json` records 243 passed / 0 failed / 0 skipped from `bash dev/bin/release-checks` (exit 0) at `61bd107`; Alice independently ran the codex harness 42/42 and release-checks green; Carl ran release-checks green. Recorded in the settled-decisions ledger. The command is also queued in `-checks-1.json` so it re-runs after rework.

### Orchestrator verification of reviewer claims

Every finding below was checked directly rather than taken on the reviewer's word:

- **Line-217 comment / acceptance criterion** — confirmed. `rg -n '"\$PROMPT" < /dev/null' codex-run.sh` returns two matches: line 217 (the stale comment) and line 358 (the copilot fallback, the legitimate one). The PRD requires a count of 1. The other three acceptance criteria pass: `PASS "` count is 40 (required 40), `printf '%s' "$PROMPT" |` count is 2 (required 2), release-checks green.
- **Trailing-newline divergence** — confirmed. `git show 61bd107` shows the read changed from `PROMPT=$(cat "$PROMPT_FILE")` to the sentinel form at line 142. `test_sonnet_run.sh:376-393` (T20) explicitly pins the opposite for the twin script, with the comment "Pins (does not change) the pre-existing `PROMPT=$(cat "$PROMPT_FILE")` read".
- **Guard bypass** — confirmed by reading the code path: a 0-byte file still trips `Prompt required` (so the PRD's existing error-case test stays green), but a newline-only file no longer does.
- **Fresh JSON path missing the `-` pin** — confirmed. The `--emit-thread-id` block (lines 207-232) asserts `--json` presence and the `--output-last-message` value; no assertion covers the final argv token. The stub captures piped stdin whether or not `-` is passed, so nothing would catch its loss on that path.
- **Stale resume banner** — confirmed. Lines 710-715 still read "the RESUME argv path must also redirect codex's stdin to /dev/null", while the assertion at 732 now requires stdin to equal the prompt.
- **794-line file** — confirmed, `wc -l` = 794.

## Alice

Ran the codex harness (42/42) and `dev/bin/release-checks` (green), verified all four PRD `rg -c` counts directly, diffed the unchanged comment against the base commit, and cross-checked the `sonnet-run.sh` precedent. Five findings: the line-217 comment (🟠), the trailing-newline divergence from T20 (🟡), the duplicated stdin blocks (🟡), the guard bypass (⚪), and the 794/800 line count (⚪).

R1: pass
R2: pass
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: fail
R10: pass
R11: pass
R12: pass
R13: pass

## Blake

Blind lens, PRD-only prompt; located the code himself. Confirmed the runtime behavior matches the PRD on all three codex paths, the copilot fallback is untouched, the `Prompt required` guard stays, and `dispatch-contract.md` names the second exception correctly. Two findings: the line-217 comment failing the PRD's own acceptance gate (🟠), and the undocumented `-f` trailing-newline side effect (⚪). No filesystem-notes block was needed (project root is not a dot-directory and `dev/local` is not a symlink).

B1: fail
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
B15: fail
B16: pass
B17: pass
B18: pass
B19: pass

## Bob

Codex, static-only sandbox, carrying the doubt + de-slop lens. Thread id `01a0784f-d7ff-7162-bcff-b869d4f26fa1` captured for cycle-2 resume. Five findings plus one sandbox non-verification: the sentinel masking `cat` failures, the unpinned trailing `-` on the fresh JSON path, the line-217 comment, the stale resume banner, and the redundant `! grep` after `diff`. His three new findings were all independently confirmed above.

FIX / VERIFY / KNOWN buckets were emitted (Bob carries the doubt lens this cycle; `doubt_reviewer` is `codex` and Eve was not active). His single VERIFY item is queued in `-checks-1.json` with `source: "bob"`.

R1: fail
R2: pass
R3: pass
R4: pass
R6: pass
R7: pass
R8: pass
R9: fail
R10: fail
R11: pass
R12: pass
R13: pass
D1: pass
D2: pass
D3: pass
D4: pass
D5: pass

## Carl

Gemini via copilot backend, model `gemini-3.8-flash`. Ran the codex harness and release-checks himself and reproduced the PRD's `rg` counts. One finding: the line-217 comment failing the acceptance criterion (🟡). No frontend surface in this diff, so he reviewed as a generalist and correctly invented no frontend findings.

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

Verdict: 8 findings
Tests: 243 passed, 0 failed, 0 skipped (reused from last-verification.json at 61bd107b4cf16f26f222bcdf7871aa85cf2679dc)
