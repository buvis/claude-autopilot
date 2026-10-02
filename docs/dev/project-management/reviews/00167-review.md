# Review: PRD 00167 - Time-box local verification commands

Session 6 of the 00159-00168 fast-track drain.
Diff range `f3579f9..292418f` (7 commits). Converged after 2 review cycles.

## Panel

| Lens | Reviewer | Model | Cycle 1 | Cycle 2 |
|---|---|---|---|---|
| Consensus, implementation-aware | Alice | Sonnet | ran, 4 findings | ran, 2 findings |
| Blind, PRD only | Blake | Sonnet | ran, 1 finding | ran, clean |
| Doubt + de-slop | Eve | Fable | ran, 7 FIX + 1 VERIFY | ran, 4 FIX |
| Consensus + doubt rubric, codex | Bob | codex CLI | ran, 5 findings | ran (resumed thread), 5 findings |

No reviewer failed. Bob's cycle-2 run resumed his own thread, so two of his five
cycle-2 items (the vacuous pin, the red-check field collision) were already
fixed in the working tree when his reply landed; they are deduped below against
the reviewers who raised them first.

## Evidence the tests could not give

- **Live render.** The dispatch prologue reaches an implementor only through
  `render_prompt.py`, so `agents/ivan.md` was rendered for real three times
  (once per prologue change). Final: 3116 bytes, both rules present at lines
  61-65 of the rendered prompt. A prose pin proves the persona file carries the
  text; only the render proves it survives to the prompt.
- **The pack's own gates, run on this diff.** `check_style_limits.py` exited 1
  on the first draft (`FILE | test_dispatch_prose.py | 801 lines`) - that is
  what caught finding 6 below, not any reviewer's arithmetic. It exits 0 now, as
  does `check_split_hygiene.py` on the new test file.
- **Fail-first on the pins.** A worktree at `f3579f9` with only the new test
  file copied in: 4 failed, each on a distinct rule.
- **The vacuous-pin proof.** `'60000' in '600000 ms'` is `True`;
  `re.search(r'(?<!\d)60000(?!\d)', '600000 ms')` is `None`. Run, not reasoned.
- **Eve's VERIFY (does 60000 ms clear a commit with the hook stack armed?)**:
  answered by this session - seven commits through aegis `validate_commit_msg`
  plus warden, none anywhere near a minute.

## Findings

Severity as raised. "Fixed" means fixed and re-verified in a later cycle.

| # | Sev | Finding | Raised by | Disposition |
|---|---|---|---|---|
| 1 | HIGH | The `verification: "timeout:<command>"` stamp was defined as firing on a *second* timeout, but the full-suite class explicitly gets no re-run - so a foreground full-suite timeout, the longest wait in the pack, could never be recorded anywhere | Alice, Eve, Bob (3 lenses, same line) | **Fixed** `6da9fc6`: a class with no larger budget records its FIRST timeout, stated at both rule sites and pinned |
| 2 | HIGH | The step-7 stamp named a write path that does not exist: `task-done` / `append-attempt` are the only attempt writers and both run at task exit, before step 7 | Eve, Bob | **Fixed** `6da9fc6`: a step-7 timeout is recorded in the phase report only, beside the `verification: none (no suite found)` line that step already uses. Deviation from the PRD, recorded below |
| 3 | HIGH | The prologue carried the separation rule but not the budgets, so an implementor still passed no `timeout` - leaving the PRD's own success metric unmet inside a dispatch, which is where the measured 17-minute hang happened | Bob | **Fixed** `6da9fc6` |
| 4 | MEDIUM | The prologue's budget sentence assigned 300000 ms to "a test, lint or build run", contradicting the 600000 ms full-suite class for an implementor running a suite | Bob (cycle 2) | **Fixed** `292418f`: 60000 / 300000 narrow / 600000 full |
| 5 | MEDIUM | Step 2.95's red-check was routed to `verification`, colliding with `red_check`, which already owns "the runner cannot execute them". An absent `red_check` reads as "ran, saw red" | Eve (cycle 2), Bob (cycle 2) | **Fixed** `292418f`: the red-check keeps `red_check: "skipped:<cause>"`; `verification` is scoped to step 5.5. Pinned |
| 6 | MEDIUM | The pins pushed `test_dispatch_prose.py` to 801 lines, over the repo's 800-line cap - confirmed live by the pack's own style gate, not just by counting | Blake, Alice | **Fixed** `c58ea11`: pins moved to `test_command_budget_prose.py`, matching `test_style_gate_prose.py`'s precedent. `test_dispatch_prose.py` is byte-identical to its pre-PRD state |
| 7 | MEDIUM | The budget-number pin was vacuous: `"60000" in dispatch` is satisfied by `"600000"`, so the inspection budget could be deleted with the suite green | Eve (cycle 2), Bob (cycle 2) | **Fixed** `292418f`: digit-bounded `re.search` |
| 8 | MEDIUM | The pins covered `SKILL.md` and `ivan.md` but not `tess-prompt.md` / `tess-retry-prompt.md`, two of the four files that physically carry the prologue | Alice, Eve | **Fixed** `c58ea11`: all four carriers, both sentences |
| 9 | MEDIUM | The record docs kept a dead disjunct ("or on the first timeout when its class has no larger one") after the field was scoped to a class that always has a larger budget | Alice (cycle 2) | **Fixed** `292418f`: disjunct removed, the rule now reads plainly |
| 10 | LOW | `SKILL.md:82` still advertised "the three distinct deadlines" while the target doc said six | Eve (cycle 2) | **Fixed** `292418f` |
| 11 | LOW | "Five deadlines" miscounted its own list (600000 shared a bullet with 300000) | Eve | **Fixed** `6da9fc6`: six, 600000 on its own row |
| 12 | LOW | "This section shrinks no deadline that already exists" was false for the catch-all: an unclassified foreground call went from the tool's 120000 ms default to 60000 ms | Eve | **Fixed** `6da9fc6`: scoped to pack-documented deadlines, with the tightening named |
| 13 | LOW | The problem statement said foreground Bash has "no deadline" while the same section documents the tool's 120000 ms default | Bob (cycle 2) | **Fixed** `292418f`: it has no deadline *of this pack's choosing*; the 120000 ms default is named, and the measured 17 min 48 s stall is what shows it is not a reliable stop |
| 14 | LOW | Step 2.95's red-check was unclassed, so it fell to the 60000 ms catch-all | Eve | **Fixed** `6da9fc6`: added to the lint-and-narrow row |
| 15 | LOW | The CHANGELOG claimed the attempt stamp for every class | Eve | **Fixed** `292418f` (scoped in `6da9fc6`, refined after finding 5) |
| 16 | LOW | The new file's docstring said `test_dispatch_prose.py` "is at its 800-line limit" - present tense, but the file is 709 lines now | Eve (cycle 2) | **Fixed** `292418f`: reworded to the historical fact |
| 17 | LOW | The PRD text still requires a step-7 attempt stamp the pack cannot write | Bob (cycle 2) | **Fixed** `292418f`: an "Implementation note" added to the PRD itself, so a reader of `done/` is not misled |
| 18 | LOW | "a queued verification check" in the budget table names a term the pack defines nowhere | Alice, Eve (as KNOWN) | **Accepted as-is**: verbatim PRD wording; defining the verify queue is outside this PRD |
| 19 | LOW | The catch-all rule ("no documented class takes the inspection budget") has no dedicated pin | Blake (cycle 2, explicitly not a gap) | **Accepted as-is**: matches the pack's convention of selective, load-bearing pins |

No CRITICAL was raised in either cycle. No finding was dismissed on my own read,
so no Victor dispatch was needed - the two that would have qualified (findings 1
and 2) were each raised independently by two or three lenses and confirmed
against the pack's own text (`attempt-logging.md` § Append procedure names
`task-done` and `append-attempt` as the only writers) before being fixed.

## Deviations from the PRD

1. The CHANGELOG entry landed in the first commit, not the Phase 2 task -
   `rules/changelog.md` requires it in the commit that introduces the behavior.
   The Phase 2 acceptance check still passes.
2. The prologue sentence was mirrored into `agents/ivan.md`,
   `references/tess-prompt.md` and `references/tess-retry-prompt.md` beyond the
   PRD's literal "SKILL.md only" wording. SKILL.md declares the prologue a line
   every dispatch prompt "must contain verbatim", and those three files are the
   only place it reaches an implementor.
3. The prologue also carries the budget numbers, not only the separation
   sentence. Without them the PRD's success metric is unmet inside a dispatch.
4. A step-7 timeout records in the phase report only (finding 2). A step-2.95
   red-check timeout keeps `red_check` (finding 5). The PRD said "on the attempt
   record for a step-5.5 or step-7 command"; only step 5.5 has a live entry.
5. `state-schema.md` had no `verification` key in the `tasks[].attempts`
   signature at all, so the field was added rather than only extended.
6. The pins live in a new `test_command_budget_prose.py`, not in
   `test_dispatch_prose.py` as the PRD names (finding 6).

## Suite

`uv run --no-project --with pytest --with rich --with textual python -m pytest -q skills`
-> **2166 passed, 4 warnings, 459 subtests passed in 52.59s**.
Baseline before this PRD: 2159 passed. The seven new tests are this PRD's prose
pins. Zero failures, zero skips.
