# Backlog review - claude-autopilot - 2026-10-18

Verdict: GO (batch 202610161547 triaged; next batch 00327 v3, 00349, 00350, 00351)

Run under the standing authorization (`~/.claude/AGENTS.md` § Autonomy) on the user's instruction to triage batch 202610161547's deferred items and hold stubs on their behalf, after the batch drained on 2026-10-17 20:48 CEST (17 done, 00327 and 00347 parked). The attended `review-batch` walkthrough was replaced by this pass: every HIGH stub re-verified against HEAD e8ca2f7 (`rg`, `Read`, one probe script for the delegation guard), every deferred row given a disposition in the ledger (`autopilot/deferred/202610161547-deferred.json`, fields `resolved`, `triaged_on`, `disposition`), and every open finding carried into a discovery document for elicitation and review before any PRD is written, as the user asked.

## Hold stubs
| Stub | Ledger key | Verified at HEAD | Disposition |
|---|---|---|---|
| 00328 consolidate_findings drops bullet-prefixed lines | 26a70f459e6f | `_LINE_RE` tolerates `^(?:[-*]\s+)?` since 3d862afd (2026-10-07), before the batch | closed: already fixed; the cycle-1 drop had another cause the orchestrator's workaround hid (no indented or numbered `[BOB]` lines survive in `docs/dev/tmp/bob-output-00320*`) |
| 00329 relative `gitdir:` pointer not refused | 6da9cfe213cf | holds: `_worktree_gitdir_pointer` returns the pointer unanchored, `samefile` raises, `continue` swallows | discovery 00360 |
| 00336 caller-signal SIGKILL without grace | 3a338afd1712 | holds: `_run_script:262` calls `verification._kill_gate` (SIGKILL) while the timeout path uses SIGTERM + `SCRIPT_GRACE_S` | discovery 00361 |
| 00337 replay guard only inside `_run_runner` | 557e1d62e8fd | holds: `_raise_on_signal` at line 158 only; `_run_in_worktree`'s `finally` at 221 unguarded | discovery 00361 |
| 00338 two SIGHUP CHANGELOG lines | 61fe1a3ae2f0 | lines 114 and 115 describe two changes; the grace is the named `SCRIPT_GRACE_S = 30` | closed: acceptance over-specified |
| 00339 guard restored before worktree removal | 470a046570d6 | holds (same guard scope) | discovery 00361 |
| 00343 bracket-in-bracket bypass | 31b3267b160e | holds: both payloads allowed by `is_phase_delegation` | discovery 00362 |
| 00344 unspaced fullwidth `！`/`？` | 54f138480301 | holds: both allowed, `。` denied | discovery 00362 |
| 00346 unbounded walk on any nonzero git result | ca4ddb14119d | holds: `_find_autopilot_dir_in_repo:1931` sets `stop` only on rc 0; no `try` around `subprocess.run` | discovery 00363 |

All nine moved from `prds/hold/` to `prds/done/` with a note naming the disposition; none is a PRD yet, by the user's process (discovery, elicitation, review, then PRD).

## Deferred rows (79)
| Disposition | Rows |
|---|---|
| discovery 00360 (verify log-sink refusal residue) | 15 (1 high, 8 medium, 6 low, all 00320 cap-overflow) |
| discovery 00361 (replay and helper signal residue) | 15 (3 high, 6 medium, 6 low, 00322 cap-overflow) |
| discovery 00362 (delegation guard pairing residue) | 8 (2 high, 5 medium, 1 low, 00324 cap-overflow) |
| discovery 00363 (markers walk-up and ledger prose residue) | 13 (1 high, 7 medium, 5 low, 00326 cap-overflow) |
| discovery 00364 (files over the 800-line cap) | 7 (review-close deferrals naming the cap) |
| closed: accepted deviation recorded by review-close | 12 (additions beyond the PRD, fail-first replays that pass at base by design, double `refuse`, `·`, negation reach, bisect) |
| closed: already fixed before the batch | 1 (00328) |
| closed: acceptance over-specified | 1 (00338) |
| resolved by 00327 v3 | 2 (the either-or hedge in `test_skip_ceiling_fails_the_gate_above_three`, its mechanical-check twin) |
| resolved: 00327 superseded, 00347 done | 2 (stall records) |
| external: loupe PRD 00001 | 1 (formatter reflow in the 00326 diff) |
| closed: by design or settled | 2 (00321 verify-escape, 00333 assumed-ambiguity) |

## New discovery documents (this session)
- 00352 batch health signals after a release; 00353 prove the pack on a clean machine; 00354 deferred findings never get reviewed; 00355 verify a single-voice HIGH before it blocks; 00356 stand-down reads formatter dirt as a peer; 00357 the drain's QA run leaves no trace until it ends; 00358 card gates miss the consumers of a changed predicate; 00359 the lane record contradicts the classifier (from the release-readiness review).
- 00360-00364 (from this triage, above).

## Gaps
- The deferred rows of the eleven earlier batches (`autopilot/deferred/2026090*` to `202610141430`) were not triaged here; discovery 00354 proposes the mechanical pass that would close them.
- No PRD was authored from the triage: the user's process puts elicitation and review before a PRD.

## End state
Hold is empty. Backlog: 00327 v3, 00349, 00350, 00351. Discovery: 00352-00364 awaiting `/elicit-requirements` and `/review-discovery-doc`.
