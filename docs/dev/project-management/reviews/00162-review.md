# Review: PRD 00162 - fix style-gate blindness to new files

Session 3 of the 00159-00168 fast-track drain.
Range `b0857f0..HEAD`. Panel: Alice (Sonnet, implementation-aware), Blake
(Sonnet, blind/PRD-only), Eve (Fable, doubt + de-slop), Bob (codex, static,
rubric R1-R13). All four ran; none failed.

Suite at review time: 2118 (baseline) -> 2123 passed, 4 warnings, 459 subtests.
After rework: **2126 passed, 4 warnings, 459 subtests, 52.10s**, zero failures,
zero skips.

Converged after one rework cycle. Eve re-verified all three of her fixes at
HEAD (D1-D5 pass), Bob's R2 passes and his second R1 fail is closed, and Victor
refuted the one declined finding.

## Live check (the suite cannot do this one)

Ran step 7.0's literal command chain in this repo, twice.

First run, before the rework: an untracked `probe_untracked_live.py` holding a
60-line function produced `FUNCTION | ... | probe_over_limit | 60 lines` and
exit 1 - the PRD's Phase 1 exit criterion, met live. The same run also flagged
`violations()` at 54 lines in this PRD's own diff, which is why `13c6511`
exists.

Second run, after the rework: same result for the oversized module, an empty
untracked `.py` no longer forces exit 2, and the new untracked test file reads
clean. That run also flagged the wiring pin at 52 lines and
`test_dispatch_prose.py` at 822 lines, which is why `6e32f8c` exists. The gate
caught its own PRD twice.

Probe files deleted; `git ls-files --others --exclude-standard -- '*.py'` is
empty.

## Findings

| # | Sev | Finding | Reviewer | File | Status |
|---|-----|---------|----------|------|--------|
| 1 | HIGH | The new skip contract fails healthy phases. A 100%-similarity rename, a mode-only chmod and an empty new file all emit a diff block with no `+++ b/` line, so the candidate resolves to nothing, lands in `skipped`, and the gate exits 2 where it exited 0. An empty `__init__.py` is enough to trigger it. | Eve (confirmed live by me: empty `.py` emits header + `new file mode` + `index`, no `+++`) | check_style_limits.py:36-80 | **Fixed** `387b260` |
| 2 | HIGH | Registering the header path made `+++ b/./a/b.py` and `diff --git a/a/b.py b/a/b.py` two keys that tie at equal match depth, turning a resolvable file ambiguous. Not raised by a reviewer - the existing suite caught it inside the fix for #1. A latent pooling bug: two spellings of one path were always separate keys. | existing test `test_match_normalises_dot_slash_and_double_slash_diff_paths` | check_style_limits.py | **Fixed** `387b260` (`_norm` on both key sites) |
| 3 | MEDIUM | The prose pin checked three isolated tokens; removing the append target, the final `mv`, or the untracked paths from the candidate list would leave it green. Bob failed R1 and R2 on it. | Bob | test_dispatch_prose.py:371 | **Fixed** `387b260` + `6e32f8c` (naming pin + wiring pin: append target equals the `--output=` target, the `mv` reaches the `--diff` path, `plus those untracked paths`) |
| 4 | MEDIUM | `$TMPDIR` unset (Linux, headless) aims `--output=$TMPDIR/phase-diff.txt` and the append at `/phase-diff.txt`. | Eve | SKILL.md:466 | **Fixed** `387b260` - `${TMPDIR:-/tmp}`, both occurrences |
| 5 | MEDIUM | This PRD's own diff violated the limits it polices: `violations()` at 54 lines, then the wiring pin at 52 lines and `test_dispatch_prose.py` at 822. | the live gate run | - | **Fixed** `13c6511`, `6e32f8c` |
| 6 | LOW | A file `git add`ed but not committed is invisible to both paths: absent from `<base>..HEAD`, and no longer listed by `ls-files --others` once staged. Relies on the loop's commit-per-task discipline. | Alice | SKILL.md | **Accepted.** The PRD scopes untracked files only. Closing it means diffing the working tree rather than the committed range, which changes what "this phase's diff introduced" means - a different PRD. |
| 7 | LOW | Step 7.0 is one dense paragraph mixing diff construction, enumeration, execution and exit handling; Bob asked for ordered commands and bullets, and on the rework pass argued the restructure fits the ceiling (497 -> 500). | Bob (twice) | SKILL.md:466 | **Declined, refuted by Victor.** The ceiling test counts `_TEXT.count("\n") + 1`, so the gate sees 498, not `wc -l`'s 497: Bob's own +3 lands at 501 and fails the ceiling his fix claims to fit under. Victor also found 00163 **deletes** step 7.0 entirely (its task: "Delete step 7.0 entirely", acceptance `rg -n "7\.0\|Style-limit gate"` with no hit), so restructuring it now is churn. No broken path was shown; the finding concedes "without changing behavior". |
| 12 | MEDIUM | `_norm` was only covered incidentally, by the dot-slash matcher test; the hunkless tests all spell `mod.py` identically, so they would stay green with normalisation removed. Bob failed R1 on it. | Bob (rework pass) | test_check_style_limits.py | **Fixed** `250641a`. `test_two_spellings_of_one_path_are_one_key` names the rule; stubbing `_norm` to identity makes `touched_ranges` return `['b.py', './b.py']` and the test fail. |
| 8 | LOW | A stray untracked `.py` unrelated to the phase (user scratch left in the worktree) now enters the gate. | Eve | - | **Accepted as designed.** The PRD says "every untracked Python file in the worktree"; failing loud on a forgotten file is the feature, and the outcome is non-blocking. |
| 9 | LOW | With both an unmatched candidate and real violations, exit 2 outranks exit 1: violations print but no fixer is dispatched. | Eve | check_style_limits.py:216-227 | **Pre-existing**, untouched by this diff ("an incomplete gate is never a pass"). |
| 10 | LOW | `_no_index_full_add` hand-transcribes git's output (omits the `index` line) rather than shelling to git, so format drift would evade the tests. | Eve | test_check_style_limits.py | **Accepted.** Verified byte-shape against real git twice this session; live-git generation adds environment coupling the PRD did not ask for. |
| 11 | ⚪ | Cannot statically verify the 2123-test run. | Bob | - | Suite output is pasted above and in the context file. |
| 13 | MEDIUM | `387b260` is a `fix` commit with no CHANGELOG update, and the `[Unreleased]` bullet omitted the content-free-block behavior. The changelog rule makes that blocking and non-deferrable. | Eve (rework pass) | CHANGELOG.md:52 | **Fixed** `c43b933`. The bullet now names the rename / chmod / empty-file case. The breach itself stands recorded: the entry should have ridden in `387b260`. |
| 14 | LOW | `_DIFF_HEADER_RE` lazy-matches the first ` b/`, so a path containing a literal ` b/` misparses, and it never matches a `core.quotePath`-quoted header (non-ASCII names). | Eve | check_style_limits.py | **Accepted.** Both degrade to the loud exit-2 skip, never a silent clean, and such Python module paths are pathological. |

No reviewer contested another's finding, so no Victor dispatch was needed.
Nothing was dismissed on my own read: finding 7 is the only decline, and it went
back to its author with the ceiling arithmetic.

## Rubric

Alice R1-R13 pass. Blake derived B1-B12 from the PRD (no rubric reached him)
and passed all twelve. Bob failed R1 and R2 on finding 3; after the rework R2
passes and his second R1 fail (finding 12) is fixed in `250641a`.

## Deviations from the PRD

- The no-match skip is recorded inside `_resolve_diff_path`, not in
  `violations()` as the PRD's Behavior line specifies. The PRD-literal
  placement needed a dedup guard against the ambiguous-tie branch and pushed
  `violations()` to 54 lines, which the live gate run flagged. Behavior is
  identical: one `skipped` entry per unresolvable path, order preserved.
- Step 7.0 stages `phase-diff.txt` under `${TMPDIR:-/tmp}` and `mv`s it into
  `dev/local/tmp/`. The PRD's literal `>>` into `dev/local/` is denied at
  runtime by aegis's `block_devlocal_redirects.py`. Final path and bytes are
  as specified.
- `touched_ranges` also registers hunkless blocks and normalises diff-path
  keys. Not in the PRD; both fix regressions this PRD's own change introduced.
- The prose pins live in `test_dispatch_prose_prd00162.py`, not in
  `test_dispatch_prose.py` as the PRD's Phase 1 task 2 says, because they
  crossed that file's 800-line limit. Same pattern as
  `test_check_style_limits_prd00136.py`.
- The CHANGELOG entry landed across the two `fix` commits that introduce the
  behavior, not only in the final task.
- One Phase 0 task-2 test (the absent-candidate exit-2 case) landed in the
  task-1 commit, so the fix had a failing regression test first
  (`rules/testing.md`).
- `test_violations_records_an_unreadable_path_in_the_skipped_list` was
  rewritten: it asserted the old contract ("a path that simply is not in the
  diff is NOT a skip"), which this PRD reverses.
