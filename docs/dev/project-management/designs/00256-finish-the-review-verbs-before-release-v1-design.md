# Finish the review verbs before release — design

## Architecture fit

All five fixes land in the existing `skills/run-autopilot/cli/` verb layer
(`review_close.py`, `review_stage.py`, `verification.py`, `gate.py`,
`triage.py`) plus the `skills/review-work-completion` and
`skills/run-autopilot` prose that documents them, and `dev/bin/release-checks`.
No new module, no new layer: every capability is a targeted correction of an
existing function or a sync between code that already does the right thing
and prose/fixtures that don't yet describe it.

Two of the five capabilities (`review-stage inputs`, `review-close
correctness`'s "Close every lens") turn out, on inspection, to be prose/fixture
bugs rather than code bugs: `review_close.close()` already derives lens status
generically from whatever the `agents:` frontmatter lists (`_PERSONA_LENS`
covers all five personas), and `review-stage`'s CLI already accepts
`--settled-ledger`/`--prior-findings` and threads them through `stage()`. The
gap is that `output-formats.md`'s example `agents:` block only shows
`alice/bob/carl`, and `SKILL.md` step 3 tells the model to hand-append ledger
context instead of passing the flags the code already supports. These are
doc/fixture fixes, not new code — smallest-diff design option, taken.

## Module placement

Edits to existing files only, no new files except one new test file this PRD
doesn't need (all target test files already exist — `test_triage.py`,
`test_verification.py`, `test_review_close.py`, `test_review_stage.py`,
`test_gate.py` — confirm each exists before adding; if a target test file is
missing, create it next to its sibling CLI module, matching existing fixture
conventions in that directory, no separate design step required since the
interfaces below are exact).

- `skills/run-autopilot/cli/review_close.py` — change one dict value (line 48 area).
- `skills/run-autopilot/cli/review_stage.py` — change one call site (`_eve_inputs`), delete one function (`resolve_base`) and its one call site, remove one conditional gate (`run["doubt"]`).
- `skills/run-autopilot/cli/verification.py` — rewrite `run_gate()` to stream and stay under 50 lines; fix `_ancestor_and_clean()`'s porcelain parsing for renames.
- `skills/run-autopilot/cli/gate.py` — add a `--findings` argument and a new cross-check function.
- `skills/run-autopilot/cli/triage.py` — widen the `SEVERE` frozenset.
- `dev/bin/release-checks` — replace the fabricated summary line with one driven by the real pytest/harness run already in the script (see Data flow).
- `skills/review-work-completion/SKILL.md` — edit lines 216-218 and 248, and the step-3 `review-stage` invocation synopsis.
- `skills/review-work-completion/references/output-formats.md` — extend the `agents:` example to all five personas; add a `dispatch_rows:` block to the format.
- `skills/run-autopilot/references/phase-review.md` — edit the cap-overflow `severity` instruction (near line 59) to say "word".

## Interfaces & contracts

### `review_close.py` — `_DISPATCH_OUTCOME`

```python
_DISPATCH_OUTCOME = {"available": "ok", "unavailable": "error", "timeout": "timeout"}
```

Only the `"unavailable"` value changes, `"failed"` → `"error"`. `"error"` is a
valid member of `record_dispatch.OUTCOMES = ("ok", "timeout", "killed",
"error", "lost")` (`skills/work/scripts/record_dispatch.py:28`); `"failed"`
was not, so this also fixes a latent subprocess-argparse failure, not just a
semantic label.

Test: `test_every_dispatch_outcome_is_recordable` asserts every value in
`_DISPATCH_OUTCOME` is a member of `record_dispatch.OUTCOMES`.

### `review_close.py` — close every lens (fixture-only fix)

No code change. Add a fixture review file under the test file's existing
fixture convention whose `agents:` frontmatter lists all five personas
(`alice, blake, bob, carl, eve`), each `available` or `disabled`. After
`close()` runs on it, `state.review_lenses` (as `_lens_states()` derives it
via `_PERSONA_LENS`) must contain no value still `"running"`.

```python
_PERSONA_LENS = {
    "alice": "consensus", "blake": "blind", "bob": "doubt",
    "carl": "ui", "eve": "fable",
}  # unchanged — already correct
```

Test: `test_close_leaves_no_lens_running` builds this five-persona fixture,
runs `close()`, asserts no lens in the resulting `review_lenses` state is
`"running"`.

### `review_stage.py` — Eve gets the raw PRD body

```python
def _eve_inputs(run: dict) -> str:
    """agent-invocation.md's five Eve run inputs."""
    context = _read(run["context"])
    scope = _SCOPE_RE.search(context)
    diff_range = f"{scope.group(1)}..HEAD" if scope else NO_RANGE
    changed = "\n".join(run["changed"]) or NO_DIFF
    return "\n\n".join(
        [
            f"## PRD\n{run['prd_body']}",   # was run['prd']
            f"## Diff range\n{diff_range}",
            f"## Changed files\n{changed}",
            f"## Findings precedent\n{run['findings']}",
            f"## Mechanical test checks\n{_mech_checks(context)}",
        ],
    )
```

One-line change: `run['prd']` → `run['prd_body']`. `run["prd_body"]` already
exists in `_run_inputs()`'s returned dict (built via `_prd_body()`), unchanged.

Test: `test_eve_gets_raw_prd_only` asserts `_eve_inputs` output's `## PRD`
section equals `run["prd_body"]` verbatim, and does not contain any text unique
to the merged `run["prd"]` (e.g. a `## Design Doc` marker only the merged text
carries).

### `review_stage.py` — Bob's doubt appendix is unconditional

```python
    if name == "bob":
        eve = _read(AGENTS_DIR / "eve.md")
        appendix = [_section(eve, title) for title in EVE_DOUBT_SECTIONS]
        source = "\n\n".join([source.rstrip(), *appendix])
        values["PACK_FINDINGS"] = run["findings"]
        source = f"{source.rstrip()}\n\n{CITATION_LINE}\n"
```

Delete the `if run["doubt"]:` gate around the appendix block; the four lines
that were inside it (building and appending the Eve doubt sections, setting
`PACK_FINDINGS`) now run unconditionally for Bob, every cycle. The
`run["doubt"]` key itself (`"eve" not in roster"`) becomes dead in this
function; leave it in `_run_inputs()`'s returned dict only if another caller
reads it — grep confirms `_plan()`'s Bob branch is the sole reader, so delete
the `"doubt"` key from the dict literal in `_run_inputs()` too (orphaned by
this change).

Test: `test_bob_keeps_doubt_appendix_when_eve_rostered` builds a roster that
includes `"eve"`, renders Bob's prompt, asserts the appendix's D1-D5 rubric
headers (`EVE_DOUBT_SECTIONS` titles) are present.

### `review_stage.py` — one diff-base resolver

Delete `resolve_base()` (current lines ~206-224) entirely. Its sole caller,
`stage()` (current line ~805: `base = resolve_base(repo_root, since)`),
instead reads the base already resolved and recorded by `gather-context.sh` in
the context file's `_Diff scope: ... (changes since|vs <SHA>)_` line, using
the existing `_SCOPE_RE` regex (already defined, already used by
`_eve_inputs`):

```python
    context_text = _read(context_file)   # the context file stage() already has in hand
    scope = _SCOPE_RE.search(context_text)
    base = scope.group(1) if scope else None
```

`base` keeps the same downstream contract (feeds `_append_mech_blocks()` →
`replay_tests_against_base.py --base <base>`, `None` meaning "no replay"), so
no other signature changes. The `since` parameter to `stage()` is unused by
this resolution now; keep it in the signature only if another caller still
passes it meaningfully — if `since` has no other reader after this change,
drop the parameter and update `stage()`'s one call site in `cli/__main__.py`
(the `review-stage` subcommand handler) to stop passing `--since`'s value
through. (Confirm at implementation time; this design does not require
removing `--since` from the CLI flag itself, only the now-redundant internal
resolver.)

Test: `test_replay_uses_gather_context_base` builds a context file with a
known `_Diff scope: ... (changes since deadbeef)_` line, calls `stage()`,
asserts the replay base used is `deadbeef` and that `resolve_base` no longer
exists as a symbol in the module (`hasattr(review_stage, "resolve_base") is
False`, or an `ImportError`/`AttributeError` guard — whichever the test
harness's existing convention for "symbol removed" assertions uses elsewhere
in this test file).

### `gate.py` — findings JSON cross-check

```python
parser.add_argument("--findings", type=Path, default=None)
```

Added to `gate.py`'s own `main()` parser AND to `cli/__main__.py`'s separate
`gate` subparser (`__main__.py:781-795` defines its own argument list, which
is what `autopilot gate --review-file` actually dispatches through — adding
`--findings` only to `gate.py`'s internal `main()` leaves the CLI entry point
blind to it). Both need the flag; `__main__.py`'s handler threads it to
`gate.run_gate()`/`check()` exactly like `--review-file` already is.

**Wiring into `review_close.close()`.** The design doc's first draft added
`--findings` only to the standalone `autopilot gate` verb — which never runs
inside `review_close.close()`'s own path. `close()` (`review_close.py:146-
162`) calls `gate.run_gate()` without `--findings` and separately applies
`chosen_findings` to state; a findings/table mismatch there currently has no
check at all, so divergent JSON can still mutate state through `close()`,
independent of whatever `autopilot gate --findings` catches standalone. Fix:
`close()` passes its own `chosen_findings` payload (already in hand — it is
what it is about to apply) through the SAME cross-check function before
applying it to state, and refuses on a mismatch (see "Surfacing the refusal"
below for how that refusal reaches the CLI's exit code). This makes the
cross-check function a plain Python function callable from both `gate.main()`
(CLI path) and `close()` (in-process path), not a subprocess-only check —
write it as `_cross_check_findings(review_text: str, findings: list[dict]) ->
str | None` taking already-loaded data, not file paths, so both callers can
hand it whatever they already have in memory (`close()` has `chosen_findings`
as Python objects already; `gate.main()` loads the `--findings` JSON file
itself before calling it).

**Subset, not bidirectional equality.** `chosen_findings` is deliberately a
**selected batch**, not the full consolidated table: `phase-review.md`'s
Tail-sweep selects only the swept subset, and `[C{cycle}]` requeues / resolved
PAUSE rows are excluded from what a given `close()` call applies. Requiring
every table row to also appear in `chosen_findings` ("and vice versa",
the first draft's wording) would reject every ordinary partial batch. Fix:
`_cross_check_findings` validates **one direction only** — every row in
`findings` must match some row in the review's consolidated table (a chosen
finding must be real, not invented); it does NOT require the reverse (the
table may legitimately contain rows `close()` isn't applying this call).
Completeness of *coverage* (did this batch skip something it shouldn't have)
is a different, already-separately-enforced concern (classification/routing,
not this cross-check) and is out of scope here.

**Surfacing the refusal through the CLI.** `close()` itself returns a dict,
not a process exit code (confirmed live), and `cli/__main__.py`'s
`_run_review_close()` currently maps every "not applied" result to exit 1 —
there is no existing path to a distinct exit 2 from `close()`. Fix:
`close()`'s returned dict gains a `refused: "findings_mismatch"` (or similar)
key when the cross-check fails, distinct from its other not-applied reasons;
`_run_review_close()` checks that key and returns exit 2 specifically for it,
exit 1 for every other not-applied case (unchanged). This is a small,
additive change to the dict shape and to one `if` in `_run_review_close()`,
not a new return type.

**Malformed vs. mismatched.** `_cross_check_findings` distinguishes "the
review file's `## Consolidated Findings` section is missing or unparsable"
(a shape problem) from "the section parsed fine but disagrees with
`findings`" (the mismatch this feature targets) from "the section parsed
fine and is a legitimate empty set" (zero findings is a valid state, not an
error). It returns a tagged result, not a bare `str | None`:
`("ok", None) | ("mismatch", <first mismatched row text>) | ("malformed",
<reason>)`. `gate.check()` keeps its existing exit-1 convention for
`"malformed"` (folded into its existing malformed-input checks, not a new
exit code), exits 2 only for `"mismatch"`, and exits 0 for `"ok"` — including
the legitimate-empty-set case, which must not be confused with "malformed."

Test: `test_review_close_refuses_on_findings_mismatch` — `close()` given a
`chosen_findings` payload that disagrees with the review file's consolidated
table does not mutate state and its returned dict carries
`refused: "findings_mismatch"`; the CLI handler maps that to exit 2.
`test_cli_exit_2_on_findings_mismatch` — drives `_run_review_close()` itself
(not just `close()`) and asserts the process exit code is 2.
`test_partial_batch_is_not_a_mismatch` — `findings` holding a real subset of
the table's rows (a Tail-sweep selection) passes the cross-check even though
the table has additional rows `findings` doesn't mention.
`test_malformed_findings_section_exits_1_not_2` — a review file with no
`## Consolidated Findings` section at all exits via `check()`'s existing
exit-1 path, not exit 2. `test_empty_findings_is_not_malformed` — a
well-formed, empty consolidated table with an empty `findings` list exits 0.

**Row comparison and normalization.** Compares row sets by the tuple
`(severity, file_key, issue_text)`, where each field is normalized by a new
`_normalize_finding_row()` shared by both `gate.py` and `close()`:

- `severity`: the table's cell may be an emoji alone (`🟠`), a word alone
  (`high`), or combined (`🟠 High`, confirmed live in
  `output-formats.md:90-94`'s own example). Normalize to the **word only**:
  strip any leading emoji character(s) and surrounding whitespace, then
  lowercase what remains; a cell of emoji-only (no trailing word) maps through
  a fixed `{"🔴": "critical", "🟠": "high", "🟡": "medium", "⚪": "low"}` table
  before lowercasing — `⚪`, not `🟢`: confirmed live, `output-formats.md`'s
  own "Agent Output Format" example uses `⚪ Low`, and `review_close.py`'s
  `_DECISION_SEVERITY` / `cli/__main__.py`'s `_KNOWN_SEVERITIES` both use `⚪`
  for low; the earlier draft's `🟢` was never the actual symbol anywhere in
  this codebase and would have silently failed to normalize any real Low row. The findings JSON's own `severity` field
  (confirmed single-emoji-or-word by the `consolidate_findings.py` dataclass
  inspected during review) normalizes through the same function.
- `file_key`: `check()` itself has **no existing row/table parsing to reuse**
  — confirmed live (`gate.py:105-132`): it checks for section headers,
  the verdict line, and the tests line as fixed strings, never parses a
  findings table. `_cross_check_findings` is new parsing, not reused parsing;
  extract the file path as the text between the `|` delimiters in the
  **table row** shape (see below) or after `| {file} |` in the **bullet-list**
  shape, then normalize to its repo-relative string as-written (no path
  resolution beyond stripping surrounding whitespace).

**Which `## Consolidated Findings` shape to parse.**
`output-formats.md` documents two different shapes under that same heading:
a bare pipe table ("Consolidated Findings Table", lines 88-94,
`| Consensus | Severity | Issue | File | Found By |`) and a bullet list
nested under consensus-tier subheadings (inside "Review Summary Format",
lines 137-146, `- [M/N] 🟠 {issue} | {file} | Found by: {agents}`). The
**saved review file** — the artifact `gate --review-file` actually reads —
follows the Review Summary Format template, so `_cross_check_findings`
parses the **bullet-list shape** (lines 137-146's pattern: one `- [tier] 
{severity emoji} {issue} | {file} | Found by: {agents}` line per finding,
grouped under `### Full Consensus (N/N)` / `### Majority Consensus (>50%)` /
`### Minority (<=50%)` subheadings). The standalone pipe table (lines 88-94)
is a different, earlier-stage artifact (the Consolidation Rules' intermediate
table, not the saved file's own findings section) and is out of scope for
this parser.
- `issue_text`: `" ".join(issue_text.split())` to collapse whitespace.

`check()`'s existing malformed-input exit code is **1** (confirmed: a missing
section/verdict/tests line exits 1, not 2, in the live code). This
cross-check's three-way tagged result (see "Malformed vs. mismatched" above)
keeps that distinction: `"malformed"` routes through `check()`'s existing
exit-1 path; `"mismatch"` alone exits 2, naming the first mismatched row.

```python
def _cross_check_findings(
    review_text: str, findings: list[dict],
) -> tuple[str, str | None]:
    """("ok", None) when every findings row matches a consolidated-table row
    after normalization (one-directional: findings subset-of table, not
    bidirectional equality — see "Subset, not bidirectional equality").
    ("mismatch", <row text>) for the first findings row with no table match.
    ("malformed", <reason>) when the table section itself can't be located or
    parsed. An empty findings list against a well-formed, possibly-empty
    table is ("ok", None), never "malformed"."""
```

Tests: `test_gate_refuses_findings_json_mismatch` (one row in the JSON with
no matching table row → exit 2 naming that row).
`test_gate_accepts_matching_findings_json` (every JSON row matches a table
row, using the documented combined `🟠 High` cell shape → exit 0, same as no
`--findings` given). `test_cross_check_normalizes_combined_severity_cell` (a
table row written `🟠 High` and a findings-JSON row written `high` compare
equal). Plus the subset/malformed/empty tests listed under "Surfacing the
refusal through the CLI" above.

### `verification.py` — real test counts

`run_gate()` stops trusting a single self-reported summary line from the gate
command as the sole source of truth when that command is `release-checks`
itself fabricating the line (see `dev/bin/release-checks` below) — the fix is
two-sided:

1. `dev/bin/release-checks` runs more than pytest: confirmed live, it also
   runs `test_codex_run.sh` (emits its own measured pass/fail summary) AND
   two further shell harnesses, `test_gather_context_paths.sh` and
   `test_gather_context_id.sh`, which print individual `PASS:` lines per case
   and fail fast with **no aggregate summary of their own** — a strictly
   different shape from `test_codex_run.sh`'s. A single "parse pytest's
   summary, or reuse the harness's own summary" rule (the prior draft) has no
   answer for these two. Fix: give each block an explicit **count adapter**
   rather than assuming a uniform shape:
   - pytest blocks: parse that invocation's own `-q` final summary line.
   - `test_codex_run.sh`: reuse its existing measured summary as-is.
   - `test_gather_context_paths.sh` / `test_gather_context_id.sh`: count
     their own `PASS:` lines as passed-case totals (one line = one case);
     their fail-fast exit (no summary at all on failure) is treated as an
     **unknown remainder** — the cases that never printed a `PASS:` line
     before the script aborted are not counted as failed (nothing measured
     them), only as part of the infrastructure-failure signal below.
   The script accumulates each adapter's counts into running totals
   (`total_passed += `, etc.), restructured so a failing block is
   **recorded, not fatal** — it currently `set -e`-exits before the summary
   line on any failure, which is why FAIL is hardcoded to 0 today; each
   block's exit status feeds the running `FAIL` count without aborting the
   script. **Two distinct failure shapes, two distinct responses:** a block
   that ran to completion and reported a nonzero failed count contributes
   that real number to `total_failed`. A block that could not report at all
   (a harness that aborted before any count — e.g. one of the two
   gather-context scripts dying mid-run) contributes nothing to any numeric
   total (never an invented number) and instead forces the script's own
   `EXIT` code non-zero directly, independent of the printed counts — so an
   infrastructure failure can never present as "FAIL 0" (today's bug) nor as
   a fabricated failed-test count it never measured. `verification.
   SUMMARY_RE` requires all three counts to be numeric (`\d+`), so this
   script-level distinction — numeric totals vs. a forced nonzero `EXIT` —
   is exactly how an unmeasurable remainder gets represented without
   breaking that regex: the printed line's three counts are always the
   real numbers measured so far, and `EXIT` alone carries the "something
   went unmeasured" signal. At the end, print
   `PASS <total_passed> FAIL <total_failed> SKIP <total_skipped> EXIT <code>`
   (`verification.SUMMARY_RE`'s shape, unchanged), where `<code>` is 0 only
   when every block completed AND reported zero failures — replacing the
   current `grep -c '^echo "\[checks\]' "$0"` fabrication.
2. `run_gate()` itself keeps its CURRENT persistence contract unchanged: no
   write at all when `SUMMARY_RE` never matches (preserves the pre-existing
   `test_run_gate_unparseable_output_records_nothing`, which asserts the
   record file does not exist — confirmed at `test_verification.py:190`; an
   earlier draft of this design claimed `run_gate()` should write explicit
   `null` counts on no match, which directly contradicts that existing,
   unchanged test and is dropped). "An unparseable block yields null, never a
   guess" (PRD Risks) is about a *partial* match: if `SUMMARY_RE` matches but
   one of its three capture groups is present with a non-numeric or missing
   value (not expected given the regex's `\d+` groups, but guard it anyway),
   write `null` for that one field rather than coercing a guess — the
   all-or-nothing "no match at all → no write" behavior is untouched.

Test: `test_summary_counts_tests_not_check_blocks` — run `release-checks` (or
a test double with the same structure) and assert the printed summary line's
`PASS`/`FAIL` numbers equal the real pytest total across every block
combined, not the script's own `echo "[checks]"` line count.
`test_summary_line_printed_on_failure` — inject a failing check, assert the
summary line still prints with `FAIL` > 0. New:
`test_infrastructure_failure_is_not_counted_as_a_test_failure` — simulate one
of `test_gather_context_paths.sh`/`test_gather_context_id.sh` aborting before
printing any `PASS:` line; the script's own exit code goes non-zero without
inflating `FAIL` by a number it never measured.
`test_gather_context_harness_counts_pass_lines` — a normal run of either
gather-context script contributes one passed count per `PASS:` line printed.

### `verification.py` — bounded, streaming `run_gate`

Rewrite `run_gate()` (currently 75 lines, buffering the full
`proc.communicate(timeout=timeout)` output via separate stdout/stderr pipes)
to cap memory and keep a real timeout. The naive "iterate `proc.stdout` line
by line" approach is rejected outright: a child that writes arbitrarily many
bytes with no newline makes a single `readline()` call buffer unbounded data
before it ever returns a line, which defeats the byte cap below regardless of
how small the kept tail is. Instead:

1. **Byte-bounded chunked read, not line-based.** Read `proc.stdout` in fixed
   chunks (e.g. `os.read(proc.stdout.fileno(), 4096)`), appending each chunk
   to a bounded buffer that enforces BOTH a byte cap (reuse the existing
   `GATE_OUTPUT_CAP` constant, confirmed present in `verification.py` =
   `2_000_000` — do not introduce a second, differently-sized cap) and keeps
   only the tail once the cap is exceeded (drop from the front, not the
   back).
2. **Last match wins, not first.** `SUMMARY_RE` is re-scanned against the
   *whole current buffer* after each chunk, and the function keeps the
   **last** match found so far, not the first — `test_run_gate_prints_one_
   summary_line`'s sibling expectations require the final summary line to
   win when a command legitimately prints more than one candidate line
   (e.g. a retry emits `EXIT 1` then later `EXIT 0`); stopping at the first
   match the moment it appears (the earlier draft's framing) would lock in a
   stale line a later chunk supersedes. A chunk boundary splitting a summary
   line mid-string self-corrects on the next chunk because the scan re-reads
   the whole buffer each time, not just the new bytes — no partial-line
   bookkeeping needed for this part.
3. **Deadline-driven draining of both pipes, with an explicit "done" rule.**
   `run_gate()`'s existing `timeout` parameter governs a wall-clock deadline
   (`time.monotonic() + timeout`), not a single blocking
   `communicate(timeout=timeout)` call. Drain **both** stdout and stderr
   against that deadline using `selectors.DefaultSelector` (registering both
   fds) — reading only stdout and leaving stderr's pipe undrained can
   deadlock if the child fills the stderr pipe buffer and blocks on a write
   the parent never services. **"Done" is child-reaped AND both pipes at EOF
   (both fds unregistered from the selector after a zero-length read)** —
   not merely "a match exists," since child exit does not guarantee its
   pipes have been fully drained and a later chunk could still supersede an
   already-found match per point 2. On reaching "done" before the deadline,
   stop and parse the final (last-match) result immediately — no need to
   wait out the full timeout. On deadline expiry with "done" not yet reached,
   terminate the process **group** (matching the existing kill behavior) and
   return the timeout outcome exactly as today (`test_run_gate_times_out_
   and_writes_nothing` must still pass; `test_verification.py:209-231`'s
   prompt-termination requirement is satisfied by "done" firing promptly once
   the child actually exits and both pipes drain, not by matching early).
4. Function body stays under 50 lines; extract the chunked-read/selector-
   drain loop into one small helper (`_drain_bounded(proc, cap, deadline) ->
   tuple[str, str]` or similar — exact shape at implementation) so `run_gate()`
   itself reads as deadline setup → drain → parse → write, not inlining the
   selector loop. No class, no generator utility module — one bounded helper
   function.

Tests (pre-existing, must still pass unchanged): `test_run_gate_streams_and_
keeps_tail` (new, PRD-listed, now specifically asserting a byte cap holds
even with no newlines in the output — add a fixture that writes > the cap in
one unbroken burst). `test_run_gate_prints_one_summary_line`,
`test_run_gate_unparseable_output_records_nothing`,
`test_run_gate_keeps_tail_so_a_late_summary_line_still_parses`,
`test_run_gate_times_out_and_writes_nothing`, `test_run_gate_writes_last_
verification_json_on_fresh_run` (existing, unchanged behavior). New:
`test_run_gate_drains_stderr_without_deadlock` (child writes enough to stderr
to fill a pipe buffer while stdout stays quiet; `run_gate()` must not hang).
`test_run_gate_uses_last_summary_line_not_first` (child prints `EXIT 1` then
later `EXIT 0`; the recorded result reflects `EXIT 0`).

### `verification.py` — rename-safe `reuse_verdict`

`_ancestor_and_clean()`'s porcelain-dirty check currently does
`dirty = [line[3:] for line in status.stdout.splitlines() ...]` then
`all(path.startswith(STORE_PREFIX) for path in dirty)`. For a rename, porcelain
format is `R  old/path -> new/path` (or, with `git status --porcelain=1`,
exactly that `->`-separated form on one line; `-z` mode uses NUL-separated
old/new pairs instead — confirm which mode this call already uses before
assuming either). Fix: when a dirty line's code starts with `R` (or contains
`" -> "`), split on `" -> "` and check the NEW path (the side after the arrow)
against `STORE_PREFIX`, not the raw `line[3:]` slice. Non-rename lines keep
today's `line[3:]` handling unchanged.

A rename must be checked on **both** endpoints, not the new path alone: a
rename from a production file (`src/module.py`) INTO the store
(`docs/dev/project-management/...`) would pass a new-path-only check even
though a real source file just vanished from its production location — that
is still a dirty, non-store-only change. Use `git status --porcelain=1 -z`
(NUL-separated records) rather than splitting on `" -> "` in the
human-readable format, which breaks on quoted/escaped filenames and any
filename that itself contains the literal string `" -> "`.

**Exact `-z` record shape** (per git's porcelain-v1 format, confirmed against
the live docs during review — this corrects the earlier draft, which got the
field order and the status-column width wrong): each record is `XY<SPACE
><path>\0`, where `XY` is **always exactly two status-code bytes** (either
may be blank/space, not just a single letter — do not strip a "leading status
space" as if the code were one byte), followed by one space, then the path,
then a NUL terminator. For a rename or copy (`X` or `Y` — **either** column —
equal to `R` or `C`), the record carries a **second** NUL-terminated field
immediately after the first: `XY<SPACE><new-path>\0<old-path>\0` — new path
first, old (source) path second. Only rename/copy records have this second
field; every other record is a single path field.

```python
def _dirty_path_is_in_store(new_path: str, old_path: str | None) -> bool:
    """A porcelain -z status record's STORE_PREFIX check: the path field
    (and the second, source path field when the record is a rename/copy)
    must both be under STORE_PREFIX, or the record counts as dirty outside
    the store."""
    paths = (new_path, old_path) if old_path else (new_path,)
    return all(p.startswith(STORE_PREFIX) for p in paths)
```

`_ancestor_and_clean()` splits the `-z` output on `\0` into a flat field
list, consuming one `XY<SPACE><path>` field per record normally, and ONE
EXTRA field (the source path) when `XY[0] in "RC" or XY[1] in "RC"` — getting
this consumption wrong desyncs every record after a missed rename/copy, so
the parser must check both status columns, not just assume `R` sits in a
fixed position. Requires `_dirty_path_is_in_store()` true for every record.
Docstring on `_ancestor_and_clean()` (or `reuse_verdict()`, whichever
currently states the clean-tree rule) gains one sentence: "a rename or copy
is judged by both its destination and source path — crossing the store
boundary in either direction, on either path, is dirty."

Test: `test_rename_out_of_store_is_not_clean` — a rename from a `STORE_PREFIX`
path to a non-store path → `reuse_verdict()` returns "stale"/not-clean, not
"reuse". `test_rename_into_store_from_production_is_not_clean` — a rename
from a non-store production path INTO the store → still not-clean (the
new-path-only version of this check would have wrongly passed it). New:
`test_copy_record_checks_both_paths` — a `-z` copy record (`C` in either
status column) with its source path outside the store → not-clean, proving
the parser doesn't only special-case the literal letter `R`.
`test_blank_status_column_does_not_desync_fields` — a record whose first
status column is blank (space) and second is `M` parses as one path field,
not two. Existing `test_reuse_verdict_ignores_dirty_paths_under_the_store`
must still pass (a rename fully inside the store, both paths under
`STORE_PREFIX`, still reads as clean).

### `triage.py` — emoji severities

```python
SEVERE = frozenset({"critical", "high", "🔴", "🟠"})
```

`qualifies()` itself is unchanged — it already does
`str(row.get("severity") or "").strip().casefold() in SEVERE`; casefold is a
no-op on emoji, so widening the set alone is sufficient, no comparison-logic
change.

Tests: `test_emoji_high_row_qualifies` (`severity: "🟠"` → `qualifies()` is
`True`). `test_emoji_critical_row_qualifies` (`severity: "🔴"` → `True`).
Re-run `test_severity_is_matched_case_insensitively` and
`test_non_qualifying_rows_create_no_file_and_count_as_skipped` unchanged to
confirm no regression (a row with, say, `severity: "medium"` or `"🟡"` must
stay non-qualifying).

### Skill prose: flags over hand-append

`skills/review-work-completion/SKILL.md`:

- Step 3's `review-stage` invocation synopsis gains `[--settled-ledger
  <path>] [--prior-findings <path>]` alongside the existing `--cycle-id
  --state --gate-command --roster [--since] [--replay-cmd]` list, with one
  sentence: pass the ledger path / prior-findings path you already loaded
  straight to this call; `review-stage` builds the ledger/incremental block
  itself for every **consensus/doubt-lens** persona that is supposed to see
  it. Blake's blind-lens prompt deliberately stays history-free — confirmed
  live (`review_stage.py:542-549`) that Blake's branch never reads
  `run["ledger"]`/`run["incremental"]`, by design (a blind reviewer isn't
  told what was already decided). The earlier draft's wording ("renders
  these blocks into every persona's prompt") is corrected here to name Blake
  as the standing exception, not imply a universal grant.
- Lines 216-218 ("Settled decisions — do not re-raise"): replace "review-stage
  takes no ledger input, so ... append this section with the Edit tool to
  Alice's, Bob's, Carl's and Eve's prompts" with: pass `--settled-ledger
  <path>` on the step-3 `review-stage` call; it renders the settled-decisions
  section into Alice's, Bob's, Carl's and Eve's prompts itself (Blake
  excluded, per the blind-lens contract above). Delete the per-persona
  Edit-tool instruction.
- Line 248 (incremental addendum): replace "review-stage renders no
  incremental addendum, so append it with the Edit tool" with: pass
  `--prior-findings <path>` on the same call.

### Doc format: all five lenses, `dispatch_rows:` block

`skills/review-work-completion/references/output-formats.md`'s `agents:`
example extends to:

```yaml
agents:
  alice: available
  blake: available
  bob: available
  carl: available
  eve: available
```

(any entry may instead be `disabled`/`unavailable`/`timeout` per the existing
status vocabulary — the example just needs to show all five keys so authors
know to write them). Add a new `dispatch_rows:` frontmatter block directly
below `agents:`, documenting the shape `_dispatch_outcomes()` already parses
(one entry per dispatch id, already a working reader with no documented
writer-side format — this fix is the missing format text, not a code change):

```yaml
dispatch_rows:
  <persona>: <dispatch-id>
```

Keyed by **persona**, not by dispatch id — `_dispatch_outcomes()`
(`review_close.py:117-126`) reads this block by iterating personas and looking
up each one's `agents:` status to decide the `--outcome` for *that persona's*
dispatch id; a block keyed the other way round (`<dispatch-id>: status`) would
have `close()` try to end a dispatch literally named `"unavailable"` and
default every real id's outcome to `"ok"`, leaving every real dispatch row
open. One sentence: `review_close.py`'s `close()` reads this block to map each
persona in `agents:` to the dispatch id it opened, then ends that id with the
outcome `_DISPATCH_OUTCOME[agents[persona]]`; every dispatch the session
opened must have its persona listed here before the review file is saved.

Test: `test_output_format_lists_dispatch_rows_and_all_lenses` — a doc-text
assertion (grep the rendered/raw markdown for `dispatch_rows:` and for each of
`alice, blake, bob, carl, eve` appearing under the `agents:` example).

### Cap-overflow severity is a word

`skills/run-autopilot/references/phase-review.md`'s cap-overflow
`deferred_decisions` append instruction (near the existing `"type":
"cap-overflow"` line) gains an explicit `severity` note matching the
lowercase-word convention already used by `triage.SEVERE`'s non-emoji members
and by this same file's other `severity: <"critical"|"high"|"medium"|"low">`
shape: "`severity`: the word (`critical`/`high`/`medium`/`low`), not the
emoji cell — unlike the Tail-sweep `chosen_findings` instruction elsewhere in
this file, which explicitly wants the emoji verbatim; this one wants the
word." Paired with `triage.SEVERE` gaining the emoji too, so already-written
emoji rows (existing ledger entries) still mint even though new rows should be
written as words going forward.

Test: `test_cap_out_severity_is_a_word` — a doc-text assertion that the
cap-overflow instruction names the word form, not the emoji.

### Delete the superseded hold stub

`docs/dev/project-management/prds/hold/00255-triage-resolve-base-is-a-second-diff-base-resol-v1.md`
exists today and names ledger key `36c2461f9d70` (the same finding this PRD's
"One diff-base resolver" feature fixes). Task: re-check at execution time that
the file exists and names that ledger key; if so, delete it (its fix has
landed in this PRD, so no separate hold-stub session needs it); if the file is
absent or names a different key, skip the delete and report rather than
erroring the PRD.

Test: `test ! -e docs/dev/project-management/prds/hold/00255-triage-resolve-base-is-a-second-diff-base-resol-v1.md`.

## Data flow

`dev/bin/release-checks` already runs several real pytest invocations plus a
shell harness (confirmed by the PRD's measured "2564 real" test count); today
those real results are discarded and a fabricated line is printed instead.
The fixed flow: each block runs and reports its own counts → the script
accumulates them into one `PASS n FAIL n SKIP n EXIT c` line (§ "real test
counts" above) → `verification.run_gate()` drains that output under a byte
cap and a deadline (§ "bounded, streaming `run_gate`" above), scans for the
line via `SUMMARY_RE`, and on match writes `passed`/`failed`/`skipped` to
`last-verification.json`; on no match at all, writes nothing (the unchanged
contract). `gate.py`'s `--findings` cross-check — mandatory inside
`review_close.close()`, optional on the standalone `autopilot gate` verb (§
"findings JSON cross-check" above) — reads the same review file's
`## Consolidated Findings` bullet-list section plus the given findings data
and diffs row sets; a mismatch exits 2 (naming the first mismatched row),
distinct from `check()`'s own exit-1 malformed-input path.

## Reuse inventory

- `_PERSONA_LENS`, `_LENS_STATUS` (`review_close.py`) — already generic over
  all five personas; "Close every lens" needs no change here, only to the
  review-file format that feeds it.
- `_SCOPE_RE` (`review_stage.py`) — already parses the context file's resolved
  base for Eve; reused as the sole base resolver instead of maintaining
  `resolve_base()` as a second implementation.
- `SUMMARY_RE` (`verification.py`) — unchanged; only its input (the line
  `release-checks` prints) becomes truthful.
- nothing found for "streaming subprocess output with a bounded tail buffer"
  as a named existing helper; greps tried: `rg "deque" skills/run-autopilot/cli`,
  `rg "iter_lines|readline" skills/run-autopilot/cli`, `rg "def.*stream"
  skills/run-autopilot/cli` — none hit an existing generic streaming helper,
  so `run_gate()`'s rewrite inlines a small bounded loop rather than importing
  one.

## Alternatives considered

1. **Smallest-diff (chosen for 4 of 5 capabilities):** fix the exact lines the
   PRD cites, add the exact tests the PRD's acceptance criteria name, touch no
   other code path. Rejected-as-insufficient only for `run_gate()`, where the
   PRD's explicit "under 50 lines" acceptance criterion forces a structural
   rewrite (buffered → streaming) rather than a line-level patch, since the
   current function is 75 lines doing one undifferentiated buffer-then-parse
   pass.
2. **Add a shared `severity_matches()` helper used by both `triage.py` and
   `gate.py`'s new cross-check**, instead of each doing its own
   normalize-and-compare. Rejected: `triage.qualifies()`'s comparison
   (`casefold() in SEVERE`) and the cross-check's comparison (structural
   equality of normalized rows via `gate.py`'s own local normalizer) answer
   different questions — "is this row severe enough to
   mint" vs. "do these two tables agree" — forcing them through one helper
   would be a speculative abstraction over two call sites that happen to both
   touch severity strings.
3. **Rewrite `release-checks`'s check blocks into a Python test file** so
   `run_gate()`'s `SUMMARY_RE` parsing isn't needed at all. Rejected: out of
   scope — the PRD's fix is "report real counts", not "stop being a bash
   script"; rewriting the harness language is a much larger diff for the same
   acceptance criteria.

## Risks & edge cases

- **Count parsing stays brittle across pytest and the bash harness** (PRD's
  own named risk): the design pins the exact line `release-checks` must print
  and the exact regex that parses it; an unparseable block yields `null`
  (verified by `test_run_gate_unparseable_output_records_nothing`, pre-
  existing), never a guessed number.
- **`resolve_base()`'s deletion drops the `since` parameter's only live use**:
  if a future caller wants an explicit base override independent of
  `gather-context.sh`'s recorded scope, that capability is gone. Likely next
  change: if that need arises, the override should write into the context
  file's `_Diff scope:` line itself (one resolver, overridable at its single
  source) rather than resurrecting a second resolver.
- **Widening `triage.SEVERE` to include emoji is a permanent compatibility
  shim** for already-written ledger rows; the phase-review.md fix makes word
  severity the documented form going forward, so the emoji membership should
  not need removing later, but it does mean two spellings of "critical" stay
  valid indefinitely. Likely next change if this is revisited: a ledger
  migration that rewrites historical emoji rows to words, letting `SEVERE`
  shrink back to one spelling each — not needed now, flagging only.
- **`gate.py`'s standalone `--findings` flag is optional**, so a caller that
  invokes `autopilot gate --review-file` directly without `--findings` gets
  no cross-check — that path stays opt-in by design (not every gate caller
  has a findings JSON in hand). This is separate from `close()`'s own path,
  which this design makes mandatory: `close()` always has `chosen_findings`
  in hand already, so its cross-check is not optional and not deferred to a
  later PRD (see "Wiring into `review_close.close()`" above) — the
  mandatory/opt-in split is between the two call sites, not a gap left for
  later.

## Test strategy outline

Per-module unit tests exactly as named in the PRD's Phase 0-2 acceptance
criteria (listed inline next to each contract above). Exit criteria are the
PRD's own: Phase 0 — `python3 -m pytest
skills/run-autopilot/cli/test_triage.py
skills/run-autopilot/cli/test_verification.py`; Phase 1 — the four touched
test files (`test_review_close.py`, `test_review_stage.py`, `test_gate.py`,
plus `test_verification.py` if its rename-safety test lands in Phase 1 instead
of Phase 0 — follow the PRD's own phase split); Phase 2 — `bash
dev/bin/release-checks` exits 0, plus the three doc-text assertions. No new
test infrastructure; every new test is a function in an existing test file
using that file's existing fixture helpers.

## Review log

Non-blockers and questions recorded, not fixed (the two dispatch-2
non-blockers below were incidentally subsumed by the blocker-6 porcelain-
parsing fix and the SKILL.md Blake-exclusion fix, but are listed here for
the record since neither was a blocker obligation):

- (dispatch 1 re-run, non-blocker) `GATE_OUTPUT_CAP` ambiguity: whether the
  cap is combined across stdout+stderr or per-stream is not pinned by this
  design. Resolve at implementation by reading the constant's existing
  docstring/usage; not load-bearing for any acceptance test.
- (dispatch 1 re-run, question — resolved) the Risks section's framing of
  `--findings` auto-wiring as deferred future work, vs. the design's own
  "Wiring into `review_close.close()`" section already making it mandatory
  in-process — fixed: Risks section rewritten to state the mandatory/opt-in
  split directly instead of implying deferral.
- (dispatch 2, non-blocker — addressed) rename-safety checking only the
  destination path: superseded by blocker 6's both-status-column,
  both-path-field fix in dispatch 3, which already requires both endpoints.
- (dispatch 2, non-blocker — addressed) SKILL.md implying ledger context
  reaches every persona: fixed inline (Blake's blind-lens exclusion named
  explicitly) during the dispatch-2 fix pass.

dispatch 1 (claude): cardinal-sin 0, blocker 1, non-blocker 0, question 0 weak
dispatch 1 (claude): cardinal-sin 0, blocker 1, non-blocker 2, question 1
dispatch 2 (codex): cardinal-sin 1, blocker 6, non-blocker 2, question 0
dispatch 3 (codex): cardinal-sin 0, blocker 7, non-blocker 0, question 0
