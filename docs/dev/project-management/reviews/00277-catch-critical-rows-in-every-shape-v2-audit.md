# Decision Audit Log: 00277-catch-critical-rows-in-every-shape-v2

PRD: `00277-catch-critical-rows-in-every-shape-v2.md`
Started: 2026-10-14T23:28:13Z
Completed: 2026-10-14T23:28:13Z
Autonomous: 21  |  Deferred: 6  |  Doubts: 0

### [autonomous] 2026-10-14T23:28:13Z

**Decision**: Design for lead-normalised emoji rule + CommonMark-correct fences in gate.py

**Choice**: Converged after 3 review dispatches (codex unavailable both times, sandbox-init failure in this environment; Claude fallback used each time); fixed 5 blockers (ordinal-regex anchor bug, missing tab-strip, and three existing-test regressions the PRD did not name: a fence-closer test pinning old behavior, a direct _is_unread_line predicate test, and ~20 assertions through a shared _unread_detail helper)

**Rationale**: 0 open cardinal sins/blockers at close

### [autonomous] 2026-10-14T23:28:13Z

**Decision**: _strip_lead adds a "same lead mark may not repeat" rule (last_mark/break) that is in neither the PRD nor the design, so nested leads are not stripped. `> > 🔴 crash`, `- - 🔴 crash`, `– – 🔴 x` and `> > - 🔴 x` return _is_emoji_row False. The old `_BULLET_LEAD_RE.match` plus `search` arm refused all of them, so a CRITICAL row in a nested blockquote or nested list now passes the gate. Fix: drop the last_mark logic (design `_strip_lead` has none) and delete the `-- 🔴` expectation

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-14T23:28:13Z

**Decision**: `_strip_lead` stops at any repeated non-emphasis mark, so a nested lead hides the row. `> > 🔴 crash x.py:3`, `- - 🔴 crash` and `• • 🔴 x` all returned None (read as prose). The cause is the `ch == last_mark and ch not in ("*","_")` break, which skips the second mark. A nested blockquote or nested bullet row with a CRITICAL emoji and a file cell still passes the gate.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-14T23:28:13Z

**Decision**: test_non_letter_junk_before_the_emoji_is_not_a_lead pins the `-- 🔴` doubled-dash case as prose, so it locks in the nested-lead bypass above. No test covers `> > 🔴` or `- - 🔴`, which must be rows.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-14T23:28:13Z

**Decision**: CHANGELOG line 31 was not reworded, although the PRD and Task 3 require it. It still reads "wordless/bracket/fullwidth row", the claim the PRD says is wrong. Only a new line (CHANGELOG.md:36) was added. The PRD must-have "CHANGELOG line 31 describes the lead-normalised rule" is unmet

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-14T23:28:13Z

**Decision**: Task 3's required rewrite of the existing changelog entry is missing; the diff only adds a Fixed entry. Update the original entry to describe the first-character-after-lead-normalisation rule.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-14T23:28:13Z

**Decision**: Dead code: `_BULLET_LEAD_RE` is now unused (rg finds only its definition, gate.py:203), and its comment still describes the deleted bullet-lead arm. Remove it and the comment

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-14T23:28:13Z

**Decision**: `_BULLET_LEAD_RE` is now dead code (no readers) and its comment describes the removed rule.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-14T23:28:13Z

**Decision**: Style and size: the new `_fence_close` is followed directly by the unrelated `# The malformed detail...` comment with no blank lines (PEP8 expects two). gate.py is at 796 of 800 lines, and test_gate_findings_shapes.py (1056 lines) grew again past the limit

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-14T23:28:13Z

**Decision**: Simplification: _strip_lead tests single-character membership via regex _LEAD_MARK_RE.match(ch) where a frozenset lookup is simpler and avoids regex evaluation overhead

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-14T23:28:13Z

**Decision**: The design's pseudo-opener followed by a real closed fence case is untested. The current test ends with an unclosed opener. Add a visible row before a real fence pair and visible content afterward, asserting that only the real fenced span is blanked.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-14T23:28:13Z

**Decision**: `_ACCEPTED_FLIPS` accepts 00269-sweep-every-findings-token-v1-review-1 (comment: `🔴 row while the unmatched opener itself stays live (R6)...`). That line looks like a wrapped prose continuation that starts with a mention of the emoji. It meets the mechanical join rule but is probably a false refusal of the same kind packet 5 describes. The comment justifies it only as "newly caught under the no-lead-needed rule", with no check that it is a real finding row

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-14T23:28:13Z

**Decision**: The supplied context lacks the required report quoting every departing baseline entry's refusal line. Compare `_ACCEPTED_FLIPS` between 86f571cea511 and 95ff83943d5e, then check that Task 3's report quotes the previous refusal line for every departure and the current refusal line for every addition.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-14T23:28:13Z

**Decision**: Rework tier for the three mechanical D1 tasks (5 CHANGELOG-adjacent test file, 6 prose/CHANGELOG, 7 _ACCEPTED_FLIPS evidence)

**Choice**: dropped from opus to sonnet; task 4 (gate.py nested-lead logic) kept at opus

**Rationale**: Cycle 1 raised no 🔴 row, so the PRD's default_model opus floor does not apply (it is scoped to CRITICAL D-tasks). Measured: opus-floor rework tasks ran 71-118 min against 10-33 min at sonnet (00223, 00218). Task 4 keeps opus because it is the trust-boundary rule the PRD's own model_tier_rationale names.

### [autonomous] 2026-10-14T23:28:13Z

**Decision**: Bob's VERIFY item R12 (compare _ACCEPTED_FLIPS between 86f571cea511 and 95ff83943d5e and check Task 3's report quotes each departure's and each addition's refusal line)

**Choice**: not queued to the verification-check queue; routed as an ordinary fix finding into D1 task 7

**Rationale**: The item names a two-step comparison, not one runnable command, so the queue's command-shape rule excludes it (output-formats.md: a VERIFY finding whose text yields no exact command is not queued). No checks-1.json was written this cycle. Recorded so the refusal is visible rather than silent.

### [autonomous] 2026-10-14T23:28:13Z

**Decision**: R1: gate_replay_baseline.json does not cover three of the loop's own newer review files, whose lens bullets are refused with the emoji detail

**Choice**: auto-fix (tail sweep)

**Rationale**: Additive fixture work: extend the replay baseline so the loop's own current format is covered by the guard. Blake confirms the old rule refused the same lines, so this is coverage, not a new flip.

### [autonomous] 2026-10-14T23:28:13Z

**Decision**: R4: the refusal detail quotes line.strip()[:120], so an emoji row behind a >120-character lead is cut before the emoji the spec requires the detail to show

**Choice**: auto-fix (tail sweep)

**Rationale**: Clear mechanical fix in the detail composition; the PRD requires the matched emoji in the detail.

### [autonomous] 2026-10-14T23:28:13Z

**Decision**: R6: two overlapping CHANGELOG Fixed entries describe the same lead-normalisation rule

**Choice**: auto-fix (tail sweep)

**Rationale**: Editorial merge into one entry; acceptance criterion already holds either way.

### [autonomous] 2026-10-14T23:28:13Z

**Decision**: `_replay_verdict` only replays the 318 files in `gate_replay_baseline.json`. I ran `_unread_token` over every current review file with a Consolidated Findings section. Three of the loop's own newer files are refused with the emoji detail on a `- 🟠`/`- 🟡` lens bullet: 00277-catch-critical-rows-in-every-shape-v2-review-1.md:145, 00278-make-release-checks-tell-truth-v1-review-1.md:118 and 00278-make-release-checks-tell-truth-v1-review-2.md:128. The success criterion says the loop's own format is not among the new flips, and the replay guard cannot confirm that for these files. The old bullet rule refused the same lines, so this is not a flip caused by the new rule.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-14T23:28:13Z

**Decision**: The refusal detail quotes `line.strip()[:120]`. An emoji row whose lead is longer than 120 characters (for example repeated `> ` or many zero-width characters) is cut before the emoji. The detail then says "a severity emoji row" without showing the emoji. The spec requires the detail to contain the matched emoji.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [autonomous] 2026-10-14T23:28:13Z

**Decision**: CHANGELOG line 31 was reworded as asked. A second, overlapping Fixed entry at line 36 repeats the same rule instead of one entry covering the no-bullet shapes, the bold-lead false refusal and the pseudo-fence. `rg 'lead' CHANGELOG.md` hits under `[Unreleased]`, so the acceptance criterion holds.

**Choice**: auto-fixed

**Rationale**: fixed by review-close

### [deferred] 2026-10-14T23:28:13Z

**Decision**: The shared test file exceeds the 800-line limit; its final test starts at line 1041. This predates the diff, and splitting it exceeds this task's prescribed helper and closer-test edits.

**Rationale**: deferred by review-close

### [deferred] 2026-10-14T23:28:13Z

**Decision**: 7 touched test(s) pass against the pre-change code: test_a_longer_closer_closes_and_a_4_space_closer_does_not, test_a_4_space_opener_does_not_open_a_fence, test_a_line_with_no_severity_signal_is_not_refused +1 more

**Rationale**: deferred by review-close

### [deferred] 2026-10-14T23:28:13Z

**Decision**: R2: the spec names _LEAD_RE, implemented as _LEAD_MARKS + _ORDINAL_LEAD_RE + a loop in _strip_lead; behaviour matches

**Choice**: settled deferral

**Rationale**: Symbol name only; behaviour verified against every spec probe. Recorded in the PRD ledger.

### [deferred] 2026-10-14T23:28:13Z

**Decision**: R3: two fence tests live in the new test_gate_fence_shapes.py rather than the spec's file, and one pre-existing closer test was inverted

**Choice**: settled deferral

**Rationale**: The split was cycle 1's own R4 fix for the 800-line limit; the new file is registered in release-checks. The inversion is forced by the spec's new fence rule.

### [deferred] 2026-10-14T23:28:13Z

**Decision**: R5: _is_emoji_row precedes the token and pipe arms, so a row carrying both signals gets the emoji wording

**Choice**: settled deferral

**Rationale**: Wording only; the row is refused either way and the emoji wording is the more informative.

### [deferred] 2026-10-14T23:28:13Z

**Decision**: R7/R8: 100 touched tests pass against the pre-change code (fence-shapes 28, unread-shapes 72)

**Choice**: settled deferral

**Rationale**: Artefact of the incremental diff base (cycle 1's HEAD already implements the rule); the tests pinned the behaviour when written. Recorded in the PRD ledger.
