# `_ACCEPTED_FLIPS` re-baseline report (PRD 00277 v2)

Range compared: `86f571cea511` (before) -> `95ff83943d5e` (after). Produced in
rework cycle 1, task 7, to satisfy the cycle-1 finding that task 3's report
quoted neither the departures' nor the additions' refusal lines.

Method: the departures were replayed against the gate as it stood at
`86f571cea511` (`gate._unread_token` of that revision); the additions were
replayed against the current gate. Each line below is that refusal verbatim as
the gate prints it, which means the quoted line itself is cut at the gate's own
character limit - several end mid-word for that reason.

## Departures (12) - previous refusal line, old rule

- `00187-keep-cap-out-criticals-off-master-and-home-deferred-highs-v1-review-2.md`: line 77: a [m/n] token or table row the findings parser did not read: 1. Task 13 — [D2] Tail sweep: close the wrapper-operand `git` bypass and the flag-free wrapper false deny in the push gu
- `00188-record-convergence-cap-and-roster-per-prd-v1-review-2.md`: line 59: a [m/n] token or table row the findings parser did not read: **Cap check.** `state.cycle` 2 >= `rework_cap` 2 and one unresolved 🟠 High remains (not a settled deferral, not discarda
- `00189-stall-to-split-on-plan-expansion-v1-review-2.md`: line 36: a [m/n] token or table row the findings parser did not read: - Alice: ✅ Available (Claude subagent, sonnet; traced every prior High/Medium through `policy.py:112-202` and `__main__.
- `00192-split-loop-py-and-its-tests-under-the-cap-v1-review-1.md`: line 39: a [m/n] token or table row the findings parser did not read: - Blake: ✅ Available (Claude subagent, sonnet, blind/PRD-only; located the design doc and all eleven files, `wc -l` ten
- `00207-route-rework-resume-sessions-on-task-tier-v1-review-01.md`: line 81: a [m/n] token or table row the findings parser did not read: **Evidence.** Confirmed by the shapes block (`[MECH] 🟡 ... hedges with or`).
- `00218-leave-sessions-at-task-boundaries-and-run-one-devon-round-v1-review-2.md`: line 57: a [m/n] token or table row the findings parser did not read: 3. **No scan-back, and a `last_task_wall` that nothing calls** (`_cap_headroom.py:82,85,94`) — Alice, Bob, and Blake's s
- `00223-enter-the-build-gate-in-one-cli-call-v1-review-2.md`: line 200: a [m/n] token or table row the findings parser did not read: - [BLAKE] 🟡 Extra CLI flag `--prds`. The spec's inputs are only `--state`, `--prd` and `_AUTOPILOT_LOOP`. | File: skills
- `00244-tidy-the-enter-verb-and-the-review-diff-plumbing-v1-review-1.md`: line 213: a [m/n] token or table row the findings parser did not read: **None created in this step.** The cycle carries no 🔴 and no 🟠, so it meets
- `00256-finish-the-review-verbs-before-release-v1-review-2.md`: line 31: a [m/n] token or table row the findings parser did not read: **What the rework closed.** All three implementation-aware reviewers and the blind lens agree the cycle-1 🔴 is fixed: `_
- `00265-close-the-critical-row-escapes-v1-review-2.md`: line 38: a [m/n] token or table row the findings parser did not read: - `consolidate_findings.py` warned twice about citations merged only after line-suffix stripping. The second merge (R2,
- `00271-guard-v2-structural-delegation-check-v1-review-2.md`: line 59: a [m/n] token or table row the findings parser did not read: - [BLAKE] 🟡 The spec contradicts itself on `toolu_01Ku4TbcQoeik6ZLf5XkkAuD`. It is a pinned must-deny id. Its descriptio
- `00276-make-the-gate-record-trustworthy-v1-review-2.md`: line 64: a [m/n] token or table row the findings parser did not read: - [BLAKE] ⚪ The product-symlink scan runs `git ls-files -s` from `repo_root`, which lists only the subtree below `repo_r

Note: every departure's old refusal is a `[m/n] token or table row` detail, not
an emoji-row detail. These files leave the list because the emoji rule no longer
decides their tag, not because the files changed.

## Additions (7) - current refusal line, shipped rule

- `00171-route-sonnet-prompt-through-stdin-v1-review-1.md`: line 98: a severity emoji row the findings parser did not read: - ⚪ CHANGELOG "streamed byte-exact" overstates what the code keeps, because the
- `00208-hand-off-between-the-rework-design-and-the-first-fix-v1-review-01.md`: line 107: a severity emoji row the findings parser did not read: - ⚪ Add the missing second blank line before `test_phase_4_skip_is_the_rework_handoff_entry` (`test_design_rework_prose.
- `00232-keep-subagent-test-runs-narrow-v1-review-1.md`: line 71: a severity emoji row the findings parser did not read: - ⚪ Bob's "Cannot statically verify the next batch" row restates the PRD's own third Success Metric, an explicitly **pos
- `00256-finish-the-review-verbs-before-release-v1-review-1.md`: line 62: a severity emoji row the findings parser did not read: - 🟡 Blake: "`bash dev/bin/release-checks` exits 0 is not demonstrated; my run exited 1 in the `[checks] waves` block." *
- `00267-widen-the-phase-delegation-guard-v1-review-1.md`: line 74: a severity emoji row the findings parser did not read: - ⚪ Whitespace is not normalized after NFKC. The literal single space in `_PHASE_JARGON` ("work phase") means a double-s
- `00269-sweep-every-findings-token-v1-review-1.md`: line 137: a severity emoji row the findings parser did not read: 🔴 row while the unmatched opener itself stays live (R6). This gate verified
- `00269-sweep-every-findings-token-v1-review-2.md`: line 65: a severity emoji row the findings parser did not read: ⚪ (the partly-fixed second-table escape, the returned formatter reflow

## Verdict on the two 00269 entries

Both are FALSE refusals, and are kept deliberately. Each named line is the
second line of a wrapped prose paragraph whose wrap falls just before a
severity emoji, so after lead normalisation the emoji is the first character.
Nothing in the line's own text distinguishes it from a real no-lead finding row
(`🔴 crash on empty input | src/a.py:3`), which the PRD requires the gate to
catch, so narrowing the rule to exclude these would reopen that escape. The
cost is a noisy refusal on a review file that wraps that way; the alternative
is a CRITICAL row no check reads. Recorded as a known limitation, not as a
justified true positive.

The other five additions are genuine `- ⚪ ...` / `- 🟡 ...` finding rows that
sit outside the structured findings table.
