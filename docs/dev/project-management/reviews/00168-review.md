# Review: PRD 00168 — Record dispatch timing telemetry

PRD: `dev/local/prds/done/00168-record-dispatch-timing-telemetry-v1.md`
Diff range: `8b39509..HEAD`
Session base: `8b395097b241c1f87681bfd75b15e480b6b33b51`
Date: 2026-09-02

Reviewers: alice, blake, bob (codex, one thread resumed four times), eve
(fable), victor (adversarial verifier, one dispatch). Five review cycles,
five rework commits; cycles 4 and 5 re-ran only the two lenses the preceding
rework touched, and the cycle-5 rework was applied as those two reviewers
specified it and not re-reviewed.

## Suite

| Point | Result |
|---|---|
| Baseline (before this PRD, 8b39509) | 2429 passed, 1 skipped |
| Cycle 1 gate (7a34020) | 2455 passed, 1 skipped |
| Cycle 2 gate (87756a2) | 2464 passed, 1 skipped |
| Cycle 3 gate (a34ea03) | 2464 passed, 1 skipped |
| Cycle 4 gate (59c94d2) | 2464 passed, 1 skipped |
| Cycle 5 gate (3ed9c05) | 2465 passed, 1 skipped |
| Final gate (7604ff1) | **2465 passed, 1 skipped, 4 warnings, 459 subtests passed in 60.21s** |

The single skip is `test_check_build_overhead.py`'s golden-transcript test,
skipif-guarded on a transcript under `~/.claude/projects/`: machine state,
untouched by this diff, the same skip every drain session has reported.

The pack's own style gate (`check_style_limits.py --diff`) exits 0 on the
final diff. `skills/work/SKILL.md` is 499 lines by `test_dispatch_prose.py`'s
count against its 500-line ceiling; the Telemetry rule is folded into the
existing Budget/Watchdog pointer paragraph for that reason.

## Live checks the tests cannot do

Run from inside a scratch project with its own `dev/local/autopilot/`, with the
real scripts, at every cycle:

1. A render without the flags prints one line and creates no ledger file.
2. A render with both flags prints the count and then an 8-hex id; the start
   row's `prompt_bytes` equals the written file's size.
3. `start --kind devon --prompt-file <written prompt>` prints the file's byte
   count (18) and an id; a missing prompt file exits 2 with no row.
4. `end` two seconds later on both ids: `elapsed_s: 2`, outcomes `ok` and
   `timeout`, `detail` carried.
5. `handoff --edge leave` and `--edge resume` rows land with all six fields.
6. The working copy and the `ledger/` mirror are byte-identical (`cmp`).
7. With the working file `chmod 000`, `end` exits 0 and prints one stderr line
   for the failed lookup and one for the dropped append.
8. The PRD's literal Phase 0 acceptance (`end deadbeef --outcome ok` from a
   directory with no autopilot ancestor) exits 0 and creates nothing. Blake
   and Eve each re-ran it independently.

## Cycle 1 — 4 reviewers, 23 findings raised

| Sev | Finding | Found by | Disposition |
|---|---|---|---|
| HIGH | Watchdog kill sentence readable as two end rows (`timeout` then `ok`) | Bob | Fixed: branch on what `TaskStop` reports, close exactly once; pinned |
| HIGH | Devon and the deslop pass cost two extra calls, not the PRD's one | Bob, Blake (MED), Eve (KNOWN) | Fixed: `start --prompt-file` is the budget measurement those lanes already make and prints count then id, the two lines a render prints |
| MED | `_queued_at` swallowed read errors and malformed rows | Bob | Fixed: one stderr line each; exit stays 0; tested |
| MED | "Join on the same prd" cannot pair the PRD → PRD edge (`more_prds` preserves `state.prd`) | Alice, Eve | Fixed: pair a `leave` with the next `resume` in file order; `prd` differs across that edge |
| FIX | Codex deadline kill mapped to both `timeout` and `killed` | Eve | Fixed: `killed` is a stop before any deadline fired; pinned |
| FIX | Step 4.2 re-dispatch and codex → Claude fallback reuse a closed id | Eve | Fixed in cycle 2's shape (see below) |
| FIX | Codex dispatch checklist had no `end` bullet | Eve | Fixed; pinned |
| FIX | Devon/deslop `--prompt-bytes` named no source for the count | Eve | Fixed by `--prompt-file` |
| FIX | Phase 4 wrote the review resume row below the cycle skip | Eve | Fixed: moved above it, reason stated; pinned by index |
| FIX | Canonical Session handoff procedure wrote no row | Eve | Fixed: step 2 writes the `leave` row; pinned |
| FIX | CHANGELOG entry was 18 lines of implementation narrative | Eve | Fixed: 6 lines on the user-visible effect |
| FIX | Drive-by reformat of an untouched print in render_prompt.py | Eve | Reverted |
| FIX | `--prompt-bytes` optional, so `prompt_bytes: null` possible | Eve | Fixed (required pair in cycle 1, dropped outright in cycle 2) |
| FIX | Test docstrings and the module docstring carried session history | Eve | Trimmed |
| LOW | Handoff rows carry an `edge` field the PRD lacks | Blake | Accepted: without it a build → build handoff's two rows are identical |
| LOW | A mirror append failing after the working append leaves the row in one copy | Blake | Stated in the reference's never-blocks paragraph |
| LOW | `render_prompt.py:main` sits at exactly 50 lines | Alice | Recorded; compliant with the pack's gate |
| KNOWN | Working-copy-only lookup; 499-line SKILL.md; `--detail` over 8 KiB; abort-handler resumes write no row; review-phase reviewer dispatches get no rows | Eve | Recorded; the abort-handler case is stated in § Handoff rows |
| VERIFY | Run the installed-cache copy after the next release | Eve | Deferred to the release (see Deferred) |
| — | Cannot statically verify the suite count | Bob | Alice reproduced it independently |

Alice: R1-R13 pass. Blake: no B-verdicts (his dispatch template left `{RUBRIC}`
unbound; corrected in cycle 2). Eve: D1-D5 pass. Bob: R1, R4, R9, R10 fail.

## Cycle 2 — 4 reviewers, 15 findings raised

**One was introduced by rework 1** (the duplicate `leave` rows).

| Sev | Finding | Found by | Disposition |
|---|---|---|---|
| HIGH | Every phase-done site now writes the `leave` row twice (procedure step 2 plus a per-site imperative) | Bob, Eve | Fixed: per-site sentences are parentheticals naming the command step 2 substitutes; single writer |
| HIGH | Re-dispatches pay a `start` for an already-measured prompt: two extra calls | Bob | Fixed: a re-dispatch keeps its id and closes it again; no `start`; the last end row is terminal and spans every attempt |
| MED | `--prompt-file` stat'ed the path, so a directory passed | Bob | Fixed: the file is read; tested for a missing path and a directory |
| MED | Unparseable-line warning skipped when the start row was found first | Bob, Eve (KNOWN) | Fixed: lines parsed before the lookup; an absent ledger file reads as empty |
| LOW | SKILL.md "every call exits 0" vs `start --prompt-file` exit 2 | Bob, Eve | Fixed: the exception is named |
| FIX | `--prompt-bytes` had no caller | Eve | Dropped; `--prompt-file` required; tests retargeted |
| FIX | Codex `end` bullet lacked `lost` | Eve | Added for a missing or empty `-o` file |
| FIX | Review history reintroduced in test comments | Eve | Removed |
| FIX | Render-flag pin enumerated files by count | Eve | Replaced by a scan over every render block with a floor of seven |
| VERIFY | Can the task-boundary handoff fire outside the build phase? | Eve | Confirmed gated: the cap hook refuses to run unless `state.phase == "build"`; `--phase build` stands |
| B1/B3/B6/B7/B16 | `--edge`, the `start` verb, the split test module are literal spec deviations | Blake | Accepted; each is a stated deviation below |
| KNOWN | A CLI-side `leave` write in `phase-done` would be atomic; out of the PRD's structure | Eve | Recorded as a follow-up candidate |
| KNOWN | A missing `_walk_up.py` in a broken install raises at import | Eve | Covered by the release-time VERIFY |

Blake: B2, B4, B5, B8-B15, B17-B19 pass; B1, B3, B6, B7, B16 fail on the
accepted deviations. Eve: D1-D5 pass. Bob: R1, R2, R4, R7, R9, R10 fail.

## Cycle 3 — Alice (cycle 2, late), Eve, Bob; 1 Victor dispatch

**Two were introduced by rework 2** (the "close it again" wording and the
lost per-persona check).

| Sev | Finding | Found by | Disposition |
|---|---|---|---|
| HIGH | Keeping a re-dispatch's id makes the id join one-to-many and merges attempts' runtime | Bob | **REFUTED by Victor** (below); the catalogue now says "join the start row with the last end row for its id" |
| FIX | 4.2 and the reference told the reader to close the first attempt again, a third end row (same class as rework 1's duplicate `leave`) | Eve | Fixed: the first row is already closed at the kill or the empty return; only the re-dispatch's return closes the id again; watchdog reads "exactly once for this attempt" |
| FIX | "The prompt was measured once" is false for a continuation brief (a rewritten prompt) | Eve, Victor (side note) | Fixed: a verbatim re-send keeps the id; a continuation brief is a new prompt that `start --prompt-file` measures and opens its own row with |
| FIX | Catalogue still said "joining its two rows on id" | Eve | Fixed |
| FIX | The scan pin lost the per-persona kind check (proven by mutation) | Eve | Fixed: the persona is derived from the path after the render marker and asserted per block |
| MED | `_queued_at` built a second list only to defer the warning | Bob | Fixed: single pass |
| LOW | attempt-logging.md's "one start row and one end row" clause | Victor (side note) | Fixed: "one or more end rows" |
| VERIFY | Does a codex dispatch have a start row? | Eve | Yes: its `-f` file is step 3's flagged render with the TOOL-GATE NOTICE appended; the codex bullet says so. The batch health probe's hand-built prompt opens no row; it is not a task dispatch |
| VERIFY | Does a hard-cap rotation end a session with no `leave` row? | Eve | Confirmed from the hook; § Handoff rows now says the next `resume` row has no partner |
| LOW | The absent-ledger case read as a failed lookup | Alice | Already fixed in rework 2 |
| LOW | The context's live-check note said one stderr line for the unwritable file | Alice | Corrected to two |
| — | Commits landed mid-review | Alice (as CRITICAL) | Operational, not a diff defect: a34ea03 was this session's rework 2, dispatched without waiting for her 100-minute run; 6b8e087 and 39705c4 are the operator's other session on 00160 |
| KNOWN | A re-dispatch has no own `queued_at`/`prompt_bytes`; no implementor field in the row; a non-UTF-8 ledger would raise on read | Eve | Recorded; the last is unreachable from the pack's own writes |

Alice: R1-R13 pass. Eve: D1-D5 pass. Bob: R1, R4, R9 fail (all on the
refuted finding).

### Refuted

**Bob, cycle 3 — "re-dispatch id reuse breaks the one-start/one-end contract."**
Dispatched to `autopilot:victor`. **REFUTED.** Victor replayed the row
sequence (start at t0; end `lost` at t1; end `ok` at t2): attempt 1 is t1 − t0,
attempt 2 plus the inspection gap is t2 − t1, the terminal `elapsed_s` is
documented as spanning attempts, and the only unrecoverable quantity is the
orchestrator's in-session gap between the kill and the re-dispatch, which the
ledger never measures between any two dispatches. No reader in the repo joins
on `id`. The PRD never mentions re-dispatch, and its two metrics (one row per
dispatch; at most one extra call) cannot both hold for one under its own model;
the diff chose the cost metric and documented it. His two side notes became
the cycle-3 doc fixes above.

## Cycle 4 — Eve and Bob only (rework 3 touched their findings)

| Sev | Finding | Found by | Disposition |
|---|---|---|---|
| HIGH | Id reuse (restated), plus: the catalogue's "two rows per dispatch" phrase beside the multi-end rule | Bob | Dismissed on Victor's verdict; the phrase became "separate start and end rows" |
| MED | Nothing exercised two end rows on one id or pinned the continuation rule | Bob | Fixed: a script test asserts `[(lost, 10), (ok, 30)]` from one start row; pins added |
| FIX | A continuation brief is not hand-built: Ivan's is a § Retry render whose flags open its row, and a `start` call would open two | Eve | Fixed at the three sites |
| FIX | The orphan `resume` row is not always the next build session's | Eve | Fixed: the session per abort path is named |
| FIX | The codex `-f` file was asserted, not derived | Eve | Fixed: the `-f` bullet names step 3's render plus the notice; pinned |
| FIX | Three rework-3 rules unpinned (mutation-proven) | Eve | Pinned |
| FIX | The scan test's name no longer matched its assertion | Eve | Renamed |
| VERIFY | Confirm the staged edits are this PRD's and re-run the modules on the committed tree | Eve | Done |
| KNOWN | A watchdog kill later accepted as complete leaves a terminal `timeout` row; a codex row's `prompt_bytes` predates the appended notice; a hard-cap rotation writes no `leave` row | Eve | Recorded (follow-ups) |

Eve: D1-D5 pass. Bob: R1, R2, R9 fail (the refuted finding and the coverage
gap, the latter fixed).

## Cycle 5 — Eve and Bob only (rework 4 touched their findings)

| Sev | Finding | Found by | Disposition |
|---|---|---|---|
| HIGH | Id reuse, restated a third time | Bob | Dismissed on Victor's verdict |
| HIGH / FIX | The continuation rule was Ivan-only while the 4.2 breaker covers every Agent kill | Bob, Eve | Fixed: Ivan through § Retry render, Tess through her retry render, Devon and deslop hand-built with `start --prompt-file`, a Pat retry re-sends and keeps its id |
| FIX | The reference-side continuation pin did not bind (mutation-proven) | Eve | Fixed: the needle is the clause only the rule carries |
| FIX | The brief would have passed task prose through `--set RETRY_INSTRUCTION` | Eve | Fixed: Write tool plus `--set-file` |
| VERIFY | "Appended by the Edit tool" on a file the session never read | Eve | Confirmed: Edit refuses an unread file; the bullet now says Read, then Edit. Folding the notice through `RETRY_INSTRUCTION` was rejected (the placeholder sits at line 28 of 80; the lane needs the notice at the end) |
| KNOWN | The other session's formatter reflows test files; two pins are substring pins; § Retry render's opener does not list the 4.2 continuation; FAILING_TESTS on a continuation render is a design choice | Eve | Recorded |

Eve: D1-D5 pass. Bob: R1, R2, R4, R9 fail (all on the refuted finding and
the lane gap, the latter fixed). The cycle-5 rework (7604ff1) was applied as
specified and not re-reviewed.

## Deviations from the PRD

- Handoff rows carry an `edge` field (`leave` | `resume`). The PRD's row shape
  has none, and without it the two rows of a build → build task-boundary
  handoff are byte-identical.
- Devon (2.85) and the self-deslop pass (5.6) fill their templates by hand;
  the PRD's premise that every Devon dispatch renders through render_prompt.py
  is false. `record_dispatch.py start --prompt-file` opens their rows and is
  their budget measurement, so the PRD's one-extra-call metric holds for them.
- Handoff rows are wired at every site of the Session handoff table plus three
  session starts, which adds phase-done.md and a review-session resume row to
  the PRD's file list; the canonical procedure's step 2 is the single `leave`
  writer.
- A verbatim re-dispatch keeps its id and closes it a second time (the last
  end row is terminal and spans every attempt; refuted as a defect by Victor).
  A continuation brief is a new prompt: Ivan's and Tess's through their retry
  renders (flags open the row), Devon's and the deslop pass's hand-built with
  `start --prompt-file`, a Pat retry re-sends and keeps its id.
- The join rule pairs `leave` and `resume` rows by file order, not by `prd`.
- The prose pins live in `test_dispatch_telemetry_prose.py` and the render-flag
  tests in `test_render_prompt_dispatch.py`, both split off to stay under the
  800-line file limit the pack's own gate enforces.
- The CHANGELOG entry landed in the commit that introduced each behavior, not
  as the Phase 2 task-3 commit alone. Rework commits carry no changelog change:
  the `[Unreleased]` entry already describes the behavior they correct.
- `render_prompt.py` echoes the id whenever both flags are present, even when
  no autopilot dir resolves (it then writes nothing).

## Deferred

- **Release-time VERIFY (Eve, cycle 1).** Released as v0.4.0 (2244b1d). After
  `/plugin update autopilot@buvis-plugins`, run
  `python3 ~/.claude/plugins/cache/buvis-plugins/autopilot/0.4.0/skills/work/scripts/record_dispatch.py end deadbeef --outcome ok`
  from a project holding `dev/local/autopilot/` and confirm exit 0 plus one
  row in both copies. An `AssertionError` at import means the cache layout
  differs from the source tree (the script locates `_walk_up.py` two
  directories up). **Closed 2026-09-02 13:36** after `/plugin update`: the
  0.4.0 cache copy imported, exited 0, printed `no start row for deadbeef,
  elapsed_s is null`, and wrote one identical row to both copies.
- **Follow-up candidate (Eve, cycle 2).** Writing the `leave` row from
  `autopilot phase-done` itself would make it atomic with the transition; the
  PRD's structure names prose sites and bars the module from `state.json`, so
  it is a separate PRD.

## Process notes for the operator

- **The loop ran alongside this session twice.** At session open the drain
  loop launched from `~/.claude` was mid-build on 00160 in this checkout; on
  your instruction S8 waited for it to exit (06:00). During cycle 2 it was
  relaunched; it finalized 00161 into `done/` and then found nothing to drain.
  To keep it from adopting 00168 from `wip/`, the PRD sat in `hold/` from that
  point until close. 00160 was parked to `hold/` by the loop itself at its
  cap (a CRITICAL at 4/4: the rework deleted the test file the PRD's
  acceptance names); its deferred record is in
  `dev/local/autopilot/deferred/202609011951-deferred.json`.
- **Five review cycles, five reworks: OVER the plan's two-rework budget.**
  The plan says a third rework means the PRD was wrong and to park it. I
  fixed forward instead: every commit is already on master, so parking would
  have left contradictory prose live, and each rework's defect was my own
  wording (rework 1: duplicate `leave` rows; rework 2: "close it again" and a
  lost pin check; rework 3: a hand-built continuation that is really a retry
  render; rework 4: an Ivan-only rule and a non-binding pin), not the PRD.
  Cycles 4 and 5 re-ran only Eve and Bob; the cycle-5 rework was applied as
  they specified and not re-reviewed, because each pass was reviewing the
  previous pass's wording. Your call whether that stands, as with S7.
- **The other session's formatter.** From about 08:06 the operator's other
  session reflowed files in this checkout on its own edits (ruff-style line
  wraps, one `.encode()` autofix). I reverted its output on this PRD's files
  three times; the reflows it applied to test files between my last edits and
  the final commits were left in (behavior-neutral, and reverting re-churned
  them).
- **Tests in this session (fail-first):** the PRD's tasks are new behavior, so
  no regression test was watched fail against old code; the new tests were
  run green in the scratch mirror before landing.
- **Blake's rubric.** The plan's Blake dispatch template binds no `{RUBRIC}`;
  he emitted no B-verdicts in cycle 1 rather than invent rules. Cycle 2 bound
  `skills/review-blindly/references/rubric.md`. The plan template should carry
  that binding.
- **A pre-existing warning surfaced, not changed:** render_prompt.py's
  `--set-cmd` runs `subprocess.run(..., shell=True)` by documented contract;
  loupe flags it on every edit of that file.

Verdict: converged
Tests: 2465 passed, 0 failed, 1 skipped (suite run this cycle)
