## Architecture fit

Everything here lands in the existing `release gate` / `hooks guard tests` /
`release prose` layers the PRD already names; nothing new is introduced.
`dev/bin/release-checks` (bash) stays the gate's single entrypoint and keeps
its `run_pytest`/`run_harness`/`run_gather_harness` count-adapter shape;
`dev/bin/release` (bash) stays the thin shim that `exec`s the shared
`claude-plugins` release script. `hooks/guard_phase_delegation.py`'s test
(`hooks/test_guard_phase_delegation.py`) stays the hook's own pinned
contract; only its allow-corpus input changes. `skills/run-autopilot/cli/gate.py`
and `skills/work/SKILL.md` get a comment and a trim respectively — no behavior
change to either's public surface.

## Module placement

New files:
- `hooks/test_guard_phase_delegation_scratch_replay.py` — the scratch-corpus
  replay, split out of `hooks/test_guard_phase_delegation.py`.
- `skills/work/references/dashboard-state-sync.md` — receives the "Dashboard
  State Sync" section moved out of `skills/work/SKILL.md` to make the
  500-line ceiling.

Existing file gaining new tests: `skills/run-autopilot/cli/test_release_checks_counts.py`
already exists (gated by the `[checks] review verbs` block); it gains
`UNGATED` and the two new pin/refusal tests — see Reuse inventory.

Edits to existing files:
- `dev/bin/release-checks` — new `[checks]` blocks for every tracked test
  file not already named (see Interfaces below), including one brand-new
  `[checks] tracon` block with `--with rich` (today the five `tracon/`
  test files, including the three needing `rich`, are named in **no**
  `[checks]` block at all — there is nothing existing to split; `rg -n
  "tracon" dev/bin/release-checks` returns zero hits, confirmed at design
  time).
- `dev/bin/release` — one guard clause before `exec "$RELEASE"`.
- `hooks/test_guard_phase_delegation.py` — `_allow_corpus()` returns the
  committed fixtures only; its scratch-glob logic moves to the new file.
- `CHANGELOG.md` — rewrite the line-28 bullet; add a `### Changed` bullet for
  the Python 3.11 floor.
- `skills/run-autopilot/SKILL.md` — line 46's CLI prerequisite names
  `python3 (>= 3.11)`.
- `skills/run-autopilot/cli/gate.py` — one `# ponytail:` comment above
  `_backed` (line 316 today).
- `skills/run-autopilot/cli/test_doc_contract.py` — unchanged (red test 1 is
  fixed by adding doc lines elsewhere, per the PRD: "fix the docs, not the
  test").
- `skills/run-autopilot/references/*.md` or `SKILL.md` — add one `autopilot
  group-rework` and one `autopilot review-stage` invocation line (red test 1).
- `skills/work/SKILL.md` — "## Dashboard State Sync" section body moves out;
  a 2-line pointer stays.
- `skills/work/references/task-boundary-handoff.md` — one wording fix (red
  test 3, below).

## Interfaces & contracts

**Red test 1 — `test_doc_contract.py`.** `_SUBCOMMANDS` includes `group-rework`
and `review-stage`; `_doc_files()` scans `skills/run-autopilot/SKILL.md` and
`skills/run-autopilot/references/*.md`. Add one line containing the literal
substring `autopilot group-rework` and one containing `autopilot review-stage`
to any file `_doc_files()` already scans — place them in
`skills/run-autopilot/references/state-schema.md`'s existing CLI-verb listing
(or wherever that file already documents a sibling verb like `autopilot
custody`), phrased as real invocations, e.g.:
```
`autopilot group-rework <state.json>` — regroup rework tasks by file (see Phase 6 rework grouping).
`autopilot review-stage <state.json> <review-file>` — stage a finished review file for the decision gate.
```
Exact wording is free; the substring match is the only constraint.

**Red test 2 — `skills/work/SKILL.md` ≤ 500 lines.** Move the "## Dashboard
State Sync" section (current lines 152-167, ending before "## Workflow") to a
new file, `skills/work/references/dashboard-state-sync.md`, verbatim body,
with its own `# Dashboard State Sync` H1. Replace it in `SKILL.md` with:
```
## Dashboard State Sync

See `references/dashboard-state-sync.md` — `statectl`'s compound task verbs
(`task-start`/`task-done`) are the only legal way to touch `state.tasks`.
```
This drops ~14 lines, landing at ≤ 500 (measure with `wc -l` at task time;
if still over, the "## Implementor Selection" section, lines 144-150, is the
next-smallest extractable block — same treatment, same target file).

**Red test 3 — `test_step_6_5_writes_the_leave_row_before_the_stop`.** The
test does `handoff.index(command) < handoff.index("then STOP")` against
`skills/work/references/task-boundary-handoff.md`. The file currently reads
(step h, end of the paragraph): `"...so only a commit that follows it sweeps
that append in. Then STOP — end the turn."` — capital-T "Then STOP" as a new
sentence; the test's literal is lowercase `"then STOP"`, which does not
occur anywhere in the file (an earlier, unrelated occurrence of lowercase
"before the stop" is not a match either). This is a wording regression, not
a wrong test: the ordering the test enforces (leave row before STOP) still
holds in the prose, only the exact casing moved. Fix the prose to preserve
that same ordering while containing the literal substring `then STOP`:
join the two sentences with a comma instead of a period —
```
...so only a commit that follows it sweeps that append in, then STOP — end the turn.
```
No other text in that paragraph changes.

**Packet 12 — `hooks/test_guard_phase_delegation.py` / scratch replay.**
Replace:
```python
def _allow_corpus() -> list[Path]:
    real = sorted(p for p in CORPUS.glob("dispatch-*.txt") if not _self_referential(p))
    return real or sorted((FIXTURES / "allowed").glob("*.txt"))
```
with:
```python
def _allow_corpus() -> list[Path]:
    return sorted((FIXTURES / "allowed").glob("*.txt"))
```
(`CORPUS`, `_self_referential` and the `docs/dev/tmp` glob move to the new
file below; drop them from this file if nothing else in it still uses them —
confirm with `rg "_self_referential|CORPUS" hooks/test_guard_phase_delegation.py`
before deleting.)

New file `hooks/test_guard_phase_delegation_scratch_replay.py`, same HOOKS/
GUARD/FIXTURES setup as the file it split from, plus the moved `CORPUS` and
`_self_referential`:
```python
def _scratch_corpus() -> list[Path]:
    return sorted(p for p in CORPUS.glob("dispatch-*.txt") if not _self_referential(p))

@pytest.mark.skipif(not _scratch_corpus(), reason="no scratch dispatch-*.txt files in docs/dev/tmp")
@pytest.mark.parametrize("prompt_file", _scratch_corpus(), ids=lambda p: p.name)
def test_scratch_dispatch_prompt_is_allowed(prompt_file: Path) -> None:
    ...  # same body as the allow-corpus parametrized test it replaces
```
Reuse whatever helper (`_tool_input`, the subprocess invocation, the
assertion) the original allow-corpus test used — this is a straight split,
no new assertion logic.

New test in `hooks/test_guard_phase_delegation.py` (or a sibling test file in
the same directory), `test_allow_corpus_ignores_scratch_dispatch_files`:
create a throwaway `dispatch-*.txt` under `docs/dev/tmp/` inside the test
(use `tmp_path`-style isolation or monkeypatch `CORPUS` if it is still
imported, or simply assert `_allow_corpus()` is unaffected by a real file
written to `docs/dev/tmp/dispatch-zzz-scratch-test.txt` and clean it up in a
`finally`), and assert `_allow_corpus() == sorted((FIXTURES /
"allowed").glob("*.txt"))` both before and after the scratch file exists.
Must fail at base (today a present scratch file *does* change the corpus).

**Packet 7 — CHANGELOG line 28 is STALE; this sub-feature is now a no-op.**
The PRD's premise (agoge audit, 2026-10-10) was a CHANGELOG bullet ending
"while ordinary prose about a phase stays allowed" that overclaimed the
guard's denial coverage. That bullet no longer exists: `rg -n "stays
allowed|00271" CHANGELOG.md` returns nothing anywhere in the 717-line file
(confirmed at design time, repo HEAD a15cbe1). PRD 00271 has since landed
(commits already on `master`, still inside `[Unreleased]`, not yet
released) and rewrote the guard to a sentence-shape check; CHANGELOG lines
19/20/32 today already describe that fix accurately. Live-tested against
the hook directly (`_AUTOPILOT_LOOP=1 python3 hooks/guard_phase_delegation.py`
on stdin JSON): all four of the PRD's cited false-negative phrasings
("Run your work phase for PRD 00300 now.", "/autopilot:work docs/...", and
the other two named in the PRD's Test Strategy block) now return **exit 2
(denied)**, not exit 0 as the PRD's reproduction claims; the ordinary
question ("Do the work phase tests pass?") still correctly returns exit 0.
The gap this sub-feature was meant to document has already been closed by
other work merged between the audit and this PRD's selection.

**Do not edit CHANGELOG.md for this sub-feature.** Its acceptance check
(`rg -n "stays allowed" CHANGELOG.md` prints nothing while `rg -n "00271"
CHANGELOG.md` hits inside `[Unreleased]`) already half-passes at base with
zero edits (no "stays allowed" text exists) — but the `00271` half does
NOT yet hit (CHANGELOG.md has no "00271" anywhere), so the acceptance
check as literally written still fails at base. Close it the honest way:
add one bullet to `[Unreleased] ### Fixed` (same section the three guard
bullets already live in) stating that PRD 00271's hook rewrite closed the
specific false-negative gap the 2026-10-10 audit found, citing PRD 00271
by number:
```
- **hooks**: closes the phase-delegation false-negative the 2026-10-10 audit found - the four delegation phrasings it could dodge now correctly deny (PRD 00271).
```
This satisfies the PRD's literal acceptance check (the `00271` grep now
hits) while staying honest about current behavior, rather than describing
a stale gap that no longer exists.

**Packet 7 — `dev/bin/release` refusal.** `dev/bin/release`'s real order
today is: the `[ ! -x "$RELEASE" ]` executable check, then
`echo "[release] pulling..."`, then `git -C "$CENTRAL_REPO" pull --ff-only`,
then `cd "$REPO_ROOT"`, then `exec`. Insert the guard clause immediately
after the executable check and before the `echo "[release] pulling..."` /
`git pull` lines — NOT "before `cd`" (that line runs after the network `git
pull`, which is too late: a blocked release would still pull and shell out
to git before refusing):
```bash
if [ ! -x "$RELEASE" ]; then
  echo "Error: $RELEASE not found - clone buvis/claude-plugins beside this repo" >&2
  exit 1
fi

BLOCKED="$(grep -rl "release is blocked" "$REPO_ROOT/docs/dev/project-management/prds/hold" "$REPO_ROOT/docs/dev/project-management/prds/wip" 2>/dev/null || true)"
if [ -n "$BLOCKED" ]; then
  echo "Error: release blocked by:" >&2
  echo "$BLOCKED" >&2
  exit 1
fi

echo "[release] pulling latest claude-plugins (shared script + marketplace)"
git -C "$CENTRAL_REPO" pull --ff-only
```
`grep -rl` lists matching filenames (one per line) across both directories in
one call; either missing directory is swallowed by `2>/dev/null || true` so a
clean checkout with an empty `hold/` does not itself error. This placement
runs before any network or git operation, so a blocked release never reaches
`git pull` or `exec`. Because of this ordering, the refusal test (below)
never reaches the `git -C "$CENTRAL_REPO" pull --ff-only` line either, so its
`claude-plugins` fixture needs no real git repo — a bare executable stub is
enough, matching what the test already does.

**Packet 11 — stated Python floor.** `skills/run-autopilot/SKILL.md:46` —
change the CLI prerequisite line so it reads `python3` (>= 3.11) (exact
existing phrasing plus the version qualifier). `CHANGELOG.md` `[Unreleased]
### Changed`:
```
- **run-autopilot**: the CLI now needs Python 3.11 or newer (it uses datetime.UTC); 3.10 is no longer supported.
```

**Packet 20 — ceiling comment.** Directly above `def _backed(...)` in
`skills/run-autopilot/cli/gate.py` (line 316 today):
```python
# ponytail: _backed is O(N^2) in reviewed rows (N(N+1)/2 comparisons); fine
# at real review sizes (dozens of rows), 26s at 50,000. Index rows by ref
# and by (severity, file, issue) if reviews ever reach the thousands.
def _backed(row: dict, reviewed: list[Row]) -> bool:
```

**Gate-every-test pin.** `skills/run-autopilot/cli/test_release_checks_counts.py`
already has the right idiom for this (`test_every_review_verb_test_file_is_listed`,
line 231: `unrun = [path for path in entries if path not in text]` against
`_RELEASE_CHECKS.read_text()`) — reuse it rather than writing a new parser.
Add:
```python
UNGATED = (
    "hooks/test_guard_phase_delegation_scratch_replay.py",  # reads gitignored scratch input (docs/dev/tmp/dispatch-*.txt); not reproducible in a clean clone
)

def _tracked_test_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "*test_*.py"], cwd=_ROOT, capture_output=True, text=True, check=True,
    )
    return out.stdout.splitlines()

def test_every_tracked_test_file_is_gated() -> None:
    text = _RELEASE_CHECKS.read_text()
    missing = [
        path for path in _tracked_test_files()
        if path not in text and path not in UNGATED
    ]
    assert missing == [], f"{_RELEASE_CHECKS}: does not name {missing} (add a [checks] block or UNGATED with a reason)"
```
Membership is a plain substring test (`path not in text`) against the whole
script body, exactly like the existing `unrun` check above it — it does not
need to know which `[checks]` block a path lives in, only that the literal
path string appears somewhere in the file. This stays a pure read of
`dev/bin/release-checks`; it never rewrites the script's block shape
(Constraint: no loop over `git ls-files` replaces the literal lists *inside
the script* — this test lives beside the script, not inside it).

Second test in the same file, `test_release_refuses_while_a_held_prd_blocks_it`:
`dev/bin/release` derives `REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"` —
purely from `$0`'s own location, not an environment variable, so **only one**
of the fixture strategies works: copy `dev/bin/release` into a fixture tree
at `<tmp_path>/dev/bin/release`, alongside a stub executable at
`<tmp_path>/../claude-plugins/scripts/release-plugin` (sibling of the
fixture's own root, matching `CENTRAL_REPO="$REPO_ROOT/../claude-plugins"`)
that would `touch` a sentinel file if invoked, and a blocking PRD at
`<tmp_path>/docs/dev/project-management/prds/hold/0001-x.md` containing the
phrase `release is blocked`. Run the copied script directly (no `cd`, no env
override — `$0` resolves from the invocation path alone). Assert exit code
1, assert the sentinel was never touched, and assert the stderr names the
PRD file path. Add a second case covering `prds/wip/` (not just `hold/`),
since the guard scans both.

**`[checks]` block additions.** Add new blocks (new `echo "[checks] <name>"`
+ `run_pytest`/`run_harness` call) for every tracked `test_*.py` the current
script does not already name, grouped by directory/theme consistent with the
existing blocks' style (do not invent one giant catch-all block — mirror the
granularity already in the file, e.g. one block per skill directory cluster
that doesn't have one yet). Enumerate the gap set at task time with:
```
comm -23 <(git ls-files '*test_*.py' | sort) <(grep -oE '[A-Za-z0-9_./-]+test_[A-Za-z0-9_.]*\.py' dev/bin/release-checks | sort -u)
```
and add one block per natural cluster from that output, minus the one
`UNGATED` entry. The three tracon-dependent test files (named in the PRD's
Test Strategy packet 6 reproduction as the 3 `errors`; on disk today they
are `skills/run-autopilot/scripts/tracon/test_panels.py`,
`test_screens.py` and `test_stream.py` — the dashboard package renamed
itself to `l` internally but still lives under the `tracon/` directory) are
currently named in **no** `[checks]` block at all. Add them as their own new
block, `[checks] tracon`, with `--with rich` on the `uv run` invocation:
```
echo "[checks] tracon"
run_pytest uv run --no-project --with pytest --with rich python -m pytest -q \
  skills/run-autopilot/scripts/tracon/test_panels.py \
  skills/run-autopilot/scripts/tracon/test_screens.py \
  skills/run-autopilot/scripts/tracon/test_stream.py \
  skills/run-autopilot/scripts/tracon/test_discovery.py \
  skills/run-autopilot/scripts/tracon/test_model.py
```
(`test_discovery.py`/`test_model.py` are the same directory's other test
files, also currently ungated — confirm with the `comm` command above which
of the five are actually missing before finalizing the block; don't add a
file that's already named elsewhere.)

## Data flow

No runtime data flow changes — every edit here is either test-collection
surface (which files `release-checks` runs), gate-time prose (CHANGELOG,
SKILL.md), or a pre-exec guard in a release shim that reads PRD files from
disk once. `_allow_corpus()`'s only consumer is its own
`@pytest.mark.parametrize`, evaluated at collection time; narrowing its
return value changes which fixtures the existing parametrized test runs, not
any production code path.

## Reuse inventory

- `dev/bin/release-checks`'s `run_pytest`/`run_harness`/`run_gather_harness`
  count-adapter helpers (lines 37-103) are reused as-is for every new
  `[checks]` block — no new adapter needed.
- The `hold/wip` PRD-scan pattern for "release is blocked" reuses the same
  two lifecycle directories `enforce_prd_location.py` and the build gate
  already treat as canonical (`docs/dev/project-management/prds/{hold,wip}/`)
  — no new directory convention introduced.
- `test_release_checks_counts.py` already exists (named in the current
  `[checks] review verbs` block) and already tests other `release-checks`/
  `release` behavior; the PRD's two new tests land in that same file rather
  than a new one. (Design doc's Module placement list above is corrected
  here: no new file for this piece — `test_release_checks_counts.py` is an
  edit, not a new file. The Structural Decomposition section in the PRD
  itself says "NEW assertions", not "NEW file".)
- Greps tried for an existing "list every tracked test file" helper:
  `rg -n "git ls-files" skills/ hooks/ dev/` (nothing — no existing helper
  parses `git ls-files` against `release-checks`), `rg -n "UNGATED"` (nothing
  — no prior art for this exclusion-list idiom in this repo). Both confirm
  this is new, not a reinvention.

## Alternatives considered

1. **Chosen: one `UNGATED` tuple/set in a new assertion inside the existing
   `test_release_checks_counts.py`, scanning `dev/bin/release-checks` as
   text.** Smallest diff that satisfies the PRD's literal Success Metric
   ("a test fails when a tracked test file is left out") without touching
   the script's structure, which the Constraint section forbids touching.
2. **Smallest-diff alternative: no pin test at all, just add the missing
   `[checks]` blocks.** Rejected — it fixes today's gap but not the PRD's
   stated goal of catching the *next* file someone forgets to gate; the
   pin is the whole point of packet 6's "Cost" and "Risk: the pin is a
   standing obligation" language.
3. **Larger alternative: rewrite `release-checks` to loop over `git ls-files
   '*test_*.py'` directly instead of literal lists.** Rejected by the PRD's
   own Constraint — six prose tests parse the script's exact `[checks]`
   lines and literal command lists; replacing them with a loop breaks all
   six and is explicitly disallowed ("no loop over `git ls-files` replaces
   the literal lists").

## Risks & edge cases

- **The release-block scan fails open on a read error.** `2>/dev/null ||
  true` swallows a permission or I/O error on an existing-but-unreadable
  `hold/`/`wip/` the same way it swallows a missing directory, so a release
  could proceed past an unreadable blocking PRD with no diagnostic. Accepted
  for this PRD's scope (missing-directory tolerance is the stated goal); a
  future hardening could `stat` each directory first and refuse loudly on a
  real I/O error while still tolerating ENOENT.
- **The gate-every-test pin checks mentions, not execution.** `path not in
  text` passes if a tracked path appears anywhere in the script text,
  including inside a comment or a disabled line — it does not confirm the
  path is actually inside a live `run_pytest`/`run_harness` call. Accepted:
  this matches the existing `test_every_review_verb_test_file_is_listed`
  idiom's own tradeoff (same substring check), and tightening it to parse
  active commands only is out of scope for this PRD.
- **Gate wall time** grows by ~2,300 tests' worth of runtime (the PRD's own
  estimate); measure and report the delta, don't guess it in the task report.
- **The `UNGATED` tuple drifts** the moment a new ungated test file is added
  without a reason — by design, this is supposed to fail loud, not silently
  pass; future PRDs that add `test_*.py` files must update either a
  `[checks]` block or `UNGATED`.
- **`grep -rl "release is blocked"` is a text match**, not a structured flag
  — a PRD quoting the phrase in an unrelated context (e.g. "see PRD 00271:
  'the next release is blocked on this PRD'" inside a *different* PRD that
  isn't actually blocking) would also trip the refusal. The PRD accepts this
  crudeness explicitly (Risks: "Text-match release block is crude").
- **This PRD's own file is a live instance of that false-positive**: PRD
  00278 itself (this document's PRD) contains the literal phrase "release is
  blocked" multiple times while describing the feature, and sits in `wip/`
  for the duration of its own implementation. A real `dev/bin/release` run
  during that window would refuse, citing itself, with no actual intent to
  block. This is not a defect in the guard clause (its unit/integration test
  uses an isolated fixture tree, not the live repo, so the pinned test is
  unaffected) — it is an operational fact to carry into Phase 9: do not run
  `dev/bin/release` for real while this PRD is still open in `wip/`/`hold/`.
  By the time a release is normally cut (batch end, `wip/`/`backlog/`
  drained), this PRD has already moved to `done/` and stops matching.
- **Likely next changes**: (1) a future PRD may want the release block to be
  structured (frontmatter flag) rather than text-matched — this design's
  `grep` approach does not block that migration, since it only touches
  `dev/bin/release`; (2) a future PRD may want `UNGATED` reasons surfaced in
  the batch report — the tuple's shape (file → one-line reason) already
  supports that without a redesign; (3) the next test file added anywhere in
  the repo must be gated or excluded — this design's pin is what will catch
  that, by construction.
- Nothing here boxes in those three; the `UNGATED` shape and the `grep`-based
  refusal are both the smallest options that still leave room to grow.

## Test strategy outline

- Red test 1 (`test_doc_contract.py`) → green via the two added doc-invocation
  lines; verify with the exact `uv run` command the PRD names.
- Red test 2 (`test_work_skill_body_stays_under_the_500_line_ceiling`) → green
  via the Dashboard State Sync extraction; verify with `wc -l skills/work/SKILL.md`
  and the pinned test.
- Red test 3 (`test_step_6_5_writes_the_leave_row_before_the_stop`) → green via
  the comma-join wording fix; verify with the pinned test, not a hand run.
- `test_allow_corpus_ignores_scratch_dispatch_files` (new) → fails at base
  (today a scratch file changes the corpus), passes after the `_allow_corpus`
  narrowing.
- `test_every_tracked_test_file_is_gated` (new) → fails at base (today's gap:
  ~130 files per the PRD's own count), passes after the new `[checks]` blocks
  land, with `UNGATED` holding exactly the one scratch-replay entry.
- `test_release_refuses_while_a_held_prd_blocks_it` (new) → fails at base (no
  refusal exists today), passes after the `dev/bin/release` guard clause lands.
- Packet 7 CHANGELOG line 28 → no test (docs-only); verify with `rg -n
  "00271" CHANGELOG.md` hitting inside `[Unreleased]` after the one new
  bullet is added — this fails at base (zero `00271` hits anywhere in the
  file today).
- The six `[checks]`-parsing prose tests named in the PRD's Constraint
  (`test_release_checks_parallel_prose.py`, `test_wave_docs.py`,
  `test_triage_prose.py`, `test_enter_prose.py`, `test_design_rework_prose.py`,
  `test_custody_prose.py`) must still pass unchanged after the new blocks are
  added — run them explicitly after editing `dev/bin/release-checks`, before
  calling that task done.
- Final exit criterion: `bash dev/bin/release-checks` exits 0 with `FAIL 0` on
  its summary line; report the new wall time against the pre-change baseline.

## Review log

Dispatch 1 (claude) non-blocker/question findings (cardinal-sin/blocker fixed above):

- non-blocker: `test_every_tracked_test_file_is_gated`'s substring match
  (`path not in text`) could false-pass if a tracked path happens to be a
  substring of another listed command fragment. Accepted — matches the
  existing `test_every_review_verb_test_file_is_listed` idiom's own
  tradeoff; not introduced by this design.
- non-blocker: gate wall-time growth (~2,300 tests) is estimated, not
  capped; out of this PRD's scope per its own Cost/Risk language — flag for
  a follow-up PRD if cycle time becomes a problem.
- non-blocker: the "likely next changes" framing (structured release-block
  flag, `UNGATED` reasons in the batch report) is asserted, not sketched;
  cosmetic, no action needed.
- question: does "every tracked `test_*.py`" include files outside
  `skills/`/`hooks/` (e.g. under `dev/`)? Already answered by the design's
  own instruction to enumerate the gap set at task time with `git ls-files`
  before finalizing blocks — no redesign needed.

dispatch 1 (claude): cardinal-sin 0, blocker 2, non-blocker 3, question 1

Dispatch 2 (codex) findings, all non-blocker (fixed where load-bearing,
accepted and recorded in Risks & edge cases otherwise):

- non-blocker: gate-every-test pin checks mentions, not execution
  (`path not in text` can match a comment/disabled line) — recorded in
  Risks & edge cases, accepted (matches the existing idiom's tradeoff).
- non-blocker: the refusal-test fixture needs a `git` consideration too —
  superseded by the ordering fix (guard now runs before `git pull`, so the
  fixture never reaches `git` either way) and by the fixture-design fix
  below from the redundant dispatch-2 pass.
- non-blocker: the CHANGELOG replacement bullet's own wording risked
  conflating a denied question with the real delegation phrasings — moot,
  since the whole packet-7 CHANGELOG sub-feature was replaced (see next
  entry) rather than patched.
- non-blocker: the release guard's `2>/dev/null || true` silently
  swallows real scan errors, not just missing directories — recorded in
  Risks & edge cases, accepted (missing-directory tolerance is this PRD's
  stated goal; hardening against I/O errors is out of scope).

dispatch 2 (codex): cardinal-sin 0, blocker 0, non-blocker 4, question 0

A redundant same-dispatch-2 Claude pass (codex's first invocation looked
truncated before its background command fully finished; it had in fact
completed, but the redundant pass ran before that was confirmed) found two
additional real blockers codex's narrower pass missed, both now fixed above:

- blocker (fixed): packet 7's CHANGELOG premise was stale — PRD 00271 had
  already landed and closed the exact false-negative gap, so the literal
  "replace the bullet" instruction had no bullet to replace. Fixed: the
  design now adds one new bullet citing PRD 00271 instead of rewriting a
  nonexistent one, and the Interfaces section records the live hook test
  that proved the four phrasings now deny.
- blocker (fixed): Module placement's tracon-block description
  self-contradicted the later, correct Interfaces passage (claimed an
  existing tracon block to split; none exists — confirmed via `rg -n
  "tracon" dev/bin/release-checks`, zero hits). Fixed: Module placement now
  matches the Interfaces section's "no block exists, add one" framing.
- question (resolved): the refusal-test fixture design listed three
  strategies for landing inside `REPO_ROOT`; only copying the script into a
  fixture tree works, since `REPO_ROOT` is derived purely from `$0`'s
  location, not an env var. Fixed: Interfaces now states this directly and
  drops the non-working alternatives.
- non-blocker (confirmed, no change): scratch-replay split, `dev/bin/release`
  guard placement, Dashboard State Sync line math, and the `gate.py`/SKILL.md
  line numbers were independently re-verified against the live files and
  match the design exactly.

dispatch 2 (claude, redundant verification pass): cardinal-sin 0, blocker 2,
non-blocker 4, question 1
