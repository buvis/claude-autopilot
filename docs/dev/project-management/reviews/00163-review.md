# Review: PRD 00163 - enforce style limits at the task boundary

Range `c43b933..89bbfd2`, 9 commits. Panel: Alice (Sonnet, consensus), Blake
(Sonnet, blind/PRD-only), Eve (Fable, doubt + de-slop), Bob (codex, static-only,
R1-R5 rubric). Converged after 2 rework cycles.

## Panel outcome

| Reviewer | Cycle 1 | Cycle 2 (re-review) |
|---|---|---|
| Alice | 3 findings (2 MEDIUM, 1 LOW) | re-ran; found the 2 cycle-2 defects independently, confirmed closed at `e19ae11` |
| Blake | 1 finding (B10 fail: dangling step-7.0 refs) | not re-run - his single finding is a grep, verified directly |
| Eve | 7 FIX, 4 KNOWN, D1-D5 pass | re-ran; reproduced both cycle-2 defects, 4 new FIX, D1-D5 pass |
| Bob | first run FAILED (sandbox), retried; 2 HIGH + 1 MEDIUM | resumed on his own thread; 2 HIGH + 1 MEDIUM, all new |

Bob's first dispatch produced nothing usable: codex's sandbox is workspace-scoped
and the review inputs were staged in the session scratchpad, outside the repo. He
answered "cannot statically verify" and failed every rubric rule. Re-staging the
same inputs under `dev/local/tmp/` and re-running fixed it. **The plan's Bob
block already says `dev/local/tmp/<PRD>-bob-prompt.txt`; its § 2 "write review
artifacts to the scratchpad" rule does not apply to Bob.** Worth carrying: Alice,
Blake and Eve all read the scratchpad fine, so only the codex lens has this
constraint.

## Findings

Severity as raised. "Dedup" collapses reviewers naming the same line.

| # | Sev | Finding | Raised by | Disposition |
|---|---|---|---|---|
| 1 | HIGH | Step 5.6's two skip rules said "proceed to step 5.7", routing test-only and trivial diffs - the common case - past the new gate. Those tasks completed with no `style_gate` value at all. | Bob | fixed `a353340`, regression test failed first |
| 2 | HIGH | `self-deslop-prompt.md` is read-first for step 5.6 and carried the same 5.7 routing in three places, re-opening #1 from the reference side. The #1 regression test only scanned SKILL.md. | Bob (re-run), Alice, Eve | fixed `e19ae11`, test widened to the reference |
| 3 | HIGH | Git-reported paths interpolated into the gate's shell commands unquoted. | Bob | fixed `a353340` - `shlex.quote()` stated in the preamble |
| 4 | MEDIUM | `RETRY_INSTRUCTION` ended "do not modify tests", which deadlocks the likeliest violation in this repo: an oversize test file. The fixer is handed a violation it may not touch, so the gate lands `failed:` forever. | Eve | fixed `a353340` - "except to split a test file a violation line names" |
| 5 | MEDIUM | Exit 1's "re-run the gate" never said to rebuild the diff; HEAD moved, so a sibling module the fixer just created was certified unmeasured. | Eve | fixed `a353340` |
| 6 | MEDIUM | Stale "step 7.0" citations in `final-verification.md:5`, `subagent-dispatch.md:136`, `check_style_limits.py:173,234` and two of its test docstrings. | Alice, Blake, Eve | fixed `a353340`, `481f5fc` |
| 7 | MEDIUM | The dependency pin computed bounds in SKILL.md and sliced `style-gate.md`, passing only because that file repeats `compute_mech_facts.py`. Introduced by the test move in this PRD. | Bob (re-run), Alice, Eve | fixed `e19ae11` |
| 8 | MEDIUM | The allowlist test pinned the directory-suffix string while claiming to guard the creation grant - deleting the grant stayed green. | Eve | fixed `a353340`, then `89bbfd2` pinned the whole instruction in both copies |
| 9 | MEDIUM | The micro lane's step walk (`rework-mode.md`) skipped 5.65; a micro edit under the 30-line ceiling can still carry a file past 800. | Eve | fixed `a353340` |
| 10 | MEDIUM | Step 5.7's `HEAD_SHA` note named the 5.6 deslop commit but not the 5.65 style-fix commit - the commit the "reviewer reads a conforming diff" claim rides on. | Eve | fixed `a353340` |
| 11 | MEDIUM | Step 2's `<task_base_sha>` reader list omitted 5.65. | Eve (re-run) | fixed `89bbfd2` |
| 12 | MEDIUM | The new per-task report line had no prose pin. | Alice | fixed `a353340` |
| 13 | MEDIUM | "One file owns every style-gate pin" was false - four moved tests still sat in `test_dispatch_prose.py`. | Eve | fixed `a353340`; that file went 763 -> 608 lines |
| 14 | MEDIUM | Mixed SKILL.md access idiom in the new test file - the same pattern that produced #7. | Eve (re-run) | fixed `89bbfd2` |
| 15 | LOW | CHANGELOG line ran 85 chars after a reword. | Alice | fixed `a353340` |

No finding was dismissed, so no Victor dispatch was needed.

## Accepted as-is

- A foreign untracked `.py` left by a prior dispatch enters every later task's
  diff and candidate list. Scoping the sweep needs a task-start untracked
  snapshot this PRD never designed, and the PRD mandates the diff be "built
  exactly as PRD 00162 specifies". (Eve)
- A violating file at the repo root gets no directory line, so its split falls
  back to the blocker / fail-loud path. The restriction is the PRD's own
  verbatim text. (Eve)
- No explicit ladder row for an exit 2 on the re-run after a fix dispatch. The
  ladder was carried over verbatim by mandate; the existing exit-2 row gives the
  shape. (Eve)
- `design-rationale.md:90` still names `test_step_7_*` against § 7.0, and a
  frozen golden fixture mentions step 7.0. Both are historical records; rewriting
  them would misrepresent what happened. (Eve, Alice)
- Cycle-1 fixes 4-6 carry no prose pins. Pin coverage is deliberately selective
  on routing and stamps; pinning every reworked sentence would itself be slop.
  (Eve)

## Live check

The tests cannot exercise the one runnable thing this PRD adds, so it was run for
real twice - once at cycle 1 and once by Eve independently:

```
render_prompt.py agents/ivan.md --set-file FILE_PATHS=<style-files list> \
  --set RETRY_INSTRUCTION="<the verbatim permission>"
-> exit 0, 3274 chars
```

The directory line keeps its ` (new modules may be created here)` suffix in the
rendered file list, and the creation permission lands after `ivan.md`'s "Read
only the files listed above. If a file or symbol you need is not listed, stop and
report it as a blocker." That ordering is the whole capability: without it the
fixer reports a blocker instead of splitting.

This PRD's own gate was also run on this PRD's diff, at cycle 1 and at close:
`check_style_limits.py --diff <session diff> <every changed .py>` -> exit 0 both
times.

## Suite

| Point | Result |
|---|---|
| Baseline (before this PRD) | 2126 passed |
| After the build | 2128 passed |
| At close (`89bbfd2`) | 2129 passed, 4 warnings, 459 subtests, 0 failures, 0 skips |

The 4 warnings are the pre-existing legacy bare-string `completed_prds` entries
in the golden fixtures, unrelated to this change.
