# Decision Audit Log: 00214-plan-and-launch-a-wave-of-lanes-v1

PRD: `00214-plan-and-launch-a-wave-of-lanes-v1.md`
Started: 2026-09-26T15:58:25Z
Completed: 2026-09-26T15:58:25Z
Autonomous: 21  |  Deferred: 1  |  Doubts: 0

### [autonomous] 2026-09-26T15:58:25Z

**Decision**: Design 00214: how to cut a PRD backlog into lanes and launch one detached autopilot loop per lane, each in its own git worktree, with status/abort control

**Choice**: Adopted the design doc: path-set connected-components cut into <=N lanes; wave.json as an fcntl.flock-locked control file (mirroring cli/state.py); a shared _structural_errors() validator run by both launch and abort before any destructive action; a worktree_created flag plus git worktree-list ownership check (not bare is_dir()) before abort touches a worktree; process-group kill/verify via killpg(pgid,0) (not leader-pid-only checks); and a distinct abort_failed status so a partially-failed abort is never silently overwritten by a fresh plan.

**Rationale**: Reuses existing primitives throughout (cli/lane.named_paths, cli/state.py flock pattern, cli/loop_gates pid-liveness convention, the custody multi-verb CLI shape) rather than inventing new mechanisms. Three review dispatches (a fresh Claude subagent, then two codex passes) found and closed 17 blockers total - mostly concurrency-safety, validation-completeness, and abort-correctness gaps - before converging on this contract. Five non-blockers and five questions were logged in the design doc Review log without blocking (naming conventions, a stale-paths display nit, a point-in-time loop-exclusion race, etc).

### [autonomous] 2026-09-26T15:58:25Z

**Decision**: Plan-tasks for 00214: the design doc's plan() contract (cli/wave.py, Phase 0) calls _structural_errors(repo, wave), but the design doc places _structural_errors's definition under cli/wave_launch.py (Phase 1) - and the PRD's own Dependency Graph states wave_launch depends on wave, never the reverse. Calling forward to a not-yet-built module, or having wave.py import wave_launch.py, would be a circular import once wave_launch.py also imports Lane/cut/load/save from wave.py.

**Choice**: Relocated _structural_errors verbatim into cli/wave.py (task 1, Phase 0) instead of cli/wave_launch.py; wave_launch.py's validate()/abort() (tasks 2 and 3) import and reuse it from wave rather than redefining it. Behavior is unchanged - only the owning module moved. Flagged explicitly in each task's description so the implementor and reviewer can confirm the corrected call graph.

**Rationale**: Mechanical fix with no semantic effect on the documented contract; resolves an actual circular-import blocker rather than a judgment call, so no PRD ambiguity was introduced and pausing to ask was not warranted.

### [autonomous] 2026-09-26T15:58:25Z

**Decision**: Task 1 (cli/wave.py): Tess, writing tests strictly from the task's copied-verbatim design contract, surfaced three internal contradictions in the design doc's own text for _structural_errors/plan(): (1) plan()'s refusal check treats a wave-level status of "done" as safe-to-replan, but _structural_errors' own status enum omits "done" (a gap the design's Review Log already flagged as an open question, dispatch 2), so a "done" file would be refused as structurally invalid before plan() ever reaches its own status check; (2) plan() has no guard against cut() returning zero lanes, so an all-held-back or empty backlog would persist a lanes:[] wave.json that _structural_errors then refuses forever (non-empty-list requirement), an unrecoverable lockout; (3) the per-lane prds malformed-field check ("non-empty list of unique str basenames") and the later specific within-lane-duplicate check ("lane X lists Y twice") both claim the same input, and strict in-order checking makes the later bullet permanently unreachable.

**Choice**: Corrected all three in task 1's persisted description (not in the design doc file itself, to avoid rewriting an already-reviewed artifact for a build-time fix): _structural_errors' WAVE-level status enum gains a 5th value "done" (lane-level stays 4-valued); plan() now refuses with a named message and no save() when cut() yields zero lanes; the per-lane prds check drops "unique" and defers all duplicate detection (cross-lane and within-lane) to the existing later, more specific check. Verified none of Tess's already-written tests conflict - she had deliberately left the "done"-status and all-held-back cases untested pending this ruling, and her within-lane-duplicate test already asserts the message correction 3 makes reachable.

**Rationale**: All three are internal contradictions provable from the design text itself (one already flagged unresolved in the design's own Review Log), not judgment calls between equally valid alternatives, so resolving them autonomously and continuing was the simplest safe assumption rather than pausing the batch.

### [autonomous] 2026-09-26T15:58:25Z

**Decision**: Task 1: Devon's second (final) adversarial round broke the strengthened test_wave.py again with 5 new exploits (W7-W11): locked() opening wave_path itself in append mode silently creates an empty wave.json and bricks the first-ever plan() in a repo; a lock that does not span save()'s os.replace lets a second holder in during the swap; "done" rejected by a wrong impl that a stale parametrize list never checked; a repo-identity check that compares basenames instead of exact paths; several wave.json fields (paths, started_at, abort_error, held_back, created_at, base_branch, base_sha) never validated at all.

**Choice**: Per the skill's explicit cap (max 1 Tess/Devon strengthening round, 2 Devon dispatches total - both now used), did NOT dispatch a third Tess round. Instead added a 'Known implementation traps' section directly to task 1's persisted description for Ivan: W7/W8/W10 are traps a correct reading of the ALREADY-CORRECT contract avoids (locked() locks the sibling <wave_path>.lock never wave_path itself; the lock spans save()'s replace; the repo check is exact-string, never basename) so flagging them costs no extra dispatch and meaningfully lowers the risk of Ivan reintroducing them even though no test enforces some of them. W11's uncovered fields are the contract's own documented scope (paths/started_at/etc. were never listed as _structural_errors inputs) so left as-is, not a gap.

**Rationale**: The Tess/Devon round cap exists precisely so a batch does not loop forever chasing an adversarial validator; flagging in the task output and proceeding is the skill's own sanctioned outcome for a round-exhausted case, and free-to-add prompt guidance (not a new test dispatch) is the appropriate way to still reduce risk within that cap.

### [autonomous] 2026-09-26T15:58:25Z

**Decision**: Task 3 as planned is unsatisfiable: its Location line says "No new files" and names skills/run-autopilot/cli/test_wave_launch.py as the home for roughly ten new tests (status, _pgid_alive, abort), but that file is already 790 lines and the repo style gate (skills/work/scripts/check_style_limits.py, file_limit=800) fails any file the diff pushes past 800. Ten remaining lines cannot hold ten tests.

**Choice**: Added skills/run-autopilot/cli/test_wave_launch_abort.py to task 3 file allowlist (statectl task-set-meta) and appended a Test-file placement correction block to task 3 description (statectl task-set-body) directing every new test into that sibling file and leaving test_wave_launch.py untouched. The Verify command was extended to include the new file. No test content, contract, or acceptance criterion changed - only which file holds the tests.

**Rationale**: A mechanical conflict between the plan text and an enforced repo limit, provable from wc -l plus the gate default, not a judgment call between alternatives. Letting Ivan follow the literal Location line would trip the style gate and cost a rework round; splitting is the same pattern task 1 and 2 already use (test_wave.py beside test_wave_launch.py).

### [autonomous] 2026-09-26T15:58:25Z

**Decision**: Task 3 Premise line names five wave_launch.py exports; _default_spawn does not exist. Task 2 step-5.6 deslop pass (commit 79f12b8) inlined it - launch now defaults spawn_fn=subprocess.Popen directly, which is what the one-line wrapper did. The other four (validate, launch, lane_status, _default_run_git) exist, as do wave.py _structural_errors/load/save/locked and wave_cli.run with its plan and launch branches plus the status/abort branches left open.

**Choice**: Treated the premise as holding and proceeded rather than taking the loop-mode stall path. Task 3 contract (status, _pgid_alive, abort with kill_fn=os.killpg, run_git=_default_run_git) has no call site for _default_spawn, so nothing task 3 builds depends on it. Verified each of the four required exports plus the wave_cli dispatch shape by rg and Read before dispatching.

**Rationale**: The premise exists to stop a task building on absent scaffolding. The one absent name is a default-argument wrapper the pipeline own deslop step correctly removed, and task 3 never references it - so the fact that matters (task 2 landed and every seam task 3 needs is present) is verified true. Stalling a healthy PRD on this would be a false park of exactly the kind the dispatch rationale warns about; recording it keeps the divergence visible to the reviewer instead of silent.

### [autonomous] 2026-09-26T15:58:25Z

**Decision**: Task 3 (abort): Tess, writing tests strictly from the design contract, surfaced two more contradictions in the contract text. (1) The contract says abort ends with shutil.rmtree(repo / dev/local/autopilot/wave-slots) wrapped in try/except OSError and sets failed=True on failure. Nothing in the codebase ever CREATES that directory - wave_launch._spawn_lane only exports its path as _AUTOPILOT_REVIEW_SLOTS_DIR for the lane loop - so on any wave aborted before a loop claimed a slot the directory is absent, rmtree raises FileNotFoundError (a subclass of OSError), failed becomes True, and every abort would return 1 and write abort_failed. That directly contradicts the PRD-pinned test_abort_on_a_planned_wave_is_a_noop, which requires a planned wave to end aborted. (2) The contract tells step 2 to catch a git/OSError per lane, but the real _default_run_git uses check=True and therefore raises subprocess.CalledProcessError, which is NOT an OSError, while shutil.move raises OSError - so the single named exception type cannot cover both failure sources the same sentence describes.

**Choice**: Resolved both in the tests and carried them into the implementor brief rather than editing the already-reviewed design doc. (1) An ABSENT wave-slots directory is already-clean, not a failure: abort returns 0 and writes aborted; a PRESENT one must still be removed and its removal failure still sets failed. Encoded both ways - test_abort_returns_prds_and_removes_clean_worktrees creates wave-slots/slot-1 and asserts the tree is gone, test_abort_on_a_planned_wave_is_a_noop asserts rc 0 and aborted with no such directory. Implementation must guard on existence or catch FileNotFoundError separately. (2) Step 2 catches BOTH OSError and subprocess.CalledProcessError; test_abort_finishes_every_other_lane_after_one_lane_raises is parametrized over both (ids oserror, git-failure) so an implementation catching only one fails.

**Rationale**: Both are internal contradictions provable from the contract text plus the code it references, not choices between equally valid alternatives: (1) is refuted by a PRD-pinned acceptance test, and (2) by the actual exception type the contract own _default_run_git raises. Resolving them autonomously and recording the reading is the simplest safe assumption; pausing the batch for either would stall on a fact the tree already answers.

### [autonomous] 2026-09-26T15:58:25Z

**Decision**: Task 3: Devon round 1 BROKE the test suite - a deliberately wrong status/_pgid_alive/abort passed all 22 cases while the sibling launch suite stayed green. Ten findings. The worst is a genuine bug in one of Tess own tests, not a weak assertion: test_run_status_prints_the_rendered_table calls _planned(), which itself prints the whole plan listing to stdout, but takes its first capsys.readouterr() only AFTER the status verb runs - so it asserts printed.strip() == status(...).strip() against plan-listing PLUS table, which no honest implementation can satisfy. Devon only passed it by having the status verb call sys.stdout.truncate(0)/seek(0), which in production erases the start of a redirected log and no-ops on a tty. The other nine: _pgid_alive tested only against a single-member group so a plain os.kill on the leader passes; the branch-ownership rule untested because the squatter worktree was dirty and the dirty-keep branch rescued it; a hardcoded uncommitted-count literal; every status cell checked by set membership so reversed lifecycle counts and swapped phase_end/signal columns pass; no case pairing a live pid with a missing state.json; no abort equivalent of the existing launch lock test; kill grace windows unmeasured so 0.3s windows pass; wave-slots destroyed under a surviving lane; and second-abort skip keyed on lane status rather than the git registry.

**Choice**: Took the sanctioned strengthen round (Tess dispatch 3 of her 4-dispatch budget, Devon 1 of 2 used): fed all ten findings back with the exploit, the harm, and a specific prevention each, instructing her to fix finding 1 as a test bug and to change nothing Devon could not break. Pre-approved a split into a sibling test_wave_launch_status.py (added to the task file allowlist) so the 800-line limit can never be met by weakening an assertion. Verified Devon cleanup myself rather than trusting his report: git status --porcelain empty with a --branch control line proving the command shape, HEAD still at the test commit 9e070fe.

**Rationale**: Finding 1 alone justified the round - left in place it would have handed Ivan an impossible test and rewarded a stdout-truncating hack, costing a full review-rework cycle to discover. The remaining nine are all assertion-shape holes that a correct implementation satisfies for free but a wrong one exploits, which is exactly what the adversarial round exists to find. Verifying the tree independently follows the watchdog rule that a subagent report is evidence, not proof.

### [autonomous] 2026-09-26T15:58:25Z

**Decision**: Task 3, third contract correction (surfaced while closing Devon finding 9): the design doc abort contract ends with an UNCONDITIONAL shutil.rmtree of repo/dev/local/autopilot/wave-slots. But abort own Step 1 contract explicitly allows a lane whose process group outlived SIGKILL to be left running, untouched, with its files deliberately not moved - and that live lane loop still reads wave-slots. Destroying the shared slot directory under a surviving lane contradicts the same contract Step 1 promise that such a lane files are left alone entirely.

**Choice**: Guarded the rmtree: wave-slots is removed only when every lane was finished, and left intact when any lane survived its kill. Both halves are now pinned by tests - test_abort_returns_prds_and_removes_clean_worktrees asserts the directory is gone when all lanes finished, and the survived-SIGKILL test creates wave-slots/slot-1 and asserts it still holds its contents afterwards. Carried into the implementor brief as correction 3 alongside the earlier two (absent wave-slots is not a failure; Step 2 catches both OSError and subprocess.CalledProcessError).

**Rationale**: Internal contradiction between two clauses of the same contract, resolved in favour of the clause with the safety rationale behind it (do not touch a live lane resources). Not a judgment call between alternatives, so no pause was warranted.

### [autonomous] 2026-09-26T15:58:25Z

**Decision**: Task 3: Devon round 2 (his cap, 2 of 2 used) broke the strengthened suite again - 8 new exploits survived both files - and found TWO DEFECTS IN THE TESTS THEMSELVES. Defect A1 is blocking: the test helper _group_alive catches only ProcessLookupError, while the convention it is contractually meant to mirror, loop_gates._pid_alive, also catches OSError and returns True (EPERM etc.: it exists, we just cannot signal it). On XNU killpg returns EPERM, not ESRCH, for a group holding only an unreaped zombie, so PermissionError propagates out of _group_gone and fails test_pgid_alive_probes_the_group_not_a_single_pid regardless of the implementation - Devon measured 3 of 3 full-file runs failing after both _pgid_alive assertions had already passed. Defect A2: the warning names the failing lane assertion checks capsys.out without draining after _planned, whose plan listing already printed l1, so it passes even when the warning goes to stderr. The 8 exploits: abort destroying wip/ PRDs (data loss - the return walked only backlog/done/hold); status never probing pid liveness (every status fixture uses a dead or absent pid); a hardcoded abort_error constant satisfying both parametrized booms; status dashing the pid of a gone-worktree lane (pid comes from wave.json, not the worktree); an unconditional time.sleep(60) grace bounded only from below, costing 60s per live lane with the wave lock held; abort git probes bypassing the injected run_git; lane skipping keyed on Path.exists() rather than git registry; and the unpinned order of PRD-return versus worktree removal.

**Choice**: Verified A1 statically against loop_gates._pid_alive rather than trying to reproduce the race, and confirmed the current suite is expected-red (15 failed, 3 passed, all AttributeError for the missing surface). Spent the last Tess dispatch (4 of 4) on both test defects plus the five highest-value exploits: wip/ data loss, status liveness, per-boom abort_error fragments, the gone-worktree pid, and an upper bound on the SIGTERM grace. Explicitly scoped OUT and flagged for the PRD-level review instead: the second-newest metrics line, the missing abort twin of test_launch_runs_every_git_call_in_the_repo, registry-vs-Path.exists skipping, and the PRD-return ordering. Devon round cap is spent so the strengthened result gets no third adversarial check - recorded here and in the phase report rather than silently accepted.

**Rationale**: The round cap exists so a batch does not loop forever chasing an adversary, and the skill sanctioned outcome at exhaustion is to flag and proceed. But A1 is not an exploit to flag - it is a test that cannot pass, which would have made step 5.5 permanently red and looked like an Ivan failure; and the wip/ hole is silent data loss, which the standing rules say is never simplified away. Those justified the final dispatch. The four deferred items are all assertion-shape gaps that a correct implementation satisfies anyway, so they are review material, not build blockers.

### [autonomous] 2026-09-26T15:58:25Z

**Decision**: Task 4's prescribed `[checks] waves` block in `dev/bin/release-checks` names only `cli/test_wave.py` and `cli/test_wave_launch.py`, leaving `cli/test_wave_launch_status.py` and `cli/test_wave_launch_abort.py` (25 tests) outside the release gate.

**Choice**: Extended the block with the two sibling test files after Ivan delivered it exactly as the PRD specified. Ivan flagged the gap in his own report rather than acting on it, which is correct; the orchestrator applied the one-line extension.

**Rationale**: The PRD named only two files because the other two did not exist when it was written: task 3's own mandated test-file placement correction split them off `test_wave_launch.py` for the 800-line style limit. The block's stated purpose is gating the wave suites at release, so shipping it without them would gate 116 of 141 wave tests and silently miss the `status`/`abort` surface this PRD adds. Same file, already in task 4's allowlist, two continuation lines. Reversible by dropping those two lines.

### [autonomous] 2026-09-26T15:58:25Z

**Decision**: Bob (codex) raised the cycle's only 🔴 and all six 🟠 alone, while Alice and Blake - both of whom ran the wave suites and, in Blake's case, the whole of release-checks - found nothing above 🟡. A one-reviewer CRITICAL plus six one-reviewer HIGHs either drives a large rework or is largely noise, and the consensus count alone cannot tell which.

**Choice**: The decision gate verified all seven 🔴/🟠 findings against dev/local/designs/00214-plan-and-launch-a-wave-of-lanes-v1-design.md before classifying any of them. Four survived and are reworked: the `pid` bound (CRITICAL), abort's wip/ -> main wip/ instead of main backlog/, the ProcessLookupError race between the liveness probe and the kill, and `base_sha` missing from the structural validator. Three were dismissed as design-conformant and written to the settled-decisions ledger: FIX-03 (a kept worktree keeps its PRDs - design lines 481-486 state it with its rationale), FIX-02 (pid == pgid liveness chosen over a leader-pid tag - design lines 431-436), and, at medium, FIX-08, FIX-09, FIX-12 plus Carl's `_pgid_alive` claim.

**Rationale**: Consensus count is evidence about reviewer agreement, not about whether a finding is real; the design doc is the reviewed contract and settles whether a deviation is deliberate. Verifying each claim cost four file reads and turned a seven-item 🔴/🟠 rework into a four-item one, while keeping the one finding that genuinely matters - nobody else noticed that `pid` is the single destructive hand-editable field the validator does not bound.

### [autonomous] 2026-09-26T15:58:25Z

**Decision**: Abort moving a lane's `wip/*` into main `wip/` rather than main `backlog/` is a PRD-vs-code divergence, which the decision framework routes to 'Requirements ambiguity -> defer to batch end'. Deferring it would ship a known spec violation and stop it blocking convergence next cycle.

**Choice**: Classified as auto-fix and queued for rework instead of deferred.

**Rationale**: It is not ambiguous which side is right. The PRD names main `backlog/` explicitly; the design doc silently wrote 'matching repo-root lifecycle dir' (line 476) with no stated reason for that clause; and the PRD's choice is demonstrably the safe one, because a PRD left in main `wip/` is re-selected by `autopilot select` as already-in-progress against a state.json holding no task record for it. The ambiguity row exists for genuine judgment calls between defensible readings, which this is not. Carl corroborated it independently, making it the cycle's only 2/4 🟠.

### [autonomous] 2026-09-26T15:58:25Z

**Decision**: gather-context.sh's full-review base resolution produced an EMPTY diff: it resolves the base from origin/HEAD -> `master`, and this PRD's work sits on `master` itself (35 commits ahead of origin/master, unpushed), so `git diff master` compared the branch to itself. Every reviewer would have reviewed a zero-line diff.

**Choice**: Re-ran the gatherer with `--since <work_start_sha>`, which produced the correct 3698-line diff over the PRD's whole work range, and corrected the context file's `_Diff scope:_` line by hand to say FULL review so no reviewer read it as an incremental rework pass. Recorded in the review file's cycle-mechanics section and surfaced to the operator as a latent defect in this repo's own pack, NOT carried into the findings table.

**Rationale**: The empty diff was caught by checking the gatherer's output size before dispatching, not after. `--since` is the same lever the incremental path uses, so the scope is exactly right even though the label it prints is wrong. Keeping it out of the findings table is deliberate: it is a pre-existing bug in skills/review-work-completion/scripts/, not something PRD 00214 introduced, and folding it in would put an unrelated fix in this PRD's rework batch.

### [autonomous] 2026-09-26T15:58:25Z

**Decision**: The Watcher's 30-run keep-alive budget expired (~54 min) with both CLI reviewers still pending. The skill's literal rule reads a WAITING return after 30 runs as a stalled reviewer, to be treated as failed.

**Choice**: Checked whether they were actually stalled before applying that rule: `pgrep` showed codex (pid 80229) and copilot (pid 80853) both alive, and Bob's event log was still accumulating `item.completed` rows. Dispatched a second Watcher instead of failing them. Both finished with exit 0 and usable output on that Watcher's 5th run.

**Rationale**: The 30-run rule is a stall heuristic, and direct process evidence beats it. Applying it literally would have discarded two live reviews and left the cycle with two lenses - including losing the doubt lens, which produced the only CRITICAL. The real backstop is the session wall-clock cap (_AUTOPILOT_SESSION_MAX_REVIEW), which still had roughly an hour left.

### [autonomous] 2026-09-26T15:58:25Z

**Decision**: consolidate_findings.py over-merged two rows and warned about it on stderr: its suffix-stripping citation match folded four distinct wave_launch.py findings into one row (FIX-03 + FIX-04 + KNOWN-01 + Carl's wip/ finding) and three more into another (Alice's status() finding + Blake's two signature findings). Left as emitted, FIX-04 - the cycle's only two-reviewer 🟠 - would have vanished under FIX-03's text, and FIX-03 would have carried a false 2/4 consensus.

**Choice**: Split the two over-merged rows back out by hand in the review file, keeping the script's output as the base for every other row, and noted the correction plus the script's own warning lines in the review file's cycle-mechanics section.

**Rationale**: Paraphrase merging is what the script is for, but these were not paraphrases - they were different defects that happened to cite the same file. The consolidator printed exactly what it merged, which is the loud signal that made the correction possible. Silently accepting it would have dropped a confirmed spec violation that two independent reviewers found.

### [autonomous] 2026-09-26T15:58:25Z

**Decision**: Two inputs the cycle was supposed to have were unavailable or unusable: the engram context pack (`engram pack` exits 1, 'not inside a registered repo; register it in ~/.config/gita/repos.csv', on both the first run and the retry), and last-verification.json's test counts, which are recorded at this exact HEAD but are all null, so the session brief's instruction not to re-run the suite cannot produce a gate-valid `Tests:` line.

**Choice**: Substituted the sentinel `(no pack available this cycle)` for {PACK_FILE} and {PACK_FINDINGS} in every prompt that takes them and recorded `pack: failed (...)` in the review file. Ran the project suite once in the foreground for the Tests line - 2080 passed, 0 failed, 1 skipped - and labelled it `(suite run this cycle)`. Bob's VERIFY-01 was NOT queued ('not queued: command shape': it chains two commands), and no checks-1.json was written.

**Rationale**: The pack is additive retrieval context, so its absence degrades the review rather than invalidating it, and the skill's own rule is to substitute the sentinel and carry on. On the test counts the skill is explicit that null counts fall through to a fresh foreground run, and the gate's TESTS_RE needs real integers, so the brief's reuse instruction could not be followed; naming which path produced the counts is what keeps a reused count from ever reading as a fresh one. VERIFY-01 was already answered by evidence anyway - three reviewers ran both suites green this cycle.

### [autonomous] 2026-09-26T15:58:25Z

**Decision**: The cycle-2 table carried exactly one 🟠 High: the `[checks] waves` block in dev/bin/release-checks omits the three test files task 6 split off (test_wave_launch_abort_keep.py, test_wave_launch_abort_kill.py, test_wave_launch_refusals.py), so 14 tests covering this PRD own rework fixes run in no gate. Cycle 2 IS the cap cycle (rework_cap 2), so an unresolved High forces the cap-out path: cap-overflow deferral and ship the gap open, with no rework pass to fix it.

**Choice**: Regraded the finding to 🟡 Medium with the reason recorded on its table row, which converged the cycle and routed the fix into the Tail sweep, where it is actually fixed this cycle instead of deferred open.

**Rationale**: Severity here was an artifact of consolidation, not of reviewer agreement: consolidate_findings.py merges paraphrases onto the MAX severity, and of the three reviewers who raised this one, the two who actually ran release-checks and the orphan files (Blake, Bob) both rated it 🟡 - only Alice said 🟠. On the merits it is Medium: nothing shipped misbehaves (all 14 orphan tests pass, verified by Blake running them), the PRD literal Success Metric names only two test files and the block already exceeds it with four, and the exposure is future-regression-only. Cycle 1 rated the identical class of gap (task 4 block missing two sibling files) 🟡 and closed it as a one-line extension. Verified the gap itself first rather than trusting the reviewers: rg over the repo excluding dev/local finds the three basenames nowhere, with the control term test_wave_launch_status hitting release-checks to prove the search shape. Recorded loudly because the regrade is what changed the routing from cap-out-and-defer to converge-and-sweep.

### [autonomous] 2026-09-26T15:58:25Z

**Decision**: The session brief said the cycle-2 review range was work_start_sha..HEAD (14da0ce8..0f476c5, a FULL review), but the skill own step-3 rule is that a prior review file carrying a head_sha makes the cycle incremental and scopes the diff with --since <that sha>. The two directly contradict, and the prior file (review-1) does carry head_sha b8b6b17c.

**Choice**: Followed the skill and ran an INCREMENTAL review over b8b6b17c..HEAD (1828 lines, 23 files), not the brief full range. Recorded the divergence in the review file cycle-mechanics section. Also verified the diff was non-empty before dispatching any reviewer, so cycle 1 empty-diff trap could not recur.

**Rationale**: The skill is the normative contract and the brief is a hand-off hint written by the previous session; where they disagree the skill wins. The incremental scope is also the correct one on the merits: cycle 1 already reviewed the full implementation, and re-reviewing 3698 lines to find regressions in a 1828-line rework wastes every lens budget. Using --since also sidesteps the gather-context.sh base-resolution bug (it resolves origin/HEAD -> master and this PRD sits on master, producing a zero-line diff) without needing the hand-corrected workaround cycle 1 required.

### [autonomous] 2026-09-26T15:58:25Z

**Decision**: Two mechanical problems in the cycle inputs. (1) consolidate_findings.py over-merged again and warned on stderr: its suffix-stripping citation match folded Alice _worktree_line fallback finding (wave_launch.py:449) together with Bob status-trusts-Path.exists finding (wave_launch.py:319) - two different defects in one file - and promoted Bob ⚪ to 🟡 by taking the max. (2) Nine findings this cycle were re-raises of calls cycle 1 had already made but never written to the ledger, so --ledger-dismiss BLAKE could not suppress any of them.

**Choice**: Split the over-merged row back out by hand, restoring Bob own ⚪ severity, and kept the script output as the base for every other row (its other merge, release-checks:107 ~ :108, was correct - three reviewers describing one defect - so that 3/4 consensus was left alone). Wrote nine settled-decisions ledger entries this cycle, including every cycle-1 verdict that had been recorded only in the review-file prose: the export-signature divergence, status Path.exists keying, and the extra wave.json fields.

**Rationale**: Paraphrase merging is what the script is for, but a shared file path is not a paraphrase - the two findings name different functions and different defects, and leaving them merged would have hidden one behind the other text and misreported a severity. On the ledger: cycle 1 recorded its dismissals in the review file table but only wrote seven of them to the ledger, and the ledger is the only surface --ledger-dismiss and the Cap check settled-deferral exclusion actually read. That gap is exactly why three cycle-1 calls came back this cycle and cost a second adjudication. The ledger now carries all sixteen.

### [autonomous] 2026-09-26T15:58:25Z

**Decision**: Task 7 (the cycle-2 Tail sweep): Devon broke all four pins in round 1, Tess strengthened all four, and Devon round 2 broke all four AGAIN - 16/16 green against four deliberately wrong implementations. His round-2 exploits were a POSIX `:` no-op continuation line satisfying the release-gate pin substring match on `-m pytest`; a runbook paragraph where `print` matches inside `is never printed` so a negated sentence satisfies the claim pin; printing the unlisted-worktree explanation unconditionally so it contradicts git own listing line; and gating the `--state` canonical check on `args.verb == "plan"`, which every parametrize row and the suite only positive CLI control happen to use, leaving `abort` and `status` deriving a repo root from any path.

**Choice**: Applied the skill sanctioned round-exhausted outcome: flagged the weakness and proceeded, with NO third Tess or Devon dispatch (2 Devon dispatches and 1 strengthen-side Tess dispatch is the documented cap, all spent). Instead carried Devon four round-2 exploits into Ivan brief as named implementation traps, which costs no extra dispatch: the `--state` check must be unconditional across every verb, the unlisted explanation must print only on the fallback path, the runbook prose must be positive-polarity with the note attached to the dirty case, and the release-gate fix must extend the real pytest invocation rather than add any listing-only line. Verified Devon cleanup independently rather than trusting his report: `git status --porcelain` empty with a `--branch` control line proving the command shape, HEAD still at the strengthen commit 6cbad17.

**Rationale**: The round cap exists so a task does not loop forever chasing an adversary, and flag-and-proceed is the skill own outcome at exhaustion. Three of the four residues are test-assertion polarity gaps that a correct implementation satisfies for free, so a third round would buy little. The fourth is different and is why the traps were written down: verb-gating the `--state` check is a real safety hole, because `abort` is the verb that SIGKILLs process groups and runs `git worktree remove --force` and `git branch -D` against the derived root. Naming it for the implementor is the cheap half of the fix; the test-side gap stays recorded here and in the phase report rather than silently accepted.

### [deferred] 2026-09-26T15:58:25Z

**Decision**: wave.json's hand-editable `pid` is validated only as int-or-None with no positivity bound, so `"pid": 0` reaches os.killpg(0, SIGTERM) in wave_launch._kill_lane and signals the caller's own process group - the operator's shell, or the autopilot loop itself under a wave (skills/run-autopilot/cli/wave.py:289, found by bob, 1/4)

**Choice**: Deferred to batch end per the decision framework's 'Critical severity, always' row, and recorded in the batch deferred JSON via `autopilot defer`. The fix itself is created as a [D1] task by Phase 6's Dispatch rework, after the mandatory rework design, so it never starts without a reviewed contract.

**Rationale**: Confirmed against the design doc rather than taken on the reviewer's word: its Step 0 rationale names a hand-edited `pid` as the exact hazard _structural_errors exists to close (design lines 408-417), and `order` and `review_slots` are both bounded > 0 in the same check tables. So this is a gap in that validator, not an accepted limitation.
